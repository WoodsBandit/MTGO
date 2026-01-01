"""MTG Engine V3 - Activated Abilities (CR 602)

This module implements the complete activated ability system per the MTG
Comprehensive Rules section 602. Key concepts:

- CR 602.1: Activated abilities are written as "cost: effect"
- CR 602.2: Activating abilities follows a specific procedure
- CR 602.3: Timing restrictions (sorcery speed, once per turn, etc.)
- CR 602.5: Activated abilities are independent of their source
- CR 605: Mana abilities don't use the stack
- CR 606: Loyalty abilities have special timing rules
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Callable, Any, Tuple, Union, TYPE_CHECKING
from enum import Enum, auto

if TYPE_CHECKING:
    from ..game import Game
    from ..objects import GameObject, Permanent, StackedAbility, Target, ManaCost
    from ..player import Player

# Import from parent modules
from ..types import (
    Color, ObjectId, PlayerId, AbilityType, TargetType, TargetRestriction,
    PhaseType, StepType, CardType
)


# =============================================================================
# Activation Restriction Enum
# =============================================================================

class ActivationRestriction(Enum):
    """Restrictions on when an activated ability can be activated (CR 602.3)"""
    NONE = auto()                    # No restrictions, instant speed
    SORCERY_SPEED = auto()           # Only main phase, stack empty, your turn
    ONCE_PER_TURN = auto()           # Can only activate once per turn
    ONLY_DURING_COMBAT = auto()      # Only during combat phase
    ONLY_DURING_YOUR_TURN = auto()   # Only during your turn
    TAP_ABILITY = auto()             # Requires tap, creature must be untapped and not summoning sick


# =============================================================================
# Cost Dataclass
# =============================================================================

@dataclass
class Cost:
    """Represents the cost of an activated ability (CR 602.1a)

    Costs are written before the colon in ability text.
    Multiple costs are separated and all must be paid.
    """
    # Mana cost component
    mana_cost: Optional['ManaCost'] = None

    # Tap/untap costs
    tap: bool = False              # {T}
    untap: bool = False            # {Q}

    # Life payment
    life: int = 0

    # Resource costs
    sacrifice_self: bool = False
    sacrifice_type: Optional[str] = None      # e.g., "creature", "artifact"
    sacrifice_count: int = 0
    discard_count: int = 0
    discard_type: Optional[str] = None        # e.g., "card", "creature card"
    exile_from_graveyard: int = 0
    exile_from_graveyard_type: Optional[str] = None

    # Counter manipulation
    remove_counters_type: Optional[str] = None
    remove_counters_count: int = 0
    add_counters_type: Optional[str] = None
    add_counters_count: int = 0

    # Loyalty cost (for planeswalkers)
    loyalty_cost: int = 0  # Positive = add, negative = remove

    # Crew cost (tap creatures with total power >= this)
    crew_power: int = 0

    # Generic additional costs
    additional_costs: List[str] = field(default_factory=list)

    def can_pay(self, game: 'Game', player: 'Player', source: 'Permanent') -> bool:
        """Check if all components of this cost can be paid"""
        # Check mana
        if self.mana_cost:
            if not player.mana_pool.can_pay(self.mana_cost):
                return False

        # Check tap cost
        if self.tap:
            if source.is_tapped:
                return False
            # Check summoning sickness for creatures
            if source.characteristics.is_creature():
                if source.has_summoning_sickness():
                    return False

        # Check untap cost
        if self.untap:
            if not source.is_tapped:
                return False

        # Check life
        if self.life > 0:
            if player.life < self.life:
                return False

        # Check loyalty
        if self.loyalty_cost < 0:
            if source.current_loyalty() < abs(self.loyalty_cost):
                return False

        # Check sacrifice self
        if self.sacrifice_self:
            # Source must still be on battlefield
            pass  # Implicitly checked by source existing

        # Additional checks for sacrifice/discard/etc would go here
        # These require game state examination

        return True

    def pay(self, game: 'Game', player: 'Player', source: 'Permanent') -> bool:
        """Pay all components of this cost. Returns True if successful."""
        # Pay mana
        if self.mana_cost:
            if not player.mana_pool.pay(self.mana_cost):
                return False

        # Pay tap cost
        if self.tap:
            source.tap()

        # Pay untap cost
        if self.untap:
            source.untap()

        # Pay life
        if self.life > 0:
            player.lose_life(self.life)

        # Pay loyalty cost
        if self.loyalty_cost != 0:
            from ..objects import CounterType
            if self.loyalty_cost > 0:
                source.add_counter(CounterType.LOYALTY, self.loyalty_cost)
            else:
                source.remove_counter(CounterType.LOYALTY, abs(self.loyalty_cost))

        # Sacrifice self would be handled by the game engine after cost payment

        return True

    @classmethod
    def tap_only(cls) -> 'Cost':
        """Create a tap-only cost ({T})"""
        return cls(tap=True)

    @classmethod
    def mana_and_tap(cls, mana_cost: 'ManaCost') -> 'Cost':
        """Create a mana + tap cost"""
        return cls(mana_cost=mana_cost, tap=True)

    @classmethod
    def from_string(cls, cost_string: str) -> 'Cost':
        """Parse a cost string like '{2}{R}, {T}: ...'"""
        from ..objects import ManaCost

        cost = cls()
        parts = cost_string.replace(':', '').split(',')

        for part in parts:
            part = part.strip()
            if part == '{T}':
                cost.tap = True
            elif part == '{Q}':
                cost.untap = True
            elif part.startswith('Pay ') and 'life' in part:
                # "Pay 2 life"
                import re
                match = re.search(r'Pay (\d+) life', part)
                if match:
                    cost.life = int(match.group(1))
            elif part.startswith('{'):
                # Mana cost
                cost.mana_cost = ManaCost.parse(part)

        return cost


# =============================================================================
# Target Restriction for Abilities
# =============================================================================

@dataclass
class AbilityTargetRestriction:
    """Defines targeting requirements for an activated ability"""
    target_type: TargetType
    restrictions: List[str] = field(default_factory=list)
    controller_restriction: Optional[str] = None  # "you", "opponent"
    count: int = 1
    up_to: bool = False  # "up to X targets"

    def get_legal_targets(self, game: 'Game', controller_id: PlayerId) -> List[Any]:
        """Get all legal targets for this restriction"""
        targets = []

        # Get candidates based on target type
        if self.target_type in (TargetType.CREATURE, TargetType.PERMANENT,
                                TargetType.ARTIFACT, TargetType.ENCHANTMENT,
                                TargetType.PLANESWALKER, TargetType.LAND):
            candidates = game.zones.battlefield.get_all()
        elif self.target_type == TargetType.PLAYER:
            candidates = list(game.players.values())
        elif self.target_type == TargetType.CREATURE_OR_PLAYER:
            candidates = game.zones.battlefield.get_all() + list(game.players.values())
        else:
            candidates = []

        # Filter by restrictions
        for candidate in candidates:
            if self._matches_restrictions(candidate, game, controller_id):
                targets.append(candidate)

        return targets

    def _matches_restrictions(self, candidate: Any, game: 'Game',
                              controller_id: PlayerId) -> bool:
        """Check if a candidate matches all restrictions"""
        from ..objects import Permanent
        from ..player import Player

        # Controller restriction
        if self.controller_restriction == "you":
            if isinstance(candidate, Permanent):
                if candidate.controller_id != controller_id:
                    return False
            elif isinstance(candidate, Player):
                if candidate.player_id != controller_id:
                    return False
        elif self.controller_restriction == "opponent":
            if isinstance(candidate, Permanent):
                if candidate.controller_id == controller_id:
                    return False
            elif isinstance(candidate, Player):
                if candidate.player_id == controller_id:
                    return False

        # Type restrictions for permanents
        if isinstance(candidate, Permanent):
            if self.target_type == TargetType.CREATURE:
                if not candidate.characteristics.is_creature():
                    return False
            elif self.target_type == TargetType.ARTIFACT:
                if not candidate.characteristics.is_artifact():
                    return False
            elif self.target_type == TargetType.ENCHANTMENT:
                if not candidate.characteristics.is_enchantment():
                    return False
            elif self.target_type == TargetType.PLANESWALKER:
                if not candidate.characteristics.is_planeswalker():
                    return False
            elif self.target_type == TargetType.LAND:
                if not candidate.characteristics.is_land():
                    return False

        return True


# =============================================================================
# Activated Ability Base Class
# =============================================================================

@dataclass
class ActivatedAbility:
    """An activated ability as defined in CR 602

    Activated abilities have costs and effects, written as "[Cost]: [Effect]"
    They are put on the stack when activated and resolve like other objects.
    """
    # Identity
    ability_id: int = 0
    source: Any = None              # The GameObject this ability is on
    controller: Any = None          # The Player who controls this ability

    # Cost and effect
    cost: Cost = field(default_factory=Cost)
    effect: str = ""                # Text description of the effect
    effect_func: Optional[Callable] = None  # Function to execute on resolution

    # Timing restrictions
    timing: ActivationRestriction = ActivationRestriction.NONE

    # Targeting
    targets_required: List[AbilityTargetRestriction] = field(default_factory=list)

    # Turn tracking
    activations_this_turn: int = 0

    # Mana ability flag (CR 605)
    is_mana_ability: bool = False

    # Zone where this ability functions
    functions_from: str = "battlefield"  # "battlefield", "graveyard", "exile", etc.

    def can_activate(self, game: 'Game') -> bool:
        """Check if this ability can currently be activated (CR 602.2)"""
        # Get controller
        if self.controller is None:
            return False

        player = self.controller

        # Check timing restrictions
        if not self._check_timing(game, player):
            return False

        # Check if cost can be paid
        if self.source and hasattr(self.source, 'object_id'):
            if not self.cost.can_pay(game, player, self.source):
                return False

        # Check if legal targets exist (if targeting is required)
        if self.targets_required:
            for target_req in self.targets_required:
                if not target_req.up_to:  # Required targets
                    legal_targets = target_req.get_legal_targets(
                        game, player.player_id
                    )
                    if len(legal_targets) < target_req.count:
                        return False

        return True

    def _check_timing(self, game: 'Game', player: 'Player') -> bool:
        """Check timing restrictions for activation"""
        # NONE - can activate any time you have priority
        if self.timing == ActivationRestriction.NONE:
            return True

        # SORCERY_SPEED - main phase, stack empty, your turn
        if self.timing == ActivationRestriction.SORCERY_SPEED:
            if game.active_player_id != player.player_id:
                return False
            if game.current_phase not in (PhaseType.PRECOMBAT_MAIN, PhaseType.POSTCOMBAT_MAIN):
                return False
            if not game.zones.stack.is_empty():
                return False
            return True

        # ONCE_PER_TURN
        if self.timing == ActivationRestriction.ONCE_PER_TURN:
            if self.activations_this_turn >= 1:
                return False
            return True

        # ONLY_DURING_COMBAT
        if self.timing == ActivationRestriction.ONLY_DURING_COMBAT:
            if game.current_phase != PhaseType.COMBAT:
                return False
            return True

        # ONLY_DURING_YOUR_TURN
        if self.timing == ActivationRestriction.ONLY_DURING_YOUR_TURN:
            if game.active_player_id != player.player_id:
                return False
            return True

        # TAP_ABILITY - check summoning sickness
        if self.timing == ActivationRestriction.TAP_ABILITY:
            if self.source and hasattr(self.source, 'has_summoning_sickness'):
                if self.source.characteristics.is_creature():
                    if self.source.has_summoning_sickness():
                        return False
            return True

        return True

    def activate(self, game: 'Game', targets: Optional[List[Any]] = None) -> bool:
        """Activate this ability (CR 602.2)

        1. Announce activation
        2. Choose modes (if any)
        3. Choose targets
        4. Determine total cost
        5. Activate mana abilities to pay (if needed)
        6. Pay costs
        7. Put ability on stack (unless mana ability)
        """
        if not self.can_activate(game):
            return False

        player = self.controller

        # Pay costs
        if not self.cost.pay(game, player, self.source):
            return False

        # Track activation
        self.activations_this_turn += 1

        # Create stack object (unless mana ability)
        if not self.is_mana_ability:
            stack_ability = self.create_stack_object(targets)
            game.zones.stack.push(stack_ability)

            # Emit event
            from ..events import AbilityActivatedEvent
            game.events.emit(AbilityActivatedEvent(
                ability_source_id=self.source.object_id if self.source else 0,
                controller_id=player.player_id
            ))
        else:
            # Mana abilities resolve immediately
            if self.effect_func:
                self.effect_func(game, self.source, targets)

        return True

    def reset_turn_state(self):
        """Reset per-turn tracking (called at beginning of each turn)"""
        self.activations_this_turn = 0

    def create_stack_object(self, targets: Optional[List[Any]] = None) -> 'StackedAbility':
        """Create a stacked ability object for the stack"""
        from ..objects import StackedAbility, Target

        stacked = StackedAbility(
            object_id=0,  # Will be assigned by game
            owner_id=self.controller.player_id if self.controller else 0,
            controller_id=self.controller.player_id if self.controller else 0,
            source_id=self.source.object_id if self.source else 0,
            source_name=self.source.name if self.source else "",
            ability_type=AbilityType.ACTIVATED,
            effect_text=self.effect
        )

        # Add targets
        if targets:
            for target in targets:
                from ..objects import Permanent
                from ..player import Player

                if isinstance(target, Permanent):
                    stacked.targets.append(Target(
                        target_type=TargetType.PERMANENT,
                        chosen_id=target.object_id
                    ))
                elif isinstance(target, Player):
                    stacked.targets.append(Target(
                        target_type=TargetType.PLAYER,
                        chosen_player_id=target.player_id
                    ))

        # Store effect function for resolution
        if self.effect_func:
            stacked.effect_func = self.effect_func

        return stacked


# =============================================================================
# Mana Ability (CR 605)
# =============================================================================

@dataclass
class ManaAbility(ActivatedAbility):
    """A mana ability as defined in CR 605

    Mana abilities:
    - Are activated abilities that could produce mana (CR 605.1a)
    - Don't have targets (CR 605.1b)
    - Don't use the stack (CR 605.3)
    - Resolve immediately when activated
    """
    # What mana this ability produces
    mana_produced: List[Tuple[Color, int]] = field(default_factory=list)

    def __post_init__(self):
        self.is_mana_ability = True
        self.timing = ActivationRestriction.NONE  # Mana abilities can be activated anytime

    def activate(self, game: 'Game', targets: Optional[List[Any]] = None) -> bool:
        """Activate mana ability - resolves immediately without using stack"""
        if not self.can_activate(game):
            return False

        player = self.controller

        # Pay costs
        if not self.cost.pay(game, player, self.source):
            return False

        # Track activation
        self.activations_this_turn += 1

        # Add mana immediately (CR 605.3)
        for color, amount in self.mana_produced:
            player.mana_pool.add(
                color=color,
                amount=amount,
                source_id=self.source.object_id if self.source else None
            )

            # Emit mana added event
            from ..events import ManaAddedEvent
            game.events.emit(ManaAddedEvent(
                player_id=player.player_id,
                color=color,
                amount=amount,
                source_id=self.source.object_id if self.source else 0
            ))

        return True

    def create_stack_object(self, targets: Optional[List[Any]] = None) -> None:
        """Mana abilities don't create stack objects"""
        return None


# =============================================================================
# Loyalty Ability (CR 606)
# =============================================================================

@dataclass
class LoyaltyAbility(ActivatedAbility):
    """A loyalty ability as defined in CR 606

    Loyalty abilities:
    - Are activated abilities of planeswalkers
    - Can only be activated once per turn per planeswalker (CR 606.3)
    - Can only be activated at sorcery speed (CR 606.3)
    - Have loyalty costs (+ or -) as part of their cost
    """
    # Loyalty cost (positive for +N, negative for -N, 0 for 0)
    loyalty_cost: int = 0

    def __post_init__(self):
        # Set up cost with loyalty component
        self.cost.loyalty_cost = self.loyalty_cost

        # Loyalty abilities are always sorcery speed and once per turn
        self.timing = ActivationRestriction.SORCERY_SPEED

    def can_activate(self, game: 'Game') -> bool:
        """Check if loyalty ability can be activated (CR 606.3)"""
        # Check if planeswalker has already activated a loyalty ability this turn
        if self.source and hasattr(self.source, 'loyalty_activated_this_turn'):
            if self.source.loyalty_activated_this_turn:
                return False

        # Check if we have enough loyalty for minus abilities
        if self.loyalty_cost < 0:
            if self.source:
                current_loyalty = self.source.current_loyalty()
                if current_loyalty < abs(self.loyalty_cost):
                    return False

        return super().can_activate(game)

    def activate(self, game: 'Game', targets: Optional[List[Any]] = None) -> bool:
        """Activate loyalty ability"""
        if not self.can_activate(game):
            return False

        # Mark that this planeswalker has activated a loyalty ability
        if self.source and hasattr(self.source, 'loyalty_activated_this_turn'):
            self.source.loyalty_activated_this_turn = True

        # The loyalty cost adjustment is handled in Cost.pay()
        return super().activate(game, targets)


# =============================================================================
# Equip Ability (CR 702.6)
# =============================================================================

@dataclass
class EquipAbility(ActivatedAbility):
    """An equip ability as defined in CR 702.6

    Equip abilities:
    - Can only be activated at sorcery speed (CR 702.6a)
    - Target: creature you control
    - Attaches the Equipment to that creature
    """
    def __post_init__(self):
        self.timing = ActivationRestriction.SORCERY_SPEED
        self.effect = "Attach this Equipment to target creature you control."

        # Set up targeting
        self.targets_required = [
            AbilityTargetRestriction(
                target_type=TargetType.CREATURE,
                controller_restriction="you"
            )
        ]

        # Effect function
        self.effect_func = self._equip_effect

    @staticmethod
    def _equip_effect(game: 'Game', source: 'Permanent', targets: List[Any]):
        """Attach equipment to target creature"""
        if not targets:
            return

        target_creature = targets[0]

        # Unattach from current creature if attached
        if source.attached_to_id is not None:
            old_attached = game.zones.battlefield.get_by_id(source.attached_to_id)
            if old_attached:
                old_attached.remove_attachment(source.object_id)

        # Attach to new creature
        source.attach_to(target_creature.object_id)
        target_creature.add_attachment(source.object_id)


# =============================================================================
# Crew Ability (CR 702.122)
# =============================================================================

@dataclass
class CrewAbility(ActivatedAbility):
    """A crew ability as defined in CR 702.122

    Crew abilities:
    - Cost: Tap any number of creatures with total power >= crew_power
    - Effect: This Vehicle becomes an artifact creature until end of turn
    """
    crew_power: int = 0

    def __post_init__(self):
        self.timing = ActivationRestriction.NONE  # Can crew at instant speed
        self.effect = f"Crew {self.crew_power} (Tap any number of creatures you control with total power {self.crew_power} or more: This Vehicle becomes an artifact creature until end of turn.)"
        self.cost.crew_power = self.crew_power

        # Effect function
        self.effect_func = self._crew_effect

    def can_activate(self, game: 'Game') -> bool:
        """Check if crew can be activated (enough untapped creature power)"""
        if not super().can_activate(game):
            return False

        # Calculate total available power from untapped creatures
        player = self.controller
        total_power = 0

        for permanent in game.zones.battlefield.get_all():
            if permanent.controller_id == player.player_id:
                if permanent.characteristics.is_creature():
                    if not permanent.is_tapped:
                        if permanent.object_id != self.source.object_id:
                            total_power += permanent.effective_power()

        return total_power >= self.crew_power

    @staticmethod
    def _crew_effect(game: 'Game', source: 'Permanent', targets: List[Any]):
        """Turn this Vehicle into an artifact creature until end of turn"""
        from .continuous import create_type_change_effect, Duration

        # Add creature type
        source.characteristics.types.add(CardType.CREATURE)

        # Apply until end of turn effect
        # (In full implementation, this would use the continuous effects system)


# =============================================================================
# Factory Functions
# =============================================================================

def create_tap_for_mana(color: Color, source: 'Permanent' = None,
                        controller: 'Player' = None) -> ManaAbility:
    """Create a standard tap-for-mana ability like basic lands have"""
    return ManaAbility(
        source=source,
        controller=controller,
        cost=Cost(tap=True),
        effect=f"Add {{{color.value}}}.",
        mana_produced=[(color, 1)],
        timing=ActivationRestriction.TAP_ABILITY
    )


def create_loyalty_ability(cost: int, effect: str,
                           effect_func: Optional[Callable] = None,
                           source: 'Permanent' = None,
                           controller: 'Player' = None,
                           targets: Optional[List[AbilityTargetRestriction]] = None) -> LoyaltyAbility:
    """Create a planeswalker loyalty ability

    Args:
        cost: Positive for +N, negative for -N, 0 for 0
        effect: Text description of the effect
        effect_func: Function to execute on resolution
        source: The planeswalker permanent
        controller: The controlling player
        targets: Target requirements if any
    """
    ability = LoyaltyAbility(
        source=source,
        controller=controller,
        loyalty_cost=cost,
        effect=effect,
        effect_func=effect_func
    )

    if targets:
        ability.targets_required = targets

    return ability


def create_equip(mana_cost_str: str, source: 'Permanent' = None,
                 controller: 'Player' = None) -> EquipAbility:
    """Create an equip ability with the given mana cost

    Args:
        mana_cost_str: Mana cost string like "{2}" or "{1}{W}"
        source: The Equipment permanent
        controller: The controlling player
    """
    from ..objects import ManaCost

    ability = EquipAbility(
        source=source,
        controller=controller
    )
    ability.cost = Cost(mana_cost=ManaCost.parse(mana_cost_str))

    return ability


def create_crew(power: int, source: 'Permanent' = None,
                controller: 'Player' = None) -> CrewAbility:
    """Create a crew ability with the given power requirement"""
    return CrewAbility(
        source=source,
        controller=controller,
        crew_power=power
    )


# =============================================================================
# Activated Ability Manager
# =============================================================================

class ActivatedAbilityManager:
    """Manages all activated abilities in the game

    Responsibilities:
    - Track registered abilities
    - Provide list of activatable abilities for a player
    - Reset turn-based state
    """

    def __init__(self, game: 'Game'):
        self.game = game
        self.abilities: Dict[ObjectId, List[ActivatedAbility]] = {}

    def register(self, ability: ActivatedAbility, source_id: Optional[ObjectId] = None):
        """Register an activated ability"""
        if source_id is None and ability.source:
            source_id = ability.source.object_id

        if source_id is not None:
            if source_id not in self.abilities:
                self.abilities[source_id] = []
            self.abilities[source_id].append(ability)

    def unregister(self, source_id: ObjectId):
        """Remove all abilities for a source (when it leaves battlefield)"""
        if source_id in self.abilities:
            del self.abilities[source_id]

    def get_abilities(self, source_id: ObjectId) -> List[ActivatedAbility]:
        """Get all activated abilities for a source"""
        return self.abilities.get(source_id, [])

    def get_activatable(self, player: 'Player') -> List[ActivatedAbility]:
        """Get all abilities the player can currently activate"""
        activatable = []

        for source_id, abilities in self.abilities.items():
            # Find the source permanent
            result = self.game.zones.find_object(source_id)
            if not result:
                continue
            source, zone = result

            # Check each ability
            for ability in abilities:
                # Update ability's references
                ability.source = source
                ability.controller = self.game.get_player(source.controller_id)

                # Check if this player controls the source
                if source.controller_id != player.player_id:
                    continue

                # Check if ability can be activated
                if ability.can_activate(self.game):
                    activatable.append(ability)

        return activatable

    def reset_turn_state(self):
        """Reset all per-turn tracking (called at beginning of each turn)"""
        for abilities in self.abilities.values():
            for ability in abilities:
                ability.reset_turn_state()

        # Also reset loyalty ability tracking on planeswalkers
        for permanent in self.game.zones.battlefield.get_all():
            if hasattr(permanent, 'loyalty_activated_this_turn'):
                permanent.loyalty_activated_this_turn = False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    'ActivationRestriction',

    # Core classes
    'Cost',
    'AbilityTargetRestriction',
    'ActivatedAbility',
    'ManaAbility',
    'LoyaltyAbility',
    'EquipAbility',
    'CrewAbility',

    # Manager
    'ActivatedAbilityManager',

    # Factory functions
    'create_tap_for_mana',
    'create_loyalty_ability',
    'create_equip',
    'create_crew',
]
