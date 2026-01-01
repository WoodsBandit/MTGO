"""
MTG Targeting System Implementation per Comprehensive Rules 115.

CR 115.1: Some spells and abilities require their controller to choose one or more
targets for them. The targets are object(s) and/or player(s) the spell or ability
will affect.

CR 115.2: Only permanents are legal targets on the battlefield unless a spell or
ability specifies otherwise.

CR 115.4: Some spells and abilities that refer to damage require a target. They
use the phrase "target creature or player," "target creature or planeswalker,"
"any target," or similar.

CR 115.7: A target must be legal both when the spell or ability is put on the
stack and when it resolves.

CR 115.9: Spells and abilities can affect objects and players they don't target.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TYPE_CHECKING,
    Union,
)

if TYPE_CHECKING:
    from .game_state import GameState
    from .permanent import Permanent
    from .player import Player
    from .spell import Spell
    from .ability import Ability


class TargetType(Enum):
    """
    Enumeration of valid target types in Magic: The Gathering.

    These represent the various targeting restrictions that spells and
    abilities can specify per CR 115.1a.
    """
    # Basic target types
    CREATURE = auto()
    PLAYER = auto()
    PERMANENT = auto()
    SPELL = auto()
    ABILITY = auto()
    PLANESWALKER = auto()
    ARTIFACT = auto()
    ENCHANTMENT = auto()
    LAND = auto()
    BATTLE = auto()

    # Combined target types (CR 115.4)
    CREATURE_OR_PLAYER = auto()
    CREATURE_OR_PLANESWALKER = auto()
    PERMANENT_OR_PLAYER = auto()
    PLANESWALKER_OR_PLAYER = auto()
    ANY = auto()  # "any target" - creature, player, or planeswalker

    # Controller-restricted target types
    CREATURE_YOU_CONTROL = auto()
    CREATURE_OPPONENT_CONTROLS = auto()
    PERMANENT_YOU_CONTROL = auto()
    PERMANENT_OPPONENT_CONTROLS = auto()
    CREATURE_YOU_DONT_CONTROL = auto()

    # Combat-specific target types
    ATTACKING_CREATURE = auto()
    BLOCKING_CREATURE = auto()
    ATTACKING_OR_BLOCKING_CREATURE = auto()
    UNBLOCKED_CREATURE = auto()

    # Zone-specific target types
    CARD_IN_GRAVEYARD = auto()
    CREATURE_CARD_IN_GRAVEYARD = auto()
    CARD_IN_HAND = auto()
    CARD_IN_LIBRARY = auto()

    # Special target types
    EQUIPPED_CREATURE = auto()
    ENCHANTED_CREATURE = auto()
    TAPPED_CREATURE = auto()
    UNTAPPED_CREATURE = auto()
    TOKEN = auto()
    NONTOKEN = auto()


class Color(Enum):
    """Magic colors for color-based targeting restrictions."""
    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"
    COLORLESS = "C"


@dataclass
class TargetRestriction:
    """
    Defines the requirements for a legal target.

    Per CR 115.1c, a spell or ability on the stack is an illegal target for
    itself. Per CR 115.1d, a target that requires a specific characteristic
    only matches objects with that characteristic.

    Attributes:
        target_type: The base type of legal targets.
        controller_restriction: "you", "opponent", or None for any controller.
        color_restriction: Set of colors the target must have (any of them).
        non_color_restriction: Set of colors the target must NOT have.
        type_restriction: Set of card types/subtypes required.
        type_exclusion: Set of types the target must NOT have.
        power_restriction: Tuple of (operator, value) for power comparison.
        toughness_restriction: Tuple of (operator, value) for toughness.
        cmc_restriction: Tuple of (operator, value) for mana value.
        keyword_restriction: Keyword ability the target must have.
        keyword_exclusion: Keyword ability the target must NOT have.
        name_restriction: Specific card name required.
        name_exclusion: Card names that are excluded.
        custom_filter: Additional callable filter (obj, source, game) -> bool.
        must_be_tapped: If True, target must be tapped.
        must_be_untapped: If True, target must be untapped.
        other_than_source: If True, cannot target the source itself.
        other_than_chosen: Set of objects that cannot be chosen (for multi-target).
    """
    target_type: TargetType
    controller_restriction: Optional[str] = None
    color_restriction: Optional[Set[Color]] = None
    non_color_restriction: Optional[Set[Color]] = None
    type_restriction: Optional[Set[str]] = None
    type_exclusion: Optional[Set[str]] = None
    power_restriction: Optional[Tuple[str, int]] = None
    toughness_restriction: Optional[Tuple[str, int]] = None
    cmc_restriction: Optional[Tuple[str, int]] = None
    keyword_restriction: Optional[str] = None
    keyword_exclusion: Optional[str] = None
    name_restriction: Optional[str] = None
    name_exclusion: Optional[Set[str]] = None
    custom_filter: Optional[Callable[[Any, Any, Any], bool]] = None
    must_be_tapped: bool = False
    must_be_untapped: bool = False
    other_than_source: bool = False
    other_than_chosen: Optional[Set[Any]] = None

    def matches_type(self, obj: Any, game: Any) -> bool:
        """Check if object matches the base target type requirement."""
        target_type = self.target_type

        # Handle player targets
        if target_type == TargetType.PLAYER:
            return _is_player(obj)

        # Handle "any target" (CR 115.4 - creature, planeswalker, or player)
        if target_type == TargetType.ANY:
            return (_is_player(obj) or
                    _is_creature(obj) or
                    _is_planeswalker(obj))

        # Handle combined types
        if target_type == TargetType.CREATURE_OR_PLAYER:
            return _is_player(obj) or _is_creature(obj)

        if target_type == TargetType.CREATURE_OR_PLANESWALKER:
            return _is_creature(obj) or _is_planeswalker(obj)

        if target_type == TargetType.PERMANENT_OR_PLAYER:
            return _is_player(obj) or _is_permanent(obj)

        if target_type == TargetType.PLANESWALKER_OR_PLAYER:
            return _is_player(obj) or _is_planeswalker(obj)

        # Handle spell/ability targets (on the stack)
        if target_type == TargetType.SPELL:
            return _is_spell(obj)

        if target_type == TargetType.ABILITY:
            return _is_ability(obj)

        # From here, we're dealing with permanents
        if not _is_permanent(obj):
            return False

        # Basic permanent types
        if target_type == TargetType.PERMANENT:
            return True

        if target_type == TargetType.CREATURE:
            return _is_creature(obj)

        if target_type == TargetType.PLANESWALKER:
            return _is_planeswalker(obj)

        if target_type == TargetType.ARTIFACT:
            return _is_artifact(obj)

        if target_type == TargetType.ENCHANTMENT:
            return _is_enchantment(obj)

        if target_type == TargetType.LAND:
            return _is_land(obj)

        if target_type == TargetType.BATTLE:
            return _is_battle(obj)

        # Controller-restricted types
        if target_type == TargetType.CREATURE_YOU_CONTROL:
            return _is_creature(obj)  # Controller check done separately

        if target_type == TargetType.CREATURE_OPPONENT_CONTROLS:
            return _is_creature(obj)

        if target_type == TargetType.CREATURE_YOU_DONT_CONTROL:
            return _is_creature(obj)

        if target_type == TargetType.PERMANENT_YOU_CONTROL:
            return True

        if target_type == TargetType.PERMANENT_OPPONENT_CONTROLS:
            return True

        # Combat-restricted types
        if target_type == TargetType.ATTACKING_CREATURE:
            return _is_creature(obj) and _is_attacking(obj, game)

        if target_type == TargetType.BLOCKING_CREATURE:
            return _is_creature(obj) and _is_blocking(obj, game)

        if target_type == TargetType.ATTACKING_OR_BLOCKING_CREATURE:
            return _is_creature(obj) and (_is_attacking(obj, game) or
                                           _is_blocking(obj, game))

        if target_type == TargetType.UNBLOCKED_CREATURE:
            return _is_creature(obj) and _is_unblocked(obj, game)

        # Tapped/untapped restrictions
        if target_type == TargetType.TAPPED_CREATURE:
            return _is_creature(obj) and _is_tapped(obj)

        if target_type == TargetType.UNTAPPED_CREATURE:
            return _is_creature(obj) and not _is_tapped(obj)

        # Token restrictions
        if target_type == TargetType.TOKEN:
            return _is_token(obj)

        if target_type == TargetType.NONTOKEN:
            return not _is_token(obj)

        # Zone-specific types (for cards not on battlefield)
        if target_type in (TargetType.CARD_IN_GRAVEYARD,
                          TargetType.CREATURE_CARD_IN_GRAVEYARD,
                          TargetType.CARD_IN_HAND,
                          TargetType.CARD_IN_LIBRARY):
            return _is_card(obj)

        return False

    def get_implied_controller_restriction(self) -> Optional[str]:
        """Get controller restriction implied by target type."""
        if self.target_type in (TargetType.CREATURE_YOU_CONTROL,
                                TargetType.PERMANENT_YOU_CONTROL):
            return "you"
        if self.target_type in (TargetType.CREATURE_OPPONENT_CONTROLS,
                                TargetType.PERMANENT_OPPONENT_CONTROLS,
                                TargetType.CREATURE_YOU_DONT_CONTROL):
            return "opponent"
        return self.controller_restriction


@dataclass
class Target:
    """
    Represents a single target for a spell or ability.

    Per CR 115.7, targets are chosen as the spell/ability is put on the stack,
    then verified again on resolution. If any target becomes illegal, the
    spell/ability can still resolve if at least one target remains legal
    (for spells with multiple targets).

    Attributes:
        restriction: The TargetRestriction defining legal targets.
        chosen: The object or player that was targeted.
        source: The spell/ability doing the targeting.
        is_legal: Whether the target is currently legal.
        was_legal_on_cast: Whether target was legal when chosen.
        timestamp: When the target was chosen (for ordering).
    """
    restriction: TargetRestriction
    chosen: Optional[Any] = None
    source: Optional[Any] = None
    is_legal: bool = True
    was_legal_on_cast: bool = True
    timestamp: int = 0

    def __post_init__(self):
        """Validate initial state."""
        if self.chosen is not None:
            self.was_legal_on_cast = self.is_legal

    def check_legal(self, game: Any) -> bool:
        """
        Verify the target is still legal per CR 115.7.

        A target becomes illegal if:
        - It's no longer in the appropriate zone
        - It no longer matches the targeting restriction
        - It has gained hexproof/shroud/protection that prevents targeting
        - The source that targeted it is no longer valid

        Args:
            game: The current game state.

        Returns:
            True if target is still legal, False otherwise.
        """
        if self.chosen is None:
            self.is_legal = False
            return False

        # Create a checker to verify legality
        checker = TargetChecker(game)
        self.is_legal = checker.is_legal_target(
            self.chosen,
            self.restriction,
            self.source
        )

        return self.is_legal

    def set_target(self, obj: Any, game: Any) -> bool:
        """
        Attempt to target an object.

        Per CR 115.1, targets are chosen as the spell or ability is put
        on the stack. This method verifies the target is legal before
        setting it.

        Args:
            obj: The object or player to target.
            game: The current game state.

        Returns:
            True if target was set successfully, False if illegal.
        """
        checker = TargetChecker(game)

        if not checker.is_legal_target(obj, self.restriction, self.source):
            return False

        self.chosen = obj
        self.is_legal = True
        self.was_legal_on_cast = True

        return True

    def clear(self) -> None:
        """Clear the chosen target."""
        self.chosen = None
        self.is_legal = False
        self.was_legal_on_cast = False

    def get_target(self) -> Optional[Any]:
        """Get the chosen target if legal, None otherwise."""
        return self.chosen if self.is_legal else None


@dataclass
class TargetGroup:
    """
    Represents a group of targets with the same restriction.

    Some spells target multiple objects with the same requirement
    (e.g., "up to two target creatures"). This class manages such groups.

    Attributes:
        restriction: The shared TargetRestriction.
        min_targets: Minimum number of targets required.
        max_targets: Maximum number of targets allowed.
        targets: List of individual Target objects.
        must_be_different: Whether each target must be a different object.
    """
    restriction: TargetRestriction
    min_targets: int = 1
    max_targets: int = 1
    targets: List[Target] = field(default_factory=list)
    must_be_different: bool = True
    source: Optional[Any] = None

    def add_target(self, obj: Any, game: Any) -> bool:
        """
        Add a target to this group.

        Args:
            obj: The object to target.
            game: The current game state.

        Returns:
            True if target was added, False if illegal or at capacity.
        """
        if len(self.targets) >= self.max_targets:
            return False

        # Check if already targeted (if must be different)
        if self.must_be_different:
            for existing in self.targets:
                if existing.chosen is obj:
                    return False

        # Create a new restriction that excludes already-chosen targets
        restriction = self.restriction
        if self.must_be_different and self.targets:
            chosen_set = {t.chosen for t in self.targets if t.chosen is not None}
            restriction = TargetRestriction(
                target_type=self.restriction.target_type,
                controller_restriction=self.restriction.controller_restriction,
                color_restriction=self.restriction.color_restriction,
                non_color_restriction=self.restriction.non_color_restriction,
                type_restriction=self.restriction.type_restriction,
                type_exclusion=self.restriction.type_exclusion,
                power_restriction=self.restriction.power_restriction,
                toughness_restriction=self.restriction.toughness_restriction,
                cmc_restriction=self.restriction.cmc_restriction,
                keyword_restriction=self.restriction.keyword_restriction,
                keyword_exclusion=self.restriction.keyword_exclusion,
                name_restriction=self.restriction.name_restriction,
                name_exclusion=self.restriction.name_exclusion,
                custom_filter=self.restriction.custom_filter,
                must_be_tapped=self.restriction.must_be_tapped,
                must_be_untapped=self.restriction.must_be_untapped,
                other_than_source=self.restriction.other_than_source,
                other_than_chosen=chosen_set,
            )

        target = Target(restriction=restriction, source=self.source)
        if target.set_target(obj, game):
            self.targets.append(target)
            return True

        return False

    def is_valid(self) -> bool:
        """Check if target group meets minimum requirements."""
        legal_count = sum(1 for t in self.targets if t.is_legal)
        return legal_count >= self.min_targets

    def check_all_legal(self, game: Any) -> int:
        """
        Check legality of all targets.

        Returns:
            Number of targets that are still legal.
        """
        legal_count = 0
        for target in self.targets:
            if target.check_legal(game):
                legal_count += 1
        return legal_count

    def get_legal_targets(self) -> List[Any]:
        """Get all targets that are currently legal."""
        return [t.chosen for t in self.targets if t.is_legal and t.chosen]


class TargetChecker:
    """
    Validates targeting legality per CR 115.

    This class handles all targeting validation including:
    - Base type matching
    - Controller restrictions
    - Characteristic restrictions (color, type, P/T, etc.)
    - Protection abilities (CR 702.16)
    - Hexproof (CR 702.11)
    - Shroud (CR 702.18)
    - Ward (CR 702.21)

    Attributes:
        game: The current game state.
    """

    def __init__(self, game: Any):
        """
        Initialize the target checker.

        Args:
            game: The current game state.
        """
        self.game = game

    def is_legal_target(
        self,
        obj: Any,
        restriction: TargetRestriction,
        source: Any
    ) -> bool:
        """
        Check if an object is a legal target per CR 115.

        Per CR 115.9, this checks:
        1. The object is in the appropriate zone
        2. The object matches all targeting restrictions
        3. No abilities prevent the targeting (hexproof, shroud, protection)

        Args:
            obj: The potential target.
            restriction: The targeting restriction to check against.
            source: The spell/ability doing the targeting.

        Returns:
            True if obj is a legal target, False otherwise.
        """
        if obj is None:
            return False

        # Check if object is in appropriate zone
        if not self._check_zone(obj, restriction):
            return False

        # Check base type match
        if not restriction.matches_type(obj, self.game):
            return False

        # Check "other than" restrictions
        if restriction.other_than_source and obj is source:
            return False

        if restriction.other_than_chosen and obj in restriction.other_than_chosen:
            return False

        # Check controller restriction
        if not self._check_controller(obj, restriction, source):
            return False

        # Check characteristic restrictions (only for permanents/cards)
        if not _is_player(obj):
            if not self._check_characteristics(obj, restriction):
                return False

        # Check targeting prevention abilities
        if not self._check_can_be_targeted(obj, source):
            return False

        # Check custom filter
        if restriction.custom_filter is not None:
            if not restriction.custom_filter(obj, source, self.game):
                return False

        return True

    def get_legal_targets(
        self,
        restriction: TargetRestriction,
        source: Any
    ) -> List[Any]:
        """
        Get all legal targets for a given restriction.

        Args:
            restriction: The targeting restriction.
            source: The spell/ability doing the targeting.

        Returns:
            List of all legal targets.
        """
        legal_targets = []

        # Check players if applicable
        if self._can_target_players(restriction.target_type):
            for player in self._get_players():
                if self.is_legal_target(player, restriction, source):
                    legal_targets.append(player)

        # Check permanents on battlefield
        if self._can_target_permanents(restriction.target_type):
            for permanent in self._get_permanents():
                if self.is_legal_target(permanent, restriction, source):
                    legal_targets.append(permanent)

        # Check spells on stack
        if restriction.target_type == TargetType.SPELL:
            for spell in self._get_spells_on_stack():
                if self.is_legal_target(spell, restriction, source):
                    legal_targets.append(spell)

        # Check abilities on stack
        if restriction.target_type == TargetType.ABILITY:
            for ability in self._get_abilities_on_stack():
                if self.is_legal_target(ability, restriction, source):
                    legal_targets.append(ability)

        # Check graveyard cards
        if restriction.target_type in (TargetType.CARD_IN_GRAVEYARD,
                                       TargetType.CREATURE_CARD_IN_GRAVEYARD):
            for card in self._get_graveyard_cards():
                if self.is_legal_target(card, restriction, source):
                    legal_targets.append(card)

        return legal_targets

    def check_hexproof(self, obj: Any, source: Any) -> bool:
        """
        Check if hexproof prevents targeting.

        Per CR 702.11, a permanent with hexproof can't be the target of
        spells or abilities controlled by opponents.

        Args:
            obj: The object being targeted.
            source: The spell/ability doing the targeting.

        Returns:
            True if hexproof BLOCKS the targeting, False otherwise.
        """
        if not _has_hexproof(obj):
            return False

        # Hexproof only blocks opponents
        source_controller = _get_controller(source)
        obj_controller = _get_controller(obj)

        if source_controller is None or obj_controller is None:
            return False

        # Check if source controller is an opponent
        return not _same_controller(source_controller, obj_controller)

    def check_shroud(self, obj: Any) -> bool:
        """
        Check if shroud prevents targeting.

        Per CR 702.18, a permanent with shroud can't be the target of
        spells or abilities.

        Args:
            obj: The object being targeted.

        Returns:
            True if shroud BLOCKS the targeting, False otherwise.
        """
        return _has_shroud(obj)

    def check_protection(self, obj: Any, source: Any) -> bool:
        """
        Check if protection prevents targeting.

        Per CR 702.16, protection from [quality] means the object can't be:
        - Damaged by sources with that quality
        - Enchanted/equipped/fortified by permanents with that quality
        - Blocked by creatures with that quality
        - Targeted by spells/abilities with that quality

        Args:
            obj: The object being targeted.
            source: The spell/ability doing the targeting.

        Returns:
            True if protection BLOCKS the targeting, False otherwise.
        """
        if not _has_protection(obj):
            return False

        protections = _get_protections(obj)

        for protection in protections:
            if self._protection_applies(protection, source):
                return True

        return False

    def check_ward(self, obj: Any, source: Any) -> Tuple[bool, Optional[Any]]:
        """
        Check if ward applies to targeting.

        Per CR 702.21, ward is a triggered ability that counters the
        spell/ability unless its controller pays the ward cost.
        Unlike hexproof/shroud/protection, ward doesn't make targeting
        illegal - it just has consequences.

        Args:
            obj: The object being targeted.
            source: The spell/ability doing the targeting.

        Returns:
            Tuple of (has_ward, ward_cost). If has_ward is True, the
            controller of source must pay ward_cost or have the
            spell/ability countered.
        """
        if not _has_ward(obj):
            return (False, None)

        # Ward only triggers for opponents' spells/abilities
        source_controller = _get_controller(source)
        obj_controller = _get_controller(obj)

        if source_controller is None or obj_controller is None:
            return (False, None)

        if _same_controller(source_controller, obj_controller):
            return (False, None)

        ward_cost = _get_ward_cost(obj)
        return (True, ward_cost)

    def _check_zone(self, obj: Any, restriction: TargetRestriction) -> bool:
        """Check if object is in the appropriate zone for targeting."""
        target_type = restriction.target_type

        # Players are always "in zone"
        if _is_player(obj):
            return True

        # Stack-based targets
        if target_type in (TargetType.SPELL, TargetType.ABILITY):
            return _is_on_stack(obj, self.game)

        # Graveyard targets
        if target_type in (TargetType.CARD_IN_GRAVEYARD,
                          TargetType.CREATURE_CARD_IN_GRAVEYARD):
            return _is_in_graveyard(obj, self.game)

        # Hand targets
        if target_type == TargetType.CARD_IN_HAND:
            return _is_in_hand(obj, self.game)

        # Library targets
        if target_type == TargetType.CARD_IN_LIBRARY:
            return _is_in_library(obj, self.game)

        # Default: must be on battlefield
        return _is_on_battlefield(obj, self.game)

    def _check_controller(
        self,
        obj: Any,
        restriction: TargetRestriction,
        source: Any
    ) -> bool:
        """Check controller restriction."""
        controller_req = restriction.get_implied_controller_restriction()

        if controller_req is None:
            return True

        source_controller = _get_controller(source)
        obj_controller = _get_controller(obj)

        if source_controller is None or obj_controller is None:
            return True

        if controller_req == "you":
            return _same_controller(source_controller, obj_controller)
        elif controller_req == "opponent":
            return not _same_controller(source_controller, obj_controller)

        return True

    def _check_characteristics(
        self,
        obj: Any,
        restriction: TargetRestriction
    ) -> bool:
        """Check all characteristic restrictions."""
        # Color restrictions
        if restriction.color_restriction:
            obj_colors = _get_colors(obj)
            if not obj_colors or not restriction.color_restriction & obj_colors:
                return False

        if restriction.non_color_restriction:
            obj_colors = _get_colors(obj)
            if obj_colors and restriction.non_color_restriction & obj_colors:
                return False

        # Type restrictions
        if restriction.type_restriction:
            obj_types = _get_types(obj)
            if not obj_types or not restriction.type_restriction & obj_types:
                return False

        if restriction.type_exclusion:
            obj_types = _get_types(obj)
            if obj_types and restriction.type_exclusion & obj_types:
                return False

        # Power restriction
        if restriction.power_restriction:
            op, value = restriction.power_restriction
            power = _get_power(obj)
            if power is None or not self._compare(power, op, value):
                return False

        # Toughness restriction
        if restriction.toughness_restriction:
            op, value = restriction.toughness_restriction
            toughness = _get_toughness(obj)
            if toughness is None or not self._compare(toughness, op, value):
                return False

        # Mana value restriction
        if restriction.cmc_restriction:
            op, value = restriction.cmc_restriction
            cmc = _get_mana_value(obj)
            if cmc is None or not self._compare(cmc, op, value):
                return False

        # Keyword restrictions
        if restriction.keyword_restriction:
            if not _has_keyword(obj, restriction.keyword_restriction):
                return False

        if restriction.keyword_exclusion:
            if _has_keyword(obj, restriction.keyword_exclusion):
                return False

        # Name restrictions
        if restriction.name_restriction:
            if _get_name(obj) != restriction.name_restriction:
                return False

        if restriction.name_exclusion:
            if _get_name(obj) in restriction.name_exclusion:
                return False

        # Tapped/untapped restrictions
        if restriction.must_be_tapped:
            if not _is_tapped(obj):
                return False

        if restriction.must_be_untapped:
            if _is_tapped(obj):
                return False

        return True

    def _check_can_be_targeted(self, obj: Any, source: Any) -> bool:
        """Check if targeting prevention abilities block this targeting."""
        # Check shroud (blocks all targeting)
        if self.check_shroud(obj):
            return False

        # Check hexproof (blocks opponents)
        if self.check_hexproof(obj, source):
            return False

        # Check protection (blocks sources with quality)
        if self.check_protection(obj, source):
            return False

        # Note: Ward doesn't prevent targeting, just has a consequence
        # It's checked separately when the spell/ability resolves

        return True

    def _compare(self, actual: int, operator: str, expected: int) -> bool:
        """Perform a comparison operation."""
        if operator == ">":
            return actual > expected
        elif operator == ">=":
            return actual >= expected
        elif operator == "<":
            return actual < expected
        elif operator == "<=":
            return actual <= expected
        elif operator == "==" or operator == "=":
            return actual == expected
        elif operator == "!=":
            return actual != expected
        return False

    def _can_target_players(self, target_type: TargetType) -> bool:
        """Check if target type can include players."""
        return target_type in (
            TargetType.PLAYER,
            TargetType.CREATURE_OR_PLAYER,
            TargetType.PERMANENT_OR_PLAYER,
            TargetType.PLANESWALKER_OR_PLAYER,
            TargetType.ANY,
        )

    def _can_target_permanents(self, target_type: TargetType) -> bool:
        """Check if target type can include permanents."""
        return target_type not in (
            TargetType.PLAYER,
            TargetType.SPELL,
            TargetType.ABILITY,
            TargetType.CARD_IN_GRAVEYARD,
            TargetType.CREATURE_CARD_IN_GRAVEYARD,
            TargetType.CARD_IN_HAND,
            TargetType.CARD_IN_LIBRARY,
        )

    def _protection_applies(self, protection: str, source: Any) -> bool:
        """
        Check if a specific protection applies to a source.

        Protections can be from:
        - Colors: "white", "blue", "black", "red", "green"
        - Types: "artifacts", "creatures", etc.
        - Qualities: "everything", "colored spells", etc.
        """
        protection_lower = protection.lower()

        # Color protection
        color_map = {
            "white": Color.WHITE,
            "blue": Color.BLUE,
            "black": Color.BLACK,
            "red": Color.RED,
            "green": Color.GREEN,
        }

        if protection_lower in color_map:
            source_colors = _get_colors(source)
            if source_colors and color_map[protection_lower] in source_colors:
                return True

        # Protection from everything
        if protection_lower == "everything":
            return True

        # Type protection
        source_types = _get_types(source)
        if source_types:
            type_variants = {protection_lower, protection_lower.rstrip('s')}
            if source_types & type_variants:
                return True

        # CMC-based protection (e.g., "mana value 3 or less")
        if "mana value" in protection_lower:
            # Parse protection like "mana value 3 or less"
            import re
            match = re.search(r'mana value (\d+) or (less|greater)', protection_lower)
            if match:
                value = int(match.group(1))
                direction = match.group(2)
                source_cmc = _get_mana_value(source)
                if source_cmc is not None:
                    if direction == "less" and source_cmc <= value:
                        return True
                    elif direction == "greater" and source_cmc >= value:
                        return True

        return False

    def _get_players(self) -> List[Any]:
        """Get all players in the game."""
        if hasattr(self.game, 'players'):
            return list(self.game.players)
        return []

    def _get_permanents(self) -> List[Any]:
        """Get all permanents on the battlefield."""
        if hasattr(self.game, 'battlefield'):
            return list(self.game.battlefield)
        if hasattr(self.game, 'get_permanents'):
            return list(self.game.get_permanents())
        return []

    def _get_spells_on_stack(self) -> List[Any]:
        """Get all spells on the stack."""
        if hasattr(self.game, 'stack'):
            return [item for item in self.game.stack if _is_spell(item)]
        return []

    def _get_abilities_on_stack(self) -> List[Any]:
        """Get all abilities on the stack."""
        if hasattr(self.game, 'stack'):
            return [item for item in self.game.stack if _is_ability(item)]
        return []

    def _get_graveyard_cards(self) -> List[Any]:
        """Get all cards in all graveyards."""
        cards = []
        if hasattr(self.game, 'players'):
            for player in self.game.players:
                if hasattr(player, 'graveyard'):
                    cards.extend(player.graveyard)
        return cards


# =============================================================================
# Helper functions for type checking and attribute access
# =============================================================================

def _is_player(obj: Any) -> bool:
    """Check if object is a player."""
    if obj is None:
        return False
    return (hasattr(obj, 'is_player') and obj.is_player or
            type(obj).__name__ == 'Player' or
            hasattr(obj, 'life_total'))


def _is_permanent(obj: Any) -> bool:
    """Check if object is a permanent."""
    if obj is None:
        return False
    return (hasattr(obj, 'is_permanent') and obj.is_permanent or
            type(obj).__name__ == 'Permanent' or
            hasattr(obj, 'zone') and getattr(obj, 'zone', None) == 'battlefield')


def _is_creature(obj: Any) -> bool:
    """Check if object is a creature."""
    if not _is_permanent(obj):
        return False
    if hasattr(obj, 'is_creature'):
        return obj.is_creature
    if hasattr(obj, 'card_types'):
        return 'creature' in {t.lower() for t in obj.card_types}
    if hasattr(obj, 'types'):
        return 'creature' in {t.lower() for t in obj.types}
    return False


def _is_planeswalker(obj: Any) -> bool:
    """Check if object is a planeswalker."""
    if not _is_permanent(obj):
        return False
    if hasattr(obj, 'is_planeswalker'):
        return obj.is_planeswalker
    if hasattr(obj, 'card_types'):
        return 'planeswalker' in {t.lower() for t in obj.card_types}
    if hasattr(obj, 'types'):
        return 'planeswalker' in {t.lower() for t in obj.types}
    return False


def _is_artifact(obj: Any) -> bool:
    """Check if object is an artifact."""
    if not _is_permanent(obj):
        return False
    if hasattr(obj, 'is_artifact'):
        return obj.is_artifact
    if hasattr(obj, 'card_types'):
        return 'artifact' in {t.lower() for t in obj.card_types}
    if hasattr(obj, 'types'):
        return 'artifact' in {t.lower() for t in obj.types}
    return False


def _is_enchantment(obj: Any) -> bool:
    """Check if object is an enchantment."""
    if not _is_permanent(obj):
        return False
    if hasattr(obj, 'is_enchantment'):
        return obj.is_enchantment
    if hasattr(obj, 'card_types'):
        return 'enchantment' in {t.lower() for t in obj.card_types}
    if hasattr(obj, 'types'):
        return 'enchantment' in {t.lower() for t in obj.types}
    return False


def _is_land(obj: Any) -> bool:
    """Check if object is a land."""
    if not _is_permanent(obj):
        return False
    if hasattr(obj, 'is_land'):
        return obj.is_land
    if hasattr(obj, 'card_types'):
        return 'land' in {t.lower() for t in obj.card_types}
    if hasattr(obj, 'types'):
        return 'land' in {t.lower() for t in obj.types}
    return False


def _is_battle(obj: Any) -> bool:
    """Check if object is a battle."""
    if not _is_permanent(obj):
        return False
    if hasattr(obj, 'is_battle'):
        return obj.is_battle
    if hasattr(obj, 'card_types'):
        return 'battle' in {t.lower() for t in obj.card_types}
    if hasattr(obj, 'types'):
        return 'battle' in {t.lower() for t in obj.types}
    return False


def _is_spell(obj: Any) -> bool:
    """Check if object is a spell on the stack."""
    if obj is None:
        return False
    return (hasattr(obj, 'is_spell') and obj.is_spell or
            type(obj).__name__ == 'Spell')


def _is_ability(obj: Any) -> bool:
    """Check if object is an ability on the stack."""
    if obj is None:
        return False
    return (hasattr(obj, 'is_ability') and obj.is_ability or
            type(obj).__name__ in ('Ability', 'ActivatedAbility',
                                   'TriggeredAbility', 'StackedAbility'))


def _is_card(obj: Any) -> bool:
    """Check if object is a card (for zone-specific targeting)."""
    if obj is None:
        return False
    return (hasattr(obj, 'is_card') and obj.is_card or
            type(obj).__name__ == 'Card' or
            hasattr(obj, 'card_types'))


def _is_token(obj: Any) -> bool:
    """Check if object is a token."""
    if obj is None:
        return False
    return hasattr(obj, 'is_token') and obj.is_token


def _is_tapped(obj: Any) -> bool:
    """Check if permanent is tapped."""
    if obj is None:
        return False
    return hasattr(obj, 'is_tapped') and obj.is_tapped


def _is_attacking(obj: Any, game: Any) -> bool:
    """Check if creature is attacking."""
    if hasattr(obj, 'is_attacking'):
        return obj.is_attacking
    if hasattr(game, 'combat') and game.combat:
        if hasattr(game.combat, 'attackers'):
            return obj in game.combat.attackers
    return False


def _is_blocking(obj: Any, game: Any) -> bool:
    """Check if creature is blocking."""
    if hasattr(obj, 'is_blocking'):
        return obj.is_blocking
    if hasattr(game, 'combat') and game.combat:
        if hasattr(game.combat, 'blockers'):
            return obj in game.combat.blockers
    return False


def _is_unblocked(obj: Any, game: Any) -> bool:
    """Check if attacking creature is unblocked."""
    if not _is_attacking(obj, game):
        return False
    if hasattr(obj, 'is_blocked'):
        return not obj.is_blocked
    if hasattr(game, 'combat') and game.combat:
        if hasattr(game.combat, 'unblocked_attackers'):
            return obj in game.combat.unblocked_attackers
    return False


def _is_on_battlefield(obj: Any, game: Any) -> bool:
    """Check if object is on the battlefield."""
    if hasattr(obj, 'zone'):
        return obj.zone == 'battlefield'
    if hasattr(game, 'battlefield'):
        return obj in game.battlefield
    return _is_permanent(obj)


def _is_on_stack(obj: Any, game: Any) -> bool:
    """Check if object is on the stack."""
    if hasattr(obj, 'zone'):
        return obj.zone == 'stack'
    if hasattr(game, 'stack'):
        return obj in game.stack
    return False


def _is_in_graveyard(obj: Any, game: Any) -> bool:
    """Check if object is in a graveyard."""
    if hasattr(obj, 'zone'):
        return obj.zone == 'graveyard'
    if hasattr(game, 'players'):
        for player in game.players:
            if hasattr(player, 'graveyard') and obj in player.graveyard:
                return True
    return False


def _is_in_hand(obj: Any, game: Any) -> bool:
    """Check if object is in a hand."""
    if hasattr(obj, 'zone'):
        return obj.zone == 'hand'
    if hasattr(game, 'players'):
        for player in game.players:
            if hasattr(player, 'hand') and obj in player.hand:
                return True
    return False


def _is_in_library(obj: Any, game: Any) -> bool:
    """Check if object is in a library."""
    if hasattr(obj, 'zone'):
        return obj.zone == 'library'
    return False


def _has_hexproof(obj: Any) -> bool:
    """Check if object has hexproof."""
    if hasattr(obj, 'has_hexproof'):
        return obj.has_hexproof
    if hasattr(obj, 'keywords'):
        return 'hexproof' in {k.lower() for k in obj.keywords}
    if hasattr(obj, 'abilities'):
        return any('hexproof' in str(a).lower() for a in obj.abilities)
    return False


def _has_shroud(obj: Any) -> bool:
    """Check if object has shroud."""
    if hasattr(obj, 'has_shroud'):
        return obj.has_shroud
    if hasattr(obj, 'keywords'):
        return 'shroud' in {k.lower() for k in obj.keywords}
    if hasattr(obj, 'abilities'):
        return any('shroud' in str(a).lower() for a in obj.abilities)
    return False


def _has_protection(obj: Any) -> bool:
    """Check if object has any protection ability."""
    if hasattr(obj, 'has_protection'):
        return obj.has_protection
    if hasattr(obj, 'protections'):
        return len(obj.protections) > 0
    if hasattr(obj, 'keywords'):
        return any(k.lower().startswith('protection') for k in obj.keywords)
    if hasattr(obj, 'abilities'):
        return any('protection' in str(a).lower() for a in obj.abilities)
    return False


def _get_protections(obj: Any) -> List[str]:
    """Get list of protection qualities."""
    if hasattr(obj, 'protections'):
        return list(obj.protections)
    if hasattr(obj, 'keywords'):
        protections = []
        for keyword in obj.keywords:
            if keyword.lower().startswith('protection from '):
                protections.append(keyword[16:])  # Remove "protection from "
        return protections
    return []


def _has_ward(obj: Any) -> bool:
    """Check if object has ward."""
    if hasattr(obj, 'has_ward'):
        return obj.has_ward
    if hasattr(obj, 'keywords'):
        return any(k.lower().startswith('ward') for k in obj.keywords)
    if hasattr(obj, 'abilities'):
        return any('ward' in str(a).lower() for a in obj.abilities)
    return False


def _get_ward_cost(obj: Any) -> Optional[Any]:
    """Get the ward cost for an object."""
    if hasattr(obj, 'ward_cost'):
        return obj.ward_cost
    # Try to parse from keywords
    if hasattr(obj, 'keywords'):
        for keyword in obj.keywords:
            if keyword.lower().startswith('ward '):
                # Return the cost portion (e.g., "{2}" from "Ward {2}")
                return keyword[5:]
    return None


def _has_keyword(obj: Any, keyword: str) -> bool:
    """Check if object has a specific keyword ability."""
    keyword_lower = keyword.lower()
    if hasattr(obj, 'keywords'):
        return keyword_lower in {k.lower() for k in obj.keywords}
    if hasattr(obj, 'abilities'):
        return any(keyword_lower in str(a).lower() for a in obj.abilities)
    # Check for specific keyword attributes
    attr_name = f'has_{keyword_lower}'
    if hasattr(obj, attr_name):
        return getattr(obj, attr_name)
    return False


def _get_controller(obj: Any) -> Optional[Any]:
    """Get the controller of an object."""
    if hasattr(obj, 'controller'):
        return obj.controller
    if hasattr(obj, 'owner'):
        return obj.owner
    # For players, they control themselves
    if _is_player(obj):
        return obj
    return None


def _same_controller(a: Any, b: Any) -> bool:
    """Check if two objects have the same controller."""
    if a is None or b is None:
        return False
    return a is b or (hasattr(a, 'id') and hasattr(b, 'id') and a.id == b.id)


def _get_colors(obj: Any) -> Optional[Set[Color]]:
    """Get the colors of an object."""
    if hasattr(obj, 'colors'):
        colors = obj.colors
        if isinstance(colors, set):
            return colors
        # Convert from strings if needed
        color_map = {
            'W': Color.WHITE, 'white': Color.WHITE,
            'U': Color.BLUE, 'blue': Color.BLUE,
            'B': Color.BLACK, 'black': Color.BLACK,
            'R': Color.RED, 'red': Color.RED,
            'G': Color.GREEN, 'green': Color.GREEN,
            'C': Color.COLORLESS, 'colorless': Color.COLORLESS,
        }
        result = set()
        for c in colors:
            if isinstance(c, Color):
                result.add(c)
            elif c in color_map:
                result.add(color_map[c])
        return result if result else None
    return None


def _get_types(obj: Any) -> Optional[Set[str]]:
    """Get all types of an object (card types, subtypes, supertypes)."""
    types = set()

    if hasattr(obj, 'card_types'):
        types.update(t.lower() for t in obj.card_types)
    if hasattr(obj, 'types'):
        types.update(t.lower() for t in obj.types)
    if hasattr(obj, 'subtypes'):
        types.update(t.lower() for t in obj.subtypes)
    if hasattr(obj, 'supertypes'):
        types.update(t.lower() for t in obj.supertypes)

    return types if types else None


def _get_power(obj: Any) -> Optional[int]:
    """Get the power of a creature."""
    if hasattr(obj, 'power'):
        power = obj.power
        if callable(power):
            power = power()
        return int(power) if power is not None else None
    return None


def _get_toughness(obj: Any) -> Optional[int]:
    """Get the toughness of a creature."""
    if hasattr(obj, 'toughness'):
        toughness = obj.toughness
        if callable(toughness):
            toughness = toughness()
        return int(toughness) if toughness is not None else None
    return None


def _get_mana_value(obj: Any) -> Optional[int]:
    """Get the mana value (converted mana cost) of an object."""
    if hasattr(obj, 'mana_value'):
        return obj.mana_value
    if hasattr(obj, 'cmc'):
        return obj.cmc
    if hasattr(obj, 'converted_mana_cost'):
        return obj.converted_mana_cost
    return None


def _get_name(obj: Any) -> Optional[str]:
    """Get the name of an object."""
    if hasattr(obj, 'name'):
        return obj.name
    return None


# =============================================================================
# Convenience factory functions
# =============================================================================

def create_creature_target(
    controller: Optional[str] = None,
    **kwargs
) -> TargetRestriction:
    """Create a targeting restriction for creatures."""
    return TargetRestriction(
        target_type=TargetType.CREATURE,
        controller_restriction=controller,
        **kwargs
    )


def create_player_target() -> TargetRestriction:
    """Create a targeting restriction for players."""
    return TargetRestriction(target_type=TargetType.PLAYER)


def create_any_target() -> TargetRestriction:
    """Create a targeting restriction for 'any target' (creature/player/planeswalker)."""
    return TargetRestriction(target_type=TargetType.ANY)


def create_permanent_target(
    type_restriction: Optional[Set[str]] = None,
    controller: Optional[str] = None,
    **kwargs
) -> TargetRestriction:
    """Create a targeting restriction for permanents."""
    return TargetRestriction(
        target_type=TargetType.PERMANENT,
        type_restriction=type_restriction,
        controller_restriction=controller,
        **kwargs
    )


def create_spell_target(
    type_restriction: Optional[Set[str]] = None,
    **kwargs
) -> TargetRestriction:
    """Create a targeting restriction for spells on the stack."""
    return TargetRestriction(
        target_type=TargetType.SPELL,
        type_restriction=type_restriction,
        **kwargs
    )
