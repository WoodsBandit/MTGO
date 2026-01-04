# MTG Simulation Engine - Rule Violations and Bugs

Analysis Date: 2026-01-03
Engine File: `mtg_sim_package/mtg_engine.py` (5037 lines)

## Critical Bugs

### 1. **Protection Does Not Prevent Combat Damage** (CR 702.16e)
**Severity:** CRITICAL
**Location:** `deal_combat_damage()` lines 3824-3963

**Issue:**
The combat damage assignment code never checks if damage should be prevented by protection. According to CR 702.16e, protection prevents all damage that would be dealt by sources with the stated quality.

**Current Behavior:**
```python
# Line 3876-3910: Assigns damage to blockers
dmg_to_blocker = min(dmg_to_blocker, remaining_damage)
blocker.damage_marked += dmg_to_blocker  # <-- No protection check!
```

**Expected Behavior:**
Before marking damage, the engine must check:
- Does the blocker have protection from the attacker's color?
- Does the attacker have protection from the blocker's color?
- If yes, prevent the damage (don't mark it).

**Example Failure:**
- A white 3/3 creature with protection from red blocks a red 5/5
- Current: Blocker takes 5 damage and dies
- Correct: Blocker takes 0 damage (protection prevents it)

**Fix Required:**
Add protection damage prevention check before lines 3906 and 3924.

---

### 2. **Targets Not Re-Validated on Resolution** (CR 608.2b)
**Severity:** CRITICAL
**Location:** `resolve()` and `resolve_stack_item()` lines 3333-3509

**Issue:**
The engine only checks target validity for Auras (lines 3407-3420), but not for other spells. According to CR 608.2b, ALL spells must check if their targets are still legal when they resolve. If ALL targets are illegal, the spell is countered by game rules.

**Current Behavior:**
```python
def resolve(self, player: Player, card: Card, target: Any, x_value: int = 0):
    # ... (line 3387)
    for ab in card.abilities:
        self._process_ability(ab, player, opp, card, actual_target, x_value)
    # No validation that target still exists or is legal!
```

**Expected Behavior:**
Before processing abilities:
1. Check if target is still on the battlefield (if it's a permanent)
2. Check if target is still a legal target (hexproof/protection may have changed)
3. If ALL targets are illegal, counter the spell by game rules

**Example Failure:**
- Cast "Lightning Bolt" targeting opponent's creature
- Opponent responds by bouncing the creature to hand
- Current: Bolt resolves, `_process_ability()` probably crashes or does nothing
- Correct: Bolt is countered on resolution (target is illegal), goes to graveyard

**Fix Required:**
Add target validation at the start of `resolve()` and `resolve_stack_item()`.

---

### 3. **Trample Damage Assignment Ignores Protection** (CR 702.19b)
**Severity:** HIGH
**Location:** `deal_combat_damage()` lines 3930-3938

**Issue:**
When calculating trample damage, the code assigns "lethal damage" to blockers without considering that protection prevents damage. CR 702.19b states that if damage would be prevented (by protection), you must assign the full damage that would be lethal as if it weren't prevented, but then the actual damage is prevented.

**Current Behavior:**
```python
# Line 3902-3903: Calculate lethal damage
dmg_to_blocker = max(1, blocker_t - blocker.damage_marked)
# Line 3910: Subtract from remaining damage
remaining_damage -= dmg_to_blocker
# Line 3930-3938: Trample the remainder
```

**Expected Behavior:**
If blocker has protection from attacker:
1. Assign full "lethal" damage to blocker (for trample calculation)
2. **Don't actually mark the damage** (protection prevents it)
3. Trample damage = attacker's power minus assigned damage

**Example Failure:**
- 5/5 trampler with first strike attacks
- Opponent blocks with 2/2 with protection from attacker's color
- Current: Assigns 2 damage to blocker, tramples 3 to player
- Correct: Must assign 2 to blocker (prevented), tramples 3 to player (correct by accident)
- BUT if blocker already has 1 damage: Assigns 1 more (line 3903), tramples 4 (WRONG - should be 3)

**Fix Required:**
When assigning lethal damage to a blocker with protection, always assign full toughness worth, not `toughness - damage_marked`.

---

### 4. **Triggered Abilities Lack APNAP Ordering** (CR 603.3b)
**Severity:** HIGH
**Location:** `process_triggers()` lines 2507-2511

**Issue:**
The trigger queue processes triggers in the order they were queued (FIFO). According to CR 603.3b, when multiple triggered abilities trigger simultaneously, they should be put on the stack in APNAP order (Active Player, Non-Active Player).

**Current Behavior:**
```python
def process_triggers(self):
    while self.trigger_queue:
        trigger_type, source, controller, data = self.trigger_queue.pop(0)  # FIFO
        self._resolve_trigger(trigger_type, source, controller, data)
```

**Expected Behavior:**
1. Group all triggers from the same event
2. Sort by controller: Active Player's triggers first, then Non-Active Player's
3. Within each player, controller chooses order (for simplicity, can use card instance_id)
4. Put on stack in reverse order (last in, first out)

**Example Failure:**
- Both players have a creature with "when this attacks, draw a card"
- Current: Whichever trigger was queued first resolves first
- Correct: Active player's trigger should go on stack first (resolves last)

**Fix Required:**
Rewrite `process_triggers()` to sort by APNAP order before processing.

---

### 5. **"When This Dies" Triggers Don't See Death** (CR 603.10)
**Severity:** MEDIUM
**Location:** `fire_dies()` line 2719-2720, and SBA death handling

**Issue:**
According to CR 603.10, "when this dies" triggers must be able to "look back in time" to see the creature's last known information before it left the battlefield. The current implementation queues the trigger AFTER moving the creature to the graveyard, which may work, but doesn't explicitly preserve last known information if needed by the trigger effect.

**Current Behavior:**
```python
# Line 4367-4371 (SBA death)
player.battlefield.remove(creature)
player.graveyard.append(creature)
self.fire_dies(creature, player)
```

The trigger fires after the creature is already in the graveyard.

**Potential Issue:**
If a dies trigger needs to know the creature's power/toughness at the time it died, this might fail if the creature's state is modified by being in the graveyard.

**Example Scenario:**
- Creature with "When this dies, deal damage equal to its power to any target"
- Creature had +1/+1 from an Aura that also died simultaneously
- Should use power at time of death (including Aura bonus), not current graveyard state

**Fix Required:**
Capture last known information before moving to graveyard, pass to trigger.

---

### 6. **State-Based Actions Missing Trigger Timing** (CR 704.3)
**Severity:** MEDIUM
**Location:** `check_state()` lines 4135-4152

**Issue:**
According to CR 704.3, after state-based actions are applied, triggered abilities that triggered during the SBA application are put on the stack BEFORE players get priority. The current implementation processes triggers in `resolve_stack_with_priority()` (line 3093), but the comment at line 4145 suggests triggers should go on stack during `check_state()`.

**Current Behavior:**
```python
def check_state(self) -> bool:
    while self._check_sbas_once():
        pass
    return self.winner is None
    # No trigger processing here!
```

**Expected Behavior:**
After the SBA loop completes:
1. Check for triggered abilities that triggered during SBAs
2. Put them on stack in APNAP order
3. THEN return

**Example Failure:**
- Creature dies due to lethal damage (SBA)
- Another creature has "Whenever a creature dies, draw a card"
- Current: Trigger processed later in stack resolution
- Correct: Trigger should be put on stack before priority is given

**Impact:** Mostly affects timing of triggers relative to priority, probably minor in practice.

---

### 7. **Damage Assignment Order Not Implemented** (CR 510.1c)
**Severity:** MEDIUM
**Location:** `deal_combat_damage()` line 3881

**Issue:**
According to CR 510.1c, the attacking player announces the damage assignment order among multiple blockers. The current implementation sorts blockers by toughness, which is not the same as player choice.

**Current Behavior:**
```python
# Line 3880-3881
# This simulates damage assignment order
blockers_sorted = sorted(blockers, key=lambda b: self.get_creature_with_bonuses(b, all_bf)[1])
```

**Expected Behavior:**
- Attacking player chooses the order (via AI decision)
- Damage must be assigned in that order
- Lethal damage must be assigned to each blocker before moving to the next

**Example Failure:**
- 5/5 attacker blocked by 2/2 and 4/4
- Current: Sorts by toughness, assigns to 2/2 first (correct by coincidence)
- If player wanted to kill the 4/4 instead, they can't

**Impact:** Reduces strategic options, but probably works "well enough" in practice.

---

### 8. **Double Strike + Trample May Not Work Correctly** (CR 702.4c, 702.19)
**Severity:** MEDIUM
**Location:** `deal_combat_damage()` lines 3846-3963

**Issue:**
A creature with both double strike and trample should be able to trample damage in BOTH the first strike damage step and the regular damage step. The current code structure suggests this works, but there's a subtle issue with damage tracking.

**Current Behavior:**
```python
# First strike step:
dmg_to_blocker = max(1, blocker_t - blocker.damage_marked)  # Line 3903
blocker.damage_marked += dmg_to_blocker  # Line 3906
remaining_damage -= dmg_to_blocker  # Line 3910

# Regular damage step (called again with first_strike_step=False):
dmg_to_blocker = max(1, blocker_t - blocker.damage_marked)  # Accounts for first strike damage
```

**Analysis:**
This *should* work correctly. In the first strike step, damage is marked. In the regular step, `blocker.damage_marked` is higher, so less damage is assigned to the blocker, and more tramples over.

**Verification Needed:**
Test case: 5/5 double strike trampler vs 2/2 blocker
- First strike step: Assign 2, trample 3 to player
- Regular step: Blocker already has 2 marked, assign 0, trample 5 to player
- Total trample damage: 8 (correct)

**Status:** Likely correct, but needs explicit test case verification.

---

## Medium Priority Bugs

### 9. **Protection Doesn't Prevent Blocking** (CR 702.16c)
**Severity:** MEDIUM
**Location:** `declare_blocks()` lines 1751-1780

**Issue:**
The code prevents creatures with protection from blocking attackers (lines 1759-1780), but this is backwards. Protection on a BLOCKER doesn't prevent it from blocking. Protection on an ATTACKER prevents creatures with that quality from blocking it.

**Current Behavior:**
```python
# Check if attacker has protection from this blocker's colors
if att.has_keyword("protection from red"):
    # Red blocker can't block (CORRECT)
```

Wait, re-reading the code... this is actually CORRECT. The code checks if the ATTACKER has protection, and if so, prevents the blocker from blocking. Let me re-verify...

```python
for kw in att.keywords:  # Checking attacker's keywords
    if kw_lower.startswith("protection"):
        prot_from = kw_lower.replace("protection from ", "")
        if protected_color in blocker_colors:  # Blocker's color
            can_block = False  # Prevent blocking
```

Yes, this is correct per CR 702.16c. **No bug here.**

---

### 10. **Auras Don't Fall Off Due to Protection** (CR 303.4d)
**Severity:** MEDIUM
**Location:** `_check_sbas_once()` lines 4313-4338

**Issue:**
The Aura SBA check (704.5m) only verifies that the attached permanent still exists, but doesn't check if the Aura can still legally enchant it (e.g., protection gained after attachment).

**Current Behavior:**
```python
# Line 4325-4338: Check if attached permanent exists
if aura.attached_to is not None:
    attached_exists = False
    for p in [self.p1, self.p2]:
        for perm in p.battlefield:
            if perm.instance_id == aura.attached_to:
                attached_exists = True
    if not attached_exists:
        permanents_to_remove.append((aura, player))
```

**Expected Behavior:**
Also check:
- If Aura enchants a creature, does the creature have protection from the Aura's color?
- If yes, Aura falls off (goes to graveyard)

**Example Failure:**
- Red Aura enchants creature
- Creature gains protection from red (via another spell)
- Current: Aura stays attached
- Correct: Aura should fall off as SBA

**Fix Required:**
Add protection check in the Aura SBA section.

---

### 11. **Spell Fizzle Logic Incomplete** (CR 608.2b)
**Severity:** MEDIUM
**Location:** `resolve()` and `resolve_stack_item()`

**Issue:**
The only spell that properly fizzles is Auras (lines 3413-3420). Other targeted spells should also fizzle if their target is illegal on resolution, but there's no general check.

**Current Behavior:**
- Auras check target validity: YES (lines 3407-3416)
- Removal spells: NO (missing check)
- Damage spells: NO (missing check)

**Expected Behavior:**
For ALL targeted spells:
1. On resolution, check if target is still legal
2. If not, counter the spell by game rules (fizzle)
3. Don't execute any effects

**Example Failure:**
- Cast removal spell targeting opponent's creature
- Opponent gives creature hexproof in response
- Current: Removal probably tries to process ability, may crash or succeed incorrectly
- Correct: Spell should fizzle (all targets illegal)

**Fix Required:**
Add target validation at start of `resolve()` for all targeted spells.

---

## Low Priority / Design Issues

### 12. **Simultaneous Deaths Not Truly Simultaneous** (CR 704.3)
**Severity:** LOW
**Location:** `_check_sbas_once()` lines 4362-4395

**Issue:**
The code correctly collects all creatures/permanents that should die, then processes them together, which simulates simultaneity. However, dies triggers are fired one at a time in the loop (line 4371), not batched.

**Current Behavior:**
```python
for creature, player in creatures_to_die:
    # ...
    self.fire_dies(creature, player)  # Fires immediately
```

**Expected Behavior:**
This is probably fine in practice. Triggers are queued, not resolved immediately, so they'll all queue up before any resolve.

**Status:** Likely not a bug, but worth noting for future reference.

---

### 13. **No Layer System Implementation** (CR 613)
**Severity:** LOW
**Location:** N/A (feature not implemented)

**Issue:**
The engine doesn't implement the layer system for continuous effects. It uses a simpler system where bonuses from Auras/Equipment are applied on-the-fly via `get_creature_with_bonuses()`.

**Impact:**
- Most basic interactions work correctly
- Complex layer interactions (e.g., "Blood Moon" + "Urborg, Tomb of Yawgmoth") will not work
- P/T setting effects may not layer correctly with P/T modifying effects

**Status:** Known limitation, acceptable for a simulation engine (not a full rules engine).

---

### 14. **Regeneration Implementation Incomplete** (CR 701.15)
**Severity:** LOW
**Location:** `_check_sbas_once()` lines 4240-4247

**Issue:**
Regeneration is implemented as a shield that's checked during SBAs, but the shield creation is not shown in the codebase. Additionally, regeneration should remove the creature from combat (CR 701.15c), which the code does, but it's unclear how the combat state is updated.

**Current Behavior:**
```python
if creature.regenerate_shield > 0 and can_regenerate:
    creature.regenerate_shield -= 1
    creature.is_tapped = True
    creature.damage_marked = 0
    creature.deathtouch_damage = False
```

**Missing:**
- Where is `regenerate_shield` set? (Not found in codebase)
- How is "remove from combat" implemented?

**Status:** Partial implementation, probably not used in current card database.

---

### 15. **No Timestamp System for Layers** (CR 613.7)
**Severity:** LOW
**Location:** N/A

**Issue:**
Continuous effects should track timestamps to determine which applies first when effects are in the same layer. The engine uses `instance_id` for legend rule (line 4307), but doesn't track timestamps for effects.

**Status:** Acceptable limitation for a simulation engine.

---

## Edge Cases and Rule Ambiguities

### 16. **Deathtouch Damage Assignment with Multiple Blockers**
**Severity:** LOW
**Location:** `deal_combat_damage()` lines 3896-3904

**Current Behavior:**
```python
if has_deathtouch:
    dmg_to_blocker = 1  # Assign only 1 damage
```

**Verification:**
This is correct per CR 702.2c. With deathtouch, 1 damage is lethal, so attacker can assign 1 to each blocker and trample the rest.

**Status:** CORRECT

---

### 17. **Counter Annihilation Timing** (CR 704.5q)
**Severity:** LOW
**Location:** `_check_sbas_once()` lines 4256-4274

**Current Behavior:**
+1/+1 and -1/-1 counters annihilate as an SBA.

**Verification:**
This is correct per CR 704.5q.

**Status:** CORRECT

---

## Summary

### Critical Bugs (Must Fix):
1. **Protection doesn't prevent combat damage** - Damage dealt through protection
2. **Targets not re-validated on resolution** - Spells don't fizzle when target becomes illegal
3. **Trample + protection interaction** - Incorrect damage assignment calculation

### High Priority Bugs:
4. **Triggered abilities lack APNAP ordering** - Wrong stack order for simultaneous triggers
5. **"When dies" triggers don't capture last known information** - May lose state info

### Medium Priority Bugs:
6. **SBAs don't put triggers on stack at correct time** - Timing issue with priority
7. **Damage assignment order not player-controlled** - AI can't choose blocker order
8. **Auras don't fall off from protection** - Protection gained post-attachment not checked
9. **Spell fizzle logic incomplete** - Non-Aura spells don't validate targets on resolution

### Low Priority / Design Limitations:
10. **No layer system** - Simplified continuous effects model
11. **No timestamp tracking** - Can't resolve layer conflicts correctly
12. **Regeneration incomplete** - Shield creation not implemented

### Verified Correct:
- Protection prevents blocking (correctly implemented)
- Deathtouch damage assignment (correct)
- Counter annihilation (correct)
- Simultaneous death (acceptable implementation)
- Double strike + trample (likely correct, needs test)

---

## Testing Recommendations

Create unit tests for:
1. Protection preventing combat damage (both directions)
2. Protection + trample interaction
3. Spell fizzling when target gains hexproof in response
4. Multiple blockers with damage assignment order choices
5. APNAP ordering of simultaneous triggers
6. Aura falling off when enchanted creature gains protection
7. Double strike + trample damage distribution

---

## Compliance Summary

**Comprehensive Rules Coverage:**

| Rule Section | Implementation Status | Bugs Found |
|--------------|----------------------|------------|
| CR 510 (Combat Damage) | Partial | 3 bugs |
| CR 608 (Stack Resolution) | Incomplete | 2 bugs |
| CR 603 (Triggered Abilities) | Basic | 2 bugs |
| CR 704 (State-Based Actions) | Good | 2 bugs |
| CR 702.16 (Protection) | Incomplete | 2 bugs |
| CR 613 (Layers) | Not Implemented | N/A |

**Overall Assessment:** The engine implements core MTG rules reasonably well for a simulation, but has critical bugs in combat damage prevention (protection), target validation, and trigger ordering. For competitive play simulation, these bugs could significantly affect game outcomes.
