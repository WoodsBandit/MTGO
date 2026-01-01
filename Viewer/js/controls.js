/**
 * Playback Controls Module for MTGO Replay Viewer
 * Manages playback state, speed, and frame navigation
 */

class PlaybackControls {
    constructor(options = {}) {
        // Playback state properties
        this.isPlaying = false;
        this.speed = 1;
        this.currentFrame = 0;
        this.totalFrames = options.totalFrames || 0;

        // Valid speed values
        this.validSpeeds = [0.5, 1, 2, 4];

        // Playback interval reference
        this._playbackInterval = null;

        // Frame change callbacks
        this._frameChangeCallbacks = [];

        // DOM element references
        this._elements = {
            playPauseBtn: null,
            speedSlider: null,
            speedDisplay: null,
            timeline: null,
            frameDisplay: null
        };

        // Bind methods to preserve context
        this._handleKeydown = this._handleKeydown.bind(this);
        this._tick = this._tick.bind(this);

        // Initialize if options provided
        if (options.autoInit !== false) {
            this.init(options);
        }
    }

    /**
     * Initialize the controls and bind to DOM elements
     * @param {Object} options - Configuration options
     */
    init(options = {}) {
        // Get DOM elements
        this._elements.playPauseBtn = document.getElementById(options.playPauseBtnId || 'play-pause-btn');
        this._elements.speedSlider = document.getElementById(options.speedSliderId || 'speed-slider');
        this._elements.speedDisplay = document.getElementById(options.speedDisplayId || 'speed-display');
        this._elements.timeline = document.getElementById(options.timelineId || 'timeline');
        this._elements.frameDisplay = document.getElementById(options.frameDisplayId || 'frame-display');

        // Bind DOM event listeners
        this._bindDOMEvents();

        // Bind keyboard shortcuts
        this._bindKeyboardShortcuts();

        // Initial UI update
        this._updateUI();
    }

    /**
     * Bind event listeners to DOM elements
     */
    _bindDOMEvents() {
        // Play/Pause button
        if (this._elements.playPauseBtn) {
            this._elements.playPauseBtn.addEventListener('click', () => {
                this.togglePlayPause();
            });
        }

        // Speed slider
        if (this._elements.speedSlider) {
            this._elements.speedSlider.addEventListener('input', (e) => {
                const index = parseInt(e.target.value, 10);
                if (index >= 0 && index < this.validSpeeds.length) {
                    this.setSpeed(this.validSpeeds[index]);
                }
            });
        }

        // Timeline scrubber
        if (this._elements.timeline) {
            this._elements.timeline.addEventListener('input', (e) => {
                const frame = parseInt(e.target.value, 10);
                this.seekTo(frame);
            });

            // Pause playback while scrubbing
            this._elements.timeline.addEventListener('mousedown', () => {
                this._wasPaused = !this.isPlaying;
                if (this.isPlaying) {
                    this.pause();
                }
            });

            this._elements.timeline.addEventListener('mouseup', () => {
                if (!this._wasPaused) {
                    this.play();
                }
            });
        }
    }

    /**
     * Bind keyboard shortcuts for playback control
     */
    _bindKeyboardShortcuts() {
        document.addEventListener('keydown', this._handleKeydown);
    }

    /**
     * Handle keydown events for keyboard shortcuts
     * @param {KeyboardEvent} e - Keyboard event
     */
    _handleKeydown(e) {
        // Ignore if user is typing in an input field
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        switch (e.code) {
            case 'Space':
                e.preventDefault();
                this.togglePlayPause();
                break;

            case 'ArrowLeft':
                e.preventDefault();
                this.prevFrame();
                break;

            case 'ArrowRight':
                e.preventDefault();
                this.nextFrame();
                break;

            case 'Equal':
            case 'NumpadAdd':
                e.preventDefault();
                this._increaseSpeed();
                break;

            case 'Minus':
            case 'NumpadSubtract':
                e.preventDefault();
                this._decreaseSpeed();
                break;
        }
    }

    /**
     * Start playback
     */
    play() {
        if (this.isPlaying) return;
        if (this.totalFrames === 0) return;

        // If at the end, restart from beginning
        if (this.currentFrame >= this.totalFrames - 1) {
            this.currentFrame = 0;
        }

        this.isPlaying = true;
        this._startPlayback();
        this._updateUI();
    }

    /**
     * Pause playback
     */
    pause() {
        if (!this.isPlaying) return;

        this.isPlaying = false;
        this._stopPlayback();
        this._updateUI();
    }

    /**
     * Toggle between play and pause states
     */
    togglePlayPause() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }

    /**
     * Set playback speed
     * @param {number} speed - Speed multiplier (0.5, 1, 2, or 4)
     */
    setSpeed(speed) {
        if (!this.validSpeeds.includes(speed)) {
            console.warn(`Invalid speed: ${speed}. Valid speeds are: ${this.validSpeeds.join(', ')}`);
            return;
        }

        this.speed = speed;

        // Restart playback interval with new speed if currently playing
        if (this.isPlaying) {
            this._stopPlayback();
            this._startPlayback();
        }

        this._updateUI();
    }

    /**
     * Jump to a specific frame
     * @param {number} frame - Target frame number
     */
    seekTo(frame) {
        const targetFrame = Math.max(0, Math.min(frame, this.totalFrames - 1));

        if (targetFrame !== this.currentFrame) {
            this.currentFrame = targetFrame;
            this._notifyFrameChange();
            this._updateUI();
        }
    }

    /**
     * Advance to the next frame
     */
    nextFrame() {
        if (this.currentFrame < this.totalFrames - 1) {
            this.currentFrame++;
            this._notifyFrameChange();
            this._updateUI();
        } else if (this.isPlaying) {
            // Stop at end of playback
            this.pause();
        }
    }

    /**
     * Go back to the previous frame
     */
    prevFrame() {
        if (this.currentFrame > 0) {
            this.currentFrame--;
            this._notifyFrameChange();
            this._updateUI();
        }
    }

    /**
     * Register a callback for frame changes
     * @param {Function} callback - Function to call when frame changes
     * @returns {Function} Unsubscribe function
     */
    onFrameChange(callback) {
        if (typeof callback !== 'function') {
            throw new Error('Callback must be a function');
        }

        this._frameChangeCallbacks.push(callback);

        // Return unsubscribe function
        return () => {
            const index = this._frameChangeCallbacks.indexOf(callback);
            if (index > -1) {
                this._frameChangeCallbacks.splice(index, 1);
            }
        };
    }

    /**
     * Set the total number of frames
     * @param {number} total - Total frame count
     */
    setTotalFrames(total) {
        this.totalFrames = Math.max(0, total);

        // Adjust current frame if necessary
        if (this.currentFrame >= this.totalFrames) {
            this.currentFrame = Math.max(0, this.totalFrames - 1);
        }

        // Update timeline max value
        if (this._elements.timeline) {
            this._elements.timeline.max = Math.max(0, this.totalFrames - 1);
        }

        this._updateUI();
    }

    /**
     * Start the playback interval
     */
    _startPlayback() {
        // Base interval is 1000ms (1 second per frame at 1x speed)
        const baseInterval = 1000;
        const interval = baseInterval / this.speed;

        this._playbackInterval = setInterval(this._tick, interval);
    }

    /**
     * Stop the playback interval
     */
    _stopPlayback() {
        if (this._playbackInterval) {
            clearInterval(this._playbackInterval);
            this._playbackInterval = null;
        }
    }

    /**
     * Playback tick - advance to next frame
     */
    _tick() {
        this.nextFrame();
    }

    /**
     * Notify all registered callbacks of frame change
     */
    _notifyFrameChange() {
        const frameData = {
            currentFrame: this.currentFrame,
            totalFrames: this.totalFrames,
            isPlaying: this.isPlaying,
            speed: this.speed
        };

        this._frameChangeCallbacks.forEach(callback => {
            try {
                callback(frameData);
            } catch (error) {
                console.error('Error in frame change callback:', error);
            }
        });
    }

    /**
     * Increase playback speed to next valid value
     */
    _increaseSpeed() {
        const currentIndex = this.validSpeeds.indexOf(this.speed);
        if (currentIndex < this.validSpeeds.length - 1) {
            this.setSpeed(this.validSpeeds[currentIndex + 1]);
        }
    }

    /**
     * Decrease playback speed to previous valid value
     */
    _decreaseSpeed() {
        const currentIndex = this.validSpeeds.indexOf(this.speed);
        if (currentIndex > 0) {
            this.setSpeed(this.validSpeeds[currentIndex - 1]);
        }
    }

    /**
     * Update UI elements to reflect current state
     */
    _updateUI() {
        // Update play/pause button
        if (this._elements.playPauseBtn) {
            this._elements.playPauseBtn.textContent = this.isPlaying ? 'Pause' : 'Play';
            this._elements.playPauseBtn.setAttribute('aria-label', this.isPlaying ? 'Pause' : 'Play');
            this._elements.playPauseBtn.classList.toggle('playing', this.isPlaying);
            this._elements.playPauseBtn.classList.toggle('paused', !this.isPlaying);
        }

        // Update speed display
        if (this._elements.speedDisplay) {
            this._elements.speedDisplay.textContent = `${this.speed}x`;
        }

        // Update speed slider
        if (this._elements.speedSlider) {
            const speedIndex = this.validSpeeds.indexOf(this.speed);
            this._elements.speedSlider.value = speedIndex;
        }

        // Update timeline
        if (this._elements.timeline) {
            this._elements.timeline.value = this.currentFrame;
            this._elements.timeline.max = Math.max(0, this.totalFrames - 1);
        }

        // Update frame display
        if (this._elements.frameDisplay) {
            this._elements.frameDisplay.textContent = `${this.currentFrame + 1} / ${this.totalFrames}`;
        }
    }

    /**
     * Get current playback state
     * @returns {Object} Current state object
     */
    getState() {
        return {
            isPlaying: this.isPlaying,
            speed: this.speed,
            currentFrame: this.currentFrame,
            totalFrames: this.totalFrames
        };
    }

    /**
     * Reset controls to initial state
     */
    reset() {
        this.pause();
        this.currentFrame = 0;
        this.speed = 1;
        this._notifyFrameChange();
        this._updateUI();
    }

    /**
     * Clean up event listeners and intervals
     */
    destroy() {
        this._stopPlayback();
        document.removeEventListener('keydown', this._handleKeydown);
        this._frameChangeCallbacks = [];
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PlaybackControls;
}

// Also expose globally for browser usage
if (typeof window !== 'undefined') {
    window.PlaybackControls = PlaybackControls;
}
