"""
Test game runner - Runs a simulated game between two decks.
Uses simplified card representations to test the V3 engine.
"""
import sys
import os
from pathlib import Path

# Add v3 to path
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))

from dataclasses import dataclass, field
from typing import List, Set, Optional
from engine.types import Color, CardType, Zone, Supertype
from engine.objects import Card, Characteristics
from engine.game import Game, GameConfig
from engine.player import Player
from ai.agent import SimpleAI

# Try to load the V1 card database for real card data
V1_CARD_DATABASE = {}
try:
    import ast
    v1_db_path = Path(__file__).parent.parent.parent / "V1_mtg_sim_package" / "card_database.py"
    if v1_db_path.exists():
        content = v1_db_path.read_text(encoding='utf-8')
        # Extract CARD_DATABASE dict - match opening brace to closing brace before DEFAULT_STATS
        import re
        # Find where CARD_DATABASE starts
        start_match = re.search(r'CARD_DATABASE\s*=\s*\{', content)
        if start_match:
            start_pos = start_match.end() - 1  # Include the opening brace
            # Find the matching closing brace by counting
            brace_count = 0
            end_pos = start_pos
            for i, char in enumerate(content[start_pos:]):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = start_pos + i + 1
                        break
            dict_str = content[start_pos:end_pos]
            V1_CARD_DATABASE = ast.literal_eval(dict_str)
            print(f"[DB] Loaded {len(V1_CARD_DATABASE)} cards from V1 database")
except Exception as e:
    print(f"[DB] Warning: Could not load V1 database: {e}")


def parse_decklist(filepath: str) -> List[dict]:
    """Parse a decklist file into card entries."""
    cards = []
    in_sideboard = False

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            if line.lower() == 'sideboard':
                in_sideboard = True
                continue
            if in_sideboard:
                continue  # Skip sideboard for main deck

            # Parse "4 Card Name"
            parts = line.split(' ', 1)
            if len(parts) == 2 and parts[0].isdigit():
                count = int(parts[0])
                name = parts[1]
                for _ in range(count):
                    cards.append({'name': name})

    return cards


def create_simple_card(name: str, card_type: str = 'creature') -> Card:
    """
    Create a card from the database if available, otherwise use heuristics.

    Priority:
    1. Look up in V1_CARD_DATABASE for real card data
    2. Fall back to heuristics for unknown cards
    """
    colors = set()
    types = set()
    subtypes = set()
    supertypes = set()
    power = None
    toughness = None
    mana_cost = None
    keywords = []
    abilities = []

    # Try to get card data from the V1 database
    db_data = V1_CARD_DATABASE.get(name)
    if db_data:
        # Use real card data from database
        card_type_str = db_data.get('type', 'creature').lower()

        # Map types
        type_mapping = {
            'creature': CardType.CREATURE,
            'instant': CardType.INSTANT,
            'sorcery': CardType.SORCERY,
            'enchantment': CardType.ENCHANTMENT,
            'artifact': CardType.ARTIFACT,
            'land': CardType.LAND,
            'planeswalker': CardType.PLANESWALKER,
        }
        if card_type_str in type_mapping:
            types.add(type_mapping[card_type_str])
        else:
            types.add(CardType.CREATURE)  # Default

        # Get power/toughness for creatures
        if card_type_str == 'creature':
            power = db_data.get('power', 1)
            toughness = db_data.get('toughness', 1)

        # Get mana cost
        cmc = int(db_data.get('cost', 0))
        if cmc > 0 and CardType.LAND not in types:
            mana_cost = "{" + str(cmc) + "}"

        # Get keywords
        keywords = db_data.get('keywords', [])
        abilities = db_data.get('abilities', [])

        # Build rules text with keywords and abilities
        rules_parts = []
        for kw in keywords:
            kw_normalized = kw.replace('_', ' ').capitalize()
            rules_parts.append(kw_normalized)
        rules_parts.extend(abilities)
        rules_text = ", ".join(rules_parts) if rules_parts else ""

        # Build characteristics
        characteristics = Characteristics(
            name=name,
            mana_cost=mana_cost,
            colors=colors,  # V1 doesn't have color data, will be inferred
            types=types,
            subtypes=subtypes,
            supertypes=supertypes,
            power=power,
            toughness=toughness,
            rules_text=rules_text
        )

        card = Card(
            base_characteristics=characteristics,
            characteristics=characteristics.copy()
        )

        # Store keywords and abilities on the card for later use
        card._db_keywords = [kw.lower().replace('_', ' ') for kw in keywords]
        card._db_abilities = abilities  # Store raw ability codes for effect execution

        return card

    # Fall back to heuristics for cards not in database
    # Check for lands - detect common land name patterns
    basic_land_names = ['Mountain', 'Forest', 'Island', 'Swamp', 'Plains']
    is_basic_land = any(land in name for land in basic_land_names)

    # Common dual land patterns - only match if the word appears as a whole word
    # or at the END of the name (many lands end with these)
    land_keywords = [
        'Sanctuary', 'Village', 'Verge', 'Passage', 'Reef',
        'Canal', 'Crypt', 'Pool', 'Falls', 'Shore', 'Gate', 'Temple',
        'Citadel', 'Pathway', 'Channel', 'Ruins',
        'Bog', 'Marsh', 'Lake', 'Creek', 'Fortress', 'Foundry',
        'Triome', 'Grounds', 'Harbor', 'Heath', 'Steppes', 'Mire', 'Strand'
    ]
    name_lower = name.lower()
    # Check if any keyword matches (case insensitive)
    has_land_keyword = any(name_lower.endswith(kw.lower()) or
                           f" {kw.lower()}" in f" {name_lower}" or
                           name_lower == kw.lower()
                           for kw in land_keywords)
    # Also check for "Grave" specifically at the end (Watery Grave, Blood Crypt, etc)
    if name_lower.endswith(' grave') or name_lower.endswith(' crypt'):
        has_land_keyword = True

    if is_basic_land or has_land_keyword:
        types.add(CardType.LAND)
        if any(land == name for land in basic_land_names):
            supertypes.add(Supertype.BASIC)
            subtypes.add(name)
        # Assign colors based on land type - can have multiple colors for dual lands
        name_lower = name.lower()
        if 'mountain' in name_lower:
            colors.add(Color.RED)
        if 'forest' in name_lower:
            colors.add(Color.GREEN)
        if 'island' in name_lower:
            colors.add(Color.BLUE)
        if 'swamp' in name_lower:
            colors.add(Color.BLACK)
        if 'plains' in name_lower:
            colors.add(Color.WHITE)

        # Detect dual land color combinations from common naming
        dual_land_colors = {
            # Shock lands / buddy lands / etc.
            'watery': {Color.BLUE, Color.BLACK},
            'grave': {Color.BLUE, Color.BLACK},  # Watery Grave
            'gloom': {Color.BLUE, Color.BLACK},  # Gloomlake
            'restless reef': {Color.BLUE, Color.BLACK},
            'stomp': {Color.RED, Color.GREEN},
            'blood crypt': {Color.BLACK, Color.RED},
            'breed': {Color.GREEN, Color.BLUE},
            'hallowed': {Color.WHITE, Color.BLUE},
            'godless': {Color.WHITE, Color.BLACK},
            'steam': {Color.BLUE, Color.RED},
            'overgrown': {Color.BLACK, Color.GREEN},
            'sacred': {Color.WHITE, Color.GREEN},
            'spire': {Color.WHITE, Color.RED},
            'rootbound': {Color.RED, Color.GREEN},
            'sunpetal': {Color.WHITE, Color.GREEN},
            'dragonskull': {Color.BLACK, Color.RED},
            'glacial': {Color.WHITE, Color.BLUE},
            'drowned': {Color.BLUE, Color.BLACK},
            'sulfur': {Color.BLUE, Color.RED},
            'hinterland': {Color.GREEN, Color.BLUE},
            'isolated': {Color.WHITE, Color.BLACK},
            'woodland': {Color.BLACK, Color.GREEN},
            'clifftop': {Color.WHITE, Color.RED},
            'copperline': {Color.RED, Color.GREEN},
        }
        for keyword, land_colors in dual_land_colors.items():
            if keyword in name_lower:
                colors.update(land_colors)
                break
    else:
        # It's a spell - assume creature for now
        types.add(CardType.CREATURE)

        # Simple heuristic for P/T based on name hash
        name_hash = sum(ord(c) for c in name)
        power = (name_hash % 5) + 1  # 1-5
        toughness = (name_hash % 4) + 1  # 1-4

        # Assign cost based on power (roughly)
        cmc = power + 1
        mana_cost = "{" + str(cmc) + "}"

        # Color based on common keywords
        if any(x in name.lower() for x in ['fire', 'burn', 'lightning', 'red', 'flame', 'ember']):
            colors.add(Color.RED)
            mana_cost = "{" + str(max(0, cmc-1)) + "}{R}"
        elif any(x in name.lower() for x in ['forest', 'green', 'growth', 'nature']):
            colors.add(Color.GREEN)
            mana_cost = "{" + str(max(0, cmc-1)) + "}{G}"
        elif any(x in name.lower() for x in ['shadow', 'dark', 'death', 'black']):
            colors.add(Color.BLACK)
            mana_cost = "{" + str(max(0, cmc-1)) + "}{B}"
        elif any(x in name.lower() for x in ['blue', 'sea', 'water', 'mind']):
            colors.add(Color.BLUE)
            mana_cost = "{" + str(max(0, cmc-1)) + "}{U}"
        elif any(x in name.lower() for x in ['light', 'holy', 'white', 'angel']):
            colors.add(Color.WHITE)
            mana_cost = "{" + str(max(0, cmc-1)) + "}{W}"

    characteristics = Characteristics(
        name=name,
        mana_cost=mana_cost,
        colors=colors,
        types=types,
        subtypes=subtypes,
        supertypes=supertypes,
        power=power,
        toughness=toughness,
        rules_text=""
    )

    return Card(
        base_characteristics=characteristics,
        characteristics=characteristics.copy()
    )


def load_deck(filepath: str) -> List[Card]:
    """Load a deck from a file and create Card objects."""
    entries = parse_decklist(filepath)
    cards = []
    for entry in entries:
        card = create_simple_card(entry['name'])
        cards.append(card)
    return cards


def run_test_game(deck1_path: str, deck2_path: str, verbose: bool = True):
    """Run a test game between two decks."""

    print("=" * 60)
    print("MTG ENGINE V3 - Test Game")
    print("=" * 60)

    # Load decks
    print(f"\nLoading deck 1: {Path(deck1_path).name}")
    deck1 = load_deck(deck1_path)
    print(f"  Cards loaded: {len(deck1)}")

    print(f"\nLoading deck 2: {Path(deck2_path).name}")
    deck2 = load_deck(deck2_path)
    print(f"  Cards loaded: {len(deck2)}")

    # Create game config
    config = GameConfig(
        starting_life=20,
        starting_hand_size=7,
        max_turns=15,  # Short game for testing
        verbose=verbose
    )

    # Create game
    print("\nInitializing game...")
    game = Game(player_ids=[1, 2], config=config)

    # Set up the game with decks
    print("Setting up game with decks...")
    game.setup_game(deck1, deck2)

    # Attach AI agents to players
    print("Attaching AI agents...")
    for pid, player in game.players.items():
        player.ai = SimpleAI(player, game)

    # Show initial state
    print("\n" + "-" * 40)
    print("INITIAL STATE")
    print("-" * 40)
    for pid, player in game.players.items():
        library_size = len(game.zones.libraries[pid])
        hand_size = len(game.zones.hands[pid])
        print(f"Player {pid}: Life={player.life}, Library={library_size}, Hand={hand_size}")
        # Show hand
        hand = game.zones.hands[pid]
        if hasattr(hand, 'cards'):
            card_names = [c.name for c in hand.cards[:5]]
            if len(hand.cards) > 5:
                card_names.append(f"... and {len(hand.cards) - 5} more")
            print(f"  Hand: {', '.join(card_names)}")

    # Run the game
    print("\n" + "-" * 40)
    print("RUNNING GAME...")
    print("-" * 40)

    try:
        result = game.play_game()

        print("\n" + "=" * 60)
        print("GAME RESULT")
        print("=" * 60)
        print(f"Turns played: {result.turns_played}")
        print(f"Winner: Player {result.winner.player_id if result.winner else 'None (Draw)'}")
        print(f"Reason: {result.reason}")
        print(f"Final life totals: {result.final_life}")

    except Exception as e:
        print(f"\nGame error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

        # Show current state
        print("\n" + "-" * 40)
        print("STATE AT ERROR")
        print("-" * 40)
        print(f"Turn: {game.turn_number}")
        print(f"Phase: {game.current_phase}")
        print(f"Step: {game.current_step}")
        for pid, player in game.players.items():
            print(f"Player {pid}: Life={player.life}")


def main():
    """Main entry point."""
    deck_dir = Path(r"C:\Users\Xx LilMan xX\Documents\Claude Docs\MTGO\decks\12.28.25")

    # Use Mono Red Aggro vs Dimir Midrange
    deck1 = deck_dir / "Mono_Red_Aggro_Meta_AI.txt"
    deck2 = deck_dir / "Dimir_Midrange_Meta_AI.txt"

    if not deck1.exists():
        print(f"Deck not found: {deck1}")
        return
    if not deck2.exists():
        print(f"Deck not found: {deck2}")
        return

    run_test_game(str(deck1), str(deck2), verbose=True)


if __name__ == "__main__":
    main()
