#!/usr/bin/env python3
"""
Run a game and export replay JSON for the visual viewer.

Usage:
    python run_replay_game.py [deck1] [deck2] [output]

Example:
    python run_replay_game.py
    python run_replay_game.py "decks/12.28.25/Mono_Red_Aggro_Meta_AI.txt" "decks/12.28.25/Dimir_Midrange_Meta_AI.txt" "game_replay.json"
"""

import sys
import os
import random

# Add the engine to path properly
script_dir = os.path.dirname(os.path.abspath(__file__))
engine_path = os.path.join(script_dir, 'Engine')
if engine_path not in sys.path:
    sys.path.insert(0, engine_path)

from v3.engine.game import Game, GameConfig
from v3.engine.replay import ReplayRecorder
from v3.cards.parser import DecklistParser, Deck
from v3.cards.database import get_database
from v3.ai.agent import SimpleAI


def load_deck(filepath: str):
    """Load a deck from file and convert to Card objects."""
    parser = DecklistParser()
    decklist = parser.parse_file(filepath)
    database = get_database()
    return Deck.from_decklist(decklist, database)


def run_game_with_replay(deck1_path: str, deck2_path: str, output_path: str):
    """Run a game and save replay to JSON."""

    print(f"Loading decks...")
    print(f"  Deck 1: {deck1_path}")
    print(f"  Deck 2: {deck2_path}")

    # Load decks
    deck1 = load_deck(deck1_path)
    deck2 = load_deck(deck2_path)

    deck1_name = os.path.basename(deck1_path).replace('.txt', '').replace('_AI', '')
    deck2_name = os.path.basename(deck2_path).replace('.txt', '').replace('_AI', '')

    print(f"  {deck1_name}: {len(deck1.cards)} cards")
    print(f"  {deck2_name}: {len(deck2.cards)} cards")

    # Create game with config
    config = GameConfig(
        starting_life=20,
        starting_hand_size=7,
        max_turns=50,
        verbose=True
    )

    game = Game(player_ids=[1, 2], config=config)

    # Create and attach replay recorder
    recorder = ReplayRecorder()
    recorder.attach_to_game(game)
    recorder.metadata.deck1_name = deck1_name
    recorder.metadata.deck2_name = deck2_name

    # Create AI agents
    ai1 = SimpleAI(None, None)
    ai2 = SimpleAI(None, None)

    # Setup game with AI agents
    print("\nSetting up game...")
    game.setup_game(deck1.cards, deck2.cards, ai1=ai1, ai2=ai2)

    # Re-attach AI with proper references
    for pid, player in game.players.items():
        player.ai.player = player
        player.ai.game = game

    # Hook into game events to record frames
    def on_phase_change(event):
        recorder.record_action("phase_change", game.active_player_id,
                              details={"phase": str(getattr(event, 'phase', 'unknown'))})

    def on_spell_cast(event):
        card_name = "Unknown"
        if hasattr(event, 'spell') and event.spell:
            card_name = getattr(event.spell.characteristics, 'name', 'Unknown') if hasattr(event.spell, 'characteristics') else str(event.spell)
        recorder.record_action("cast_spell", getattr(event, 'player_id', game.active_player_id),
                              card=card_name)

    def on_creature_attacks(event):
        recorder.record_action("attack", game.active_player_id,
                              card=str(getattr(event, 'attacker', 'creature')))

    # Subscribe to events if the event system supports it
    if hasattr(game, 'events') and hasattr(game.events, 'subscribe'):
        try:
            game.events.subscribe('PhaseChangeEvent', on_phase_change)
            game.events.subscribe('SpellCastEvent', on_spell_cast)
            game.events.subscribe('CreatureAttacksEvent', on_creature_attacks)
        except:
            pass  # Event system may not have these events

    # Record initial state
    recorder.record_game_start(deck1_name, deck2_name)

    print("\nPlaying game...")
    print("-" * 40)

    # Play the game - let it handle everything
    result = game.play_game(max_turns=config.max_turns)

    print("-" * 40)

    # Record game end
    winner_id = result.winner.player_id if result.winner else None
    reason = result.reason if result.reason else "unknown"
    recorder.record_game_end(winner_id or 0, reason)

    # Get winner name
    winner_name = deck1_name if winner_id == 1 else deck2_name if winner_id == 2 else "Draw"

    print(f"\nGame Over!")
    print(f"Winner: Player {winner_id} ({winner_name})")
    print(f"Reason: {reason}")
    print(f"Final Life: P1={result.final_life.get(1, 0)}, P2={result.final_life.get(2, 0)}")
    print(f"Turns played: {result.turns_played}")
    print(f"Frames recorded: {len(recorder.frames)}")

    # If no frames were recorded during gameplay, create some now
    if len(recorder.frames) < 3:
        print("\nRecording final game state...")
        recorder.record_frame()

    # Save replay
    print(f"\nSaving replay to: {output_path}")
    recorder.save_to_file(output_path)

    print("Done!")
    return recorder


def find_test_decks():
    """Find available test decks."""
    deck_dirs = [
        "decks/12.28.25",
        "decks",
        "Engine/v3/tests/decks"
    ]

    for deck_dir in deck_dirs:
        full_path = os.path.join(os.path.dirname(__file__), deck_dir)
        if os.path.exists(full_path):
            decks = [f for f in os.listdir(full_path) if f.endswith('.txt')]
            if decks:
                return full_path, decks

    return None, []


def main():
    # Default paths
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) >= 3:
        deck1_path = sys.argv[1]
        deck2_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else "Viewer/demo_replay.json"
    else:
        # Find test decks
        deck_dir, available_decks = find_test_decks()

        if not available_decks:
            print("No test decks found. Creating a simple test deck...")

            # Create simple test deck directory
            test_deck_dir = os.path.join(script_dir, "test_decks")
            os.makedirs(test_deck_dir, exist_ok=True)

            # Create a simple mono-red deck
            test_deck_content = """Engine_Test_Deck

4 Abrade
4 Bristlepack Sentry
4 Burst Lightning
4 Cactuar
4 Colossal Rattlewurm
4 Demon Wall
4 Diregraf Ghoul
4 Fear of Exposure
20 Mountain
4 Pugnacious Hammerskull
4 Shipwreck Sentry
"""
            test_deck_path = os.path.join(test_deck_dir, "Engine_Test_Deck.txt")
            with open(test_deck_path, 'w') as f:
                f.write(test_deck_content)

            deck1_path = test_deck_path
            deck2_path = test_deck_path
        else:
            # Use two random decks
            if len(available_decks) >= 2:
                selected = random.sample(available_decks, 2)
            else:
                selected = [available_decks[0], available_decks[0]]

            deck1_path = os.path.join(deck_dir, selected[0])
            deck2_path = os.path.join(deck_dir, selected[1])

        output_path = os.path.join(script_dir, "Viewer", "demo_replay.json")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Run the game
    run_game_with_replay(deck1_path, deck2_path, output_path)

    print(f"\nTo view the replay:")
    print(f"  1. Open Viewer/index.html in a browser")
    print(f"  2. Drop {output_path} onto the page")
    print(f"  Or click 'Load Demo' to use the default replay")


if __name__ == "__main__":
    main()
