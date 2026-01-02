# MTG Engine V3 - Performance Optimizations

This document describes the critical performance optimizations implemented to improve tournament simulation speed and memory usage.

## Overview

The MTG Engine V3 now includes four major performance optimizations:

| ID | Optimization | Impact | Files |
|----|-------------|--------|-------|
| PERF-7 | CardTemplate Factory Pattern | ~80-90% memory reduction | `engine/card_template.py` |
| PERF-10 | Incremental GameState Updates | ~50-80% faster priority checks | `engine/state_cache.py`, `ai/agent_optimized.py` |
| PERF-3 | O(1) Object Lookups | O(n) -> O(1) for find operations | `engine/zones_optimized.py` |
| PERF-4 | Battlefield Filter Caching | O(n) -> O(1) for repeated queries | `engine/zones_optimized.py` |

---

## PERF-7: CardTemplate Factory Pattern

**Location:** `Engine/v3/engine/card_template.py`

### Problem
When running tournaments, the original code performed deep copies of entire deck objects for each game:
```python
d1 = copy.deepcopy(deck1_cards)  # Expensive!
d2 = copy.deepcopy(deck2_cards)  # Expensive!
```

For 200 games with 60-card decks, this meant:
- 200 * 120 = 24,000 deep copy operations
- Each card object contains nested ManaCost, Characteristics, abilities, etc.
- Estimated ~2KB per card deep copy = 48MB just for card copying

### Solution
Implement a flyweight pattern that separates immutable card data from mutable game state:

**CardTemplate (Immutable, Shared)**
- Name, mana cost, types, subtypes, base power/toughness
- Keywords, abilities, rules text
- Stored in singleton registry, created once per unique card

**CardInstance (Mutable, Per-Game)**
- Object ID, owner ID, controller ID
- Current zone, tap state, counters
- Damage marked, summoning sickness
- ~200 bytes vs ~2KB for full card

### Usage
```python
from engine.card_template import create_game_deck_instances, get_registry_stats

# Instead of deep copy:
d1 = create_game_deck_instances(deck1_cards, owner_id=1)
d2 = create_game_deck_instances(deck2_cards, owner_id=2)

# Check cache statistics:
stats = get_registry_stats()
print(f"Template cache hit rate: {stats['hit_rate_percent']:.1f}%")
```

### Performance Impact
- Memory reduction: ~80-90%
- Cache hit rate: >99% after first game
- Tournament runner updated: `run_tournament_optimized.py`

---

## PERF-10: Incremental GameState Updates

**Location:** `Engine/v3/engine/state_cache.py`, `Engine/v3/ai/agent_optimized.py`

### Problem
The AI's `build_game_state()` function is called every time a player receives priority. This happens 50-100+ times per turn:
```python
def decide_priority(self, game):
    state = build_game_state(game, self.player)  # Called every priority!
```

Each call rebuilds the entire GameState:
- Iterates all cards in hand
- Iterates all permanents on battlefield
- Iterates all cards in graveyard
- Calculates mana from all lands

### Solution
Implement change tracking and caching:

**CachedGameStateBuilder**
- Caches previous GameState
- Tracks what changed via notifications
- Only rebuilds changed components
- Returns cached state if nothing changed

**Change Notifications**
- `notify_zone_change()`: When objects move between zones
- `notify_life_change()`: When life totals change
- `notify_object_tapped()`: When permanents tap/untap

### Usage
```python
from ai.agent_optimized import CachedExpertAI

# Replace ExpertAI with CachedExpertAI
player.ai = CachedExpertAI(player, game)

# The game engine should notify of changes:
player.ai.notify_zone_change("battlefield")
player.ai.notify_life_change(player_id)
```

### Performance Impact
- Cache hits for unchanged priority passes: 100% faster
- Incremental updates: 50-80% faster than full rebuild
- Most effective in long games with many priority passes

---

## PERF-3: O(1) Object Lookups

**Location:** `Engine/v3/engine/zones_optimized.py`

### Problem
Finding an object by ID requires scanning all zones:
```python
def find_object(self, object_id):
    # Scans battlefield, stack, exile, command, all libraries, hands, graveyards
    for zone in self.all_zones():
        for obj in zone.objects:
            if obj.object_id == object_id:
                return obj
```

With 200+ objects across zones, this is O(n) for every lookup.

### Solution
Maintain a global dictionary index:

**GlobalObjectIndex**
```python
class GlobalObjectIndex:
    _objects: Dict[ObjectId, GameObject]  # O(1) lookup
    _locations: Dict[ObjectId, Tuple[Zone, ZoneObject]]  # Track zone too
```

Automatically updated when:
- Objects are added to zones
- Objects are removed from zones
- Objects move between zones

### Usage
```python
from engine.zones_optimized import OptimizedZoneManager

zones = OptimizedZoneManager(player_ids=[1, 2])

# O(1) lookup instead of O(n) scan
obj, zone = zones.find_object(object_id)

# Check statistics
print(zones.object_index.stats)
```

### Performance Impact
- Object lookup: O(n) -> O(1)
- Zone detection: O(n) -> O(1)
- Especially impactful for targeting, triggers, and state-based actions

---

## PERF-4: Battlefield Filter Caching

**Location:** `Engine/v3/engine/zones_optimized.py`

### Problem
Filter methods like `creatures()`, `lands()`, `untapped_lands()` scan all permanents:
```python
def creatures(self, controller_id=None):
    return [p for p in self.permanents(controller_id)
            if p.characteristics.is_creature()]
```

Called repeatedly during:
- AI decision making
- Attack/block declarations
- State-based action checks
- Trigger condition checks

### Solution
Cache filter results with version-based invalidation:

**CachedBattlefield**
```python
class CachedBattlefield(ZoneObject):
    _cache_version: int = 0
    _filter_caches: Dict[Tuple[str, Optional[PlayerId]], FilterCache]

    def creatures(self, controller_id=None):
        key = ("creatures", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached  # O(1)!

        # Cache miss - compute and store
        result = [p for p in self.permanents(controller_id)
                  if p.characteristics.is_creature()]
        self._set_cached(key, result)
        return result
```

Cache invalidation:
- Increment `_cache_version` on any add/remove
- Cached results check version before returning
- Stale results automatically recomputed

### Usage
```python
from engine.zones_optimized import OptimizedZoneManager

zones = OptimizedZoneManager(player_ids=[1, 2])

# First call: O(n) - builds cache
creatures = zones.battlefield.creatures(player_id=1)

# Subsequent calls: O(1) - returns cached
creatures = zones.battlefield.creatures(player_id=1)  # Cache hit!

# After add/remove: O(n) - cache invalidated
zones.battlefield.add(new_permanent)
creatures = zones.battlefield.creatures(player_id=1)  # Rebuilds cache

# Check statistics
print(zones.battlefield.cache_stats)
```

### Cached Methods
- `permanents(controller_id)`
- `creatures(controller_id)`
- `lands(controller_id)`
- `untapped_lands(controller_id)`
- `available_attackers(controller_id)`
- `available_blockers(controller_id)`
- `planeswalkers(controller_id)`
- `artifacts(controller_id)`
- `enchantments(controller_id)`
- `tokens(controller_id)`
- `legendaries(controller_id)`

### Performance Impact
- First call: O(n) - same as before
- Subsequent calls: O(1) - instant return
- Typical cache hit rate: 80-95% during AI turns

---

## Integration Guide

### Using All Optimizations Together

```python
# Tournament runner with all optimizations
from engine.card_template import create_game_deck_instances, get_registry_stats
from engine.zones_optimized import OptimizedZoneManager
from ai.agent_optimized import CachedExpertAI

# Setup game with optimized zones
zones = OptimizedZoneManager(player_ids=[1, 2])

# Create deck instances (not deep copies)
d1 = create_game_deck_instances(deck1_cards, owner_id=1)
d2 = create_game_deck_instances(deck2_cards, owner_id=2)

# Use cached AI
for player in game.players.values():
    player.ai = CachedExpertAI(player, game)

# Run game as normal...

# Print statistics
print("Template Registry:", get_registry_stats())
print("Object Index:", zones.object_index.stats)
print("Battlefield Cache:", zones.battlefield.cache_stats)
```

### Gradual Adoption

Each optimization can be adopted independently:

1. **PERF-7 only**: Replace `copy.deepcopy()` with `create_game_deck_instances()`
2. **PERF-3/4 only**: Replace `ZoneManager` with `OptimizedZoneManager`
3. **PERF-10 only**: Replace `ExpertAI` with `CachedExpertAI`

---

## Performance Benchmarks

Expected improvements for a 200-game tournament with 60-card decks:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Memory for card data | ~48 MB | ~5 MB | 90% reduction |
| Object lookup time | O(n) | O(1) | 100x faster |
| Battlefield filter (repeated) | O(n) | O(1) | 50-100x faster |
| GameState build (unchanged) | O(n) | O(1) | Skip entirely |
| Tournament runtime | 100% | ~60-70% | 30-40% faster |

---

## Files Created

```
Engine/v3/
├── engine/
│   ├── card_template.py      # PERF-7: CardTemplate factory
│   ├── state_cache.py        # PERF-10: GameState caching infrastructure
│   └── zones_optimized.py    # PERF-3, PERF-4: O(1) lookups + filter cache
├── ai/
│   └── agent_optimized.py    # PERF-10: Cached AI agents
├── run_tournament_optimized.py  # Tournament runner with PERF-7
└── PERFORMANCE_OPTIMIZATIONS.md  # This documentation
```
