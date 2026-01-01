"""
Replacement Effects per Comprehensive Rules 614.

CR 614.1: Some continuous effects are replacement effects. Like prevention effects,
replacement effects apply continuously as events happen - they aren't locked in ahead of time.
They use "instead" or "skip" in their text.

CR 614.4: Replacement effects must exist before the appropriate event occurs.

CR 614.5: A replacement effect doesn't invoke itself repeatedly; it gets only one opportunity
to affect an event or any modified events that may replace it.

CR 614.6: If an event is replaced, the original event never happens.

CR 614.7: If a replacement effect would cause a loop, it applies only once.

CR 614.15: Some replacement effects are self-replacement effects. These modify how an object
enters the battlefield or otherwise affects itself. Self-replacement effects apply before
other replacement effects.

CR 614.16: If an event is replaced, it never happens. A modified event is considered a new event.

CR 615: Prevention effects are a subset of replacement effects that specifically prevent damage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

if TYPE_CHECKING:
    from ..game import Game
    from ..events import Event, DamageEvent


# =============================================================================
# Core Replacement Effect Class
# =============================================================================

@dataclass
class ReplacementEffect:
    """
    A replacement effect that modifies or replaces events (CR 614).

    Replacement effects change what happens when certain events would occur.
    They substitute a different outcome for the original event.

    Key rules:
    - CR 614.5: Affected player/controller chooses order if multiple apply
    - CR 614.7: Each effect can only apply once per event
    - CR 614.15: Self-replacement effects apply first

    Attributes:
        source: The GameObject that generates this effect
        controller: The Player who controls the source
        replaced_event_type: The Event class this effect can replace
        condition: Function to check if this applies to a specific event
        replacement: Function that returns the modified event (or None to cancel)
        is_self_replacement: Whether this is a self-replacement effect (CR 614.15)
        is_prevention: Whether this is a prevention effect (CR 615)
    """
    source: Any  # GameObject
    controller: Any  # Player
    replaced_event_type: Type  # Event class to replace
    condition: Callable[[Any], bool]  # Callable[[Event], bool]
    replacement: Callable[[Any], Optional[Any]]  # Callable[[Event], Optional[Event]]
    is_self_replacement: bool = False
    is_prevention: bool = False

    # Track which events this effect has been applied to (CR 614.5)
    _applied_to_events: Set[int] = field(default_factory=set)

    # Optional metadata
    description: str = ""
    duration: Optional[str] = None  # "end_of_turn", "until_leaves", "permanent"
    expires_after_use: bool = False
    uses_remaining: Optional[int] = None

    def __post_init__(self):
        """Initialize internal state."""
        if self._applied_to_events is None:
            self._applied_to_events = set()

    def applies_to(self, event: Any) -> bool:
        """
        Check if this replacement effect applies to the given event.

        CR 614.4: The effect must exist before the event occurs.
        CR 614.5: Each effect can only apply once per event chain.

        Args:
            event: The event to check

        Returns:
            True if this effect can replace the event
        """
        # CR 614.5: Check if already applied to this event
        event_id = id(event)
        if event_id in self._applied_to_events:
            return False

        # Check type match
        if not isinstance(event, self.replaced_event_type):
            return False

        # Check uses remaining
        if self.uses_remaining is not None and self.uses_remaining <= 0:
            return False

        # Check condition
        try:
            return self.condition(event)
        except Exception:
            return False

    def replace(self, event: Any) -> Optional[Any]:
        """
        Apply this replacement effect to an event.

        CR 614.1: The replacement modifies or replaces the event.
        CR 614.16: If replaced, the original event never happens.

        Args:
            event: The event to replace

        Returns:
            The replacement event, or None if the event is completely replaced/prevented
        """
        # Mark as applied to this event (CR 614.5)
        self._applied_to_events.add(id(event))

        # Decrement uses if limited
        if self.uses_remaining is not None:
            self.uses_remaining -= 1

        # Perform the replacement
        try:
            return self.replacement(event)
        except Exception:
            # On error, return original event unchanged
            return event

    def reset_application_tracking(self) -> None:
        """Reset the tracking of which events this has been applied to."""
        self._applied_to_events.clear()

    def is_expired(self) -> bool:
        """Check if this replacement effect has expired."""
        if self.uses_remaining is not None and self.uses_remaining <= 0:
            return True
        return False

    def get_affected_player(self, event: Any) -> Optional[Any]:
        """
        Determine which player is affected by this event.

        CR 616.1: The affected player or controller of the affected object
        chooses which replacement effect to apply first.

        Args:
            event: The event being replaced

        Returns:
            The player who should choose order for this replacement
        """
        # Try common event attributes
        if hasattr(event, 'player'):
            return event.player
        if hasattr(event, 'controller'):
            return event.controller
        if hasattr(event, 'affected_player'):
            return event.affected_player
        if hasattr(event, 'target'):
            target = event.target
            if hasattr(target, 'controller'):
                return target.controller

        # Default to effect controller
        return self.controller

    def __hash__(self) -> int:
        """Hash for set operations."""
        return id(self)

    def __eq__(self, other: object) -> bool:
        """Equality based on identity."""
        return self is other


# =============================================================================
# Prevention Effect (Subclass of ReplacementEffect)
# =============================================================================

@dataclass
class PreventionEffect(ReplacementEffect):
    """
    Damage prevention effect per CR 615.

    CR 615.1: Some continuous effects are prevention effects. Like replacement effects,
    prevention effects apply continuously as events happen.

    CR 615.6: If damage that would be dealt is prevented, it never happens.

    Attributes:
        amount: Amount of damage to prevent (None = prevent all)
        prevented_so_far: Track how much has been prevented (for shields)
    """
    amount: Optional[int] = None  # None = prevent all damage
    prevented_so_far: int = 0

    # Additional prevention filters
    prevent_combat_only: bool = False
    prevent_noncombat_only: bool = False
    prevent_from_source: Optional[Any] = None  # Only prevent from specific source

    def __post_init__(self):
        """Set up prevention-specific defaults."""
        super().__post_init__()
        self.is_prevention = True

    def applies_to(self, event: Any) -> bool:
        """
        Check if this prevention applies to the damage event.

        Args:
            event: The damage event to check

        Returns:
            True if this prevention can apply
        """
        # Check basic applicability
        if not super().applies_to(event):
            return False

        # Check if prevention is depleted
        if self.amount is not None:
            remaining = self.amount - self.prevented_so_far
            if remaining <= 0:
                return False

        # Check if damage can be prevented (some damage is unpreventable)
        if hasattr(event, 'is_unpreventable') and event.is_unpreventable:
            return False

        # Check combat damage restrictions
        if hasattr(event, 'is_combat_damage'):
            if self.prevent_combat_only and not event.is_combat_damage:
                return False
            if self.prevent_noncombat_only and event.is_combat_damage:
                return False

        # Check source restriction
        if self.prevent_from_source is not None:
            if hasattr(event, 'source'):
                if event.source is not self.prevent_from_source:
                    return False

        return True

    def prevent(self, damage_event: Any) -> Optional[Any]:
        """
        Apply damage prevention to a damage event.

        CR 615.6: The damage is prevented (never happens) and a modified
        event with reduced damage may be created.

        Args:
            damage_event: The damage event to prevent

        Returns:
            Modified damage event with reduced damage, or None if fully prevented
        """
        # Mark as applied
        self._applied_to_events.add(id(damage_event))

        if not hasattr(damage_event, 'amount'):
            return damage_event

        original_amount = damage_event.amount

        if self.amount is None:
            # Prevent all damage
            prevented = original_amount
            remaining_damage = 0
        else:
            # Prevent up to remaining shield amount
            available_prevention = self.amount - self.prevented_so_far
            prevented = min(original_amount, available_prevention)
            remaining_damage = original_amount - prevented
            self.prevented_so_far += prevented

        # Track prevention for triggers
        if hasattr(damage_event, 'prevented_amount'):
            damage_event.prevented_amount = getattr(damage_event, 'prevented_amount', 0) + prevented

        # Create "damage was prevented" event for triggers if applicable
        if hasattr(damage_event, 'create_prevention_event') and prevented > 0:
            damage_event.create_prevention_event(prevented, self.source)

        if remaining_damage <= 0:
            # All damage prevented
            return None

        # Create modified event with reduced damage
        return self._create_reduced_damage_event(damage_event, remaining_damage)

    def _create_reduced_damage_event(self, original: Any, new_amount: int) -> Any:
        """
        Create a copy of the damage event with reduced damage.

        Args:
            original: The original damage event
            new_amount: The new (reduced) damage amount

        Returns:
            A new damage event with the reduced amount
        """
        # Try to use a method on the event
        if hasattr(original, 'with_amount'):
            return original.with_amount(new_amount)

        # Fallback: create a shallow copy and modify
        import copy
        try:
            new_event = copy.copy(original)
            new_event.amount = new_amount
            return new_event
        except Exception:
            # Last resort: modify in place
            original.amount = new_amount
            return original

    def replace(self, event: Any) -> Optional[Any]:
        """Override replace to use prevent for damage events."""
        return self.prevent(event)

    def remaining_prevention(self) -> Optional[int]:
        """Get the remaining prevention amount, or None if unlimited."""
        if self.amount is None:
            return None
        return max(0, self.amount - self.prevented_so_far)

    def is_expired(self) -> bool:
        """Check if this prevention shield is depleted."""
        if self.amount is not None and self.prevented_so_far >= self.amount:
            return True
        return super().is_expired()


# =============================================================================
# Replacement Effect Manager
# =============================================================================

class ReplacementEffectManager:
    """
    Manages all replacement effects and processes events through them.

    CR 614.5: Each replacement effect can only apply once to each event.
    CR 614.15: Self-replacement effects apply first.
    CR 616.1: If multiple effects could apply, the affected player chooses order.
    """

    def __init__(self, game: Any):
        """
        Initialize the replacement effect manager.

        Args:
            game: The game instance
        """
        self.game = game
        self.effects: List[ReplacementEffect] = []
        self._processing_depth: int = 0
        self._max_processing_depth: int = 100  # Prevent infinite loops

    def register(self, effect: ReplacementEffect) -> None:
        """
        Register a replacement effect with the manager.

        Args:
            effect: The replacement effect to register
        """
        if effect not in self.effects:
            self.effects.append(effect)

    def unregister(self, effect: ReplacementEffect) -> None:
        """
        Remove a replacement effect from the manager.

        Args:
            effect: The replacement effect to remove
        """
        if effect in self.effects:
            self.effects.remove(effect)

    def unregister_from_source(self, source: Any) -> int:
        """
        Remove all replacement effects from a specific source.

        Args:
            source: The source object whose effects should be removed

        Returns:
            Number of effects removed
        """
        original_count = len(self.effects)
        self.effects = [e for e in self.effects if e.source is not source]
        return original_count - len(self.effects)

    def process_event(self, event: Any) -> Optional[Any]:
        """
        Process an event through all applicable replacement effects.

        Main entry point for replacement effect processing.

        CR 614.15: Self-replacement effects apply first.
        CR 616.1: Affected player chooses order for remaining effects.
        CR 614.5: Each effect only applies once per event chain.

        Args:
            event: The event to process

        Returns:
            The final event after all replacements, or None if completely replaced
        """
        self._processing_depth += 1

        try:
            # Check for infinite loop protection
            if self._processing_depth > self._max_processing_depth:
                return event

            current_event = event
            applied_effects: Set[ReplacementEffect] = set()

            while current_event is not None:
                # Step 1: Get applicable effects for current event state
                applicable = self._get_applicable(current_event)

                # Filter out already applied effects
                applicable = [e for e in applicable if e not in applied_effects]

                if not applicable:
                    break

                # Step 2: Apply self-replacement effects first (CR 614.15)
                current_event, remaining = self._apply_self_replacements(
                    current_event, applicable
                )
                applied_effects.update(set(applicable) - set(remaining))

                if current_event is None:
                    return None

                # If no non-self effects remain, check for new applicable effects
                if not remaining:
                    continue

                # Step 3: For non-self effects, affected player chooses order (CR 616.1)
                chosen_effect = self._choose_replacement_effect(current_event, remaining)

                if chosen_effect is None:
                    break

                # Step 4: Apply the chosen replacement
                current_event = chosen_effect.replace(current_event)
                applied_effects.add(chosen_effect)

                # Step 5: Check if new replacement effects apply to modified event
                # (This happens automatically on next loop iteration)

                # Clean up expired effects
                self._cleanup_expired_effects()

            # Step 6-7: Continue until no more apply, return final event
            return current_event

        finally:
            self._processing_depth -= 1

    def _get_applicable(self, event: Any) -> List[ReplacementEffect]:
        """
        Get all replacement effects that apply to an event.

        Args:
            event: The event to check

        Returns:
            List of applicable replacement effects
        """
        return [e for e in self.effects if e.applies_to(event)]

    def _apply_self_replacements(
        self,
        event: Any,
        effects: List[ReplacementEffect]
    ) -> Tuple[Optional[Any], List[ReplacementEffect]]:
        """
        Apply all self-replacement effects to an event.

        CR 614.15: Self-replacement effects apply before other replacement effects.

        Args:
            event: The event to process
            effects: List of applicable effects

        Returns:
            Tuple of (modified event, remaining non-self effects)
        """
        self_replacements = [e for e in effects if e.is_self_replacement]
        other_replacements = [e for e in effects if not e.is_self_replacement]

        current_event = event

        # Apply all self-replacement effects
        # If multiple, affected object's controller chooses order
        while self_replacements and current_event is not None:
            if len(self_replacements) == 1:
                chosen = self_replacements[0]
            else:
                chosen = self._choose_replacement_effect(current_event, self_replacements)

            if chosen is None:
                break

            current_event = chosen.replace(current_event)
            self_replacements.remove(chosen)

        return current_event, other_replacements

    def _choose_replacement_effect(
        self,
        event: Any,
        effects: List[ReplacementEffect]
    ) -> Optional[ReplacementEffect]:
        """
        Let the affected player choose which replacement effect to apply.

        CR 616.1: The affected player or controller of the affected object
        chooses which replacement effect to apply first.

        Args:
            event: The event being replaced
            effects: List of applicable effects to choose from

        Returns:
            The chosen replacement effect
        """
        if not effects:
            return None

        if len(effects) == 1:
            return effects[0]

        # Determine the affected player
        affected_player = None
        for effect in effects:
            player = effect.get_affected_player(event)
            if player is not None:
                affected_player = player
                break

        # If no affected player found, use APNAP order (active player first)
        if affected_player is None:
            if hasattr(self.game, 'active_player'):
                affected_player = self.game.active_player

        # Request choice from player
        if affected_player is not None and hasattr(affected_player, 'choose_replacement_effect'):
            return affected_player.choose_replacement_effect(event, effects)

        # Default: apply in registration order (first registered first)
        return effects[0]

    def _cleanup_expired_effects(self) -> None:
        """Remove expired replacement effects from the list."""
        self.effects = [e for e in self.effects if not e.is_expired()]

    def clear_turn_tracking(self) -> None:
        """Reset application tracking at end of turn for all effects."""
        for effect in self.effects:
            effect.reset_application_tracking()

    def get_effects_from_source(self, source: Any) -> List[ReplacementEffect]:
        """Get all replacement effects from a specific source."""
        return [e for e in self.effects if e.source is source]

    def clear_all(self) -> None:
        """Clear all effects (for game reset)."""
        self.effects.clear()


# =============================================================================
# Common Replacement Effect Factories
# =============================================================================

def etb_with_counters(
    source: Any,
    counter_type: str,
    count: Union[int, Callable[[], int]],
    condition: Optional[Callable[[Any], bool]] = None
) -> ReplacementEffect:
    """
    Create a replacement effect for entering the battlefield with counters.

    Example: "Enters the battlefield with three +1/+1 counters."

    Args:
        source: The object generating this effect
        counter_type: Type of counter (e.g., "+1/+1", "loyalty", "charge")
        count: Number of counters, or callable returning count
        condition: Optional additional condition

    Returns:
        A self-replacement effect for ETB with counters
    """
    # Determine the event type to watch for
    try:
        from ..events import ZoneChangeEvent
        replaced_type = ZoneChangeEvent
    except ImportError:
        replaced_type = object

    def etb_condition(event: Any) -> bool:
        # Check if this is the source entering the battlefield
        if not hasattr(event, 'object'):
            return False
        if event.object is not source:
            return False
        if hasattr(event, 'destination_zone'):
            dest = event.destination_zone
            if isinstance(dest, str) and dest.lower() != 'battlefield':
                return False
            elif hasattr(dest, 'value') and dest.value.lower() != 'battlefield':
                return False
        if condition is not None:
            return condition(event)
        return True

    def etb_replacement(event: Any) -> Any:
        # Calculate counter count
        actual_count = count() if callable(count) else count

        # Modify the event to include counter addition
        if hasattr(event, 'add_etb_counters'):
            event.add_etb_counters(counter_type, actual_count)
        elif hasattr(event, 'with_counters'):
            if counter_type not in event.with_counters:
                event.with_counters[counter_type] = 0
            event.with_counters[counter_type] += actual_count
        elif hasattr(event, 'modifications'):
            event.modifications.append({
                'type': 'add_counters',
                'counter_type': counter_type,
                'count': actual_count
            })

        return event

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=etb_condition,
        replacement=etb_replacement,
        is_self_replacement=True,
        description=f"Enters with {count if not callable(count) else 'X'} {counter_type} counters"
    )


def damage_prevention(
    source: Any,
    amount: Optional[int] = None,
    condition: Optional[Callable[[Any], bool]] = None,
    prevent_combat_only: bool = False,
    prevent_from_source: Optional[Any] = None
) -> PreventionEffect:
    """
    Create a damage prevention effect.

    Example: "Prevent the next 3 damage that would be dealt to target creature."

    Args:
        source: The object generating this effect
        amount: Amount of damage to prevent (None = all)
        condition: Condition for which damage to prevent
        prevent_combat_only: Only prevent combat damage
        prevent_from_source: Only prevent damage from this source

    Returns:
        A prevention effect for damage
    """
    # Determine the event type
    try:
        from ..events import DamageEvent
        replaced_type = DamageEvent
    except ImportError:
        replaced_type = object

    def damage_condition(event: Any) -> bool:
        if condition is not None:
            return condition(event)
        return True

    return PreventionEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=damage_condition,
        replacement=lambda e: None,  # Handled by prevent() method
        amount=amount,
        prevent_combat_only=prevent_combat_only,
        prevent_from_source=prevent_from_source,
        description=f"Prevent {'all' if amount is None else amount} damage"
    )


def redirect_damage(
    source: Any,
    new_target: Any,
    amount: Optional[int] = None,
    condition: Optional[Callable[[Any], bool]] = None
) -> ReplacementEffect:
    """
    Create a damage redirection effect.

    Example: "If damage would be dealt to you, it is dealt to target creature instead."

    Args:
        source: The object generating this effect
        new_target: The new target for the damage
        amount: Amount of damage to redirect (None = all)
        condition: Condition for which damage to redirect

    Returns:
        A replacement effect that redirects damage
    """
    # Determine the event type
    try:
        from ..events import DamageEvent
        replaced_type = DamageEvent
    except ImportError:
        replaced_type = object

    redirected_so_far = [0]  # Use list for mutable closure

    def redirect_condition(event: Any) -> bool:
        if amount is not None and redirected_so_far[0] >= amount:
            return False
        if condition is not None:
            return condition(event)
        return True

    def redirect_replacement(event: Any) -> Any:
        if not hasattr(event, 'target'):
            return event

        original_amount = getattr(event, 'amount', 0)

        if amount is not None:
            remaining = amount - redirected_so_far[0]
            redirect_amount = min(original_amount, remaining)
            redirected_so_far[0] += redirect_amount

            if redirect_amount < original_amount:
                # Need to split damage between old and new target
                if hasattr(event, 'split'):
                    return event.split(new_target, redirect_amount)

        # Change the target
        import copy
        new_event = copy.copy(event)
        new_event.target = new_target
        return new_event

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=redirect_condition,
        replacement=redirect_replacement,
        description=f"Redirect damage to {new_target}"
    )


def exile_instead_of_die(
    source: Any,
    affected_objects: Optional[Callable[[Any], bool]] = None
) -> ReplacementEffect:
    """
    Create a replacement effect for exiling instead of dying.

    Example: "If a creature an opponent controls would die, exile it instead."

    Args:
        source: The object generating this effect
        affected_objects: Condition for which objects this applies to

    Returns:
        A replacement effect for exile instead of graveyard
    """
    # Determine the event type
    try:
        from ..events import ZoneChangeEvent
        replaced_type = ZoneChangeEvent
    except ImportError:
        replaced_type = object

    def die_condition(event: Any) -> bool:
        # Check this is going to graveyard from battlefield (dying)
        if not hasattr(event, 'destination_zone'):
            return False

        dest = event.destination_zone
        if isinstance(dest, str):
            if dest.lower() != 'graveyard':
                return False
        elif hasattr(dest, 'value'):
            if dest.value.lower() != 'graveyard':
                return False

        if hasattr(event, 'origin_zone'):
            origin = event.origin_zone
            if isinstance(origin, str):
                if origin.lower() != 'battlefield':
                    return False
            elif hasattr(origin, 'value'):
                if origin.value.lower() != 'battlefield':
                    return False

        if affected_objects is not None:
            obj = getattr(event, 'object', None)
            if obj is None:
                return False
            return affected_objects(obj)

        return True

    def exile_replacement(event: Any) -> Any:
        import copy
        new_event = copy.copy(event)

        # Try to set zone as enum or string
        try:
            from ..types import Zone
            new_event.destination_zone = Zone.EXILE
        except ImportError:
            new_event.destination_zone = 'exile'

        return new_event

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=die_condition,
        replacement=exile_replacement,
        description="Exile instead of dying"
    )


def draw_replacement(
    source: Any,
    replacement_action: Callable[[Any], Optional[Any]],
    condition: Optional[Callable[[Any], bool]] = None,
    affects_player: Optional[Any] = None
) -> ReplacementEffect:
    """
    Create a replacement effect for card draws.

    Example: "If you would draw a card, instead look at the top three cards..."
    (Sylvan Library, Abundance, etc.)

    Args:
        source: The object generating this effect
        replacement_action: Function to perform instead of draw
        condition: Optional additional condition
        affects_player: Only affect draws by this player

    Returns:
        A replacement effect for card draws
    """
    # Determine the event type
    try:
        from ..events import DrawEvent
        replaced_type = DrawEvent
    except ImportError:
        try:
            from ..events import DrawCardEvent
            replaced_type = DrawCardEvent
        except ImportError:
            replaced_type = object

    def draw_condition(event: Any) -> bool:
        if affects_player is not None:
            player = getattr(event, 'player', None)
            if player is not affects_player:
                return False
        if condition is not None:
            return condition(event)
        return True

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=draw_condition,
        replacement=replacement_action,
        description="Draw replacement"
    )


def if_would_gain_life(
    source: Any,
    replacement_action: Callable[[Any], Optional[Any]],
    condition: Optional[Callable[[Any], bool]] = None,
    affects_player: Optional[Any] = None
) -> ReplacementEffect:
    """
    Create a replacement effect for life gain.

    Example: "If you would gain life, you gain twice that much life instead."
    (Boon Reflection)

    Args:
        source: The object generating this effect
        replacement_action: Function to perform instead/in addition
        condition: Optional additional condition
        affects_player: Only affect life gain for this player

    Returns:
        A replacement effect for life gain
    """
    # Determine the event type
    try:
        from ..events import LifeGainEvent
        replaced_type = LifeGainEvent
    except ImportError:
        replaced_type = object

    def life_gain_condition(event: Any) -> bool:
        if affects_player is not None:
            player = getattr(event, 'player', None)
            if player is not affects_player:
                return False
        if condition is not None:
            return condition(event)
        return True

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=life_gain_condition,
        replacement=replacement_action,
        description="Life gain replacement"
    )


# =============================================================================
# Additional Factory Functions
# =============================================================================

def enters_tapped(
    source: Any,
    affected_objects: Optional[Callable[[Any], bool]] = None
) -> ReplacementEffect:
    """
    Create a replacement effect for entering the battlefield tapped.

    Example: "This land enters the battlefield tapped."

    Args:
        source: The object generating this effect
        affected_objects: Which objects this applies to (None = source only)

    Returns:
        A self-replacement effect for ETB tapped
    """
    try:
        from ..events import ZoneChangeEvent
        replaced_type = ZoneChangeEvent
    except ImportError:
        replaced_type = object

    def etb_condition(event: Any) -> bool:
        if not hasattr(event, 'destination_zone'):
            return False

        dest = event.destination_zone
        if isinstance(dest, str) and dest.lower() != 'battlefield':
            return False
        elif hasattr(dest, 'value') and dest.value.lower() != 'battlefield':
            return False

        obj = getattr(event, 'object', None)
        if obj is None:
            return False

        if affected_objects is not None:
            return affected_objects(obj)

        # Default: only apply to source
        return obj is source

    def tapped_replacement(event: Any) -> Any:
        if hasattr(event, 'set_enters_tapped'):
            event.set_enters_tapped(True)
        elif hasattr(event, 'enters_tapped'):
            event.enters_tapped = True
        elif hasattr(event, 'entered_tapped'):
            event.entered_tapped = True
        elif hasattr(event, 'modifications'):
            event.modifications.append({'type': 'enters_tapped'})
        return event

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=etb_condition,
        replacement=tapped_replacement,
        is_self_replacement=True,
        description="Enters the battlefield tapped"
    )


def double_damage(
    source: Any,
    source_filter: Optional[Callable[[Any], bool]] = None,
    target_filter: Optional[Callable[[Any], bool]] = None
) -> ReplacementEffect:
    """
    Create a damage doubling effect.

    Example: "If a source you control would deal damage, it deals double instead."

    Args:
        source: The object generating this effect
        source_filter: Filter for damage sources
        target_filter: Filter for damage targets

    Returns:
        A replacement effect that doubles damage
    """
    try:
        from ..events import DamageEvent
        replaced_type = DamageEvent
    except ImportError:
        replaced_type = object

    def damage_condition(event: Any) -> bool:
        if source_filter is not None:
            damage_source = getattr(event, 'source', None)
            if not source_filter(damage_source):
                return False
        if target_filter is not None:
            if not target_filter(event):
                return False
        return True

    def double_replacement(event: Any) -> Any:
        if hasattr(event, 'amount'):
            event.amount = event.amount * 2
        return event

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=damage_condition,
        replacement=double_replacement,
        description="Damage is doubled"
    )


def cant_gain_life(
    source: Any,
    affected_player: Optional[Any] = None
) -> ReplacementEffect:
    """
    Create a replacement effect that prevents life gain.

    Example: "Your opponents can't gain life." (Erebos, God of the Dead)

    Args:
        source: The object generating this effect
        affected_player: Which player can't gain life (None = all opponents)

    Returns:
        A replacement effect that prevents life gain
    """
    try:
        from ..events import LifeGainEvent
        replaced_type = LifeGainEvent
    except ImportError:
        replaced_type = object

    def no_life_gain_condition(event: Any) -> bool:
        player = getattr(event, 'player', None)
        if affected_player is not None:
            return player is affected_player

        # Default: affect all opponents of source's controller
        controller = getattr(source, 'controller', None)
        if controller is not None and player is not None:
            return player is not controller

        return True

    def prevent_life_gain(event: Any) -> None:
        # Return None to indicate the event is completely prevented
        return None

    return ReplacementEffect(
        source=source,
        controller=getattr(source, 'controller', None),
        replaced_event_type=replaced_type,
        condition=no_life_gain_condition,
        replacement=prevent_life_gain,
        description="Can't gain life"
    )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Core classes
    'ReplacementEffect',
    'PreventionEffect',
    'ReplacementEffectManager',

    # Factory functions
    'etb_with_counters',
    'damage_prevention',
    'redirect_damage',
    'exile_instead_of_die',
    'draw_replacement',
    'if_would_gain_life',

    # Additional factories
    'enters_tapped',
    'double_damage',
    'cant_gain_life',
]
