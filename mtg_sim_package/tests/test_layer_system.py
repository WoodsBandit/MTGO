"""
Test suite for the Layer System (MTG Rule 613)
==============================================

Tests the layer system implementation including:
- Layer ordering (1-7, with sublayers 7a-7e)
- Timestamp ordering within layers
- Dependency handling (Rule 613.8)
- Blood Moon + Urborg interaction (classic test case)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mtg_engine import Card, ManaCost, Game
from layer_system import ContinuousEffect, LayerSystem


def create_test_game():
    """Create a minimal game for testing."""
    # Create simple test decks
    lands = [Card(name="Forest", card_type="land", produces=["G"]) for _ in range(20)]
    creatures = [Card(name="Llanowar Elves", card_type="creature",
                     mana_cost=ManaCost.parse("G"), power=1, toughness=1) for _ in range(10)]
    deck1 = lands + creatures + lands[:10]
    deck2 = lands + creatures + lands[:10]

    game = Game(deck1, "Test Deck 1", "midrange",
                deck2, "Test Deck 2", "midrange", verbose=False)
    return game


def test_layer_order_constant():
    """Test that LAYER_ORDER is correctly defined."""
    expected = [1, 2, 3, 4, 5, 6, '7a', '7b', '7c', '7d', '7e']
    assert LayerSystem.LAYER_ORDER == expected, f"Expected {expected}, got {LayerSystem.LAYER_ORDER}"
    print("PASS: Layer order constant is correct")


def test_add_and_remove_effects():
    """Test adding and removing effects from the layer system."""
    game = create_test_game()

    # Create a test creature
    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    instance_id=9999)

    # Create an anthem effect
    source = Card(name="Glorious Anthem", card_type="enchantment",
                  mana_cost=ManaCost.parse("1WW"), instance_id=9998)

    effect = game.layer_system.create_anthem_effect(source, 1, 1)

    # Add the effect
    added = game.layer_system.add_effect(effect)
    assert len(game.layer_system.effects) == 1
    assert added.timestamp == 0
    assert added.effect_id == 0

    # Add another effect
    effect2 = game.layer_system.create_anthem_effect(source, 2, 2)
    added2 = game.layer_system.add_effect(effect2)
    assert len(game.layer_system.effects) == 2
    assert added2.timestamp == 1
    assert added2.effect_id == 1

    # Remove the first effect
    result = game.layer_system.remove_effect(effect)
    assert result == True
    assert len(game.layer_system.effects) == 1

    print("PASS: Add and remove effects works correctly")


def test_anthem_effect():
    """Test that anthem effects modify creature P/T correctly."""
    game = create_test_game()

    # Create a test creature
    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    instance_id=9999, controller=1)

    # Create an anthem source
    source = Card(name="Glorious Anthem", card_type="enchantment",
                  mana_cost=ManaCost.parse("1WW"), instance_id=9998)

    # Without anthem
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 2
    assert chars['toughness'] == 2

    # Add anthem (+1/+1 to all creatures)
    anthem = game.layer_system.create_anthem_effect(source, 1, 1)
    game.layer_system.add_effect(anthem)

    # With anthem
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 3, f"Expected 3, got {chars['power']}"
    assert chars['toughness'] == 3, f"Expected 3, got {chars['toughness']}"

    print("PASS: Anthem effect correctly modifies P/T")


def test_set_pt_effect():
    """Test that 'set P/T' effects (Layer 7b) override base stats."""
    game = create_test_game()

    # Create a large creature
    creature = Card(name="Colossal Dreadmaw", card_type="creature",
                    mana_cost=ManaCost.parse("4GG"), power=6, toughness=6,
                    instance_id=9999, controller=1)

    # Create a "Turn to Frog" type effect source
    source = Card(name="Turn to Frog", card_type="instant",
                  mana_cost=ManaCost.parse("1U"), instance_id=9998)

    # Set to 1/1
    effect = game.layer_system.create_set_pt_effect(source, creature, 1, 1)
    game.layer_system.add_effect(effect)

    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 1, f"Expected 1, got {chars['power']}"
    assert chars['toughness'] == 1, f"Expected 1, got {chars['toughness']}"

    print("PASS: Set P/T effect correctly overrides base stats")


def test_set_pt_then_anthem():
    """
    Test Layer 7b + 7d interaction.

    Set P/T (7b) happens before modifiers (7d), so:
    - Base 6/6 creature
    - Turn to Frog sets it to 1/1 (Layer 7b)
    - Anthem gives +1/+1 (Layer 7d)
    - Final should be 2/2
    """
    game = create_test_game()

    creature = Card(name="Colossal Dreadmaw", card_type="creature",
                    mana_cost=ManaCost.parse("4GG"), power=6, toughness=6,
                    instance_id=9999, controller=1)

    frog_source = Card(name="Turn to Frog", card_type="instant",
                       mana_cost=ManaCost.parse("1U"), instance_id=9998)
    anthem_source = Card(name="Glorious Anthem", card_type="enchantment",
                         mana_cost=ManaCost.parse("1WW"), instance_id=9997)

    # Add anthem first (Layer 7d)
    anthem = game.layer_system.create_anthem_effect(anthem_source, 1, 1)
    game.layer_system.add_effect(anthem)

    # Then add "set to 1/1" (Layer 7b) - should apply BEFORE anthem in layer order
    frog = game.layer_system.create_set_pt_effect(frog_source, creature, 1, 1)
    game.layer_system.add_effect(frog)

    chars = game.layer_system.calculate_characteristics(creature)

    # Layer 7b (set to 1/1) applies first, then Layer 7d (anthem +1/+1)
    assert chars['power'] == 2, f"Expected 2, got {chars['power']}"
    assert chars['toughness'] == 2, f"Expected 2, got {chars['toughness']}"

    print("PASS: Set P/T (7b) + Anthem (7d) layer order works correctly")


def test_switch_pt_effect():
    """Test that P/T switching (Layer 7e) works correctly."""
    game = create_test_game()

    # Create a creature with different P/T
    creature = Card(name="Wall of Stone", card_type="creature",
                    mana_cost=ManaCost.parse("1RR"), power=0, toughness=8,
                    instance_id=9999, controller=1)

    source = Card(name="Inside Out", card_type="instant",
                  mana_cost=ManaCost.parse("1U"), instance_id=9998)

    # Switch P/T
    effect = game.layer_system.create_switch_pt_effect(source, creature)
    game.layer_system.add_effect(effect)

    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 8, f"Expected 8, got {chars['power']}"
    assert chars['toughness'] == 0, f"Expected 0, got {chars['toughness']}"

    print("PASS: Switch P/T effect works correctly")


def test_anthem_then_switch():
    """
    Test Layer 7d + 7e interaction.

    - Base 0/8 Wall
    - Anthem +1/+1 (Layer 7d) -> 1/9
    - Switch (Layer 7e) -> 9/1
    """
    game = create_test_game()

    creature = Card(name="Wall of Stone", card_type="creature",
                    mana_cost=ManaCost.parse("1RR"), power=0, toughness=8,
                    instance_id=9999, controller=1)

    anthem_source = Card(name="Glorious Anthem", card_type="enchantment",
                         mana_cost=ManaCost.parse("1WW"), instance_id=9998)
    switch_source = Card(name="Inside Out", card_type="instant",
                         mana_cost=ManaCost.parse("1U"), instance_id=9997)

    # Add both effects
    anthem = game.layer_system.create_anthem_effect(anthem_source, 1, 1)
    game.layer_system.add_effect(anthem)

    switch = game.layer_system.create_switch_pt_effect(switch_source, creature)
    game.layer_system.add_effect(switch)

    chars = game.layer_system.calculate_characteristics(creature)

    # Layer 7d: 0/8 + 1/1 = 1/9
    # Layer 7e: switch -> 9/1
    assert chars['power'] == 9, f"Expected 9, got {chars['power']}"
    assert chars['toughness'] == 1, f"Expected 1, got {chars['toughness']}"

    print("PASS: Anthem (7d) + Switch (7e) layer order works correctly")


def test_add_ability_effect():
    """Test that Layer 6 add ability effects work."""
    game = create_test_game()

    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    keywords=[], instance_id=9999, controller=1)

    source = Card(name="Archetype of Courage", card_type="enchantment",
                  mana_cost=ManaCost.parse("1WW"), instance_id=9998)

    # Add flying to all creatures
    effect = game.layer_system.create_add_ability_effect(
        source,
        keywords=["flying", "first strike"],
        condition=lambda c: c.card_type == 'creature'
    )
    game.layer_system.add_effect(effect)

    chars = game.layer_system.calculate_characteristics(creature)
    assert "flying" in chars['keywords']
    assert "first strike" in chars['keywords']

    print("PASS: Add ability effect works correctly")


def test_remove_ability_effect():
    """Test that Layer 6 remove ability effects work."""
    game = create_test_game()

    creature = Card(name="Serra Angel", card_type="creature",
                    mana_cost=ManaCost.parse("3WW"), power=4, toughness=4,
                    keywords=["flying", "vigilance"], instance_id=9999, controller=1)

    source = Card(name="Humility", card_type="enchantment",
                  mana_cost=ManaCost.parse("2WW"), instance_id=9998)

    # Remove all abilities
    effect = game.layer_system.create_remove_ability_effect(
        source,
        remove_all=True,
        condition=lambda c: c.card_type == 'creature'
    )
    game.layer_system.add_effect(effect)

    chars = game.layer_system.calculate_characteristics(creature)
    assert len(chars['keywords']) == 0, f"Expected 0 keywords, got {chars['keywords']}"

    print("PASS: Remove ability effect works correctly")


def test_blood_moon_effect():
    """Test Blood Moon effect (Layer 4 type changing)."""
    game = create_test_game()

    # Create a nonbasic land
    nonbasic = Card(name="Steam Vents", card_type="land", subtype="Island Mountain",
                    produces=["U", "R"], abilities=["tap_for_UR"], instance_id=9999, controller=1)

    # Create a basic land (should NOT be affected)
    basic = Card(name="Forest", card_type="land", subtype="Forest",
                 produces=["G"], instance_id=9998, controller=1)

    blood_moon = Card(name="Blood Moon", card_type="enchantment",
                      mana_cost=ManaCost.parse("2R"), instance_id=9997)

    # Add Blood Moon effect
    effect = game.layer_system.create_blood_moon_effect(blood_moon)
    game.layer_system.add_effect(effect)

    # Nonbasic should become just a Mountain
    nonbasic_chars = game.layer_system.calculate_characteristics(nonbasic)
    assert nonbasic_chars['subtype'] == 'Mountain', f"Expected 'Mountain', got '{nonbasic_chars['subtype']}'"
    assert nonbasic_chars['produces'] == ['R'], f"Expected ['R'], got {nonbasic_chars['produces']}"
    assert nonbasic_chars['abilities'] == [], f"Expected [], got {nonbasic_chars['abilities']}"

    # Basic should be unaffected
    basic_chars = game.layer_system.calculate_characteristics(basic)
    assert basic_chars['subtype'] == 'Forest', f"Expected 'Forest', got '{basic_chars['subtype']}'"
    assert basic_chars['produces'] == ['G'], f"Expected ['G'], got {basic_chars['produces']}"

    print("PASS: Blood Moon effect works correctly")


def test_urborg_effect():
    """Test Urborg effect (Layer 4 type adding)."""
    game = create_test_game()

    # Create lands
    forest = Card(name="Forest", card_type="land", subtype="Forest",
                  produces=["G"], instance_id=9999, controller=1)

    urborg = Card(name="Urborg, Tomb of Yawgmoth", card_type="land", subtype="",
                  produces=["B"], instance_id=9998, controller=1)

    # Add Urborg effect
    effect = game.layer_system.create_urborg_effect(urborg)
    game.layer_system.add_effect(effect)

    # Forest should now be "Forest Swamp" and produce G,B
    forest_chars = game.layer_system.calculate_characteristics(forest)
    assert 'Swamp' in forest_chars['subtype'], f"Expected 'Swamp' in subtype, got '{forest_chars['subtype']}'"
    assert 'B' in forest_chars['produces'], f"Expected 'B' in produces, got {forest_chars['produces']}"

    print("PASS: Urborg effect works correctly")


def test_blood_moon_plus_urborg():
    """
    Test the classic Blood Moon + Urborg interaction.

    Key interaction (both are Layer 4):
    - Blood Moon makes nonbasic lands into Mountains, removing their abilities
    - Urborg gives all lands the Swamp type and ability to produce B

    Because Blood Moon removes abilities from Urborg (a nonbasic land),
    Urborg's ability never applies. Result: nonbasics are just Mountains.

    This is a dependency case handled by timestamp order within the same layer.
    Whichever enters first determines the order, but since Blood Moon removes
    the ability that would create Urborg's effect, the interaction is:

    If Blood Moon is on battlefield, Urborg loses its ability before it can
    create its effect (Urborg is a nonbasic land, so Blood Moon applies to it).
    """
    game = create_test_game()

    # Create lands
    steam_vents = Card(name="Steam Vents", card_type="land", subtype="Island Mountain",
                       produces=["U", "R"], instance_id=9999, controller=1)

    urborg = Card(name="Urborg, Tomb of Yawgmoth", card_type="land", subtype="",
                  produces=["B"], abilities=["all_lands_swamp"], instance_id=9998, controller=1)

    blood_moon = Card(name="Blood Moon", card_type="enchantment",
                      mana_cost=ManaCost.parse("2R"), instance_id=9997)

    # Add Blood Moon effect FIRST (enters the battlefield first)
    bm_effect = game.layer_system.create_blood_moon_effect(blood_moon)
    game.layer_system.add_effect(bm_effect)

    # Blood Moon makes Urborg into a Mountain, removing its ability
    # So Urborg's effect should NOT be created (ability was removed)
    urborg_chars = game.layer_system.calculate_characteristics(urborg)
    assert urborg_chars['subtype'] == 'Mountain', f"Urborg should be a Mountain, got '{urborg_chars['subtype']}'"
    assert urborg_chars['abilities'] == [], f"Urborg should have no abilities, got {urborg_chars['abilities']}"

    # Since Urborg's ability is removed, its effect won't exist
    # Steam Vents should just be a Mountain (from Blood Moon)
    sv_chars = game.layer_system.calculate_characteristics(steam_vents)
    assert sv_chars['subtype'] == 'Mountain', f"Steam Vents should be Mountain, got '{sv_chars['subtype']}'"
    assert 'B' not in sv_chars['produces'], f"Should not produce B (no Urborg effect), got {sv_chars['produces']}"

    print("PASS: Blood Moon + Urborg interaction works correctly")


def test_timestamp_ordering():
    """Test that effects in the same layer are ordered by timestamp."""
    game = create_test_game()

    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    instance_id=9999, controller=1)

    source1 = Card(name="Anthem 1", card_type="enchantment", instance_id=9998)
    source2 = Card(name="Anthem 2", card_type="enchantment", instance_id=9997)

    # Add first anthem (+1/+1)
    effect1 = game.layer_system.create_anthem_effect(source1, 1, 1)
    game.layer_system.add_effect(effect1)
    assert effect1.timestamp == 0

    # Add second anthem (+2/+2)
    effect2 = game.layer_system.create_anthem_effect(source2, 2, 2)
    game.layer_system.add_effect(effect2)
    assert effect2.timestamp == 1

    # Both should apply: 2 + 1 + 2 = 5
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 5, f"Expected 5, got {chars['power']}"
    assert chars['toughness'] == 5, f"Expected 5, got {chars['toughness']}"

    print("PASS: Timestamp ordering works correctly")


def test_control_change_effect():
    """Test Layer 2 control changing effects."""
    game = create_test_game()

    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    instance_id=9999, controller=1)

    source = Card(name="Control Magic", card_type="enchantment",
                  mana_cost=ManaCost.parse("2UU"), instance_id=9998)

    # Original controller is 1
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['controller'] == 1

    # Change control to player 2
    effect = game.layer_system.create_control_change_effect(source, creature, 2)
    game.layer_system.add_effect(effect)

    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['controller'] == 2, f"Expected controller 2, got {chars['controller']}"

    print("PASS: Control change effect works correctly")


def test_color_change_effect():
    """Test Layer 5 color changing effects."""
    game = create_test_game()

    # Create a green creature
    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    instance_id=9999, controller=1)

    source = Card(name="Painter's Servant", card_type="artifact",
                  mana_cost=ManaCost.parse("2"), instance_id=9998)

    # Add blue to all permanents
    effect = game.layer_system.create_color_change_effect(source, add_colors=['U'])
    game.layer_system.add_effect(effect)

    chars = game.layer_system.calculate_characteristics(creature)
    assert 'G' in chars['colors'], f"Should still have G, got {chars['colors']}"
    assert 'U' in chars['colors'], f"Should have U added, got {chars['colors']}"

    print("PASS: Color change effect works correctly")


def test_remove_expired_effects():
    """Test that end_of_turn effects are properly removed."""
    game = create_test_game()

    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    instance_id=9999, controller=1)

    source = Card(name="Giant Growth", card_type="instant",
                  mana_cost=ManaCost.parse("G"), instance_id=9998)

    # Create a temporary +3/+3 effect (end of turn)
    def applies(card):
        return card.instance_id == creature.instance_id

    def modify(perm, chars):
        chars['power'] = chars.get('power', perm.power) + 3
        chars['toughness'] = chars.get('toughness', perm.toughness) + 3
        return chars

    effect = ContinuousEffect(
        source=source,
        layer='7d',
        modification=modify,
        applies_to=applies,
        duration='end_of_turn'
    )
    game.layer_system.add_effect(effect)

    # Effect should be active
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 5, f"Expected 5, got {chars['power']}"

    # Remove expired effects
    removed = game.layer_system.remove_expired_effects()
    assert removed == 1, f"Expected 1 removed, got {removed}"

    # Effect should be gone
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 2, f"Expected 2, got {chars['power']}"

    print("PASS: Remove expired effects works correctly")


def test_remove_effects_from_source():
    """Test that effects are removed when source leaves battlefield."""
    game = create_test_game()

    creature = Card(name="Grizzly Bears", card_type="creature",
                    mana_cost=ManaCost.parse("1G"), power=2, toughness=2,
                    instance_id=9999, controller=1)

    source = Card(name="Glorious Anthem", card_type="enchantment",
                  mana_cost=ManaCost.parse("1WW"), instance_id=9998)

    # Add effect
    effect = game.layer_system.create_anthem_effect(source, 1, 1)
    game.layer_system.add_effect(effect)

    # Effect should be active
    assert len(game.layer_system.effects) == 1
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 3

    # Remove all effects from source (simulating it leaving battlefield)
    removed = game.layer_system.remove_effects_from_source(source)
    assert removed == 1, f"Expected 1 removed, got {removed}"
    assert len(game.layer_system.effects) == 0

    # Effect should be gone
    chars = game.layer_system.calculate_characteristics(creature)
    assert chars['power'] == 2, f"Expected 2, got {chars['power']}"

    print("PASS: Remove effects from source works correctly")


def run_all_tests():
    """Run all layer system tests."""
    print("=" * 60)
    print("LAYER SYSTEM TESTS (MTG Rule 613)")
    print("=" * 60)
    print()

    tests = [
        test_layer_order_constant,
        test_add_and_remove_effects,
        test_anthem_effect,
        test_set_pt_effect,
        test_set_pt_then_anthem,
        test_switch_pt_effect,
        test_anthem_then_switch,
        test_add_ability_effect,
        test_remove_ability_effect,
        test_blood_moon_effect,
        test_urborg_effect,
        test_blood_moon_plus_urborg,
        test_timestamp_ordering,
        test_control_change_effect,
        test_color_change_effect,
        test_remove_expired_effects,
        test_remove_effects_from_source,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}")
            print(f"  Exception: {type(e).__name__}: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
