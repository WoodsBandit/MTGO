#!/usr/bin/env python3
"""
MTG Engine V3 - Simple Match Runner

Point to two deck files and run a match simulation.
This provides the V1-style interface for easy deck testing.

Usage:
    python run_match.py deck1.txt deck2.txt [--games 5] [--verbose]

Example:
    python run_match.py "path/to/MonoRed.txt" "path/to/Dimir.txt" --games 3
"""

import sys
import argparse
from pathlib import Path

# Add v3 to path
v3_dir = Path(__file__).parent
sys.path.insert(0, str(v3_dir))

# Suppress DB loading message for cleaner match output
import io
import contextlib

# Import with suppressed output (DB message will print inside the module)
from tests.run_game import create_simple_card, parse_decklist, V1_CARD_DATABASE
from engine.game import Game, GameConfig
from engine.player import Player
from ai.agent import SimpleAI


def load_deck(filepath: str) -> list:
    """Load a deck from file and create Card objects."""
    entries = parse_decklist(filepath)
    cards = []
    for entry in entries:
        card = create_simple_card(entry['name'])
        cards.append(card)
    return cards


def run_single_game(deck1_cards, deck2_cards, deck1_name, deck2_name, verbose=False):
    """Run a single game and return the result."""
    import copy

    config = GameConfig(
        starting_life=20,
        starting_hand_size=7,
        max_turns=50,
        verbose=verbose
    )

    game = Game(player_ids=[1, 2], config=config)

    # Create fresh copies of cards
    d1 = copy.deepcopy(deck1_cards)
    d2 = copy.deepcopy(deck2_cards)

    game.setup_game(d1, d2)

    # Attach AI
    for pid, player in game.players.items():
        player.ai = SimpleAI(player, game)

    result = game.play_game()

    return {
        'winner_id': result.winner.player_id if result.winner else None,
        'turns': result.turns_played,
        'reason': result.reason,
        'final_life': result.final_life,
        'deck1_name': deck1_name,
        'deck2_name': deck2_name
    }


def run_match(deck1_path: str, deck2_path: str, num_games: int = 3, verbose: bool = False):
    """Run a match (multiple games) between two decks."""

    deck1_name = Path(deck1_path).stem.replace('_', ' ')
    deck2_name = Path(deck2_path).stem.replace('_', ' ')

    print("=" * 60)
    print("MTG ENGINE V3 - Match Simulation")
    print("=" * 60)
    print(f"\n{deck1_name} vs {deck2_name}")
    print(f"Best of {num_games} games\n")

    # Load decks
    deck1_cards = load_deck(deck1_path)
    deck2_cards = load_deck(deck2_path)

    print(f"Deck 1: {len(deck1_cards)} cards")
    print(f"Deck 2: {len(deck2_cards)} cards\n")

    # Track results
    deck1_wins = 0
    deck2_wins = 0
    game_results = []

    wins_needed = (num_games // 2) + 1
    games_played = 0

    while deck1_wins < wins_needed and deck2_wins < wins_needed and games_played < num_games:
        games_played += 1
        print(f"--- Game {games_played} ---")

        result = run_single_game(deck1_cards, deck2_cards, deck1_name, deck2_name, verbose)
        game_results.append(result)

        if result['winner_id'] == 1:
            deck1_wins += 1
            winner = deck1_name
        else:
            deck2_wins += 1
            winner = deck2_name

        print(f"  Winner: {winner}")
        print(f"  Turns: {result['turns']}")
        print(f"  Reason: {result['reason']}")
        print(f"  Final Life: P1={result['final_life'].get(1, 0)}, P2={result['final_life'].get(2, 0)}")
        print()

    # Print match summary
    print("=" * 60)
    print("MATCH RESULT")
    print("=" * 60)
    print(f"\n{deck1_name}: {deck1_wins} wins")
    print(f"{deck2_name}: {deck2_wins} wins")
    print()

    if deck1_wins > deck2_wins:
        print(f"*** {deck1_name} WINS THE MATCH {deck1_wins}-{deck2_wins} ***")
    elif deck2_wins > deck1_wins:
        print(f"*** {deck2_name} WINS THE MATCH {deck2_wins}-{deck1_wins} ***")
    else:
        print(f"*** MATCH DRAW {deck1_wins}-{deck2_wins} ***")

    print()

    return {
        'deck1_name': deck1_name,
        'deck2_name': deck2_name,
        'deck1_wins': deck1_wins,
        'deck2_wins': deck2_wins,
        'games': game_results
    }


def main():
    parser = argparse.ArgumentParser(description='Run MTG match simulation')
    parser.add_argument('deck1', help='Path to first deck file')
    parser.add_argument('deck2', help='Path to second deck file')
    parser.add_argument('--games', type=int, default=3, help='Number of games (default: 3)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed game output')

    args = parser.parse_args()

    # Validate deck files
    if not Path(args.deck1).exists():
        print(f"Error: Deck file not found: {args.deck1}")
        sys.exit(1)
    if not Path(args.deck2).exists():
        print(f"Error: Deck file not found: {args.deck2}")
        sys.exit(1)

    run_match(args.deck1, args.deck2, args.games, args.verbose)


if __name__ == "__main__":
    main()
