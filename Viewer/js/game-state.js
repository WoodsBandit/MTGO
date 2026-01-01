/**
 * GameState Module
 * Manages game state and replay data for MTGO Viewer
 */

class GameState {
    constructor() {
        this.metadata = null;
        this.frames = [];
        this.currentFrameIndex = 0;
        this.isLoaded = false;
    }

    /**
     * Load and parse replay data from JSON
     * @param {Object|string} jsonData - Replay data as object or JSON string
     * @returns {Object} Result with success status and any errors
     */
    loadReplay(jsonData) {
        const result = {
            success: false,
            errors: [],
            warnings: []
        };

        try {
            // Parse JSON string if needed
            let data = jsonData;
            if (typeof jsonData === 'string') {
                try {
                    data = JSON.parse(jsonData);
                } catch (parseError) {
                    result.errors.push(`Failed to parse JSON: ${parseError.message}`);
                    return result;
                }
            }

            // Validate the replay data structure
            const validation = this._validateReplayData(data);
            result.errors.push(...validation.errors);
            result.warnings.push(...validation.warnings);

            if (validation.errors.length > 0) {
                return result;
            }

            // Store the validated data
            this.metadata = this._normalizeMetadata(data.metadata);
            this.frames = this._normalizeFrames(data.frames);
            this.currentFrameIndex = 0;
            this.isLoaded = true;

            result.success = true;
            return result;

        } catch (error) {
            result.errors.push(`Unexpected error loading replay: ${error.message}`);
            return result;
        }
    }

    /**
     * Get a specific frame by index
     * @param {number} index - Frame index (0-based)
     * @returns {Object|null} Frame data or null if not found
     */
    getFrame(index) {
        if (!this.isLoaded) {
            console.warn('GameState: No replay loaded');
            return null;
        }

        if (index < 0 || index >= this.frames.length) {
            console.warn(`GameState: Frame index ${index} out of bounds (0-${this.frames.length - 1})`);
            return null;
        }

        return this.frames[index];
    }

    /**
     * Get the total number of frames in the replay
     * @returns {number} Total frame count
     */
    getTotalFrames() {
        return this.frames.length;
    }

    /**
     * Get the current frame's state
     * @returns {Object|null} Current frame data or null if not loaded
     */
    getCurrentState() {
        if (!this.isLoaded) {
            return null;
        }
        return this.getFrame(this.currentFrameIndex);
    }

    /**
     * Get the action that led to a specific frame
     * @param {number} frameIndex - Frame index
     * @returns {Object|null} Action object or null if not available
     */
    getAction(frameIndex) {
        const frame = this.getFrame(frameIndex);
        if (!frame) {
            return null;
        }
        return frame.action || null;
    }

    /**
     * Set the current frame index
     * @param {number} index - New frame index
     * @returns {boolean} True if successful
     */
    setCurrentFrame(index) {
        if (!this.isLoaded) {
            return false;
        }

        if (index < 0 || index >= this.frames.length) {
            return false;
        }

        this.currentFrameIndex = index;
        return true;
    }

    /**
     * Move to the next frame
     * @returns {boolean} True if moved, false if at end
     */
    nextFrame() {
        if (this.currentFrameIndex < this.frames.length - 1) {
            this.currentFrameIndex++;
            return true;
        }
        return false;
    }

    /**
     * Move to the previous frame
     * @returns {boolean} True if moved, false if at beginning
     */
    previousFrame() {
        if (this.currentFrameIndex > 0) {
            this.currentFrameIndex--;
            return true;
        }
        return false;
    }

    /**
     * Get the replay metadata
     * @returns {Object|null} Metadata or null if not loaded
     */
    getMetadata() {
        return this.metadata;
    }

    /**
     * Get a player's state at a specific frame
     * @param {number} frameIndex - Frame index
     * @param {number|string} playerId - Player ID (1 or 2)
     * @returns {Object|null} Player state or null
     */
    getPlayerState(frameIndex, playerId) {
        const frame = this.getFrame(frameIndex);
        if (!frame || !frame.players) {
            return null;
        }

        const id = String(playerId);
        return frame.players[id] || null;
    }

    /**
     * Check if replay is loaded
     * @returns {boolean} True if a replay is loaded
     */
    hasReplay() {
        return this.isLoaded;
    }

    /**
     * Clear the current replay data
     */
    clear() {
        this.metadata = null;
        this.frames = [];
        this.currentFrameIndex = 0;
        this.isLoaded = false;
    }

    /**
     * Validate replay data structure
     * @private
     * @param {Object} data - Raw replay data
     * @returns {Object} Validation result with errors and warnings
     */
    _validateReplayData(data) {
        const errors = [];
        const warnings = [];

        // Check for required top-level properties
        if (!data || typeof data !== 'object') {
            errors.push('Replay data must be an object');
            return { errors, warnings };
        }

        // Validate frames array
        if (!data.frames) {
            errors.push('Missing required "frames" array');
        } else if (!Array.isArray(data.frames)) {
            errors.push('"frames" must be an array');
        } else if (data.frames.length === 0) {
            errors.push('"frames" array cannot be empty');
        } else {
            // Validate individual frames
            data.frames.forEach((frame, index) => {
                const frameValidation = this._validateFrame(frame, index);
                errors.push(...frameValidation.errors);
                warnings.push(...frameValidation.warnings);
            });
        }

        // Validate metadata (optional but recommended)
        if (!data.metadata) {
            warnings.push('Missing "metadata" object - using defaults');
        } else {
            const metaValidation = this._validateMetadata(data.metadata);
            warnings.push(...metaValidation.warnings);
        }

        return { errors, warnings };
    }

    /**
     * Validate a single frame
     * @private
     * @param {Object} frame - Frame data
     * @param {number} index - Frame index
     * @returns {Object} Validation result
     */
    _validateFrame(frame, index) {
        const errors = [];
        const warnings = [];
        const prefix = `Frame ${index}:`;

        if (!frame || typeof frame !== 'object') {
            errors.push(`${prefix} must be an object`);
            return { errors, warnings };
        }

        // Check for players object
        if (!frame.players) {
            errors.push(`${prefix} missing "players" object`);
        } else if (typeof frame.players !== 'object') {
            errors.push(`${prefix} "players" must be an object`);
        } else {
            // Validate player data
            ['1', '2'].forEach(playerId => {
                if (!frame.players[playerId]) {
                    warnings.push(`${prefix} missing player ${playerId} data`);
                } else {
                    const playerValidation = this._validatePlayerState(frame.players[playerId], playerId, index);
                    warnings.push(...playerValidation.warnings);
                }
            });
        }

        // Optional fields with warnings
        if (frame.turn === undefined) {
            warnings.push(`${prefix} missing "turn" field`);
        }

        if (!frame.phase) {
            warnings.push(`${prefix} missing "phase" field`);
        }

        if (frame.activePlayer === undefined) {
            warnings.push(`${prefix} missing "activePlayer" field`);
        }

        return { errors, warnings };
    }

    /**
     * Validate player state within a frame
     * @private
     * @param {Object} player - Player state
     * @param {string} playerId - Player ID
     * @param {number} frameIndex - Frame index
     * @returns {Object} Validation result
     */
    _validatePlayerState(player, playerId, frameIndex) {
        const warnings = [];
        const prefix = `Frame ${frameIndex}, Player ${playerId}:`;

        if (player.life === undefined) {
            warnings.push(`${prefix} missing "life" field`);
        }

        if (!Array.isArray(player.hand)) {
            warnings.push(`${prefix} "hand" should be an array`);
        }

        if (!player.battlefield) {
            warnings.push(`${prefix} missing "battlefield" object`);
        }

        if (player.library === undefined) {
            warnings.push(`${prefix} missing "library" count`);
        }

        if (!Array.isArray(player.graveyard)) {
            warnings.push(`${prefix} "graveyard" should be an array`);
        }

        return { warnings };
    }

    /**
     * Validate metadata object
     * @private
     * @param {Object} metadata - Metadata object
     * @returns {Object} Validation result
     */
    _validateMetadata(metadata) {
        const warnings = [];

        if (!metadata.date) {
            warnings.push('Metadata: missing "date" field');
        }

        if (!metadata.deck1) {
            warnings.push('Metadata: missing "deck1" field');
        }

        if (!metadata.deck2) {
            warnings.push('Metadata: missing "deck2" field');
        }

        if (metadata.winner === undefined) {
            warnings.push('Metadata: missing "winner" field');
        }

        return { warnings };
    }

    /**
     * Normalize metadata with defaults
     * @private
     * @param {Object} metadata - Raw metadata
     * @returns {Object} Normalized metadata
     */
    _normalizeMetadata(metadata) {
        const defaults = {
            date: null,
            deck1: 'Unknown Deck',
            deck2: 'Unknown Deck',
            winner: null,
            format: 'Unknown',
            gameNumber: 1
        };

        if (!metadata) {
            return { ...defaults };
        }

        return {
            ...defaults,
            ...metadata
        };
    }

    /**
     * Normalize frames array with defaults for missing fields
     * @private
     * @param {Array} frames - Raw frames array
     * @returns {Array} Normalized frames
     */
    _normalizeFrames(frames) {
        return frames.map((frame, index) => this._normalizeFrame(frame, index));
    }

    /**
     * Normalize a single frame with defaults
     * @private
     * @param {Object} frame - Raw frame data
     * @param {number} index - Frame index
     * @returns {Object} Normalized frame
     */
    _normalizeFrame(frame, index) {
        const normalized = {
            frameIndex: index,
            turn: frame.turn ?? 1,
            phase: frame.phase || 'unknown',
            activePlayer: frame.activePlayer ?? 1,
            action: frame.action || null,
            players: {}
        };

        // Normalize player data
        ['1', '2'].forEach(playerId => {
            normalized.players[playerId] = this._normalizePlayerState(
                frame.players?.[playerId],
                playerId
            );
        });

        // Preserve any additional custom fields
        Object.keys(frame).forEach(key => {
            if (!['turn', 'phase', 'activePlayer', 'action', 'players'].includes(key)) {
                normalized[key] = frame[key];
            }
        });

        return normalized;
    }

    /**
     * Normalize player state with defaults
     * @private
     * @param {Object} player - Raw player state
     * @param {string} playerId - Player ID
     * @returns {Object} Normalized player state
     */
    _normalizePlayerState(player, playerId) {
        const defaults = {
            life: 20,
            hand: [],
            battlefield: {
                lands: [],
                creatures: [],
                artifacts: [],
                enchantments: [],
                planeswalkers: [],
                other: []
            },
            library: 0,
            graveyard: [],
            exile: [],
            manaPool: {
                white: 0,
                blue: 0,
                black: 0,
                red: 0,
                green: 0,
                colorless: 0
            }
        };

        if (!player) {
            return { ...defaults, playerId };
        }

        // Deep merge battlefield
        const battlefield = {
            ...defaults.battlefield,
            ...(player.battlefield || {})
        };

        // Deep merge mana pool
        const manaPool = {
            ...defaults.manaPool,
            ...(player.manaPool || {})
        };

        return {
            playerId,
            life: player.life ?? defaults.life,
            hand: Array.isArray(player.hand) ? player.hand : defaults.hand,
            battlefield,
            library: player.library ?? defaults.library,
            graveyard: Array.isArray(player.graveyard) ? player.graveyard : defaults.graveyard,
            exile: Array.isArray(player.exile) ? player.exile : defaults.exile,
            manaPool,
            // Preserve any additional custom fields
            ...Object.fromEntries(
                Object.entries(player).filter(([key]) =>
                    !['life', 'hand', 'battlefield', 'library', 'graveyard', 'exile', 'manaPool'].includes(key)
                )
            )
        };
    }

    /**
     * Get all unique phases in the replay
     * @returns {Array} Array of unique phase names
     */
    getPhases() {
        const phases = new Set();
        this.frames.forEach(frame => {
            if (frame.phase) {
                phases.add(frame.phase);
            }
        });
        return Array.from(phases);
    }

    /**
     * Get all frames for a specific turn
     * @param {number} turnNumber - Turn number
     * @returns {Array} Array of frames for that turn
     */
    getFramesForTurn(turnNumber) {
        return this.frames.filter(frame => frame.turn === turnNumber);
    }

    /**
     * Get the maximum turn number in the replay
     * @returns {number} Maximum turn number
     */
    getMaxTurn() {
        if (this.frames.length === 0) return 0;
        return Math.max(...this.frames.map(f => f.turn || 0));
    }

    /**
     * Find frames where a specific action type occurred
     * @param {string} actionType - Action type to search for
     * @returns {Array} Array of frame indices
     */
    findActionFrames(actionType) {
        const indices = [];
        this.frames.forEach((frame, index) => {
            if (frame.action?.type === actionType) {
                indices.push(index);
            }
        });
        return indices;
    }

    /**
     * Export current state as JSON string
     * @returns {string} JSON representation of the replay
     */
    toJSON() {
        return JSON.stringify({
            metadata: this.metadata,
            frames: this.frames
        }, null, 2);
    }
}

// Export for different module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GameState };
} else if (typeof window !== 'undefined') {
    window.GameState = GameState;
}
