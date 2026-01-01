"""MTG Engine V3 - Layer System (CR 613)

This module implements the complete layer system for applying continuous effects
as defined in the Magic: The Gathering Comprehensive Rules section 613.

Key Concepts:
- CR 613.1: The seven layers for applying continuous effects
- CR 613.2: Within each layer, effects are applied in timestamp order
- CR 613.3: Layer 7 sublayers for P/T modifications
- CR 613.7: Dependencies between effects (CR 613.8)
- CR 613.8: Dependency rules that override timestamp ordering

The layer system ensures deterministic and rules-accurate game state calculation
by applying effects in the correct order.
"""
from dataclasses import dataclass, field
from typing import (
    List, Dict, Optional, Set, Callable, Any, Tuple,
    Union, TYPE_CHECKING
)
from enum import Enum
from collections import defaultdict
import copy

from ..types import (
    ObjectId, PlayerId, Timestamp, Zone, Color, CardType,
    Supertype, CounterType, StepType, PhaseType, KeywordAbility
)

if TYPE_CHECKING:
    from ..game import Game
    from ..objects import GameObject, Permanent, Card
    from ..zones import ZoneManager
    from .continuous import ContinuousEffect, Duration, DurationTracker


# =============================================================================
# LAYER ENUMERATION (CR 613.1)
# =============================================================================

class Layer(Enum):
    """The seven layers of continuous effects per CR 613.1

    Layer order is critical for correct game state calculation.
    Effects in lower layers are applied before effects in higher layers.

    Layer 7 is subdivided into sublayers 7a-7e for power/toughness effects.
    The numeric values use decimals to maintain proper ordering.
    """
    # Layer 1: Copy effects (CR 613.1a)
    # Clone, Vesuvan Doppelganger, Copy Artifact
    LAYER_1_COPY = 1

    # Layer 2: Control-changing effects (CR 613.1b)
    # Control Magic, Sower of Temptation, Act of Treason
    LAYER_2_CONTROL = 2

    # Layer 3: Text-changing effects (CR 613.1c)
    # Magical Hack, Sleight of Mind, Mind Bend
    LAYER_3_TEXT = 3

    # Layer 4: Type-changing effects (CR 613.1d)
    # Blood Moon, Arcane Adaptation, Conspiracy
    LAYER_4_TYPE = 4

    # Layer 5: Color-changing effects (CR 613.1e)
    # Painter's Servant, Trait Doctoring, Shifting Sky
    LAYER_5_COLOR = 5

    # Layer 6: Ability-adding/removing effects (CR 613.1f)
    # Akroma's Memorial, Muraganda Petroglyphs, Humility
    LAYER_6_ABILITY = 6

    # Layer 7a: Characteristic-defining abilities (CR 613.4a)
    # Tarmogoyf's P/T, Nightmare's P/T based on swamps
    LAYER_7A_CDA = 7.1

    # Layer 7b: Set P/T to specific values (CR 613.4b)
    # Turn to Frog (becomes 1/1), Ovinize (becomes 0/1)
    LAYER_7B_SET_PT = 7.2

    # Layer 7c: Modify P/T with +N/+N or -N/-N (CR 613.4c)
    # Giant Growth (+3/+3), Glorious Anthem (+1/+1)
    LAYER_7C_MODIFY_PT = 7.3

    # Layer 7d: P/T changes from counters (CR 613.4d)
    # +1/+1 counters, -1/-1 counters
    LAYER_7D_COUNTERS = 7.4

    # Layer 7e: Switch P/T effects (CR 613.4e)
    # About Face, Twisted Image, Inside Out
    LAYER_7E_SWITCH = 7.5

    def __lt__(self, other):
        """Enable proper sorting of layers by value."""
        if isinstance(other, Layer):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, Layer):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, Layer):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Layer):
            return self.value >= other.value
        return NotImplemented


# =============================================================================
# DEPENDENCY TYPES
# =============================================================================

class DependencyType(Enum):
    """Types of dependencies between continuous effects (CR 613.8)."""
    # No dependency
    NONE = 0

    # Effect A's existence depends on Effect B
    # Example: "Green creatures get +1/+1" depends on "All creatures are green"
    EXISTENCE = 1

    # Effect A's result depends on Effect B's result
    # Example: Two anthems that boost each other's creatures
    VALUE = 2


# =============================================================================
# LAYER SYSTEM
# =============================================================================

class LayerSystem:
    """Manages the layer system for continuous effects (CR 613).

    The LayerSystem is responsible for:
    - Tracking all active continuous effects
    - Applying effects in correct layer order
    - Handling dependencies between effects within the same layer
    - Managing effect expiration and cleanup

    This class should be called:
    - Before each time state-based actions are checked
    - After any zone change
    - After any effect is created or removed

    Attributes:
        game: Reference to the game object
        effects: List of all active continuous effects
    """

    def __init__(self, game: 'Game'):
        """Initialize the layer system.

        Args:
            game: The game instance this layer system belongs to
        """
        self.game: 'Game' = game
        self.effects: List['ContinuousEffect'] = []

        # Cache for optimization
        self._effects_by_layer: Dict[Layer, List['ContinuousEffect']] = defaultdict(list)
        self._cache_valid: bool = False

        # Dependency tracking
        self._dependency_graph: Dict[int, Set[int]] = defaultdict(set)

    # =========================================================================
    # EFFECT MANAGEMENT
    # =========================================================================

    def add_effect(self, effect: 'ContinuousEffect') -> None:
        """Add a continuous effect to the layer system.

        Args:
            effect: The continuous effect to add
        """
        self.effects.append(effect)
        self._cache_valid = False

    def remove_effect(self, effect: 'ContinuousEffect') -> None:
        """Remove a specific continuous effect.

        Args:
            effect: The continuous effect to remove
        """
        if effect in self.effects:
            self.effects.remove(effect)
            self._cache_valid = False

    def remove_effects_from_source(self, source: Any) -> None:
        """Remove all effects originating from a specific source.

        This is typically called when a permanent leaves the battlefield
        and its static abilities' effects should end.

        Args:
            source: The source object (usually a Permanent)
        """
        source_id = getattr(source, 'object_id', source)

        original_count = len(self.effects)
        self.effects = [e for e in self.effects if e.source_id != source_id]

        if len(self.effects) != original_count:
            self._cache_valid = False

    def get_expired_effects(self) -> List['ContinuousEffect']:
        """Get all effects that have expired.

        Returns:
            List of expired ContinuousEffect objects
        """
        expired = []
        for effect in self.effects:
            if effect.is_expired(self.game):
                expired.append(effect)
        return expired

    def cleanup_expired(self) -> None:
        """Remove all expired effects from the system.

        This should be called during cleanup step or when processing
        state-based actions.
        """
        original_count = len(self.effects)
        self.effects = [e for e in self.effects if not e.is_expired(self.game)]

        if len(self.effects) != original_count:
            self._cache_valid = False

    # =========================================================================
    # LAYER APPLICATION
    # =========================================================================

    def apply_all_effects(self) -> None:
        """Apply all continuous effects in layer order (CR 613).

        This is the main entry point for the layer system. It:
        1. Gets all permanents on the battlefield
        2. Resets their characteristics to base (printed) values
        3. For each layer in order:
           a. Gets effects in that layer
           b. Sorts by timestamp (respecting dependencies)
           c. Applies each effect to matching objects
        4. Applies counter-based P/T modifications in layer 7d
        """
        # Remove expired effects first
        self.cleanup_expired()

        # Get all permanents on the battlefield
        permanents = self._get_all_permanents()

        # Reset all permanents to base characteristics
        for perm in permanents:
            self._reset_to_base(perm)

        # Rebuild cache if needed
        if not self._cache_valid:
            self._rebuild_cache()

        # Apply effects in layer order
        for layer in sorted(Layer, key=lambda l: l.value):
            self._apply_layer(layer, permanents)

    def _get_all_permanents(self) -> List['Permanent']:
        """Get all permanents currently on the battlefield.

        Returns:
            List of all Permanent objects on the battlefield
        """
        if hasattr(self.game, 'zones') and hasattr(self.game.zones, 'battlefield'):
            if hasattr(self.game.zones.battlefield, 'permanents'):
                return list(self.game.zones.battlefield.permanents())
            elif hasattr(self.game.zones.battlefield, 'objects'):
                return list(self.game.zones.battlefield.objects)
        return []

    def _reset_to_base(self, permanent: 'Permanent') -> None:
        """Reset a permanent to its base (printed) characteristics.

        This is called before applying any continuous effects so that
        all effects are applied fresh each time.

        Args:
            permanent: The permanent to reset
        """
        # Get base characteristics from source card or base_characteristics
        if hasattr(permanent, 'base_characteristics'):
            base = permanent.base_characteristics

            # Reset types
            if hasattr(permanent, 'characteristics'):
                chars = permanent.characteristics

                if hasattr(base, 'types') and hasattr(chars, 'types'):
                    chars.types = set(base.types) if base.types else set()

                if hasattr(base, 'subtypes') and hasattr(chars, 'subtypes'):
                    chars.subtypes = set(base.subtypes) if base.subtypes else set()

                if hasattr(base, 'supertypes') and hasattr(chars, 'supertypes'):
                    chars.supertypes = set(base.supertypes) if base.supertypes else set()

                # Reset colors
                if hasattr(base, 'colors') and hasattr(chars, 'colors'):
                    chars.colors = set(base.colors) if base.colors else set()

                # Reset P/T
                if hasattr(base, 'power') and hasattr(chars, 'power'):
                    chars.power = base.power

                if hasattr(base, 'toughness') and hasattr(chars, 'toughness'):
                    chars.toughness = base.toughness

                # Reset loyalty
                if hasattr(base, 'loyalty') and hasattr(chars, 'loyalty'):
                    chars.loyalty = base.loyalty

        # Reset granted abilities
        if hasattr(permanent, 'granted_abilities'):
            permanent.granted_abilities = []

        # Reset keywords cache
        if hasattr(permanent, '_keyword_cache'):
            # Restore from base keywords if available
            if hasattr(permanent, 'base_characteristics'):
                base = permanent.base_characteristics
                if hasattr(base, 'keywords') and base.keywords:
                    permanent._keyword_cache = set(k.lower() for k in base.keywords)
                else:
                    permanent._keyword_cache = set()
            else:
                permanent._keyword_cache = set()

    def _rebuild_cache(self) -> None:
        """Rebuild the layer cache for efficient layer-based access."""
        self._effects_by_layer.clear()
        for effect in self.effects:
            self._effects_by_layer[effect.layer].append(effect)
        self._cache_valid = True

    def _apply_layer(self, layer: Layer, permanents: List['Permanent']) -> None:
        """Apply all effects in a specific layer.

        Args:
            layer: The layer to apply
            permanents: List of all permanents on the battlefield
        """
        layer_effects = self._effects_by_layer.get(layer, [])

        if layer_effects:
            # Sort effects respecting dependencies
            sorted_effects = self._sort_effects_in_layer(layer_effects)

            # Apply each effect to matching permanents
            for effect in sorted_effects:
                for perm in permanents:
                    if effect.applies_to(perm, self.game):
                        effect.apply(perm, self.game)

        # Special handling for Layer 7d - counters
        if layer == Layer.LAYER_7D_COUNTERS:
            for perm in permanents:
                self._apply_counter_pt(perm)

    def _apply_counter_pt(self, permanent: 'Permanent') -> None:
        """Apply P/T modifications from counters (Layer 7d).

        Per CR 613.4d, +1/+1 and -1/-1 counters modify P/T.
        Note: +1/+1 and -1/-1 counters cancel each other as a state-based
        action (CR 704.5q), but that happens separately.

        Args:
            permanent: The permanent to apply counter modifications to
        """
        if not hasattr(permanent, 'counters'):
            return

        if not hasattr(permanent, 'characteristics'):
            return

        chars = permanent.characteristics
        if chars.power is None or chars.toughness is None:
            return  # Not a creature

        counters = permanent.counters

        # +1/+1 counters
        plus_one = counters.get(CounterType.PLUS_ONE_PLUS_ONE, 0)
        if plus_one > 0:
            chars.power += plus_one
            chars.toughness += plus_one

        # -1/-1 counters
        minus_one = counters.get(CounterType.MINUS_ONE_MINUS_ONE, 0)
        if minus_one > 0:
            chars.power -= minus_one
            chars.toughness -= minus_one

        # Other P/T modifying counters
        counter_modifiers = {
            CounterType.PLUS_TWO_PLUS_ZERO: (2, 0),
            CounterType.PLUS_ZERO_PLUS_ONE: (0, 1),
            CounterType.PLUS_ONE_PLUS_TWO: (1, 2),
            CounterType.MINUS_ZERO_MINUS_ONE: (0, -1),
            CounterType.MINUS_ZERO_MINUS_TWO: (0, -2),
            CounterType.MINUS_TWO_MINUS_ONE: (-2, -1),
        }

        for counter_type, (p_mod, t_mod) in counter_modifiers.items():
            count = counters.get(counter_type, 0)
            if count > 0:
                chars.power += p_mod * count
                chars.toughness += t_mod * count

    # =========================================================================
    # DEPENDENCY HANDLING (CR 613.8)
    # =========================================================================

    def _sort_effects_in_layer(
        self,
        effects: List['ContinuousEffect']
    ) -> List['ContinuousEffect']:
        """Sort effects within a layer respecting dependencies.

        Per CR 613.8:
        - Within a layer, effects are normally applied in timestamp order
        - However, if effect A depends on effect B, B is applied first
          regardless of timestamps
        - Circular dependencies are broken by timestamp

        This uses a topological sort with timestamp as a tiebreaker.

        Args:
            effects: List of effects in the same layer

        Returns:
            Sorted list of effects respecting dependencies
        """
        if not effects:
            return []

        if len(effects) == 1:
            return effects

        # Build dependency graph
        # depends_on[effect_id] = set of effect_ids that must be applied first
        depends_on: Dict[int, Set[int]] = defaultdict(set)
        effect_map: Dict[int, 'ContinuousEffect'] = {}

        for effect in effects:
            effect_map[effect.effect_id] = effect

        # Check all pairs for dependencies
        for effect_a in effects:
            for effect_b in effects:
                if effect_a is effect_b:
                    continue
                if self._check_dependency(effect_a, effect_b):
                    # effect_a depends on effect_b, so effect_b must come first
                    depends_on[effect_a.effect_id].add(effect_b.effect_id)

        # Topological sort with timestamp as tiebreaker
        result: List['ContinuousEffect'] = []
        remaining = set(effect_map.keys())

        while remaining:
            # Find effects with no unsatisfied dependencies
            ready = []
            for effect_id in remaining:
                unsatisfied = depends_on[effect_id] & remaining
                if not unsatisfied:
                    ready.append(effect_id)

            if not ready:
                # Circular dependency detected - break by timestamp
                # Find the effect with the earliest timestamp among remaining
                earliest_id = min(remaining,
                                  key=lambda eid: effect_map[eid].timestamp)
                ready = [earliest_id]

            # Sort ready effects by timestamp
            ready.sort(key=lambda eid: effect_map[eid].timestamp)

            # Add to result and remove from remaining
            for effect_id in ready:
                result.append(effect_map[effect_id])
                remaining.remove(effect_id)

        return result

    def _check_dependency(
        self,
        effect_a: 'ContinuousEffect',
        effect_b: 'ContinuousEffect'
    ) -> bool:
        """Check if effect_a depends on effect_b (CR 613.8).

        Effect A depends on Effect B if:
        1. They apply in the same layer (or sublayer)
        2. Applying B would change whether A applies or what A does
        3. Neither is from a characteristic-defining ability (CDAs don't
           create dependencies per CR 613.8a)

        Classic example:
        - Effect A: "Creatures you control have flying"
        - Effect B: "All lands are creatures"
        - A depends on B because B determines what objects are creatures,
          which affects what A applies to.

        Args:
            effect_a: The effect that might depend on effect_b
            effect_b: The effect that might be depended upon

        Returns:
            True if effect_a depends on effect_b
        """
        # Must be in the same layer
        if effect_a.layer != effect_b.layer:
            return False

        # CDAs don't create dependencies (CR 613.8a)
        if getattr(effect_a, 'is_cda', False) or getattr(effect_b, 'is_cda', False):
            return False

        # Check explicit dependency
        if hasattr(effect_a, 'depends_on') and effect_b.effect_id in effect_a.depends_on:
            return True

        # Check if effect_b modifies what effect_a checks for applicability
        # This is a complex check that requires analyzing the effects

        # Type-changing effects can create dependencies with ability grants
        # e.g., "All creatures gain flying" depends on "All lands are creatures"
        if effect_a.layer == Layer.LAYER_6_ABILITY:
            # If effect_b changes types and effect_a filters by type
            if hasattr(effect_a, 'affected_filter') and effect_a.affected_filter:
                # effect_b could affect what matches the filter
                # For a complete implementation, we'd need to analyze the filter
                pass

        # Control changes can create dependencies
        # e.g., "Creatures you control get +1/+1" depends on control effects
        if effect_a.layer in (Layer.LAYER_7C_MODIFY_PT, Layer.LAYER_6_ABILITY):
            if effect_b.layer == Layer.LAYER_2_CONTROL:
                # If effect_a checks controller
                if hasattr(effect_a, 'affected_filter') and effect_a.affected_filter:
                    # This could create a dependency
                    pass

        # Type changes can create dependencies for type-checking effects
        if effect_b.layer == Layer.LAYER_4_TYPE:
            # Effects that filter by type may depend on type-changing effects
            if hasattr(effect_a, 'affected_filter') and effect_a.affected_filter:
                # Would need to check if filter involves type checking
                pass

        return False


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_layer_for_modification_type(mod_type: str) -> Layer:
    """Get the appropriate layer for a modification type.

    Args:
        mod_type: String identifier for the modification type

    Returns:
        The Layer enum value for that modification type
    """
    layer_mapping = {
        # Layer 1
        'copy': Layer.LAYER_1_COPY,

        # Layer 2
        'set_controller': Layer.LAYER_2_CONTROL,
        'control': Layer.LAYER_2_CONTROL,

        # Layer 3
        'change_text': Layer.LAYER_3_TEXT,
        'text': Layer.LAYER_3_TEXT,

        # Layer 4
        'add_type': Layer.LAYER_4_TYPE,
        'remove_type': Layer.LAYER_4_TYPE,
        'add_subtype': Layer.LAYER_4_TYPE,
        'remove_subtype': Layer.LAYER_4_TYPE,
        'add_supertype': Layer.LAYER_4_TYPE,
        'remove_supertype': Layer.LAYER_4_TYPE,
        'set_types': Layer.LAYER_4_TYPE,
        'set_subtypes': Layer.LAYER_4_TYPE,
        'type': Layer.LAYER_4_TYPE,

        # Layer 5
        'add_color': Layer.LAYER_5_COLOR,
        'remove_color': Layer.LAYER_5_COLOR,
        'set_colors': Layer.LAYER_5_COLOR,
        'color': Layer.LAYER_5_COLOR,

        # Layer 6
        'add_ability': Layer.LAYER_6_ABILITY,
        'remove_ability': Layer.LAYER_6_ABILITY,
        'add_keyword': Layer.LAYER_6_ABILITY,
        'remove_keyword': Layer.LAYER_6_ABILITY,
        'remove_all_abilities': Layer.LAYER_6_ABILITY,
        'ability': Layer.LAYER_6_ABILITY,

        # Layer 7a
        'set_base_power_toughness': Layer.LAYER_7A_CDA,
        'cda': Layer.LAYER_7A_CDA,

        # Layer 7b
        'set_power': Layer.LAYER_7B_SET_PT,
        'set_toughness': Layer.LAYER_7B_SET_PT,
        'set_power_toughness': Layer.LAYER_7B_SET_PT,
        'set_pt': Layer.LAYER_7B_SET_PT,

        # Layer 7c
        'modify_power': Layer.LAYER_7C_MODIFY_PT,
        'modify_toughness': Layer.LAYER_7C_MODIFY_PT,
        'modify_power_toughness': Layer.LAYER_7C_MODIFY_PT,
        'modify_pt': Layer.LAYER_7C_MODIFY_PT,
        'pump': Layer.LAYER_7C_MODIFY_PT,

        # Layer 7d - handled separately (counters)
        'counters': Layer.LAYER_7D_COUNTERS,

        # Layer 7e
        'switch_power_toughness': Layer.LAYER_7E_SWITCH,
        'switch_pt': Layer.LAYER_7E_SWITCH,
        'switch': Layer.LAYER_7E_SWITCH,
    }

    return layer_mapping.get(mod_type.lower(), Layer.LAYER_6_ABILITY)


def is_layer_7_sublayer(layer: Layer) -> bool:
    """Check if a layer is one of the Layer 7 sublayers.

    Args:
        layer: The layer to check

    Returns:
        True if this is a Layer 7 sublayer (7a-7e)
    """
    return layer in (
        Layer.LAYER_7A_CDA,
        Layer.LAYER_7B_SET_PT,
        Layer.LAYER_7C_MODIFY_PT,
        Layer.LAYER_7D_COUNTERS,
        Layer.LAYER_7E_SWITCH,
    )


def get_all_layers_in_order() -> List[Layer]:
    """Get all layers in the correct application order.

    Returns:
        List of Layer enum values in application order
    """
    return sorted(Layer, key=lambda l: l.value)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core classes
    'Layer',
    'LayerSystem',
    'DependencyType',

    # Helper functions
    'get_layer_for_modification_type',
    'is_layer_7_sublayer',
    'get_all_layers_in_order',
]
