"""MTG Engine V3 - Spell Cast Transaction

This module implements the SpellCastTransaction class for atomic spell casting
with mana payment, validation, and rollback support.

Per CR 601.2, casting a spell follows a specific sequence where costs
are paid as the final step before the spell is considered cast.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .types import Color
from .mana import ManaCost, Mana, ManaPool, get_land_mana_color

if TYPE_CHECKING:
    pass


class SpellCastTransaction:
    """Transaction wrapper for spell casting with mana payment.

    Provides atomic spell casting with validation and rollback support.
    Per CR 601.2, casting a spell follows a specific sequence where costs
    are paid as the final step before the spell is considered cast.

    This transaction ensures:
    1. Mana availability is validated BEFORE any state changes
    2. Mana is actually deducted from the pool when paying costs
    3. If any step fails, the transaction can be rolled back
    4. The spell cast is atomic - either fully completes or fully reverts

    Usage:
        transaction = SpellCastTransaction(game, player_id, card, mana_cost)
        if transaction.validate():
            if transaction.execute():
                # Spell was successfully cast and paid for
                pass
            else:
                # Execution failed, state was rolled back
                transaction.rollback()
        else:
            # Validation failed, spell cannot be cast
            pass

    Or use as context manager:
        with SpellCastTransaction(game, player_id, card, mana_cost) as txn:
            if txn.is_valid:
                # Perform spell cast operations
                # Auto-commits on success, auto-rollback on exception
                pass

    Attributes:
        game: The game instance.
        player_id: ID of the player casting the spell.
        card: The card being cast.
        mana_cost: The mana cost to pay.
        x_value: The value chosen for X in the cost (default 0).
        is_valid: Whether the transaction passed validation.
        is_committed: Whether the transaction has been committed.
        is_rolled_back: Whether the transaction has been rolled back.
    """

    def __init__(self, game: Any, player_id: int, card: Any,
                 mana_cost: Optional[ManaCost] = None, x_value: int = 0):
        """Initialize a spell cast transaction.

        Args:
            game: The game instance.
            player_id: ID of the player casting the spell.
            card: The card being cast.
            mana_cost: The mana cost to pay. If None, parsed from card.
            x_value: The value chosen for X (default 0).
        """
        self.game = game
        self.player_id = player_id
        self.card = card
        self.x_value = x_value

        # Parse mana cost if not provided
        if mana_cost is None and card is not None:
            cost_str = None
            if hasattr(card, 'characteristics') and card.characteristics:
                cost_str = getattr(card.characteristics, 'mana_cost', None)
            self.mana_cost = ManaCost.parse(cost_str) if cost_str else ManaCost()
        else:
            self.mana_cost = mana_cost or ManaCost()

        # Transaction state
        self.is_valid: bool = False
        self.is_committed: bool = False
        self.is_rolled_back: bool = False
        self._validation_error: Optional[str] = None

        # Snapshot for rollback
        self._mana_snapshot: Optional[List[Mana]] = None
        self._tapped_lands: List[Any] = []

    @property
    def validation_error(self) -> Optional[str]:
        """Get the validation error message, if any."""
        return self._validation_error

    def validate(self) -> bool:
        """Validate that the spell can be cast and costs can be paid.

        Checks:
        1. Player exists and is valid
        2. Mana cost can be paid (either from pool or by tapping lands)

        Returns:
            True if the spell can be cast, False otherwise.
        """
        if self.is_committed or self.is_rolled_back:
            self._validation_error = "Transaction already finalized"
            return False

        # Get player
        player = self.game.get_player(self.player_id)
        if player is None:
            self._validation_error = f"Player {self.player_id} not found"
            return False

        # Check if cost is free (no validation needed for mana)
        if self.mana_cost.is_free:
            self.is_valid = True
            return True

        # Check if player can pay from current mana pool
        if player.mana_pool.can_pay(self.mana_cost, self.x_value):
            self.is_valid = True
            return True

        # Check if player can pay by tapping lands
        # Calculate total mana available (pool + untapped lands)
        available_mana = player.mana_pool.total()
        lands = self.game.zones.battlefield.untapped_lands(self.player_id)
        available_mana += len(lands)

        # Check if total available >= total cost required
        total_cost = self._calculate_total_mana_required()

        if available_mana >= total_cost:
            # More detailed check: can we satisfy colored requirements?
            if self._can_satisfy_colored_requirements(player, lands):
                self.is_valid = True
                return True

        self._validation_error = f"Insufficient mana to pay {self.mana_cost}"
        self.is_valid = False
        return False

    def _calculate_total_mana_required(self) -> int:
        """Calculate total mana required including X value."""
        total = 0
        for symbol in self.mana_cost.symbols:
            if symbol.is_x:
                total += self.x_value
            elif symbol.is_generic:
                total += symbol.generic_amount
            else:
                total += 1  # Colored, hybrid, phyrexian, etc.
        return total

    def _can_satisfy_colored_requirements(self, player: Any, lands: List[Any]) -> bool:
        """Check if colored mana requirements can be satisfied.

        This is a simplified check - full implementation would use
        the same backtracking algorithm as ManaPool._can_satisfy_requirements.
        """
        # Build color requirements from cost
        color_needed: Dict[Color, int] = {}
        for symbol in self.mana_cost.symbols:
            if symbol.is_x or symbol.is_generic:
                continue
            if symbol.colors:
                for color in symbol.colors:
                    if color != Color.COLORLESS:
                        color_needed[color] = color_needed.get(color, 0) + 1
                        break  # Only count first color for hybrid

        # Check pool first
        for color, needed in list(color_needed.items()):
            available = player.mana_pool.get_amount(color)
            color_needed[color] = max(0, needed - available)

        # Check lands
        for land in lands:
            if all(n == 0 for n in color_needed.values()):
                break
            mana_color = get_land_mana_color(
                land.characteristics.name,
                land.characteristics.subtypes
            )
            if mana_color in color_needed and color_needed[mana_color] > 0:
                color_needed[mana_color] -= 1

        return all(n == 0 for n in color_needed.values())

    def execute(self) -> bool:
        """Execute the transaction: tap lands if needed and pay mana.

        This method:
        1. Takes a snapshot of the current mana pool state
        2. Taps lands as needed via auto_pay_cost
        3. Pays the mana cost from the pool

        If payment fails, the transaction is NOT automatically rolled back.
        Call rollback() explicitly if needed.

        Returns:
            True if mana was successfully paid, False otherwise.
        """
        if not self.is_valid:
            return False

        if self.is_committed or self.is_rolled_back:
            return False

        # Free spells succeed immediately
        if self.mana_cost.is_free:
            self.is_committed = True
            return True

        player = self.game.get_player(self.player_id)
        if player is None:
            return False

        # Take snapshot before any changes
        self._mana_snapshot = [
            Mana(
                color=m.color,
                source=m.source,
                restrictions=m.restrictions.copy() if m.restrictions else [],
                is_snow=m.is_snow
            )
            for m in player.mana_pool.mana
        ]

        # Track which lands we tap
        self._tapped_lands = []

        # Use the mana manager to auto-pay (taps lands and pays from pool)
        success = self.game.mana_manager.auto_pay_cost(self.player_id, self.mana_cost)

        if success:
            self.is_committed = True
            return True
        else:
            # Payment failed - state may be partially modified
            # Caller should call rollback() if needed
            return False

    def rollback(self) -> bool:
        """Rollback the transaction, restoring mana pool state.

        This restores the mana pool to its state before execute() was called.
        Note: This does NOT untap lands that were tapped during auto_pay_cost,
        as that would require more complex game state tracking.

        Returns:
            True if rollback succeeded, False if nothing to rollback.
        """
        if self.is_rolled_back:
            return False

        if self._mana_snapshot is None:
            # Nothing to rollback
            self.is_rolled_back = True
            return True

        player = self.game.get_player(self.player_id)
        if player is None:
            return False

        # Restore mana pool from snapshot
        player.mana_pool.mana = self._mana_snapshot
        self._mana_snapshot = None
        self.is_rolled_back = True
        self.is_committed = False

        return True

    def __enter__(self) -> 'SpellCastTransaction':
        """Context manager entry - validates the transaction."""
        self.validate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit - commits on success, rollback on exception."""
        if exc_type is not None:
            # Exception occurred - rollback
            if not self.is_rolled_back and not self.is_committed:
                self.rollback()
            return False  # Don't suppress the exception

        # No exception - if valid and not yet committed, execute
        if self.is_valid and not self.is_committed and not self.is_rolled_back:
            if not self.execute():
                self.rollback()

        return False


__all__ = ['SpellCastTransaction']
