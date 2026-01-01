"""MTG Engine V3 - Core Types and Enumerations

This module defines all fundamental types, enumerations, and type aliases
used throughout the MTG simulation engine. These definitions follow the
Magic: The Gathering Comprehensive Rules.
"""
from enum import Enum, Flag, auto
from typing import (
    Set, List, Dict, Optional, Union, Callable, Any,
    Tuple, FrozenSet, TypeVar, Generic, Protocol, TYPE_CHECKING
)
from dataclasses import dataclass, field


# =============================================================================
# Type Aliases
# =============================================================================

PlayerId = int
ObjectId = int
Timestamp = int
ZoneId = int
ManaValue = int
LifeTotal = int
DamageAmount = int
Power = int
Toughness = int
Loyalty = int
DefenseValue = int


# =============================================================================
# Color and Mana Types
# =============================================================================

class Color(Flag):
    """
    The five colors of Magic plus colorless.

    Uses Flag to allow combining colors for multicolored cards.
    The WUBRG ordering follows official Magic convention.

    Reference: CR 105 (Colors)
    """
    COLORLESS = 0
    WHITE = auto()
    BLUE = auto()
    BLACK = auto()
    RED = auto()
    GREEN = auto()

    # Common color combinations
    AZORIUS = WHITE | BLUE
    DIMIR = BLUE | BLACK
    RAKDOS = BLACK | RED
    GRUUL = RED | GREEN
    SELESNYA = GREEN | WHITE
    ORZHOV = WHITE | BLACK
    IZZET = BLUE | RED
    GOLGARI = BLACK | GREEN
    BOROS = RED | WHITE
    SIMIC = GREEN | BLUE

    @classmethod
    def all_colors(cls) -> "Color":
        """Returns a Color flag with all five colors set."""
        return cls.WHITE | cls.BLUE | cls.BLACK | cls.RED | cls.GREEN


class ManaType(Enum):
    """
    Types of mana that can be produced and spent.

    Reference: CR 106 (Mana)
    """
    WHITE = 'W'
    BLUE = 'U'
    BLACK = 'B'
    RED = 'R'
    GREEN = 'G'
    COLORLESS = 'C'
    GENERIC = 'X'  # Can be paid with any type
    SNOW = 'S'
    PHYREXIAN_WHITE = 'PW'
    PHYREXIAN_BLUE = 'PU'
    PHYREXIAN_BLACK = 'PB'
    PHYREXIAN_RED = 'PR'
    PHYREXIAN_GREEN = 'PG'

    def to_color(self) -> Color:
        """Converts this mana type to its corresponding color."""
        mapping = {
            ManaType.WHITE: Color.WHITE,
            ManaType.BLUE: Color.BLUE,
            ManaType.BLACK: Color.BLACK,
            ManaType.RED: Color.RED,
            ManaType.GREEN: Color.GREEN,
            ManaType.COLORLESS: Color.COLORLESS,
            ManaType.PHYREXIAN_WHITE: Color.WHITE,
            ManaType.PHYREXIAN_BLUE: Color.BLUE,
            ManaType.PHYREXIAN_BLACK: Color.BLACK,
            ManaType.PHYREXIAN_RED: Color.RED,
            ManaType.PHYREXIAN_GREEN: Color.GREEN,
        }
        return mapping.get(self, Color.COLORLESS)


class ColorIdentity(Flag):
    """Color identity flags for Commander format."""
    COLORLESS = 0
    WHITE = auto()
    BLUE = auto()
    BLACK = auto()
    RED = auto()
    GREEN = auto()


# =============================================================================
# Card Types
# =============================================================================

class CardType(Enum):
    """
    Main card types as defined in CR 300-310.

    A card can have multiple types (e.g., Artifact Creature).
    """
    CREATURE = auto()
    INSTANT = auto()
    SORCERY = auto()
    ENCHANTMENT = auto()
    ARTIFACT = auto()
    LAND = auto()
    PLANESWALKER = auto()
    BATTLE = auto()
    TRIBAL = auto()  # Deprecated but still legal
    KINDRED = auto()  # Replacement for Tribal (2024+)
    DUNGEON = auto()
    PLANE = auto()
    PHENOMENON = auto()
    VANGUARD = auto()
    SCHEME = auto()
    CONSPIRACY = auto()

    def is_permanent_type(self) -> bool:
        """Returns True if this card type represents a permanent."""
        return self in {
            CardType.CREATURE,
            CardType.ENCHANTMENT,
            CardType.ARTIFACT,
            CardType.LAND,
            CardType.PLANESWALKER,
            CardType.BATTLE,
        }

    def can_be_cast(self) -> bool:
        """Returns True if cards of this type can be cast (not played as lands)."""
        return self != CardType.LAND


class Supertype(Enum):
    """
    Supertypes as defined in CR 205.4.

    Supertypes appear before the card type on the type line
    and provide additional rules meaning.
    """
    LEGENDARY = auto()
    BASIC = auto()
    SNOW = auto()
    WORLD = auto()
    ONGOING = auto()  # Used in Archenemy
    ELITE = auto()    # Used in specific sets


class PermanentType(Enum):
    """Card types that are permanents on the battlefield."""
    CREATURE = auto()
    ENCHANTMENT = auto()
    ARTIFACT = auto()
    LAND = auto()
    PLANESWALKER = auto()
    BATTLE = auto()


# =============================================================================
# Zones
# =============================================================================

class Zone(Enum):
    """
    Game zones as defined in CR 400.

    Zones are areas where cards and other objects exist during a game.
    Each zone has specific rules about visibility and ordering.
    """
    LIBRARY = auto()      # Face-down, ordered
    HAND = auto()         # Hidden from opponents
    BATTLEFIELD = auto()  # Public, unordered
    GRAVEYARD = auto()    # Public, ordered
    STACK = auto()        # Public, ordered (LIFO)
    EXILE = auto()        # Public, unordered (usually)
    COMMAND = auto()      # Public (commanders, emblems, etc.)
    ANTE = auto()         # Legacy zone, rarely used
    SIDEBOARD = auto()    # During construction
    OUTSIDE_GAME = auto() # Companion, wish targets

    def is_public(self) -> bool:
        """Returns True if objects in this zone are visible to all players."""
        return self in {
            Zone.BATTLEFIELD,
            Zone.GRAVEYARD,
            Zone.STACK,
            Zone.EXILE,
            Zone.COMMAND,
        }

    def is_ordered(self) -> bool:
        """Returns True if the order of objects in this zone matters."""
        return self in {
            Zone.LIBRARY,
            Zone.GRAVEYARD,
            Zone.STACK,
        }


class ZoneVisibility(Enum):
    """Visibility rules for zones."""
    HIDDEN = auto()       # Library
    PRIVATE = auto()      # Hand (owner only)
    PUBLIC = auto()       # Battlefield, graveyard, stack, exile
    FACE_DOWN = auto()    # Morph, manifest


# =============================================================================
# Turn Structure
# =============================================================================

class PhaseType(Enum):
    """
    Phases of a turn as defined in CR 500.

    Each phase contains one or more steps. Phases define the
    overall structure of a turn.
    """
    BEGINNING = auto()
    PRECOMBAT_MAIN = auto()
    COMBAT = auto()
    POSTCOMBAT_MAIN = auto()
    ENDING = auto()


class StepType(Enum):
    """
    Steps within phases as defined in CR 501-512.

    Steps are the granular divisions of a turn where specific
    game actions occur and players receive priority.
    """
    # Beginning phase
    UNTAP = auto()
    UPKEEP = auto()
    DRAW = auto()

    # Main phase (represented as single step for consistency)
    PRECOMBAT_MAIN = auto()

    # Combat phase
    BEGINNING_OF_COMBAT = auto()
    DECLARE_ATTACKERS = auto()
    DECLARE_BLOCKERS = auto()
    FIRST_STRIKE_DAMAGE = auto()  # Only occurs when first/double strike exists
    COMBAT_DAMAGE = auto()
    END_OF_COMBAT = auto()

    # Second main phase
    POSTCOMBAT_MAIN = auto()

    # Ending phase
    END = auto()
    CLEANUP = auto()

    def players_get_priority(self) -> bool:
        """
        Returns True if players normally receive priority during this step.

        Note: Players don't normally get priority during untap and cleanup,
        unless a triggered ability triggers or a state-based action is performed.
        """
        return self not in {StepType.UNTAP, StepType.CLEANUP}

    def get_phase(self) -> PhaseType:
        """Returns the phase this step belongs to."""
        if self in {StepType.UNTAP, StepType.UPKEEP, StepType.DRAW}:
            return PhaseType.BEGINNING
        elif self == StepType.PRECOMBAT_MAIN:
            return PhaseType.PRECOMBAT_MAIN
        elif self in {
            StepType.BEGINNING_OF_COMBAT,
            StepType.DECLARE_ATTACKERS,
            StepType.DECLARE_BLOCKERS,
            StepType.COMBAT_DAMAGE,
            StepType.FIRST_STRIKE_DAMAGE,
            StepType.END_OF_COMBAT,
        }:
            return PhaseType.COMBAT
        elif self == StepType.POSTCOMBAT_MAIN:
            return PhaseType.POSTCOMBAT_MAIN
        else:
            return PhaseType.ENDING


class TurnFlag(Flag):
    """Flags tracking various turn-based restrictions and states."""
    NONE = 0
    LAND_PLAYED = auto()
    ATTACKED_THIS_TURN = auto()
    BLOCKED_THIS_TURN = auto()
    CAST_SPELL_THIS_TURN = auto()
    DRAWN_CARD_THIS_TURN = auto()
    CREATURE_DIED_THIS_TURN = auto()
    LIFE_GAINED_THIS_TURN = auto()
    LIFE_LOST_THIS_TURN = auto()
    DAMAGE_DEALT_THIS_TURN = auto()


# =============================================================================
# Counters
# =============================================================================

class CounterType(Enum):
    """
    Counter types that can be placed on objects or players.

    Counters are markers placed on objects or players that modify
    characteristics or track information.

    Reference: CR 122 (Counters)
    """
    # Power/Toughness modifiers
    PLUS_ONE_PLUS_ONE = "+1/+1"
    MINUS_ONE_MINUS_ONE = "-1/-1"
    PLUS_TWO_PLUS_ZERO = "+2/+0"
    PLUS_ZERO_PLUS_ONE = "+0/+1"
    PLUS_ZERO_PLUS_TWO = "+0/+2"
    PLUS_ONE_PLUS_ZERO = "+1/+0"
    PLUS_ONE_PLUS_TWO = "+1/+2"
    MINUS_ZERO_MINUS_ONE = "-0/-1"
    MINUS_ZERO_MINUS_TWO = "-0/-2"
    MINUS_ONE_MINUS_ZERO = "-1/-0"
    MINUS_TWO_MINUS_ONE = "-2/-1"
    MINUS_TWO_MINUS_TWO = "-2/-2"

    # Planeswalker
    LOYALTY = "loyalty"

    # Battle
    DEFENSE = "defense"

    # Common named counters
    CHARGE = "charge"
    AGE = "age"
    AIM = "aim"
    ARROW = "arrow"
    ARROWHEAD = "arrowhead"
    AWAKENING = "awakening"
    BLAZE = "blaze"
    BLOOD = "blood"
    BOUNTY = "bounty"
    BRIBERY = "bribery"
    BRICK = "brick"
    CAGE = "cage"
    CARRION = "carrion"
    COIN = "coin"
    CORPSE = "corpse"
    CREDIT = "credit"
    CRYSTAL = "crystal"
    CUBE = "cube"
    CURRENCY = "currency"
    DEATH = "death"
    DELAY = "delay"
    DEPLETION = "depletion"
    DESPAIR = "despair"
    DEVOTION = "devotion"
    DIVINITY = "divinity"
    DOOM = "doom"
    DREAM = "dream"
    ECHO = "echo"
    EGG = "egg"
    ELIXIR = "elixir"
    ENERGY = "energy"
    EON = "eon"
    EXPERIENCE = "experience"
    EYEBALL = "eyeball"
    FADE = "fade"
    FATE = "fate"
    FEATHER = "feather"
    FETCH = "fetch"
    FILIBUSTER = "filibuster"
    FLAME = "flame"
    FLOOD = "flood"
    FLYING = "flying"
    FORESHADOW = "foreshadow"
    FUNGUS = "fungus"
    FUNK = "funk"
    FUSE = "fuse"
    GEM = "gem"
    GLYPH = "glyph"
    GOLD = "gold"
    GROWTH = "growth"
    HATCHLING = "hatchling"
    HEALING = "healing"
    HIT = "hit"
    HOOFPRINT = "hoofprint"
    HOUR = "hour"
    HOURGLASS = "hourglass"
    HUNGER = "hunger"
    ICE = "ice"
    INCARNATION = "incarnation"
    INFECTION = "infection"
    INFESTATION = "infestation"
    INFLUENCE = "influence"
    INGENUITY = "ingenuity"
    INTERVENTION = "intervention"
    ISOLATION = "isolation"
    JAVELIN = "javelin"
    JUDGMENT = "judgment"
    KI = "ki"
    KNOWLEDGE = "knowledge"
    LEVEL = "level"
    LORE = "lore"
    LUCK = "luck"
    MAGNET = "magnet"
    MANIFESTATION = "manifestation"
    MANNEQUIN = "mannequin"
    MASK = "mask"
    MATRIX = "matrix"
    MEMORY = "memory"
    MINE = "mine"
    MINING = "mining"
    MIRE = "mire"
    MUSIC = "music"
    MUSTER = "muster"
    NET = "net"
    NIGHT = "night"
    OIL = "oil"
    OMEN = "omen"
    ORE = "ore"
    PAGE = "page"
    PAIN = "pain"
    PARALYZATION = "paralyzation"
    PETAL = "petal"
    PETRIFICATION = "petrification"
    PHYLACTERY = "phylactery"
    PIN = "pin"
    PLAGUE = "plague"
    PLOT = "plot"
    POISON = "poison"
    POLYP = "polyp"
    PRESSURE = "pressure"
    PREY = "prey"
    PUPA = "pupa"
    QUEST = "quest"
    RAD = "rad"
    RING = "ring"
    RUST = "rust"
    SCREAM = "scream"
    SCROLL = "scroll"
    SHELL = "shell"
    SHIELD = "shield"
    SHRED = "shred"
    SILVER = "silver"
    SLEEP = "sleep"
    SLIME = "slime"
    SLUMBER = "slumber"
    SOOT = "soot"
    SOUL = "soul"
    SPARK = "spark"
    SPORE = "spore"
    STASH = "stash"
    STORAGE = "storage"
    STRIFE = "strife"
    STUDY = "study"
    STUN = "stun"
    SUSPECT = "suspect"
    TASK = "task"
    THEFT = "theft"
    TICKET = "ticket"
    TIDE = "tide"
    TIME = "time"
    TOWER = "tower"
    TRAINING = "training"
    TRAP = "trap"
    TREASURE = "treasure"
    UNITY = "unity"
    VELOCITY = "velocity"
    VERSE = "verse"
    VITALITY = "vitality"
    VOID = "void"
    VORTEX = "vortex"
    VOYAGE = "voyage"
    WAGE = "wage"
    WINCH = "winch"
    WIND = "wind"
    WISH = "wish"

    def modifies_power_toughness(self) -> bool:
        """Returns True if this counter type modifies power and/or toughness."""
        return self in {
            CounterType.PLUS_ONE_PLUS_ONE,
            CounterType.MINUS_ONE_MINUS_ONE,
            CounterType.PLUS_TWO_PLUS_ZERO,
            CounterType.PLUS_ZERO_PLUS_ONE,
            CounterType.PLUS_ZERO_PLUS_TWO,
            CounterType.PLUS_ONE_PLUS_ZERO,
            CounterType.PLUS_ONE_PLUS_TWO,
            CounterType.MINUS_ZERO_MINUS_ONE,
            CounterType.MINUS_ZERO_MINUS_TWO,
            CounterType.MINUS_ONE_MINUS_ZERO,
            CounterType.MINUS_TWO_MINUS_ONE,
            CounterType.MINUS_TWO_MINUS_TWO,
        }


# =============================================================================
# Abilities
# =============================================================================

class AbilityType(Enum):
    """
    Types of abilities as defined in CR 112-113.

    Abilities define what cards can do. Each type has different
    rules for when and how it can be used.
    """
    TRIGGERED = auto()    # Triggered by game events ("When...", "Whenever...", "At...")
    ACTIVATED = auto()    # Activated by paying costs ("Cost: Effect")
    STATIC = auto()       # Always in effect while on battlefield
    MANA = auto()         # Special activated ability that produces mana
    SPELL = auto()        # Ability of a spell on the stack
    EVASION = auto()      # Affects how creatures can be blocked
    REPLACEMENT = auto()  # Replaces events with other events
    PREVENTION = auto()   # Prevents damage or other effects
    CHARACTERISTIC_DEFINING = auto()  # Defines characteristics in all zones
    LOYALTY = auto()      # Planeswalker loyalty abilities

    def uses_stack(self) -> bool:
        """Returns True if this ability type uses the stack when activated/triggered."""
        return self in {
            AbilityType.TRIGGERED,
            AbilityType.ACTIVATED,
            AbilityType.SPELL,
            AbilityType.LOYALTY,
        }


class TriggeredAbilityTriggerType(Enum):
    """When triggered abilities trigger."""
    ENTERS_BATTLEFIELD = auto()
    LEAVES_BATTLEFIELD = auto()
    DIES = auto()
    ATTACKS = auto()
    BLOCKS = auto()
    BECOMES_BLOCKED = auto()
    DEALS_DAMAGE = auto()
    DEALS_COMBAT_DAMAGE = auto()
    DEALS_COMBAT_DAMAGE_TO_PLAYER = auto()
    BEGINNING_OF_UPKEEP = auto()
    BEGINNING_OF_DRAW = auto()
    BEGINNING_OF_COMBAT = auto()
    BEGINNING_OF_END_STEP = auto()
    END_OF_COMBAT = auto()
    CAST = auto()
    SPELL_CAST = auto()
    ABILITY_ACTIVATED = auto()
    LIFE_GAINED = auto()
    LIFE_LOST = auto()
    COUNTER_PLACED = auto()
    COUNTER_REMOVED = auto()
    BECOMES_TARGET = auto()
    TAPS = auto()
    UNTAPS = auto()
    TRANSFORMS = auto()
    FLIPS = auto()
    WHENEVER = auto()  # Generic trigger


class TimingRestriction(Enum):
    """
    When abilities and spells can be activated/cast.

    Determines when a spell or ability can legally be cast or activated.

    Reference: CR 307 (Sorceries), CR 304 (Instants)
    """
    INSTANT = auto()      # Any time you have priority
    SORCERY = auto()      # Main phase, stack empty, your turn
    SPECIAL = auto()      # Has specific timing rules
    MANA_ABILITY = auto() # Doesn't use stack, can be activated during mana payment


class ActivationRestriction(Flag):
    """Restrictions on ability activation."""
    NONE = 0
    ONCE_PER_TURN = auto()
    ONLY_DURING_COMBAT = auto()
    ONLY_DURING_YOUR_TURN = auto()
    ONLY_AS_SORCERY = auto()
    ONLY_IF_ATTACKED = auto()
    ONLY_IF_BLOCKED = auto()
    TAP_REQUIRED = auto()
    UNTAP_REQUIRED = auto()


# =============================================================================
# Targeting
# =============================================================================

class TargetType(Enum):
    """
    Types of targets for spells and abilities.

    Used for defining and validating targeting requirements.

    Reference: CR 115 (Targets)
    """
    PLAYER = auto()
    CREATURE = auto()
    ARTIFACT = auto()
    ENCHANTMENT = auto()
    PLANESWALKER = auto()
    LAND = auto()
    PERMANENT = auto()
    SPELL = auto()
    ABILITY = auto()
    CARD = auto()  # In graveyard, hand, library
    ANY = auto()
    BATTLE = auto()
    CREATURE_OR_PLAYER = auto()
    CREATURE_OR_PLANESWALKER = auto()
    ANY_TARGET = auto()  # Creature, player, or planeswalker
    ATTACKING_CREATURE = auto()
    BLOCKING_CREATURE = auto()
    NONLAND_PERMANENT = auto()
    NONCREATURE_PERMANENT = auto()


class TargetRestriction(Flag):
    """Restrictions on valid targets."""
    NONE = 0
    OPPONENT_CONTROLS = auto()
    YOU_CONTROL = auto()
    ATTACKING = auto()
    BLOCKING = auto()
    TAPPED = auto()
    UNTAPPED = auto()
    WITH_FLYING = auto()
    WITHOUT_FLYING = auto()
    NONBLACK = auto()
    NONARTIFACT = auto()
    ANOTHER = auto()  # Other than source


# =============================================================================
# Player Actions
# =============================================================================

class ActionType(Enum):
    """
    Types of actions a player can take.

    These are the discrete actions that can be performed during
    a game, used for the action/priority system.

    Reference: CR 115-117 (Timing and Priority)
    """
    # Priority actions
    PASS = auto()              # Pass priority
    CAST_SPELL = auto()        # Cast a spell from hand or other zone
    ACTIVATE_ABILITY = auto()  # Activate an activated ability
    ACTIVATE_MANA_ABILITY = auto()  # Activate a mana ability
    PLAY_LAND = auto()         # Play a land (special action)

    # Combat actions
    ATTACK = auto()            # Declare a creature as an attacker
    BLOCK = auto()             # Declare a creature as a blocker
    DECLARE_ATTACKER = auto()  # Alias for ATTACK
    DECLARE_BLOCKER = auto()   # Alias for BLOCK
    ORDER_BLOCKERS = auto()    # Order blockers for damage assignment
    ORDER_ATTACKERS = auto()   # Order attackers (for blocking creature)
    ORDER_DAMAGE = auto()      # Assign combat damage

    # Special actions (don't use stack)
    SPECIAL_ACTION = auto()    # Generic special action
    TURN_FACE_UP = auto()      # Turn a face-down permanent face up
    SUSPEND = auto()           # Suspend a card from hand
    FORETELL = auto()          # Foretell a card from hand
    COMPANION = auto()         # Put companion into hand

    # Payment/Choice actions
    PAY_COST = auto()          # Pay a cost (mana, life, sacrifice, etc.)
    MAKE_CHOICE = auto()       # Make a game choice (modes, targets, etc.)
    ASSIGN_DAMAGE = auto()     # Assign combat damage

    # Triggered ability handling
    ORDER_TRIGGERS = auto()    # Order simultaneous triggered abilities

    # Concession
    CONCEDE = auto()           # Concede the game

    # Mulligan
    MULLIGAN = auto()          # Take a mulligan
    KEEP_HAND = auto()         # Keep current hand

    # Sideboarding
    SIDEBOARD = auto()         # Exchange cards with sideboard

    def requires_priority(self) -> bool:
        """Returns True if this action requires having priority."""
        return self in {
            ActionType.PASS,
            ActionType.CAST_SPELL,
            ActionType.ACTIVATE_ABILITY,
            ActionType.PLAY_LAND,
            ActionType.TURN_FACE_UP,
        }

    def is_special_action(self) -> bool:
        """Returns True if this is a special action (doesn't use stack)."""
        return self in {
            ActionType.PLAY_LAND,
            ActionType.TURN_FACE_UP,
            ActionType.SUSPEND,
            ActionType.FORETELL,
            ActionType.COMPANION,
            ActionType.SPECIAL_ACTION,
        }


class PriorityResult(Enum):
    """Result of priority passing."""
    PRIORITY_PASSED = auto()  # One player passed
    ALL_PASSED = auto()       # All players passed in succession
    ACTION_TAKEN = auto()     # Player took an action
    SBA_PERFORMED = auto()    # State-based actions were performed


class SpecialActionType(Enum):
    """Types of special actions (CR 116.2)."""
    TURN_FACE_UP = auto()     # Morph
    PLAY_LAND = auto()
    SUSPEND = auto()
    COMPANIONS_TO_HAND = auto()
    FORETELL = auto()
    ROLL_PLANAR_DIE = auto()


# =============================================================================
# Combat
# =============================================================================

class CombatStatus(Enum):
    """Combat-related status of creatures."""
    NOT_IN_COMBAT = auto()
    ATTACKING = auto()
    ATTACKING_PLANESWALKER = auto()
    ATTACKING_BATTLE = auto()
    BLOCKING = auto()
    BLOCKED = auto()
    UNBLOCKED = auto()


class DamageType(Flag):
    """
    Types of damage for tracking prevention and effects.

    Reference: CR 120 (Damage)
    """
    NORMAL = auto()
    COMBAT = auto()
    NONCOMBAT = auto()
    UNPREVENTABLE = auto()
    INFECT = auto()      # Dealt as -1/-1 counters to creatures
    WITHER = auto()      # Dealt as -1/-1 counters to creatures
    LIFELINK = auto()
    DEATHTOUCH = auto()
    TRAMPLE = auto()


# =============================================================================
# Layers System (CR 613)
# =============================================================================

class Layer(Enum):
    """Layers for continuous effects as defined in CR 613."""
    LAYER_1_COPY = 1
    LAYER_2_CONTROL = 2
    LAYER_3_TEXT = 3
    LAYER_4_TYPE = 4
    LAYER_5_COLOR = 5
    LAYER_6_ABILITY = 6
    LAYER_7A_CDA = 7        # Characteristic-defining abilities
    LAYER_7B_SET_PT = 8     # Set P/T to specific values
    LAYER_7C_MODIFY_PT = 9  # Modify P/T (+X/+Y, -X/-Y)
    LAYER_7D_COUNTER = 10   # P/T from counters
    LAYER_7E_SWITCH = 11    # Switch P/T


class DependencyType(Enum):
    """Types of dependencies between continuous effects."""
    NONE = auto()
    EXISTENCE = auto()  # Effect depends on another's existence
    VALUE = auto()      # Effect depends on another's value
    BEHAVIOR = auto()   # Effect modifies how another behaves


# =============================================================================
# Game State
# =============================================================================

class GamePhase(Enum):
    """High-level game phases."""
    NOT_STARTED = auto()
    MULLIGAN = auto()
    ACTIVE = auto()
    ENDED = auto()


class GameResult(Enum):
    """Possible game outcomes."""
    IN_PROGRESS = auto()
    WIN = auto()
    LOSS = auto()
    DRAW = auto()
    TIE = auto()


class ResultType(Enum):
    """Alias for GameResult for compatibility."""
    WIN = auto()
    LOSS = auto()
    DRAW = auto()
    IN_PROGRESS = auto()


class LossReason(Enum):
    """Reasons a player can lose."""
    ZERO_LIFE = auto()
    DREW_FROM_EMPTY_LIBRARY = auto()
    TEN_POISON_COUNTERS = auto()
    EFFECT = auto()  # "You lose the game"
    CONCEDED = auto()
    COMMANDER_DAMAGE = auto()  # 21+ from single commander


class WinReason(Enum):
    """Reasons a player can win."""
    OPPONENTS_LOST = auto()
    EFFECT = auto()  # "You win the game"


# =============================================================================
# Object Characteristics
# =============================================================================

class Characteristic(Enum):
    """Object characteristics as defined in CR 109.3."""
    NAME = auto()
    MANA_COST = auto()
    COLOR = auto()
    COLOR_INDICATOR = auto()
    TYPE = auto()
    SUBTYPE = auto()
    SUPERTYPE = auto()
    RULES_TEXT = auto()
    ABILITIES = auto()
    POWER = auto()
    TOUGHNESS = auto()
    LOYALTY = auto()
    DEFENSE = auto()
    HAND_MODIFIER = auto()
    LIFE_MODIFIER = auto()


class ObjectStatus(Flag):
    """Status flags for permanents."""
    NONE = 0
    TAPPED = auto()
    FLIPPED = auto()
    FACE_DOWN = auto()
    PHASED_OUT = auto()
    TRANSFORMED = auto()
    MONSTROUS = auto()
    RENOWNED = auto()
    GOADED = auto()
    SUSPECTED = auto()
    SADDLED = auto()


class StatusType(Enum):
    """
    Represents status conditions that can apply to permanents.

    These are boolean states that affect how a permanent functions.

    Reference: CR 110.5 (Status)
    """
    TAPPED = auto()
    UNTAPPED = auto()
    FLIPPED = auto()
    UNFLIPPED = auto()
    FACE_UP = auto()
    FACE_DOWN = auto()
    PHASED_IN = auto()
    PHASED_OUT = auto()


class TokenType(Enum):
    """Predefined token types for common tokens."""
    TREASURE = auto()
    FOOD = auto()
    CLUE = auto()
    BLOOD = auto()
    SOLDIER = auto()
    ZOMBIE = auto()
    SPIRIT = auto()
    SAPROLING = auto()
    BEAST = auto()
    GOBLIN = auto()
    ELEMENTAL = auto()
    ANGEL = auto()
    COPY = auto()  # Copy of another permanent


# =============================================================================
# Keywords and Keyword Abilities
# =============================================================================

class KeywordAbility(Enum):
    """
    Keyword abilities as defined in CR 702.

    Keyword abilities are abilities that are referenced by a single
    word or phrase and have specific rules meaning.
    """
    # Evergreen keywords
    DEATHTOUCH = auto()
    DEFENDER = auto()
    DOUBLE_STRIKE = auto()
    ENCHANT = auto()
    EQUIP = auto()
    FIRST_STRIKE = auto()
    FLASH = auto()
    FLYING = auto()
    HASTE = auto()
    HEXPROOF = auto()
    INDESTRUCTIBLE = auto()
    INTIMIDATE = auto()
    LANDWALK = auto()
    LIFELINK = auto()
    MENACE = auto()
    PROTECTION = auto()
    REACH = auto()
    SHROUD = auto()
    TRAMPLE = auto()
    VIGILANCE = auto()
    WARD = auto()

    # Combat keywords
    BANDING = auto()
    BUSHIDO = auto()
    FLANKING = auto()
    PROVOKE = auto()
    RAMPAGE = auto()
    SHADOW = auto()
    HORSEMANSHIP = auto()
    FEAR = auto()
    SKULK = auto()

    # Other common keywords
    AFFINITY = auto()
    ANNIHILATOR = auto()
    BATTLE_CRY = auto()
    BESTOW = auto()
    BLOODTHIRST = auto()
    CASCADE = auto()
    CHANGELING = auto()
    CHAMPION = auto()
    CIPHER = auto()
    CONSPIRE = auto()
    CONVOKE = auto()
    CREW = auto()
    CUMULATIVE_UPKEEP = auto()
    CYCLING = auto()
    DETHRONE = auto()
    DEVOID = auto()
    DEVOUR = auto()
    DREDGE = auto()
    ECHO = auto()
    EMBALM = auto()
    EMERGE = auto()
    ENTWINE = auto()
    ETERNALIZE = auto()
    EVOKE = auto()
    EVOLVE = auto()
    EXALTED = auto()
    EXPLOIT = auto()
    EXTORT = auto()
    FABRICATE = auto()
    FADING = auto()
    FLASHBACK = auto()
    FUSE = auto()
    GRAFT = auto()
    GRAVESTORM = auto()
    HAUNT = auto()
    HIDEAWAY = auto()
    IMPROVISE = auto()
    INFECT = auto()
    INGEST = auto()
    KICKER = auto()
    LIVING_WEAPON = auto()
    MADNESS = auto()
    MELEE = auto()
    MENTOR = auto()
    MIRACLE = auto()
    MODULAR = auto()
    MORPH = auto()
    MEGAMORPH = auto()
    DISGUISE = auto()
    CLOAK = auto()
    MYRIAD = auto()
    NINJUTSU = auto()
    OFFERING = auto()
    OUTLAST = auto()
    OVERLOAD = auto()
    PARTNER = auto()
    PERSIST = auto()
    PHASING = auto()
    POISONOUS = auto()
    PROWESS = auto()
    PROWL = auto()
    RAID = auto()
    RALLY = auto()
    REBOUND = auto()
    RECOVER = auto()
    REINFORCE = auto()
    RENOWN = auto()
    REPLICATE = auto()
    RETRACE = auto()
    RIOT = auto()
    SCAVENGE = auto()
    SOULBOND = auto()
    SOULSHIFT = auto()
    SPECTACLE = auto()
    SPLICE = auto()
    SPLIT_SECOND = auto()
    STORM = auto()
    SUNBURST = auto()
    SURGE = auto()
    SUSPEND = auto()
    TOTEM_ARMOR = auto()
    TRANSFIGURE = auto()
    TRANSMUTE = auto()
    TRIBUTE = auto()
    UNDAUNTED = auto()
    UNDYING = auto()
    UNEARTH = auto()
    UNLEASH = auto()
    VANISHING = auto()
    WITHER = auto()
    TOXIC = auto()

    # Equipment keywords
    RECONFIGURE = auto()
    FOR_MIRRODIN = auto()
    LIVING_METAL = auto()

    # Land keywords
    LANDCYCLING = auto()

    # Newer keywords
    ADVENTURE = auto()
    AMASS = auto()
    COMPANION = auto()
    ESCAPE = auto()
    FORETELL = auto()
    MUTATE = auto()
    LEARN = auto()
    DAYBOUND = auto()
    NIGHTBOUND = auto()
    DISTURB = auto()
    DECAYED = auto()
    CLEAVE = auto()
    TRAINING = auto()
    CASUALTY = auto()
    CONNIVE = auto()
    BLITZ = auto()
    ENLIST = auto()
    READ_AHEAD = auto()
    PROTOTYPE = auto()
    CORRUPTED = auto()
    BACKUP = auto()
    BARGAIN = auto()
    CRAFT = auto()
    OFFSPRING = auto()
    RAVENOUS = auto()
    SQUAD = auto()
    PLOT = auto()
    GIFT = auto()
    IMPENDING = auto()
    SURVIVAL = auto()

    def is_evasion(self) -> bool:
        """Returns True if this keyword provides evasion."""
        return self in {
            KeywordAbility.FLYING,
            KeywordAbility.FEAR,
            KeywordAbility.INTIMIDATE,
            KeywordAbility.HORSEMANSHIP,
            KeywordAbility.SHADOW,
            KeywordAbility.SKULK,
            KeywordAbility.MENACE,
            KeywordAbility.LANDWALK,
        }


class KeywordAction(Enum):
    """Keyword actions as defined in CR 701."""
    ACTIVATE = auto()
    ATTACH = auto()
    CAST = auto()
    COUNTER = auto()
    CREATE = auto()
    DESTROY = auto()
    DISCARD = auto()
    DOUBLE = auto()
    EXCHANGE = auto()
    EXILE = auto()
    FIGHT = auto()
    MILL = auto()
    PLAY = auto()
    REGENERATE = auto()
    REVEAL = auto()
    SACRIFICE = auto()
    SCRY = auto()
    SEARCH = auto()
    SHUFFLE = auto()
    TAP = auto()
    UNTAP = auto()
    TRANSFORM = auto()
    SURVEIL = auto()
    ADAPT = auto()
    AMASS = auto()
    BOLSTER = auto()
    CLASH = auto()
    CONNIVE_ACTION = auto()
    CONJURE = auto()
    DISCOVER = auto()
    EXPLORE = auto()
    FATESEAL = auto()
    GOAD = auto()
    INCUBATE = auto()
    INVESTIGATE = auto()
    LEARN = auto()
    MANIFEST = auto()
    MELD = auto()
    MONSTROSITY = auto()
    POPULATE = auto()
    PROLIFERATE = auto()
    ROLE = auto()
    SET_IN_MOTION = auto()
    SUPPORT = auto()
    VENTURE = auto()
    VOTE = auto()


# =============================================================================
# Replacement Effects
# =============================================================================

class ReplacementEffectType(Enum):
    """Types of replacement effects."""
    ENTERS_BATTLEFIELD = auto()  # ETB replacements
    LEAVES_BATTLEFIELD = auto()
    WOULD_DIE = auto()
    WOULD_DRAW = auto()
    WOULD_DISCARD = auto()
    WOULD_BE_DESTROYED = auto()
    WOULD_DEAL_DAMAGE = auto()
    WOULD_GAIN_LIFE = auto()
    WOULD_LOSE_LIFE = auto()
    WOULD_PUT_COUNTER = auto()
    WOULD_UNTAP = auto()
    WOULD_TAP = auto()
    IF_WOULD = auto()  # Generic "if X would happen"


class PreventionEffectType(Enum):
    """Types of prevention effects."""
    DAMAGE = auto()
    COMBAT_DAMAGE = auto()
    NONCOMBAT_DAMAGE = auto()
    ALL_DAMAGE = auto()
    NEXT_DAMAGE = auto()


# =============================================================================
# Cost Types
# =============================================================================

class CostType(Enum):
    """Types of costs."""
    MANA = auto()
    TAP = auto()
    UNTAP = auto()
    SACRIFICE = auto()
    DISCARD = auto()
    EXILE = auto()
    PAY_LIFE = auto()
    REMOVE_COUNTER = auto()
    PUT_COUNTER = auto()
    REVEAL = auto()
    RETURN_TO_HAND = auto()


class AdditionalCostType(Enum):
    """Types of additional costs."""
    KICKER = auto()
    MULTIKICKER = auto()
    BUYBACK = auto()
    ENTWINE = auto()
    ADDITIONAL = auto()
    ALTERNATIVE = auto()  # Like flashback
    COMMANDER_TAX = auto()


# =============================================================================
# Events
# =============================================================================

class GameEventType(Enum):
    """Types of game events that can be observed."""
    # Zone changes
    ZONE_CHANGE = auto()
    ENTERS_BATTLEFIELD = auto()
    LEAVES_BATTLEFIELD = auto()
    DIES = auto()
    EXILED = auto()
    PUT_INTO_GRAVEYARD = auto()
    RETURNED_TO_HAND = auto()
    PUT_INTO_LIBRARY = auto()
    DRAWN = auto()
    DISCARDED = auto()
    MILLED = auto()

    # Combat
    ATTACK_DECLARED = auto()
    BLOCK_DECLARED = auto()
    BECOMES_BLOCKED = auto()
    BECOMES_UNBLOCKED = auto()
    COMBAT_DAMAGE_DEALT = auto()

    # Damage and life
    DAMAGE_DEALT = auto()
    LIFE_GAINED = auto()
    LIFE_LOST = auto()
    LIFE_PAID = auto()

    # Spells and abilities
    SPELL_CAST = auto()
    ABILITY_ACTIVATED = auto()
    ABILITY_TRIGGERED = auto()
    SPELL_RESOLVED = auto()
    SPELL_COUNTERED = auto()

    # Counters
    COUNTER_ADDED = auto()
    COUNTER_REMOVED = auto()

    # Status changes
    TAPPED = auto()
    UNTAPPED = auto()
    TRANSFORMED = auto()
    FLIPPED = auto()
    PHASED_IN = auto()
    PHASED_OUT = auto()

    # Game structure
    TURN_BEGAN = auto()
    TURN_ENDED = auto()
    PHASE_BEGAN = auto()
    PHASE_ENDED = auto()
    STEP_BEGAN = auto()
    STEP_ENDED = auto()
    PRIORITY_PASSED = auto()

    # Player events
    PLAYER_LOST = auto()
    PLAYER_WON = auto()
    PLAYER_DREW = auto()  # Drew the game, not cards

    # Miscellaneous
    SEARCHED_LIBRARY = auto()
    SHUFFLED_LIBRARY = auto()
    REVEALED = auto()
    TARGETED = auto()
    BECAME_TARGET = auto()
    FIGHT = auto()
    CREATED_TOKEN = auto()
    REGENERATED = auto()
    SACRIFICED = auto()
    DESTROYED = auto()


# =============================================================================
# Format-Specific Types
# =============================================================================

class Format(Enum):
    """Supported game formats."""
    STANDARD = auto()
    MODERN = auto()
    LEGACY = auto()
    VINTAGE = auto()
    PAUPER = auto()
    COMMANDER = auto()
    BRAWL = auto()
    HISTORIC = auto()
    PIONEER = auto()
    ALCHEMY = auto()
    LIMITED_DRAFT = auto()
    LIMITED_SEALED = auto()
    TWO_HEADED_GIANT = auto()


class DeckZone(Enum):
    """Zones during deck construction."""
    MAIN_DECK = auto()
    SIDEBOARD = auto()
    COMPANION = auto()
    COMMAND_ZONE = auto()


# =============================================================================
# Data Classes for Complex Types
# =============================================================================

@dataclass(frozen=True)
class ManaCost:
    """Represents a mana cost."""
    white: int = 0
    blue: int = 0
    black: int = 0
    red: int = 0
    green: int = 0
    colorless: int = 0  # Specifically colorless (diamond symbol)
    generic: int = 0
    snow: int = 0
    phyrexian: Dict[Color, int] = field(default_factory=dict)
    hybrid: List[Tuple[ManaType, ManaType]] = field(default_factory=list)
    x_cost: int = 0  # Number of X in the cost

    @property
    def mana_value(self) -> int:
        """Calculate converted mana cost / mana value."""
        total = (self.white + self.blue + self.black +
                self.red + self.green + self.colorless +
                self.generic + self.snow)
        total += sum(self.phyrexian.values())
        total += len(self.hybrid)  # Each hybrid costs 1
        # X is 0 except on stack where it has a value
        return total

    @property
    def colors(self) -> Set[Color]:
        """Get colors in this mana cost."""
        result = set()
        if self.white > 0:
            result.add(Color.WHITE)
        if self.blue > 0:
            result.add(Color.BLUE)
        if self.black > 0:
            result.add(Color.BLACK)
        if self.red > 0:
            result.add(Color.RED)
        if self.green > 0:
            result.add(Color.GREEN)
        for color in self.phyrexian:
            result.add(color)
        for pair in self.hybrid:
            for mana_type in pair:
                if mana_type == ManaType.WHITE:
                    result.add(Color.WHITE)
                elif mana_type == ManaType.BLUE:
                    result.add(Color.BLUE)
                elif mana_type == ManaType.BLACK:
                    result.add(Color.BLACK)
                elif mana_type == ManaType.RED:
                    result.add(Color.RED)
                elif mana_type == ManaType.GREEN:
                    result.add(Color.GREEN)
        return result


@dataclass
class ManaPool:
    """Represents a player's mana pool."""
    white: int = 0
    blue: int = 0
    black: int = 0
    red: int = 0
    green: int = 0
    colorless: int = 0
    snow_white: int = 0
    snow_blue: int = 0
    snow_black: int = 0
    snow_red: int = 0
    snow_green: int = 0
    snow_colorless: int = 0

    def empty(self) -> int:
        """Empty the mana pool and return total mana lost."""
        total = (self.white + self.blue + self.black +
                self.red + self.green + self.colorless +
                self.snow_white + self.snow_blue + self.snow_black +
                self.snow_red + self.snow_green + self.snow_colorless)
        self.white = 0
        self.blue = 0
        self.black = 0
        self.red = 0
        self.green = 0
        self.colorless = 0
        self.snow_white = 0
        self.snow_blue = 0
        self.snow_black = 0
        self.snow_red = 0
        self.snow_green = 0
        self.snow_colorless = 0
        return total

    def total(self) -> int:
        """Get total mana in pool."""
        return (self.white + self.blue + self.black +
                self.red + self.green + self.colorless +
                self.snow_white + self.snow_blue + self.snow_black +
                self.snow_red + self.snow_green + self.snow_colorless)


@dataclass
class DamageInfo:
    """Information about damage being dealt."""
    source_id: ObjectId
    target_id: Union[ObjectId, PlayerId]
    amount: int
    is_combat: bool = False
    is_unpreventable: bool = False
    has_deathtouch: bool = False
    has_lifelink: bool = False
    has_infect: bool = False
    has_wither: bool = False
    has_trample: bool = False


@dataclass
class TargetInfo:
    """Information about a target."""
    target_type: TargetType
    target_id: Union[ObjectId, PlayerId]
    restrictions: TargetRestriction = TargetRestriction.NONE
    is_legal: bool = True


@dataclass
class CostRequirement:
    """Represents a cost that must be paid."""
    cost_type: CostType
    amount: Union[int, ManaCost, None] = None
    specific_type: Optional[str] = None  # e.g., "creature" for sacrifice
    is_paid: bool = False


@dataclass
class StackEntry:
    """Entry on the stack (spell or ability)."""
    object_id: ObjectId
    controller_id: PlayerId
    targets: List[TargetInfo] = field(default_factory=list)
    x_value: int = 0
    modes_chosen: List[int] = field(default_factory=list)
    additional_costs_paid: List[AdditionalCostType] = field(default_factory=list)
    timestamp: Timestamp = 0


@dataclass
class ContinuousEffect:
    """A continuous effect modifying the game state."""
    source_id: ObjectId
    layer: Layer
    timestamp: Timestamp
    duration: 'Duration'
    affected_objects: Optional[Callable[[ObjectId], bool]] = None
    modification: Optional[Callable[[Any], Any]] = None
    dependency: Optional['ContinuousEffect'] = None


class Duration(Enum):
    """Duration of continuous effects."""
    PERMANENT = auto()  # Until removed
    WHILE_ON_BATTLEFIELD = auto()
    WHILE_ATTACHED = auto()
    UNTIL_END_OF_TURN = auto()
    UNTIL_YOUR_NEXT_TURN = auto()
    UNTIL_END_OF_COMBAT = auto()
    UNTIL_LEAVES_BATTLEFIELD = auto()
    UNTIL_CLEANUP = auto()
    ONE_SHOT = auto()  # Immediately applies and is done


# =============================================================================
# Protocol Types for Duck Typing
# =============================================================================

class Targetable(Protocol):
    """Protocol for objects that can be targeted."""
    object_id: ObjectId
    def is_legal_target(self, source_id: ObjectId, target_type: TargetType) -> bool: ...


class Damageable(Protocol):
    """Protocol for objects that can receive damage."""
    object_id: ObjectId
    def receive_damage(self, damage: DamageInfo) -> int: ...


class Permanent(Protocol):
    """Protocol for permanents on the battlefield."""
    object_id: ObjectId
    controller_id: PlayerId
    status: ObjectStatus
    def tap(self) -> bool: ...
    def untap(self) -> bool: ...


# =============================================================================
# Type Variables for Generic Types
# =============================================================================

T = TypeVar('T')
CardT = TypeVar('CardT', bound='Permanent')
EffectT = TypeVar('EffectT', bound='ContinuousEffect')


# =============================================================================
# Utility Types
# =============================================================================

@dataclass
class GameAction:
    """Represents an action a player can take."""
    action_type: ActionType
    player_id: PlayerId
    source_id: Optional[ObjectId] = None
    targets: List[TargetInfo] = field(default_factory=list)
    mana_payment: Optional[ManaCost] = None
    x_value: int = 0
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Choice:
    """Represents a choice a player must make."""
    player_id: PlayerId
    choice_type: str  # e.g., "target", "mode", "order"
    options: List[Any]
    min_choices: int = 1
    max_choices: int = 1
    description: str = ""


@dataclass
class GameState:
    """Minimal game state snapshot for decision making."""
    active_player_id: PlayerId
    priority_player_id: Optional[PlayerId]
    phase: PhaseType
    step: StepType
    turn_number: int
    stack_empty: bool
    can_play_sorcery: bool


# =============================================================================
# Frozen Sets for Common Groupings
# =============================================================================

PERMANENT_TYPES: FrozenSet[CardType] = frozenset({
    CardType.CREATURE,
    CardType.ARTIFACT,
    CardType.ENCHANTMENT,
    CardType.LAND,
    CardType.PLANESWALKER,
    CardType.BATTLE,
})

SPELL_TYPES: FrozenSet[CardType] = frozenset({
    CardType.INSTANT,
    CardType.SORCERY,
})

MAIN_PHASES: FrozenSet[PhaseType] = frozenset({
    PhaseType.PRECOMBAT_MAIN,
    PhaseType.POSTCOMBAT_MAIN,
})

COMBAT_STEPS: FrozenSet[StepType] = frozenset({
    StepType.BEGINNING_OF_COMBAT,
    StepType.DECLARE_ATTACKERS,
    StepType.DECLARE_BLOCKERS,
    StepType.COMBAT_DAMAGE,
    StepType.FIRST_STRIKE_DAMAGE,
    StepType.END_OF_COMBAT,
})


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Type aliases
    'PlayerId', 'ObjectId', 'Timestamp', 'ZoneId', 'ManaValue',
    'LifeTotal', 'DamageAmount', 'Power', 'Toughness', 'Loyalty', 'DefenseValue',

    # Enums - Colors and Mana
    'Color', 'ManaType', 'ColorIdentity',

    # Enums - Card Types
    'CardType', 'Supertype', 'PermanentType',

    # Enums - Zones
    'Zone', 'ZoneVisibility',

    # Enums - Turn Structure
    'PhaseType', 'StepType', 'TurnFlag',

    # Enums - Counters
    'CounterType',

    # Enums - Abilities
    'AbilityType', 'TriggeredAbilityTriggerType', 'TimingRestriction',
    'ActivationRestriction',

    # Enums - Targeting
    'TargetType', 'TargetRestriction',

    # Enums - Actions
    'ActionType', 'PriorityResult', 'SpecialActionType',

    # Enums - Combat
    'CombatStatus', 'DamageType',

    # Enums - Layers
    'Layer', 'DependencyType',

    # Enums - Game State
    'GamePhase', 'GameResult', 'ResultType', 'LossReason', 'WinReason',

    # Enums - Characteristics
    'Characteristic', 'ObjectStatus', 'StatusType', 'TokenType',

    # Enums - Keywords
    'KeywordAbility', 'KeywordAction',

    # Enums - Replacement Effects
    'ReplacementEffectType', 'PreventionEffectType',

    # Enums - Costs
    'CostType', 'AdditionalCostType',

    # Enums - Events
    'GameEventType',

    # Enums - Formats
    'Format', 'DeckZone',

    # Enums - Duration
    'Duration',

    # Data Classes
    'ManaCost', 'ManaPool', 'DamageInfo', 'TargetInfo',
    'CostRequirement', 'StackEntry', 'ContinuousEffect',
    'GameAction', 'Choice', 'GameState',

    # Protocols
    'Targetable', 'Damageable', 'Permanent',

    # Type Variables
    'T', 'CardT', 'EffectT',

    # Frozen Sets
    'PERMANENT_TYPES', 'SPELL_TYPES', 'MAIN_PHASES', 'COMBAT_STEPS',
]
