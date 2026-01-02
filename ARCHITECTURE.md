# MTGO Engine - System Architecture

Comprehensive architectural documentation for the MTGO Magic: The Gathering game engine (V3).

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Design Philosophy](#design-philosophy)
4. [Core Architecture](#core-architecture)
5. [Module Descriptions](#module-descriptions)
6. [Data Flow](#data-flow)
7. [Game Loop Architecture](#game-loop-architecture)
8. [Priority and Stack System](#priority-and-stack-system)
9. [Design Decisions](#design-decisions)
10. [Extension Points](#extension-points)

## Executive Summary

The MTGO Engine V3 is a comprehensive, rules-accurate implementation of Magic: The Gathering game logic. Built entirely in Python with zero external dependencies, it simulates complete MTG games following the Comprehensive Rules (CR).

**Key Characteristics:**

- **Rules-First Design**: Directly implements MTG Comprehensive Rules sections
- **Zero Dependencies**: Pure Python 3.10+ standard library implementation
- **Modular Architecture**: Clear separation between game systems
- **Type-Safe**: Extensive use of type hints and dataclasses
- **Event-Driven**: Event bus system for triggers and state changes
- **Extensible**: Plugin architecture for AI agents and custom abilities

**Primary Use Cases:**

- Automated deck testing and matchup analysis
- AI agent development and training
- Rules verification and edge case testing
- Tournament simulation and meta analysis
- Educational tool for learning MTG rules

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MTGO Engine V3                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Game Loop   │  │   AI Agent   │  │ Deck Parser  │     │
│  │  Controller  │◄─┤   Interface  │  │  & Database  │     │
│  └──────┬───────┘  └──────────────┘  └──────┬───────┘     │
│         │                                     │             │
│  ┌──────▼──────────────────────────────────┬─▼───────┐    │
│  │          Game State Manager             │ Card DB  │    │
│  │                                          └──────────┘    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                 │
│  │  │  Zone   │  │ Priority│  │  Stack  │                 │
│  │  │ Manager │  │ System  │  │ Manager │                 │
│  │  └─────────┘  └─────────┘  └─────────┘                 │
│  │                                                          │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                 │
│  │  │ Combat  │  │  Mana   │  │ Trigger │                 │
│  │  │ Manager │  │ Manager │  │ Manager │                 │
│  │  └─────────┘  └─────────┘  └─────────┘                 │
│  │                                                          │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                 │
│  │  │  Turn   │  │  State- │  │ Effects │                 │
│  │  │ Manager │  │  Based  │  │  Layer  │                 │
│  │  │         │  │ Actions │  │ System  │                 │
│  │  └─────────┘  └─────────┘  └─────────┘                 │
│  │                                                          │
│  │  ┌─────────────────────────────────────┐               │
│  │  │        Event Bus System             │               │
│  │  └─────────────────────────────────────┘               │
│  └─────────────────────────────────────────────────────────┘
│                                                             │
└─────────────────────────────────────────────────────────────┘

         ▲                                      ▲
         │                                      │
    ┌────┴─────┐                          ┌────┴──────┐
    │  Player  │                          │  Player   │
    │    1     │                          │     2     │
    │  (AI)    │                          │   (AI)    │
    └──────────┘                          └───────────┘
```

### Component Boundaries

The engine is organized into distinct subsystems:

| Subsystem | Responsibility | CR Section |
|-----------|---------------|------------|
| **Game** | Core game controller and orchestration | CR 100-104 |
| **Zones** | Library, hand, battlefield, graveyard, etc. | CR 400-406 |
| **Objects** | Cards, permanents, spells, abilities | CR 109-113 |
| **Turn Structure** | Phases, steps, turn progression | CR 500-514 |
| **Priority** | Priority passing and action timing | CR 117 |
| **Stack** | LIFO spell/ability resolution | CR 405, 608 |
| **Combat** | Attack/block declarations and damage | CR 506-511 |
| **Mana** | Mana pool and payment system | CR 106 |
| **Effects** | Continuous, triggered, activated abilities | CR 603, 604, 611-613 |
| **SBA** | State-based actions | CR 704 |
| **Events** | Event bus and trigger detection | CR 603 |

## Design Philosophy

### Principles

1. **Comprehensive Rules Fidelity**
   - Each module references specific CR sections
   - Implementation follows CR structure and terminology
   - Comments cite rule numbers for traceability

2. **Zero External Dependencies**
   - Uses only Python standard library
   - Ensures easy deployment and maintenance
   - Reduces version conflict issues
   - Facilitates long-term stability

3. **Type Safety First**
   - Extensive use of Python type hints
   - Dataclasses for structured data
   - Enums for discrete states
   - TYPE_CHECKING guards to avoid circular imports

4. **Event-Driven Architecture**
   - Event bus for loose coupling
   - Triggers subscribe to game events
   - Easy to extend with new trigger types
   - Clear separation of concerns

5. **Immutability Where Possible**
   - Characteristics copying for layer system
   - Frozen dataclasses for configuration
   - Reduces state mutation bugs

### Design Constraints

**Constraints Accepted:**

- AI decision-making is simplified (not full game-tree search)
- Not a networked multiplayer system (local only)
- Limited to two-player games (multiplayer not yet implemented)
- Card implementations are limited to common mechanics

**Rationale:**

These constraints allow focus on rules accuracy and system reliability over breadth of features.

## Core Architecture

### Engine V3 Directory Structure

```
Engine/v3/
├── __init__.py
├── ai/                          # AI agent system
│   ├── __init__.py
│   └── agent.py                 # AIAgent interface, SimpleAI
├── cards/                       # Card database
│   ├── __init__.py
│   ├── database.py              # CardData, CardDatabase
│   └── parser.py                # Decklist parsing
├── engine/                      # Core game engine
│   ├── __init__.py
│   ├── combat.py                # Combat manager (CR 506-511)
│   ├── events.py                # Event bus system
│   ├── game.py                  # Main Game class
│   ├── mana.py                  # Mana system (CR 106)
│   ├── match.py                 # Match runner (best-of-N)
│   ├── objects.py               # GameObject, Card, Permanent
│   ├── player.py                # Player class, ManaPool
│   ├── priority.py              # Priority system (CR 117)
│   ├── replay.py                # Replay recording
│   ├── sba.py                   # State-based actions (CR 704)
│   ├── stack.py                 # Stack manager (CR 405, 608)
│   ├── targeting.py             # Target validation
│   ├── turns.py                 # Turn structure (CR 500-514)
│   ├── types.py                 # Type definitions and enums
│   ├── zones.py                 # Zone manager (CR 400-406)
│   ├── effects/                 # Effects subsystem
│   │   ├── __init__.py
│   │   ├── activated.py         # Activated abilities (CR 604)
│   │   ├── continuous.py        # Continuous effects (CR 611-613)
│   │   ├── layers.py            # Layer system (CR 613)
│   │   ├── replacement.py       # Replacement effects (CR 614)
│   │   └── triggered.py         # Triggered abilities (CR 603)
│   └── keywords/                # Keyword abilities
│       ├── __init__.py
│       └── static.py            # Static keyword implementations
├── tests/                       # Test suite
│   └── ...
├── run_match.py                 # Match runner script
└── run_tournament.py            # Tournament simulation
```

### Core Type System

The type system (defined in `engine/types.py`) provides type-safe enums and type aliases:

```python
# Core ID types
PlayerId = int
ObjectId = int
ZoneId = int

# Enums for discrete states
class PhaseType(Enum):
    BEGINNING = auto()
    MAIN_1 = auto()
    COMBAT = auto()
    MAIN_2 = auto()
    ENDING = auto()

class StepType(Enum):
    UNTAP = auto()
    UPKEEP = auto()
    DRAW = auto()
    BEGIN_COMBAT = auto()
    DECLARE_ATTACKERS = auto()
    DECLARE_BLOCKERS = auto()
    COMBAT_DAMAGE = auto()
    END_COMBAT = auto()
    END_STEP = auto()
    CLEANUP = auto()

class Zone(Enum):
    LIBRARY = auto()
    HAND = auto()
    BATTLEFIELD = auto()
    GRAVEYARD = auto()
    STACK = auto()
    EXILE = auto()
    COMMAND = auto()

class Color(Enum):
    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"
    COLORLESS = "C"

class CardType(Enum):
    CREATURE = auto()
    INSTANT = auto()
    SORCERY = auto()
    ENCHANTMENT = auto()
    ARTIFACT = auto()
    PLANESWALKER = auto()
    LAND = auto()
    BATTLE = auto()
```

## Module Descriptions

### Game Module (`engine/game.py`)

**Purpose**: Central orchestrator for all game systems.

**Key Classes:**

- `GameConfig`: Configuration settings (starting life, hand size, turn limit)
- `GameResult`: Game outcome data (winner, reason, turns played)
- `Game`: Main game controller

**Responsibilities:**

- Initializes all subsystems (zones, stack, combat, etc.)
- Manages turn progression
- Coordinates between subsystems
- Tracks win/loss conditions
- Provides event bus for game-wide events

**Critical Methods:**

```python
class Game:
    def setup_game(self, deck1_cards, deck2_cards, ai1, ai2):
        """Initialize game with decks and AI agents"""

    def play_game(self, max_turns=50) -> GameResult:
        """Run complete game loop until game ends"""

    def advance_turn(self):
        """Progress to next turn (increment counter, switch active player)"""

    def advance_phase(self):
        """Progress to next phase in turn structure"""

    def check_game_over(self) -> bool:
        """Check if game has ended (life totals, decking, etc.)"""
```

**Design Notes:**

- Uses dependency injection for all subsystems
- Subsystems reference back to game for context
- Verbose logging controlled by config flag
- Maintains timestamp counter for layer system ordering

### Objects Module (`engine/objects.py`)

**Purpose**: Implements the game object hierarchy per CR 109-113.

**Key Classes:**

```python
@dataclass
class Characteristics:
    """CR 109.3 - Object characteristics"""
    name: str
    mana_cost: Optional[str]
    colors: Set[Color]
    types: Set[CardType]
    subtypes: Set[str]
    supertypes: Set[Supertype]
    power: Optional[int]
    toughness: Optional[int]
    loyalty: Optional[int]
    rules_text: str

@dataclass
class GameObject:
    """CR 109 - Base class for all game objects"""
    object_id: int
    base_characteristics: Characteristics
    characteristics: Characteristics  # Modified by effects
    owner: Player
    controller: Player
    zone: Zone
    timestamp: int

@dataclass
class Card(GameObject):
    """CR 108 - A Magic card"""
    is_token: bool = False
    is_copy: bool = False

@dataclass
class Permanent(GameObject):
    """CR 110 - An object on the battlefield"""
    tapped: bool = False
    summoning_sick: bool = False
    damage_marked: int = 0
    counters: Dict[CounterType, int]
    attached_to: Optional[ObjectId] = None
```

**Design Notes:**

- Separates base_characteristics (printed) from characteristics (current)
- This separation enables the layer system (CR 613) to function correctly
- Characteristics are copied when objects change zones
- Permanents add battlefield-specific state (tapped, damage, counters)

### Zone Manager (`engine/zones.py`)

**Purpose**: Manages all game zones per CR 400-406.

**Zone Types:**

- **Library**: CR 401 - Ordered list of cards (deck)
- **Hand**: CR 402 - Private zone, cards known only to owner
- **Battlefield**: CR 403 - Public zone, permanents exist here
- **Graveyard**: CR 404 - Ordered, public zone
- **Stack**: CR 405 - LIFO zone for spells and abilities
- **Exile**: CR 406 - Public zone, cards removed from game
- **Command**: CR 408 - For commanders, emblems, planes (future use)

**Key Methods:**

```python
class ZoneManager:
    def move_card(self, card: Card, from_zone: Zone, to_zone: Zone,
                  position: int = -1):
        """Move a card between zones (triggers zone-change events)"""

    def get_zone_contents(self, zone: Zone, player_id: PlayerId) -> List[Card]:
        """Get all cards in a specific zone for a player"""

    def shuffle_library(self, player_id: PlayerId):
        """Randomize library order"""
```

**Design Notes:**

- Each zone is player-specific (except stack)
- Zone transitions trigger events (for "enters battlefield" triggers, etc.)
- Maintains ordering for relevant zones (library, graveyard)
- Hidden zones (library, hand) have visibility restrictions

### Priority System (`engine/priority.py`)

**Purpose**: Implements the priority system per CR 117.

**Key Concepts:**

- Only the player with priority can take actions (CR 117.1)
- Active player receives priority at start of most steps (CR 117.3a)
- Priority passes in turn order (CR 117.3c)
- When all players pass in succession, top of stack resolves or phase ends (CR 117.4)

**State Machine:**

```
┌─────────────────────────────────────────────────────┐
│  Priority System State                              │
│                                                      │
│  ┌──────────────┐                                   │
│  │ Active Player│                                   │
│  │  Gets Priority│                                  │
│  └──────┬───────┘                                   │
│         │                                            │
│         ▼                                            │
│  ┌──────────────┐   Action Taken   ┌─────────────┐ │
│  │   Waiting    ├─────────────────►│Active Player│ │
│  │  for Player  │                   │ Retains     │ │
│  │   Response   │                   │ Priority    │ │
│  └──────┬───────┘                   └─────────────┘ │
│         │                                            │
│         │ Pass Priority                              │
│         ▼                                            │
│  ┌──────────────┐                                   │
│  │  Next Player │                                   │
│  │  in Turn     │                                   │
│  │  Order       │                                   │
│  └──────┬───────┘                                   │
│         │                                            │
│         │ All Passed?                                │
│         ▼                                            │
│  ┌──────────────┐   Yes     ┌──────────────┐       │
│  │ Check Passed ├──────────►│  Resolve Top │       │
│  │    Set       │           │  of Stack OR │       │
│  │              │           │  End Phase   │       │
│  └──────┬───────┘           └──────────────┘       │
│         │ No                                         │
│         │ (Continue passing)                         │
│         └─────────┐                                  │
│                   │                                  │
└───────────────────┼──────────────────────────────────┘
                    │
                    ▼
              (Next player gets priority)
```

**Implementation:**

```python
class PrioritySystem:
    def give_priority(self, player: Player):
        """Give priority to player, reset passed set"""

    def pass_priority(self) -> PriorityResult:
        """Current player passes priority"""
        # Returns: PRIORITY_PASSED, ALL_PASSED, or ACTION_TAKEN

    def action_taken(self, player: Player):
        """Player took an action (resets passed set)"""
```

### Stack Manager (`engine/stack.py`)

**Purpose**: Implements the stack per CR 405 and resolution per CR 608.

**Stack Semantics:**

- LIFO (Last In, First Out) ordering
- Top item resolves when all players pass priority in succession
- Spells become permanents or go to graveyard on resolution
- Abilities resolve and cease to exist

**Key Classes:**

```python
@dataclass
class StackObject(ABC):
    """Base class for stack objects"""
    object_id: int
    source: GameObject
    controller: Player
    targets: List[Target]
    timestamp: int

@dataclass
class SpellOnStack(StackObject):
    """A spell on the stack"""
    card: Card
    is_permanent_spell: bool
    x_value: Optional[int]

@dataclass
class AbilityOnStack(StackObject):
    """A triggered or activated ability on the stack"""
    ability_text: str
    ability_type: AbilityType
```

**Stack Operations:**

```python
class StackManager:
    def push(self, stack_object: StackObject):
        """Add spell/ability to top of stack"""

    def pop(self) -> Optional[StackObject]:
        """Remove and return top of stack"""

    def resolve_top(self):
        """Resolve top stack object"""
        # Spells: Create permanents or apply instant/sorcery effects
        # Abilities: Execute ability effects

    def is_empty(self) -> bool:
        """Check if stack is empty"""
```

### Combat Manager (`engine/combat.py`)

**Purpose**: Handles combat phase per CR 506-511.

**Combat Steps:**

1. **Beginning of Combat** (CR 507): Players can cast instants/activate abilities
2. **Declare Attackers** (CR 508): Active player declares attacking creatures
3. **Declare Blockers** (CR 509): Defending player declares blocking creatures
4. **Combat Damage** (CR 510): Damage is dealt simultaneously
5. **End of Combat** (CR 511): Cleanup of combat-specific state

**State Tracking:**

```python
@dataclass
class AttackDeclaration:
    """Declaration of attackers"""
    attackers: List[Permanent]  # Creatures attacking
    planeswalker_targets: Dict[ObjectId, ObjectId]  # Attacker -> target

@dataclass
class BlockDeclaration:
    """Declaration of blockers"""
    blocks: Dict[ObjectId, List[ObjectId]]  # Attacker -> [blockers]
    damage_assignment_order: Dict[ObjectId, List[ObjectId]]
```

**Combat Flow:**

```
┌────────────────────────────────────────────────────┐
│             Combat Phase Flow                      │
│                                                     │
│  1. Begin Combat Step                              │
│     ├─ Trigger "beginning of combat" abilities     │
│     └─ Priority round                              │
│                                                     │
│  2. Declare Attackers Step                         │
│     ├─ Active player chooses attackers             │
│     ├─ Tap attackers (unless vigilance)            │
│     ├─ Trigger "attacks" abilities                 │
│     ├─ Check attacking restrictions/requirements   │
│     └─ Priority round                              │
│                                                     │
│  3. Declare Blockers Step                          │
│     ├─ Defending player chooses blockers           │
│     ├─ Trigger "blocks" abilities                  │
│     ├─ Active player orders multiple blockers      │
│     └─ Priority round                              │
│                                                     │
│  4. Combat Damage Step                             │
│     ├─ All combat damage dealt simultaneously      │
│     ├─ Trigger "deals combat damage" abilities     │
│     └─ Priority round                              │
│                                                     │
│  5. End of Combat Step                             │
│     ├─ Remove creatures from combat                │
│     ├─ Trigger "end of combat" abilities           │
│     └─ Priority round                              │
│                                                     │
└────────────────────────────────────────────────────┘
```

### Mana System (`engine/mana.py`)

**Purpose**: Implements mana production and payment per CR 106.

**ManaPool:**

```python
@dataclass
class ManaPool:
    """Player's mana pool"""
    mana: Dict[Color, int]  # Color -> amount

    def add(self, color: Color, amount: int):
        """Add mana to pool"""

    def can_pay(self, cost: Dict[Color, int]) -> bool:
        """Check if cost is payable"""

    def pay(self, cost: Dict[Color, int]) -> bool:
        """Pay mana cost, return success"""

    def empty(self):
        """Empty all mana (end of step/phase)"""
```

**Mana Abilities:**

- Special actions that don't use the stack (CR 605)
- Can be activated at any time player has priority
- Resolve immediately without priority passing
- Land tap abilities are the most common type

### Turn Manager (`engine/turns.py`)

**Purpose**: Implements turn structure per CR 500-514.

**Turn Structure:**

```
┌─────────────────────────────────────────────────────┐
│                  MTG Turn Structure                  │
│                                                      │
│  BEGINNING PHASE                                     │
│  ├─ Untap Step (no priority)                        │
│  ├─ Upkeep Step                                     │
│  └─ Draw Step                                       │
│                                                      │
│  MAIN PHASE 1 (Pre-Combat)                          │
│  └─ Main Phase Step                                 │
│                                                      │
│  COMBAT PHASE                                        │
│  ├─ Beginning of Combat Step                        │
│  ├─ Declare Attackers Step                          │
│  ├─ Declare Blockers Step                           │
│  ├─ Combat Damage Step                              │
│  └─ End of Combat Step                              │
│                                                      │
│  MAIN PHASE 2 (Post-Combat)                         │
│  └─ Main Phase Step                                 │
│                                                      │
│  ENDING PHASE                                        │
│  ├─ End Step                                        │
│  └─ Cleanup Step                                    │
│      ├─ Discard to hand size                        │
│      ├─ Remove damage marked                        │
│      └─ End "until end of turn" effects             │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Implementation:**

```python
@dataclass
class Step:
    step_type: StepType
    has_priority: bool  # False for untap and normally cleanup
    turn_based_actions: List[Callable]

@dataclass
class Phase:
    phase_type: PhaseType
    steps: List[Step]

class Turn:
    """Represents a complete turn"""
    phases: List[Phase]
```

### Event System (`engine/events.py`)

**Purpose**: Event bus for decoupled communication between systems.

**Event Types:**

- `GameStartEvent`: Game begins
- `TurnStartEvent`: New turn begins
- `PhaseStartEvent`: Phase begins
- `StepStartEvent`: Step begins
- `DrawCardEvent`: Player draws a card
- `LandPlayedEvent`: Land is played
- `SpellCastEvent`: Spell is cast
- `EntersBattlefieldEvent`: Permanent enters battlefield
- `DealsD amageEvent`: Damage is dealt
- `PlayerLostEvent`: Player loses the game
- `GameEndedEvent`: Game ends

**Usage:**

```python
class EventBus:
    def publish(self, event: Event):
        """Publish event to all subscribers"""

    def subscribe(self, event_type: Type[Event], handler: Callable):
        """Subscribe handler to event type"""
```

**Design Notes:**

- Triggered abilities subscribe to relevant events
- Replacement effects intercept events before they happen
- Event handlers are called in timestamp order

### State-Based Actions (`engine/sba.py`)

**Purpose**: Automatic game rule enforcement per CR 704.

**SBA Checks:**

```python
def check_state_based_actions(game: Game) -> bool:
    """
    Check all state-based actions (CR 704).
    Returns True if any SBA was performed.
    """
    performed_any = False

    # CR 704.5a - Player at 0 or less life loses
    for player in game.players.values():
        if player.life <= 0:
            player.has_lost = True
            performed_any = True

    # CR 704.5b - Player with 10+ poison counters loses
    # CR 704.5c - Player tries to draw from empty library loses
    # CR 704.5f - Creature with toughness <= 0 dies
    # CR 704.5g - Creature with lethal damage dies
    # CR 704.5h - Planeswalker with 0 loyalty dies
    # CR 704.5i - Legendary rule
    # CR 704.5k - Auras with invalid targets are put into graveyard
    # ... many more

    return performed_any

def run_sba_loop(game: Game):
    """
    Run SBAs repeatedly until none are performed (CR 704.3).
    """
    while check_state_based_actions(game):
        pass  # Repeat until stable state
```

**When SBAs Are Checked:**

- Before a player receives priority
- After any game action
- Between spell/ability resolutions

### AI Agent System (`ai/agent.py`)

**Purpose**: Provide interface for AI decision-making.

**AI Interface:**

```python
class AIAgent(ABC):
    @abstractmethod
    def choose_action(self, game_state: GameStateView,
                     available_actions: List[Action]) -> Action:
        """Choose an action from available options"""

    @abstractmethod
    def declare_attackers(self, game_state: GameStateView) -> AttackDeclaration:
        """Choose which creatures attack"""

    @abstractmethod
    def declare_blockers(self, game_state: GameStateView,
                        attackers: List[Permanent]) -> BlockDeclaration:
        """Choose how to block"""

    @abstractmethod
    def choose_targets(self, game_state: GameStateView,
                      spell: Spell, valid_targets: List[GameObject]) -> List[GameObject]:
        """Choose targets for spell/ability"""
```

**SimpleAI Implementation:**

- Heuristic-based decision making
- Always plays land if able
- Casts creatures on curve
- Attacks with all creatures unless obviously bad
- Blocks to minimize damage
- Casts removal on largest threats

**Extension Points:**

- Implement custom AI by extending `AIAgent`
- Access game state through read-only `GameStateView`
- Use `CardInfo` and `PermanentInfo` for decision-making

## Data Flow

### Game Initialization Flow

```
User Code
   │
   ├─► Load Deck Files (DecklistParser)
   │      │
   │      ├─► Parse decklist format
   │      └─► Look up cards in CardDatabase
   │
   ├─► Create Game(player_ids, config)
   │      │
   │      ├─► Initialize EventBus
   │      ├─► Initialize ZoneManager
   │      ├─► Create Players
   │      ├─► Initialize all subsystems
   │      │      ├─► StackManager
   │      │      ├─► PrioritySystem
   │      │      ├─► CombatManager
   │      │      ├─► ManaManager
   │      │      └─► TriggerManager
   │      └─► Set initial game state
   │
   └─► game.setup_game(deck1_cards, deck2_cards, ai1, ai2)
          │
          ├─► Shuffle decks
          ├─► Move cards to libraries
          ├─► Draw opening hands (7 cards)
          ├─► Attach AI agents to players
          └─► Publish GameStartEvent
```

### Turn Execution Flow

```
game.play_game() called
   │
   └─► While not game_over:
          │
          ├─► game.execute_turn()
          │      │
          │      ├─► Increment turn counter
          │      ├─► Publish TurnStartEvent
          │      │
          │      ├─► FOR EACH PHASE:
          │      │      │
          │      │      ├─► Publish PhaseStartEvent
          │      │      │
          │      │      ├─► FOR EACH STEP IN PHASE:
          │      │      │      │
          │      │      │      ├─► Publish StepStartEvent
          │      │      │      │
          │      │      │      ├─► Execute turn-based actions
          │      │      │      │   (e.g., untap, draw card)
          │      │      │      │
          │      │      │      ├─► Check triggers (from events)
          │      │      │      ├─► Put triggers on stack
          │      │      │      ├─► Run SBA loop
          │      │      │      │
          │      │      │      ├─► IF step has priority:
          │      │      │      │      │
          │      │      │      │      └─► run_priority_round()
          │      │      │      │             │
          │      │      │      │             └─► [Priority Flow]
          │      │      │      │
          │      │      │      ├─► Empty mana pools
          │      │      │      └─► Publish StepEndEvent
          │      │      │
          │      │      └─► Publish PhaseEndEvent
          │      │
          │      └─► Publish TurnEndEvent
          │
          └─► Check win/loss conditions
                 │
                 └─► If game over: return GameResult
```

### Priority Round Flow

```
run_priority_round(game) called
   │
   ├─► Give priority to active player
   │
   └─► LOOP until all players pass in succession:
          │
          ├─► Current player with priority
          │      │
          │      ├─► Ask AI for action
          │      │      │
          │      │      └─► AI.choose_action(game_state, available_actions)
          │      │             │
          │      │             └─► Returns Action (pass, cast spell, activate ability, etc.)
          │      │
          │      ├─► IF action is PASS:
          │      │      │
          │      │      ├─► Add player to "passed" set
          │      │      ├─► Give priority to next player
          │      │      │
          │      │      └─► IF all players have passed:
          │      │             │
          │      │             ├─► IF stack is not empty:
          │      │             │      │
          │      │             │      ├─► Pop top of stack
          │      │             │      ├─► Resolve spell/ability
          │      │             │      ├─► Run SBA loop
          │      │             │      ├─► Clear "passed" set
          │      │             │      └─► Give priority to active player
          │      │             │             (repeat priority round)
          │      │             │
          │      │             └─► ELSE (stack is empty):
          │      │                    │
          │      │                    └─► END priority round (phase/step ends)
          │      │
          │      └─► ELSE (action taken):
          │             │
          │             ├─► Execute action
          │             │      ├─► Cast spell → add to stack
          │             │      ├─► Activate ability → add to stack
          │             │      ├─► Play land → put onto battlefield
          │             │      └─► Special action → execute immediately
          │             │
          │             ├─► Run SBA loop
          │             ├─► Check triggers → put on stack
          │             ├─► Clear "passed" set
          │             └─► Give priority to active player
          │                    (continue priority round)
          │
          └─► (Loop continues until all pass with empty stack)
```

## Game Loop Architecture

### Main Game Loop

The main game loop coordinates all systems:

```python
def play_game(self, max_turns=50) -> GameResult:
    """Execute complete game from start to finish."""

    # Setup phase (not shown - deck shuffle, opening hands, etc.)

    while not self.game_over and self.turn_number < max_turns:
        # 1. Execute turn
        self.execute_turn()

        # 2. Check game-ending conditions
        if self.check_game_over():
            break

    # Determine winner and create result
    return self.create_game_result()

def execute_turn(self):
    """Execute a single complete turn."""

    # Increment turn counter
    self.turn_number += 1
    self.events.publish(TurnStartEvent(self.turn_number, self.active_player_id))

    # Execute each phase
    for phase in self.turn_structure:
        self.execute_phase(phase)

    # Advance to next player
    self.advance_turn()
    self.events.publish(TurnEndEvent(self.turn_number))

def execute_phase(self, phase: Phase):
    """Execute a single phase."""

    self.current_phase = phase.phase_type
    self.events.publish(PhaseStartEvent(phase.phase_type))

    # Execute each step in the phase
    for step in phase.steps:
        self.execute_step(step)

    self.events.publish(PhaseEndEvent(phase.phase_type))

def execute_step(self, step: Step):
    """Execute a single step."""

    self.current_step = step.step_type
    self.events.publish(StepStartEvent(step.step_type))

    # Perform turn-based actions (untap, draw, etc.)
    for action in step.turn_based_actions:
        action(self)

    # Check for triggered abilities
    self.triggers.check_pending_triggers()

    # Run state-based actions
    run_sba_loop(self)

    # Priority round (if applicable)
    if step.has_priority:
        run_priority_round(self)

    # Empty mana pools (CR 106.4)
    for player in self.players.values():
        player.mana_pool.empty()

    self.events.publish(StepEndEvent(step.step_type))
```

### Spell Casting Flow

```
Player casts spell
   │
   ├─► 1. Announce spell (CR 601.2a)
   │      ├─► Move card from hand to stack
   │      └─► Create SpellOnStack object
   │
   ├─► 2. Choose modes (if modal) (CR 601.2b)
   │
   ├─► 3. Choose targets (CR 601.2c)
   │      └─► Validate targets are legal
   │
   ├─► 4. Determine total cost (CR 601.2f)
   │      ├─► Base mana cost
   │      ├─► Additional costs
   │      └─► Cost increases/reductions
   │
   ├─► 5. Activate mana abilities (CR 601.2g)
   │      └─► Tap lands, etc.
   │
   ├─► 6. Pay costs (CR 601.2h)
   │      ├─► Pay mana from pool
   │      └─► Pay other costs (life, sacrifice, etc.)
   │
   ├─► 7. Spell becomes cast (CR 601.2i)
   │      ├─► Publish SpellCastEvent
   │      └─► Check triggers
   │
   └─► 8. Active player receives priority
```

### Stack Resolution

```
Top of stack resolves (when all players pass)
   │
   ├─► Pop stack object
   │
   ├─► Check if targets are still legal (CR 608.2b)
   │      │
   │      └─► If any targets illegal: fizzle (do nothing)
   │
   ├─► IF spell:
   │      │
   │      ├─► IF permanent spell:
   │      │      │
   │      │      ├─► Move card to battlefield
   │      │      ├─► Create Permanent object
   │      │      ├─► Publish EntersBattlefieldEvent
   │      │      └─► Check triggers
   │      │
   │      └─► ELSE (instant/sorcery):
   │             │
   │             ├─► Execute spell effects
   │             └─► Move card to graveyard
   │
   └─► IF ability:
          │
          ├─► Execute ability effects
          └─► Ability ceases to exist
```

## Priority and Stack System

### Detailed Priority Mechanics

Priority is the most complex timing system in MTG. The engine implements it precisely:

**Priority States:**

1. **Active Player Has Priority**: Can take actions or pass
2. **Waiting for Player**: Other players in turn order sequence
3. **All Passed**: Stack resolves or phase ends

**Priority Actions:**

Players with priority can:
- Cast a spell
- Activate an activated ability
- Take a special action (play land, turn face-up, etc.)
- Pass priority

**Priority Rules Implemented:**

```python
# CR 117.3a: Active player gets priority at start of most steps
def begin_step_with_priority(self):
    self.priority.give_priority(self.active_player)

# CR 117.3b: After spell/ability resolves, active player gets priority
def after_resolution(self):
    run_sba_loop(self)
    self.triggers.check_and_push_triggers()
    self.priority.give_priority(self.active_player)

# CR 117.3c: When player passes, priority goes to next player
def pass_priority(self):
    next_player = self.get_next_player_in_turn_order()
    self.priority.give_priority(next_player)

# CR 117.4: All players pass in succession → resolve or end
def all_players_passed(self):
    if not self.stack_manager.is_empty():
        self.stack_manager.resolve_top()
        self.after_resolution()  # Active player gets priority again
    else:
        # End current phase/step
        return
```

### Stack Interaction Patterns

**Pattern 1: Single Spell**

```
T1: Player 1 casts Lightning Bolt targeting Player 2
    Stack: [Lightning Bolt]
    Priority → Player 1

P1: Pass
    Priority → Player 2

P2: Pass
    All passed → Resolve Lightning Bolt
    Player 2 takes 3 damage
    Stack: []
    Priority → Player 1
```

**Pattern 2: Response Chain**

```
T1: Player 1 casts Baneslayer Angel
    Stack: [Baneslayer Angel]
    Priority → Player 1

P1: Pass
    Priority → Player 2

P2: Casts Counterspell targeting Baneslayer Angel
    Stack: [Baneslayer Angel, Counterspell]
    Priority → Player 2

P2: Pass
    Priority → Player 1

P1: Pass
    All passed → Resolve Counterspell
    Baneslayer Angel is countered
    Stack: []
    Priority → Player 1
```

**Pattern 3: Mana Abilities (Don't Use Stack)**

```
T1: Player 1 taps Mountain for {R}
    (Mana ability, doesn't use stack)
    Player 1 mana pool: {R}
    Priority still with Player 1

P1: Casts Lightning Bolt
    Stack: [Lightning Bolt]
    Player 1 mana pool: {} (cost paid)
    Priority → Player 1
```

## Design Decisions

### Why Zero Dependencies?

**Decision**: Build entire engine using only Python standard library.

**Rationale:**
- **Deployment Simplicity**: No `pip install`, no version conflicts
- **Long-Term Stability**: Standard library is stable across Python versions
- **Educational Value**: Code is self-contained and auditable
- **Reduced Attack Surface**: No third-party code to audit
- **Maintenance**: Fewer moving parts to maintain

**Trade-offs Accepted:**
- More code to write (no game engine libraries)
- Slower than optimized C extensions
- Manual implementation of data structures

**Alternatives Considered:**
- Using `pygame` for visualization → Rejected (adds dependency)
- Using `numpy` for performance → Rejected (not needed for game logic)
- Using `networkx` for game tree → Rejected (AI not graph-based)

### Why Dataclasses Over Regular Classes?

**Decision**: Use `@dataclass` for all data structures.

**Rationale:**
- **Automatic Methods**: `__init__`, `__repr__`, `__eq__` generated automatically
- **Type Hints**: Integrated type checking support
- **Immutability Option**: `frozen=True` for immutable configs
- **Clarity**: Field definitions are clear and concise
- **Performance**: Comparable to regular classes

**Example:**

```python
# With dataclass (10 lines)
@dataclass
class GameConfig:
    starting_life: int = 20
    starting_hand_size: int = 7
    max_turns: int = 50
    verbose: bool = False

# Without dataclass (30+ lines)
class GameConfig:
    def __init__(self, starting_life=20, starting_hand_size=7,
                 max_turns=50, verbose=False):
        self.starting_life = starting_life
        self.starting_hand_size = starting_hand_size
        self.max_turns = max_turns
        self.verbose = verbose

    def __repr__(self):
        return (f"GameConfig(starting_life={self.starting_life}, "
                f"starting_hand_size={self.starting_hand_size}, "
                f"max_turns={self.max_turns}, verbose={self.verbose})")

    def __eq__(self, other):
        if not isinstance(other, GameConfig):
            return NotImplemented
        return (self.starting_life == other.starting_life and
                self.starting_hand_size == other.starting_hand_size and
                self.max_turns == other.max_turns and
                self.verbose == other.verbose)
```

### Why Event Bus Architecture?

**Decision**: Use event-driven architecture for triggers and state changes.

**Rationale:**
- **Decoupling**: Triggered abilities don't need to know about game internals
- **Extensibility**: Easy to add new triggers and effects
- **Testability**: Can test triggers in isolation
- **CR Compliance**: Matches how MTG rules describe triggers (CR 603)

**Implementation:**

```python
class EventBus:
    def __init__(self):
        self.subscribers: Dict[Type[Event], List[Callable]] = {}

    def subscribe(self, event_type: Type[Event], handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def publish(self, event: Event):
        event_type = type(event)
        for handler in self.subscribers.get(event_type, []):
            handler(event)
```

**Usage Example:**

```python
# Trigger: "Whenever a creature enters the battlefield, draw a card"
def creature_etb_trigger(event: EntersBattlefieldEvent):
    if event.permanent.characteristics.is_creature():
        game.draw_card(controller)

game.events.subscribe(EntersBattlefieldEvent, creature_etb_trigger)
```

### Why SimpleAI Instead of Full Game-Tree Search?

**Decision**: Implement heuristic-based AI instead of minimax/MCTS.

**Rationale:**
- **Performance**: MTG game trees are enormous (branching factor > 1000)
- **Scope**: Focus on rules accuracy, not AI quality
- **Extensibility**: Users can implement advanced AI if needed
- **Testing**: Heuristic AI provides consistent, predictable behavior for testing

**Trade-offs:**
- SimpleAI makes suboptimal plays
- Cannot handle complex strategic situations
- Doesn't learn or improve

**Extension Point:**
```python
class AlphaBetaAI(AIAgent):
    """Minimax with alpha-beta pruning (user-implemented)"""

    def evaluate_game_state(self, state: GameStateView) -> float:
        # Heuristic evaluation function
        pass

    def search(self, state: GameStateView, depth: int) -> Action:
        # Game tree search
        pass
```

### Why Separate base_characteristics and characteristics?

**Decision**: Every GameObject has both base_characteristics (printed values) and characteristics (current values).

**Rationale:**
- **Layer System**: CR 613 requires tracking original values and applied effects
- **Copiable Values**: Some effects copy "copiable characteristics" (CR 707.2)
- **Zone Changes**: When objects change zones, characteristics reset to base values
- **Effect Removal**: When effects end, need to revert to base

**Example:**

```python
# Giant Growth gives +3/+3 until end of turn
creature = game.get_permanent(creature_id)
creature.base_characteristics.power = 2      # Original (doesn't change)
creature.base_characteristics.toughness = 2

# Apply Giant Growth
creature.characteristics.power = 5           # Modified (2 + 3)
creature.characteristics.toughness = 5       # Modified (2 + 3)

# End of turn - effect expires
creature.characteristics.power = 2           # Reverts to base
creature.characteristics.toughness = 2
```

## Extension Points

### Adding Custom Cards

Extend the card database with custom implementations:

```python
# In cards/database.py
def create_custom_card(card_data: CardData) -> Card:
    """Create a card with custom ability implementations."""

    card = Card.from_card_data(card_data)

    # Add triggered abilities
    if "Whenever this creature attacks" in card_data.oracle_text:
        ability = create_triggered_ability(
            trigger_type=TriggerType.ATTACKS,
            effect=custom_effect_function
        )
        card.abilities.append(ability)

    return card
```

### Implementing New AI Agents

Create advanced AI by extending `AIAgent`:

```python
# In ai/my_agent.py
from v3.ai.agent import AIAgent, Action, GameStateView

class ReinforcementLearningAI(AIAgent):
    """AI agent using reinforcement learning."""

    def __init__(self, model_path: str):
        self.model = load_model(model_path)

    def choose_action(self, game_state: GameStateView,
                     available_actions: List[Action]) -> Action:
        # Convert game state to feature vector
        features = self.extract_features(game_state)

        # Query model for action probabilities
        action_probs = self.model.predict(features)

        # Select action
        return self.select_action(available_actions, action_probs)
```

### Adding New Keyword Abilities

Implement keywords in the effects system:

```python
# In engine/keywords/static.py
def has_flying(permanent: Permanent) -> bool:
    """Check if permanent has flying (CR 702.9)."""
    return "flying" in permanent.keywords

def can_block(blocker: Permanent, attacker: Permanent) -> bool:
    """Check if blocker can block attacker (CR 509.1b)."""

    # CR 702.9b: Creature with flying can't be blocked except by flying/reach
    if has_flying(attacker):
        if not (has_flying(blocker) or has_reach(blocker)):
            return False

    return True
```

### Custom Replay Viewers

The replay JSON format is extensible:

```json
{
  "metadata": {
    "engine_version": "3.0",
    "deck1_name": "Mono Red Aggro",
    "deck2_name": "Dimir Control"
  },
  "frames": [
    {
      "turn": 1,
      "phase": "BEGINNING",
      "step": "DRAW",
      "active_player": 1,
      "game_state": {
        "player1": {"life": 20, "hand_size": 8, "library_size": 52},
        "player2": {"life": 20, "hand_size": 7, "library_size": 53},
        "battlefield": [...]
      },
      "action": {"type": "draw_card", "player": 1}
    }
  ]
}
```

Implement custom visualizations by parsing this JSON.

## Conclusion

The MTGO Engine V3 is a comprehensive, rules-accurate MTG simulation system built on solid architectural principles. Its modular design, zero-dependency approach, and extensive documentation make it suitable for deck testing, AI development, and rules education.

For further documentation:
- **API Reference**: See [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Quick Start**: See [QUICKSTART.md](QUICKSTART.md)
- **Installation**: See [INSTALLATION.md](INSTALLATION.md)

**Key Takeaways:**

1. **Rules Fidelity**: Every module maps to Comprehensive Rules sections
2. **Modularity**: Clear subsystem boundaries with well-defined responsibilities
3. **Extensibility**: Multiple extension points for custom cards, AI, and visualizations
4. **Zero Dependencies**: Pure Python for maximum portability
5. **Type Safety**: Extensive type hints and dataclasses for reliability

The architecture balances rules accuracy, performance, and maintainability to create a robust MTG simulation engine.
