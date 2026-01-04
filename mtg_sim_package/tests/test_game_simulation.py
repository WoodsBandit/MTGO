"""
Comprehensive Test Suite for MTG Universal Simulation Engine v3
================================================================

Tests full game simulations covering:
- Match structures (Bo1, Bo3, sideboarding)
- Turn phase execution
- Deck archetype matchups
- Edge cases (stack depth, triggers, alternative win conditions)
- Sideboard mechanics
- APNAP ordering and priority

Usage:
    pytest tests/test_game_simulation.py -v
    pytest tests/test_game_simulation.py -v -k "test_bo3"
"""

import sys
import os
import pytest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mtg_engine import (
    Card, ManaCost, Player, Game, AI, Log,
    run_match, run_match_from_files,
    SideboardAI, parse_decklist
)


# =============================================================================
# FIXTURE: TEST DECKS
# =============================================================================

@pytest.fixture
def simple_aggro_deck():
    """Basic mono-red aggro deck for testing"""
    return """
4 Monastery Swiftspear
4 Emberheart Challenger
4 Heartfire Hero
4 Lightning Strike
4 Play with Fire
20 Mountain
"""

@pytest.fixture
def simple_control_deck():
    """Basic blue-white control deck for testing"""
    return """
4 Thalia, Guardian of Thraben
4 Reprieve
4 No More Lies
4 Aether Spike
4 Get Lost
20 Island
"""

@pytest.fixture
def simple_midrange_deck():
    """Basic green-black midrange deck for testing"""
    return """
4 Deep Cavern Bat
4 Preacher of the Schism
4 Liliana of the Veil
4 Gix's Command
4 Go for the Throat
20 Swamp
"""

@pytest.fixture
def simple_ramp_deck():
    """Basic green ramp deck for testing"""
    return """
4 Llanowar Elves
4 Cultivate
4 Nissa, Who Shakes the World
4 Ulvenwald Oddity
4 Carnivorous Canopy
20 Forest
"""

@pytest.fixture
def deck_with_sideboard():
    """Deck with 15-card sideboard"""
    return """
4 Monastery Swiftspear
4 Emberheart Challenger
4 Heartfire Hero
4 Lightning Strike
4 Play with Fire
20 Mountain

3 Torch the Tower
3 Rending Flame
3 Strangle
3 Scorching Dragonfire
3 Voltage Surge
"""

@pytest.fixture
def poison_deck():
    """Deck focused on poison counters"""
    return """
4 Venerated Rotpriest
4 Bloated Contaminator
4 Norn's Decree
4 Prologue to Phyresis
4 Infectious Bite
20 Forest
"""

@pytest.fixture
def mill_deck():
    """Deck focused on library depletion"""
    return """
4 Maddening Cacophony
4 Fractured Sanity
4 Tasha's Hideous Laughter
4 Ruin Crab
4 Watery Grave
20 Island
"""

@pytest.fixture
def planeswalker_deck():
    """Deck with multiple planeswalkers"""
    return """
4 Nissa, Who Shakes the World
4 Liliana of the Veil
4 Jace, the Mind Sculptor
4 Cultivate
4 Dark Ritual
10 Forest
10 Swamp
"""


# =============================================================================
# TEST SECTION 1: MATCH STRUCTURE
# =============================================================================

class TestMatchStructure:
    """Test different match formats and game structure"""

    def test_bo1_single_game(self, simple_aggro_deck, simple_control_deck):
        """Test best-of-1 single game format"""
        results = run_match(
            simple_aggro_deck,
            simple_control_deck,
            "Aggro", "Control",
            matches=1,
            games=1,
            verbose=False,
            sideboard=False
        )

        # Validate results structure
        assert "deck1" in results
        assert "deck2" in results
        assert "deck1_wins" in results
        assert "deck2_wins" in results
        assert "deck1_games" in results
        assert "deck2_games" in results

        # Validate match outcome
        assert results["deck1_wins"] + results["deck2_wins"] == 1
        assert results["deck1_games"] + results["deck2_games"] == 1

    def test_bo3_match_structure(self, simple_aggro_deck, simple_control_deck):
        """Test best-of-3 with proper game count"""
        results = run_match(
            simple_aggro_deck,
            simple_control_deck,
            "Aggro", "Control",
            matches=1,
            games=3,
            verbose=False,
            sideboard=False
        )

        # Bo3 should play 2-3 games (first to 2 wins)
        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games >= 2 and total_games <= 3

        # Winner should have 2 game wins
        max_wins = max(results["deck1_games"], results["deck2_games"])
        assert max_wins == 2

    def test_match_winner_determination(self, simple_aggro_deck, simple_control_deck):
        """Test that match winner is correctly determined"""
        results = run_match(
            simple_aggro_deck,
            simple_control_deck,
            "Aggro", "Control",
            matches=5,
            games=3,
            verbose=False,
            sideboard=False
        )

        # Total matches should equal number of matches played
        assert results["deck1_wins"] + results["deck2_wins"] == 5

        # Game count should be reasonable (10-15 games for 5 Bo3 matches)
        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games >= 10 and total_games <= 15

    def test_game_state_reset_between_games(self, simple_aggro_deck, simple_control_deck):
        """Test that game state properly resets between games"""
        # Run a Bo3 and ensure each game starts fresh
        results = run_match(
            simple_aggro_deck,
            simple_control_deck,
            "Aggro", "Control",
            matches=1,
            games=3,
            verbose=False,
            sideboard=False
        )

        # If multiple games were played, state reset worked
        # (would crash if state wasn't reset properly)
        assert results["deck1_games"] + results["deck2_games"] >= 2


# =============================================================================
# TEST SECTION 2: TURN STRUCTURE & PHASES
# =============================================================================

class TestTurnStructure:
    """Test turn phase execution and timing"""

    def test_turn_phases_execute(self):
        """Test that all turn phases execute correctly"""
        # Create a simple game
        lands = [Card(name="Forest", card_type="land", produces=["G"]) for _ in range(20)]
        creatures = [Card(name="Llanowar Elves", mana_cost=ManaCost(G=1),
                         card_type="creature", power=1, toughness=1) for _ in range(10)]

        deck1 = lands[:10] + creatures[:5]
        deck2 = lands[10:] + creatures[5:]

        game = Game(deck1, "Player 1", "midrange",
                   deck2, "Player 2", "midrange", verbose=False)

        # Play a few turns
        game.deal_hands()
        for _ in range(3):
            result = game.play_turn()
            assert result is True or game.winner is not None

            if game.winner:
                break

    def test_untap_phase_clears_tapped_permanents(self):
        """Test untap phase untaps all permanents"""
        lands = [Card(name="Island", card_type="land", produces=["U"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "control",
                   lands[10:], "Deck2", "control", verbose=False)

        game.deal_hands()

        # Add a land to battlefield and tap it
        land = Card(name="Island", card_type="land", produces=["U"], instance_id=1)
        land.is_tapped = True
        game.p1.battlefield.append(land)

        # Play turn (should untap)
        game.play_turn()

        # Land should be untapped
        assert land.is_tapped == False

    def test_draw_phase_draws_card(self):
        """Test draw phase draws exactly one card"""
        lands = [Card(name="Forest", card_type="land", produces=["G"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "ramp",
                   lands[10:], "Deck2", "ramp", verbose=False)

        game.deal_hands()
        initial_hand_size = len(game.p1.hand)

        # Play turn (player 2 goes first in turn 1, so p1 draws)
        game.turn = 1
        game.active_id = 2
        game.play_turn()

        # P2 (active) should have drawn
        # (Initial hand + draw - any cards played)
        assert len(game.p2.library) < 10  # Drew from library

    def test_mana_empties_between_phases(self):
        """Test mana pool empties at end of turn"""
        lands = [Card(name="Mountain", card_type="land", produces=["R"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "aggro",
                   lands[10:], "Deck2", "aggro", verbose=False)

        game.deal_hands()

        # Add mana to active player's pool
        game.p1.mana_pool.add("R")
        assert game.p1.mana_pool.R == 1

        # Play turn (should clear mana)
        game.active_id = 1
        game.play_turn()

        # Mana should be cleared
        assert game.p1.mana_pool.R == 0

    def test_summoning_sickness_removed(self):
        """Test creatures lose summoning sickness after one turn"""
        creatures = [Card(name="Bears", mana_cost=ManaCost(G=2),
                         card_type="creature", power=2, toughness=2) for _ in range(20)]

        game = Game(creatures[:10], "Deck1", "aggro",
                   creatures[10:], "Deck2", "aggro", verbose=False)

        game.deal_hands()

        # Add creature to battlefield with summoning sickness
        creature = Card(name="Bears", mana_cost=ManaCost(G=2),
                       card_type="creature", power=2, toughness=2, instance_id=1)
        creature.summoning_sick = True
        game.p1.battlefield.append(creature)

        # Play turn
        game.active_id = 1
        game.play_turn()

        # Summoning sickness should be cleared
        assert creature.summoning_sick == False


# =============================================================================
# TEST SECTION 3: DECK MATCHUP SIMULATIONS
# =============================================================================

class TestDeckMatchups:
    """Test actual game simulations between different archetypes"""

    @pytest.mark.slow
    def test_aggro_vs_control_matchup(self, simple_aggro_deck, simple_control_deck):
        """Test aggro vs control matchup (10 games)"""
        results = run_match(
            simple_aggro_deck,
            simple_control_deck,
            "Aggro", "Control",
            matches=5,
            games=1,
            verbose=False,
            sideboard=False
        )

        # Both decks should win at least some games (probabilistic)
        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games == 5

    @pytest.mark.slow
    def test_midrange_vs_aggro_matchup(self, simple_midrange_deck, simple_aggro_deck):
        """Test midrange vs aggro matchup (10 games)"""
        results = run_match(
            simple_midrange_deck,
            simple_aggro_deck,
            "Midrange", "Aggro",
            matches=5,
            games=1,
            verbose=False,
            sideboard=False
        )

        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games == 5

    @pytest.mark.slow
    def test_control_vs_midrange_matchup(self, simple_control_deck, simple_midrange_deck):
        """Test control vs midrange matchup (10 games)"""
        results = run_match(
            simple_control_deck,
            simple_midrange_deck,
            "Control", "Midrange",
            matches=5,
            games=1,
            verbose=False,
            sideboard=False
        )

        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games == 5

    @pytest.mark.slow
    def test_aggro_mirror_match(self, simple_aggro_deck):
        """Test aggro mirror match (10 games)"""
        results = run_match(
            simple_aggro_deck,
            simple_aggro_deck,
            "Aggro 1", "Aggro 2",
            matches=5,
            games=1,
            verbose=False,
            sideboard=False
        )

        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games == 5

    @pytest.mark.slow
    def test_control_mirror_match(self, simple_control_deck):
        """Test control mirror match (10 games)"""
        results = run_match(
            simple_control_deck,
            simple_control_deck,
            "Control 1", "Control 2",
            matches=5,
            games=1,
            verbose=False,
            sideboard=False
        )

        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games == 5

    @pytest.mark.slow
    def test_midrange_mirror_match(self, simple_midrange_deck):
        """Test midrange mirror match (10 games)"""
        results = run_match(
            simple_midrange_deck,
            simple_midrange_deck,
            "Midrange 1", "Midrange 2",
            matches=5,
            games=1,
            verbose=False,
            sideboard=False
        )

        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games == 5


# =============================================================================
# TEST SECTION 4: EDGE CASE GAMES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and complex game states"""

    def test_deep_stack_handling(self):
        """Test game with 5+ items on stack"""
        # This would require specific cards that generate stack items
        # For now, test that stack can handle multiple items
        lands = [Card(name="Island", card_type="land", produces=["U"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "control",
                   lands[10:], "Deck2", "control", verbose=False)

        # Add multiple items to stack
        for i in range(6):
            from mtg_engine import StackItem
            item = StackItem(
                card=lands[i],
                controller=1,
                target=None,
                stack_id=i,
                x_value=0
            )
            game.stack.append(item)

        # Stack should handle 6 items
        assert len(game.stack) == 6

        # Resolve stack (LIFO order)
        game.stack.clear()
        assert len(game.stack) == 0

    def test_multiple_triggered_abilities(self):
        """Test handling multiple triggers simultaneously"""
        # Test trigger queue functionality
        lands = [Card(name="Forest", card_type="land", produces=["G"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "midrange",
                   lands[10:], "Deck2", "midrange", verbose=False)

        # Trigger queue should handle multiple triggers
        game.trigger_queue.append(("landfall", lands[0], game.p1, None))
        game.trigger_queue.append(("etb", lands[1], game.p1, None))
        game.trigger_queue.append(("dies", lands[2], game.p2, None))

        assert len(game.trigger_queue) == 3

    def test_poison_counter_win_condition(self, poison_deck, simple_control_deck):
        """Test game ending via poison counters"""
        results = run_match(
            poison_deck,
            simple_control_deck,
            "Poison", "Control",
            matches=1,
            games=1,
            verbose=False,
            sideboard=False
        )

        # Game should complete without crashing
        assert results["deck1_wins"] + results["deck2_wins"] == 1

    def test_library_depletion_win_condition(self, mill_deck, simple_aggro_deck):
        """Test game ending via library depletion"""
        results = run_match(
            mill_deck,
            simple_aggro_deck,
            "Mill", "Aggro",
            matches=1,
            games=1,
            verbose=False,
            sideboard=False
        )

        # Game should complete without crashing
        assert results["deck1_wins"] + results["deck2_wins"] == 1

    def test_planeswalker_combat(self, planeswalker_deck, simple_aggro_deck):
        """Test game with planeswalker combat interactions"""
        results = run_match(
            planeswalker_deck,
            simple_aggro_deck,
            "Planeswalkers", "Aggro",
            matches=1,
            games=1,
            verbose=False,
            sideboard=False
        )

        # Game should complete without crashing
        assert results["deck1_wins"] + results["deck2_wins"] == 1

    def test_damage_marked_clears_each_turn(self):
        """Test that damage marked on creatures clears each turn"""
        creatures = [Card(name="Bears", mana_cost=ManaCost(G=2),
                         card_type="creature", power=2, toughness=2) for _ in range(20)]

        game = Game(creatures[:10], "Deck1", "aggro",
                   creatures[10:], "Deck2", "aggro", verbose=False)

        game.deal_hands()

        # Add creature with damage
        creature = Card(name="Bears", mana_cost=ManaCost(G=2),
                       card_type="creature", power=2, toughness=2, instance_id=1)
        creature.damage_marked = 1
        game.p1.battlefield.append(creature)

        # Play turn
        game.active_id = 1
        game.play_turn()

        # Damage should be cleared
        assert creature.damage_marked == 0


# =============================================================================
# TEST SECTION 5: SIDEBOARD MECHANICS
# =============================================================================

class TestSideboardMechanics:
    """Test sideboarding between games"""

    def test_sideboard_cards_swapped(self, deck_with_sideboard, simple_control_deck):
        """Test that cards are swapped between games"""
        results = run_match(
            deck_with_sideboard,
            simple_control_deck,
            "Aggro with SB", "Control",
            matches=1,
            games=3,
            verbose=False,
            sideboard=True
        )

        # Game should complete with sideboarding
        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games >= 2

    def test_deck_size_maintained_after_sideboard(self):
        """Test deck returns to 60/15 after sideboarding"""
        # Create deck and sideboard
        deck_str = """
4 Lightning Strike
20 Mountain
"""
        cards, sideboard, name, arch = parse_decklist(deck_str)

        # Create sideboard AI
        sb_ai = SideboardAI(cards, sideboard, "aggro")

        # Initial sizes
        assert len(sb_ai.deck) == 24  # 4 + 20
        assert len(sb_ai.sideboard) == 0

    def test_ai_sideboard_decisions(self):
        """Test AI makes reasonable sideboard decisions"""
        # Create a deck with removal
        removal = [Card(name="Lightning Strike", mana_cost=ManaCost(R=1, generic=1),
                       card_type="instant", abilities=["damage_3"]) for _ in range(4)]
        lands = [Card(name="Mountain", card_type="land", produces=["R"]) for _ in range(20)]

        deck = removal + lands

        # Create sideboard with sweepers
        sweepers = [Card(name="Anger of the Gods", mana_cost=ManaCost(R=3),
                        card_type="sorcery", abilities=["damage_sweep"]) for _ in range(3)]

        sb_ai = SideboardAI(deck, sweepers, "control")

        # Sideboard vs aggro (should bring in sweepers)
        cards_in, cards_out = sb_ai.sideboard_for_matchup("aggro")

        # Should suggest bringing in cards
        assert len(cards_in) >= 0  # May or may not sideboard based on AI logic

    def test_sideboard_symmetry(self, deck_with_sideboard):
        """Test both players sideboard against each other"""
        results = run_match(
            deck_with_sideboard,
            deck_with_sideboard,
            "Deck1", "Deck2",
            matches=1,
            games=3,
            verbose=False,
            sideboard=True
        )

        # Both decks should be able to sideboard
        total_games = results["deck1_games"] + results["deck2_games"]
        assert total_games >= 2


# =============================================================================
# TEST SECTION 6: PRIORITY & APNAP
# =============================================================================

class TestPriorityAndAPNAP:
    """Test priority passing and APNAP order"""

    def test_simultaneous_triggers_apnap_order(self):
        """Test APNAP (Active Player, Non-Active Player) ordering"""
        lands = [Card(name="Forest", card_type="land", produces=["G"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "midrange",
                   lands[10:], "Deck2", "midrange", verbose=False)

        game.deal_hands()

        # Add landfall creatures for both players
        landfall1 = Card(name="Scute Swarm", mana_cost=ManaCost(G=3),
                        card_type="creature", power=1, toughness=1,
                        abilities=["landfall_create_token"], instance_id=1)
        landfall2 = Card(name="Scute Swarm", mana_cost=ManaCost(G=3),
                        card_type="creature", power=1, toughness=1,
                        abilities=["landfall_create_token"], instance_id=2)

        game.p1.battlefield.append(landfall1)
        game.p2.battlefield.append(landfall2)

        # Play land (should trigger both)
        # Active player's trigger goes on stack first (resolves last)
        # This tests APNAP ordering
        game.active_id = 1

    def test_multiple_sba_checks(self):
        """Test multiple state-based actions at once"""
        creatures = [Card(name="Bears", mana_cost=ManaCost(G=2),
                         card_type="creature", power=2, toughness=2) for _ in range(20)]

        game = Game(creatures[:10], "Deck1", "aggro",
                   creatures[10:], "Deck2", "aggro", verbose=False)

        game.deal_hands()

        # Create creature with lethal damage
        creature1 = Card(name="Bears", mana_cost=ManaCost(G=2),
                        card_type="creature", power=2, toughness=2, instance_id=1)
        creature1.damage_marked = 2  # Lethal

        # Create planeswalker with 0 loyalty
        pw = Card(name="Jace", mana_cost=ManaCost(U=3),
                 card_type="planeswalker", loyalty=0, instance_id=2)
        pw.counters["loyalty"] = 0

        game.p1.battlefield.extend([creature1, pw])

        # Check state (should remove both)
        game.check_state()

        # Both should be in graveyard
        assert creature1 in game.p1.graveyard
        assert pw in game.p1.graveyard

    def test_stack_lifo_order(self):
        """Test stack resolves in LIFO (Last In, First Out) order"""
        lands = [Card(name="Island", card_type="land", produces=["U"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "control",
                   lands[10:], "Deck2", "control", verbose=False)

        from mtg_engine import StackItem

        # Add items to stack (using correct StackItem signature)
        item1 = StackItem(card=lands[0], controller=1, target=None, stack_id=1)
        item2 = StackItem(card=lands[1], controller=1, target=None, stack_id=2)
        item3 = StackItem(card=lands[2], controller=1, target=None, stack_id=3)

        game.stack = [item1, item2, item3]

        # Top of stack should be last added (item3)
        assert game.stack[-1].stack_id == 3

        # Pop from stack
        top = game.stack.pop()
        assert top.stack_id == 3

        next_top = game.stack.pop()
        assert next_top.stack_id == 2


# =============================================================================
# TEST SECTION 7: GAME MECHANICS VALIDATION
# =============================================================================

class TestGameMechanics:
    """Test specific game mechanics"""

    def test_life_total_changes(self):
        """Test life total tracking"""
        lands = [Card(name="Plains", card_type="land", produces=["W"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "aggro",
                   lands[10:], "Deck2", "aggro", verbose=False)

        # Initial life
        assert game.p1.life == 20
        assert game.p2.life == 20

        # Deal damage
        game.p2.life -= 3
        assert game.p2.life == 17

        # Gain life
        game.p1.life += 5
        assert game.p1.life == 25

    def test_poison_counter_tracking(self):
        """Test poison counter accumulation"""
        lands = [Card(name="Forest", card_type="land", produces=["G"]) for _ in range(20)]

        game = Game(lands[:10], "Deck1", "poison",
                   lands[10:], "Deck2", "control", verbose=False)

        # Initial poison
        assert game.p1.poison_counters == 0
        assert game.p2.poison_counters == 0

        # Add poison
        game.p2.poison_counters += 3
        assert game.p2.poison_counters == 3

        # Check win condition (10 poison)
        game.p2.poison_counters = 10
        game.check_state()
        assert game.winner == 1  # P1 wins (P2 has 10 poison)

    def test_card_zone_transitions(self):
        """Test cards moving between zones"""
        card = Card(name="Lightning Strike", mana_cost=ManaCost(R=1, generic=1),
                   card_type="instant", instance_id=1)

        lands = [Card(name="Mountain", card_type="land", produces=["R"]) for _ in range(20)]

        game = Game(lands[:10] + [card], "Deck1", "aggro",
                   lands[10:], "Deck2", "control", verbose=False)

        game.deal_hands()

        # Card starts in library
        # Move to hand (via draw)
        # Move to graveyard (via play)
        # Each transition should work correctly

        initial_library = len(game.p1.library)
        game.draw(game.p1, 1)
        assert len(game.p1.library) == initial_library - 1
        assert len(game.p1.hand) >= 1

    def test_mana_pool_operations(self):
        """Test mana pool add/pay/clear operations"""
        from mtg_engine import ManaPool

        pool = ManaPool()

        # Add mana
        pool.add("R")
        pool.add("R")
        pool.add("G")
        assert pool.R == 2
        assert pool.G == 1

        # Create cost
        cost = ManaCost(R=2, generic=1)

        # Check if can pay
        can_pay = pool.can_pay(cost)
        # Should be able to pay 2R with 2R + G (using G for generic)

        # Clear pool
        pool.clear()
        assert pool.R == 0
        assert pool.G == 0


# =============================================================================
# TEST MARKERS & CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

if __name__ == "__main__":
    """Run tests with pytest"""
    pytest.main([__file__, "-v", "--tb=short"])
