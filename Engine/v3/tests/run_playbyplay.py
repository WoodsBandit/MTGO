"""
Play-by-play game runner - Runs a single game and generates detailed report.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add v3 to path
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))

from run_game import load_deck, V1_CARD_DATABASE
from engine.types import CardType, PhaseType, StepType
from engine.game import Game, GameConfig
from engine.events import (
    TurnStartEvent, TurnEndEvent, PhaseBeginEvent,
    EntersBattlefieldEvent, DrawCardEvent, LandPlayedEvent,
    GameEvent, ZoneChangeEvent
)
from ai.agent import SimpleAI


class PlayByPlayLogger:
    """Captures detailed play-by-play game log via events."""

    def __init__(self, game):
        self.game = game
        self.log_lines = []
        self.current_turn = 0
        self.current_phase = None
        self.turn_actions = []  # Actions within current turn

        # Subscribe to events
        game.events.subscribe(TurnStartEvent, self.on_turn_start)
        game.events.subscribe(TurnEndEvent, self.on_turn_end)
        game.events.subscribe(PhaseBeginEvent, self.on_phase_start)
        game.events.subscribe(EntersBattlefieldEvent, self.on_etb)
        game.events.subscribe(LandPlayedEvent, self.on_land_played)

    def log(self, msg: str):
        self.log_lines.append(msg)

    def on_turn_start(self, event: TurnStartEvent):
        self.current_turn = event.turn_number
        self.turn_actions = []

        # Get game state at turn start
        self.log(f"\n---\n\n## Turn {event.turn_number} - Player {event.active_player_id}\n")

        for pid in [1, 2]:
            player = self.game.players[pid]
            creatures, lands = self.get_board(pid)

            life_str = f"Life: {player.life}"
            land_count = len(lands)
            creature_count = len(creatures)

            self.log(f"**Player {pid}** - {life_str} | Lands: {land_count} | Creatures: {creature_count}")

            if creatures:
                self.log(f"  - Board: {', '.join(creatures[:5])}")
                if len(creatures) > 5:
                    self.log(f"    ...and {len(creatures) - 5} more")

        self.log("")

    def on_turn_end(self, event: TurnEndEvent):
        # Log life changes at end of turn
        for pid in [1, 2]:
            player = self.game.players[pid]
            if player.life < 20:
                self.log(f"  End of turn: P{pid} at {player.life} life")

    def on_phase_start(self, event: PhaseBeginEvent):
        phase = event.phase_type
        if phase in [PhaseType.PRECOMBAT_MAIN, PhaseType.COMBAT, PhaseType.POSTCOMBAT_MAIN]:
            phase_name = phase.name.replace('_', ' ').title()
            self.log(f"\n**{phase_name}**")
            self.current_phase = phase

    def on_etb(self, event: EntersBattlefieldEvent):
        # Get permanent from battlefield by object_id
        obj_id = event.object_id
        perm = self.game.zones.battlefield.get_by_id(obj_id)
        if perm and hasattr(perm, 'characteristics') and perm.characteristics:
            name = perm.characteristics.name
            controller = perm.controller_id

            if perm.characteristics.is_creature():
                p = perm.characteristics.power or 0
                t = perm.characteristics.toughness or 0
                self.log(f"  - P{controller} plays **{name}** ({p}/{t})")
            elif not perm.characteristics.is_land():
                self.log(f"  - P{controller} plays **{name}**")

    def on_land_played(self, event: LandPlayedEvent):
        if hasattr(event, 'land') and event.land:
            name = event.land.characteristics.name if event.land.characteristics else "Land"
            pid = event.player_id
            self.log(f"  - P{pid} plays **{name}**")
        elif hasattr(event, 'player_id'):
            self.log(f"  - P{event.player_id} plays a land")

    def get_board(self, player_id):
        """Get creatures and lands for a player."""
        bf = self.game.zones.battlefield
        creatures = []
        lands = []

        for perm in bf.creatures(controller_id=player_id):
            name = perm.characteristics.name if perm.characteristics else "?"
            p = perm.characteristics.power if perm.characteristics else 0
            t = perm.characteristics.toughness if perm.characteristics else 0
            tapped = " (T)" if getattr(perm, 'is_tapped', False) else ""
            creatures.append(f"{name} {p}/{t}{tapped}")

        for perm in bf.lands(controller_id=player_id):
            name = perm.characteristics.name if perm.characteristics else "?"
            lands.append(name)

        return creatures, lands


def get_hand_contents(game, player_id):
    """Get card names in a player's hand."""
    hand = game.zones.hands[player_id]
    cards = hand.cards if hasattr(hand, 'cards') else []
    return [c.characteristics.name if c.characteristics else "?" for c in cards]


def run_playbyplay_game(deck_path: str, output_path: str):
    """Run a game and generate play-by-play markdown report."""

    # Header
    deck_name = Path(deck_path).stem
    lines = []
    lines.append(f"# Play-by-Play Report: {deck_name} Mirror Match\n")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"**Engine:** MTG V3\n")
    lines.append(f"**Format:** Mirror Match (same deck vs itself)\n")

    # Load deck
    lines.append("\n### Deck List\n")
    deck1 = load_deck(deck_path)
    deck2 = load_deck(deck_path)

    # Count cards
    card_counts = {}
    for card in deck1:
        name = card.characteristics.name if card.characteristics else "Unknown"
        card_counts[name] = card_counts.get(name, 0) + 1

    for name, count in sorted(card_counts.items()):
        lines.append(f"- {count}x {name}")

    lines.append(f"\n**Total:** {len(deck1)} cards\n")

    # Create game
    config = GameConfig(
        starting_life=20,
        starting_hand_size=7,
        max_turns=20,
        verbose=False
    )

    game = Game(player_ids=[1, 2], config=config)
    game.setup_game(deck1, deck2)

    # Attach AI
    for pid, player in game.players.items():
        player.ai = SimpleAI(player, game)

    # Attach event logger
    logger = PlayByPlayLogger(game)

    # Run game start to draw opening hands
    if hasattr(game, 'start_game'):
        game.start_game()

    # Opening hands
    lines.append("\n### Opening Hands\n")
    for pid in [1, 2]:
        hand_cards = get_hand_contents(game, pid)
        if hand_cards:
            lines.append(f"**Player {pid}:** {', '.join(hand_cards)}\n")
        else:
            # Try to get hand contents directly
            hand = game.zones.hands.get(pid)
            if hand and hasattr(hand, 'objects'):
                names = [c.characteristics.name if hasattr(c, 'characteristics') and c.characteristics else "?" for c in hand.objects]
                if names:
                    lines.append(f"**Player {pid}:** {', '.join(names)}\n")
                else:
                    lines.append(f"**Player {pid}:** (drawing at game start)\n")
            else:
                lines.append(f"**Player {pid}:** (drawing at game start)\n")

    # Game play section
    lines.append("\n### Game Play\n")

    # Run the game
    try:
        result = game.play_game()

        # Add the logged events
        lines.extend(logger.log_lines)

        # Game result
        lines.append("\n---\n")
        lines.append("\n### Game Result\n")

        if result.winner:
            lines.append(f"**Winner:** Player {result.winner.player_id}")
        else:
            lines.append("**Result:** Draw (turn limit)")

        lines.append(f"\n**Turns Played:** {result.turns_played}")
        lines.append(f"\n**Win Reason:** {result.reason}")

        for pid in [1, 2]:
            lines.append(f"\n**Player {pid} Final Life:** {result.final_life.get(pid, '?')}")

        # Final board state
        lines.append("\n\n### Final Board State\n")
        bf = game.zones.battlefield
        for pid in [1, 2]:
            creatures = []
            lands = []

            for perm in bf.creatures(controller_id=pid):
                name = perm.characteristics.name if perm.characteristics else "?"
                p = perm.characteristics.power if perm.characteristics else 0
                t = perm.characteristics.toughness if perm.characteristics else 0
                creatures.append(f"{name} {p}/{t}")

            for perm in bf.lands(controller_id=pid):
                name = perm.characteristics.name if perm.characteristics else "?"
                lands.append(name)

            lines.append(f"**Player {pid}:**")
            lines.append(f"  - Lands ({len(lands)}): {', '.join(lands[:8]) if lands else 'None'}")
            if len(lands) > 8:
                lines.append(f"    ...and {len(lands) - 8} more")
            lines.append(f"  - Creatures ({len(creatures)}): {', '.join(creatures) if creatures else 'None'}\n")

    except Exception as e:
        lines.append(f"\n**ERROR:** {type(e).__name__}: {e}\n")
        import traceback
        lines.append(f"```\n{traceback.format_exc()}\n```")

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Report written to: {output_path}")
    return result.winner.player_id if result.winner else None


if __name__ == "__main__":
    deck_dir = Path(r"C:\Users\Xx LilMan xX\Documents\Claude Docs\MTGO\decks\12.28.25")
    output_dir = Path(r"C:\Users\Xx LilMan xX\Documents\Claude Docs\MTGO")

    deck_path = deck_dir / "Engine_Test_Deck.txt"
    output_path = output_dir / "testdeck_1_report.md"

    winner = run_playbyplay_game(str(deck_path), str(output_path))
    print(f"Winner: Player {winner}")
