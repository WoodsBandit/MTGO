# MTGO Engine - Installation Guide

Complete installation and setup instructions for the MTGO Magic: The Gathering game engine.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Python Installation](#python-installation)
3. [Project Setup](#project-setup)
4. [Verification](#verification)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Setup](#advanced-setup)

## System Requirements

### Minimum Requirements

- **Operating System**: Windows 10/11, macOS 10.14+, or Linux (any modern distribution)
- **Python Version**: 3.10 or higher (tested with Python 3.14.0)
- **RAM**: 512 MB (for basic single-game execution)
- **Disk Space**: 50 MB for the engine + card database
- **Dependencies**: **NONE** - Pure Python standard library implementation

### Recommended Requirements

- **Python Version**: 3.11+ (improved performance with structural pattern matching)
- **RAM**: 2 GB (for tournament mode with parallel processing)
- **Disk Space**: 500 MB (includes space for game replays and logs)

### Supported Platforms

The engine has been tested on:
- Windows 10/11 (Python 3.10-3.14)
- macOS 12+ (Python 3.10-3.13)
- Ubuntu 20.04+ (Python 3.10+)

## Python Installation

### Checking Existing Python Installation

Open a terminal/command prompt and run:

```bash
python --version
```

Or on some systems:

```bash
python3 --version
```

You should see output like `Python 3.10.0` or higher. If you see `Python 2.x` or an error, proceed with installation.

### Installing Python

#### Windows

1. Download Python from [python.org/downloads](https://www.python.org/downloads/)
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Choose "Install Now" or customize for advanced options
5. Verify installation:
   ```cmd
   python --version
   ```

#### macOS

**Option 1: Official Installer**
1. Download Python from [python.org/downloads](https://www.python.org/downloads/)
2. Run the `.pkg` installer
3. Verify installation:
   ```bash
   python3 --version
   ```

**Option 2: Homebrew** (recommended)
```bash
brew install python@3.11
python3 --version
```

#### Linux

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
python3.11 --version
```

**Fedora/RHEL:**
```bash
sudo dnf install python3.11
python3.11 --version
```

**Arch Linux:**
```bash
sudo pacman -S python
python --version
```

## Project Setup

### Step 1: Obtain the Project

**Option A: Clone with Git**
```bash
cd ~/Documents
git clone <repository-url> MTGO
cd MTGO
```

**Option B: Download and Extract**
1. Download the project ZIP file
2. Extract to a directory of your choice (e.g., `C:/Users/YourName/Documents/MTGO`)
3. Navigate to the directory:
   ```bash
   cd "C:/Users/YourName/Documents/MTGO"
   ```

### Step 2: Verify Project Structure

Your project directory should contain:

```
MTGO/
├── Engine/
│   ├── V1_mtg_sim_package/      # Legacy V1 engine
│   └── v3/                       # Current V3 engine
│       ├── ai/                   # AI agent system
│       ├── cards/                # Card database
│       ├── engine/               # Core game engine
│       │   ├── effects/          # Effects system
│       │   └── keywords/         # Keyword abilities
│       ├── tests/                # Test suite
│       ├── run_match.py          # Match runner
│       └── run_tournament.py     # Tournament runner
├── decks/                        # Deck storage
│   └── 12.28.25/                 # Sample decks
├── Viewer/                       # Replay visualization
├── run_replay_game.py            # Main game runner
├── QUICKSTART.md
├── INSTALLATION.md
└── README.md
```

### Step 3: No Dependencies Required!

Unlike most Python projects, the MTGO engine has **zero external dependencies**. Everything is implemented using Python's standard library:

- No `pip install` required
- No `requirements.txt` to manage
- No virtual environment necessary (though you can use one if preferred)

This design decision ensures:
- Minimal setup friction
- No version conflicts
- Easy deployment
- Fast installation

## Verification

### Basic Verification

Verify the engine can import properly:

```bash
cd "C:/Users/Xx LilMan xX/Documents/Claude Docs/MTGO"
python -c "import sys; sys.path.insert(0, 'Engine'); from v3.engine.game import Game; print('Engine loaded successfully!')"
```

Expected output:
```
Engine loaded successfully!
```

### Running First Test

Execute the quick test to verify everything works:

```bash
python run_replay_game.py
```

If this runs without errors and produces output ending with "Done!", your installation is successful.

### Verification Checklist

- [ ] Python 3.10+ installed and in PATH
- [ ] Project files extracted/cloned
- [ ] Directory structure matches expected layout
- [ ] `python -c "import sys; ..."` command succeeds
- [ ] `run_replay_game.py` executes without import errors
- [ ] Game completes and generates `Viewer/demo_replay.json`

## Configuration

### Game Configuration

The engine uses a `GameConfig` dataclass for configuration. You can customize:

```python
from v3.engine.game import Game, GameConfig

config = GameConfig(
    starting_life=20,        # Default: 20 (Standard), use 40 for Commander
    starting_hand_size=7,    # Default: 7
    max_turns=50,            # Default: 50 (prevents infinite games)
    verbose=True             # Default: False (set True for detailed logging)
)

game = Game(player_ids=[1, 2], config=config)
```

### Default Settings

The engine ships with sensible defaults:

| Setting | Default Value | Purpose |
|---------|---------------|---------|
| `starting_life` | 20 | Standard constructed life total |
| `starting_hand_size` | 7 | MTG standard opening hand |
| `max_turns` | 50 | Prevents infinite loops in testing |
| `verbose` | False | Reduces console spam in tournaments |

### Customizing Deck Locations

Deck paths are relative to the project root:

```python
# In run_replay_game.py
deck1_path = "decks/12.28.25/Mono_Red_Aggro_Meta_AI.txt"
deck2_path = "decks/custom/My_Deck_AI.txt"
```

Or use absolute paths:

```python
deck1_path = "C:/Users/YourName/MTGO/decks/my_deck.txt"
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'v3'`

**Solution**:
- Ensure you're running from the correct directory
- The `run_replay_game.py` script automatically adds `Engine/` to path
- If running your own scripts, add:
  ```python
  import sys
  import os
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Engine'))
  ```

### Python Version Issues

**Problem**: `SyntaxError` or features not working

**Solution**:
- Verify Python version: `python --version`
- The engine uses modern Python features (dataclasses, type hints, structural pattern matching)
- Upgrade to Python 3.10+ if using an older version

### Path Issues on Windows

**Problem**: `FileNotFoundError` when loading decks

**Solutions**:
- Use forward slashes: `decks/12.28.25/deck.txt`
- Or use raw strings: `r"decks\12.28.25\deck.txt"`
- Or escape backslashes: `"decks\\12.28.25\\deck.txt"`

### Card Database Loading Issues

**Problem**: Cards not found or parsing errors

**Solution**:
- Verify card names match database exactly (case-sensitive)
- Check deck format (MTGO import format required)
- Ensure deck file is UTF-8 encoded
- Example valid deck entry:
  ```
  4 Lightning Bolt
  20 Mountain
  ```

### Memory Issues (Large Tournaments)

**Problem**: Memory errors during large tournament runs

**Solutions**:
- Reduce parallel processing workers in `run_tournament.py`
- Run matches sequentially instead of parallel
- Increase system swap/page file size
- Run tournament in batches

### Permission Errors

**Problem**: Cannot write to output directories

**Solutions**:
- Ensure write permissions on project directory
- On Linux/macOS: `chmod -R u+w ./MTGO`
- On Windows: Right-click folder > Properties > Security > Edit permissions
- Create output directories manually:
  ```bash
  mkdir -p Viewer
  mkdir -p decks/custom
  ```

## Advanced Setup

### Virtual Environment (Optional)

While not required, you can use a virtual environment for isolation:

```bash
# Create virtual environment
python -m venv mtgo_env

# Activate (Windows)
mtgo_env\Scripts\activate

# Activate (macOS/Linux)
source mtgo_env/bin/activate

# Run engine
python run_replay_game.py

# Deactivate when done
deactivate
```

### Development Setup

For development work:

1. **Enable verbose logging**:
   ```python
   config = GameConfig(verbose=True)
   ```

2. **Run test suite**:
   ```bash
   cd Engine/v3/tests
   python run_all_tests.py
   ```

3. **Create custom AI agents**:
   - See `Engine/v3/ai/agent.py` for `AIAgent` base class
   - Extend `SimpleAI` or implement from scratch

### Performance Optimization

For faster execution:

1. **Use PyPy** (alternative Python interpreter):
   ```bash
   pypy3 run_replay_game.py
   ```
   Can be 2-5x faster for computation-heavy games.

2. **Disable verbose output**:
   ```python
   config = GameConfig(verbose=False)
   ```

3. **Reduce replay frame recording**:
   Modify `run_replay_game.py` to record fewer frames

### Running on Headless Servers

For running tournaments on servers without GUI:

```bash
# Run tournament in background
nohup python Engine/v3/run_tournament.py > tournament.log 2>&1 &

# Check progress
tail -f tournament.log

# Kill if needed
pkill -f run_tournament.py
```

## Next Steps

After successful installation:

1. **Quick Start**: Follow [QUICKSTART.md](QUICKSTART.md) to run your first game
2. **Learn Architecture**: Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the design
3. **API Documentation**: Explore [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for detailed API docs
4. **Build Decks**: Create custom decks in `decks/custom/`
5. **Extend AI**: Implement custom AI agents by subclassing `AIAgent`

## Getting Help

If you encounter issues not covered here:

1. Check the [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) guide
2. Review console error messages carefully
3. Verify all verification steps passed
4. Check Python version compatibility
5. Ensure project structure is intact

## Version Compatibility Matrix

| Python Version | Engine V3 | Notes |
|----------------|-----------|-------|
| 3.10.x | ✅ Full | Minimum required version |
| 3.11.x | ✅ Full | Recommended for performance |
| 3.12.x | ✅ Full | Full support |
| 3.13.x | ✅ Full | Full support |
| 3.14.x | ✅ Full | Tested and working |
| 3.9.x | ❌ Not supported | Missing required features |
| 3.8.x and below | ❌ Not supported | Too old |

Success! You should now have a working MTGO engine installation. Proceed to the [QUICKSTART.md](QUICKSTART.md) guide to run your first game.
