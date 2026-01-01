"""MTG Engine V3 - Main Game Class

This module implements the complete MTG game controller following the
Comprehensive Rules. The Game class ties together all game systems:
- Zone management (CR 400)
- Turn structure (CR 500-514)
- Priority system (CR 117)
- Stack and resolution (CR 405, 608)
- State-based actions (CR 704)
- Combat (CR 506-511)
- Triggered abilities (CR 603)
- Continuous effects (CR 613)
- Mana system (CR 106)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any, TYPE_CHECKING

from .types import (
    PlayerId, ObjectId, PhaseType, StepType, ActionType,
    Zone, CardType, CounterType
)
from .events import (
    EventBus, TurnStartEvent, TurnEndEvent, PhaseStartEvent, PhaseEndEvent,
    StepStartEvent, DrawCardEvent, LandPlayedEvent, UntapEvent,
    EntersBattlefieldEvent, GameStartEvent, GameEndedEvent,
    PlayerLostEvent, PlayerWonEvent
)
from .zones import ZoneManager
from .player import Player
from .priority import PrioritySystem, run_priority_round
from .stack import StackManager
from .mana import ManaAbilityManager
from .combat import CombatManager
from .sba import run_sba_loop, check_state_based_actions
from .effects.triggered import TriggerManager, put_triggers_on_stack

if TYPE_CHECKING:
    from .objects import Card, Permanent, GameObject, Spell, StackedAbility, Target
    from ..ai.agent import AIAgent


# =============================================================================
# CONFIGURATION AND RESULT DATACLASSES
# =============================================================================

@dataclass
class GameConfig:
    """
    Configuration settings for a game instance.

    Attributes:
        starting_life: Initial life total for each player (default 20)
        starting_hand_size: Number of cards drawn at game start (default 7)
        max_turns: Maximum turns before forcing a result (default 50)
        verbose: Enable detailed logging output (default False)
    """
    starting_life: int = 20
    starting_hand_size: int = 7
    max_turns: int = 50
    verbose: bool = False


@dataclass
class GameResult:
    """
    Result of a completed game.

    Attributes:
        winner: The winning player, or None for a draw
        reason: How the game ended ("life", "decked", "concede", "turn_limit", "poison")
        turns_played: Total number of turns played
        final_life: Dictionary mapping player_id to final life total
    """
    winner: Optional[Player] = None
    reason: str = ""
    turns_played: int = 0
    final_life: Dict[int, int] = field(default_factory=dict)


# =============================================================================
# MAIN GAME CLASS
# =============================================================================

class Game:
    """
    Main game controller for Magic: The Gathering simulation.

    The Game class is the central orchestrator that:
    - Maintains all game state
    - Manages turn structure and phase progression
    - Coordinates between subsystems (zones, stack, combat, etc.)
    - Enforces rules and timing restrictions
    - Tracks win/loss conditions

    Attributes:
        events: Event bus for game events and triggers
        zones: Zone manager for all game zones
        priority: Priority system manager
        players: Dictionary of players by ID
        stack_manager: Stack and resolution manager
        mana_manager: Mana ability manager
        combat_manager: Combat phase manager
        triggers: Triggered ability manager
        turn_number: Current turn number
        active_player_id: ID of the active player
        current_phase: Current game phase
        current_step: Current step within the phase
        game_over: Whether the game has ended
        winner_id: ID of the winning player (if any)
    """

    def __init__(self, player_ids: List[PlayerId] = None, config: GameConfig = None):
        """
        Initialize a new game.

        Args:
            player_ids: List of player IDs. Defaults to [1, 2] for two-player game.
            config: Game configuration settings. Uses defaults if not provided.
        """
        player_ids = player_ids or [1, 2]
        self.config = config or GameConfig()

        # Core systems
        self.events = EventBus()
        self.zones = ZoneManager(player_ids)
        self.priority = PrioritySystem(self)
        self._timestamp_counter = 0

        # Players - use config starting_life
        self.players: Dict[PlayerId, Player] = {}
        for pid in player_ids:
            player = Player(player_id=pid, name=f"Player {pid}")
            player.life = self.config.starting_life
            self.players[pid] = player

        # priority system gets player order from game.players

        # Managers - initialized after events/zones so they can reference game
        self.stack_manager = StackManager(self)
        self.mana_manager = ManaAbilityManager(self)
        self.combat_manager = CombatManager(self)
        self.triggers = TriggerManager(self)

        # Game state
        self.turn_number: int = 0
        self.active_player_id: PlayerId = player_ids[0]
        self.current_phase: PhaseType = PhaseType.BEGINNING
        self.current_step: StepType = StepType.UNTAP
        self.game_over: bool = False
        self.winner_id: Optional[PlayerId] = None
        self.game_started: bool = False

        # Object ID management
        self._next_object_id: ObjectId = 1

        # Track extra turns
        self._extra_turns: List[PlayerId] = []

        # Track skipped phases/steps
        self._skipped_phases: Set[Tuple[PlayerId, PhaseType]] = set()
        self._skipped_steps: Set[Tuple[PlayerId, StepType]] = set()

    # =========================================================================
    # OBJECT ID MANAGEMENT
    # =========================================================================

    def next_object_id(self) -> ObjectId:
        """
        Get next unique object ID.

        Every game object (card, permanent, spell, ability, token) gets a
        unique ID for tracking throughout the game.

        Returns:
            A unique ObjectId
        """
        oid = self._next_object_id
        self._next_object_id += 1
        return oid

    # =========================================================================
    # PLAYER ACCESS
    # =========================================================================

    def get_player(self, player_id: PlayerId) -> Player:
        """
        Get player by ID.

        Args:
            player_id: The player's ID

        Returns:
            The Player object

        Raises:
            KeyError: If player_id not found
        """
        return self.players[player_id]

    def get_timestamp(self) -> int:
        """Get a unique timestamp for object ordering."""
        self._timestamp_counter += 1
        return self._timestamp_counter

    def get_opponent_id(self, player_id: PlayerId) -> PlayerId:
        """
        Get opponent's player ID (for two-player games).

        Args:
            player_id: A player's ID

        Returns:
            The opponent's ID (in two-player game)
        """
        for pid in self.players:
            if pid != player_id:
                return pid
        return player_id  # Fallback for single-player testing

    def get_opponents(self, player_id: PlayerId) -> List[PlayerId]:
        """
        Get all opponent IDs (for multiplayer support).

        Args:
            player_id: A player's ID

        Returns:
            List of opponent IDs
        """
        return [pid for pid in self.players if pid != player_id]

    def get_active_player(self) -> Player:
        """Get the currently active player."""
        return self.players[self.active_player_id]

    def get_priority_player(self) -> Optional[Player]:
        """Get the player who currently has priority."""
        if self.priority.priority_player_id is None:
            return None
        return self.players[self.priority.priority_player_id]

    # =========================================================================
    # GAME SETUP
    # =========================================================================

    def setup_game(
        self,
        deck1: List['Card'],
        deck2: List['Card'],
        ai1: 'AIAgent' = None,
        ai2: 'AIAgent' = None
    ):
        """
        Set up a new game with two decks.

        Handles:
        - Assigning cards to players
        - Setting up libraries
        - Drawing opening hands
        - Assigning AI controllers

        Args:
            deck1: Deck for player 1
            deck2: Deck for player 2
            ai1: Optional AI controller for player 1
            ai2: Optional AI controller for player 2
        """
        player_ids = list(self.players.keys())

        # Set up player 1
        p1 = self.players[player_ids[0]]
        if ai1:
            p1.ai = ai1
        else:
            # Import and create default AI
            try:
                from ..ai.agent import AIAgent
                p1.ai = AIAgent(player_ids[0])
            except ImportError:
                pass

        for card in deck1:
            card.object_id = self.next_object_id()
            card.owner = p1
            card.controller = p1
            self.zones.libraries[player_ids[0]].add(card)
        self.zones.libraries[player_ids[0]].shuffle()

        # Set up player 2
        p2 = self.players[player_ids[1]]
        if ai2:
            p2.ai = ai2
        else:
            try:
                from ..ai.agent import AIAgent
                p2.ai = AIAgent(player_ids[1])
            except ImportError:
                pass

        for card in deck2:
            card.object_id = self.next_object_id()
            card.owner = p2
            card.controller = p2
            self.zones.libraries[player_ids[1]].add(card)
        self.zones.libraries[player_ids[1]].shuffle()

        # Draw opening hands (using config.starting_hand_size)
        for pid in player_ids:
            for _ in range(self.config.starting_hand_size):
                self._draw_card(pid)

        self.game_started = True

        # Emit game start event
        self.events.emit(GameStartEvent(
            player_ids=player_ids
        ))

    # =========================================================================
    # CARD DRAWING
    # =========================================================================

    def _draw_card(self, player_id: PlayerId) -> bool:
        """
        Draw a card for a player (internal method).

        Handles:
        - Moving card from library to hand
        - Tracking empty library draws (for SBA)
        - Emitting draw event

        Args:
            player_id: Player drawing the card

        Returns:
            True if a card was drawn, False if library was empty
        """
        library = self.zones.libraries[player_id]

        if len(library) == 0:
            self.players[player_id].drew_from_empty_library = True
            return False

        card = library.draw()
        if card:
            self.zones.hands[player_id].add(card)
            card.zone = Zone.HAND

            # DrawCardEvent is alias for DrawEvent which expects player and cards
            self.events.emit(DrawCardEvent(
                player=self.players[player_id],
                cards=[card]
            ))
            return True
        return False

    def draw_cards(self, player_id: PlayerId, count: int) -> int:
        """
        Draw multiple cards for a player.

        Args:
            player_id: Player drawing cards
            count: Number of cards to draw

        Returns:
            Number of cards actually drawn
        """
        drawn = 0
        for _ in range(count):
            if self._draw_card(player_id):
                drawn += 1
            else:
                break
        return drawn

    # =========================================================================
    # MAIN GAME LOOP
    # =========================================================================

    def play_game(self, max_turns: int = None) -> GameResult:
        """
        Play a complete game until someone wins or max turns reached.

        Args:
            max_turns: Maximum number of turns before forcing a result.
                       Uses config.max_turns if not specified.

        Returns:
            GameResult with winner, reason, turns played, and final life totals
        """
        # Use config.max_turns if not explicitly overridden
        max_turns = max_turns if max_turns is not None else self.config.max_turns
        win_reason = ""

        while not self.game_over and self.turn_number < max_turns:
            self._play_turn()

            # Check for winner after each turn
            if self.check_game_over():
                break

        # Turn limit reached - determine winner by life total
        if not self.game_over and self.turn_number >= max_turns:
            self.game_over = True
            best = max(self.players.values(), key=lambda p: p.life)
            self.winner_id = best.player_id
            win_reason = "turn_limit"

            self.events.emit(GameEndedEvent(
                winner_id=self.winner_id,
                is_draw=False
            ))

        # Determine win reason if not already set
        if not win_reason and self.winner_id is not None:
            winner = self.players.get(self.winner_id)
            for pid, player in self.players.items():
                if pid != self.winner_id:
                    # Check why opponent lost
                    if player.life <= 0:
                        win_reason = "life"
                    elif getattr(player, 'drew_from_empty_library', False):
                        win_reason = "decked"
                    elif getattr(player, 'poison_counters', 0) >= 10:
                        win_reason = "poison"
                    elif getattr(player, 'has_conceded', False):
                        win_reason = "concede"
                    else:
                        win_reason = "unknown"
                    break

        # Build final life totals
        final_life = {pid: p.life for pid, p in self.players.items()}

        # Get winner Player object
        winner = self.players.get(self.winner_id) if self.winner_id else None

        return GameResult(
            winner=winner,
            reason=win_reason,
            turns_played=self.turn_number,
            final_life=final_life
        )

    def check_game_over(self) -> bool:
        """
        Check if the game should end.

        Checks:
        - Players with 0 or less life
        - Players who drew from empty library
        - Players with 10+ poison counters
        - Only one player remaining

        Returns:
            True if game has ended
        """
        if self.game_over:
            return True

        # Run SBAs to check for losses
        run_sba_loop(self)

        # Count alive players
        alive = [p for p in self.players.values() if p.is_alive()]

        if len(alive) == 0:
            # Draw (shouldn't normally happen)
            self.game_over = True
            return True

        if len(alive) == 1:
            # Winner!
            self.game_over = True
            self.winner_id = alive[0].player_id

            self.events.emit(PlayerWonEvent(
                player_id=self.winner_id,
                reason="last_standing"
            ))
            self.events.emit(GameEndedEvent(
                winner_id=self.winner_id,
                is_draw=False
            ))
            return True

        return False

    # =========================================================================
    # TURN STRUCTURE (CR 500)
    # =========================================================================

    def _play_turn(self):
        """
        Execute one complete turn.

        Turn structure per CR 500:
        1. Beginning Phase (Untap, Upkeep, Draw)
        2. Pre-combat Main Phase
        3. Combat Phase
        4. Post-combat Main Phase
        5. Ending Phase (End Step, Cleanup)
        """
        self.turn_number += 1
        active = self.players[self.active_player_id]
        active.reset_turn_state()  # Reset lands played, etc.

        # Reset AI turn state if present
        if active.ai and hasattr(active.ai, 'reset_turn_state'):
            active.ai.reset_turn_state()

        # Set active player for APNAP ordering
        if hasattr(self.triggers, 'set_active_player'):
            self.triggers.set_active_player(self.active_player_id)

        self.events.emit(TurnStartEvent(
            turn_number=self.turn_number,
            active_player_id=self.active_player_id
        ))

        # BEGINNING PHASE
        self._beginning_phase()
        if self.check_game_over():
            return

        # PRECOMBAT MAIN PHASE
        self._main_phase(StepType.PRECOMBAT_MAIN)
        if self.check_game_over():
            return

        # COMBAT PHASE
        self._combat_phase()
        if self.check_game_over():
            return

        # POSTCOMBAT MAIN PHASE
        self._main_phase(StepType.POSTCOMBAT_MAIN)
        if self.check_game_over():
            return

        # ENDING PHASE
        self._ending_phase()

        # Turn end
        self.events.emit(TurnEndEvent(
            turn_number=self.turn_number,
            active_player_id=self.active_player_id
        ))

        active.end_turn()
        self._switch_active_player()

    # =========================================================================
    # BEGINNING PHASE (CR 501-504)
    # =========================================================================

    def _beginning_phase(self):
        """
        Beginning phase: Untap, Upkeep, Draw (CR 501-504).
        """
        self.current_phase = PhaseType.BEGINNING
        self.events.emit(PhaseStartEvent(
            phase_type=PhaseType.BEGINNING
        ))

        # Untap step (CR 502) - no priority given
        self.current_step = StepType.UNTAP
        self._untap_step()
        # Empty mana pools at end of step (CR 106.4b)
        self._empty_mana_pools()

        # Upkeep step (CR 503)
        self.current_step = StepType.UPKEEP
        self.events.emit(StepStartEvent(
            step_type=StepType.UPKEEP
        ))
        run_priority_round(self)
        # Empty mana pools at end of step (CR 106.4b)
        self._empty_mana_pools()

        if self.check_game_over():
            return

        # Draw step (CR 504)
        self.current_step = StepType.DRAW
        self.events.emit(StepStartEvent(
            step_type=StepType.DRAW
        ))

        # First player doesn't draw on first turn (CR 103.7a)
        player_ids = list(self.players.keys())
        if not (self.turn_number == 1 and self.active_player_id == player_ids[0]):
            self._draw_card(self.active_player_id)

        run_priority_round(self)
        # Empty mana pools at end of step (CR 106.4b)
        self._empty_mana_pools()

        self.events.emit(PhaseEndEvent(
            phase_type=PhaseType.BEGINNING
        ))

    def _untap_step(self):
        """
        Untap step (CR 502).

        During the untap step:
        - Phasing occurs (before anything else)
        - Active player's permanents untap
        - No priority is given (no player actions)
        """
        from .events import UntapEvent

        for perm in self.zones.battlefield.permanents(self.active_player_id):
            # Check for "doesn't untap during your untap step" effects
            if hasattr(perm, 'doesnt_untap') and perm.doesnt_untap:
                continue

            if perm.is_tapped:
                perm.untap()
                self.events.emit(UntapEvent(
                    permanent=perm
                ))

            # Clear summoning sickness flag
            if hasattr(perm, 'entered_battlefield_this_turn'):
                perm.entered_battlefield_this_turn = False
            if hasattr(perm, 'has_summoning_sickness'):
                # Creatures that started the turn under your control lose summoning sickness
                if perm.controller_id == self.active_player_id:
                    perm.has_summoning_sickness = False

            # Clear damage from previous turn
            if hasattr(perm, 'characteristics') and perm.characteristics.is_creature():
                perm.damage_marked = 0
                if hasattr(perm, 'damage_sources_with_deathtouch'):
                    perm.damage_sources_with_deathtouch.clear()

    # =========================================================================
    # MAIN PHASE (CR 505)
    # =========================================================================

    def _main_phase(self, step: StepType):
        """
        Main phase (CR 505).

        During a main phase:
        - Sorcery-speed spells can be cast
        - Lands can be played
        - Priority passes until both players pass with empty stack

        Args:
            step: Either PRECOMBAT_MAIN or POSTCOMBAT_MAIN
        """
        if step == StepType.PRECOMBAT_MAIN:
            self.current_phase = PhaseType.PRECOMBAT_MAIN
        else:
            self.current_phase = PhaseType.POSTCOMBAT_MAIN

        self.current_step = step

        self.events.emit(PhaseStartEvent(
            phase_type=self.current_phase
        ))
        self.events.emit(StepStartEvent(
            step_type=step
        ))

        # Priority rounds until stack empty and both pass
        while run_priority_round(self):
            if self.check_game_over():
                return

        # Empty mana pools at end of phase (CR 106.4)
        self._empty_mana_pools()

        self.events.emit(PhaseEndEvent(
            phase_type=self.current_phase
        ))

    # =========================================================================
    # COMBAT PHASE (CR 506-511)
    # =========================================================================

    def _combat_phase(self):
        """
        Combat phase (CR 506-511).

        Delegates to CombatManager for full combat implementation.
        """
        self.current_phase = PhaseType.COMBAT
        self.combat_manager.run_combat_phase()

    # =========================================================================
    # ENDING PHASE (CR 512-514)
    # =========================================================================

    def _ending_phase(self):
        """
        Ending phase: End step, Cleanup (CR 512-514).
        """
        self.current_phase = PhaseType.ENDING
        self.events.emit(PhaseStartEvent(
            phase_type=PhaseType.ENDING
        ))

        # End step (CR 513)
        self.current_step = StepType.END
        self.events.emit(StepStartEvent(
            step_type=StepType.END
        ))
        run_priority_round(self)

        # Empty mana at end of step (CR 106.4)
        self._empty_mana_pools()

        if self.check_game_over():
            return

        # Cleanup step (CR 514) - usually no priority
        self.current_step = StepType.CLEANUP
        self._cleanup_step()

        self.events.emit(PhaseEndEvent(
            phase_type=PhaseType.ENDING
        ))

    def _cleanup_step(self):
        """
        Cleanup step (CR 514).

        During cleanup:
        1. Active player discards to hand size
        2. Damage is removed from permanents
        3. "Until end of turn" effects end
        4. Mana pools empty
        5. Usually no priority (unless triggers go on stack)
        """
        active = self.players[self.active_player_id]

        # Discard to hand size
        hand = self.zones.hands[self.active_player_id]
        while len(hand) > 7:
            # AI chooses what to discard
            if active.ai:
                cards = list(hand.objects)
                if cards:
                    # Simple heuristic: discard highest CMC first
                    def get_cmc(card):
                        """Get mana value from a card's mana cost string."""
                        cost = card.characteristics.mana_cost
                        if not cost:
                            return 0
                        if isinstance(cost, str):
                            # Parse mana cost string like "{3}{R}{R}"
                            import re
                            total = 0
                            # Find generic mana {N}
                            for m in re.findall(r'\{(\d+)\}', cost):
                                total += int(m)
                            # Count colored mana symbols
                            total += len(re.findall(r'\{[WUBRG]\}', cost))
                            return total
                        return getattr(cost, 'mana_value', 0)

                    cards.sort(key=get_cmc, reverse=True)
                    discard = cards[0]
                    hand.remove(discard)
                    self.zones.graveyards[self.active_player_id].add(discard)
                    discard.zone = Zone.GRAVEYARD
                else:
                    break
            else:
                break  # Would need player input

        # Clear damage from all creatures
        for perm in self.zones.battlefield.creatures():
            perm.damage_marked = 0
            if hasattr(perm, 'damage_sources_with_deathtouch'):
                perm.damage_sources_with_deathtouch.clear()

        # Empty mana pools
        self._empty_mana_pools()

        # Clean up delayed triggers
        self.triggers.cleanup_delayed_triggers()

        # Check if there are triggers - if so, need priority round
        # (This is a simplified check; full implementation would be more complex)
        if self.triggers.pending_triggers:
            put_triggers_on_stack(self)
            if not self.zones.stack.is_empty():
                run_priority_round(self)
                # May need another cleanup step after this

    def _empty_mana_pools(self):
        """
        Empty all players' mana pools.

        Per CR 106.4, mana empties at the end of each step and phase.
        """
        for player in self.players.values():
            player.mana_pool.empty()

    # =========================================================================
    # TURN ORDER
    # =========================================================================

    def _switch_active_player(self):
        """
        Switch to next active player.

        Handles:
        - Normal turn rotation
        - Extra turns (if any are queued)
        """
        # Check for extra turns first
        if self._extra_turns:
            self.active_player_id = self._extra_turns.pop(0)
        else:
            # Normal rotation
            player_ids = list(self.players.keys())
            idx = player_ids.index(self.active_player_id)
            self.active_player_id = player_ids[(idx + 1) % len(player_ids)]

        self.priority.set_active_player(self.active_player_id)

    def add_extra_turn(self, player_id: PlayerId):
        """
        Add an extra turn for a player.

        Extra turns are taken in LIFO order (most recently added first).

        Args:
            player_id: Player who takes the extra turn
        """
        self._extra_turns.insert(0, player_id)

    # =========================================================================
    # ACTION EXECUTION
    # =========================================================================

    def execute_action(self, player_or_action: Any, action: Any = None):
        """
        Execute a player action.

        Handles:
        - Playing lands
        - Casting spells
        - Activating abilities
        - Special actions

        Args:
            player_or_action: Either the player taking action, or the action itself
            action: The action if player was passed first
        """
        # Handle both (player, action) and (action) signatures
        if action is None:
            action = player_or_action
            player = self.players.get(self.active_player_id)
        else:
            player = player_or_action

        # Get action type - handle both string and enum
        action_type = action.action_type
        if isinstance(action_type, str):
            action_type = action_type.lower()

        # Execute based on action type
        if action_type in (ActionType.PLAY_LAND, "play_land"):
            self._execute_play_land_ai(player, action)
        elif action_type in (ActionType.CAST_SPELL, "cast_spell"):
            self._execute_cast_spell_ai(player, action)
        elif action_type in (ActionType.ACTIVATE_ABILITY, "activate_ability"):
            self._execute_activate_ability(action)
        elif action_type in (ActionType.ACTIVATE_MANA_ABILITY, "activate_mana_ability"):
            self._execute_activate_mana_ability(action)

    def _execute_play_land_ai(self, player: 'Player', action: Any):
        """
        Execute land play from AI action.

        Args:
            player: The player playing the land
            action: AI action with card reference
        """
        from .objects import Permanent

        player_id = player.player_id
        hand = self.zones.hands[player_id]

        # Get card from action - AI uses card reference
        card = action.card if hasattr(action, 'card') else None
        if card is None and hasattr(action, 'card_id'):
            card = hand.get_by_id(action.card_id)

        if card and player.can_play_land():
            hand.remove(card)

            # Create permanent
            perm = Permanent(
                object_id=card.object_id,
                base_characteristics=card.characteristics,
                characteristics=card.characteristics.copy() if hasattr(card.characteristics, 'copy') else card.characteristics,
                owner=player,
                controller=player,
                zone=Zone.BATTLEFIELD,
                entered_battlefield_this_turn=True,
                summoning_sick=False  # Lands don't have summoning sickness
            )
            self.zones.battlefield.add(perm)
            player.land_played_this_turn = True

            # Notify AI
            if player.ai and hasattr(player.ai, 'notify_land_played'):
                player.ai.notify_land_played()

            self.events.emit(LandPlayedEvent(
                land_id=perm.object_id,
                player_id=player_id
            ))

            # ETB event
            self.events.emit(EntersBattlefieldEvent(
                object_id=perm.object_id,
                from_zone=Zone.HAND
            ))

    def _execute_cast_spell_ai(self, player: 'Player', action: Any):
        """
        Execute spell casting from AI action.

        Args:
            player: The player casting
            action: AI action with card reference
        """
        from .objects import Permanent

        player_id = player.player_id
        hand = self.zones.hands[player_id]

        # Get card from action
        card = action.card if hasattr(action, 'card') else None
        if card is None:
            return

        # Check if we can cast (simplified - just check if in hand)
        if card not in hand.objects:
            return

        # PAY MANA COST - CR 601.2h
        mana_cost_str = card.characteristics.mana_cost if card.characteristics else None
        if mana_cost_str:
            from .mana import ManaCost
            cost = ManaCost.parse(mana_cost_str)
            if not self.mana_manager.auto_pay_cost(player_id, cost):
                # Can't afford - don't cast
                return

        hand.remove(card)

        # For creatures, put directly on battlefield (simplified - no stack)
        chars = card.characteristics
        is_creature = any(
            str(t).lower() == 'creature' or (hasattr(t, 'name') and t.name.lower() == 'creature')
            for t in chars.types
        )

        if is_creature:
            perm = Permanent(
                object_id=card.object_id,
                base_characteristics=chars,
                characteristics=chars.copy() if hasattr(chars, 'copy') else chars,
                owner=player,
                controller=player,
                zone=Zone.BATTLEFIELD,
                entered_battlefield_this_turn=True,
                summoning_sick=True
            )
            self.zones.battlefield.add(perm)

            self.events.emit(EntersBattlefieldEvent(
                object_id=perm.object_id,
                from_zone=Zone.HAND
            ))
        else:
            # Non-creature spells go to graveyard after resolving
            self.zones.graveyards[player_id].add(card)
            card.zone = Zone.GRAVEYARD

        player.spells_cast_this_turn += 1

    def _execute_play_land(self, action: Any):
        """
        Execute land play action.

        Args:
            action: Action with card_id of land to play
        """
        from .objects import Permanent

        player_id = self.priority.priority_player_id
        player = self.players[player_id]
        hand = self.zones.hands[player_id]

        card = hand.get_by_id(action.card_id)

        if card and player.can_play_land():
            hand.remove(card)

            # Create permanent
            perm = Permanent(
                object_id=card.object_id,
                owner_id=card.owner_id,
                controller_id=card.controller_id,
                characteristics=card.characteristics,
                zone=Zone.BATTLEFIELD,
                timestamp=self.get_timestamp(),
                entered_battlefield_this_turn=True
            )

            self.zones.battlefield.add(perm)
            player.play_land()

            self.events.emit(LandPlayedEvent(
                land_id=perm.object_id,
                player_id=player_id,
                land_drop_number=player.lands_played_this_turn
            ))

            # ETB event
            self.events.emit(EntersBattlefieldEvent(
                object_id=perm.object_id,
                from_zone=Zone.HAND
            ))

    def _execute_cast_spell(self, action: Any):
        """
        Execute spell casting action.

        Args:
            action: Action with card_id, targets, and other spell parameters
        """
        targets = getattr(action, 'targets', [])
        modes = getattr(action, 'modes', None)
        x_value = getattr(action, 'x_value', 0)

        self.stack_manager.cast_spell(
            self.priority.priority_player_id,
            action.card_id,
            targets=targets,
            modes=modes,
            x_value=x_value
        )

    def _execute_activate_ability(self, action: Any):
        """
        Execute ability activation.

        Args:
            action: Action with source_id, ability_index, and targets
        """
        targets = getattr(action, 'targets', [])
        ability_index = getattr(action, 'ability_index', 0)

        self.stack_manager.activate_ability(
            self.priority.priority_player_id,
            action.source_id,
            ability_index,
            targets=targets
        )

    def _execute_activate_mana_ability(self, action: Any):
        """
        Execute mana ability activation.

        Mana abilities don't use the stack (CR 605.3).

        Args:
            action: Action with source_id of permanent with mana ability
        """
        self.mana_manager.activate_mana_ability(
            self.priority.priority_player_id,
            action.source_id
        )

    # =========================================================================
    # STACK RESOLUTION
    # =========================================================================

    def resolve_top_of_stack(self):
        """
        Resolve the top object of the stack.

        Delegates to StackManager for spell/ability resolution.
        """
        self.stack_manager.resolve_top()

    # =========================================================================
    # GAME STATE QUERIES
    # =========================================================================

    def can_play_sorcery(self, player_id: PlayerId) -> bool:
        """
        Check if a player can cast sorcery-speed spells.

        Sorcery-speed actions require:
        - It's a main phase
        - The stack is empty
        - The player is the active player
        - The player has priority

        Args:
            player_id: Player to check

        Returns:
            True if sorcery-speed actions are allowed
        """
        if self.current_phase not in (PhaseType.PRECOMBAT_MAIN, PhaseType.POSTCOMBAT_MAIN):
            return False
        if not self.zones.stack.is_empty():
            return False
        if player_id != self.active_player_id:
            return False
        if self.priority.priority_player_id != player_id:
            return False
        return True

    def can_play_instant(self, player_id: PlayerId) -> bool:
        """
        Check if a player can cast instant-speed spells.

        Args:
            player_id: Player to check

        Returns:
            True if the player has priority
        """
        return self.priority.priority_player_id == player_id

    def get_legal_actions(self, player_id: PlayerId) -> List[Any]:
        """
        Get all legal actions for a player.

        This is a simplified version - full implementation would check
        all possible spells, abilities, and special actions.

        Args:
            player_id: Player to get actions for

        Returns:
            List of legal actions
        """
        actions = []

        # Always can pass
        from .types import GameAction
        actions.append(GameAction(
            action_type=ActionType.PASS,
            player_id=player_id
        ))

        # Check for land plays
        if self.can_play_sorcery(player_id):
            player = self.players[player_id]
            if player.can_play_land():
                hand = self.zones.hands[player_id]
                for card in hand.playable_lands():
                    actions.append(GameAction(
                        action_type=ActionType.PLAY_LAND,
                        player_id=player_id,
                        source_id=card.object_id
                    ))

        # Additional actions (spells, abilities) would be added here

        return actions

    def get_game_state_snapshot(self) -> Dict[str, Any]:
        """
        Get a snapshot of current game state.

        Useful for AI decision making and debugging.

        Returns:
            Dictionary containing key game state information
        """
        return {
            'turn_number': self.turn_number,
            'active_player_id': self.active_player_id,
            'priority_player_id': self.priority.priority_player_id,
            'current_phase': self.current_phase,
            'current_step': self.current_step,
            'stack_empty': self.zones.stack.is_empty(),
            'game_over': self.game_over,
            'winner_id': self.winner_id,
            'player_states': {
                pid: {
                    'life': p.life,
                    'poison': p.poison_counters,
                    'hand_size': len(self.zones.hands[pid]),
                    'library_size': len(self.zones.libraries[pid]),
                    'graveyard_size': len(self.zones.graveyards[pid]),
                    'creature_count': len(self.zones.battlefield.creatures(pid)),
                    'land_count': len(self.zones.battlefield.lands(pid)),
                }
                for pid, p in self.players.items()
            }
        }

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def destroy_permanent(self, permanent_id: ObjectId) -> bool:
        """
        Destroy a permanent (moves to graveyard unless indestructible).

        Args:
            permanent_id: ID of permanent to destroy

        Returns:
            True if permanent was destroyed
        """
        from .events import DestroyEvent

        perm = self.zones.battlefield.get_by_id(permanent_id)
        if not perm:
            return False

        # Check indestructible
        if hasattr(perm, 'has_keyword') and perm.has_keyword('indestructible'):
            return False

        # Remove from battlefield
        self.zones.battlefield.remove(perm)

        # Add to graveyard (unless token)
        if not (hasattr(perm, 'is_token') and perm.is_token):
            self.zones.graveyards[perm.owner_id].add(perm)
            perm.zone = Zone.GRAVEYARD

        self.events.emit(DestroyEvent(
            permanent_id=permanent_id,
            source_id=None
        ))

        return True

    def exile_permanent(self, permanent_id: ObjectId) -> bool:
        """
        Exile a permanent.

        Args:
            permanent_id: ID of permanent to exile

        Returns:
            True if permanent was exiled
        """
        from .events import ExileEvent

        perm = self.zones.battlefield.get_by_id(permanent_id)
        if not perm:
            return False

        # Remove from battlefield
        self.zones.battlefield.remove(perm)

        # Add to exile (unless token - tokens cease to exist)
        if not (hasattr(perm, 'is_token') and perm.is_token):
            self.zones.exile.add(perm)
            perm.zone = Zone.EXILE

        self.events.emit(ExileEvent(
            object_id=permanent_id,
            from_zone=Zone.BATTLEFIELD
        ))

        return True

    def sacrifice_permanent(self, permanent_id: ObjectId, player_id: PlayerId) -> bool:
        """
        Sacrifice a permanent (can't be regenerated).

        Args:
            permanent_id: ID of permanent to sacrifice
            player_id: Player sacrificing the permanent

        Returns:
            True if permanent was sacrificed
        """
        from .events import SacrificeEvent

        perm = self.zones.battlefield.get_by_id(permanent_id)
        if not perm:
            return False

        # Can only sacrifice own permanents
        if perm.controller_id != player_id:
            return False

        # Remove from battlefield
        self.zones.battlefield.remove(perm)

        # Add to graveyard (unless token)
        if not (hasattr(perm, 'is_token') and perm.is_token):
            self.zones.graveyards[perm.owner_id].add(perm)
            perm.zone = Zone.GRAVEYARD

        self.events.emit(SacrificeEvent(
            permanent_id=permanent_id,
            controller_id=player_id
        ))

        return True

    def create_token(
        self,
        controller_id: PlayerId,
        name: str,
        types: Set[CardType],
        subtypes: Set[str] = None,
        power: int = None,
        toughness: int = None,
        abilities: List[str] = None,
        colors: Set = None,
        count: int = 1
    ) -> List['Permanent']:
        """
        Create token(s) on the battlefield.

        Args:
            controller_id: Player who controls the tokens
            name: Token name
            types: Card types (usually {CardType.CREATURE})
            subtypes: Creature types, etc.
            power: Power (for creatures)
            toughness: Toughness (for creatures)
            abilities: List of ability texts
            colors: Token colors
            count: Number of tokens to create

        Returns:
            List of created token permanents
        """
        from .objects import Token, Characteristics
        from .events import TokenCreatedEvent

        tokens = []

        for _ in range(count):
            # Create characteristics
            chars = Characteristics(
                name=name,
                types=types,
                subtypes=subtypes or set(),
                power=power,
                toughness=toughness,
                colors=colors or set()
            )

            # Create token
            token = Token(
                object_id=self.next_object_id(),
                owner_id=controller_id,
                controller_id=controller_id,
                characteristics=chars,
                zone=Zone.BATTLEFIELD,
                timestamp=self.get_timestamp(),
                entered_battlefield_this_turn=True
            )

            self.zones.battlefield.add(token)
            tokens.append(token)

            self.events.emit(TokenCreatedEvent(
                token_id=token.object_id,
                controller_id=controller_id,
                token_name=name
            ))

            self.events.emit(EntersBattlefieldEvent(
                object_id=token.object_id,
                from_zone=Zone.COMMAND,  # Tokens don't really come from anywhere
                to_zone=Zone.BATTLEFIELD,
                controller_id=controller_id
            ))

        return tokens

    def deal_damage(
        self,
        source_id: ObjectId,
        target_id: ObjectId,
        amount: int,
        is_combat: bool = False
    ) -> int:
        """
        Deal damage to a creature or planeswalker.

        Args:
            source_id: ID of damage source
            target_id: ID of target permanent
            amount: Amount of damage
            is_combat: Whether this is combat damage

        Returns:
            Amount of damage actually dealt
        """
        from .events import DamageEvent

        target = self.zones.battlefield.get_by_id(target_id)
        if not target or amount <= 0:
            return 0

        source = self.zones.battlefield.get_by_id(source_id)

        # Check for damage prevention effects (simplified)
        # Full implementation would use replacement effects

        # Mark damage on creature
        if target.characteristics.is_creature():
            target.damage_marked = getattr(target, 'damage_marked', 0) + amount

            # Track deathtouch sources
            if source and hasattr(source, 'has_keyword') and source.has_keyword('deathtouch'):
                if not hasattr(target, 'damage_sources_with_deathtouch'):
                    target.damage_sources_with_deathtouch = set()
                target.damage_sources_with_deathtouch.add(source_id)

        # Remove loyalty from planeswalker
        if CardType.PLANESWALKER in target.characteristics.types:
            current = target.counters.get(CounterType.LOYALTY, 0)
            target.counters[CounterType.LOYALTY] = max(0, current - amount)

        self.events.emit(DamageEvent(
            source_id=source_id,
            target_id=target_id,
            amount=amount,
            is_combat=is_combat,
            has_deathtouch=(source and hasattr(source, 'has_keyword') and source.has_keyword('deathtouch')),
            has_lifelink=(source and hasattr(source, 'has_keyword') and source.has_keyword('lifelink'))
        ))

        # Handle lifelink
        if source and hasattr(source, 'has_keyword') and source.has_keyword('lifelink'):
            if hasattr(source, 'controller_id'):
                self.players[source.controller_id].gain_life(amount)

        return amount

    def deal_damage_to_player(
        self,
        source_id: ObjectId,
        player_id: PlayerId,
        amount: int,
        is_combat: bool = False
    ) -> int:
        """
        Deal damage to a player.

        Args:
            source_id: ID of damage source
            player_id: Target player ID
            amount: Amount of damage
            is_combat: Whether this is combat damage

        Returns:
            Amount of damage actually dealt
        """
        from .events import DamageEvent

        if amount <= 0:
            return 0

        player = self.players.get(player_id)
        if not player:
            return 0

        source = self.zones.battlefield.get_by_id(source_id)

        # Deal damage (causes life loss)
        player.deal_damage(amount, source_id)

        self.events.emit(DamageEvent(
            source_id=source_id,
            target_player_id=player_id,
            amount=amount,
            is_combat=is_combat,
            has_lifelink=(source and hasattr(source, 'has_keyword') and source.has_keyword('lifelink')),
            has_infect=(source and hasattr(source, 'has_keyword') and source.has_keyword('infect'))
        ))

        # Handle infect (poison counters instead of damage)
        if source and hasattr(source, 'has_keyword') and source.has_keyword('infect'):
            player.add_poison(amount)

        # Handle lifelink
        if source and hasattr(source, 'has_keyword') and source.has_keyword('lifelink'):
            if hasattr(source, 'controller_id'):
                self.players[source.controller_id].gain_life(amount)

        return amount

    # =========================================================================
    # LOGGING METHODS
    # =========================================================================

    def log(self, message: str, level: str = "info"):
        """
        Log a message if verbose mode is enabled.

        Args:
            message: The message to log
            level: Log level ("info", "debug", "warning", "error")
        """
        if self.config.verbose:
            prefix = {
                "info": "[INFO]",
                "debug": "[DEBUG]",
                "warning": "[WARN]",
                "error": "[ERROR]"
            }.get(level, "[INFO]")
            print(f"{prefix} Turn {self.turn_number}: {message}")

    def log_game_state(self):
        """
        Log the current game state (if verbose mode is enabled).

        Outputs player life totals, hand sizes, board state, etc.
        """
        if not self.config.verbose:
            return

        print(f"\n{'='*60}")
        print(f"TURN {self.turn_number} - {self.current_phase.name} / {self.current_step.name}")
        print(f"Active Player: {self.active_player_id}")
        print(f"{'='*60}")

        for pid, player in self.players.items():
            print(f"\nPlayer {pid}: {player.life} life, {player.poison_counters} poison")
            print(f"  Hand: {len(self.zones.hands[pid])} cards")
            print(f"  Library: {len(self.zones.libraries[pid])} cards")
            print(f"  Graveyard: {len(self.zones.graveyards[pid])} cards")

            creatures = self.zones.battlefield.creatures(pid)
            lands = self.zones.battlefield.lands(pid)
            print(f"  Battlefield: {len(creatures)} creatures, {len(lands)} lands")

            if creatures:
                for c in creatures[:5]:  # Show first 5
                    name = c.characteristics.name if hasattr(c, 'characteristics') else 'Unknown'
                    p = c.characteristics.power if hasattr(c.characteristics, 'power') else '?'
                    t = c.characteristics.toughness if hasattr(c.characteristics, 'toughness') else '?'
                    tapped = " (tapped)" if getattr(c, 'is_tapped', False) else ""
                    print(f"    - {name} {p}/{t}{tapped}")

        if not self.zones.stack.is_empty():
            print(f"\nStack: {len(self.zones.stack)} objects")

        print(f"{'='*60}\n")

    # =========================================================================
    # SPELL EFFECTS EXECUTION
    # =========================================================================

    def execute_spell_effects(self, spell: Any) -> None:
        """
        Execute the effects of a spell based on its abilities.

        Parses the abilities from the card's _db_abilities attribute or rules_text
        and executes the corresponding effects.

        Args:
            spell: The Spell object being resolved
        """
        if not spell.card:
            return

        card = spell.card
        controller_id = spell.controller_id

        # Get abilities from the card (stored from V1 database)
        abilities = getattr(card, '_db_abilities', [])
        if not abilities:
            # Try to parse from rules_text
            rules = getattr(card.characteristics, 'rules_text', '') or ''
            if rules:
                abilities = [a.strip() for a in rules.split(',') if a.strip()]

        # Execute each ability
        for ability_text in abilities:
            self._execute_ability_effect(ability_text, controller_id, spell)

    def _execute_ability_effect(
        self,
        ability_text: str,
        controller_id: PlayerId,
        spell: Any = None
    ) -> None:
        """
        Execute a single ability effect.

        Parses V1 database ability codes and executes them.

        Args:
            ability_text: The ability text/code (e.g., 'draw_2', 'damage_3')
            controller_id: The player who controls the effect
            spell: Optional spell that is the source of the effect
        """
        text = ability_text.lower().strip()

        # CARD DRAW EFFECTS
        if text.startswith('draw_'):
            try:
                count = int(text.split('_')[1])
                self._effect_draw(controller_id, count)
            except (IndexError, ValueError):
                self._effect_draw(controller_id, 1)

        # DAMAGE EFFECTS
        elif text.startswith('damage_'):
            parts = text.split('_')
            if len(parts) > 1:
                if parts[1] == 'variable':
                    # Variable damage - use 3 as default
                    amount = 3
                else:
                    try:
                        amount = int(parts[1])
                    except ValueError:
                        amount = 3
                # Deal damage to opponent
                opponent_id = self._get_opponent(controller_id)
                self.deal_damage_to_player(0, opponent_id, amount)

        # TOKEN CREATION
        elif text.startswith('create_token'):
            parts = text.split('_')
            power, toughness = 1, 1
            if len(parts) >= 4:
                try:
                    power = int(parts[2])
                    toughness = int(parts[3])
                except ValueError:
                    pass
            self.create_tokens(
                name="Token",
                power=power,
                toughness=toughness,
                types={CardType.CREATURE},
                controller_id=controller_id,
                count=1
            )

        # DESTRUCTION
        elif text == 'destroy_creature':
            # Simplified: destroy opponent's first creature
            opponent_id = self._get_opponent(controller_id)
            creatures = self.zones.battlefield.creatures(opponent_id)
            if creatures:
                target = creatures[0]
                self._destroy_permanent(target)

        elif text == 'destroy_artifact':
            opponent_id = self._get_opponent(controller_id)
            permanents = self.zones.battlefield.get_all(owner_id=opponent_id)
            for p in permanents:
                if CardType.ARTIFACT in p.characteristics.types:
                    self._destroy_permanent(p)
                    break

        # COUNTERSPELL
        elif text == 'counter_spell':
            # Counter handled differently - need stack interaction
            pass  # Counterspells require targeting

        # EXILE
        elif text == 'exile':
            opponent_id = self._get_opponent(controller_id)
            permanents = self.zones.battlefield.get_all(owner_id=opponent_id)
            if permanents:
                self._exile_permanent(permanents[0])

        # BOUNCE
        elif text == 'bounce':
            opponent_id = self._get_opponent(controller_id)
            permanents = self.zones.battlefield.get_all(owner_id=opponent_id)
            if permanents:
                self._bounce_permanent(permanents[0])

        # PUMP
        elif text.startswith('pump_'):
            parts = text.split('_')
            if len(parts) >= 3:
                try:
                    power_boost = int(parts[1])
                    toughness_boost = int(parts[2])
                    # Pump own creature
                    creatures = self.zones.battlefield.creatures(controller_id)
                    if creatures:
                        self._pump_creature(creatures[0], power_boost, toughness_boost)
                except ValueError:
                    pass

        # LIFEGAIN
        elif text.startswith('gain_life') or text.startswith('lifegain'):
            try:
                parts = text.split('_')
                amount = int(parts[-1]) if len(parts) > 1 else 3
                self.players[controller_id].gain_life(amount)
            except ValueError:
                self.players[controller_id].gain_life(3)

        # MILL
        elif text.startswith('mill_'):
            try:
                count = int(text.split('_')[1])
                opponent_id = self._get_opponent(controller_id)
                for _ in range(count):
                    self._mill_card(opponent_id)
            except (IndexError, ValueError):
                pass

    def _get_opponent(self, player_id: PlayerId) -> PlayerId:
        """Get the opponent's player ID."""
        for pid in self.players:
            if pid != player_id:
                return pid
        return player_id  # Fallback

    def _effect_draw(self, player_id: PlayerId, count: int) -> None:
        """Draw cards for a player."""
        for _ in range(count):
            self.draw_card(player_id)

    def _destroy_permanent(self, permanent: Any) -> None:
        """Destroy a permanent (move to graveyard)."""
        if not permanent:
            return

        owner_id = getattr(permanent, 'owner_id', 1)
        self.zones.battlefield.remove(permanent)
        self.zones.graveyards[owner_id].add(permanent)

        # Emit event
        from .events import ZoneChangeEvent
        self.events.emit(ZoneChangeEvent(
            object_id=permanent.object_id,
            from_zone=Zone.BATTLEFIELD,
            to_zone=Zone.GRAVEYARD
        ))

    def _exile_permanent(self, permanent: Any) -> None:
        """Exile a permanent."""
        if not permanent:
            return

        owner_id = getattr(permanent, 'owner_id', 1)
        self.zones.battlefield.remove(permanent)
        self.zones.exile.add(permanent)

        from .events import ZoneChangeEvent
        self.events.emit(ZoneChangeEvent(
            object_id=permanent.object_id,
            from_zone=Zone.BATTLEFIELD,
            to_zone=Zone.EXILE
        ))

    def _bounce_permanent(self, permanent: Any) -> None:
        """Return a permanent to its owner's hand."""
        if not permanent:
            return

        owner_id = getattr(permanent, 'owner_id', 1)
        self.zones.battlefield.remove(permanent)
        self.zones.hands[owner_id].add(permanent)

        from .events import ZoneChangeEvent
        self.events.emit(ZoneChangeEvent(
            object_id=permanent.object_id,
            from_zone=Zone.BATTLEFIELD,
            to_zone=Zone.HAND
        ))

    def _pump_creature(self, creature: Any, power: int, toughness: int) -> None:
        """Give a creature +X/+X until end of turn."""
        if not creature:
            return

        # Apply temporary buff (simplified - should use continuous effects)
        if hasattr(creature, 'characteristics'):
            if creature.characteristics.power is not None:
                creature.characteristics.power += power
            if creature.characteristics.toughness is not None:
                creature.characteristics.toughness += toughness

    def _mill_card(self, player_id: PlayerId) -> None:
        """Mill a card from player's library to graveyard."""
        library = self.zones.libraries.get(player_id)
        if library and len(library) > 0:
            card = library.draw()
            self.zones.graveyards[player_id].add(card)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = ['Game', 'GameConfig', 'GameResult']
