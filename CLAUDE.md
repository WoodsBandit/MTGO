# MTG Deckbuilder Project - Claude Code Instructions

## Project Overview
This is an expert Magic: The Gathering deck building and theory crafting assistant. The project helps analyze card collections (binders) and build competitive Standard decks using established MTG theory principles.

## Core Capabilities
- Analyze player binder contents to identify viable deck strategies
- Build optimized Standard-legal decks from available card pools
- Apply foundational MTG theory (card advantage, tempo, mana curve, etc.)
- Provide MTGO-import ready decklists

## Key Files

### `MTG_Expert_Context.md`
Contains the comprehensive theory crafting knowledge base including:
- Foundational MTG theory (Card Advantage, Tempo, Mana Curve, Who's the Beatdown, Inevitability)
- Deck archetypes (Aggro, Control, Combo, Midrange, Tempo, Ramp)
- Deck construction principles (Rule of 9, threat density, mana base construction)
- Sideboard construction guidelines
- Standard-specific meta notes (December 2025)
- Famous deck lessons from MTG history

### `Slade_Standard_Binder.txt`
Player "Slade's" card collection inventory. Contains card names and quantities available for deck building.

### `Woods_Standard_Binder.txt`
Player "Woods'" card collection inventory. Contains card names and quantities available for deck building.

## Output Format Requirements
All decklists must be provided in MTGO-import ready format:
```
[Deck Name]_AI

[Number] [Card Name]
[Number] [Card Name]
...

Sideboard
[Number] [Card Name]
...
```

Each deck should include:
- Archetype classification
- Tier assessment
- Key synergies explained
- Matchup notes
- Sideboard guide when relevant

## Workflow Guidelines

### When Analyzing a Binder
1. Identify playsets (4-ofs) as build-around candidates
2. Find synergy clusters (cards that work together)
3. Evaluate mana base (dual lands, fixing available)
4. Check for staple removal/interaction
5. Assess sideboard options

### When Building Decks
1. Identify the strategy and win condition
2. Select core cards (16-20 cards, 4-ofs)
3. Add supporting cast (12-16 cards)
4. Include appropriate interaction (8-12 cards)
5. Build mana base (20-27 lands based on archetype)
6. Refine and test against expected metagame

## Standard Format Notes (December 2025)
- Diverse metagame with no dominant deck (>15% share)
- Avatar: The Last Airbender cards impacting format
- Lands-matter strategies viable (Ouroboroid, landfall)
- Graveyard strategies present (Aftermath Analyst, reanimator)
- Aggro strong in Bo1, midrange/control better in Bo3

## Important Principles
- "Misassignment of role = game loss" - Always identify who's the beatdown
- Prioritize consistency (4-ofs over powerful 1-ofs)
- Apply Frank Karsten's mana source guidelines for color consistency
- Consider the Rock-Paper-Scissors triangle when positioning decks
- "The essence of strategy is choosing what not to do"
