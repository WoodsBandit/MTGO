"""
Test suite for mana system - validates mana cost parsing, pools, and payment.

Tests cover:
- Mana cost parsing (CR 107.4)
- Mana pool management
- Mana payment validation
- Color requirements
- Generic mana handling
"""
import pytest
import sys
from pathlib import Path

# Add v3 to path
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))

from engine.mana import ManaCost, ManaSymbol, ManaPool
from engine.types import Color


# =============================================================================
# MANA COST PARSING TESTS
# =============================================================================

class TestManaCostParsing:
    """Tests for parsing mana cost strings."""

    def test_parse_colorless_only(self):
        """Test parsing pure colorless costs like {3}."""
        cost = ManaCost.parse("{3}")
        assert cost.cmc == 3

    def test_parse_single_color(self):
        """Test parsing single color costs like {U}."""
        cost = ManaCost.parse("{U}")
        assert cost.cmc == 1

    def test_parse_multicolor(self):
        """Test parsing multicolor costs like {2}{U}{U}."""
        cost = ManaCost.parse("{2}{U}{U}")
        assert cost.cmc == 4

    def test_parse_all_colors(self):
        """Test parsing costs with all five colors."""
        cost = ManaCost.parse("{W}{U}{B}{R}{G}")
        assert cost.cmc == 5

    def test_parse_zero_cost(self):
        """Test parsing zero mana cost {0}."""
        cost = ManaCost.parse("{0}")
        assert cost.cmc == 0

    def test_parse_empty_string(self):
        """Test parsing empty string (free spell / land)."""
        cost = ManaCost.parse("")
        assert cost.cmc == 0

    def test_parse_complex_cost(self):
        """Test parsing complex costs like {3}{W}{W}{U}."""
        cost = ManaCost.parse("{3}{W}{W}{U}")
        assert cost.cmc == 6

    def test_parse_high_cmc(self):
        """Test parsing high CMC costs like {10}."""
        cost = ManaCost.parse("{10}")
        assert cost.cmc == 10


# =============================================================================
# MANA POOL TESTS
# =============================================================================

class TestManaPool:
    """Tests for mana pool management."""

    def test_empty_pool(self):
        """Test newly created pool is empty."""
        pool = ManaPool()
        assert pool.total() == 0

    def test_add_single_mana(self):
        """Test adding a single mana."""
        pool = ManaPool()
        pool.add(Color.BLUE, 1)
        assert pool.total() == 1
        assert pool.get_amount(Color.BLUE) == 1

    def test_add_multiple_mana(self):
        """Test adding multiple mana of same color."""
        pool = ManaPool()
        pool.add(Color.RED, 3)
        assert pool.total() == 3
        assert pool.get_amount(Color.RED) == 3

    def test_add_different_colors(self):
        """Test adding mana of different colors."""
        pool = ManaPool()
        pool.add(Color.WHITE, 2)
        pool.add(Color.GREEN, 3)
        assert pool.total() == 5
        assert pool.get_amount(Color.WHITE) == 2
        assert pool.get_amount(Color.GREEN) == 3

    def test_colorless_mana(self):
        """Test adding colorless mana."""
        pool = ManaPool()
        pool.add(Color.COLORLESS, 4)
        assert pool.total() == 4
        assert pool.get_amount(Color.COLORLESS) == 4


# =============================================================================
# MANA PAYMENT TESTS
# =============================================================================

class TestManaPayment:
    """Tests for mana cost payment validation."""

    def test_can_pay_exact(self):
        """Test paying exact mana cost."""
        pool = ManaPool()
        pool.add(Color.BLUE, 4)
        cost = ManaCost.parse("{2}{U}{U}")
        assert pool.can_pay(cost) == True

    def test_can_pay_with_extra(self):
        """Test paying when pool has extra mana."""
        pool = ManaPool()
        pool.add(Color.RED, 5)
        cost = ManaCost.parse("{R}{R}")
        assert pool.can_pay(cost) == True

    def test_cannot_pay_missing_color(self):
        """Test cannot pay without required color."""
        pool = ManaPool()
        pool.add(Color.RED, 5)
        cost = ManaCost.parse("{U}")
        assert pool.can_pay(cost) == False

    def test_cannot_pay_insufficient(self):
        """Test cannot pay with insufficient mana."""
        pool = ManaPool()
        pool.add(Color.WHITE, 1)
        cost = ManaCost.parse("{2}{W}{W}")
        assert pool.can_pay(cost) == False

    def test_generic_paid_by_any_color(self):
        """Test generic mana can be paid by any color."""
        pool = ManaPool()
        pool.add(Color.GREEN, 3)
        cost = ManaCost.parse("{3}")
        assert pool.can_pay(cost) == True

    def test_pay_multicolor(self):
        """Test paying multicolor cost."""
        pool = ManaPool()
        pool.add(Color.WHITE, 2)
        pool.add(Color.BLUE, 2)
        cost = ManaCost.parse("{1}{W}{U}")
        assert pool.can_pay(cost) == True


# =============================================================================
# MANA SYMBOL TESTS
# =============================================================================

class TestManaSymbol:
    """Tests for individual mana symbols."""

    def test_color_symbols(self):
        """Test color symbol identification."""
        # Test that symbols can be created from strings
        assert ManaSymbol.from_string("W") is not None
        assert ManaSymbol.from_string("U") is not None
        assert ManaSymbol.from_string("B") is not None
        assert ManaSymbol.from_string("R") is not None
        assert ManaSymbol.from_string("G") is not None

    def test_generic_symbol(self):
        """Test generic mana symbol."""
        symbol = ManaSymbol.from_string("3")
        assert symbol is not None


# =============================================================================
# RUN TESTS
# =============================================================================

def run_mana_tests():
    """Run all mana tests and report results."""
    print("=" * 60)
    print("MTG ENGINE V3 - Mana System Unit Tests")
    print("=" * 60)

    results = []

    # Test cost parsing
    print("\nTesting Mana Cost Parsing...")
    try:
        t = TestManaCostParsing()
        t.test_parse_colorless_only()
        t.test_parse_single_color()
        t.test_parse_multicolor()
        t.test_parse_all_colors()
        t.test_parse_zero_cost()
        t.test_parse_empty_string()
        t.test_parse_complex_cost()
        t.test_parse_high_cmc()
        results.append(("Mana Cost Parsing", True))
        print("  PASS")
    except Exception as e:
        results.append(("Mana Cost Parsing", False))
        print(f"  FAIL: {e}")

    # Test mana pool
    print("\nTesting Mana Pool...")
    try:
        t = TestManaPool()
        t.test_empty_pool()
        t.test_add_single_mana()
        t.test_add_multiple_mana()
        t.test_add_different_colors()
        t.test_colorless_mana()
        results.append(("Mana Pool", True))
        print("  PASS")
    except Exception as e:
        results.append(("Mana Pool", False))
        print(f"  FAIL: {e}")

    # Test mana payment
    print("\nTesting Mana Payment...")
    try:
        t = TestManaPayment()
        t.test_can_pay_exact()
        t.test_can_pay_with_extra()
        t.test_cannot_pay_missing_color()
        t.test_cannot_pay_insufficient()
        t.test_generic_paid_by_any_color()
        t.test_pay_multicolor()
        results.append(("Mana Payment", True))
        print("  PASS")
    except Exception as e:
        results.append(("Mana Payment", False))
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
    success = run_mana_tests()
    sys.exit(0 if success else 1)
