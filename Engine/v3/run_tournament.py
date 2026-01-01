#!/usr/bin/env python3
"""
MTG Engine V3 - Tournament Runner

Runs a round-robin tournament between multiple decks.
Each matchup plays 100 games each way (A vs B, then B vs A).

Usage:
    python run_tournament.py [--games 100] [--output results.txt]
"""

import sys
import argparse
import time
import copy
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add v3 to path
v3_dir = Path(__file__).parent
sys.path.insert(0, str(v3_dir))

# Suppress DB loading message
import io
import contextlib

from tests.run_game import create_simple_card, parse_decklist, V1_CARD_DATABASE
from engine.game import Game, GameConfig
from ai.agent import SimpleAI, ExpertAI


def load_deck(filepath: str) -> list:
    """Load a deck from file and create Card objects."""
    entries = parse_decklist(filepath)
    cards = []
    for entry in entries:
        card = create_simple_card(entry['name'])
        cards.append(card)
    return cards


def run_single_game(deck1_cards, deck2_cards, verbose=False):
    """Run a single game and return winner (1 or 2)."""
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

    # Attach Expert AI for high-level play
    for pid, player in game.players.items():
        player.ai = ExpertAI(player, game)

    try:
        result = game.play_game()
        if result.winner:
            return result.winner.player_id
        return 0  # Draw
    except Exception as e:
        # Game error - count as draw
        return 0


def run_matchup(deck1_name, deck1_cards, deck2_name, deck2_cards, games_per_side=100, verbose=False):
    """
    Run a complete matchup between two decks.

    Plays games_per_side games with deck1 as player 1,
    then games_per_side games with deck2 as player 1.

    Returns dict with results.
    """
    results = {
        'deck1_name': deck1_name,
        'deck2_name': deck2_name,
        'deck1_wins_as_p1': 0,
        'deck2_wins_as_p1': 0,
        'deck1_wins_as_p2': 0,
        'deck2_wins_as_p2': 0,
        'draws': 0,
        'total_games': games_per_side * 2
    }

    # First set: deck1 is player 1
    for i in range(games_per_side):
        winner = run_single_game(deck1_cards, deck2_cards, verbose)
        if winner == 1:
            results['deck1_wins_as_p1'] += 1
        elif winner == 2:
            results['deck2_wins_as_p2'] += 1
        else:
            results['draws'] += 1

    # Second set: deck2 is player 1
    for i in range(games_per_side):
        winner = run_single_game(deck2_cards, deck1_cards, verbose)
        if winner == 1:
            results['deck2_wins_as_p1'] += 1
        elif winner == 2:
            results['deck1_wins_as_p2'] += 1
        else:
            results['draws'] += 1

    # Calculate totals
    results['deck1_total_wins'] = results['deck1_wins_as_p1'] + results['deck1_wins_as_p2']
    results['deck2_total_wins'] = results['deck2_wins_as_p1'] + results['deck2_wins_as_p2']
    results['deck1_winrate'] = results['deck1_total_wins'] / (results['total_games'] - results['draws']) * 100 if (results['total_games'] - results['draws']) > 0 else 0
    results['deck2_winrate'] = results['deck2_total_wins'] / (results['total_games'] - results['draws']) * 100 if (results['total_games'] - results['draws']) > 0 else 0

    return results


def run_tournament(deck_dir: str, games_per_side: int = 100, output_file: str = None, verbose: bool = False):
    """
    Run a round-robin tournament between all decks in a directory.
    """
    deck_dir = Path(deck_dir)

    # Find all deck files
    deck_files = sorted(deck_dir.glob("*.txt"))
    if not deck_files:
        print(f"No deck files found in {deck_dir}")
        return

    print("=" * 70)
    print("MTG ENGINE V3 - TOURNAMENT")
    print("=" * 70)
    print(f"\nDecks found: {len(deck_files)}")
    print(f"Games per matchup: {games_per_side * 2} ({games_per_side} each way)")

    # Load all decks
    decks = {}
    for deck_file in deck_files:
        deck_name = deck_file.stem.replace('_', ' ')
        try:
            deck_cards = load_deck(str(deck_file))
            decks[deck_name] = deck_cards
            print(f"  Loaded: {deck_name} ({len(deck_cards)} cards)")
        except Exception as e:
            print(f"  Error loading {deck_name}: {e}")

    if len(decks) < 2:
        print("Need at least 2 decks for a tournament")
        return

    # Calculate total matchups
    deck_names = list(decks.keys())
    num_decks = len(deck_names)
    num_matchups = (num_decks * (num_decks - 1)) // 2
    total_games = num_matchups * games_per_side * 2

    print(f"\nTotal matchups: {num_matchups}")
    print(f"Total games to play: {total_games}")
    print(f"\nStarting tournament at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)

    # Track overall stats
    deck_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'matchups_won': 0, 'matchups_lost': 0})
    matchup_results = []

    start_time = time.time()
    matchup_count = 0

    # Run all matchups
    for i in range(num_decks):
        for j in range(i + 1, num_decks):
            matchup_count += 1
            deck1_name = deck_names[i]
            deck2_name = deck_names[j]

            print(f"\nMatchup {matchup_count}/{num_matchups}: {deck1_name} vs {deck2_name}")

            matchup_start = time.time()
            result = run_matchup(
                deck1_name, decks[deck1_name],
                deck2_name, decks[deck2_name],
                games_per_side, verbose
            )
            matchup_time = time.time() - matchup_start

            matchup_results.append(result)

            # Update deck stats
            deck_stats[deck1_name]['wins'] += result['deck1_total_wins']
            deck_stats[deck1_name]['losses'] += result['deck2_total_wins']
            deck_stats[deck1_name]['draws'] += result['draws']

            deck_stats[deck2_name]['wins'] += result['deck2_total_wins']
            deck_stats[deck2_name]['losses'] += result['deck1_total_wins']
            deck_stats[deck2_name]['draws'] += result['draws']

            # Track matchup wins
            if result['deck1_total_wins'] > result['deck2_total_wins']:
                deck_stats[deck1_name]['matchups_won'] += 1
                deck_stats[deck2_name]['matchups_lost'] += 1
            elif result['deck2_total_wins'] > result['deck1_total_wins']:
                deck_stats[deck2_name]['matchups_won'] += 1
                deck_stats[deck1_name]['matchups_lost'] += 1

            print(f"  Result: {deck1_name} {result['deck1_total_wins']}-{result['deck2_total_wins']} {deck2_name}")
            print(f"  (Draws: {result['draws']}, Time: {matchup_time:.1f}s)")

    total_time = time.time() - start_time

    # Generate report
    report = generate_report(deck_stats, matchup_results, total_time, games_per_side)

    print("\n" + report)

    # Save to file if requested
    if output_file:
        output_path = Path(output_file)
        output_path.write_text(report)
        print(f"\nResults saved to: {output_path}")

    return deck_stats, matchup_results


def generate_report(deck_stats, matchup_results, total_time, games_per_side):
    """Generate a formatted tournament report."""
    lines = []
    lines.append("=" * 70)
    lines.append("TOURNAMENT RESULTS")
    lines.append("=" * 70)
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    lines.append(f"Games per matchup: {games_per_side * 2}")

    # Overall standings
    lines.append("\n" + "-" * 70)
    lines.append("OVERALL STANDINGS")
    lines.append("-" * 70)

    # Sort by win rate
    standings = []
    for deck_name, stats in deck_stats.items():
        total = stats['wins'] + stats['losses']
        winrate = (stats['wins'] / total * 100) if total > 0 else 0
        standings.append({
            'name': deck_name,
            'wins': stats['wins'],
            'losses': stats['losses'],
            'draws': stats['draws'],
            'winrate': winrate,
            'matchups_won': stats['matchups_won'],
            'matchups_lost': stats['matchups_lost']
        })

    standings.sort(key=lambda x: x['winrate'], reverse=True)

    lines.append(f"\n{'Rank':<5} {'Deck':<35} {'W-L':<12} {'Win%':<8} {'Matchups':<10}")
    lines.append("-" * 70)

    for rank, s in enumerate(standings, 1):
        record = f"{s['wins']}-{s['losses']}"
        matchups = f"{s['matchups_won']}-{s['matchups_lost']}"
        lines.append(f"{rank:<5} {s['name']:<35} {record:<12} {s['winrate']:.1f}%   {matchups:<10}")

    # Head-to-head matrix
    lines.append("\n" + "-" * 70)
    lines.append("HEAD-TO-HEAD RESULTS")
    lines.append("-" * 70)

    for result in matchup_results:
        d1 = result['deck1_name']
        d2 = result['deck2_name']
        w1 = result['deck1_total_wins']
        w2 = result['deck2_total_wins']
        draws = result['draws']

        if w1 > w2:
            winner = d1
        elif w2 > w1:
            winner = d2
        else:
            winner = "DRAW"

        lines.append(f"\n{d1} vs {d2}")
        lines.append(f"  Score: {w1}-{w2} (Draws: {draws})")
        lines.append(f"  Winner: {winner}")
        lines.append(f"  {d1} as P1: {result['deck1_wins_as_p1']} wins")
        lines.append(f"  {d2} as P1: {result['deck2_wins_as_p1']} wins")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Run MTG tournament simulation')
    parser.add_argument('--deck-dir', type=str,
                        default=r"C:\Users\Xx LilMan xX\Documents\Claude Docs\MTGO\decks\tournament",
                        help='Directory containing deck files')
    parser.add_argument('--games', type=int, default=100,
                        help='Games per side (total = games * 2)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file for results')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed game output')

    args = parser.parse_args()

    # Set default output file
    if args.output is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = str(Path(args.deck_dir).parent / f"tournament_results_{timestamp}.txt")

    run_tournament(args.deck_dir, args.games, args.output, args.verbose)


if __name__ == "__main__":
    main()
