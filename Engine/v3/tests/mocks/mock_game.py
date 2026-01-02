"""
MockGame - Lightweight game mock for testing.

Provides a simplified game object for testing priority, stack, and turn
structure without the full engine overhead.
"""

from typing import Dict, List, Optional
from ...engine.player import Player
from ...engine.priority import PrioritySystem
from ...engine.stack import Stack
from ...engine.types import PlayerId, PhaseType, StepType


class MockGame:
    """
    Lightweight mock game for isolated testing.

    Provides minimal game state needed for testing priority system,
    stack operations, and basic game flow without full engine complexity.

    Attributes:
        players: Dict mapping player_id to Player objects
        priority: PrioritySystem instance
        zones: Mock zones object with stack
        active_player_id: ID of the active player
        current_phase: Current phase
        current_step: Current step
        turn_number: Current turn number
        game_over: Whether the game has ended
    """

    def __init__(self, player_ids: List[PlayerId] = None):
        """
        Initialize mock game with specified players.

        Args:
            player_ids: List of player IDs (default [1, 2])
        """
        player_ids = player_ids or [1, 2]

        # Create players
        self.players: Dict[PlayerId, Player] = {}
        for pid in player_ids:
            player = Player(player_id=pid, name=f"Player {pid}")
            player.life = 20
            self.players[pid] = player

        # Game state
        self.active_player_id = player_ids[0]
        self.current_phase = PhaseType.PRECOMBAT_MAIN
        self.current_step = StepType.PRECOMBAT_MAIN
        self.turn_number = 1
        self.game_over = False
        self._next_object_id = 1

        # Create minimal zones
        self.zones = MockZones()

        # Priority system
        self.priority = PrioritySystem(self)

    def get_player(self, player_id: PlayerId) -> Player:
        """Get a player by ID."""
        return self.players[player_id]

    def get_active_player(self) -> Player:
        """Get the active player."""
        return self.players[self.active_player_id]

    @property
    def active_player(self) -> Player:
        """Get the active player (property accessor)."""
        return self.players[self.active_player_id]

    def next_object_id(self) -> int:
        """Generate next unique object ID."""
        oid = self._next_object_id
        self._next_object_id += 1
        return oid

    def get_priority_action(self, player: Player):
        """
        Mock priority action (always returns None = pass).

        Override in specific tests to provide actions.

        Args:
            player: Player who has priority

        Returns:
            None (pass priority)
        """
        return None


class MockZones:
    """
    Mock zones object for testing.

    Provides minimal zone structure needed for testing stack operations.
    """

    def __init__(self):
        """Initialize mock zones with just a stack."""
        self.stack = Stack(game=None)
