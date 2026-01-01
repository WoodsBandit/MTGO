# MTG Simulation Engine v2

Drop in MTGO .txt decklists → get match results.

## FOR FUTURE CLAUDES - Adding Missing Cards

If the engine warns about unknown cards, add them to card_database.py BEFORE running matches:

```python
CARD_DATABASE["Card Name"] = {
    "type": "creature",  # creature/instant/sorcery/enchantment/artifact/planeswalker/land
    "cost": 3,           # CMC
    "power": 3,          # creatures only
    "toughness": 2,      # creatures only
    "keywords": ["trample", "haste"],  # combat keywords
    "abilities": ["damage_3", "draw_1"]  # see ability list below
}
```

**Common abilities to use:**
- `damage_X` - deals X damage to target
- `damage_X_sweep` - deals X to opponent AND all their creatures
- `draw_X` - draw X cards
- `destroy_creature` - destroys target creature
- `exile` - exiles target
- `bounce` - returns to hand
- `bite` - your creature deals its power to target creature
- `fight` - bite but target hits back
- `create_token_P_T` - creates P/T token
- `token_on_spell` or `spell_trigger` - creates 1/1 when casting spells
- `magebane` - deals escalating damage when opponent casts spells (PRIORITY KILL TARGET)
- `landfall` - triggers on land ETB
- `mana_dork` - taps for mana

**After adding cards, re-export the zip if significant additions were made.**

## Quick Start

```python
from mtg_engine import run_match

deck1 = """
4 Magebane Lizard
4 Pugnacious Hammerskull  
20 Forest
4 Mountain
"""

deck2 = """
4 Gran-Gran
4 Combustion Technique
22 Island
"""

run_match(deck1, deck2, "Gruul", "Izzet", matches=5)
```

From files:
```python
from mtg_engine import run_match_from_files
run_match_from_files("deck1.txt", "deck2.txt", matches=5)
```

## Files

- **mtg_engine.py** - Core simulation engine
- **card_database.py** - 3164 Standard cards from Scryfall

## Unknown Cards

If a card isn't in database:
```
⚠️  Unknown cards: ['New Card']
```

Add to card_database.py:
```python
CARD_DATABASE["New Card"] = {
    "type": "creature", "cost": 3, "power": 3, "toughness": 2,
    "keywords": ["trample"], "abilities": ["draw_1"]
}
```

## Supported Abilities

| Ability | Effect |
|---------|--------|
| `damage_X` | Deal X damage |
| `draw_X` | Draw X cards |
| `destroy_creature` | Destroy creature |
| `exile` | Exile target |
| `bounce` | Return to hand |
| `bite` / `fight` | Creature removal |
| `create_token_P_T` | Make token |
| `magebane` | Damage on opponent spells |

## Keywords

trample, haste, flying, reach, deathtouch, first_strike, lifelink, menace, vigilance, flash, hexproof, ward

## Verbose Mode

```python
run_match(deck1, deck2, verbose=True)
```

## Engine Updates

If new cards/abilities are added during a session, provide user an updated zip at the end.
