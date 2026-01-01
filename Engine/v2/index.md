# MTG Engine V3 Development - Quick Reference Index

> **READ THIS FIRST** at the start of each session to regain context.

---

## Project Summary

**Goal:** Transform V1 "quick deck testing" engine into a rules-accurate MTG simulator for competitive analysis.

**Current Status:** V3 ENGINE BUILD COMPLETE - All 15 phases implemented, 5/5 tests passing.

**Key Documents:**
| Document | Location | Purpose |
|----------|----------|---------|
| Development Plan | `v2/plan.md` | 15-phase implementation roadmap |
| Session Logs | `v2/logs.md` | Work history and decisions |
| Build Checkpoint | `v3/CHECKPOINT.md` | Current build status |
| V1 Engine Audit | `../Engine_Report_122825.md` | Detailed analysis of V1 engine |
| V1 Engine | `V1_mtg_sim_package/mtg_engine.py` | Reference implementation |
| Card Database | `V1_mtg_sim_package/card_database.py` | 3,164 Standard cards |

---

## Current Status: BUILD COMPLETE

### Test Results (All Passing)
```
============================================================
MTG ENGINE V3 - Integration Tests
============================================================
  Imports: PASS (13/13 modules)
  Deck Loading: PASS (16 decks found)
  Game Setup: PASS
  Mana System: PASS
  Combat Keywords: PASS

Total: 5 passed, 0 failed
============================================================
```

### Phase Status
| Phase | Name | Status |
|-------|------|--------|
| 0 | Foundation | COMPLETE |
| 1-2 | Turn/Priority/Stack | COMPLETE |
| 3-4 | Mana/SBA | COMPLETE |
| 5-7 | Targeting/Combat | COMPLETE |
| 8-11 | Abilities/Effects | COMPLETE |
| 12-15 | Cards/AI/Tests | COMPLETE |

---

## V3 Engine Architecture (Implemented)

```
┌─────────────────────────────────────────────────────────────┐
│                      MATCH RUNNER                           │
│  (match.py - Best-of-3, deck loading, results)              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      GAME ENGINE                            │
│  (game.py - Turn structure, priority, stack, SBAs)          │
└─────────────────────────────────────────────────────────────┘
                              │
┌──────────────┬───────────────────┬─────────────────────────┐
│   ZONES      │   OBJECTS         │   EFFECTS               │
│  (zones.py)  │  (objects.py)     │  (effects/*.py)         │
│  7 zones     │  Card, Permanent  │  Triggered, Activated   │
│  Library     │  Spell, Token     │  Continuous, Replacement│
│  Hand, etc.  │                   │  7-Layer System         │
└──────────────┴───────────────────┴─────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    CARD DATABASE                            │
│  (cards/database.py, parser.py)                             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      AI AGENTS                              │
│  (ai/agent.py - Priority decisions, combat)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure (Implemented)

```
Engine/
├── V1_mtg_sim_package/          # Original engine (reference)
│   ├── mtg_engine.py            # 868 lines
│   ├── card_database.py         # 3,164 cards
│   └── README.md
│
├── v2/                          # Documentation
│   ├── plan.md                  # 15-phase development plan
│   ├── logs.md                  # Session logs
│   └── index.md                 # This file
│
└── v3/                          # NEW ENGINE (31 files)
    ├── CHECKPOINT.md            # Build status
    ├── __init__.py
    ├── engine/
    │   ├── __init__.py          # Lazy imports
    │   ├── types.py             # 1,600+ lines - All enums/types
    │   ├── events.py            # 1,000+ lines - Event bus
    │   ├── zones.py             # 1,200+ lines - Zone management
    │   ├── objects.py           # GameObject, Permanent, Spell
    │   ├── player.py            # Player class
    │   ├── priority.py          # Priority system (CR 117)
    │   ├── stack.py             # Stack (CR 405)
    │   ├── mana.py              # Mana system
    │   ├── sba.py               # State-based actions (CR 704)
    │   ├── targeting.py         # Target system
    │   ├── combat.py            # Combat with keywords
    │   ├── turns.py             # Turn structure
    │   ├── game.py              # 1,400+ lines - Main Game
    │   ├── match.py             # Match runner
    │   ├── effects/
    │   │   ├── __init__.py
    │   │   ├── triggered.py     # Triggered abilities (CR 603)
    │   │   ├── activated.py     # Activated abilities
    │   │   ├── continuous.py    # Continuous effects
    │   │   ├── replacement.py   # Replacement effects (CR 614)
    │   │   └── layers.py        # 7-layer system (CR 613)
    │   └── keywords/
    │       ├── __init__.py
    │       └── static.py        # Flying, trample, etc.
    ├── cards/
    │   ├── __init__.py
    │   ├── database.py          # Card database
    │   └── parser.py            # MTGO decklist parser
    ├── ai/
    │   ├── __init__.py
    │   └── agent.py             # AI framework
    └── tests/
        ├── __init__.py
        └── test_runner.py       # Integration tests
```

---

## Key Features Implemented

| Feature | CR Reference | Module |
|---------|-------------|--------|
| Priority System | CR 117 | priority.py |
| The Stack | CR 405 | stack.py |
| Turn Structure | CR 500-514 | turns.py |
| Combat Phases | CR 506-511 | combat.py |
| 7-Layer System | CR 613 | effects/layers.py |
| Replacement Effects | CR 614 | effects/replacement.py |
| Triggered Abilities | CR 603 | effects/triggered.py |
| State-Based Actions | CR 704 | sba.py |
| Keywords | CR 702 | keywords/static.py |

### Combat Keywords Working:
- Flying, Trample, Deathtouch, First Strike
- Double Strike, Lifelink, Vigilance
- Haste, Menace, Reach

---

## Quick Commands

```python
# Run V1 engine (for reference)
from V1_mtg_sim_package.mtg_engine import run_match
run_match(deck1_txt, deck2_txt, matches=5, verbose=True)

# V3 engine usage
import sys
sys.path.insert(0, "path/to/Engine/v3")

from engine.game import Game
from engine.player import Player
from engine.match import Match

# Run integration tests
python tests/test_runner.py
```

---

## Test Decks Available

16 decks in `/MTGO/decks/12.28.25/`:
- Boros_Auras_AI.txt
- Dimir_Midrange_Meta_AI.txt
- Elves_Tribal_AI.txt
- Gruul_Spell_Punisher_AI.txt
- Mono_Red_Aggro_Meta_AI.txt
- And 11 more...

---

## Next Development Steps

1. **Connect Card Database** - Link V1's 3,164 cards to V3 engine
2. **Card Abilities** - Implement card-specific triggered/activated abilities
3. **Full Game Simulation** - Run complete games with test decks
4. **AI Strategy** - Develop decision-making algorithms
5. **Validation** - Test against known MTG interactions

---

## Essential Rules References

| Topic | CR Section | Key Points |
|-------|------------|------------|
| Priority | 117 | Active player gets priority first; all must pass for resolution |
| Stack | 405 | LIFO; objects resolve one at a time; priority between |
| Turn Structure | 500-514 | Untap→Upkeep→Draw→Main→Combat→Main2→End→Cleanup |
| Combat | 506-511 | 5 steps; first strike creates extra damage step |
| Casting | 601 | Announce→modes→targets→division→costs→pay |
| Resolution | 608 | Check targets→execute effects→zone change |
| Continuous Effects | 613 | 7 layers; timestamps; dependencies |
| Replacement | 614 | "Instead"; self-replacement first; player chooses order |
| Keywords | 702 | Flying, trample, deathtouch, first strike, etc. |
| State-Based Actions | 704 | Checked before priority; life, damage, toughness |

---

## Glossary

| Term | Meaning |
|------|---------|
| SBA | State-Based Action (CR 704) |
| CR | Comprehensive Rules |
| APNAP | Active Player, Non-Active Player (order) |
| LIFO | Last In, First Out (stack resolution) |
| ETB | Enters The Battlefield |
| LTB | Leaves The Battlefield |
| CMC | Converted Mana Cost (now "mana value") |
| P/T | Power/Toughness |

---

## Resources

- **MTG Comprehensive Rules:** [magic.wizards.com/en/rules](https://magic.wizards.com/en/rules)
- **Hyperlinked Rules:** [yawgatog.com/resources/magic-rules](https://yawgatog.com/resources/magic-rules/)
- **Scryfall API:** [scryfall.com/docs/api](https://scryfall.com/docs/api)

---

*Index created: December 28, 2025*
*Last updated: December 28, 2025 - V3 BUILD COMPLETE*
