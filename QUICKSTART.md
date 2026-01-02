# MTGO Engine - Quick Start Guide

Get started with the MTGO Magic: The Gathering game engine in under 5 minutes.

## Prerequisites

- **Python 3.10+** (tested with Python 3.14.0)
- **No external dependencies** - Pure Python implementation!
- A terminal/command prompt
- Two MTG deck files in MTGO format

## Installation

### 1. Clone or Download the Project

```bash
cd "C:/Users/YourName/Documents"
# Project should be in a directory accessible by your user
```

### 2. Verify Python Installation

```bash
python --version
# Should output: Python 3.10 or higher
```

That's it! The engine has zero external dependencies.

## Running Your First Match

### Option 1: Quick Test (Uses Included Decks)

```bash
cd "C:/Users/Xx LilMan xX/Documents/Claude Docs/MTGO"
python run_replay_game.py
```

This will:
- Automatically find test decks in `decks/12.28.25/` or create simple test decks
- Run a complete game between two AI opponents
- Save a replay JSON to `Viewer/demo_replay.json`
- Display turn-by-turn gameplay in the console

### Option 2: Specify Your Own Decks

```bash
python run_replay_game.py "decks/12.28.25/Mono_Red_Aggro_Meta_AI.txt" "decks/12.28.25/Dimir_Midrange_Meta_AI.txt"
```

### Option 3: Run the V3 Engine Directly

```bash
cd Engine/v3
python run_match.py
```

## Expected Output

You should see output like this:

```
Loading decks...
  Deck 1: decks/12.28.25/Mono_Red_Aggro_Meta_AI.txt
  Deck 2: decks/12.28.25/Dimir_Midrange_Meta_AI.txt
  Mono_Red_Aggro_Meta: 60 cards
  Dimir_Midrange_Meta: 60 cards

Setting up game...

Playing game...
----------------------------------------
Turn 1 (Player 1)
  Beginning Phase
    Untap Step
    Upkeep Step
    Draw Step: Player 1 draws a card
  Main Phase 1
    Player 1 plays Mountain
  Combat Phase
    No attackers declared
  Main Phase 2
  Ending Phase
    End Step
    Cleanup Step

Turn 2 (Player 2)
  Beginning Phase
  ...
----------------------------------------

Game Over!
Winner: Player 1 (Mono_Red_Aggro_Meta)
Reason: opponent_life_zero
Final Life: P1=14, P2=0
Turns played: 8
Frames recorded: 47

Saving replay to: Viewer/demo_replay.json
Done!

To view the replay:
  1. Open Viewer/index.html in a browser
  2. Drop Viewer/demo_replay.json onto the page
  Or click 'Load Demo' to use the default replay
```

## Deck Format

Decks must be in MTGO import format:

```
Deck_Name_AI

4 Lightning Bolt
20 Mountain
4 Monastery Swiftspear
...

Sideboard
3 Abrade
2 Burning Hands
...
```

## What Happens During a Game?

1. **Game Setup**: Each player shuffles their 60-card deck and draws 7 cards
2. **Turn Structure**: Players alternate turns following MTG rules (Beginning, Main 1, Combat, Main 2, Ending)
3. **AI Decision Making**: SimpleAI agents make decisions about playing lands, casting spells, attacking, and blocking
4. **State-Based Actions**: Engine automatically checks for player death, creature damage, etc.
5. **Game End**: Game ends when a player reaches 0 life, runs out of cards, or turn limit is reached (default: 50 turns)

## Viewing Game Replays

The engine generates JSON replay files that can be visualized:

1. Navigate to `Viewer/index.html` in your web browser
2. Drag and drop the generated `demo_replay.json` file onto the page
3. Use the replay controls to step through the game turn-by-turn

## Running Multiple Games (Tournament Mode)

```bash
cd Engine/v3
python run_tournament.py
```

This will run multiple matches between all deck pairings and generate statistics.

## Quick Troubleshooting

### "Python not found"
- Install Python 3.10+ from python.org
- Ensure Python is added to your system PATH

### "No module named 'v3'"
- Make sure you're running from the correct directory
- The script adds `Engine/` to the path automatically

### "File not found" for decks
- Check that deck files exist in `decks/12.28.25/`
- Verify file paths use forward slashes or proper Windows backslashes
- Run without arguments to use auto-detected test decks

### Game ends immediately
- Check deck format (must have 60 cards minimum for constructed)
- Verify cards in decklist exist in the card database
- Check console output for parsing errors

## Next Steps

- **Learn the Architecture**: Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the engine design
- **Explore the API**: Check [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for detailed class documentation
- **Build Custom Decks**: Create your own decks using the MTGO format
- **Implement Custom AI**: Extend the `AIAgent` class to create smarter decision-making agents
- **Run Tournaments**: Use `run_tournament.py` to test multiple deck matchups

## Key Files Reference

| File | Purpose |
|------|---------|
| `run_replay_game.py` | Main entry point - runs a game and generates replay |
| `Engine/v3/run_match.py` | Run best-of-3 matches |
| `Engine/v3/run_tournament.py` | Tournament runner for multiple matches |
| `Engine/v3/engine/game.py` | Core game engine |
| `Engine/v3/ai/agent.py` | AI agent interface |
| `decks/12.28.25/` | Sample deck files |

## Resources

- Full installation details: [INSTALLATION.md](INSTALLATION.md)
- System architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- API documentation: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- MTG Comprehensive Rules: https://magic.wizards.com/en/rules

Happy playtesting!
