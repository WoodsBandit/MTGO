# MTG Deckbuilder Project

An expert Magic: The Gathering deck building and theory crafting assistant designed for use with Claude Code.

## Project Structure

```
mtg-deckbuilder-project/
├── CLAUDE.md                    # Claude Code instructions
├── README.md                    # This file
├── MTG_Expert_Context.md        # Theory crafting knowledge base
├── binders/
│   ├── Slade_Standard_Binder.txt   # Slade's card collection
│   └── Woods_Standard_Binder.txt   # Woods' card collection
└── decks/                       # Output folder for generated decklists
```

## Usage

1. Copy this project to a directory accessible by Claude Code
2. Ask Claude to analyze binder contents and build decks
3. Generated decklists will be MTGO-import ready

## Features

- Analyze player card collections (binders)
- Build competitive Standard-legal decks
- Apply foundational MTG theory principles
- Generate MTGO-import ready decklists
- Provide archetype classification, tier assessment, and sideboard guides

## Decklist Output Format

All decklists follow MTGO-import format:
```
[Deck Name]_AI

[Number] [Card Name]
[Number] [Card Name]
...

Sideboard
[Number] [Card Name]
...
```

## Theory Framework

The project applies established MTG theory including:
- Card Advantage (Brian Weissman)
- Mana Curve (Jay Schneider/Sligh)
- Who's the Beatdown (Mike Flores)
- Inevitability (Zvi Mowshowitz)
- Frank Karsten's mana source guidelines

See `MTG_Expert_Context.md` for the complete theory framework.
