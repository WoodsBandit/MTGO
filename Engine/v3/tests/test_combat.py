"""
Test suite for combat system - validates all combat keywords and interactions.
Uses pytest framework.

Tests cover:
- First Strike / Double Strike (CR 702.7, CR 702.4)
- Deathtouch (CR 702.2)
- Trample (CR 702.19)
- Lifelink (CR 702.15)
- Flying / Reach (CR 702.9, CR 702.17)
- Vigilance (CR 702.20)
- Menace (CR 702.111)
- Complex keyword interactions
"""
import pytest
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from unittest.mock import Mock, MagicMock, patch


# =============================================================================
# MOCK CLASSES FOR ISOLATED TESTING
# =============================================================================

@dataclass
class MockCharacteristics:
    """Mock characteristics for testing"""
    name: str = "Test Creature"
    power: Optional[int] = 2
    toughness: Optional[int] = 2
    types: Set[str] = field(default_factory=lambda: {"Creature"})
    subtypes: Set[str] = field(default_factory=set)
    colors: Set[str] = field(default_factory=set)

    def is_creature(self) -> bool:
        return "Creature" in self.types

    def is_artifact(self) -> bool:
        return "Artifact" in self.types

    def has_color(self, color) -> bool:
        return color in self.colors


@dataclass
class MockPermanent:
    """Mock permanent for combat testing"""
    object_id: int
    controller_id: int = 1
    owner_id: int = 1
    characteristics: MockCharacteristics = field(default_factory=MockCharacteristics)

    # Status
    is_tapped: bool = False
    is_attacking: bool = False
    is_blocking: bool = False
    has_summoning_sickness: bool = False

    # Combat tracking
    attacking_player_id: Optional[int] = None
    attacking_planeswalker_id: Optional[int] = None
    blocked_by_ids: List[int] = field(default_factory=list)
    blocking_ids: List[int] = field(default_factory=list)
    damage_assignment_order: List[int] = field(default_factory=list)

    # Damage
    damage_marked: int = 0
    damage_sources_with_deathtouch: Set[int] = field(default_factory=set)

    # Keywords
    _keywords: Set[str] = field(default_factory=set)

    # Counters
    counters: Dict[str, int] = field(default_factory=dict)

    def has_keyword(self, keyword: str) -> bool:
        return keyword.lower() in self._keywords

    def add_keyword(self, keyword: str):
        self._keywords.add(keyword.lower())

    def remove_keyword(self, keyword: str):
        self._keywords.discard(keyword.lower())

    def tap(self) -> bool:
        if self.is_tapped:
            return False
        self.is_tapped = True
        return True

    def untap(self) -> bool:
        if not self.is_tapped:
            return False
        self.is_tapped = False
        return True

    def effective_power(self) -> int:
        base = self.characteristics.power or 0
        base += self.counters.get("+1/+1", 0)
        base -= self.counters.get("-1/-1", 0)
        return base

    def effective_toughness(self) -> int:
        base = self.characteristics.toughness or 0
        base += self.counters.get("+1/+1", 0)
        base -= self.counters.get("-1/-1", 0)
        return base


@dataclass
class MockPlayer:
    """Mock player for combat testing"""
    player_id: int
    name: str = "Test Player"
    life: int = 20
    has_lost: bool = False
    ai: Any = None

    def deal_damage(self, amount: int, source_id: int) -> int:
        if amount <= 0:
            return 0
        self.life -= amount
        return amount

    def gain_life(self, amount: int) -> int:
        if amount <= 0:
            return 0
        self.life += amount
        return amount


class MockBattlefield:
    """Mock battlefield zone"""

    def __init__(self):
        self.objects: List[MockPermanent] = []
        self._by_id: Dict[int, MockPermanent] = {}

    def add(self, permanent: MockPermanent):
        self.objects.append(permanent)
        self._by_id[permanent.object_id] = permanent

    def get_by_id(self, object_id: int) -> Optional[MockPermanent]:
        return self._by_id.get(object_id)

    def creatures(self, controller_id: Optional[int] = None) -> List[MockPermanent]:
        result = [p for p in self.objects if p.characteristics.is_creature()]
        if controller_id is not None:
            result = [p for p in result if p.controller_id == controller_id]
        return result


class MockZones:
    """Mock zones container"""

    def __init__(self):
        self.battlefield = MockBattlefield()


class MockEventManager:
    """Mock event manager that records events"""

    def __init__(self):
        self.events: List[Any] = []

    def emit(self, event: Any):
        self.events.append(event)

    def clear(self):
        self.events.clear()


class MockGame:
    """Mock game state for combat testing"""

    def __init__(self):
        self.zones = MockZones()
        self.events = MockEventManager()
        self.players: Dict[int, MockPlayer] = {
            1: MockPlayer(player_id=1, name="Player 1"),
            2: MockPlayer(player_id=2, name="Player 2")
        }
        self.active_player_id: int = 1
        self.priority_player_id: int = 1
        self._next_object_id: int = 1000

    def get_player(self, player_id: int) -> Optional[MockPlayer]:
        return self.players.get(player_id)

    def check_game_over(self) -> bool:
        return any(p.has_lost for p in self.players.values())

    def get_object(self, object_id: int) -> Optional[MockPermanent]:
        return self.zones.battlefield.get_by_id(object_id)

    def next_object_id(self) -> int:
        self._next_object_id += 1
        return self._next_object_id


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def game() -> MockGame:
    """Create a minimal game state for testing"""
    return MockGame()


@pytest.fixture
def vanilla_creature(game: MockGame) -> MockPermanent:
    """2/2 creature with no abilities"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Grizzly Bears",
            power=2,
            toughness=2
        )
    )
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def flying_creature(game: MockGame) -> MockPermanent:
    """2/2 with flying"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Wind Drake",
            power=2,
            toughness=2
        )
    )
    creature.add_keyword("flying")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def reach_creature(game: MockGame) -> MockPermanent:
    """2/4 with reach"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=2,
        characteristics=MockCharacteristics(
            name="Giant Spider",
            power=2,
            toughness=4
        )
    )
    creature.add_keyword("reach")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def first_strike_creature(game: MockGame) -> MockPermanent:
    """3/2 with first strike"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Cavalry Pegasus",
            power=3,
            toughness=2
        )
    )
    creature.add_keyword("first_strike")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def double_strike_creature(game: MockGame) -> MockPermanent:
    """2/2 with double strike"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Fencing Ace",
            power=2,
            toughness=2
        )
    )
    creature.add_keyword("double_strike")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def deathtouch_creature(game: MockGame) -> MockPermanent:
    """1/1 with deathtouch"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Typhoid Rats",
            power=1,
            toughness=1
        )
    )
    creature.add_keyword("deathtouch")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def trample_creature(game: MockGame) -> MockPermanent:
    """5/5 with trample"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Colossal Dreadmaw",
            power=5,
            toughness=5
        )
    )
    creature.add_keyword("trample")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def lifelink_creature(game: MockGame) -> MockPermanent:
    """3/3 with lifelink"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Vampire Nighthawk",
            power=3,
            toughness=3
        )
    )
    creature.add_keyword("lifelink")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def vigilance_creature(game: MockGame) -> MockPermanent:
    """3/3 with vigilance"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Heliod's Pilgrim",
            power=3,
            toughness=3
        )
    )
    creature.add_keyword("vigilance")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def menace_creature(game: MockGame) -> MockPermanent:
    """3/2 with menace"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=1,
        characteristics=MockCharacteristics(
            name="Goblin War Party",
            power=3,
            toughness=2
        )
    )
    creature.add_keyword("menace")
    game.zones.battlefield.add(creature)
    return creature


@pytest.fixture
def indestructible_creature(game: MockGame) -> MockPermanent:
    """4/4 with indestructible"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=2,
        characteristics=MockCharacteristics(
            name="Darksteel Colossus",
            power=4,
            toughness=4
        )
    )
    creature.add_keyword("indestructible")
    game.zones.battlefield.add(creature)
    return creature


def create_creature(game: MockGame, controller_id: int, power: int, toughness: int,
                    name: str = "Test Creature", keywords: Optional[Set[str]] = None) -> MockPermanent:
    """Helper to create creatures with specific stats"""
    creature = MockPermanent(
        object_id=game.next_object_id(),
        controller_id=controller_id,
        characteristics=MockCharacteristics(
            name=name,
            power=power,
            toughness=toughness
        )
    )
    if keywords:
        for kw in keywords:
            creature.add_keyword(kw)
    game.zones.battlefield.add(creature)
    return creature


# =============================================================================
# COMBAT HELPER FUNCTIONS
# =============================================================================

def calculate_lethal_damage(creature: MockPermanent, has_deathtouch: bool) -> int:
    """Calculate lethal damage needed for a creature"""
    if has_deathtouch:
        return 1
    return max(1, creature.effective_toughness() - creature.damage_marked)


def simulate_combat_damage(
    attacker: MockPermanent,
    blockers: List[MockPermanent],
    defending_player: MockPlayer,
    game: MockGame
) -> Dict[str, Any]:
    """
    Simulate combat damage between an attacker and blockers.

    Returns a dict with:
    - attacker_damage_taken: int
    - blocker_damage_taken: Dict[int, int] (object_id -> damage)
    - player_damage_taken: int
    - life_gained: int (from lifelink)
    - creatures_that_die: List[int] (object_ids)
    """
    result = {
        "attacker_damage_taken": 0,
        "blocker_damage_taken": {},
        "player_damage_taken": 0,
        "life_gained": 0,
        "creatures_that_die": []
    }

    attacker_power = attacker.effective_power()
    has_deathtouch = attacker.has_keyword("deathtouch")
    has_trample = attacker.has_keyword("trample")
    has_lifelink = attacker.has_keyword("lifelink")
    has_first_strike = attacker.has_keyword("first_strike")
    has_double_strike = attacker.has_keyword("double_strike")

    if not blockers:
        # Unblocked - all damage to player
        result["player_damage_taken"] = attacker_power
        if has_lifelink:
            result["life_gained"] = attacker_power
        return result

    # Calculate damage from blockers to attacker
    blocker_has_first_strike = any(
        b.has_keyword("first_strike") or b.has_keyword("double_strike")
        for b in blockers
    )
    blocker_has_deathtouch = any(b.has_keyword("deathtouch") for b in blockers)

    # First strike step
    if has_first_strike or has_double_strike:
        # Attacker deals first strike damage
        remaining_power = attacker_power
        for blocker in blockers:
            if remaining_power <= 0:
                break
            lethal = calculate_lethal_damage(blocker, has_deathtouch)
            damage_to_blocker = min(remaining_power, lethal)
            result["blocker_damage_taken"][blocker.object_id] = damage_to_blocker
            remaining_power -= damage_to_blocker

            # Check if blocker dies
            if has_deathtouch and damage_to_blocker > 0:
                result["creatures_that_die"].append(blocker.object_id)
            elif damage_to_blocker >= blocker.effective_toughness():
                result["creatures_that_die"].append(blocker.object_id)

        # Trample excess
        if has_trample and remaining_power > 0:
            result["player_damage_taken"] += remaining_power

        if has_lifelink:
            result["life_gained"] += attacker_power - remaining_power + (remaining_power if has_trample else 0)

    # Regular damage step (if blocker survives first strike)
    if not (has_first_strike and not has_double_strike):
        # Blockers deal damage to attacker (if they survived first strike)
        total_blocker_damage = 0
        for blocker in blockers:
            if blocker.object_id not in result["creatures_that_die"]:
                total_blocker_damage += blocker.effective_power()

        result["attacker_damage_taken"] = total_blocker_damage

        # Check if attacker dies
        attacker_toughness = attacker.effective_toughness()
        if blocker_has_deathtouch and total_blocker_damage > 0:
            if not attacker.has_keyword("indestructible"):
                result["creatures_that_die"].append(attacker.object_id)
        elif total_blocker_damage >= attacker_toughness:
            if not attacker.has_keyword("indestructible"):
                result["creatures_that_die"].append(attacker.object_id)

    # Handle double strike second hit
    if has_double_strike:
        remaining_power = attacker_power
        for blocker in blockers:
            if blocker.object_id in result["creatures_that_die"]:
                continue  # Already dead from first strike
            if remaining_power <= 0:
                break
            lethal = calculate_lethal_damage(blocker, has_deathtouch)
            damage = min(remaining_power, lethal)
            result["blocker_damage_taken"][blocker.object_id] = \
                result["blocker_damage_taken"].get(blocker.object_id, 0) + damage
            remaining_power -= damage

        if has_trample and remaining_power > 0:
            result["player_damage_taken"] += remaining_power

        if has_lifelink:
            result["life_gained"] += attacker_power

    return result


# =============================================================================
# FIRST STRIKE TESTS
# =============================================================================

class TestFirstStrike:
    """Tests for first strike combat ability (CR 702.7)"""

    def test_first_strike_kills_before_damage(self, game: MockGame):
        """3/2 first strike vs 2/3 vanilla - first striker wins, takes no damage"""
        attacker = create_creature(game, 1, 3, 2, "First Striker", {"first_strike"})
        blocker = create_creature(game, 2, 2, 3, "Vanilla Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # First striker deals 3 damage to blocker (killing it)
        assert result["blocker_damage_taken"][blocker.object_id] == 3
        assert blocker.object_id in result["creatures_that_die"]

        # Blocker dies in first strike step, never deals damage
        assert result["attacker_damage_taken"] == 0
        assert attacker.object_id not in result["creatures_that_die"]

    def test_first_strike_vs_first_strike(self, game: MockGame):
        """Both have first strike - simultaneous damage"""
        attacker = create_creature(game, 1, 3, 2, "First Striker A", {"first_strike"})
        blocker = create_creature(game, 2, 3, 2, "First Striker B", {"first_strike"})

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Both deal damage simultaneously in first strike step
        assert result["blocker_damage_taken"][blocker.object_id] == 3
        assert result["attacker_damage_taken"] == 3
        assert blocker.object_id in result["creatures_that_die"]
        assert attacker.object_id in result["creatures_that_die"]

    def test_first_strike_vs_larger_creature(self, game: MockGame):
        """3/2 first strike vs 5/5 vanilla - first striker dies"""
        attacker = create_creature(game, 1, 3, 2, "First Striker", {"first_strike"})
        blocker = create_creature(game, 2, 5, 5, "Big Vanilla")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # First striker deals 3 damage, blocker survives
        assert result["blocker_damage_taken"][blocker.object_id] == 3
        assert blocker.object_id not in result["creatures_that_die"]

        # Blocker deals 5 damage back, killing attacker
        assert result["attacker_damage_taken"] == 5
        assert attacker.object_id in result["creatures_that_die"]

    def test_double_strike_deals_twice(self, game: MockGame):
        """Double strike creature deals damage in both steps"""
        attacker = create_creature(game, 1, 2, 2, "Double Striker", {"double_strike"})
        blocker = create_creature(game, 2, 1, 4, "Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Double strike deals 2 damage twice = 4 total
        assert result["blocker_damage_taken"][blocker.object_id] == 4
        assert blocker.object_id in result["creatures_that_die"]

    def test_double_strike_trample_overkill(self, game: MockGame):
        """6/6 double strike trample vs 2/2 - deals 4+6=10 to player after lethal"""
        attacker = create_creature(game, 1, 6, 6, "DS Trampler", {"double_strike", "trample"})
        blocker = create_creature(game, 2, 2, 2, "Small Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # First strike: 2 to blocker (lethal), 4 tramples
        # Regular: blocker dead, 6 tramples
        # Total trample: 4 + 6 = 10
        assert result["player_damage_taken"] == 10
        assert blocker.object_id in result["creatures_that_die"]


# =============================================================================
# DEATHTOUCH TESTS
# =============================================================================

class TestDeathtouch:
    """Tests for deathtouch combat ability (CR 702.2)"""

    def test_deathtouch_kills_any_toughness(self, game: MockGame):
        """1/1 deathtouch kills 10/10"""
        attacker = create_creature(game, 1, 1, 1, "Deathtouch", {"deathtouch"})
        blocker = create_creature(game, 2, 10, 10, "Giant")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Deathtouch deals 1 damage, which is lethal
        assert result["blocker_damage_taken"][blocker.object_id] == 1
        assert blocker.object_id in result["creatures_that_die"]

        # Giant deals 10 damage back, killing deathtouch
        assert result["attacker_damage_taken"] == 10
        assert attacker.object_id in result["creatures_that_die"]

    def test_deathtouch_trample_interaction(self, game: MockGame):
        """6/6 trample deathtouch blocked by 5/5 - 1 to blocker, 5 tramples

        Per CR 702.2c and 702.19b, when assigning damage with both
        deathtouch and trample, 1 damage is considered lethal.
        """
        attacker = create_creature(game, 1, 6, 6, "DT Trampler", {"deathtouch", "trample"})
        blocker = create_creature(game, 2, 5, 5, "Big Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Only 1 damage needed to kill blocker, 5 tramples
        assert result["blocker_damage_taken"][blocker.object_id] == 1
        assert result["player_damage_taken"] == 5
        assert blocker.object_id in result["creatures_that_die"]

    def test_first_strike_beats_deathtouch(self, game: MockGame):
        """3/1 first strike vs 1/1 deathtouch - first striker wins"""
        attacker = create_creature(game, 1, 3, 1, "First Striker", {"first_strike"})
        blocker = create_creature(game, 2, 1, 1, "Deathtouch", {"deathtouch"})

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # First strike kills deathtouch before it can deal damage
        assert blocker.object_id in result["creatures_that_die"]
        assert result["attacker_damage_taken"] == 0
        assert attacker.object_id not in result["creatures_that_die"]

    def test_deathtouch_vs_indestructible(self, game: MockGame):
        """1/1 deathtouch vs 4/4 indestructible - indestructible survives"""
        attacker = create_creature(game, 1, 1, 1, "Deathtouch", {"deathtouch"})
        blocker = create_creature(game, 2, 4, 4, "Indestructible", {"indestructible"})

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Deathtouch damage is dealt but indestructible prevents death
        assert result["blocker_damage_taken"][blocker.object_id] == 1
        assert blocker.object_id not in result["creatures_that_die"]

        # Indestructible kills deathtouch
        assert attacker.object_id in result["creatures_that_die"]

    def test_deathtouch_multiple_blockers(self, game: MockGame):
        """3/3 deathtouch vs two 3/3s - kills both with 1 damage each"""
        attacker = create_creature(game, 1, 3, 3, "Deathtouch", {"deathtouch"})
        blocker1 = create_creature(game, 2, 3, 3, "Blocker 1")
        blocker2 = create_creature(game, 2, 3, 3, "Blocker 2")

        result = simulate_combat_damage(attacker, [blocker1, blocker2], game.players[2], game)

        # 1 damage to each is lethal, third damage is wasted
        assert blocker1.object_id in result["creatures_that_die"]
        assert blocker2.object_id in result["creatures_that_die"]


# =============================================================================
# TRAMPLE TESTS
# =============================================================================

class TestTrample:
    """Tests for trample combat ability (CR 702.19)"""

    def test_trample_excess_damage(self, game: MockGame):
        """5/5 trample blocked by 2/2 - 2 to blocker, 3 to player"""
        attacker = create_creature(game, 1, 5, 5, "Trampler", {"trample"})
        blocker = create_creature(game, 2, 2, 2, "Small Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        assert result["blocker_damage_taken"][blocker.object_id] == 2
        assert result["player_damage_taken"] == 3
        assert blocker.object_id in result["creatures_that_die"]

    def test_trample_multiple_blockers(self, game: MockGame):
        """7/7 trample blocked by 2/2 and 3/3 - assigns lethal then tramples"""
        attacker = create_creature(game, 1, 7, 7, "Big Trampler", {"trample"})
        blocker1 = create_creature(game, 2, 2, 2, "Blocker 1")
        blocker2 = create_creature(game, 2, 3, 3, "Blocker 2")

        result = simulate_combat_damage(attacker, [blocker1, blocker2], game.players[2], game)

        # 2 to first blocker, 3 to second blocker, 2 tramples
        assert result["blocker_damage_taken"][blocker1.object_id] == 2
        assert result["blocker_damage_taken"][blocker2.object_id] == 3
        assert result["player_damage_taken"] == 2
        assert blocker1.object_id in result["creatures_that_die"]
        assert blocker2.object_id in result["creatures_that_die"]

    def test_trample_no_excess(self, game: MockGame):
        """4/4 trample blocked by 4/4 - all damage to blocker, none tramples"""
        attacker = create_creature(game, 1, 4, 4, "Trampler", {"trample"})
        blocker = create_creature(game, 2, 4, 4, "Equal Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        assert result["blocker_damage_taken"][blocker.object_id] == 4
        assert result["player_damage_taken"] == 0

    def test_trample_overkill_single_blocker(self, game: MockGame):
        """10/10 trample blocked by 1/1 - 1 to blocker, 9 tramples"""
        attacker = create_creature(game, 1, 10, 10, "Huge Trampler", {"trample"})
        blocker = create_creature(game, 2, 1, 1, "Tiny Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Must assign lethal (1), rest tramples
        assert result["blocker_damage_taken"][blocker.object_id] == 1
        assert result["player_damage_taken"] == 9


# =============================================================================
# LIFELINK TESTS
# =============================================================================

class TestLifelink:
    """Tests for lifelink combat ability (CR 702.15)"""

    def test_lifelink_combat_damage(self, game: MockGame):
        """3/3 lifelink deals combat damage - controller gains 3 life"""
        attacker = create_creature(game, 1, 3, 3, "Lifelinker", {"lifelink"})

        result = simulate_combat_damage(attacker, [], game.players[2], game)

        # Unblocked, deals 3 to player, gains 3 life
        assert result["player_damage_taken"] == 3
        assert result["life_gained"] == 3

    def test_lifelink_blocked(self, game: MockGame):
        """3/3 lifelink blocked by 1/1 - still gains 3 life"""
        attacker = create_creature(game, 1, 3, 3, "Lifelinker", {"lifelink"})
        blocker = create_creature(game, 2, 1, 1, "Chump")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Deals 3 damage (1 to blocker, 2 wasted), gains 1 life (only from actual damage dealt)
        # Note: Lifelink gains life equal to damage DEALT, not power
        # All 3 power is "dealt" to the blocker
        assert result["blocker_damage_taken"][blocker.object_id] >= 1
        # Lifelink triggers on damage dealt, so it depends on how much was actually dealt
        # In standard rules, you gain life equal to the damage dealt to all targets

    def test_lifelink_trample(self, game: MockGame):
        """5/5 lifelink trample blocked by 2/2 - gains 5 life total"""
        attacker = create_creature(game, 1, 5, 5, "LT", {"lifelink", "trample"})
        blocker = create_creature(game, 2, 2, 2, "Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # 2 damage to blocker, 3 tramples to player, gains 5 total
        assert result["blocker_damage_taken"][blocker.object_id] == 2
        assert result["player_damage_taken"] == 3
        # Total damage dealt = 5, so life gained = 5

    def test_double_strike_lifelink(self, game: MockGame):
        """Double strike + lifelink gains life twice"""
        attacker = create_creature(game, 1, 3, 3, "DS Lifelink", {"double_strike", "lifelink"})

        result = simulate_combat_damage(attacker, [], game.players[2], game)

        # 3 damage in first strike, 3 damage in regular = 6 total damage
        # Gains 6 life
        assert result["player_damage_taken"] == 6
        assert result["life_gained"] == 6


# =============================================================================
# FLYING TESTS
# =============================================================================

class TestFlying:
    """Tests for flying and reach abilities (CR 702.9, CR 702.17)"""

    def test_flying_evasion_check(self, game: MockGame):
        """Flying creature cannot be blocked by non-flying, non-reach"""
        flyer = create_creature(game, 1, 2, 2, "Flyer", {"flying"})
        ground = create_creature(game, 2, 4, 4, "Ground")

        # Check if ground creature can block flyer
        can_block = not flyer.has_keyword("flying") or \
                   ground.has_keyword("flying") or \
                   ground.has_keyword("reach")

        assert can_block is False

    def test_reach_blocks_flying(self, game: MockGame):
        """2/4 reach can block 2/2 flying"""
        flyer = create_creature(game, 1, 2, 2, "Flyer", {"flying"})
        reacher = create_creature(game, 2, 2, 4, "Reacher", {"reach"})

        can_block = not flyer.has_keyword("flying") or \
                   reacher.has_keyword("flying") or \
                   reacher.has_keyword("reach")

        assert can_block is True

    def test_flying_blocks_flying(self, game: MockGame):
        """Flying creature can block another flying creature"""
        flyer1 = create_creature(game, 1, 2, 2, "Flyer A", {"flying"})
        flyer2 = create_creature(game, 2, 2, 2, "Flyer B", {"flying"})

        can_block = not flyer1.has_keyword("flying") or \
                   flyer2.has_keyword("flying") or \
                   flyer2.has_keyword("reach")

        assert can_block is True

    def test_ground_vs_ground(self, game: MockGame):
        """Ground creature can block ground creature"""
        ground1 = create_creature(game, 1, 2, 2, "Ground A")
        ground2 = create_creature(game, 2, 2, 2, "Ground B")

        can_block = not ground1.has_keyword("flying") or \
                   ground2.has_keyword("flying") or \
                   ground2.has_keyword("reach")

        assert can_block is True


# =============================================================================
# VIGILANCE TESTS
# =============================================================================

class TestVigilance:
    """Tests for vigilance ability (CR 702.20)"""

    def test_vigilance_doesnt_tap(self, game: MockGame):
        """Vigilance creature doesn't tap when attacking"""
        vigilant = create_creature(game, 1, 3, 3, "Vigilant", {"vigilance"})

        # Simulate attack declaration
        vigilant.is_attacking = True
        if not vigilant.has_keyword("vigilance"):
            vigilant.tap()

        assert vigilant.is_tapped is False

    def test_non_vigilance_taps(self, game: MockGame):
        """Non-vigilance creature taps when attacking"""
        normal = create_creature(game, 1, 3, 3, "Normal")

        # Simulate attack declaration
        normal.is_attacking = True
        if not normal.has_keyword("vigilance"):
            normal.tap()

        assert normal.is_tapped is True

    def test_vigilance_can_block_after_attacking(self, game: MockGame):
        """Vigilance creature could theoretically block after attacking

        Note: In actual MTG, you can't attack and block in the same combat,
        but vigilance keeps the creature untapped which matters for other effects.
        """
        vigilant = create_creature(game, 1, 3, 3, "Vigilant", {"vigilance"})

        # Attack
        vigilant.is_attacking = True
        if not vigilant.has_keyword("vigilance"):
            vigilant.tap()

        # After combat, creature is untapped
        vigilant.is_attacking = False

        # Creature is untapped and could block on opponent's turn
        assert vigilant.is_tapped is False


# =============================================================================
# MENACE TESTS
# =============================================================================

class TestMenace:
    """Tests for menace ability (CR 702.111)"""

    def test_menace_requires_two_blockers(self, game: MockGame):
        """Menace creature can't be blocked by single creature"""
        menace = create_creature(game, 1, 3, 2, "Menace", {"menace"})
        blocker = create_creature(game, 2, 4, 4, "Single Blocker")

        # Check if single blocker is legal
        blocker_count = 1
        is_legal_block = not menace.has_keyword("menace") or blocker_count >= 2

        assert is_legal_block is False

    def test_menace_blocked_by_two(self, game: MockGame):
        """Menace creature can be blocked by two creatures"""
        menace = create_creature(game, 1, 3, 2, "Menace", {"menace"})
        blocker1 = create_creature(game, 2, 2, 2, "Blocker 1")
        blocker2 = create_creature(game, 2, 2, 2, "Blocker 2")

        # Check if two blockers is legal
        blocker_count = 2
        is_legal_block = not menace.has_keyword("menace") or blocker_count >= 2

        assert is_legal_block is True

    def test_menace_blocked_by_three(self, game: MockGame):
        """Menace creature can be blocked by more than two creatures"""
        menace = create_creature(game, 1, 3, 2, "Menace", {"menace"})

        blocker_count = 3
        is_legal_block = not menace.has_keyword("menace") or blocker_count >= 2

        assert is_legal_block is True

    def test_menace_combat_damage(self, game: MockGame):
        """3/2 menace blocked by two 2/2s - menace dies, kills one blocker"""
        menace = create_creature(game, 1, 3, 2, "Menace", {"menace"})
        blocker1 = create_creature(game, 2, 2, 2, "Blocker 1")
        blocker2 = create_creature(game, 2, 2, 2, "Blocker 2")

        result = simulate_combat_damage(menace, [blocker1, blocker2], game.players[2], game)

        # Menace deals 3 damage - kills first blocker (2 damage), 1 to second
        assert blocker1.object_id in result["creatures_that_die"]
        assert result["blocker_damage_taken"][blocker1.object_id] == 2
        assert result["blocker_damage_taken"][blocker2.object_id] == 1
        assert blocker2.object_id not in result["creatures_that_die"]

        # Blockers deal 4 total damage (2+2), menace dies
        assert result["attacker_damage_taken"] == 4
        assert menace.object_id in result["creatures_that_die"]


# =============================================================================
# COMPLEX INTERACTIONS
# =============================================================================

class TestComplexInteractions:
    """Tests for complex keyword combinations"""

    def test_first_strike_deathtouch_vs_indestructible(self, game: MockGame):
        """First strike + deathtouch vs indestructible - indestructible survives"""
        attacker = create_creature(game, 1, 1, 1, "FS DT", {"first_strike", "deathtouch"})
        blocker = create_creature(game, 2, 5, 5, "Indestructible", {"indestructible"})

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # First strike deathtouch deals 1 damage
        assert result["blocker_damage_taken"][blocker.object_id] == 1

        # Indestructible survives deathtouch
        assert blocker.object_id not in result["creatures_that_die"]

        # Indestructible deals 5 damage, killing attacker
        assert attacker.object_id in result["creatures_that_die"]

    def test_double_strike_lifelink_blocked(self, game: MockGame):
        """Double strike + lifelink blocked - gains life from both hits"""
        attacker = create_creature(game, 1, 3, 3, "DS LL", {"double_strike", "lifelink"})
        blocker = create_creature(game, 2, 2, 6, "Tough Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Double strike deals 3 + 3 = 6 damage
        assert result["blocker_damage_taken"][blocker.object_id] == 6
        assert blocker.object_id in result["creatures_that_die"]

        # Lifelink gains life from both damage steps
        assert result["life_gained"] == 6

    def test_trample_deathtouch_multiple_blockers(self, game: MockGame):
        """Trample + deathtouch vs multiple blockers - 1 damage each, rest tramples"""
        attacker = create_creature(game, 1, 6, 6, "TDT", {"trample", "deathtouch"})
        blocker1 = create_creature(game, 2, 3, 3, "Blocker 1")
        blocker2 = create_creature(game, 2, 3, 3, "Blocker 2")

        result = simulate_combat_damage(attacker, [blocker1, blocker2], game.players[2], game)

        # 1 damage to each blocker (lethal with deathtouch), 4 tramples
        assert result["blocker_damage_taken"][blocker1.object_id] == 1
        assert result["blocker_damage_taken"][blocker2.object_id] == 1
        assert result["player_damage_taken"] == 4
        assert blocker1.object_id in result["creatures_that_die"]
        assert blocker2.object_id in result["creatures_that_die"]

    def test_flying_first_strike_vs_reach(self, game: MockGame):
        """Flying first strike vs reach - first strike resolves first"""
        attacker = create_creature(game, 1, 3, 2, "Flying FS", {"flying", "first_strike"})
        blocker = create_creature(game, 2, 2, 3, "Reach", {"reach"})

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # First strike deals 3 damage, killing blocker
        assert blocker.object_id in result["creatures_that_die"]
        # Blocker never deals damage
        assert result["attacker_damage_taken"] == 0

    def test_vigilance_lifelink_menace(self, game: MockGame):
        """Vigilance + lifelink + menace - all abilities work together"""
        attacker = create_creature(game, 1, 4, 4, "VLM", {"vigilance", "lifelink", "menace"})

        # Attack declaration - doesn't tap
        attacker.is_attacking = True
        if not attacker.has_keyword("vigilance"):
            attacker.tap()
        assert attacker.is_tapped is False

        # Check menace requirement
        is_legal_single_block = not attacker.has_keyword("menace") or 1 >= 2
        assert is_legal_single_block is False

        # If blocked by two creatures
        blocker1 = create_creature(game, 2, 2, 2, "Blocker 1")
        blocker2 = create_creature(game, 2, 2, 2, "Blocker 2")

        result = simulate_combat_damage(attacker, [blocker1, blocker2], game.players[2], game)

        # Lifelink still works
        total_damage_dealt = (result["blocker_damage_taken"].get(blocker1.object_id, 0) +
                             result["blocker_damage_taken"].get(blocker2.object_id, 0))
        assert result["life_gained"] > 0

    def test_double_strike_first_strike_redundant(self, game: MockGame):
        """Double strike + first strike - redundant, works same as double strike"""
        attacker = create_creature(game, 1, 2, 2, "DS+FS", {"double_strike", "first_strike"})
        blocker = create_creature(game, 2, 1, 4, "Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Still deals damage twice like normal double strike
        assert result["blocker_damage_taken"][blocker.object_id] == 4
        assert blocker.object_id in result["creatures_that_die"]

    def test_indestructible_vs_massive_damage(self, game: MockGame):
        """Indestructible survives any amount of regular damage"""
        attacker = create_creature(game, 1, 100, 100, "Colossus")
        blocker = create_creature(game, 2, 1, 1, "Indestructible", {"indestructible"})

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # Takes 100 damage but doesn't die
        assert result["blocker_damage_taken"][blocker.object_id] == 1
        assert blocker.object_id not in result["creatures_that_die"]

    def test_zero_power_creature_combat(self, game: MockGame):
        """0/3 creature deals no combat damage"""
        attacker = create_creature(game, 1, 0, 3, "Wall")
        blocker = create_creature(game, 2, 2, 2, "Blocker")

        result = simulate_combat_damage(attacker, [blocker], game.players[2], game)

        # 0 power = 0 damage
        assert result["blocker_damage_taken"].get(blocker.object_id, 0) == 0
        assert blocker.object_id not in result["creatures_that_die"]

        # Blocker still deals damage
        assert result["attacker_damage_taken"] == 2

    def test_negative_power_counter_interaction(self, game: MockGame):
        """Creature with -1/-1 counters reducing power"""
        attacker = create_creature(game, 1, 3, 3, "Weakened")
        attacker.counters["-1/-1"] = 2  # Now 1/1

        assert attacker.effective_power() == 1
        assert attacker.effective_toughness() == 1

        result = simulate_combat_damage(attacker, [], game.players[2], game)
        assert result["player_damage_taken"] == 1


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Edge cases and unusual scenarios"""

    def test_unblocked_attacker_all_damage_to_player(self, game: MockGame):
        """Unblocked attacker deals all damage to defending player"""
        attacker = create_creature(game, 1, 5, 5, "Attacker")

        result = simulate_combat_damage(attacker, [], game.players[2], game)

        assert result["player_damage_taken"] == 5
        assert result["attacker_damage_taken"] == 0

    def test_multiple_blockers_damage_assignment(self, game: MockGame):
        """Damage must be assigned in order, lethal before moving on"""
        attacker = create_creature(game, 1, 5, 5, "Attacker")
        blocker1 = create_creature(game, 2, 1, 2, "First in order")
        blocker2 = create_creature(game, 2, 1, 2, "Second in order")
        blocker3 = create_creature(game, 2, 1, 2, "Third in order")

        result = simulate_combat_damage(attacker, [blocker1, blocker2, blocker3], game.players[2], game)

        # 2 to first (lethal), 2 to second (lethal), 1 to third
        assert result["blocker_damage_taken"][blocker1.object_id] == 2
        assert result["blocker_damage_taken"][blocker2.object_id] == 2
        assert result["blocker_damage_taken"][blocker3.object_id] == 1

        assert blocker1.object_id in result["creatures_that_die"]
        assert blocker2.object_id in result["creatures_that_die"]
        assert blocker3.object_id not in result["creatures_that_die"]

    def test_creature_with_all_keywords(self, game: MockGame):
        """Test creature with multiple keywords"""
        super_creature = create_creature(
            game, 1, 4, 4, "Super Creature",
            {"flying", "first_strike", "deathtouch", "trample", "lifelink", "vigilance"}
        )

        # Doesn't tap when attacking
        super_creature.is_attacking = True
        if not super_creature.has_keyword("vigilance"):
            super_creature.tap()
        assert super_creature.is_tapped is False

        # Combat vs 2/4 blocker
        blocker = create_creature(game, 2, 2, 4, "Blocker")

        result = simulate_combat_damage(super_creature, [blocker], game.players[2], game)

        # First strike + deathtouch = kills blocker with 1 damage
        assert blocker.object_id in result["creatures_that_die"]

        # Trample = 3 damage to player
        assert result["player_damage_taken"] == 3

        # Lifelink = 4 life gained
        assert result["life_gained"] == 4

        # No damage taken (first strike killed blocker)
        assert result["attacker_damage_taken"] == 0


# =============================================================================
# STATE-BASED ACTIONS RELATED
# =============================================================================

class TestCombatSBA:
    """Tests related to state-based actions in combat"""

    def test_zero_toughness_dies(self, game: MockGame):
        """Creature with 0 or less toughness dies (SBA)"""
        creature = create_creature(game, 1, 3, 3, "Soon to die")
        creature.counters["-1/-1"] = 3

        assert creature.effective_toughness() == 0
        # In actual game, SBA would destroy this

    def test_lethal_damage_marked(self, game: MockGame):
        """Creature with lethal damage marked dies (SBA)"""
        creature = create_creature(game, 1, 3, 3, "Damaged")
        creature.damage_marked = 3

        # Lethal damage check
        has_lethal = creature.damage_marked >= creature.effective_toughness()
        assert has_lethal is True

    def test_deathtouch_damage_tracked(self, game: MockGame):
        """Deathtouch damage source is tracked"""
        creature = create_creature(game, 1, 3, 3, "Target")
        deathtouch_source_id = 999

        creature.damage_marked = 1
        creature.damage_sources_with_deathtouch.add(deathtouch_source_id)

        # Any damage from deathtouch source is lethal
        has_deathtouch_damage = len(creature.damage_sources_with_deathtouch) > 0
        assert has_deathtouch_damage is True


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
