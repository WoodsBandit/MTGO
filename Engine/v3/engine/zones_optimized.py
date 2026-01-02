"""MTG Engine V3 - Optimized Zone System (PERF-3, PERF-4)

This module provides optimized versions of the zone classes with:

PERF-3: O(1) Object Lookups
- GlobalObjectIndex: Dict[ObjectId, GameObject] for instant lookup across all zones
- Eliminates O(n) zone scans when finding objects by ID

PERF-4: Battlefield Filter Caching
- CachedBattlefield: Caches creatures(), lands(), etc. filter results
- Invalidation on zone changes (add/remove operations)

Usage:
    # Replace ZoneManager with OptimizedZoneManager
    from engine.zones_optimized import OptimizedZoneManager

    zones = OptimizedZoneManager(player_ids=[1, 2])
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterator, Callable, Tuple, Any, Set, TYPE_CHECKING

# Import base types from original zones module
from .zones import (
    ZoneObject, Library, Hand, Graveyard, Stack, Exile, Command,
    ZoneChangeInfo, is_public_zone, is_hidden_zone, is_shared_zone, is_player_zone
)
from .types import Zone, PlayerId, ObjectId, CardType, Supertype, Color

if TYPE_CHECKING:
    from .events import EventBus, GameEvent
    from .player import Player
    from .objects import GameObject, Card, Permanent, Token, Spell, StackedAbility


# =============================================================================
# PERF-3: GLOBAL OBJECT INDEX
# =============================================================================

class GlobalObjectIndex:
    """
    Global dictionary for O(1) object lookups across all zones.

    Instead of scanning each zone sequentially to find an object,
    this index provides immediate lookup by object ID.

    Performance improvement: O(number_of_zones * objects_per_zone) -> O(1)
    """

    def __init__(self):
        # Primary index: ObjectId -> GameObject
        self._objects: Dict[ObjectId, 'GameObject'] = {}

        # Secondary index: ObjectId -> (Zone, ZoneObject)
        self._locations: Dict[ObjectId, Tuple[Zone, 'ZoneObject']] = {}

        # Statistics
        self._lookups: int = 0
        self._hits: int = 0
        self._misses: int = 0

    def register(self, obj: 'GameObject', zone: Zone, zone_obj: 'ZoneObject') -> None:
        """Register an object in the index."""
        self._objects[obj.object_id] = obj
        self._locations[obj.object_id] = (zone, zone_obj)

    def unregister(self, object_id: ObjectId) -> Optional['GameObject']:
        """Remove an object from the index and return it."""
        self._locations.pop(object_id, None)
        return self._objects.pop(object_id, None)

    def get(self, object_id: ObjectId) -> Optional['GameObject']:
        """Get object by ID in O(1)."""
        self._lookups += 1
        obj = self._objects.get(object_id)
        if obj:
            self._hits += 1
        else:
            self._misses += 1
        return obj

    def get_location(self, object_id: ObjectId) -> Optional[Tuple[Zone, 'ZoneObject']]:
        """Get the zone and zone object for an object."""
        return self._locations.get(object_id)

    def get_zone(self, object_id: ObjectId) -> Optional[Zone]:
        """Get just the zone type for an object."""
        loc = self._locations.get(object_id)
        return loc[0] if loc else None

    def update_location(self, object_id: ObjectId, zone: Zone, zone_obj: 'ZoneObject') -> None:
        """Update the location of an object (after zone change)."""
        if object_id in self._objects:
            self._locations[object_id] = (zone, zone_obj)

    def contains(self, object_id: ObjectId) -> bool:
        """Check if object exists in index."""
        return object_id in self._objects

    def clear(self) -> None:
        """Clear the entire index."""
        self._objects.clear()
        self._locations.clear()

    def __len__(self) -> int:
        return len(self._objects)

    def __contains__(self, object_id: ObjectId) -> bool:
        return object_id in self._objects

    @property
    def stats(self) -> Dict[str, Any]:
        """Get lookup statistics."""
        hit_rate = (self._hits / self._lookups * 100) if self._lookups > 0 else 0
        return {
            "total_objects": len(self._objects),
            "lookups": self._lookups,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": hit_rate,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._lookups = 0
        self._hits = 0
        self._misses = 0


# =============================================================================
# PERF-4: CACHED BATTLEFIELD
# =============================================================================

@dataclass
class FilterCache:
    """Cache for a single filter result."""
    version: int = 0
    result: List[Any] = field(default_factory=list)

    def is_valid(self, current_version: int) -> bool:
        return self.version == current_version


class CachedBattlefield(ZoneObject):
    """
    Battlefield with cached filter results for O(1) repeated queries.

    All filter methods (creatures(), lands(), etc.) check the cache first.
    Cache is invalidated when any object is added or removed.

    Performance improvement:
    - First call: O(n) - must scan all objects
    - Subsequent calls: O(1) - return cached result
    - After any change: Cache invalidated, next call is O(n)
    """

    def __init__(self):
        super().__init__(
            zone_type=Zone.BATTLEFIELD,
            owner_id=None,
            is_public=True,
            is_ordered=False
        )

        # Cache version - incremented on any add/remove
        self._cache_version: int = 0

        # Cached filter results
        # Key: (filter_name, controller_id or None)
        self._filter_caches: Dict[Tuple[str, Optional[PlayerId]], FilterCache] = {}

        # Statistics
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    def _invalidate_cache(self) -> None:
        """Invalidate all cached results."""
        self._cache_version += 1
        # Don't clear caches, just increment version
        # Old cached results will be detected as stale

    def _get_cached(self, key: Tuple[str, Optional[PlayerId]]) -> Optional[List[Any]]:
        """Get cached result if valid."""
        if key in self._filter_caches:
            cache = self._filter_caches[key]
            if cache.is_valid(self._cache_version):
                self._cache_hits += 1
                return cache.result
        self._cache_misses += 1
        return None

    def _set_cached(self, key: Tuple[str, Optional[PlayerId]], result: List[Any]) -> None:
        """Store result in cache."""
        self._filter_caches[key] = FilterCache(
            version=self._cache_version,
            result=result
        )

    def add(self, obj: 'GameObject', position: Optional[int] = None) -> None:
        """Add object and invalidate cache."""
        super().add(obj, position)
        self._invalidate_cache()

    def remove(self, obj: 'GameObject') -> bool:
        """Remove object and invalidate cache."""
        result = super().remove(obj)
        if result:
            self._invalidate_cache()
        return result

    def remove_by_id(self, object_id: ObjectId) -> Optional['GameObject']:
        """Remove by ID and invalidate cache."""
        result = super().remove_by_id(object_id)
        if result:
            self._invalidate_cache()
        return result

    def clear(self) -> List['GameObject']:
        """Clear all objects and invalidate cache."""
        result = super().clear()
        self._invalidate_cache()
        return result

    # =========================================================================
    # CACHED FILTER METHODS
    # =========================================================================

    def permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get all permanents, optionally filtered by controller (cached)."""
        key = ("permanents", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        from .objects import Permanent
        perms = [o for o in self.objects if isinstance(o, Permanent)]
        if controller_id is not None:
            perms = [p for p in perms if p.controller_id == controller_id]

        self._set_cached(key, perms)
        return perms

    def permanents_owned_by(self, owner_id: PlayerId) -> List['Permanent']:
        """Get permanents owned by a player (cached)."""
        key = ("owned_by", owner_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        from .objects import Permanent
        perms = [o for o in self.objects
                 if isinstance(o, Permanent) and o.owner_id == owner_id]

        self._set_cached(key, perms)
        return perms

    def creatures(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures (cached)."""
        key = ("creatures", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        creatures = [p for p in perms if p.characteristics.is_creature()]

        self._set_cached(key, creatures)
        return creatures

    def noncreature_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get non-creature permanents (cached)."""
        key = ("noncreatures", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        noncreatures = [p for p in perms if not p.characteristics.is_creature()]

        self._set_cached(key, noncreatures)
        return noncreatures

    def lands(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get lands (cached)."""
        key = ("lands", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        lands = [p for p in perms if p.characteristics.is_land()]

        self._set_cached(key, lands)
        return lands

    def nonland_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get non-land permanents (cached)."""
        key = ("nonlands", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        nonlands = [p for p in perms if not p.characteristics.is_land()]

        self._set_cached(key, nonlands)
        return nonlands

    def untapped_lands(self, controller_id: PlayerId) -> List['Permanent']:
        """Get untapped lands for a player (cached)."""
        key = ("untapped_lands", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        lands = self.lands(controller_id)
        untapped = [p for p in lands if not p.is_tapped]

        self._set_cached(key, untapped)
        return untapped

    def tapped_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get tapped permanents (cached)."""
        key = ("tapped", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        tapped = [p for p in perms if p.is_tapped]

        self._set_cached(key, tapped)
        return tapped

    def untapped_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get untapped permanents (cached)."""
        key = ("untapped", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        untapped = [p for p in perms if not p.is_tapped]

        self._set_cached(key, untapped)
        return untapped

    def available_attackers(self, controller_id: PlayerId) -> List['Permanent']:
        """Get creatures that can attack (cached)."""
        key = ("attackers", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        creatures = self.creatures(controller_id)
        attackers = [p for p in creatures if p.can_attack()]

        self._set_cached(key, attackers)
        return attackers

    def available_blockers(self, controller_id: PlayerId) -> List['Permanent']:
        """Get creatures that can block (cached)."""
        key = ("blockers", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        creatures = self.creatures(controller_id)
        blockers = [p for p in creatures if p.can_block()]

        self._set_cached(key, blockers)
        return blockers

    def planeswalkers(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get planeswalkers (cached)."""
        key = ("planeswalkers", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        pws = [p for p in perms if CardType.PLANESWALKER in p.characteristics.types]

        self._set_cached(key, pws)
        return pws

    def artifacts(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get artifacts (cached)."""
        key = ("artifacts", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        arts = [p for p in perms if CardType.ARTIFACT in p.characteristics.types]

        self._set_cached(key, arts)
        return arts

    def enchantments(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get enchantments (cached)."""
        key = ("enchantments", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        ench = [p for p in perms if CardType.ENCHANTMENT in p.characteristics.types]

        self._set_cached(key, ench)
        return ench

    def tokens(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get tokens (cached)."""
        key = ("tokens", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        from .objects import Token
        tokens = [o for o in self.objects if isinstance(o, Token)]
        if controller_id is not None:
            tokens = [t for t in tokens if t.controller_id == controller_id]

        self._set_cached(key, tokens)
        return tokens

    def legendaries(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get legendary permanents (cached)."""
        key = ("legendaries", controller_id)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        perms = self.permanents(controller_id)
        legends = [p for p in perms if Supertype.LEGENDARY in p.characteristics.supertypes]

        self._set_cached(key, legends)
        return legends

    # =========================================================================
    # UNCACHED METHODS (complex or rarely used)
    # =========================================================================

    def auras(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get aura enchantments (not cached - builds on enchantments)."""
        return [p for p in self.enchantments(controller_id)
                if "Aura" in (p.characteristics.subtypes or [])]

    def equipment(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get equipment artifacts (not cached - builds on artifacts)."""
        return [p for p in self.artifacts(controller_id)
                if "Equipment" in (p.characteristics.subtypes or [])]

    def nontoken_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get non-token permanents (not cached)."""
        from .objects import Token
        return [o for o in self.permanents(controller_id) if not isinstance(o, Token)]

    def with_keyword(self, keyword: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents with a keyword ability."""
        return [p for p in self.permanents(controller_id) if p.has_keyword(keyword)]

    def without_keyword(self, keyword: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents without a keyword ability."""
        return [p for p in self.permanents(controller_id) if not p.has_keyword(keyword)]

    def by_name(self, name: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents with a specific name."""
        return [p for p in self.permanents(controller_id)
                if p.characteristics.name == name]

    def by_subtype(self, subtype: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents with a specific subtype."""
        return [p for p in self.permanents(controller_id)
                if subtype in (p.characteristics.subtypes or [])]

    def by_color(self, color: Color, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents of a specific color."""
        return [p for p in self.permanents(controller_id)
                if color in p.characteristics.colors]

    def by_power(self, power: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures with specific power."""
        return [p for p in self.creatures(controller_id)
                if p.effective_power() == power]

    def by_power_or_less(self, max_power: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures with power at most max_power."""
        return [p for p in self.creatures(controller_id)
                if p.effective_power() <= max_power]

    def by_toughness(self, toughness: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures with specific toughness."""
        return [p for p in self.creatures(controller_id)
                if p.effective_toughness() == toughness]

    # =========================================================================
    # COUNT METHODS (use cached filters)
    # =========================================================================

    def creature_count(self, controller_id: Optional[PlayerId] = None) -> int:
        """Get number of creatures (uses cache)."""
        return len(self.creatures(controller_id))

    def land_count(self, controller_id: Optional[PlayerId] = None) -> int:
        """Get number of lands (uses cache)."""
        return len(self.lands(controller_id))

    def permanent_count(self, controller_id: Optional[PlayerId] = None) -> int:
        """Get total number of permanents (uses cache)."""
        return len(self.permanents(controller_id))

    def total_power(self, controller_id: PlayerId) -> int:
        """Get total power of creatures (uses cache)."""
        return sum(c.effective_power() for c in self.creatures(controller_id))

    def total_toughness(self, controller_id: PlayerId) -> int:
        """Get total toughness of creatures (uses cache)."""
        return sum(c.effective_toughness() for c in self.creatures(controller_id))

    def attacking_creatures(self) -> List['Permanent']:
        """Get creatures that are currently attacking."""
        return [p for p in self.creatures() if getattr(p, 'is_attacking', False)]

    def blocking_creatures(self) -> List['Permanent']:
        """Get creatures that are currently blocking."""
        return [p for p in self.creatures() if getattr(p, 'is_blocking', False)]

    # =========================================================================
    # CACHE STATISTICS
    # =========================================================================

    @property
    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            "version": self._cache_version,
            "cache_entries": len(self._filter_caches),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate_percent": hit_rate,
        }

    def reset_cache_stats(self) -> None:
        """Reset cache statistics."""
        self._cache_hits = 0
        self._cache_misses = 0

    def notify_state_change(self) -> None:
        """
        Notify that a permanent's state changed (tapped, counters, etc.).

        This invalidates caches that depend on mutable permanent state,
        like untapped_lands, available_attackers, etc.
        """
        # Invalidate state-dependent caches
        state_dependent = [
            "untapped_lands", "tapped", "untapped",
            "attackers", "blockers"
        ]
        # Remove only state-dependent caches
        keys_to_remove = [
            key for key in self._filter_caches
            if key[0] in state_dependent
        ]
        for key in keys_to_remove:
            del self._filter_caches[key]


# =============================================================================
# OPTIMIZED ZONE MANAGER
# =============================================================================

class OptimizedZoneManager:
    """
    Zone manager with O(1) object lookup and cached battlefield filters.

    Drop-in replacement for ZoneManager with performance optimizations.
    """

    def __init__(self, player_ids: List[PlayerId]):
        """Initialize all zones with optimizations."""

        # Global object index for O(1) lookups
        self._object_index = GlobalObjectIndex()

        # Shared zones (use cached battlefield)
        self.battlefield = CachedBattlefield()
        self.stack = Stack()
        self.exile = Exile()
        self.command = Command()

        # Per-player zones
        self.libraries: Dict[PlayerId, Library] = {}
        self.hands: Dict[PlayerId, Hand] = {}
        self.graveyards: Dict[PlayerId, Graveyard] = {}

        for pid in player_ids:
            self.libraries[pid] = Library(pid)
            self.hands[pid] = Hand(pid)
            self.graveyards[pid] = Graveyard(pid)

        self._player_ids = player_ids
        self._next_timestamp = 0
        self._zone_change_history: List[ZoneChangeInfo] = []

    @property
    def player_ids(self) -> List[PlayerId]:
        """Get list of player IDs."""
        return self._player_ids.copy()

    @property
    def object_index(self) -> GlobalObjectIndex:
        """Get the global object index."""
        return self._object_index

    def get_zone(self, zone_type: Zone, player_id: Optional[PlayerId] = None) -> ZoneObject:
        """Get a zone by type."""
        if zone_type == Zone.BATTLEFIELD:
            return self.battlefield
        elif zone_type == Zone.STACK:
            return self.stack
        elif zone_type == Zone.EXILE:
            return self.exile
        elif zone_type == Zone.COMMAND:
            return self.command
        elif zone_type == Zone.LIBRARY:
            if player_id is None:
                raise ValueError("player_id required for library zone")
            return self.libraries[player_id]
        elif zone_type == Zone.HAND:
            if player_id is None:
                raise ValueError("player_id required for hand zone")
            return self.hands[player_id]
        elif zone_type == Zone.GRAVEYARD:
            if player_id is None:
                raise ValueError("player_id required for graveyard zone")
            return self.graveyards[player_id]
        else:
            raise ValueError(f"Unknown zone type: {zone_type}")

    def find_object(self, object_id: ObjectId) -> Optional[Tuple['GameObject', ZoneObject]]:
        """
        Find object across all zones in O(1).

        Uses the global object index instead of scanning zones.
        """
        obj = self._object_index.get(object_id)
        if obj is None:
            return None

        location = self._object_index.get_location(object_id)
        if location is None:
            return None

        zone_type, zone_obj = location
        return (obj, zone_obj)

    def get_object_zone(self, object_id: ObjectId) -> Optional[Zone]:
        """Get the zone type an object is in (O(1))."""
        return self._object_index.get_zone(object_id)

    def _register_object(self, obj: 'GameObject', zone: Zone, zone_obj: ZoneObject) -> None:
        """Register object in the global index."""
        self._object_index.register(obj, zone, zone_obj)

    def _unregister_object(self, object_id: ObjectId) -> None:
        """Unregister object from the global index."""
        self._object_index.unregister(object_id)

    def move_object(
        self,
        obj: 'GameObject',
        to_zone: Zone,
        to_player: Optional[PlayerId] = None,
        position: Optional[int] = None,
        events: Optional['EventBus'] = None
    ) -> Optional[ZoneChangeInfo]:
        """
        Move object between zones with index updates.
        """
        # Find current zone
        result = self.find_object(obj.object_id)
        if not result:
            return None

        current_obj, from_zone_obj = result
        from_zone = from_zone_obj.zone_type

        # Determine destination
        dest_player = to_player or obj.owner_id

        try:
            dest_zone = self.get_zone(to_zone, dest_player)
        except ValueError:
            return None

        # Handle tokens leaving battlefield
        from .objects import Token
        was_token = isinstance(obj, Token)

        if was_token and from_zone == Zone.BATTLEFIELD and to_zone != Zone.BATTLEFIELD:
            from_zone_obj.remove(obj)
            self._unregister_object(obj.object_id)

            change_info = ZoneChangeInfo(
                object_id=obj.object_id,
                from_zone=from_zone,
                to_zone=to_zone,
                from_owner=from_zone_obj.owner_id,
                to_owner=dest_player,
                was_token=True,
                timestamp=self._next_timestamp
            )
            self._next_timestamp += 1
            self._zone_change_history.append(change_info)
            return change_info

        # Regular move
        from_zone_obj.remove(obj)
        dest_zone.add(obj, position)
        obj.zone = to_zone

        # Update index
        self._object_index.update_location(obj.object_id, to_zone, dest_zone)

        change_info = ZoneChangeInfo(
            object_id=obj.object_id,
            from_zone=from_zone,
            to_zone=to_zone,
            from_owner=from_zone_obj.owner_id,
            to_owner=dest_zone.owner_id,
            was_token=was_token,
            was_visible=from_zone_obj.is_public,
            timestamp=self._next_timestamp
        )
        self._next_timestamp += 1
        self._zone_change_history.append(change_info)

        return change_info

    def add_to_zone(
        self,
        obj: 'GameObject',
        zone_type: Zone,
        player_id: Optional[PlayerId] = None,
        position: Optional[int] = None
    ) -> None:
        """Add object to a zone and register in index."""
        zone_obj = self.get_zone(zone_type, player_id)
        zone_obj.add(obj, position)
        obj.zone = zone_type
        self._register_object(obj, zone_type, zone_obj)

    # =========================================================================
    # CONVENIENCE METHODS (delegate to base implementation)
    # =========================================================================

    def all_zones(self) -> List[ZoneObject]:
        """Get all zones in the game."""
        zones = [self.battlefield, self.stack, self.exile, self.command]
        zones.extend(self.libraries.values())
        zones.extend(self.hands.values())
        zones.extend(self.graveyards.values())
        return zones

    def draw_card(
        self,
        player_id: PlayerId,
        events: Optional['EventBus'] = None
    ) -> Optional['Card']:
        """Draw a card for a player."""
        library = self.libraries[player_id]
        hand = self.hands[player_id]

        card = library.draw()
        if card:
            hand.add(card)
            card.zone = Zone.HAND
            # Update index
            self._object_index.update_location(card.object_id, Zone.HAND, hand)
        return card

    def draw_cards(
        self,
        player_id: PlayerId,
        count: int,
        events: Optional['EventBus'] = None
    ) -> List['Card']:
        """Draw multiple cards for a player."""
        return [self.draw_card(player_id, events)
                for _ in range(count)
                if not self.libraries[player_id].is_empty()]

    def shuffle_library(self, player_id: PlayerId) -> None:
        """Shuffle a player's library."""
        self.libraries[player_id].shuffle()

    def all_permanents(self) -> List['Permanent']:
        """Get all permanents on the battlefield (cached)."""
        return self.battlefield.permanents()

    def player_permanents(self, player_id: PlayerId) -> List['Permanent']:
        """Get all permanents controlled by a player (cached)."""
        return self.battlefield.permanents(player_id)

    def is_stack_empty(self) -> bool:
        """Check if the stack is empty."""
        return self.stack.is_empty()

    def stack_depth(self) -> int:
        """Get the current stack depth."""
        return self.stack.depth()

    def get_hand_size(self, player_id: PlayerId) -> int:
        """Get number of cards in a player's hand."""
        return len(self.hands[player_id])

    def get_library_count(self, player_id: PlayerId) -> int:
        """Get number of cards in a player's library."""
        return len(self.libraries[player_id])

    def get_graveyard_count(self, player_id: PlayerId) -> int:
        """Get number of cards in a player's graveyard."""
        return len(self.graveyards[player_id])

    def is_library_empty(self, player_id: PlayerId) -> bool:
        """Check if a player's library is empty."""
        return self.libraries[player_id].is_empty()

    # =========================================================================
    # STATISTICS
    # =========================================================================

    @property
    def stats(self) -> Dict[str, Any]:
        """Get combined statistics for all optimizations."""
        return {
            "object_index": self._object_index.stats,
            "battlefield_cache": self.battlefield.cache_stats,
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._object_index.reset_stats()
        self.battlefield.reset_cache_stats()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'GlobalObjectIndex',
    'CachedBattlefield',
    'OptimizedZoneManager',
    # Re-export from zones.py
    'ZoneChangeInfo',
    'ZoneObject',
    'Library',
    'Hand',
    'Graveyard',
    'Stack',
    'Exile',
    'Command',
    'is_public_zone',
    'is_hidden_zone',
    'is_shared_zone',
    'is_player_zone',
]
