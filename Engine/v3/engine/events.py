"""
Event bus system for MTG triggered abilities and game state changes.

This module implements the event system that allows game components to
communicate state changes and enables triggered abilities to respond
to game events according to MTG rules.

Rule References:
- 603: Handling Triggered Abilities
- 613.7: Timestamp ordering for effects
- 614: Replacement Effects
- 615: Prevention Effects
"""

from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Set,
    Tuple,
)
from enum import Enum, auto
import time


# =============================================================================
# Type Aliases
# =============================================================================

ObjectId = int
PlayerId = int
Timestamp = int

# Type variable for event types
E = TypeVar('E', bound='Event')


# =============================================================================
# Base Event Class
# =============================================================================

@dataclass
class Event:
    """
    Base class for all events in the MTG engine.

    Attributes:
        timestamp: Monotonically increasing counter for event ordering.
                   Used for determining APNAP order and "as this happened" effects.
                   Per rule 613.7, timestamps determine the order of effects.
        source: The game object that caused this event (if any).
                Will be a GameObject in practice.
        cancelled: Whether this event has been cancelled by a replacement effect.
    """
    timestamp: int = field(default_factory=lambda: int(time.time_ns()))
    source: Optional[Any] = None  # Will be GameObject in practice
    cancelled: bool = False

    def cancel(self) -> None:
        """Mark this event as cancelled. Cancelled events are not processed."""
        self.cancelled = True

    def is_cancelled(self) -> bool:
        """Check if this event has been cancelled."""
        return self.cancelled


# =============================================================================
# Game Event Base Class
# =============================================================================

@dataclass
class GameEvent(Event):
    """
    Base class for game-specific events.

    All MTG game state changes should inherit from this class rather than
    Event directly, allowing for game-specific event handling.
    """
    pass


# =============================================================================
# Zone Change Events
# =============================================================================

@dataclass
class ZoneChangeEvent(GameEvent):
    """
    Event fired when a game object moves between zones.

    This is one of the most important events in MTG as many triggered
    abilities care about objects entering or leaving zones (ETB, dies,
    leaves the battlefield, etc.).

    Rule 400.7: An object that moves from one zone to another becomes a new
    object with no memory of its previous existence.

    Attributes:
        object: The game object that changed zones.
        from_zone: The zone the object left (None if entering from outside game).
        to_zone: The zone the object entered (None if leaving the game).
    """
    object: Any = None  # The GameObject moving
    from_zone: Optional[Any] = None  # Zone enum or Zone object
    to_zone: Optional[Any] = None  # Zone enum or Zone object

    def is_entering_battlefield(self) -> bool:
        """Check if this represents an object entering the battlefield."""
        from_zone_name = getattr(self.from_zone, 'name', str(self.from_zone))
        to_zone_name = getattr(self.to_zone, 'name', str(self.to_zone))
        return to_zone_name == 'BATTLEFIELD' and from_zone_name != 'BATTLEFIELD'

    def is_leaving_battlefield(self) -> bool:
        """Check if this represents an object leaving the battlefield."""
        from_zone_name = getattr(self.from_zone, 'name', str(self.from_zone))
        to_zone_name = getattr(self.to_zone, 'name', str(self.to_zone))
        return from_zone_name == 'BATTLEFIELD' and to_zone_name != 'BATTLEFIELD'

    def is_dying(self) -> bool:
        """
        Check if this represents a creature dying.

        Per rule 700.4, "dies" means a creature or planeswalker moving
        from the battlefield to the graveyard.
        """
        from_zone_name = getattr(self.from_zone, 'name', str(self.from_zone))
        to_zone_name = getattr(self.to_zone, 'name', str(self.to_zone))
        return from_zone_name == 'BATTLEFIELD' and to_zone_name == 'GRAVEYARD'


# =============================================================================
# Damage Events
# =============================================================================

@dataclass
class DamageEvent(GameEvent):
    """
    Event fired when damage is dealt.

    Rule 120: Damage is dealt as part of combat (rule 510) or as the result
    of a spell or ability.

    This covers both combat damage and non-combat damage (e.g., from spells
    or abilities). Triggered abilities like lifelink and deathtouch respond
    to damage events.

    Attributes:
        source: The object dealing the damage.
        target: The object or player receiving the damage.
        amount: The amount of damage dealt.
        is_combat: Whether this is combat damage.
        is_prevented: Whether the damage was prevented.
    """
    target: Any = None  # Player or GameObject receiving damage
    amount: int = 0
    is_combat: bool = False
    is_prevented: bool = False

    def was_lethal(self, target_toughness: int = 0) -> bool:
        """
        Check if this damage was lethal to the target.

        Note: Requires external context about target's toughness and
        damage already marked on it.
        """
        if self.is_prevented or self.amount <= 0:
            return False
        return self.amount >= target_toughness


# =============================================================================
# Life Total Events
# =============================================================================

@dataclass
class LifeChangeEvent(GameEvent):
    """
    Event fired when a player's life total changes.

    Rule 119: Life totals can change due to damage, life gain, life loss,
    or effects that set life to a specific number.

    Attributes:
        player: The player whose life total changed.
        amount: The change in life (positive for gain, negative for loss).
        old_total: The life total before the change.
        new_total: The life total after the change.
    """
    player: Any = None  # Player object
    amount: int = 0
    old_total: int = 0
    new_total: int = 0

    def is_life_gain(self) -> bool:
        """Check if this represents life gain."""
        return self.amount > 0

    def is_life_loss(self) -> bool:
        """Check if this represents life loss."""
        return self.amount < 0


# =============================================================================
# Spell and Ability Events
# =============================================================================

@dataclass
class SpellCastEvent(GameEvent):
    """
    Event fired when a spell is cast.

    Rule 601: Casting Spells. This triggers abilities like
    "whenever you cast a spell..." (prowess, storm, etc.)

    Attributes:
        spell: The spell object being cast (on the stack).
        controller: The player casting the spell.
    """
    spell: Any = None  # Spell object on the stack
    controller: Any = None  # Player casting the spell

    def is_creature_spell(self) -> bool:
        """Check if this is a creature spell."""
        if self.spell is None:
            return False
        types = getattr(self.spell, 'types', [])
        return 'CREATURE' in types or 'creature' in [str(t).lower() for t in types]

    def is_noncreature_spell(self) -> bool:
        """Check if this is a noncreature spell."""
        return not self.is_creature_spell()


@dataclass
class AbilityTriggeredEvent(GameEvent):
    """
    Event fired when a triggered ability triggers.

    Rule 603: Triggered abilities begin with "when," "whenever," or "at."
    They trigger based on game events or game states.

    This is used for tracking triggers and for abilities that care about
    other abilities triggering.

    Attributes:
        ability: The triggered ability that triggered.
        source: The permanent or object the ability is from.
    """
    ability: Any = None  # TriggeredAbility object


# =============================================================================
# Counter Events
# =============================================================================

@dataclass
class CounterAddedEvent(GameEvent):
    """
    Event fired when counters are added to a permanent.

    Rule 122: Counters are markers placed on an object or player that
    modify its characteristics and/or interact with a rule, ability,
    or effect.

    Attributes:
        permanent: The permanent receiving counters.
        counter_type: The type of counter being added (e.g., "+1/+1", "loyalty").
        amount: The number of counters added.
    """
    permanent: Any = None  # Permanent receiving counters
    counter_type: str = ""
    amount: int = 0


@dataclass
class CounterRemovedEvent(GameEvent):
    """
    Event fired when counters are removed from a permanent.

    Attributes:
        permanent: The permanent losing counters.
        counter_type: The type of counter being removed.
        amount: The number of counters removed.
    """
    permanent: Any = None  # Permanent losing counters
    counter_type: str = ""
    amount: int = 0


# =============================================================================
# Tap/Untap Events
# =============================================================================

@dataclass
class TapEvent(GameEvent):
    """
    Event fired when a permanent becomes tapped.

    Rule 701.21: To tap a permanent, turn it sideways from an upright position.

    Attributes:
        permanent: The permanent that was tapped.
    """
    permanent: Any = None  # The permanent being tapped


@dataclass
class UntapEvent(GameEvent):
    """
    Event fired when a permanent becomes untapped.

    Rule 701.22: To untap a permanent, rotate it back to an upright position.

    Attributes:
        permanent: The permanent that was untapped.
    """
    permanent: Any = None  # The permanent being untapped


# =============================================================================
# Combat Events
# =============================================================================

@dataclass
class AttacksEvent(GameEvent):
    """
    Event fired when a creature is declared as an attacker.

    Rule 508: Declare Attackers Step. Triggers "whenever ~ attacks" abilities.

    Note: This is fired during the declare attackers step, not when
    damage is dealt.

    Attributes:
        creature: The attacking creature.
        defending: The player or planeswalker being attacked.
    """
    creature: Any = None  # Attacking creature
    defending: Any = None  # Player or Planeswalker being attacked


@dataclass
class BlocksEvent(GameEvent):
    """
    Event fired when a creature is declared as a blocker.

    Rule 509: Declare Blockers Step. Triggers "whenever ~ blocks" abilities.

    Attributes:
        blocker: The blocking creature.
        attacker: The attacking creature being blocked.
    """
    blocker: Any = None  # Blocking creature
    attacker: Any = None  # Creature being blocked


@dataclass
class BecomesBlockedEvent(GameEvent):
    """
    Event fired when an attacking creature becomes blocked.

    Rule 509.1h: An attacking creature becomes blocked when a blocker
    is declared for it.

    Attributes:
        attacker_id: The object ID of the attacking creature.
        blocker_ids: List of object IDs of all creatures blocking this attacker.
    """
    attacker_id: ObjectId = 0
    blocker_ids: List[ObjectId] = field(default_factory=list)


@dataclass
class CombatDamageDealtEvent(GameEvent):
    """
    Event fired after combat damage is dealt.

    Rule 510: Combat Damage Step. Triggers "whenever combat damage is dealt"
    abilities.

    Attributes:
        is_first_strike: True if this is first strike damage, False for regular.
        damage_events: List of individual damage events from this combat step.
        attacking_player_id: The player who attacked this combat.
    """
    is_first_strike: bool = False
    damage_events: List[Any] = field(default_factory=list)
    attacking_player_id: PlayerId = 0


# =============================================================================
# Turn Structure Events
# =============================================================================

@dataclass
class StepBeginEvent(GameEvent):
    """
    Event fired when a step begins.

    Rule 500: Turn Structure. Many abilities trigger at the beginning
    of specific steps (e.g., "at the beginning of your upkeep").

    Attributes:
        step_type: The type of step beginning (e.g., UPKEEP, DRAW, COMBAT_DAMAGE).
        active_player_id: The active player during this step.
    """
    step_type: Any = None  # Step enum value
    active_player_id: PlayerId = 0


@dataclass
class StepEndEvent(GameEvent):
    """
    Event fired when a step ends.

    Attributes:
        step_type: The type of step ending.
    """
    step_type: Any = None  # Step enum value


@dataclass
class PhaseBeginEvent(GameEvent):
    """
    Event fired when a phase begins.

    Rule 500: Turn Structure. Some abilities trigger at the beginning
    of phases (e.g., "at the beginning of combat").

    Attributes:
        phase_type: The type of phase beginning (e.g., MAIN, COMBAT, END).
    """
    phase_type: Any = None  # Phase enum value


@dataclass
class PhaseEndEvent(GameEvent):
    """
    Event fired when a phase ends.

    Attributes:
        phase_type: The type of phase ending.
    """
    phase_type: Any = None  # Phase enum value


# =============================================================================
# Card Draw and Discard Events
# =============================================================================

@dataclass
class DrawEvent(GameEvent):
    """
    Event fired when a player draws one or more cards.

    Rule 121: Drawing a Card. The card is moved from the library to the
    player's hand. Triggers "whenever you draw a card" abilities.

    Per MTG rules, each card drawn is a separate event, but for efficiency
    we batch them when multiple cards are drawn simultaneously.

    Attributes:
        player: The player drawing cards.
        cards: List of cards drawn.
    """
    player: Any = None  # Player drawing
    cards: List[Any] = field(default_factory=list)  # Cards drawn

    @property
    def num_cards(self) -> int:
        """Return the number of cards drawn."""
        return len(self.cards)


@dataclass
class DiscardEvent(GameEvent):
    """
    Event fired when a player discards one or more cards.

    Rule 701.8: To discard a card, move it from the hand to the graveyard.
    Triggers "whenever you discard a card" abilities.

    Attributes:
        player: The player discarding cards.
        cards: List of cards discarded.
    """
    player: Any = None  # Player discarding
    cards: List[Any] = field(default_factory=list)  # Cards discarded

    @property
    def num_cards(self) -> int:
        """Return the number of cards discarded."""
        return len(self.cards)


# =============================================================================
# Event Bus Implementation
# =============================================================================

# Type alias for event callbacks
EventCallback = Callable[[Event], None]
ReplacementHandler = Callable[[Event], Optional[Event]]


class EventBus:
    """
    Central event dispatcher for the MTG engine.

    The EventBus implements the observer pattern, allowing game components
    to subscribe to specific event types and receive notifications when
    those events occur.

    This is crucial for:
    - Triggered abilities (listening for specific game events per rule 603)
    - State-based actions (monitoring game state changes per rule 704)
    - Replacement effects (intercepting and modifying events per rule 614)
    - Prevention effects (preventing damage and other effects per rule 615)
    - Game logging and replay systems

    Thread Safety: This implementation is NOT thread-safe. For concurrent
    access, external synchronization is required.
    """

    def __init__(self) -> None:
        """Initialize an empty event bus."""
        # Map from event type to list of subscribers
        self._subscribers: Dict[Type[Event], List[EventCallback]] = {}

        # Replacement effect handlers (called before normal subscribers)
        # Per rule 614, replacement effects modify events before they happen
        self._replacement_handlers: Dict[Type[Event], List[ReplacementHandler]] = {}

        # Event history for debugging, replay, and "this turn" tracking
        self._event_history: List[Event] = []
        self._history_enabled: bool = False
        self._max_history_size: int = 1000

        # Timestamp counter for event ordering (rule 613.7)
        self._next_timestamp: int = 0

    def subscribe(
        self,
        event_type: Type[E],
        callback: Callable[[E], None]
    ) -> None:
        """
        Subscribe to events of a specific type.

        The callback will be invoked when events of this type or any
        subtype are emitted.

        Args:
            event_type: The type of event to subscribe to.
            callback: Function to call when the event occurs.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(
        self,
        event_type: Type[E],
        callback: Callable[[E], None]
    ) -> bool:
        """
        Unsubscribe from events of a specific type.

        Args:
            event_type: The type of event to unsubscribe from.
            callback: The callback to remove.

        Returns:
            True if the callback was found and removed, False otherwise.
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                return True
            except ValueError:
                pass
        return False

    def subscribe_replacement(
        self,
        event_type: Type[E],
        handler: Callable[[E], Optional[E]]
    ) -> None:
        """
        Subscribe a replacement effect handler.

        Rule 614: Replacement effects modify events as they happen.
        They use "instead" language and apply before the original
        event would occur.

        The handler receives the event and returns either:
        - The same event (unmodified)
        - A modified event (replacement occurred)
        - None (to cancel the event entirely)

        Args:
            event_type: The type of event to handle.
            handler: Function that may modify or cancel the event.
        """
        if event_type not in self._replacement_handlers:
            self._replacement_handlers[event_type] = []
        if handler not in self._replacement_handlers[event_type]:
            self._replacement_handlers[event_type].append(handler)

    def unsubscribe_replacement(
        self,
        event_type: Type[E],
        handler: Callable[[E], Optional[E]]
    ) -> bool:
        """
        Remove a replacement effect handler.

        Args:
            event_type: The type of event.
            handler: The handler to remove.

        Returns:
            True if the handler was found and removed, False otherwise.
        """
        if event_type in self._replacement_handlers:
            try:
                self._replacement_handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False

    def emit(self, event: Event) -> Event:
        """
        Emit an event to all subscribers.

        The event processing order is:
        1. Assign timestamp for ordering
        2. Apply replacement effect handlers
        3. If not cancelled, notify all regular subscribers
        4. Record in history if enabled

        Args:
            event: The event to emit.

        Returns:
            The event (possibly modified by replacement effects).
        """
        # Assign timestamp for proper ordering (rule 613.7)
        event.timestamp = self._next_timestamp
        self._next_timestamp += 1

        # Apply replacement effects first (rule 614)
        event = self._apply_replacements(event)

        # Don't process cancelled events
        if event.is_cancelled():
            if self._history_enabled:
                self._record_event(event)
            return event

        # Record in history if enabled
        if self._history_enabled:
            self._record_event(event)

        # Get all applicable subscribers
        callbacks = self._get_subscribers_for_event(event)

        # Call each subscriber
        for callback in callbacks:
            if event.is_cancelled():
                break
            try:
                callback(event)
            except Exception as e:
                # Log error but continue processing other subscribers
                # In production, this should use proper logging
                print(f"Error in event handler: {e}")

        return event

    def emit_and_wait(self, event: Event) -> Event:
        """
        Emit an event and wait for replacement effects to process it.

        This method is specifically for events that may be replaced or
        modified, such as:
        - Damage that might be prevented (rule 615)
        - Zone changes that might be replaced (e.g., "if would die, instead...")
        - Life gain/loss that might be modified

        Unlike emit(), this method emphasizes the replacement effect
        processing and returns the final (possibly replaced) event
        for the caller to handle.

        Args:
            event: The event to emit.

        Returns:
            The final event after all replacement effects have been applied.
        """
        # Assign timestamp
        event.timestamp = self._next_timestamp
        self._next_timestamp += 1

        # Apply replacement effects (may completely replace the event)
        final_event = self._apply_replacements(event)

        # If the event was cancelled, return it without notifying subscribers
        if final_event.is_cancelled():
            if self._history_enabled:
                self._record_event(final_event)
            return final_event

        # Record in history
        if self._history_enabled:
            self._record_event(final_event)

        # Notify all subscribers
        callbacks = self._get_subscribers_for_event(final_event)
        for callback in callbacks:
            if final_event.is_cancelled():
                break
            try:
                callback(final_event)
            except Exception as e:
                print(f"Error in event handler: {e}")

        return final_event

    def _apply_replacements(self, event: Event) -> Event:
        """
        Apply all applicable replacement effect handlers to an event.

        Rule 614.5: If multiple replacement effects would apply, the
        affected player or controller of the affected object chooses
        the order. This implementation applies them in registration order.

        Args:
            event: The event to process.

        Returns:
            The event after all replacement effects have been applied.
        """
        current_event = event
        event_type = type(event)

        # Check exact type match first
        if event_type in self._replacement_handlers:
            for handler in self._replacement_handlers[event_type]:
                result = handler(current_event)
                if result is None:
                    current_event.cancel()
                    return current_event
                current_event = result
                if current_event.is_cancelled():
                    return current_event

        # Check parent type matches (for handlers registered on base classes)
        for parent_type in event_type.__mro__[1:]:
            if parent_type in self._replacement_handlers and parent_type != object:
                for handler in self._replacement_handlers[parent_type]:
                    result = handler(current_event)
                    if result is None:
                        current_event.cancel()
                        return current_event
                    current_event = result
                    if current_event.is_cancelled():
                        return current_event

        return current_event

    def _get_subscribers_for_event(self, event: Event) -> List[EventCallback]:
        """
        Get all subscribers that should receive this event.

        This includes exact type matches and subscribers registered
        for parent event types.

        Args:
            event: The event being emitted.

        Returns:
            List of callbacks to invoke.
        """
        callbacks: List[EventCallback] = []
        event_type = type(event)
        seen: Set[EventCallback] = set()

        # Exact type subscribers
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                if callback not in seen:
                    callbacks.append(callback)
                    seen.add(callback)

        # Parent type subscribers (for subscribing to base classes like GameEvent)
        for parent_type in event_type.__mro__[1:]:
            if parent_type in self._subscribers and parent_type != object:
                for callback in self._subscribers[parent_type]:
                    if callback not in seen:
                        callbacks.append(callback)
                        seen.add(callback)

        return callbacks

    def _record_event(self, event: Event) -> None:
        """Record an event in the history."""
        self._event_history.append(event)

        # Trim history if it exceeds max size
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]

    def enable_history(self, enabled: bool = True, max_size: int = 1000) -> None:
        """
        Enable or disable event history recording.

        History is useful for:
        - "This turn" tracking for abilities
        - Replay and debugging
        - UI updates showing recent events

        Args:
            enabled: Whether to record events.
            max_size: Maximum number of events to keep in history.
        """
        self._history_enabled = enabled
        self._max_history_size = max_size

    def get_history(
        self,
        event_type: Optional[Type[Event]] = None,
        since_timestamp: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Get the event history, optionally filtered.

        Args:
            event_type: Filter to only events of this type (and subtypes).
            since_timestamp: Only include events after this timestamp.
            limit: Maximum number of events to return.

        Returns:
            List of recorded events matching the filters.
        """
        result = self._event_history.copy()

        if event_type is not None:
            result = [e for e in result if isinstance(e, event_type)]

        if since_timestamp is not None:
            result = [e for e in result if e.timestamp >= since_timestamp]

        if limit is not None:
            result = result[-limit:]

        return result

    def clear_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()

    def clear_all_subscribers(self) -> None:
        """
        Remove all subscribers and replacement handlers.

        Useful for testing or game reset.
        """
        self._subscribers.clear()
        self._replacement_handlers.clear()

    def get_subscriber_count(self, event_type: Optional[Type[Event]] = None) -> int:
        """
        Get the number of subscribers.

        Args:
            event_type: If provided, count only subscribers to this type.
                       If None, count all subscribers.

        Returns:
            Number of subscribers.
        """
        if event_type is not None:
            return len(self._subscribers.get(event_type, []))

        total = sum(len(subs) for subs in self._subscribers.values())
        return total

    def get_current_timestamp(self) -> int:
        """Get the current timestamp value (next event's timestamp)."""
        return self._next_timestamp


# =============================================================================
# Additional Game Events (for game.py compatibility)
# =============================================================================

@dataclass
class TurnStartEvent(GameEvent):
    """Emitted when a turn begins."""
    turn_number: int = 0
    active_player_id: PlayerId = 0


@dataclass
class TurnEndEvent(GameEvent):
    """Emitted when a turn ends."""
    turn_number: int = 0
    active_player_id: PlayerId = 0


@dataclass
class GameStartEvent(GameEvent):
    """Emitted when a game starts."""
    player_ids: List[PlayerId] = field(default_factory=list)


@dataclass
class GameEndedEvent(GameEvent):
    """Emitted when a game ends."""
    winner_id: Optional[PlayerId] = None
    reason: str = ""
    is_draw: bool = False


@dataclass
class PlayerLostEvent(GameEvent):
    """Emitted when a player loses."""
    player_id: PlayerId = 0
    reason: str = ""


@dataclass
class PlayerWonEvent(GameEvent):
    """Emitted when a player wins."""
    player_id: PlayerId = 0
    reason: str = ""


@dataclass
class LandPlayedEvent(GameEvent):
    """Emitted when a land is played."""
    land_id: ObjectId = 0
    player_id: PlayerId = 0


@dataclass
class EntersBattlefieldEvent(GameEvent):
    """Emitted when an object enters the battlefield."""
    object_id: ObjectId = 0
    from_zone: str = ""


@dataclass
class DestroyEvent(GameEvent):
    """Emitted when a permanent is destroyed."""
    permanent_id: ObjectId = 0


@dataclass
class ExileEvent(GameEvent):
    """Emitted when a permanent is exiled."""
    object_id: ObjectId = 0
    from_zone: str = ""


@dataclass
class SacrificeEvent(GameEvent):
    """Emitted when a permanent is sacrificed."""
    permanent_id: ObjectId = 0
    player_id: PlayerId = 0


@dataclass
class TokenCreatedEvent(GameEvent):
    """Emitted when a token is created."""
    token_id: ObjectId = 0
    token_name: str = ""
    controller_id: PlayerId = 0


@dataclass
class DiesEvent(GameEvent):
    """Emitted when a creature dies (goes from battlefield to graveyard)."""
    permanent_id: ObjectId = 0
    permanent: Any = None


@dataclass
class LeavesPlayEvent(GameEvent):
    """Emitted when a permanent leaves the battlefield."""
    permanent_id: ObjectId = 0
    destination_zone: str = ""


@dataclass
class ManaAddedEvent(GameEvent):
    """Emitted when mana is added to a player's mana pool."""
    player_id: PlayerId = 0
    color: Any = None  # Color enum
    amount: int = 1
    source_id: ObjectId = 0


# Aliases for compatibility
PhaseStartEvent = PhaseBeginEvent
StepStartEvent = StepBeginEvent
DrawCardEvent = DrawEvent
LeavesBattlefieldEvent = LeavesPlayEvent


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Type aliases
    'ObjectId',
    'PlayerId',
    'Timestamp',
    'EventCallback',
    'ReplacementHandler',

    # Base classes
    'Event',
    'GameEvent',

    # Zone change events
    'ZoneChangeEvent',
    'EntersBattlefieldEvent',
    'ExileEvent',

    # Damage events
    'DamageEvent',

    # Life events
    'LifeChangeEvent',

    # Spell/ability events
    'SpellCastEvent',
    'AbilityTriggeredEvent',

    # Counter events
    'CounterAddedEvent',
    'CounterRemovedEvent',

    # Tap/untap events
    'TapEvent',
    'UntapEvent',

    # Mana events
    'ManaAddedEvent',

    # Combat events
    'AttacksEvent',
    'BlocksEvent',
    'BecomesBlockedEvent',
    'CombatDamageDealtEvent',

    # Turn structure events
    'TurnStartEvent',
    'TurnEndEvent',
    'StepBeginEvent',
    'StepEndEvent',
    'StepStartEvent',
    'PhaseBeginEvent',
    'PhaseEndEvent',
    'PhaseStartEvent',

    # Card events
    'DrawEvent',
    'DrawCardEvent',
    'DiscardEvent',

    # Game events
    'GameStartEvent',
    'GameEndedEvent',
    'PlayerLostEvent',
    'PlayerWonEvent',
    'LandPlayedEvent',
    'DestroyEvent',
    'SacrificeEvent',
    'TokenCreatedEvent',
    'DiesEvent',
    'LeavesPlayEvent',
    'LeavesBattlefieldEvent',

    # Event bus
    'EventBus',
]
