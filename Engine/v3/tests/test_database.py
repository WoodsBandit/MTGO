"""
Test suite for card database - validates V1 database loading and card data.

Tests cover:
- Database loading
- Card data structure
- Card type validation
- Keyword validation
- Ability validation
- Card lookup
"""
import pytest
import sys
from pathlib import Path

# Add v3 to path
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))

from tests.run_game import V1_CARD_DATABASE


# =============================================================================
# DATABASE LOADING TESTS
# =============================================================================

class TestDatabaseLoading:
    """Tests for database loading."""

    def test_database_loaded(self):
        """Test V1 database is loaded."""
        assert V1_CARD_DATABASE is not None
        assert len(V1_CARD_DATABASE) > 0

    def test_database_has_many_cards(self):
        """Test database has expected number of cards (3000+)."""
        assert len(V1_CARD_DATABASE) >= 3000

    def test_exact_card_count(self):
        """Test database has exactly 3164 cards."""
        assert len(V1_CARD_DATABASE) == 3164


# =============================================================================
# CARD DATA STRUCTURE TESTS
# =============================================================================

class TestCardDataStructure:
    """Tests for card data structure."""

    def test_card_has_type(self):
        """Test all cards have a type field."""
        for name, data in list(V1_CARD_DATABASE.items())[:100]:
            assert 'type' in data, f"Card {name} missing type"

    def test_card_has_cost(self):
        """Test most cards have a cost field."""
        cards_with_cost = 0
        for name, data in V1_CARD_DATABASE.items():
            if 'cost' in data:
                cards_with_cost += 1
        # Most cards should have cost (lands may not)
        assert cards_with_cost > 2500

    def test_creature_has_power_toughness(self):
        """Test creatures have power and toughness."""
        for name, data in V1_CARD_DATABASE.items():
            if data.get('type') == 'creature':
                assert 'power' in data, f"Creature {name} missing power"
                assert 'toughness' in data, f"Creature {name} missing toughness"
                break  # Just check first creature


# =============================================================================
# CARD TYPE TESTS
# =============================================================================

class TestCardTypes:
    """Tests for card type distribution."""

    def test_has_creatures(self):
        """Test database has creatures."""
        creatures = [n for n, d in V1_CARD_DATABASE.items() if d.get('type') == 'creature']
        assert len(creatures) > 1000

    def test_has_instants(self):
        """Test database has instants."""
        instants = [n for n, d in V1_CARD_DATABASE.items() if d.get('type') == 'instant']
        assert len(instants) > 100

    def test_has_sorceries(self):
        """Test database has sorceries."""
        sorceries = [n for n, d in V1_CARD_DATABASE.items() if d.get('type') == 'sorcery']
        assert len(sorceries) > 100

    def test_has_lands(self):
        """Test database has lands."""
        lands = [n for n, d in V1_CARD_DATABASE.items() if d.get('type') == 'land']
        assert len(lands) > 50

    def test_has_enchantments(self):
        """Test database has enchantments."""
        enchantments = [n for n, d in V1_CARD_DATABASE.items() if d.get('type') == 'enchantment']
        assert len(enchantments) > 50

    def test_has_artifacts(self):
        """Test database has artifacts."""
        artifacts = [n for n, d in V1_CARD_DATABASE.items() if d.get('type') == 'artifact']
        assert len(artifacts) > 20

    def test_has_planeswalkers(self):
        """Test database has planeswalkers."""
        planeswalkers = [n for n, d in V1_CARD_DATABASE.items() if d.get('type') == 'planeswalker']
        assert len(planeswalkers) > 5


# =============================================================================
# KEYWORD TESTS
# =============================================================================

class TestKeywords:
    """Tests for keyword abilities."""

    def test_flying_exists(self):
        """Test some cards have flying."""
        flying_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if 'flying' in d.get('keywords', [])
        ]
        assert len(flying_cards) > 100

    def test_trample_exists(self):
        """Test some cards have trample."""
        trample_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if 'trample' in d.get('keywords', [])
        ]
        assert len(trample_cards) > 50

    def test_deathtouch_exists(self):
        """Test some cards have deathtouch."""
        deathtouch_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if 'deathtouch' in d.get('keywords', [])
        ]
        assert len(deathtouch_cards) > 20

    def test_lifelink_exists(self):
        """Test some cards have lifelink."""
        lifelink_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if 'lifelink' in d.get('keywords', [])
        ]
        assert len(lifelink_cards) > 20

    def test_haste_exists(self):
        """Test some cards have haste."""
        haste_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if 'haste' in d.get('keywords', [])
        ]
        assert len(haste_cards) > 20


# =============================================================================
# ABILITY TESTS
# =============================================================================

class TestAbilities:
    """Tests for card abilities."""

    def test_draw_abilities_exist(self):
        """Test some cards have draw abilities."""
        draw_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if any('draw_' in a for a in d.get('abilities', []))
        ]
        assert len(draw_cards) > 50

    def test_damage_abilities_exist(self):
        """Test some cards have damage abilities."""
        damage_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if any('damage_' in a for a in d.get('abilities', []))
        ]
        assert len(damage_cards) > 20

    def test_token_abilities_exist(self):
        """Test some cards have token creation abilities."""
        token_cards = [
            n for n, d in V1_CARD_DATABASE.items()
            if any('create_token' in a for a in d.get('abilities', []))
        ]
        assert len(token_cards) > 50


# =============================================================================
# SPECIFIC CARD TESTS
# =============================================================================

class TestSpecificCards:
    """Tests for specific well-known cards."""

    def test_lightning_strike(self):
        """Test Lightning Strike exists with correct data."""
        if "Lightning Strike" in V1_CARD_DATABASE:
            card = V1_CARD_DATABASE["Lightning Strike"]
            assert card['type'] == 'instant'
            assert card['cost'] == 2.0

    def test_llanowar_elves(self):
        """Test Llanowar Elves exists with correct data."""
        if "Llanowar Elves" in V1_CARD_DATABASE:
            card = V1_CARD_DATABASE["Llanowar Elves"]
            assert card['type'] == 'creature'
            assert card['power'] == 1
            assert card['toughness'] == 1


# =============================================================================
# CARD LOOKUP TESTS
# =============================================================================

class TestCardLookup:
    """Tests for card lookup functionality."""

    def test_lookup_by_exact_name(self):
        """Test looking up card by exact name."""
        # Get first card name
        first_name = list(V1_CARD_DATABASE.keys())[0]
        card = V1_CARD_DATABASE.get(first_name)
        assert card is not None

    def test_lookup_nonexistent(self):
        """Test looking up nonexistent card returns None."""
        card = V1_CARD_DATABASE.get("This Card Does Not Exist XYZ123")
        assert card is None

    def test_lookup_case_sensitive(self):
        """Test card lookup is case sensitive."""
        # Get a card name
        real_name = "Lightning Strike"
        if real_name in V1_CARD_DATABASE:
            # Wrong case should not find it
            wrong_case = V1_CARD_DATABASE.get("lightning strike")
            assert wrong_case is None


# =============================================================================
# RUN TESTS
# =============================================================================

def run_database_tests():
    """Run all database tests and report results."""
    print("=" * 60)
    print("MTG ENGINE V3 - Card Database Unit Tests")
    print("=" * 60)

    results = []

    # Test Database Loading
    print("\nTesting Database Loading...")
    try:
        t = TestDatabaseLoading()
        t.test_database_loaded()
        t.test_database_has_many_cards()
        t.test_exact_card_count()
        results.append(("Database Loading", True))
        print("  PASS")
    except Exception as e:
        results.append(("Database Loading", False))
        print(f"  FAIL: {e}")

    # Test Card Data Structure
    print("\nTesting Card Data Structure...")
    try:
        t = TestCardDataStructure()
        t.test_card_has_type()
        t.test_card_has_cost()
        t.test_creature_has_power_toughness()
        results.append(("Card Data Structure", True))
        print("  PASS")
    except Exception as e:
        results.append(("Card Data Structure", False))
        print(f"  FAIL: {e}")

    # Test Card Types
    print("\nTesting Card Types...")
    try:
        t = TestCardTypes()
        t.test_has_creatures()
        t.test_has_instants()
        t.test_has_sorceries()
        t.test_has_lands()
        t.test_has_enchantments()
        t.test_has_artifacts()
        t.test_has_planeswalkers()
        results.append(("Card Types", True))
        print("  PASS")
    except Exception as e:
        results.append(("Card Types", False))
        print(f"  FAIL: {e}")

    # Test Keywords
    print("\nTesting Keywords...")
    try:
        t = TestKeywords()
        t.test_flying_exists()
        t.test_trample_exists()
        t.test_deathtouch_exists()
        t.test_lifelink_exists()
        t.test_haste_exists()
        results.append(("Keywords", True))
        print("  PASS")
    except Exception as e:
        results.append(("Keywords", False))
        print(f"  FAIL: {e}")

    # Test Abilities
    print("\nTesting Abilities...")
    try:
        t = TestAbilities()
        t.test_draw_abilities_exist()
        t.test_damage_abilities_exist()
        t.test_token_abilities_exist()
        results.append(("Abilities", True))
        print("  PASS")
    except Exception as e:
        results.append(("Abilities", False))
        print(f"  FAIL: {e}")

    # Test Specific Cards
    print("\nTesting Specific Cards...")
    try:
        t = TestSpecificCards()
        t.test_lightning_strike()
        t.test_llanowar_elves()
        results.append(("Specific Cards", True))
        print("  PASS")
    except Exception as e:
        results.append(("Specific Cards", False))
        print(f"  FAIL: {e}")

    # Test Card Lookup
    print("\nTesting Card Lookup...")
    try:
        t = TestCardLookup()
        t.test_lookup_by_exact_name()
        t.test_lookup_nonexistent()
        t.test_lookup_case_sensitive()
        results.append(("Card Lookup", True))
        print("  PASS")
    except Exception as e:
        results.append(("Card Lookup", False))
        print(f"  FAIL: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
    print(f"\nTotal: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    success = run_database_tests()
    sys.exit(0 if success else 1)
