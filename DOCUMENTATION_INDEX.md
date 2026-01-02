# MTGO Engine Documentation Index

Complete documentation for the MTGO Magic: The Gathering game engine.

## Quick Navigation

| Document | Purpose | When to Read |
|----------|---------|--------------|
| [QUICKSTART.md](QUICKSTART.md) | Get running in 5 minutes | **Start here** for first-time setup |
| [INSTALLATION.md](INSTALLATION.md) | Complete installation guide | Troubleshooting setup issues |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and architecture | Understanding how the engine works |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Complete API documentation | Building custom features or AI |

## Documentation Overview

### QUICKSTART.md (5.4 KB)

**What it covers:**
- Prerequisites (Python 3.10+, zero dependencies)
- Running your first match in under 5 minutes
- Expected output and basic troubleshooting
- Deck format requirements
- Viewing game replays

**Best for:** Getting the engine running immediately.

**Key sections:**
- Prerequisites
- Installation (2-step process)
- Running Your First Match (3 options)
- Expected Output
- Quick Troubleshooting

---

### INSTALLATION.md (12 KB)

**What it covers:**
- Detailed system requirements
- Platform-specific Python installation (Windows, macOS, Linux)
- Project setup and verification
- Configuration options
- Comprehensive troubleshooting guide
- Advanced setup (virtual environments, development, servers)

**Best for:** In-depth installation, configuration, and resolving issues.

**Key sections:**
- System Requirements
- Python Installation (all platforms)
- Project Setup
- Verification Checklist
- Configuration (GameConfig options)
- Troubleshooting (import errors, path issues, memory, permissions)
- Advanced Setup (virtual environments, performance, headless servers)

---

### ARCHITECTURE.md (52 KB)

**What it covers:**
- High-level system overview and design philosophy
- Detailed module descriptions (15+ subsystems)
- Data flow diagrams (initialization, turn execution, priority)
- Game loop architecture
- Priority and stack system (with detailed examples)
- Design decisions and rationale
- Extension points for custom development

**Best for:** Understanding the engine internals, contributing code, or implementing custom features.

**Key sections:**
- Executive Summary
- System Overview (component diagram)
- Design Philosophy (rules fidelity, zero dependencies, type safety)
- Core Architecture (directory structure, type system)
- Module Descriptions:
  - Game, Objects, Zones, Priority, Stack, Combat, Mana, Turns, Events, SBA, AI
- Data Flow (initialization, turn execution, spell casting, stack resolution)
- Game Loop Architecture (main loop, spell casting, stack resolution)
- Priority and Stack System (detailed mechanics, interaction patterns)
- Design Decisions (why zero dependencies, dataclasses, event bus, SimpleAI)
- Extension Points (custom cards, AI agents, keywords, replay viewers)

---

### docs/API_REFERENCE.md (36 KB)

**What it covers:**
- Complete API reference for all public classes
- Type system documentation (enums, type aliases)
- Core classes (Game, GameConfig, GameResult)
- Game objects (GameObject, Card, Permanent, Player, ManaPool)
- AI agent interface (AIAgent, SimpleAI, CardInfo, PermanentInfo)
- Card database (CardDatabase, CardData, DecklistParser, Deck)
- Events system (EventBus, event types)
- Utilities (Match runner, Replay recorder)
- Usage examples (complete game, custom AI, tournament)

**Best for:** Writing code that uses the engine, implementing custom AI, extending functionality.

**Key sections:**
- Overview (import paths)
- Core Classes (Game, GameConfig, GameResult)
- Type System (all enums and type aliases)
- Game Objects (full API for Card, Permanent, Player, etc.)
- AI Agent Interface (how to implement custom AI)
- Card Database (loading and parsing decks)
- Events System (event-driven programming)
- Utilities (match/tournament runners, replay system)
- Usage Examples (complete working code examples)

---

## Reading Paths

### For Different User Types

#### First-Time User (Just Want to Run Games)

1. [QUICKSTART.md](QUICKSTART.md) - Run your first game in 5 minutes
2. [INSTALLATION.md](INSTALLATION.md) - Only if you encounter issues

**Time commitment:** 5-15 minutes

---

#### Developer (Want to Understand the System)

1. [QUICKSTART.md](QUICKSTART.md) - Get it running first
2. [ARCHITECTURE.md](ARCHITECTURE.md) - Understand the design
3. [docs/API_REFERENCE.md](docs/API_REFERENCE.md) - Reference while coding

**Time commitment:** 1-2 hours for full understanding

---

#### AI Researcher (Want to Build Custom Agents)

1. [QUICKSTART.md](QUICKSTART.md) - Run basic games
2. [docs/API_REFERENCE.md](docs/API_REFERENCE.md) → "AI Agent Interface" section
3. [ARCHITECTURE.md](ARCHITECTURE.md) → "AI Agent System" section
4. [docs/API_REFERENCE.md](docs/API_REFERENCE.md) → "Usage Examples" → Custom AI Example

**Time commitment:** 30-45 minutes

---

#### Contributor (Want to Add Features)

1. [QUICKSTART.md](QUICKSTART.md) - Run it first
2. [ARCHITECTURE.md](ARCHITECTURE.md) - Read completely for full understanding
3. [docs/API_REFERENCE.md](docs/API_REFERENCE.md) - Reference while coding
4. [INSTALLATION.md](INSTALLATION.md) → "Development Setup"

**Time commitment:** 2-3 hours for comprehensive understanding

---

## Documentation Statistics

| Document | Size | Sections | Code Examples | Diagrams |
|----------|------|----------|---------------|----------|
| QUICKSTART.md | 5.4 KB | 10 | 8 | 1 (output) |
| INSTALLATION.md | 12 KB | 22 | 25 | 0 |
| ARCHITECTURE.md | 52 KB | 45 | 30+ | 5 (ASCII) |
| API_REFERENCE.md | 36 KB | 50+ | 20+ | 0 |
| **Total** | **105 KB** | **127+** | **83+** | **6** |

## Key Concepts Cross-Reference

### Finding Information About...

| Topic | Primary Document | Secondary Document |
|-------|------------------|-------------------|
| **Installation** | INSTALLATION.md | QUICKSTART.md |
| **First Run** | QUICKSTART.md | INSTALLATION.md |
| **Game Class** | API_REFERENCE.md → "Game" | ARCHITECTURE.md → "Game Module" |
| **Turn Structure** | ARCHITECTURE.md → "Turn Manager" | API_REFERENCE.md → "Type System" |
| **Priority System** | ARCHITECTURE.md → "Priority and Stack System" | API_REFERENCE.md → "Type System" |
| **AI Development** | API_REFERENCE.md → "AI Agent Interface" | ARCHITECTURE.md → "AI Agent System" |
| **Card Database** | API_REFERENCE.md → "Card Database" | ARCHITECTURE.md → "Extension Points" |
| **Events** | API_REFERENCE.md → "Events System" | ARCHITECTURE.md → "Event System" |
| **Combat** | ARCHITECTURE.md → "Combat Manager" | API_REFERENCE.md (via Game methods) |
| **Deck Format** | QUICKSTART.md → "Deck Format" | API_REFERENCE.md → "DecklistParser" |
| **Configuration** | INSTALLATION.md → "Configuration" | API_REFERENCE.md → "GameConfig" |
| **Troubleshooting** | INSTALLATION.md → "Troubleshooting" | QUICKSTART.md → "Quick Troubleshooting" |
| **Design Decisions** | ARCHITECTURE.md → "Design Decisions" | N/A |
| **Extension Points** | ARCHITECTURE.md → "Extension Points" | API_REFERENCE.md → "Usage Examples" |

## Visual Documentation Summary

```
┌─────────────────────────────────────────────────────────────┐
│                  MTGO Engine Documentation                  │
│                                                             │
│  Start Here                Quick Reference                  │
│  ┌───────────────┐         ┌──────────────────┐           │
│  │ QUICKSTART.md │────────►│ API_REFERENCE.md │           │
│  │  (5 minutes)  │         │  (coding guide)  │           │
│  └───────┬───────┘         └──────────────────┘           │
│          │                                                  │
│          │ Issues?                                          │
│          ▼                                                  │
│  ┌─────────────────┐       Deep Dive                       │
│  │ INSTALLATION.md │       ┌──────────────────┐           │
│  │ (troubleshoot)  │       │ ARCHITECTURE.md  │           │
│  └─────────────────┘       │ (system design)  │           │
│                            └──────────────────┘           │
│                                                             │
│  Learning Path:                                             │
│  QUICKSTART → ARCHITECTURE → API_REFERENCE                  │
│                                                             │
│  Development Path:                                          │
│  QUICKSTART → API_REFERENCE → ARCHITECTURE                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Additional Resources

### Project Files

- `README.md` - Project overview and purpose
- `CLAUDE.md` - Project instructions for Claude Code assistant
- `MTG_Expert_Context.md` - MTG theory and meta analysis
- `run_replay_game.py` - Main entry point script
- `Engine/v3/` - Engine source code

### Example Decks

- `decks/12.28.25/` - Sample competitive Standard decks
- `decks/tournament/` - Tournament-tested decklists

### Test Suite

- `Engine/v3/tests/` - Comprehensive test suite
- `Engine/v3/tests/run_all_tests.py` - Run all tests

### Viewer

- `Viewer/index.html` - Replay visualization tool
- `Viewer/demo_replay.json` - Sample replay file

## Version Information

- **Documentation Version:** 1.0
- **Engine Version:** 3.0
- **Created:** January 2026
- **Python Requirement:** 3.10+
- **Dependencies:** None (pure Python standard library)

## Getting Help

1. **Quick Issues:** Check [QUICKSTART.md](QUICKSTART.md) → "Quick Troubleshooting"
2. **Setup Issues:** See [INSTALLATION.md](INSTALLATION.md) → "Troubleshooting"
3. **Understanding Design:** Read [ARCHITECTURE.md](ARCHITECTURE.md)
4. **API Questions:** Reference [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
5. **Code Examples:** See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) → "Usage Examples"

## Next Steps

Choose your path:

- **I want to run a game now** → [QUICKSTART.md](QUICKSTART.md)
- **I want to understand the system** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **I want to write code** → [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **I'm having problems** → [INSTALLATION.md](INSTALLATION.md)

Happy coding!
