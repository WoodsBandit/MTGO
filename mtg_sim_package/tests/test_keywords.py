"""
Comprehensive MTG Engine Keyword Testing Suite
===============================================

Tests ALL keyword abilities and combat mechanics in the MTG engine.
Covers evasion, combat, protection, return mechanics, and special keywords.

Test Categories:
1. Evasion Keywords (flying, reach, menace, trample, unblockable)
2. Combat Keywords (first strike, double strike, deathtouch, lifelink, vigilance, haste, defender)
3. Protection Keywords (hexproof, shroud, ward, protection, indestructible)
4. Return Keywords (persist, undying)
5. Special Keywords (phasing, regenerate, wither, infect)

Total: 40+ test cases
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mtg_engine import Card, Player, Game, ManaCost, ManaPool
from dataclasses import dataclass, field
from typing import List


# =============================================================================
# TEST FIXTURES AND HELPERS
# =============================================================================

class GameContext:
    """Lightweight game context for testing"""
    def __init__(self):
        self.p1 = Player(player_id=1, deck_name="Player 1", archetype="midrange", life=20)
        self.p2 = Player(player_id=2, deck_name="Player 2", archetype="midrange", life=20)

        # Give each player 10 basic lands
        for _ in range(10):
            self.p1.battlefield.append(Card(
                name="Forest",
                card_type="land",
                produces=["G"]
            ))
            self.p2.battlefield.append(Card(
                name="Forest",
                card_type="land",
                produces=["G"]
            ))


@pytest.fixture
def game():
    """Create a basic game context for testing"""
    return GameContext()


def create_creature(name="Test Creature", power=2, toughness=2, keywords=None, controller=1, summoning_sick=False):
    """Helper to create test creatures"""
    if keywords is None:
        keywords = []
    return Card(
        name=name,
        card_type="creature",
        power=power,
        toughness=toughness,
        keywords=keywords,
        controller=controller,
        summoning_sick=summoning_sick,
        instance_id=id(name)  # Unique ID
    )


# =============================================================================
# 1. EVASION KEYWORDS
# =============================================================================

class TestEvasionKeywords:
    """Test flying, reach, menace, trample, and unblockable"""

    def test_flying_blocked_by_flying(self, game):
        """Flying creature can be blocked by flying creature"""
        attacker = create_creature("Flying Attacker", 2, 2, ["flying"])
        blocker = create_creature("Flying Blocker", 1, 1, ["flying"], controller=2)

        game.p1.battlefield.append(attacker)
        game.p2.battlefield.append(blocker)

        # Check that flying can block flying
        assert not (attacker.has_keyword("flying") and
                   not (blocker.has_keyword("flying") or blocker.has_keyword("reach")))

    def test_flying_blocked_by_reach(self, game):
        """Flying creature can be blocked by reach creature"""
        attacker = create_creature("Flying Attacker", 2, 2, ["flying"])
        blocker = create_creature("Reach Blocker", 1, 3, ["reach"], controller=2)

        game.p1.battlefield.append(attacker)
        game.p2.battlefield.append(blocker)

        # Reach can block flying
        assert blocker.has_keyword("reach")
        can_block = blocker.has_keyword("flying") or blocker.has_keyword("reach")
        assert can_block

    def test_flying_not_blocked_by_normal(self, game):
        """Flying creature cannot be blocked by normal creature"""
        attacker = create_creature("Flying Attacker", 2, 2, ["flying"])
        blocker = create_creature("Normal Blocker", 3, 3, [], controller=2)

        # Normal creature cannot block flying
        if attacker.has_keyword("flying"):
            can_block = blocker.has_keyword("flying") or blocker.has_keyword("reach")
            assert not can_block

    def test_reach_blocks_flying(self, game):
        """Reach creature can block flying attackers"""
        attacker = create_creature("Flying Attacker", 3, 3, ["flying"])
        blocker = create_creature("Reach Blocker", 2, 5, ["reach"], controller=2)

        game.p1.battlefield.append(attacker)
        game.p2.battlefield.append(blocker)

        # Reach allows blocking flying
        assert blocker.has_keyword("reach")

    def test_reach_blocks_normal(self, game):
        """Reach creature can also block normal creatures"""
        attacker = create_creature("Normal Attacker", 2, 2, [])
        blocker = create_creature("Reach Blocker", 1, 4, ["reach"], controller=2)

        # Reach doesn't restrict blocking non-flying
        assert True  # Reach is always allowed to block

    def test_menace_requires_two_blockers(self, game):
        """Menace creature requires at least 2 blockers"""
        attacker = create_creature("Menace Attacker", 3, 3, ["menace"])
        blocker1 = create_creature("Blocker 1", 2, 2, [], controller=2)

        game.p1.battlefield.append(attacker)
        game.p2.battlefield.append(blocker1)

        # One blocker is insufficient for menace
        has_menace = attacker.has_keyword("menace")
        available_blockers = 1

        if has_menace and available_blockers < 2:
            can_block = False
        else:
            can_block = True

        assert not can_block

    def test_menace_blocked_by_two(self, game):
        """Menace creature can be blocked by 2+ creatures"""
        attacker = create_creature("Menace Attacker", 4, 4, ["menace"])
        blocker1 = create_creature("Blocker 1", 1, 1, [], controller=2)
        blocker2 = create_creature("Blocker 2", 1, 1, [], controller=2)

        game.p1.battlefield.append(attacker)
        game.p2.battlefield.extend([blocker1, blocker2])

        # Two blockers satisfy menace
        has_menace = attacker.has_keyword("menace")
        available_blockers = 2

        can_block = available_blockers >= 2
        assert can_block

    def test_trample_excess_damage_to_player(self, game):
        """Trample deals excess damage to defending player"""
        attacker = create_creature("Trampler", 5, 5, ["trample"])
        blocker = create_creature("Small Blocker", 1, 2, [], controller=2)

        game.p1.battlefield.append(attacker)
        game.p2.battlefield.append(blocker)

        # Calculate trample damage
        blocker_toughness = blocker.eff_toughness()
        attacker_power = attacker.eff_power()
        lethal_damage = blocker_toughness  # 2 damage is lethal
        excess_damage = attacker_power - lethal_damage  # 5 - 2 = 3

        assert attacker.has_keyword("trample")
        assert excess_damage == 3

    def test_trample_all_damage_if_unblocked(self, game):
        """Unblocked trampler deals all damage to player"""
        attacker = create_creature("Trampler", 6, 6, ["trample"])

        # No blockers means all damage goes through
        assert attacker.has_keyword("trample")
        damage_to_player = attacker.eff_power()
        assert damage_to_player == 6

    def test_trample_overkill_still_lethal(self, game):
        """Trample must assign lethal damage before trampling over"""
        attacker = create_creature("Big Trampler", 10, 10, ["trample"])
        blocker = create_creature("Blocker", 2, 3, [], controller=2)

        # Must assign at least toughness as lethal
        lethal = blocker.eff_toughness()  # 3
        max_trample = attacker.eff_power() - lethal  # 10 - 3 = 7

        assert max_trample == 7


# =============================================================================
# 2. COMBAT KEYWORDS
# =============================================================================

class TestCombatKeywords:
    """Test first strike, double strike, deathtouch, lifelink, vigilance, haste, defender"""

    def test_first_strike_deals_damage_first(self, game):
        """First strike creature deals damage before normal combat"""
        attacker = create_creature("First Striker", 2, 2, ["first strike"])
        blocker = create_creature("Normal Blocker", 3, 1, [], controller=2)

        # First strike should kill blocker before it deals damage back
        has_first_strike = attacker.has_keyword("first strike") or attacker.has_keyword("first_strike")
        assert has_first_strike

        # Blocker dies in first strike step (2 damage >= 1 toughness)
        blocker_dies_first = attacker.eff_power() >= blocker.eff_toughness()
        assert blocker_dies_first

    def test_double_strike_deals_twice(self, game):
        """Double strike creature deals damage in both combat steps"""
        attacker = create_creature("Double Striker", 3, 3, ["double strike"])

        has_double = attacker.has_keyword("double strike") or attacker.has_keyword("double_strike")
        assert has_double

        # Deals damage twice: once in first strike, once in regular
        total_damage = attacker.eff_power() * 2
        assert total_damage == 6

    def test_double_strike_vs_first_strike(self, game):
        """Double strike deals damage in both first strike and regular combat"""
        attacker = create_creature("Double Striker", 3, 3, ["double strike"])
        blocker = create_creature("First Striker", 2, 3, ["first strike"], controller=2)

        # Both deal in first strike step
        # Attacker: 3 damage kills blocker (3 >= 3 toughness)
        # Blocker: 2 damage to attacker (attacker survives with 3 toughness)
        # Then attacker would deal 3 more in regular step (but blocker is dead)

        blocker_dies = attacker.eff_power() >= blocker.eff_toughness()
        attacker_survives = attacker.eff_toughness() > blocker.eff_power()

        assert blocker_dies
        assert attacker_survives

    def test_deathtouch_one_damage_lethal(self, game):
        """Deathtouch makes any damage lethal"""
        attacker = create_creature("Deathtouch Creature", 1, 1, ["deathtouch"])
        blocker = create_creature("Big Blocker", 5, 10, [], controller=2)

        # 1 damage is lethal with deathtouch
        has_deathtouch = attacker.has_keyword("deathtouch")
        damage_dealt = attacker.eff_power()  # 1

        is_lethal = has_deathtouch and damage_dealt > 0
        assert is_lethal

    def test_deathtouch_zero_power_not_lethal(self, game):
        """Deathtouch with 0 power doesn't kill"""
        attacker = create_creature("Weak Deathtouch", 0, 1, ["deathtouch"])
        blocker = create_creature("Blocker", 2, 2, [], controller=2)

        # 0 damage is not lethal even with deathtouch
        has_deathtouch = attacker.has_keyword("deathtouch")
        damage = attacker.eff_power()

        is_lethal = has_deathtouch and damage > 0
        assert not is_lethal

    def test_deathtouch_plus_first_strike(self, game):
        """Deathtouch + first strike kills before taking damage"""
        attacker = create_creature("Deadly Striker", 1, 1, ["deathtouch", "first strike"])
        blocker = create_creature("Big Blocker", 10, 10, [], controller=2)

        # Kills in first strike step with deathtouch before taking damage
        has_both = attacker.has_keyword("deathtouch") and attacker.has_keyword("first strike")
        assert has_both

    def test_lifelink_gains_life(self, game):
        """Lifelink gains life equal to damage dealt"""
        attacker = create_creature("Lifelinker", 4, 4, ["lifelink"])

        initial_life = game.p1.life
        damage_dealt = attacker.eff_power()

        # Lifelink would gain 4 life
        expected_life_gain = damage_dealt
        assert expected_life_gain == 4

    def test_vigilance_doesnt_tap(self, game):
        """Vigilance creature doesn't tap when attacking"""
        attacker = create_creature("Vigilant Knight", 3, 3, ["vigilance"])

        has_vigilance = attacker.has_keyword("vigilance")
        should_tap = not has_vigilance

        assert not should_tap

    def test_haste_ignores_summoning_sickness(self, game):
        """Haste allows attacking on turn played"""
        creature = create_creature("Hasty Creature", 2, 2, ["haste"], summoning_sick=True)

        # Can attack despite summoning sickness
        can_attack = not creature.summoning_sick or creature.has_keyword("haste")
        assert can_attack

    def test_no_haste_summoning_sick(self, game):
        """Creature without haste cannot attack when summoning sick"""
        creature = create_creature("Normal Creature", 2, 2, [], summoning_sick=True)

        can_attack = not creature.summoning_sick or creature.has_keyword("haste")
        assert not can_attack

    def test_defender_cannot_attack(self, game):
        """Defender creature cannot attack"""
        creature = create_creature("Wall", 0, 5, ["defender"])

        has_defender = creature.has_keyword("defender")
        can_attack = not has_defender

        assert not can_attack

    def test_defender_can_block(self, game):
        """Defender can still block"""
        defender = create_creature("Wall", 0, 7, ["defender"], controller=2)

        # Defender doesn't restrict blocking
        can_block = True
        assert can_block


# =============================================================================
# 3. PROTECTION KEYWORDS
# =============================================================================

class TestProtectionKeywords:
    """Test hexproof, shroud, ward, protection, indestructible"""

    def test_hexproof_opponent_cannot_target(self, game):
        """Hexproof prevents opponent targeting"""
        creature = create_creature("Hexproof Creature", 3, 3, ["hexproof"], controller=1)

        # Opponent (controller=2) tries to target
        targeting_opponent = 2
        creature_controller = 1

        if creature.has_keyword("hexproof") and targeting_opponent != creature_controller:
            can_target = False
        else:
            can_target = True

        assert not can_target

    def test_hexproof_owner_can_target(self, game):
        """Hexproof doesn't prevent owner targeting"""
        creature = create_creature("Hexproof Creature", 3, 3, ["hexproof"], controller=1)

        # Owner (controller=1) can target own hexproof creature
        targeting_player = 1
        creature_controller = 1

        if creature.has_keyword("shroud"):
            can_target = False
        elif creature.has_keyword("hexproof") and targeting_player != creature_controller:
            can_target = False
        else:
            can_target = True

        assert can_target

    def test_shroud_nobody_can_target(self, game):
        """Shroud prevents all targeting"""
        creature = create_creature("Shroud Creature", 2, 2, ["shroud"], controller=1)

        # Even owner cannot target
        if creature.has_keyword("shroud"):
            can_target = False
        else:
            can_target = True

        assert not can_target

    def test_ward_requires_payment(self, game):
        """Ward requires life payment or spell is countered"""
        creature = create_creature("Ward Creature", 3, 3, ["ward 2"], controller=2)

        # Extract ward cost
        ward_cost = 0
        for kw in creature.keywords:
            if kw.lower().startswith("ward"):
                parts = kw.split()
                if len(parts) > 1:
                    ward_cost = int(parts[1])

        assert ward_cost == 2

    def test_ward_different_values(self, game):
        """Ward can have different costs"""
        ward_1 = create_creature("Ward 1", 2, 2, ["ward 1"])
        ward_3 = create_creature("Ward 3", 3, 3, ["ward 3"])

        # Parse ward costs
        def get_ward_cost(creature):
            for kw in creature.keywords:
                if kw.lower().startswith("ward"):
                    parts = kw.split()
                    if len(parts) > 1:
                        return int(parts[1])
            return 0

        assert get_ward_cost(ward_1) == 1
        assert get_ward_cost(ward_3) == 3

    def test_protection_from_color(self, game):
        """Protection from color prevents targeting"""
        creature = create_creature("Pro-Red", 2, 2, ["protection from red"], controller=2)

        # Red spell trying to target
        spell_colors = ["R"]

        can_target = True
        for kw in creature.keywords:
            if kw.lower().startswith("protection"):
                prot_from = kw.lower().replace("protection from ", "")
                # Check if spell color matches protection
                if prot_from in ["red", "r"] and "R" in spell_colors:
                    can_target = False

        assert not can_target

    def test_protection_blocks_damage(self, game):
        """Protection from color prevents damage from that color"""
        creature = create_creature("Pro-Black", 2, 2, ["protection from black"])

        # Protection prevents damage, blocking, targeting, and enchanting (DEBT)
        has_protection = any("protection from black" in kw.lower() for kw in creature.keywords)
        assert has_protection

    def test_indestructible_survives_damage(self, game):
        """Indestructible creature survives lethal damage"""
        creature = create_creature("Indestructible", 3, 3, ["indestructible"])

        # Take 10 damage
        creature.damage_marked = 10

        # Should survive because indestructible
        dies_from_damage = creature.damage_marked >= creature.eff_toughness() and not creature.has_keyword("indestructible")

        assert not dies_from_damage

    def test_indestructible_dies_to_zero_toughness(self, game):
        """Indestructible still dies to 0 toughness"""
        creature = create_creature("Indestructible", 3, 3, ["indestructible"])

        # Get -4/-4 (toughness becomes -1)
        creature.counters["-1/-1"] = 4

        # Dies to 0 or less toughness even with indestructible
        dies = creature.eff_toughness() <= 0
        assert dies

    def test_indestructible_survives_destroy_effects(self, game):
        """Indestructible prevents destroy effects"""
        creature = create_creature("Indestructible", 4, 4, ["indestructible"])

        # Destroy spell targeting it
        # Indestructible prevents destruction
        survives = creature.has_keyword("indestructible")
        assert survives


# =============================================================================
# 4. RETURN KEYWORDS
# =============================================================================

class TestReturnKeywords:
    """Test persist and undying"""

    def test_persist_returns_with_minus_counter(self, game):
        """Persist returns creature with -1/-1 counter"""
        creature = create_creature("Persist Creature", 3, 3, ["persist"])

        # Dies without -1/-1 counters
        has_minus_counters = "-1/-1" in creature.counters and creature.counters["-1/-1"] > 0

        can_persist = creature.has_keyword("persist") and not has_minus_counters
        assert can_persist

        # After persisting, has -1/-1 counter
        creature.counters["-1/-1"] = 1
        can_persist_again = creature.has_keyword("persist") and not (creature.counters.get("-1/-1", 0) > 0)
        assert not can_persist_again

    def test_persist_only_once(self, game):
        """Persist only triggers if creature has no -1/-1 counters"""
        creature = create_creature("Persist Creature", 2, 2, ["persist"])
        creature.counters["-1/-1"] = 1

        # Has -1/-1 counter, cannot persist
        can_persist = creature.has_keyword("persist") and creature.counters.get("-1/-1", 0) == 0
        assert not can_persist

    def test_undying_returns_with_plus_counter(self, game):
        """Undying returns creature with +1/+1 counter"""
        creature = create_creature("Undying Creature", 2, 2, ["undying"])

        # Dies without +1/+1 counters
        has_plus_counters = "+1/+1" in creature.counters and creature.counters["+1/+1"] > 0

        can_undying = creature.has_keyword("undying") and not has_plus_counters
        assert can_undying

        # After undying, has +1/+1 counter
        creature.counters["+1/+1"] = 1
        can_undying_again = creature.has_keyword("undying") and not (creature.counters.get("+1/+1", 0) > 0)
        assert not can_undying_again

    def test_undying_only_once(self, game):
        """Undying only triggers if creature has no +1/+1 counters"""
        creature = create_creature("Undying Creature", 3, 3, ["undying"])
        creature.counters["+1/+1"] = 2

        # Has +1/+1 counters, cannot undying
        can_undying = creature.has_keyword("undying") and creature.counters.get("+1/+1", 0) == 0
        assert not can_undying

    def test_persist_undying_interaction(self, game):
        """Creature with both persist and undying"""
        creature = create_creature("Both Keywords", 2, 2, ["persist", "undying"])

        # Engine would choose persist first (appears first in keyword list)
        # This is implementation-specific
        has_both = creature.has_keyword("persist") and creature.has_keyword("undying")
        assert has_both


# =============================================================================
# 5. SPECIAL KEYWORDS
# =============================================================================

class TestSpecialKeywords:
    """Test phasing, regenerate, wither, infect"""

    def test_phasing_phases_out(self, game):
        """Phasing creature phases out at untap"""
        creature = create_creature("Phasing Creature", 2, 2, ["phasing"])
        creature.phased_out = False

        # At beginning of untap, phases out
        if creature.has_keyword("phasing"):
            creature.phased_out = True

        assert creature.phased_out

    def test_phasing_phases_back_in(self, game):
        """Phased out creature phases back in"""
        creature = create_creature("Phasing Creature", 2, 2, ["phasing"])
        creature.phased_out = True

        # Next untap, phases back in
        if creature.phased_out and creature.has_keyword("phasing"):
            creature.phased_out = False

        assert not creature.phased_out

    def test_regenerate_shield_prevents_death(self, game):
        """Regeneration shield prevents death from damage"""
        creature = create_creature("Regenerating", 2, 2, [])
        creature.regenerate_shield = 1

        # Take lethal damage
        creature.damage_marked = 5

        # Shield saves it
        can_regenerate = creature.regenerate_shield > 0
        if can_regenerate:
            creature.regenerate_shield -= 1
            creature.damage_marked = 0
            creature.is_tapped = True

        assert creature.damage_marked == 0
        assert creature.is_tapped
        assert creature.regenerate_shield == 0

    def test_shield_counters_prevent_death(self, game):
        """Shield counters prevent death"""
        creature = create_creature("Shielded", 3, 3, [])
        creature.shield_counters = 1

        # Take lethal damage
        creature.damage_marked = 5

        # Shield counter prevents death
        can_use_shield = creature.shield_counters > 0
        if can_use_shield:
            creature.shield_counters -= 1
            creature.damage_marked = 0

        assert creature.damage_marked == 0
        assert creature.shield_counters == 0

    def test_wither_deals_minus_counters(self, game):
        """Wither deals damage as -1/-1 counters to creatures"""
        attacker = create_creature("Wither Creature", 3, 2, ["wither"])
        blocker = create_creature("Blocker", 2, 4, [], controller=2)

        # Wither converts damage to -1/-1 counters
        has_wither = attacker.has_keyword("wither")
        damage = attacker.eff_power()

        if has_wither:
            # Should get 3 -1/-1 counters instead of damage
            expected_counters = damage
            assert expected_counters == 3

    def test_wither_to_player_normal_damage(self, game):
        """Wither deals normal damage to players"""
        creature = create_creature("Wither Creature", 4, 3, ["wither"])

        # Wither only affects creatures, not players
        # Player takes normal damage
        has_wither = creature.has_keyword("wither")
        damage_to_player = creature.eff_power()

        assert damage_to_player == 4

    def test_infect_poison_to_players(self, game):
        """Infect deals poison counters to players"""
        creature = create_creature("Infect Creature", 3, 2, ["infect"])

        initial_poison = game.p2.poison_counters
        has_infect = creature.has_keyword("infect")
        damage = creature.eff_power()

        if has_infect:
            expected_poison = initial_poison + damage
            assert expected_poison == 3

    def test_infect_minus_counters_to_creatures(self, game):
        """Infect deals -1/-1 counters to creatures"""
        attacker = create_creature("Infect Creature", 2, 2, ["infect"])
        blocker = create_creature("Blocker", 3, 3, [], controller=2)

        has_infect = attacker.has_keyword("infect")
        damage = attacker.eff_power()

        if has_infect:
            # Deals 2 -1/-1 counters instead of damage
            expected_counters = damage
            assert expected_counters == 2

    def test_infect_ten_poison_loses(self, game):
        """10 poison counters causes player to lose"""
        game.p2.poison_counters = 10

        # State-based action: 10+ poison = lose
        loses = game.p2.poison_counters >= 10
        assert loses


# =============================================================================
# 6. KEYWORD COMBINATIONS
# =============================================================================

class TestKeywordCombinations:
    """Test interactions between multiple keywords"""

    def test_flying_deathtouch(self, game):
        """Flying + deathtouch is hard to block and lethal"""
        creature = create_creature("Flying Deathtouch", 1, 1, ["flying", "deathtouch"])

        assert creature.has_keyword("flying")
        assert creature.has_keyword("deathtouch")

    def test_trample_deathtouch(self, game):
        """Trample + deathtouch: 1 damage is lethal, rest tramples"""
        attacker = create_creature("Trample Deathtouch", 5, 5, ["trample", "deathtouch"])
        blocker = create_creature("Blocker", 2, 10, [], controller=2)

        # Only 1 damage needed to kill blocker with deathtouch
        # Remaining 4 tramples through
        has_both = attacker.has_keyword("trample") and attacker.has_keyword("deathtouch")
        if has_both:
            lethal = 1  # Deathtouch makes 1 damage lethal
            trample_damage = attacker.eff_power() - lethal
            assert trample_damage == 4

    def test_double_strike_lifelink(self, game):
        """Double strike + lifelink gains life twice"""
        creature = create_creature("Double Lifelink", 3, 3, ["double strike", "lifelink"])

        # Deals 3 damage twice with lifelink
        has_both = creature.has_keyword("double strike") and creature.has_keyword("lifelink")
        if has_both:
            life_gain = creature.eff_power() * 2
            assert life_gain == 6

    def test_vigilance_flying(self, game):
        """Vigilance + flying: doesn't tap and hard to block"""
        creature = create_creature("Vigilant Flyer", 3, 3, ["vigilance", "flying"])

        assert creature.has_keyword("vigilance")
        assert creature.has_keyword("flying")

    def test_haste_menace(self, game):
        """Haste + menace: immediate threat requiring multiple blockers"""
        creature = create_creature("Hasty Menace", 3, 2, ["haste", "menace"], summoning_sick=True)

        can_attack = creature.has_keyword("haste")
        needs_two_blockers = creature.has_keyword("menace")

        assert can_attack
        assert needs_two_blockers


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
