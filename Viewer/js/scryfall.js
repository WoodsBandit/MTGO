/**
 * Scryfall API Module for MTGO Viewer
 * Handles fetching card images from Scryfall with caching and rate limiting
 */

const Scryfall = (function() {
    'use strict';

    // ===================
    // Configuration
    // ===================

    const API_BASE_URL = 'https://api.scryfall.com/cards/named';
    const RATE_LIMIT_MS = 100; // 10 requests per second = 100ms between requests
    const PLACEHOLDER_IMAGE = 'https://cards.scryfall.io/normal/front/0/0/0aacc7b0-5b88-41ab-9735-09a7c0e59acc.jpg'; // Generic card back
    const CARD_BACK_IMAGE = 'https://cards.scryfall.io/normal/back/0/0/0aacc7b0-5b88-41ab-9735-09a7c0e59acc.jpg';

    // Alternative placeholder using a data URI for offline fallback
    const OFFLINE_PLACEHOLDER = 'data:image/svg+xml,' + encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="245" height="342" viewBox="0 0 245 342">
            <rect width="245" height="342" fill="#1a1a2e" rx="12"/>
            <rect x="8" y="8" width="229" height="326" fill="none" stroke="#4a4a6a" stroke-width="2" rx="8"/>
            <text x="122.5" y="171" text-anchor="middle" fill="#6a6a8a" font-family="Arial, sans-serif" font-size="14">Card Not Found</text>
        </svg>
    `);

    // ===================
    // State
    // ===================

    // Cache for storing fetched card image URLs
    const imageCache = new Map();

    // Queue for rate limiting
    let lastRequestTime = 0;
    const requestQueue = [];
    let isProcessingQueue = false;

    // ===================
    // Rate Limiting
    // ===================

    /**
     * Process the request queue with rate limiting
     */
    async function processQueue() {
        if (isProcessingQueue || requestQueue.length === 0) {
            return;
        }

        isProcessingQueue = true;

        while (requestQueue.length > 0) {
            const now = Date.now();
            const timeSinceLastRequest = now - lastRequestTime;

            if (timeSinceLastRequest < RATE_LIMIT_MS) {
                await sleep(RATE_LIMIT_MS - timeSinceLastRequest);
            }

            const { resolve, reject, cardName } = requestQueue.shift();
            lastRequestTime = Date.now();

            try {
                const url = await fetchCardImageUrl(cardName);
                resolve(url);
            } catch (error) {
                reject(error);
            }
        }

        isProcessingQueue = false;
    }

    /**
     * Sleep utility for rate limiting
     * @param {number} ms - Milliseconds to sleep
     * @returns {Promise<void>}
     */
    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Add a request to the queue
     * @param {string} cardName - The card name to fetch
     * @returns {Promise<string>} - Promise resolving to the image URL
     */
    function queueRequest(cardName) {
        return new Promise((resolve, reject) => {
            requestQueue.push({ resolve, reject, cardName });
            processQueue();
        });
    }

    // ===================
    // API Functions
    // ===================

    /**
     * Fetch card image URL from Scryfall API (internal, no caching)
     * @param {string} cardName - The exact card name
     * @returns {Promise<string>} - The image URL
     */
    async function fetchCardImageUrl(cardName) {
        const encodedName = encodeURIComponent(cardName);
        const url = `${API_BASE_URL}?exact=${encodedName}`;

        const response = await fetch(url);

        if (!response.ok) {
            if (response.status === 404) {
                console.warn(`Scryfall: Card not found: "${cardName}"`);
                return OFFLINE_PLACEHOLDER;
            }
            throw new Error(`Scryfall API error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();

        // Handle different card layouts
        if (data.image_uris) {
            // Normal cards
            return data.image_uris.normal || data.image_uris.large || data.image_uris.small;
        } else if (data.card_faces && data.card_faces[0].image_uris) {
            // Double-faced cards - return front face by default
            return data.card_faces[0].image_uris.normal ||
                   data.card_faces[0].image_uris.large ||
                   data.card_faces[0].image_uris.small;
        }

        // Fallback to placeholder if no image found
        console.warn(`Scryfall: No image found for card: "${cardName}"`);
        return OFFLINE_PLACEHOLDER;
    }

    // ===================
    // Public API
    // ===================

    /**
     * Get the image URL for a card by name
     * Uses caching and rate limiting
     * @param {string} cardName - The exact card name
     * @returns {Promise<string>} - The image URL
     */
    async function getCardImageUrl(cardName) {
        if (!cardName || typeof cardName !== 'string') {
            console.warn('Scryfall: Invalid card name provided');
            return OFFLINE_PLACEHOLDER;
        }

        // Normalize card name for cache key
        const cacheKey = cardName.toLowerCase().trim();

        // Check cache first
        if (imageCache.has(cacheKey)) {
            return imageCache.get(cacheKey);
        }

        try {
            // Queue the request for rate limiting
            const imageUrl = await queueRequest(cardName.trim());

            // Cache the result
            imageCache.set(cacheKey, imageUrl);

            return imageUrl;
        } catch (error) {
            console.error(`Scryfall: Error fetching image for "${cardName}":`, error);
            return OFFLINE_PLACEHOLDER;
        }
    }

    /**
     * Get the back face image URL for double-faced cards
     * @param {string} cardName - The exact card name
     * @returns {Promise<string>} - The back face image URL
     */
    async function getCardBackFaceUrl(cardName) {
        if (!cardName || typeof cardName !== 'string') {
            console.warn('Scryfall: Invalid card name provided');
            return OFFLINE_PLACEHOLDER;
        }

        const cacheKey = `${cardName.toLowerCase().trim()}_back`;

        // Check cache first
        if (imageCache.has(cacheKey)) {
            return imageCache.get(cacheKey);
        }

        try {
            const encodedName = encodeURIComponent(cardName.trim());
            const url = `${API_BASE_URL}?exact=${encodedName}`;

            // Use rate limiting
            const now = Date.now();
            const timeSinceLastRequest = now - lastRequestTime;
            if (timeSinceLastRequest < RATE_LIMIT_MS) {
                await sleep(RATE_LIMIT_MS - timeSinceLastRequest);
            }
            lastRequestTime = Date.now();

            const response = await fetch(url);

            if (!response.ok) {
                return OFFLINE_PLACEHOLDER;
            }

            const data = await response.json();

            let imageUrl = OFFLINE_PLACEHOLDER;

            // Get back face for double-faced cards
            if (data.card_faces && data.card_faces.length > 1 && data.card_faces[1].image_uris) {
                imageUrl = data.card_faces[1].image_uris.normal ||
                           data.card_faces[1].image_uris.large ||
                           data.card_faces[1].image_uris.small;
            }

            imageCache.set(cacheKey, imageUrl);
            return imageUrl;
        } catch (error) {
            console.error(`Scryfall: Error fetching back face for "${cardName}":`, error);
            return OFFLINE_PLACEHOLDER;
        }
    }

    /**
     * Get the standard card back image (for face-down cards, library, etc.)
     * @returns {string} - The card back image URL
     */
    function getCardBackImage() {
        return CARD_BACK_IMAGE;
    }

    /**
     * Get the placeholder image URL
     * @returns {string} - The placeholder image URL
     */
    function getPlaceholderImage() {
        return OFFLINE_PLACEHOLDER;
    }

    /**
     * Preload multiple card images
     * Useful for preloading decks or zone cards
     * @param {string[]} cardNames - Array of card names to preload
     * @returns {Promise<Map<string, string>>} - Map of card names to image URLs
     */
    async function preloadCards(cardNames) {
        if (!Array.isArray(cardNames)) {
            console.warn('Scryfall: preloadCards expects an array of card names');
            return new Map();
        }

        const results = new Map();
        const uniqueNames = [...new Set(cardNames.filter(name => name && typeof name === 'string'))];

        for (const cardName of uniqueNames) {
            const imageUrl = await getCardImageUrl(cardName);
            results.set(cardName, imageUrl);
        }

        return results;
    }

    /**
     * Clear the image cache
     * Useful for memory management or refreshing images
     */
    function clearCache() {
        imageCache.clear();
        console.log('Scryfall: Image cache cleared');
    }

    /**
     * Get cache statistics
     * @returns {Object} - Cache statistics
     */
    function getCacheStats() {
        return {
            size: imageCache.size,
            queueLength: requestQueue.length,
            isProcessing: isProcessingQueue
        };
    }

    /**
     * Check if a card is cached
     * @param {string} cardName - The card name to check
     * @returns {boolean} - True if cached
     */
    function isCached(cardName) {
        if (!cardName) return false;
        return imageCache.has(cardName.toLowerCase().trim());
    }

    // ===================
    // Module Export
    // ===================

    return {
        // Primary functions
        getCardImageUrl,
        getCardBackFaceUrl,
        getCardBackImage,
        getPlaceholderImage,

        // Utility functions
        preloadCards,
        clearCache,
        getCacheStats,
        isCached,

        // Constants (for external use if needed)
        CARD_BACK_IMAGE,
        PLACEHOLDER_IMAGE: OFFLINE_PLACEHOLDER
    };

})();

// Export for module systems (CommonJS/ES6)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Scryfall;
}
