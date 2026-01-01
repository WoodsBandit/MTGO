"""
MTG Stack Implementation per Comprehensive Rules 405 and 608.

CR 405 - The Stack
CR 608 - Resolving Spells and Abilities

This module provides:
- StackObject: Base class for all objects on the stack
- SpellOnStack: Represents a spell on the stack
- AbilityOnStack: Represents a triggered or activated ability on the stack
- Stack: The stack zone itself with LIFO ordering
- Helper functions for creating stack objects
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Iterator, TYPE_CHECKING
from abc import ABC, abstractmethod

from .types import Zone, AbilityType, PlayerId, ObjectId

if TYPE_CHECKING:
    from .game import Game
    from .objects import Spell, StackedAbility, Target


# =============================================================================
# Stack Object Base Classes
# =============================================================================

@dataclass
class StackObject(ABC):
    """
    Base class for objects on the stack per CR 405.1.

    CR 405.1: When a spell is cast, the physical card is put on the stack.
    When an ability is activated or triggers, it goes on the stack without
    any card associated with it.

    Attributes:
        object_id: Unique identifier for this stack object
        source: The GameObject that is the source of this spell/ability
        controller: The Player who controls this object on the stack
        targets: List of targets chosen for this spell/ability
        timestamp: When this object was put on the stack (for ordering)
    """
    object_id: int
    source: Any  # GameObject - the source of this spell/ability
    controller: Any  # Player - who controls this object on the stack
    targets: List[Any] = field(default_factory=list)
    timestamp: int = 0

    @abstractmethod
    def get_description(self) -> str:
        """Return a human-readable description of this stack object."""
        pass

    @abstractmethod
    def is_spell(self) -> bool:
        """Return True if this is a spell, False if it's an ability."""
        pass


@dataclass
class SpellOnStack(StackObject):
    """
    A spell on the stack per CR 405.1 and CR 112.1.

    CR 112.1: A spell is a card on the stack. As the first step of being cast,
    the card becomes a spell and is moved to the stack.

    CR 112.1a: A copy of a spell is also a spell, even if it has no card
    associated with it.

    Attributes:
        card: The Card object being cast (None for copies without cards)
        modes: List of chosen mode indices for modal spells (CR 700.2)
        x_value: The chosen value of X if the spell has X in its cost
        is_permanent_spell: True for creature, artifact, enchantment,
                           planeswalker, and battle spells
        is_copy: True if this is a copy of a spell (CR 707.10)
    """
    card: Any = None  # Card object being cast
    modes: List[int] = field(default_factory=list)  # Chosen modes for modal spells
    x_value: Optional[int] = None  # Value of X if spell has X in cost
    is_permanent_spell: bool = False  # Permanents go to battlefield on resolution
    is_copy: bool = False  # Copies don't have associated cards (CR 707.10)

    def get_description(self) -> str:
        """Return description of the spell."""
        if self.card:
            card_name = getattr(self.card, 'name', None)
            if card_name is None and hasattr(self.card, 'characteristics'):
                card_name = getattr(self.card.characteristics, 'name', 'Unknown Spell')
            card_name = card_name or 'Unknown Spell'
        else:
            card_name = 'Unknown Spell'

        copy_text = " (copy)" if self.is_copy else ""
        x_text = f" (X={self.x_value})" if self.x_value is not None else ""
        return f"{card_name}{copy_text}{x_text}"

    def is_spell(self) -> bool:
        """Spells return True."""
        return True


@dataclass
class AbilityOnStack(StackObject):
    """
    An ability on the stack per CR 405.1 and CR 113.

    CR 113.3a: Activated abilities have a cost and an effect.
    They are written as "[Cost]: [Effect]."

    CR 113.3c: Triggered abilities have a trigger condition and an effect.
    They are written as "When/Whenever/At [trigger condition], [effect]."

    Attributes:
        ability_type: Either "triggered" or "activated"
        effect_text: Text describing the ability's effect
        trigger_event: For triggered abilities, the event that caused the trigger
    """
    ability_type: str = "triggered"  # "triggered" or "activated"
    effect_text: str = ""  # Text describing the effect
    trigger_event: Optional[Any] = None  # For triggered abilities

    def get_description(self) -> str:
        """Return description of the ability."""
        if self.source:
            source_name = getattr(self.source, 'name', None)
            if source_name is None and hasattr(self.source, 'characteristics'):
                source_name = getattr(self.source.characteristics, 'name', 'Unknown Source')
            source_name = source_name or 'Unknown Source'
        else:
            source_name = 'Unknown Source'

        return f"{self.ability_type.capitalize()} ability of {source_name}: {self.effect_text}"

    def is_spell(self) -> bool:
        """Abilities return False."""
        return False


# =============================================================================
# Stack Zone Class
# =============================================================================

class Stack:
    """
    The stack zone per CR 405.

    CR 405.1: The stack is a zone. Spells and abilities are put on the stack
    while waiting to resolve.

    CR 405.2: The stack keeps track of the order that spells and abilities
    were added to it. Each time an object is put on the stack, it's put on
    top of all objects already there.

    CR 405.5: When all players pass in succession, the top (last-added)
    spell or ability on the stack resolves.

    CR 405.6: Some things that happen during the game don't use the stack.
    (State-based actions, mana abilities, special actions)

    Attributes:
        objects: List of StackObjects, with index 0 being bottom of stack
        game: Reference to the Game object for resolution
        _next_timestamp: Counter for assigning timestamps
    """

    def __init__(self, game: Any = None):
        """
        Initialize the stack.

        Args:
            game: Reference to the Game object
        """
        self.objects: List[StackObject] = []
        self.game: Any = game
        self._next_timestamp: int = 0

    def push(self, obj: StackObject) -> None:
        """
        Add an object to the top of the stack per CR 405.2.

        CR 405.2: Each time an object is put on the stack, it's put on top
        of all objects already there.

        Args:
            obj: The StackObject to add to the stack
        """
        obj.timestamp = self._next_timestamp
        self._next_timestamp += 1
        self.objects.append(obj)

    def pop(self) -> Optional[StackObject]:
        """
        Remove and return the top object from the stack.

        Returns:
            The top StackObject, or None if the stack is empty
        """
        if self.objects:
            return self.objects.pop()
        return None

    def top(self) -> Optional[StackObject]:
        """
        Peek at the top object without removing it.

        Returns:
            The top StackObject, or None if the stack is empty
        """
        if self.objects:
            return self.objects[-1]
        return None

    def is_empty(self) -> bool:
        """
        Check if the stack is empty.

        Returns:
            True if the stack has no objects
        """
        return len(self.objects) == 0

    def __len__(self) -> int:
        """Return the number of objects on the stack."""
        return len(self.objects)

    def __iter__(self) -> Iterator[StackObject]:
        """
        Iterate from top to bottom of stack.

        This matches the order in which objects would resolve
        (top of stack resolves first).
        """
        return reversed(self.objects).__iter__()

    def check_targets_legal(self, obj: StackObject) -> bool:
        """
        Check if an object has at least one legal target per CR 608.2b.

        CR 608.2b: If the spell or ability specifies targets, it checks whether
        the targets are still legal. A target that's no longer in the zone it
        was in when it was targeted is illegal. A target is also illegal if it's
        protected from qualities of the source, or if the targeting was otherwise
        illegal.

        Args:
            obj: The StackObject to check

        Returns:
            True if object has no targets, or has at least one legal target.
            False if all targets are illegal (spell/ability will fizzle).
        """
        if not obj.targets:
            # No targets means we don't need to check - always legal
            return True

        # Count legal targets
        legal_count = 0
        for target in obj.targets:
            if self._is_target_legal(target, obj):
                legal_count += 1

        # CR 608.2b: If all targets are illegal, the spell/ability doesn't resolve
        return legal_count > 0

    def _is_target_legal(self, target: Any, stack_obj: StackObject) -> bool:
        """
        Check if a single target is still legal.

        A target is illegal if:
        - It no longer exists (left the game)
        - It changed zones since being targeted
        - It has protection from the source's qualities
        - It has hexproof and is controlled by an opponent
        - It has shroud
        - It otherwise doesn't meet targeting requirements

        Args:
            target: The target to check
            stack_obj: The stack object doing the targeting

        Returns:
            True if the target is legal, False otherwise
        """
        # Check if target still exists
        if target is None:
            return False

        # If target has its own is_legal method (Target objects from objects.py)
        if hasattr(target, 'is_legal'):
            return target.is_legal(self.game)

        # Check for zone change
        if hasattr(target, 'zone') and hasattr(target, 'targeted_in_zone'):
            if target.zone != target.targeted_in_zone:
                return False

        # Check for shroud (can't be targeted at all)
        if hasattr(target, 'has_shroud'):
            if callable(target.has_shroud):
                if target.has_shroud():
                    return False
            elif target.has_shroud:
                return False

        # Check for hexproof (can't be targeted by opponents)
        if hasattr(target, 'has_hexproof'):
            has_hexproof = target.has_hexproof() if callable(target.has_hexproof) else target.has_hexproof
            if has_hexproof:
                target_controller = getattr(target, 'controller', None) or getattr(target, 'controller_id', None)
                source_controller = stack_obj.controller
                if hasattr(source_controller, 'player_id'):
                    source_controller = source_controller.player_id
                if target_controller != source_controller:
                    return False

        # Check for protection
        if hasattr(target, 'has_protection_from'):
            if target.has_protection_from(stack_obj.source):
                return False

        # Check if object is still a valid game object
        if hasattr(target, 'is_valid_target'):
            return target.is_valid_target()

        return True

    def fizzle(self, obj: StackObject) -> None:
        """
        Remove a spell or ability from the stack without resolving per CR 608.2b.

        CR 608.2b: If all its targets are now illegal, the spell or ability
        doesn't resolve. It's removed from the stack and, if it's a spell,
        put into its owner's graveyard.

        Note: Copies of spells cease to exist instead of going to graveyard.

        Args:
            obj: The StackObject that fizzled
        """
        # Remove from stack if present
        if obj in self.objects:
            self.objects.remove(obj)

        # If it's a spell (not a copy), put the card in owner's graveyard
        if isinstance(obj, SpellOnStack) and not obj.is_copy:
            if obj.card:
                self._move_to_graveyard(obj.card, obj.controller)

    def _move_to_graveyard(self, card: Any, controller: Any) -> None:
        """
        Move a card to its owner's graveyard.

        CR 400.3: If an object would go to any library, graveyard, or hand
        other than its owner's, it goes to its owner's corresponding zone.

        Args:
            card: The card to move
            controller: The controller of the spell (owner may differ)
        """
        if self.game:
            # Get owner from card
            owner_id = getattr(card, 'owner_id', None) or getattr(card, 'owner', None)

            # Try using game's zone management
            if hasattr(self.game, 'zones') and hasattr(self.game.zones, 'graveyards'):
                if owner_id is not None:
                    self.game.zones.graveyards[owner_id].add(card)
                    if hasattr(card, 'zone'):
                        card.zone = Zone.GRAVEYARD
                    return

            # Try using game's move method
            if hasattr(self.game, 'move_to_graveyard'):
                self.game.move_to_graveyard(card)
                return

        # Fallback: direct manipulation
        if hasattr(card, 'owner') and hasattr(card.owner, 'graveyard'):
            card.owner.graveyard.append(card)
            if hasattr(card, 'zone'):
                card.zone = Zone.GRAVEYARD

    def _move_to_battlefield(self, card: Any, controller: Any, spell: SpellOnStack) -> None:
        """
        Move a permanent card to the battlefield under controller's control.

        CR 608.3: If the object that's resolving is a permanent spell, its
        resolution involves a single action: the permanent card becomes a
        permanent on the battlefield under the control of the spell's controller.

        Args:
            card: The permanent card to put onto battlefield
            controller: The player who will control the permanent
            spell: The spell that is resolving (for characteristics)
        """
        if self.game:
            # Import here to avoid circular imports
            from .events import EntersBattlefieldEvent
            from .objects import Permanent

            # Get controller ID
            controller_id = controller
            if hasattr(controller, 'player_id'):
                controller_id = controller.player_id

            owner_id = getattr(card, 'owner_id', controller_id)

            # Create permanent from spell
            characteristics = getattr(spell, 'characteristics', None)
            if characteristics is None and hasattr(card, 'characteristics'):
                characteristics = card.characteristics

            permanent = Permanent(
                object_id=spell.object_id,
                owner_id=owner_id,
                controller_id=controller_id,
                characteristics=characteristics,
                zone=Zone.BATTLEFIELD,
                timestamp=self._next_timestamp,
                entered_battlefield_this_turn=True
            )

            # Add to battlefield via zone management
            if hasattr(self.game, 'zones') and hasattr(self.game.zones, 'battlefield'):
                self.game.zones.battlefield.add(permanent)

            # Emit enters battlefield event
            if hasattr(self.game, 'events'):
                self.game.events.emit(EntersBattlefieldEvent(
                    object_id=permanent.object_id,
                    from_zone=Zone.STACK,
                    to_zone=Zone.BATTLEFIELD
                ))
            return

        # Fallback: direct manipulation
        if hasattr(controller, 'battlefield'):
            controller.battlefield.append(card)
            if hasattr(card, 'zone'):
                card.zone = Zone.BATTLEFIELD
            if hasattr(card, 'controller'):
                card.controller = controller

    def resolve_top(self) -> bool:
        """
        Resolve the top object on the stack per CR 608.

        CR 608.1: Each resolved spell and ability is resolved in the order
        the instructions are written on it.

        CR 608.2: If the object that's resolving is an instant spell, a
        sorcery spell, or an ability, its resolution may involve several steps.

        CR 608.2b: If the spell or ability specifies targets, it checks
        whether the targets are still legal.

        CR 608.3: If the object that's resolving is a permanent spell, its
        resolution involves a single action: the permanent card becomes a
        permanent on the battlefield.

        Returns:
            True if resolution succeeded
            False if fizzled (all targets illegal) or stack was empty
        """
        obj = self.top()
        if obj is None:
            return False

        # CR 608.2b: Check if targets are still legal
        if obj.targets and not self.check_targets_legal(obj):
            # All targets are illegal - fizzle
            self.fizzle(obj)
            return False

        # Remove from stack before resolution
        self.pop()

        # Get list of still-legal targets for resolution
        legal_targets = [t for t in obj.targets if self._is_target_legal(t, obj)]

        # Resolve based on type
        if isinstance(obj, SpellOnStack):
            return self._resolve_spell(obj, legal_targets)
        elif isinstance(obj, AbilityOnStack):
            return self._resolve_ability(obj, legal_targets)

        return True

    def _resolve_spell(self, spell: SpellOnStack, legal_targets: List[Any]) -> bool:
        """
        Resolve a spell per CR 608.2 and 608.3.

        CR 608.2c: The controller of the spell follows its instructions in
        the order written.

        CR 608.2d: If an effect requires information from the game, it uses
        the current information.

        CR 608.2g: If an effect requires a target and there are no legal
        targets, that part of the effect does nothing.

        CR 608.2k: Instant and sorcery spells are put into owner's graveyard
        after resolution.

        CR 608.3: Permanent spells become permanents on the battlefield.

        Args:
            spell: The spell to resolve
            legal_targets: List of targets that are still legal

        Returns:
            True if resolution completed successfully
        """
        if spell.is_permanent_spell:
            # CR 608.3: Permanent spell becomes a permanent on the battlefield
            if spell.card and not spell.is_copy:
                self._move_to_battlefield(spell.card, spell.controller, spell)
            # Copies of permanent spells still create tokens/permanents
            # This would be handled by the game engine
        else:
            # CR 608.2: Execute instant/sorcery effects
            self._execute_spell_effects(spell, legal_targets)

            # CR 608.2k: Put instant/sorcery in graveyard after resolution
            if spell.card and not spell.is_copy:
                self._move_to_graveyard(spell.card, spell.controller)

        return True

    def _execute_spell_effects(self, spell: SpellOnStack, legal_targets: List[Any]) -> None:
        """
        Execute the effects of an instant or sorcery spell.

        CR 608.2c: The controller follows instructions in order written.

        CR 608.2g: Parts of the effect that require illegal targets do nothing.

        Args:
            spell: The spell being resolved
            legal_targets: Targets that are still legal
        """
        # Build resolution context
        resolve_context = {
            'controller': spell.controller,
            'targets': legal_targets,
            'modes': spell.modes,
            'x_value': spell.x_value,
            'game': self.game,
            'source': spell.source,
        }

        # Try card's resolve method first
        if spell.card and hasattr(spell.card, 'resolve'):
            spell.card.resolve(resolve_context)
        # Delegate to game engine if available
        elif self.game and hasattr(self.game, 'resolve_spell'):
            self.game.resolve_spell(spell, legal_targets)

    def _resolve_ability(self, ability: AbilityOnStack, legal_targets: List[Any]) -> bool:
        """
        Resolve an ability per CR 608.2.

        CR 608.2c: Follow instructions in order.

        CR 608.2g: Parts requiring illegal targets do nothing.

        Args:
            ability: The ability to resolve
            legal_targets: Targets that are still legal

        Returns:
            True if resolution completed
        """
        self._execute_ability_effects(ability, legal_targets)
        return True

    def _execute_ability_effects(self, ability: AbilityOnStack, legal_targets: List[Any]) -> None:
        """
        Execute the effects of an ability.

        Args:
            ability: The ability being resolved
            legal_targets: Targets that are still legal
        """
        # Build resolution context
        resolve_context = {
            'controller': ability.controller,
            'targets': legal_targets,
            'trigger_event': ability.trigger_event,
            'effect_text': ability.effect_text,
            'game': self.game,
            'source': ability.source,
        }

        # Try source's resolve_ability method
        if ability.source and hasattr(ability.source, 'resolve_ability'):
            ability.source.resolve_ability(resolve_context)
        # Delegate to game engine if available
        elif self.game and hasattr(self.game, 'resolve_ability'):
            self.game.resolve_ability(ability, legal_targets)

    def get_objects_controlled_by(self, player: Any) -> List[StackObject]:
        """
        Get all stack objects controlled by a specific player.

        Args:
            player: The player to check (can be Player object or player_id)

        Returns:
            List of StackObjects controlled by that player
        """
        player_id = player
        if hasattr(player, 'player_id'):
            player_id = player.player_id

        result = []
        for obj in self.objects:
            obj_controller = obj.controller
            if hasattr(obj_controller, 'player_id'):
                obj_controller = obj_controller.player_id
            if obj_controller == player_id:
                result.append(obj)
        return result

    def remove(self, obj: StackObject) -> bool:
        """
        Remove a specific object from the stack (for counterspells, etc.).

        CR 701.5a: To counter a spell or ability means to cancel it, removing
        it from the stack. It doesn't resolve and none of its effects occur.

        Args:
            obj: The object to remove

        Returns:
            True if object was found and removed
        """
        if obj in self.objects:
            self.objects.remove(obj)
            return True
        return False

    def clear(self) -> None:
        """Clear all objects from the stack (for game reset, etc.)."""
        self.objects.clear()

    def find_by_id(self, object_id: int) -> Optional[StackObject]:
        """
        Find a stack object by its object_id.

        Args:
            object_id: The ID to search for

        Returns:
            The StackObject if found, None otherwise
        """
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None


# =============================================================================
# Helper Functions
# =============================================================================

_next_object_id: int = 0


def _get_next_object_id() -> int:
    """Generate a unique object ID for stack objects."""
    global _next_object_id
    _next_object_id += 1
    return _next_object_id


def reset_object_id_counter(start: int = 0) -> None:
    """Reset the object ID counter (useful for testing)."""
    global _next_object_id
    _next_object_id = start


def create_spell(
    card: Any,
    controller: Any,
    targets: List[Any] = None,
    modes: List[int] = None,
    x: Optional[int] = None,
    is_copy: bool = False
) -> SpellOnStack:
    """
    Create a SpellOnStack object for casting a spell.

    CR 601.2: To cast a spell, a player follows these steps in order.
    This function creates the spell object that goes on the stack.

    Args:
        card: The card being cast
        controller: The player casting the spell
        targets: List of targets for the spell
        modes: List of chosen modes for modal spells (CR 700.2)
        x: Value of X if spell has X in its cost (CR 107.3)
        is_copy: True if this is a copy of a spell (CR 707.10)

    Returns:
        A SpellOnStack ready to be pushed onto the stack
    """
    # Determine if this is a permanent spell
    is_permanent = False
    if card:
        # Check for explicit is_permanent attribute
        if hasattr(card, 'is_permanent'):
            is_permanent = card.is_permanent
        elif hasattr(card, 'is_permanent_spell'):
            is_permanent = card.is_permanent_spell
        elif hasattr(card, 'characteristics'):
            # Check card types from characteristics
            chars = card.characteristics
            if hasattr(chars, 'is_creature') and chars.is_creature():
                is_permanent = True
            elif hasattr(chars, 'is_artifact') and chars.is_artifact():
                is_permanent = True
            elif hasattr(chars, 'is_enchantment') and chars.is_enchantment():
                is_permanent = True
            elif hasattr(chars, 'is_planeswalker') and chars.is_planeswalker():
                is_permanent = True
            elif hasattr(chars, 'is_battle') and chars.is_battle():
                is_permanent = True
            elif hasattr(chars, 'card_types'):
                card_types = chars.card_types
                permanent_types = {'creature', 'artifact', 'enchantment',
                                   'planeswalker', 'land', 'battle'}
                type_set = {t.lower() if isinstance(t, str) else str(t).lower()
                           for t in card_types}
                is_permanent = bool(type_set & permanent_types)
        elif hasattr(card, 'card_types'):
            card_types = card.card_types
            permanent_types = {'creature', 'artifact', 'enchantment',
                               'planeswalker', 'land', 'battle'}
            type_set = {t.lower() if isinstance(t, str) else str(t).lower()
                       for t in card_types}
            is_permanent = bool(type_set & permanent_types)

    return SpellOnStack(
        object_id=_get_next_object_id(),
        source=card,
        controller=controller,
        targets=targets if targets is not None else [],
        card=card,
        modes=modes if modes is not None else [],
        x_value=x,
        is_permanent_spell=is_permanent,
        is_copy=is_copy,
    )


def create_triggered_ability(
    source: Any,
    controller: Any,
    effect: str,
    trigger_event: Any = None,
    targets: List[Any] = None
) -> AbilityOnStack:
    """
    Create an AbilityOnStack for a triggered ability.

    CR 603.3: Once an ability triggers, its controller puts it on the stack
    as an object that's not a card the next time a player would receive priority.

    CR 113.3c: Triggered abilities are written as "When/Whenever/At [trigger], [effect]."

    Args:
        source: The object that has this ability (permanent, card, etc.)
        controller: The player who controls the triggered ability
        effect: Text describing the ability's effect
        trigger_event: The event that caused the trigger
        targets: List of targets for the ability (if any)

    Returns:
        An AbilityOnStack ready to be pushed onto the stack
    """
    return AbilityOnStack(
        object_id=_get_next_object_id(),
        source=source,
        controller=controller,
        targets=targets if targets is not None else [],
        ability_type="triggered",
        effect_text=effect,
        trigger_event=trigger_event,
    )


def create_activated_ability(
    source: Any,
    controller: Any,
    effect: str,
    targets: List[Any] = None
) -> AbilityOnStack:
    """
    Create an AbilityOnStack for an activated ability.

    CR 602.2: To activate an ability, a player puts it on the stack, then
    pays its costs.

    CR 113.3a: Activated abilities are written as "[Cost]: [Effect]."

    Args:
        source: The object that has this ability
        controller: The player activating the ability
        effect: Text describing the ability's effect
        targets: List of targets for the ability (if any)

    Returns:
        An AbilityOnStack ready to be pushed onto the stack
    """
    return AbilityOnStack(
        object_id=_get_next_object_id(),
        source=source,
        controller=controller,
        targets=targets if targets is not None else [],
        ability_type="activated",
        effect_text=effect,
        trigger_event=None,
    )


# =============================================================================
# Stack Manager (Integration with existing engine)
# =============================================================================

class StackManager:
    """
    Manages the stack and resolution.

    This class provides integration between the Stack zone and the rest
    of the game engine, handling casting spells, activating abilities,
    and triggering abilities according to the Comprehensive Rules.
    """

    def __init__(self, game: 'Game'):
        """
        Initialize the StackManager.

        Args:
            game: Reference to the Game object
        """
        self.game = game
        self.stack = Stack(game)

    def cast_spell(self, player_id: PlayerId, card_id: ObjectId,
                   targets: List['Target'] = None, modes: List[int] = None,
                   x_value: int = 0) -> bool:
        """
        Cast a spell (CR 601).

        CR 601.2: To cast a spell is to take it from the zone it's in,
        put it on the stack, and pay its costs.

        Args:
            player_id: The player casting the spell
            card_id: The object ID of the card to cast
            targets: List of Target objects for the spell
            modes: List of chosen modes for modal spells
            x_value: Value of X if applicable

        Returns:
            True if the spell was successfully cast
        """
        from .events import SpellCastEvent
        from .objects import Spell

        # Get card from hand
        hand = self.game.zones.hands[player_id]
        card = hand.get_by_id(card_id)
        if not card:
            return False

        # Check if we can pay cost
        player = self.game.get_player(player_id)
        mana_cost = card.characteristics.mana_cost
        if mana_cost and not player.mana_pool.can_pay(mana_cost):
            return False

        # Create spell object
        spell = Spell(
            object_id=self.game.next_object_id(),
            owner_id=player_id,
            controller_id=player_id,
            characteristics=card.characteristics.copy() if hasattr(card.characteristics, 'copy') else card.characteristics,
            card=card,
            targets=targets or [],
            chosen_modes=modes or [],
            x_value=x_value
        )
        spell.timestamp = self.game.events.get_timestamp()

        # Pay cost
        if mana_cost:
            player.mana_pool.pay(mana_cost)

        # Remove from hand
        hand.remove(card)

        # Put on stack
        self.game.zones.stack.push(spell)

        # Record spell cast
        player.record_spell_cast()

        # Emit event
        self.game.events.emit(SpellCastEvent(
            spell_id=spell.object_id,
            controller_id=player_id,
            is_creature_spell=card.characteristics.is_creature(),
            is_noncreature_spell=not card.characteristics.is_creature() and not card.characteristics.is_land(),
            mana_spent=mana_cost.cmc if mana_cost else 0
        ))

        return True

    def activate_ability(self, player_id: PlayerId, source_id: ObjectId,
                        ability_index: int, targets: List['Target'] = None) -> bool:
        """
        Activate an activated ability (CR 602).

        CR 602.2: To activate an ability, put it on the stack, pay its costs,
        and make choices (like targets and modes).

        Args:
            player_id: The player activating the ability
            source_id: The object ID of the source permanent/card
            ability_index: Index of the ability being activated
            targets: List of Target objects for the ability

        Returns:
            True if the ability was successfully activated
        """
        from .objects import StackedAbility
        from .events import AbilityActivatedEvent

        # Find source
        result = self.game.zones.find_object(source_id)
        if not result:
            return False

        source, zone = result

        # Create stacked ability
        stacked = StackedAbility(
            object_id=self.game.next_object_id(),
            owner_id=player_id,
            controller_id=player_id,
            source_id=source_id,
            ability_type=AbilityType.ACTIVATED,
            targets=targets or []
        )
        stacked.timestamp = self.game.events.get_timestamp()

        # Put on stack
        self.game.zones.stack.push(stacked)

        # Emit event
        self.game.events.emit(AbilityActivatedEvent(
            ability_source_id=source_id,
            controller_id=player_id
        ))

        return True

    def trigger_ability(self, source_id: ObjectId, controller_id: PlayerId,
                       trigger_event: Any, targets: List['Target'] = None) -> bool:
        """
        Put a triggered ability on the stack (CR 603).

        CR 603.3: Once an ability has triggered, its controller puts it on
        the stack as an object that's not a card the next time a player
        would receive priority.

        Args:
            source_id: The object ID of the source
            controller_id: The player who controls the triggered ability
            trigger_event: The event that triggered the ability
            targets: List of Target objects (may be chosen later)

        Returns:
            True if the ability was successfully put on the stack
        """
        from .objects import StackedAbility
        from .events import AbilityTriggeredEvent

        # Create stacked ability
        stacked = StackedAbility(
            object_id=self.game.next_object_id(),
            owner_id=controller_id,
            controller_id=controller_id,
            source_id=source_id,
            ability_type=AbilityType.TRIGGERED,
            targets=targets or [],
            trigger_event=trigger_event
        )
        stacked.timestamp = self.game.events.get_timestamp()

        # Put on stack
        self.game.zones.stack.push(stacked)

        # Emit event
        self.game.events.emit(AbilityTriggeredEvent(
            ability_source_id=source_id,
            controller_id=controller_id
        ))

        return True

    def resolve_top(self) -> bool:
        """
        Resolve the top object of the stack (CR 608).

        CR 608.1: Each resolved spell and ability is resolved by following
        the instructions written on it.

        Returns:
            True if resolution succeeded, False if stack empty or fizzled
        """
        from .objects import Spell, StackedAbility

        stack = self.game.zones.stack

        if stack.is_empty():
            return False

        obj = stack.pop()

        if isinstance(obj, Spell):
            return self._resolve_spell(obj)
        elif isinstance(obj, StackedAbility):
            return self._resolve_ability(obj)

        return False

    def _resolve_spell(self, spell: 'Spell') -> bool:
        """
        Resolve a spell (CR 608.2 and 608.3).

        Args:
            spell: The Spell object to resolve

        Returns:
            True if resolution succeeded, False if fizzled
        """
        # Check targets still legal (CR 608.2b)
        if spell.targets:
            legal_targets = [t for t in spell.targets if t.is_legal(self.game)]
            if not legal_targets and spell.targets:
                # All targets illegal - fizzle
                if spell.card:
                    self.game.zones.graveyards[spell.owner_id].add(spell.card)
                return False

        # Execute spell effects
        self._execute_spell_effects(spell)

        # Move card to appropriate zone
        if spell.card:
            if spell.is_permanent_spell():
                # CR 608.3: Enter battlefield
                self._enter_battlefield(spell)
            else:
                # CR 608.2k: Instant/sorcery goes to graveyard
                self.game.zones.graveyards[spell.owner_id].add(spell.card)

        return True

    def _resolve_ability(self, ability: 'StackedAbility') -> bool:
        """
        Resolve an ability (CR 608.2).

        Args:
            ability: The StackedAbility object to resolve

        Returns:
            True if resolution succeeded, False if fizzled
        """
        # Check targets (CR 608.2b)
        if ability.targets:
            legal_targets = [t for t in ability.targets if t.is_legal(self.game)]
            if not legal_targets and ability.targets:
                return False  # Fizzle

        # Execute ability effects
        self._execute_ability_effects(ability)

        return True

    def _execute_spell_effects(self, spell: 'Spell') -> None:
        """
        Execute the effects of a spell.

        Args:
            spell: The Spell object being resolved
        """
        # This will be implemented by the effects system
        # The game engine should handle effect execution
        if hasattr(self.game, 'execute_spell_effects'):
            self.game.execute_spell_effects(spell)

    def _execute_ability_effects(self, ability: 'StackedAbility') -> None:
        """
        Execute the effects of an ability.

        Args:
            ability: The StackedAbility object being resolved
        """
        # This will be implemented by the effects system
        if hasattr(self.game, 'execute_ability_effects'):
            self.game.execute_ability_effects(ability)

    def _enter_battlefield(self, spell: 'Spell') -> None:
        """
        Have a permanent enter the battlefield (CR 608.3).

        Args:
            spell: The permanent spell resolving
        """
        from .objects import Permanent
        from .events import EntersBattlefieldEvent

        # Create permanent from spell
        permanent = Permanent(
            object_id=spell.object_id,
            owner_id=spell.owner_id,
            controller_id=spell.controller_id,
            characteristics=spell.characteristics,
            zone=Zone.BATTLEFIELD,
            timestamp=self.game.events.get_timestamp(),
            entered_battlefield_this_turn=True
        )

        # Add to battlefield
        self.game.zones.battlefield.add(permanent)

        # Emit event
        self.game.events.emit(EntersBattlefieldEvent(
            object_id=permanent.object_id,
            from_zone=Zone.STACK,
            to_zone=Zone.BATTLEFIELD
        ))

    def counter_spell(self, spell_id: ObjectId) -> bool:
        """
        Counter a spell on the stack (CR 701.5).

        CR 701.5a: To counter a spell or ability means to cancel it,
        removing it from the stack. It doesn't resolve and none of
        its effects occur.

        Args:
            spell_id: The object ID of the spell to counter

        Returns:
            True if the spell was countered
        """
        from .objects import Spell

        stack = self.game.zones.stack

        # Find the spell
        obj = stack.find_by_id(spell_id) if hasattr(stack, 'find_by_id') else None
        if obj is None:
            for item in stack.objects:
                if item.object_id == spell_id:
                    obj = item
                    break

        if obj is None:
            return False

        # Remove from stack
        stack.remove(obj)

        # If it's a spell with a card, put card in graveyard
        if isinstance(obj, Spell) and obj.card:
            self.game.zones.graveyards[obj.owner_id].add(obj.card)

        return True
