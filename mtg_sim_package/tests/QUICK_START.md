# SBA Test Suite - Quick Start Guide

## Installation

No additional dependencies needed beyond pytest:
```bash
pip install pytest
```

## Running Tests

### Quick Test Run (Recommended)
```bash
cd mtg_sim_package
pytest tests/test_sba.py -v
```

Expected output:
```
============================= 44 passed in 0.06s ==============================
```

### Run Specific Test Categories

**Player Loss Conditions:**
```bash
pytest tests/test_sba.py::TestPlayerLossConditions -v
```

**Creature Death:**
```bash
pytest tests/test_sba.py::TestCreatureDeath -v
```

**Counter Interactions:**
```bash
pytest tests/test_sba.py::TestCounterInteractions -v
```

**Planeswalkers:**
```bash
pytest tests/test_sba.py::TestPlaneswalkerSBAs -v
```

**Auras:**
```bash
pytest tests/test_sba.py::TestAuraSBAs -v
```

**Tokens:**
```bash
pytest tests/test_sba.py::TestTokenSBAs -v
```

**SBA Loop:**
```bash
pytest tests/test_sba.py::TestSBALoop -v
```

**Edge Cases:**
```bash
pytest tests/test_sba.py::TestEdgeCases -v
```

## Test File Structure

```
tests/
├── __init__.py              # Package marker
├── test_sba.py              # 44 SBA test cases
├── README.md                # Comprehensive documentation
├── SBA_TEST_SUMMARY.md      # Detailed test report
└── QUICK_START.md           # This file
```

## Common Test Patterns

### Testing Creature Death
```python
def test_creature_dies_from_lethal_damage(self, game_with_creatures):
    creature = game_with_creatures.p1.battlefield[0]
    creature.damage_marked = 3  # 3/3 creature takes 3 damage

    game_with_creatures.check_state()

    assert creature not in game_with_creatures.p1.battlefield
    assert creature in game_with_creatures.p1.graveyard
```

### Testing Player Loss
```python
def test_player_loses_at_zero_life(self, basic_game):
    basic_game.p1.life = 0

    result = basic_game.check_state()

    assert basic_game.winner == 2
    assert result == False  # Game is over
```

### Testing SBA Loop
```python
def test_sba_loop_counter_cancellation_then_death(self, basic_game):
    creature.counters["+1/+1"] = 1
    creature.counters["-1/-1"] = 3  # Net -2/-2 -> dies

    basic_game.check_state()

    # First loop: counters cancel
    # Second loop: creature dies from 0 toughness
    assert creature in basic_game.p1.graveyard
```

## Quick Debugging

### Run Single Test with Full Output
```bash
pytest tests/test_sba.py::TestCreatureDeath::test_indestructible_does_not_prevent_zero_toughness_death -v -s
```

### Run with Detailed Failure Info
```bash
pytest tests/test_sba.py -v --tb=long
```

### Run and Stop on First Failure
```bash
pytest tests/test_sba.py -x
```

## Test Coverage by MTG Rule

| Rule | What It Tests | Tests |
|------|---------------|-------|
| 704.5a | Life <= 0 loses | 3 |
| 704.5b | 10+ poison loses | 3 |
| 704.5c | Draw from empty library | 2 |
| 704.5d | Tokens cease to exist | 5 |
| 704.5f | Toughness <= 0 | 4 |
| 704.5g | Lethal damage | 4 |
| 704.5h | Deathtouch | 2 |
| 704.5i | Planeswalker loyalty <= 0 | 3 |
| 704.5j | Legend rule | 2 |
| 704.5m | Aura attachments | 2 |
| 704.5q | Counter annihilation | 4 |

## Adding New Tests

1. **Choose appropriate test class** based on SBA category
2. **Use fixture** (`basic_game` or `game_with_creatures`)
3. **Setup test condition**
4. **Call `check_state()`**
5. **Assert expected outcome**

Example:
```python
def test_new_sba_scenario(self, basic_game):
    """704.X: Description of what you're testing"""
    # Setup
    creature = Card(name="Test", card_type="creature",
                   power=1, toughness=1)
    basic_game.p1.battlefield.append(creature)

    # Create SBA condition
    creature.toughness = 0

    # Execute
    basic_game.check_state()

    # Assert
    assert creature not in basic_game.p1.battlefield
    assert creature in basic_game.p1.graveyard
```

## Troubleshooting

### Test Fails: "Card object has no attribute X"
Check the Card dataclass in `mtg_engine.py` - you may be using a field that doesn't exist.

### Test Fails: "creature still on battlefield"
The engine might not be checking that specific SBA. Check `Game._check_sbas_once()` implementation.

### Tests are slow
SBA tests should run in ~0.06 seconds total. If slower, check for accidental verbose logging or infinite loops.

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Run SBA Tests
  run: |
    cd mtg_sim_package
    pytest tests/test_sba.py -v --tb=short
```

### GitLab CI Example
```yaml
test_sba:
  script:
    - cd mtg_sim_package
    - pytest tests/test_sba.py -v --tb=short
```

## Key Assertions to Use

### Creature Death
```python
assert creature not in player.battlefield
assert creature in player.graveyard
```

### Token Death
```python
assert token not in player.battlefield
assert token not in player.graveyard  # Tokens cease to exist
```

### Player Loss
```python
assert game.winner == expected_winner_id
assert game.check_state() == False  # Game over
```

### No SBA Applied
```python
result = game.check_state()
assert result == True  # Game continues
assert game.winner is None
```

## MTG Rules Reference

All tests based on **MTG Comprehensive Rules Section 704**:
https://magic.wizards.com/en/rules

Key rule: **704.3** - "Whenever a player would get priority, the game checks for any of the listed conditions for state-based actions, then the game performs all applicable state-based actions simultaneously as a single event. If any state-based actions are performed as a result of a check, the check is repeated; otherwise all triggered abilities that are waiting to be put on the stack are put on the stack, then the check is repeated."

## Support

For issues or questions:
1. Check test output for specific assertion failures
2. Review `tests/README.md` for detailed documentation
3. Review `tests/SBA_TEST_SUMMARY.md` for comprehensive coverage analysis
4. Check `mtg_engine.py` implementation of `check_state()` and `_check_sbas_once()`

## Quick Stats

- **Total Tests**: 44
- **Test Categories**: 8
- **MTG Rules Covered**: 12
- **Execution Time**: 0.06 seconds
- **Pass Rate**: 100%
