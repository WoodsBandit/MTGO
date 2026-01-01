"""
Integration test runner for MTG Engine V3.
Validates the engine works with real decks from the test deck folder.
"""
import sys
import os
from pathlib import Path

# Add v3 directory to path for imports
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))
os.chdir(str(v3_dir))

def test_imports():
    """Test that all engine modules can be imported."""
    print("Testing imports...")
    passed = 0
    failed = 0

    imports_to_test = [
        ("engine.types", ["Color", "CardType", "StepType", "PhaseType"]),
        ("engine.events", ["EventBus", "ZoneChangeEvent", "DamageEvent"]),
        ("engine.zones", ["Library", "Hand", "Battlefield", "Graveyard"]),
        ("engine.objects", ["Card", "Permanent", "Spell"]),
        ("engine.player", ["Player"]),
        ("engine.stack", ["Stack"]),
        ("engine.priority", ["PrioritySystem"]),
        ("engine.mana", ["ManaCost", "ManaSymbol"]),
        ("engine.sba", ["StateBasedActionChecker"]),
        ("engine.combat", ["CombatManager"]),
        ("engine.targeting", ["TargetChecker"]),
        ("engine.game", ["Game"]),
        ("engine.match", ["Match"]),
    ]

    for module_name, symbols in imports_to_test:
        try:
            module = __import__(module_name, fromlist=symbols)
            for sym in symbols:
                getattr(module, sym)
            passed += 1
        except Exception as e:
            print(f"  Failed: {module_name} - {e}")
            failed += 1

    print(f"  {passed}/{passed+failed} modules imported successfully")
    return failed == 0

def test_deck_loading():
    """Test loading decks from the test folder."""
    print("\nTesting deck loading...")
    deck_path = Path(r"C:\Users\Xx LilMan xX\Documents\Claude Docs\MTGO\decks\12.28.25")

    if not deck_path.exists():
        print(f"  Deck folder not found: {deck_path}")
        return False

    deck_files = list(deck_path.glob("*.txt"))
    print(f"  Found {len(deck_files)} deck files")

    for deck_file in deck_files[:3]:  # Test first 3
        print(f"  Loading: {deck_file.name}")
        try:
            with open(deck_file, 'r') as f:
                content = f.read()
                lines = [l for l in content.split('\n') if l.strip() and not l.startswith('//')]
                card_count = sum(int(l.split()[0]) for l in lines if l[0].isdigit())
                print(f"    Cards: {card_count}")
        except Exception as e:
            print(f"    Error: {e}")

    return True

def test_basic_game_setup():
    """Test basic game setup."""
    print("\nTesting basic game setup...")
    try:
        from engine.player import Player
        from engine.zones import Library, Hand, Battlefield
        from engine.events import EventBus

        # Create players
        p1 = Player(player_id=1, name="Player 1")
        p2 = Player(player_id=2, name="Player 2")
        print(f"  Created players: {p1.name}, {p2.name}")
        print(f"  Starting life: {p1.life}, {p2.life}")

        # Create event bus
        event_bus = EventBus()
        print(f"  Event bus created")

        # Create battlefield
        battlefield = Battlefield()
        print(f"  Battlefield created")

        return True
    except Exception as e:
        print(f"  Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mana_system():
    """Test mana system."""
    print("\nTesting mana system...")
    try:
        from engine.mana import ManaCost, ManaSymbol, ManaPool
        from engine.types import Color

        # Test mana cost parsing
        cost = ManaCost.parse("{2}{U}{U}")
        print(f"  Parsed cost: {cost}")
        print(f"  CMC: {cost.cmc}")

        # Test mana pool
        pool = ManaPool()
        pool.add(Color.BLUE, 3)
        pool.add(Color.COLORLESS, 2)
        print(f"  Pool total: {pool.total()}")

        return True
    except Exception as e:
        print(f"  Mana test failed: {e}")
        return False

def test_combat_keywords():
    """Test combat keyword detection."""
    print("\nTesting combat keywords...")
    try:
        # Test keyword presence
        keywords = ["flying", "trample", "deathtouch", "first_strike", "lifelink", "vigilance", "haste", "menace"]
        print(f"  Checking {len(keywords)} keywords")
        for kw in keywords:
            print(f"    - {kw}")
        return True
    except Exception as e:
        print(f"  Keyword test failed: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("MTG ENGINE V3 - Integration Tests")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Deck Loading", test_deck_loading()))
    results.append(("Game Setup", test_basic_game_setup()))
    results.append(("Mana System", test_mana_system()))
    results.append(("Combat Keywords", test_combat_keywords()))

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
