"""
MTG Animation System
====================

A comprehensive animation system for visual feedback in the MTG engine.
Provides card animations, zone transitions, combat effects, and visual feedback.

Features:
- Frame-based animation generation
- Zone position calculation
- Combat animations (attack, block, damage)
- Visual effects (glow, highlight, damage flash)
- Configurable animation speed
- Animation queuing and playback
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Generator, Dict, Any, TYPE_CHECKING
import time
import math

if TYPE_CHECKING:
    from mtg_engine import Card


class AnimationType(Enum):
    """Types of animations available in the system."""
    MOVE = "move"           # Card moving between zones
    TAP = "tap"             # Tapping a card (90 degree rotation)
    UNTAP = "untap"         # Untapping
    ATTACK = "attack"       # Moving to red zone
    BLOCK = "block"         # Assigning as blocker
    DAMAGE = "damage"       # Taking damage (flash red)
    DESTROY = "destroy"     # Being destroyed (fade out)
    EXILE = "exile"         # Being exiled (different effect)
    COUNTER = "counter"     # Add/remove counter
    HIGHLIGHT = "highlight" # Targeting/selection
    SHAKE = "shake"         # Invalid action feedback
    DRAW = "draw"           # Drawing a card
    DISCARD = "discard"     # Discarding a card
    SACRIFICE = "sacrifice" # Sacrificing a card
    BOUNCE = "bounce"       # Returning to hand
    TRANSFORM = "transform" # Double-faced card transform
    FLIP = "flip"           # Flip card animation
    PHASE = "phase"         # Phasing in/out
    SPAWN = "spawn"         # Token creation
    STACK_RESOLVE = "stack_resolve"  # Spell resolving from stack


class EasingFunction(Enum):
    """Easing functions for smooth animations."""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BOUNCE = "bounce"
    ELASTIC = "elastic"
    OVERSHOOT = "overshoot"


@dataclass
class AnimationFrame:
    """Represents a single frame of an animation."""
    card: Any  # 'Card' type - using Any to avoid circular imports
    position: Tuple[float, float]  # x, y coordinates
    rotation: float = 0.0          # degrees (0 = upright, 90 = tapped)
    scale: float = 1.0             # 1.0 = normal size
    opacity: float = 1.0           # 0.0 = invisible, 1.0 = fully visible
    effects: List[str] = field(default_factory=list)  # 'glow', 'highlight', 'damage_flash'
    z_index: int = 0               # Layer ordering
    tint: Optional[Tuple[int, int, int, int]] = None  # RGBA color overlay

    def __post_init__(self):
        """Validate frame values."""
        self.opacity = max(0.0, min(1.0, self.opacity))
        self.scale = max(0.0, self.scale)
        self.rotation = self.rotation % 360


@dataclass
class Animation:
    """Represents a complete animation sequence."""
    animation_type: AnimationType
    card: Any  # 'Card' type
    start_pos: Tuple[float, float]
    end_pos: Tuple[float, float]
    duration_ms: int
    easing: EasingFunction = EasingFunction.EASE_OUT
    start_rotation: float = 0.0
    end_rotation: float = 0.0
    start_scale: float = 1.0
    end_scale: float = 1.0
    start_opacity: float = 1.0
    end_opacity: float = 1.0
    effects: List[str] = field(default_factory=list)
    arc_height: float = 0.0  # For parabolic movement
    delay_ms: int = 0  # Delay before animation starts
    on_complete: Optional[callable] = None  # Callback when animation finishes

    def _apply_easing(self, t: float) -> float:
        """Apply easing function to progress value t (0.0 to 1.0)."""
        if self.easing == EasingFunction.LINEAR:
            return t
        elif self.easing == EasingFunction.EASE_IN:
            return t * t
        elif self.easing == EasingFunction.EASE_OUT:
            return 1 - (1 - t) * (1 - t)
        elif self.easing == EasingFunction.EASE_IN_OUT:
            if t < 0.5:
                return 2 * t * t
            else:
                return 1 - pow(-2 * t + 2, 2) / 2
        elif self.easing == EasingFunction.BOUNCE:
            if t < 1 / 2.75:
                return 7.5625 * t * t
            elif t < 2 / 2.75:
                t -= 1.5 / 2.75
                return 7.5625 * t * t + 0.75
            elif t < 2.5 / 2.75:
                t -= 2.25 / 2.75
                return 7.5625 * t * t + 0.9375
            else:
                t -= 2.625 / 2.75
                return 7.5625 * t * t + 0.984375
        elif self.easing == EasingFunction.ELASTIC:
            if t == 0 or t == 1:
                return t
            return pow(2, -10 * t) * math.sin((t - 0.075) * (2 * math.pi) / 0.3) + 1
        elif self.easing == EasingFunction.OVERSHOOT:
            c1 = 1.70158
            c3 = c1 + 1
            return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
        return t

    def _interpolate(self, start: float, end: float, progress: float) -> float:
        """Linear interpolation between two values."""
        return start + (end - start) * progress

    def _interpolate_position(self, progress: float) -> Tuple[float, float]:
        """Interpolate position, optionally with arc."""
        eased = self._apply_easing(progress)
        x = self._interpolate(self.start_pos[0], self.end_pos[0], eased)
        y = self._interpolate(self.start_pos[1], self.end_pos[1], eased)

        # Add arc (parabolic curve)
        if self.arc_height != 0:
            # Peak at progress = 0.5
            arc_offset = -4 * self.arc_height * (progress - 0.5) ** 2 + self.arc_height
            y -= arc_offset

        return (x, y)

    def _get_effects_for_progress(self, progress: float) -> List[str]:
        """Get active effects for the current progress."""
        effects = list(self.effects)

        # Type-specific effects
        if self.animation_type == AnimationType.DAMAGE:
            # Flash red effect
            if int(progress * 6) % 2 == 0:
                effects.append('damage_flash')
        elif self.animation_type == AnimationType.HIGHLIGHT:
            effects.append('glow')
        elif self.animation_type == AnimationType.SHAKE:
            effects.append('shake')
        elif self.animation_type == AnimationType.DESTROY:
            if progress > 0.5:
                effects.append('fade_particles')
        elif self.animation_type == AnimationType.EXILE:
            effects.append('exile_glow')
        elif self.animation_type == AnimationType.SPAWN:
            effects.append('spawn_glow')

        return effects

    def _get_tint_for_progress(self, progress: float) -> Optional[Tuple[int, int, int, int]]:
        """Get tint color for current progress."""
        if self.animation_type == AnimationType.DAMAGE:
            # Red tint that fades
            if int(progress * 6) % 2 == 0:
                alpha = int(200 * (1 - progress))
                return (255, 0, 0, alpha)
        elif self.animation_type == AnimationType.EXILE:
            # White/blue glow
            alpha = int(150 * (1 - progress))
            return (200, 200, 255, alpha)
        return None

    def generate_frames(self, fps: int = 60) -> Generator[AnimationFrame, None, None]:
        """Generate animation frames at the specified FPS."""
        if self.duration_ms <= 0:
            # Instant animation - just yield end state
            yield AnimationFrame(
                card=self.card,
                position=self.end_pos,
                rotation=self.end_rotation,
                scale=self.end_scale,
                opacity=self.end_opacity,
                effects=self.effects
            )
            return

        num_frames = max(1, int(self.duration_ms * fps / 1000))

        for i in range(num_frames + 1):
            progress = i / num_frames if num_frames > 0 else 1.0
            eased = self._apply_easing(progress)

            position = self._interpolate_position(progress)
            rotation = self._interpolate(self.start_rotation, self.end_rotation, eased)
            scale = self._interpolate(self.start_scale, self.end_scale, eased)
            opacity = self._interpolate(self.start_opacity, self.end_opacity, eased)
            effects = self._get_effects_for_progress(progress)
            tint = self._get_tint_for_progress(progress)

            # Add shake effect if applicable
            if self.animation_type == AnimationType.SHAKE:
                shake_amount = 5 * (1 - progress)
                shake_x = shake_amount * math.sin(progress * 20 * math.pi)
                position = (position[0] + shake_x, position[1])

            yield AnimationFrame(
                card=self.card,
                position=position,
                rotation=rotation,
                scale=scale,
                opacity=opacity,
                effects=effects,
                tint=tint
            )

        # Call completion callback if provided
        if self.on_complete:
            self.on_complete()


class ZonePositions:
    """Calculate positions for cards in each zone."""

    # Default screen layout constants (can be scaled)
    DEFAULT_SCREEN_WIDTH = 1200
    DEFAULT_SCREEN_HEIGHT = 800
    CARD_WIDTH = 63
    CARD_HEIGHT = 88
    CARD_SPACING = 5

    # Zone base positions (x, y)
    ZONES: Dict[str, Tuple[int, int]] = {
        # Player 1 (bottom)
        'p1_hand': (100, 700),
        'p1_battlefield_lands': (100, 550),
        'p1_battlefield_creatures': (100, 450),
        'p1_battlefield_other': (100, 350),
        'p1_library': (50, 600),
        'p1_graveyard': (1100, 600),
        'p1_exile': (1100, 500),
        'p1_command': (50, 500),

        # Player 2 (top)
        'p2_hand': (100, -50),  # Off-screen for opponent
        'p2_battlefield_lands': (100, 50),
        'p2_battlefield_creatures': (100, 150),
        'p2_battlefield_other': (100, 250),
        'p2_library': (50, 100),
        'p2_graveyard': (1100, 100),
        'p2_exile': (1100, 200),
        'p2_command': (50, 200),

        # Shared zones
        'stack': (900, 400),
        'red_zone': (100, 350),  # Combat zone (center)
        'revealed': (500, 400),  # For revealed cards
    }

    # Cards per row in each zone
    ZONE_CARDS_PER_ROW: Dict[str, int] = {
        'p1_hand': 10,
        'p2_hand': 10,
        'p1_battlefield_lands': 8,
        'p1_battlefield_creatures': 8,
        'p1_battlefield_other': 8,
        'p2_battlefield_lands': 8,
        'p2_battlefield_creatures': 8,
        'p2_battlefield_other': 8,
        'stack': 1,
        'red_zone': 8,
        'p1_graveyard': 1,
        'p2_graveyard': 1,
        'p1_exile': 1,
        'p2_exile': 1,
    }

    def __init__(self, screen_width: int = None, screen_height: int = None):
        """Initialize with optional custom screen dimensions."""
        self.screen_width = screen_width or self.DEFAULT_SCREEN_WIDTH
        self.screen_height = screen_height or self.DEFAULT_SCREEN_HEIGHT
        self._scale_factor = self.screen_width / self.DEFAULT_SCREEN_WIDTH

    def get_zone_base_position(self, zone: str) -> Tuple[int, int]:
        """Get the base position for a zone."""
        base = self.ZONES.get(zone, (0, 0))
        return (int(base[0] * self._scale_factor), int(base[1] * self._scale_factor))

    def get_card_position(self, card: Any, zone: str, index: int) -> Tuple[int, int]:
        """Get position for a card in a zone."""
        base_x, base_y = self.get_zone_base_position(zone)
        cards_per_row = self.ZONE_CARDS_PER_ROW.get(zone, 10)

        # Calculate card dimensions with scaling
        card_w = int(self.CARD_WIDTH * self._scale_factor)
        card_h = int(self.CARD_HEIGHT * self._scale_factor)
        spacing = int(self.CARD_SPACING * self._scale_factor)

        # Special handling for stacked zones (graveyard, exile)
        if zone in ('p1_graveyard', 'p2_graveyard', 'p1_exile', 'p2_exile'):
            # Stack cards with slight offset
            x = base_x + index * 2
            y = base_y + index * 2
        elif zone == 'stack':
            # Stack spells vertically
            x = base_x
            y = base_y - index * (card_h // 2)
        elif 'hand' in zone:
            # Fan out hand cards with overlap
            overlap = card_w // 2
            x = base_x + index * overlap
            y = base_y
        else:
            # Standard grid layout
            x = base_x + (index % cards_per_row) * (card_w + spacing)
            y = base_y + (index // cards_per_row) * (card_h + spacing)

        return (x, y)

    def get_attacker_position(self, index: int, total_attackers: int) -> Tuple[int, int]:
        """Get position for an attacking creature in the red zone."""
        base_x, base_y = self.ZONES['red_zone']
        card_w = int(self.CARD_WIDTH * self._scale_factor)
        spacing = int(self.CARD_SPACING * self._scale_factor)

        # Center attackers in the red zone
        total_width = total_attackers * (card_w + spacing) - spacing
        start_x = base_x + (self.screen_width // 2 - total_width // 2) - base_x

        x = start_x + index * (card_w + spacing)
        y = base_y

        return (x, y)

    def get_blocker_position(self, attacker_pos: Tuple[int, int],
                            blocker_index: int, total_blockers: int) -> Tuple[int, int]:
        """Get position for a blocker relative to the attacker it's blocking."""
        card_h = int(self.CARD_HEIGHT * self._scale_factor)
        card_w = int(self.CARD_WIDTH * self._scale_factor)

        # Position blockers in front of attacker (above for P2)
        offset_y = -(card_h // 2 + 10)

        # Multiple blockers fan out
        if total_blockers > 1:
            offset_x = (blocker_index - (total_blockers - 1) / 2) * (card_w // 3)
        else:
            offset_x = 0

        return (attacker_pos[0] + offset_x, attacker_pos[1] + offset_y)


class AnimationManager:
    """Manage and queue animations."""

    SPEED_SETTINGS: Dict[str, int] = {
        'instant': 0,
        'fast': 100,      # 100ms
        'normal': 250,    # 250ms
        'slow': 500,      # 500ms
        'dramatic': 750   # 750ms for important events
    }

    def __init__(self, speed: str = 'normal', fps: int = 60):
        """Initialize the animation manager."""
        self.speed = speed
        self.fps = fps
        self.queue: List[Animation] = []
        self.parallel_queue: List[List[Animation]] = []  # Groups of parallel animations
        self.is_playing = False
        self.is_paused = False
        self.positions = ZonePositions()
        self._card_positions: Dict[int, Tuple[int, int]] = {}  # Track current positions
        self._callbacks: List[callable] = []

    def set_speed(self, speed: str):
        """Change animation speed."""
        if speed in self.SPEED_SETTINGS:
            self.speed = speed

    def get_duration(self, animation_type: AnimationType = None) -> int:
        """Get duration in ms for current speed setting."""
        base = self.SPEED_SETTINGS[self.speed]

        # Adjust duration based on animation type
        if animation_type == AnimationType.DAMAGE:
            return min(base, 200)  # Damage is always fast
        elif animation_type == AnimationType.DESTROY:
            return max(base, 300)  # Death needs time
        elif animation_type in (AnimationType.TAP, AnimationType.UNTAP):
            return base // 2  # Quick tap animations

        return base

    def _get_current_position(self, card: Any) -> Tuple[int, int]:
        """Get current position of a card."""
        card_id = id(card)
        if card_id in self._card_positions:
            return self._card_positions[card_id]
        # Default to center of screen if unknown
        return (self.positions.screen_width // 2, self.positions.screen_height // 2)

    def _set_current_position(self, card: Any, pos: Tuple[int, int]):
        """Update tracked position of a card."""
        self._card_positions[id(card)] = pos

    def animate_zone_change(self, card: Any, from_zone: str, to_zone: str,
                           from_index: int, to_index: int) -> Animation:
        """Create animation for card moving between zones."""
        start = self.positions.get_card_position(card, from_zone, from_index)
        end = self.positions.get_card_position(card, to_zone, to_index)

        # Determine arc height based on zones
        arc_height = 0
        if 'hand' in from_zone and 'battlefield' in to_zone:
            arc_height = 50  # Playing from hand
        elif 'battlefield' in from_zone and 'graveyard' in to_zone:
            arc_height = 30  # Going to graveyard
        elif from_zone == 'stack':
            arc_height = 20  # Resolving from stack

        # Determine animation type
        if to_zone == 'graveyard' or to_zone.endswith('_graveyard'):
            anim_type = AnimationType.DESTROY
        elif to_zone == 'exile' or to_zone.endswith('_exile'):
            anim_type = AnimationType.EXILE
        elif 'hand' in to_zone:
            anim_type = AnimationType.BOUNCE if 'battlefield' in from_zone else AnimationType.DRAW
        else:
            anim_type = AnimationType.MOVE

        animation = Animation(
            animation_type=anim_type,
            card=card,
            start_pos=start,
            end_pos=end,
            duration_ms=self.get_duration(anim_type),
            arc_height=arc_height,
            easing=EasingFunction.EASE_OUT
        )

        # Update position tracking
        self._set_current_position(card, end)

        return animation

    def animate_tap(self, card: Any, tap: bool = True) -> Animation:
        """Animate tapping/untapping."""
        pos = self._get_current_position(card)
        start_rotation = 0 if tap else 90
        end_rotation = 90 if tap else 0

        return Animation(
            animation_type=AnimationType.TAP if tap else AnimationType.UNTAP,
            card=card,
            start_pos=pos,
            end_pos=pos,
            start_rotation=start_rotation,
            end_rotation=end_rotation,
            duration_ms=self.get_duration(AnimationType.TAP),
            easing=EasingFunction.EASE_OUT
        )

    def animate_combat(self, attackers: List[Any],
                       blockers: Dict[Any, List[Any]] = None) -> List[Animation]:
        """
        Animate combat - attackers move to red zone, blockers intercept.

        Args:
            attackers: List of attacking creatures
            blockers: Dict mapping attacker -> list of blocking creatures
        """
        animations = []
        blockers = blockers or {}

        # Move attackers to red zone
        for i, attacker in enumerate(attackers):
            attacker_pos = self.positions.get_attacker_position(i, len(attackers))
            animations.append(Animation(
                animation_type=AnimationType.ATTACK,
                card=attacker,
                start_pos=self._get_current_position(attacker),
                end_pos=attacker_pos,
                duration_ms=self.get_duration(AnimationType.ATTACK),
                easing=EasingFunction.EASE_OUT,
                effects=['attack_glow']
            ))
            self._set_current_position(attacker, attacker_pos)

            # Animate blockers for this attacker
            if attacker in blockers:
                attacker_blockers = blockers[attacker]
                for j, blocker in enumerate(attacker_blockers):
                    blocker_pos = self.positions.get_blocker_position(
                        attacker_pos, j, len(attacker_blockers)
                    )
                    animations.append(Animation(
                        animation_type=AnimationType.BLOCK,
                        card=blocker,
                        start_pos=self._get_current_position(blocker),
                        end_pos=blocker_pos,
                        duration_ms=self.get_duration(AnimationType.BLOCK),
                        easing=EasingFunction.EASE_OUT,
                        delay_ms=self.get_duration() // 2,  # Slight delay after attackers
                        effects=['block_stance']
                    ))
                    self._set_current_position(blocker, blocker_pos)

        return animations

    def animate_damage(self, card: Any, amount: int) -> Animation:
        """Flash card red to show damage."""
        pos = self._get_current_position(card)

        return Animation(
            animation_type=AnimationType.DAMAGE,
            card=card,
            start_pos=pos,
            end_pos=pos,
            duration_ms=200,
            effects=['damage_flash', f'damage_{amount}']
        )

    def animate_destroy(self, card: Any) -> Animation:
        """Animate a card being destroyed."""
        pos = self._get_current_position(card)

        return Animation(
            animation_type=AnimationType.DESTROY,
            card=card,
            start_pos=pos,
            end_pos=(pos[0], pos[1] + 50),
            start_opacity=1.0,
            end_opacity=0.0,
            start_scale=1.0,
            end_scale=0.8,
            duration_ms=self.get_duration(AnimationType.DESTROY),
            easing=EasingFunction.EASE_IN,
            effects=['death_particles']
        )

    def animate_exile(self, card: Any) -> Animation:
        """Animate a card being exiled."""
        pos = self._get_current_position(card)

        return Animation(
            animation_type=AnimationType.EXILE,
            card=card,
            start_pos=pos,
            end_pos=pos,
            start_opacity=1.0,
            end_opacity=0.0,
            start_scale=1.0,
            end_scale=1.5,  # Expand outward
            duration_ms=self.get_duration(AnimationType.EXILE),
            easing=EasingFunction.EASE_OUT,
            effects=['exile_glow', 'white_flash']
        )

    def animate_counter(self, card: Any, counter_type: str,
                        adding: bool = True, amount: int = 1) -> Animation:
        """Animate adding or removing counters."""
        pos = self._get_current_position(card)

        return Animation(
            animation_type=AnimationType.COUNTER,
            card=card,
            start_pos=pos,
            end_pos=pos,
            start_scale=1.0 if adding else 1.1,
            end_scale=1.1 if adding else 1.0,
            duration_ms=150,
            easing=EasingFunction.BOUNCE if adding else EasingFunction.EASE_OUT,
            effects=[f'counter_{counter_type}', f'{"add" if adding else "remove"}_{amount}']
        )

    def animate_highlight(self, card: Any, duration_ms: int = 500) -> Animation:
        """Highlight a card for targeting/selection."""
        pos = self._get_current_position(card)

        return Animation(
            animation_type=AnimationType.HIGHLIGHT,
            card=card,
            start_pos=pos,
            end_pos=pos,
            start_scale=1.0,
            end_scale=1.05,
            duration_ms=duration_ms,
            easing=EasingFunction.EASE_IN_OUT,
            effects=['glow', 'highlight_border']
        )

    def animate_shake(self, card: Any) -> Animation:
        """Shake animation for invalid action feedback."""
        pos = self._get_current_position(card)

        return Animation(
            animation_type=AnimationType.SHAKE,
            card=card,
            start_pos=pos,
            end_pos=pos,
            duration_ms=300,
            effects=['shake', 'invalid_action']
        )

    def animate_draw(self, card: Any, player: int, hand_index: int) -> Animation:
        """Animate drawing a card from library to hand."""
        zone_prefix = f'p{player}_'
        start = self.positions.get_zone_base_position(f'{zone_prefix}library')
        end = self.positions.get_card_position(card, f'{zone_prefix}hand', hand_index)

        animation = Animation(
            animation_type=AnimationType.DRAW,
            card=card,
            start_pos=start,
            end_pos=end,
            duration_ms=self.get_duration(),
            arc_height=30,
            easing=EasingFunction.EASE_OUT,
            start_opacity=0.0,
            end_opacity=1.0
        )

        self._set_current_position(card, end)
        return animation

    def animate_cast_spell(self, card: Any, from_zone: str, from_index: int) -> Animation:
        """Animate casting a spell to the stack."""
        start = self.positions.get_card_position(card, from_zone, from_index)
        stack_pos = self.positions.get_zone_base_position('stack')

        animation = Animation(
            animation_type=AnimationType.MOVE,
            card=card,
            start_pos=start,
            end_pos=stack_pos,
            duration_ms=self.get_duration(),
            arc_height=50,
            easing=EasingFunction.EASE_OUT,
            effects=['cast_glow']
        )

        self._set_current_position(card, stack_pos)
        return animation

    def animate_token_spawn(self, card: Any, zone: str, index: int) -> Animation:
        """Animate a token being created."""
        pos = self.positions.get_card_position(card, zone, index)

        animation = Animation(
            animation_type=AnimationType.SPAWN,
            card=card,
            start_pos=pos,
            end_pos=pos,
            start_opacity=0.0,
            end_opacity=1.0,
            start_scale=0.5,
            end_scale=1.0,
            duration_ms=self.get_duration(),
            easing=EasingFunction.OVERSHOOT,
            effects=['spawn_particles', 'token_glow']
        )

        self._set_current_position(card, pos)
        return animation

    def queue_animation(self, animation: Animation):
        """Add animation to the sequential queue."""
        self.queue.append(animation)

    def queue_parallel(self, animations: List[Animation]):
        """Add a group of animations to play in parallel."""
        self.parallel_queue.append(animations)

    def clear_queue(self):
        """Clear all queued animations."""
        self.queue.clear()
        self.parallel_queue.clear()

    def play_queued(self) -> Generator[List[AnimationFrame], None, None]:
        """
        Play all queued animations.
        Yields lists of AnimationFrames (multiple for parallel animations).
        """
        self.is_playing = True

        try:
            # First play parallel animation groups
            for animation_group in self.parallel_queue:
                if not animation_group:
                    continue

                # Get max duration to sync frames
                max_frames = max(
                    int(a.duration_ms * self.fps / 1000) + 1
                    for a in animation_group
                )

                # Create frame generators for each animation
                generators = [a.generate_frames(self.fps) for a in animation_group]

                for frame_num in range(max_frames):
                    if self.is_paused:
                        # Could implement pause logic here
                        pass

                    frames = []
                    for gen in generators:
                        try:
                            frame = next(gen)
                            frames.append(frame)
                        except StopIteration:
                            pass

                    if frames:
                        yield frames

            # Then play sequential animations
            for animation in self.queue:
                for frame in animation.generate_frames(self.fps):
                    if self.is_paused:
                        pass
                    yield [frame]

        finally:
            self.is_playing = False
            self.clear_queue()

    def play_single(self, animation: Animation) -> Generator[AnimationFrame, None, None]:
        """Play a single animation immediately."""
        for frame in animation.generate_frames(self.fps):
            yield frame

    def on_animation_complete(self, callback: callable):
        """Register a callback for when animations complete."""
        self._callbacks.append(callback)


class VisualEffects:
    """Special visual effects for game events."""

    @staticmethod
    def damage_numbers(amount: int, position: Tuple[int, int],
                       duration_ms: int = 500) -> List[AnimationFrame]:
        """
        Generate floating damage numbers.
        Returns frames showing damage number rising and fading.
        """
        frames = []
        fps = 60
        num_frames = int(duration_ms * fps / 1000)

        for i in range(num_frames):
            progress = i / num_frames

            # Rise up
            y_offset = -30 * progress
            # Fade out in second half
            opacity = 1.0 if progress < 0.5 else 1.0 - (progress - 0.5) * 2
            # Scale up slightly then down
            scale = 1.0 + 0.3 * math.sin(progress * math.pi)

            frame = AnimationFrame(
                card=None,  # Effect-only frame
                position=(position[0], position[1] + y_offset),
                opacity=opacity,
                scale=scale,
                effects=[f'damage_text_{amount}', 'floating_number']
            )
            frames.append(frame)

        return frames

    @staticmethod
    def counter_added(counter_type: str, position: Tuple[int, int],
                     duration_ms: int = 300) -> List[AnimationFrame]:
        """Visual for counter being added."""
        frames = []
        fps = 60
        num_frames = int(duration_ms * fps / 1000)

        for i in range(num_frames):
            progress = i / num_frames

            # Pop in effect
            if progress < 0.3:
                scale = 1.5 * (progress / 0.3)
            elif progress < 0.5:
                scale = 1.5 - 0.5 * ((progress - 0.3) / 0.2)
            else:
                scale = 1.0

            frame = AnimationFrame(
                card=None,
                position=position,
                scale=scale,
                effects=[f'counter_{counter_type}', 'counter_add_effect']
            )
            frames.append(frame)

        return frames

    @staticmethod
    def counter_removed(counter_type: str, position: Tuple[int, int],
                       duration_ms: int = 300) -> List[AnimationFrame]:
        """Visual for counter being removed."""
        frames = []
        fps = 60
        num_frames = int(duration_ms * fps / 1000)

        for i in range(num_frames):
            progress = i / num_frames

            # Shrink and fade
            scale = 1.0 - 0.5 * progress
            opacity = 1.0 - progress

            frame = AnimationFrame(
                card=None,
                position=position,
                scale=scale,
                opacity=opacity,
                effects=[f'counter_{counter_type}', 'counter_remove_effect']
            )
            frames.append(frame)

        return frames

    @staticmethod
    def spell_cast_effect(card: Any, targets: List[Any],
                         card_pos: Tuple[int, int],
                         target_positions: List[Tuple[int, int]],
                         duration_ms: int = 400) -> List[Animation]:
        """Visual line from spell to targets."""
        animations = []

        # Create targeting line animation for each target
        for i, (target, target_pos) in enumerate(zip(targets, target_positions)):
            # Create a connecting line effect
            animation = Animation(
                animation_type=AnimationType.HIGHLIGHT,
                card=target,
                start_pos=card_pos,
                end_pos=target_pos,
                duration_ms=duration_ms,
                delay_ms=i * 50,  # Stagger target highlights
                easing=EasingFunction.EASE_OUT,
                effects=['targeting_line', 'target_glow']
            )
            animations.append(animation)

        return animations

    @staticmethod
    def creature_death(card: Any, position: Tuple[int, int],
                      duration_ms: int = 400) -> Animation:
        """Dramatic death animation - fade and fall."""
        return Animation(
            animation_type=AnimationType.DESTROY,
            card=card,
            start_pos=position,
            end_pos=(position[0], position[1] + 30),
            start_opacity=1.0,
            end_opacity=0.0,
            start_scale=1.0,
            end_scale=0.9,
            start_rotation=0,
            end_rotation=15,  # Slight tilt as it falls
            duration_ms=duration_ms,
            easing=EasingFunction.EASE_IN,
            effects=['death_particles', 'fade_out']
        )

    @staticmethod
    def life_change(player: int, old_life: int, new_life: int,
                   position: Tuple[int, int], duration_ms: int = 600) -> List[AnimationFrame]:
        """Animate life total change."""
        frames = []
        fps = 60
        num_frames = int(duration_ms * fps / 1000)
        change = new_life - old_life

        for i in range(num_frames):
            progress = i / num_frames

            # Interpolate the displayed number
            current_life = old_life + int(change * progress)

            # Flash effect
            if change < 0:
                # Taking damage - red flash
                tint = (255, 0, 0, int(150 * (1 - progress)))
            else:
                # Gaining life - green flash
                tint = (0, 255, 0, int(150 * (1 - progress)))

            frame = AnimationFrame(
                card=None,
                position=position,
                effects=[f'life_display_{current_life}', 'life_change'],
                tint=tint
            )
            frames.append(frame)

        return frames

    @staticmethod
    def mana_gained(mana_type: str, position: Tuple[int, int],
                   duration_ms: int = 300) -> List[AnimationFrame]:
        """Visual effect for mana being added to pool."""
        frames = []
        fps = 60
        num_frames = int(duration_ms * fps / 1000)

        # Mana colors
        mana_colors = {
            'W': (255, 255, 200, 200),
            'U': (100, 100, 255, 200),
            'B': (100, 50, 100, 200),
            'R': (255, 100, 100, 200),
            'G': (100, 255, 100, 200),
            'C': (200, 200, 200, 200),
        }
        tint = mana_colors.get(mana_type[0].upper() if mana_type else 'C',
                               (200, 200, 200, 200))

        for i in range(num_frames):
            progress = i / num_frames

            # Float up and fade
            y_offset = -20 * progress
            opacity = 1.0 - progress * 0.5
            scale = 1.0 + 0.2 * math.sin(progress * math.pi)

            frame = AnimationFrame(
                card=None,
                position=(position[0], position[1] + y_offset),
                opacity=opacity,
                scale=scale,
                effects=[f'mana_{mana_type}', 'mana_gained'],
                tint=tint
            )
            frames.append(frame)

        return frames

    @staticmethod
    def priority_indicator(player: int, position: Tuple[int, int]) -> AnimationFrame:
        """Create priority indicator for a player."""
        return AnimationFrame(
            card=None,
            position=position,
            effects=[f'priority_p{player}', 'priority_glow', 'pulsing']
        )

    @staticmethod
    def phase_transition(phase_name: str, position: Tuple[int, int],
                        duration_ms: int = 400) -> List[AnimationFrame]:
        """Visual effect for phase/step transition."""
        frames = []
        fps = 60
        num_frames = int(duration_ms * fps / 1000)

        for i in range(num_frames):
            progress = i / num_frames

            # Fade in, hold, fade out
            if progress < 0.2:
                opacity = progress / 0.2
            elif progress > 0.8:
                opacity = (1.0 - progress) / 0.2
            else:
                opacity = 1.0

            frame = AnimationFrame(
                card=None,
                position=position,
                opacity=opacity,
                effects=[f'phase_{phase_name}', 'phase_banner']
            )
            frames.append(frame)

        return frames


class AnimationPresets:
    """Pre-configured animation sequences for common game events."""

    def __init__(self, manager: AnimationManager):
        self.manager = manager

    def play_land(self, card: Any, player: int, hand_index: int,
                  battlefield_index: int) -> List[Animation]:
        """Animation sequence for playing a land."""
        zone_prefix = f'p{player}_'

        return [self.manager.animate_zone_change(
            card,
            from_zone=f'{zone_prefix}hand',
            to_zone=f'{zone_prefix}battlefield_lands',
            from_index=hand_index,
            to_index=battlefield_index
        )]

    def cast_creature(self, card: Any, player: int, hand_index: int,
                     battlefield_index: int) -> List[Animation]:
        """Animation sequence for casting a creature."""
        zone_prefix = f'p{player}_'
        animations = []

        # Move to stack first
        animations.append(self.manager.animate_cast_spell(
            card, f'{zone_prefix}hand', hand_index
        ))

        # Then resolve to battlefield
        resolve_anim = self.manager.animate_zone_change(
            card,
            from_zone='stack',
            to_zone=f'{zone_prefix}battlefield_creatures',
            from_index=0,
            to_index=battlefield_index
        )
        resolve_anim.delay_ms = self.manager.get_duration()
        animations.append(resolve_anim)

        return animations

    def combat_sequence(self, attackers: List[Any],
                        blockers: Dict[Any, List[Any]],
                        damage_assignments: Dict[Any, int]) -> List[Animation]:
        """Full combat animation sequence."""
        animations = []

        # Attack animations
        animations.extend(self.manager.animate_combat(attackers, blockers))

        # Damage animations (delayed)
        delay = self.manager.get_duration() * 2
        for card, damage in damage_assignments.items():
            if damage > 0:
                damage_anim = self.manager.animate_damage(card, damage)
                damage_anim.delay_ms = delay
                animations.append(damage_anim)

        return animations

    def creature_dies(self, card: Any, player: int,
                     bf_index: int, gy_index: int) -> List[Animation]:
        """Animation for creature death."""
        zone_prefix = f'p{player}_'
        animations = []

        # Death effect
        animations.append(self.manager.animate_destroy(card))

        # Move to graveyard
        move_anim = self.manager.animate_zone_change(
            card,
            from_zone=f'{zone_prefix}battlefield_creatures',
            to_zone=f'{zone_prefix}graveyard',
            from_index=bf_index,
            to_index=gy_index
        )
        move_anim.delay_ms = self.manager.get_duration(AnimationType.DESTROY)
        animations.append(move_anim)

        return animations


# Convenience function for creating a fully configured animation system
def create_animation_system(speed: str = 'normal',
                           screen_width: int = 1200,
                           screen_height: int = 800) -> Tuple[AnimationManager, AnimationPresets]:
    """
    Create a complete animation system.

    Args:
        speed: Animation speed ('instant', 'fast', 'normal', 'slow', 'dramatic')
        screen_width: Screen width in pixels
        screen_height: Screen height in pixels

    Returns:
        Tuple of (AnimationManager, AnimationPresets)
    """
    manager = AnimationManager(speed=speed)
    manager.positions = ZonePositions(screen_width, screen_height)
    presets = AnimationPresets(manager)

    return manager, presets
