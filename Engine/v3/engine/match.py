"""MTG Engine V3 - Match Runner

This module implements the match runner for best-of-3 (or best-of-N) games
following the Magic: The Gathering tournament rules. It handles:
- Game summaries and match results
- Best-of-N match logic with alternating play/draw
- Match running with parallel execution support
- Convenience functions for running matchups

Rules References:
- MTR 2.1: Match Structure
- MTR 2.2: Play/Draw Rule
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy

from .game import Game
from .types import PlayerId


# =============================================================================
# GAME SUMMARY
# =============================================================================

@dataclass
class GameSummary:
    """
    Summary of a completed game.

    Captures the essential outcome information from a single game
    for reporting and analysis purposes.

    Attributes:
        game_number: Which game in the match (1, 2, 3, etc.)
        winner_id: Player ID of the winner
        turns: Total number of turns played
        winner_life: Life total of the winner at game end
        loser_life: Life total of the loser at game end
        winning_reason: How the game was won (e.g., "opponent_life_zero",
                       "opponent_decked", "opponent_conceded", "turn_limit")
    """
    game_number: int
    winner_id: PlayerId
    turns: int
    winner_life: int
    loser_life: int
    winning_reason: str

    def __str__(self) -> str:
        return (f"Game {self.game_number}: Player {self.winner_id} wins "
                f"({self.winning_reason}) on turn {self.turns}")


# =============================================================================
# MATCH RESULT
# =============================================================================

@dataclass
class MatchResult:
    """
    Result of a completed match (best-of-N games).

    Tracks all games played in the match and determines the overall winner.

    Attributes:
        deck1_name: Name of the first deck
        deck2_name: Name of the second deck
        deck1_wins: Number of games won by deck 1
        deck2_wins: Number of games won by deck 2
        games: List of GameSummary objects for each game played
        winner: Name of the winning deck (or "Draw" if tied)
    """
    deck1_name: str
    deck2_name: str
    deck1_wins: int
    deck2_wins: int
    games: List[GameSummary]
    winner: str

    @property
    def is_complete(self) -> bool:
        """
        Check if the match has been completed.

        A match is complete when one player has a majority of wins
        in a best-of-N format.

        Returns:
            True if the match has a decisive winner
        """
        return len(self.games) > 0 and self.winner != ""

    @property
    def score(self) -> str:
        """
        Get the match score in standard format.

        Returns:
            Score string like "2-1" or "2-0"
        """
        return f"{self.deck1_wins}-{self.deck2_wins}"

    def __str__(self) -> str:
        return (f"{self.deck1_name} vs {self.deck2_name}: "
                f"{self.score} - {self.winner} wins")


# =============================================================================
# GAME CONFIG
# =============================================================================

@dataclass
class GameConfig:
    """
    Configuration options for game execution.

    Attributes:
        max_turns: Maximum turns before forcing a result (default 50)
        starting_life: Starting life total (default 20)
        starting_hand_size: Cards drawn at game start (default 7)
        verbose: Whether to print game progress (default False)
        random_seed: Optional seed for reproducibility (default None)
    """
    max_turns: int = 50
    starting_life: int = 20
    starting_hand_size: int = 7
    verbose: bool = False
    random_seed: Optional[int] = None


# =============================================================================
# DECK CLASS (Wrapper for DeckList)
# =============================================================================

@dataclass
class Deck:
    """
    Deck wrapper for match play.

    Wraps a DeckList with additional metadata for match tracking.

    Attributes:
        name: Deck name
        cards: List of Card objects in the mainboard
        sideboard: List of Card objects in the sideboard
    """
    name: str
    cards: List[Any]  # List[Card]
    sideboard: List[Any] = field(default_factory=list)

    def copy_cards(self) -> List[Any]:
        """
        Create a deep copy of the deck's cards for a new game.

        Returns:
            New list of Card copies
        """
        return copy.deepcopy(self.cards)

    def __len__(self) -> int:
        return len(self.cards)


# =============================================================================
# MATCH CLASS
# =============================================================================

class Match:
    """
    Manages a best-of-N match between two decks.

    Handles:
    - Playing individual games
    - Tracking match score
    - Alternating play/draw between games
    - Determining match winner

    Attributes:
        deck1: First deck
        deck2: Second deck
        best_of: Number of games in the match (default 3)
        games_played: List of completed Game objects
        results: List of GameSummary objects
        config: Optional GameConfig for customization
    """

    def __init__(
        self,
        deck1: Deck,
        deck2: Deck,
        best_of: int = 3,
        config: GameConfig = None
    ):
        """
        Initialize a new match.

        Args:
            deck1: First deck (plays first in game 1)
            deck2: Second deck
            best_of: Number of games (must be odd, default 3)
            config: Optional game configuration
        """
        self.deck1 = deck1
        self.deck2 = deck2
        self.best_of = best_of
        self.games_played: List[Game] = []
        self.results: List[GameSummary] = []
        self.config = config or GameConfig()

        # Track wins
        self._deck1_wins = 0
        self._deck2_wins = 0

    def play(self) -> MatchResult:
        """
        Play the complete match.

        Plays games until one player has won a majority (e.g., 2 out of 3).
        Alternates which player is on the play each game.

        Returns:
            MatchResult with complete match information
        """
        wins_needed = (self.best_of // 2) + 1
        game_number = 1

        while not self.is_complete():
            # Alternate who plays first
            # Game 1: deck1 on play, Game 2: deck2 on play, etc.
            deck1_on_play = (game_number % 2) == 1

            summary = self.play_game(game_number, deck1_on_play)
            self.results.append(summary)

            # Update win counts
            if summary.winner_id == 1:
                self._deck1_wins += 1
            else:
                self._deck2_wins += 1

            game_number += 1

            # Check if someone has won the match
            if self._deck1_wins >= wins_needed or self._deck2_wins >= wins_needed:
                break

        # Determine match winner
        if self._deck1_wins > self._deck2_wins:
            winner = self.deck1.name
        elif self._deck2_wins > self._deck1_wins:
            winner = self.deck2.name
        else:
            winner = "Draw"

        return MatchResult(
            deck1_name=self.deck1.name,
            deck2_name=self.deck2.name,
            deck1_wins=self._deck1_wins,
            deck2_wins=self._deck2_wins,
            games=self.results.copy(),
            winner=winner
        )

    def play_game(self, game_number: int, deck1_on_play: bool) -> GameSummary:
        """
        Play a single game in the match.

        Args:
            game_number: Which game this is (1, 2, 3, etc.)
            deck1_on_play: True if deck1 plays first, False if deck2 plays first

        Returns:
            GameSummary of the completed game
        """
        from .game import GameConfig as EngineGameConfig
        from ..ai.agent import SimpleAI

        # Create game config for the engine
        engine_config = EngineGameConfig(
            starting_life=self.config.starting_life,
            starting_hand_size=self.config.starting_hand_size,
            max_turns=self.config.max_turns,
            verbose=self.config.verbose
        )

        # Create fresh game
        player_ids = [1, 2] if deck1_on_play else [2, 1]
        game = Game(player_ids=player_ids, config=engine_config)

        # Get fresh copies of deck cards
        deck1_cards = self.deck1.copy_cards()
        deck2_cards = self.deck2.copy_cards()

        # Setup game
        game.setup_game(deck1_cards, deck2_cards)

        # Attach AI agents to players
        for pid, player in game.players.items():
            player.ai = SimpleAI(player, game)

        # Play the game and get result
        result = game.play_game(max_turns=self.config.max_turns)

        # Store game reference
        self.games_played.append(game)

        # Extract winner_id from result
        winner_id = result.winner.player_id if result.winner else None

        # Determine winning reason
        winning_reason = result.reason if result.reason else self._determine_winning_reason(game, winner_id)

        # Get life totals from result
        winner_life = result.final_life.get(winner_id, 0) if winner_id else 0
        loser_id = 2 if winner_id == 1 else 1
        loser_life = result.final_life.get(loser_id, 0)

        # Map back to deck perspective (player 1 is always deck1)
        actual_winner_id = winner_id if deck1_on_play else (2 if winner_id == 1 else 1)

        return GameSummary(
            game_number=game_number,
            winner_id=actual_winner_id,
            turns=result.turns_played,
            winner_life=winner_life,
            loser_life=loser_life,
            winning_reason=winning_reason
        )

    def _determine_winning_reason(self, game: Game, winner_id: Optional[PlayerId]) -> str:
        """
        Determine how the game was won.

        Args:
            game: The completed game
            winner_id: ID of the winning player

        Returns:
            String describing the winning reason
        """
        if winner_id is None:
            return "no_winner"

        loser_id = 2 if winner_id == 1 else 1
        loser = game.players[loser_id]

        if loser.life <= 0:
            return "opponent_life_zero"
        elif loser.drew_from_empty_library:
            return "opponent_decked"
        elif loser.poison_counters >= 10:
            return "opponent_poisoned"
        elif loser.loss_reason:
            return loser.loss_reason
        elif game.turn_number >= self.config.max_turns:
            return "turn_limit"
        else:
            return "opponent_lost"

    def is_complete(self) -> bool:
        """
        Check if the match is complete.

        Returns:
            True if one player has won a majority of games
        """
        wins_needed = (self.best_of // 2) + 1
        return self._deck1_wins >= wins_needed or self._deck2_wins >= wins_needed

    def get_winner(self) -> Optional[str]:
        """
        Get the match winner's deck name.

        Returns:
            Winner's deck name, or None if match not complete
        """
        if not self.is_complete():
            return None

        if self._deck1_wins > self._deck2_wins:
            return self.deck1.name
        elif self._deck2_wins > self._deck1_wins:
            return self.deck2.name
        else:
            return None


# =============================================================================
# MATCH RUNNER RESULT
# =============================================================================

@dataclass
class MatchRunnerResult:
    """
    Result of running multiple matches between two decks.

    Aggregates statistics across all matches played.

    Attributes:
        deck1_name: Name of the first deck
        deck2_name: Name of the second deck
        deck1_match_wins: Total matches won by deck 1
        deck2_match_wins: Total matches won by deck 2
        deck1_game_wins: Total games won by deck 1
        deck2_game_wins: Total games won by deck 2
        matches: List of all MatchResult objects
    """
    deck1_name: str
    deck2_name: str
    deck1_match_wins: int
    deck2_match_wins: int
    deck1_game_wins: int
    deck2_game_wins: int
    matches: List[MatchResult]

    @property
    def deck1_winrate(self) -> float:
        """
        Calculate deck 1's match win rate.

        Returns:
            Win rate as a float (0.0 to 1.0)
        """
        total = self.deck1_match_wins + self.deck2_match_wins
        if total == 0:
            return 0.0
        return self.deck1_match_wins / total

    @property
    def deck2_winrate(self) -> float:
        """
        Calculate deck 2's match win rate.

        Returns:
            Win rate as a float (0.0 to 1.0)
        """
        total = self.deck1_match_wins + self.deck2_match_wins
        if total == 0:
            return 0.0
        return self.deck2_match_wins / total

    @property
    def deck1_game_winrate(self) -> float:
        """
        Calculate deck 1's game win rate across all matches.

        Returns:
            Win rate as a float (0.0 to 1.0)
        """
        total = self.deck1_game_wins + self.deck2_game_wins
        if total == 0:
            return 0.0
        return self.deck1_game_wins / total

    @property
    def deck2_game_winrate(self) -> float:
        """
        Calculate deck 2's game win rate across all matches.

        Returns:
            Win rate as a float (0.0 to 1.0)
        """
        total = self.deck1_game_wins + self.deck2_game_wins
        if total == 0:
            return 0.0
        return self.deck2_game_wins / total

    @property
    def total_matches(self) -> int:
        """Get total number of matches played."""
        return len(self.matches)

    @property
    def total_games(self) -> int:
        """Get total number of games played."""
        return self.deck1_game_wins + self.deck2_game_wins

    def __str__(self) -> str:
        return (f"{self.deck1_name} vs {self.deck2_name}: "
                f"{self.deck1_match_wins}-{self.deck2_match_wins} matches "
                f"({self.deck1_winrate:.1%} win rate)")


# =============================================================================
# MATCH RUNNER CLASS
# =============================================================================

class MatchRunner:
    """
    Runs multiple matches between two decks.

    Supports both sequential and parallel execution for running
    large numbers of matches for statistical analysis.

    Attributes:
        deck1: First deck
        deck2: Second deck
        num_matches: Number of matches to run (default 5)
        config: Optional GameConfig for all games
    """

    def __init__(
        self,
        deck1: Deck,
        deck2: Deck,
        num_matches: int = 5,
        config: GameConfig = None
    ):
        """
        Initialize the match runner.

        Args:
            deck1: First deck
            deck2: Second deck
            num_matches: Number of matches to run
            config: Optional game configuration
        """
        self.deck1 = deck1
        self.deck2 = deck2
        self.num_matches = num_matches
        self.config = config or GameConfig()

    def run(self) -> MatchRunnerResult:
        """
        Run all matches sequentially.

        Returns:
            MatchRunnerResult with aggregated statistics
        """
        matches: List[MatchResult] = []
        deck1_match_wins = 0
        deck2_match_wins = 0
        deck1_game_wins = 0
        deck2_game_wins = 0

        for i in range(self.num_matches):
            if self.config.verbose:
                print(f"Playing match {i + 1}/{self.num_matches}...")

            match = Match(
                deck1=self.deck1,
                deck2=self.deck2,
                best_of=3,
                config=self.config
            )

            result = match.play()
            matches.append(result)

            # Update statistics
            deck1_game_wins += result.deck1_wins
            deck2_game_wins += result.deck2_wins

            if result.winner == self.deck1.name:
                deck1_match_wins += 1
            elif result.winner == self.deck2.name:
                deck2_match_wins += 1

            if self.config.verbose:
                print(f"  {result}")

        return MatchRunnerResult(
            deck1_name=self.deck1.name,
            deck2_name=self.deck2.name,
            deck1_match_wins=deck1_match_wins,
            deck2_match_wins=deck2_match_wins,
            deck1_game_wins=deck1_game_wins,
            deck2_game_wins=deck2_game_wins,
            matches=matches
        )

    def run_parallel(self, num_workers: int = 4) -> MatchRunnerResult:
        """
        Run matches in parallel using multiple processes.

        Note: Due to Python's GIL, this uses ProcessPoolExecutor for
        true parallelism. Each match runs in a separate process.

        Args:
            num_workers: Number of parallel worker processes

        Returns:
            MatchRunnerResult with aggregated statistics
        """
        matches: List[MatchResult] = []

        # Create match configurations for parallel execution
        match_configs = [
            (self.deck1, self.deck2, 3, self.config)
            for _ in range(self.num_matches)
        ]

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(_run_single_match, *config)
                for config in match_configs
            ]

            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                matches.append(result)

                if self.config.verbose:
                    print(f"Completed match {i + 1}/{self.num_matches}: {result}")

        # Aggregate results
        deck1_match_wins = sum(
            1 for m in matches if m.winner == self.deck1.name
        )
        deck2_match_wins = sum(
            1 for m in matches if m.winner == self.deck2.name
        )
        deck1_game_wins = sum(m.deck1_wins for m in matches)
        deck2_game_wins = sum(m.deck2_wins for m in matches)

        return MatchRunnerResult(
            deck1_name=self.deck1.name,
            deck2_name=self.deck2.name,
            deck1_match_wins=deck1_match_wins,
            deck2_match_wins=deck2_match_wins,
            deck1_game_wins=deck1_game_wins,
            deck2_game_wins=deck2_game_wins,
            matches=matches
        )


def _run_single_match(
    deck1: Deck,
    deck2: Deck,
    best_of: int,
    config: GameConfig
) -> MatchResult:
    """
    Helper function for parallel match execution.

    This function runs in a separate process when using run_parallel.

    Args:
        deck1: First deck
        deck2: Second deck
        best_of: Number of games in match
        config: Game configuration

    Returns:
        MatchResult of the completed match
    """
    match = Match(deck1=deck1, deck2=deck2, best_of=best_of, config=config)
    return match.play()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_matchup(
    deck1_path: str,
    deck2_path: str,
    matches: int = 5,
    best_of: int = 3,
    verbose: bool = False
) -> MatchRunnerResult:
    """
    Convenience function to run a matchup from deck files.

    Loads decks from MTGO-format deck files and runs the specified
    number of matches.

    Args:
        deck1_path: File path to first deck
        deck2_path: File path to second deck
        matches: Number of matches to run (default 5)
        best_of: Games per match (default 3)
        verbose: Whether to print progress (default False)

    Returns:
        MatchRunnerResult with complete statistics

    Example:
        result = run_matchup(
            "decks/mono_red.txt",
            "decks/control.txt",
            matches=10,
            verbose=True
        )
        print_results(result)
    """
    from ..cards.parser import load_deck_file

    # Load decks
    decklist1 = load_deck_file(deck1_path)
    decklist2 = load_deck_file(deck2_path)

    # Create Deck wrappers
    deck1 = Deck(
        name=decklist1.name,
        cards=decklist1.mainboard,
        sideboard=decklist1.sideboard
    )
    deck2 = Deck(
        name=decklist2.name,
        cards=decklist2.mainboard,
        sideboard=decklist2.sideboard
    )

    # Configure and run
    config = GameConfig(verbose=verbose)

    runner = MatchRunner(
        deck1=deck1,
        deck2=deck2,
        num_matches=matches,
        config=config
    )

    return runner.run()


def print_results(result: MatchRunnerResult) -> None:
    """
    Pretty print match results.

    Displays a formatted summary of the matchup results including
    match scores, game scores, and win rates.

    Args:
        result: MatchRunnerResult to display

    Example output:
        ========================================
        MATCHUP RESULTS
        ========================================
        Mono Red Aggro vs UW Control

        Match Record: 3-2
        Game Record:  7-6

        Mono Red Aggro: 60.0% match win rate
        UW Control:     40.0% match win rate

        Individual Matches:
          Match 1: Mono Red Aggro wins (2-1)
          Match 2: UW Control wins (2-0)
          ...
        ========================================
    """
    width = 50
    separator = "=" * width

    print(separator)
    print("MATCHUP RESULTS".center(width))
    print(separator)
    print()
    print(f"{result.deck1_name} vs {result.deck2_name}")
    print()
    print(f"Match Record: {result.deck1_match_wins}-{result.deck2_match_wins}")
    print(f"Game Record:  {result.deck1_game_wins}-{result.deck2_game_wins}")
    print()
    print(f"{result.deck1_name}: {result.deck1_winrate:.1%} match win rate")
    print(f"{result.deck2_name}: {result.deck2_winrate:.1%} match win rate")
    print()

    if result.matches:
        print("Individual Matches:")
        for i, match in enumerate(result.matches, 1):
            print(f"  Match {i}: {match.winner} wins ({match.score})")
        print()

    print(separator)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Data classes
    'GameSummary',
    'MatchResult',
    'MatchRunnerResult',
    'GameConfig',
    'Deck',

    # Classes
    'Match',
    'MatchRunner',

    # Functions
    'run_matchup',
    'print_results',
]
