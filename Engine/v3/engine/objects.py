"""MTG Engine V3 - Game Objects

This module implements the core game object hierarchy as defined in the
Magic: The Gathering Comprehensive Rules:
- Section 109: Objects
- Section 110: Permanents
- Section 111: Tokens
- Section 112: Spells
- Section 113: Abilities

All game objects share common characteristics and can exist in various zones.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any, TYPE_CHECKING
import copy

from .types import Color, CardType, Supertype, CounterType

if TYPE_CHECKING:
    from .player import Player
    from .zones import Zone as ZoneObject


# =============================================================================
# Characteristics (CR 109.3)
# =============================================================================

@dataclass
class Characteristics:
    """
    Characteristics of a game object as defined in CR 109.3.

    These are the values printed on a card (or defined for tokens/copies)
    that can be modified by continuous effects during the game.
    """
    name: str = ""
    mana_cost: Optional[str] = None  # String format like "{2}{U}{U}"
    colors: Set[Color] = field(default_factory=set)
    types: Set[CardType] = field(default_factory=set)
    subtypes: Set[str] = field(default_factory=set)
    supertypes: Set[Supertype] = field(default_factory=set)
    power: Optional[int] = None
    toughness: Optional[int] = None
    loyalty: Optional[int] = None
    rules_text: str = ""

    def copy(self) -> 'Characteristics':
        """Create a deep copy of these characteristics."""
        return Characteristics(
            name=self.name,
            mana_cost=self.mana_cost,
            colors=set(self.colors),
            types=set(self.types),
            subtypes=set(self.subtypes),
            supertypes=set(self.supertypes),
            power=self.power,
            toughness=self.toughness,
            loyalty=self.loyalty,
            rules_text=self.rules_text
        )

    # Type checking convenience methods
    def is_creature(self) -> bool:
        return CardType.CREATURE in self.types

    def is_land(self) -> bool:
        return CardType.LAND in self.types

    def is_planeswalker(self) -> bool:
        return CardType.PLANESWALKER in self.types

    def is_artifact(self) -> bool:
        return CardType.ARTIFACT in self.types

    def is_enchantment(self) -> bool:
        return CardType.ENCHANTMENT in self.types

    def is_instant(self) -> bool:
        return CardType.INSTANT in self.types

    def is_sorcery(self) -> bool:
        return CardType.SORCERY in self.types

    def is_battle(self) -> bool:
        return CardType.BATTLE in self.types

    def is_legendary(self) -> bool:
        return Supertype.LEGENDARY in self.supertypes

    def is_basic(self) -> bool:
        return Supertype.BASIC in self.supertypes


# =============================================================================
# Base GameObject (CR 109)
# =============================================================================

@dataclass
class GameObject:
    """
    Base class for all game objects as defined in CR 109.

    Game objects include cards, tokens, spell copies, abilities on the stack,
    emblems, and dungeons. All game objects have characteristics and can
    exist in zones.
    """
    object_id: int = 0

    # Characteristics - base (printed/original) and current (after effects)
    base_characteristics: Characteristics = field(default_factory=Characteristics)
    characteristics: Characteristics = field(default_factory=Characteristics)

    # Ownership and control (CR 108.3, 108.4)
    owner: Optional[Any] = None  # Player who owns this object
    controller: Optional[Any] = None  # Player who controls this object

    # Zone location
    zone: Optional[Any] = None  # Current zone containing this object

    # Timestamps for layer system (CR 613)
    timestamp: int = 0

    def __post_init__(self):
        """Initialize characteristics copy if not set."""
        if self.characteristics.name == "" and self.base_characteristics.name != "":
            self.characteristics = self.base_characteristics.copy()

    @property
    def name(self) -> str:
        return self.characteristics.name

    @property
    def mana_cost(self) -> Optional[str]:
        return self.characteristics.mana_cost

    @property
    def colors(self) -> Set[Color]:
        return self.characteristics.colors

    @property
    def types(self) -> Set[CardType]:
        return self.characteristics.types

    @property
    def subtypes(self) -> Set[str]:
        return self.characteristics.subtypes

    @property
    def supertypes(self) -> Set[Supertype]:
        return self.characteristics.supertypes

    def reset_characteristics(self):
        """Reset current characteristics to base values."""
        self.characteristics = self.base_characteristics.copy()

    def get_controller(self) -> Optional[Any]:
        """Get the controller, defaulting to owner if not set."""
        return self.controller if self.controller is not None else self.owner

    @property
    def owner_id(self) -> int:
        """Get the owner's player ID."""
        if self.owner and hasattr(self.owner, 'player_id'):
            return self.owner.player_id
        return 0

    @property
    def controller_id(self) -> int:
        """Get the controller's player ID."""
        ctrl = self.get_controller()
        if ctrl and hasattr(ctrl, 'player_id'):
            return ctrl.player_id
        return 0


# =============================================================================
# Card (CR 108)
# =============================================================================

@dataclass
class Card(GameObject):
    """
    A card object as defined in CR 108.

    Cards are the primary game objects. They have printed characteristics
    and can exist in any zone. When cast, they become spells on the stack.
    When they resolve (if permanent types), they become permanents.
    """
    # For double-faced cards
    back_face_characteristics: Optional[Characteristics] = None
    is_transformed: bool = False

    # For split cards
    split_characteristics: Optional[List[Characteristics]] = None

    # For adventure cards
    adventure_characteristics: Optional[Characteristics] = None

    def get_active_characteristics(self) -> Characteristics:
        """Get the currently active face's characteristics."""
        if self.is_transformed and self.back_face_characteristics:
            return self.back_face_characteristics
        return self.characteristics

    def transform(self):
        """Transform this double-faced card."""
        if self.back_face_characteristics is not None:
            self.is_transformed = not self.is_transformed


# =============================================================================
# Permanent (CR 110)
# =============================================================================

@dataclass
class Permanent(GameObject):
    """
    A permanent on the battlefield as defined in CR 110.

    Permanents have additional state beyond base game objects including
    tap status, counters, damage, and attachments.
    """
    # Status flags (CR 110.5)
    is_tapped: bool = False
    is_flipped: bool = False
    is_face_down: bool = False
    is_phased_out: bool = False

    # Damage tracking (CR 120)
    damage_marked: int = 0
    dealt_damage_by_deathtouch: bool = False

    # Counters (CR 122)
    counters: Dict[CounterType, int] = field(default_factory=dict)

    # Attachments (CR 301.5, 303.4)
    attached_to: Optional['Permanent'] = None
    attachments: List['Permanent'] = field(default_factory=list)

    # Summoning sickness tracking (CR 302.6)
    summoning_sick: bool = True
    entered_battlefield_this_turn: bool = True

    # Source card (if this permanent came from a card)
    source_card: Optional[Card] = None

    # Keyword cache for efficient lookup
    _keyword_cache: Set[str] = field(default_factory=set)

    # --- Tap/Untap Methods ---

    def tap(self) -> bool:
        """Tap this permanent (CR 701.21).

        Returns:
            True if the permanent was tapped, False if already tapped.
        """
        if self.is_tapped:
            return False  # Already tapped
        self.is_tapped = True
        return True

    def untap(self) -> bool:
        """Untap this permanent (CR 701.20).

        Returns:
            True if the permanent was untapped, False if already untapped.
        """
        if not self.is_tapped:
            return False  # Already untapped
        self.is_tapped = False
        return True

    # --- Counter Methods (CR 122) ---

    def add_counter(self, counter_type: CounterType, amount: int = 1):
        """Add counters of the specified type to this permanent."""
        if amount <= 0:
            return
        current = self.counters.get(counter_type, 0)
        self.counters[counter_type] = current + amount
        self._handle_counter_interaction()

    def remove_counter(self, counter_type: CounterType, amount: int = 1):
        """Remove counters of the specified type from this permanent."""
        if amount <= 0:
            return
        current = self.counters.get(counter_type, 0)
        new_amount = max(0, current - amount)
        if new_amount == 0:
            self.counters.pop(counter_type, None)
        else:
            self.counters[counter_type] = new_amount

    def get_counter_count(self, counter_type: CounterType) -> int:
        """Get the number of counters of a specific type."""
        return self.counters.get(counter_type, 0)

    def _handle_counter_interaction(self):
        """
        Handle +1/+1 and -1/-1 counter annihilation (CR 122.3).

        If a permanent has both +1/+1 and -1/-1 counters, they are
        removed in pairs as a state-based action.
        """
        plus = self.counters.get(CounterType.PLUS_ONE_PLUS_ONE, 0)
        minus = self.counters.get(CounterType.MINUS_ONE_MINUS_ONE, 0)

        if plus > 0 and minus > 0:
            to_remove = min(plus, minus)
            new_plus = plus - to_remove
            new_minus = minus - to_remove

            if new_plus == 0:
                self.counters.pop(CounterType.PLUS_ONE_PLUS_ONE, None)
            else:
                self.counters[CounterType.PLUS_ONE_PLUS_ONE] = new_plus

            if new_minus == 0:
                self.counters.pop(CounterType.MINUS_ONE_MINUS_ONE, None)
            else:
                self.counters[CounterType.MINUS_ONE_MINUS_ONE] = new_minus

    # --- Damage Methods (CR 120) ---

    def mark_damage(self, amount: int, source: 'GameObject',
                    has_deathtouch: bool = False):
        """
        Mark damage on this permanent (CR 120.3).

        Args:
            amount: Amount of damage to mark
            source: The source dealing the damage
            has_deathtouch: Whether the source has deathtouch
        """
        if amount <= 0:
            return
        self.damage_marked += amount
        if has_deathtouch:
            self.dealt_damage_by_deathtouch = True

    def clear_damage(self):
        """Clear all marked damage (happens at cleanup step)."""
        self.damage_marked = 0
        self.dealt_damage_by_deathtouch = False

    # --- Keyword Methods ---

    def has_keyword(self, keyword: str) -> bool:
        """Check if this permanent has a keyword ability."""
        return keyword.lower() in self._keyword_cache

    def add_keyword(self, keyword: str):
        """Add a keyword ability to this permanent."""
        self._keyword_cache.add(keyword.lower())

    def remove_keyword(self, keyword: str):
        """Remove a keyword ability from this permanent."""
        self._keyword_cache.discard(keyword.lower())

    # --- Type Properties ---

    @property
    def is_creature(self) -> bool:
        """Check if this is a creature."""
        return self.characteristics.is_creature()

    @property
    def is_land(self) -> bool:
        """Check if this is a land."""
        return self.characteristics.is_land()

    @property
    def is_planeswalker(self) -> bool:
        """Check if this is a planeswalker."""
        return self.characteristics.is_planeswalker()

    @property
    def is_artifact(self) -> bool:
        """Check if this is an artifact."""
        return self.characteristics.is_artifact()

    @property
    def is_enchantment(self) -> bool:
        """Check if this is an enchantment."""
        return self.characteristics.is_enchantment()

    # --- Power/Toughness Methods ---

    def eff_power(self) -> int:
        """
        Calculate effective power including counters (CR 613.4).

        Note: This is a simplified calculation. Full layer system
        applies all continuous effects in proper order.
        """
        base = self.characteristics.power or 0
        base += self.counters.get(CounterType.PLUS_ONE_PLUS_ONE, 0)
        base -= self.counters.get(CounterType.MINUS_ONE_MINUS_ONE, 0)
        return base

    def eff_toughness(self) -> int:
        """
        Calculate effective toughness including counters (CR 613.4).

        Note: This is a simplified calculation. Full layer system
        applies all continuous effects in proper order.
        """
        base = self.characteristics.toughness or 0
        base += self.counters.get(CounterType.PLUS_ONE_PLUS_ONE, 0)
        base -= self.counters.get(CounterType.MINUS_ONE_MINUS_ONE, 0)
        return base

    def has_lethal_damage(self) -> bool:
        """Check if this creature has lethal damage marked."""
        if not self.is_creature:
            return False
        toughness = self.eff_toughness()
        if toughness <= 0:
            return True
        if self.damage_marked >= toughness:
            return True
        if self.dealt_damage_by_deathtouch and self.damage_marked > 0:
            return True
        return False

    def has_summoning_sickness(self) -> bool:
        """Check if this creature has summoning sickness (CR 302.6)."""
        if not self.is_creature:
            return False
        if self.has_keyword("haste"):
            return False
        return self.summoning_sick

    # --- Turn Lifecycle ---

    def on_new_turn(self):
        """Called at the beginning of each turn."""
        self.entered_battlefield_this_turn = False
        # Summoning sickness clears when controlled continuously since start of turn
        if not self.entered_battlefield_this_turn:
            self.summoning_sick = False


# =============================================================================
# Spell (CR 112)
# =============================================================================

@dataclass
class Spell(GameObject):
    """
    A spell on the stack as defined in CR 112.

    When a card is cast, it becomes a spell on the stack. Spells
    have targets, modes, and other choices locked in during casting.
    """
    # Source card (None for copies of spells)
    card: Optional[Card] = None

    # Targeting
    targets: List[Any] = field(default_factory=list)

    # Modal spells (CR 700.2)
    modes: List[int] = field(default_factory=list)

    # X value for spells with {X} in cost (CR 107.3)
    x_value: Optional[int] = None

    # Copy tracking
    is_copy: bool = False

    # Additional spell information
    alternative_cost_used: Optional[str] = None  # "flashback", "overload", etc.
    kicked: bool = False
    kicked_times: int = 0  # For multikicker

    def __post_init__(self):
        """Initialize spell from card if provided."""
        super().__post_init__()
        if self.card is not None:
            self.base_characteristics = self.card.base_characteristics.copy()
            self.characteristics = self.card.characteristics.copy()
            self.owner = self.card.owner
            self.controller = self.card.controller

    def is_permanent_spell(self) -> bool:
        """Check if this spell will become a permanent on resolution."""
        permanent_types = {
            CardType.CREATURE, CardType.ARTIFACT, CardType.ENCHANTMENT,
            CardType.PLANESWALKER, CardType.LAND, CardType.BATTLE
        }
        return bool(self.characteristics.types & permanent_types)

    def has_legal_targets(self) -> bool:
        """
        Check if at least one target is still legal (CR 608.2b).

        A spell is countered on resolution if all targets are illegal.
        """
        if not self.targets:
            return True  # Spells with no targets are always legal
        # Actual legality checking would be done by the game engine
        return True

    def copy(self) -> 'Spell':
        """
        Create a copy of this spell (CR 707.10).

        The copy has the same characteristics, targets, modes, and
        other choices, but is not a card.
        """
        spell_copy = Spell(
            base_characteristics=self.base_characteristics.copy(),
            characteristics=self.characteristics.copy(),
            owner=self.controller,  # Controller of original becomes owner of copy
            controller=self.controller,
            targets=list(self.targets),  # Targets can be changed for copies
            modes=list(self.modes),
            x_value=self.x_value,
            is_copy=True,
            alternative_cost_used=self.alternative_cost_used,
            kicked=self.kicked,
            kicked_times=self.kicked_times
        )
        return spell_copy


# =============================================================================
# Token (CR 111)
# =============================================================================

@dataclass
class Token(Permanent):
    """
    A token permanent as defined in CR 111.

    Tokens are permanents that aren't represented by cards. They are
    created by effects and cease to exist in any zone other than
    the battlefield (CR 111.8).
    """
    is_token: bool = True

    # What created this token
    created_by: Optional[GameObject] = None

    @classmethod
    def create(cls,
               name: str,
               types: Set[CardType],
               power: Optional[int] = None,
               toughness: Optional[int] = None,
               colors: Optional[Set[Color]] = None,
               subtypes: Optional[Set[str]] = None,
               keywords: Optional[Set[str]] = None,
               owner: Optional[Any] = None,
               controller: Optional[Any] = None,
               created_by: Optional[GameObject] = None) -> 'Token':
        """
        Factory method to create a token with the specified characteristics.

        Args:
            name: Token name (e.g., "Soldier", "Zombie")
            types: Card types (e.g., {CardType.CREATURE})
            power: Power for creature tokens
            toughness: Toughness for creature tokens
            colors: Token colors
            subtypes: Creature types or other subtypes
            keywords: Keyword abilities
            owner: Player who owns the token
            controller: Player who controls the token
            created_by: The object that created this token
        """
        characteristics = Characteristics(
            name=name,
            types=types,
            power=power,
            toughness=toughness,
            colors=colors or set(),
            subtypes=subtypes or set()
        )

        token = cls(
            base_characteristics=characteristics,
            characteristics=characteristics.copy(),
            owner=owner,
            controller=controller or owner,
            created_by=created_by,
            summoning_sick=True,
            entered_battlefield_this_turn=True
        )

        # Add keywords
        if keywords:
            for kw in keywords:
                token.add_keyword(kw)

        return token

    @classmethod
    def create_creature(cls,
                        name: str,
                        power: int,
                        toughness: int,
                        colors: Optional[Set[Color]] = None,
                        subtypes: Optional[Set[str]] = None,
                        keywords: Optional[Set[str]] = None,
                        owner: Optional[Any] = None,
                        controller: Optional[Any] = None,
                        created_by: Optional[GameObject] = None) -> 'Token':
        """Convenience method to create a creature token."""
        return cls.create(
            name=name,
            types={CardType.CREATURE},
            power=power,
            toughness=toughness,
            colors=colors,
            subtypes=subtypes,
            keywords=keywords,
            owner=owner,
            controller=controller,
            created_by=created_by
        )


# =============================================================================
# Ability (CR 113) - Base Implementation
# =============================================================================

@dataclass
class Ability:
    """
    Base class for abilities as defined in CR 113.

    Abilities are either:
    - Activated: "[Cost]: [Effect]"
    - Triggered: "When/Whenever/At [condition], [effect]"
    - Static: Continuous effects

    This is a base implementation. Detailed ability handling is in
    the effects module.
    """
    # Source of the ability
    source: Optional[GameObject] = None

    # Controller of the ability (may differ from source controller)
    controller: Optional[Any] = None  # Player

    # Ability text for display/parsing
    rules_text: str = ""

    # Ability identifier
    ability_id: int = 0

    def get_controller(self) -> Optional[Any]:
        """
        Get the controller of this ability.

        Defaults to the controller of the source if not explicitly set.
        """
        if self.controller is not None:
            return self.controller
        if self.source is not None:
            return self.source.get_controller()
        return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'Characteristics',
    'GameObject',
    'Card',
    'Permanent',
    'Spell',
    'Token',
    'Ability',
]
