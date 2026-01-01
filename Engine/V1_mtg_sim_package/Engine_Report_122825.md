# MTG Simulation Engine v2.1 - Comprehensive Audit Report
**Date:** December 28, 2025
**Engine Version:** 2.1
**Auditor:** Claude (Opus 4.5)

---

## Executive Summary

This report provides a comprehensive audit of `mtg_engine.py` against the official Magic: The Gathering Comprehensive Rules (November 14, 2025) and MTGO client documentation. The engine is a **simplified simulation** designed for deck testing rather than full rules compliance. While it captures core gameplay patterns effectively, there are significant deviations from official rules that users should understand.

**Overall Assessment:** The engine provides **reasonable approximation** for testing deck matchups but should not be considered rules-accurate for edge cases or competitive play analysis.

---

## Table of Contents

1. [Card Database Overview](#1-card-database-overview)
2. [Engine Architecture Analysis](#2-engine-architecture-analysis)
3. [Rules Compliance Audit](#3-rules-compliance-audit)
4. [Critical Deviations](#4-critical-deviations)
5. [Keyword Implementation Review](#5-keyword-implementation-review)
6. [Ability System Analysis](#6-ability-system-analysis)
7. [Combat System Audit](#7-combat-system-audit)
8. [Recommendations](#8-recommendations)

---

## 1. Card Database Overview

### Statistics
- **Total Cards:** 3,164 Standard-legal cards
- **Source:** Scryfall API auto-generated
- **Format:** Python dictionary (`CARD_DATABASE`)

### Card Data Structure
```python
{
    "Card Name": {
        "type": "creature|instant|sorcery|enchantment|artifact|planeswalker|land",
        "cost": float,      # CMC (Converted Mana Cost)
        "power": int,       # Creatures only
        "toughness": int,   # Creatures only
        "keywords": [...],  # Combat keywords
        "abilities": [...], # Special abilities
        "loyalty": int      # Planeswalkers only
    }
}
```

### Database Limitations

| Issue | Impact | Severity |
|-------|--------|----------|
| No color identity stored | Cannot enforce color-based effects | Medium |
| No mana pip information | All costs treated as generic | High |
| Modal cards simplified | Only primary mode tracked | Medium |
| Transform/MDFC cards | Combined stats, no transform logic | High |
| No rarity data | Cannot simulate draft/sealed | Low |

### Sample Card Entries Reviewed

- Standard creatures with keywords (flying, deathtouch, trample)
- Instants/sorceries with damage abilities
- Planeswalkers with loyalty counters
- Dual-faced cards (represented with "//")
- Recent Standard sets including Avatar: The Last Airbender and Final Fantasy crossovers

---

## 2. Engine Architecture Analysis

### Core Data Structures

#### Card Class (`mtg_engine.py:31-64`)
```python
@dataclass
class Card:
    name: str
    mana_cost: int
    card_type: str
    power: int = 0
    toughness: int = 0
    keywords: List[str]
    abilities: List[str]
    loyalty: int = 0
    instance_id: int = 0
    is_tapped: bool = False
    damage_marked: int = 0
    summoning_sick: bool = True
    counters: Dict[str, int]
    controller: int = 0
```

**Effective Stats Methods:**
- `eff_power()` - Base power + "+1/+1" counters
- `eff_toughness()` - Base toughness + "+1/+1" counters

#### Player Class (`mtg_engine.py:67-91`)
Tracks: life, library, hand, battlefield, graveyard, land_played, spells_cast

**Helper Methods:**
- `untapped_lands()` - Available mana
- `creatures()` - Battlefield creatures
- `attackers_available()` - Non-sick, untapped creatures (or with haste)
- `total_power()` - Sum of creature power

### Game Flow

```
deal_hands() → 7 cards each
    ↓
play_turn() loop (max 30 turns):
    1. Untap all permanents
    2. Remove summoning sickness
    3. Clear damage markers
    4. Draw card (except P1 turn 1)
    5. AI main phase actions
    6. Combat phase
    7. Switch active player
    ↓
Winner determined by life or turn limit
```

---

## 3. Rules Compliance Audit

### Turn Structure Comparison

| Phase/Step | Official Rules | Engine Implementation | Compliant? |
|------------|---------------|----------------------|------------|
| **Beginning Phase** | | | |
| Untap Step | Untap, no priority | `c.is_tapped = False` | Partial |
| Upkeep Step | Triggers, priority | Not implemented | NO |
| Draw Step | Draw, priority | `self.draw(act)` | Partial |
| **Main Phase** | | | |
| Pre-combat Main | Cast spells, priority passes | AI casts all at once | NO |
| **Combat Phase** | | | |
| Beginning of Combat | Priority passes | Not implemented | NO |
| Declare Attackers | Tap attackers, priority | `a.is_tapped = True` | Partial |
| Declare Blockers | Choose blockers, priority | AI blocking logic | Partial |
| Combat Damage | Assign/deal simultaneously | Simplified | Partial |
| End of Combat | Triggers, priority | Not implemented | NO |
| **Main Phase 2** | Not implemented | NO | NO |
| **Ending Phase** | | | |
| End Step | Triggers, priority | Not implemented | NO |
| Cleanup Step | Discard, damage clears | `c.damage_marked = 0` | Partial |

### Priority System

**Official Rules (Rule 117):**
> "Priority is the right to cast a spell, activate an ability, or take a special action. Players receive priority at specific points and must pass before the game progresses."

**Engine Implementation:**
- **NO priority system exists**
- AI takes all actions sequentially without opponent response windows
- Instant-speed interaction impossible
- No stack for spells/abilities

**Impact:** HIGH - Fundamentally changes game dynamics

### Stack Implementation

**Official Rules (Rule 405):**
> "The stack is a zone where spells and abilities wait to resolve. Objects resolve in LIFO (last-in-first-out) order after all players pass priority."

**Engine Implementation:**
- **NO stack exists**
- Spells/abilities resolve immediately upon casting
- No response window between cast and resolution
- Triggered abilities resolve immediately

**Impact:** HIGH - Combat tricks, counterspells, and interaction are impossible

---

## 4. Critical Deviations

### 4.1 No Stack / No Priority

**Location:** `mtg_engine.py:497-521` (`resolve()` method)

The `resolve()` function immediately processes effects without any stack mechanism:

```python
def resolve(self, player: Player, card: Card, target: Any):
    # Effects happen immediately - no stack, no priority
    for ab in card.abilities:
        self._process_ability(ab, player, opp, card, target)
```

**Official Rule 608:** Spells and abilities resolve one at a time after all players pass priority. The engine skips this entirely.

### 4.2 No Instant-Speed Interaction

**Problem:** The engine cannot represent:
- Counterspells
- Combat tricks (Giant Growth effects)
- Flash creatures blocking
- Activated abilities in response

**Why It Matters:** Many competitive deck strategies rely on instant-speed interaction. Testing a control deck's counterspell package is impossible.

### 4.3 Single Main Phase

**Location:** `mtg_engine.py:667-726` (`play_turn()`)

The engine has only one main phase before combat. Official rules have two main phases (pre-combat and post-combat).

**Impact:** Strategies involving post-combat card advantage or holding up mana are not simulated.

### 4.4 No Upkeep/End Step Triggers

Many cards trigger during upkeep or end step. The engine skips these phases entirely:

- Upkeep triggers (cumulative upkeep, "at the beginning of your upkeep")
- End step triggers ("at the beginning of your end step")
- "Until end of turn" effects don't expire properly

### 4.5 Simplified Mana System

**Location:** `mtg_engine.py:481-487` (`tap_lands()`)

```python
def tap_lands(self, player: Player, n: int):
    tapped = 0
    for c in player.battlefield:
        if c.card_type == "land" and not c.is_tapped and tapped < n:
            c.is_tapped = True
            tapped += 1
```

**Issues:**
- No color requirements - all mana treated as colorless
- No mana abilities (Birds of Paradise, mana dorks)
- No mana pool management
- Cannot model mana screw/flood due to colors

### 4.6 No Mulligan System

The engine deals 7 cards to each player with no option to mulligan. The London Mulligan system is not implemented.

---

## 5. Keyword Implementation Review

### Implemented Keywords

| Keyword | Rule Reference | Implementation | Accuracy |
|---------|---------------|----------------|----------|
| **Trample** | 702.19 | Excess damage to player | CORRECT |
| **Haste** | 702.10 | Ignores summoning sickness | CORRECT |
| **Flying** | 702.9 | Evasion check | CORRECT |
| **Reach** | 702.17 | Can block flying | CORRECT |
| **Lifelink** | 702.15 | Gain life = damage dealt | CORRECT |
| **First Strike** | 702.7 | **NOT IMPLEMENTED** | MISSING |
| **Double Strike** | 702.4 | **NOT IMPLEMENTED** | MISSING |
| **Deathtouch** | 702.2 | **NOT IMPLEMENTED** | MISSING |
| **Menace** | 702.110 | Listed but not enforced | BROKEN |
| **Vigilance** | 702.20 | Listed but not enforced | BROKEN |
| **Ward** | 702.21 | Listed but not enforced | BROKEN |
| **Hexproof** | 702.11 | Listed but not enforced | BROKEN |
| **Flash** | 702.8 | Listed but not enforced | BROKEN |

### Critical Missing: First Strike

**Official Rule 702.7:**
> "If at least one attacking or blocking creature has first strike or double strike as the combat damage step begins, the only creatures that assign combat damage in that step are those with first strike or double strike. After that step... the phase gets a second combat damage step."

**Engine Code (`mtg_engine.py:606-654`):**
Combat damage is dealt simultaneously with no first strike sub-step. This is a **major deviation** affecting creature combat calculations.

### Critical Missing: Deathtouch

**Official Rule 702.2:**
> "Deathtouch is a static ability. Any amount of damage dealt to a creature by a source with deathtouch is lethal damage."

**State-Based Action 704.5h:**
> "If a creature has been dealt damage by a source with deathtouch since the last time state-based actions were checked, that creature is destroyed."

**Engine Implementation:** Deathtouch appears in card data but combat never checks for it. A 1/1 deathtouch should kill any creature it damages - this doesn't happen.

### Critical Missing: Vigilance

**Official Rule 702.20:**
> "Attacking doesn't cause creatures with vigilance to tap."

**Engine Code (`mtg_engine.py:613-614`):**
```python
for a in attackers:
    a.is_tapped = True  # ALL attackers tap - vigilance ignored
```

---

## 6. Ability System Analysis

### Supported Abilities

| Ability Code | Effect | Implementation |
|--------------|--------|----------------|
| `damage_X` | Deal X damage to target | Working |
| `damage_X_sweep` | X to player + all creatures | Working |
| `draw_X` | Draw X cards | Working |
| `destroy_creature` | Destroy target creature | Working |
| `exile` | Exile target | Working |
| `bounce` | Return to hand | Working |
| `bite` | Your creature deals power damage | Working |
| `fight` | Bite + target hits back | Working |
| `create_token_P_T` | Create P/T token | Working |
| `token_on_spell` / `spell_trigger` | Create 1/1 on spell cast | Working |
| `magebane` | Damage when opponent casts spells | Working (priority threat) |
| `landfall` | Trigger on land ETB | Listed, partial |
| `mana_dork` | Tap for mana | Listed, not functional |
| `pump_2_2` | +2/+2 effect | Listed, partial |
| `counter_spell` | Counter target spell | **Cannot work (no stack)** |

### Ability Processing

**Location:** `mtg_engine.py:523-604` (`_process_ability()`)

Abilities are processed in order via string matching:

```python
if ab.startswith("damage_"):
    # damage logic
elif ab.startswith("draw_"):
    # draw logic
elif ab in ["destroy_creature", "exile"]:
    # removal logic
```

**Limitation:** No support for:
- Modal abilities (choose one)
- X costs (variables)
- Targeting restrictions
- "Each opponent" vs "target opponent"
- Conditional effects ("if you control...")

### Magebane Special Handling

The AI prioritizes killing creatures with `magebane` ability because they deal escalating damage when the opponent casts spells. This is correctly identified as a high-priority threat (`mtg_engine.py:225-226`):

```python
if "magebane" in c.abilities:
    threat += 15  # Massive threat priority
```

---

## 7. Combat System Audit

### Damage Assignment

**Recent Rules Change (Magic: The Gathering Foundations 2024):**
> "The rule update abolished the notion of damage assignment order. Instead, the attacking player can divide the attacker's combat damage as they choose among the creatures it's blocked by."

**Engine Implementation:** The engine never had damage assignment order - it uses simplified 1:1 blocking only. This happens to align with the newer rules philosophy but doesn't properly implement multiple blockers.

### Combat Code Analysis

**Location:** `mtg_engine.py:606-654` (`combat()`)

```python
def combat(self, attackers: List[Card], blocks: Dict[int, int]):
    # Simplified: 1 attacker maps to 0-1 blocker
    for att in attackers:
        blocker = next((c for c in opp.battlefield
                       if c.instance_id == blocks.get(att.instance_id)), None)
        if blocker:
            # Mutual damage
            blocker.damage_marked += att.eff_power()
            att.damage_marked += blocker.eff_power()
```

### Combat Issues

| Issue | Official Rule | Engine Behavior |
|-------|--------------|-----------------|
| Multiple blockers | Single creature can be blocked by many | 1:1 only |
| First strike | Creates additional damage step | Not implemented |
| Deathtouch | 1 damage = lethal | Not checked |
| Vigilance | No tap when attacking | Always taps |
| Menace | Must be blocked by 2+ | Not enforced |
| Trample with deathtouch | 1 damage lethal, rest tramples | No deathtouch |
| Lifelink timing | Simultaneous with damage | Correct |
| Damage prevention | Prevent X damage effects | Not implemented |

### Blocking AI

**Location:** `mtg_engine.py:379-425` (`AI.blockers()`)

The blocking AI uses a scoring system:

```python
score = 0
if kills and survives:  # Ideal trade
    score = 10
elif kills:  # Trade down
    score = 5
elif survives:  # Chump + survive
    score = 2
else:  # Chump and die
    score = -5

if "deathtouch" in b.keywords:
    score += 5  # Deathtouch bonus
```

**Problem:** The deathtouch bonus affects blocking decisions but deathtouch isn't actually applied in damage resolution.

---

## 8. Recommendations

### Priority 1: Critical Fixes

1. **Implement First Strike**
   - Add second combat damage step when first/double strike present
   - Check creatures for first_strike keyword before damage assignment
   - Estimated complexity: Medium

2. **Implement Deathtouch**
   - After damage marked, check source for deathtouch
   - If deathtouch source dealt any damage, creature dies
   - Estimated complexity: Low

3. **Implement Vigilance**
   - Check for vigilance keyword before tapping attackers
   - `if "vigilance" not in a.keywords: a.is_tapped = True`
   - Estimated complexity: Low

### Priority 2: Gameplay Improvements

4. **Add Second Main Phase**
   - Duplicate main phase logic after combat
   - Allow post-combat spell casting
   - Estimated complexity: Low

5. **Multiple Blockers**
   - Allow multiple creatures to block one attacker
   - Distribute damage among blockers
   - Estimated complexity: Medium

6. **Menace Enforcement**
   - Require 2+ blockers for menace creatures
   - Estimated complexity: Low

### Priority 3: Advanced Features

7. **Basic Stack Implementation**
   - Add spell/ability queue
   - Allow simple responses (at minimum, triggered abilities)
   - Estimated complexity: High

8. **Upkeep/End Step Triggers**
   - Process "at beginning of upkeep" abilities
   - Process "at beginning of end step" abilities
   - Estimated complexity: Medium

9. **Mulligan System**
   - Implement London Mulligan
   - Allow hand evaluation before game start
   - Estimated complexity: Low

### Not Recommended for This Engine

These features would require fundamental architecture changes:

- Full priority/stack system with instant-speed interaction
- Color-specific mana requirements
- Modal spell choices
- Planeswalker loyalty ability activation
- Equipment/Aura attachment
- Transform/flip card mechanics

---

## Appendix A: Rule References

### Official MTG Comprehensive Rules (November 14, 2025)
- **Rule 117:** Timing and Priority
- **Rule 405:** Stack Zone
- **Rule 500-514:** Turn Structure
- **Rule 506-511:** Combat Phase
- **Rule 510:** Combat Damage Step
- **Rule 608:** Resolving Spells and Abilities
- **Rule 702:** Keyword Abilities
- **Rule 704:** State-Based Actions

### Sources Consulted
- [MTG Comprehensive Rules](https://magic.wizards.com/en/rules)
- [Yawgatog Hyperlinked Rules](https://yawgatog.com/resources/magic-rules/)
- [MTGO Advanced Client Guide](https://www.mtgo.com/en/mtgo/advanced)
- [MTG Wiki - Stack](https://mtg.fandom.com/wiki/Stack)
- [MTG Wiki - Combat Damage Step](https://mtg.fandom.com/wiki/Combat_damage_step)
- [MTG Wiki - State-Based Actions](https://mtg.fandom.com/wiki/State-based_action)

---

## Appendix B: Engine File Reference

| File | Size | Purpose |
|------|------|---------|
| `mtg_engine.py` | 30KB | Core simulation (868 lines) |
| `card_database.py` | 313KB | 3,164 card definitions |
| `README.md` | 2.7KB | Usage documentation |

### Key Functions

| Function | Line | Purpose |
|----------|------|---------|
| `parse_decklist()` | 112 | Parse MTGO .txt format |
| `AI.board_eval()` | 219 | Evaluate board state |
| `AI.main_phase()` | 316 | Decide main phase actions |
| `AI.attackers()` | 352 | Choose attackers |
| `AI.blockers()` | 379 | Choose blockers |
| `Game.resolve()` | 497 | Resolve spell effects |
| `Game.combat()` | 606 | Process combat damage |
| `Game.play_turn()` | 667 | Execute one turn |
| `run_match()` | 753 | Run complete match series |

---

**Report Complete**

*This audit was performed against the official Magic: The Gathering Comprehensive Rules effective November 14, 2025. The engine version audited was v2.1 as found in the provided source files.*
