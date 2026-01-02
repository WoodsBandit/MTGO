/**
 * Playmat Module - Visual board state renderer for MTG game viewer
 * Manages the visual representation of the game state including cards, zones, and animations
 *
 * Security: SEC-001 XSS prevention via DOM APIs and input sanitization
 */

// =============================================================================
// Security: XSS Prevention Utilities (SEC-001)
// =============================================================================

/**
 * SEC-001: Sanitize a number for safe display.
 * @param {*} value - The value to validate
 * @param {number} defaultValue - Default if invalid
 * @returns {number} - Safe numeric value
 */
function sanitizeNumber(value, defaultValue = 0) {
    const num = parseInt(value, 10);
    if (isNaN(num) || !isFinite(num) || num < -10000 || num > 10000) {
        return defaultValue;
    }
    return num;
}

/**
 * SEC-001: Sanitize card name to prevent injection.
 * @param {string} name - Card name to validate
 * @returns {string} - Safe card name
 */
function sanitizeCardName(name) {
    if (!name || typeof name !== 'string') {
        return 'Unknown Card';
    }
    // Remove any HTML tags, limit length
    return name.replace(/<[^>]*>/g, '').trim().substring(0, 200);
}

/**
 * SEC-001: Clear element children safely (replaces innerHTML = '').
 * @param {Element} element - Element to clear
 */
function clearElement(element) {
    while (element.firstChild) {
        element.removeChild(element.firstChild);
    }
}

/**
 * SEC-001: Create text node safely.
 * @param {string} text - Text content
 * @returns {Text} - Safe text node
 */
function createSafeText(text) {
    return document.createTextNode(text == null ? '' : String(text));
}

// =============================================================================
// Scryfall API integration for card images
// =============================================================================
const Scryfall = {
    baseUrl: 'https://api.scryfall.com',
    imageCache: new Map(),

    /**
     * Get card image URL from Scryfall
     * @param {string} cardName - Name of the card
     * @param {string} size - Image size: 'small', 'normal', 'large', 'png', 'art_crop', 'border_crop'
     * @returns {Promise<string>} - URL to the card image
     */
    async getCardImageUrl(cardName, size = 'normal') {
        const cacheKey = `${cardName}_${size}`;
        if (this.imageCache.has(cacheKey)) {
            return this.imageCache.get(cacheKey);
        }

        try {
            const encodedName = encodeURIComponent(cardName);
            const response = await fetch(`${this.baseUrl}/cards/named?exact=${encodedName}`);

            if (!response.ok) {
                // Try fuzzy search as fallback
                const fuzzyResponse = await fetch(`${this.baseUrl}/cards/named?fuzzy=${encodedName}`);
                if (!fuzzyResponse.ok) {
                    throw new Error(`Card not found: ${cardName}`);
                }
                const data = await fuzzyResponse.json();
                return this.extractImageUrl(data, size, cacheKey);
            }

            const data = await response.json();
            return this.extractImageUrl(data, size, cacheKey);
        } catch (error) {
            console.error(`Error fetching card image for ${cardName}:`, error);
            return this.getPlaceholderImage();
        }
    },

    /**
     * Extract image URL from Scryfall response
     */
    extractImageUrl(data, size, cacheKey) {
        let imageUrl;

        // Handle double-faced cards
        if (data.card_faces && data.card_faces[0].image_uris) {
            imageUrl = data.card_faces[0].image_uris[size] || data.card_faces[0].image_uris.normal;
        } else if (data.image_uris) {
            imageUrl = data.image_uris[size] || data.image_uris.normal;
        } else {
            imageUrl = this.getPlaceholderImage();
        }

        this.imageCache.set(cacheKey, imageUrl);
        return imageUrl;
    },

    /**
     * Get placeholder image for cards that can't be found
     */
    getPlaceholderImage() {
        return 'data:image/svg+xml,' + encodeURIComponent(`
            <svg xmlns="http://www.w3.org/2000/svg" width="146" height="204" viewBox="0 0 146 204">
                <rect width="146" height="204" fill="#1a1a2e" rx="8"/>
                <rect x="4" y="4" width="138" height="196" fill="#16213e" rx="6" stroke="#0f3460" stroke-width="2"/>
                <text x="73" y="102" text-anchor="middle" fill="#e94560" font-family="Arial" font-size="12">Card Not Found</text>
            </svg>
        `);
    },

    /**
     * Preload images for a list of cards
     * @param {Array<string>} cardNames - Array of card names to preload
     */
    async preloadCards(cardNames) {
        const uniqueNames = [...new Set(cardNames)];
        const promises = uniqueNames.map(name => this.getCardImageUrl(name));
        await Promise.allSettled(promises);
    }
};

/**
 * Playmat class - Main visual board state manager
 */
class Playmat {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container element '${containerId}' not found`);
        }

        this.options = {
            cardWidth: 100,
            cardHeight: 140,
            animationDuration: 300,
            showCardBacks: true,
            playerOrientation: 'bottom', // 'bottom' = player 1 at bottom
            ...options
        };

        this.gameState = null;
        this.cardElements = new Map(); // cardId -> DOM element
        this.highlightedCards = new Set();

        this.initialize();
    }

    /**
     * Initialize the playmat DOM structure
     */
    initialize() {
        this.container.innerHTML = '';
        this.container.classList.add('playmat-container');

        // Create the main playmat structure
        this.container.innerHTML = `
            <div class="playmat">
                <!-- Opponent's side (Player 2) -->
                <div class="player-area opponent" data-player="2">
                    <div class="player-info">
                        <div class="player-name">Opponent</div>
                        <div class="life-total" data-life="2">20</div>
                        <div class="player-stats">
                            <span class="library-count" title="Library">0</span>
                            <span class="hand-count" title="Hand">0</span>
                        </div>
                    </div>
                    <div class="zones-row">
                        <div class="zone graveyard" data-zone="graveyard" data-player="2">
                            <div class="zone-label">Graveyard</div>
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone exile" data-zone="exile" data-player="2">
                            <div class="zone-label">Exile</div>
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone hand" data-zone="hand" data-player="2">
                            <div class="zone-label">Hand</div>
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone library" data-zone="library" data-player="2">
                            <div class="zone-label">Library</div>
                            <div class="zone-cards"></div>
                        </div>
                    </div>
                    <div class="battlefield-section">
                        <div class="zone battlefield non-lands" data-zone="battlefield-nonlands" data-player="2">
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone battlefield lands" data-zone="battlefield-lands" data-player="2">
                            <div class="zone-cards"></div>
                        </div>
                    </div>
                </div>

                <!-- Center area -->
                <div class="center-area">
                    <div class="stack-zone" data-zone="stack">
                        <div class="zone-label">Stack</div>
                        <div class="zone-cards"></div>
                    </div>
                    <div class="turn-info">
                        <div class="turn-number">Turn 1</div>
                        <div class="phase-indicator">Main Phase</div>
                        <div class="active-player">Active: Player 1</div>
                    </div>
                </div>

                <!-- Player's side (Player 1) -->
                <div class="player-area player" data-player="1">
                    <div class="battlefield-section">
                        <div class="zone battlefield lands" data-zone="battlefield-lands" data-player="1">
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone battlefield non-lands" data-zone="battlefield-nonlands" data-player="1">
                            <div class="zone-cards"></div>
                        </div>
                    </div>
                    <div class="zones-row">
                        <div class="zone library" data-zone="library" data-player="1">
                            <div class="zone-label">Library</div>
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone hand" data-zone="hand" data-player="1">
                            <div class="zone-label">Hand</div>
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone exile" data-zone="exile" data-player="1">
                            <div class="zone-label">Exile</div>
                            <div class="zone-cards"></div>
                        </div>
                        <div class="zone graveyard" data-zone="graveyard" data-player="1">
                            <div class="zone-label">Graveyard</div>
                            <div class="zone-cards"></div>
                        </div>
                    </div>
                    <div class="player-info">
                        <div class="player-name">You</div>
                        <div class="life-total" data-life="1">20</div>
                        <div class="player-stats">
                            <span class="library-count" title="Library">0</span>
                            <span class="hand-count" title="Hand">0</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.injectStyles();
    }

    /**
     * Inject required CSS styles
     */
    injectStyles() {
        if (document.getElementById('playmat-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'playmat-styles';
        styles.textContent = `
            .playmat-container {
                width: 100%;
                height: 100vh;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                overflow: hidden;
            }

            .playmat {
                display: flex;
                flex-direction: column;
                height: 100%;
                padding: 10px;
                box-sizing: border-box;
            }

            .player-area {
                flex: 1;
                display: flex;
                flex-direction: column;
                min-height: 0;
            }

            .player-area.opponent {
                flex-direction: column;
            }

            .player-area.player {
                flex-direction: column-reverse;
            }

            .player-info {
                display: flex;
                align-items: center;
                gap: 20px;
                padding: 10px 20px;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 8px;
                margin: 5px 0;
            }

            .player-name {
                font-size: 18px;
                font-weight: bold;
                color: #fff;
            }

            .life-total {
                font-size: 32px;
                font-weight: bold;
                color: #4ade80;
                min-width: 60px;
                text-align: center;
                padding: 5px 15px;
                background: rgba(0, 0, 0, 0.4);
                border-radius: 8px;
                transition: all 0.3s ease;
            }

            .life-total.damage {
                animation: damage-flash 0.5s ease;
                color: #ef4444;
            }

            .life-total.heal {
                animation: heal-flash 0.5s ease;
                color: #22c55e;
            }

            @keyframes damage-flash {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.2); background: rgba(239, 68, 68, 0.3); }
            }

            @keyframes heal-flash {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.2); background: rgba(34, 197, 94, 0.3); }
            }

            .player-stats {
                display: flex;
                gap: 15px;
                color: #94a3b8;
                font-size: 14px;
            }

            .player-stats span::before {
                margin-right: 5px;
            }

            .library-count::before { content: '📚'; }
            .hand-count::before { content: '✋'; }

            .zones-row {
                display: flex;
                gap: 10px;
                padding: 5px;
                min-height: 80px;
            }

            .zone {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 8px;
                position: relative;
            }

            .zone-label {
                position: absolute;
                top: -10px;
                left: 10px;
                font-size: 11px;
                color: #64748b;
                background: #16213e;
                padding: 2px 8px;
                border-radius: 4px;
            }

            .zone.hand {
                flex: 1;
            }

            .zone.library,
            .zone.graveyard,
            .zone.exile {
                width: 80px;
            }

            .zone-cards {
                display: flex;
                flex-wrap: wrap;
                gap: 5px;
                min-height: 50px;
                align-items: flex-start;
            }

            .zone.hand .zone-cards {
                justify-content: center;
            }

            .battlefield-section {
                flex: 1;
                display: flex;
                flex-direction: column;
                gap: 5px;
                min-height: 0;
            }

            .zone.battlefield {
                flex: 1;
                overflow-x: auto;
                overflow-y: hidden;
            }

            .zone.battlefield .zone-cards {
                flex-wrap: nowrap;
                min-height: 100%;
                padding: 10px 5px;
            }

            .zone.battlefield.lands {
                max-height: 100px;
                background: rgba(34, 139, 34, 0.1);
            }

            .zone.battlefield.non-lands {
                background: rgba(139, 69, 19, 0.1);
            }

            .center-area {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 40px;
                padding: 10px;
                min-height: 60px;
            }

            .stack-zone {
                display: flex;
                gap: 5px;
                padding: 10px;
                background: rgba(147, 51, 234, 0.2);
                border: 1px solid rgba(147, 51, 234, 0.4);
                border-radius: 8px;
                min-width: 200px;
                min-height: 50px;
            }

            .turn-info {
                text-align: center;
                color: #fff;
            }

            .turn-number {
                font-size: 24px;
                font-weight: bold;
            }

            .phase-indicator {
                font-size: 14px;
                color: #fbbf24;
                text-transform: uppercase;
            }

            .active-player {
                font-size: 12px;
                color: #94a3b8;
            }

            /* Card Styles */
            .card {
                width: ${this.options.cardWidth}px;
                height: ${this.options.cardHeight}px;
                border-radius: 8px;
                background: #1a1a2e;
                position: relative;
                cursor: pointer;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                flex-shrink: 0;
            }

            .card:hover {
                transform: translateY(-5px) scale(1.05);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
                z-index: 100;
            }

            .card img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                border-radius: 8px;
            }

            .card.tapped {
                transform: rotate(90deg);
                margin: 20px 10px;
            }

            .card.tapped:hover {
                transform: rotate(90deg) translateY(-5px) scale(1.05);
            }

            .card.highlighted {
                box-shadow: 0 0 20px 5px #fbbf24;
                animation: highlight-pulse 1s infinite;
            }

            @keyframes highlight-pulse {
                0%, 100% { box-shadow: 0 0 20px 5px rgba(251, 191, 36, 0.8); }
                50% { box-shadow: 0 0 30px 10px rgba(251, 191, 36, 0.4); }
            }

            .card.face-down img {
                display: none;
            }

            .card.face-down::after {
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(135deg, #2d1b69, #11998e);
                border-radius: 8px;
                border: 2px solid #4a3298;
            }

            .card-counters {
                position: absolute;
                bottom: 5px;
                right: 5px;
                display: flex;
                flex-wrap: wrap;
                gap: 3px;
                max-width: 80%;
            }

            .counter {
                background: rgba(0, 0, 0, 0.8);
                color: #fff;
                font-size: 10px;
                padding: 2px 5px;
                border-radius: 4px;
                font-weight: bold;
            }

            .counter.plus { background: #22c55e; }
            .counter.minus { background: #ef4444; }
            .counter.loyalty { background: #3b82f6; }
            .counter.other { background: #8b5cf6; }

            .card-pt {
                position: absolute;
                bottom: 5px;
                right: 5px;
                background: rgba(0, 0, 0, 0.85);
                color: #fff;
                font-size: 12px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }

            .card-pt.modified {
                color: #fbbf24;
            }

            .attached-cards {
                position: absolute;
                top: -20px;
                left: 50%;
                transform: translateX(-50%);
                display: flex;
                gap: 2px;
            }

            .attached-card {
                width: 30px;
                height: 42px;
                border-radius: 4px;
                overflow: hidden;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }

            .attached-card img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }

            /* Animation classes */
            .card.entering {
                animation: card-enter 0.3s ease forwards;
            }

            .card.leaving {
                animation: card-leave 0.3s ease forwards;
            }

            .card.moving {
                transition: all 0.3s ease;
            }

            @keyframes card-enter {
                from {
                    opacity: 0;
                    transform: scale(0.5) translateY(-20px);
                }
                to {
                    opacity: 1;
                    transform: scale(1) translateY(0);
                }
            }

            @keyframes card-leave {
                from {
                    opacity: 1;
                    transform: scale(1);
                }
                to {
                    opacity: 0;
                    transform: scale(0.5) translateY(20px);
                }
            }

            /* Tooltip */
            .card-tooltip {
                position: fixed;
                z-index: 1000;
                pointer-events: none;
                transform: translate(-50%, -100%);
                margin-top: -10px;
            }

            .card-tooltip img {
                width: 250px;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8);
            }

            /* Library pile visual */
            .zone.library .zone-cards {
                position: relative;
            }

            .library-pile {
                position: relative;
                width: 60px;
                height: 84px;
            }

            .library-pile .card {
                position: absolute;
                width: 60px;
                height: 84px;
            }

            .library-pile .card:nth-child(1) { top: 0; left: 0; }
            .library-pile .card:nth-child(2) { top: 2px; left: 2px; }
            .library-pile .card:nth-child(3) { top: 4px; left: 4px; }

            .library-count-overlay {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(0, 0, 0, 0.8);
                color: #fff;
                font-size: 18px;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 6px;
                z-index: 10;
            }
        `;
        document.head.appendChild(styles);
    }

    /**
     * Render the complete game state
     * @param {Object} state - The game state object
     */
    async renderGameState(state) {
        if (!state) return;

        this.gameState = state;

        // Update turn info
        this.updateTurnInfo(state);

        // Update each player
        for (const playerId of Object.keys(state.players)) {
            const playerState = state.players[playerId];

            // Update life total
            this.updateLifeTotal(playerId, playerState.life);

            // Update zones
            await this.updateZone(playerId, 'hand', playerState.hand || []);
            await this.updateZone(playerId, 'graveyard', playerState.graveyard || []);
            await this.updateZone(playerId, 'exile', playerState.exile || []);

            // Split battlefield into lands and non-lands
            const battlefield = playerState.battlefield || [];
            const lands = battlefield.filter(card => this.isLand(card));
            const nonLands = battlefield.filter(card => !this.isLand(card));

            await this.updateZone(playerId, 'battlefield-lands', lands);
            await this.updateZone(playerId, 'battlefield-nonlands', nonLands);

            // Update library (just show count)
            this.updateLibrary(playerId, playerState.library);

            // Update stats display
            this.updatePlayerStats(playerId, playerState);
        }

        // Update stack
        if (state.stack) {
            await this.updateStack(state.stack);
        }
    }

    /**
     * Update turn information display
     */
    updateTurnInfo(state) {
        const turnInfo = this.container.querySelector('.turn-info');
        if (!turnInfo) return;

        const turnNumber = turnInfo.querySelector('.turn-number');
        const phaseIndicator = turnInfo.querySelector('.phase-indicator');
        const activePlayer = turnInfo.querySelector('.active-player');

        if (turnNumber) turnNumber.textContent = `Turn ${state.turn || 1}`;
        if (phaseIndicator) phaseIndicator.textContent = this.formatPhase(state.phase);
        if (activePlayer) activePlayer.textContent = `Active: Player ${state.activePlayer || 1}`;
    }

    /**
     * Format phase name for display
     */
    formatPhase(phase) {
        if (!phase) return 'Main Phase';

        const phaseNames = {
            'untap': 'Untap',
            'upkeep': 'Upkeep',
            'draw': 'Draw',
            'precombat_main': 'Main Phase 1',
            'main1': 'Main Phase 1',
            'begin_combat': 'Beginning of Combat',
            'declare_attackers': 'Declare Attackers',
            'declare_blockers': 'Declare Blockers',
            'combat_damage': 'Combat Damage',
            'end_combat': 'End of Combat',
            'postcombat_main': 'Main Phase 2',
            'main2': 'Main Phase 2',
            'end': 'End Step',
            'cleanup': 'Cleanup'
        };

        return phaseNames[phase] || phase.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    /**
     * Check if a card is a land
     */
    isLand(card) {
        if (!card) return false;
        const types = card.types || card.type || '';
        return types.toLowerCase().includes('land');
    }

    /**
     * Create a card DOM element
     * @param {Object} cardData - Card data object
     * @returns {HTMLElement} - The card element
     */
    async createCardElement(cardData) {
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.cardId = cardData.id || cardData.instanceId || Math.random().toString(36).substr(2, 9);
        card.dataset.cardName = cardData.name || 'Unknown Card';

        // Add tapped state
        if (cardData.tapped) {
            card.classList.add('tapped');
        }

        // Add face-down state
        if (cardData.faceDown) {
            card.classList.add('face-down');
        }

        // Create image element
        const img = document.createElement('img');
        img.alt = cardData.name || 'Card';
        img.loading = 'lazy';

        // Get image from Scryfall
        if (cardData.name && !cardData.faceDown) {
            try {
                const imageUrl = await Scryfall.getCardImageUrl(cardData.name, 'normal');
                img.src = imageUrl;
            } catch (error) {
                img.src = Scryfall.getPlaceholderImage();
            }
        } else {
            img.src = Scryfall.getPlaceholderImage();
        }

        card.appendChild(img);

        // Add power/toughness for creatures
        if (cardData.power !== undefined && cardData.toughness !== undefined) {
            const pt = document.createElement('div');
            pt.className = 'card-pt';

            const basePower = cardData.basePower ?? cardData.power;
            const baseToughness = cardData.baseToughness ?? cardData.toughness;

            if (cardData.power !== basePower || cardData.toughness !== baseToughness) {
                pt.classList.add('modified');
            }

            pt.textContent = `${cardData.power}/${cardData.toughness}`;
            card.appendChild(pt);
        }

        // Add counters
        if (cardData.counters && Object.keys(cardData.counters).length > 0) {
            const countersDiv = document.createElement('div');
            countersDiv.className = 'card-counters';

            for (const [type, count] of Object.entries(cardData.counters)) {
                if (count > 0) {
                    const counter = document.createElement('span');
                    counter.className = 'counter';

                    if (type === '+1/+1' || type === 'plus') {
                        counter.classList.add('plus');
                        counter.textContent = `+${count}`;
                    } else if (type === '-1/-1' || type === 'minus') {
                        counter.classList.add('minus');
                        counter.textContent = `-${count}`;
                    } else if (type === 'loyalty') {
                        counter.classList.add('loyalty');
                        counter.textContent = count;
                    } else {
                        counter.classList.add('other');
                        counter.textContent = `${type}: ${count}`;
                    }

                    countersDiv.appendChild(counter);
                }
            }

            card.appendChild(countersDiv);
        }

        // Add attached cards (auras/equipment)
        if (cardData.attachments && cardData.attachments.length > 0) {
            const attachedDiv = document.createElement('div');
            attachedDiv.className = 'attached-cards';

            for (const attachment of cardData.attachments) {
                const attachedCard = document.createElement('div');
                attachedCard.className = 'attached-card';

                const attachedImg = document.createElement('img');
                attachedImg.alt = attachment.name || 'Attached';

                if (attachment.name) {
                    try {
                        attachedImg.src = await Scryfall.getCardImageUrl(attachment.name, 'small');
                    } catch {
                        attachedImg.src = Scryfall.getPlaceholderImage();
                    }
                }

                attachedCard.appendChild(attachedImg);
                attachedDiv.appendChild(attachedCard);
            }

            card.appendChild(attachedDiv);
        }

        // Add hover tooltip
        this.addCardTooltip(card, cardData);

        // Store reference
        this.cardElements.set(card.dataset.cardId, card);

        return card;
    }

    /**
     * Add hover tooltip to a card
     */
    addCardTooltip(cardElement, cardData) {
        let tooltip = null;

        cardElement.addEventListener('mouseenter', async (e) => {
            if (cardData.faceDown) return;

            tooltip = document.createElement('div');
            tooltip.className = 'card-tooltip';

            const img = document.createElement('img');
            img.alt = cardData.name || 'Card';

            if (cardData.name) {
                try {
                    img.src = await Scryfall.getCardImageUrl(cardData.name, 'large');
                } catch {
                    img.src = Scryfall.getPlaceholderImage();
                }
            }

            tooltip.appendChild(img);
            document.body.appendChild(tooltip);

            // Position tooltip
            const rect = cardElement.getBoundingClientRect();
            tooltip.style.left = `${rect.left + rect.width / 2}px`;
            tooltip.style.top = `${rect.top}px`;
        });

        cardElement.addEventListener('mouseleave', () => {
            if (tooltip && tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
                tooltip = null;
            }
        });

        cardElement.addEventListener('mousemove', (e) => {
            if (tooltip) {
                tooltip.style.left = `${e.clientX}px`;
                tooltip.style.top = `${e.clientY - 10}px`;
            }
        });
    }

    /**
     * Update cards in a specific zone
     * @param {string|number} playerId - Player ID
     * @param {string} zoneName - Zone name
     * @param {Array} cards - Array of card objects
     */
    async updateZone(playerId, zoneName, cards) {
        const zoneSelector = `.zone[data-zone="${zoneName}"][data-player="${playerId}"] .zone-cards`;
        const zoneContainer = this.container.querySelector(zoneSelector);

        if (!zoneContainer) {
            console.warn(`Zone not found: ${zoneName} for player ${playerId}`);
            return;
        }

        // Get current cards in zone
        const currentCards = Array.from(zoneContainer.querySelectorAll('.card'));
        const currentIds = new Set(currentCards.map(el => el.dataset.cardId));
        const newIds = new Set(cards.map(card => card.id || card.instanceId || card.name));

        // Remove cards that are no longer in zone
        for (const cardEl of currentCards) {
            if (!newIds.has(cardEl.dataset.cardId)) {
                await this.animateCardRemoval(cardEl);
            }
        }

        // SEC-001: Clear zone safely using DOM APIs
        clearElement(zoneContainer);

        // Add cards
        for (const cardData of cards) {
            const cardEl = await this.createCardElement(cardData);

            // Check if this is a new card
            const cardId = cardData.id || cardData.instanceId || cardData.name;
            if (!currentIds.has(cardId)) {
                cardEl.classList.add('entering');
                setTimeout(() => cardEl.classList.remove('entering'), 300);
            }

            zoneContainer.appendChild(cardEl);
        }
    }

    /**
     * Animate card removal
     */
    async animateCardRemoval(cardElement) {
        return new Promise(resolve => {
            cardElement.classList.add('leaving');
            setTimeout(() => {
                if (cardElement.parentNode) {
                    cardElement.parentNode.removeChild(cardElement);
                }
                resolve();
            }, this.options.animationDuration);
        });
    }

    /**
     * Update the stack zone
     */
    async updateStack(stackItems) {
        const stackContainer = this.container.querySelector('.stack-zone .zone-cards');
        if (!stackContainer) return;

        // SEC-001: Clear stack safely using DOM APIs
        clearElement(stackContainer);

        for (const item of stackItems) {
            const cardEl = await this.createCardElement(item);
            cardEl.classList.add('entering');
            setTimeout(() => cardEl.classList.remove('entering'), 300);
            stackContainer.appendChild(cardEl);
        }
    }

    /**
     * Update library display
     */
    updateLibrary(playerId, libraryCount) {
        const libraryZone = this.container.querySelector(
            `.zone[data-zone="library"][data-player="${playerId}"] .zone-cards`
        );

        if (!libraryZone) return;

        // SEC-001: Sanitize the count value
        const count = sanitizeNumber(
            typeof libraryCount === 'number' ? libraryCount : (libraryCount?.length || 0),
            0
        );

        // SEC-001: Build library pile using DOM APIs instead of innerHTML
        clearElement(libraryZone);

        const libraryPile = document.createElement('div');
        libraryPile.className = 'library-pile';

        // Add face-down cards for visual pile effect
        const card1 = document.createElement('div');
        card1.className = 'card face-down';
        libraryPile.appendChild(card1);

        if (count > 1) {
            const card2 = document.createElement('div');
            card2.className = 'card face-down';
            libraryPile.appendChild(card2);
        }

        if (count > 2) {
            const card3 = document.createElement('div');
            card3.className = 'card face-down';
            libraryPile.appendChild(card3);
        }

        // SEC-001: Use textContent for count display (safe)
        const countOverlay = document.createElement('div');
        countOverlay.className = 'library-count-overlay';
        countOverlay.textContent = String(count);
        libraryPile.appendChild(countOverlay);

        libraryZone.appendChild(libraryPile);
    }

    /**
     * Update player stats display
     */
    updatePlayerStats(playerId, playerState) {
        const playerArea = this.container.querySelector(`.player-area[data-player="${playerId}"]`);
        if (!playerArea) return;

        const libraryCount = playerArea.querySelector('.library-count');
        const handCount = playerArea.querySelector('.hand-count');

        if (libraryCount) {
            const libCount = typeof playerState.library === 'number'
                ? playerState.library
                : (playerState.library?.length || 0);
            libraryCount.textContent = libCount;
        }

        if (handCount) {
            handCount.textContent = playerState.hand?.length || 0;
        }
    }

    /**
     * Update life total display
     * @param {string|number} playerId - Player ID
     * @param {number} life - New life total
     */
    updateLifeTotal(playerId, life) {
        const lifeElement = this.container.querySelector(`.life-total[data-life="${playerId}"]`);
        if (!lifeElement) return;

        const currentLife = parseInt(lifeElement.textContent) || 20;

        if (life !== currentLife) {
            // Add animation class
            lifeElement.classList.remove('damage', 'heal');
            void lifeElement.offsetWidth; // Force reflow

            if (life < currentLife) {
                lifeElement.classList.add('damage');
            } else {
                lifeElement.classList.add('heal');
            }

            // Remove animation class after animation completes
            setTimeout(() => {
                lifeElement.classList.remove('damage', 'heal');
            }, 500);
        }

        lifeElement.textContent = life;

        // Change color based on life total
        if (life <= 5) {
            lifeElement.style.color = '#ef4444';
        } else if (life <= 10) {
            lifeElement.style.color = '#f97316';
        } else {
            lifeElement.style.color = '#4ade80';
        }
    }

    /**
     * Highlight a specific card
     * @param {string} cardId - Card ID to highlight
     */
    highlightCard(cardId) {
        const cardElement = this.cardElements.get(cardId);
        if (cardElement) {
            cardElement.classList.add('highlighted');
            this.highlightedCards.add(cardId);
        }

        // Also search by data attribute
        const cardByAttr = this.container.querySelector(`.card[data-card-id="${cardId}"]`);
        if (cardByAttr) {
            cardByAttr.classList.add('highlighted');
            this.highlightedCards.add(cardId);
        }
    }

    /**
     * Remove all highlights
     */
    clearHighlights() {
        for (const cardId of this.highlightedCards) {
            const cardElement = this.cardElements.get(cardId);
            if (cardElement) {
                cardElement.classList.remove('highlighted');
            }
        }

        // Also clear by class
        this.container.querySelectorAll('.card.highlighted').forEach(el => {
            el.classList.remove('highlighted');
        });

        this.highlightedCards.clear();
    }

    /**
     * Animate a card moving between zones
     * @param {string} cardId - Card ID
     * @param {Object} fromZone - Source zone {playerId, zoneName}
     * @param {Object} toZone - Destination zone {playerId, zoneName}
     */
    async animateCardMovement(cardId, fromZone, toZone) {
        const cardElement = this.cardElements.get(cardId);
        if (!cardElement) return;

        // Get positions
        const startRect = cardElement.getBoundingClientRect();

        // Create a clone for animation
        const clone = cardElement.cloneNode(true);
        clone.style.position = 'fixed';
        clone.style.left = `${startRect.left}px`;
        clone.style.top = `${startRect.top}px`;
        clone.style.width = `${startRect.width}px`;
        clone.style.height = `${startRect.height}px`;
        clone.style.zIndex = '1000';
        clone.style.transition = `all ${this.options.animationDuration}ms ease`;
        document.body.appendChild(clone);

        // Remove original
        cardElement.remove();

        // Get destination
        const destZone = this.container.querySelector(
            `.zone[data-zone="${toZone.zoneName}"][data-player="${toZone.playerId}"] .zone-cards`
        );

        if (destZone) {
            const destRect = destZone.getBoundingClientRect();

            // Animate to destination
            requestAnimationFrame(() => {
                clone.style.left = `${destRect.left + 10}px`;
                clone.style.top = `${destRect.top + 10}px`;
            });
        }

        // Remove clone after animation
        setTimeout(() => {
            clone.remove();
        }, this.options.animationDuration);
    }

    /**
     * Set player names
     */
    setPlayerNames(player1Name, player2Name) {
        const player1 = this.container.querySelector('.player-area[data-player="1"] .player-name');
        const player2 = this.container.querySelector('.player-area[data-player="2"] .player-name');

        if (player1) player1.textContent = player1Name;
        if (player2) player2.textContent = player2Name;
    }

    /**
     * Clear the playmat
     */
    clear() {
        this.cardElements.clear();
        this.highlightedCards.clear();
        this.gameState = null;
        this.initialize();
    }

    /**
     * Get the current game state
     */
    getGameState() {
        return this.gameState;
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Playmat, Scryfall };
}

// Also make available globally
if (typeof window !== 'undefined') {
    window.Playmat = Playmat;
    window.Scryfall = Scryfall;
}
