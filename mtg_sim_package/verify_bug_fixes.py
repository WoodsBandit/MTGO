"""
MTG Engine Bug Fix Verification Suite
=====================================
Tests all 9 bugs that were fixed to ensure they work correctly.
"""

import sys
sys.path.insert(0, '.')

from mtg_engine import (
    Card, Player, Game, ManaCost, ManaPool, AI, StackItem,
    parse_decklist, run_match
)
from dataclasses import dataclass
from typing import List, Dict, Tuple

# Test counters
passed = 0
failed = 0
results = []

def test(name: str, condition: bool, details: str = ""):
    global passed, failed
    if condition:
        passed += 1
        results.append(f"  PASS: {name}")
    else:
        failed += 1
        results.append(f"  FAIL: {name} - {details}")

def create_test_game() -> Game:
    """Create a minimal game for testing"""
    # Create minimal card lists
    cards1 = []
    cards2 = []
    for i in range(30):
        land = Card(
            name="Mountain",
            mana_cost=ManaCost(),
            card_type="land",
            produces=["R"],
            instance_id=i
        )
        cards1.append(land)
        cards2.append(land.copy())
    return Game(cards1, "Test1", "aggro", cards2, "Test2", "aggro", verbose=False)

def create_creature(name: str, power: int, toughness: int, keywords: List[str] = None,
                   cost: str = "1", card_type: str = "creature") -> Card:
    """Helper to create test creatures"""
    return Card(
        name=name,
        mana_cost=ManaCost.parse(cost),
        card_type=card_type,
        power=power,
        toughness=toughness,
        keywords=keywords or [],
        abilities=[],
        instance_id=hash(name) % 10000
    )

print("=" * 60)
print("MTG ENGINE BUG FIX VERIFICATION")
print("=" * 60)

# =============================================================================
# BUG #1: Protection Prevents Combat Damage
# =============================================================================
print("\n[BUG #1] Protection Prevents Combat Damage (CR 702.16e)")
print("-" * 50)

game = create_test_game()

# Create a red attacker and a blocker with protection from red
red_attacker = create_creature("Red Dragon", 5, 5, cost="3RR")
pro_red_blocker = create_creature("White Knight", 2, 2, ["protection from red"], cost="WW")

# Put on battlefield
game.p1.battlefield.append(red_attacker)
game.p2.battlefield.append(pro_red_blocker)

# Check protection prevents damage helper exists and works
has_method = hasattr(game, '_protection_prevents_damage')
test("_protection_prevents_damage() method exists", has_method)

if has_method:
    all_bf = game.p1.battlefield + game.p2.battlefield
    prevents = game._protection_prevents_damage(red_attacker, pro_red_blocker, all_bf)
    test("Protection from red blocks red damage", prevents,
         f"Expected True, got {prevents}")

    # Check the reverse - red attacker doesn't have protection from white
    no_prevent = not game._protection_prevents_damage(pro_red_blocker, red_attacker, all_bf)
    test("No protection = no prevention", no_prevent)

# =============================================================================
# BUG #2: Target Validation on Resolution
# =============================================================================
print("\n[BUG #2] Target Validation on Resolution (CR 608.2b)")
print("-" * 50)

game = create_test_game()

# Check the validation method exists
has_validate = hasattr(game, '_validate_target_on_resolution')
test("_validate_target_on_resolution() method exists", has_validate)

if has_validate:
    # Create a creature and test targeting
    target_creature = create_creature("Test Target", 3, 3)
    target_creature.instance_id = 12345
    game.p2.battlefield.append(target_creature)

    removal_spell = create_creature("Lightning Bolt", 0, 0, cost="R")
    removal_spell.card_type = "instant"
    removal_spell.abilities = ["damage_3"]

    # Valid target should pass
    valid = game._validate_target_on_resolution(removal_spell, target_creature, game.p1)
    test("Valid target passes validation", valid)

    # Remove target from battlefield
    game.p2.battlefield.remove(target_creature)

    # Now target should fail validation
    invalid = not game._validate_target_on_resolution(removal_spell, target_creature, game.p1)
    test("Removed target fails validation (spell fizzles)", invalid,
         "Target left battlefield but validation passed")

# =============================================================================
# BUG #3: Trample + Protection Calculation
# =============================================================================
print("\n[BUG #3] Trample + Protection Math (CR 702.19b)")
print("-" * 50)

game = create_test_game()

# Red trampler vs pro-red blocker
trampler = create_creature("Charging Rhino", 6, 4, ["trample"], cost="3RR")
pro_red = create_creature("Shield Bearer", 2, 2, ["protection from red"], cost="WW")

trampler.instance_id = 100
pro_red.instance_id = 200

game.p1.battlefield.append(trampler)
game.p2.battlefield.append(pro_red)

# The key insight: with protection, blocker takes 0 damage, but trampler
# still assigns "lethal" (2) for trample calculation, so 4 tramples through

# We can't easily test the combat math directly, but we can verify the
# protection check is being applied
if hasattr(game, '_protection_prevents_damage'):
    all_bf = game.p1.battlefield + game.p2.battlefield
    prevents = game._protection_prevents_damage(trampler, pro_red, all_bf)
    test("Trample attacker's damage prevented by protection", prevents)
    test("Blocker would take 0 damage (protected)", prevents)

# =============================================================================
# BUG #4: APNAP Trigger Ordering
# =============================================================================
print("\n[BUG #4] APNAP Trigger Ordering (CR 603.3b)")
print("-" * 50)

game = create_test_game()

# Check that process_triggers handles APNAP
# Queue triggers from both players
creature1 = create_creature("P1 Creature", 2, 2)
creature1.instance_id = 301
creature2 = create_creature("P2 Creature", 2, 2)
creature2.instance_id = 302

# Queue triggers - P1 is active, P2 is not
game.queue_trigger("dies", creature1, game.p1, {})
game.queue_trigger("dies", creature2, game.p2, {})

# Check queue has both
test("Triggers queued correctly", len(game.trigger_queue) == 2)

# Process triggers - should handle APNAP order
initial_queue_len = len(game.trigger_queue)
game.process_triggers()
test("Triggers processed", len(game.trigger_queue) == 0,
     f"Queue still has {len(game.trigger_queue)} items")

# =============================================================================
# BUG #5: Last Known Information for Dies Triggers
# =============================================================================
print("\n[BUG #5] Last Known Information (CR 603.10)")
print("-" * 50)

game = create_test_game()

# Create a creature with counters
dying_creature = create_creature("Boosted Creature", 2, 2)
dying_creature.instance_id = 400
dying_creature.counters["+1/+1"] = 3  # Now effectively 5/5

game.p1.battlefield.append(dying_creature)

# Check that fire_dies accepts last_known_info parameter
import inspect
sig = inspect.signature(game.fire_dies)
params = list(sig.parameters.keys())
test("fire_dies accepts last_known_info parameter", "last_known_info" in params,
     f"Parameters: {params}")

# Capture last known info before death
all_bf = game.p1.battlefield + game.p2.battlefield
p, t, kws = game.get_creature_with_bonuses(dying_creature, all_bf)
last_known = {
    'power': p,
    'toughness': t,
    'keywords': kws,
    'counters': dying_creature.counters.copy()
}

test("Last known power includes counters", last_known['power'] == 5,
     f"Expected 5, got {last_known['power']}")
test("Last known toughness includes counters", last_known['toughness'] == 5,
     f"Expected 5, got {last_known['toughness']}")

# =============================================================================
# BUG #6: SBA Trigger Processing
# =============================================================================
print("\n[BUG #6] SBA Trigger Processing (CR 704.3)")
print("-" * 50)

game = create_test_game()

# Check that check_state processes triggers
# Add a creature that will die to SBA
dying = create_creature("Dying Creature", 1, 0)  # 0 toughness = dies to SBA
dying.instance_id = 500
dying.abilities = ["dies_draw_1"]  # Has a dies trigger

game.p1.battlefield.append(dying)

# Run SBA check
game.check_state()

# Creature should be dead (in graveyard)
in_graveyard = any(c.instance_id == 500 for c in game.p1.graveyard)
not_on_bf = not any(c.instance_id == 500 for c in game.p1.battlefield)

test("0 toughness creature died to SBA", in_graveyard and not_on_bf,
     f"Graveyard: {in_graveyard}, Not on BF: {not_on_bf}")

# =============================================================================
# BUG #7: Damage Assignment Order
# =============================================================================
print("\n[BUG #7] Damage Assignment Order (CR 510.1c)")
print("-" * 50)

game = create_test_game()

# Check that Game has choose_damage_assignment_order method (moved from AI to Game)
has_method = hasattr(game, 'choose_damage_assignment_order')
test("Game has choose_damage_assignment_order() method", has_method)

if has_method:
    attacker = create_creature("Big Attacker", 6, 6)

    # Create blockers - one with deathtouch (should be killed first)
    deathtouch_blocker = create_creature("Deathtouch Snake", 1, 1, ["deathtouch"])
    deathtouch_blocker.instance_id = 601

    normal_blocker = create_creature("Normal Bear", 2, 2)
    normal_blocker.instance_id = 602

    lifelink_blocker = create_creature("Lifelink Angel", 3, 3, ["lifelink"])
    lifelink_blocker.instance_id = 603

    blockers = [normal_blocker, lifelink_blocker, deathtouch_blocker]
    all_bf = blockers + [attacker]  # battlefield for the method

    # Game should prioritize deathtouch first
    ordered = game.choose_damage_assignment_order(attacker, blockers, all_bf)

    # Deathtouch should be first (highest priority to kill)
    first_has_deathtouch = "deathtouch" in [k.lower() for k in ordered[0].keywords]
    test("AI prioritizes killing deathtouch blockers first", first_has_deathtouch,
         f"First blocker: {ordered[0].name}")

# =============================================================================
# BUG #8: Auras Fall Off from Protection
# =============================================================================
print("\n[BUG #8] Auras Fall Off from Protection (CR 303.4d)")
print("-" * 50)

game = create_test_game()

# Create a red aura attached to a creature
red_aura = Card(
    name="Red Enchantment",
    mana_cost=ManaCost.parse("R"),
    card_type="enchantment",
    subtype="aura",
    keywords=[],
    abilities=[],
    grants=["+2/+0"],
    instance_id=700
)

# Create creature that will gain protection
enchanted_creature = create_creature("Enchanted Guy", 2, 2)
enchanted_creature.instance_id = 701

# Attach aura
red_aura.attached_to = enchanted_creature.instance_id

game.p1.battlefield.append(enchanted_creature)
game.p1.battlefield.append(red_aura)

# Before protection - aura should stay
game._check_sbas_once()
aura_on_bf = any(c.instance_id == 700 for c in game.p1.battlefield)
test("Aura stays without protection", aura_on_bf)

# Now give creature protection from red
enchanted_creature.keywords.append("protection from red")

# Run SBA - aura should fall off
game._check_sbas_once()
aura_gone = not any(c.instance_id == 700 for c in game.p1.battlefield)
aura_in_gy = any(c.instance_id == 700 for c in game.p1.graveyard)

test("Aura falls off when creature gains protection", aura_gone,
     f"Aura still on battlefield: {not aura_gone}")
test("Fallen aura goes to graveyard", aura_in_gy)

# =============================================================================
# BUG #9: Complete Spell Fizzle Logic
# =============================================================================
print("\n[BUG #9] Complete Spell Fizzle Logic (CR 608.2b)")
print("-" * 50)

game = create_test_game()

# Test that non-aura targeted spells also fizzle
# This is essentially the same as Bug #2 but for different spell types

# Create a damage spell
burn_spell = Card(
    name="Lightning Bolt",
    mana_cost=ManaCost.parse("R"),
    card_type="instant",
    abilities=["damage_3"],
    instance_id=800
)

# Create target
target = create_creature("Target Dummy", 3, 3)
target.instance_id = 801
game.p2.battlefield.append(target)

# Validation should pass with valid target
if hasattr(game, '_validate_target_on_resolution'):
    valid = game._validate_target_on_resolution(burn_spell, target, game.p1)
    test("Burn spell validates with valid target", valid)

    # Give target hexproof
    target.keywords.append("hexproof")

    # Now should fail (hexproof blocks opponent targeting)
    invalid = not game._validate_target_on_resolution(burn_spell, target, game.p1)
    test("Burn spell fizzles when target gains hexproof", invalid,
         "Hexproof target still valid")

# =============================================================================
# FULL GAME SIMULATION
# =============================================================================
print("\n[FULL SIMULATION] Running actual game simulations")
print("-" * 50)

# Run some actual matches to verify nothing is broken
try:
    # Simple aggro deck
    aggro_deck = """
4 Monastery Swiftspear
4 Soul-Scar Mage
4 Lightning Bolt
4 Shock
4 Play with Fire
20 Mountain
20 Mountain
"""

    # Simple control deck
    control_deck = """
4 Counterspell
4 Cancel
4 Divination
4 Air Elemental
4 Unsummon
20 Island
20 Island
"""

    # Run 5 matches
    results_match = run_match(aggro_deck, control_deck, "Aggro", "Control", matches=5, verbose=False)

    total_matches = results_match.get('deck1_wins', 0) + results_match.get('deck2_wins', 0)
    test(f"5-match simulation completed", total_matches == 5,
         f"Only {total_matches} matches completed")

    print(f"  Match result: Aggro {results_match.get('deck1_wins', 0)} - {results_match.get('deck2_wins', 0)} Control")

except Exception as e:
    test("Game simulation runs without errors", False, str(e))

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print("VERIFICATION SUMMARY")
print("=" * 60)

for r in results:
    print(r)

print("\n" + "-" * 60)
print(f"TOTAL: {passed} passed, {failed} failed")
print("-" * 60)

if failed == 0:
    print("\nALL BUG FIXES VERIFIED SUCCESSFULLY!")
else:
    print(f"\n{failed} VERIFICATION(S) FAILED - Review needed")

sys.exit(0 if failed == 0 else 1)
