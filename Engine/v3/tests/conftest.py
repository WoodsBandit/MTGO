"""
Shared pytest fixtures for MTG Engine V3 tests.

This module provides reusable fixtures for common test scenarios including:
- Game instances (2-player and 4-player multiplayer)
- Mock players and game objects
- Empty battlefield states
- Test card objects

Following pytest best practices for fixture design and reusability.
"""

import pytest
from typing import List, Dict

from ..engine.game import Game, GameConfig
from ..engine.player import Player, ManaPool
from ..engine.objects import Card, Permanent, Characteristics, GameObject
from ..engine.types import Color, CardType, Supertype, Zone, PlayerId
from .mocks.mock_game import MockGame
from .mocks.mock_player import MockPlayer
from .mocks.mock_objects import MockCard, MockPermanent, MockCreature


# =============================================================================
# Game Fixtures
# =============================================================================

@pytest.fixture
def game():
    """
    Create a standard 2-player game for testing.

    Returns:
        Game: A freshly initialized game with 2 players, no decks loaded.

    Usage:
        def test_something(game):
            assert game.turn_number == 0
            assert len(game.players) == 2
    """
    config = GameConfig(
        starting_life=20,
        starting_hand_size=7,
        max_turns=50,
        verbose=False
    )
    return Game(player_ids=[1, 2], config=config)


@pytest.fixture
def multiplayer_game():
    """
    Create a 4-player multiplayer game for testing.

    Returns:
        Game: A freshly initialized game with 4 players for multiplayer scenarios.

    Usage:
        def test_multiplayer(multiplayer_game):
            assert len(multiplayer_game.players) == 4
    """
    config = GameConfig(
        starting_life=20,
        starting_hand_size=7,
        max_turns=50,
        verbose=False
    )
    return Game(player_ids=[1, 2, 3, 4], config=config)


@pytest.fixture
def mock_game():
    """
    Create a lightweight mock game for isolated testing.

    Returns:
        MockGame: A simple mock game object for testing without full engine.

    Usage:
        def test_priority(mock_game):
            # Test priority system without full game overhead
            pass
    """
    return MockGame(player_ids=[1, 2])


# =============================================================================
# Player Fixtures
# =============================================================================

@pytest.fixture
def player1(game):
    """
    Get player 1 from a standard 2-player game.

    Args:
        game: The game fixture

    Returns:
        Player: Player 1 (player_id=1)

    Usage:
        def test_player(player1):
            assert player1.player_id == 1
            assert player1.life == 20
    """
    return game.players[1]


@pytest.fixture
def player2(game):
    """
    Get player 2 from a standard 2-player game.

    Args:
        game: The game fixture

    Returns:
        Player: Player 2 (player_id=2)
    """
    return game.players[2]


@pytest.fixture
def mock_player():
    """
    Create a lightweight mock player for isolated testing.

    Returns:
        MockPlayer: A simple mock player object.

    Usage:
        def test_mana_pool(mock_player):
            mock_player.mana_pool.add(Color.BLUE, 3)
            assert mock_player.mana_pool.get(Color.BLUE) == 3
    """
    return MockPlayer(player_id=1, name="Test Player")


# =============================================================================
# Battlefield Fixtures
# =============================================================================

@pytest.fixture
def empty_battlefield(game):
    """
    Create a game with an empty battlefield state.

    Ensures the battlefield has no permanents, useful for testing
    battlefield interactions from a clean slate.

    Args:
        game: The game fixture

    Returns:
        Game: The game with confirmed empty battlefield

    Usage:
        def test_etb(empty_battlefield):
            assert len(empty_battlefield.zones.battlefield) == 0
            # Add creature, test ETB effects
    """
    game.zones.battlefield.clear()
    return game


# =============================================================================
# Card and Object Fixtures
# =============================================================================

@pytest.fixture
def mock_card():
    """
    Create a generic mock card for testing.

    Returns:
        MockCard: A simple card with basic characteristics.

    Usage:
        def test_cast_spell(game, mock_card):
            # Use mock_card to test spell casting
            pass
    """
    return MockCard(
        name="Test Card",
        mana_cost="{2}{U}",
        types={CardType.INSTANT},
        colors={Color.BLUE}
    )


@pytest.fixture
def mock_creature():
    """
    Create a generic mock creature for testing.

    Returns:
        MockCreature: A simple 2/2 creature.

    Usage:
        def test_combat(game, mock_creature):
            # Add creature to battlefield, test combat
            game.zones.battlefield.add(mock_creature)
    """
    return MockCreature(
        name="Test Creature",
        mana_cost="{1}{G}",
        power=2,
        toughness=2,
        colors={Color.GREEN}
    )


@pytest.fixture
def mock_permanent(game, player1):
    """
    Create a generic mock permanent on the battlefield.

    Args:
        game: The game fixture
        player1: Owner/controller of the permanent

    Returns:
        MockPermanent: A permanent already on the battlefield.

    Usage:
        def test_permanent_ability(mock_permanent):
            assert mock_permanent.zone == Zone.BATTLEFIELD
    """
    perm = MockPermanent(
        object_id=game.next_object_id(),
        owner=player1,
        controller=player1,
        name="Test Permanent",
        types={CardType.ARTIFACT}
    )
    perm.zone = Zone.BATTLEFIELD
    return perm


# =============================================================================
# Mana Pool Fixtures
# =============================================================================

@pytest.fixture
def mana_pool():
    """
    Create an empty mana pool for testing mana operations.

    Returns:
        ManaPool: Fresh mana pool with all colors at 0.

    Usage:
        def test_mana_payment(mana_pool):
            mana_pool.add(Color.RED, 2)
            assert mana_pool.can_pay({Color.RED: 1})
    """
    return ManaPool()


@pytest.fixture
def mana_pool_with_mana(mana_pool):
    """
    Create a mana pool pre-loaded with test mana.

    Provides:
    - 2 White mana
    - 3 Blue mana
    - 1 Black mana
    - 2 Red mana
    - 1 Green mana
    - 3 Colorless mana

    Args:
        mana_pool: The base mana pool fixture

    Returns:
        ManaPool: Mana pool with diverse mana for testing costs.

    Usage:
        def test_complex_cost(mana_pool_with_mana):
            assert mana_pool_with_mana.total() == 12
    """
    mana_pool.add(Color.WHITE, 2)
    mana_pool.add(Color.BLUE, 3)
    mana_pool.add(Color.BLACK, 1)
    mana_pool.add(Color.RED, 2)
    mana_pool.add(Color.GREEN, 1)
    mana_pool.add(Color.COLORLESS, 3)
    return mana_pool


# =============================================================================
# Card Factory Fixtures
# =============================================================================

@pytest.fixture
def card_factory(game):
    """
    Factory fixture for creating test cards with custom attributes.

    Args:
        game: The game fixture for object IDs

    Returns:
        Callable: Function to create cards with specified attributes.

    Usage:
        def test_cards(card_factory):
            giant = card_factory(name="Giant", power=4, toughness=4)
            bolt = card_factory(name="Bolt", types={CardType.INSTANT})
    """
    def _create_card(
        name: str = "Test Card",
        mana_cost: str = "{2}",
        types: set = None,
        colors: set = None,
        power: int = None,
        toughness: int = None,
        rules_text: str = ""
    ) -> Card:
        """
        Create a card with specified attributes.

        Args:
            name: Card name
            mana_cost: Mana cost string like "{2}{U}{U}"
            types: Set of CardType enums
            colors: Set of Color enums
            power: Power (for creatures)
            toughness: Toughness (for creatures)
            rules_text: Rules text/oracle text

        Returns:
            Card: A fully initialized card object
        """
        if types is None:
            types = {CardType.ARTIFACT}
        if colors is None:
            colors = set()

        chars = Characteristics(
            name=name,
            mana_cost=mana_cost,
            colors=colors,
            types=types,
            power=power,
            toughness=toughness,
            rules_text=rules_text
        )

        card = Card(
            object_id=game.next_object_id(),
            base_characteristics=chars,
            characteristics=chars.copy()
        )
        return card

    return _create_card


@pytest.fixture
def permanent_factory(game, player1):
    """
    Factory fixture for creating test permanents.

    Args:
        game: The game fixture
        player1: Default owner/controller

    Returns:
        Callable: Function to create permanents with specified attributes.

    Usage:
        def test_battlefield(permanent_factory):
            bear = permanent_factory(power=2, toughness=2)
            game.zones.battlefield.add(bear)
    """
    def _create_permanent(
        name: str = "Test Permanent",
        types: set = None,
        power: int = None,
        toughness: int = None,
        controller: Player = None
    ) -> Permanent:
        """
        Create a permanent with specified attributes.

        Args:
            name: Permanent name
            types: Set of CardType enums
            power: Power (for creatures)
            toughness: Toughness (for creatures)
            controller: Controlling player (defaults to player1)

        Returns:
            Permanent: A permanent ready to be added to battlefield
        """
        if types is None:
            types = {CardType.CREATURE}
        if controller is None:
            controller = player1

        chars = Characteristics(
            name=name,
            types=types,
            power=power,
            toughness=toughness
        )

        perm = Permanent(
            object_id=game.next_object_id(),
            base_characteristics=chars,
            characteristics=chars.copy(),
            owner=controller,
            controller=controller,
            zone=Zone.BATTLEFIELD,
            timestamp=game.get_timestamp()
        )
        return perm

    return _create_permanent


# =============================================================================
# Priority Test Fixtures
# =============================================================================

@pytest.fixture
def priority_system(game):
    """
    Get the priority system from a game for direct testing.

    Args:
        game: The game fixture

    Returns:
        PrioritySystem: The game's priority system

    Usage:
        def test_priority_passing(priority_system, player1):
            priority_system.give_priority(player1)
            assert priority_system.get_priority_holder() == player1
    """
    return game.priority


@pytest.fixture
def priority_with_active_player(game, player1):
    """
    Setup priority system with player1 as active player.

    Args:
        game: The game fixture
        player1: Player 1

    Returns:
        PrioritySystem: Priority system with active player set

    Usage:
        def test_active_priority(priority_with_active_player):
            # Player 1 is active and has priority
            pass
    """
    game.active_player_id = player1.player_id
    game.priority.give_priority(player1)
    return game.priority


# =============================================================================
# Stack Test Fixtures
# =============================================================================

@pytest.fixture
def stack(game):
    """
    Get the stack from a game for direct testing.

    Args:
        game: The game fixture

    Returns:
        Stack: The game's stack zone

    Usage:
        def test_stack_operations(stack):
            assert stack.is_empty()
            # Push spells, test LIFO ordering
    """
    return game.zones.stack


@pytest.fixture
def empty_stack(stack):
    """
    Ensure the stack is empty.

    Args:
        stack: The stack fixture

    Returns:
        Stack: An empty stack

    Usage:
        def test_from_empty(empty_stack):
            assert empty_stack.is_empty()
    """
    stack.clear()
    return stack
