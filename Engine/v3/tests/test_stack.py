"""
Stack System Tests for MTG Engine V3.

Tests the stack implementation per Comprehensive Rules 405 and 608:
- LIFO (Last In, First Out) ordering
- Pushing spells and abilities
- Spell resolution
- Target legality checking
- Fizzling when targets become illegal
- Stack object manipulation

CR 405: The Stack
CR 608: Resolving Spells and Abilities
"""

import pytest
from ..engine.stack import (
    Stack, SpellOnStack, AbilityOnStack, StackObject,
    create_spell, create_triggered_ability, create_activated_ability
)
from ..engine.types import Zone, CardType
from .mocks.mock_objects import MockCard, MockPermanent, MockCreature
from .mocks.mock_player import MockPlayer


class TestStackBasics:
    """Test basic stack operations."""

    def test_stack_starts_empty(self, game):
        """
        Test that a new stack is empty.

        CR 405.1: The stack starts each game empty.
        """
        stack = game.zones.stack

        assert stack.is_empty() is True
        assert len(stack) == 0
        assert stack.top() is None

    def test_push_spell_to_stack(self, game):
        """
        Test pushing a spell onto the stack.

        CR 405.2: Each time an object is put on the stack, it's put on top
        of all objects already there.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        card = MockCard(name="Lightning Bolt", mana_cost="{R}")
        spell = create_spell(card, player)

        stack.push(spell)

        assert stack.is_empty() is False
        assert len(stack) == 1
        assert stack.top() == spell

    def test_stack_lifo_ordering(self, game):
        """
        Test stack uses LIFO (Last In, First Out) ordering.

        CR 405.5: When all players pass in succession, the top spell
        or ability on the stack resolves (most recent object resolves first).
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        spell1 = create_spell(MockCard(name="Spell 1"), player)
        spell2 = create_spell(MockCard(name="Spell 2"), player)
        spell3 = create_spell(MockCard(name="Spell 3"), player)

        stack.push(spell1)
        stack.push(spell2)
        stack.push(spell3)

        assert len(stack) == 3
        assert stack.top() == spell3  # Most recent on top

        popped = stack.pop()
        assert popped == spell3
        assert stack.top() == spell2

        popped = stack.pop()
        assert popped == spell2
        assert stack.top() == spell1

    def test_pop_from_empty_stack(self, game):
        """
        Test popping from an empty stack returns None.

        Edge case handling.
        """
        stack = game.zones.stack

        assert stack.is_empty() is True
        result = stack.pop()
        assert result is None

    def test_stack_iteration_order(self, game):
        """
        Test iterating stack goes from top to bottom.

        Iteration should match resolution order (top first).
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        spell1 = create_spell(MockCard(name="First"), player)
        spell2 = create_spell(MockCard(name="Second"), player)
        spell3 = create_spell(MockCard(name="Third"), player)

        stack.push(spell1)
        stack.push(spell2)
        stack.push(spell3)

        # Iteration should go Third -> Second -> First (top to bottom)
        items = list(stack)
        assert len(items) == 3
        assert items[0] == spell3  # Top
        assert items[1] == spell2
        assert items[2] == spell1  # Bottom


class TestSpellCreation:
    """Test creating spell objects."""

    def test_create_instant_spell(self):
        """Test creating an instant spell."""
        player = MockPlayer(player_id=1)
        card = MockCard(
            name="Counterspell",
            mana_cost="{U}{U}",
            types={CardType.INSTANT}
        )

        spell = create_spell(card, player)

        assert spell.card == card
        assert spell.controller == player
        assert spell.is_spell() is True
        assert spell.is_permanent_spell is False
        assert spell.is_copy is False

    def test_create_creature_spell(self):
        """
        Test creating a creature spell (permanent spell).

        CR 608.3: Permanent spells become permanents on resolution.
        """
        player = MockPlayer(player_id=1)
        card = MockCard(
            name="Grizzly Bears",
            mana_cost="{1}{G}",
            types={CardType.CREATURE}
        )

        spell = create_spell(card, player)

        assert spell.is_permanent_spell is True
        assert spell.card == card

    def test_create_spell_with_targets(self):
        """Test creating a spell with targets."""
        player = MockPlayer(player_id=1)
        card = MockCard(name="Shock")
        target_creature = MockCreature(name="Target")

        spell = create_spell(card, player, targets=[target_creature])

        assert len(spell.targets) == 1
        assert spell.targets[0] == target_creature

    def test_create_spell_copy(self):
        """
        Test creating a copy of a spell.

        CR 707.10: Spell copies aren't cards and don't go to graveyard.
        """
        player = MockPlayer(player_id=1)
        card = MockCard(name="Lightning Bolt")

        spell = create_spell(card, player, is_copy=True)

        assert spell.is_copy is True
        assert spell.card == card  # Copy still references original card


class TestAbilityCreation:
    """Test creating ability objects."""

    def test_create_triggered_ability(self):
        """
        Test creating a triggered ability.

        CR 603: Triggered abilities use the stack.
        """
        player = MockPlayer(player_id=1)
        source = MockPermanent(
            object_id=1,
            owner=player,
            controller=player,
            name="Llanowar Elves"
        )

        ability = create_triggered_ability(
            source=source,
            controller=player,
            effect="Add {G}",
            trigger_event="enters_battlefield"
        )

        assert ability.source == source
        assert ability.controller == player
        assert ability.ability_type == "triggered"
        assert ability.is_spell() is False
        assert ability.trigger_event == "enters_battlefield"

    def test_create_activated_ability(self):
        """
        Test creating an activated ability.

        CR 602: Activated abilities use the stack.
        """
        player = MockPlayer(player_id=1)
        source = MockPermanent(
            object_id=1,
            owner=player,
            controller=player,
            name="Prodigal Sorcerer"
        )

        ability = create_activated_ability(
            source=source,
            controller=player,
            effect="{T}: Deal 1 damage to any target"
        )

        assert ability.source == source
        assert ability.controller == player
        assert ability.ability_type == "activated"
        assert ability.is_spell() is False

    def test_ability_with_targets(self):
        """Test creating an ability with targets."""
        player = MockPlayer(player_id=1)
        source = MockPermanent(
            object_id=1,
            owner=player,
            controller=player,
            name="Tim"
        )
        target = MockPlayer(player_id=2)

        ability = create_activated_ability(
            source=source,
            controller=player,
            effect="Deal damage",
            targets=[target]
        )

        assert len(ability.targets) == 1
        assert ability.targets[0] == target


class TestStackTargeting:
    """Test target legality checking."""

    def test_check_targets_no_targets(self, game):
        """
        Test spells without targets are always legal.

        CR 608.2b: If the spell has no targets, this step is skipped.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        card = MockCard(name="Wrath of God")
        spell = create_spell(card, player, targets=[])

        stack.push(spell)

        # Spell with no targets should be legal
        assert stack.check_targets_legal(spell) is True

    def test_spell_fizzle_illegal_targets(self, game):
        """
        Test spell fizzles when all targets become illegal.

        CR 608.2b: If all its targets are now illegal, the spell or ability
        doesn't resolve. It's removed from the stack.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        # Create a target that will become illegal
        target = MockCreature(object_id=10, name="Target", owner=player, controller=player)
        target.zone = Zone.BATTLEFIELD
        target.targeted_in_zone = Zone.BATTLEFIELD

        card = MockCard(name="Shock")
        spell = create_spell(card, player, targets=[target])

        stack.push(spell)
        assert stack.check_targets_legal(spell) is True

        # Make target illegal by moving it to graveyard (zone change)
        target.zone = Zone.GRAVEYARD

        # Now spell should have illegal targets
        assert stack.check_targets_legal(spell) is False

        # Fizzle the spell
        stack.fizzle(spell)
        assert stack.is_empty() is True

    def test_partial_targets_legal(self, game):
        """
        Test spell is legal if at least one target is still legal.

        CR 608.2b: The spell or ability is countered only if all
        its targets are illegal.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        target1 = MockCreature(object_id=10, name="T1", owner=player, controller=player)
        target2 = MockCreature(object_id=11, name="T2", owner=player, controller=player)
        target1.zone = Zone.BATTLEFIELD
        target2.zone = Zone.BATTLEFIELD
        target1.targeted_in_zone = Zone.BATTLEFIELD
        target2.targeted_in_zone = Zone.BATTLEFIELD

        card = MockCard(name="Multi-target Spell")
        spell = create_spell(card, player, targets=[target1, target2])

        stack.push(spell)

        # Make only target1 illegal
        target1.zone = Zone.GRAVEYARD

        # Spell should still be legal (target2 is still legal)
        assert stack.check_targets_legal(spell) is True


class TestStackResolution:
    """Test stack resolution mechanics."""

    def test_resolve_top_of_stack(self, game):
        """
        Test resolving the top object removes it from stack.

        CR 608: When a spell or ability resolves, it's removed from the stack.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        spell1 = create_spell(MockCard(name="First"), player)
        spell2 = create_spell(MockCard(name="Second"), player)

        stack.push(spell1)
        stack.push(spell2)

        assert len(stack) == 2
        assert stack.top() == spell2

        # Resolve top (spell2)
        result = stack.resolve_top()

        # spell2 should be removed, spell1 should remain
        assert len(stack) == 1
        assert stack.top() == spell1

    def test_resolve_empty_stack_returns_false(self, game):
        """
        Test resolving empty stack returns False.

        Edge case handling.
        """
        stack = game.zones.stack

        assert stack.is_empty() is True
        result = stack.resolve_top()
        assert result is False

    def test_resolve_fizzled_spell(self, game):
        """
        Test spell with all illegal targets fizzles on resolution.

        CR 608.2b: All illegal targets -> doesn't resolve.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        target = MockCreature(object_id=10, name="Target", owner=player, controller=player)
        target.zone = Zone.BATTLEFIELD
        target.targeted_in_zone = Zone.BATTLEFIELD

        card = MockCard(name="Murder")
        spell = create_spell(card, player, targets=[target])

        stack.push(spell)

        # Make target illegal before resolution
        target.zone = Zone.GRAVEYARD

        # Try to resolve - should fizzle
        result = stack.resolve_top()

        # Resolution should fail (fizzle)
        assert result is False
        assert stack.is_empty() is True


class TestStackManipulation:
    """Test stack manipulation operations."""

    def test_remove_specific_object(self, game):
        """
        Test removing a specific object from the stack.

        CR 701.5a: To counter a spell means to cancel it, removing
        it from the stack.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        spell1 = create_spell(MockCard(name="First"), player)
        spell2 = create_spell(MockCard(name="Second"), player)
        spell3 = create_spell(MockCard(name="Third"), player)

        stack.push(spell1)
        stack.push(spell2)
        stack.push(spell3)

        assert len(stack) == 3

        # Remove spell2 (middle of stack)
        result = stack.remove(spell2)

        assert result is True
        assert len(stack) == 2
        assert spell2 not in stack.objects
        assert spell1 in stack.objects
        assert spell3 in stack.objects

    def test_find_by_id(self, game):
        """Test finding a stack object by its ID."""
        stack = game.zones.stack
        player = list(game.players.values())[0]

        spell = create_spell(MockCard(name="Test"), player)
        spell.object_id = 42

        stack.push(spell)

        found = stack.find_by_id(42)
        assert found == spell

        not_found = stack.find_by_id(999)
        assert not_found is None

    def test_clear_stack(self, game):
        """Test clearing the entire stack."""
        stack = game.zones.stack
        player = list(game.players.values())[0]

        for i in range(5):
            stack.push(create_spell(MockCard(name=f"Spell {i}"), player))

        assert len(stack) == 5

        stack.clear()

        assert stack.is_empty() is True
        assert len(stack) == 0

    def test_get_objects_controlled_by(self, game):
        """Test getting stack objects controlled by a specific player."""
        stack = game.zones.stack
        player1 = list(game.players.values())[0]
        player2 = list(game.players.values())[1]

        spell1 = create_spell(MockCard(name="P1 Spell 1"), player1)
        spell2 = create_spell(MockCard(name="P2 Spell"), player2)
        spell3 = create_spell(MockCard(name="P1 Spell 2"), player1)

        stack.push(spell1)
        stack.push(spell2)
        stack.push(spell3)

        p1_spells = stack.get_objects_controlled_by(player1)
        p2_spells = stack.get_objects_controlled_by(player2)

        assert len(p1_spells) == 2
        assert len(p2_spells) == 1
        assert spell1 in p1_spells
        assert spell3 in p1_spells
        assert spell2 in p2_spells


class TestStackTimestamps:
    """Test timestamp ordering on the stack."""

    def test_timestamps_increment(self, game):
        """
        Test that timestamps increment for each stack object.

        Timestamps are used to preserve ordering information.
        """
        stack = game.zones.stack
        player = list(game.players.values())[0]

        spell1 = create_spell(MockCard(name="First"), player)
        spell2 = create_spell(MockCard(name="Second"), player)
        spell3 = create_spell(MockCard(name="Third"), player)

        stack.push(spell1)
        stack.push(spell2)
        stack.push(spell3)

        # Timestamps should be in order
        assert spell1.timestamp < spell2.timestamp < spell3.timestamp

    def test_timestamp_uniqueness(self, game):
        """Test that each object gets a unique timestamp."""
        stack = game.zones.stack
        player = list(game.players.values())[0]

        spells = [create_spell(MockCard(name=f"S{i}"), player) for i in range(10)]

        for spell in spells:
            stack.push(spell)

        timestamps = [spell.timestamp for spell in spells]
        # All timestamps should be unique
        assert len(timestamps) == len(set(timestamps))


class TestStackEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_spell_description_formatting(self):
        """Test spell description string formatting."""
        player = MockPlayer(player_id=1)
        card = MockCard(name="Lightning Bolt")

        spell = create_spell(card, player)
        desc = spell.get_description()

        assert "Lightning Bolt" in desc
        assert "(copy)" not in desc

        spell_copy = create_spell(card, player, is_copy=True)
        copy_desc = spell_copy.get_description()

        assert "(copy)" in copy_desc

    def test_ability_description_formatting(self):
        """Test ability description string formatting."""
        player = MockPlayer(player_id=1)
        source = MockPermanent(
            object_id=1,
            owner=player,
            controller=player,
            name="Test Permanent"
        )

        ability = create_triggered_ability(
            source=source,
            controller=player,
            effect="Draw a card"
        )

        desc = ability.get_description()

        assert "Test Permanent" in desc
        assert "Draw a card" in desc
        assert "Triggered" in desc or "triggered" in desc
