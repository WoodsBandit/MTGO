"""
MTG Priority System implementation per Comprehensive Rules 117.

This module implements the complete priority system for Magic: The Gathering,
including priority passing, action tracking, and priority round execution.

CR 117.1: A player can normally take actions only when they have priority.
CR 117.3: Which player has priority is determined by the following rules:
    - The active player receives priority at the beginning of most steps and phases.
    - When a spell or ability resolves, the active player receives priority.
    - When priority passes from one player to another, priority passes in turn order.
CR 117.4: If all players pass in succession, the top object on the stack resolves,
          or if the stack is empty, the phase or step ends.
"""

from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional, Set

from .player import Player

if TYPE_CHECKING:
    from .game import Game


class PriorityResult(Enum):
    """
    Result of a priority pass action.

    Used to communicate what happened when a player passes priority,
    allowing the caller to take appropriate action.
    """

    PRIORITY_PASSED = auto()  # Priority moved to the next player in turn order
    ALL_PASSED = auto()       # All players passed in succession without taking action
    ACTION_TAKEN = auto()     # A player took an action (cast spell, activate ability, etc.)


class PrioritySystem:
    """
    Manages the priority system for an MTG game.

    Priority determines which player may take actions at any given time.
    Only the player with priority may cast spells, activate abilities,
    or take special actions (CR 117.1).

    Key Rules Implemented:
    - CR 117.3a: The active player receives priority after most game events
    - CR 117.3b: After spell/ability resolution, active player receives priority
    - CR 117.3c: When a player passes, priority goes to next player in turn order
    - CR 117.4: When all pass in succession, top of stack resolves or phase ends

    Attributes:
        game: Reference to the Game object for accessing players and turn order
        priority_player: The Player who currently holds priority (None if no one has it)
        passed_players: Set of Players who have passed priority in succession
        waiting_for_response: Flag indicating the system is waiting for player input
    """

    def __init__(self, game: Any) -> None:
        """
        Initialize the priority system.

        Args:
            game: The Game object this priority system belongs to
        """
        self.game: Any = game
        self.priority_player: Optional[Player] = None
        self.passed_players: Set[Player] = set()
        self.waiting_for_response: bool = False

    def give_priority(self, player: Player) -> None:
        """
        Give priority to the specified player.

        Per CR 117.3a, when a player receives priority, the set of players
        who have passed in succession is cleared. This ensures that after
        any game action, all players get a chance to respond.

        This is called:
        - At the beginning of most steps and phases (active player)
        - After a spell or ability resolves (active player)
        - After a player takes any action (active player keeps priority initially,
          but this resets the passed set)

        Args:
            player: The Player to receive priority
        """
        self.priority_player = player
        self.passed_players.clear()
        self.waiting_for_response = True

    def pass_priority(self) -> PriorityResult:
        """
        Current player passes priority to the next player in turn order.

        Per CR 117.3d, if a player has priority and chooses not to take any
        actions, that player passes priority to the next player in turn order.

        Per CR 117.4, if all players pass in succession (that is, if all
        players pass without taking any actions in between passing), the
        spell or ability on top of the stack resolves or, if the stack is
        empty, the phase or step ends.

        Returns:
            PriorityResult indicating what happened:
            - PRIORITY_PASSED: Priority moved to next player, round continues
            - ALL_PASSED: All players have passed in succession

        Raises:
            ValueError: If no player currently has priority
        """
        if self.priority_player is None:
            raise ValueError("No player currently has priority")

        # Add current player to the set of passed players
        self.passed_players.add(self.priority_player)

        # Check if all players have passed in succession
        if self.all_passed():
            self.priority_player = None
            self.waiting_for_response = False
            return PriorityResult.ALL_PASSED

        # Pass to next player in turn order (APNAP order)
        self.priority_player = self._get_next_player()
        self.waiting_for_response = True
        return PriorityResult.PRIORITY_PASSED

    def player_takes_action(self) -> None:
        """
        Record that the current player has taken an action.

        Per CR 117.3c, after a spell or ability is put onto the stack,
        the active player receives priority. This method clears the
        passed players set so that all players get a chance to respond
        to the new game state.

        Called when:
        - A player casts a spell
        - A player activates an ability
        - A player takes a special action
        - Any action that changes the game state

        Note: The caller is responsible for giving priority to the
        appropriate player after the action is complete. Typically,
        the player who took the action retains priority (CR 117.3c).
        """
        self.passed_players.clear()

    def get_priority_holder(self) -> Optional[Player]:
        """
        Get the player who currently holds priority.

        Returns:
            The Player with priority, or None if no player has priority
            (e.g., during resolution of spells/abilities or between phases)
        """
        return self.priority_player

    def all_passed(self) -> bool:
        """
        Check if all players have passed in succession.

        Per CR 117.4, when all players pass in succession, either the
        top of the stack resolves or the phase/step ends.

        This checks if every player in the game is in the passed_players set,
        which indicates a complete round of passing without any actions.

        Returns:
            True if all players in the game have passed without taking
            any actions in between, False otherwise
        """
        all_players = self._get_all_players()
        if not all_players:
            return False
        return all(player in self.passed_players for player in all_players)

    def reset(self) -> None:
        """
        Reset all priority state.

        This is typically called:
        - At the start of a new game
        - When completely resetting the game state
        - During certain cleanup operations

        Clears the priority holder, passed players set, and waiting flag.
        """
        self.priority_player = None
        self.passed_players.clear()
        self.waiting_for_response = False

    def set_active_player(self, player_id: int) -> None:
        """
        Update priority system when the active player changes.

        Called when the turn passes to a new player. Resets priority
        state for the new turn.

        Args:
            player_id: The new active player's ID
        """
        self.reset()

    def _get_next_player(self) -> Player:
        """
        Get the next player in turn order after the current priority holder.

        Priority passes in Active Player, Non-Active Player (APNAP) order,
        which in a two-player game is simply alternating, and in multiplayer
        follows the turn order starting from the active player.

        Returns:
            The next Player in turn order

        Raises:
            ValueError: If priority_player is None or player list is empty
        """
        if self.priority_player is None:
            raise ValueError("No player currently has priority")

        all_players = self._get_all_players()
        if not all_players:
            raise ValueError("No players in game")

        try:
            current_index = all_players.index(self.priority_player)
        except ValueError:
            raise ValueError("Current priority holder not found in player list")

        # Get next player in turn order (wrapping around)
        next_index = (current_index + 1) % len(all_players)
        return all_players[next_index]

    def _get_all_players(self) -> list:
        """
        Get all players from the game in turn order.

        Supports multiple ways the game might expose its player list
        for flexibility with different Game implementations.

        Returns:
            List of all Player objects in the game in turn order
        """
        if self.game is None:
            return []

        # Try various ways the game might store players
        if hasattr(self.game, 'players'):
            players = self.game.players
            if isinstance(players, dict):
                # Dict of player_id -> Player
                return list(players.values())
            elif isinstance(players, list):
                return players
            elif hasattr(players, '__iter__'):
                return list(players)

        if hasattr(self.game, 'get_players'):
            return list(self.game.get_players())

        if hasattr(self.game, 'turn_order'):
            return list(self.game.turn_order)

        return []


class PriorityRound:
    """
    Helper class for executing a complete priority round.

    A priority round is the process of giving each player a chance to act,
    starting with the active player, and continuing until either:

    1. All players pass in succession with an empty stack -> phase/step ends
    2. All players pass in succession with non-empty stack -> top object resolves
    3. A player takes an action -> new round begins with active player

    This class encapsulates the logic for running these rounds according
    to the Comprehensive Rules, handling the iteration and resolution.

    Attributes:
        priority_system: The PrioritySystem instance for managing priority state
        stack: Reference to the game's stack for checking emptiness and resolution
    """

    def __init__(self, priority_system: PrioritySystem, stack: Any) -> None:
        """
        Initialize a priority round.

        Args:
            priority_system: The PrioritySystem instance to use for priority management
            stack: The game's stack object (for checking if empty and resolving)
        """
        self.priority_system = priority_system
        self.stack = stack

    def run(self) -> None:
        """
        Execute a complete priority round.

        This method implements the core priority loop per CR 117:

        1. Active player receives priority (CR 117.3a)
        2. Each player with priority may take an action or pass
        3. If a player takes an action:
           - The passed set is cleared (everyone gets to respond)
           - Active player receives priority again (CR 117.3c)
        4. If all players pass in succession:
           - If stack is empty: return (phase/step ends per CR 117.4)
           - If stack has objects: resolve top, then active player gets priority

        This method continues running until the phase/step should end
        (all passed with empty stack), handling multiple resolution cycles.
        """
        game = self.priority_system.game
        if game is None:
            return

        # Get the active player (the player whose turn it is)
        active_player = self._get_active_player()
        if active_player is None:
            return

        # Give priority to the active player to start the round
        self.priority_system.give_priority(active_player)

        # Main priority loop
        while True:
            current_player = self.priority_system.get_priority_holder()
            if current_player is None:
                # No one has priority, shouldn't happen in normal flow
                break

            # Get the player's decision (action or pass)
            # This is typically blocking and waits for player input
            action = self._get_player_decision(current_player)

            if action is None:
                # Player passes priority
                result = self.priority_system.pass_priority()

                if result == PriorityResult.ALL_PASSED:
                    # All players have passed in succession
                    if self._is_stack_empty():
                        # Stack is empty - phase/step ends (CR 117.4)
                        return
                    else:
                        # Stack is not empty - resolve top object (CR 117.4)
                        self._resolve_top_of_stack()
                        # After resolution, active player receives priority (CR 117.3b)
                        self.priority_system.give_priority(active_player)
                # If PRIORITY_PASSED, continue the loop with new priority holder

            else:
                # Player takes an action
                self._execute_action(current_player, action)
                # Clear passed players since everyone gets to respond
                self.priority_system.player_takes_action()
                # Active player receives priority after object placed on stack (CR 117.3c)
                # Note: The acting player retains priority, but for simplicity
                # we give to active player. In practice, the acting player IS
                # typically the one with priority, and they keep it after acting.
                self.priority_system.give_priority(active_player)

    def _get_active_player(self) -> Optional[Player]:
        """
        Get the active player (the player whose turn it is).

        Attempts various ways to access the active player from the game
        object to support different Game implementations.

        Returns:
            The active Player, or None if not determinable
        """
        game = self.priority_system.game
        if game is None:
            return None

        if hasattr(game, 'active_player'):
            return game.active_player

        if hasattr(game, 'turn') and hasattr(game.turn, 'active_player'):
            return game.turn.active_player

        if hasattr(game, 'get_active_player'):
            return game.get_active_player()

        # Fallback: first player in turn order
        players = self.priority_system._get_all_players()
        return players[0] if players else None

    def _get_player_decision(self, player: Player) -> Optional[Any]:
        """
        Get a player's decision for their priority.

        This method interfaces with the game's action system to get
        what the player wants to do. The action can come from:
        - AI decision making
        - User input (in interactive mode)
        - Automated testing

        Args:
            player: The Player who has priority and must decide

        Returns:
            None if the player passes priority, or an action object
            if they want to take an action (cast spell, activate ability, etc.)
        """
        game = self.priority_system.game

        # Check if game has a method to get player decisions
        if hasattr(game, 'get_priority_action'):
            return game.get_priority_action(player)

        if hasattr(player, 'get_priority_action'):
            return player.get_priority_action(game)

        if hasattr(player, 'decide_priority'):
            return player.decide_priority(game)

        # Check for AI controller
        if hasattr(player, 'ai') and player.ai is not None:
            # Debug
            # print(f"  [Priority] Player {player.player_id} has AI, calling decide_priority")
            if hasattr(player.ai, 'decide_priority'):
                result = player.ai.decide_priority(game)
                # print(f"  [Priority] AI returned: {result}")
                return result
            elif hasattr(player.ai, 'get_priority_action'):
                return player.ai.get_priority_action(game)

        # Default behavior: pass priority
        # In a real implementation, this would wait for player input
        return None

    def _execute_action(self, player: Player, action: Any) -> None:
        """
        Execute an action taken by a player.

        This delegates to the game's action execution system.
        Actions can include casting spells, activating abilities,
        playing lands, or special actions.

        Args:
            player: The Player taking the action
            action: The action object to execute
        """
        game = self.priority_system.game

        if hasattr(game, 'execute_action'):
            game.execute_action(player, action)
        elif hasattr(game, 'execute'):
            game.execute(action)
        elif hasattr(action, 'execute'):
            action.execute(game, player)
        elif callable(action):
            action(game, player)

    def _is_stack_empty(self) -> bool:
        """
        Check if the stack is empty.

        Used to determine whether all-pass should end the phase
        or resolve the top of stack.

        Returns:
            True if the stack is empty (no spells/abilities waiting),
            False if there are objects on the stack to resolve
        """
        if self.stack is None:
            return True

        if hasattr(self.stack, 'is_empty'):
            return self.stack.is_empty()

        if hasattr(self.stack, '__len__'):
            return len(self.stack) == 0

        if hasattr(self.stack, 'empty'):
            if callable(self.stack.empty):
                return self.stack.empty()
            return self.stack.empty

        return True

    def _resolve_top_of_stack(self) -> None:
        """
        Resolve the top object on the stack.

        Per CR 608, when the top of the stack resolves, the game
        processes its effects. This includes:
        - Checking if all targets are still legal
        - Executing the spell/ability's effects
        - Moving the card to appropriate zone (graveyard for most spells)

        The stack object is expected to handle the actual resolution logic.
        """
        if self.stack is None:
            return

        if hasattr(self.stack, 'resolve'):
            self.stack.resolve()
        elif hasattr(self.stack, 'resolve_top'):
            self.stack.resolve_top()
        elif hasattr(self.stack, 'pop'):
            # If stack just has pop, get the object and resolve it
            top_object = self.stack.pop()
            if hasattr(top_object, 'resolve'):
                top_object.resolve()


# =============================================================================
# Convenience Function
# =============================================================================

def run_priority_round(game: Any) -> bool:
    """
    Run a complete priority round for the given game.

    This is a convenience function that creates a PriorityRound and runs it.
    It handles the priority pass sequence until either:
    - All players pass with empty stack (returns False - phase ends)
    - All players pass with non-empty stack (resolves top, returns True)
    - A player takes an action (restarts priority, returns True)

    Args:
        game: The Game object containing priority_system and zones

    Returns:
        True if something happened (action taken or stack resolved),
        False if all players passed with empty stack (phase should end)
    """
    # Support both 'priority' and 'priority_system' attribute names
    if hasattr(game, 'priority_system'):
        priority_system = game.priority_system
    elif hasattr(game, 'priority'):
        priority_system = game.priority
    else:
        return False
    stack = game.zones.stack if hasattr(game, 'zones') and hasattr(game.zones, 'stack') else None

    priority_round = PriorityRound(priority_system, stack)
    priority_round.run()

    # Return whether the stack still has items (more processing needed)
    if stack and hasattr(stack, 'is_empty'):
        return not stack.is_empty()
    return False
