"""
Static Keyword Abilities Implementation per MTG Comprehensive Rules 702.

This module implements all static keyword abilities that modify game rules
or creature interactions without requiring activation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Type, Callable, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from ..game import Game
    from ..permanent import Permanent
    from ..player import Player


class KeywordCategory(Enum):
    """Categories of static keywords per CR 702."""
    EVASION = auto()
    COMBAT = auto()
    PROTECTION = auto()
    CASTING = auto()
    TRIGGERED_STATIC = auto()
    OTHER = auto()


class ProtectionQuality(Enum):
    """Qualities that Protection can apply to (DEBT)."""
    DAMAGE = auto()          # D - Prevents all damage from sources with quality
    ENCHANT_EQUIP = auto()   # E - Can't be enchanted/equipped by permanents with quality
    BLOCK = auto()           # B - Can't be blocked by creatures with quality
    TARGET = auto()          # T - Can't be targeted by spells/abilities with quality


@dataclass
class StaticKeyword(ABC):
    """
    Base class for all static keyword abilities per CR 702.

    Static keywords are abilities that apply continuously while the
    permanent is on the battlefield (or in some cases, other zones).

    Attributes:
        keyword_name: The name of the keyword ability
        source: The permanent that has this keyword
        category: The category of keyword for rules processing
    """
    keyword_name: str
    source: Any  # Permanent
    category: KeywordCategory = field(default=KeywordCategory.OTHER)

    def apply(self, game: 'Game') -> None:
        """
        Called when this keyword effect should be applied to the game state.

        This is invoked during layer processing when the permanent enters
        the battlefield or when the keyword is granted.

        Args:
            game: The current game state
        """
        pass

    def remove(self, game: 'Game') -> None:
        """
        Called when this keyword effect should be removed from the game state.

        This is invoked when the permanent leaves the battlefield or
        when the keyword is removed by another effect.

        Args:
            game: The current game state
        """
        pass

    def __hash__(self) -> int:
        return hash((self.keyword_name, id(self.source)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StaticKeyword):
            return False
        return self.keyword_name == other.keyword_name and self.source is other.source


# =============================================================================
# EVASION KEYWORDS (CR 702.9, 702.110, 702.117, etc.)
# =============================================================================

@dataclass
class Flying(StaticKeyword):
    """
    Flying (CR 702.9)

    A creature with flying can't be blocked except by creatures with
    flying and/or reach.
    """
    keyword_name: str = field(default="Flying", init=False)
    category: KeywordCategory = field(default=KeywordCategory.EVASION, init=False)

    def can_be_blocked_by(self, blocker: 'Permanent') -> bool:
        """Check if this flying creature can be blocked by the given creature."""
        blocker_keywords = get_keyword_names(blocker)
        return "Flying" in blocker_keywords or "Reach" in blocker_keywords


@dataclass
class Menace(StaticKeyword):
    """
    Menace (CR 702.110)

    A creature with menace can't be blocked except by two or more creatures.
    """
    keyword_name: str = field(default="Menace", init=False)
    category: KeywordCategory = field(default=KeywordCategory.EVASION, init=False)

    def minimum_blockers_required(self) -> int:
        """Return the minimum number of blockers required."""
        return 2


@dataclass
class Skulk(StaticKeyword):
    """
    Skulk (CR 702.117)

    A creature with skulk can't be blocked by creatures with greater power.
    """
    keyword_name: str = field(default="Skulk", init=False)
    category: KeywordCategory = field(default=KeywordCategory.EVASION, init=False)

    def can_be_blocked_by(self, blocker: 'Permanent') -> bool:
        """Check if this creature can be blocked by the given creature."""
        source_power = getattr(self.source, 'power', 0)
        blocker_power = getattr(blocker, 'power', 0)
        return blocker_power <= source_power


@dataclass
class Shadow(StaticKeyword):
    """
    Shadow (CR 702.28)

    A creature with shadow can block or be blocked by only creatures with shadow.
    """
    keyword_name: str = field(default="Shadow", init=False)
    category: KeywordCategory = field(default=KeywordCategory.EVASION, init=False)

    def can_be_blocked_by(self, blocker: 'Permanent') -> bool:
        """Check if this creature can be blocked by the given creature."""
        return "Shadow" in get_keyword_names(blocker)

    def can_block(self, attacker: 'Permanent') -> bool:
        """Check if this creature can block the given attacker."""
        return "Shadow" in get_keyword_names(attacker)


@dataclass
class Fear(StaticKeyword):
    """
    Fear (CR 702.36)

    A creature with fear can't be blocked except by artifact creatures
    and/or black creatures.
    """
    keyword_name: str = field(default="Fear", init=False)
    category: KeywordCategory = field(default=KeywordCategory.EVASION, init=False)

    def can_be_blocked_by(self, blocker: 'Permanent') -> bool:
        """Check if this creature can be blocked by the given creature."""
        blocker_types = getattr(blocker, 'card_types', set())
        blocker_colors = getattr(blocker, 'colors', set())

        is_artifact_creature = 'artifact' in {t.lower() for t in blocker_types}
        is_black = 'black' in {c.lower() for c in blocker_colors}

        return is_artifact_creature or is_black


@dataclass
class Intimidate(StaticKeyword):
    """
    Intimidate (CR 702.13)

    A creature with intimidate can't be blocked except by artifact creatures
    and/or creatures that share a color with it.
    """
    keyword_name: str = field(default="Intimidate", init=False)
    category: KeywordCategory = field(default=KeywordCategory.EVASION, init=False)

    def can_be_blocked_by(self, blocker: 'Permanent') -> bool:
        """Check if this creature can be blocked by the given creature."""
        blocker_types = getattr(blocker, 'card_types', set())
        blocker_colors = set(c.lower() for c in getattr(blocker, 'colors', set()))
        source_colors = set(c.lower() for c in getattr(self.source, 'colors', set()))

        is_artifact_creature = 'artifact' in {t.lower() for t in blocker_types}
        shares_color = bool(blocker_colors & source_colors)

        return is_artifact_creature or shares_color


@dataclass
class Horsemanship(StaticKeyword):
    """
    Horsemanship (CR 702.30)

    A creature with horsemanship can't be blocked except by creatures
    with horsemanship.
    """
    keyword_name: str = field(default="Horsemanship", init=False)
    category: KeywordCategory = field(default=KeywordCategory.EVASION, init=False)

    def can_be_blocked_by(self, blocker: 'Permanent') -> bool:
        """Check if this creature can be blocked by the given creature."""
        return "Horsemanship" in get_keyword_names(blocker)


# =============================================================================
# COMBAT KEYWORDS (CR 702.2, 702.4, 702.7, etc.)
# =============================================================================

@dataclass
class FirstStrike(StaticKeyword):
    """
    First Strike (CR 702.7)

    A creature with first strike deals combat damage before creatures
    without first strike.
    """
    keyword_name: str = field(default="First Strike", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def deals_first_strike_damage(self) -> bool:
        """Return True if this creature deals damage in the first strike step."""
        return True

    def deals_normal_damage(self) -> bool:
        """Return True if this creature deals damage in the normal combat step."""
        return False


@dataclass
class DoubleStrike(StaticKeyword):
    """
    Double Strike (CR 702.4)

    A creature with double strike deals both first-strike and regular
    combat damage.
    """
    keyword_name: str = field(default="Double Strike", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def deals_first_strike_damage(self) -> bool:
        """Return True if this creature deals damage in the first strike step."""
        return True

    def deals_normal_damage(self) -> bool:
        """Return True if this creature deals damage in the normal combat step."""
        return True


@dataclass
class Trample(StaticKeyword):
    """
    Trample (CR 702.19)

    If a creature with trample would assign enough damage to its blockers
    to destroy them, it may assign the rest of its damage to the defending
    player or planeswalker.
    """
    keyword_name: str = field(default="Trample", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def calculate_excess_damage(
        self,
        total_damage: int,
        blockers: List['Permanent'],
        game: 'Game'
    ) -> int:
        """
        Calculate excess damage that can be assigned to defending player.

        Per CR 702.19b, lethal damage considers toughness minus damage already
        marked, plus any deathtouch considerations.

        Args:
            total_damage: Total damage the attacker can assign
            blockers: List of blocking creatures
            game: Current game state

        Returns:
            Amount of excess damage that can trample through
        """
        required_damage = 0
        attacker_has_deathtouch = "Deathtouch" in get_keyword_names(self.source)

        for blocker in blockers:
            toughness = getattr(blocker, 'toughness', 0)
            damage_marked = getattr(blocker, 'damage_marked', 0)
            remaining_toughness = toughness - damage_marked

            if attacker_has_deathtouch:
                # With deathtouch, only 1 damage is required per blocker
                required_damage += 1 if remaining_toughness > 0 else 0
            else:
                required_damage += max(0, remaining_toughness)

        return max(0, total_damage - required_damage)


@dataclass
class Deathtouch(StaticKeyword):
    """
    Deathtouch (CR 702.2)

    Any amount of damage a source with deathtouch deals to a creature
    is considered lethal damage.
    """
    keyword_name: str = field(default="Deathtouch", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def is_lethal_damage(self, damage_amount: int) -> bool:
        """Return True if the given damage amount is lethal (always True if > 0)."""
        return damage_amount > 0

    def lethal_damage_amount(self) -> int:
        """Return the amount of damage needed to be lethal."""
        return 1


@dataclass
class Lifelink(StaticKeyword):
    """
    Lifelink (CR 702.15)

    Damage dealt by a source with lifelink causes that source's controller
    to gain that much life (in addition to any other results that damage causes).
    """
    keyword_name: str = field(default="Lifelink", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def apply_lifelink(self, damage_dealt: int, game: 'Game') -> None:
        """
        Apply lifelink effect when damage is dealt.

        Args:
            damage_dealt: Amount of damage dealt
            game: Current game state
        """
        if damage_dealt > 0:
            controller = getattr(self.source, 'controller', None)
            if controller is not None:
                current_life = getattr(controller, 'life', 0)
                controller.life = current_life + damage_dealt


@dataclass
class Vigilance(StaticKeyword):
    """
    Vigilance (CR 702.20)

    Attacking doesn't cause creatures with vigilance to tap.
    """
    keyword_name: str = field(default="Vigilance", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def taps_when_attacking(self) -> bool:
        """Return whether this creature taps when attacking."""
        return False


@dataclass
class Haste(StaticKeyword):
    """
    Haste (CR 702.10)

    A creature with haste can attack and use activated abilities with tap
    or untap symbols even if it hasn't been continuously controlled since
    the beginning of its controller's most recent turn.
    """
    keyword_name: str = field(default="Haste", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def ignores_summoning_sickness(self) -> bool:
        """Return True if this creature ignores summoning sickness."""
        return True


@dataclass
class Defender(StaticKeyword):
    """
    Defender (CR 702.3)

    A creature with defender can't attack.
    """
    keyword_name: str = field(default="Defender", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def can_attack(self) -> bool:
        """Return whether this creature can attack."""
        return False


@dataclass
class Reach(StaticKeyword):
    """
    Reach (CR 702.17)

    A creature with reach can block creatures with flying.
    """
    keyword_name: str = field(default="Reach", init=False)
    category: KeywordCategory = field(default=KeywordCategory.COMBAT, init=False)

    def can_block_flying(self) -> bool:
        """Return whether this creature can block flying creatures."""
        return True


# =============================================================================
# PROTECTION KEYWORDS (CR 702.16, 702.11, 702.18, etc.)
# =============================================================================

@dataclass
class Hexproof(StaticKeyword):
    """
    Hexproof (CR 702.11)

    A permanent with hexproof can't be the target of spells or abilities
    your opponents control.
    """
    keyword_name: str = field(default="Hexproof", init=False)
    category: KeywordCategory = field(default=KeywordCategory.PROTECTION, init=False)
    # Optional: hexproof from specific qualities (e.g., "Hexproof from black")
    from_quality: Optional[str] = None

    def can_be_targeted_by(
        self,
        source: Any,
        controller: 'Player',
        game: 'Game'
    ) -> bool:
        """
        Check if this permanent can be targeted by the given source.

        Args:
            source: The spell or ability attempting to target
            controller: The controller of the source
            game: Current game state

        Returns:
            True if targeting is allowed, False otherwise
        """
        permanent_controller = getattr(self.source, 'controller', None)

        # Hexproof only prevents targeting by opponents
        if permanent_controller is not None and controller is permanent_controller:
            return True

        # Check for "hexproof from X" variant
        if self.from_quality is not None:
            source_colors = set(c.lower() for c in getattr(source, 'colors', set()))
            if self.from_quality.lower() not in source_colors:
                return True

        return False


@dataclass
class Shroud(StaticKeyword):
    """
    Shroud (CR 702.18)

    A permanent with shroud can't be the target of spells or abilities.
    """
    keyword_name: str = field(default="Shroud", init=False)
    category: KeywordCategory = field(default=KeywordCategory.PROTECTION, init=False)

    def can_be_targeted_by(
        self,
        source: Any,
        controller: 'Player',
        game: 'Game'
    ) -> bool:
        """
        Check if this permanent can be targeted.

        Shroud prevents all targeting, even by the permanent's controller.

        Returns:
            Always False - shroud prevents all targeting
        """
        return False


@dataclass
class Indestructible(StaticKeyword):
    """
    Indestructible (CR 702.12)

    A permanent with indestructible can't be destroyed. Such permanents
    aren't destroyed by lethal damage, and they ignore the state-based
    action that checks for lethal damage.
    """
    keyword_name: str = field(default="Indestructible", init=False)
    category: KeywordCategory = field(default=KeywordCategory.PROTECTION, init=False)

    def can_be_destroyed(self) -> bool:
        """Return whether this permanent can be destroyed."""
        return False

    def apply(self, game: 'Game') -> None:
        """Apply indestructible status to the permanent."""
        if hasattr(self.source, 'indestructible'):
            self.source.indestructible = True

    def remove(self, game: 'Game') -> None:
        """Remove indestructible status from the permanent."""
        if hasattr(self.source, 'indestructible'):
            self.source.indestructible = False


@dataclass
class Protection(StaticKeyword):
    """
    Protection (CR 702.16)

    Protection from [quality] provides the DEBT benefits:
    - Damage: All damage from sources with that quality is prevented
    - Enchant/Equip: Can't be enchanted/equipped by permanents with that quality
    - Block: Can't be blocked by creatures with that quality
    - Target: Can't be targeted by spells/abilities with that quality

    The quality can be a color, card type, or other characteristic.
    """
    keyword_name: str = field(default="Protection", init=False)
    category: KeywordCategory = field(default=KeywordCategory.PROTECTION, init=False)
    from_quality: str = ""  # e.g., "white", "creatures", "everything"

    def __post_init__(self):
        if self.from_quality:
            self.keyword_name = f"Protection from {self.from_quality}"

    def has_quality(self, source: Any) -> bool:
        """
        Check if a source has the quality this protection applies to.

        Args:
            source: The source to check

        Returns:
            True if the source has the protected quality
        """
        quality = self.from_quality.lower()

        # Protection from everything
        if quality == "everything":
            return True

        # Color check
        colors = {"white", "blue", "black", "red", "green"}
        if quality in colors:
            source_colors = set(c.lower() for c in getattr(source, 'colors', set()))
            return quality in source_colors

        # Card type check
        source_types = set(t.lower() for t in getattr(source, 'card_types', set()))
        source_subtypes = set(t.lower() for t in getattr(source, 'subtypes', set()))

        if quality in source_types or quality in source_subtypes:
            return True

        # "Colored" or "colorless"
        source_colors = getattr(source, 'colors', set())
        if quality == "colored":
            return len(source_colors) > 0
        if quality == "colorless":
            return len(source_colors) == 0

        return False

    def prevents_damage_from(self, source: Any) -> bool:
        """Check if damage from the source is prevented (D in DEBT)."""
        return self.has_quality(source)

    def prevents_enchant_equip_from(self, source: Any) -> bool:
        """Check if enchanting/equipping from the source is prevented (E in DEBT)."""
        return self.has_quality(source)

    def prevents_blocking_by(self, blocker: Any) -> bool:
        """Check if blocking by the creature is prevented (B in DEBT)."""
        return self.has_quality(blocker)

    def prevents_targeting_by(self, source: Any) -> bool:
        """Check if targeting by the source is prevented (T in DEBT)."""
        return self.has_quality(source)

    def can_be_blocked_by(self, blocker: 'Permanent') -> bool:
        """Check if this creature can be blocked by the given blocker."""
        return not self.prevents_blocking_by(blocker)


# =============================================================================
# OTHER STATIC KEYWORDS (CR 702.8, 702.107, 702.21)
# =============================================================================

@dataclass
class Flash(StaticKeyword):
    """
    Flash (CR 702.8)

    A spell with flash may be cast at any time the player could cast an instant.
    """
    keyword_name: str = field(default="Flash", init=False)
    category: KeywordCategory = field(default=KeywordCategory.CASTING, init=False)

    def can_cast_as_instant(self) -> bool:
        """Return whether this spell can be cast at instant speed."""
        return True


@dataclass
class Prowess(StaticKeyword):
    """
    Prowess (CR 702.107)

    Whenever you cast a noncreature spell, this creature gets +1/+1
    until end of turn.

    Note: This is technically a triggered ability, but is included here
    as it's commonly grouped with static keywords.
    """
    keyword_name: str = field(default="Prowess", init=False)
    category: KeywordCategory = field(default=KeywordCategory.TRIGGERED_STATIC, init=False)

    def triggers_on_noncreature_spell(self) -> bool:
        """Return True as prowess triggers on noncreature spells."""
        return True

    def get_bonus(self) -> tuple:
        """Return the power/toughness bonus granted."""
        return (1, 1)


@dataclass
class Ward(StaticKeyword):
    """
    Ward (CR 702.21)

    Whenever this permanent becomes the target of a spell or ability an
    opponent controls, counter that spell or ability unless its controller
    pays [cost].
    """
    keyword_name: str = field(default="Ward", init=False)
    category: KeywordCategory = field(default=KeywordCategory.PROTECTION, init=False)
    cost: Any = None  # Mana cost, life payment, etc.

    def __post_init__(self):
        if self.cost is not None:
            self.keyword_name = f"Ward {self.cost}"

    def get_ward_cost(self) -> Any:
        """Return the cost that must be paid to avoid being countered."""
        return self.cost

    def triggers_on_target(self, source: Any, controller: 'Player', game: 'Game') -> bool:
        """
        Check if ward triggers when targeted.

        Args:
            source: The spell or ability targeting this permanent
            controller: The controller of the targeting source
            game: Current game state

        Returns:
            True if ward should trigger (opponent is targeting)
        """
        permanent_controller = getattr(self.source, 'controller', None)
        return permanent_controller is not None and controller is not permanent_controller


# =============================================================================
# KEYWORD REGISTRY
# =============================================================================

class KeywordRegistry:
    """
    Registry for managing and querying static keyword abilities.

    This class provides a central point for registering keyword classes
    and checking what keywords permanents have.
    """

    def __init__(self):
        self.keywords: Dict[str, Type[StaticKeyword]] = {}
        self._register_default_keywords()

    def _register_default_keywords(self) -> None:
        """Register all built-in keyword classes."""
        # Evasion keywords
        self.register("Flying", Flying)
        self.register("Menace", Menace)
        self.register("Skulk", Skulk)
        self.register("Shadow", Shadow)
        self.register("Fear", Fear)
        self.register("Intimidate", Intimidate)
        self.register("Horsemanship", Horsemanship)

        # Combat keywords
        self.register("First Strike", FirstStrike)
        self.register("Double Strike", DoubleStrike)
        self.register("Trample", Trample)
        self.register("Deathtouch", Deathtouch)
        self.register("Lifelink", Lifelink)
        self.register("Vigilance", Vigilance)
        self.register("Haste", Haste)
        self.register("Defender", Defender)
        self.register("Reach", Reach)

        # Protection keywords
        self.register("Hexproof", Hexproof)
        self.register("Shroud", Shroud)
        self.register("Indestructible", Indestructible)
        self.register("Protection", Protection)

        # Other keywords
        self.register("Flash", Flash)
        self.register("Prowess", Prowess)
        self.register("Ward", Ward)

    def register(self, keyword_name: str, keyword_class: Type[StaticKeyword]) -> None:
        """
        Register a keyword class with the registry.

        Args:
            keyword_name: The name of the keyword (case-insensitive for lookup)
            keyword_class: The class implementing the keyword
        """
        self.keywords[keyword_name.lower()] = keyword_class

    def get_keyword_class(self, keyword_name: str) -> Optional[Type[StaticKeyword]]:
        """
        Get the class for a keyword by name.

        Args:
            keyword_name: The keyword name to look up

        Returns:
            The keyword class, or None if not found
        """
        # Direct lookup
        if keyword_name.lower() in self.keywords:
            return self.keywords[keyword_name.lower()]

        # Handle "Protection from X" variants
        if keyword_name.lower().startswith("protection from"):
            return self.keywords.get("protection")

        # Handle "Hexproof from X" variants
        if keyword_name.lower().startswith("hexproof from"):
            return self.keywords.get("hexproof")

        # Handle "Ward X" variants
        if keyword_name.lower().startswith("ward"):
            return self.keywords.get("ward")

        return None

    def has_keyword(self, permanent: 'Permanent', keyword_name: str) -> bool:
        """
        Check if a permanent has a specific keyword.

        Args:
            permanent: The permanent to check
            keyword_name: The keyword to look for

        Returns:
            True if the permanent has the keyword
        """
        keyword_names = get_keyword_names(permanent)
        keyword_lower = keyword_name.lower()

        for name in keyword_names:
            if name.lower() == keyword_lower:
                return True
            # Handle variants like "Protection from white" matching "Protection"
            if name.lower().startswith(keyword_lower):
                return True

        return False

    def get_keywords(self, permanent: 'Permanent') -> List[StaticKeyword]:
        """
        Get all keyword instances for a permanent.

        Args:
            permanent: The permanent to get keywords for

        Returns:
            List of StaticKeyword instances
        """
        keywords = []

        # Get keywords from the permanent's keyword list
        keyword_list = getattr(permanent, 'keywords', [])

        for kw in keyword_list:
            if isinstance(kw, StaticKeyword):
                keywords.append(kw)
            elif isinstance(kw, str):
                keyword_class = self.get_keyword_class(kw)
                if keyword_class is not None:
                    # Handle special cases
                    if kw.lower().startswith("protection from"):
                        quality = kw[16:]  # Remove "protection from "
                        keywords.append(keyword_class(source=permanent, from_quality=quality))
                    elif kw.lower().startswith("hexproof from"):
                        quality = kw[14:]  # Remove "hexproof from "
                        keywords.append(keyword_class(source=permanent, from_quality=quality))
                    elif kw.lower().startswith("ward"):
                        cost = kw[5:] if len(kw) > 4 else None
                        keywords.append(keyword_class(source=permanent, cost=cost))
                    else:
                        keywords.append(keyword_class(source=permanent))

        return keywords

    def check_evasion(
        self,
        attacker: 'Permanent',
        potential_blockers: List['Permanent']
    ) -> List['Permanent']:
        """
        Filter potential blockers based on attacker's evasion abilities.

        Args:
            attacker: The attacking creature
            potential_blockers: List of creatures that could potentially block

        Returns:
            List of creatures that can legally block the attacker
        """
        valid_blockers = []

        for blocker in potential_blockers:
            if self.can_be_blocked_by(attacker, blocker):
                valid_blockers.append(blocker)

        return valid_blockers

    def can_be_blocked_by(self, attacker: 'Permanent', blocker: 'Permanent') -> bool:
        """
        Determine if an attacker can be blocked by a specific blocker.

        This checks all relevant evasion and protection abilities.

        Args:
            attacker: The attacking creature
            blocker: The potential blocking creature

        Returns:
            True if the blocker can legally block the attacker
        """
        attacker_keywords = self.get_keywords(attacker)
        blocker_keywords = self.get_keywords(blocker)

        # Check attacker's evasion abilities
        for kw in attacker_keywords:
            if kw.category == KeywordCategory.EVASION:
                if hasattr(kw, 'can_be_blocked_by'):
                    if not kw.can_be_blocked_by(blocker):
                        return False

            # Check protection
            if isinstance(kw, Protection):
                if not kw.can_be_blocked_by(blocker):
                    return False

        # Check shadow specially - shadow creatures can only block shadow
        blocker_has_shadow = any(isinstance(kw, Shadow) for kw in blocker_keywords)
        attacker_has_shadow = any(isinstance(kw, Shadow) for kw in attacker_keywords)

        if blocker_has_shadow and not attacker_has_shadow:
            return False

        return True

    def get_minimum_blockers(self, attacker: 'Permanent') -> int:
        """
        Get the minimum number of creatures required to block an attacker.

        Args:
            attacker: The attacking creature

        Returns:
            Minimum number of blockers required (default 1)
        """
        keywords = self.get_keywords(attacker)

        for kw in keywords:
            if isinstance(kw, Menace):
                return kw.minimum_blockers_required()

        return 1


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_keyword_names(permanent: 'Permanent') -> Set[str]:
    """
    Get the set of keyword names a permanent has.

    Args:
        permanent: The permanent to check

    Returns:
        Set of keyword name strings
    """
    keywords = getattr(permanent, 'keywords', [])
    names = set()

    for kw in keywords:
        if isinstance(kw, StaticKeyword):
            names.add(kw.keyword_name)
        elif isinstance(kw, str):
            names.add(kw)

    return names


def parse_keywords(text: str) -> List[str]:
    """
    Parse keyword abilities from card text.

    This function extracts keyword abilities from rules text, handling
    comma-separated lists and multiline text.

    Args:
        text: The card text to parse

    Returns:
        List of keyword ability names found in the text
    """
    keywords = []

    # Known keywords with their patterns
    keyword_patterns = [
        # Simple keywords (single word)
        r'\b(Flying|Trample|Haste|Vigilance|Deathtouch|Lifelink|Menace|Reach)\b',
        r'\b(Defender|Flash|Prowess|Shroud|Indestructible|Skulk|Shadow|Fear)\b',
        r'\b(Intimidate|Horsemanship)\b',
        # Multi-word keywords
        r'\b(First [Ss]trike|Double [Ss]trike)\b',
        # Keywords with parameters
        r'\b(Protection from \w+)\b',
        r'\b(Hexproof from \w+)\b',
        r'\b(Hexproof)\b',
        r'\b(Ward \{[^}]+\})\b',
        r'\b(Ward \d+)\b',
    ]

    for pattern in keyword_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Normalize capitalization
            normalized = match.strip()
            if normalized.lower() == "first strike":
                normalized = "First Strike"
            elif normalized.lower() == "double strike":
                normalized = "Double Strike"
            else:
                normalized = normalized.title()

            if normalized not in keywords:
                keywords.append(normalized)

    return keywords


def apply_keyword_effects(game: 'Game', permanent: 'Permanent') -> None:
    """
    Apply all keyword effects from a permanent to the game state.

    This should be called when a permanent enters the battlefield or
    when its keywords change.

    Args:
        game: The current game state
        permanent: The permanent whose keywords should be applied
    """
    registry = KeywordRegistry()
    keywords = registry.get_keywords(permanent)

    for keyword in keywords:
        keyword.apply(game)


def remove_keyword_effects(game: 'Game', permanent: 'Permanent') -> None:
    """
    Remove all keyword effects from a permanent from the game state.

    This should be called when a permanent leaves the battlefield or
    when its keywords are removed.

    Args:
        game: The current game state
        permanent: The permanent whose keywords should be removed
    """
    registry = KeywordRegistry()
    keywords = registry.get_keywords(permanent)

    for keyword in keywords:
        keyword.remove(game)


def create_keyword(
    keyword_name: str,
    source: 'Permanent',
    **kwargs
) -> Optional[StaticKeyword]:
    """
    Factory function to create a keyword instance.

    Args:
        keyword_name: The name of the keyword to create
        source: The permanent that will have this keyword
        **kwargs: Additional arguments for keyword initialization

    Returns:
        A StaticKeyword instance, or None if the keyword is unknown
    """
    registry = KeywordRegistry()
    keyword_class = registry.get_keyword_class(keyword_name)

    if keyword_class is None:
        return None

    # Handle special cases
    if keyword_name.lower().startswith("protection from"):
        quality = keyword_name[16:]
        return keyword_class(source=source, from_quality=quality, **kwargs)
    elif keyword_name.lower().startswith("hexproof from"):
        quality = keyword_name[14:]
        return keyword_class(source=source, from_quality=quality, **kwargs)
    elif keyword_name.lower().startswith("ward"):
        cost = kwargs.pop('cost', keyword_name[5:] if len(keyword_name) > 4 else None)
        return keyword_class(source=source, cost=cost, **kwargs)

    return keyword_class(source=source, **kwargs)


def check_targeting_legality(
    target: 'Permanent',
    source: Any,
    controller: 'Player',
    game: 'Game'
) -> bool:
    """
    Check if a permanent can be legally targeted by a source.

    This checks hexproof, shroud, protection, and ward abilities.

    Args:
        target: The permanent being targeted
        source: The spell or ability doing the targeting
        controller: The controller of the source
        game: Current game state

    Returns:
        True if targeting is legal, False otherwise
    """
    registry = KeywordRegistry()
    keywords = registry.get_keywords(target)

    for keyword in keywords:
        # Shroud prevents all targeting
        if isinstance(keyword, Shroud):
            return False

        # Hexproof prevents opponent targeting
        if isinstance(keyword, Hexproof):
            if not keyword.can_be_targeted_by(source, controller, game):
                return False

        # Protection prevents targeting by sources with the quality
        if isinstance(keyword, Protection):
            if keyword.prevents_targeting_by(source):
                return False

    return True


def check_damage_prevention(
    target: 'Permanent',
    source: Any,
    damage_amount: int,
    game: 'Game'
) -> int:
    """
    Check if damage should be prevented by protection abilities.

    Args:
        target: The permanent receiving damage
        source: The source of the damage
        damage_amount: The amount of damage to be dealt
        game: Current game state

    Returns:
        The amount of damage after prevention effects (0 if prevented)
    """
    registry = KeywordRegistry()
    keywords = registry.get_keywords(target)

    for keyword in keywords:
        if isinstance(keyword, Protection):
            if keyword.prevents_damage_from(source):
                return 0

    return damage_amount


# Global registry instance for convenience
_global_registry: Optional[KeywordRegistry] = None


def get_registry() -> KeywordRegistry:
    """
    Get the global keyword registry instance.

    Returns:
        The global KeywordRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = KeywordRegistry()
    return _global_registry
