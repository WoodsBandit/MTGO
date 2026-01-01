"""MTG Engine V3 - Zone System

This module implements the complete MTG zone system according to the
Comprehensive Rules (section 400). All zone management, zone changes,
and zone-specific behaviors are handled here.

Zones in MTG:
- Library: Hidden, ordered (owned by each player)
- Hand: Hidden, unordered (owned by each player)
- Battlefield: Public, shared, unordered
- Graveyard: Public, ordered (owned by each player)
- Stack: Public, shared, ordered (LIFO)
- Exile: Public, shared, unordered
- Command: Public, shared, unordered
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Iterator, Callable, Tuple, Any, Set, TYPE_CHECKING
from enum import Enum, auto
import random

from .types import Zone, PlayerId, ObjectId, CardType, Supertype, Color

if TYPE_CHECKING:
    from .events import EventBus, GameEvent
    from .player import Player
    from .objects import GameObject, Card, Permanent, Token, Spell, StackedAbility


# =============================================================================
# ZONE CHANGE TRACKING
# =============================================================================

@dataclass
class ZoneChangeInfo:
    """Information about a zone change for tracking and triggers"""
    object_id: ObjectId
    from_zone: Zone
    to_zone: Zone
    from_owner: Optional[PlayerId] = None
    to_owner: Optional[PlayerId] = None
    was_token: bool = False
    was_visible: bool = False
    timestamp: int = 0

    @property
    def entered_battlefield(self) -> bool:
        return self.to_zone == Zone.BATTLEFIELD

    @property
    def left_battlefield(self) -> bool:
        return self.from_zone == Zone.BATTLEFIELD

    @property
    def died(self) -> bool:
        """Creature went from battlefield to graveyard"""
        return self.from_zone == Zone.BATTLEFIELD and self.to_zone == Zone.GRAVEYARD

    @property
    def was_countered(self) -> bool:
        """Spell was countered (stack to graveyard without resolving)"""
        return self.from_zone == Zone.STACK and self.to_zone == Zone.GRAVEYARD

    @property
    def was_exiled(self) -> bool:
        return self.to_zone == Zone.EXILE

    @property
    def was_bounced(self) -> bool:
        """Returned to hand from battlefield"""
        return self.from_zone == Zone.BATTLEFIELD and self.to_zone == Zone.HAND

    @property
    def was_milled(self) -> bool:
        """Went from library to graveyard"""
        return self.from_zone == Zone.LIBRARY and self.to_zone == Zone.GRAVEYARD

    @property
    def was_discarded(self) -> bool:
        """Went from hand to graveyard"""
        return self.from_zone == Zone.HAND and self.to_zone == Zone.GRAVEYARD


# =============================================================================
# BASE ZONE CLASS
# =============================================================================

@dataclass
class ZoneObject:
    """Base container for zone management

    All zones inherit from this class and can override specific behaviors.
    """
    zone_type: Zone
    owner_id: Optional[PlayerId] = None  # None for shared zones (battlefield, stack, exile, command)
    is_public: bool = False  # Whether contents are visible to all players
    is_ordered: bool = False  # Whether order matters (library, graveyard, stack)
    objects: List['GameObject'] = field(default_factory=list)

    # Track object IDs for fast lookup
    _id_cache: Set[ObjectId] = field(default_factory=set)

    def __post_init__(self):
        """Initialize the ID cache"""
        self._id_cache = {obj.object_id for obj in self.objects}

    def add(self, obj: 'GameObject', position: Optional[int] = None) -> None:
        """Add object to zone

        Args:
            obj: The game object to add
            position: For ordered zones, where to insert (None = end/top)
        """
        obj.zone = self.zone_type
        if position is not None and self.is_ordered:
            self.objects.insert(position, obj)
        else:
            self.objects.append(obj)
        self._id_cache.add(obj.object_id)

    def remove(self, obj: 'GameObject') -> bool:
        """Remove object from zone

        Returns:
            True if object was found and removed
        """
        try:
            self.objects.remove(obj)
            self._id_cache.discard(obj.object_id)
            return True
        except ValueError:
            return False

    def remove_by_id(self, object_id: ObjectId) -> Optional['GameObject']:
        """Remove object by ID

        Returns:
            The removed object, or None if not found
        """
        for obj in self.objects:
            if obj.object_id == object_id:
                self.objects.remove(obj)
                self._id_cache.discard(object_id)
                return obj
        return None

    def get_by_id(self, object_id: ObjectId) -> Optional['GameObject']:
        """Get object by ID without removing

        Returns:
            The object, or None if not found
        """
        if object_id not in self._id_cache:
            return None
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None

    def contains(self, obj: 'GameObject') -> bool:
        """Check if zone contains object"""
        return obj.object_id in self._id_cache

    def contains_id(self, object_id: ObjectId) -> bool:
        """Check if zone contains object by ID"""
        return object_id in self._id_cache

    def clear(self) -> List['GameObject']:
        """Remove and return all objects"""
        removed = self.objects.copy()
        self.objects.clear()
        self._id_cache.clear()
        return removed

    def __len__(self) -> int:
        return len(self.objects)

    def __iter__(self) -> Iterator['GameObject']:
        return iter(self.objects)

    def __bool__(self) -> bool:
        return len(self.objects) > 0

    def __contains__(self, obj: 'GameObject') -> bool:
        return self.contains(obj)

    def filter(self, predicate: Callable[['GameObject'], bool]) -> List['GameObject']:
        """Filter objects by predicate

        Args:
            predicate: Function that returns True for objects to include

        Returns:
            List of matching objects
        """
        return [o for o in self.objects if predicate(o)]

    def find_first(self, predicate: Callable[['GameObject'], bool]) -> Optional['GameObject']:
        """Find first object matching predicate

        Returns:
            First matching object, or None
        """
        for o in self.objects:
            if predicate(o):
                return o
        return None

    def count(self, predicate: Callable[['GameObject'], bool]) -> int:
        """Count objects matching predicate"""
        return sum(1 for o in self.objects if predicate(o))

    def top(self) -> Optional['GameObject']:
        """Get top of zone (for ordered zones like library/stack)

        For library: top card is last in list (what you draw)
        For stack: top is last in list (what resolves next)
        """
        return self.objects[-1] if self.objects else None

    def bottom(self) -> Optional['GameObject']:
        """Get bottom of zone

        For library: bottom card is first in list
        """
        return self.objects[0] if self.objects else None

    def pop_top(self) -> Optional['GameObject']:
        """Remove and return top object"""
        if self.objects:
            obj = self.objects.pop()
            self._id_cache.discard(obj.object_id)
            return obj
        return None

    def pop_bottom(self) -> Optional['GameObject']:
        """Remove and return bottom object"""
        if self.objects:
            obj = self.objects.pop(0)
            self._id_cache.discard(obj.object_id)
            return obj
        return None

    def shuffle(self) -> None:
        """Shuffle zone (primarily for library)"""
        random.shuffle(self.objects)

    def get_all(self) -> List['GameObject']:
        """Get all objects (copy of list)"""
        return self.objects.copy()

    def get_ids(self) -> Set[ObjectId]:
        """Get all object IDs"""
        return self._id_cache.copy()


# =============================================================================
# LIBRARY ZONE
# =============================================================================

class Library(ZoneObject):
    """Player's library (deck)

    The library is hidden and ordered. The "top" of the library is the last
    element in the list (what gets drawn). The "bottom" is the first element.

    Rule 401: Library rules
    """

    def __init__(self, owner_id: PlayerId):
        super().__init__(
            zone_type=Zone.LIBRARY,
            owner_id=owner_id,
            is_public=False,
            is_ordered=True
        )
        self._shuffle_pending = False

    def draw(self) -> Optional['Card']:
        """Draw top card (remove from library)

        Returns:
            The drawn card, or None if library is empty

        Note: Drawing from an empty library is handled by state-based actions
        """
        if self.objects:
            card = self.objects.pop()
            self._id_cache.discard(card.object_id)
            return card
        return None

    def draw_multiple(self, n: int) -> List['Card']:
        """Draw multiple cards

        Returns:
            List of drawn cards (may be fewer than n if library runs out)
        """
        cards = []
        for _ in range(n):
            card = self.draw()
            if card is None:
                break
            cards.append(card)
        return cards

    def peek(self, n: int = 1) -> List['Card']:
        """Look at top N cards without removing

        Returns cards in order from top to deeper (first element is top card)
        """
        if not self.objects:
            return []
        # Get last n elements, reversed so top is first
        return list(reversed(self.objects[-n:]))

    def peek_bottom(self, n: int = 1) -> List['Card']:
        """Look at bottom N cards without removing"""
        return self.objects[:n].copy()

    def put_on_top(self, cards: List['Card']) -> None:
        """Put cards on top in given order (first card will be on top)"""
        for card in reversed(cards):
            card.zone = Zone.LIBRARY
            self.objects.append(card)
            self._id_cache.add(card.object_id)

    def put_on_bottom(self, cards: List['Card'], random_order: bool = False) -> None:
        """Put cards on bottom

        Args:
            cards: Cards to put on bottom
            random_order: If True, put in random order (for some effects)
        """
        if random_order:
            cards = cards.copy()
            random.shuffle(cards)
        for card in cards:
            card.zone = Zone.LIBRARY
            self.objects.insert(0, card)
            self._id_cache.add(card.object_id)

    def put_nth_from_top(self, card: 'Card', position: int) -> None:
        """Put card at specific position from top (0 = top)"""
        card.zone = Zone.LIBRARY
        insert_pos = len(self.objects) - position
        if insert_pos < 0:
            insert_pos = 0
        self.objects.insert(insert_pos, card)
        self._id_cache.add(card.object_id)

    def search(self, predicate: Callable[['Card'], bool]) -> List['Card']:
        """Search library for cards matching predicate

        This represents the player searching their library.
        The library will typically need to be shuffled after a search.

        Returns:
            List of matching cards (still in library)
        """
        self._shuffle_pending = True
        return [c for c in self.objects if predicate(c)]

    def search_and_remove(self, predicate: Callable[['Card'], bool], max_count: int = 1) -> List['Card']:
        """Search library and remove matching cards

        Args:
            predicate: Function to match cards
            max_count: Maximum number of cards to remove

        Returns:
            List of removed cards
        """
        self._shuffle_pending = True
        found = []
        for card in list(self.objects):
            if len(found) >= max_count:
                break
            if predicate(card):
                self.objects.remove(card)
                self._id_cache.discard(card.object_id)
                found.append(card)
        return found

    def reveal_top(self, n: int = 1) -> List['Card']:
        """Reveal top N cards (same as peek, but marks as revealed for tracking)"""
        return self.peek(n)

    def mill(self, n: int) -> List['Card']:
        """Mill top N cards (remove from library, typically go to graveyard)

        Returns the milled cards for placement in graveyard
        """
        milled = []
        for _ in range(n):
            card = self.draw()
            if card is None:
                break
            milled.append(card)
        return milled

    def is_empty(self) -> bool:
        """Check if library is empty"""
        return len(self.objects) == 0

    def needs_shuffle(self) -> bool:
        """Check if library was searched and needs shuffling"""
        return self._shuffle_pending

    def shuffle(self) -> None:
        """Shuffle the library"""
        random.shuffle(self.objects)
        self._shuffle_pending = False

    def cards_remaining(self) -> int:
        """Get number of cards remaining"""
        return len(self.objects)


# =============================================================================
# HAND ZONE
# =============================================================================

class Hand(ZoneObject):
    """Player's hand

    The hand is hidden (from opponents) and unordered.

    Rule 402: Hand rules
    """

    def __init__(self, owner_id: PlayerId):
        super().__init__(
            zone_type=Zone.HAND,
            owner_id=owner_id,
            is_public=False,
            is_ordered=False
        )
        self.revealed_cards: Set[ObjectId] = set()  # Cards revealed to opponents
        self.max_hand_size: int = 7  # Can be modified by effects

    def get_by_name(self, name: str) -> Optional['Card']:
        """Get first card with given name"""
        for card in self.objects:
            if card.characteristics.name == name:
                return card
        return None

    def get_all_by_name(self, name: str) -> List['Card']:
        """Get all cards with given name"""
        return [c for c in self.objects if c.characteristics.name == name]

    def playable_lands(self) -> List['Card']:
        """Get lands that can potentially be played (type check only)"""
        return [c for c in self.objects if c.characteristics.is_land()]

    def castable_spells(self, available_mana: int) -> List['Card']:
        """Get spells that can potentially be cast with available mana

        Note: This is a simplified check. Full casting legality requires
        checking timing restrictions, additional costs, etc.
        """
        return [c for c in self.objects
                if not c.characteristics.is_land()
                and c.characteristics.mana_cost
                and c.characteristics.mana_cost.cmc <= available_mana]

    def by_type(self, card_type: CardType) -> List['Card']:
        """Get cards of a specific type"""
        return [c for c in self.objects if card_type in c.characteristics.types]

    def by_color(self, color: Color) -> List['Card']:
        """Get cards of a specific color"""
        return [c for c in self.objects if color in c.characteristics.colors]

    def colorless_cards(self) -> List['Card']:
        """Get colorless cards"""
        return [c for c in self.objects if not c.characteristics.colors]

    def reveal(self, card: 'Card') -> None:
        """Mark a card as revealed to opponents"""
        if card.object_id in self._id_cache:
            self.revealed_cards.add(card.object_id)

    def reveal_all(self) -> None:
        """Reveal entire hand"""
        self.revealed_cards = self._id_cache.copy()

    def hide(self, card: 'Card') -> None:
        """Hide a previously revealed card"""
        self.revealed_cards.discard(card.object_id)

    def hide_all(self) -> None:
        """Hide all revealed cards"""
        self.revealed_cards.clear()

    def is_revealed(self, card: 'Card') -> bool:
        """Check if card is revealed"""
        return card.object_id in self.revealed_cards

    def discard(self, card: 'Card') -> Optional['Card']:
        """Discard a card (remove from hand)

        Returns the discarded card for placement in graveyard
        """
        if self.remove(card):
            self.revealed_cards.discard(card.object_id)
            return card
        return None

    def discard_random(self) -> Optional['Card']:
        """Discard a random card"""
        if self.objects:
            card = random.choice(self.objects)
            return self.discard(card)
        return None

    def discard_to_hand_size(self) -> List['Card']:
        """Discard down to maximum hand size

        Note: In actual game, player chooses which cards to discard.
        This returns excess cards for the game to handle.
        """
        excess = len(self.objects) - self.max_hand_size
        if excess <= 0:
            return []
        # Return excess count, game/AI will choose which to discard
        return []  # Placeholder - actual discard requires player choice

    def is_over_max(self) -> bool:
        """Check if hand exceeds maximum size"""
        return len(self.objects) > self.max_hand_size

    def cards_over_max(self) -> int:
        """Get number of cards over maximum hand size"""
        return max(0, len(self.objects) - self.max_hand_size)


# =============================================================================
# GRAVEYARD ZONE
# =============================================================================

class Graveyard(ZoneObject):
    """Player's graveyard

    The graveyard is public and ordered (order matters for some effects).
    Newest cards are at the top (end of list).

    Rule 404: Graveyard rules
    """

    def __init__(self, owner_id: PlayerId):
        super().__init__(
            zone_type=Zone.GRAVEYARD,
            owner_id=owner_id,
            is_public=True,
            is_ordered=True
        )

    def creatures(self) -> List['Card']:
        """Get creature cards"""
        return [c for c in self.objects if c.characteristics.is_creature()]

    def instant_sorceries(self) -> List['Card']:
        """Get instant and sorcery cards"""
        return [c for c in self.objects
                if c.characteristics.is_instant() or c.characteristics.is_sorcery()]

    def instants(self) -> List['Card']:
        """Get instant cards"""
        return [c for c in self.objects if c.characteristics.is_instant()]

    def sorceries(self) -> List['Card']:
        """Get sorcery cards"""
        return [c for c in self.objects if c.characteristics.is_sorcery()]

    def lands(self) -> List['Card']:
        """Get land cards"""
        return [c for c in self.objects if c.characteristics.is_land()]

    def artifacts(self) -> List['Card']:
        """Get artifact cards"""
        return [c for c in self.objects if CardType.ARTIFACT in c.characteristics.types]

    def enchantments(self) -> List['Card']:
        """Get enchantment cards"""
        return [c for c in self.objects if CardType.ENCHANTMENT in c.characteristics.types]

    def planeswalkers(self) -> List['Card']:
        """Get planeswalker cards"""
        return [c for c in self.objects if CardType.PLANESWALKER in c.characteristics.types]

    def by_type(self, card_type: CardType) -> List['Card']:
        """Get cards of a specific type"""
        return [c for c in self.objects if card_type in c.characteristics.types]

    def by_cmc(self, cmc: int) -> List['Card']:
        """Get cards with specific mana value"""
        return [c for c in self.objects
                if c.characteristics.mana_cost and c.characteristics.mana_cost.cmc == cmc]

    def by_cmc_or_less(self, max_cmc: int) -> List['Card']:
        """Get cards with mana value at most max_cmc"""
        return [c for c in self.objects
                if c.characteristics.mana_cost and c.characteristics.mana_cost.cmc <= max_cmc]

    def card_types_count(self) -> Dict[str, int]:
        """Get count of each card type (for Delirium, Descend, etc.)"""
        type_counts: Dict[str, int] = {}
        for card in self.objects:
            for card_type in card.characteristics.types:
                type_name = card_type.name if hasattr(card_type, 'name') else str(card_type)
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
        return type_counts

    def unique_card_types(self) -> int:
        """Get number of unique card types (for Delirium check)"""
        types_seen = set()
        for card in self.objects:
            for card_type in card.characteristics.types:
                types_seen.add(card_type)
        return len(types_seen)

    def has_delirium(self) -> bool:
        """Check if graveyard has 4+ card types (Delirium)"""
        return self.unique_card_types() >= 4

    def most_recent(self, n: int = 1) -> List['Card']:
        """Get the N most recently added cards"""
        return list(reversed(self.objects[-n:]))

    def exile_all(self) -> List['Card']:
        """Remove all cards (for effects that exile a graveyard)"""
        return self.clear()


# =============================================================================
# BATTLEFIELD ZONE
# =============================================================================

class Battlefield(ZoneObject):
    """Shared battlefield zone

    The battlefield is public, shared between all players, and unordered.
    Only permanents exist on the battlefield.

    Rule 403: Battlefield rules
    """

    def __init__(self):
        super().__init__(
            zone_type=Zone.BATTLEFIELD,
            owner_id=None,
            is_public=True,
            is_ordered=False
        )

    def permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get all permanents, optionally filtered by controller

        Args:
            controller_id: If provided, only return permanents controlled by this player
        """
        from .objects import Permanent
        perms = [o for o in self.objects if isinstance(o, Permanent)]
        if controller_id is not None:
            perms = [p for p in perms if p.controller_id == controller_id]
        return perms

    def permanents_owned_by(self, owner_id: PlayerId) -> List['Permanent']:
        """Get permanents owned by a player (regardless of controller)"""
        from .objects import Permanent
        return [o for o in self.objects
                if isinstance(o, Permanent) and o.owner_id == owner_id]

    def creatures(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures"""
        return [p for p in self.permanents(controller_id) if p.characteristics.is_creature()]

    def noncreature_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get non-creature permanents"""
        return [p for p in self.permanents(controller_id) if not p.characteristics.is_creature()]

    def lands(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get lands"""
        return [p for p in self.permanents(controller_id) if p.characteristics.is_land()]

    def nonland_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get non-land permanents"""
        return [p for p in self.permanents(controller_id) if not p.characteristics.is_land()]

    def untapped_lands(self, controller_id: PlayerId) -> List['Permanent']:
        """Get untapped lands for a player"""
        return [p for p in self.lands(controller_id) if not p.is_tapped]

    def tapped_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get tapped permanents"""
        return [p for p in self.permanents(controller_id) if p.is_tapped]

    def untapped_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get untapped permanents"""
        return [p for p in self.permanents(controller_id) if not p.is_tapped]

    def available_attackers(self, controller_id: PlayerId) -> List['Permanent']:
        """Get creatures that can attack

        Basic check: untapped creatures without summoning sickness
        (or with haste), not affected by "can't attack" effects
        """
        attackers = []
        for p in self.creatures(controller_id):
            if p.can_attack():
                attackers.append(p)
        return attackers

    def available_blockers(self, controller_id: PlayerId) -> List['Permanent']:
        """Get creatures that can block

        Basic check: untapped creatures not affected by "can't block" effects
        """
        blockers = []
        for p in self.creatures(controller_id):
            if p.can_block():
                blockers.append(p)
        return blockers

    def planeswalkers(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get planeswalkers"""
        return [p for p in self.permanents(controller_id)
                if CardType.PLANESWALKER in p.characteristics.types]

    def artifacts(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get artifacts"""
        return [p for p in self.permanents(controller_id)
                if CardType.ARTIFACT in p.characteristics.types]

    def enchantments(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get enchantments"""
        return [p for p in self.permanents(controller_id)
                if CardType.ENCHANTMENT in p.characteristics.types]

    def auras(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get aura enchantments"""
        return [p for p in self.enchantments(controller_id)
                if "Aura" in (p.characteristics.subtypes or [])]

    def equipment(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get equipment artifacts"""
        return [p for p in self.artifacts(controller_id)
                if "Equipment" in (p.characteristics.subtypes or [])]

    def tokens(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get tokens"""
        from .objects import Token
        tokens = [o for o in self.objects if isinstance(o, Token)]
        if controller_id is not None:
            tokens = [t for t in tokens if t.controller_id == controller_id]
        return tokens

    def nontoken_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get non-token permanents"""
        from .objects import Token
        perms = [o for o in self.permanents(controller_id) if not isinstance(o, Token)]
        return perms

    def with_keyword(self, keyword: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents with a keyword ability"""
        return [p for p in self.permanents(controller_id) if p.has_keyword(keyword)]

    def without_keyword(self, keyword: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents without a keyword ability"""
        return [p for p in self.permanents(controller_id) if not p.has_keyword(keyword)]

    def legendaries(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get legendary permanents"""
        return [p for p in self.permanents(controller_id)
                if Supertype.LEGENDARY in p.characteristics.supertypes]

    def by_name(self, name: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents with a specific name"""
        return [p for p in self.permanents(controller_id)
                if p.characteristics.name == name]

    def by_subtype(self, subtype: str, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents with a specific subtype (creature type, land type, etc.)"""
        return [p for p in self.permanents(controller_id)
                if subtype in (p.characteristics.subtypes or [])]

    def by_color(self, color: Color, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents of a specific color"""
        return [p for p in self.permanents(controller_id)
                if color in p.characteristics.colors]

    def colorless_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get colorless permanents"""
        return [p for p in self.permanents(controller_id)
                if not p.characteristics.colors]

    def multicolored_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get multicolored permanents"""
        return [p for p in self.permanents(controller_id)
                if len(p.characteristics.colors) >= 2]

    def by_power(self, power: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures with specific power"""
        return [p for p in self.creatures(controller_id)
                if p.effective_power() == power]

    def by_power_or_less(self, max_power: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures with power at most max_power"""
        return [p for p in self.creatures(controller_id)
                if p.effective_power() <= max_power]

    def by_power_or_greater(self, min_power: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures with power at least min_power"""
        return [p for p in self.creatures(controller_id)
                if p.effective_power() >= min_power]

    def by_toughness(self, toughness: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures with specific toughness"""
        return [p for p in self.creatures(controller_id)
                if p.effective_toughness() == toughness]

    def by_cmc(self, cmc: int, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents with specific mana value"""
        return [p for p in self.permanents(controller_id)
                if p.characteristics.mana_cost and p.characteristics.mana_cost.cmc == cmc]

    def total_power(self, controller_id: PlayerId) -> int:
        """Get total power of creatures controlled by player"""
        return sum(c.effective_power() for c in self.creatures(controller_id))

    def total_toughness(self, controller_id: PlayerId) -> int:
        """Get total toughness of creatures controlled by player"""
        return sum(c.effective_toughness() for c in self.creatures(controller_id))

    def creature_count(self, controller_id: Optional[PlayerId] = None) -> int:
        """Get number of creatures"""
        return len(self.creatures(controller_id))

    def land_count(self, controller_id: Optional[PlayerId] = None) -> int:
        """Get number of lands"""
        return len(self.lands(controller_id))

    def permanent_count(self, controller_id: Optional[PlayerId] = None) -> int:
        """Get total number of permanents"""
        return len(self.permanents(controller_id))

    def attacking_creatures(self) -> List['Permanent']:
        """Get creatures that are currently attacking"""
        return [p for p in self.creatures() if getattr(p, 'is_attacking', False)]

    def blocking_creatures(self) -> List['Permanent']:
        """Get creatures that are currently blocking"""
        return [p for p in self.creatures() if getattr(p, 'is_blocking', False)]

    def enchanted_permanents(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get permanents that have auras attached"""
        return [p for p in self.permanents(controller_id)
                if hasattr(p, 'attached_auras') and p.attached_auras]

    def equipped_creatures(self, controller_id: Optional[PlayerId] = None) -> List['Permanent']:
        """Get creatures that have equipment attached"""
        return [p for p in self.creatures(controller_id)
                if hasattr(p, 'attached_equipment') and p.attached_equipment]


# =============================================================================
# STACK ZONE
# =============================================================================

class Stack(ZoneObject):
    """The stack zone

    The stack is public, shared, and ordered (LIFO - last in, first out).
    Spells and abilities go on the stack.

    Rule 405: Stack rules
    """

    def __init__(self):
        super().__init__(
            zone_type=Zone.STACK,
            owner_id=None,
            is_public=True,
            is_ordered=True
        )

    def is_empty(self) -> bool:
        """Check if stack is empty"""
        return len(self.objects) == 0

    def push(self, obj: 'GameObject') -> None:
        """Push onto stack (LIFO)"""
        obj.zone = Zone.STACK
        self.objects.append(obj)
        self._id_cache.add(obj.object_id)

    def pop(self) -> Optional['GameObject']:
        """Pop from stack (resolve top)"""
        if self.objects:
            obj = self.objects.pop()
            self._id_cache.discard(obj.object_id)
            return obj
        return None

    def peek(self) -> Optional['GameObject']:
        """Look at top of stack without removing"""
        return self.objects[-1] if self.objects else None

    def spells(self) -> List['Spell']:
        """Get spell objects on stack"""
        from .objects import Spell
        return [o for o in self.objects if isinstance(o, Spell)]

    def abilities(self) -> List['StackedAbility']:
        """Get ability objects on stack"""
        from .objects import StackedAbility
        return [o for o in self.objects if isinstance(o, StackedAbility)]

    def spells_controlled_by(self, controller_id: PlayerId) -> List['Spell']:
        """Get spells controlled by a player"""
        from .objects import Spell
        return [o for o in self.objects
                if isinstance(o, Spell) and o.controller_id == controller_id]

    def abilities_controlled_by(self, controller_id: PlayerId) -> List['StackedAbility']:
        """Get abilities controlled by a player"""
        from .objects import StackedAbility
        return [o for o in self.objects
                if isinstance(o, StackedAbility) and o.controller_id == controller_id]

    def objects_controlled_by(self, controller_id: PlayerId) -> List['GameObject']:
        """Get all stack objects controlled by a player"""
        return [o for o in self.objects if o.controller_id == controller_id]

    def counterable_spells(self) -> List['Spell']:
        """Get spells that can be countered (don't have 'can't be countered')"""
        from .objects import Spell
        return [o for o in self.spells() if not o.has_keyword("uncounterable")]

    def instant_speed_only(self) -> bool:
        """Check if only instant-speed actions are allowed (stack not empty)"""
        return not self.is_empty()

    def depth(self) -> int:
        """Get stack depth"""
        return len(self.objects)

    def get_nth(self, n: int) -> Optional['GameObject']:
        """Get nth object from top (0 = top)"""
        if n < len(self.objects):
            return self.objects[-(n + 1)]
        return None

    def remove_from_stack(self, obj: 'GameObject') -> bool:
        """Remove specific object from stack (for countering, etc.)"""
        return self.remove(obj)


# =============================================================================
# EXILE ZONE
# =============================================================================

class Exile(ZoneObject):
    """Exile zone

    Exile is public, shared, and unordered.
    Cards in exile are "outside the game" but tracked.

    Rule 406: Exile rules
    """

    def __init__(self):
        super().__init__(
            zone_type=Zone.EXILE,
            owner_id=None,
            is_public=True,
            is_ordered=False
        )
        # Track exile associations (for effects like Imprint, Adventure, etc.)
        self.exile_groups: Dict[str, Set[ObjectId]] = {}
        self.face_down: Set[ObjectId] = set()  # Face-down exiled cards

    def owned_by(self, player_id: PlayerId) -> List['GameObject']:
        """Get objects owned by player"""
        return [o for o in self.objects if o.owner_id == player_id]

    def add_to_group(self, obj: 'GameObject', group_name: str) -> None:
        """Add exiled object to a named group (for tracking)

        Used for effects like Imprint that care about specific exiled cards
        """
        if group_name not in self.exile_groups:
            self.exile_groups[group_name] = set()
        self.exile_groups[group_name].add(obj.object_id)

    def get_group(self, group_name: str) -> List['GameObject']:
        """Get objects in a named exile group"""
        if group_name not in self.exile_groups:
            return []
        group_ids = self.exile_groups[group_name]
        return [o for o in self.objects if o.object_id in group_ids]

    def remove_from_group(self, obj: 'GameObject', group_name: str) -> None:
        """Remove object from a named group"""
        if group_name in self.exile_groups:
            self.exile_groups[group_name].discard(obj.object_id)

    def clear_group(self, group_name: str) -> None:
        """Clear a named exile group"""
        if group_name in self.exile_groups:
            del self.exile_groups[group_name]

    def exile_face_down(self, obj: 'GameObject') -> None:
        """Exile object face-down"""
        self.add(obj)
        self.face_down.add(obj.object_id)

    def is_face_down(self, obj: 'GameObject') -> bool:
        """Check if exiled object is face-down"""
        return obj.object_id in self.face_down

    def turn_face_up(self, obj: 'GameObject') -> None:
        """Turn face-down exiled card face-up"""
        self.face_down.discard(obj.object_id)

    def remove(self, obj: 'GameObject') -> bool:
        """Remove object from exile, cleaning up tracking"""
        if super().remove(obj):
            self.face_down.discard(obj.object_id)
            # Clean up from all groups
            for group in self.exile_groups.values():
                group.discard(obj.object_id)
            return True
        return False

    def cards_with_adventure(self) -> List['Card']:
        """Get cards exiled with adventure (can be cast from exile)"""
        return self.get_group("adventure")

    def foretold_cards(self, owner_id: Optional[PlayerId] = None) -> List['Card']:
        """Get foretold cards"""
        cards = self.get_group("foretell")
        if owner_id is not None:
            cards = [c for c in cards if c.owner_id == owner_id]
        return cards


# =============================================================================
# COMMAND ZONE
# =============================================================================

class Command(ZoneObject):
    """Command zone

    The command zone is public, shared, and unordered.
    Used for commanders, emblems, conspiracies, and other special objects.

    Rule 408: Command zone rules
    """

    def __init__(self):
        super().__init__(
            zone_type=Zone.COMMAND,
            owner_id=None,
            is_public=True,
            is_ordered=False
        )

    def commanders(self, owner_id: Optional[PlayerId] = None) -> List['Card']:
        """Get commander cards"""
        commanders = [o for o in self.objects
                     if hasattr(o, 'is_commander') and o.is_commander]
        if owner_id is not None:
            commanders = [c for c in commanders if c.owner_id == owner_id]
        return commanders

    def emblems(self, controller_id: Optional[PlayerId] = None) -> List['GameObject']:
        """Get emblems"""
        emblems = [o for o in self.objects
                  if hasattr(o, 'is_emblem') and o.is_emblem]
        if controller_id is not None:
            emblems = [e for e in emblems if e.controller_id == controller_id]
        return emblems

    def planes(self) -> List['GameObject']:
        """Get plane cards (for Planechase)"""
        return [o for o in self.objects
               if CardType.PLANE in getattr(o, 'characteristics', object()).types]

    def schemes(self, owner_id: Optional[PlayerId] = None) -> List['GameObject']:
        """Get scheme cards (for Archenemy)"""
        schemes = [o for o in self.objects
                  if CardType.SCHEME in getattr(o, 'characteristics', object()).types]
        if owner_id is not None:
            schemes = [s for s in schemes if s.owner_id == owner_id]
        return schemes

    def add_emblem(self, emblem: 'GameObject') -> None:
        """Add an emblem to the command zone"""
        emblem.is_emblem = True
        self.add(emblem)

    def add_commander(self, commander: 'Card') -> None:
        """Add a commander to the command zone"""
        commander.is_commander = True
        self.add(commander)


# =============================================================================
# ZONE MANAGER
# =============================================================================

class ZoneManager:
    """Manages all zones in the game

    Provides unified interface for zone operations, zone changes,
    and cross-zone queries.
    """

    def __init__(self, player_ids: List[PlayerId]):
        """Initialize all zones for the game

        Args:
            player_ids: List of player IDs in the game
        """
        # Shared zones
        self.battlefield = Battlefield()
        self.stack = Stack()
        self.exile = Exile()
        self.command = Command()

        # Per-player zones
        self.libraries: Dict[PlayerId, Library] = {}
        self.hands: Dict[PlayerId, Hand] = {}
        self.graveyards: Dict[PlayerId, Graveyard] = {}

        for pid in player_ids:
            self.libraries[pid] = Library(pid)
            self.hands[pid] = Hand(pid)
            self.graveyards[pid] = Graveyard(pid)

        self._player_ids = player_ids
        self._next_timestamp = 0
        self._zone_change_history: List[ZoneChangeInfo] = []

    @property
    def player_ids(self) -> List[PlayerId]:
        """Get list of player IDs"""
        return self._player_ids.copy()

    def get_zone(self, zone_type: Zone, player_id: Optional[PlayerId] = None) -> ZoneObject:
        """Get a zone by type

        Args:
            zone_type: The type of zone to get
            player_id: Required for player-specific zones (library, hand, graveyard)

        Returns:
            The requested zone

        Raises:
            ValueError: If zone type is unknown or player_id is missing for player zones
        """
        if zone_type == Zone.BATTLEFIELD:
            return self.battlefield
        elif zone_type == Zone.STACK:
            return self.stack
        elif zone_type == Zone.EXILE:
            return self.exile
        elif zone_type == Zone.COMMAND:
            return self.command
        elif zone_type == Zone.LIBRARY:
            if player_id is None:
                raise ValueError("player_id required for library zone")
            if player_id not in self.libraries:
                raise ValueError(f"Unknown player_id: {player_id}")
            return self.libraries[player_id]
        elif zone_type == Zone.HAND:
            if player_id is None:
                raise ValueError("player_id required for hand zone")
            if player_id not in self.hands:
                raise ValueError(f"Unknown player_id: {player_id}")
            return self.hands[player_id]
        elif zone_type == Zone.GRAVEYARD:
            if player_id is None:
                raise ValueError("player_id required for graveyard zone")
            if player_id not in self.graveyards:
                raise ValueError(f"Unknown player_id: {player_id}")
            return self.graveyards[player_id]
        else:
            raise ValueError(f"Unknown zone type: {zone_type}")

    def all_zones(self) -> List[ZoneObject]:
        """Get all zones in the game"""
        zones = [self.battlefield, self.stack, self.exile, self.command]
        zones.extend(self.libraries.values())
        zones.extend(self.hands.values())
        zones.extend(self.graveyards.values())
        return zones

    def find_object(self, object_id: ObjectId) -> Optional[Tuple['GameObject', ZoneObject]]:
        """Find object across all zones

        Returns:
            Tuple of (object, zone) if found, None otherwise
        """
        # Check shared zones first (most common)
        for zone in [self.battlefield, self.stack, self.exile, self.command]:
            obj = zone.get_by_id(object_id)
            if obj:
                return (obj, zone)

        # Check player-specific zones
        for zones_dict in [self.libraries, self.hands, self.graveyards]:
            for zone in zones_dict.values():
                obj = zone.get_by_id(object_id)
                if obj:
                    return (obj, zone)

        return None

    def get_object_zone(self, object_id: ObjectId) -> Optional[Zone]:
        """Get the zone type an object is in

        Returns:
            Zone type if found, None otherwise
        """
        result = self.find_object(object_id)
        return result[1].zone_type if result else None

    def move_object(
        self,
        obj: 'GameObject',
        to_zone: Zone,
        to_player: Optional[PlayerId] = None,
        position: Optional[int] = None,
        events: Optional['EventBus'] = None
    ) -> Optional[ZoneChangeInfo]:
        """Move object between zones

        Args:
            obj: The game object to move
            to_zone: Destination zone type
            to_player: Destination player (for player-specific zones)
            position: Position in destination (for ordered zones)
            events: Event bus for emitting zone change events

        Returns:
            ZoneChangeInfo if move succeeded, None otherwise
        """
        # Find current zone
        result = self.find_object(obj.object_id)
        if not result:
            return None

        current_obj, from_zone_obj = result
        from_zone = from_zone_obj.zone_type

        # Determine destination player
        dest_player = to_player or obj.owner_id

        # Get destination zone
        try:
            dest_zone = self.get_zone(to_zone, dest_player)
        except ValueError:
            return None

        # Check for token leaving battlefield
        from .objects import Token
        was_token = isinstance(obj, Token)

        # Tokens cease to exist if they leave the battlefield
        if was_token and from_zone == Zone.BATTLEFIELD and to_zone != Zone.BATTLEFIELD:
            from_zone_obj.remove(obj)
            # Token ceases to exist - don't add to destination
            change_info = ZoneChangeInfo(
                object_id=obj.object_id,
                from_zone=from_zone,
                to_zone=to_zone,
                from_owner=from_zone_obj.owner_id,
                to_owner=dest_player,
                was_token=True,
                timestamp=self._next_timestamp
            )
            self._next_timestamp += 1
            self._zone_change_history.append(change_info)

            if events:
                self._emit_zone_change_events(change_info, obj, events)

            return change_info

        # Remove from source
        from_zone_obj.remove(obj)

        # Add to destination
        dest_zone.add(obj, position)

        # Update object's zone
        obj.zone = to_zone

        # Create change info
        change_info = ZoneChangeInfo(
            object_id=obj.object_id,
            from_zone=from_zone,
            to_zone=to_zone,
            from_owner=from_zone_obj.owner_id,
            to_owner=dest_zone.owner_id,
            was_token=was_token,
            was_visible=from_zone_obj.is_public,
            timestamp=self._next_timestamp
        )
        self._next_timestamp += 1
        self._zone_change_history.append(change_info)

        # Emit events
        if events:
            self._emit_zone_change_events(change_info, obj, events)

        return change_info

    def _emit_zone_change_events(
        self,
        change_info: ZoneChangeInfo,
        obj: 'GameObject',
        events: 'EventBus'
    ) -> None:
        """Emit appropriate events for a zone change"""
        # Import event types
        try:
            from .events import (
                ZoneChangeEvent, EntersBattlefieldEvent,
                LeavesBattlefieldEvent, DiesEvent, DrawEvent,
                DiscardEvent, MillEvent, ExileEvent
            )
        except ImportError:
            # Events module not yet created
            return

        # Emit general zone change event
        events.emit(ZoneChangeEvent(
            object_id=change_info.object_id,
            from_zone=change_info.from_zone,
            to_zone=change_info.to_zone
        ))

        # Emit specific events
        if change_info.entered_battlefield:
            events.emit(EntersBattlefieldEvent(
                object_id=change_info.object_id,
                from_zone=change_info.from_zone,
                to_zone=change_info.to_zone
            ))

        if change_info.left_battlefield:
            events.emit(LeavesBattlefieldEvent(
                object_id=change_info.object_id,
                to_zone=change_info.to_zone
            ))

            # Check for death (creature going to graveyard from battlefield)
            if change_info.died and hasattr(obj, 'characteristics'):
                if obj.characteristics.is_creature():
                    events.emit(DiesEvent(object_id=change_info.object_id))

        # Draw event
        if change_info.from_zone == Zone.LIBRARY and change_info.to_zone == Zone.HAND:
            events.emit(DrawEvent(
                object_id=change_info.object_id,
                player_id=change_info.to_owner
            ))

        # Discard event
        if change_info.was_discarded:
            events.emit(DiscardEvent(
                object_id=change_info.object_id,
                player_id=change_info.from_owner
            ))

        # Mill event
        if change_info.was_milled:
            events.emit(MillEvent(
                object_id=change_info.object_id,
                player_id=change_info.from_owner
            ))

        # Exile event
        if change_info.was_exiled:
            events.emit(ExileEvent(
                object_id=change_info.object_id,
                from_zone=change_info.from_zone
            ))

    def move_multiple(
        self,
        objects: List['GameObject'],
        to_zone: Zone,
        to_player: Optional[PlayerId] = None,
        events: Optional['EventBus'] = None
    ) -> List[ZoneChangeInfo]:
        """Move multiple objects to the same zone

        Returns:
            List of ZoneChangeInfo for successful moves
        """
        changes = []
        for obj in objects:
            change = self.move_object(obj, to_zone, to_player, events=events)
            if change:
                changes.append(change)
        return changes

    def get_zone_change_history(self, since_timestamp: int = 0) -> List[ZoneChangeInfo]:
        """Get zone change history since a timestamp"""
        return [c for c in self._zone_change_history if c.timestamp >= since_timestamp]

    def clear_zone_change_history(self) -> None:
        """Clear zone change history"""
        self._zone_change_history.clear()

    # ==========================================================================
    # CONVENIENCE METHODS FOR COMMON OPERATIONS
    # ==========================================================================

    def draw_card(
        self,
        player_id: PlayerId,
        events: Optional['EventBus'] = None
    ) -> Optional['Card']:
        """Draw a card for a player

        Returns:
            The drawn card, or None if library is empty
        """
        library = self.libraries[player_id]
        hand = self.hands[player_id]

        card = library.draw()
        if card:
            hand.add(card)
            card.zone = Zone.HAND

            if events:
                try:
                    from .events import DrawEvent
                    events.emit(DrawEvent(
                        object_id=card.object_id,
                        player_id=player_id
                    ))
                except ImportError:
                    pass

        return card

    def draw_cards(
        self,
        player_id: PlayerId,
        count: int,
        events: Optional['EventBus'] = None
    ) -> List['Card']:
        """Draw multiple cards for a player"""
        cards = []
        for _ in range(count):
            card = self.draw_card(player_id, events)
            if card is None:
                break
            cards.append(card)
        return cards

    def discard_card(
        self,
        player_id: PlayerId,
        card: 'Card',
        events: Optional['EventBus'] = None
    ) -> bool:
        """Discard a card from a player's hand to graveyard

        Returns:
            True if discard succeeded
        """
        hand = self.hands[player_id]
        graveyard = self.graveyards[player_id]

        if hand.remove(card):
            graveyard.add(card)
            card.zone = Zone.GRAVEYARD

            if events:
                try:
                    from .events import DiscardEvent
                    events.emit(DiscardEvent(
                        object_id=card.object_id,
                        player_id=player_id
                    ))
                except ImportError:
                    pass

            return True
        return False

    def mill_cards(
        self,
        player_id: PlayerId,
        count: int,
        events: Optional['EventBus'] = None
    ) -> List['Card']:
        """Mill cards from a player's library to graveyard"""
        library = self.libraries[player_id]
        graveyard = self.graveyards[player_id]

        milled = library.mill(count)
        for card in milled:
            graveyard.add(card)
            card.zone = Zone.GRAVEYARD

            if events:
                try:
                    from .events import MillEvent
                    events.emit(MillEvent(
                        object_id=card.object_id,
                        player_id=player_id
                    ))
                except ImportError:
                    pass

        return milled

    def shuffle_library(self, player_id: PlayerId) -> None:
        """Shuffle a player's library"""
        self.libraries[player_id].shuffle()

    def all_permanents(self) -> List['Permanent']:
        """Get all permanents on the battlefield"""
        return self.battlefield.permanents()

    def player_permanents(self, player_id: PlayerId) -> List['Permanent']:
        """Get all permanents controlled by a player"""
        return self.battlefield.permanents(player_id)

    def get_graveyard_count(self, player_id: PlayerId) -> int:
        """Get number of cards in a player's graveyard"""
        return len(self.graveyards[player_id])

    def get_library_count(self, player_id: PlayerId) -> int:
        """Get number of cards in a player's library"""
        return len(self.libraries[player_id])

    def get_hand_size(self, player_id: PlayerId) -> int:
        """Get number of cards in a player's hand"""
        return len(self.hands[player_id])

    def is_library_empty(self, player_id: PlayerId) -> bool:
        """Check if a player's library is empty"""
        return self.libraries[player_id].is_empty()

    def is_stack_empty(self) -> bool:
        """Check if the stack is empty"""
        return self.stack.is_empty()

    def stack_depth(self) -> int:
        """Get the current stack depth"""
        return self.stack.depth()

    def objects_on_battlefield(self, predicate: Callable[['Permanent'], bool]) -> List['Permanent']:
        """Get battlefield permanents matching a predicate"""
        return self.battlefield.filter(predicate)

    def count_on_battlefield(self, predicate: Callable[['Permanent'], bool]) -> int:
        """Count battlefield permanents matching a predicate"""
        return self.battlefield.count(predicate)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def is_public_zone(zone: Zone) -> bool:
    """Check if a zone type is public"""
    return zone in (Zone.BATTLEFIELD, Zone.STACK, Zone.GRAVEYARD, Zone.EXILE, Zone.COMMAND)


def is_hidden_zone(zone: Zone) -> bool:
    """Check if a zone type is hidden"""
    return zone in (Zone.LIBRARY, Zone.HAND)


def is_shared_zone(zone: Zone) -> bool:
    """Check if a zone type is shared between players"""
    return zone in (Zone.BATTLEFIELD, Zone.STACK, Zone.EXILE, Zone.COMMAND)


def is_player_zone(zone: Zone) -> bool:
    """Check if a zone type is player-specific"""
    return zone in (Zone.LIBRARY, Zone.HAND, Zone.GRAVEYARD)


def get_default_destination(zone: Zone, owner_id: PlayerId) -> Tuple[Zone, PlayerId]:
    """Get the default destination when leaving a zone

    Generally, objects go to their owner's appropriate zone.
    """
    if zone == Zone.BATTLEFIELD:
        return (Zone.GRAVEYARD, owner_id)
    elif zone == Zone.STACK:
        return (Zone.GRAVEYARD, owner_id)
    elif zone == Zone.HAND:
        return (Zone.GRAVEYARD, owner_id)
    else:
        return (Zone.GRAVEYARD, owner_id)
