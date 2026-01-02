"""
Priority System Tests for MTG Engine V3.

Tests the priority system implementation per Comprehensive Rules 117:
- Priority passing between players
- All-pass detection
- Priority after actions
- APNAP (Active Player, Non-Active Player) ordering
- Priority holder tracking

CR 117: Timing and Priority
CR 117.1: Players can only take actions when they have priority
CR 117.3: Priority passing rules
CR 117.4: All-pass rules (stack resolution or phase end)
"""

import pytest
from ..engine.priority import PrioritySystem, PriorityResult
from ..engine.player import Player
from .mocks.mock_game import MockGame


class TestPriorityBasics:
    """Test basic priority system functionality."""

    def test_give_priority_to_player(self, game, player1):
        """
        Test giving priority to a specific player.

        CR 117.3a: The active player receives priority at the beginning
        of most steps and phases.
        """
        game.priority.give_priority(player1)

        assert game.priority.get_priority_holder() == player1
        assert player1 in game.priority.passed_players or len(game.priority.passed_players) == 0
        assert game.priority.waiting_for_response is True

    def test_pass_priority_to_next(self, game, player1, player2):
        """
        Test passing priority to the next player in turn order.

        CR 117.3d: If a player has priority and chooses not to take an action,
        that player passes priority to the next player in turn order.
        """
        game.priority.give_priority(player1)
        result = game.priority.pass_priority()

        assert result == PriorityResult.PRIORITY_PASSED
        assert game.priority.get_priority_holder() == player2
        assert player1 in game.priority.passed_players

    def test_all_players_passed(self, game, player1, player2):
        """
        Test detection when all players pass in succession.

        CR 117.4: If all players pass in succession (that is, if all players
        pass without taking any actions in between passing), the spell or
        ability on top of the stack resolves or, if the stack is empty,
        the phase or step ends.
        """
        game.priority.give_priority(player1)
        result1 = game.priority.pass_priority()
        assert result1 == PriorityResult.PRIORITY_PASSED

        # Now player2 has priority
        result2 = game.priority.pass_priority()
        assert result2 == PriorityResult.ALL_PASSED
        assert game.priority.get_priority_holder() is None

    def test_priority_after_action(self, game, player1, player2):
        """
        Test priority handling after a player takes an action.

        CR 117.3c: After a player takes an action, the active player
        receives priority, and the passed set is cleared so all players
        get a chance to respond.
        """
        game.priority.give_priority(player1)
        game.priority.pass_priority()  # Pass to player2

        assert game.priority.get_priority_holder() == player2
        assert len(game.priority.passed_players) == 1  # player1 passed

        # Player2 takes an action
        game.priority.player_takes_action()

        # Passed set should be cleared
        assert len(game.priority.passed_players) == 0

    def test_priority_holder_none_initially(self, game):
        """
        Test that priority holder is None on game initialization.

        Priority must be explicitly given to a player before anyone
        can take actions.
        """
        assert game.priority.get_priority_holder() is None

    def test_reset_clears_state(self, game, player1):
        """
        Test that reset clears all priority state.

        Used when completely resetting the priority system.
        """
        game.priority.give_priority(player1)
        game.priority.pass_priority()

        assert game.priority.get_priority_holder() is not None
        assert len(game.priority.passed_players) > 0

        game.priority.reset()

        assert game.priority.get_priority_holder() is None
        assert len(game.priority.passed_players) == 0
        assert game.priority.waiting_for_response is False


class TestPriorityOrdering:
    """Test priority passing order (APNAP)."""

    def test_two_player_alternating(self, game, player1, player2):
        """
        Test priority alternates between two players.

        In a 2-player game, priority passes P1 -> P2 -> P1.
        """
        game.priority.give_priority(player1)
        assert game.priority.get_priority_holder() == player1

        game.priority.pass_priority()
        assert game.priority.get_priority_holder() == player2

        game.priority.player_takes_action()  # Reset passed set
        game.priority.give_priority(player1)
        game.priority.pass_priority()
        assert game.priority.get_priority_holder() == player2

    def test_multiplayer_priority_order(self, multiplayer_game):
        """
        Test priority passes in turn order in multiplayer.

        In a 4-player game, priority should follow turn order.
        """
        players = list(multiplayer_game.players.values())

        multiplayer_game.priority.give_priority(players[0])
        assert multiplayer_game.priority.get_priority_holder() == players[0]

        multiplayer_game.priority.pass_priority()
        assert multiplayer_game.priority.get_priority_holder() == players[1]

        multiplayer_game.priority.pass_priority()
        assert multiplayer_game.priority.get_priority_holder() == players[2]

        multiplayer_game.priority.pass_priority()
        assert multiplayer_game.priority.get_priority_holder() == players[3]

    def test_priority_wraps_around(self, game, player1, player2):
        """
        Test priority wraps from last player back to first.

        After the last player in turn order, priority should wrap
        back to the first player.
        """
        game.priority.give_priority(player2)
        game.priority.pass_priority()

        # Should wrap back to player1
        assert game.priority.get_priority_holder() == player1


class TestPriorityAllPass:
    """Test all-pass detection and behavior."""

    def test_all_pass_empty_set(self, game, player1):
        """
        Test all_passed() returns False with empty passed set.

        If no players have passed, not all players have passed.
        """
        game.priority.give_priority(player1)
        # Immediately check, no one passed yet
        assert game.priority.all_passed() is False

    def test_all_pass_partial(self, game, player1, player2):
        """
        Test all_passed() returns False when only some players passed.

        All players must pass in succession for all_passed to be True.
        """
        game.priority.give_priority(player1)
        game.priority.pass_priority()  # Only player1 passed

        assert game.priority.all_passed() is False

    def test_all_pass_complete(self, game, player1, player2):
        """
        Test all_passed() returns True when all players have passed.

        CR 117.4: When all players pass in succession.
        """
        game.priority.give_priority(player1)
        game.priority.pass_priority()  # player1 passes
        game.priority.pass_priority()  # player2 passes

        # After both pass, all_passed should be True
        # (the second pass_priority() will have set holder to None)
        assert game.priority.all_passed() is True

    def test_all_pass_clears_after_action(self, game, player1, player2):
        """
        Test all_passed becomes False after an action clears passed set.

        Taking an action resets the all-pass condition.
        """
        game.priority.give_priority(player1)
        game.priority.pass_priority()
        game.priority.pass_priority()

        assert game.priority.all_passed() is True

        # Reset and give priority again
        game.priority.give_priority(player1)
        game.priority.player_takes_action()

        assert game.priority.all_passed() is False


class TestPriorityEdgeCases:
    """Test edge cases and error conditions."""

    def test_pass_without_priority_holder_raises(self, game):
        """
        Test passing priority when no one has priority raises error.

        This should not happen in normal game flow, but must be handled.
        """
        game.priority.reset()
        assert game.priority.get_priority_holder() is None

        with pytest.raises(ValueError, match="No player currently has priority"):
            game.priority.pass_priority()

    def test_set_active_player_resets_priority(self, game, player1):
        """
        Test that changing active player resets priority state.

        When the turn changes, priority state should be reset.
        """
        game.priority.give_priority(player1)
        game.priority.pass_priority()

        assert game.priority.get_priority_holder() is not None
        assert len(game.priority.passed_players) > 0

        # Change active player (simulating new turn)
        game.priority.set_active_player(2)

        assert game.priority.get_priority_holder() is None
        assert len(game.priority.passed_players) == 0

    def test_player_takes_action_clears_passes(self, game, player1, player2):
        """
        Test player_takes_action() clears the passed players set.

        CR 117.3c: After a spell or ability is put on the stack,
        the passed set is cleared.
        """
        game.priority.give_priority(player1)
        game.priority.pass_priority()

        assert len(game.priority.passed_players) == 1
        assert player1 in game.priority.passed_players

        game.priority.player_takes_action()

        assert len(game.priority.passed_players) == 0

    def test_multiple_action_cycles(self, game, player1, player2):
        """
        Test multiple cycles of priority passing with actions.

        Simulates a realistic game flow with actions and passes.
        """
        # Round 1: Player1 acts
        game.priority.give_priority(player1)
        game.priority.player_takes_action()
        assert len(game.priority.passed_players) == 0

        # Round 2: Player1 passes, Player2 acts
        game.priority.give_priority(player1)
        game.priority.pass_priority()
        assert player1 in game.priority.passed_players

        game.priority.player_takes_action()  # Player2 acts
        assert len(game.priority.passed_players) == 0

        # Round 3: Both pass
        game.priority.give_priority(player1)
        game.priority.pass_priority()
        result = game.priority.pass_priority()

        assert result == PriorityResult.ALL_PASSED


class TestPriorityIntegration:
    """Test priority system integration with game flow."""

    def test_priority_with_mock_game(self):
        """
        Test priority system with MockGame.

        Ensures priority system works with minimal game mock.
        """
        mock_game = MockGame(player_ids=[1, 2])
        priority = mock_game.priority
        players = list(mock_game.players.values())

        priority.give_priority(players[0])
        assert priority.get_priority_holder() == players[0]

        priority.pass_priority()
        assert priority.get_priority_holder() == players[1]

        priority.pass_priority()
        assert priority.all_passed() is True

    def test_priority_player_equality(self, game, player1):
        """
        Test priority holder is same object as player.

        Ensures we're tracking actual player objects, not copies.
        """
        game.priority.give_priority(player1)
        holder = game.priority.get_priority_holder()

        assert holder is player1
        assert holder.player_id == player1.player_id

    def test_waiting_for_response_flag(self, game, player1, player2):
        """
        Test waiting_for_response flag tracks priority state.

        This flag indicates when the system is waiting for a player decision.
        """
        assert game.priority.waiting_for_response is False

        game.priority.give_priority(player1)
        assert game.priority.waiting_for_response is True

        game.priority.pass_priority()
        assert game.priority.waiting_for_response is True  # Still waiting for player2

        game.priority.pass_priority()  # All pass
        assert game.priority.waiting_for_response is False
