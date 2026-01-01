"""
Triggered Abilities Implementation per CR 603.

CR 603.1: Triggered abilities have a trigger condition and an effect.
          They begin with "when," "whenever," or "at."
CR 603.2: Whenever a game event matches a trigger condition, the ability triggers.
CR 603.3: Once triggered, the ability goes on the stack the next time a player
          would receive priority.
CR 603.3b: If multiple triggered abilities trigger simultaneously, active player's
           triggers are put on stack first (APNAP order), then each player
           chooses order of their own.
CR 603.4: Intervening-if clauses check both when triggering and when resolving.
CR 603.5: Some triggers look back in time (LKI - Last Known Information).
CR 603.6: Trigger conditions and zone-change triggers.
CR 603.7: Reflexive triggered abilities.
CR 603.10: State triggers only trigger once until condition becomes false again.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

if TYPE_CHECKING:
    from ..game import Game
    from ..player import Player
    from ..game_object import GameObject
    from ..stack import AbilityOnStack
    from .targeting import TargetRestriction


# -----------------------------------------------------------------------------
# Event Base Class (for type hints - actual events defined elsewhere)
# -----------------------------------------------------------------------------

class Event:
    """Base class for all game events that can trigger abilities."""
    pass


# -----------------------------------------------------------------------------
# Trigger Type Enum
# -----------------------------------------------------------------------------

class TriggerType(Enum):
    """
    Timing words that introduce triggered abilities.

    CR 603.1: Triggered abilities use the words "when," "whenever," or "at."

    - WHEN: Triggers once for a specific occurrence (e.g., "When this enters...")
    - WHENEVER: Triggers each time the condition is met (e.g., "Whenever you cast...")
    - AT: Triggers at a specific point in time (e.g., "At the beginning of upkeep...")
    """
    WHEN = auto()      # Single occurrence trigger
    WHENEVER = auto()  # Repeatable trigger
    AT = auto()        # Time-based trigger


# -----------------------------------------------------------------------------
# Trigger Condition
# -----------------------------------------------------------------------------

@dataclass
class TriggerCondition:
    """
    Defines when a triggered ability triggers.

    CR 603.1: A triggered ability has a trigger condition and an effect.
    The trigger condition defines which events cause the ability to trigger.

    Attributes:
        event_type: The type of event this condition listens for.
        filter_func: Optional function to further filter matching events.
                    Takes (event, source_object) and returns bool.
        source_requirement: Specifies relationship between triggering object and source:
                           - "self": Only triggers for the source object itself
                           - "you_control": Only triggers for objects controller controls
                           - "any": Triggers for any matching object (default)
    """
    event_type: Type[Event]
    filter_func: Optional[Callable[[Event, Any], bool]] = None
    source_requirement: Optional[str] = None  # "self", "you_control", "any"

    def matches(self, event: Event, source: Any) -> bool:
        """
        Check if an event matches this trigger condition.

        CR 603.2: Whenever a game event or game state matches a triggered
        ability's trigger event, that ability automatically triggers.

        Args:
            event: The event to check against.
            source: The source GameObject of the triggered ability.

        Returns:
            True if the event matches this trigger condition.
        """
        # Check event type
        if not isinstance(event, self.event_type):
            return False

        # Check source requirement
        if self.source_requirement:
            if not self._check_source_requirement(event, source):
                return False

        # Apply custom filter
        if self.filter_func is not None:
            if not self.filter_func(event, source):
                return False

        return True

    def _check_source_requirement(self, event: Event, source: Any) -> bool:
        """
        Check if the event meets the source requirement.

        Args:
            event: The event to check.
            source: The source of the triggered ability.

        Returns:
            True if the source requirement is met.
        """
        if self.source_requirement == "self":
            # The event must involve the source object itself
            event_object = getattr(event, 'object', None) or getattr(event, 'permanent', None)
            return event_object is source

        elif self.source_requirement == "you_control":
            # The event must involve an object the source's controller controls
            event_object = getattr(event, 'object', None) or getattr(event, 'permanent', None)
            if event_object is None:
                return False
            source_controller = getattr(source, 'controller', None)
            event_controller = getattr(event_object, 'controller', None)
            return source_controller is not None and source_controller == event_controller

        elif self.source_requirement == "any":
            # No restriction
            return True

        # Unknown requirement - default to True
        return True


# -----------------------------------------------------------------------------
# Triggered Ability
# -----------------------------------------------------------------------------

@dataclass
class TriggeredAbility:
    """
    A triggered ability on a game object.

    CR 603.1: A triggered ability has a trigger condition and an effect.
    CR 603.4: A triggered ability may have an "intervening 'if' clause."
              This condition is checked when the ability would trigger and
              again when it would resolve. If false at either time, the
              ability doesn't trigger or is removed from the stack.

    Attributes:
        source: The GameObject that has this triggered ability.
        controller: The player who controls this ability (usually source's controller).
        trigger_condition: The condition that causes this ability to trigger.
        trigger_type: WHEN, WHENEVER, or AT.
        effect: Text description of the effect (for display/parsing).
        intervening_if: Optional condition checked on trigger and resolution.
        targets_required: List of targeting restrictions for this ability.
        one_shot: If True, this ability is removed after triggering once.
    """
    source: Any  # GameObject
    controller: Any  # Player
    trigger_condition: TriggerCondition
    trigger_type: TriggerType
    effect: str
    intervening_if: Optional[Callable[[], bool]] = None
    targets_required: List[Any] = field(default_factory=list)  # List[TargetRestriction]
    one_shot: bool = False

    # Internal tracking
    _has_triggered: bool = field(default=False, repr=False)

    def check_trigger(self, event: Event) -> bool:
        """
        Check if this ability triggers from the given event.

        CR 603.2: Whenever a game event or game state matches a triggered
        ability's trigger event, that ability automatically triggers.

        CR 603.4: If there's an intervening-if clause, the condition must
        be true for the ability to trigger.

        Args:
            event: The event to check.

        Returns:
            True if this ability triggers from the event.
        """
        # One-shot abilities only trigger once
        if self.one_shot and self._has_triggered:
            return False

        # Check if the trigger condition matches
        if not self.trigger_condition.matches(event, self.source):
            return False

        # CR 603.4: Check intervening-if clause
        if self.intervening_if is not None:
            if not self.intervening_if():
                return False

        return True

    def create_stack_object(
        self,
        event: Event,
        targets: Optional[List[Any]] = None
    ) -> 'AbilityOnStack':
        """
        Create a stack object for this triggered ability.

        CR 603.3: Once an ability has triggered, its controller puts it on
        the stack as an object the next time a player would receive priority.

        Args:
            event: The event that caused this trigger.
            targets: The chosen targets for this ability (if any).

        Returns:
            An AbilityOnStack object representing this trigger on the stack.
        """
        # Mark as triggered for one-shot abilities
        if self.one_shot:
            self._has_triggered = True

        # Import here to avoid circular imports
        from ..stack import AbilityOnStack

        return AbilityOnStack(
            source=self.source,
            controller=self.controller,
            ability=self,
            effect_text=self.effect,
            targets=targets or [],
            trigger_event=event,
            intervening_if=self.intervening_if,
        )

    def reset(self) -> None:
        """Reset the trigger state (for one-shot abilities returning to zones)."""
        self._has_triggered = False


# -----------------------------------------------------------------------------
# Common Trigger Condition Factory Functions
# -----------------------------------------------------------------------------

def enters_battlefield(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "enters the battlefield" events.

    CR 603.6a: "Enters the battlefield" abilities trigger when a permanent
    enters the battlefield.

    Args:
        filter_func: Optional filter for the entering permanent.
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for ETB events.
    """
    # Import the actual event type (assumed to exist)
    from ..events import EntersBattlefieldEvent

    return TriggerCondition(
        event_type=EntersBattlefieldEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def leaves_battlefield(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "leaves the battlefield" events.

    CR 603.6c: An ability that triggers when a permanent leaves the
    battlefield triggers when that permanent is exiled, destroyed,
    sacrificed, or otherwise put into another zone from the battlefield.

    Args:
        filter_func: Optional filter for the leaving permanent.
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for LTB events.
    """
    from ..events import LeavesBattlefieldEvent

    return TriggerCondition(
        event_type=LeavesBattlefieldEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def dies(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "dies" events (creature goes to graveyard from battlefield).

    CR 700.4: The word "dies" means "is put into a graveyard from the battlefield."

    Args:
        filter_func: Optional filter for the dying creature.
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for death events.
    """
    from ..events import DiesEvent

    return TriggerCondition(
        event_type=DiesEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def attacks(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "attacks" events.

    CR 508.1a: Triggered abilities that trigger "whenever" or "when"
    a creature attacks trigger when creatures are declared as attackers.

    Args:
        filter_func: Optional filter for the attacking creature.
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for attack declaration events.
    """
    from ..events import AttacksEvent

    return TriggerCondition(
        event_type=AttacksEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def blocks(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "blocks" events.

    CR 509.1h: Triggered abilities that trigger "whenever" or "when"
    a creature blocks trigger when creatures are declared as blockers.

    Args:
        filter_func: Optional filter for the blocking creature.
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for block declaration events.
    """
    from ..events import BlocksEvent

    return TriggerCondition(
        event_type=BlocksEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def deals_damage(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "deals damage" events.

    Args:
        filter_func: Optional filter (can check damage amount, target, etc.).
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for damage events.
    """
    from ..events import DealsDamageEvent

    return TriggerCondition(
        event_type=DealsDamageEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def deals_combat_damage(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "deals combat damage" events.

    CR 510.1: Combat damage is assigned and dealt during the combat damage step.

    Args:
        filter_func: Optional filter (can check damage amount, target, etc.).
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for combat damage events.
    """
    from ..events import DealsCombatDamageEvent

    return TriggerCondition(
        event_type=DealsCombatDamageEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def beginning_of_upkeep(whose: str = "yours") -> TriggerCondition:
    """
    Create a trigger condition for "at the beginning of upkeep" events.

    CR 503.1: The upkeep step has no turn-based actions. Active player
    gets priority and triggered abilities that trigger at the beginning
    of upkeep go on the stack.

    Args:
        whose: "yours" (controller's upkeep), "each" (each upkeep),
               "opponents" (opponents' upkeeps only).

    Returns:
        A TriggerCondition for upkeep events.
    """
    from ..events import BeginningOfUpkeepEvent

    def upkeep_filter(event: Event, source: Any) -> bool:
        active_player = getattr(event, 'player', None)
        controller = getattr(source, 'controller', None)

        if whose == "yours":
            return active_player == controller
        elif whose == "each":
            return True
        elif whose == "opponents":
            return active_player != controller and active_player is not None
        return True

    return TriggerCondition(
        event_type=BeginningOfUpkeepEvent,
        filter_func=upkeep_filter,
        source_requirement=None,
    )


def beginning_of_end_step(whose: str = "yours") -> TriggerCondition:
    """
    Create a trigger condition for "at the beginning of the end step" events.

    CR 513.1: The end step has no turn-based actions. Triggered abilities
    that trigger at the beginning of the end step go on the stack.

    Args:
        whose: "yours", "each", or "opponents".

    Returns:
        A TriggerCondition for end step events.
    """
    from ..events import BeginningOfEndStepEvent

    def end_step_filter(event: Event, source: Any) -> bool:
        active_player = getattr(event, 'player', None)
        controller = getattr(source, 'controller', None)

        if whose == "yours":
            return active_player == controller
        elif whose == "each":
            return True
        elif whose == "opponents":
            return active_player != controller and active_player is not None
        return True

    return TriggerCondition(
        event_type=BeginningOfEndStepEvent,
        filter_func=end_step_filter,
        source_requirement=None,
    )


def spell_cast(
    filter_func: Optional[Callable[[Event, Any], bool]] = None,
    source_requirement: str = "any"
) -> TriggerCondition:
    """
    Create a trigger condition for "casts a spell" events.

    CR 601.2a: To cast a spell, a player moves that card from where it is
    to the stack. Triggered abilities that trigger when a spell is cast
    trigger after this occurs.

    Args:
        filter_func: Optional filter for the spell (type, color, etc.).
        source_requirement: "self", "you_control", or "any".

    Returns:
        A TriggerCondition for spell cast events.
    """
    from ..events import SpellCastEvent

    return TriggerCondition(
        event_type=SpellCastEvent,
        filter_func=filter_func,
        source_requirement=source_requirement,
    )


def landfall() -> TriggerCondition:
    """
    Create a trigger condition for landfall (land enters under your control).

    Landfall is an ability word that indicates abilities that trigger
    whenever a land enters the battlefield under your control.

    Returns:
        A TriggerCondition for landfall events.
    """
    from ..events import EntersBattlefieldEvent

    def is_land_you_control(event: Event, source: Any) -> bool:
        permanent = getattr(event, 'permanent', None) or getattr(event, 'object', None)
        if permanent is None:
            return False

        # Check if it's a land
        card_types = getattr(permanent, 'card_types', [])
        if 'Land' not in card_types and 'land' not in card_types:
            return False

        # Check if it's under source's controller's control
        source_controller = getattr(source, 'controller', None)
        permanent_controller = getattr(permanent, 'controller', None)

        return source_controller is not None and source_controller == permanent_controller

    return TriggerCondition(
        event_type=EntersBattlefieldEvent,
        filter_func=is_land_you_control,
        source_requirement=None,
    )


def life_gained(
    filter_func: Optional[Callable[[Event, Any], bool]] = None
) -> TriggerCondition:
    """
    Create a trigger condition for "gains life" events.

    CR 119.6: Some triggered abilities trigger whenever a player gains life.

    Args:
        filter_func: Optional filter (can check amount, player, etc.).

    Returns:
        A TriggerCondition for life gain events.
    """
    from ..events import LifeGainedEvent

    return TriggerCondition(
        event_type=LifeGainedEvent,
        filter_func=filter_func,
        source_requirement=None,
    )


def life_lost(
    filter_func: Optional[Callable[[Event, Any], bool]] = None
) -> TriggerCondition:
    """
    Create a trigger condition for "loses life" events.

    Args:
        filter_func: Optional filter (can check amount, player, etc.).

    Returns:
        A TriggerCondition for life loss events.
    """
    from ..events import LifeLostEvent

    return TriggerCondition(
        event_type=LifeLostEvent,
        filter_func=filter_func,
        source_requirement=None,
    )


def counter_added(
    counter_type: Optional[str] = None
) -> TriggerCondition:
    """
    Create a trigger condition for "counter is placed" events.

    CR 122.6: Some triggered abilities trigger when counters are put
    on an object or player.

    Args:
        counter_type: If specified, only trigger for this type of counter
                     (e.g., "+1/+1", "loyalty", "charge").

    Returns:
        A TriggerCondition for counter events.
    """
    from ..events import CounterAddedEvent

    def counter_filter(event: Event, source: Any) -> bool:
        if counter_type is None:
            return True
        event_counter_type = getattr(event, 'counter_type', None)
        return event_counter_type == counter_type

    return TriggerCondition(
        event_type=CounterAddedEvent,
        filter_func=counter_filter if counter_type else None,
        source_requirement=None,
    )


# -----------------------------------------------------------------------------
# Trigger Manager
# -----------------------------------------------------------------------------

class TriggerManager:
    """
    Manages triggered abilities for the game.

    CR 603.2: Whenever a game event or game state matches a triggered
    ability's trigger event, that ability automatically triggers.

    CR 603.3: Once an ability has triggered, its controller puts it on
    the stack as an object the next time a player would receive priority.

    CR 603.3b: If multiple abilities have triggered since the last time
    a player received priority, the abilities are placed on the stack
    in APNAP order (Active Player, Non-Active Player).

    Attributes:
        game: Reference to the game state.
        registered_triggers: Map of event types to abilities that listen for them.
        pending_triggers: Triggers that have fired but not yet been put on stack.
    """

    def __init__(self, game: Any):
        """
        Initialize the trigger manager.

        Args:
            game: The game state object.
        """
        self.game: Any = game
        self.registered_triggers: Dict[Type[Event], List[TriggeredAbility]] = {}
        self.pending_triggers: List[Tuple[TriggeredAbility, Event]] = []

    def register(self, ability: TriggeredAbility) -> None:
        """
        Register a triggered ability to listen for events.

        CR 603.2: Triggered abilities automatically trigger when their
        trigger condition is met.

        Args:
            ability: The triggered ability to register.
        """
        event_type = ability.trigger_condition.event_type

        if event_type not in self.registered_triggers:
            self.registered_triggers[event_type] = []

        if ability not in self.registered_triggers[event_type]:
            self.registered_triggers[event_type].append(ability)

    def unregister(self, ability: TriggeredAbility) -> None:
        """
        Unregister a triggered ability.

        Called when the source leaves the battlefield or otherwise
        loses the ability.

        Args:
            ability: The triggered ability to unregister.
        """
        event_type = ability.trigger_condition.event_type

        if event_type in self.registered_triggers:
            if ability in self.registered_triggers[event_type]:
                self.registered_triggers[event_type].remove(ability)

        # Also remove from pending triggers
        self.pending_triggers = [
            (a, e) for a, e in self.pending_triggers if a != ability
        ]

    def on_event(self, event: Event) -> None:
        """
        Process an event and check all registered triggers.

        CR 603.2: When the game event matches a triggered ability's
        trigger condition, that ability automatically triggers.

        Args:
            event: The event that occurred.
        """
        event_type = type(event)

        # Check all abilities registered for this event type
        abilities = self.registered_triggers.get(event_type, [])

        for ability in abilities:
            if ability.check_trigger(event):
                # Add to pending triggers
                self.pending_triggers.append((ability, event))

                # Handle one-shot triggers
                if ability.one_shot:
                    self.unregister(ability)

    def put_triggers_on_stack(self) -> List[Any]:
        """
        Put all pending triggers on the stack in APNAP order.

        CR 603.3b: If multiple abilities have triggered, the active player
        puts all abilities they control on the stack in any order, then
        each other player in APNAP order does the same.

        The triggers that go on the stack FIRST will resolve LAST
        (stack is LIFO).

        Returns:
            List of AbilityOnStack objects that were put on the stack.
        """
        if not self.pending_triggers:
            return []

        stack_objects = []

        # Group triggers by controller
        triggers_by_controller: Dict[Any, List[Tuple[TriggeredAbility, Event]]] = {}

        for ability, event in self.pending_triggers:
            controller = ability.controller
            if controller not in triggers_by_controller:
                triggers_by_controller[controller] = []
            triggers_by_controller[controller].append((ability, event))

        # Get player order (APNAP - Active Player, Non-Active Player)
        player_order = self._get_apnap_order()

        # Active player's triggers go on stack first (resolve last)
        # Then other players in turn order
        for player in player_order:
            if player in triggers_by_controller:
                player_triggers = triggers_by_controller[player]

                # Player orders their own triggers
                # For now, use the order they were added (game should prompt player)
                ordered_triggers = self._order_triggers_for_player(player, player_triggers)

                for ability, event in ordered_triggers:
                    # Check intervening-if again before putting on stack
                    # CR 603.4: The condition is checked when the ability would
                    # be put on the stack
                    if ability.intervening_if is not None:
                        if not ability.intervening_if():
                            continue

                    # Get targets if required (game should prompt for targets)
                    targets = self._get_targets_for_ability(ability, event)

                    # Create and add to stack
                    stack_object = ability.create_stack_object(event, targets)
                    stack_objects.append(stack_object)

                    # Add to the game's stack
                    if hasattr(self.game, 'stack'):
                        self.game.stack.push(stack_object)

        # Clear pending triggers
        self.clear_pending()

        return stack_objects

    def _get_apnap_order(self) -> List[Any]:
        """
        Get players in APNAP (Active Player, Non-Active Player) order.

        CR 101.4: If multiple players would make choices and/or take actions
        simultaneously, the active player makes their choices first, then
        each other player in turn order.

        Returns:
            List of players in APNAP order.
        """
        if not hasattr(self.game, 'active_player') or not hasattr(self.game, 'players'):
            # Fallback: return all controllers from pending triggers
            controllers = []
            for ability, _ in self.pending_triggers:
                if ability.controller not in controllers:
                    controllers.append(ability.controller)
            return controllers

        active_player = self.game.active_player
        players = self.game.players

        # Find active player's index
        try:
            active_index = players.index(active_player)
        except (ValueError, AttributeError):
            return list(players)

        # Return players starting from active player in turn order
        return players[active_index:] + players[:active_index]

    def _order_triggers_for_player(
        self,
        player: Any,
        triggers: List[Tuple[TriggeredAbility, Event]]
    ) -> List[Tuple[TriggeredAbility, Event]]:
        """
        Allow a player to order their simultaneous triggers.

        CR 603.3b: Each player chooses the relative order of triggered
        abilities they control.

        Args:
            player: The player ordering their triggers.
            triggers: The triggers to order.

        Returns:
            The ordered list of triggers.
        """
        # If only one trigger, no ordering needed
        if len(triggers) <= 1:
            return triggers

        # In a full implementation, the game would prompt the player
        # For now, return in the order received (FIFO)
        # Triggers put on stack first resolve last, so this order means
        # earlier triggers resolve last

        # Check if game has a method to prompt for ordering
        if hasattr(self.game, 'prompt_trigger_order'):
            return self.game.prompt_trigger_order(player, triggers)

        return triggers

    def _get_targets_for_ability(
        self,
        ability: TriggeredAbility,
        event: Event
    ) -> List[Any]:
        """
        Get targets for a triggered ability.

        CR 603.3c: If a triggered ability has targets, the player who
        controls the ability chooses targets when they put the ability
        on the stack.

        Args:
            ability: The triggered ability.
            event: The triggering event.

        Returns:
            List of chosen targets.
        """
        if not ability.targets_required:
            return []

        # In a full implementation, the game would prompt the player
        # Check if game has a method to prompt for targets
        if hasattr(self.game, 'prompt_targets'):
            return self.game.prompt_targets(
                ability.controller,
                ability,
                event
            )

        return []

    def clear_pending(self) -> None:
        """
        Clear all pending triggers.

        Called after triggers have been put on the stack, or when
        the game state is reset.
        """
        self.pending_triggers.clear()

    def get_pending_count(self) -> int:
        """
        Get the number of pending triggers.

        Returns:
            The number of triggers waiting to be put on the stack.
        """
        return len(self.pending_triggers)

    def get_triggers_for_source(self, source: Any) -> List[TriggeredAbility]:
        """
        Get all triggered abilities from a specific source.

        Args:
            source: The source game object.

        Returns:
            List of triggered abilities with this source.
        """
        result = []
        for abilities in self.registered_triggers.values():
            for ability in abilities:
                if ability.source is source:
                    result.append(ability)
        return result

    def unregister_all_from_source(self, source: Any) -> None:
        """
        Unregister all triggered abilities from a source.

        Called when a permanent leaves the battlefield.

        Args:
            source: The source game object.
        """
        for event_type in list(self.registered_triggers.keys()):
            self.registered_triggers[event_type] = [
                ability for ability in self.registered_triggers[event_type]
                if ability.source is not source
            ]

        # Also remove from pending
        self.pending_triggers = [
            (ability, event) for ability, event in self.pending_triggers
            if ability.source is not source
        ]

    def cleanup_delayed_triggers(self) -> None:
        """
        Remove expired delayed triggered abilities during cleanup step.

        Called during the cleanup step (CR 514) to remove delayed triggers
        that were set to expire "at end of turn" or "until end of turn".
        """
        # Remove delayed triggers with "end_of_turn" duration
        for event_type in list(self.registered_triggers.keys()):
            self.registered_triggers[event_type] = [
                ability for ability in self.registered_triggers[event_type]
                if not (isinstance(ability, DelayedTriggeredAbility)
                       and ability.duration == "end_of_turn")
            ]

        # Also remove from pending
        self.pending_triggers = [
            (ability, event) for ability, event in self.pending_triggers
            if not (isinstance(ability, DelayedTriggeredAbility)
                   and ability.duration == "end_of_turn")
        ]


# -----------------------------------------------------------------------------
# Delayed Triggered Abilities (CR 603.7)
# -----------------------------------------------------------------------------

@dataclass
class DelayedTriggeredAbility(TriggeredAbility):
    """
    A delayed triggered ability created by another effect.

    CR 603.7: An effect may create a delayed triggered ability that can
    do something at a later time. A delayed triggered ability is created
    only once and triggers only once.

    CR 603.7a: Delayed triggered abilities created by resolution of
    spells and abilities trigger once and then are removed.

    Attributes:
        duration: When this delayed trigger expires ("end_of_turn",
                 "end_of_combat", "next_upkeep", etc.)
        created_by: The effect that created this delayed trigger.
    """
    duration: Optional[str] = None
    created_by: Optional[Any] = None

    def __post_init__(self):
        # Delayed triggers are always one-shot
        self.one_shot = True


# -----------------------------------------------------------------------------
# Reflexive Triggered Abilities (CR 603.12)
# -----------------------------------------------------------------------------

@dataclass
class ReflexiveTriggeredAbility(TriggeredAbility):
    """
    A reflexive triggered ability that triggers from the resolution of another ability.

    CR 603.12: A reflexive triggered ability triggers from actions taken
    during the resolution of the spell or ability that created it.
    It is put on the stack after that spell or ability resolves.

    Example: "When you do, draw a card" - triggers from choices made
    during resolution.
    """
    parent_ability: Optional[Any] = None  # The ability that created this


# -----------------------------------------------------------------------------
# State Triggered Abilities (CR 603.8)
# -----------------------------------------------------------------------------

@dataclass
class StateTriggeredAbility(TriggeredAbility):
    """
    A state-triggered ability that triggers when a game state is true.

    CR 603.8: Some triggered abilities trigger when a game state (such
    as a player controlling no permanents of a particular card type)
    is true, rather than triggering when an event occurs.

    CR 603.8a: A state-triggered ability triggers once each time its
    trigger condition is met, not continuously. It doesn't trigger
    again until the game state ceases to meet the condition, then
    meets it again.
    """
    state_check: Callable[[], bool] = field(default=lambda: False)
    _state_was_true: bool = field(default=False, repr=False)

    def check_state(self) -> bool:
        """
        Check if the state trigger should fire.

        Returns:
            True if the trigger should fire.
        """
        state_is_true = self.state_check()

        # Only trigger on transition from false to true
        should_trigger = state_is_true and not self._state_was_true

        # Update state tracking
        self._state_was_true = state_is_true

        if should_trigger:
            # Check intervening-if clause
            if self.intervening_if is not None:
                if not self.intervening_if():
                    return False

        return should_trigger


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------

def put_triggers_on_stack(game: Any) -> List[Any]:
    """
    Put all pending triggers on the stack for the given game.

    This is a convenience function that calls the TriggerManager's
    put_triggers_on_stack method.

    Args:
        game: The game state object with a trigger_manager attribute.

    Returns:
        List of AbilityOnStack objects that were put on the stack.
    """
    if hasattr(game, 'trigger_manager'):
        return game.trigger_manager.put_triggers_on_stack()
    if hasattr(game, 'triggers'):
        return game.triggers.put_triggers_on_stack()
    return []
