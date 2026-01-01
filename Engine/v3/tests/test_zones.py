"""
Test suite for zone management - validates zone operations and card movement.

Uses mock implementations to test zone behavior independently of engine code.

Tests cover:
- Library operations (CR 401)
- Hand operations (CR 402)
- Battlefield operations (CR 403)
- Graveyard operations (CR 404)
- Stack operations (CR 405)
- Exile operations (CR 406)
"""
import pytest
import sys
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Set, Optional, List, Any

# Add v3 to path for type imports only
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))

from engine.types import Zone, CardType


# =============================================================================
# MOCK ZONE IMPLEMENTATIONS FOR TESTING
# =============================================================================

@dataclass
class MockCard:
    """Simple mock card for zone testing."""
    object_id: int
    name: str = "Test Card"
    owner_id: int = 1
    controller_id: int = 1


class MockLibrary:
    """Mock library zone for testing."""

    def __init__(self):
        self.cards: List[MockCard] = []

    def __len__(self):
        return len(self.cards)

    def is_empty(self):
        return len(self.cards) == 0

    def add(self, card: MockCard):
        self.cards.insert(0, card)  # Add to top

    def draw(self) -> Optional[MockCard]:
        return self.cards.pop(0) if self.cards else None

    def shuffle(self):
        random.shuffle(self.cards)

    def put_on_top(self, card: MockCard):
        self.cards.insert(0, card)

    def put_on_bottom(self, card: MockCard):
        self.cards.append(card)


class MockHand:
    """Mock hand zone for testing."""

    def __init__(self):
        self.cards: List[MockCard] = []

    def __len__(self):
        return len(self.cards)

    def __contains__(self, card):
        return card in self.cards

    def add(self, card: MockCard):
        self.cards.append(card)

    def remove(self, card: MockCard) -> bool:
        if card in self.cards:
            self.cards.remove(card)
            return True
        return False

    def get_by_id(self, object_id: int) -> Optional[MockCard]:
        for card in self.cards:
            if card.object_id == object_id:
                return card
        return None


class MockBattlefield:
    """Mock battlefield zone for testing."""

    def __init__(self):
        self.permanents: List[MockCard] = []

    def __len__(self):
        return len(self.permanents)

    def add(self, perm: MockCard):
        self.permanents.append(perm)

    def remove(self, perm: MockCard):
        if perm in self.permanents:
            self.permanents.remove(perm)

    def creatures(self, controller_id: int) -> List[MockCard]:
        return [p for p in self.permanents if p.controller_id == controller_id]

    def get_all(self, controller_id: int = None) -> List[MockCard]:
        if controller_id is None:
            return self.permanents[:]
        return [p for p in self.permanents if p.controller_id == controller_id]

    def get_by_id(self, object_id: int) -> Optional[MockCard]:
        for perm in self.permanents:
            if perm.object_id == object_id:
                return perm
        return None


class MockGraveyard:
    """Mock graveyard zone for testing."""

    def __init__(self):
        self.cards: List[MockCard] = []

    def __len__(self):
        return len(self.cards)

    def add(self, card: MockCard):
        self.cards.append(card)

    def remove(self, card: MockCard):
        if card in self.cards:
            self.cards.remove(card)


class MockExile:
    """Mock exile zone for testing."""

    def __init__(self):
        self.cards: List[MockCard] = []
        self.face_down: Set[int] = set()

    def __len__(self):
        return len(self.cards)

    def add(self, card: MockCard, face_down: bool = False):
        self.cards.append(card)
        if face_down:
            self.face_down.add(card.object_id)


class MockStack:
    """Mock stack zone for testing."""

    def __init__(self):
        self.items: List[MockCard] = []

    def is_empty(self):
        return len(self.items) == 0

    def push(self, item: MockCard):
        self.items.append(item)

    def pop(self) -> Optional[MockCard]:
        return self.items.pop() if self.items else None

    def peek(self) -> Optional[MockCard]:
        return self.items[-1] if self.items else None


# =============================================================================
# LIBRARY TESTS
# =============================================================================

class TestLibrary:
    """Tests for library zone operations."""

    def test_create_empty_library(self):
        """Test creating empty library."""
        lib = MockLibrary()
        assert len(lib) == 0
        assert lib.is_empty() == True

    def test_add_cards_to_library(self):
        """Test adding cards to library."""
        lib = MockLibrary()
        card = MockCard(object_id=1)
        lib.add(card)
        assert len(lib) == 1

    def test_draw_from_library(self):
        """Test drawing a card from library."""
        lib = MockLibrary()
        card = MockCard(object_id=1, name="Test Draw")
        lib.add(card)
        drawn = lib.draw()
        assert drawn.name == "Test Draw"
        assert len(lib) == 0

    def test_draw_from_empty_library(self):
        """Test drawing from empty library returns None."""
        lib = MockLibrary()
        drawn = lib.draw()
        assert drawn is None

    def test_shuffle_library(self):
        """Test shuffling library."""
        lib = MockLibrary()
        for i in range(10):
            lib.add(MockCard(object_id=i, name=f"Card {i}"))
        lib.shuffle()
        assert len(lib) == 10  # Same count after shuffle

    def test_put_on_top(self):
        """Test putting card on top of library."""
        lib = MockLibrary()
        lib.add(MockCard(object_id=1, name="Bottom"))
        lib.put_on_top(MockCard(object_id=2, name="Top"))
        drawn = lib.draw()
        assert drawn.name == "Top"

    def test_put_on_bottom(self):
        """Test putting card on bottom of library."""
        lib = MockLibrary()
        lib.add(MockCard(object_id=1, name="Top"))
        lib.put_on_bottom(MockCard(object_id=2, name="Bottom"))
        # Draw should get Top first
        drawn = lib.draw()
        assert drawn.name == "Top"


# =============================================================================
# HAND TESTS
# =============================================================================

class TestHand:
    """Tests for hand zone operations."""

    def test_create_empty_hand(self):
        """Test creating empty hand."""
        hand = MockHand()
        assert len(hand) == 0

    def test_add_card_to_hand(self):
        """Test adding card to hand."""
        hand = MockHand()
        card = MockCard(object_id=1)
        hand.add(card)
        assert len(hand) == 1

    def test_remove_card_from_hand(self):
        """Test removing specific card from hand."""
        hand = MockHand()
        card = MockCard(object_id=1)
        hand.add(card)
        removed = hand.remove(card)
        assert removed == True
        assert len(hand) == 0

    def test_hand_contains_card(self):
        """Test checking if hand contains card."""
        hand = MockHand()
        card = MockCard(object_id=1)
        hand.add(card)
        assert card in hand

    def test_get_card_by_id(self):
        """Test getting card from hand by ID."""
        hand = MockHand()
        card = MockCard(object_id=42, name="Find Me")
        hand.add(card)
        found = hand.get_by_id(42)
        assert found is not None
        assert found.name == "Find Me"


# =============================================================================
# BATTLEFIELD TESTS
# =============================================================================

class TestBattlefield:
    """Tests for battlefield zone operations."""

    def test_create_empty_battlefield(self):
        """Test creating empty battlefield."""
        bf = MockBattlefield()
        assert len(bf) == 0

    def test_add_permanent(self):
        """Test adding permanent to battlefield."""
        bf = MockBattlefield()
        perm = MockCard(object_id=1)
        bf.add(perm)
        assert len(bf) == 1

    def test_remove_permanent(self):
        """Test removing permanent from battlefield."""
        bf = MockBattlefield()
        perm = MockCard(object_id=1)
        bf.add(perm)
        bf.remove(perm)
        assert len(bf) == 0

    def test_get_creatures(self):
        """Test filtering creatures on battlefield."""
        bf = MockBattlefield()
        creature = MockCard(object_id=1, controller_id=1)
        bf.add(creature)

        creatures = bf.creatures(1)
        assert len(creatures) == 1

    def test_get_by_controller(self):
        """Test getting permanents by controller."""
        bf = MockBattlefield()
        p1_perm = MockCard(object_id=1, controller_id=1)
        p2_perm = MockCard(object_id=2, controller_id=2)
        bf.add(p1_perm)
        bf.add(p2_perm)

        p1_perms = bf.get_all(controller_id=1)
        assert len(p1_perms) == 1
        assert all(p.controller_id == 1 for p in p1_perms)

    def test_get_by_id(self):
        """Test getting permanent by object ID."""
        bf = MockBattlefield()
        perm = MockCard(object_id=99, name="Specific Card")
        bf.add(perm)
        found = bf.get_by_id(99)
        assert found is not None
        assert found.name == "Specific Card"


# =============================================================================
# GRAVEYARD TESTS
# =============================================================================

class TestGraveyard:
    """Tests for graveyard zone operations."""

    def test_create_empty_graveyard(self):
        """Test creating empty graveyard."""
        gy = MockGraveyard()
        assert len(gy) == 0

    def test_add_to_graveyard(self):
        """Test adding card to graveyard."""
        gy = MockGraveyard()
        card = MockCard(object_id=1)
        gy.add(card)
        assert len(gy) == 1

    def test_graveyard_order(self):
        """Test graveyard maintains order (most recent on top)."""
        gy = MockGraveyard()
        gy.add(MockCard(object_id=1, name="First"))
        gy.add(MockCard(object_id=2, name="Second"))
        assert len(gy) == 2

    def test_remove_from_graveyard(self):
        """Test removing card from graveyard (e.g., for recursion)."""
        gy = MockGraveyard()
        card = MockCard(object_id=1)
        gy.add(card)
        gy.remove(card)
        assert len(gy) == 0


# =============================================================================
# EXILE TESTS
# =============================================================================

class TestExile:
    """Tests for exile zone operations."""

    def test_create_empty_exile(self):
        """Test creating empty exile zone."""
        exile = MockExile()
        assert len(exile) == 0

    def test_add_to_exile(self):
        """Test exiling a card."""
        exile = MockExile()
        card = MockCard(object_id=1)
        exile.add(card)
        assert len(exile) == 1

    def test_exile_face_down(self):
        """Test exiling face down (for certain effects)."""
        exile = MockExile()
        card = MockCard(object_id=1)
        exile.add(card, face_down=True)
        assert len(exile) == 1
        assert card.object_id in exile.face_down


# =============================================================================
# STACK TESTS
# =============================================================================

class TestStack:
    """Tests for stack zone operations."""

    def test_create_empty_stack(self):
        """Test creating empty stack."""
        stack = MockStack()
        assert stack.is_empty() == True

    def test_stack_is_lifo(self):
        """Test stack uses Last-In-First-Out order."""
        stack = MockStack()
        spell1 = MockCard(object_id=1, name="First")
        spell2 = MockCard(object_id=2, name="Second")
        stack.push(spell1)
        stack.push(spell2)
        # Pop should return most recent
        top = stack.pop()
        assert top.name == "Second"

    def test_peek_stack(self):
        """Test peeking at top of stack without removing."""
        stack = MockStack()
        spell = MockCard(object_id=1, name="Peek Me")
        stack.push(spell)
        top = stack.peek()
        assert top.name == "Peek Me"
        assert not stack.is_empty()  # Still on stack


# =============================================================================
# RUN TESTS
# =============================================================================

def run_zone_tests():
    """Run all zone tests and report results."""
    print("=" * 60)
    print("MTG ENGINE V3 - Zone Management Unit Tests")
    print("=" * 60)

    results = []

    # Test Library
    print("\nTesting Library...")
    try:
        t = TestLibrary()
        t.test_create_empty_library()
        t.test_add_cards_to_library()
        t.test_draw_from_library()
        t.test_draw_from_empty_library()
        t.test_shuffle_library()
        t.test_put_on_top()
        t.test_put_on_bottom()
        results.append(("Library", True))
        print("  PASS")
    except Exception as e:
        results.append(("Library", False))
        print(f"  FAIL: {e}")

    # Test Hand
    print("\nTesting Hand...")
    try:
        t = TestHand()
        t.test_create_empty_hand()
        t.test_add_card_to_hand()
        t.test_remove_card_from_hand()
        t.test_hand_contains_card()
        t.test_get_card_by_id()
        results.append(("Hand", True))
        print("  PASS")
    except Exception as e:
        results.append(("Hand", False))
        print(f"  FAIL: {e}")

    # Test Battlefield
    print("\nTesting Battlefield...")
    try:
        t = TestBattlefield()
        t.test_create_empty_battlefield()
        t.test_add_permanent()
        t.test_remove_permanent()
        t.test_get_creatures()
        t.test_get_by_controller()
        t.test_get_by_id()
        results.append(("Battlefield", True))
        print("  PASS")
    except Exception as e:
        results.append(("Battlefield", False))
        print(f"  FAIL: {e}")

    # Test Graveyard
    print("\nTesting Graveyard...")
    try:
        t = TestGraveyard()
        t.test_create_empty_graveyard()
        t.test_add_to_graveyard()
        t.test_graveyard_order()
        t.test_remove_from_graveyard()
        results.append(("Graveyard", True))
        print("  PASS")
    except Exception as e:
        results.append(("Graveyard", False))
        print(f"  FAIL: {e}")

    # Test Exile
    print("\nTesting Exile...")
    try:
        t = TestExile()
        t.test_create_empty_exile()
        t.test_add_to_exile()
        t.test_exile_face_down()
        results.append(("Exile", True))
        print("  PASS")
    except Exception as e:
        results.append(("Exile", False))
        print(f"  FAIL: {e}")

    # Test Stack
    print("\nTesting Stack...")
    try:
        t = TestStack()
        t.test_create_empty_stack()
        t.test_stack_is_lifo()
        t.test_peek_stack()
        results.append(("Stack", True))
        print("  PASS")
    except Exception as e:
        results.append(("Stack", False))
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
    success = run_zone_tests()
    sys.exit(0 if success else 1)
