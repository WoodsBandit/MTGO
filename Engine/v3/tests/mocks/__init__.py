"""
Mock objects for MTG Engine V3 testing.

This package provides lightweight mock implementations of game objects
for isolated unit testing without the full engine overhead.

Modules:
- mock_game: MockGame for testing game-level interactions
- mock_player: MockPlayer for testing player actions
- mock_objects: MockCard, MockPermanent, MockCreature for testing game objects
"""

from .mock_game import MockGame
from .mock_player import MockPlayer
from .mock_objects import MockCard, MockPermanent, MockCreature

__all__ = [
    'MockGame',
    'MockPlayer',
    'MockCard',
    'MockPermanent',
    'MockCreature',
]
