# MAIN.JS FIXES

This document contains the key changes needed for main.js:

## Changes Required

1. **JS-1**: Remove duplicate GameState class stub (lines 681-789)
2. **JS-5**: Replace setInterval playback with requestAnimationFrame (lines 970-972)

---

## CHANGE 1: JS-1 - Remove Duplicate GameState Class

**LOCATION**: Lines 681-789

The main.js file contains a GameState class that duplicates the implementation in game-state.js.

### What to do:

Delete the entire GameState class block (lines 681-789) and replace with a comment noting that the real implementation is in game-state.js.

### Replace this block:

```javascript
// ============================================================================
// GameState Module (Stub - to be replaced with actual module)
// ============================================================================

class GameState {
    // ... entire class definition (approximately 105 lines)
}
```

### With:

```javascript
// ============================================================================
// NOTE: GameState class is now in game-state.js module
// The stub has been removed to avoid shadowing the real implementation.
// Make sure game-state.js is loaded before main.js in your HTML.
// ============================================================================
```

### Important: Update your HTML file

Ensure game-state.js is loaded BEFORE main.js in your HTML:

```html
<script src="js/game-state.js"></script>
<script src="js/controls.js"></script>
<script src="js/playmat.js"></script>
<script src="js/main.js"></script>
```

---

## CHANGE 2: JS-5 - Replace setInterval with requestAnimationFrame

**LOCATION**: Lines 959-991 (play and pause methods in Controls class)

### Replace the play() method (around line 959):

**OLD:**
```javascript
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
```

**NEW:**
```javascript
play() {
    if (this.isPlaying) return;
    if (this.currentFrame >= this.totalFrames - 1) {
        this.goToFrame(0);
    }

    this.isPlaying = true;
    if (this.elements.btnPlay) {
        this.elements.btnPlay.textContent = 'Pause';
    }

    // Use requestAnimationFrame for smoother playback
    this._lastFrameTime = performance.now();
    this._animationFrameId = requestAnimationFrame((timestamp) => this._playbackLoop(timestamp));

    Logger.info('Playback started');
}
```

### Add new _playbackLoop method after play():

```javascript
/**
 * Playback loop using requestAnimationFrame
 * @param {number} timestamp - Current timestamp from requestAnimationFrame
 */
_playbackLoop(timestamp) {
    if (!this.isPlaying) return;

    const elapsed = timestamp - this._lastFrameTime;

    if (elapsed >= this.playbackSpeed) {
        this._lastFrameTime = timestamp - (elapsed % this.playbackSpeed);
        this.nextFrame();
    }

    if (this.isPlaying) {
        this._animationFrameId = requestAnimationFrame((ts) => this._playbackLoop(ts));
    }
}
```

### Replace the pause() method:

**OLD:**
```javascript
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
```

**NEW:**
```javascript
pause() {
    if (!this.isPlaying) return;

    this.isPlaying = false;
    if (this.elements.btnPlay) {
        this.elements.btnPlay.textContent = 'Play';
    }

    if (this._animationFrameId) {
        cancelAnimationFrame(this._animationFrameId);
        this._animationFrameId = null;
    }

    Logger.info('Playback paused');
}
```

---

## Summary of Benefits

### Removing GameState Stub (JS-1)
- **Before**: Duplicate GameState class that shadows the real implementation
- **After**: Single source of truth in game-state.js
- **Benefit**: No confusion, consistent behavior, easier maintenance

### requestAnimationFrame (JS-5)
- **Before**: setInterval with fixed timing, can drift and cause janky playback
- **After**: requestAnimationFrame synced to display refresh rate
- **Benefit**: Smoother animations, better performance, proper frame timing
