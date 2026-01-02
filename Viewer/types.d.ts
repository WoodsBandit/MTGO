/**
 * TypeScript type definitions for MTGO Replay Viewer
 *
 * These interfaces define the core data structures used throughout the application
 * for representing game state, player information, cards, and game actions.
 */

/**
 * Represents the mana pool for a player
 */
export interface ManaPool {
    /** White mana */
    W: number;
    /** Blue mana */
    U: number;
    /** Black mana */
    B: number;
    /** Red mana */
    R: number;
    /** Green mana */
    G: number;
    /** Colorless mana */
    C: number;
}

/**
 * Represents a Magic: The Gathering card
 */
export interface Card {
    /** Unique identifier for this card instance */
    id: number | string;

    /** Card name */
    name: string;

    /** Card type line (e.g., "Creature", "Instant", "Land") */
    type: string;

    /** Mana cost in MTG notation (e.g., "{2}{R}{R}") */
    manaCost?: string;

    /** Power value for creatures */
    power?: number;

    /** Toughness value for creatures */
    toughness?: number;

    /** Whether the card is tapped */
    tapped?: boolean;

    /** Whether the creature is attacking */
    attacking?: boolean;

    /** Whether the creature is blocking */
    blocking?: boolean;

    /** Whether the creature has summoning sickness */
    summoningSick?: boolean;

    /** Array of keywords (e.g., ["Flying", "Haste"]) */
    keywords?: string[];

    /** Controller of the card (player ID) */
    controller?: number;

    /** Target of a spell or ability */
    target?: {
        id: number | string;
        name: string;
    };

    /** Counters on the card */
    counters?: {
        [counterType: string]: number;
    };

    /** Cards attached to this card (auras, equipment) */
    attachments?: Card[];

    /** Whether the card is face-down */
    faceDown?: boolean;

    /** Base power (before modifications) */
    basePower?: number;

    /** Base toughness (before modifications) */
    baseToughness?: number;
}

/**
 * Represents the state of a single player at a point in time
 */
export interface PlayerState {
    /** Current life total */
    life: number;

    /** Cards in hand */
    hand: Card[];

    /** Library size (number) or array of cards if visible */
    library: number | Card[];

    /** Cards in graveyard */
    graveyard: Card[];

    /** Cards in exile */
    exile: Card[];

    /** Cards on the battlefield */
    battlefield: Card[];

    /** Current mana pool */
    manaPool: ManaPool;
}

/**
 * Represents a game action that occurred
 */
export interface GameAction {
    /** Type of action (e.g., "play_land", "cast_spell", "combat_damage") */
    type: string;

    /** Human-readable description of the action */
    description: string;

    /** Player who performed the action */
    player?: number;

    /** Card involved in the action */
    card?: string;

    /** Target of the action */
    target?: string;

    /** Damage dealt (for damage actions) */
    damage?: number;

    /** Attackers declared (for declare_attackers action) */
    attackers?: string[];

    /** Blockers declared (for declare_blockers action) */
    blockers?: {
        blocker: string;
        blocking: string;
    }[];
}

/**
 * Represents a single frame (snapshot) of the game state
 */
export interface GameFrame {
    /** Frame number (0-indexed) */
    frameNumber: number;

    /** Current turn number */
    turn: number;

    /** Current game phase */
    phase: string;

    /** Active player (1 or 2) */
    activePlayer: number;

    /** Action that led to this game state */
    action: GameAction;

    /** Complete game state at this frame */
    state: {
        /** Player 1's state */
        player1: PlayerState;
        /** Player 2's state */
        player2: PlayerState;
        /** Cards on the stack */
        stack: Card[];
    };
}

/**
 * Metadata about a replay
 */
export interface ReplayMetadata {
    /** Game format (e.g., "Standard", "Modern") */
    format: string;

    /** Date the game was played */
    date: string;

    /** Player 1 information */
    player1: {
        name: string;
        deck?: string;
    };

    /** Player 2 information */
    player2: {
        name: string;
        deck?: string;
    };

    /** Winner of the game (1, 2, or null for draw) */
    winner?: number | null;

    /** Game number in a match */
    gameNumber?: number;
}

/**
 * Complete replay data structure
 */
export interface Replay {
    /** Replay metadata */
    metadata: ReplayMetadata;

    /** Initial game state before any actions */
    initialState?: {
        player1: PlayerState;
        player2: PlayerState;
    };

    /** Array of game frames */
    frames: GameFrame[];
}

/**
 * Playback control state
 */
export interface PlaybackState {
    /** Whether playback is currently running */
    isPlaying: boolean;

    /** Playback speed multiplier */
    speed: number;

    /** Current frame index */
    currentFrame: number;

    /** Total number of frames */
    totalFrames: number;
}

/**
 * Frame change event data passed to callbacks
 */
export interface FrameChangeEvent {
    /** Current frame index */
    currentFrame: number;

    /** Total number of frames */
    totalFrames: number;

    /** Whether playback is active */
    isPlaying: boolean;

    /** Current playback speed */
    speed: number;
}

/**
 * Validation result from GameState
 */
export interface ValidationResult {
    /** Whether validation succeeded */
    success: boolean;

    /** Array of error messages */
    errors: string[];

    /** Array of warning messages */
    warnings: string[];
}

/**
 * Options for Playmat initialization
 */
export interface PlaymatOptions {
    /** Width of card elements in pixels */
    cardWidth?: number;

    /** Height of card elements in pixels */
    cardHeight?: number;

    /** Animation duration in milliseconds */
    animationDuration?: number;

    /** Whether to show card backs for hidden cards */
    showCardBacks?: boolean;

    /** Player orientation ('bottom' = player 1 at bottom) */
    playerOrientation?: 'bottom' | 'top';
}

/**
 * Options for PlaybackControls initialization
 */
export interface PlaybackControlsOptions {
    /** Total number of frames */
    totalFrames?: number;

    /** Whether to auto-initialize on construction */
    autoInit?: boolean;

    /** ID of play/pause button element */
    playPauseBtnId?: string;

    /** ID of speed slider element */
    speedSliderId?: string;

    /** ID of speed display element */
    speedDisplayId?: string;

    /** ID of timeline element */
    timelineId?: string;

    /** ID of frame display element */
    frameDisplayId?: string;
}

/**
 * Card image size options for Scryfall API
 */
export type ScryfallImageSize = 'small' | 'normal' | 'large' | 'png' | 'art_crop' | 'border_crop';

/**
 * Scryfall card data (partial, commonly used fields)
 */
export interface ScryfallCard {
    /** Card name */
    name: string;

    /** Image URIs for different sizes */
    image_uris?: {
        [K in ScryfallImageSize]?: string;
    };

    /** Card faces for double-faced cards */
    card_faces?: Array<{
        name: string;
        image_uris?: {
            [K in ScryfallImageSize]?: string;
        };
    }>;
}
