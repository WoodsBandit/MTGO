# MTG Engine to MTGO Competitive Platform Roadmap

## Executive Summary

This document outlines the comprehensive transformation plan to evolve our homebrew MTG simulation engine into a fully MTGO-compliant competitive platform. Based on analysis of the MTG Comprehensive Rules, MTGO interface specifications, and tournament play-by-plays, this roadmap identifies all gaps and provides prioritized implementation phases.

**Current State**: ~85% rules compliance, 3,715 Standard cards (100% coverage)
**Target State**: 100% rules compliance, full MTGO UI/UX parity, tournament-ready

---

## Part 1: Current Engine Assessment

### 1.1 Already Implemented Features (22 Systems)

| Feature | Rule Reference | Status | Notes |
|---------|---------------|--------|-------|
| Priority System | Rule 117 | IMPLEMENTED | `resolve_stack_with_priority()`, `pass_priority()`, `hold_priority()` |
| APNAP Trigger Ordering | Rule 603.3b | IMPLEMENTED | `process_triggers()` with proper player ordering |
| State-Based Actions | Rule 704 | IMPLEMENTED | `check_state()`, `_check_sbas_once()` (704.5a-q) |
| Combat Phase Structure | Rules 506-511 | IMPLEMENTED | All 5 combat steps with proper timing |
| London Mulligan | Rule 103.5 | IMPLEMENTED | `_mulligan_player()` with bottom selection |
| Stack Resolution | Rule 608 | IMPLEMENTED | LIFO resolution with proper timing |
| Protection | Rule 702.16 | IMPLEMENTED | DEBT acronym (Damage, Enchant/Equip, Block, Target) |
| Hexproof/Shroud | Rules 702.11, 702.18 | IMPLEMENTED | Target validation includes these |
| Ward | Rule 702.21 | IMPLEMENTED | Counter unless cost paid |
| Regeneration | Rule 701.15 | IMPLEMENTED | Shield creation and removal |
| Phasing | Rule 702.26 | IMPLEMENTED | Phase in/out mechanics |
| Flashback | Rule 702.34 | IMPLEMENTED | Cast from graveyard |
| Escape | Rule 702.138 | IMPLEMENTED | Cast from graveyard with exile cost |
| Kicker/Multikicker | Rule 702.33 | IMPLEMENTED | Additional costs |
| Modal Spells | Rule 700.2 | IMPLEMENTED | Choose modes on cast |
| Adventure | Rule 715 | IMPLEMENTED | Adventure half castable |
| MDFC | Rule 712 | IMPLEMENTED | Modal double-faced cards |
| Equipment | Rule 301.5 | IMPLEMENTED | Attach/detach mechanics |
| Vehicles | Rule 301.7 | IMPLEMENTED | Crew mechanics |
| Sagas | Rule 714 | IMPLEMENTED | Chapter progression |
| Planeswalkers | Rule 306 | IMPLEMENTED | Loyalty abilities |
| Persist/Undying | Rules 702.79, 702.93 | IMPLEMENTED | Return with counters |

### 1.2 Bug Fixes Verified (9 Fixes)

All previously identified bugs have been fixed and verified:

1. **Protection Prevents Combat Damage** (CR 702.16e) - `_protection_prevents_damage()`
2. **Target Validation on Resolution** (CR 608.2b) - `_validate_target_on_resolution()`
3. **Trample + Protection Calculation** (CR 702.19b) - Proper lethal damage assignment
4. **APNAP Trigger Ordering** (CR 603.3b) - Active player's triggers first
5. **Last Known Information for Dies Triggers** (CR 603.10) - `fire_dies()` with `last_known_info`
6. **SBA Trigger Processing** (CR 704.3) - Triggers fire after SBA cleanup
7. **Damage Assignment Order** (CR 510.1c) - `choose_damage_assignment_order()`
8. **Auras Fall Off from Protection** (CR 303.4d) - SBA check for illegal attachments
9. **Complete Spell Fizzle Logic** (CR 608.2b) - All targeted spells fizzle on invalid targets

---

## Part 2: Rules Compliance Gap Analysis

### 2.1 Critical Missing Systems (Priority 1)

#### 2.1.1 Replacement Effects (Rule 614)
**Current**: Not implemented
**Impact**: HIGH - Breaks many card interactions

```
Rule 614.1: Replacement effects modify how an event happens.
Rule 614.1a: "If [event], [replacement] instead"
Rule 614.1b: "As [event], [modification]"
Rule 614.2: Can only apply once per event
Rule 614.6: Self-replacement effects apply first
Rule 614.7: Affected player/controller chooses order
```

**Cards Affected**:
- Damage redirection (Deflecting Palm, Rakdos Charm)
- ETB modifications (Panharmonicon, Yarok)
- Death replacements (Rest in Peace, Leyline of the Void)
- Draw replacements (Notion Thief, Alms Collector)

**Implementation Required**:
```python
class ReplacementEffect:
    def __init__(self, source, event_type, condition, replacement_func):
        self.source = source
        self.event_type = event_type  # 'damage', 'draw', 'etb', 'die', etc.
        self.condition = condition     # lambda checking if applies
        self.replacement = replacement_func
        self.self_replacement = False  # Rule 614.6

    def applies_to(self, event) -> bool:
        return self.event_type == event.type and self.condition(event)

    def apply(self, event) -> Event:
        return self.replacement(event)

def process_event_with_replacements(event, replacement_effects, affected_player):
    """Rule 614.7: Affected player chooses order for multiple replacements"""
    applicable = [r for r in replacement_effects if r.applies_to(event)]

    # Rule 614.6: Self-replacement effects apply first
    self_replacements = [r for r in applicable if r.self_replacement]
    other_replacements = [r for r in applicable if not r.self_replacement]

    for replacement in self_replacements:
        event = replacement.apply(event)
        applicable = [r for r in other_replacements if r.applies_to(event)]

    while applicable:
        if len(applicable) == 1:
            chosen = applicable[0]
        else:
            chosen = affected_player.choose_replacement_effect(applicable)

        event = chosen.apply(event)
        applicable = [r for r in applicable if r.applies_to(event) and r != chosen]

    return event
```

#### 2.1.2 Layer System (Rule 613)
**Current**: Not implemented
**Impact**: HIGH - Continuous effects calculate incorrectly

```
Rule 613.1: Layers for continuous effects:
  Layer 1: Copy effects
  Layer 2: Control-changing effects
  Layer 3: Text-changing effects
  Layer 4: Type-changing effects
  Layer 5: Color-changing effects
  Layer 6: Ability adding/removing effects
  Layer 7: Power/toughness effects (sublayers 7a-7e)
    7a: Characteristic-defining abilities
    7b: Set P/T to specific value
    7c: Modifications from counters
    7d: Effects that modify without setting
    7e: Effects that switch P/T

Rule 613.7: Within a layer, use timestamp order (or dependency)
Rule 613.8: Dependency - if one effect could change how another applies
```

**Critical Test Case (Magus of the Moon + Blood Moon + Urborg)**:
```
Battlefield: Blood Moon, Urborg (Tomb of Yawgmoth), Magus of the Moon
Layer 4 (types):
  - Blood Moon: "Nonbasic lands are Mountains" (timestamp 1)
  - Urborg: "Each land is a Swamp in addition" (timestamp 2)
  - Magus: "Nonbasic lands are Mountains" (timestamp 3)

Result: All nonbasic lands are Mountains (not Swamps)
Urborg's ability is removed by Blood Moon before it can apply
```

**Implementation Required**:
```python
class ContinuousEffect:
    def __init__(self, source, layer, sublayer=None, modification_func,
                 applies_to_func, timestamp, duration='permanent'):
        self.source = source
        self.layer = layer
        self.sublayer = sublayer
        self.modify = modification_func
        self.applies_to = applies_to_func
        self.timestamp = timestamp
        self.duration = duration
        self.dependencies = []

class LayerSystem:
    LAYERS = [1, 2, 3, 4, 5, 6, '7a', '7b', '7c', '7d', '7e']

    def __init__(self, game):
        self.game = game
        self.continuous_effects = []

    def calculate_characteristics(self, permanent):
        """Apply all continuous effects in layer order"""
        # Start with base characteristics
        char = permanent.base_characteristics.copy()

        for layer in self.LAYERS:
            effects_in_layer = [e for e in self.continuous_effects
                               if e.layer == layer]

            # Sort by timestamp, handling dependencies (Rule 613.8)
            ordered = self._dependency_sort(effects_in_layer)

            for effect in ordered:
                if effect.applies_to(permanent, char):
                    char = effect.modify(permanent, char)

        return char

    def _dependency_sort(self, effects):
        """Rule 613.8: Sort considering dependencies"""
        # Topological sort based on dependencies
        # Effect A depends on B if B's result could change whether A applies
        pass
```

#### 2.1.3 Copy Effects (Rule 707)
**Current**: Not implemented
**Impact**: MEDIUM-HIGH - Clone/copy cards don't work

```
Rule 707.1: Copy effects copy copiable values
Rule 707.2: Copiable values are: name, mana cost, color, card type,
            subtype, supertype, rules text, power/toughness, loyalty
Rule 707.3: Copy doesn't copy counters, attached objects, effects
Rule 707.9: Copy of a copy uses same copiable values
Rule 707.10: Copy-and-modify effects modify after copying
```

**Implementation Required**:
```python
def create_copy(original, modifications=None):
    """Rule 707: Create a copy of a permanent/spell"""
    # Copy only copiable values (Rule 707.2)
    copy = Card(
        name=original.name,
        mana_cost=original.mana_cost.copy(),
        color=original.color.copy(),
        card_type=original.card_type,
        subtype=original.subtype.copy(),
        supertype=original.supertype.copy(),
        rules_text=original.rules_text,
        power=original.base_power,
        toughness=original.base_toughness,
        loyalty=original.base_loyalty
    )

    # Rule 707.10: Apply modifications if any
    if modifications:
        for mod in modifications:
            mod.apply(copy)

    # Rule 707.3: Don't copy these
    copy.counters = {}
    copy.attached_cards = []
    copy.continuous_effects_on_it = []

    return copy
```

### 2.2 Important Missing Systems (Priority 2)

#### 2.2.1 Control-Changing Effects
**Current**: Not implemented
**Impact**: MEDIUM - Mind Control, Act of Treason don't work

```
Rule 108.4: Controller determined by control-changing effects
Layer 2 effects change controller
Effects can grant control "until end of turn" or permanently
```

**Cards Affected**: Mind Control, Agent of Treachery, Claim the Firstborn, Act of Treason

#### 2.2.2 Suspend/Cascade/Storm
**Current**: Not implemented
**Impact**: MEDIUM - These mechanics are in Standard

```
Suspend (Rule 702.62):
  - Exile with time counters
  - Remove counter each upkeep
  - Cast without paying mana cost at 0 counters
  - Gains haste

Cascade (Rule 702.85):
  - Exile cards until lower MV found
  - May cast without paying
  - Put rest on bottom in random order

Storm (Rule 702.40):
  - Copy spell for each spell cast before it this turn
```

#### 2.2.3 Mutate
**Current**: Not implemented
**Impact**: LOW - Few Standard-legal mutate cards

```
Rule 702.140:
  - Cast creature on top or under another creature you own
  - Resulting creature has all abilities
  - P/T and characteristics of top creature
  - Counts as one permanent
```

#### 2.2.4 Companion
**Current**: Not implemented
**Impact**: LOW - Companion mechanic with restrictions

```
Rule 702.139:
  - Companion in sideboard with deck restriction
  - May pay 3 to put in hand (once per game)
  - Deck must meet restriction for entire game
```

### 2.3 Edge Cases & Corner Cases (Priority 3)

#### 2.3.1 Damage Prevention/Redirection
- Damage can't be prevented effects
- Multiple prevention shields
- Redirection order

#### 2.3.2 Mana Abilities
- Mana abilities don't use stack (Rule 605.3b)
- Triggered mana abilities (Rule 605.1b)
- Mana ability identification

#### 2.3.3 Split Second
- Rule 702.61: Can't cast spells or activate non-mana abilities
- Triggered abilities still trigger
- Special actions still allowed

#### 2.3.4 Static Ability Interactions
- Multiple static abilities affecting same permanent
- Ability word triggers (Landfall, Constellation)
- Characteristic-defining abilities

---

## Part 3: MTGO UI/UX Implementation Plan

### 3.1 Zone Display System

MTGO uses distinct visual zones that must be implemented:

```
┌─────────────────────────────────────────────────────────────────┐
│                        OPPONENT AREA                            │
├─────────────────────────────────────────────────────────────────┤
│ [Exile X] [GY ⚰] [Effects ⛨] [Command ⚑]    [Library 40]      │
│                                                                 │
│ ┌─────────────────────── BATTLEFIELD ──────────────────────┐   │
│ │  [Lands Row]                                              │   │
│ │  [Creatures Row]                                          │   │
│ │  [Other Permanents Row]                                   │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│                    ═══════ RED ZONE ═══════                     │
│                    (Combat/Targeting Area)                      │
│                                                                 │
│ ┌─────────────────── YOUR BATTLEFIELD ─────────────────────┐   │
│ │  [Other Permanents Row]                                   │   │
│ │  [Creatures Row]                                          │   │
│ │  [Lands Row]                                              │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│ [Exile X] [GY ⚰] [Effects ⛨] [Command ⚑]    [Library 52]      │
├─────────────────────────────────────────────────────────────────┤
│ [Hand: Card1] [Card2] [Card3] [Card4] [Card5] [Card6] [Card7]  │
├─────────────────────────────────────────────────────────────────┤
│ STACK: [Spell 1] -> [Ability 2] -> [Spell 3]                   │
├─────────────────────────────────────────────────────────────────┤
│ [Phase: Main 1] [Priority: YOU]  [Timer: 24:35] [F4] [F6] [F8] │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Zone Implementation

```python
class ZoneDisplay:
    """MTGO-style zone display system"""

    ZONES = {
        'library': {'icon': '📚', 'hidden': True, 'countable': True},
        'hand': {'icon': '🖐', 'hidden_to_opponent': True},
        'battlefield': {'icon': None, 'rows': ['lands', 'creatures', 'other']},
        'graveyard': {'icon': '⚰', 'viewable': True, 'ordered': True},
        'exile': {'icon': '✖', 'viewable': True, 'may_have_face_down': True},
        'stack': {'icon': '📜', 'ordered': True, 'lifo': True},
        'command': {'icon': '⚑', 'commanders': True},
        'effects': {'icon': '⛨', 'emblems_and_effects': True}
    }

    def render_zone(self, zone_name, player, viewer):
        zone = getattr(player, zone_name)
        config = self.ZONES[zone_name]

        if config.get('hidden') and player != viewer:
            return f"{config['icon']} [{len(zone)}]"

        if config.get('hidden_to_opponent') and player != viewer:
            return f"{config['icon']} [{len(zone)} cards]"

        return self._render_cards(zone, config)
```

### 3.3 Priority Stop System

MTGO uses configurable stops for priority:

```python
class PriorityStops:
    """MTGO-style priority stop configuration"""

    DEFAULT_STOPS = {
        'upkeep': {'yours': False, 'opponents': True},
        'draw': {'yours': False, 'opponents': False},
        'main1': {'yours': True, 'opponents': False},
        'begin_combat': {'yours': True, 'opponents': True},
        'declare_attackers': {'yours': True, 'opponents': True},
        'declare_blockers': {'yours': True, 'opponents': True},
        'first_strike_damage': {'yours': True, 'opponents': True},
        'combat_damage': {'yours': True, 'opponents': True},
        'end_combat': {'yours': False, 'opponents': False},
        'main2': {'yours': True, 'opponents': False},
        'end_step': {'yours': True, 'opponents': True},
    }

    def should_stop(self, phase, active_player, priority_player, game_state):
        """Determine if we should pause for priority"""
        is_yours = priority_player == self.player

        # Always stop if there's something on the stack
        if game_state.stack:
            return True

        # Check configured stops
        phase_config = self.stops.get(phase, {'yours': True, 'opponents': True})
        if is_yours:
            return phase_config['yours']
        else:
            return phase_config['opponents']
```

### 3.4 Keyboard Shortcuts (MTGO Standard)

```python
MTGO_SHORTCUTS = {
    '3': 'yes',           # Confirm/OK
    '4': 'no',            # Cancel/No
    'F2': 'pass_priority', # OK/Pass priority
    'F4': 'yield_turn',   # Yield until end of turn
    'F6': 'yield_all',    # Yield all priority (auto-pass)
    'F8': 'yield_stack',  # Yield until stack empty
    'Q': 'zoom_card',     # Zoom on card under cursor
    'Ctrl+Z': 'undo_mana', # Undo mana ability
    'Tab': 'cycle_stops', # Cycle through stop settings
    'Space': 'tap_card',  # Tap selected card
}

class InputHandler:
    def process_input(self, key, game_state):
        action = MTGO_SHORTCUTS.get(key)

        if action == 'yes':
            return self.confirm_action(game_state)
        elif action == 'no':
            return self.cancel_action(game_state)
        elif action == 'yield_turn':
            return self.set_yield('end_of_turn')
        elif action == 'yield_all':
            return self.set_yield('all')
        # ... etc
```

### 3.5 Timer System

```python
class ChessTimer:
    """MTGO-style chess clock timer"""

    FORMATS = {
        'open_play': {'initial': 60 * 60, 'reserve': 0},      # 60 min
        'tournament_practice': {'initial': 25 * 60, 'reserve': 0},  # 25 min
        'league': {'initial': 25 * 60, 'reserve': 0},
        'challenge': {'initial': 25 * 60, 'reserve': 0},
        'premier': {'initial': 25 * 60, 'reserve': 5 * 60},   # 25 + 5 reserve
    }

    def __init__(self, format_type='tournament_practice'):
        config = self.FORMATS[format_type]
        self.time_remaining = {
            'player1': config['initial'],
            'player2': config['initial']
        }
        self.reserve = {
            'player1': config['reserve'],
            'player2': config['reserve']
        }
        self.active_player = None
        self.is_running = False

    def switch_to(self, player):
        """Switch clock to new player (priority change)"""
        if self.active_player:
            self._stop_clock(self.active_player)
        self.active_player = player
        self._start_clock(player)

    def tick(self, elapsed_seconds):
        """Called each tick while clock running"""
        if not self.active_player or not self.is_running:
            return

        self.time_remaining[self.active_player] -= elapsed_seconds

        if self.time_remaining[self.active_player] <= 0:
            # Use reserve time if available
            if self.reserve[self.active_player] > 0:
                self.time_remaining[self.active_player] = self.reserve[self.active_player]
                self.reserve[self.active_player] = 0
            else:
                self.player_timeout(self.active_player)
```

### 3.6 Card Movement Animations

```python
class CardAnimator:
    """Handle card movement and zone transitions"""

    ANIMATION_SPEEDS = {
        'instant': 0,
        'fast': 150,      # 150ms
        'normal': 300,    # 300ms
        'slow': 500       # 500ms
    }

    def move_card(self, card, from_zone, to_zone, animation='normal'):
        """Animate card moving between zones"""
        start_pos = self.get_zone_position(from_zone)
        end_pos = self.get_zone_position(to_zone)

        # Calculate arc for natural movement
        if self._is_battlefield_to_graveyard(from_zone, to_zone):
            # Dramatic arc for dying creature
            arc_height = 100
        else:
            arc_height = 50

        frames = self._interpolate_arc(start_pos, end_pos, arc_height,
                                       self.ANIMATION_SPEEDS[animation])

        for frame in frames:
            self.render_card_at(card, frame)
            yield  # Allow frame update

        # Final placement
        self.place_card_in_zone(card, to_zone)

    def tap_card(self, card, tap=True):
        """Animate tapping/untapping"""
        target_rotation = 90 if tap else 0
        current_rotation = card.rotation

        for angle in self._interpolate(current_rotation, target_rotation, 10):
            card.rotation = angle
            self.render_card(card)
            yield
```

### 3.7 Visual Indicators

```python
class VisualIndicators:
    """MTGO-style visual feedback"""

    INDICATORS = {
        'can_attack': {'border': 'green', 'glow': True},
        'summoning_sick': {'overlay': 'gray_haze', 'icon': '💤'},
        'tapped': {'rotation': 90},
        'targeted': {'highlight': 'yellow', 'arrow': True},
        'valid_target': {'border': 'green'},
        'invalid_target': {'border': 'red'},
        'has_activated_ability': {'icon': '⚡'},
        'has_triggered_ability': {'icon': '🔔'},
        'damage_marked': {'number_overlay': 'red'},
        'counters': {'icon_per_type': True},
        'aura_attached': {'connection_line': True},
        'equipment_attached': {'connection_line': True},
    }

    def highlight_valid_targets(self, spell_or_ability, game_state):
        """Show all legal targets for current spell/ability"""
        valid = self.get_valid_targets(spell_or_ability, game_state)

        for permanent in game_state.all_permanents:
            if permanent in valid:
                self.apply_indicator(permanent, 'valid_target')
            else:
                self.apply_indicator(permanent, 'invalid_target')
```

---

## Part 4: Card Interaction Matrix

### 4.1 Complex Interaction Categories

| Category | Examples | Implementation Complexity |
|----------|----------|--------------------------|
| ETB Triggers + Replacement | Panharmonicon, Yarok | HIGH - Needs replacement effects |
| Death Triggers + Replacement | Rest in Peace, Leyline | HIGH - Layer interactions |
| Continuous P/T Modification | Anthem effects, -1/-1 effects | HIGH - Full layer system |
| Combat Damage Modification | Trample + Deathtouch | MEDIUM - Already partial |
| Static Ability Stacking | Multiple lords | MEDIUM - Needs proper ordering |
| Targeting with Hexproof | Own hexproof creatures | LOW - Targeting rules |

### 4.2 Priority Card Interactions to Test

These represent common MTGO tournament scenarios:

1. **Sheoldred + Draw Effects**
   - Opponent draws: they lose 2 life
   - You draw: you gain 2 life
   - Multiple triggers stack correctly

2. **Raffine Connive Chain**
   - Attack triggers connive
   - Each connive draws, then discards
   - +1/+1 counters if nonland discarded

3. **Atraxa + Planeswalkers**
   - End step proliferate
   - Choose which counters to proliferate
   - All permanents with counters eligible

4. **Sunfall + Death Triggers**
   - All creatures exiled (not destroyed)
   - No death triggers fire
   - Incubate token created

5. **Wedding Announcement Transformations**
   - Chapter progression
   - Token creation
   - Transform condition check

### 4.3 Interaction Test Suite

```python
class InteractionTestSuite:
    """Comprehensive interaction testing"""

    TEST_CASES = [
        {
            'name': 'Double Death Trigger with Replacement',
            'setup': ['Blood Artist', 'Zulaport Cutthroat', 'Rest in Peace'],
            'action': 'creature_dies',
            'expected': {
                'death_triggers': 0,  # RIP replaces death with exile
                'life_change': 0
            }
        },
        {
            'name': 'Panharmonicon ETB Doubling',
            'setup': ['Panharmonicon', 'Ravenous Chupacabra'],
            'action': 'etb_chupacabra',
            'expected': {
                'destroy_triggers': 2,  # Doubled by Panharmonicon
            }
        },
        {
            'name': 'Layer System - Blood Moon + Urborg',
            'setup': ['Blood Moon', 'Urborg, Tomb of Yawgmoth'],
            'action': 'check_land_types',
            'expected': {
                'urborg_type': ['Mountain'],  # Not Swamp - ability removed
                'other_nonbasic_type': ['Mountain']
            }
        },
        # ... more test cases
    ]
```

---

## Part 5: Implementation Roadmap

### Phase 1: Core Rules Completion (Weeks 1-4)

#### 1.1 Replacement Effects System (Week 1-2)
- Implement `ReplacementEffect` class
- Add replacement effect registry
- Implement `process_event_with_replacements()`
- Self-replacement priority (Rule 614.6)
- Player choice for multiple replacements (Rule 614.7)

**Test Cases**:
- Rest in Peace replacing death
- Panharmonicon doubling ETB
- Damage prevention/redirection

#### 1.2 Layer System Implementation (Week 2-3)
- Implement all 7 layers with sublayers
- Timestamp tracking for effects
- Dependency detection (Rule 613.8)
- Continuous effect recalculation

**Test Cases**:
- Blood Moon + Urborg scenario
- Multiple anthem effects
- P/T setting vs modification

#### 1.3 Copy Effects (Week 3-4)
- Implement `create_copy()` function
- Copiable values definition
- Copy-and-modify effects
- Copy of a copy handling

**Test Cases**:
- Clone effects
- Spark Double
- Copy that copies

### Phase 2: Missing Mechanics (Weeks 5-6)

#### 2.1 Control-Changing Effects
- Layer 2 implementation
- Temporary vs permanent control
- "Until end of turn" duration tracking

#### 2.2 Suspend/Cascade/Storm
- Time counter mechanics
- Exile zone casting
- Storm count tracking
- Cascade resolution

#### 2.3 Additional Keywords
- Mutate (if needed)
- Companion restrictions
- Split Second handling

### Phase 3: UI Foundation (Weeks 7-10)

#### 3.1 Zone System (Week 7)
- Implement all MTGO zones
- Zone rendering logic
- Card positioning

#### 3.2 Priority & Timing Display (Week 8)
- Priority indicator
- Phase/step display
- Stack visualization
- Timer implementation

#### 3.3 Card Interaction UI (Week 9)
- Target highlighting
- Valid action indicators
- Drag-and-drop for cards
- Context menus

#### 3.4 Animation System (Week 10)
- Card movement animations
- Tap/untap animations
- Zone transition effects
- Damage visualization

### Phase 4: Competitive Features (Weeks 11-12)

#### 4.1 Match & Tournament Support
- Best-of-3 match structure
- Sideboard handling
- Match timer
- Game state saving/loading

#### 4.2 Advanced Stop System
- Configurable priority stops
- Yield functionality (F4/F6/F8)
- Auto-pass intelligence

#### 4.3 Replay System
- Game state recording
- Replay playback
- Move-by-move analysis

---

## Part 6: Testing Strategy

### 6.1 Rules Compliance Tests

```python
class RulesComplianceTest:
    """Test against MTG Comprehensive Rules"""

    def test_rule_704_5a(self):
        """Player at 0 or less life loses"""
        game = create_game()
        game.player1.life = 0
        game.check_state()
        assert game.player1.has_lost

    def test_rule_704_5f(self):
        """Creature with 0 or less toughness dies"""
        game = create_game()
        creature = create_creature(power=2, toughness=0)
        game.battlefield.append(creature)
        game.check_state()
        assert creature in game.graveyard

    def test_rule_117_3a(self):
        """Active player receives priority after spell resolves"""
        game = create_game()
        game.cast_spell(game.player1, spell)
        game.resolve_stack()
        assert game.priority_player == game.active_player
```

### 6.2 MTGO Parity Tests

```python
class MTGOParityTest:
    """Test against known MTGO behavior"""

    def test_mtgo_combat_display(self):
        """Combat uses red zone correctly"""
        game = create_game()
        attacker = create_creature()
        game.declare_attackers([attacker])

        # Red zone should contain attacker
        assert attacker in game.ui.red_zone

    def test_mtgo_timer_switch(self):
        """Timer switches on priority change"""
        game = create_game()
        timer = game.timer

        game.pass_priority()
        assert timer.active_player == game.player2
```

### 6.3 Tournament Scenario Tests

Based on documented MTGO Championship play-by-plays:

```python
class TournamentScenarioTest:
    """Recreate documented tournament situations"""

    def test_mocs_finals_scenario_1(self):
        """Complex board state from MOCS finals"""
        # Setup exact board state
        game = create_game()
        setup_board(game, {
            'p1_creatures': ['Sheoldred, the Apocalypse'],
            'p1_lands': ['Swamp'] * 4 + ['Caves of Koilos'] * 2,
            'p2_creatures': ['Raffine, Scheming Seer'],
            'p2_life': 14,
            # ...
        })

        # Execute documented play sequence
        game.cast_spell(game.player1, 'Cut Down', target='Raffine')

        # Verify documented outcome
        assert 'Raffine' in game.player2.graveyard
```

---

## Part 7: Performance Benchmarks

### 7.1 Target Metrics

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| Turn simulation | ~50ms | <10ms | 5x improvement needed |
| Game simulation | ~2s | <500ms | For 20-turn average |
| AI decision time | ~100ms | <50ms | Per decision point |
| UI render | N/A | 16ms | 60 FPS target |
| Memory per game | ~50MB | <25MB | For multiple games |

### 7.2 Optimization Areas

1. **Layer Calculation Caching**
   - Only recalculate when effects change
   - Dirty flag per permanent

2. **Trigger Batching**
   - Group triggers by type
   - Process in optimal order

3. **Target Validation Caching**
   - Cache valid targets per spell type
   - Invalidate on game state change

4. **AI Move Generation**
   - Prune obviously bad moves early
   - Use iterative deepening

---

## Part 8: Risk Assessment

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Layer system complexity | High | High | Extensive testing, reference MTGO behavior |
| Replacement effect edge cases | Medium | High | Document all cases, test thoroughly |
| UI performance | Medium | Medium | Profile early, optimize incrementally |
| Card database maintenance | Low | Medium | Automated Scryfall updates |

### 8.2 Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scope creep | High | High | Strict phase gates, prioritization |
| Unknown edge cases | Medium | Medium | Community testing, bug bounty |
| Integration issues | Medium | Medium | Continuous integration testing |

---

## Appendices

### Appendix A: MTG Comprehensive Rules Reference

Key rules sections for implementation:

- **100-199**: Game Concepts
- **200-299**: Parts of a Card
- **300-399**: Card Types
- **400-499**: Zones
- **500-599**: Turn Structure
- **600-699**: Spells, Abilities, Effects
- **700-799**: Additional Rules (Keywords start at 702)

### Appendix B: MTGO Interface Specifications

- Minimum resolution: 1024x768
- Card size: 63x88 pixels (scaled)
- Zone margins: 10px
- Animation frame rate: 60 FPS
- Network latency tolerance: <500ms

### Appendix C: File Structure

```
mtg_sim_package/
├── core/
│   ├── game.py           # Main game loop
│   ├── player.py         # Player state
│   ├── zones.py          # Zone management
│   ├── stack.py          # Stack operations
│   └── state_based.py    # SBA processing
├── rules/
│   ├── layers.py         # Layer system
│   ├── replacement.py    # Replacement effects
│   ├── priority.py       # Priority handling
│   └── combat.py         # Combat rules
├── cards/
│   ├── database.py       # Card definitions
│   ├── parser.py         # Card text parsing
│   └── abilities.py      # Ability implementations
├── ui/
│   ├── display.py        # Main display
│   ├── zones.py          # Zone rendering
│   ├── animations.py     # Card animations
│   └── input.py          # Input handling
├── ai/
│   ├── ai.py             # AI decision making
│   ├── evaluation.py     # Board evaluation
│   └── search.py         # Move search
└── tests/
    ├── rules/            # Rules compliance tests
    ├── interactions/     # Card interaction tests
    └── scenarios/        # Tournament scenarios
```

---

## Conclusion

This roadmap provides a comprehensive path from our current homebrew engine (85% rules compliance, 100% Standard card coverage) to a fully MTGO-compliant competitive platform. The key priorities are:

1. **Immediate**: Layer system and replacement effects (critical for correct gameplay)
2. **Short-term**: Copy effects and control-changing (enables more cards)
3. **Medium-term**: Full MTGO UI/UX (enables human play)
4. **Long-term**: Tournament features (competitive viability)

Estimated total effort: 12 weeks for core functionality, additional 4-8 weeks for polish and tournament features.

---

*Document generated: January 2026*
*Engine version: 3.0 (3,715 cards, 22 implemented systems)*
*Target: MTGO Competitive Parity*
