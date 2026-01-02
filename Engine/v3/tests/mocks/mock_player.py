"""
MockPlayer - Lightweight player mock for testing.

Provides a simplified player object for testing without full zone setup.
"""

from typing import Optional
from ...engine.player import ManaPool
from ...engine.types import PlayerId


class MockPlayer:
    """
    Lightweight mock player for isolated testing.

    Provides minimal player state needed for testing mana operations,
    life totals, and basic player actions.

    Attributes:
        player_id: Unique player identifier
        name: Player name
        life: Current life total
        mana_pool: Player's mana pool
        poison_counters: Number of poison counters
        has_lost: Whether player has lost the game
        land_played_this_turn: Whether player played a land this turn
        max_lands_per_turn: Maximum lands playable per turn
    """

    def __init__(
        self,
        player_id: PlayerId,
        name: str = "Test Player",
        starting_life: int = 20
    ):
        """
        Initialize mock player.

        Args:
            player_id: Unique player ID
            name: Player name
            starting_life: Starting life total (default 20)
        """
        self.player_id = player_id
        self.name = name
        self.life = starting_life
        self.poison_counters = 0
        self.has_lost = False
        self.loss_reason: Optional[str] = None

        # Mana pool
        self.mana_pool = ManaPool()

        # Turn state
        self.land_played_this_turn = False
        self.max_lands_per_turn = 1
        self.spells_cast_this_turn = 0

    def gain_life(self, amount: int) -> int:
        """
        Gain life.

        Args:
            amount: Amount of life to gain

        Returns:
            Actual amount gained
        """
        if amount <= 0:
            return 0
        self.life += amount
        return amount

    def lose_life(self, amount: int) -> int:
        """
        Lose life.

        Args:
            amount: Amount of life to lose

        Returns:
            Actual amount lost
        """
        if amount <= 0:
            return 0
        self.life -= amount
        return amount

    def deal_damage(self, amount: int, source) -> int:
        """
        Deal damage to this player.

        Args:
            amount: Amount of damage
            source: Source of damage

        Returns:
            Actual damage dealt
        """
        if amount <= 0:
            return 0
        self.life -= amount
        return amount

    def lose_game(self, reason: str) -> None:
        """
        Mark player as having lost.

        Args:
            reason: Reason for loss
        """
        self.has_lost = True
        self.loss_reason = reason

    def is_alive(self) -> bool:
        """Check if player is still in the game."""
        return not self.has_lost

    def can_play_land(self) -> bool:
        """Check if player can play a land."""
        if self.land_played_this_turn:
            return self.max_lands_per_turn > 1
        return True

    def reset_turn_state(self) -> None:
        """Reset per-turn state."""
        self.land_played_this_turn = False
        self.spells_cast_this_turn = 0
        self.max_lands_per_turn = 1

    def add_poison(self, amount: int) -> None:
        """
        Add poison counters.

        Args:
            amount: Number of poison counters to add
        """
        self.poison_counters += amount

    def __str__(self) -> str:
        """String representation."""
        status = "lost" if self.has_lost else f"life={self.life}"
        return f"MockPlayer({self.name}, {status})"

    def __repr__(self) -> str:
        """Debug representation."""
        return (f"MockPlayer(id={self.player_id}, name={self.name!r}, "
                f"life={self.life}, lost={self.has_lost})")

    def __hash__(self) -> int:
        """Make hashable based on player_id."""
        return hash(self.player_id)

    def __eq__(self, other) -> bool:
        """Compare by player_id."""
        if isinstance(other, MockPlayer):
            return self.player_id == other.player_id
        return False
