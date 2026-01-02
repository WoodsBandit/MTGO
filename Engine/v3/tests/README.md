# MTG Engine V3 - Test Infrastructure

Comprehensive testing framework for the MTG Engine V3 project, built following pytest best practices and test-driven development principles.

## Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures for all tests
├── mocks/
│   ├── __init__.py
│   ├── mock_game.py         # MockGame for isolated testing
│   ├── mock_player.py       # MockPlayer for player-level tests
│   └── mock_objects.py      # MockCard, MockPermanent, MockCreature
├── test_priority.py         # Priority system tests (20 tests)
├── test_stack.py            # Stack system tests (26 tests)
└── README.md                # This file
```

## Test Files Created

### 1. conftest.py - Shared Fixtures
Provides reusable pytest fixtures for common test scenarios:

**Game Fixtures:**
- `game()` - Standard 2-player game
- `multiplayer_game()` - 4-player multiplayer game
- `mock_game()` - Lightweight mock for isolated testing
- `empty_battlefield()` - Game with cleared battlefield

**Player Fixtures:**
- `player1()`, `player2()` - Quick access to players
- `mock_player()` - Lightweight player mock

**Object Fixtures:**
- `mock_card()` - Generic test card
- `mock_creature()` - Generic 2/2 creature
- `mock_permanent()` - Generic permanent

**Factory Fixtures:**
- `card_factory()` - Create custom cards with specific attributes
- `permanent_factory()` - Create custom permanents

**System Fixtures:**
- `priority_system()` - Direct access to priority system
- `stack()` - Direct access to stack
- `mana_pool()` - Empty mana pool for testing
- `mana_pool_with_mana()` - Pre-loaded mana pool

### 2. Mocks Package

#### mock_game.py - MockGame Class
Lightweight game mock for testing without full engine overhead.

**Features:**
- Minimal game state (players, turn, phase)
- Priority system integration
- Mock zones with stack
- Object ID generation

**Use cases:**
- Testing priority system in isolation
- Testing stack operations
- Testing basic game flow without full complexity

#### mock_player.py - MockPlayer Class
Simplified player for focused testing.

**Features:**
- Life total tracking
- Mana pool management
- Poison counters
- Turn state (lands played, spells cast)
- Loss tracking

**Use cases:**
- Testing mana payment logic
- Testing player interactions
- Testing life total changes
- Isolated player state tests

#### mock_objects.py - Mock Game Objects

**MockCard:**
- Simple card representation
- Characteristics (name, mana cost, types, colors)
- Zone tracking

**MockPermanent:**
- Battlefield representation
- Tap/untap functionality
- Ownership and control
- Timestamp tracking

**MockCreature:**
- Extends MockPermanent
- Power/toughness tracking
- Keyword abilities
- Combat state (attacking, blocking)
- Damage tracking
- Pump effects

### 3. test_priority.py - Priority System Tests (20 tests)

Tests the priority system per CR 117 (Timing and Priority).

**Test Classes:**

**TestPriorityBasics (6 tests):**
- `test_give_priority_to_player` - Giving priority to specific player
- `test_pass_priority_to_next` - Passing to next in turn order
- `test_all_players_passed` - All-pass detection
- `test_priority_after_action` - Priority after player action
- `test_priority_holder_none_initially` - Initial state
- `test_reset_clears_state` - Reset functionality

**TestPriorityOrdering (3 tests):**
- `test_two_player_alternating` - 2-player priority alternation
- `test_multiplayer_priority_order` - APNAP order in 4-player
- `test_priority_wraps_around` - Priority wrap-around

**TestPriorityAllPass (4 tests):**
- `test_all_pass_empty_set` - Empty pass set behavior
- `test_all_pass_partial` - Partial pass detection
- `test_all_pass_complete` - Complete all-pass detection
- `test_all_pass_clears_after_action` - Action clears passes

**TestPriorityEdgeCases (4 tests):**
- `test_pass_without_priority_holder_raises` - Error handling
- `test_set_active_player_resets_priority` - Active player changes
- `test_player_takes_action_clears_passes` - Action clearing
- `test_multiple_action_cycles` - Multiple pass/action cycles

**TestPriorityIntegration (3 tests):**
- `test_priority_with_mock_game` - MockGame integration
- `test_priority_player_equality` - Object identity
- `test_waiting_for_response_flag` - Response flag tracking

### 4. test_stack.py - Stack System Tests (26 tests)

Tests the stack implementation per CR 405 (The Stack) and CR 608 (Resolving Spells and Abilities).

**Test Classes:**

**TestStackBasics (5 tests):**
- `test_stack_starts_empty` - Initial empty state
- `test_push_spell_to_stack` - Adding spells
- `test_stack_lifo_ordering` - LIFO ordering verification
- `test_pop_from_empty_stack` - Edge case handling
- `test_stack_iteration_order` - Iteration from top to bottom

**TestSpellCreation (4 tests):**
- `test_create_instant_spell` - Instant spell creation
- `test_create_creature_spell` - Permanent spell creation
- `test_create_spell_with_targets` - Targeted spells
- `test_create_spell_copy` - Spell copies

**TestAbilityCreation (3 tests):**
- `test_create_triggered_ability` - Triggered abilities
- `test_create_activated_ability` - Activated abilities
- `test_ability_with_targets` - Targeted abilities

**TestStackTargeting (3 tests):**
- `test_check_targets_no_targets` - Spells without targets
- `test_spell_fizzle_illegal_targets` - All targets illegal
- `test_partial_targets_legal` - Some targets still legal

**TestStackResolution (3 tests):**
- `test_resolve_top_of_stack` - Normal resolution
- `test_resolve_empty_stack_returns_false` - Empty stack edge case
- `test_resolve_fizzled_spell` - Fizzling on resolution

**TestStackManipulation (5 tests):**
- `test_remove_specific_object` - Counterspell removal
- `test_find_by_id` - Finding by object ID
- `test_clear_stack` - Clearing entire stack
- `test_get_objects_controlled_by` - Filter by controller

**TestStackTimestamps (2 tests):**
- `test_timestamps_increment` - Timestamp ordering
- `test_timestamp_uniqueness` - Unique timestamps

**TestStackEdgeCases (2 tests):**
- `test_spell_description_formatting` - String formatting
- `test_ability_description_formatting` - Ability descriptions

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test File
```bash
pytest tests/test_priority.py -v
pytest tests/test_stack.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_priority.py::TestPriorityBasics -v
```

### Run Specific Test
```bash
pytest tests/test_priority.py::TestPriorityBasics::test_give_priority_to_player -v
```

### Run with Coverage
```bash
pytest tests/ --cov=engine --cov-report=html
```

### Run with Detailed Output
```bash
pytest tests/ -vv --tb=long
```

## Test Results

### Current Status

**test_priority.py:** ✅ **20/20 tests passing** (100%)
- All priority system tests passing
- Complete CR 117 coverage
- APNAP ordering validated
- Edge cases handled

**test_stack.py:** ⚠️ **15/26 tests passing** (58%)
- Basic stack operations: ✅ Passing (mostly)
- Spell/ability creation: ✅ Passing
- Target checking: Needs API alignment
- Resolution: Needs API alignment
- Timestamps: Needs implementation adjustment

### Known Issues

Some stack tests fail due to API differences between the standalone Stack class (stack.py) and the integrated ZoneManager implementation. These can be fixed by:

1. Using `stack_manager.resolve_top()` instead of `stack.resolve_top()`
2. Adjusting timestamp assignments to use game.get_timestamp()
3. Using appropriate zone manager methods

## Test Coverage

The test suite provides coverage for:

### Priority System (CR 117)
- ✅ Giving priority to players
- ✅ Passing priority in turn order
- ✅ All-pass detection
- ✅ Priority after actions
- ✅ APNAP ordering (2-player and multiplayer)
- ✅ Edge cases and error handling

### Stack System (CR 405, 608)
- ✅ LIFO ordering
- ✅ Pushing/popping objects
- ✅ Spell creation (instant, creature, targeted)
- ✅ Ability creation (triggered, activated)
- ⚠️ Target legality checking (needs alignment)
- ⚠️ Resolution mechanics (needs alignment)
- ✅ Stack manipulation (remove, clear, find)
- ⚠️ Timestamp ordering (needs adjustment)

## Best Practices Demonstrated

1. **Fixture Organization**: Comprehensive conftest.py with hierarchical fixtures
2. **Test Class Organization**: Logical grouping by feature area
3. **Test Naming**: Descriptive names following `test_<what>_<expected>` pattern
4. **Documentation**: Docstrings with CR references
5. **Isolation**: Mock objects for testing without full engine
6. **Edge Cases**: Explicit edge case and error condition testing
7. **Assertions**: Clear, specific assertions with helpful messages

## Next Steps

To complete the test infrastructure:

1. ✅ Priority system tests - COMPLETE
2. ✅ Stack system tests - IMPLEMENTED (needs API alignment)
3. 🔲 Integration tests for priority + stack interaction
4. 🔲 Combat system tests
5. 🔲 Turn structure tests
6. 🔲 Mana system tests
7. 🔲 Zone management tests
8. 🔲 State-based action tests
9. 🔲 Triggered ability tests
10. 🔲 Continuous effect tests

## Contributing

When adding new tests:

1. Add fixtures to `conftest.py` if they're reusable
2. Group related tests into test classes
3. Include CR references in docstrings
4. Test both happy path and edge cases
5. Use descriptive test names
6. Keep tests focused and isolated
7. Leverage existing mocks when possible
8. Add parametrized tests for similar scenarios

## References

- [Comprehensive Rules](https://magic.wizards.com/en/rules)
- CR 117: Timing and Priority
- CR 405: The Stack
- CR 608: Resolving Spells and Abilities
- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
