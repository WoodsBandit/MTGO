"""MTG Engine V3 - Card Template Factory (PERF-7)

This module implements a CardTemplate factory pattern that shares immutable card data
across all instances of the same card. This eliminates the need for deep copying
entire card objects for each game, dramatically reducing memory usage and improving
performance in tournament simulations.

Key concepts:
- CardTemplate: Immutable shared data (name, types, base P/T, keywords, abilities)
- CardInstance: Lightweight per-game instance with mutable state (counters, damage, etc.)

Performance impact:
- Before: deep copy of ~100 cards per game = O(n * card_size) per game
- After: share templates, create lightweight instances = O(n * instance_size) per game
- Memory reduction: ~80-90% for card data in multi-game tournaments
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, ClassVar, TYPE_CHECKING
from weakref import WeakValueDictionary
import copy

from .types import Color, CardType, Supertype, Zone, ObjectId

if TYPE_CHECKING:
    from .objects import Card, Permanent


# =============================================================================
# IMMUTABLE CARD TEMPLATE
# =============================================================================

@dataclass(frozen=True)
class CardTemplate:
    """
    Immutable card template containing all static card data.

    This class is frozen (immutable) and can be safely shared across
    all games without copying. All mutable game state belongs in
    CardInstance or Permanent objects.

    Attributes:
        name: Card name (unique identifier for template lookup)
        mana_cost: Mana cost string (e.g., "{2}{U}{U}")
        cmc: Converted mana cost / mana value
        types: Frozenset of card types
        subtypes: Frozenset of subtypes
        supertypes: Frozenset of supertypes
        colors: Frozenset of colors
        base_power: Base power for creatures (None for non-creatures)
        base_toughness: Base toughness for creatures
        base_loyalty: Base loyalty for planeswalkers
        rules_text: Oracle text
        keywords: Frozenset of keyword abilities
        abilities: Tuple of ability definitions (immutable)
    """
    name: str
    mana_cost: Optional[str] = None
    cmc: int = 0
    types: frozenset = field(default_factory=frozenset)
    subtypes: frozenset = field(default_factory=frozenset)
    supertypes: frozenset = field(default_factory=frozenset)
    colors: frozenset = field(default_factory=frozenset)
    base_power: Optional[int] = None
    base_toughness: Optional[int] = None
    base_loyalty: Optional[int] = None
    rules_text: str = ""
    keywords: frozenset = field(default_factory=frozenset)
    abilities: tuple = field(default_factory=tuple)

    # Template metadata
    db_keywords: tuple = field(default_factory=tuple)
    db_abilities: tuple = field(default_factory=tuple)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, CardTemplate):
            return False
        return self.name == other.name

    # Type checking convenience methods
    def is_creature(self) -> bool:
        return CardType.CREATURE in self.types

    def is_land(self) -> bool:
        return CardType.LAND in self.types

    def is_instant(self) -> bool:
        return CardType.INSTANT in self.types

    def is_sorcery(self) -> bool:
        return CardType.SORCERY in self.types

    def is_artifact(self) -> bool:
        return CardType.ARTIFACT in self.types

    def is_enchantment(self) -> bool:
        return CardType.ENCHANTMENT in self.types

    def is_planeswalker(self) -> bool:
        return CardType.PLANESWALKER in self.types

    def is_legendary(self) -> bool:
        return Supertype.LEGENDARY in self.supertypes

    def is_basic(self) -> bool:
        return Supertype.BASIC in self.supertypes

    def has_keyword(self, keyword: str) -> bool:
        return keyword.lower() in self.keywords


# =============================================================================
# CARD TEMPLATE REGISTRY (SINGLETON)
# =============================================================================

class CardTemplateRegistry:
    """
    Singleton registry for CardTemplate instances.

    Ensures each unique card name has exactly one CardTemplate instance
    shared across all games. Uses a dictionary for O(1) lookup.

    Thread-safety: This implementation is not thread-safe. For multi-threaded
    tournament runners, consider adding locking or using a thread-local registry.
    """

    _instance: ClassVar[Optional['CardTemplateRegistry']] = None

    def __new__(cls) -> 'CardTemplateRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._templates: Dict[str, CardTemplate] = {}
        self._hit_count: int = 0
        self._miss_count: int = 0
        self._initialized = True

    def get_or_create(
        self,
        name: str,
        mana_cost: Optional[str] = None,
        cmc: int = 0,
        types: Optional[Set[CardType]] = None,
        subtypes: Optional[Set[str]] = None,
        supertypes: Optional[Set[Supertype]] = None,
        colors: Optional[Set[Color]] = None,
        base_power: Optional[int] = None,
        base_toughness: Optional[int] = None,
        base_loyalty: Optional[int] = None,
        rules_text: str = "",
        keywords: Optional[Set[str]] = None,
        abilities: Optional[List[Any]] = None,
        db_keywords: Optional[List[str]] = None,
        db_abilities: Optional[List[str]] = None,
    ) -> CardTemplate:
        """
        Get existing template or create new one.

        If a template for this card name already exists, return it.
        Otherwise, create a new template and cache it.

        Args:
            name: Card name (used as key)
            ... other args: Card properties for new template creation

        Returns:
            CardTemplate instance (shared if previously created)
        """
        # Fast path: template already exists
        if name in self._templates:
            self._hit_count += 1
            return self._templates[name]

        # Slow path: create new template
        self._miss_count += 1

        template = CardTemplate(
            name=name,
            mana_cost=mana_cost,
            cmc=cmc,
            types=frozenset(types) if types else frozenset(),
            subtypes=frozenset(subtypes) if subtypes else frozenset(),
            supertypes=frozenset(supertypes) if supertypes else frozenset(),
            colors=frozenset(colors) if colors else frozenset(),
            base_power=base_power,
            base_toughness=base_toughness,
            base_loyalty=base_loyalty,
            rules_text=rules_text,
            keywords=frozenset(kw.lower() for kw in keywords) if keywords else frozenset(),
            abilities=tuple(abilities) if abilities else tuple(),
            db_keywords=tuple(db_keywords) if db_keywords else tuple(),
            db_abilities=tuple(db_abilities) if db_abilities else tuple(),
        )

        self._templates[name] = template
        return template

    def get(self, name: str) -> Optional[CardTemplate]:
        """Get template by name, or None if not found."""
        return self._templates.get(name)

    def has(self, name: str) -> bool:
        """Check if template exists."""
        return name in self._templates

    def clear(self):
        """Clear all cached templates (for testing)."""
        self._templates.clear()
        self._hit_count = 0
        self._miss_count = 0

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total * 100) if total > 0 else 0
        return {
            "templates_cached": len(self._templates),
            "cache_hits": self._hit_count,
            "cache_misses": self._miss_count,
            "hit_rate_percent": hit_rate,
        }

    def __len__(self) -> int:
        return len(self._templates)

    def __contains__(self, name: str) -> bool:
        return name in self._templates


# =============================================================================
# CARD INSTANCE (LIGHTWEIGHT PER-GAME OBJECT)
# =============================================================================

@dataclass
class CardInstance:
    """
    Lightweight per-game card instance.

    References an immutable CardTemplate for static data and maintains
    only game-specific mutable state. This dramatically reduces memory
    usage compared to deep copying entire card objects.

    Attributes:
        template: Reference to shared immutable CardTemplate
        object_id: Unique ID for this instance in the game
        owner_id: Player ID who owns this card
        controller_id: Player ID who controls this card
        zone: Current zone location

        # Mutable state
        is_tapped: Whether the permanent is tapped
        counters: Counter dict (for permanents)
        damage_marked: Damage on creatures
        summoning_sick: Summoning sickness flag
        attached_to_id: ID of what this is attached to (auras/equipment)
    """
    template: CardTemplate
    object_id: int = 0
    owner_id: int = 0
    controller_id: int = 0
    zone: Zone = Zone.LIBRARY

    # Mutable permanent state (only used when on battlefield)
    is_tapped: bool = False
    counters: Dict[str, int] = field(default_factory=dict)
    damage_marked: int = 0
    summoning_sick: bool = True
    attached_to_id: Optional[int] = None
    timestamp: int = 0

    # Characteristic modifications (for continuous effects)
    power_mod: int = 0
    toughness_mod: int = 0
    added_keywords: Set[str] = field(default_factory=set)
    removed_keywords: Set[str] = field(default_factory=set)
    added_types: Set[CardType] = field(default_factory=set)
    removed_types: Set[CardType] = field(default_factory=set)

    # Convenience properties that delegate to template
    @property
    def name(self) -> str:
        return self.template.name

    @property
    def mana_cost(self) -> Optional[str]:
        return self.template.mana_cost

    @property
    def cmc(self) -> int:
        return self.template.cmc

    @property
    def colors(self) -> frozenset:
        return self.template.colors

    @property
    def rules_text(self) -> str:
        return self.template.rules_text

    # Computed properties
    @property
    def types(self) -> Set[CardType]:
        """Get current types (base + added - removed)."""
        current = set(self.template.types)
        current.update(self.added_types)
        current -= self.removed_types
        return current

    @property
    def subtypes(self) -> frozenset:
        return self.template.subtypes

    @property
    def supertypes(self) -> frozenset:
        return self.template.supertypes

    @property
    def power(self) -> Optional[int]:
        """Get current power (base + counters + mods)."""
        if self.template.base_power is None:
            return None
        base = self.template.base_power
        base += self.counters.get("+1/+1", 0)
        base -= self.counters.get("-1/-1", 0)
        base += self.power_mod
        return base

    @property
    def toughness(self) -> Optional[int]:
        """Get current toughness (base + counters + mods)."""
        if self.template.base_toughness is None:
            return None
        base = self.template.base_toughness
        base += self.counters.get("+1/+1", 0)
        base -= self.counters.get("-1/-1", 0)
        base += self.toughness_mod
        return base

    @property
    def loyalty(self) -> Optional[int]:
        """Get current loyalty (base + counters)."""
        if self.template.base_loyalty is None:
            return None
        return self.template.base_loyalty + self.counters.get("loyalty", 0)

    def has_keyword(self, keyword: str) -> bool:
        """Check if instance has keyword (base + added - removed)."""
        kw_lower = keyword.lower()
        if kw_lower in self.removed_keywords:
            return False
        if kw_lower in self.added_keywords:
            return True
        return self.template.has_keyword(kw_lower)

    # Type checking methods
    def is_creature(self) -> bool:
        return CardType.CREATURE in self.types

    def is_land(self) -> bool:
        return CardType.LAND in self.types

    def is_instant(self) -> bool:
        return CardType.INSTANT in self.types

    def is_sorcery(self) -> bool:
        return CardType.SORCERY in self.types

    def is_artifact(self) -> bool:
        return CardType.ARTIFACT in self.types

    def is_enchantment(self) -> bool:
        return CardType.ENCHANTMENT in self.types

    def is_planeswalker(self) -> bool:
        return CardType.PLANESWALKER in self.types

    # Combat readiness
    def has_summoning_sickness(self) -> bool:
        if not self.is_creature():
            return False
        if self.has_keyword("haste"):
            return False
        return self.summoning_sick

    def can_attack(self) -> bool:
        return (
            self.is_creature() and
            not self.is_tapped and
            not self.has_summoning_sickness() and
            not self.has_keyword("defender")
        )

    def can_block(self) -> bool:
        return self.is_creature() and not self.is_tapped

    # State management
    def reset_combat_state(self):
        """Reset combat-related state at end of combat."""
        pass  # CardInstance doesn't track attacking/blocking directly

    def clear_damage(self):
        """Clear marked damage (end of turn)."""
        self.damage_marked = 0

    def on_new_turn(self, is_controller_turn: bool):
        """Called at start of each turn."""
        if is_controller_turn:
            self.summoning_sick = False

    def create_copy(self, new_object_id: int) -> 'CardInstance':
        """
        Create a shallow copy with new object ID.

        The template reference is shared (by design), only mutable
        state is copied. This is much faster than deep copying.
        """
        return CardInstance(
            template=self.template,  # Shared reference
            object_id=new_object_id,
            owner_id=self.owner_id,
            controller_id=self.owner_id,  # Reset to owner
            zone=Zone.LIBRARY,  # Reset to library
            # Reset mutable state
            is_tapped=False,
            counters={},
            damage_marked=0,
            summoning_sick=True,
            attached_to_id=None,
            timestamp=0,
            power_mod=0,
            toughness_mod=0,
            added_keywords=set(),
            removed_keywords=set(),
            added_types=set(),
            removed_types=set(),
        )


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_registry = CardTemplateRegistry()


def get_template_registry() -> CardTemplateRegistry:
    """Get the global template registry."""
    return _registry


def create_card_instance_from_template(
    template: CardTemplate,
    object_id: int = 0,
    owner_id: int = 0,
) -> CardInstance:
    """Create a lightweight CardInstance from a template."""
    return CardInstance(
        template=template,
        object_id=object_id,
        owner_id=owner_id,
        controller_id=owner_id,
        zone=Zone.LIBRARY,
    )


def create_template_from_card_data(
    name: str,
    types: Set[CardType],
    mana_cost: Optional[str] = None,
    cmc: int = 0,
    subtypes: Optional[Set[str]] = None,
    supertypes: Optional[Set[Supertype]] = None,
    colors: Optional[Set[Color]] = None,
    power: Optional[int] = None,
    toughness: Optional[int] = None,
    loyalty: Optional[int] = None,
    rules_text: str = "",
    keywords: Optional[List[str]] = None,
    abilities: Optional[List[str]] = None,
    db_keywords: Optional[List[str]] = None,
    db_abilities: Optional[List[str]] = None,
) -> CardTemplate:
    """
    Create or get a CardTemplate from card data.

    Uses the global registry to ensure templates are shared.
    """
    return _registry.get_or_create(
        name=name,
        mana_cost=mana_cost,
        cmc=cmc,
        types=types,
        subtypes=subtypes or set(),
        supertypes=supertypes or set(),
        colors=colors or set(),
        base_power=power,
        base_toughness=toughness,
        base_loyalty=loyalty,
        rules_text=rules_text,
        keywords=set(keywords) if keywords else set(),
        abilities=abilities or [],
        db_keywords=db_keywords or [],
        db_abilities=db_abilities or [],
    )


def get_registry_stats() -> Dict[str, Any]:
    """Get template registry statistics."""
    return _registry.stats


def clear_template_cache():
    """Clear the template cache (for testing)."""
    _registry.clear()


# =============================================================================
# ADAPTER: CONVERT CARD TO CARDINSTANCE AND BACK
# =============================================================================

def card_to_instance(card: 'Card', object_id: int = 0) -> CardInstance:
    """
    Convert a Card object to a CardInstance with shared template.

    This is an adapter for gradual migration - existing code can
    continue using Card objects while new code uses CardInstance.
    """
    from .objects import Card, Characteristics

    chars = card.characteristics if hasattr(card, 'characteristics') else card.base_characteristics

    # Get or create template
    template = _registry.get_or_create(
        name=chars.name,
        mana_cost=str(chars.mana_cost) if chars.mana_cost else None,
        cmc=chars.mana_cost.cmc if hasattr(chars.mana_cost, 'cmc') else 0,
        types=chars.types if chars.types else set(),
        subtypes=chars.subtypes if chars.subtypes else set(),
        supertypes=chars.supertypes if chars.supertypes else set(),
        colors=chars.colors if chars.colors else set(),
        base_power=chars.power,
        base_toughness=chars.toughness,
        base_loyalty=chars.loyalty,
        rules_text=chars.rules_text if hasattr(chars, 'rules_text') else "",
        keywords=getattr(card, '_db_keywords', []),
        abilities=[],
        db_keywords=getattr(card, '_db_keywords', []),
        db_abilities=getattr(card, '_db_abilities', []),
    )

    return CardInstance(
        template=template,
        object_id=object_id or getattr(card, 'object_id', 0),
        owner_id=card.owner_id if hasattr(card, 'owner_id') else 0,
        controller_id=card.controller_id if hasattr(card, 'controller_id') else 0,
        zone=card.zone if hasattr(card, 'zone') else Zone.LIBRARY,
    )


def create_deck_instances(cards: List['Card'], owner_id: int = 0) -> List[CardInstance]:
    """
    Convert a list of Card objects to CardInstances with shared templates.

    This is the primary entry point for PERF-7 optimization.
    Instead of deep-copying an entire deck, we create lightweight
    instances that share templates.

    Args:
        cards: List of Card objects (can be the same deck used multiple times)
        owner_id: Player ID who owns these cards

    Returns:
        List of CardInstance objects with shared templates
    """
    instances = []
    next_id = 1

    for card in cards:
        instance = card_to_instance(card, object_id=next_id)
        instance.owner_id = owner_id
        instance.controller_id = owner_id
        instances.append(instance)
        next_id += 1

    return instances


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CardTemplate',
    'CardTemplateRegistry',
    'CardInstance',
    'get_template_registry',
    'create_card_instance_from_template',
    'create_template_from_card_data',
    'get_registry_stats',
    'clear_template_cache',
    'card_to_instance',
    'create_deck_instances',
]
