# MTG Simulation Engine v2 → v3: Competitive Rules-Accurate Simulator
## Sequential Phased Development Plan

**Project Goal:** Transform the V1 "quick deck testing" engine into a precise, rules-accurate MTG simulator suitable for competitive analysis.

**Current State (V1/V2.1):** ~870 lines, simplified combat, no stack, no priority, limited keywords
**Target State (V3):** Full rules compliance per MTG Comprehensive Rules (CR), MTGO-equivalent resolution

---

## Table of Contents

1. [Architecture Philosophy](#architecture-philosophy)
2. [Dependency Graph](#dependency-graph)
3. [Phase Overview](#phase-overview)
4. [Detailed Phase Specifications](#detailed-phase-specifications)
5. [Testing Strategy](#testing-strategy)
6. [Milestones & Checkpoints](#milestones--checkpoints)

---

## Architecture Philosophy

### Core Principles

1. **Event-Driven Architecture**
   - All game actions emit events
   - Triggered abilities listen for events
   - Replacement effects intercept events
   - Enables proper trigger ordering and replacement chains

2. **Immutable Game State Snapshots**
   - Game state can be cloned for AI lookahead
   - Enables "what-if" analysis
   - Supports undo/replay functionality

3. **Separation of Concerns**
   ```
   ┌─────────────────────────────────────────────────────────┐
   │                      GAME RUNNER                        │
   │  (Match management, deck loading, results tracking)     │
   └─────────────────────────────────────────────────────────┘
                              │
   ┌─────────────────────────────────────────────────────────┐
   │                      GAME ENGINE                        │
   │  (Turn structure, priority, stack, state-based actions) │
   └─────────────────────────────────────────────────────────┘
                              │
   ┌──────────────┬───────────────────┬─────────────────────┐
   │   ZONES      │   OBJECTS         │   EFFECTS           │
   │  (7 zones)   │  (Cards, Tokens)  │  (Continuous, etc)  │
   └──────────────┴───────────────────┴─────────────────────┘
                              │
   ┌─────────────────────────────────────────────────────────┐
   │                    CARD DATABASE                        │
   │  (Card definitions, abilities, Oracle text parsing)     │
   └─────────────────────────────────────────────────────────┘
                              │
   ┌─────────────────────────────────────────────────────────┐
   │                      AI AGENTS                          │
   │  (Decision making, priority handling, combat math)      │
   └─────────────────────────────────────────────────────────┘
   ```

4. **Rules as Data**
   - Keywords implemented as composable behaviors
   - Abilities defined declaratively where possible
   - New cards addable without engine changes (mostly)

---

## Dependency Graph

```
Phase 0: Foundation
    │
    ├──► Phase 1: Turn Structure & Priority ◄─────────────────┐
    │         │                                                │
    │         ▼                                                │
    │    Phase 2: The Stack                                    │
    │         │                                                │
    │         ├──────────────────────┐                         │
    │         ▼                      ▼                         │
    │    Phase 3: Mana          Phase 5: Targeting             │
    │         │                      │                         │
    │         ▼                      │                         │
    │    Phase 4: State-Based ◄──────┘                         │
    │         Actions                                          │
    │         │                                                │
    │         ├──────────────────────────────────────┐         │
    │         ▼                                      ▼         │
    │    Phase 6: Combat Core              Phase 8: Triggered  │
    │         │                                 Abilities      │
    │         ▼                                      │         │
    │    Phase 7: Combat Keywords                    │         │
    │         │                                      │         │
    │         ▼                                      ▼         │
    │    Phase 9: Activated Abilities ◄──────────────┘         │
    │         │                                                │
    │         ▼                                                │
    │    Phase 10: Continuous Effects & Layers                 │
    │         │                                                │
    │         ▼                                                │
    │    Phase 11: Replacement Effects ────────────────────────┘
    │         │
    │         ▼
    │    Phase 12: Card Database v2
    │         │
    │         ▼
    │    Phase 13: AI Improvements
    │         │
    │         ▼
    │    Phase 14: Testing & Validation
    │         │
    │         ▼
    └──► Phase 15: Polish & Extensions
```

---

## Phase Overview

| Phase | Name | Description | Est. Complexity | Dependencies |
|-------|------|-------------|-----------------|--------------|
| 0 | Foundation | Architecture, classes, event system | High | None |
| 1 | Turn Structure | All phases/steps, basic priority | High | Phase 0 |
| 2 | The Stack | LIFO resolution, priority passing | High | Phase 1 |
| 3 | Mana System | Colors, costs, mana abilities | Medium | Phase 2 |
| 4 | State-Based Actions | SBA checker, creature death | Medium | Phase 1-3 |
| 5 | Targeting | Legal targets, restrictions | Medium | Phase 2 |
| 6 | Combat Core | Attack/block declaration, damage | High | Phase 4 |
| 7 | Combat Keywords | First strike, deathtouch, trample | Medium | Phase 6 |
| 8 | Triggered Abilities | Trigger detection, stack placement | High | Phase 2, 4 |
| 9 | Activated Abilities | Costs, timing, loyalty abilities | Medium | Phase 2, 3 |
| 10 | Continuous Effects | Layer system, timestamps | Very High | Phase 4, 8, 9 |
| 11 | Replacement Effects | "Instead" processing, prevention | High | Phase 8, 10 |
| 12 | Card Database v2 | Enhanced data, Oracle parsing | Medium | Phase 8-11 |
| 13 | AI Improvements | Priority-aware, instant response | High | All prior |
| 14 | Testing & Validation | Comprehensive test suites | Medium | All prior |
| 15 | Polish & Extensions | Sideboarding, replays, stats | Medium | Phase 14 |

---

## Detailed Phase Specifications

---

### Phase 0: Foundation & Architecture

**Goal:** Establish the core architecture that all subsequent phases build upon.

#### 0.1 Core Classes

```python
# New class hierarchy

class GameObject:
    """Base class for all game objects (cards, tokens, emblems, etc.)"""
    object_id: int
    owner: Player
    controller: Player
    characteristics: Characteristics

class Characteristics:
    """Mutable characteristics of an object"""
    name: str
    mana_cost: ManaCost
    colors: Set[Color]
    types: Set[CardType]
    subtypes: Set[str]
    supertypes: Set[Supertype]
    power: Optional[int]
    toughness: Optional[int]
    loyalty: Optional[int]
    abilities: List[Ability]
    rules_text: str

class Permanent(GameObject):
    """Object on the battlefield"""
    is_tapped: bool
    is_flipped: bool
    is_face_down: bool
    is_phased_out: bool
    damage_marked: int
    counters: Dict[CounterType, int]
    attached_to: Optional[Permanent]
    attachments: List[Permanent]

class Spell(GameObject):
    """Object on the stack"""
    targets: List[Target]
    modes: List[Mode]
    x_value: Optional[int]

class Ability:
    """Base class for all abilities"""
    source: GameObject
    controller: Player

class TriggeredAbility(Ability):
    trigger_condition: TriggerCondition
    trigger_event: Event

class ActivatedAbility(Ability):
    cost: Cost
    timing_restriction: TimingRestriction

class StaticAbility(Ability):
    effect: ContinuousEffect

class ManaAbility(ActivatedAbility):
    """Special activated ability that doesn't use stack"""
    pass
```

#### 0.2 Zone System

```python
class Zone:
    """Base class for game zones"""
    objects: List[GameObject]
    owner: Optional[Player]  # None for shared zones
    is_public: bool
    is_ordered: bool

class Library(Zone):       # Private, ordered
class Hand(Zone):          # Private, unordered
class Battlefield(Zone):   # Public, unordered, shared
class Graveyard(Zone):     # Public, ordered
class Stack(Zone):         # Public, ordered, shared
class Exile(Zone):         # Public, unordered (usually)
class Command(Zone):       # Public, unordered
```

#### 0.3 Event System

```python
class Event:
    """Base class for game events"""
    timestamp: int
    source: Optional[GameObject]

class DamageEvent(Event):
    source: GameObject
    target: Union[Player, Permanent]
    amount: int
    is_combat: bool

class ZoneChangeEvent(Event):
    object: GameObject
    from_zone: Zone
    to_zone: Zone

class SpellCastEvent(Event):
    spell: Spell

class AbilityTriggeredEvent(Event):
    ability: TriggeredAbility

class EventBus:
    """Publish/subscribe for game events"""
    def emit(event: Event)
    def subscribe(event_type: Type[Event], callback: Callable)
```

#### 0.4 File Structure

```
v2/
├── engine/
│   ├── __init__.py
│   ├── game.py              # Main Game class
│   ├── player.py            # Player class
│   ├── objects.py           # GameObject, Permanent, Spell
│   ├── zones.py             # Zone implementations
│   ├── events.py            # Event system
│   ├── priority.py          # Priority system
│   ├── stack.py             # Stack management
│   ├── mana.py              # Mana system
│   ├── combat.py            # Combat system
│   ├── sba.py               # State-based actions
│   ├── targeting.py         # Targeting system
│   ├── effects/
│   │   ├── __init__.py
│   │   ├── continuous.py    # Continuous effects
│   │   ├── replacement.py   # Replacement effects
│   │   ├── layers.py        # Layer system
│   │   └── triggered.py     # Triggered abilities
│   └── keywords/
│       ├── __init__.py
│       ├── static.py        # Static keyword abilities
│       ├── triggered.py     # Triggered keyword abilities
│       └── activated.py     # Activated keyword abilities
├── cards/
│   ├── __init__.py
│   ├── database.py          # Card database
│   ├── parser.py            # Decklist parser
│   └── abilities.py         # Ability definitions
├── ai/
│   ├── __init__.py
│   ├── agent.py             # Base AI agent
│   ├── priority.py          # Priority decisions
│   ├── combat.py            # Combat decisions
│   └── strategy.py          # High-level strategy
├── tests/
│   ├── __init__.py
│   ├── test_priority.py
│   ├── test_stack.py
│   ├── test_combat.py
│   └── ...
└── utils/
    ├── __init__.py
    ├── logging.py
    └── replay.py
```

#### 0.5 Deliverables

- [ ] Base class definitions
- [ ] Zone system with zone change tracking
- [ ] Event bus implementation
- [ ] Object ID management
- [ ] Basic logging framework
- [ ] Unit test framework setup

---

### Phase 1: Turn Structure & Priority

**Goal:** Implement the complete turn structure with proper priority passing.

**Reference:** CR 500-514 (Turn Structure), CR 117 (Timing and Priority)

#### 1.1 Turn Structure Implementation

```python
class Turn:
    number: int
    active_player: Player
    phases: List[Phase]

class Phase:
    phase_type: PhaseType  # BEGINNING, PRECOMBAT_MAIN, COMBAT, POSTCOMBAT_MAIN, ENDING
    steps: List[Step]

class Step:
    step_type: StepType
    has_priority_round: bool
    turn_based_actions: List[Callable]

# Complete step enumeration
class StepType(Enum):
    # Beginning Phase
    UNTAP = auto()           # No priority
    UPKEEP = auto()          # Priority
    DRAW = auto()            # Priority

    # Main Phases
    PRECOMBAT_MAIN = auto()  # Priority
    POSTCOMBAT_MAIN = auto() # Priority

    # Combat Phase
    BEGINNING_OF_COMBAT = auto()  # Priority
    DECLARE_ATTACKERS = auto()    # Priority
    DECLARE_BLOCKERS = auto()     # Priority
    COMBAT_DAMAGE = auto()        # Priority (may have two: first strike + regular)
    END_OF_COMBAT = auto()        # Priority

    # Ending Phase
    END = auto()             # Priority
    CLEANUP = auto()         # Usually no priority
```

#### 1.2 Priority System

```python
class PrioritySystem:
    """Manages priority passing between players"""

    def __init__(self, game: Game):
        self.game = game
        self.priority_player: Optional[Player] = None
        self.passed_players: Set[Player] = set()

    def give_priority(self, player: Player):
        """Give priority to a player"""
        self.priority_player = player
        self.passed_players.clear()

    def pass_priority(self, player: Player):
        """Player passes priority"""
        assert player == self.priority_player
        self.passed_players.add(player)

        # Move to next player in turn order
        next_player = self.game.next_player(player)

        if next_player in self.passed_players:
            # All players passed in succession
            return PriorityResult.ALL_PASSED
        else:
            self.priority_player = next_player
            return PriorityResult.PRIORITY_PASSED

    def player_takes_action(self, player: Player):
        """Player takes an action (casts spell, activates ability)"""
        # Clear passed set - everyone gets chance to respond
        self.passed_players.clear()
```

#### 1.3 Turn Execution Flow

```python
def execute_turn(game: Game, active_player: Player):
    """Execute a complete turn"""

    # BEGINNING PHASE
    # Untap Step (no priority)
    execute_untap_step(active_player)

    # Upkeep Step
    trigger_upkeep_abilities(active_player)
    priority_round(game)

    # Draw Step
    if not (game.turn_number == 1 and active_player == game.starting_player):
        active_player.draw(1)
    trigger_draw_step_abilities(active_player)
    priority_round(game)

    # PRECOMBAT MAIN PHASE
    main_phase(game, active_player)

    # COMBAT PHASE
    combat_phase(game, active_player)

    # POSTCOMBAT MAIN PHASE
    main_phase(game, active_player)

    # ENDING PHASE
    # End Step
    trigger_end_step_abilities(active_player)
    priority_round(game)

    # Cleanup Step
    cleanup_step(game, active_player)

def priority_round(game: Game):
    """Execute a full priority round"""
    game.check_state_based_actions()  # (Phase 4)
    game.put_triggered_abilities_on_stack()  # (Phase 8)

    game.priority.give_priority(game.active_player)

    while True:
        player = game.priority.priority_player
        action = player.ai.get_priority_action(game)

        if action.type == ActionType.PASS:
            result = game.priority.pass_priority(player)
            if result == PriorityResult.ALL_PASSED:
                if game.stack.is_empty():
                    return  # Phase/step ends
                else:
                    game.stack.resolve_top()  # (Phase 2)
                    # SBAs and triggers checked, new priority round
                    game.check_state_based_actions()
                    game.put_triggered_abilities_on_stack()
                    game.priority.give_priority(game.active_player)
        else:
            game.execute_action(action)
            game.priority.player_takes_action(player)
```

#### 1.4 Deliverables

- [ ] Complete turn structure with all phases/steps
- [ ] Priority system with proper passing
- [ ] Turn-based actions (untap, draw)
- [ ] Phase/step transition logic
- [ ] Active player tracking
- [ ] Integration with AI for priority decisions

---

### Phase 2: The Stack

**Goal:** Implement the stack zone with LIFO resolution and priority between resolutions.

**Reference:** CR 405 (Stack), CR 608 (Resolving Spells and Abilities)

#### 2.1 Stack Implementation

```python
class Stack(Zone):
    """The stack zone - LIFO resolution"""

    def __init__(self):
        super().__init__()
        self.objects: List[StackObject] = []

    def push(self, obj: StackObject):
        """Add object to top of stack"""
        obj.timestamp = self.game.get_timestamp()
        self.objects.append(obj)
        self.game.events.emit(ObjectPutOnStackEvent(obj))

    def resolve_top(self):
        """Resolve the top object of the stack"""
        if not self.objects:
            return

        obj = self.objects.pop()

        if isinstance(obj, Spell):
            self._resolve_spell(obj)
        elif isinstance(obj, StackedAbility):
            self._resolve_ability(obj)

    def _resolve_spell(self, spell: Spell):
        """Resolve a spell"""
        # Check if all targets still legal (CR 608.2b)
        if spell.targets and not any(t.is_legal() for t in spell.targets):
            # Spell fizzles - removed from stack, goes to graveyard
            spell.owner.graveyard.add(spell.card)
            return

        # Execute spell effects
        spell.resolve()

        # Move card to appropriate zone
        if spell.is_permanent:
            self.game.battlefield.add(spell.as_permanent())
        else:
            spell.owner.graveyard.add(spell.card)

    def _resolve_ability(self, ability: StackedAbility):
        """Resolve a triggered or activated ability"""
        # Check targets
        if ability.targets and not any(t.is_legal() for t in ability.targets):
            return  # Ability fizzles

        ability.resolve()

class StackObject:
    """Base class for objects on the stack"""
    source: GameObject
    controller: Player
    targets: List[Target]
    timestamp: int

class Spell(StackObject):
    """A spell on the stack"""
    card: Card
    modes: List[Mode]
    x_value: Optional[int]

class StackedAbility(StackObject):
    """A triggered or activated ability on the stack"""
    ability: Ability
```

#### 2.2 Casting Spells

```python
def cast_spell(player: Player, card: Card, targets: List[Target] = None):
    """Cast a spell (CR 601)"""

    # 601.2a - Announce spell, move to stack
    spell = Spell(card=card, controller=player)

    # 601.2b - Choose modes (if modal)
    if card.is_modal:
        spell.modes = player.ai.choose_modes(card)

    # 601.2c - Choose targets
    if card.requires_targets:
        spell.targets = targets or player.ai.choose_targets(card)
        if not spell.targets:
            return False  # Can't cast without legal targets

    # 601.2d - Choose division (damage, counters)
    if card.divides_among_targets:
        spell.division = player.ai.choose_division(card, spell.targets)

    # 601.2e - Choose X value
    if card.has_x_cost:
        spell.x_value = player.ai.choose_x_value(card)

    # 601.2f - Determine total cost
    total_cost = calculate_total_cost(card, spell)

    # 601.2g - Activate mana abilities (if needed)
    # 601.2h - Pay costs
    if not player.can_pay(total_cost):
        return False
    player.pay_cost(total_cost)

    # Put on stack
    game.stack.push(spell)
    game.events.emit(SpellCastEvent(spell))

    return True
```

#### 2.3 Deliverables

- [ ] Stack zone implementation
- [ ] Spell casting process (CR 601)
- [ ] Ability stacking (triggered + activated)
- [ ] Resolution process (CR 608)
- [ ] Target legality checking
- [ ] Fizzling mechanics
- [ ] Integration with priority system

---

### Phase 3: Mana System

**Goal:** Implement colored mana, mana costs, mana pools, and mana abilities.

**Reference:** CR 106 (Mana), CR 107 (Numbers and Symbols), CR 605 (Mana Abilities)

#### 3.1 Mana Representation

```python
class Color(Enum):
    WHITE = 'W'
    BLUE = 'U'
    BLACK = 'B'
    RED = 'R'
    GREEN = 'G'
    COLORLESS = 'C'

class Mana:
    """A single mana"""
    color: Color
    source: Optional[Permanent]
    restrictions: List[ManaRestriction]  # "only for creature spells", etc.

class ManaPool:
    """A player's mana pool"""
    mana: List[Mana]

    def add(self, color: Color, amount: int = 1, source: Permanent = None):
        for _ in range(amount):
            self.mana.append(Mana(color=color, source=source))

    def can_pay(self, cost: ManaCost) -> bool:
        """Check if this pool can pay a mana cost"""
        return self._find_payment(cost) is not None

    def pay(self, cost: ManaCost) -> bool:
        """Pay a mana cost from this pool"""
        payment = self._find_payment(cost)
        if payment is None:
            return False
        for mana in payment:
            self.mana.remove(mana)
        return True

    def empty(self):
        """Empty the mana pool (between steps/phases)"""
        # Note: Some mana doesn't empty (Omnath, etc.)
        lost = [m for m in self.mana if not m.persists]
        self.mana = [m for m in self.mana if m.persists]
        if lost:
            self.game.events.emit(ManaLostEvent(self.player, lost))

class ManaCost:
    """A mana cost"""
    symbols: List[ManaSymbol]

    @property
    def cmc(self) -> int:
        """Converted mana cost / mana value"""
        return sum(s.cmc_contribution for s in self.symbols)

    @property
    def colors(self) -> Set[Color]:
        """Colors of this mana cost"""
        return {s.color for s in self.symbols if s.color}

class ManaSymbol:
    """A single mana symbol in a cost"""
    # Types: generic (3), colored (W), hybrid (W/U), phyrexian (W/P), etc.
    symbol_type: ManaSymbolType
    color: Optional[Color]
    generic_amount: Optional[int]  # For generic symbols
```

#### 3.2 Mana Abilities

```python
class ManaAbility(ActivatedAbility):
    """An activated ability that produces mana (CR 605)"""

    def is_mana_ability(self) -> bool:
        """
        A mana ability:
        - Could produce mana when it resolves
        - Doesn't target
        - Isn't a loyalty ability
        """
        return (
            self.produces_mana and
            not self.targets and
            not isinstance(self, LoyaltyAbility)
        )

    def activate(self, player: Player):
        """Mana abilities don't use the stack"""
        # Pay costs
        if not player.can_pay(self.cost):
            return False
        player.pay_cost(self.cost)

        # Immediately resolve
        self.resolve()
        return True

# Land mana abilities
BASIC_LAND_ABILITIES = {
    "Plains": ManaAbility(produces=Color.WHITE),
    "Island": ManaAbility(produces=Color.BLUE),
    "Swamp": ManaAbility(produces=Color.BLACK),
    "Mountain": ManaAbility(produces=Color.RED),
    "Forest": ManaAbility(produces=Color.GREEN),
}
```

#### 3.3 Deliverables

- [ ] Mana and ManaPool classes
- [ ] ManaCost representation with all symbol types
- [ ] Cost payment algorithm (colored before generic)
- [ ] Mana abilities (don't use stack)
- [ ] Basic land mana production
- [ ] Non-basic land mana abilities
- [ ] Mana dork creatures
- [ ] Mana pool emptying between phases
- [ ] Cost modification (additional costs, cost reduction)

---

### Phase 4: State-Based Actions

**Goal:** Implement all state-based actions that are checked before priority is given.

**Reference:** CR 704 (State-Based Actions)

#### 4.1 SBA Checker

```python
class StateBasedActionChecker:
    """Checks and performs state-based actions (CR 704)"""

    def check_and_perform(self, game: Game) -> bool:
        """
        Check all SBAs and perform them.
        Returns True if any SBAs were performed.
        Must be called repeatedly until no SBAs occur.
        """
        performed = False

        # CR 704.5a - Player with 0 or less life loses
        for player in game.players:
            if player.life <= 0:
                player.lose_game("life <= 0")
                performed = True

        # CR 704.5b - Player who drew from empty library loses
        for player in game.players:
            if player.drew_from_empty_library:
                player.lose_game("drew from empty library")
                performed = True

        # CR 704.5c - Player with 10+ poison counters loses
        for player in game.players:
            if player.poison_counters >= 10:
                player.lose_game("10+ poison counters")
                performed = True

        # CR 704.5f - Creature with toughness 0 or less dies
        for permanent in game.battlefield.creatures():
            if permanent.toughness <= 0:
                permanent.die()
                performed = True

        # CR 704.5g - Creature with lethal damage dies
        for permanent in game.battlefield.creatures():
            if permanent.damage_marked >= permanent.toughness:
                permanent.die()
                performed = True

        # CR 704.5h - Creature dealt damage by deathtouch source dies
        for permanent in game.battlefield.creatures():
            if permanent.dealt_damage_by_deathtouch:
                permanent.die()
                performed = True

        # CR 704.5i - Planeswalker with 0 loyalty dies
        for permanent in game.battlefield.planeswalkers():
            if permanent.loyalty <= 0:
                permanent.die()
                performed = True

        # CR 704.5j - Legend rule
        for player in game.players:
            legends = defaultdict(list)
            for permanent in player.battlefield.legendaries():
                legends[permanent.name].append(permanent)
            for name, copies in legends.items():
                if len(copies) > 1:
                    # Player chooses one to keep
                    to_keep = player.ai.choose_legend_to_keep(copies)
                    for copy in copies:
                        if copy != to_keep:
                            copy.die()
                    performed = True

        # CR 704.5m - Aura not attached to legal object
        for permanent in game.battlefield.auras():
            if not permanent.attached_to or not permanent.can_enchant(permanent.attached_to):
                permanent.owner.graveyard.add(permanent)
                game.battlefield.remove(permanent)
                performed = True

        # CR 704.5n - Equipment/Fortification attached to illegal permanent
        # Similar to auras

        # CR 704.5q - +1/+1 and -1/-1 counters annihilate
        for permanent in game.battlefield.permanents():
            plus = permanent.counters.get(CounterType.PLUS_ONE_PLUS_ONE, 0)
            minus = permanent.counters.get(CounterType.MINUS_ONE_MINUS_ONE, 0)
            if plus > 0 and minus > 0:
                remove = min(plus, minus)
                permanent.counters[CounterType.PLUS_ONE_PLUS_ONE] -= remove
                permanent.counters[CounterType.MINUS_ONE_MINUS_ONE] -= remove
                performed = True

        return performed

    def run_until_stable(self, game: Game):
        """Run SBA checks until no more actions are performed"""
        while self.check_and_perform(game):
            pass
```

#### 4.2 Deliverables

- [ ] Complete SBA checker
- [ ] Player loss conditions (life, library, poison)
- [ ] Creature death (toughness, damage, deathtouch)
- [ ] Planeswalker death (loyalty)
- [ ] Legend rule
- [ ] Aura/Equipment attachment checks
- [ ] Counter annihilation
- [ ] Token cease-to-exist checks
- [ ] Integration with priority (SBAs before priority given)

---

### Phase 5: Targeting System

**Goal:** Implement proper targeting with restrictions and legality checking.

**Reference:** CR 115 (Targets), CR 608.2b (Illegal Targets on Resolution)

#### 5.1 Target System

```python
class Target:
    """A target for a spell or ability"""
    requirement: TargetRequirement
    chosen: Optional[Union[Player, GameObject]]

    def is_legal(self) -> bool:
        """Check if target is still legal"""
        if self.chosen is None:
            return False
        return self.requirement.is_legal_target(self.chosen)

class TargetRequirement:
    """Defines what can be targeted"""
    target_type: TargetType  # CREATURE, PLAYER, PERMANENT, ANY, etc.
    restrictions: List[TargetRestriction]
    zone: Zone  # Usually battlefield

    def is_legal_target(self, obj: Union[Player, GameObject]) -> bool:
        # Check basic type
        if not self._matches_type(obj):
            return False

        # Check restrictions
        for restriction in self.restrictions:
            if not restriction.allows(obj):
                return False

        # Check targeting restrictions on the object
        if isinstance(obj, Permanent):
            if obj.has_hexproof and obj.controller != self.source.controller:
                return False
            if obj.has_shroud:
                return False
            # Protection checks
            if obj.has_protection_from(self.source):
                return False

        return True

class TargetRestriction:
    """A restriction on what can be targeted"""
    # Examples: "creature you control", "nonblack creature", "creature with power 4 or greater"
    restriction_type: str
    value: Any

    def allows(self, obj: Union[Player, GameObject]) -> bool:
        # Implementation depends on restriction_type
        pass

class Ward(Ability):
    """Ward - Counter spell unless controller pays cost"""
    cost: Cost

    def on_targeted(self, source: GameObject):
        if source.controller != self.permanent.controller:
            # Trigger ward ability
            ward_trigger = WardTriggeredAbility(source=self.permanent, cost=self.cost)
            game.stack.push(ward_trigger)
```

#### 5.2 Deliverables

- [ ] Target class with legality tracking
- [ ] Target requirement definitions
- [ ] Hexproof implementation
- [ ] Shroud implementation
- [ ] Protection implementation
- [ ] Ward implementation
- [ ] Target choosing AI
- [ ] Illegal target handling on resolution
- [ ] "Each" vs "target" distinction

---

### Phase 6: Combat Core

**Goal:** Implement the combat phase structure with attack and block declarations.

**Reference:** CR 506-511 (Combat Phase)

#### 6.1 Combat Structure

```python
class CombatPhase:
    """Manages the combat phase"""

    attackers: List[AttackDeclaration]
    blockers: List[BlockDeclaration]
    damage_assignment: Dict[int, List[Tuple[int, int]]]  # attacker_id -> [(target_id, damage)]

    def beginning_of_combat_step(self, game: Game):
        """CR 507 - Beginning of Combat Step"""
        # Choose player/planeswalker to attack (if multiple opponents)
        game.events.emit(BeginningOfCombatEvent())
        game.priority_round()

    def declare_attackers_step(self, game: Game):
        """CR 508 - Declare Attackers Step"""
        active = game.active_player

        # 508.1a - Active player declares attackers
        self.attackers = active.ai.choose_attackers(game)

        for decl in self.attackers:
            creature = decl.creature
            # 508.1c - Check attack restrictions
            if not self._can_attack(creature, decl.defending):
                self.attackers.remove(decl)
                continue
            # 508.1d - Tap attacker (unless vigilance)
            if not creature.has_keyword("vigilance"):
                creature.tap()
            # 508.1e - Attacking triggers
            game.events.emit(AttacksEvent(creature, decl.defending))

        # 508.1j - Pay attack costs (rare)
        # 508.1k - Emit "attacks" event for trigger purposes

        game.priority_round()

    def declare_blockers_step(self, game: Game):
        """CR 509 - Declare Blockers Step"""
        defending = game.defending_player

        # 509.1a - Defending player declares blockers
        self.blockers = defending.ai.choose_blockers(game, self.attackers)

        for decl in self.blockers:
            creature = decl.blocker
            attacker = decl.blocking

            # 509.1b - Check block restrictions
            if not self._can_block(creature, attacker):
                self.blockers.remove(decl)
                continue

            # Blocking triggers
            game.events.emit(BlocksEvent(creature, attacker))

        # 509.2 - Damage assignment order (for multiple blockers)
        # (Note: Simplified in recent rules, attackers can divide freely)

        game.priority_round()

    def combat_damage_step(self, game: Game):
        """CR 510 - Combat Damage Step"""
        # Check for first strike / double strike
        has_first_strike = any(
            a.creature.has_keyword("first_strike") or a.creature.has_keyword("double_strike")
            for a in self.attackers
        ) or any(
            b.blocker.has_keyword("first_strike") or b.blocker.has_keyword("double_strike")
            for b in self.blockers
        )

        if has_first_strike:
            # First strike damage step
            self._deal_combat_damage(game, first_strike_only=True)
            game.check_state_based_actions()
            game.priority_round()

            # Regular damage step
            self._deal_combat_damage(game, first_strike_only=False)
        else:
            # Single damage step
            self._deal_combat_damage(game, first_strike_only=False)

        game.check_state_based_actions()
        game.priority_round()

    def end_of_combat_step(self, game: Game):
        """CR 511 - End of Combat Step"""
        game.events.emit(EndOfCombatEvent())
        game.priority_round()

        # Remove creatures from combat
        self.attackers.clear()
        self.blockers.clear()
```

#### 6.2 Damage Assignment

```python
def _deal_combat_damage(self, game: Game, first_strike_only: bool):
    """Assign and deal combat damage"""

    for decl in self.attackers:
        creature = decl.creature

        # Skip if doesn't deal damage this step
        if first_strike_only:
            if not (creature.has_keyword("first_strike") or creature.has_keyword("double_strike")):
                continue
        else:
            if creature.has_keyword("first_strike") and not creature.has_keyword("double_strike"):
                continue

        # Skip if creature no longer on battlefield
        if creature not in game.battlefield:
            continue

        blockers = self._get_blockers_for(creature)
        damage = creature.power

        if not blockers:
            # Unblocked - damage to defending player/planeswalker
            self._deal_damage(creature, decl.defending, damage)
        else:
            # Blocked
            if creature.has_keyword("trample"):
                # Must assign lethal to each blocker, excess to defending
                for blocker in blockers:
                    lethal = self._lethal_damage_for(blocker, creature)
                    assigned = min(damage, lethal)
                    self._deal_damage(creature, blocker, assigned)
                    damage -= assigned
                if damage > 0:
                    self._deal_damage(creature, decl.defending, damage)
            else:
                # Divide among blockers as controller chooses
                assignment = creature.controller.ai.assign_damage(creature, blockers, damage)
                for blocker, dmg in assignment:
                    self._deal_damage(creature, blocker, dmg)

    # Blocker damage to attackers
    for decl in self.blockers:
        blocker = decl.blocker
        attacker = decl.blocking

        if first_strike_only:
            if not (blocker.has_keyword("first_strike") or blocker.has_keyword("double_strike")):
                continue
        else:
            if blocker.has_keyword("first_strike") and not blocker.has_keyword("double_strike"):
                continue

        if blocker not in game.battlefield:
            continue

        self._deal_damage(blocker, attacker, blocker.power)

def _lethal_damage_for(self, creature: Permanent, source: Permanent) -> int:
    """Calculate lethal damage for a creature"""
    if source.has_keyword("deathtouch"):
        return 1
    return max(0, creature.toughness - creature.damage_marked)
```

#### 6.3 Deliverables

- [ ] Combat phase structure with all steps
- [ ] Attacker declaration
- [ ] Blocker declaration
- [ ] Attack restrictions (defender, can't attack, must attack)
- [ ] Block restrictions (flying, menace, can't block)
- [ ] Damage assignment (attacker chooses division)
- [ ] Combat triggers (attacks, blocks, deals damage)
- [ ] Integration with priority

---

### Phase 7: Combat Keywords

**Goal:** Implement all combat-relevant keywords.

**Reference:** CR 702 (Keyword Abilities)

#### 7.1 Keyword Implementations

```python
# Static keywords that affect combat

class FlyingAbility(StaticAbility):
    """Can only be blocked by creatures with flying or reach"""
    def modify_can_be_blocked_by(self, blocker: Permanent) -> bool:
        return blocker.has_keyword("flying") or blocker.has_keyword("reach")

class ReachAbility(StaticAbility):
    """Can block creatures with flying"""
    pass  # Modifies blocking restrictions

class TrampleAbility(StaticAbility):
    """Excess damage assigned to defending player"""
    pass  # Handled in damage assignment

class DeathtouchAbility(StaticAbility):
    """Any damage dealt is lethal"""
    pass  # Modifies lethal damage calculation + marks creatures

class FirstStrikeAbility(StaticAbility):
    """Deals combat damage in first strike step"""
    pass  # Handled in combat damage step

class DoubleStrikeAbility(StaticAbility):
    """Deals combat damage in both steps"""
    pass  # Handled in combat damage step

class LifelinkAbility(StaticAbility):
    """Damage dealt causes controller to gain life"""
    # This is handled when damage is dealt
    def on_damage_dealt(self, amount: int):
        self.permanent.controller.life += amount

class VigilanceAbility(StaticAbility):
    """Doesn't tap when attacking"""
    pass  # Handled in declare attackers

class MenaceAbility(StaticAbility):
    """Can't be blocked except by two or more creatures"""
    def modify_blocking_requirements(self) -> int:
        return 2  # Minimum blockers required

class HasteAbility(StaticAbility):
    """Can attack/tap the turn it enters"""
    pass  # Ignores summoning sickness

class DefenderAbility(StaticAbility):
    """Can't attack"""
    def can_attack(self) -> bool:
        return False

class IndestructibleAbility(StaticAbility):
    """Can't be destroyed"""
    pass  # Modifies destroy effects

class HexproofAbility(StaticAbility):
    """Can't be targeted by opponents"""
    pass  # Handled in targeting

class ProtectionAbility(StaticAbility):
    """Protection from [quality]"""
    quality: ProtectionQuality  # Color, type, etc.

    def prevents_damage_from(self, source: GameObject) -> bool:
        return self.quality.matches(source)

    def prevents_targeting_by(self, source: GameObject) -> bool:
        return self.quality.matches(source)

    def prevents_blocking_by(self, creature: Permanent) -> bool:
        return self.quality.matches(creature)

    def prevents_attachment_by(self, aura_or_equipment: Permanent) -> bool:
        return self.quality.matches(aura_or_equipment)
```

#### 7.2 Deliverables

- [ ] Flying + Reach
- [ ] Trample (with deathtouch interaction)
- [ ] Deathtouch
- [ ] First Strike + Double Strike
- [ ] Lifelink
- [ ] Vigilance
- [ ] Menace
- [ ] Haste
- [ ] Defender
- [ ] Indestructible
- [ ] Hexproof
- [ ] Shroud (legacy)
- [ ] Protection from X
- [ ] Flash (covered in casting timing)

---

### Phase 8: Triggered Abilities

**Goal:** Implement triggered ability detection, stacking, and resolution.

**Reference:** CR 603 (Handling Triggered Abilities)

#### 8.1 Trigger System

```python
class TriggerCondition:
    """Defines when an ability triggers"""
    event_type: Type[Event]
    filter: Callable[[Event], bool]

    def matches(self, event: Event) -> bool:
        if not isinstance(event, self.event_type):
            return False
        return self.filter(event)

class TriggeredAbility(Ability):
    """An ability that triggers from game events"""
    trigger_condition: TriggerCondition
    effect: Effect
    intervening_if: Optional[Callable[[], bool]] = None

    def check_trigger(self, event: Event) -> bool:
        """Check if this ability triggers from the event"""
        if not self.trigger_condition.matches(event):
            return False
        if self.intervening_if and not self.intervening_if():
            return False
        return True

class TriggerManager:
    """Manages triggered ability detection and stacking"""

    def __init__(self, game: Game):
        self.game = game
        self.pending_triggers: List[Tuple[TriggeredAbility, Event]] = []

    def register_trigger(self, ability: TriggeredAbility, source: GameObject):
        """Register a triggered ability for event listening"""
        self.game.events.subscribe(
            ability.trigger_condition.event_type,
            lambda e: self._on_event(ability, source, e)
        )

    def _on_event(self, ability: TriggeredAbility, source: GameObject, event: Event):
        """Called when a potentially triggering event occurs"""
        if ability.check_trigger(event):
            self.pending_triggers.append((ability, event, source))

    def put_triggers_on_stack(self):
        """Put all pending triggers on stack in APNAP order"""
        if not self.pending_triggers:
            return

        # Group by controller
        by_controller = defaultdict(list)
        for ability, event, source in self.pending_triggers:
            controller = ability.controller or source.controller
            by_controller[controller].append((ability, event, source))

        # Active player's triggers go on stack first (resolve last)
        # Then in turn order
        order = self.game.turn_order_from(self.game.active_player)

        for player in order:
            triggers = by_controller[player]
            if not triggers:
                continue

            # Player chooses order for their triggers
            ordered = player.ai.order_triggers(triggers)

            for ability, event, source in ordered:
                # Check intervening-if again
                if ability.intervening_if and not ability.intervening_if():
                    continue

                stacked = StackedAbility(
                    ability=ability,
                    source=source,
                    controller=ability.controller or source.controller,
                    trigger_event=event
                )

                # Choose targets if needed
                if ability.requires_targets:
                    stacked.targets = player.ai.choose_targets(ability)

                self.game.stack.push(stacked)

        self.pending_triggers.clear()
```

#### 8.2 Common Triggers

```python
# Zone change triggers
class EntersBattlefieldTrigger(TriggerCondition):
    """Triggers when a permanent enters the battlefield"""
    event_type = ZoneChangeEvent

    def filter(self, event: ZoneChangeEvent) -> bool:
        return event.to_zone == Zone.BATTLEFIELD

class DiesTrigger(TriggerCondition):
    """Triggers when a creature dies"""
    event_type = ZoneChangeEvent

    def filter(self, event: ZoneChangeEvent) -> bool:
        return (event.from_zone == Zone.BATTLEFIELD and
                event.to_zone == Zone.GRAVEYARD and
                event.object.is_creature)

class LeavesBattlefieldTrigger(TriggerCondition):
    """Triggers when a permanent leaves the battlefield"""
    event_type = ZoneChangeEvent

    def filter(self, event: ZoneChangeEvent) -> bool:
        return event.from_zone == Zone.BATTLEFIELD

# Combat triggers
class AttacksTrigger(TriggerCondition):
    event_type = AttacksEvent

class BlocksTrigger(TriggerCondition):
    event_type = BlocksEvent

class DealsDamageTrigger(TriggerCondition):
    event_type = DamageEvent

# Phase/step triggers
class BeginningOfUpkeepTrigger(TriggerCondition):
    event_type = StepBeginEvent

    def filter(self, event: StepBeginEvent) -> bool:
        return event.step == StepType.UPKEEP

class BeginningOfEndStepTrigger(TriggerCondition):
    event_type = StepBeginEvent

    def filter(self, event: StepBeginEvent) -> bool:
        return event.step == StepType.END

# Spell/ability triggers
class SpellCastTrigger(TriggerCondition):
    event_type = SpellCastEvent

class LandfallTrigger(TriggerCondition):
    """Landfall - Whenever a land enters the battlefield under your control"""
    event_type = ZoneChangeEvent

    def filter(self, event: ZoneChangeEvent) -> bool:
        return (event.to_zone == Zone.BATTLEFIELD and
                event.object.is_land and
                event.object.controller == self.source.controller)
```

#### 8.3 Deliverables

- [ ] TriggerCondition framework
- [ ] TriggeredAbility class
- [ ] TriggerManager for event listening
- [ ] APNAP ordering for trigger stacking
- [ ] Intervening-if clause handling
- [ ] Common trigger patterns (ETB, dies, attacks, etc.)
- [ ] Landfall implementation
- [ ] Phase/step triggers
- [ ] Spell cast triggers

---

### Phase 9: Activated Abilities

**Goal:** Implement activated abilities with costs, timing, and activation restrictions.

**Reference:** CR 602 (Activating Activated Abilities)

#### 9.1 Activated Ability System

```python
class ActivatedAbility(Ability):
    """An ability that can be activated by paying a cost"""
    cost: Cost
    effect: Effect
    timing: TimingRestriction = TimingRestriction.INSTANT
    activation_limit: Optional[ActivationLimit] = None

    def can_activate(self, game: Game, player: Player) -> bool:
        """Check if this ability can be activated"""
        # Check controller
        if player != self.source.controller:
            return False

        # Check timing
        if self.timing == TimingRestriction.SORCERY:
            if game.stack.objects or game.active_player != player:
                return False
            if game.current_step not in [StepType.PRECOMBAT_MAIN, StepType.POSTCOMBAT_MAIN]:
                return False

        # Check activation limit
        if self.activation_limit:
            if not self.activation_limit.can_activate(game, self):
                return False

        # Check if cost can be paid
        if not player.can_pay(self.cost):
            return False

        return True

    def activate(self, game: Game, player: Player, targets: List[Target] = None):
        """Activate this ability"""
        # Pay cost
        player.pay_cost(self.cost)

        # Track activation for limits
        if self.activation_limit:
            self.activation_limit.record_activation(game)

        # Put on stack (unless mana ability)
        if isinstance(self, ManaAbility):
            self.resolve()
        else:
            stacked = StackedAbility(
                ability=self,
                source=self.source,
                controller=player,
                targets=targets or []
            )
            game.stack.push(stacked)

class Cost:
    """A cost to pay for an ability or spell"""
    mana: Optional[ManaCost] = None
    tap: bool = False
    sacrifice: Optional[SacrificeRequirement] = None
    discard: Optional[DiscardRequirement] = None
    pay_life: int = 0
    other: List[OtherCost] = field(default_factory=list)

    def can_pay(self, player: Player, source: Permanent) -> bool:
        if self.mana and not player.mana_pool.can_pay(self.mana):
            return False
        if self.tap and source.is_tapped:
            return False
        if self.sacrifice and not player.can_sacrifice(self.sacrifice):
            return False
        if self.pay_life and player.life < self.pay_life:
            return False
        return True

class ActivationLimit:
    """Limits on how often an ability can be activated"""
    limit_type: LimitType  # ONCE_PER_TURN, ONCE_PER_GAME, X_TIMES_PER_TURN
    count: int = 1

    activations: Dict[int, int] = field(default_factory=dict)  # turn -> count

    def can_activate(self, game: Game, ability: Ability) -> bool:
        if self.limit_type == LimitType.ONCE_PER_TURN:
            return self.activations.get(game.turn_number, 0) < self.count
        return True

class TimingRestriction(Enum):
    INSTANT = auto()   # Any time you have priority
    SORCERY = auto()   # Only during your main phase, stack empty
```

#### 9.2 Loyalty Abilities

```python
class LoyaltyAbility(ActivatedAbility):
    """A planeswalker loyalty ability"""
    loyalty_cost: int  # Positive for +, negative for -

    def can_activate(self, game: Game, player: Player) -> bool:
        # Only once per turn, only at sorcery speed
        if not super().can_activate(game, player):
            return False

        # Check loyalty
        if self.loyalty_cost < 0:
            if self.source.loyalty < abs(self.loyalty_cost):
                return False

        # Only one loyalty ability per turn per planeswalker
        if game.loyalty_activated_this_turn.get(self.source.object_id):
            return False

        return True

    def activate(self, game: Game, player: Player, targets: List[Target] = None):
        # Adjust loyalty as cost
        self.source.loyalty += self.loyalty_cost

        # Track that we activated
        game.loyalty_activated_this_turn[self.source.object_id] = True

        # Put on stack
        super().activate(game, player, targets)
```

#### 9.3 Deliverables

- [ ] ActivatedAbility framework
- [ ] Cost representation (mana, tap, sacrifice, life, etc.)
- [ ] Timing restrictions (instant vs sorcery speed)
- [ ] Activation limits (once per turn, etc.)
- [ ] Mana abilities (don't use stack)
- [ ] Loyalty abilities
- [ ] Equipment abilities (Equip)
- [ ] Common activated abilities from database

---

### Phase 10: Continuous Effects & Layers

**Goal:** Implement the layer system for continuous effects.

**Reference:** CR 613 (Continuous Effects), CR 613.1-613.7 (Layer System)

#### 10.1 Layer System

```python
class Layer(Enum):
    """The seven layers of continuous effects"""
    LAYER_1_COPY = 1          # Copy effects
    LAYER_2_CONTROL = 2       # Control-changing effects
    LAYER_3_TEXT = 3          # Text-changing effects
    LAYER_4_TYPE = 4          # Type-changing effects
    LAYER_5_COLOR = 5         # Color-changing effects
    LAYER_6_ABILITY = 6       # Ability adding/removing
    LAYER_7A_CDA = 7.1        # Characteristic-defining abilities
    LAYER_7B_SET_PT = 7.2     # Set P/T to specific value
    LAYER_7C_MODIFY_PT = 7.3  # Modify P/T (+X/+Y)
    LAYER_7D_COUNTER = 7.4    # P/T from counters
    LAYER_7E_SWITCH = 7.5     # Switch P/T

class ContinuousEffect:
    """A continuous effect that modifies game state"""
    source: GameObject
    layer: Layer
    timestamp: int
    duration: Duration
    affected: AffectedObjects
    modification: Modification
    dependency: List['ContinuousEffect'] = field(default_factory=list)

    def applies_to(self, obj: GameObject) -> bool:
        """Check if this effect applies to an object"""
        return self.affected.matches(obj)

    def apply(self, obj: GameObject):
        """Apply this effect to an object"""
        self.modification.apply(obj)

class ContinuousEffectManager:
    """Manages all continuous effects"""

    effects: List[ContinuousEffect]

    def apply_all_effects(self, game: Game):
        """Apply all continuous effects in layer order"""

        # Get all objects that could be affected
        objects = list(game.battlefield.permanents())

        # Apply effects layer by layer
        for layer in Layer:
            layer_effects = [e for e in self.effects if e.layer == layer]

            # Sort by timestamp, respecting dependencies
            sorted_effects = self._sort_with_dependencies(layer_effects)

            for effect in sorted_effects:
                for obj in objects:
                    if effect.applies_to(obj):
                        effect.apply(obj)

    def _sort_with_dependencies(self, effects: List[ContinuousEffect]) -> List[ContinuousEffect]:
        """Topological sort respecting dependencies"""
        # Dependency: Effect A depends on Effect B if A's existence or
        # applicability depends on what B does
        # Example: "Creatures you control have flying" depends on
        #          "All creatures are artifacts" if checking for creatures

        result = []
        remaining = effects.copy()

        while remaining:
            # Find effects with no unsatisfied dependencies
            ready = [e for e in remaining
                    if all(d in result for d in e.dependency)]

            if not ready:
                # Dependency cycle - use timestamps
                ready = sorted(remaining, key=lambda e: e.timestamp)[:1]

            # Sort ready effects by timestamp
            ready.sort(key=lambda e: e.timestamp)

            for e in ready:
                result.append(e)
                remaining.remove(e)

        return result
```

#### 10.2 Common Continuous Effects

```python
# Static abilities that create continuous effects

class AnthemEffect(ContinuousEffect):
    """All creatures you control get +1/+1"""
    layer = Layer.LAYER_7C_MODIFY_PT

    def affected_matches(self, obj: GameObject) -> bool:
        return (obj.is_creature and
                obj.controller == self.source.controller)

    def apply(self, obj: GameObject):
        obj.power += 1
        obj.toughness += 1

class TypeChangingEffect(ContinuousEffect):
    """Target creature becomes an artifact in addition to its other types"""
    layer = Layer.LAYER_4_TYPE

    def apply(self, obj: GameObject):
        obj.types.add(CardType.ARTIFACT)

class AbilityGrantingEffect(ContinuousEffect):
    """Creatures you control have flying"""
    layer = Layer.LAYER_6_ABILITY

    def apply(self, obj: GameObject):
        obj.abilities.append(FlyingAbility(source=self.source))
```

#### 10.3 Deliverables

- [ ] Layer enumeration
- [ ] ContinuousEffect base class
- [ ] Effect manager with layer ordering
- [ ] Timestamp tracking
- [ ] Dependency detection and resolution
- [ ] P/T modification through layers
- [ ] Type changing effects
- [ ] Ability granting/removing effects
- [ ] Color changing effects
- [ ] Characteristic-defining abilities

---

### Phase 11: Replacement Effects

**Goal:** Implement replacement effects and prevention effects.

**Reference:** CR 614 (Replacement Effects), CR 615 (Prevention Effects)

#### 11.1 Replacement Effect System

```python
class ReplacementEffect:
    """An effect that replaces an event with a different event"""
    source: GameObject
    replaced_event: Type[Event]
    condition: Callable[[Event], bool]
    replacement: Callable[[Event], Optional[Event]]
    is_self_replacement: bool = False

    def applies_to(self, event: Event) -> bool:
        """Check if this replacement applies to an event"""
        if not isinstance(event, self.replaced_event):
            return False
        return self.condition(event)

    def replace(self, event: Event) -> Optional[Event]:
        """Replace the event, returning the new event (or None)"""
        return self.replacement(event)

class PreventionEffect(ReplacementEffect):
    """A replacement effect that prevents damage"""
    prevented_type: Type[DamageEvent] = DamageEvent
    amount: Optional[int] = None  # None = all damage

    def applies_to(self, event: Event) -> bool:
        if not isinstance(event, DamageEvent):
            return False
        return self.condition(event)

    def replace(self, event: DamageEvent) -> Optional[DamageEvent]:
        if self.amount is None:
            # Prevent all damage
            return None
        else:
            # Prevent up to N damage
            prevented = min(event.amount, self.amount)
            self.amount -= prevented
            event.amount -= prevented
            if event.amount <= 0:
                return None
            return event

class ReplacementEffectManager:
    """Manages replacement effects"""

    effects: List[ReplacementEffect]

    def process_event(self, event: Event, affected_player: Player) -> Optional[Event]:
        """Process an event through replacement effects"""

        applicable = [e for e in self.effects if e.applies_to(event)]

        if not applicable:
            return event

        # Self-replacement rules apply first
        self_replacements = [e for e in applicable if e.is_self_replacement]
        for effect in self_replacements:
            event = effect.replace(event)
            if event is None:
                return None
            applicable.remove(effect)

        # If multiple replacements apply, affected player/controller chooses
        while applicable:
            if len(applicable) == 1:
                chosen = applicable[0]
            else:
                chosen = affected_player.ai.choose_replacement_effect(applicable)

            event = chosen.replace(event)
            if event is None:
                return None

            applicable.remove(chosen)

            # Recheck which effects still apply
            applicable = [e for e in applicable if e.applies_to(event)]

        return event
```

#### 11.2 Common Replacement Effects

```python
# "If you would draw a card, instead..."
class DrawReplacementEffect(ReplacementEffect):
    replaced_event = DrawEvent

    # Example: Notion Thief - opponents draw -> you draw
    def condition(self, event: DrawEvent) -> bool:
        return event.player != self.source.controller

    def replace(self, event: DrawEvent) -> DrawEvent:
        return DrawEvent(player=self.source.controller, count=event.count)

# "If damage would be dealt, prevent it"
class DamagePreventionEffect(PreventionEffect):
    def condition(self, event: DamageEvent) -> bool:
        # Protection from red - prevent damage from red sources
        return Color.RED in event.source.colors

# "Enters the battlefield with counters"
class ETBCounterEffect(ReplacementEffect):
    replaced_event = ZoneChangeEvent
    is_self_replacement = True

    counter_type: CounterType
    count: int

    def condition(self, event: ZoneChangeEvent) -> bool:
        return (event.object == self.source and
                event.to_zone == Zone.BATTLEFIELD)

    def replace(self, event: ZoneChangeEvent) -> ZoneChangeEvent:
        # Add counters to object before it enters
        event.object.counters[self.counter_type] = self.count
        return event

# "Dies" triggers vs exile replacement
class ExileInsteadOfDieEffect(ReplacementEffect):
    replaced_event = ZoneChangeEvent

    def condition(self, event: ZoneChangeEvent) -> bool:
        return (event.from_zone == Zone.BATTLEFIELD and
                event.to_zone == Zone.GRAVEYARD)

    def replace(self, event: ZoneChangeEvent) -> ZoneChangeEvent:
        event.to_zone = Zone.EXILE
        return event
```

#### 11.3 Deliverables

- [ ] ReplacementEffect framework
- [ ] PreventionEffect subclass
- [ ] Effect manager with proper ordering
- [ ] Self-replacement rule handling
- [ ] Player choice for multiple applicable effects
- [ ] "As enters" effects
- [ ] Damage prevention
- [ ] Draw replacement
- [ ] Zone change replacement
- [ ] "If would die, instead" effects

---

### Phase 12: Card Database v2

**Goal:** Enhanced card data with full ability representation.

#### 12.1 Enhanced Card Data Format

```python
class CardData:
    """Complete card data from database"""
    name: str
    mana_cost: ManaCost
    types: Set[CardType]
    subtypes: Set[str]
    supertypes: Set[Supertype]
    oracle_text: str
    power: Optional[str]  # Can be "*" or "X"
    toughness: Optional[str]
    loyalty: Optional[int]
    keywords: List[str]
    abilities: List[AbilityData]
    color_identity: Set[Color]

class AbilityData:
    """Parsed ability data"""
    ability_type: AbilityType  # TRIGGERED, ACTIVATED, STATIC, MANA
    trigger_condition: Optional[str]
    cost: Optional[str]
    effect: str
    targets: Optional[str]

# Example card data
CARD_DATA = {
    "Magebane Lizard": CardData(
        name="Magebane Lizard",
        mana_cost=ManaCost.parse("{1}{R}"),
        types={CardType.CREATURE},
        subtypes={"Lizard"},
        supertypes=set(),
        oracle_text="Whenever an opponent casts a noncreature spell, Magebane Lizard deals 1 damage to that player.",
        power="2",
        toughness="1",
        keywords=[],
        abilities=[
            AbilityData(
                ability_type=AbilityType.TRIGGERED,
                trigger_condition="whenever an opponent casts a noncreature spell",
                effect="deals 1 damage to that player",
                targets=None
            )
        ],
        color_identity={Color.RED}
    )
}
```

#### 12.2 Ability Parsing

```python
class AbilityParser:
    """Parse Oracle text into structured abilities"""

    TRIGGER_PATTERNS = [
        (r"^When(ever)? (.*?),", "triggered"),
        (r"^At the beginning of (.*?),", "triggered"),
        (r"^(.*?) enters the battlefield", "etb"),
    ]

    ACTIVATED_PATTERN = r"^(.*?): (.*)"

    KEYWORD_PATTERNS = [
        (r"\bflying\b", "flying"),
        (r"\btrample\b", "trample"),
        (r"\bdeathtouch\b", "deathtouch"),
        # ... etc
    ]

    def parse(self, oracle_text: str) -> List[AbilityData]:
        abilities = []

        # Split into paragraphs (each is typically one ability)
        paragraphs = oracle_text.split("\n")

        for para in paragraphs:
            ability = self._parse_paragraph(para)
            if ability:
                abilities.append(ability)

        return abilities
```

#### 12.3 Deliverables

- [ ] Enhanced CardData class
- [ ] ManaCost parser ("{2}{U}{U}" -> ManaCost object)
- [ ] Ability parsing from Oracle text
- [ ] Keyword detection
- [ ] Trigger condition parsing
- [ ] Cost parsing for activated abilities
- [ ] Effect parsing (damage, draw, destroy, etc.)
- [ ] Modal card support
- [ ] Transform/MDFC support
- [ ] Scryfall API integration for data updates

---

### Phase 13: AI Improvements

**Goal:** Priority-aware AI that can make instant-speed decisions.

#### 13.1 Enhanced AI Architecture

```python
class PriorityAwareAI:
    """AI that understands priority and instant-speed play"""

    def get_priority_action(self, game: Game) -> Action:
        """Decide what to do when we have priority"""

        player = self.player

        # Check if we need to respond to something on stack
        if not game.stack.is_empty():
            response = self._evaluate_response(game)
            if response:
                return response

        # Main phase actions
        if self._is_main_phase(game):
            action = self._evaluate_main_phase(game)
            if action:
                return action

        # Combat phase actions
        if game.current_step == StepType.DECLARE_ATTACKERS:
            return self._evaluate_combat_tricks(game)

        # Default: pass priority
        return Action(type=ActionType.PASS)

    def _evaluate_response(self, game: Game) -> Optional[Action]:
        """Evaluate if we should respond to the stack"""

        top = game.stack.top()

        # Counterspell check
        if isinstance(top, Spell) and top.controller != self.player:
            counters = self._find_counterspells(game)
            if counters and self._should_counter(top, counters):
                return self._cast_counterspell(counters[0], top)

        # Combat trick check
        if isinstance(top, StackedAbility) and "damage" in str(top):
            tricks = self._find_combat_tricks(game)
            if tricks:
                return self._use_combat_trick(tricks[0])

        return None

    def _should_counter(self, spell: Spell, counters: List[Card]) -> bool:
        """Decide if a spell is worth countering"""
        threat_level = self._evaluate_threat(spell)
        return threat_level >= 7  # Threshold for countering

class CombatMathAI:
    """AI for combat decisions with full keyword awareness"""

    def choose_attackers(self, game: Game) -> List[AttackDeclaration]:
        """Choose optimal attackers considering all keywords"""

        available = [c for c in self.player.creatures()
                    if self._can_attack(c, game)]

        # Evaluate each potential attack
        attack_scores = []
        for creature in available:
            score = self._evaluate_attack(creature, game)
            attack_scores.append((creature, score))

        # Consider lethal
        if self._can_attack_for_lethal(available, game):
            return [AttackDeclaration(c, game.defending_player)
                   for c in available]

        # Otherwise, attack with profitable creatures
        return [AttackDeclaration(c, game.defending_player)
               for c, score in attack_scores if score > 0]

    def _evaluate_attack(self, creature: Permanent, game: Game) -> float:
        """Evaluate how good an attack is"""
        score = 0.0

        blockers = self._get_potential_blockers(game)

        # Evasion
        if creature.has_keyword("flying"):
            ground_blockers = [b for b in blockers
                              if not b.has_keyword("flying") and
                              not b.has_keyword("reach")]
            if not any(b.has_keyword("flying") or b.has_keyword("reach") for b in blockers):
                score += creature.power  # Unblockable damage value

        # Trample
        if creature.has_keyword("trample"):
            best_blocker = max(blockers, key=lambda b: b.toughness, default=None)
            if best_blocker:
                excess = creature.power - best_blocker.toughness
                if excess > 0:
                    score += excess * 0.8

        # First strike advantage
        if creature.has_keyword("first_strike") or creature.has_keyword("double_strike"):
            killable = [b for b in blockers if b.toughness <= creature.power]
            score += len(killable) * 0.5

        # Deathtouch trades up
        if creature.has_keyword("deathtouch"):
            big_creatures = [b for b in blockers if b.power >= 3]
            score += len(big_creatures) * 0.3

        return score
```

#### 13.2 Deliverables

- [ ] Priority-aware decision making
- [ ] Instant-speed response evaluation
- [ ] Counterspell AI
- [ ] Combat trick timing
- [ ] Full combat math with all keywords
- [ ] Threat evaluation
- [ ] Card advantage evaluation
- [ ] Mulligan decisions
- [ ] Sideboard decisions (Phase 15)

---

### Phase 14: Testing & Validation

**Goal:** Comprehensive test suite validating rules accuracy.

#### 14.1 Test Categories

```python
# Unit tests for individual systems

class TestPrioritySystem:
    def test_active_player_receives_priority_first(self):
        pass

    def test_priority_passes_in_turn_order(self):
        pass

    def test_all_pass_resolves_stack(self):
        pass

class TestStackResolution:
    def test_lifo_resolution(self):
        pass

    def test_fizzle_on_illegal_targets(self):
        pass

    def test_partial_resolution_with_some_legal_targets(self):
        pass

class TestCombatDamage:
    def test_first_strike_deals_first(self):
        """First strike creature should kill regular creature before it deals damage"""
        pass

    def test_deathtouch_one_damage_lethal(self):
        """1 damage from deathtouch should kill any creature"""
        pass

    def test_trample_with_deathtouch(self):
        """Deathtouch + trample should only need 1 damage to each blocker"""
        pass

    def test_lifelink_timing(self):
        """Lifelink should gain life simultaneously with damage"""
        pass

# Integration tests

class TestKnownInteractions:
    """Tests for known complex interactions"""

    def test_indestructible_vs_deathtouch(self):
        """Deathtouch doesn't destroy indestructible"""
        pass

    def test_protection_prevents_damage(self):
        """Protection from red prevents red damage"""
        pass

    def test_hexproof_vs_wrath(self):
        """Hexproof doesn't prevent board wipes"""
        pass

    def test_replacement_effect_ordering(self):
        """Player chooses order of replacement effects"""
        pass
```

#### 14.2 MTGO Comparison Testing

```python
class MTGOComparisonTest:
    """Compare engine results with known MTGO game states"""

    def load_mtgo_replay(self, replay_file: str) -> GameReplay:
        """Load an MTGO game replay for comparison"""
        pass

    def verify_state_matches(self, engine_state: GameState, mtgo_state: GameState):
        """Verify our engine matches MTGO's state"""
        assert engine_state.p1_life == mtgo_state.p1_life
        assert engine_state.p2_life == mtgo_state.p2_life
        # ... etc
```

#### 14.3 Deliverables

- [ ] Unit tests for all core systems
- [ ] Integration tests for cross-system interaction
- [ ] Known interaction tests (edge cases)
- [ ] Regression test suite
- [ ] Performance benchmarks
- [ ] MTGO comparison framework (if replays available)
- [ ] Fuzzing for crash discovery
- [ ] CI/CD integration

---

### Phase 15: Polish & Extensions

**Goal:** Additional features for competitive analysis.

#### 15.1 Sideboarding

```python
class Sideboard:
    """15-card sideboard management"""
    cards: List[Card]

class SideboardPlan:
    """Sideboard plan for a matchup"""
    out: Dict[str, int]  # Card name -> count to remove
    in_: Dict[str, int]  # Card name -> count to add

class Match:
    """Best-of-3 match with sideboarding"""

    def play_match(self, deck1: Deck, deck2: Deck) -> MatchResult:
        # Game 1
        result1 = self.play_game(deck1.mainboard, deck2.mainboard)

        # Sideboard
        deck1_g2 = self.apply_sideboard(deck1, result1, game=2)
        deck2_g2 = self.apply_sideboard(deck2, result1, game=2)

        # Game 2
        result2 = self.play_game(deck1_g2, deck2_g2)

        if result1.winner == result2.winner:
            return MatchResult(winner=result1.winner, games=[result1, result2])

        # Sideboard again for game 3
        deck1_g3 = self.apply_sideboard(deck1, result2, game=3)
        deck2_g3 = self.apply_sideboard(deck2, result2, game=3)

        # Game 3
        result3 = self.play_game(deck1_g3, deck2_g3)

        return MatchResult(winner=result3.winner, games=[result1, result2, result3])
```

#### 15.2 Replay System

```python
class GameReplay:
    """Record and replay games"""

    actions: List[Action]
    random_seed: int
    initial_libraries: Tuple[List[Card], List[Card]]

    def save(self, filename: str):
        pass

    @classmethod
    def load(cls, filename: str) -> 'GameReplay':
        pass

    def replay(self) -> Game:
        """Replay the game deterministically"""
        random.seed(self.random_seed)
        game = Game(self.initial_libraries)
        for action in self.actions:
            game.execute(action)
        return game
```

#### 15.3 Statistics & Analysis

```python
class MatchupAnalysis:
    """Statistical analysis of matchups"""

    def run_simulation(self, deck1: Deck, deck2: Deck,
                       iterations: int = 1000) -> MatchupStats:
        wins = {1: 0, 2: 0}
        game_details = []

        for _ in range(iterations):
            result = self.play_match(deck1, deck2)
            wins[result.winner] += 1
            game_details.append(result)

        return MatchupStats(
            deck1_winrate=wins[1] / iterations,
            deck2_winrate=wins[2] / iterations,
            average_game_length=...,
            key_cards=self._identify_key_cards(game_details),
            # ...
        )
```

#### 15.4 Deliverables

- [ ] Sideboard support
- [ ] Sideboard AI
- [ ] Best-of-3 match runner
- [ ] Game replay recording
- [ ] Replay playback
- [ ] Matchup statistics
- [ ] Win rate analysis
- [ ] Key card identification
- [ ] Mulligan statistics
- [ ] Export formats (JSON, CSV)

---

## Testing Strategy

### Test Pyramid

```
        /\
       /  \     End-to-End Tests (full matches)
      /----\
     /      \   Integration Tests (multi-system)
    /--------\
   /          \ Unit Tests (individual functions)
  /------------\
```

### Test Coverage Goals

| Phase | Target Coverage |
|-------|----------------|
| Core Systems (0-4) | 95% |
| Combat (6-7) | 90% |
| Abilities (8-9) | 85% |
| Effects (10-11) | 85% |
| AI (13) | 70% |

### Continuous Integration

- Run tests on every commit
- Block merge on test failure
- Performance regression detection
- Coverage reporting

---

## Milestones & Checkpoints

### Milestone 1: "It's a Game" (Phases 0-4)
- **Criteria:** Can play a game with lands, creatures, and basic spells
- **Verification:** Priority passes, stack resolves, creatures can attack and die

### Milestone 2: "Combat Works" (Phases 5-7)
- **Criteria:** All combat keywords function correctly
- **Verification:** First strike, deathtouch, trample all work as expected

### Milestone 3: "Full Abilities" (Phases 8-11)
- **Criteria:** Triggered and activated abilities work with proper timing
- **Verification:** ETB triggers, dies triggers, activated abilities all function

### Milestone 4: "Competitive Ready" (Phases 12-14)
- **Criteria:** Engine passes validation against known interactions
- **Verification:** Test suite passes, no known rules violations

### Milestone 5: "Analysis Tool" (Phase 15)
- **Criteria:** Can run matchup simulations and generate statistics
- **Verification:** Produces meaningful win rate data for known matchups

---

## Appendix: Reference Material

### Official Rules Documents
- [MTG Comprehensive Rules](https://magic.wizards.com/en/rules)
- [MTGO Advanced Client Guide](https://www.mtgo.com/en/mtgo/advanced)

### Key Rule Sections
- CR 117: Timing and Priority
- CR 405: Stack
- CR 500-514: Turn Structure
- CR 506-511: Combat Phase
- CR 601-602: Casting/Activating
- CR 603: Triggered Abilities
- CR 608: Resolution
- CR 613: Continuous Effects
- CR 614: Replacement Effects
- CR 702: Keyword Abilities
- CR 704: State-Based Actions

---

*Plan Version: 1.0*
*Created: December 28, 2025*
*Engine Target: V3.0*
