"""
Quick test runner - Runs a game with minimal output to verify mana fixes.
"""
import sys
import io
from pathlib import Path
from contextlib import redirect_stdout

# Add v3 to path
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))

# Capture initial DB load message
old_stdout = sys.stdout
sys.stdout = io.StringIO()

from tests.run_game import load_deck, V1_CARD_DATABASE
from engine.game import Game, GameConfig
from ai.agent import SimpleAI

db_output = sys.stdout.getvalue()
sys.stdout = old_stdout

# Print DB status
if "Loaded" in db_output:
    print(db_output.strip())

def run_quiet_game(deck_path: str, max_turns: int = 10):
    """Run a game with suppressed AI output."""

    print(f"\nLoading deck: {Path(deck_path).name}")
    deck1 = load_deck(deck_path)
    deck2 = load_deck(deck_path)
    print(f"Cards loaded: {len(deck1)}")

    # Create game
    config = GameConfig(
        starting_life=20,
        starting_hand_size=7,
        max_turns=max_turns,
        verbose=False
    )

    game = Game(player_ids=[1, 2], config=config)
    game.setup_game(deck1, deck2)

    # Attach AI
    for pid, player in game.players.items():
        player.ai = SimpleAI(player, game)

    print(f"\nRunning {max_turns}-turn game (AI output suppressed)...")

    # Capture AI spam during game
    captured = io.StringIO()
    with redirect_stdout(captured):
        try:
            result = game.play_game()
        except Exception as e:
            sys.stdout = old_stdout
            print(f"\nERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    # Show result
    print("\n" + "=" * 50)
    print("GAME RESULT")
    print("=" * 50)
    print(f"Turns played: {result.turns_played}")
    print(f"Winner: Player {result.winner.player_id if result.winner else 'None (Draw)'}")
    print(f"Reason: {result.reason}")
    print(f"Final life: P1={result.final_life.get(1, '?')}, P2={result.final_life.get(2, '?')}")

    # Show final board
    print("\nFinal Board:")
    bf = game.zones.battlefield
    for pid in [1, 2]:
        creatures = list(bf.creatures(controller_id=pid))
        lands = list(bf.lands(controller_id=pid))
        tapped_lands = sum(1 for l in lands if getattr(l, 'is_tapped', False))
        print(f"  P{pid}: {len(lands)} lands ({tapped_lands} tapped), {len(creatures)} creatures")

    # Count AI output lines to see if there's a loop
    ai_lines = captured.getvalue().count('\n')
    print(f"\nAI output lines suppressed: {ai_lines}")

    return result


def main():
    deck_dir = Path(r"C:\Users\Xx LilMan xX\Documents\Claude Docs\MTGO\decks\12.28.25")

    # Use simple test deck
    test_deck = deck_dir / "Engine_Test_Deck.txt"
    if not test_deck.exists():
        # Try mono red
        test_deck = deck_dir / "Mono_Red_Aggro_Meta_AI.txt"

    if not test_deck.exists():
        print(f"No test deck found in {deck_dir}")
        # List available decks
        decks = list(deck_dir.glob("*.txt"))
        if decks:
            print("Available decks:")
            for d in decks[:5]:
                print(f"  {d.name}")
            test_deck = decks[0]
        else:
            return

    run_quiet_game(str(test_deck), max_turns=5)


if __name__ == "__main__":
    main()
