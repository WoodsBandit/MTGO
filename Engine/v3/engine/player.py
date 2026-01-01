"""MTG Engine V3 - Player Class

This module implements the Player class and ManaPool class according to the
Magic: The Gathering Comprehensive Rules. Players are game participants with
life totals, mana pools, and access to their zones.

Rules References:
- CR 102: Players
- CR 106: Mana
- CR 117: Costs (paying mana)
- CR 119: Life
- CR 120: Damage
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, TYPE_CHECKING

from .types import Color, PlayerId, ObjectId

if TYPE_CHECKING:
    from .zones import Library, Hand, Graveyard
    from .objects import Card, Permanent


# =============================================================================
# MANA POOL CLASS
# =============================================================================

@dataclass
class ManaPool:
    """A player's mana pool.

    The mana pool holds mana that has been produced but not yet spent.
    Mana empties from the pool at the end of each step and phase (CR 106.4).

    This implementation uses Color enum as keys for the mana dictionary,
    tracking both colored mana (W, U, B, R, G) and colorless mana (C).
    """

    mana: Dict[Color, int] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize mana pool with zero of each color."""
        if not self.mana:
            self.mana = {color: 0 for color in Color}

    def add(self, color: Color, amount: int = 1, source: Any = None) -> None:
        """Add mana of a specific color to the pool.

        Args:
            color: The color of mana to add (from Color enum)
            amount: The amount of mana to add (default 1)
            source: Optional source permanent that produced this mana
        """
        if amount < 0:
            return
        if color not in self.mana:
            self.mana[color] = 0
        self.mana[color] += amount

    def remove(self, color: Color, amount: int = 1) -> bool:
        """Remove mana of a specific color from the pool.

        Args:
            color: The color of mana to remove
            amount: The amount to remove (default 1)

        Returns:
            True if the mana was successfully removed, False if insufficient mana
        """
        if amount < 0:
            return True
        current = self.mana.get(color, 0)
        if current < amount:
            return False
        self.mana[color] = current - amount
        return True

    def _cost_to_dict(self, cost) -> Dict[Color, int]:
        """Convert a ManaCost or dict to a color->amount dict.

        Args:
            cost: Either a Dict[Color, int] or a ManaCost object.

        Returns:
            Dict mapping Color to amount needed.
        """
        if isinstance(cost, dict):
            return cost

        # It's a ManaCost - convert symbols to dict
        result: Dict[Color, int] = {color: 0 for color in Color}

        for symbol in cost.symbols:
            if symbol.is_generic:
                result[Color.COLORLESS] = result.get(Color.COLORLESS, 0) + symbol.generic_amount
            elif symbol.is_x:
                # X cost - use 0 for now (caller should specify)
                pass
            elif symbol.colors:
                # Use first color for hybrid, normal colored mana
                for color in symbol.colors:
                    result[color] = result.get(color, 0) + 1
                    break  # Only count once
            elif symbol.is_colorless:
                result[Color.COLORLESS] = result.get(Color.COLORLESS, 0) + 1

        return result

    def can_pay(self, cost) -> bool:
        """Check if the pool can pay a mana cost.

        Args:
            cost: Dictionary mapping Color to required amount, or a ManaCost object.
                  Use Color.COLORLESS for generic mana costs (can be paid with any color).

        Returns:
            True if the cost can be paid, False otherwise

        Note:
            Generic mana (represented by COLORLESS in the cost) can be paid with
            any type of mana. Colored requirements must be paid with that specific color.
        """
        cost_dict = self._cost_to_dict(cost)

        # Make a copy of current mana to simulate payment
        available = dict(self.mana)

        # First, pay colored costs (specific requirements)
        for color, required in cost_dict.items():
            if color == Color.COLORLESS:
                continue  # Handle generic costs last
            if available.get(color, 0) < required:
                return False
            available[color] -= required

        # Now check if we have enough total mana for generic costs
        generic_needed = cost_dict.get(Color.COLORLESS, 0)
        if generic_needed > 0:
            total_remaining = sum(v for v in available.values() if v > 0)
            if total_remaining < generic_needed:
                return False

        return True

    def pay(self, cost) -> bool:
        """Pay a mana cost from the pool.

        Args:
            cost: Dictionary mapping Color to required amount, or a ManaCost object.
                  Use Color.COLORLESS for generic mana costs.

        Returns:
            True if the cost was successfully paid, False if payment failed

        Note:
            When paying generic costs, mana is consumed in a specific order:
            Colorless first, then colors in WUBRG order. This mimics typical
            MTGO auto-pay behavior.
        """
        if not self.can_pay(cost):
            return False

        cost_dict = self._cost_to_dict(cost)

        # Pay colored costs first
        for color, required in cost_dict.items():
            if color == Color.COLORLESS:
                continue
            self.mana[color] -= required

        # Pay generic costs using any available mana
        generic_needed = cost_dict.get(Color.COLORLESS, 0)
        if generic_needed > 0:
            # Consume colorless mana first, then colors in order
            pay_order = [
                Color.COLORLESS,
                Color.WHITE,
                Color.BLUE,
                Color.BLACK,
                Color.RED,
                Color.GREEN
            ]
            for color in pay_order:
                if generic_needed <= 0:
                    break
                available = self.mana.get(color, 0)
                to_pay = min(available, generic_needed)
                if to_pay > 0:
                    self.mana[color] -= to_pay
                    generic_needed -= to_pay

        return True

    def total(self) -> int:
        """Get the total amount of mana in the pool.

        Returns:
            Total mana across all colors
        """
        return sum(v for v in self.mana.values() if v > 0)

    def empty(self) -> None:
        """Empty the mana pool.

        Called at the end of each step and phase per CR 106.4.
        Also called when mana burn was still a rule (pre-M10) but
        now simply clears the pool with no life loss.
        """
        for color in self.mana:
            self.mana[color] = 0

    def get(self, color: Color) -> int:
        """Get amount of mana of a specific color.

        Args:
            color: The color to query

        Returns:
            Amount of that color of mana available
        """
        return self.mana.get(color, 0)

    def __str__(self) -> str:
        """Display the mana pool in a readable format.

        Returns:
            String like "{W}{W}{U}{B}{R}{G}{C}{C}" or "Empty" if no mana
        """
        if self.total() == 0:
            return "Empty"

        parts = []
        symbol_map = {
            Color.WHITE: 'W',
            Color.BLUE: 'U',
            Color.BLACK: 'B',
            Color.RED: 'R',
            Color.GREEN: 'G',
            Color.COLORLESS: 'C'
        }

        for color in [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN, Color.COLORLESS]:
            count = self.mana.get(color, 0)
            for _ in range(count):
                parts.append(f"{{{symbol_map[color]}}}")

        return ''.join(parts) if parts else "Empty"

    def __repr__(self) -> str:
        """Debug representation of the mana pool."""
        non_zero = {c.value: v for c, v in self.mana.items() if v > 0}
        return f"ManaPool({non_zero})"


# =============================================================================
# PLAYER CLASS
# =============================================================================

@dataclass
class Player:
    """Represents a player in the game.

    A player has a life total, mana pool, and zones (library, hand, graveyard).
    Players can take actions during the game such as drawing cards, casting spells,
    and playing lands.

    Rules References:
    - CR 102: Players
    - CR 103: Starting the Game
    - CR 104: Ending the Game
    - CR 119: Life
    - CR 120: Damage
    """

    # Identity
    player_id: int
    name: str

    # Life and counters
    life: int = 20
    poison_counters: int = 0

    # Mana pool
    mana_pool: ManaPool = field(default_factory=ManaPool)

    # Loss tracking
    has_lost: bool = False
    loss_reason: Optional[str] = None

    # Turn state tracking
    land_played_this_turn: bool = False
    max_lands_per_turn: int = 1
    spells_cast_this_turn: int = 0
    drew_from_empty_library: bool = False

    # Zone references (set by game during setup)
    library: Optional['Library'] = None
    hand: Optional['Hand'] = None
    graveyard: Optional['Graveyard'] = None

    # Reference to battlefield for convenience queries (set by game)
    _battlefield: Optional[Any] = field(default=None, repr=False)

    # AI agent reference (set by game if player is AI-controlled)
    ai: Optional[Any] = field(default=None, repr=False)

    def gain_life(self, amount: int) -> int:
        """Gain life.

        Args:
            amount: Amount of life to gain

        Returns:
            The actual amount of life gained (for triggers)

        Note:
            Life gain can be prevented or modified by effects.
            The return value indicates actual life gained.
        """
        if amount <= 0:
            return 0
        self.life += amount
        return amount

    def lose_life(self, amount: int) -> int:
        """Lose life (not from damage).

        This represents life loss from effects like "lose 2 life",
        which is different from damage and cannot be prevented by
        damage prevention effects.

        Args:
            amount: Amount of life to lose

        Returns:
            The actual amount of life lost

        Note:
            Life loss is different from damage (CR 119.3).
            Life loss cannot be prevented by damage prevention.
        """
        if amount <= 0:
            return 0
        self.life -= amount
        return amount

    def deal_damage(self, amount: int, source: Any) -> int:
        """Deal damage to this player.

        Damage is different from life loss (CR 120). Damage can be:
        - Prevented by prevention effects
        - Modified by replacement effects
        - Tracked for certain abilities

        Args:
            amount: Amount of damage to deal
            source: The source of the damage (permanent, spell, etc.)

        Returns:
            The actual amount of damage dealt after modifications

        Note:
            - Damage causes life loss equal to the damage dealt
            - Damage from a source with infect gives poison counters instead
            - Damage can be prevented; life loss cannot
        """
        if amount <= 0:
            return 0

        # TODO: Check for damage prevention effects
        # TODO: Check for infect (would give poison counters instead)
        # TODO: Check for lifelink on source (would gain life for source's controller)

        # For now, simple implementation: damage causes life loss
        actual_damage = amount
        self.life -= actual_damage
        return actual_damage

    def draw(self, count: int = 1) -> List['Card']:
        """Draw cards from library.

        Args:
            count: Number of cards to draw (default 1)

        Returns:
            List of Card objects that were drawn

        Note:
            If the library is empty when a player would draw,
            that player loses the game as a state-based action (CR 704.5b).
            This method sets drew_from_empty_library flag for SBA checking.
        """
        drawn_cards: List['Card'] = []

        if self.library is None:
            return drawn_cards

        for _ in range(count):
            if len(self.library) == 0:
                # Attempted to draw from empty library
                self.drew_from_empty_library = True
                break

            card = self.library.draw()
            if card is not None and self.hand is not None:
                self.hand.add(card)
                drawn_cards.append(card)

        return drawn_cards

    def discard(self, cards: List['Card']) -> None:
        """Discard cards from hand to graveyard.

        Args:
            cards: List of Card objects to discard

        Note:
            Discarding is a specific action that triggers "when discarded" abilities.
            This is different from cards being put into graveyard from other zones.
        """
        if self.hand is None or self.graveyard is None:
            return

        for card in cards:
            if self.hand.remove(card):
                self.graveyard.add(card)

    def lose_game(self, reason: str) -> None:
        """Mark this player as having lost the game.

        Args:
            reason: Description of why the player lost
                   (e.g., "life total reached 0", "drew from empty library",
                    "10 or more poison counters", "effect")
        """
        self.has_lost = True
        self.loss_reason = reason

    def can_play_land(self) -> bool:
        """Check if the player can play a land this turn.

        Returns:
            True if the player has land plays remaining

        Note:
            Default is 1 land per turn, but effects can modify max_lands_per_turn.
            Effects like Exploration add to the count.
            This only checks the count, not timing restrictions.
        """
        if self.land_played_this_turn:
            # Already used the default land play
            return self.max_lands_per_turn > 1
        return True

    def reset_turn_state(self) -> None:
        """Reset turn-based state at the start of a new turn.

        Called at the beginning of the turn to reset:
        - Land played tracking
        - Spells cast counter
        - Other per-turn tracking
        """
        self.land_played_this_turn = False
        self.spells_cast_this_turn = 0
        self.max_lands_per_turn = 1  # Reset to default, effects will modify

    def end_turn(self) -> None:
        """Clean up at the end of turn.

        Called during cleanup step to:
        - Empty mana pool (CR 514.3)
        - Any other end-of-turn player cleanup
        """
        self.mana_pool.empty()

    # =========================================================================
    # BATTLEFIELD QUERIES (Convenience Methods)
    # =========================================================================

    def creatures(self) -> List['Permanent']:
        """Get all creatures this player controls.

        Returns:
            List of Permanent objects that are creatures controlled by this player
        """
        if self._battlefield is None:
            return []
        return self._battlefield.creatures(self.player_id)

    def permanents(self) -> List['Permanent']:
        """Get all permanents this player controls.

        Returns:
            List of all Permanent objects controlled by this player
        """
        if self._battlefield is None:
            return []
        return self._battlefield.permanents(self.player_id)

    def lands(self) -> List['Permanent']:
        """Get all lands this player controls.

        Returns:
            List of Permanent objects that are lands controlled by this player
        """
        if self._battlefield is None:
            return []
        return self._battlefield.lands(self.player_id)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def is_alive(self) -> bool:
        """Check if this player is still in the game.

        Returns:
            True if the player has not lost
        """
        return not self.has_lost

    def hand_size(self) -> int:
        """Get the number of cards in hand.

        Returns:
            Number of cards in the player's hand
        """
        if self.hand is None:
            return 0
        return len(self.hand)

    def library_size(self) -> int:
        """Get the number of cards in library.

        Returns:
            Number of cards remaining in library
        """
        if self.library is None:
            return 0
        return len(self.library)

    def graveyard_size(self) -> int:
        """Get the number of cards in graveyard.

        Returns:
            Number of cards in graveyard
        """
        if self.graveyard is None:
            return 0
        return len(self.graveyard)

    def __str__(self) -> str:
        """String representation of the player."""
        status = "lost" if self.has_lost else f"life={self.life}"
        return f"Player({self.name}, {status})"

    def __hash__(self) -> int:
        """Make Player hashable based on player_id."""
        return hash(self.player_id)

    def __eq__(self, other) -> bool:
        """Compare players by player_id."""
        if isinstance(other, Player):
            return self.player_id == other.player_id
        return False

    def __repr__(self) -> str:
        """Debug representation of the player."""
        return (f"Player(id={self.player_id}, name={self.name!r}, "
                f"life={self.life}, poison={self.poison_counters}, "
                f"lost={self.has_lost})")


# =============================================================================
# PLAYER STATE SNAPSHOT
# =============================================================================

@dataclass
class PlayerState:
    """Snapshot of player state for AI/analysis.

    This is an immutable view of a player's current state, useful for
    AI decision making and game state analysis without direct references
    to mutable game objects.
    """
    player_id: PlayerId
    life: int
    poison_counters: int
    hand_size: int
    library_size: int
    graveyard_size: int
    creatures_count: int
    lands_count: int
    total_power: int
    mana_available: int
    has_lost: bool

    @classmethod
    def from_player(cls, player: Player) -> 'PlayerState':
        """Create a snapshot from a Player object.

        Args:
            player: The Player to snapshot

        Returns:
            PlayerState snapshot
        """
        creatures = player.creatures()
        total_power = sum(
            getattr(c, 'power', 0)
            for c in creatures
            if hasattr(c, 'power')
        )

        return cls(
            player_id=player.player_id,
            life=player.life,
            poison_counters=player.poison_counters,
            hand_size=player.hand_size(),
            library_size=player.library_size(),
            graveyard_size=player.graveyard_size(),
            creatures_count=len(creatures),
            lands_count=len(player.lands()),
            total_power=total_power,
            mana_available=player.mana_pool.total(),
            has_lost=player.has_lost
        )
