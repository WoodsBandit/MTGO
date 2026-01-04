"""
MTGO Timer and Priority Stop System
====================================

Implements MTGO-style chess timer and configurable priority stops.

Features:
- Chess clock timer with format-specific configurations
- Priority stop configuration (which phases to auto-pass)
- Yield system (F4/F6/F8 shortcuts)
- Keyboard shortcut handling

Usage:
------
from mtgo_timer import ChessTimer, PriorityStops, InputHandler, TimeoutException

# Create timer for a match
timer = ChessTimer('tournament_practice')
timer.start()
timer.switch_to('player1')

# Priority stops per player
stops = PriorityStops(player)
if stops.should_stop('main1', is_active=True, has_stack=False):
    # Give player priority
    ...

# Handle keyboard input
handler = InputHandler(game, player)
action = handler.process_key('F4')  # Yield until end of turn


Integration with Game class:
----------------------------
To integrate with mtg_engine.Game, add these attributes in __init__:

    from mtgo_timer import TimerManager

    class Game:
        def __init__(self, ...):
            # ... existing init code ...

            # Add timer and priority system
            self.timer_manager = TimerManager(
                game=self,
                format_type='tournament_practice',
                player_keys=['player1', 'player2']
            )

            # Convenience aliases
            self.timer = self.timer_manager.timer
            self.priority_stops = self.timer_manager.priority_stops

Then modify priority passing:

    def give_priority(self, player_key):
        # Check if should auto-pass
        if self.timer_manager.should_auto_pass(
            player_key, self.current_phase,
            is_active=(player_key == self.active_player_key),
            has_stack=len(self.stack) > 0,
            current_turn=self.turn
        ):
            return self.auto_pass(player_key)

        # Switch timer
        self.timer_manager.on_priority_change(self.last_priority, player_key)

        # Actually give priority
        ...

Keyboard shortcuts:

    action = self.timer_manager.process_input(player_key, key, self.turn)
    if isinstance(action, PassPriorityAction):
        self.pass_priority(player_key)
    elif isinstance(action, YieldAction):
        # Already handled by InputHandler
        self.pass_priority(player_key)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable, List
from enum import Enum, auto
from copy import deepcopy


# =============================================================================
# EXCEPTIONS
# =============================================================================

class TimeoutException(Exception):
    """Raised when a player runs out of time"""

    def __init__(self, player_key: str, message: str = None):
        self.player_key = player_key
        self.message = message or f"Player {player_key} has run out of time"
        super().__init__(self.message)


class InvalidPhaseError(Exception):
    """Raised when an invalid phase name is used"""
    pass


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class Phase(Enum):
    """All phases/steps in MTG where priority can be given"""
    UNTAP = auto()
    UPKEEP = auto()
    DRAW = auto()
    MAIN1 = auto()
    BEGIN_COMBAT = auto()
    DECLARE_ATTACKERS = auto()
    DECLARE_BLOCKERS = auto()
    FIRST_STRIKE_DAMAGE = auto()
    COMBAT_DAMAGE = auto()
    END_COMBAT = auto()
    MAIN2 = auto()
    END_STEP = auto()
    CLEANUP = auto()


class YieldType(Enum):
    """Types of yields (auto-pass) a player can set"""
    NONE = auto()           # No yield active
    END_OF_TURN = auto()    # Yield until end of current turn (F4)
    STACK_EMPTY = auto()    # Yield until stack is empty (F8)
    ALL = auto()            # Yield all priority forever (F6)


# Phase name mappings for string-based access
PHASE_NAMES = {
    'untap': Phase.UNTAP,
    'upkeep': Phase.UPKEEP,
    'draw': Phase.DRAW,
    'main1': Phase.MAIN1,
    'precombat_main': Phase.MAIN1,
    'begin_combat': Phase.BEGIN_COMBAT,
    'beginning_of_combat': Phase.BEGIN_COMBAT,
    'declare_attackers': Phase.DECLARE_ATTACKERS,
    'attackers': Phase.DECLARE_ATTACKERS,
    'declare_blockers': Phase.DECLARE_BLOCKERS,
    'blockers': Phase.DECLARE_BLOCKERS,
    'first_strike_damage': Phase.FIRST_STRIKE_DAMAGE,
    'first_strike': Phase.FIRST_STRIKE_DAMAGE,
    'combat_damage': Phase.COMBAT_DAMAGE,
    'damage': Phase.COMBAT_DAMAGE,
    'end_combat': Phase.END_COMBAT,
    'end_of_combat': Phase.END_COMBAT,
    'main2': Phase.MAIN2,
    'postcombat_main': Phase.MAIN2,
    'end_step': Phase.END_STEP,
    'end': Phase.END_STEP,
    'cleanup': Phase.CLEANUP,
}


# =============================================================================
# PRIORITY STOP CONFIGURATION
# =============================================================================

@dataclass
class StopConfig:
    """Configuration for a single phase stop"""
    yours: bool = False      # Stop when you are active player
    opponents: bool = False  # Stop when opponent is active player

    def copy(self) -> 'StopConfig':
        return StopConfig(yours=self.yours, opponents=self.opponents)


class PriorityStops:
    """
    MTGO-style configurable priority stops.

    Manages when a player should receive priority during a game.
    Players can configure which phases they want to stop at for both
    their own turns and opponent turns.

    Attributes:
        player: The player this configuration belongs to
        stops: Dict mapping phase names to StopConfig
        yield_until: Current yield type (if any)
        yield_turn_number: Turn number when yield was set (for end_of_turn)
    """

    # Default MTGO stop configuration
    DEFAULT_STOPS: Dict[str, Dict[str, bool]] = {
        'upkeep': {'yours': False, 'opponents': True},
        'draw': {'yours': False, 'opponents': False},
        'main1': {'yours': True, 'opponents': False},
        'begin_combat': {'yours': True, 'opponents': True},
        'declare_attackers': {'yours': True, 'opponents': True},
        'declare_blockers': {'yours': True, 'opponents': True},
        'first_strike_damage': {'yours': True, 'opponents': True},
        'combat_damage': {'yours': True, 'opponents': True},
        'end_combat': {'yours': False, 'opponents': False},
        'main2': {'yours': True, 'opponents': False},
        'end_step': {'yours': True, 'opponents': True},
    }

    def __init__(self, player: Any = None):
        """
        Initialize priority stops with default configuration.

        Args:
            player: The player object this configuration belongs to
        """
        self.player = player
        self.stops: Dict[str, StopConfig] = {}
        self.yield_until: YieldType = YieldType.NONE
        self.yield_turn_number: Optional[int] = None

        # Initialize from defaults
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default stop configuration"""
        for phase, config in self.DEFAULT_STOPS.items():
            self.stops[phase] = StopConfig(
                yours=config['yours'],
                opponents=config['opponents']
            )

    def _normalize_phase(self, phase: str) -> str:
        """Normalize phase name to standard form"""
        phase_lower = phase.lower().replace(' ', '_').replace('-', '_')
        if phase_lower in PHASE_NAMES:
            # Map to standard name
            phase_enum = PHASE_NAMES[phase_lower]
            # Find the standard name for this enum
            for name, enum_val in PHASE_NAMES.items():
                if enum_val == phase_enum and name in self.DEFAULT_STOPS:
                    return name
        return phase_lower

    def should_stop(
        self,
        phase: str,
        is_active: bool,
        has_stack: bool,
        current_turn: int = 0
    ) -> bool:
        """
        Determine if player should receive priority at this phase.

        Args:
            phase: Current phase name (e.g., 'main1', 'declare_attackers')
            is_active: True if this player is the active player
            has_stack: True if there are items on the stack
            current_turn: Current turn number (for yield_until checks)

        Returns:
            True if player should receive priority, False to auto-pass
        """
        # Always stop if stack has items (something to respond to)
        if has_stack:
            # Clear F8 yield if stack just got items after being empty
            if self.yield_until == YieldType.STACK_EMPTY:
                self.yield_until = YieldType.NONE
            return True

        # Check yield settings
        if self.yield_until == YieldType.ALL:
            # F6 - yield everything
            return False

        if self.yield_until == YieldType.END_OF_TURN:
            # F4 - yield until end of turn
            if self.yield_turn_number is not None and current_turn > self.yield_turn_number:
                # New turn, clear yield
                self.yield_until = YieldType.NONE
            else:
                return False

        if self.yield_until == YieldType.STACK_EMPTY:
            # F8 - yield until stack empty (and stack IS empty here)
            return False

        # Check configured stops for this phase
        phase_normalized = self._normalize_phase(phase)

        if phase_normalized not in self.stops:
            # Unknown phase, default to stopping
            return True

        config = self.stops[phase_normalized]

        if is_active:
            return config.yours
        else:
            return config.opponents

    def set_yield(self, yield_type: str, current_turn: int = 0) -> None:
        """
        Set a yield (auto-pass) mode.

        Args:
            yield_type: One of 'end_of_turn', 'stack_empty', 'all', or 'none'
            current_turn: Current turn number (for end_of_turn tracking)
        """
        yield_map = {
            'end_of_turn': YieldType.END_OF_TURN,
            'stack_empty': YieldType.STACK_EMPTY,
            'all': YieldType.ALL,
            'none': YieldType.NONE,
        }

        yield_type_lower = yield_type.lower().replace(' ', '_').replace('-', '_')

        if yield_type_lower not in yield_map:
            raise ValueError(f"Invalid yield type: {yield_type}. "
                           f"Valid options: {list(yield_map.keys())}")

        self.yield_until = yield_map[yield_type_lower]

        if self.yield_until == YieldType.END_OF_TURN:
            self.yield_turn_number = current_turn
        else:
            self.yield_turn_number = None

    def clear_yield(self) -> None:
        """
        Clear any active yield.

        Called automatically when opponent takes an action that requires
        attention, or at the start of a new turn.
        """
        self.yield_until = YieldType.NONE
        self.yield_turn_number = None

    def set_stop(
        self,
        phase: str,
        yours: Optional[bool] = None,
        opponents: Optional[bool] = None
    ) -> None:
        """
        Configure a stop for a specific phase.

        Args:
            phase: Phase name (e.g., 'main1', 'upkeep')
            yours: Whether to stop on your turn (None = don't change)
            opponents: Whether to stop on opponent's turn (None = don't change)
        """
        phase_normalized = self._normalize_phase(phase)

        if phase_normalized not in self.stops:
            self.stops[phase_normalized] = StopConfig()

        if yours is not None:
            self.stops[phase_normalized].yours = yours
        if opponents is not None:
            self.stops[phase_normalized].opponents = opponents

    def toggle_stop(self, phase: str, is_yours: bool) -> bool:
        """
        Toggle a stop setting and return new value.

        Args:
            phase: Phase name
            is_yours: True to toggle 'yours', False to toggle 'opponents'

        Returns:
            New value of the toggled setting
        """
        phase_normalized = self._normalize_phase(phase)

        if phase_normalized not in self.stops:
            self.stops[phase_normalized] = StopConfig()

        config = self.stops[phase_normalized]

        if is_yours:
            config.yours = not config.yours
            return config.yours
        else:
            config.opponents = not config.opponents
            return config.opponents

    def get_stops_display(self) -> Dict[str, Dict[str, bool]]:
        """
        Get all stops in display format.

        Returns:
            Dict mapping phase names to {'yours': bool, 'opponents': bool}
        """
        result = {}
        for phase, config in self.stops.items():
            result[phase] = {
                'yours': config.yours,
                'opponents': config.opponents
            }
        return result

    def reset_to_defaults(self) -> None:
        """Reset all stops to default configuration"""
        self._load_defaults()
        self.clear_yield()

    def copy(self) -> 'PriorityStops':
        """Create a deep copy of this configuration"""
        new_stops = PriorityStops(self.player)
        new_stops.stops = {k: v.copy() for k, v in self.stops.items()}
        new_stops.yield_until = self.yield_until
        new_stops.yield_turn_number = self.yield_turn_number
        return new_stops


# =============================================================================
# CHESS TIMER
# =============================================================================

class ChessTimer:
    """
    MTGO-style chess clock for match timing.

    Implements a chess clock where each player has their own time pool.
    Time counts down only for the player who currently has priority.
    Some formats include reserve time that activates when main time runs out.

    Attributes:
        format_type: The timer format being used
        time_remaining: Dict mapping player keys to remaining seconds
        reserve: Dict mapping player keys to reserve time seconds
        active_player_clock: Key of player whose clock is running
        is_running: Whether the timer is currently counting down
    """

    # MTGO timer format configurations
    FORMATS: Dict[str, Dict[str, int]] = {
        'open_play': {'initial': 60 * 60, 'reserve': 0},           # 60 min casual
        'tournament_practice': {'initial': 25 * 60, 'reserve': 0}, # 25 min
        'league': {'initial': 25 * 60, 'reserve': 0},              # 25 min
        'challenge': {'initial': 25 * 60, 'reserve': 0},           # 25 min
        'premier': {'initial': 25 * 60, 'reserve': 5 * 60},        # 25 + 5 reserve
        'vintage_challenge': {'initial': 25 * 60, 'reserve': 0},   # 25 min
        'legacy_challenge': {'initial': 25 * 60, 'reserve': 0},    # 25 min
        'modern_challenge': {'initial': 25 * 60, 'reserve': 0},    # 25 min
        'standard_challenge': {'initial': 25 * 60, 'reserve': 0},  # 25 min
        'limited': {'initial': 25 * 60, 'reserve': 0},             # 25 min for draft/sealed
        'cube': {'initial': 25 * 60, 'reserve': 0},                # 25 min
        'test': {'initial': 5 * 60, 'reserve': 1 * 60},            # 5 + 1 for testing
        'blitz': {'initial': 3 * 60, 'reserve': 0},                # 3 min speed format
        'unlimited': {'initial': 99 * 60 * 60, 'reserve': 0},      # Effectively unlimited
    }

    def __init__(
        self,
        format_type: str = 'tournament_practice',
        player_keys: Optional[List[str]] = None
    ):
        """
        Initialize chess timer for a match.

        Args:
            format_type: Timer format (see FORMATS for options)
            player_keys: List of player identifiers (default: ['player1', 'player2'])

        Raises:
            ValueError: If format_type is not recognized
        """
        if format_type not in self.FORMATS:
            raise ValueError(
                f"Unknown format: {format_type}. "
                f"Valid formats: {list(self.FORMATS.keys())}"
            )

        self.format_type = format_type
        config = self.FORMATS[format_type]

        if player_keys is None:
            player_keys = ['player1', 'player2']

        self.player_keys = player_keys
        self.time_remaining: Dict[str, float] = {
            key: float(config['initial']) for key in player_keys
        }
        self.reserve: Dict[str, float] = {
            key: float(config['reserve']) for key in player_keys
        }

        self.active_player_clock: Optional[str] = None
        self.is_running: bool = False
        self.last_tick: Optional[float] = None

        # Callbacks for time events
        self.on_low_time: Optional[Callable[[str, float], None]] = None
        self.on_timeout: Optional[Callable[[str], None]] = None
        self.low_time_threshold: float = 60.0  # Warn when under 1 minute
        self._low_time_warned: Dict[str, bool] = {key: False for key in player_keys}

    def start(self) -> None:
        """Start the timer running"""
        self.is_running = True
        self.last_tick = time.time()

    def pause(self) -> None:
        """Pause the timer (e.g., for sideboarding)"""
        if self.is_running:
            self._update_time()
        self.is_running = False

    def resume(self) -> None:
        """Resume a paused timer"""
        if not self.is_running:
            self.is_running = True
            self.last_tick = time.time()

    def switch_to(self, player_key: str) -> None:
        """
        Switch active clock to a different player.

        Called when priority passes from one player to another.

        Args:
            player_key: Key of player to switch to

        Raises:
            ValueError: If player_key is not valid
        """
        if player_key not in self.time_remaining:
            raise ValueError(f"Unknown player: {player_key}")

        if self.is_running:
            self._update_time()

        self.active_player_clock = player_key
        self.last_tick = time.time()

    def _update_time(self) -> None:
        """Update time for active player (internal method)"""
        if not self.is_running or self.active_player_clock is None:
            return

        now = time.time()
        elapsed = now - self.last_tick
        self.last_tick = now

        player = self.active_player_clock
        self.time_remaining[player] -= elapsed

        # Check for low time warning
        if (self.time_remaining[player] <= self.low_time_threshold
            and not self._low_time_warned[player]
            and self.time_remaining[player] > 0):
            self._low_time_warned[player] = True
            if self.on_low_time:
                self.on_low_time(player, self.time_remaining[player])

        # Check for timeout
        if self.time_remaining[player] <= 0:
            self._handle_timeout()

    def _handle_timeout(self) -> None:
        """Handle player running out of time"""
        player = self.active_player_clock

        if self.reserve[player] > 0:
            # Transfer reserve time to main time
            self.time_remaining[player] = self.reserve[player]
            self.reserve[player] = 0.0
            self._low_time_warned[player] = False  # Reset warning for reserve
        else:
            # Player loses on time
            self.is_running = False
            if self.on_timeout:
                self.on_timeout(player)
            raise TimeoutException(player)

    def get_time(self, player_key: str) -> float:
        """
        Get remaining time for a player in seconds.

        Args:
            player_key: Player to check

        Returns:
            Remaining time in seconds (float)
        """
        if player_key not in self.time_remaining:
            raise ValueError(f"Unknown player: {player_key}")

        # Update first if this player's clock is running
        if self.is_running and self.active_player_clock == player_key:
            self._update_time()

        return max(0.0, self.time_remaining[player_key])

    def get_reserve(self, player_key: str) -> float:
        """
        Get remaining reserve time for a player.

        Args:
            player_key: Player to check

        Returns:
            Remaining reserve time in seconds
        """
        if player_key not in self.reserve:
            raise ValueError(f"Unknown player: {player_key}")
        return self.reserve[player_key]

    def get_display(self, player_key: str) -> str:
        """
        Format time for display as MM:SS.

        Args:
            player_key: Player to format time for

        Returns:
            Formatted time string (e.g., "24:35" or "00:05")
        """
        seconds = int(self.get_time(player_key))
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    def get_display_full(self, player_key: str) -> str:
        """
        Format time with reserve for display.

        Args:
            player_key: Player to format time for

        Returns:
            Formatted time string (e.g., "24:35 (+5:00)" or "24:35")
        """
        main_display = self.get_display(player_key)
        reserve = self.reserve[player_key]

        if reserve > 0:
            reserve_mins = int(reserve) // 60
            reserve_secs = int(reserve) % 60
            return f"{main_display} (+{reserve_mins:02d}:{reserve_secs:02d})"

        return main_display

    def add_time(self, player_key: str, seconds: float) -> None:
        """
        Add time to a player's clock (e.g., for extensions).

        Args:
            player_key: Player to add time to
            seconds: Seconds to add
        """
        if player_key not in self.time_remaining:
            raise ValueError(f"Unknown player: {player_key}")

        self.time_remaining[player_key] += seconds

    def set_time(self, player_key: str, seconds: float) -> None:
        """
        Set a player's time directly.

        Args:
            player_key: Player to set time for
            seconds: New time in seconds
        """
        if player_key not in self.time_remaining:
            raise ValueError(f"Unknown player: {player_key}")

        self.time_remaining[player_key] = max(0.0, seconds)

    def get_all_times(self) -> Dict[str, Dict[str, float]]:
        """
        Get all player times.

        Returns:
            Dict with player keys mapping to {'remaining': float, 'reserve': float}
        """
        if self.is_running:
            self._update_time()

        return {
            key: {
                'remaining': max(0.0, self.time_remaining[key]),
                'reserve': self.reserve[key]
            }
            for key in self.player_keys
        }

    def is_timeout(self, player_key: str) -> bool:
        """
        Check if a player has timed out.

        Args:
            player_key: Player to check

        Returns:
            True if player has no time remaining
        """
        return (self.get_time(player_key) <= 0
                and self.get_reserve(player_key) <= 0)

    def reset(self) -> None:
        """Reset timer to initial state"""
        config = self.FORMATS[self.format_type]

        for key in self.player_keys:
            self.time_remaining[key] = float(config['initial'])
            self.reserve[key] = float(config['reserve'])
            self._low_time_warned[key] = False

        self.active_player_clock = None
        self.is_running = False
        self.last_tick = None


# =============================================================================
# KEYBOARD SHORTCUTS
# =============================================================================

# MTGO keyboard shortcut mappings
MTGO_SHORTCUTS: Dict[str, str] = {
    '3': 'yes',              # Confirm/OK
    '4': 'no',               # Cancel/No
    'F2': 'pass_priority',   # OK/Pass priority
    'F4': 'yield_turn',      # Yield until end of turn
    'F6': 'yield_all',       # Yield all priority
    'F8': 'yield_stack',     # Yield until stack empty
    'Q': 'zoom_card',        # Zoom on card
    'Ctrl+Z': 'undo_mana',   # Undo mana ability
    'Tab': 'cycle_select',   # Cycle through selectable objects
    'Space': 'confirm',      # Alternative confirm
    'Enter': 'confirm',      # Alternative confirm
    'Escape': 'cancel',      # Cancel current action
    'Z': 'undo',             # Undo last action (if allowed)
}


@dataclass
class Action:
    """Base class for player actions"""
    action_type: str
    data: Optional[Any] = None

    def __repr__(self) -> str:
        if self.data:
            return f"Action({self.action_type}, {self.data})"
        return f"Action({self.action_type})"


class PassPriorityAction(Action):
    """Action representing passing priority"""
    def __init__(self):
        super().__init__('pass_priority')


class YieldAction(Action):
    """Action representing setting a yield"""
    def __init__(self, yield_type: str):
        super().__init__('yield', yield_type)


class CancelAction(Action):
    """Action representing canceling current action"""
    def __init__(self):
        super().__init__('cancel')


class ConfirmAction(Action):
    """Action representing confirming a choice"""
    def __init__(self, choice: Optional[Any] = None):
        super().__init__('confirm', choice)


class UndoAction(Action):
    """Action representing undoing last action"""
    def __init__(self, undo_type: str = 'mana'):
        super().__init__('undo', undo_type)


class ZoomAction(Action):
    """Action for zooming on a card"""
    def __init__(self, card: Optional[Any] = None):
        super().__init__('zoom', card)


class InputHandler:
    """
    Handles keyboard input and translates to game actions.

    Manages the mapping between MTGO keyboard shortcuts and
    game actions, including priority stop configuration.

    Attributes:
        game: Reference to the game object
        player: The player this handler belongs to
        priority_stops: Priority stop configuration for this player
    """

    def __init__(self, game: Any, player: Any):
        """
        Initialize input handler.

        Args:
            game: Game object reference
            player: Player object this handler is for
        """
        self.game = game
        self.player = player
        self.priority_stops = PriorityStops(player)

        # Custom shortcut overrides
        self.custom_shortcuts: Dict[str, str] = {}

        # Context for multi-key sequences
        self.pending_modifier: Optional[str] = None

        # Currently selected/hovered card for zoom
        self.hovered_card: Optional[Any] = None

    def get_shortcuts(self) -> Dict[str, str]:
        """Get current shortcut mappings (base + custom overrides)"""
        shortcuts = MTGO_SHORTCUTS.copy()
        shortcuts.update(self.custom_shortcuts)
        return shortcuts

    def set_custom_shortcut(self, key: str, action: str) -> None:
        """
        Set a custom shortcut override.

        Args:
            key: Key combination (e.g., 'F5', 'Ctrl+X')
            action: Action name to map to
        """
        self.custom_shortcuts[key] = action

    def clear_custom_shortcut(self, key: str) -> None:
        """Remove a custom shortcut override"""
        self.custom_shortcuts.pop(key, None)

    def process_key(self, key: str, current_turn: int = 0) -> Optional[Action]:
        """
        Process a keyboard input and return corresponding action.

        Args:
            key: Key pressed (e.g., 'F4', 'Q', 'Ctrl+Z')
            current_turn: Current turn number (for yield tracking)

        Returns:
            Action object if key maps to an action, None otherwise
        """
        # Normalize key format
        key_normalized = self._normalize_key(key)

        # Look up in shortcuts
        shortcuts = self.get_shortcuts()
        action_name = shortcuts.get(key_normalized)

        if not action_name:
            return None

        # Create appropriate action
        return self._create_action(action_name, current_turn)

    def _normalize_key(self, key: str) -> str:
        """Normalize key string to standard format"""
        # Handle common variations
        key = key.replace('Control', 'Ctrl')
        key = key.replace('control', 'Ctrl')
        key = key.replace('CTRL', 'Ctrl')
        key = key.replace('Command', 'Cmd')
        key = key.replace('command', 'Cmd')
        key = key.replace('CMD', 'Cmd')

        # Ensure consistent format for function keys
        if key.lower().startswith('f') and key[1:].isdigit():
            key = 'F' + key[1:]

        return key

    def _create_action(self, action_name: str, current_turn: int) -> Optional[Action]:
        """Create an Action object from action name"""

        if action_name == 'pass_priority':
            return PassPriorityAction()

        elif action_name == 'yield_turn':
            self.priority_stops.set_yield('end_of_turn', current_turn)
            return YieldAction('end_of_turn')

        elif action_name == 'yield_all':
            self.priority_stops.set_yield('all', current_turn)
            return YieldAction('all')

        elif action_name == 'yield_stack':
            self.priority_stops.set_yield('stack_empty', current_turn)
            return YieldAction('stack_empty')

        elif action_name == 'yes' or action_name == 'confirm':
            return ConfirmAction(True)

        elif action_name == 'no' or action_name == 'cancel':
            return CancelAction()

        elif action_name == 'undo_mana':
            return UndoAction('mana')

        elif action_name == 'undo':
            return UndoAction('general')

        elif action_name == 'zoom_card':
            return ZoomAction(self.hovered_card)

        elif action_name == 'cycle_select':
            return Action('cycle_select')

        return None

    def on_opponent_action(self) -> None:
        """
        Called when opponent takes an action.

        Clears yield if opponent does something significant.
        """
        # Clear end-of-turn yield on opponent action
        if self.priority_stops.yield_until == YieldType.END_OF_TURN:
            self.priority_stops.clear_yield()

    def on_new_turn(self) -> None:
        """
        Called at the start of a new turn.

        Clears end-of-turn yield automatically.
        """
        if self.priority_stops.yield_until == YieldType.END_OF_TURN:
            self.priority_stops.clear_yield()

    def on_stack_empty(self) -> None:
        """
        Called when the stack becomes empty.

        Clears stack-empty yield.
        """
        if self.priority_stops.yield_until == YieldType.STACK_EMPTY:
            self.priority_stops.clear_yield()


# =============================================================================
# GAME INTEGRATION HELPERS
# =============================================================================

class TimerManager:
    """
    Manager class for integrating timer and priority stops with a game.

    Provides a clean interface for the Game class to use for all
    timing and priority-related operations.

    Attributes:
        timer: The chess timer instance
        priority_stops: Dict mapping player keys to PriorityStops
        input_handlers: Dict mapping player keys to InputHandler
    """

    def __init__(
        self,
        game: Any,
        format_type: str = 'tournament_practice',
        player_keys: Optional[List[str]] = None
    ):
        """
        Initialize timer manager.

        Args:
            game: Game object to manage
            format_type: Timer format to use
            player_keys: Player identifiers
        """
        self.game = game

        if player_keys is None:
            player_keys = ['player1', 'player2']

        self.player_keys = player_keys
        self.timer = ChessTimer(format_type, player_keys)
        self.priority_stops: Dict[str, PriorityStops] = {}
        self.input_handlers: Dict[str, InputHandler] = {}

        # Initialize per-player components
        for key in player_keys:
            player = self._get_player(key)
            self.priority_stops[key] = PriorityStops(player)
            self.input_handlers[key] = InputHandler(game, player)
            # Share priority_stops with input handler
            self.input_handlers[key].priority_stops = self.priority_stops[key]

    def _get_player(self, player_key: str) -> Any:
        """Get player object from game by key"""
        # This should be customized based on actual game structure
        if hasattr(self.game, 'players'):
            if isinstance(self.game.players, dict):
                return self.game.players.get(player_key)
            elif isinstance(self.game.players, list):
                idx = self.player_keys.index(player_key)
                if idx < len(self.game.players):
                    return self.game.players[idx]
        return None

    def start_match(self) -> None:
        """Start the timer for a new match"""
        self.timer.start()

    def end_match(self) -> None:
        """Stop the timer at match end"""
        self.timer.pause()

    def on_priority_change(self, from_player: str, to_player: str) -> None:
        """
        Handle priority changing from one player to another.

        Args:
            from_player: Player losing priority
            to_player: Player gaining priority
        """
        self.timer.switch_to(to_player)

    def should_auto_pass(
        self,
        player_key: str,
        phase: str,
        is_active: bool,
        has_stack: bool,
        current_turn: int = 0
    ) -> bool:
        """
        Check if a player should auto-pass priority.

        Args:
            player_key: Player to check
            phase: Current phase
            is_active: Whether player is active
            has_stack: Whether stack has items
            current_turn: Current turn number

        Returns:
            True if should auto-pass, False if should give priority
        """
        stops = self.priority_stops.get(player_key)
        if stops:
            return not stops.should_stop(phase, is_active, has_stack, current_turn)
        return False

    def process_input(
        self,
        player_key: str,
        key: str,
        current_turn: int = 0
    ) -> Optional[Action]:
        """
        Process keyboard input for a player.

        Args:
            player_key: Player who pressed the key
            key: Key pressed
            current_turn: Current turn number

        Returns:
            Action if input was recognized, None otherwise
        """
        handler = self.input_handlers.get(player_key)
        if handler:
            return handler.process_key(key, current_turn)
        return None

    def on_new_turn(self, active_player: str) -> None:
        """
        Handle start of a new turn.

        Args:
            active_player: The new active player
        """
        for handler in self.input_handlers.values():
            handler.on_new_turn()

    def on_opponent_action(self, player_key: str) -> None:
        """
        Notify a player that opponent took an action.

        Args:
            player_key: Player to notify
        """
        handler = self.input_handlers.get(player_key)
        if handler:
            handler.on_opponent_action()

    def get_time_display(self, player_key: str) -> str:
        """Get formatted time for display"""
        return self.timer.get_display(player_key)

    def get_all_status(self) -> Dict[str, Any]:
        """Get complete status of timer and stops"""
        return {
            'timer': self.timer.get_all_times(),
            'active_clock': self.timer.active_player_clock,
            'is_running': self.timer.is_running,
            'stops': {
                key: stops.get_stops_display()
                for key, stops in self.priority_stops.items()
            },
            'yields': {
                key: stops.yield_until.name
                for key, stops in self.priority_stops.items()
            }
        }


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Exceptions
    'TimeoutException',
    'InvalidPhaseError',

    # Enums
    'Phase',
    'YieldType',

    # Constants
    'PHASE_NAMES',
    'MTGO_SHORTCUTS',

    # Core classes
    'PriorityStops',
    'StopConfig',
    'ChessTimer',
    'InputHandler',
    'TimerManager',

    # Action classes
    'Action',
    'PassPriorityAction',
    'YieldAction',
    'CancelAction',
    'ConfirmAction',
    'UndoAction',
    'ZoomAction',
]
