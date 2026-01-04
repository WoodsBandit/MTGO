"""
MTG Layer System Implementation (Rule 613)
==========================================

This module implements the Layer System as defined in MTG Comprehensive Rules 613.
The layer system determines the order in which continuous effects are applied to
determine the characteristics of permanents.

Layers (Rule 613.1):
    1: Copy effects (Clone, Vesuvan Doppelganger)
    2: Control-changing effects (Control Magic, Bribery)
    3: Text-changing effects (Artificial Evolution, Mind Bend)
    4: Type-changing effects (Blood Moon, Urborg Tomb of Yawgmoth)
    5: Color-changing effects (Painter's Servant, Prismatic Lace)
    6: Ability adding/removing effects (Humility, Glorious Anthem)
    7: Power/Toughness effects with sublayers:
       7a: Characteristic-defining abilities (Tarmogoyf, */* creatures)
       7b: Set P/T to specific value (Awoken Horror 13/13, Ovinize 0/1)
       7c: Modifications from +1/+1 and -1/-1 counters
       7d: Effects that modify without setting (+2/+2 from equipment, anthems)
       7e: Effects that switch power and toughness

Example - Blood Moon + Urborg interaction:
    Both are Layer 4 effects. Blood Moon removes abilities from nonbasic lands
    (making them Mountains with just "T: Add R"). Since Urborg's ability is on
    a nonbasic land, Blood Moon removes it before it can apply, so nonbasic
    lands are just Mountains, not Swamp Mountains.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Union, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from mtg_engine import Card, Game


@dataclass
class ContinuousEffect:
    """
    Represents a continuous effect in MTG's layer system (Rule 613).

    Continuous effects modify characteristics of permanents and are applied
    in a specific order based on layers and sublayers.

    Attributes:
        source: The Card creating this effect
        layer: Which layer this effect applies in (1-7 or '7a'-'7e')
        modification: Function that takes (permanent, characteristics_dict) and returns modified dict
        applies_to: Function that takes a Card and returns True if effect applies to it
        timestamp: When this effect was created (for ordering within same layer)
        duration: How long the effect lasts ('permanent', 'end_of_turn', 'until_leaves', etc.)
        dependencies: List of effects this depends on (for dependency ordering per Rule 613.8)
        effect_id: Unique identifier for this effect
    """
    source: 'Card'
    layer: Union[int, str]  # 1-7 or '7a', '7b', '7c', '7d', '7e'
    modification: Callable[['Card', Dict[str, Any]], Dict[str, Any]]
    applies_to: Callable[['Card'], bool]
    timestamp: int = 0
    duration: str = 'permanent'
    dependencies: List['ContinuousEffect'] = field(default_factory=list)
    effect_id: int = 0

    def __hash__(self):
        return hash(self.effect_id)

    def __eq__(self, other):
        if isinstance(other, ContinuousEffect):
            return self.effect_id == other.effect_id
        return False


class LayerSystem:
    """
    Implements MTG's Layer System per Rule 613.

    The Layer System determines the order in which continuous effects are applied.
    Effects are sorted first by layer, then by timestamp within each layer,
    with special handling for dependencies (Rule 613.8).
    """

    # Layer ordering per Rule 613.1
    LAYER_ORDER = [1, 2, 3, 4, 5, 6, '7a', '7b', '7c', '7d', '7e']

    def __init__(self, game: 'Game'):
        self.game = game
        self.effects: List[ContinuousEffect] = []
        self.timestamp_counter = 0
        self.effect_id_counter = 0

    def add_effect(self, effect: ContinuousEffect) -> ContinuousEffect:
        """
        Add a continuous effect to the system.

        Assigns a timestamp for ordering purposes.
        """
        effect.timestamp = self.timestamp_counter
        self.timestamp_counter += 1
        effect.effect_id = self.effect_id_counter
        self.effect_id_counter += 1
        self.effects.append(effect)
        return effect

    def remove_effect(self, effect: ContinuousEffect) -> bool:
        """Remove a continuous effect from the system."""
        if effect in self.effects:
            self.effects.remove(effect)
            return True
        return False

    def remove_effects_from_source(self, source: 'Card') -> int:
        """
        Remove all effects created by a specific source card.
        Used when the source leaves the battlefield.

        Returns the number of effects removed.
        """
        to_remove = [e for e in self.effects if e.source.instance_id == source.instance_id]
        for effect in to_remove:
            self.effects.remove(effect)
        return len(to_remove)

    def remove_expired_effects(self) -> int:
        """
        Remove effects that have expired based on their duration.
        Called at end of turn for 'end_of_turn' effects.

        Returns the number of effects removed.
        """
        # Note: 'until_leaves' effects are handled by remove_effects_from_source
        to_remove = [e for e in self.effects if e.duration == 'end_of_turn']
        for effect in to_remove:
            self.effects.remove(effect)
        return len(to_remove)

    def get_effects_in_layer(self, layer: Union[int, str]) -> List[ContinuousEffect]:
        """Get all effects that apply in a specific layer, sorted by timestamp."""
        layer_effects = [e for e in self.effects if e.layer == layer]
        return self._sort_with_dependencies(layer_effects)

    def _sort_with_dependencies(self, effects: List[ContinuousEffect]) -> List[ContinuousEffect]:
        """
        Sort effects respecting dependencies (Rule 613.8).

        Rule 613.8: If an effect's application depends on characteristics
        that are modified by another effect in the same layer, the dependent
        effect is applied after the effect it depends on.

        Uses topological sorting to handle dependency chains.
        """
        if not effects:
            return []

        # Build dependency graph
        effect_set = set(effects)

        # Create adjacency list for topological sort
        # If A depends on B, then B must come before A
        dependencies_map: Dict[int, List[int]] = {e.effect_id: [] for e in effects}

        for effect in effects:
            for dep in effect.dependencies:
                if dep in effect_set:
                    dependencies_map[effect.effect_id].append(dep.effect_id)

        # Topological sort using Kahn's algorithm
        in_degree: Dict[int, int] = {e.effect_id: 0 for e in effects}
        for effect_id, deps in dependencies_map.items():
            in_degree[effect_id] = len(deps)

        # Build reverse map: effect_id -> effect
        id_to_effect = {e.effect_id: e for e in effects}

        # Build forward adjacency: if A depends on B, add A to B's "dependents"
        dependents_map: Dict[int, List[int]] = {e.effect_id: [] for e in effects}
        for effect_id, deps in dependencies_map.items():
            for dep_id in deps:
                if dep_id in dependents_map:
                    dependents_map[dep_id].append(effect_id)

        # Start with effects that have no dependencies
        queue = [e for e in effects if in_degree[e.effect_id] == 0]
        queue.sort(key=lambda e: e.timestamp)

        result = []
        while queue:
            current = queue.pop(0)
            result.append(current)

            for dependent_id in dependents_map[current.effect_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(id_to_effect[dependent_id])

            queue.sort(key=lambda e: e.timestamp)

        # If result doesn't contain all effects, there's a cycle
        if len(result) < len(effects):
            remaining = [e for e in effects if e not in result]
            remaining.sort(key=lambda e: e.timestamp)
            result.extend(remaining)

        return result

    def calculate_characteristics(self, permanent: 'Card') -> Dict[str, Any]:
        """
        Calculate the final characteristics of a permanent after applying
        all continuous effects in layer order.

        This is the core method that applies the layer system.

        Args:
            permanent: The card to calculate characteristics for

        Returns:
            Dictionary with calculated characteristics:
            - 'name': str
            - 'card_type': str
            - 'subtype': str
            - 'colors': List[str]
            - 'power': int
            - 'toughness': int
            - 'keywords': List[str]
            - 'abilities': List[str]
            - 'controller': int
            - 'produces': List[str] (for lands)
        """
        # Start with base characteristics from the card
        chars: Dict[str, Any] = {
            'name': permanent.name,
            'card_type': permanent.card_type,
            'subtype': permanent.subtype,
            'colors': permanent.mana_cost.colors() if permanent.mana_cost else [],
            'power': permanent.power,
            'toughness': permanent.toughness,
            'keywords': list(permanent.keywords),
            'abilities': list(permanent.abilities),
            'controller': permanent.controller,
            'produces': list(permanent.produces) if permanent.produces else [],
            'is_copy': False,
        }

        # Apply effects layer by layer
        for layer in self.LAYER_ORDER:
            layer_effects = self.get_effects_in_layer(layer)

            for effect in layer_effects:
                if effect.applies_to(permanent):
                    chars = effect.modification(permanent, chars)

        return chars

    def get_power_toughness(self, creature: 'Card', battlefield: List['Card'] = None) -> Tuple[int, int]:
        """
        Get the calculated power and toughness for a creature.

        Args:
            creature: The creature card
            battlefield: Optional battlefield for attachment lookup

        Returns:
            Tuple of (power, toughness)
        """
        chars = self.calculate_characteristics(creature)
        power = chars.get('power', creature.power)
        toughness = chars.get('toughness', creature.toughness)
        return power, toughness

    def get_keywords(self, permanent: 'Card') -> List[str]:
        """Get the calculated keywords for a permanent after layer 6 effects."""
        chars = self.calculate_characteristics(permanent)
        return chars.get('keywords', list(permanent.keywords))

    def get_abilities(self, permanent: 'Card') -> List[str]:
        """Get the calculated abilities for a permanent after all layer effects."""
        chars = self.calculate_characteristics(permanent)
        return chars.get('abilities', list(permanent.abilities))

    def is_affected_by_layer(self, permanent: 'Card', layer: Union[int, str]) -> bool:
        """Check if a permanent is affected by any effects in a specific layer."""
        layer_effects = self.get_effects_in_layer(layer)
        return any(effect.applies_to(permanent) for effect in layer_effects)

    # =========================================================================
    # FACTORY METHODS FOR COMMON EFFECTS
    # =========================================================================

    def create_blood_moon_effect(self, blood_moon: 'Card') -> ContinuousEffect:
        """
        Factory method to create the Blood Moon effect.

        Blood Moon (Layer 4): "Nonbasic lands are Mountains."
        """
        def applies_to_nonbasic_land(card: 'Card') -> bool:
            if card.card_type != 'land':
                return False
            basic_land_names = {'Forest', 'Plains', 'Island', 'Swamp', 'Mountain',
                               'Snow-Covered Forest', 'Snow-Covered Plains',
                               'Snow-Covered Island', 'Snow-Covered Swamp',
                               'Snow-Covered Mountain', 'Wastes'}
            return card.name not in basic_land_names

        def make_mountain(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            chars['subtype'] = 'Mountain'
            chars['abilities'] = []
            chars['produces'] = ['R']
            return chars

        return ContinuousEffect(
            source=blood_moon,
            layer=4,
            modification=make_mountain,
            applies_to=applies_to_nonbasic_land,
            duration='until_leaves'
        )

    def create_urborg_effect(self, urborg: 'Card') -> ContinuousEffect:
        """
        Factory method to create the Urborg, Tomb of Yawgmoth effect.

        Urborg (Layer 4): "Each land is a Swamp in addition to its other types."
        """
        def applies_to_all_lands(card: 'Card') -> bool:
            return card.card_type == 'land'

        def add_swamp_type(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            current_subtype = chars.get('subtype', '')
            if 'Swamp' not in current_subtype:
                if current_subtype:
                    chars['subtype'] = current_subtype + ' Swamp'
                else:
                    chars['subtype'] = 'Swamp'
            produces = chars.get('produces', [])
            if 'B' not in produces:
                produces = list(produces) + ['B']
                chars['produces'] = produces
            return chars

        return ContinuousEffect(
            source=urborg,
            layer=4,
            modification=add_swamp_type,
            applies_to=applies_to_all_lands,
            duration='until_leaves'
        )

    def create_anthem_effect(self, source: 'Card', power_bonus: int, toughness_bonus: int,
                             condition: Callable[['Card'], bool] = None) -> ContinuousEffect:
        """
        Factory method to create a creature anthem effect (like Glorious Anthem).

        Anthems apply in Layer 7d (effects that modify without setting).
        """
        def applies_to_creatures(card: 'Card') -> bool:
            if card.card_type != 'creature' and not card.is_creature_now():
                return False
            if condition:
                return condition(card)
            return True

        def apply_bonus(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            chars['power'] = chars.get('power', permanent.power) + power_bonus
            chars['toughness'] = chars.get('toughness', permanent.toughness) + toughness_bonus
            return chars

        return ContinuousEffect(
            source=source,
            layer='7d',
            modification=apply_bonus,
            applies_to=applies_to_creatures,
            duration='until_leaves'
        )

    def create_counter_effect(self, creature: 'Card') -> ContinuousEffect:
        """
        Factory method to create the effect for +1/+1 and -1/-1 counters.

        Counter effects apply in Layer 7c.
        """
        def applies_to_self(card: 'Card') -> bool:
            return card.instance_id == creature.instance_id

        def apply_counters(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            plus_counters = permanent.counters.get('+1/+1', 0)
            minus_counters = permanent.counters.get('-1/-1', 0)
            chars['power'] = chars.get('power', permanent.power) + plus_counters - minus_counters
            chars['toughness'] = chars.get('toughness', permanent.toughness) + plus_counters - minus_counters
            return chars

        return ContinuousEffect(
            source=creature,
            layer='7c',
            modification=apply_counters,
            applies_to=applies_to_self,
            duration='permanent'
        )

    def create_set_pt_effect(self, source: 'Card', target: 'Card',
                              new_power: int, new_toughness: int,
                              duration: str = 'end_of_turn') -> ContinuousEffect:
        """
        Factory method to create a "set power/toughness" effect (Layer 7b).

        Examples: Ovinize (0/1), Turn to Frog (1/1), Awoken Horror (13/13)
        """
        def applies_to_target(card: 'Card') -> bool:
            return card.instance_id == target.instance_id

        def set_pt(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            chars['power'] = new_power
            chars['toughness'] = new_toughness
            return chars

        return ContinuousEffect(
            source=source,
            layer='7b',
            modification=set_pt,
            applies_to=applies_to_target,
            duration=duration
        )

    def create_switch_pt_effect(self, source: 'Card', target: 'Card',
                                 duration: str = 'end_of_turn') -> ContinuousEffect:
        """
        Factory method to create a power/toughness switching effect (Layer 7e).

        Examples: Twisted Image, Inside Out
        """
        def applies_to_target(card: 'Card') -> bool:
            return card.instance_id == target.instance_id

        def switch_pt(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            current_power = chars.get('power', permanent.power)
            current_toughness = chars.get('toughness', permanent.toughness)
            chars['power'] = current_toughness
            chars['toughness'] = current_power
            return chars

        return ContinuousEffect(
            source=source,
            layer='7e',
            modification=switch_pt,
            applies_to=applies_to_target,
            duration=duration
        )

    def create_add_ability_effect(self, source: 'Card',
                                   keywords: List[str] = None,
                                   abilities: List[str] = None,
                                   condition: Callable[['Card'], bool] = None,
                                   duration: str = 'until_leaves') -> ContinuousEffect:
        """
        Factory method to create an ability-granting effect (Layer 6).

        Examples: Archetype of Courage (gives first strike), Equipment grants
        """
        keywords = keywords or []
        abilities = abilities or []

        def applies_to_permanents(card: 'Card') -> bool:
            if condition:
                return condition(card)
            return True

        def add_abilities(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            current_keywords = chars.get('keywords', list(permanent.keywords))
            current_abilities = chars.get('abilities', list(permanent.abilities))

            for kw in keywords:
                if kw.lower() not in [k.lower() for k in current_keywords]:
                    current_keywords.append(kw)

            for ability in abilities:
                if ability not in current_abilities:
                    current_abilities.append(ability)

            chars['keywords'] = current_keywords
            chars['abilities'] = current_abilities
            return chars

        return ContinuousEffect(
            source=source,
            layer=6,
            modification=add_abilities,
            applies_to=applies_to_permanents,
            duration=duration
        )

    def create_remove_ability_effect(self, source: 'Card',
                                      keywords: List[str] = None,
                                      remove_all: bool = False,
                                      condition: Callable[['Card'], bool] = None,
                                      duration: str = 'until_leaves') -> ContinuousEffect:
        """
        Factory method to create an ability-removing effect (Layer 6).

        Examples: Humility (removes all abilities), Sudden Spoiling
        """
        keywords = keywords or []

        def applies_to_permanents(card: 'Card') -> bool:
            if condition:
                return condition(card)
            return True

        def remove_abilities(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            if remove_all:
                chars['keywords'] = []
                chars['abilities'] = []
            else:
                current_keywords = chars.get('keywords', list(permanent.keywords))
                chars['keywords'] = [kw for kw in current_keywords
                                     if kw.lower() not in [k.lower() for k in keywords]]
            return chars

        return ContinuousEffect(
            source=source,
            layer=6,
            modification=remove_abilities,
            applies_to=applies_to_permanents,
            duration=duration
        )

    def create_color_change_effect(self, source: 'Card',
                                    new_colors: List[str] = None,
                                    add_colors: List[str] = None,
                                    condition: Callable[['Card'], bool] = None,
                                    duration: str = 'until_leaves') -> ContinuousEffect:
        """
        Factory method to create a color-changing effect (Layer 5).

        Examples: Painter's Servant (adds color), Prismatic Lace
        """
        def applies_to_permanents(card: 'Card') -> bool:
            if condition:
                return condition(card)
            return True

        def change_colors(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            if new_colors is not None:
                chars['colors'] = list(new_colors)
            elif add_colors is not None:
                current_colors = chars.get('colors', permanent.mana_cost.colors() if permanent.mana_cost else [])
                for color in add_colors:
                    if color not in current_colors:
                        current_colors.append(color)
                chars['colors'] = current_colors
            return chars

        return ContinuousEffect(
            source=source,
            layer=5,
            modification=change_colors,
            applies_to=applies_to_permanents,
            duration=duration
        )

    def create_control_change_effect(self, source: 'Card', target: 'Card',
                                      new_controller: int,
                                      duration: str = 'until_leaves') -> ContinuousEffect:
        """
        Factory method to create a control-changing effect (Layer 2).

        Examples: Control Magic, Act of Treason, Bribery
        """
        def applies_to_target(card: 'Card') -> bool:
            return card.instance_id == target.instance_id

        def change_control(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            chars['controller'] = new_controller
            return chars

        return ContinuousEffect(
            source=source,
            layer=2,
            modification=change_control,
            applies_to=applies_to_target,
            duration=duration
        )

    def create_type_change_effect(self, source: 'Card',
                                   new_types: str = None,
                                   add_types: str = None,
                                   condition: Callable[['Card'], bool] = None,
                                   duration: str = 'until_leaves') -> ContinuousEffect:
        """
        Factory method to create a type-changing effect (Layer 4).

        Examples: Blood Moon (makes lands Mountains), Enchanted Evening
        """
        def applies_to_permanents(card: 'Card') -> bool:
            if condition:
                return condition(card)
            return True

        def change_types(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            if new_types is not None:
                chars['subtype'] = new_types
            elif add_types is not None:
                current_subtype = chars.get('subtype', permanent.subtype)
                if current_subtype:
                    chars['subtype'] = current_subtype + ' ' + add_types
                else:
                    chars['subtype'] = add_types
            return chars

        return ContinuousEffect(
            source=source,
            layer=4,
            modification=change_types,
            applies_to=applies_to_permanents,
            duration=duration
        )

    def create_attachment_effect(self, attachment: 'Card', attached_to: 'Card',
                                  battlefield: List['Card']) -> ContinuousEffect:
        """
        Factory method to create an effect for an attached aura or equipment.

        This creates a Layer 7d effect for stat bonuses.
        """
        power_bonus = 0
        toughness_bonus = 0
        keywords_granted: List[str] = []

        for grant in attachment.grants:
            stat_match = re.match(r'([+-]?\d+)/([+-]?\d+)', grant)
            if stat_match:
                power_bonus += int(stat_match.group(1))
                toughness_bonus += int(stat_match.group(2))
            else:
                keywords_granted.append(grant.lower())

        def applies_to_attached(card: 'Card') -> bool:
            return card.instance_id == attached_to.instance_id

        def apply_attachment_bonus(permanent: 'Card', chars: Dict[str, Any]) -> Dict[str, Any]:
            chars['power'] = chars.get('power', permanent.power) + power_bonus
            chars['toughness'] = chars.get('toughness', permanent.toughness) + toughness_bonus
            return chars

        return ContinuousEffect(
            source=attachment,
            layer='7d',
            modification=apply_attachment_bonus,
            applies_to=applies_to_attached,
            duration='until_leaves'
        )
