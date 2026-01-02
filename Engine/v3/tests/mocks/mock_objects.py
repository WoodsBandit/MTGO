"""
Mock game objects for testing.

Provides lightweight mocks for cards, permanents, and creatures without
requiring full engine initialization.
"""

from typing import Set, Optional
from ...engine.objects import Characteristics, GameObject
from ...engine.types import Color, CardType, Supertype, Zone


class MockCard:
    """
    Lightweight mock card for testing.

    Simpler than full Card class, useful for isolated tests.

    Attributes:
        object_id: Unique object identifier
        name: Card name
        mana_cost: Mana cost string
        types: Set of card types
        colors: Set of colors
        characteristics: Card characteristics
        owner: Owning player
        controller: Controlling player
        zone: Current zone
    """

    def __init__(
        self,
        name: str = "Test Card",
        mana_cost: str = "{2}",
        types: Set[CardType] = None,
        colors: Set[Color] = None,
        power: Optional[int] = None,
        toughness: Optional[int] = None,
        rules_text: str = "",
        object_id: int = 1
    ):
        """
        Initialize mock card.

        Args:
            name: Card name
            mana_cost: Mana cost string like "{2}{U}"
            types: Set of CardType enums
            colors: Set of Color enums
            power: Power (for creatures)
            toughness: Toughness (for creatures)
            rules_text: Rules/oracle text
            object_id: Unique object ID
        """
        self.object_id = object_id
        self.name = name
        self.mana_cost = mana_cost
        self.types = types or set()
        self.colors = colors or set()

        # Create characteristics
        self.characteristics = Characteristics(
            name=name,
            mana_cost=mana_cost,
            colors=colors or set(),
            types=types or set(),
            power=power,
            toughness=toughness,
            rules_text=rules_text
        )

        # Zone information
        self.owner = None
        self.controller = None
        self.zone = Zone.HAND

    def is_creature(self) -> bool:
        """Check if this is a creature card."""
        return CardType.CREATURE in self.types

    def is_land(self) -> bool:
        """Check if this is a land card."""
        return CardType.LAND in self.types

    def is_instant(self) -> bool:
        """Check if this is an instant."""
        return CardType.INSTANT in self.types

    def is_sorcery(self) -> bool:
        """Check if this is a sorcery."""
        return CardType.SORCERY in self.types

    def __repr__(self) -> str:
        """Debug representation."""
        return f"MockCard({self.name!r}, types={self.types})"


class MockPermanent:
    """
    Lightweight mock permanent for testing.

    Represents a permanent on the battlefield with minimal state.

    Attributes:
        object_id: Unique identifier
        name: Permanent name
        types: Card types
        characteristics: Permanent characteristics
        owner: Owning player
        controller: Controlling player
        zone: Current zone (should be BATTLEFIELD)
        is_tapped: Whether permanent is tapped
        summoning_sick: Whether permanent has summoning sickness
        timestamp: Timestamp for layer ordering
    """

    def __init__(
        self,
        object_id: int,
        owner,
        controller,
        name: str = "Test Permanent",
        types: Set[CardType] = None,
        power: Optional[int] = None,
        toughness: Optional[int] = None,
        colors: Set[Color] = None
    ):
        """
        Initialize mock permanent.

        Args:
            object_id: Unique object ID
            owner: Owning player
            controller: Controlling player
            name: Permanent name
            types: Set of CardType enums
            power: Power (for creatures)
            toughness: Toughness (for creatures)
            colors: Set of colors
        """
        self.object_id = object_id
        self.name = name
        self.owner = owner
        self.controller = controller
        self.zone = Zone.BATTLEFIELD
        self.types = types or set()

        # Characteristics
        self.characteristics = Characteristics(
            name=name,
            types=types or set(),
            power=power,
            toughness=toughness,
            colors=colors or set()
        )

        # Permanent state
        self.is_tapped = False
        self.summoning_sick = False
        self.entered_battlefield_this_turn = False
        self.timestamp = 0

        # Damage tracking
        self.damage_marked = 0

    @property
    def owner_id(self) -> int:
        """Get owner's player ID."""
        if self.owner and hasattr(self.owner, 'player_id'):
            return self.owner.player_id
        return 0

    @property
    def controller_id(self) -> int:
        """Get controller's player ID."""
        if self.controller and hasattr(self.controller, 'player_id'):
            return self.controller.player_id
        return 0

    def tap(self) -> None:
        """Tap this permanent."""
        self.is_tapped = True

    def untap(self) -> None:
        """Untap this permanent."""
        self.is_tapped = False

    def is_creature(self) -> bool:
        """Check if this is a creature."""
        return CardType.CREATURE in self.types

    def is_land(self) -> bool:
        """Check if this is a land."""
        return CardType.LAND in self.types

    def is_artifact(self) -> bool:
        """Check if this is an artifact."""
        return CardType.ARTIFACT in self.types

    def __repr__(self) -> str:
        """Debug representation."""
        tapped_str = " (tapped)" if self.is_tapped else ""
        return f"MockPermanent({self.name!r}{tapped_str})"


class MockCreature(MockPermanent):
    """
    Lightweight mock creature for testing combat and creature interactions.

    Extends MockPermanent with creature-specific attributes.

    Attributes:
        power: Current power
        toughness: Current toughness
        base_power: Base power (before modifications)
        base_toughness: Base toughness (before modifications)
        keywords: Set of keyword abilities
        attacking: Whether creature is attacking
        blocking: List of attackers this creature blocks
        blocked_by: List of blockers blocking this creature
    """

    def __init__(
        self,
        object_id: int = 1,
        owner=None,
        controller=None,
        name: str = "Test Creature",
        mana_cost: str = "{2}",
        power: int = 2,
        toughness: int = 2,
        colors: Set[Color] = None,
        keywords: Set[str] = None
    ):
        """
        Initialize mock creature.

        Args:
            object_id: Unique object ID
            owner: Owning player
            controller: Controlling player
            name: Creature name
            mana_cost: Mana cost string
            power: Power value
            toughness: Toughness value
            colors: Set of colors
            keywords: Set of keyword abilities
        """
        super().__init__(
            object_id=object_id,
            owner=owner,
            controller=controller,
            name=name,
            types={CardType.CREATURE},
            power=power,
            toughness=toughness,
            colors=colors
        )

        self.mana_cost = mana_cost
        self.power = power
        self.toughness = toughness
        self.base_power = power
        self.base_toughness = toughness
        self.keywords = keywords or set()

        # Combat state
        self.attacking = False
        self.blocking: list = []
        self.blocked_by: list = []

        # Update characteristics with power/toughness
        self.characteristics.power = power
        self.characteristics.toughness = toughness
        self.characteristics.mana_cost = mana_cost

    def has_keyword(self, keyword: str) -> bool:
        """
        Check if creature has a specific keyword.

        Args:
            keyword: Keyword ability to check (case-insensitive)

        Returns:
            True if creature has the keyword
        """
        keyword_lower = keyword.lower()
        return any(k.lower() == keyword_lower for k in self.keywords)

    def add_keyword(self, keyword: str) -> None:
        """
        Add a keyword ability.

        Args:
            keyword: Keyword to add
        """
        self.keywords.add(keyword)

    def remove_keyword(self, keyword: str) -> None:
        """
        Remove a keyword ability.

        Args:
            keyword: Keyword to remove
        """
        self.keywords = {k for k in self.keywords if k.lower() != keyword.lower()}

    def deal_damage_to(self, target, amount: int) -> int:
        """
        Deal damage to another permanent or player.

        Args:
            target: Target permanent or player
            amount: Amount of damage to deal

        Returns:
            Amount of damage actually dealt
        """
        if hasattr(target, 'damage_marked'):
            # Target is a creature
            target.damage_marked += amount
        elif hasattr(target, 'life'):
            # Target is a player
            target.life -= amount

        return amount

    def take_damage(self, amount: int, source=None) -> int:
        """
        Take damage from a source.

        Args:
            amount: Amount of damage to take
            source: Source of damage

        Returns:
            Amount of damage taken
        """
        self.damage_marked += amount
        return amount

    def is_dead(self) -> bool:
        """
        Check if creature should die to state-based actions.

        Returns:
            True if damage marked >= toughness or toughness <= 0
        """
        return (self.damage_marked >= self.toughness or
                self.toughness <= 0)

    def reset_damage(self) -> None:
        """Reset damage marked to 0."""
        self.damage_marked = 0

    def pump(self, power_mod: int, toughness_mod: int) -> None:
        """
        Temporarily modify power/toughness.

        Args:
            power_mod: Power modification
            toughness_mod: Toughness modification
        """
        self.power += power_mod
        self.toughness += toughness_mod
        self.characteristics.power = self.power
        self.characteristics.toughness = self.toughness

    def reset_pt(self) -> None:
        """Reset power/toughness to base values."""
        self.power = self.base_power
        self.toughness = self.base_toughness
        self.characteristics.power = self.power
        self.characteristics.toughness = self.toughness

    def __repr__(self) -> str:
        """Debug representation."""
        tapped_str = " (tapped)" if self.is_tapped else ""
        attacking_str = " (attacking)" if self.attacking else ""
        return (f"MockCreature({self.name!r} {self.power}/{self.toughness}"
                f"{tapped_str}{attacking_str})")
