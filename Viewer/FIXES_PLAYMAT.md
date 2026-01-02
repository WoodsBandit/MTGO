# PLAYMAT.JS FIXES

This document contains the key changes needed for playmat.js:

## Changes Required

1. **JS-3**: Convert per-card event listeners to event delegation pattern (lines 869-911)
2. **DocumentFragment batching**: Add batching in updateZone() method for DOM performance

---

## CHANGE 1: JS-3 - Event Delegation for Card Tooltips

**LOCATION**: Lines 869-911 (addCardTooltip method)

### Replace the existing addCardTooltip method with:

```javascript
/**
 * Add hover tooltip to a card - now using event delegation (JS-3 fix)
 * Note: This method now only stores card data for delegation.
 * Actual event handling is done via container-level delegation.
 */
addCardTooltip(cardElement, cardData) {
    // Store card data on element for delegation handler
    cardElement._cardData = cardData;
}
```

### Add this new method after addCardTooltip:

```javascript
/**
 * Initialize event delegation for card tooltips (JS-3 fix)
 * Called once during initialize() to set up container-level event handling
 */
_initializeTooltipDelegation() {
    let tooltip = null;
    let currentCard = null;

    // Single mouseenter handler on container using event delegation
    this.container.addEventListener('mouseover', async (e) => {
        const cardElement = e.target.closest('.card');
        if (!cardElement || cardElement === currentCard) return;

        const cardData = cardElement._cardData;
        if (!cardData || cardData.faceDown) return;

        // Clean up existing tooltip
        if (tooltip && tooltip.parentNode) {
            tooltip.parentNode.removeChild(tooltip);
        }

        currentCard = cardElement;
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

    // Single mouseleave handler on container
    this.container.addEventListener('mouseout', (e) => {
        const cardElement = e.target.closest('.card');
        const relatedCard = e.relatedTarget?.closest?.('.card');

        // Only remove tooltip if actually leaving a card
        if (cardElement && cardElement !== relatedCard) {
            if (tooltip && tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
                tooltip = null;
            }
            currentCard = null;
        }
    });

    // Single mousemove handler on container
    this.container.addEventListener('mousemove', (e) => {
        if (tooltip && currentCard) {
            tooltip.style.left = `${e.clientX}px`;
            tooltip.style.top = `${e.clientY - 10}px`;
        }
    });
}
```

### Also add this line at the end of the initialize() method:

```javascript
this._initializeTooltipDelegation();
```

---

## CHANGE 2: DocumentFragment Batching in updateZone()

**LOCATION**: Lines 919-956 (updateZone method)

### Replace the existing updateZone method with:

```javascript
/**
 * Update cards in a specific zone
 * Uses DocumentFragment for batched DOM updates (performance optimization)
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

    // Use DocumentFragment for batched DOM updates (performance optimization)
    const fragment = document.createDocumentFragment();

    // Add cards to fragment
    for (const cardData of cards) {
        const cardEl = await this.createCardElement(cardData);

        // Check if this is a new card
        const cardId = cardData.id || cardData.instanceId || cardData.name;
        if (!currentIds.has(cardId)) {
            cardEl.classList.add('entering');
            setTimeout(() => cardEl.classList.remove('entering'), 300);
        }

        fragment.appendChild(cardEl);
    }

    // Single DOM operation: clear and append fragment
    // Note: Use safe DOM methods - clear children then append
    while (zoneContainer.firstChild) {
        zoneContainer.removeChild(zoneContainer.firstChild);
    }
    zoneContainer.appendChild(fragment);
}
```

---

## Summary of Benefits

### Event Delegation (JS-3)
- **Before**: Each card had 3 event listeners (mouseenter, mouseleave, mousemove)
- **After**: Only 3 event listeners on the container, handling all cards
- **Benefit**: Reduced memory usage and improved performance with many cards

### DocumentFragment Batching
- **Before**: Multiple individual DOM insertions
- **After**: Single DOM operation using DocumentFragment
- **Benefit**: Reduced layout thrashing and improved rendering performance
