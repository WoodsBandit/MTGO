"""Core engine components - lazy imports to avoid circular dependencies"""

# Core types can be imported directly
from .types import (
    Color, CardType, StepType, PhaseType, Zone as ZoneType,
    CounterType, KeywordAbility, AbilityType, Layer, GameEventType
)

# Other imports are lazy to avoid circular dependencies
def __getattr__(name):
    """Lazy import for engine components."""
    if name == 'Game':
        from .game import Game
        return Game
    elif name == 'Player':
        from .player import Player
        return Player
    elif name == 'GameObject':
        from .objects import GameObject
        return GameObject
    elif name == 'Permanent':
        from .objects import Permanent
        return Permanent
    elif name == 'Spell':
        from .objects import Spell
        return Spell
    elif name == 'Card':
        from .objects import Card
        return Card
    elif name == 'ZoneManager':
        from .zones import ZoneManager
        return ZoneManager
    elif name == 'Stack':
        from .stack import Stack
        return Stack
    elif name == 'PrioritySystem':
        from .priority import PrioritySystem
        return PrioritySystem
    elif name == 'CombatManager':
        from .combat import CombatManager
        return CombatManager
    elif name == 'ManaCost':
        from .mana import ManaCost
        return ManaCost
    elif name == 'ManaPool':
        from .mana import ManaPool
        return ManaPool
    elif name == 'Mana':
        from .mana import Mana
        return Mana
    elif name == 'StateBasedActionChecker':
        from .sba import StateBasedActionChecker
        return StateBasedActionChecker
    elif name == 'TurnManager':
        from .turns import TurnManager
        return TurnManager
    elif name == 'TargetChecker':
        from .targeting import TargetChecker
        return TargetChecker
    elif name == 'EventBus':
        from .events import EventBus
        return EventBus
    elif name == 'Match':
        from .match import Match
        return Match
    raise AttributeError(f"module 'engine' has no attribute {name!r}")
