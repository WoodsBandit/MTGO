# MTGO Engine V3 - API Reference

Complete API documentation for the MTGO Magic: The Gathering game engine.

## Table of Contents

1. [Overview](#overview)
2. [Core Classes](#core-classes)
3. [Type System](#type-system)
4. [Game Management](#game-management)
5. [Game Objects](#game-objects)
6. [AI Agent Interface](#ai-agent-interface)
7. [Card Database](#card-database)
8. [Events System](#events-system)
9. [Utilities](#utilities)
10. [Usage Examples](#usage-examples)

## Overview

The MTGO Engine V3 API is organized into several key modules:

```
v3.engine          # Core game engine
v3.ai              # AI agent interface
v3.cards           # Card database and parsing
v3.tests           # Test utilities
```

All classes use type hints and are documented with docstrings. Import paths follow the pattern:

```python
from v3.engine.game import Game, GameConfig, GameResult
from v3.engine.objects import Card, Permanent, GameObject
from v3.ai.agent import AIAgent, SimpleAI, CardInfo, PermanentInfo
from v3.cards.database import get_database, CardData
from v3.cards.parser import DecklistParser, Deck
```

## Core Classes

### Game

**Location**: `v3.engine.game`

The main game controller that orchestrates all game systems.

#### Class Definition

```python
class Game:
    """
    Main game controller for Magic: The Gathering simulation.

    Attributes:
        events (EventBus): Event bus for game events and triggers
        zones (ZoneManager): Zone manager for all game zones
        priority (PrioritySystem): Priority system manager
        players (Dict[PlayerId, Player]): Dictionary of players by ID
        stack_manager (StackManager): Stack and resolution manager
        mana_manager (ManaAbilityManager): Mana ability manager
        combat_manager (CombatManager): Combat phase manager
        triggers (TriggerManager): Triggered ability manager
        turn_number (int): Current turn number
        active_player_id (PlayerId): ID of the active player
        current_phase (PhaseType): Current game phase
        current_step (StepType): Current step within the phase
        game_over (bool): Whether the game has ended
        winner_id (Optional[PlayerId]): ID of the winning player
    """
```

#### Constructor

```python
def __init__(self, player_ids: List[PlayerId] = None,
             config: GameConfig = None) -> None:
    """
    Initialize a new game.

    Args:
        player_ids: List of player IDs. Defaults to [1, 2] for two-player.
        config: Game configuration settings. Uses defaults if not provided.

    Example:
        >>> game = Game(player_ids=[1, 2], config=GameConfig(starting_life=20))
    """
```

#### Key Methods

##### setup_game

```python
def setup_game(self, deck1_cards: List[Card], deck2_cards: List[Card],
               ai1: AIAgent, ai2: AIAgent) -> None:
    """
    Initialize game with decks and AI agents.

    This method:
    - Assigns decks to players
    - Shuffles libraries
    - Draws opening hands (uses config.starting_hand_size)
    - Attaches AI agents to players
    - Publishes GameStartEvent

    Args:
        deck1_cards: List of Card objects for player 1's deck
        deck2_cards: List of Card objects for player 2's deck
        ai1: AI agent for player 1
        ai2: AI agent for player 2

    Example:
        >>> from v3.cards.parser import DecklistParser, Deck
        >>> from v3.cards.database import get_database
        >>> parser = DecklistParser()
        >>> decklist1 = parser.parse_file("deck1.txt")
        >>> deck1 = Deck.from_decklist(decklist1, get_database())
        >>> game.setup_game(deck1.cards, deck2.cards, ai1, ai2)
    """
```

##### play_game

```python
def play_game(self, max_turns: int = 50) -> GameResult:
    """
    Execute complete game from start to finish.

    Runs the game loop until:
    - A player wins/loses (life = 0, decking, etc.)
    - Turn limit reached
    - Game is explicitly ended

    Args:
        max_turns: Maximum turns before forcing game end (default: 50)

    Returns:
        GameResult: Contains winner, reason, turns played, final life totals

    Example:
        >>> result = game.play_game(max_turns=30)
        >>> print(f"Winner: Player {result.winner.player_id}")
        >>> print(f"Reason: {result.reason}")
        >>> print(f"Turns: {result.turns_played}")
    """
```

##### get_game_state

```python
def get_game_state(self) -> Dict[str, Any]:
    """
    Get current game state as a dictionary.

    Returns dictionary containing:
    - turn_number: Current turn
    - phase: Current phase
    - step: Current step
    - active_player: Active player ID
    - players: Player states (life, hand size, library size)
    - battlefield: List of all permanents
    - stack: Current stack contents

    Returns:
        Dict[str, Any]: Complete game state snapshot

    Example:
        >>> state = game.get_game_state()
        >>> print(f"Turn {state['turn_number']}")
        >>> print(f"P1 Life: {state['players'][1]['life']}")
    """
```

### GameConfig

**Location**: `v3.engine.game`

Configuration settings for a game instance.

```python
@dataclass
class GameConfig:
    """
    Configuration settings for a game instance.

    Attributes:
        starting_life (int): Initial life total (default: 20)
        starting_hand_size (int): Opening hand size (default: 7)
        max_turns (int): Maximum turns before draw (default: 50)
        verbose (bool): Enable detailed logging (default: False)
    """
    starting_life: int = 20
    starting_hand_size: int = 7
    max_turns: int = 50
    verbose: bool = False
```

**Usage:**

```python
# Standard game
config = GameConfig()

# Commander game
config = GameConfig(starting_life=40)

# Verbose testing
config = GameConfig(verbose=True, max_turns=10)
```

### GameResult

**Location**: `v3.engine.game`

Result of a completed game.

```python
@dataclass
class GameResult:
    """
    Result of a completed game.

    Attributes:
        winner (Optional[Player]): The winning player (None for draw)
        reason (str): How the game ended
        turns_played (int): Total turns played
        final_life (Dict[int, int]): Player ID -> final life total
    """
    winner: Optional[Player] = None
    reason: str = ""
    turns_played: int = 0
    final_life: Dict[int, int] = field(default_factory=dict)
```

**Common `reason` values:**

- `"life"`: Opponent reached 0 or less life
- `"decked"`: Opponent tried to draw from empty library
- `"concede"`: Opponent conceded
- `"turn_limit"`: Maximum turns reached
- `"poison"`: Opponent reached 10+ poison counters

## Type System

### Enums

**Location**: `v3.engine.types`

#### PhaseType

```python
class PhaseType(Enum):
    """Game phases per CR 500."""
    BEGINNING = auto()
    MAIN_1 = auto()
    COMBAT = auto()
    MAIN_2 = auto()
    ENDING = auto()
```

#### StepType

```python
class StepType(Enum):
    """Turn steps per CR 500-514."""
    UNTAP = auto()
    UPKEEP = auto()
    DRAW = auto()
    MAIN = auto()  # Used for both main phases
    BEGIN_COMBAT = auto()
    DECLARE_ATTACKERS = auto()
    DECLARE_BLOCKERS = auto()
    COMBAT_DAMAGE = auto()
    END_COMBAT = auto()
    END_STEP = auto()
    CLEANUP = auto()
```

#### Zone

```python
class Zone(Enum):
    """Game zones per CR 400."""
    LIBRARY = auto()
    HAND = auto()
    BATTLEFIELD = auto()
    GRAVEYARD = auto()
    STACK = auto()
    EXILE = auto()
    COMMAND = auto()
```

#### CardType

```python
class CardType(Enum):
    """Card types per CR 300."""
    CREATURE = auto()
    INSTANT = auto()
    SORCERY = auto()
    ENCHANTMENT = auto()
    ARTIFACT = auto()
    LAND = auto()
    PLANESWALKER = auto()
    BATTLE = auto()

    def is_permanent_type(self) -> bool:
        """Returns True if cards of this type are permanents."""
```

#### Color

```python
class Color(Flag):
    """The five colors of Magic plus colorless (CR 105)."""
    COLORLESS = 0
    WHITE = auto()
    BLUE = auto()
    BLACK = auto()
    RED = auto()
    GREEN = auto()

    # Guild colors (combinations)
    AZORIUS = WHITE | BLUE
    DIMIR = BLUE | BLACK
    RAKDOS = BLACK | RED
    GRUUL = RED | GREEN
    SELESNYA = GREEN | WHITE
    # ... (10 guilds total)

    @classmethod
    def all_colors(cls) -> "Color":
        """Returns all five colors combined."""
```

### Type Aliases

```python
PlayerId = int          # Player identifier (usually 1 or 2)
ObjectId = int          # Unique ID for game objects
Timestamp = int         # Layer system timestamp
ZoneId = int            # Zone identifier
ManaValue = int         # Converted mana cost
LifeTotal = int         # Life total
DamageAmount = int      # Amount of damage
Power = int             # Creature power
Toughness = int         # Creature toughness
Loyalty = int           # Planeswalker loyalty
```

## Game Objects

### GameObject

**Location**: `v3.engine.objects`

Base class for all game objects (CR 109).

```python
@dataclass
class GameObject:
    """
    Base class for all game objects.

    Attributes:
        object_id (int): Unique identifier
        base_characteristics (Characteristics): Original printed values
        characteristics (Characteristics): Current values (after effects)
        owner (Player): Player who owns this object
        controller (Player): Player who controls this object
        zone (Zone): Current zone
        timestamp (int): Creation timestamp for layer ordering
    """
    object_id: int = 0
    base_characteristics: Characteristics = field(default_factory=Characteristics)
    characteristics: Characteristics = field(default_factory=Characteristics)
    owner: Optional[Player] = None
    controller: Optional[Player] = None
    zone: Optional[Zone] = None
    timestamp: int = 0

    # Convenience properties
    @property
    def name(self) -> str:
        """Card name."""
        return self.characteristics.name

    @property
    def mana_cost(self) -> Optional[str]:
        """Mana cost string (e.g., "{2}{U}{U}")."""
        return self.characteristics.mana_cost

    @property
    def colors(self) -> Set[Color]:
        """Set of colors."""
        return self.characteristics.colors

    @property
    def types(self) -> Set[CardType]:
        """Set of card types."""
        return self.characteristics.types
```

### Characteristics

**Location**: `v3.engine.objects`

Characteristics of a game object per CR 109.3.

```python
@dataclass
class Characteristics:
    """
    Characteristics of a game object (CR 109.3).

    Attributes:
        name (str): Card name
        mana_cost (Optional[str]): Mana cost (e.g., "{2}{U}{U}")
        colors (Set[Color]): Set of colors
        types (Set[CardType]): Set of card types
        subtypes (Set[str]): Set of subtypes (e.g., {"Human", "Wizard"})
        supertypes (Set[Supertype]): Set of supertypes (e.g., {LEGENDARY})
        power (Optional[int]): Creature power
        toughness (Optional[int]): Creature toughness
        loyalty (Optional[int]): Planeswalker starting loyalty
        rules_text (str): Oracle text
    """
    name: str = ""
    mana_cost: Optional[str] = None
    colors: Set[Color] = field(default_factory=set)
    types: Set[CardType] = field(default_factory=set)
    subtypes: Set[str] = field(default_factory=set)
    supertypes: Set[Supertype] = field(default_factory=set)
    power: Optional[int] = None
    toughness: Optional[int] = None
    loyalty: Optional[int] = None
    rules_text: str = ""

    # Type checking methods
    def is_creature(self) -> bool:
        """Returns True if this has type Creature."""
        return CardType.CREATURE in self.types

    def is_land(self) -> bool:
        """Returns True if this has type Land."""
        return CardType.LAND in self.types

    def is_instant(self) -> bool:
        """Returns True if this has type Instant."""
        return CardType.INSTANT in self.types

    def is_sorcery(self) -> bool:
        """Returns True if this has type Sorcery."""
        return CardType.SORCERY in self.types

    def is_legendary(self) -> bool:
        """Returns True if this has supertype Legendary."""
        return Supertype.LEGENDARY in self.supertypes
```

### Card

**Location**: `v3.engine.objects`

A Magic card (CR 108).

```python
@dataclass
class Card(GameObject):
    """
    A Magic card (CR 108).

    Inherits from GameObject and adds card-specific attributes.

    Attributes:
        is_token (bool): True if this is a token (CR 111)
        is_copy (bool): True if this is a copy (CR 707)
    """
    is_token: bool = False
    is_copy: bool = False
```

### Permanent

**Location**: `v3.engine.objects`

An object on the battlefield (CR 110).

```python
@dataclass
class Permanent(GameObject):
    """
    An object on the battlefield (CR 110).

    Attributes:
        tapped (bool): Whether permanent is tapped
        summoning_sick (bool): Has summoning sickness (CR 302.6)
        damage_marked (int): Damage marked on this permanent
        counters (Dict[CounterType, int]): Counters on this permanent
        attached_to (Optional[ObjectId]): What this is attached to (for Auras)
    """
    tapped: bool = False
    summoning_sick: bool = False
    damage_marked: int = 0
    counters: Dict[CounterType, int] = field(default_factory=dict)
    attached_to: Optional[ObjectId] = None

    def tap(self) -> None:
        """Tap this permanent (CR 701.21a)."""
        self.tapped = True

    def untap(self) -> None:
        """Untap this permanent (CR 701.21b)."""
        self.tapped = False

    def is_tapped(self) -> bool:
        """Check if permanent is tapped."""
        return self.tapped

    def add_counter(self, counter_type: CounterType, amount: int = 1) -> None:
        """Add counters to this permanent."""
        current = self.counters.get(counter_type, 0)
        self.counters[counter_type] = current + amount

    def remove_counter(self, counter_type: CounterType, amount: int = 1) -> bool:
        """Remove counters. Returns True if successful."""
        current = self.counters.get(counter_type, 0)
        if current < amount:
            return False
        self.counters[counter_type] = current - amount
        return True
```

### Player

**Location**: `v3.engine.player`

Represents a player in the game (CR 102).

```python
@dataclass
class Player:
    """
    A player in the game (CR 102).

    Attributes:
        player_id (PlayerId): Unique player identifier
        name (str): Player name
        life (int): Current life total
        poison_counters (int): Poison counters (CR 122)
        energy_counters (int): Energy counters
        has_lost (bool): Whether player has lost
        has_won (bool): Whether player has won
        mana_pool (ManaPool): Player's mana pool
        ai (Optional[AIAgent]): AI agent controlling this player
    """
    player_id: PlayerId
    name: str
    life: int = 20
    poison_counters: int = 0
    energy_counters: int = 0
    has_lost: bool = False
    has_won: bool = False
    mana_pool: ManaPool = field(default_factory=ManaPool)
    ai: Optional[Any] = None  # AIAgent

    def gain_life(self, amount: int) -> None:
        """Gain life (CR 119.6)."""
        self.life += amount

    def lose_life(self, amount: int) -> None:
        """Lose life (CR 119.7)."""
        self.life -= amount

    def take_damage(self, amount: int, source: Optional[GameObject] = None) -> None:
        """Take damage (CR 120.3)."""
        self.life -= amount
```

### ManaPool

**Location**: `v3.engine.player`

A player's mana pool (CR 106.4).

```python
@dataclass
class ManaPool:
    """
    A player's mana pool (CR 106.4).

    The mana pool holds produced mana until it's spent.
    Mana empties from pools at end of each step/phase.

    Attributes:
        mana (Dict[Color, int]): Color -> amount of mana
    """
    mana: Dict[Color, int] = field(default_factory=dict)

    def add(self, color: Color, amount: int = 1) -> None:
        """
        Add mana to the pool.

        Args:
            color: Color of mana to add
            amount: Amount to add (default: 1)

        Example:
            >>> pool.add(Color.RED, 3)  # Add {R}{R}{R}
        """

    def can_pay(self, cost: Dict[Color, int]) -> bool:
        """
        Check if a cost can be paid with current mana.

        Args:
            cost: Dictionary of Color -> amount required

        Returns:
            True if cost is payable

        Example:
            >>> cost = {Color.RED: 2, Color.COLORLESS: 3}
            >>> pool.can_pay(cost)
        """

    def pay(self, cost: Dict[Color, int]) -> bool:
        """
        Pay a mana cost.

        Args:
            cost: Dictionary of Color -> amount to pay

        Returns:
            True if payment succeeded, False if insufficient mana

        Example:
            >>> cost = {Color.BLUE: 2}
            >>> if pool.pay(cost):
            ...     print("Cost paid successfully")
        """

    def empty(self) -> None:
        """Empty all mana from the pool (CR 106.4)."""
        self.mana = {color: 0 for color in Color}
```

## AI Agent Interface

### AIAgent

**Location**: `v3.ai.agent`

Abstract base class for AI decision-making agents.

```python
class AIAgent(ABC):
    """
    Base class for AI agents that control players.

    Subclass this to implement custom AI behavior.

    Attributes:
        player (Player): The player this AI controls
        game (Game): Reference to the game
    """

    @abstractmethod
    def choose_action(self, game_state: GameStateView,
                     available_actions: List[Action]) -> Action:
        """
        Choose an action from available options.

        Args:
            game_state: Read-only view of current game state
            available_actions: List of valid actions

        Returns:
            Action: The chosen action

        Example:
            >>> def choose_action(self, game_state, available_actions):
            ...     # Always play land if possible
            ...     for action in available_actions:
            ...         if action.action_type == "play_land":
            ...             return action
            ...     return Action(action_type="pass")
        """

    @abstractmethod
    def declare_attackers(self, game_state: GameStateView) -> AttackDeclaration:
        """
        Choose which creatures attack.

        Args:
            game_state: Read-only view of current game state

        Returns:
            AttackDeclaration: Attack declaration
        """

    @abstractmethod
    def declare_blockers(self, game_state: GameStateView,
                        attackers: List[PermanentInfo]) -> BlockDeclaration:
        """
        Choose how to block attackers.

        Args:
            game_state: Read-only view of current game state
            attackers: List of attacking creatures

        Returns:
            BlockDeclaration: Block declaration
        """

    @abstractmethod
    def choose_targets(self, game_state: GameStateView,
                      spell: Any, valid_targets: List[Any]) -> List[Any]:
        """
        Choose targets for a spell or ability.

        Args:
            game_state: Read-only game state
            spell: The spell requiring targets
            valid_targets: List of valid target options

        Returns:
            List of chosen targets
        """
```

### SimpleAI

**Location**: `v3.ai.agent`

Basic heuristic-based AI implementation.

```python
class SimpleAI(AIAgent):
    """
    Simple heuristic-based AI agent.

    Strategy:
    - Always plays a land if possible
    - Casts creatures on curve
    - Attacks with all creatures (unless obviously suicidal)
    - Blocks to minimize damage
    - Casts removal on largest threats
    """

    def __init__(self, player: Optional[Player], game: Optional[Game]):
        """Initialize SimpleAI with player and game references."""
        self.player = player
        self.game = game
```

### CardInfo

**Location**: `v3.ai.agent`

Read-only card information for AI decisions.

```python
@dataclass
class CardInfo:
    """
    Read-only card information for AI decisions.

    Attributes:
        name (str): Card name
        card_types (List[str]): List of types
        subtypes (List[str]): List of subtypes
        mana_cost (str): Mana cost string
        cmc (int): Converted mana cost
        power (Optional[int]): Creature power
        toughness (Optional[int]): Creature toughness
        abilities (List[str]): List of ability texts
        keywords (List[str]): List of keywords
        reference (Any): Reference to actual card object
    """

    # Type checking properties
    @property
    def is_creature(self) -> bool:
        """Returns True if this is a creature."""

    @property
    def is_instant(self) -> bool:
        """Returns True if this is an instant."""

    @property
    def is_land(self) -> bool:
        """Returns True if this is a land."""
```

### PermanentInfo

**Location**: `v3.ai.agent`

Read-only permanent information for AI decisions.

```python
@dataclass
class PermanentInfo:
    """
    Read-only permanent information for AI decisions.

    Attributes:
        name (str): Permanent name
        card_types (List[str]): List of types
        subtypes (List[str]): List of subtypes
        power (Optional[int]): Current power
        toughness (Optional[int]): Current toughness
        damage_marked (int): Damage on permanent
        is_tapped (bool): Whether tapped
        is_attacking (bool): Whether attacking
        is_blocking (bool): Whether blocking
        has_summoning_sickness (bool): Has summoning sickness
        keywords (List[str]): List of keywords
        abilities (List[str]): List of abilities
        controller_id (PlayerId): Controlling player
        reference (Any): Reference to actual permanent
    """
```

## Card Database

### get_database

**Location**: `v3.cards.database`

Get the singleton card database instance.

```python
def get_database() -> CardDatabase:
    """
    Get the singleton card database instance.

    Returns:
        CardDatabase: The global card database

    Example:
        >>> from v3.cards.database import get_database
        >>> db = get_database()
        >>> card_data = db.get_card("Lightning Bolt")
    """
```

### CardDatabase

**Location**: `v3.cards.database`

Database of all known cards.

```python
class CardDatabase:
    """
    Database of card data.

    Methods:
        get_card(name: str) -> Optional[CardData]:
            Look up card by name.

        search(query: str, filters: Dict) -> List[CardData]:
            Search for cards matching criteria.

        add_card(card_data: CardData) -> None:
            Add custom card to database.
    """

    def get_card(self, name: str) -> Optional[CardData]:
        """
        Look up card by exact name.

        Args:
            name: Card name (case-sensitive)

        Returns:
            CardData if found, None otherwise

        Example:
            >>> db = get_database()
            >>> bolt = db.get_card("Lightning Bolt")
            >>> print(bolt.mana_cost)  # "{R}"
        """
```

### CardData

**Location**: `v3.cards.database`

Complete card data structure.

```python
@dataclass
class CardData:
    """
    Complete card data structure.

    Attributes:
        name (str): Card name
        mana_cost (str): Mana cost (e.g., "{2}{U}{U}")
        cmc (int): Converted mana cost
        types (List[str]): Card types
        subtypes (List[str]): Subtypes
        supertypes (List[str]): Supertypes
        oracle_text (str): Full oracle text
        power (Optional[str]): Power (can be "*" or number)
        toughness (Optional[str]): Toughness
        loyalty (Optional[int]): Starting loyalty
        colors (List[str]): Color list
        keywords (List[str]): Keywords
        abilities (List[AbilityData]): Parsed abilities
    """
```

### DecklistParser

**Location**: `v3.cards.parser`

Parse decklist files in MTGO format.

```python
class DecklistParser:
    """
    Parse decklists in MTGO import format.

    Format:
        Deck_Name

        4 Lightning Bolt
        20 Mountain
        ...

        Sideboard
        3 Abrade
        ...
    """

    def parse_file(self, filepath: str) -> Decklist:
        """
        Parse a decklist file.

        Args:
            filepath: Path to decklist file

        Returns:
            Decklist: Parsed decklist data

        Example:
            >>> parser = DecklistParser()
            >>> decklist = parser.parse_file("mono_red.txt")
            >>> print(decklist.name)
            >>> print(f"Main deck: {len(decklist.main)} cards")
        """

    def parse_string(self, content: str) -> Decklist:
        """
        Parse decklist from string.

        Args:
            content: Decklist content

        Returns:
            Decklist: Parsed decklist data
        """
```

### Deck

**Location**: `v3.cards.parser`

A constructed deck with card objects.

```python
@dataclass
class Deck:
    """
    A deck with actual Card objects.

    Attributes:
        name (str): Deck name
        cards (List[Card]): List of Card objects (mainboard)
        sideboard (List[Card]): List of Card objects (sideboard)
    """

    @classmethod
    def from_decklist(cls, decklist: Decklist, database: CardDatabase) -> "Deck":
        """
        Create a Deck from a Decklist and database.

        Args:
            decklist: Parsed decklist
            database: Card database

        Returns:
            Deck: Deck with Card objects

        Example:
            >>> parser = DecklistParser()
            >>> decklist = parser.parse_file("deck.txt")
            >>> db = get_database()
            >>> deck = Deck.from_decklist(decklist, db)
            >>> game.setup_game(deck.cards, deck2.cards, ai1, ai2)
        """
```

## Events System

### EventBus

**Location**: `v3.engine.events`

Event bus for publish-subscribe pattern.

```python
class EventBus:
    """
    Event bus for game events.

    Allows systems to subscribe to events and be notified when they occur.
    """

    def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Event object to publish

        Example:
            >>> game.events.publish(DrawCardEvent(player_id=1))
        """

    def subscribe(self, event_type: Type[Event], handler: Callable) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Callable to invoke when event occurs

        Example:
            >>> def on_draw(event: DrawCardEvent):
            ...     print(f"Player {event.player_id} drew a card")
            >>> game.events.subscribe(DrawCardEvent, on_draw)
        """
```

### Event Types

Common event classes:

```python
@dataclass
class GameStartEvent:
    """Published when game begins."""
    pass

@dataclass
class TurnStartEvent:
    """Published at start of each turn."""
    turn_number: int
    player_id: PlayerId

@dataclass
class PhaseStartEvent:
    """Published at start of each phase."""
    phase: PhaseType

@dataclass
class DrawCardEvent:
    """Published when a player draws a card."""
    player_id: PlayerId
    card: Card

@dataclass
class SpellCastEvent:
    """Published when a spell is cast."""
    player_id: PlayerId
    spell: Any  # SpellOnStack

@dataclass
class EntersBattlefieldEvent:
    """Published when permanent enters battlefield."""
    permanent: Permanent
    controller: Player

@dataclass
class DealsDamageEvent:
    """Published when damage is dealt."""
    source: GameObject
    target: Union[Player, Permanent]
    amount: int
    is_combat_damage: bool
```

## Utilities

### Match Runner

**Location**: `v3.engine.match`

Run best-of-N matches.

```python
@dataclass
class MatchResult:
    """
    Result of a best-of-N match.

    Attributes:
        deck1_name (str): First deck name
        deck2_name (str): Second deck name
        deck1_wins (int): Games won by deck 1
        deck2_wins (int): Games won by deck 2
        games (List[GameSummary]): List of game results
        winner (str): Winning deck name
    """

def run_match(deck1: Deck, deck2: Deck, num_games: int = 3,
              ai_class: Type[AIAgent] = SimpleAI) -> MatchResult:
    """
    Run a best-of-N match.

    Args:
        deck1: First deck
        deck2: Second deck
        num_games: Number of games (default: 3 for best-of-3)
        ai_class: AI class to use (default: SimpleAI)

    Returns:
        MatchResult: Complete match results

    Example:
        >>> result = run_match(deck1, deck2, num_games=3)
        >>> print(f"{result.winner} wins {result.deck1_wins}-{result.deck2_wins}")
    """
```

### Replay Recorder

**Location**: `v3.engine.replay`

Record games for playback.

```python
class ReplayRecorder:
    """
    Records game state for replay visualization.

    Methods:
        attach_to_game(game: Game) -> None:
            Attach recorder to a game.

        record_frame() -> None:
            Record current game state as a frame.

        record_action(action_type: str, player_id: int, **kwargs) -> None:
            Record a specific action.

        save_to_file(filepath: str) -> None:
            Save replay to JSON file.
    """

    def save_to_file(self, filepath: str) -> None:
        """
        Save recorded replay to JSON file.

        Args:
            filepath: Path to save JSON file

        Example:
            >>> recorder = ReplayRecorder()
            >>> recorder.attach_to_game(game)
            >>> game.play_game()
            >>> recorder.save_to_file("replay.json")
        """
```

## Usage Examples

### Complete Game Example

```python
#!/usr/bin/env python3
"""Complete example: Run a game between two decks."""

import sys
import os

# Add engine to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Engine'))

from v3.engine.game import Game, GameConfig, GameResult
from v3.engine.replay import ReplayRecorder
from v3.cards.parser import DecklistParser, Deck
from v3.cards.database import get_database
from v3.ai.agent import SimpleAI

def main():
    # Parse decks
    parser = DecklistParser()
    decklist1 = parser.parse_file("decks/mono_red.txt")
    decklist2 = parser.parse_file("decks/control.txt")

    # Load cards from database
    database = get_database()
    deck1 = Deck.from_decklist(decklist1, database)
    deck2 = Deck.from_decklist(decklist2, database)

    # Create game
    config = GameConfig(
        starting_life=20,
        verbose=True
    )
    game = Game(player_ids=[1, 2], config=config)

    # Create AI agents
    ai1 = SimpleAI(None, None)
    ai2 = SimpleAI(None, None)

    # Setup game
    game.setup_game(deck1.cards, deck2.cards, ai1, ai2)

    # Attach replay recorder
    recorder = ReplayRecorder()
    recorder.attach_to_game(game)

    # Play game
    result = game.play_game()

    # Print results
    print(f"\nGame Over!")
    print(f"Winner: Player {result.winner.player_id}")
    print(f"Reason: {result.reason}")
    print(f"Turns: {result.turns_played}")
    print(f"Final Life: {result.final_life}")

    # Save replay
    recorder.save_to_file("replay.json")

if __name__ == "__main__":
    main()
```

### Custom AI Example

```python
"""Example: Custom AI that prefers removal spells."""

from v3.ai.agent import AIAgent, Action, CardInfo, PermanentInfo
from v3.engine.game import Game

class RemovalAI(AIAgent):
    """AI that prioritizes casting removal spells."""

    def choose_action(self, game_state, available_actions):
        # First, check for removal spells
        for action in available_actions:
            if action.action_type == "cast_spell":
                card = action.card
                if self._is_removal(card):
                    # Target largest creature
                    targets = self._find_best_removal_target(game_state)
                    if targets:
                        action.targets = [targets[0]]
                        return action

        # Otherwise, play land if possible
        for action in available_actions:
            if action.action_type == "play_land":
                return action

        # Default: pass
        return Action(action_type="pass")

    def _is_removal(self, card: CardInfo) -> bool:
        """Check if card is a removal spell."""
        removal_keywords = ["destroy", "exile", "damage to target"]
        text = card.rules_text.lower()
        return any(keyword in text for keyword in removal_keywords)

    def declare_attackers(self, game_state):
        # Simple: attack with all creatures
        my_creatures = [p for p in game_state.battlefield
                       if p.controller_id == self.player.player_id
                       and p.is_creature
                       and not p.is_tapped
                       and not p.has_summoning_sickness]

        return AttackDeclaration(attackers=my_creatures)

    def declare_blockers(self, game_state, attackers):
        # Block to minimize damage
        # (Simple implementation omitted for brevity)
        return BlockDeclaration(blocks={})
```

### Tournament Example

```python
"""Example: Run a tournament between multiple decks."""

from v3.engine.match import run_match, MatchResult
from v3.cards.parser import DecklistParser, Deck
from v3.cards.database import get_database
import itertools

def run_tournament(deck_files: List[str]) -> Dict[str, Dict[str, MatchResult]]:
    """
    Run round-robin tournament.

    Args:
        deck_files: List of paths to deck files

    Returns:
        Dictionary of deck1 -> deck2 -> MatchResult
    """
    # Load all decks
    parser = DecklistParser()
    database = get_database()

    decks = []
    for filepath in deck_files:
        decklist = parser.parse_file(filepath)
        deck = Deck.from_decklist(decklist, database)
        decks.append((filepath, deck))

    # Run all matchups
    results = {}

    for (name1, deck1), (name2, deck2) in itertools.combinations(decks, 2):
        print(f"\nMatch: {name1} vs {name2}")
        result = run_match(deck1, deck2, num_games=3)

        if name1 not in results:
            results[name1] = {}
        results[name1][name2] = result

        print(f"Result: {result.winner} wins {result.deck1_wins}-{result.deck2_wins}")

    return results

# Run tournament
deck_files = [
    "decks/mono_red.txt",
    "decks/control.txt",
    "decks/midrange.txt",
    "decks/combo.txt"
]

results = run_tournament(deck_files)
```

## Summary

The MTGO Engine V3 API provides:

- **Complete game simulation** with `Game` class
- **Type-safe objects** using dataclasses and enums
- **Extensible AI** through `AIAgent` interface
- **Card database** with parsing and lookup
- **Event system** for triggers and effects
- **Match/tournament utilities** for testing

All classes follow MTG Comprehensive Rules and include detailed docstrings. The zero-dependency design ensures portability and ease of deployment.

For architectural details, see [ARCHITECTURE.md](../ARCHITECTURE.md).
For getting started, see [QUICKSTART.md](../QUICKSTART.md).
