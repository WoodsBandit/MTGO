/**
 * MTGO Replay Viewer - Main Entry Point
 *
 * This module initializes all components and wires them together for
 * the MTG Online replay viewer application.
 *
 * Flow:
 * 1. Page loads
 * 2. User drops replay JSON file (or loads demo)
 * 3. GameState parses replay
 * 4. Controls initialized with frame count
 * 5. User presses play
 * 6. Each frame: Controls advances -> GameState provides state -> Playmat renders
 */

// ============================================================================
// Sample Replay Data (for demo/testing when no file is loaded)
// ============================================================================

const SAMPLE_REPLAY = {
    metadata: {
        format: "Standard",
        date: "2025-01-01",
        player1: { name: "Player1", deck: "Gruul Dinosaurs" },
        player2: { name: "Player2", deck: "Mono Red Aggro" }
    },
    initialState: {
        player1: { life: 20, hand: [], library: 60, graveyard: [], exile: [], battlefield: [] },
        player2: { life: 20, hand: [], library: 60, graveyard: [], exile: [], battlefield: [] }
    },
    frames: [
        {
            frameNumber: 0,
            turn: 1,
            phase: "Beginning",
            activePlayer: 1,
            action: { type: "game_start", description: "Game begins. Player1 wins the die roll." },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 1, name: "Mountain", type: "Land" },
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 6, name: "Raging Goblin", type: "Creature", manaCost: "{R}", power: 1, toughness: 1 },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 20,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 1,
            turn: 1,
            phase: "Main 1",
            activePlayer: 1,
            action: { type: "play_land", player: 1, card: "Mountain", description: "P1 plays Mountain" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 6, name: "Raging Goblin", type: "Creature", manaCost: "{R}", power: 1, toughness: 1 },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: false }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 20,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 2,
            turn: 1,
            phase: "Main 1",
            activePlayer: 1,
            action: { type: "tap_land", player: 1, card: "Mountain", description: "P1 taps Mountain for {R}" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 6, name: "Raging Goblin", type: "Creature", manaCost: "{R}", power: 1, toughness: 1 },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: true }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 1, G: 0, C: 0 }
                },
                player2: {
                    life: 20,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 3,
            turn: 1,
            phase: "Main 1",
            activePlayer: 1,
            action: { type: "cast_spell", player: 1, card: "Raging Goblin", description: "P1 casts Raging Goblin" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: true }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 20,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: [
                    { id: 6, name: "Raging Goblin", type: "Creature", manaCost: "{R}", controller: 1 }
                ]
            }
        },
        {
            frameNumber: 4,
            turn: 1,
            phase: "Main 1",
            activePlayer: 1,
            action: { type: "resolve", card: "Raging Goblin", description: "Raging Goblin resolves and enters the battlefield" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: true },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: false, summoningSick: true, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 20,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 5,
            turn: 1,
            phase: "Combat - Declare Attackers",
            activePlayer: 1,
            action: { type: "declare_attackers", player: 1, attackers: ["Raging Goblin"], description: "P1 attacks with Raging Goblin" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: true },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: true, attacking: true, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 20,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 6,
            turn: 1,
            phase: "Combat - Damage",
            activePlayer: 1,
            action: { type: "combat_damage", damage: 1, target: "Player2", description: "Raging Goblin deals 1 damage to P2" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: true },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: true, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 19,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 7,
            turn: 1,
            phase: "End",
            activePlayer: 1,
            action: { type: "pass_turn", player: 1, description: "P1 passes turn" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: true },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: true, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 19,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 8,
            turn: 2,
            phase: "Beginning - Untap",
            activePlayer: 2,
            action: { type: "untap", player: 2, description: "P2's turn begins - Untap step" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: false },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: false, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 19,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 9,
            turn: 2,
            phase: "Beginning - Draw",
            activePlayer: 2,
            action: { type: "draw", player: 2, description: "P2 draws a card" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: false },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: false, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 19,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" },
                        { id: 108, name: "Card", type: "Unknown" }
                    ],
                    library: 52,
                    graveyard: [],
                    exile: [],
                    battlefield: [],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 10,
            turn: 2,
            phase: "Main 1",
            activePlayer: 2,
            action: { type: "play_land", player: 2, card: "Mountain", description: "P2 plays Mountain" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: false },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: false, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 19,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" },
                        { id: 107, name: "Card", type: "Unknown" }
                    ],
                    library: 52,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 201, name: "Mountain", type: "Land", tapped: false }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        },
        {
            frameNumber: 11,
            turn: 2,
            phase: "Main 1",
            activePlayer: 2,
            action: { type: "cast_spell", player: 2, card: "Shock", target: "Raging Goblin", description: "P2 casts Shock targeting Raging Goblin" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: false },
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1, tapped: false, keywords: ["Haste"] }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 19,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" }
                    ],
                    library: 52,
                    graveyard: [],
                    exile: [],
                    battlefield: [
                        { id: 201, name: "Mountain", type: "Land", tapped: true }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: [
                    { id: 202, name: "Shock", type: "Instant", manaCost: "{R}", controller: 2, target: { id: 6, name: "Raging Goblin" } }
                ]
            }
        },
        {
            frameNumber: 12,
            turn: 2,
            phase: "Main 1",
            activePlayer: 2,
            action: { type: "resolve", card: "Shock", description: "Shock resolves, dealing 2 damage to Raging Goblin" },
            state: {
                player1: {
                    life: 20,
                    hand: [
                        { id: 2, name: "Forest", type: "Land" },
                        { id: 3, name: "Lightning Bolt", type: "Instant", manaCost: "{R}" },
                        { id: 4, name: "Llanowar Elves", type: "Creature", manaCost: "{G}", power: 1, toughness: 1 },
                        { id: 5, name: "Stomping Ground", type: "Land" },
                        { id: 7, name: "Giant Growth", type: "Instant", manaCost: "{G}" }
                    ],
                    library: 53,
                    graveyard: [
                        { id: 6, name: "Raging Goblin", type: "Creature", power: 1, toughness: 1 }
                    ],
                    exile: [],
                    battlefield: [
                        { id: 1, name: "Mountain", type: "Land", tapped: false }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                player2: {
                    life: 19,
                    hand: [
                        { id: 101, name: "Card", type: "Unknown" },
                        { id: 102, name: "Card", type: "Unknown" },
                        { id: 103, name: "Card", type: "Unknown" },
                        { id: 104, name: "Card", type: "Unknown" },
                        { id: 105, name: "Card", type: "Unknown" },
                        { id: 106, name: "Card", type: "Unknown" }
                    ],
                    library: 52,
                    graveyard: [
                        { id: 202, name: "Shock", type: "Instant" }
                    ],
                    exile: [],
                    battlefield: [
                        { id: 201, name: "Mountain", type: "Land", tapped: true }
                    ],
                    manaPool: { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 }
                },
                stack: []
            }
        }
    ]
};

// ============================================================================
// Logger Utility
// ============================================================================

const Logger = {
    enabled: true,
    prefix: '[MTGO Viewer]',

    log(...args) {
        if (this.enabled) {
            console.log(this.prefix, ...args);
        }
    },

    info(...args) {
        if (this.enabled) {
            console.info(this.prefix, '[INFO]', ...args);
        }
    },

    warn(...args) {
        if (this.enabled) {
            console.warn(this.prefix, '[WARN]', ...args);
        }
    },

    error(...args) {
        if (this.enabled) {
            console.error(this.prefix, '[ERROR]', ...args);
        }
    },

    debug(...args) {
        if (this.enabled) {
            console.debug(this.prefix, '[DEBUG]', ...args);
        }
    },

    group(label) {
        if (this.enabled) {
            console.group(this.prefix + ' ' + label);
        }
    },

    groupEnd() {
        if (this.enabled) {
            console.groupEnd();
        }
    }
};

// ============================================================================
// GameState Module (Stub - to be replaced with actual module)
// ============================================================================

class GameState {
    constructor() {
        this.replay = null;
        this.currentFrame = 0;
        this.frameCount = 0;
        Logger.debug('GameState initialized');
    }

    /**
     * Load and parse a replay JSON object
     * @param {Object} replayData - The replay data object
     */
    loadReplay(replayData) {
        Logger.group('Loading Replay');

        if (!replayData || !replayData.frames || !Array.isArray(replayData.frames)) {
            throw new Error('Invalid replay format: missing frames array');
        }

        this.replay = replayData;
        this.frameCount = replayData.frames.length;
        this.currentFrame = 0;

        Logger.info('Replay loaded successfully');
        Logger.info(`Metadata:`, replayData.metadata || 'No metadata');
        Logger.info(`Total frames: ${this.frameCount}`);
        Logger.groupEnd();

        return this;
    }

    /**
     * Get the state at a specific frame
     * @param {number} frameIndex - The frame index to retrieve
     * @returns {Object} The game state at that frame
     */
    getStateAtFrame(frameIndex) {
        if (!this.replay) {
            Logger.warn('No replay loaded, returning null state');
            return null;
        }

        if (frameIndex < 0 || frameIndex >= this.frameCount) {
            Logger.warn(`Frame ${frameIndex} out of bounds (0-${this.frameCount - 1})`);
            return null;
        }

        this.currentFrame = frameIndex;
        return this.replay.frames[frameIndex];
    }

    /**
     * Get the action description for a frame
     * @param {number} frameIndex - The frame index
     * @returns {string} The action description
     */
    getActionDescription(frameIndex) {
        const frame = this.getStateAtFrame(frameIndex);
        if (!frame || !frame.action) {
            return '';
        }
        return frame.action.description || '';
    }

    /**
     * Get turn and phase info for a frame
     * @param {number} frameIndex - The frame index
     * @returns {Object} Turn and phase information
     */
    getTurnInfo(frameIndex) {
        const frame = this.getStateAtFrame(frameIndex);
        if (!frame) {
            return { turn: 0, phase: 'Unknown', activePlayer: 0 };
        }
        return {
            turn: frame.turn || 0,
            phase: frame.phase || 'Unknown',
            activePlayer: frame.activePlayer || 0
        };
    }

    /**
     * Get metadata about the replay
     * @returns {Object} Replay metadata
     */
    getMetadata() {
        return this.replay?.metadata || null;
    }

    /**
     * Get total frame count
     * @returns {number} Number of frames
     */
    getFrameCount() {
        return this.frameCount;
    }

    /**
     * Check if a replay is loaded
     * @returns {boolean} True if replay is loaded
     */
    isLoaded() {
        return this.replay !== null;
    }
}

// ============================================================================
// Controls Module (Stub - to be replaced with actual module)
// ============================================================================

class Controls {
    constructor(container) {
        this.container = container;
        this.currentFrame = 0;
        this.totalFrames = 0;
        this.isPlaying = false;
        this.playbackSpeed = 1000; // ms per frame
        this.playInterval = null;
        this.onFrameChange = null;

        this.elements = {};
        this.createUI();
        Logger.debug('Controls initialized');
    }

    createUI() {
        // Create control elements if container exists
        if (!this.container) {
            Logger.warn('No container provided for controls');
            return;
        }

        this.container.innerHTML = `
            <div class="controls-wrapper">
                <div class="playback-controls">
                    <button id="btn-first" title="First Frame">|&lt;</button>
                    <button id="btn-prev" title="Previous Frame">&lt;</button>
                    <button id="btn-play" title="Play/Pause">Play</button>
                    <button id="btn-next" title="Next Frame">&gt;</button>
                    <button id="btn-last" title="Last Frame">&gt;|</button>
                </div>
                <div class="frame-info">
                    <span id="frame-display">Frame: 0 / 0</span>
                    <input type="range" id="frame-slider" min="0" max="0" value="0">
                </div>
                <div class="speed-control">
                    <label for="speed-select">Speed:</label>
                    <select id="speed-select">
                        <option value="2000">0.5x</option>
                        <option value="1000" selected>1x</option>
                        <option value="500">2x</option>
                        <option value="250">4x</option>
                    </select>
                </div>
            </div>
        `;

        // Cache element references
        this.elements = {
            btnFirst: this.container.querySelector('#btn-first'),
            btnPrev: this.container.querySelector('#btn-prev'),
            btnPlay: this.container.querySelector('#btn-play'),
            btnNext: this.container.querySelector('#btn-next'),
            btnLast: this.container.querySelector('#btn-last'),
            frameDisplay: this.container.querySelector('#frame-display'),
            frameSlider: this.container.querySelector('#frame-slider'),
            speedSelect: this.container.querySelector('#speed-select')
        };

        this.bindEvents();
    }

    bindEvents() {
        const { btnFirst, btnPrev, btnPlay, btnNext, btnLast, frameSlider, speedSelect } = this.elements;

        if (btnFirst) btnFirst.addEventListener('click', () => this.goToFrame(0));
        if (btnPrev) btnPrev.addEventListener('click', () => this.previousFrame());
        if (btnPlay) btnPlay.addEventListener('click', () => this.togglePlay());
        if (btnNext) btnNext.addEventListener('click', () => this.nextFrame());
        if (btnLast) btnLast.addEventListener('click', () => this.goToFrame(this.totalFrames - 1));

        if (frameSlider) {
            frameSlider.addEventListener('input', (e) => {
                this.goToFrame(parseInt(e.target.value, 10));
            });
        }

        if (speedSelect) {
            speedSelect.addEventListener('change', (e) => {
                this.playbackSpeed = parseInt(e.target.value, 10);
                if (this.isPlaying) {
                    this.pause();
                    this.play();
                }
                Logger.info(`Playback speed changed to ${this.playbackSpeed}ms per frame`);
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    this.togglePlay();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    this.previousFrame();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    this.nextFrame();
                    break;
                case 'Home':
                    e.preventDefault();
                    this.goToFrame(0);
                    break;
                case 'End':
                    e.preventDefault();
                    this.goToFrame(this.totalFrames - 1);
                    break;
            }
        });
    }

    /**
     * Initialize controls with frame count
     * @param {number} frameCount - Total number of frames
     */
    init(frameCount) {
        this.totalFrames = frameCount;
        this.currentFrame = 0;

        if (this.elements.frameSlider) {
            this.elements.frameSlider.max = Math.max(0, frameCount - 1);
            this.elements.frameSlider.value = 0;
        }

        this.updateDisplay();
        Logger.info(`Controls initialized with ${frameCount} frames`);
    }

    /**
     * Go to a specific frame
     * @param {number} frame - Target frame index
     */
    goToFrame(frame) {
        if (frame < 0) frame = 0;
        if (frame >= this.totalFrames) frame = this.totalFrames - 1;

        this.currentFrame = frame;
        this.updateDisplay();

        if (this.onFrameChange) {
            this.onFrameChange(frame);
        }
    }

    nextFrame() {
        if (this.currentFrame < this.totalFrames - 1) {
            this.goToFrame(this.currentFrame + 1);
        } else if (this.isPlaying) {
            this.pause();
        }
    }

    previousFrame() {
        if (this.currentFrame > 0) {
            this.goToFrame(this.currentFrame - 1);
        }
    }

    play() {
        if (this.isPlaying) return;
        if (this.currentFrame >= this.totalFrames - 1) {
            this.goToFrame(0);
        }

        this.isPlaying = true;
        if (this.elements.btnPlay) {
            this.elements.btnPlay.textContent = 'Pause';
        }

        this.playInterval = setInterval(() => {
            this.nextFrame();
        }, this.playbackSpeed);

        Logger.info('Playback started');
    }

    pause() {
        if (!this.isPlaying) return;

        this.isPlaying = false;
        if (this.elements.btnPlay) {
            this.elements.btnPlay.textContent = 'Play';
        }

        if (this.playInterval) {
            clearInterval(this.playInterval);
            this.playInterval = null;
        }

        Logger.info('Playback paused');
    }

    togglePlay() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }

    updateDisplay() {
        if (this.elements.frameDisplay) {
            this.elements.frameDisplay.textContent = `Frame: ${this.currentFrame + 1} / ${this.totalFrames}`;
        }
        if (this.elements.frameSlider) {
            this.elements.frameSlider.value = this.currentFrame;
        }
    }

    /**
     * Get current frame index
     * @returns {number} Current frame
     */
    getCurrentFrame() {
        return this.currentFrame;
    }

    /**
     * Set callback for frame changes
     * @param {Function} callback - Function to call on frame change
     */
    setOnFrameChange(callback) {
        this.onFrameChange = callback;
    }
}

// ============================================================================
// Playmat Module (Stub - to be replaced with actual module)
// ============================================================================

class Playmat {
    constructor(container) {
        this.container = container;
        this.elements = {};
        this.createUI();
        Logger.debug('Playmat initialized');
    }

    createUI() {
        if (!this.container) {
            Logger.warn('No container provided for playmat');
            return;
        }

        this.container.innerHTML = `
            <div class="playmat-wrapper">
                <div class="player-area opponent-area" id="player2-area">
                    <div class="player-info">
                        <span class="player-name" id="p2-name">Player 2</span>
                        <span class="player-life" id="p2-life">20</span>
                    </div>
                    <div class="zone-row">
                        <div class="zone hand-zone" id="p2-hand">
                            <div class="zone-label">Hand</div>
                            <div class="zone-contents"></div>
                        </div>
                    </div>
                    <div class="zone-row">
                        <div class="zone battlefield-zone" id="p2-battlefield">
                            <div class="zone-label">Battlefield</div>
                            <div class="zone-contents"></div>
                        </div>
                    </div>
                    <div class="zone-row secondary-zones">
                        <div class="zone library-zone" id="p2-library">
                            <div class="zone-label">Library</div>
                            <div class="zone-count">0</div>
                        </div>
                        <div class="zone graveyard-zone" id="p2-graveyard">
                            <div class="zone-label">Graveyard</div>
                            <div class="zone-contents"></div>
                        </div>
                        <div class="zone exile-zone" id="p2-exile">
                            <div class="zone-label">Exile</div>
                            <div class="zone-contents"></div>
                        </div>
                    </div>
                </div>

                <div class="center-area">
                    <div class="stack-zone" id="stack">
                        <div class="zone-label">Stack</div>
                        <div class="zone-contents"></div>
                    </div>
                    <div class="turn-info" id="turn-info">
                        <div class="turn-number">Turn 0</div>
                        <div class="phase-name">---</div>
                        <div class="active-player">Active: ---</div>
                    </div>
                </div>

                <div class="player-area your-area" id="player1-area">
                    <div class="zone-row secondary-zones">
                        <div class="zone library-zone" id="p1-library">
                            <div class="zone-label">Library</div>
                            <div class="zone-count">0</div>
                        </div>
                        <div class="zone graveyard-zone" id="p1-graveyard">
                            <div class="zone-label">Graveyard</div>
                            <div class="zone-contents"></div>
                        </div>
                        <div class="zone exile-zone" id="p1-exile">
                            <div class="zone-label">Exile</div>
                            <div class="zone-contents"></div>
                        </div>
                    </div>
                    <div class="zone-row">
                        <div class="zone battlefield-zone" id="p1-battlefield">
                            <div class="zone-label">Battlefield</div>
                            <div class="zone-contents"></div>
                        </div>
                    </div>
                    <div class="zone-row">
                        <div class="zone hand-zone" id="p1-hand">
                            <div class="zone-label">Hand</div>
                            <div class="zone-contents"></div>
                        </div>
                    </div>
                    <div class="player-info">
                        <span class="player-name" id="p1-name">Player 1</span>
                        <span class="player-life" id="p1-life">20</span>
                    </div>
                </div>
            </div>
        `;

        // Cache element references
        this.elements = {
            p1Name: this.container.querySelector('#p1-name'),
            p1Life: this.container.querySelector('#p1-life'),
            p1Hand: this.container.querySelector('#p1-hand .zone-contents'),
            p1Battlefield: this.container.querySelector('#p1-battlefield .zone-contents'),
            p1Library: this.container.querySelector('#p1-library .zone-count'),
            p1Graveyard: this.container.querySelector('#p1-graveyard .zone-contents'),
            p1Exile: this.container.querySelector('#p1-exile .zone-contents'),
            p2Name: this.container.querySelector('#p2-name'),
            p2Life: this.container.querySelector('#p2-life'),
            p2Hand: this.container.querySelector('#p2-hand .zone-contents'),
            p2Battlefield: this.container.querySelector('#p2-battlefield .zone-contents'),
            p2Library: this.container.querySelector('#p2-library .zone-count'),
            p2Graveyard: this.container.querySelector('#p2-graveyard .zone-contents'),
            p2Exile: this.container.querySelector('#p2-exile .zone-contents'),
            stack: this.container.querySelector('#stack .zone-contents'),
            turnInfo: this.container.querySelector('#turn-info')
        };
    }

    /**
     * Render a game state frame
     * @param {Object} frame - The frame data to render
     */
    render(frame) {
        if (!frame || !frame.state) {
            Logger.warn('Invalid frame data for rendering');
            return;
        }

        const { state } = frame;

        // Render Player 1
        if (state.player1) {
            this.renderPlayer(1, state.player1);
        }

        // Render Player 2
        if (state.player2) {
            this.renderPlayer(2, state.player2);
        }

        // Render Stack
        this.renderStack(state.stack || []);

        // Render Turn Info
        this.renderTurnInfo(frame);

        Logger.debug(`Rendered frame ${frame.frameNumber}`);
    }

    renderPlayer(playerNum, playerState) {
        const prefix = `p${playerNum}`;

        // Life total
        if (this.elements[`${prefix}Life`]) {
            this.elements[`${prefix}Life`].textContent = playerState.life || 0;
        }

        // Hand
        if (this.elements[`${prefix}Hand`]) {
            this.elements[`${prefix}Hand`].innerHTML = this.renderCards(playerState.hand || [], 'hand');
        }

        // Battlefield
        if (this.elements[`${prefix}Battlefield`]) {
            this.elements[`${prefix}Battlefield`].innerHTML = this.renderCards(playerState.battlefield || [], 'battlefield');
        }

        // Library (just count)
        if (this.elements[`${prefix}Library`]) {
            const libraryCount = typeof playerState.library === 'number'
                ? playerState.library
                : (playerState.library?.length || 0);
            this.elements[`${prefix}Library`].textContent = libraryCount;
        }

        // Graveyard
        if (this.elements[`${prefix}Graveyard`]) {
            this.elements[`${prefix}Graveyard`].innerHTML = this.renderCards(playerState.graveyard || [], 'graveyard');
        }

        // Exile
        if (this.elements[`${prefix}Exile`]) {
            this.elements[`${prefix}Exile`].innerHTML = this.renderCards(playerState.exile || [], 'exile');
        }
    }

    renderCards(cards, zone) {
        if (!cards || cards.length === 0) {
            return '<span class="empty-zone">Empty</span>';
        }

        return cards.map(card => this.renderCard(card, zone)).join('');
    }

    renderCard(card, zone) {
        const classes = ['card'];

        // Add type class
        if (card.type) {
            classes.push(`card-${card.type.toLowerCase().replace(/\s+/g, '-')}`);
        }

        // Add state classes
        if (card.tapped) classes.push('tapped');
        if (card.attacking) classes.push('attacking');
        if (card.blocking) classes.push('blocking');
        if (card.summoningSick) classes.push('summoning-sick');

        // Build card HTML
        let cardContent = `<div class="card-name">${card.name || 'Unknown'}</div>`;

        if (card.manaCost) {
            cardContent += `<div class="card-mana">${card.manaCost}</div>`;
        }

        if (card.power !== undefined && card.toughness !== undefined) {
            cardContent += `<div class="card-pt">${card.power}/${card.toughness}</div>`;
        }

        if (card.keywords && card.keywords.length > 0) {
            cardContent += `<div class="card-keywords">${card.keywords.join(', ')}</div>`;
        }

        return `<div class="${classes.join(' ')}" data-card-id="${card.id || ''}">${cardContent}</div>`;
    }

    renderStack(stack) {
        if (!this.elements.stack) return;

        if (!stack || stack.length === 0) {
            this.elements.stack.innerHTML = '<span class="empty-zone">Empty</span>';
            return;
        }

        this.elements.stack.innerHTML = stack.map((item, index) => {
            let itemHtml = `<div class="stack-item" data-stack-index="${index}">`;
            itemHtml += `<span class="stack-item-name">${item.name || 'Unknown'}</span>`;
            if (item.target) {
                itemHtml += `<span class="stack-item-target"> targeting ${item.target.name || 'Unknown'}</span>`;
            }
            itemHtml += '</div>';
            return itemHtml;
        }).join('');
    }

    renderTurnInfo(frame) {
        if (!this.elements.turnInfo) return;

        const turnNum = this.elements.turnInfo.querySelector('.turn-number');
        const phaseName = this.elements.turnInfo.querySelector('.phase-name');
        const activePlayer = this.elements.turnInfo.querySelector('.active-player');

        if (turnNum) turnNum.textContent = `Turn ${frame.turn || 0}`;
        if (phaseName) phaseName.textContent = frame.phase || '---';
        if (activePlayer) activePlayer.textContent = `Active: P${frame.activePlayer || 0}`;
    }

    /**
     * Set player names from metadata
     * @param {Object} metadata - Replay metadata
     */
    setPlayerNames(metadata) {
        if (!metadata) return;

        if (metadata.player1?.name && this.elements.p1Name) {
            this.elements.p1Name.textContent = metadata.player1.name;
        }
        if (metadata.player2?.name && this.elements.p2Name) {
            this.elements.p2Name.textContent = metadata.player2.name;
        }
    }

    /**
     * Clear the playmat to initial state
     */
    clear() {
        const emptyState = {
            life: 20,
            hand: [],
            library: 0,
            graveyard: [],
            exile: [],
            battlefield: []
        };

        this.renderPlayer(1, emptyState);
        this.renderPlayer(2, emptyState);
        this.renderStack([]);

        if (this.elements.turnInfo) {
            const turnNum = this.elements.turnInfo.querySelector('.turn-number');
            const phaseName = this.elements.turnInfo.querySelector('.phase-name');
            const activePlayer = this.elements.turnInfo.querySelector('.active-player');

            if (turnNum) turnNum.textContent = 'Turn 0';
            if (phaseName) phaseName.textContent = '---';
            if (activePlayer) activePlayer.textContent = 'Active: ---';
        }
    }
}

// ============================================================================
// Main Application Controller
// ============================================================================

class MTGOViewer {
    constructor() {
        this.gameState = null;
        this.controls = null;
        this.playmat = null;
        this.actionDisplay = null;
        this.isInitialized = false;
        this.isDemo = false;

        Logger.info('MTGOViewer instance created');
    }

    /**
     * Initialize the application
     */
    init() {
        Logger.group('Initializing MTGO Viewer');

        try {
            // Get container elements
            const playmatContainer = document.getElementById('playmat-container');
            const controlsContainer = document.getElementById('controls-container');
            this.actionDisplay = document.getElementById('action-display');

            if (!playmatContainer) {
                throw new Error('Playmat container not found (#playmat-container)');
            }
            if (!controlsContainer) {
                throw new Error('Controls container not found (#controls-container)');
            }

            // Initialize modules
            this.gameState = new GameState();
            this.playmat = new Playmat(playmatContainer);
            this.controls = new Controls(controlsContainer);

            // Wire up frame change callback
            this.controls.setOnFrameChange((frame) => this.onFrameChange(frame));

            // Set up file loading
            this.setupFileLoading();

            // Display welcome message
            this.showMessage('Drop a replay JSON file or click "Load Demo" to begin', 'info');

            // Add demo button
            this.addDemoButton();

            this.isInitialized = true;
            Logger.info('Initialization complete');

        } catch (error) {
            Logger.error('Initialization failed:', error);
            this.showMessage(`Initialization failed: ${error.message}`, 'error');
        }

        Logger.groupEnd();
    }

    /**
     * Set up file drag-drop and input handling
     */
    setupFileLoading() {
        // Get or create drop zone
        let dropZone = document.getElementById('drop-zone');
        if (!dropZone) {
            dropZone = document.createElement('div');
            dropZone.id = 'drop-zone';
            dropZone.innerHTML = `
                <div class="drop-zone-content">
                    <p>Drop replay JSON file here</p>
                    <p>or</p>
                    <input type="file" id="file-input" accept=".json" style="display: none;">
                    <button id="btn-browse">Browse Files</button>
                </div>
            `;
            document.body.insertBefore(dropZone, document.body.firstChild);
        }

        const fileInput = dropZone.querySelector('#file-input') || document.getElementById('file-input');
        const browseBtn = dropZone.querySelector('#btn-browse');

        // Drag and drop events
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.loadFile(files[0]);
            }
        });

        // File input change
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.loadFile(e.target.files[0]);
                }
            });
        }

        // Browse button
        if (browseBtn && fileInput) {
            browseBtn.addEventListener('click', () => {
                fileInput.click();
            });
        }

        Logger.debug('File loading handlers set up');
    }

    /**
     * Add demo button to the UI
     */
    addDemoButton() {
        const dropZone = document.getElementById('drop-zone');
        if (!dropZone) return;

        const content = dropZone.querySelector('.drop-zone-content');
        if (!content) return;

        const demoBtn = document.createElement('button');
        demoBtn.id = 'btn-demo';
        demoBtn.textContent = 'Load Demo';
        demoBtn.addEventListener('click', () => this.loadDemo());

        content.appendChild(demoBtn);
    }

    /**
     * Load a replay file
     * @param {File} file - The file to load
     */
    loadFile(file) {
        Logger.info(`Loading file: ${file.name}`);

        if (!file.name.endsWith('.json')) {
            this.showMessage('Please select a JSON file', 'error');
            return;
        }

        const reader = new FileReader();

        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                this.loadReplay(data);
                this.hideDropZone();
            } catch (error) {
                Logger.error('Failed to parse JSON:', error);
                this.showMessage(`Failed to parse JSON: ${error.message}`, 'error');
            }
        };

        reader.onerror = () => {
            Logger.error('Failed to read file');
            this.showMessage('Failed to read file', 'error');
        };

        reader.readAsText(file);
    }

    /**
     * Load demo/sample replay
     */
    loadDemo() {
        Logger.info('Loading demo replay');
        this.isDemo = true;

        try {
            this.loadReplay(SAMPLE_REPLAY);
            this.hideDropZone();
            this.showMessage('Demo loaded! Use controls to navigate the replay.', 'success');
        } catch (error) {
            Logger.error('Failed to load demo:', error);
            this.showMessage(`Failed to load demo: ${error.message}`, 'error');
        }
    }

    /**
     * Load replay data into the viewer
     * @param {Object} replayData - The replay data object
     */
    loadReplay(replayData) {
        Logger.group('Loading Replay Data');

        try {
            // Load into GameState
            this.gameState.loadReplay(replayData);

            // Initialize controls with frame count
            const frameCount = this.gameState.getFrameCount();
            this.controls.init(frameCount);

            // Set player names in playmat
            const metadata = this.gameState.getMetadata();
            if (metadata) {
                this.playmat.setPlayerNames(metadata);
                Logger.info('Match:', metadata.player1?.name || 'P1', 'vs', metadata.player2?.name || 'P2');
            }

            // Render first frame
            this.onFrameChange(0);

            Logger.info('Replay loaded successfully');

        } catch (error) {
            Logger.error('Failed to load replay:', error);
            throw error;
        }

        Logger.groupEnd();
    }

    /**
     * Handle frame change from controls
     * @param {number} frameIndex - The new frame index
     */
    onFrameChange(frameIndex) {
        if (!this.gameState.isLoaded()) {
            Logger.warn('No replay loaded');
            return;
        }

        // Get frame data
        const frame = this.gameState.getStateAtFrame(frameIndex);
        if (!frame) {
            Logger.warn(`Could not get frame ${frameIndex}`);
            return;
        }

        // Render the frame
        this.playmat.render(frame);

        // Update action display
        this.updateActionDisplay(frame);

        Logger.debug(`Frame ${frameIndex}: ${frame.action?.description || 'No action'}`);
    }

    /**
     * Update the action description display
     * @param {Object} frame - The current frame
     */
    updateActionDisplay(frame) {
        if (!this.actionDisplay) {
            // Create action display if it doesn't exist
            this.actionDisplay = document.getElementById('action-display');
            if (!this.actionDisplay) {
                this.actionDisplay = document.createElement('div');
                this.actionDisplay.id = 'action-display';
                this.actionDisplay.className = 'action-display';
                const controlsContainer = document.getElementById('controls-container');
                if (controlsContainer) {
                    controlsContainer.parentNode.insertBefore(this.actionDisplay, controlsContainer.nextSibling);
                }
            }
        }

        if (this.actionDisplay && frame.action) {
            const actionType = frame.action.type || 'unknown';
            const description = frame.action.description || '';

            this.actionDisplay.innerHTML = `
                <div class="action-type ${actionType}">${actionType.replace(/_/g, ' ').toUpperCase()}</div>
                <div class="action-description">${description}</div>
            `;

            // Add animation class
            this.actionDisplay.classList.remove('action-animate');
            void this.actionDisplay.offsetWidth; // Force reflow
            this.actionDisplay.classList.add('action-animate');
        }
    }

    /**
     * Show a message to the user
     * @param {string} message - The message text
     * @param {string} type - Message type (info, success, error, warning)
     */
    showMessage(message, type = 'info') {
        let messageContainer = document.getElementById('message-container');
        if (!messageContainer) {
            messageContainer = document.createElement('div');
            messageContainer.id = 'message-container';
            document.body.appendChild(messageContainer);
        }

        const messageEl = document.createElement('div');
        messageEl.className = `message message-${type}`;
        messageEl.textContent = message;

        messageContainer.appendChild(messageEl);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            messageEl.classList.add('fade-out');
            setTimeout(() => messageEl.remove(), 300);
        }, 5000);

        Logger.info(`[${type.toUpperCase()}] ${message}`);
    }

    /**
     * Hide the drop zone after loading a file
     */
    hideDropZone() {
        const dropZone = document.getElementById('drop-zone');
        if (dropZone) {
            dropZone.classList.add('hidden');
        }
    }

    /**
     * Show the drop zone
     */
    showDropZone() {
        const dropZone = document.getElementById('drop-zone');
        if (dropZone) {
            dropZone.classList.remove('hidden');
        }
    }
}

// ============================================================================
// DOM Ready Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    Logger.info('DOM Content Loaded - Starting MTGO Viewer');

    // Create and initialize the viewer
    const viewer = new MTGOViewer();
    viewer.init();

    // Expose to global scope for debugging
    window.MTGOViewer = viewer;
    window.Logger = Logger;

    Logger.info('MTGO Viewer ready. Access via window.MTGOViewer for debugging.');
});

// ============================================================================
// Export modules for potential ES6 module usage
// ============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        MTGOViewer,
        GameState,
        Controls,
        Playmat,
        Logger,
        SAMPLE_REPLAY
    };
}
