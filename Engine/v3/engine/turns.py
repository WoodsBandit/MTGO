"""MTG Engine V3 - Turn Structure Implementation

This module implements the complete MTG turn structure per Comprehensive Rules 500-514.
It provides the Step, Phase, Turn, and TurnManager classes for managing game flow.

Rule References:
- CR 500: Turn Structure Overview
- CR 501: Beginning Phase
- CR 502: Untap Step
- CR 503: Upkeep Step
- CR 504: Draw Step
- CR 505: Main Phase
- CR 506: Combat Phase Overview
- CR 507: Beginning of Combat Step
- CR 508: Declare Attackers Step
- CR 509: Declare Blockers Step
- CR 510: Combat Damage Step
- CR 511: End of Combat Step
- CR 512: Ending Phase
- CR 513: End Step
- CR 514: Cleanup Step
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, TYPE_CHECKING

from .types import StepType, PhaseType

if TYPE_CHECKING:
    from .game import Game
    from .player import Player


# =============================================================================
# Step Data Class
# =============================================================================

@dataclass
class Step:
    """
    Represents a single step within a phase.

    Steps are the smallest unit of turn structure in MTG. Each step has
    specific rules about what happens during it and whether players
    receive priority.

    Attributes:
        step_type: The type of step (from StepType enum)
        has_priority: Whether players receive priority during this step.
                      Per CR 502.3, no players receive priority during untap.
                      Per CR 514.3, players normally don't receive priority during cleanup.
        turn_based_actions: List of callable actions that occur at the start
                            of this step before players receive priority.
                            These are turn-based actions per CR 703.
    """
    step_type: StepType
    has_priority: bool = True
    turn_based_actions: List[Callable[['Game'], None]] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation of the step."""
        return f"Step({self.step_type.name})"

    def __repr__(self) -> str:
        """Debug representation of the step."""
        return (f"Step(step_type={self.step_type.name}, "
                f"has_priority={self.has_priority}, "
                f"turn_based_actions={len(self.turn_based_actions)})")


# =============================================================================
# Phase Data Class
# =============================================================================

@dataclass
class Phase:
    """
    Represents a phase of a turn, containing one or more steps.

    Phases group related steps together. Some phases have multiple steps
    (Beginning, Combat, Ending), while others have a single step (Main phases).

    Attributes:
        phase_type: The type of phase (from PhaseType enum)
        steps: List of Step objects that make up this phase
    """
    phase_type: PhaseType
    steps: List[Step] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation of the phase."""
        return f"Phase({self.phase_type.name}, {len(self.steps)} steps)"

    def __repr__(self) -> str:
        """Debug representation of the phase."""
        step_names = [s.step_type.name for s in self.steps]
        return f"Phase(phase_type={self.phase_type.name}, steps={step_names})"


# =============================================================================
# Turn Class
# =============================================================================

@dataclass
class Turn:
    """
    Represents a complete turn for one player.

    A turn consists of five phases: Beginning, Pre-combat Main, Combat,
    Post-combat Main, and Ending. Each phase contains one or more steps.

    Per CR 500.1, a turn consists of phases, which in turn consist of steps.
    The active player is the player whose turn it is.

    Attributes:
        turn_number: The sequential turn number in the game (starts at 1)
        active_player: The player whose turn this is
        phases: List of Phase objects making up this turn
        current_phase_index: Index into phases list for current phase
        current_step_index: Index into current phase's steps for current step
    """
    turn_number: int
    active_player: Any  # Player object
    phases: List[Phase] = field(default_factory=list)
    current_phase_index: int = 0
    current_step_index: int = 0

    @property
    def current_phase(self) -> Phase:
        """
        Get the current phase of the turn.

        Returns:
            The Phase object for the current phase

        Raises:
            IndexError: If current_phase_index is out of bounds
        """
        if not self.phases:
            raise IndexError("Turn has no phases")
        return self.phases[self.current_phase_index]

    @property
    def current_step(self) -> Step:
        """
        Get the current step of the turn.

        Returns:
            The Step object for the current step within the current phase

        Raises:
            IndexError: If current_step_index is out of bounds
        """
        phase = self.current_phase
        if not phase.steps:
            raise IndexError("Current phase has no steps")
        return phase.steps[self.current_step_index]

    @property
    def is_main_phase(self) -> bool:
        """
        Check if the current phase is a main phase.

        Per CR 505.1, the main phase is when sorcery-speed spells can be cast
        and lands can be played. There are two main phases per turn.

        Returns:
            True if the current phase is either pre-combat or post-combat main
        """
        if not self.phases:
            return False
        current = self.current_phase.phase_type
        return current in (PhaseType.PRECOMBAT_MAIN, PhaseType.POSTCOMBAT_MAIN)

    @property
    def is_combat_phase(self) -> bool:
        """
        Check if the current phase is the combat phase.

        The combat phase contains multiple steps for attacking, blocking,
        and dealing damage.

        Returns:
            True if the current phase is combat
        """
        if not self.phases:
            return False
        return self.current_phase.phase_type == PhaseType.COMBAT

    def advance_step(self) -> bool:
        """
        Advance to the next step within the current phase.

        Returns:
            True if advanced to next step, False if at end of phase
        """
        phase = self.current_phase
        if self.current_step_index < len(phase.steps) - 1:
            self.current_step_index += 1
            return True
        return False

    def advance_phase(self) -> bool:
        """
        Advance to the next phase of the turn.

        Resets the step index to 0 for the new phase.

        Returns:
            True if advanced to next phase, False if at end of turn
        """
        if self.current_phase_index < len(self.phases) - 1:
            self.current_phase_index += 1
            self.current_step_index = 0
            return True
        return False

    def __str__(self) -> str:
        """String representation of the turn."""
        player_name = getattr(self.active_player, 'name', str(self.active_player))
        return f"Turn {self.turn_number} ({player_name})"

    def __repr__(self) -> str:
        """Debug representation of the turn."""
        player_name = getattr(self.active_player, 'name', str(self.active_player))
        phase_names = [p.phase_type.name for p in self.phases]
        return (f"Turn(turn_number={self.turn_number}, "
                f"active_player={player_name}, "
                f"phases={phase_names})")


# =============================================================================
# TurnManager Class
# =============================================================================

class TurnManager:
    """
    Manages turn flow and execution for the game.

    The TurnManager is responsible for:
    - Creating turns with proper phase/step structure
    - Running steps, phases, and complete turns
    - Tracking active player rotation
    - Coordinating with other game systems (events, SBAs, priority)

    Per CR 500, turns are the fundamental unit of game time, and the
    TurnManager ensures all turn structure rules are followed.

    Attributes:
        game: Reference to the Game object
        turn_number: Current turn number (0 = game not started)
        active_player_index: Index into player list for active player
        current_turn: The current Turn object being executed
    """

    def __init__(self, game: 'Game'):
        """
        Initialize the TurnManager with a game reference.

        Args:
            game: The Game object this manager belongs to
        """
        self.game = game
        self.turn_number: int = 0
        self.active_player_index: int = 0
        self.current_turn: Optional[Turn] = None

    def start_game(self) -> None:
        """
        Set up the TurnManager for the first turn.

        Called during game initialization to prepare for turn 1.
        Sets the turn counter and active player to starting values.
        """
        self.turn_number = 0
        self.active_player_index = 0
        self.current_turn = None

    def get_active_player(self) -> 'Player':
        """
        Get the currently active player.

        The active player is the player whose turn it is (CR 102.1).

        Returns:
            The Player object for the active player

        Raises:
            KeyError: If no players exist
        """
        player_ids = list(self.game.players.keys())
        if not player_ids:
            raise KeyError("No players in game")
        player_id = player_ids[self.active_player_index % len(player_ids)]
        return self.game.players[player_id]

    def get_non_active_players(self) -> List['Player']:
        """
        Get all players who are not the active player.

        In APNAP (Active Player, Non-Active Player) order, these players
        follow the active player for simultaneous choices and priority.

        Returns:
            List of Player objects for all non-active players in turn order
        """
        player_ids = list(self.game.players.keys())
        if not player_ids:
            return []

        active_id = player_ids[self.active_player_index % len(player_ids)]
        non_active = []

        # Build list in turn order starting after active player
        for i in range(1, len(player_ids)):
            idx = (self.active_player_index + i) % len(player_ids)
            non_active.append(self.game.players[player_ids[idx]])

        return non_active

    def start_new_turn(self) -> Turn:
        """
        Create and start a new turn for the next active player.

        Increments the turn counter, creates a Turn object with the standard
        phase/step structure, and returns it for execution.

        Returns:
            The new Turn object to be executed
        """
        self.turn_number += 1
        active_player = self.get_active_player()

        self.current_turn = create_standard_turn(active_player, self.turn_number)

        return self.current_turn

    def next_turn(self) -> None:
        """
        Advance to the next player's turn.

        Rotates the active player to the next player in turn order.
        Does not create the new turn - call start_new_turn() for that.
        """
        player_ids = list(self.game.players.keys())
        if player_ids:
            self.active_player_index = (self.active_player_index + 1) % len(player_ids)

    def run_step(self, step: Step) -> None:
        """
        Execute a single step of a turn.

        Step execution per CR 500.2:
        1. Begin step - emit StepBeginEvent
        2. Perform turn-based actions (untap permanents, draw card, etc.)
        3. Check state-based actions
        4. Put triggered abilities on stack
        5. If step has priority: run priority round(s) until stack empty and all pass
        6. End step - emit StepEndEvent

        Args:
            step: The Step object to execute
        """
        from .events import StepBeginEvent, StepEndEvent
        from .sba import run_sba_loop
        from .effects.triggered import put_triggers_on_stack

        # 1. Emit step begin event
        self.game.events.emit(StepBeginEvent(step_type=step.step_type))

        # 2. Perform turn-based actions for this step
        for action in step.turn_based_actions:
            action(self.game)

        # 3. Check state-based actions
        run_sba_loop(self.game)

        # 4. Put triggered abilities on stack (APNAP order)
        put_triggers_on_stack(self.game)

        # 5. Run priority round if this step has priority
        if step.has_priority:
            self._run_priority_rounds()

        # 6. Emit step end event
        self.game.events.emit(StepEndEvent(step_type=step.step_type))

    def run_phase(self, phase: Phase) -> None:
        """
        Execute a complete phase with all its steps.

        Iterates through each step in the phase and executes it.
        The phase begin/end events are emitted by the caller (run_turn).

        Args:
            phase: The Phase object to execute
        """
        for step in phase.steps:
            if self.game.game_over:
                return
            self.run_step(step)

    def run_turn(self) -> None:
        """
        Execute a complete turn for the active player.

        Turn execution per CR 500:
        1. Reset player's turn state (untap tracking, etc.)
        2. Run BEGINNING phase (Untap, Upkeep, Draw)
        3. Run PRECOMBAT_MAIN phase
        4. Run COMBAT phase (all combat steps)
        5. Run POSTCOMBAT_MAIN phase
        6. Run ENDING phase (End step, Cleanup)

        Creates the turn, runs all phases, then advances to next player.
        """
        from .events import PhaseBeginEvent, PhaseEndEvent

        # Start new turn
        turn = self.start_new_turn()

        # Reset player turn state
        active_player = self.get_active_player()
        if hasattr(active_player, 'reset_turn_state'):
            active_player.reset_turn_state()

        # Update game state
        self.game.turn_number = self.turn_number
        self.game.active_player_id = active_player.player_id

        # Run each phase
        for phase_index, phase in enumerate(turn.phases):
            if self.game.game_over:
                return

            # Update current phase tracking
            turn.current_phase_index = phase_index
            turn.current_step_index = 0
            self.game.current_phase = phase.phase_type

            # Emit phase begin event
            self.game.events.emit(PhaseBeginEvent(phase_type=phase.phase_type))

            # Run the phase (all steps)
            self.run_phase(phase)

            # Emit phase end event
            self.game.events.emit(PhaseEndEvent(phase_type=phase.phase_type))

        # Advance to next player's turn
        self.next_turn()

    def _run_priority_rounds(self) -> None:
        """
        Run priority rounds until stack is empty and all players pass.

        This implements the core priority loop per CR 117.4:
        - Active player receives priority
        - Priority passes around until all pass in succession
        - If stack is non-empty, resolve top and repeat
        - If stack is empty and all pass, priority round ends
        """
        from .priority import run_priority_round

        # Run priority rounds until complete
        while run_priority_round(self.game):
            if self.game.game_over:
                return


# =============================================================================
# Turn-Based Actions
# =============================================================================

def _untap_permanents(game: 'Game') -> None:
    """
    Turn-based action: Untap active player's permanents.

    Per CR 502.3, the active player untaps all permanents they control
    that have tap symbols in their costs and don't have "doesn't untap"
    effects applied to them.

    Args:
        game: The Game object
    """
    from .events import UntapEvent

    active_player_id = game.active_player_id

    for permanent in game.zones.battlefield.permanents(active_player_id):
        # Check for "doesn't untap during your untap step" effects
        if hasattr(permanent, 'doesnt_untap') and permanent.doesnt_untap:
            continue

        if hasattr(permanent, 'is_tapped') and permanent.is_tapped:
            permanent.untap()
            game.events.emit(UntapEvent(permanent=permanent))


def _draw_card(game: 'Game') -> None:
    """
    Turn-based action: Active player draws a card.

    Per CR 504.1, the active player draws a card during the draw step.
    Exception: The starting player skips the draw on turn 1 (CR 103.7a).

    Args:
        game: The Game object
    """
    from .events import DrawEvent

    active_player_id = game.active_player_id
    player = game.players[active_player_id]

    # Check for first turn of the game (starting player doesn't draw)
    player_ids = list(game.players.keys())
    if game.turn_number == 1 and active_player_id == player_ids[0]:
        return

    # Draw a card
    if hasattr(game, 'draw_cards'):
        game.draw_cards(active_player_id, 1)
    elif hasattr(player, 'draw'):
        cards = player.draw(1)
        if cards:
            game.events.emit(DrawEvent(player=player, cards=cards))


def _cleanup_discard_to_hand_size(game: 'Game') -> None:
    """
    Turn-based action: Active player discards to hand size.

    Per CR 514.1, the active player discards down to their maximum hand size
    (normally 7) during the cleanup step.

    Args:
        game: The Game object
    """
    active_player_id = game.active_player_id
    player = game.players[active_player_id]
    hand = game.zones.hands[active_player_id]

    max_hand_size = getattr(player, 'max_hand_size', 7)

    while len(hand) > max_hand_size:
        # Let AI or player choose what to discard
        if hasattr(player, 'ai') and player.ai:
            cards = list(hand.objects)
            if cards:
                # Simple heuristic: discard highest CMC first
                cards.sort(
                    key=lambda c: (
                        c.characteristics.mana_cost.mana_value
                        if hasattr(c, 'characteristics') and
                           hasattr(c.characteristics, 'mana_cost') and
                           c.characteristics.mana_cost else 0
                    ),
                    reverse=True
                )
                discard = cards[0]
                hand.remove(discard)
                game.zones.graveyards[active_player_id].add(discard)
            else:
                break
        else:
            # Would need player input - for now just break
            break


def _cleanup_damage_wears_off(game: 'Game') -> None:
    """
    Turn-based action: Damage wears off from creatures.

    Per CR 514.2, all damage marked on permanents is removed during cleanup.

    Args:
        game: The Game object
    """
    for creature in game.zones.battlefield.creatures():
        creature.damage_marked = 0
        if hasattr(creature, 'damage_sources_with_deathtouch'):
            creature.damage_sources_with_deathtouch.clear()


def _cleanup_end_until_end_of_turn_effects(game: 'Game') -> None:
    """
    Turn-based action: "Until end of turn" effects end.

    Per CR 514.2, effects that last "until end of turn" or "this turn"
    end during the cleanup step.

    Args:
        game: The Game object
    """
    # This would interact with the continuous effects system
    # Implementation depends on how effects are tracked
    if hasattr(game, 'effects') and hasattr(game.effects, 'end_turn_effects'):
        game.effects.end_turn_effects()


def _empty_mana_pools(game: 'Game') -> None:
    """
    Turn-based action: Empty all players' mana pools.

    Per CR 514.3a (and CR 106.4), mana pools empty at the end of each
    step and phase. The cleanup step explicitly empties pools.

    Args:
        game: The Game object
    """
    for player in game.players.values():
        if hasattr(player, 'mana_pool'):
            player.mana_pool.empty()


# =============================================================================
# Standard Turn Factory Function
# =============================================================================

def create_standard_turn(active_player: Any, turn_number: int = 1) -> Turn:
    """
    Create a standard turn with all phases and steps per CR 500-514.

    The standard turn structure is:

    BEGINNING Phase (CR 501):
        - UNTAP Step (CR 502): No priority, untap permanents
        - UPKEEP Step (CR 503): Priority, "at beginning of upkeep" triggers
        - DRAW Step (CR 504): Active player draws, then priority

    PRECOMBAT_MAIN Phase (CR 505):
        - Main step: Priority, can cast sorceries and play lands

    COMBAT Phase (CR 506):
        - BEGINNING_OF_COMBAT Step (CR 507): Priority
        - DECLARE_ATTACKERS Step (CR 508): Declare attackers, then priority
        - DECLARE_BLOCKERS Step (CR 509): Declare blockers, then priority
        - COMBAT_DAMAGE Step (CR 510): Damage dealt, then priority
            (May be split for first strike - handled by combat manager)
        - END_OF_COMBAT Step (CR 511): Priority, combat ends

    POSTCOMBAT_MAIN Phase (CR 505):
        - Main step: Priority, can cast sorceries and play lands

    ENDING Phase (CR 512):
        - END Step (CR 513): Priority, "at beginning of end step" triggers
        - CLEANUP Step (CR 514): Discard to hand size, damage wears off,
            normally no priority

    Args:
        active_player: The Player object whose turn this is
        turn_number: The turn number (default 1)

    Returns:
        A fully constructed Turn object ready for execution
    """

    # BEGINNING PHASE
    beginning_phase = Phase(
        phase_type=PhaseType.BEGINNING,
        steps=[
            # Untap step - no priority (CR 502.3)
            Step(
                step_type=StepType.UNTAP,
                has_priority=False,
                turn_based_actions=[_untap_permanents]
            ),
            # Upkeep step - has priority (CR 503)
            Step(
                step_type=StepType.UPKEEP,
                has_priority=True,
                turn_based_actions=[]
            ),
            # Draw step - draw card, then priority (CR 504)
            Step(
                step_type=StepType.DRAW,
                has_priority=True,
                turn_based_actions=[_draw_card]
            ),
        ]
    )

    # PRECOMBAT MAIN PHASE
    precombat_main_phase = Phase(
        phase_type=PhaseType.PRECOMBAT_MAIN,
        steps=[
            Step(
                step_type=StepType.PRECOMBAT_MAIN,
                has_priority=True,
                turn_based_actions=[]
            ),
        ]
    )

    # COMBAT PHASE
    combat_phase = Phase(
        phase_type=PhaseType.COMBAT,
        steps=[
            # Beginning of combat (CR 507)
            Step(
                step_type=StepType.BEGINNING_OF_COMBAT,
                has_priority=True,
                turn_based_actions=[]
            ),
            # Declare attackers (CR 508)
            Step(
                step_type=StepType.DECLARE_ATTACKERS,
                has_priority=True,
                turn_based_actions=[]
            ),
            # Declare blockers (CR 509)
            Step(
                step_type=StepType.DECLARE_BLOCKERS,
                has_priority=True,
                turn_based_actions=[]
            ),
            # Combat damage (CR 510)
            # Note: First strike damage handled separately by combat manager
            Step(
                step_type=StepType.COMBAT_DAMAGE,
                has_priority=True,
                turn_based_actions=[]
            ),
            # End of combat (CR 511)
            Step(
                step_type=StepType.END_OF_COMBAT,
                has_priority=True,
                turn_based_actions=[]
            ),
        ]
    )

    # POSTCOMBAT MAIN PHASE
    postcombat_main_phase = Phase(
        phase_type=PhaseType.POSTCOMBAT_MAIN,
        steps=[
            Step(
                step_type=StepType.POSTCOMBAT_MAIN,
                has_priority=True,
                turn_based_actions=[]
            ),
        ]
    )

    # ENDING PHASE
    ending_phase = Phase(
        phase_type=PhaseType.ENDING,
        steps=[
            # End step (CR 513)
            Step(
                step_type=StepType.END,
                has_priority=True,
                turn_based_actions=[]
            ),
            # Cleanup step (CR 514)
            # Normally no priority unless triggers occur
            Step(
                step_type=StepType.CLEANUP,
                has_priority=False,
                turn_based_actions=[
                    _cleanup_discard_to_hand_size,
                    _cleanup_damage_wears_off,
                    _cleanup_end_until_end_of_turn_effects,
                    _empty_mana_pools,
                ]
            ),
        ]
    )

    # Create and return the complete turn
    return Turn(
        turn_number=turn_number,
        active_player=active_player,
        phases=[
            beginning_phase,
            precombat_main_phase,
            combat_phase,
            postcombat_main_phase,
            ending_phase,
        ],
        current_phase_index=0,
        current_step_index=0,
    )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Data classes
    'Step',
    'Phase',
    'Turn',

    # Manager class
    'TurnManager',

    # Factory function
    'create_standard_turn',

    # Turn-based actions (for testing/extension)
    '_untap_permanents',
    '_draw_card',
    '_cleanup_discard_to_hand_size',
    '_cleanup_damage_wears_off',
    '_cleanup_end_until_end_of_turn_effects',
    '_empty_mana_pools',
]
