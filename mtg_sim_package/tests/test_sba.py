"""
Comprehensive Test Suite for State-Based Actions (SBAs)
========================================================

Tests ALL State-Based Actions per MTG Comprehensive Rules 704:
- Player loss conditions (life, poison, draw from empty library)
- Creature death (toughness, damage, deathtouch)
- Counter interactions (+1/+1 and -1/-1 cancellation)
- Planeswalker SBAs (loyalty, legend rule)
- Aura SBAs (illegal attachments)
- Token SBAs (tokens in non-battlefield zones)
- SBA loop (multiple SBAs in single check)

Uses pytest for comprehensive validation.
Target: 30+ test cases
"""

import pytest
import sys
sys.path.insert(0, '..')

from mtg_engine import (
    Card, ManaCost, Player, Game, Log, ManaPool
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def basic_game():
    """Create a basic game with minimal setup."""
    lands = [Card(name="Forest", card_type="land", produces=["G"]) for _ in range(40)]
    game = Game(
        lands[:20], "Player 1", "control",
        lands[20:], "Player 2", "control",
        verbose=False
    )
    return game


@pytest.fixture
def game_with_creatures():
    """Create a game with creatures on the battlefield."""
    lands = [Card(name="Plains", card_type="land", produces=["W"]) for _ in range(40)]
    game = Game(
        lands[:20], "Player 1", "midrange",
        lands[20:], "Player 2", "midrange",
        verbose=False
    )

    # Add creatures to P1 battlefield
    c1 = Card(
        name="Test Creature 1",
        mana_cost=ManaCost(generic=2, W=1),
        card_type="creature",
        power=3,
        toughness=3,
        instance_id=100
    )
    c2 = Card(
        name="Test Creature 2",
        mana_cost=ManaCost(generic=1, W=1),
        card_type="creature",
        power=2,
        toughness=2,
        instance_id=101
    )

    game.p1.battlefield.extend([c1, c2])

    return game


# =============================================================================
# PLAYER LOSS CONDITIONS (704.5a-c)
# =============================================================================

class TestPlayerLossConditions:
    """Test player loss conditions per MTG 704.5a-c"""

    def test_player_loses_at_zero_life(self, basic_game):
        """704.5a: Player at 0 life loses the game"""
        basic_game.p1.life = 0

        # Check state should detect loss
        result = basic_game.check_state()

        assert basic_game.winner == 2, "P2 should win when P1 at 0 life"
        assert result == False, "Game should be over"

    def test_player_loses_at_negative_life(self, basic_game):
        """704.5a: Player at negative life loses the game"""
        basic_game.p2.life = -5

        result = basic_game.check_state()

        assert basic_game.winner == 1, "P1 should win when P2 at negative life"
        assert result == False, "Game should be over"

    def test_player_loses_at_ten_poison_counters(self, basic_game):
        """704.5b: Player with 10+ poison counters loses"""
        basic_game.p1.poison_counters = 10

        result = basic_game.check_state()

        assert basic_game.winner == 2, "P2 should win when P1 has 10 poison"
        assert result == False, "Game should be over"

    def test_player_loses_above_ten_poison_counters(self, basic_game):
        """704.5b: Player with >10 poison counters loses"""
        basic_game.p2.poison_counters = 15

        result = basic_game.check_state()

        assert basic_game.winner == 1, "P1 should win when P2 has 15 poison"
        assert result == False, "Game should be over"

    def test_nine_poison_counters_does_not_lose(self, basic_game):
        """Player with 9 poison counters should NOT lose"""
        basic_game.p1.poison_counters = 9

        result = basic_game.check_state()

        assert basic_game.winner is None, "No winner yet with 9 poison"
        assert result == True, "Game should continue"

    def test_attempted_draw_from_empty_library_loses(self, basic_game):
        """704.5c: Player who attempted to draw from empty library loses"""
        basic_game.p1.library = []
        basic_game.p1.attempted_draw_from_empty = True

        result = basic_game.check_state()

        assert basic_game.winner == 2, "P2 should win when P1 drew from empty library"
        assert result == False, "Game should be over"

    def test_empty_library_without_draw_does_not_lose(self, basic_game):
        """Player with empty library but no draw attempt should not lose"""
        basic_game.p1.library = []
        basic_game.p1.attempted_draw_from_empty = False

        result = basic_game.check_state()

        assert basic_game.winner is None, "No winner with empty library (no draw attempt)"
        assert result == True, "Game should continue"

    def test_multiple_players_lose_simultaneously(self, basic_game):
        """When multiple loss conditions occur, first checked wins"""
        # Both players at 0 life - P1 checked first, so P2 wins
        basic_game.p1.life = 0
        basic_game.p2.life = 0

        result = basic_game.check_state()

        # In the engine, P1 is checked first, so P2 wins
        assert basic_game.winner == 2, "P2 should win (P1 checked first in SBA)"
        assert result == False, "Game should be over"


# =============================================================================
# CREATURE DEATH (704.5f-h)
# =============================================================================

class TestCreatureDeath:
    """Test creature death conditions per MTG 704.5f-h"""

    def test_creature_dies_with_zero_toughness(self, game_with_creatures):
        """704.5f: Creature with toughness <= 0 dies"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.toughness = 0

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield, "Creature should be removed"
        assert creature in game_with_creatures.p1.graveyard, "Creature should be in graveyard"

    def test_creature_dies_with_negative_toughness(self, game_with_creatures):
        """704.5f: Creature with negative toughness dies"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.toughness = -2

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield
        assert creature in game_with_creatures.p1.graveyard

    def test_creature_dies_from_lethal_damage(self, game_with_creatures):
        """704.5g: Creature with lethal damage dies"""
        creature = game_with_creatures.p1.battlefield[0]
        # Creature is 3/3, deal 3 damage
        creature.damage_marked = 3

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield
        assert creature in game_with_creatures.p1.graveyard

    def test_creature_dies_from_excess_damage(self, game_with_creatures):
        """Creature with damage >= toughness dies"""
        creature = game_with_creatures.p1.battlefield[0]
        # Creature is 3/3, deal 5 damage
        creature.damage_marked = 5

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield
        assert creature in game_with_creatures.p1.graveyard

    def test_creature_survives_non_lethal_damage(self, game_with_creatures):
        """Creature with damage < toughness survives"""
        creature = game_with_creatures.p1.battlefield[0]
        # Creature is 3/3, deal 2 damage
        creature.damage_marked = 2

        game_with_creatures.check_state()

        assert creature in game_with_creatures.p1.battlefield, "Creature should survive"
        assert creature not in game_with_creatures.p1.graveyard

    def test_creature_dies_from_deathtouch_damage(self, game_with_creatures):
        """704.5h: Creature with any deathtouch damage dies"""
        creature = game_with_creatures.p1.battlefield[0]
        # Creature is 3/3, but has deathtouch damage
        creature.damage_marked = 1
        creature.deathtouch_damage = True

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield
        assert creature in game_with_creatures.p1.graveyard

    def test_deathtouch_requires_damage(self, game_with_creatures):
        """Deathtouch flag without damage doesn't kill"""
        creature = game_with_creatures.p1.battlefield[0]
        # Has deathtouch flag but no damage
        creature.damage_marked = 0
        creature.deathtouch_damage = True

        game_with_creatures.check_state()

        assert creature in game_with_creatures.p1.battlefield, "Should survive without damage"

    def test_indestructible_prevents_lethal_damage_death(self, game_with_creatures):
        """Indestructible prevents death from damage"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.keywords.append("indestructible")
        creature.damage_marked = 10  # Lethal damage

        game_with_creatures.check_state()

        assert creature in game_with_creatures.p1.battlefield, "Indestructible should survive damage"
        assert creature not in game_with_creatures.p1.graveyard

    def test_indestructible_prevents_deathtouch_death(self, game_with_creatures):
        """Indestructible prevents death from deathtouch"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.keywords.append("indestructible")
        creature.damage_marked = 1
        creature.deathtouch_damage = True

        game_with_creatures.check_state()

        assert creature in game_with_creatures.p1.battlefield, "Indestructible should survive deathtouch"

    def test_indestructible_does_not_prevent_zero_toughness_death(self, game_with_creatures):
        """704.5f: Indestructible does NOT prevent 0 toughness death"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.keywords.append("indestructible")
        creature.toughness = 0

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield, "0 toughness kills even indestructible"
        assert creature in game_with_creatures.p1.graveyard

    def test_creature_with_minus_counters_zero_toughness(self, game_with_creatures):
        """Creature with enough -1/-1 counters to reach 0 toughness dies"""
        creature = game_with_creatures.p1.battlefield[0]
        # Creature is 3/3, add 3 -1/-1 counters
        creature.counters["-1/-1"] = 3

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield
        assert creature in game_with_creatures.p1.graveyard


# =============================================================================
# COUNTER INTERACTIONS (704.5q)
# =============================================================================

class TestCounterInteractions:
    """Test +1/+1 and -1/-1 counter annihilation per MTG 704.5q"""

    def test_plus_and_minus_counters_cancel(self, game_with_creatures):
        """704.5q: +1/+1 and -1/-1 counters cancel each other"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.counters["+1/+1"] = 3
        creature.counters["-1/-1"] = 2

        game_with_creatures.check_state()

        # Should have 1 +1/+1 counter remaining
        assert creature.counters.get("+1/+1", 0) == 1, "Should have 1 +1/+1 counter"
        assert creature.counters.get("-1/-1", 0) == 0, "Should have 0 -1/-1 counters"

    def test_minus_counters_cancel_plus_counters(self, game_with_creatures):
        """More -1/-1 than +1/+1 leaves -1/-1 counters"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.counters["+1/+1"] = 2
        creature.counters["-1/-1"] = 5

        game_with_creatures.check_state()

        assert creature.counters.get("+1/+1", 0) == 0, "Should have 0 +1/+1 counters"
        assert creature.counters.get("-1/-1", 0) == 3, "Should have 3 -1/-1 counters"

    def test_equal_counters_cancel_completely(self, game_with_creatures):
        """Equal numbers of +1/+1 and -1/-1 cancel completely"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.counters["+1/+1"] = 4
        creature.counters["-1/-1"] = 4

        game_with_creatures.check_state()

        assert "+1/+1" not in creature.counters or creature.counters["+1/+1"] == 0
        assert "-1/-1" not in creature.counters or creature.counters["-1/-1"] == 0

    def test_counter_cancellation_then_death(self, game_with_creatures):
        """Counters cancel, then check if creature dies from 0 toughness"""
        creature = game_with_creatures.p1.battlefield[0]
        # Creature is 3/3
        creature.counters["+1/+1"] = 1
        creature.counters["-1/-1"] = 4  # Net: -3/-3, making it 0/0

        game_with_creatures.check_state()

        # First counters cancel (leaving 3 -1/-1), then creature dies
        assert creature not in game_with_creatures.p1.battlefield
        assert creature in game_with_creatures.p1.graveyard


# =============================================================================
# PLANESWALKER SBAs (704.5i, 704.5j)
# =============================================================================

class TestPlaneswalkerSBAs:
    """Test planeswalker State-Based Actions"""

    def test_planeswalker_dies_at_zero_loyalty(self, basic_game):
        """704.5i: Planeswalker with 0 loyalty dies"""
        pw = Card(
            name="Test Walker",
            mana_cost=ManaCost(generic=3, U=1),
            card_type="planeswalker",
            loyalty=3,
            loyalty_abilities=["+1:draw_1", "-2:damage_2_any"],
            instance_id=100
        )
        pw.counters["loyalty"] = 0
        basic_game.p1.battlefield.append(pw)

        basic_game.check_state()

        assert pw not in basic_game.p1.battlefield
        assert pw in basic_game.p1.graveyard

    def test_planeswalker_dies_at_negative_loyalty(self, basic_game):
        """704.5i: Planeswalker with negative loyalty dies"""
        pw = Card(
            name="Test Walker",
            mana_cost=ManaCost(generic=3, U=1),
            card_type="planeswalker",
            loyalty=3,
            loyalty_abilities=["+1:draw_1"],
            instance_id=100
        )
        pw.counters["loyalty"] = -2
        basic_game.p1.battlefield.append(pw)

        basic_game.check_state()

        assert pw not in basic_game.p1.battlefield
        assert pw in basic_game.p1.graveyard

    def test_planeswalker_survives_with_one_loyalty(self, basic_game):
        """Planeswalker with 1 loyalty survives"""
        pw = Card(
            name="Test Walker",
            mana_cost=ManaCost(generic=3),
            card_type="planeswalker",
            loyalty=3,
            loyalty_abilities=["+1:draw_1"],
            instance_id=100
        )
        pw.counters["loyalty"] = 1
        basic_game.p1.battlefield.append(pw)

        basic_game.check_state()

        assert pw in basic_game.p1.battlefield, "Should survive with 1 loyalty"
        assert pw not in basic_game.p1.graveyard

    def test_legend_rule_keeps_newest_planeswalker(self, basic_game):
        """704.5j: Legend rule - controller keeps one, sacrifices others (keeps newest)"""
        pw1 = Card(
            name="Jace, the Mind Sculptor",
            mana_cost=ManaCost(generic=2, U=2),
            card_type="planeswalker",
            loyalty=3,
            loyalty_abilities=["+2:draw_1"],
            keywords=["legendary"],
            instance_id=100
        )
        pw1.counters["loyalty"] = 3

        pw2 = Card(
            name="Jace, the Mind Sculptor",
            mana_cost=ManaCost(generic=2, U=2),
            card_type="planeswalker",
            loyalty=3,
            loyalty_abilities=["+2:draw_1"],
            keywords=["legendary"],
            instance_id=101  # Higher ID = newer
        )
        pw2.counters["loyalty"] = 3

        basic_game.p1.battlefield.extend([pw1, pw2])

        basic_game.check_state()

        # Should keep pw2 (newer instance_id)
        assert pw2 in basic_game.p1.battlefield, "Should keep newer planeswalker"
        assert pw1 not in basic_game.p1.battlefield, "Should sacrifice older planeswalker"
        assert pw1 in basic_game.p1.graveyard

    def test_legend_rule_different_names_both_survive(self, basic_game):
        """Legend rule only applies to same name - different names survive"""
        pw1 = Card(
            name="Jace, the Mind Sculptor",
            mana_cost=ManaCost(generic=2, U=2),
            card_type="planeswalker",
            loyalty=3,
            keywords=["legendary"],
            instance_id=100
        )
        pw1.counters["loyalty"] = 3

        pw2 = Card(
            name="Liliana, Death's Majesty",
            mana_cost=ManaCost(generic=3, B=2),
            card_type="planeswalker",
            loyalty=5,
            keywords=["legendary"],
            instance_id=101
        )
        pw2.counters["loyalty"] = 5

        basic_game.p1.battlefield.extend([pw1, pw2])

        basic_game.check_state()

        assert pw1 in basic_game.p1.battlefield, "Different names should both survive"
        assert pw2 in basic_game.p1.battlefield


# =============================================================================
# AURA SBAs (704.5m)
# =============================================================================

class TestAuraSBAs:
    """Test Aura State-Based Actions per MTG 704.5m"""

    def test_aura_dies_when_enchanted_permanent_leaves(self, game_with_creatures):
        """704.5m: Aura without legal attached permanent goes to graveyard"""
        creature = game_with_creatures.p1.battlefield[0]

        aura = Card(
            name="Test Aura",
            mana_cost=ManaCost(generic=1, W=1),
            card_type="enchantment",
            subtype="aura",
            instance_id=200,
            attached_to=creature.instance_id
        )
        game_with_creatures.p1.battlefield.append(aura)

        # Remove the creature
        game_with_creatures.p1.battlefield.remove(creature)
        game_with_creatures.p1.graveyard.append(creature)

        game_with_creatures.check_state()

        assert aura not in game_with_creatures.p1.battlefield, "Aura should be removed"
        assert aura in game_with_creatures.p1.graveyard, "Aura should go to graveyard"

    def test_aura_survives_with_legal_attachment(self, game_with_creatures):
        """Aura with legal attachment survives"""
        creature = game_with_creatures.p1.battlefield[0]

        aura = Card(
            name="Test Aura",
            mana_cost=ManaCost(generic=1, W=1),
            card_type="enchantment",
            subtype="aura",
            instance_id=200,
            attached_to=creature.instance_id
        )
        game_with_creatures.p1.battlefield.append(aura)

        game_with_creatures.check_state()

        assert aura in game_with_creatures.p1.battlefield, "Aura should survive"
        assert aura not in game_with_creatures.p1.graveyard

    def test_equipment_survives_when_creature_dies(self, game_with_creatures):
        """Equipment stays on battlefield when equipped creature dies (not Aura)"""
        creature = game_with_creatures.p1.battlefield[0]

        equipment = Card(
            name="Test Equipment",
            mana_cost=ManaCost(generic=2),
            card_type="artifact",
            subtype="equipment",
            instance_id=200,
            attached_to=creature.instance_id
        )
        game_with_creatures.p1.battlefield.append(equipment)

        # Remove the creature
        game_with_creatures.p1.battlefield.remove(creature)
        game_with_creatures.p1.graveyard.append(creature)

        game_with_creatures.check_state()

        # Equipment should stay on battlefield (just unattached)
        assert equipment in game_with_creatures.p1.battlefield, "Equipment should stay"
        assert equipment not in game_with_creatures.p1.graveyard


# =============================================================================
# TOKEN SBAs (704.5d)
# =============================================================================

class TestTokenSBAs:
    """Test Token State-Based Actions per MTG 704.5d"""

    def test_token_ceases_to_exist_in_graveyard(self, basic_game):
        """704.5d: Token in graveyard ceases to exist"""
        token = Card(
            name="Soldier Token",
            card_type="creature",
            power=1,
            toughness=1,
            instance_id=100,
            is_token=True
        )
        basic_game.p1.graveyard.append(token)

        basic_game.check_state()

        assert token not in basic_game.p1.graveyard, "Token should cease to exist"

    def test_token_ceases_to_exist_in_exile(self, basic_game):
        """Token in exile ceases to exist"""
        token = Card(
            name="Soldier Token",
            card_type="creature",
            power=1,
            toughness=1,
            instance_id=100,
            is_token=True
        )
        basic_game.p1.exile.append(token)

        basic_game.check_state()

        assert token not in basic_game.p1.exile, "Token should cease to exist"

    def test_token_ceases_to_exist_in_hand(self, basic_game):
        """Token in hand ceases to exist"""
        token = Card(
            name="Soldier Token",
            card_type="creature",
            power=1,
            toughness=1,
            instance_id=100,
            is_token=True
        )
        basic_game.p1.hand.append(token)

        basic_game.check_state()

        assert token not in basic_game.p1.hand, "Token should cease to exist"

    def test_token_survives_on_battlefield(self, basic_game):
        """Token on battlefield survives"""
        token = Card(
            name="Soldier Token",
            card_type="creature",
            power=1,
            toughness=1,
            instance_id=100,
            is_token=True
        )
        basic_game.p1.battlefield.append(token)

        basic_game.check_state()

        assert token in basic_game.p1.battlefield, "Token should stay on battlefield"

    def test_token_dies_and_ceases_immediately(self, basic_game):
        """Token that dies goes to graveyard then ceases to exist"""
        token = Card(
            name="Soldier Token",
            card_type="creature",
            power=1,
            toughness=1,
            instance_id=100,
            is_token=True
        )
        token.damage_marked = 1  # Lethal damage
        basic_game.p1.battlefield.append(token)

        basic_game.check_state()

        # Token should be removed from battlefield and not in graveyard
        assert token not in basic_game.p1.battlefield
        assert token not in basic_game.p1.graveyard, "Token shouldn't persist in graveyard"


# =============================================================================
# SBA LOOP (704.3)
# =============================================================================

class TestSBALoop:
    """Test that SBAs loop until none apply (MTG 704.3)"""

    def test_multiple_sbas_in_single_check(self, basic_game):
        """Multiple SBAs should be processed in one check"""
        # Create two creatures that will die
        c1 = Card(
            name="Dying Creature 1",
            card_type="creature",
            power=2,
            toughness=2,
            instance_id=100
        )
        c1.damage_marked = 2  # Lethal

        c2 = Card(
            name="Dying Creature 2",
            card_type="creature",
            power=1,
            toughness=1,
            instance_id=101
        )
        c2.toughness = 0

        basic_game.p1.battlefield.extend([c1, c2])

        basic_game.check_state()

        # Both should be removed simultaneously
        assert c1 not in basic_game.p1.battlefield
        assert c2 not in basic_game.p1.battlefield
        assert c1 in basic_game.p1.graveyard
        assert c2 in basic_game.p1.graveyard

    def test_sba_loop_counter_cancellation_then_death(self, basic_game):
        """SBA loop: counters cancel in first pass, creature dies in second pass"""
        creature = Card(
            name="Test Creature",
            card_type="creature",
            power=2,
            toughness=2,
            instance_id=100
        )
        # +1/+1 and -1/-1 will cancel, leaving net -2/-2, making it 0/0
        creature.counters["+1/+1"] = 1
        creature.counters["-1/-1"] = 3

        basic_game.p1.battlefield.append(creature)

        basic_game.check_state()

        # First loop: counters cancel (leaving 2 -1/-1)
        # Second loop: creature dies from 0 toughness
        assert creature not in basic_game.p1.battlefield
        assert creature in basic_game.p1.graveyard

    def test_sba_checks_until_none_apply(self, basic_game):
        """SBA checking loops until no more SBAs apply"""
        # Create token that will die and go to graveyard, then cease to exist
        token = Card(
            name="Dying Token",
            card_type="creature",
            power=1,
            toughness=1,
            instance_id=100,
            is_token=True
        )
        token.damage_marked = 1  # Lethal damage
        basic_game.p1.battlefield.append(token)

        basic_game.check_state()

        # First loop: token dies, goes to graveyard
        # Second loop: token in graveyard ceases to exist
        assert token not in basic_game.p1.battlefield
        assert token not in basic_game.p1.graveyard

    def test_multiple_players_multiple_sbas(self, basic_game):
        """Multiple SBAs across both players"""
        # P1 has dying creature
        c1 = Card(
            name="P1 Creature",
            card_type="creature",
            power=2,
            toughness=2,
            instance_id=100
        )
        c1.damage_marked = 2
        basic_game.p1.battlefield.append(c1)

        # P2 has dying planeswalker
        pw = Card(
            name="P2 Walker",
            card_type="planeswalker",
            loyalty=3,
            instance_id=101
        )
        pw.counters["loyalty"] = 0
        basic_game.p2.battlefield.append(pw)

        basic_game.check_state()

        assert c1 not in basic_game.p1.battlefield
        assert c1 in basic_game.p1.graveyard
        assert pw not in basic_game.p2.battlefield
        assert pw in basic_game.p2.graveyard


# =============================================================================
# EDGE CASES AND COMPLEX SCENARIOS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and complex SBA scenarios"""

    def test_regeneration_prevents_death(self, game_with_creatures):
        """Creature with regeneration shield doesn't die from lethal damage"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.damage_marked = 3  # Lethal (3/3 creature)
        creature.regenerate_shield = 1

        game_with_creatures.check_state()

        assert creature in game_with_creatures.p1.battlefield, "Should regenerate"
        assert creature.is_tapped == True, "Should be tapped after regeneration"
        assert creature.damage_marked == 0, "Damage should be removed"
        assert creature.regenerate_shield == 0, "Shield should be consumed"

    def test_shield_counter_prevents_death(self, game_with_creatures):
        """Creature with shield counter doesn't die (D&D mechanic)"""
        creature = game_with_creatures.p1.battlefield[0]
        creature.damage_marked = 3  # Lethal
        creature.shield_counters = 1

        game_with_creatures.check_state()

        assert creature in game_with_creatures.p1.battlefield, "Should survive with shield"
        assert creature.shield_counters == 0, "Shield should be consumed"
        assert creature.damage_marked == 0, "Damage should be removed"

    def test_no_false_positives_healthy_board(self, game_with_creatures):
        """Healthy board state shouldn't trigger any SBAs"""
        initial_p1_bf = list(game_with_creatures.p1.battlefield)
        initial_p2_bf = list(game_with_creatures.p2.battlefield)

        result = game_with_creatures.check_state()

        assert result == True, "Game should continue"
        assert game_with_creatures.winner is None, "No winner"
        assert game_with_creatures.p1.battlefield == initial_p1_bf, "P1 battlefield unchanged"
        assert game_with_creatures.p2.battlefield == initial_p2_bf, "P2 battlefield unchanged"

    def test_creature_with_both_damage_and_counters(self, game_with_creatures):
        """Creature with damage AND -1/-1 counters (combined lethality)"""
        creature = game_with_creatures.p1.battlefield[0]
        # Creature is 3/3
        creature.damage_marked = 2
        creature.counters["-1/-1"] = 2  # Makes it 1/1, so 2 damage is lethal

        game_with_creatures.check_state()

        assert creature not in game_with_creatures.p1.battlefield
        assert creature in game_with_creatures.p1.graveyard


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
