"""
MTG Universal Simulation Engine v3
===================================

Parses standard MTGO .txt decklists and simulates matches.
Now with colored mana, combat keywords, mulligans, and more!

USAGE:
------
from mtg_engine import run_match

# From .txt decklist strings:
results = run_match(deck1_txt, deck2_txt, matches=5)

# Or from file paths:
results = run_match_from_files("deck1.txt", "deck2.txt", matches=5)
"""

import random
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Set, Callable, Union
from card_database import get_card_data, CARD_DATABASE
from layer_system import ContinuousEffect, LayerSystem

ENGINE_VERSION = "3.0"

# Mana color constants
COLORS = ["W", "U", "B", "R", "G"]  # White, Blue, Black, Red, Green


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

@dataclass
class ManaCost:
    """Represents a mana cost like {2}{W}{W} or {3}{U}{B} or {X}{R}{R}"""
    generic: int = 0  # Generic/colorless requirement
    W: int = 0  # White pips
    U: int = 0  # Blue pips
    B: int = 0  # Black pips
    R: int = 0  # Red pips
    G: int = 0  # Green pips
    X: int = 0  # Number of X in the cost (e.g., "XX" = 2)

    def cmc(self) -> int:
        """Converted mana cost / mana value (X counts as 0 when not on stack)"""
        return self.generic + self.W + self.U + self.B + self.R + self.G

    def has_x(self) -> bool:
        """Check if this cost contains X"""
        return self.X > 0

    def colors(self) -> List[str]:
        """Return list of colors in this cost"""
        result = []
        if self.W > 0: result.append("W")
        if self.U > 0: result.append("U")
        if self.B > 0: result.append("B")
        if self.R > 0: result.append("R")
        if self.G > 0: result.append("G")
        return result

    def copy(self) -> 'ManaCost':
        return ManaCost(self.generic, self.W, self.U, self.B, self.R, self.G, self.X)

    def add(self, other: 'ManaCost'):
        """Add another ManaCost to this one (for kicker costs, etc.)"""
        self.generic += other.generic
        self.W += other.W
        self.U += other.U
        self.B += other.B
        self.R += other.R
        self.G += other.G
        self.X += other.X

    @staticmethod
    def parse(cost_str: str) -> 'ManaCost':
        """Parse a mana cost string like '2WW' or '3UB' or 'RRR' or 'XRR'"""
        if not cost_str:
            return ManaCost()
        cost = ManaCost()
        cost_str = str(cost_str).upper()
        # Count X's first (before parsing numbers)
        cost.X = cost_str.count('X')
        # Remove X's before parsing numbers to avoid confusion
        clean_str = cost_str.replace('X', '')
        numbers = re.findall(r'\d+', clean_str)
        if numbers:
            cost.generic = sum(int(n) for n in numbers)
        cost.W = cost_str.count('W')
        cost.U = cost_str.count('U')
        cost.B = cost_str.count('B')
        cost.R = cost_str.count('R')
        cost.G = cost_str.count('G')
        return cost


@dataclass
class ManaPool:
    """Represents available mana from lands"""
    W: int = 0
    U: int = 0
    B: int = 0
    R: int = 0
    G: int = 0
    C: int = 0  # Colorless

    def total(self) -> int:
        return self.W + self.U + self.B + self.R + self.G + self.C

    def can_pay(self, cost: ManaCost, x_value: int = 0) -> bool:
        """Check if this pool can pay the given cost (X spells require x_value >= 0)"""
        if self.W < cost.W: return False
        if self.U < cost.U: return False
        if self.B < cost.B: return False
        if self.R < cost.R: return False
        if self.G < cost.G: return False
        remaining = (self.W - cost.W + self.U - cost.U + self.B - cost.B +
                    self.R - cost.R + self.G - cost.G + self.C)
        # For X spells, need enough for generic + (X * x_value)
        x_cost = cost.X * x_value if cost.X > 0 else 0
        return remaining >= cost.generic + x_cost

    def max_x_value(self, cost: ManaCost) -> int:
        """Calculate maximum X value that can be paid with this pool"""
        if cost.X == 0:
            return 0
        # First check if we can pay colored requirements
        if self.W < cost.W or self.U < cost.U or self.B < cost.B:
            return 0
        if self.R < cost.R or self.G < cost.G:
            return 0
        # Remaining mana after colored pips
        remaining = (self.W - cost.W + self.U - cost.U + self.B - cost.B +
                    self.R - cost.R + self.G - cost.G + self.C)
        # Subtract generic cost first
        remaining -= cost.generic
        if remaining < 0:
            return 0
        # Divide by number of X's in cost
        return remaining // cost.X

    def copy(self) -> 'ManaPool':
        return ManaPool(self.W, self.U, self.B, self.R, self.G, self.C)

    def add(self, color: str, amount: int = 1):
        if hasattr(self, color):
            setattr(self, color, getattr(self, color) + amount)

    def clear(self):
        self.W = self.U = self.B = self.R = self.G = self.C = 0

    def pay_cost(self, cost: ManaCost) -> bool:
        """
        Actually deduct mana from the pool to pay a cost.
        Returns True if payment successful, False if insufficient mana.
        This modifies the pool in place.
        """
        if not self.can_pay(cost):
            return False

        # Deduct colored mana first
        self.W -= cost.W
        self.U -= cost.U
        self.B -= cost.B
        self.R -= cost.R
        self.G -= cost.G

        # Deduct generic from remaining (prefer colorless first, then excess colored)
        generic = cost.generic
        if generic > 0 and self.C > 0:
            deduct = min(self.C, generic)
            self.C -= deduct
            generic -= deduct

        # Then use excess colored mana for generic
        for color in ["W", "U", "B", "R", "G"]:
            if generic <= 0:
                break
            avail = getattr(self, color)
            deduct = min(avail, generic)
            setattr(self, color, avail - deduct)
            generic -= deduct

        return True


@dataclass
class Card:
    name: str
    mana_cost: ManaCost = field(default_factory=ManaCost)
    card_type: str = "creature"
    subtype: str = ""  # e.g., "aura", "equipment"
    power: int = 0
    toughness: int = 0
    keywords: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)
    loyalty: int = 0
    produces: List[str] = field(default_factory=list)  # Mana colors for lands
    loyalty_abilities: List[str] = field(default_factory=list)  # e.g., ["+1:draw_1", "-3:destroy_creature"]

    # Aura/Equipment fields
    grants: List[str] = field(default_factory=list)  # Bonuses: ["+2/+2", "flying", "trample"]
    equip_cost: str = ""  # Mana cost to equip (e.g., "2", "1W")
    return_to_hand: bool = False  # Rancor-like ability

    # Instance state
    instance_id: int = 0
    is_tapped: bool = False
    damage_marked: int = 0
    summoning_sick: bool = True
    counters: Dict[str, int] = field(default_factory=dict)
    controller: int = 0
    activated_this_turn: bool = False  # For planeswalker loyalty abilities (once per turn)
    is_token: bool = False  # True if this is a token (for SBA: tokens cease to exist outside battlefield)
    attached_to: Optional[int] = None  # instance_id of permanent this is attached to (for Auras/Equipment)
    deathtouch_damage: bool = False  # Tracks if creature has taken any deathtouch damage this turn
    phased_out: bool = False  # True if creature is phased out (treated as not existing)
    regenerate_shield: int = 0  # Number of regeneration shields available
    shield_counters: int = 0  # Shield counters (from D&D set) - remove instead of dying

    # Modal spells and kicker
    modes: List[str] = field(default_factory=list)  # Available modes: ["damage_3", "destroy_artifact", "counter_spell"]
    choose_two: bool = False  # If True, choose two modes instead of one
    kicker: str = ""  # Optional additional cost: "2R", "4", etc.
    multikicker: str = ""  # Can pay multiple times: "1G"
    if_kicked: List[str] = field(default_factory=list)  # Additional/replacement effects when kicked

    # Alternative casting costs
    flashback: str = ""  # e.g., "2R" - cast from graveyard for this cost, exile after
    escape: str = ""  # e.g., "3BB" - cast from graveyard for this cost
    escape_exile: int = 0  # Number of other cards to exile from graveyard as additional cost
    overload: str = ""  # e.g., "4UR" - cast for higher cost, affects all valid targets
    adventure: Optional[Dict[str, Any]] = None  # {"cost": "1G", "abilities": ["create_1_1_token"]}
    on_adventure: bool = False  # True if card is exiled face-up after casting adventure

    # Vehicle fields
    crew: int = 0  # Minimum total power needed to crew (0 = not a vehicle)
    is_crewed: bool = False  # True if vehicle is crewed this turn (acts as creature)

    # Saga fields
    chapters: List[str] = field(default_factory=list)  # Chapter abilities: ["effect1", "effect2", "effect3"]

    # Control tracking (Rule 108.4)
    owner: int = 0  # Player ID who started with the card (never changes)
    control_effects: List['ControlEffect'] = field(default_factory=list)  # Stack of control effects (Layer 2)

    # MDFC (Modal Double-Faced Card) fields
    is_mdfc: bool = False  # True if this card has two playable faces
    mdfc_back: Optional['Card'] = None  # Reference to back face (only set on front face)
    mdfc_front: Optional['Card'] = None  # Reference to front face (only set on back face)
    mdfc_played_as: str = ""  # "front" or "back" - which face is on battlefield
    mdfc_enters_tapped: bool = False  # For land backs that enter tapped

    def copy(self) -> 'Card':
        new_card = Card(
            name=self.name, mana_cost=self.mana_cost.copy(),
            card_type=self.card_type, subtype=self.subtype,
            power=self.power, toughness=self.toughness,
            keywords=self.keywords.copy(), abilities=self.abilities.copy(),
            loyalty=self.loyalty, produces=self.produces.copy(),
            loyalty_abilities=self.loyalty_abilities.copy(),
            grants=self.grants.copy(), equip_cost=self.equip_cost,
            return_to_hand=self.return_to_hand,
            instance_id=self.instance_id, is_tapped=self.is_tapped,
            damage_marked=self.damage_marked, summoning_sick=self.summoning_sick,
            counters=self.counters.copy(), controller=self.controller,
            activated_this_turn=self.activated_this_turn,
            is_token=self.is_token, attached_to=self.attached_to,
            deathtouch_damage=self.deathtouch_damage,
            phased_out=self.phased_out, regenerate_shield=self.regenerate_shield,
            shield_counters=self.shield_counters,
            modes=self.modes.copy(), choose_two=self.choose_two,
            kicker=self.kicker, multikicker=self.multikicker,
            if_kicked=self.if_kicked.copy(),
            flashback=self.flashback, escape=self.escape,
            escape_exile=self.escape_exile, overload=self.overload,
            adventure=self.adventure.copy() if self.adventure else None,
            on_adventure=self.on_adventure,
            crew=self.crew, is_crewed=self.is_crewed,
            chapters=self.chapters.copy(),
            owner=self.owner,
            control_effects=[],  # Control effects don't copy (each copy starts fresh)
            is_mdfc=self.is_mdfc, mdfc_played_as=self.mdfc_played_as,
            mdfc_enters_tapped=self.mdfc_enters_tapped
        )
        # Don't copy mdfc_back/mdfc_front references to avoid circular refs
        return new_card

    def current_loyalty(self) -> int:
        """Get current loyalty (base + counters)"""
        return self.counters.get("loyalty", self.loyalty)

    def cmc(self) -> int:
        return self.mana_cost.cmc()

    def is_aura(self) -> bool:
        """Check if this card is an aura enchantment"""
        return self.card_type == "enchantment" and self.subtype.lower() == "aura"

    def is_equipment(self) -> bool:
        """Check if this card is equipment"""
        return self.card_type == "artifact" and self.subtype.lower() == "equipment"

    def is_vehicle(self) -> bool:
        """Check if this card is a vehicle"""
        return self.card_type == "artifact" and self.subtype.lower() == "vehicle"

    def is_saga(self) -> bool:
        """Check if this card is a saga enchantment"""
        return self.card_type == "enchantment" and self.subtype.lower() == "saga"

    def current_chapter(self) -> int:
        """Get current saga chapter based on lore counters (0 if not a saga)"""
        if not self.is_saga():
            return 0
        return self.counters.get("lore", 0)

    def final_chapter(self) -> int:
        """Get the final chapter number for this saga"""
        return len(self.chapters)

    def is_creature_now(self) -> bool:
        """Check if this card is currently a creature (including crewed vehicles)"""
        if self.card_type == "creature":
            return True
        if self.is_vehicle() and self.is_crewed:
            return True
        return False

    def eff_power(self) -> int:
        """Get effective power including counters (attachments handled by engine)"""
        return self.power + self.counters.get("+1/+1", 0) - self.counters.get("-1/-1", 0)

    def eff_toughness(self) -> int:
        """Get effective toughness including counters (attachments handled by engine)"""
        return self.toughness + self.counters.get("+1/+1", 0) - self.counters.get("-1/-1", 0)

    def has_keyword(self, kw: str) -> bool:
        return kw.lower() in [k.lower() for k in self.keywords]


def apply_attached_bonuses(creature: Card, battlefield: List['Card']) -> Tuple[int, int, List[str]]:
    """
    Calculate total bonuses from all attached auras and equipment.

    Args:
        creature: The creature to check
        battlefield: The battlefield to find attachments on

    Returns:
        Tuple of (power_bonus, toughness_bonus, keywords_granted)
    """
    power_bonus = 0
    toughness_bonus = 0
    keywords_granted = []

    # Find all attachments (cards that have attached_to pointing to this creature)
    for card in battlefield:
        if card.attached_to == creature.instance_id:
            for grant in card.grants:
                # Parse stat bonuses like "+2/+2", "+2/+0", "+0/+3"
                stat_match = re.match(r'([+-]?\d+)/([+-]?\d+)', grant)
                if stat_match:
                    power_bonus += int(stat_match.group(1))
                    toughness_bonus += int(stat_match.group(2))
                else:
                    # It's a keyword
                    keywords_granted.append(grant.lower())

    return power_bonus, toughness_bonus, keywords_granted


def get_attachments(creature: Card, battlefield: List['Card']) -> List['Card']:
    """Get all auras and equipment attached to a creature."""
    return [c for c in battlefield if c.attached_to == creature.instance_id]


# =============================================================================
# COPY EFFECTS SYSTEM (MTG Rule 707)
# =============================================================================

# Global ID counter for copy effects (used when Game instance not available)
_copy_id_counter = 10000


def _generate_copy_id() -> int:
    """Generate a unique ID for copies when Game.next_id isn't available."""
    global _copy_id_counter
    _copy_id_counter += 1
    return _copy_id_counter


def create_copy(original: Card, modifications: List[Callable[[Card], None]] = None,
                instance_id: int = None) -> Card:
    """
    Rule 707: Create a copy of a card/permanent using only copiable values.

    Rule 707.2 - Copiable values are:
    - Name, mana cost, color indicator, card type, subtype, supertype
    - Rules text (abilities), power/toughness, loyalty

    Rule 707.2 - NOT copied:
    - Counters, stickers, attached objects, effects modifying characteristics
    - Outside-the-game status, tapped/untapped, phased status
    - Face-up/face-down status, any other non-copiable information

    Rule 707.3: Copy effects don't copy whether an object is tapped/untapped,
    phased in/out, face up/down, or the counters on it.

    Rule 707.9: Copy effects copying a copy use the copiable values of the
    original object that was copied (copies are not recursive).

    Args:
        original: The card/permanent to copy
        modifications: Optional list of modification functions to apply after copying
                      (for "copy except..." effects like Spark Double, Phantasmal Image)
        instance_id: Optional specific instance_id to assign (otherwise generates one)

    Returns:
        A new Card instance with copied copiable values

    Example modifications for common clone effects:
        # Spark Double - not legendary, enters with +1/+1 counter
        def spark_double_mod(copy):
            copy.counters["+1/+1"] = copy.counters.get("+1/+1", 0) + 1

        # Phantasmal Image - is an Illusion, has sacrifice trigger
        def phantasmal_mod(copy):
            copy.subtype = "illusion"
            if "sacrifice_when_targeted" not in copy.abilities:
                copy.abilities.append("sacrifice_when_targeted")
    """
    # Determine if original is an MDFC and handle Rule 707.8
    # (copying a double-faced card copies only the face that's up)
    source = original
    if original.is_mdfc and original.mdfc_played_as == "back" and original.mdfc_front:
        # If played as back, we're copying the back face characteristics
        # (but the card object already has those values when mdfc_played_as is set)
        pass  # Use current values

    # Rule 707.2: Copy only copiable values
    copy = Card(
        # Core copiable values
        name=source.name,
        mana_cost=source.mana_cost.copy() if source.mana_cost else ManaCost(),
        card_type=source.card_type,
        subtype=source.subtype,

        # Power/toughness (use base values)
        power=source.power,
        toughness=source.toughness,

        # Loyalty for planeswalkers
        loyalty=source.loyalty,

        # Abilities and keywords (copiable rules text)
        keywords=source.keywords.copy() if source.keywords else [],
        abilities=source.abilities.copy() if source.abilities else [],
        loyalty_abilities=source.loyalty_abilities.copy() if source.loyalty_abilities else [],

        # Land mana production
        produces=source.produces.copy() if source.produces else [],

        # Aura/Equipment grants (part of rules text)
        grants=source.grants.copy() if source.grants else [],
        equip_cost=source.equip_cost,
        return_to_hand=source.return_to_hand,

        # Modal/kicker characteristics (part of rules text)
        modes=source.modes.copy() if source.modes else [],
        choose_two=source.choose_two,
        kicker=source.kicker,
        multikicker=source.multikicker,
        if_kicked=source.if_kicked.copy() if source.if_kicked else [],

        # Alternative costs (part of rules text)
        flashback=source.flashback,
        escape=source.escape,
        escape_exile=source.escape_exile,
        overload=source.overload,
        adventure=source.adventure.copy() if source.adventure else None,

        # Vehicle crew (part of rules text)
        crew=source.crew,

        # Saga chapters (part of rules text)
        chapters=source.chapters.copy() if source.chapters else [],

        # Instance-specific values (NOT copied, use defaults)
        instance_id=instance_id if instance_id is not None else _generate_copy_id(),
        is_tapped=False,  # Rule 707.3: Not copied
        damage_marked=0,  # Rule 707.3: Not copied
        summoning_sick=True,  # New permanent has summoning sickness
        counters={},  # Rule 707.3: Counters not copied
        controller=0,  # Set by caller
        activated_this_turn=False,
        is_token=False,  # Set by caller if creating token copy
        attached_to=None,  # Rule 707.3: Not copied
        deathtouch_damage=False,
        phased_out=False,  # Rule 707.3: Not copied
        regenerate_shield=0,
        shield_counters=0,
        on_adventure=False,
        is_crewed=False,

        # MDFC - copy doesn't preserve double-faced nature by default
        is_mdfc=False,
        mdfc_played_as="",
        mdfc_enters_tapped=False
    )

    # Rule 707.10: Apply copy modifications (for "copy except..." effects)
    if modifications:
        for mod in modifications:
            mod(copy)

    return copy


def copy_spell_on_stack(original: Card, modifications: List[Callable[[Card], None]] = None,
                        instance_id: int = None) -> Card:
    """
    Rule 707.10: Copy a spell on the stack.

    Similar to create_copy but for spells being copied (e.g., Fork, Twincast).
    The copy is created on the stack and can have new targets chosen.

    Args:
        original: The spell being copied
        modifications: Optional modifications to the copy
        instance_id: Optional specific instance_id

    Returns:
        A new Card representing the spell copy
    """
    return create_copy(original, modifications, instance_id)


# Common modification functions for clone effects
def modification_not_legendary(copy: Card) -> None:
    """
    Modification for Spark Double and similar - removes legendary status.
    Note: In this implementation, legendary is part of card_type string.
    """
    if "legendary" in copy.card_type.lower():
        copy.card_type = copy.card_type.lower().replace("legendary ", "").replace("legendary", "")
        copy.card_type = copy.card_type.strip()
        if not copy.card_type:
            copy.card_type = "creature"


def modification_add_counter(counter_type: str, amount: int = 1) -> Callable[[Card], None]:
    """
    Factory for modifications that add counters (like Spark Double's +1/+1).

    Args:
        counter_type: Type of counter ("+1/+1", "-1/-1", "loyalty", etc.)
        amount: Number of counters to add

    Returns:
        A modification function
    """
    def mod(copy: Card) -> None:
        copy.counters[counter_type] = copy.counters.get(counter_type, 0) + amount
    return mod


def modification_add_ability(ability: str) -> Callable[[Card], None]:
    """
    Factory for modifications that add abilities (like Phantasmal Image).

    Args:
        ability: The ability string to add

    Returns:
        A modification function
    """
    def mod(copy: Card) -> None:
        if ability not in copy.abilities:
            copy.abilities.append(ability)
    return mod


def modification_change_subtype(new_subtype: str) -> Callable[[Card], None]:
    """
    Factory for modifications that change subtype.

    Args:
        new_subtype: The new subtype

    Returns:
        A modification function
    """
    def mod(copy: Card) -> None:
        copy.subtype = new_subtype
    return mod


def modification_add_keyword(keyword: str) -> Callable[[Card], None]:
    """
    Factory for modifications that add keywords.

    Args:
        keyword: The keyword to add

    Returns:
        A modification function
    """
    def mod(copy: Card) -> None:
        if keyword.lower() not in [k.lower() for k in copy.keywords]:
            copy.keywords.append(keyword)
    return mod


@dataclass
class StackItem:
    """Represents a spell or ability on the stack"""
    card: Card
    controller: int  # Player ID who cast/controls this
    target: Any = None
    stack_id: int = 0  # Unique identifier for targeting
    is_countered: bool = False
    x_value: int = 0  # Chosen X value for X spells
    chosen_modes: List[str] = field(default_factory=list)  # Selected modes for modal spells
    was_kicked: bool = False  # Whether kicker was paid
    kicker_count: int = 0  # Number of times multikicker was paid
    # Alternative casting tracking
    cast_with_flashback: bool = False  # Cast from graveyard with flashback
    cast_with_escape: bool = False  # Cast from graveyard with escape
    cast_with_overload: bool = False  # Cast with overload (affects all targets)
    cast_as_adventure: bool = False  # Cast the adventure part of the card

    def is_creature_spell(self) -> bool:
        return self.card.card_type == "creature"

    def is_noncreature_spell(self) -> bool:
        return self.card.card_type in ["instant", "sorcery", "enchantment", "artifact", "planeswalker"]

    def cmc(self) -> int:
        """CMC on stack includes X value"""
        base_cmc = self.card.cmc()
        if self.card.mana_cost.has_x():
            return base_cmc + (self.card.mana_cost.X * self.x_value)
        return base_cmc


# =============================================================================
# CONTROL-CHANGING EFFECTS SYSTEM (MTG Rule 108.4, Layer 2)
# =============================================================================

@dataclass
class ControlEffect:
    """
    Represents a control-changing effect (Layer 2 in the layer system).

    Per Rule 108.4: Each object has a controller, which is normally
    the player who put it onto the stack or battlefield, but control
    can change via control-changing effects.

    Control effects stack - the most recent (highest timestamp) wins.
    When an effect ends, control reverts to the next effect in the stack,
    or to the owner if no effects remain.
    """
    new_controller: int  # Player ID of the new controller
    source_id: int  # Instance ID of the card causing the control change
    duration: str  # 'permanent', 'end_of_turn', 'until_leaves', 'until_source_leaves'
    timestamp: int  # Used to determine which effect wins (Layer 2 timestamp order)

    def __repr__(self) -> str:
        return f"ControlEffect(to=P{self.new_controller}, src={self.source_id}, dur={self.duration}, ts={self.timestamp})"


class ControlChangeManager:
    """
    Manages control-changing effects for permanents.

    Implements Layer 2 of the layer system where control is determined.
    Multiple control effects stack, with the most recent (highest timestamp) winning.

    Common control-changing cards:
    - Mind Control: Permanent control (aura-based, ends when aura leaves)
    - Act of Treason: Until end of turn, also untaps and grants haste
    - Agent of Treachery: Permanent control via ETB trigger
    - Claim the Firstborn: Until end of turn for low-MV creatures
    """

    def __init__(self, game: 'Game'):
        self.game = game
        self.timestamp_counter = 0

    def get_next_timestamp(self) -> int:
        """Get the next timestamp for ordering effects."""
        self.timestamp_counter += 1
        return self.timestamp_counter

    def change_control(self, permanent: Card, new_controller_id: int,
                       source: Card, duration: str = 'permanent') -> bool:
        """
        Change control of a permanent.

        Args:
            permanent: The permanent to change control of
            new_controller_id: Player ID of the new controller (1 or 2)
            source: The card causing the control change
            duration: One of 'permanent', 'end_of_turn', 'until_leaves', 'until_source_leaves'

        Returns:
            True if control was successfully changed
        """
        if new_controller_id not in [1, 2]:
            return False

        old_controller_id = permanent.controller

        # Create the control effect
        effect = ControlEffect(
            new_controller=new_controller_id,
            source_id=source.instance_id,
            duration=duration,
            timestamp=self.get_next_timestamp()
        )
        permanent.control_effects.append(effect)

        # Update the controller
        self._update_controller(permanent)

        # Log the control change if it actually changed
        if permanent.controller != old_controller_id:
            duration_text = {
                'permanent': 'permanently',
                'end_of_turn': 'until end of turn',
                'until_leaves': 'until it leaves',
                'until_source_leaves': f'while {source.name} remains'
            }.get(duration, duration)
            self.game.log.log(f"    P{new_controller_id} gains control of {permanent.name} {duration_text}")

        return True

    def end_of_turn_cleanup(self):
        """
        Remove 'until end of turn' control effects at end of turn.
        Called during the cleanup step.
        """
        for player in [self.game.p1, self.game.p2]:
            for permanent in player.battlefield[:]:  # Slice to avoid modification during iteration
                if not permanent.control_effects:
                    continue

                # Remove end_of_turn effects
                original_len = len(permanent.control_effects)
                permanent.control_effects = [
                    e for e in permanent.control_effects
                    if e.duration != 'end_of_turn'
                ]

                # If we removed any effects, update controller
                if len(permanent.control_effects) != original_len:
                    self._update_controller(permanent)

    def on_permanent_leaves(self, source: Card):
        """
        Remove control effects when their source leaves the battlefield.

        This handles:
        - Aura-based control (Mind Control falls off when Mind Control leaves)
        - 'until_source_leaves' effects (e.g., Sower of Temptation)

        Args:
            source: The permanent that is leaving the battlefield
        """
        for player in [self.game.p1, self.game.p2]:
            for permanent in player.battlefield[:]:
                if not permanent.control_effects:
                    continue

                original_len = len(permanent.control_effects)
                permanent.control_effects = [
                    e for e in permanent.control_effects
                    if not (e.source_id == source.instance_id or
                           (e.duration == 'until_source_leaves' and e.source_id == source.instance_id))
                ]

                # If we removed any effects, update controller
                if len(permanent.control_effects) != original_len:
                    self._update_controller(permanent)

    def _update_controller(self, permanent: Card):
        """
        Recalculate and update the controller based on active control effects.

        Per Layer 2 timestamp ordering, the most recent effect wins.
        If no effects, controller reverts to owner.
        """
        if not permanent.control_effects:
            # No control effects - controller is owner
            target_controller = permanent.owner
        else:
            # Latest timestamp effect determines controller (Layer 2)
            latest = max(permanent.control_effects, key=lambda e: e.timestamp)
            target_controller = latest.new_controller

        # Only move if controller actually changed
        if permanent.controller != target_controller:
            self._move_permanent(permanent, target_controller)

    def _move_permanent(self, permanent: Card, new_controller_id: int):
        """
        Move a permanent between players' battlefields.

        Args:
            permanent: The permanent to move
            new_controller_id: Player ID of the new controller
        """
        old_controller_id = permanent.controller
        old_player = self.game.p1 if old_controller_id == 1 else self.game.p2
        new_player = self.game.p1 if new_controller_id == 1 else self.game.p2

        # Remove from old controller's battlefield
        if permanent in old_player.battlefield:
            old_player.battlefield.remove(permanent)

        # Add to new controller's battlefield
        if permanent not in new_player.battlefield:
            new_player.battlefield.append(permanent)

        # Update the controller field
        permanent.controller = new_controller_id

        self.game.log.log(f"    {permanent.name} moved to P{new_controller_id}'s battlefield")

    def get_controller(self, permanent: Card) -> int:
        """Get the current controller of a permanent."""
        return permanent.controller

    def get_owner(self, permanent: Card) -> int:
        """Get the owner of a card (never changes)."""
        return permanent.owner

    def revert_to_owner(self, permanent: Card):
        """
        Revert control of a permanent to its owner.
        Called when a card changes zones (owner always gets it back).
        """
        permanent.control_effects.clear()
        if permanent.controller != permanent.owner:
            self._move_permanent(permanent, permanent.owner)

    def threaten_effect(self, permanent: Card, new_controller_id: int, source: Card):
        """
        Apply a "threaten" effect like Act of Treason.

        This is a convenience method that:
        1. Gains control until end of turn
        2. Untaps the permanent
        3. Grants haste (so it can attack)

        Cards this implements:
        - Act of Treason: {2}{R} - Gain control of target creature until EOT. Untap, gains haste.
        - Claim the Firstborn: {R} - Gain control of creature with MV 3 or less until EOT. Untap, gains haste.
        - Mark of Mutiny: {2}{R} - Gain control, put +1/+1 counter, untap, gains haste.
        - Traitorous Blood: {1}{R}{R} - Same as Act of Treason + gains trample.
        """
        # Gain control until end of turn
        self.change_control(permanent, new_controller_id, source, duration='end_of_turn')

        # Untap it
        if permanent.is_tapped:
            permanent.is_tapped = False
            self.game.log.log(f"    {permanent.name} untaps")

        # Grant haste (remove summoning sickness)
        permanent.summoning_sick = False
        if "haste" not in [kw.lower() for kw in permanent.keywords]:
            permanent.keywords.append("haste")
            self.game.log.log(f"    {permanent.name} gains haste until end of turn")

    def aura_control_effect(self, permanent: Card, aura: Card, new_controller_id: int):
        """
        Apply an Aura-based control effect like Mind Control.

        The control effect ends when the Aura leaves the battlefield.

        Cards this implements:
        - Mind Control: {3}{U}{U} - You control enchanted creature.
        - Control Magic: {2}{U}{U} - You control enchanted creature.
        - Volition Reins: {3}{U}{U}{U} - Gain control of target permanent.
        """
        self.change_control(permanent, new_controller_id, aura, duration='until_source_leaves')


# =============================================================================
# REPLACEMENT EFFECTS SYSTEM (MTG Rule 614)
# =============================================================================

@dataclass
class GameEvent:
    """
    Represents a game event that can be modified by replacement effects.

    Event types:
    - 'die': A creature/permanent would die (go to graveyard from battlefield)
    - 'etb': A permanent would enter the battlefield
    - 'draw': A player would draw a card
    - 'damage': Damage would be dealt
    - 'discard': A card would be discarded
    - 'counter': A counter would be placed
    - 'zone_change': A card would change zones (general)
    """
    event_type: str  # 'die', 'etb', 'damage', 'draw', 'discard', 'counter', 'zone_change'
    source: Optional[Card] = None  # The source causing the event (damage source, etc.)
    card: Optional[Card] = None  # The card affected (creature dying, entering, etc.)
    player: Optional['Player'] = None  # The player affected
    controller: Optional['Player'] = None  # Controller of the affected card

    # Event-specific data
    destination_zone: str = ""  # For zone changes: 'graveyard', 'exile', 'hand', 'library'
    origin_zone: str = ""  # Where the card is coming from
    damage_amount: int = 0  # For damage events
    damage_target: Any = None  # Target of damage (creature, player, planeswalker)
    counter_type: str = ""  # For counter events: '+1/+1', 'loyalty', etc.
    counter_amount: int = 0  # Number of counters
    draw_count: int = 0  # Number of cards to draw

    # Replacement tracking
    is_cancelled: bool = False  # If True, event doesn't happen at all
    is_modified: bool = False  # If True, event was modified by a replacement
    replacement_data: Dict[str, Any] = field(default_factory=dict)  # Modified event data
    applied_replacements: List[str] = field(default_factory=list)  # IDs of applied effects

    # ETB-specific
    etb_tapped: bool = False  # If True, enters tapped
    etb_with_counters: Dict[str, int] = field(default_factory=dict)  # Counters to enter with
    etb_trigger_count: int = 1  # Number of times ETB triggers (Panharmonicon = 2)

    def copy(self) -> 'GameEvent':
        """Create a copy of this event"""
        new_event = GameEvent(
            event_type=self.event_type,
            source=self.source,
            card=self.card,
            player=self.player,
            controller=self.controller,
            destination_zone=self.destination_zone,
            origin_zone=self.origin_zone,
            damage_amount=self.damage_amount,
            damage_target=self.damage_target,
            counter_type=self.counter_type,
            counter_amount=self.counter_amount,
            draw_count=self.draw_count,
            is_cancelled=self.is_cancelled,
            is_modified=self.is_modified,
            replacement_data=self.replacement_data.copy(),
            applied_replacements=self.applied_replacements.copy(),
            etb_tapped=self.etb_tapped,
            etb_with_counters=self.etb_with_counters.copy(),
            etb_trigger_count=self.etb_trigger_count,
        )
        return new_event


@dataclass
class ReplacementEffect:
    """
    Represents a replacement effect per MTG Rule 614.

    Replacement effects modify events before they happen:
    - "If X would happen, Y happens instead"
    - "If X would happen, X happens with modifications"

    Key rules:
    - 614.2: Each replacement can only apply once per event
    - 614.6: Self-replacement effects apply first
    - 614.7: For multiple effects, affected player/controller chooses order
    """
    source: Card  # The card creating this replacement effect
    effect_id: str  # Unique identifier (source.instance_id + effect name)
    event_type: str  # 'die', 'etb', 'damage', 'draw', 'discard', 'counter', 'zone_change'
    condition: Callable[['GameEvent', 'Game'], bool]  # Checks if this effect applies
    replacement: Callable[['GameEvent', 'Game'], 'GameEvent']  # Modifies the event
    self_replacement: bool = False  # Rule 614.6: Self-replacements apply first
    controller_id: int = 0  # Player who controls this effect (for ordering choices)
    description: str = ""  # Human-readable description for logging

    def applies_to(self, event: 'GameEvent', game: 'Game') -> bool:
        """Check if this replacement effect applies to the given event"""
        # Check event type matches
        if self.event_type != event.event_type:
            return False
        # Check if already applied to this event (Rule 614.2)
        if self.effect_id in event.applied_replacements:
            return False
        # Check condition
        return self.condition(event, game)

    def apply(self, event: 'GameEvent', game: 'Game') -> 'GameEvent':
        """Apply this replacement effect to the event"""
        # Mark as applied (Rule 614.2 - can only apply once per event)
        event.applied_replacements.append(self.effect_id)
        event.is_modified = True
        # Apply the replacement
        return self.replacement(event, game)


@dataclass
class Player:
    player_id: int
    deck_name: str
    archetype: str = "midrange"
    life: int = 20
    poison_counters: int = 0  # For SBA: 10+ poison = lose game
    library: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    battlefield: List[Card] = field(default_factory=list)
    graveyard: List[Card] = field(default_factory=list)
    exile: List[Card] = field(default_factory=list)
    land_played: bool = False
    spells_cast: int = 0
    mana_pool: ManaPool = field(default_factory=ManaPool)
    attempted_draw_from_empty: bool = False  # For SBA: drawing from empty library = lose

    def untapped_lands(self) -> List[Card]:
        """Return list of untapped lands"""
        return [c for c in self.battlefield if c.card_type == "land" and not c.is_tapped]

    def available_mana(self, include_dorks: bool = True) -> ManaPool:
        """
        Calculate total mana available from untapped lands and mana dorks.

        Args:
            include_dorks: If True, also count mana from untapped mana dorks
        """
        pool = ManaPool()

        # Mana from lands
        for land in self.untapped_lands():
            if land.produces:
                # Add first color the land produces (simplified)
                pool.add(land.produces[0])
            else:
                # Basic land detection by name
                name = land.name.lower()
                if "plains" in name or "white" in name: pool.W += 1
                elif "island" in name or "blue" in name: pool.U += 1
                elif "swamp" in name or "black" in name: pool.B += 1
                elif "mountain" in name or "red" in name: pool.R += 1
                elif "forest" in name or "green" in name: pool.G += 1
                else:
                    # Dual lands - check for color pairs in name
                    added = False
                    for color in COLORS:
                        if color.lower() in name:
                            pool.add(color)
                            added = True
                            break
                    if not added:
                        pool.C += 1  # Colorless if unknown

        # Mana from mana dorks (if requested)
        if include_dorks:
            for dork in self.untapped_mana_dorks():
                produces = self.mana_dork_produces(dork)
                if produces:
                    if "any" in produces:
                        # For calculation purposes, count as G (most common)
                        pool.add("G")
                    else:
                        pool.add(produces[0])

        return pool

    def can_cast(self, card: Card) -> bool:
        """Check if player can cast this card"""
        return self.available_mana().can_pay(card.mana_cost)

    def creatures(self) -> List[Card]:
        """Return creatures and crewed vehicles (excludes phased-out)"""
        return [c for c in self.battlefield if c.is_creature_now() and not c.phased_out]

    def vehicles(self) -> List[Card]:
        """Return all vehicles on battlefield (excludes phased-out)"""
        return [c for c in self.battlefield if c.is_vehicle() and not c.phased_out]

    def planeswalkers(self) -> List[Card]:
        """Return list of planeswalkers on battlefield (excludes phased-out)"""
        return [c for c in self.battlefield if c.card_type == "planeswalker" and not c.phased_out]

    def attackers_available(self) -> List[Card]:
        """Return creatures that can attack (not tapped, no summoning sickness unless haste, no defender)"""
        return [c for c in self.creatures()
                if not c.is_tapped
                and (not c.summoning_sick or c.has_keyword("haste"))
                and not c.has_keyword("defender")]

    def total_power(self) -> int:
        return sum(c.eff_power() for c in self.creatures())

    def untapped_mana_dorks(self) -> List[Card]:
        """
        Return list of untapped creatures that can tap for mana.
        Looks for 'tap_for_X' abilities or 'mana_dork' ability.
        Creature must not have summoning sickness (unless it has haste).
        """
        dorks = []
        for c in self.battlefield:
            if c.card_type != "creature":
                continue
            if c.is_tapped:
                continue
            # Check for summoning sickness
            if c.summoning_sick and not c.has_keyword("haste"):
                continue
            # Check if it has mana ability
            has_mana_ability = False
            for ab in c.abilities:
                if ab.startswith("tap_for_") or ab == "mana_dork":
                    has_mana_ability = True
                    break
            if has_mana_ability:
                dorks.append(c)
        return dorks

    def mana_dork_produces(self, card: Card) -> List[str]:
        """
        Determine what mana a dork produces based on its abilities.
        Returns list of colors it can produce (e.g., ["G"] or ["W", "U"] or ["any"]).
        """
        for ab in card.abilities:
            if ab.startswith("tap_for_"):
                # Parse format: tap_for_G, tap_for_WU, tap_for_any
                mana_part = ab[8:]  # Remove 'tap_for_'
                if mana_part == "any":
                    return ["any"]
                # Return each color as separate entry
                return list(mana_part.upper())
            elif ab == "mana_dork":
                # Legacy format - assume produces G (most common for mana dorks)
                return ["G"]
        return []


class Log:
    def __init__(self, verbose: bool = True):
        self.entries = []
        self.verbose = verbose
    
    def log(self, msg: str):
        self.entries.append(msg)
        if self.verbose:
            print(msg)
    
    def section(self, title: str):
        self.log(f"\n{'='*60}\n  {title}\n{'='*60}")


# =============================================================================
# DECK PARSER - Reads MTGO .txt format
# =============================================================================

def detect_land_colors(card_name: str) -> List[str]:
    """Detect what colors a land produces from its name"""
    name = card_name.lower()
    colors = []

    # Basic lands
    if "plains" in name: return ["W"]
    if "island" in name: return ["U"]
    if "swamp" in name: return ["B"]
    if "mountain" in name: return ["R"]
    if "forest" in name: return ["G"]

    # Common dual land patterns
    dual_patterns = {
        # Fetchlands, shocklands, etc. by color pair names
        "azorius": ["W", "U"], "dimir": ["U", "B"], "rakdos": ["B", "R"],
        "gruul": ["R", "G"], "selesnya": ["G", "W"], "orzhov": ["W", "B"],
        "izzet": ["U", "R"], "golgari": ["B", "G"], "boros": ["R", "W"],
        "simic": ["G", "U"],
        # Pain lands
        "adarkar": ["W", "U"], "underground": ["U", "B"], "sulfurous": ["B", "R"],
        "karplusan": ["R", "G"], "brushland": ["G", "W"], "caves of koilos": ["W", "B"],
        "shivan": ["U", "R"], "llanowar": ["B", "G"], "battlefield": ["R", "W"],
        "yavimaya": ["G", "U"],
        # Pathways, triomes, etc.
        "coastal": ["W", "U"], "clearwater": ["U", "B"], "blightstep": ["B", "R"],
        "cragcrown": ["R", "G"], "branchloft": ["G", "W"], "brightclimb": ["W", "B"],
        "riverglide": ["U", "R"], "darkbore": ["B", "G"], "needleverge": ["R", "W"],
        "barkchannel": ["G", "U"],
    }

    for pattern, cols in dual_patterns.items():
        if pattern in name:
            return cols

    # Check for color words
    if "white" in name: colors.append("W")
    if "blue" in name: colors.append("U")
    if "black" in name: colors.append("B")
    if "red" in name: colors.append("R")
    if "green" in name: colors.append("G")

    return colors if colors else ["C"]  # Colorless if unknown


def is_mdfc_card(card_name: str) -> bool:
    """Check if a card name indicates a Modal Double-Faced Card"""
    return " // " in card_name


def parse_mdfc_faces(card_name: str) -> Tuple[str, str]:
    """Split an MDFC name into front and back face names"""
    if " // " in card_name:
        parts = card_name.split(" // ")
        return parts[0].strip(), parts[1].strip()
    return card_name, ""


def create_mdfc_back_face(front_card: 'Card', back_data: Dict, back_name: str) -> 'Card':
    """
    Create the back face of an MDFC and link it to the front.
    Back face data comes from card_database MDFC structure.
    """
    back_type = back_data.get("type", "land")
    back_cost_str = back_data.get("cost", back_data.get("mana_cost", ""))

    if isinstance(back_cost_str, int):
        back_cost = ManaCost(generic=back_cost_str)
    else:
        back_cost = ManaCost.parse(str(back_cost_str)) if back_cost_str else ManaCost()

    # Detect produces for land backs
    produces = []
    if back_type == "land":
        produces = back_data.get("produces", detect_land_colors(back_name))

    back_card = Card(
        name=back_name,
        mana_cost=back_cost,
        card_type=back_type,
        subtype=str(back_data.get("subtype", "")),
        power=int(back_data.get("power", 0)),
        toughness=int(back_data.get("toughness", 0)),
        keywords=list(back_data.get("keywords", [])),
        abilities=list(back_data.get("abilities", [])),
        produces=produces,
        is_mdfc=True,
        mdfc_front=front_card,
        mdfc_enters_tapped=bool(back_data.get("enters_tapped", False))
    )

    # Link front to back
    front_card.is_mdfc = True
    front_card.mdfc_back = back_card

    return back_card


def _generate_loyalty_abilities(card_data: Dict) -> List[str]:
    """
    Auto-generate loyalty abilities for planeswalkers based on their regular abilities.
    Format: "+N:effect" or "-N:effect"
    """
    abilities = card_data.get("abilities", [])
    loyalty = int(card_data.get("loyalty", 4))
    generated = []

    # Create a +1 ability (plus ability - usually first/safest)
    if abilities:
        generated.append(f"+1:{abilities[0]}")

    # Create minus abilities from remaining abilities
    if len(abilities) >= 2:
        # Second ability is usually a -2 or -3
        generated.append(f"-2:{abilities[1]}")

    if len(abilities) >= 3:
        # Third ability is usually ultimate (-6 to -8)
        ultimate_cost = max(loyalty - 1, 5)
        generated.append(f"-{ultimate_cost}:{abilities[2]}")

    # Fallback: if no abilities, create generic ones
    if not generated:
        generated = ["+1:draw_1", f"-{loyalty}:damage_3_any"]

    return generated


def parse_loyalty_ability(ability_str: str) -> Tuple[int, str]:
    """
    Parse a loyalty ability string like "+1:draw_1" or "-3:destroy_creature".
    Returns (cost_change, effect_str).
    """
    if ':' not in ability_str:
        return (0, ability_str)

    cost_part, effect = ability_str.split(':', 1)
    cost_part = cost_part.strip()

    # Parse +N or -N
    if cost_part.startswith('+'):
        cost = int(cost_part[1:])
    elif cost_part.startswith('-'):
        cost = -int(cost_part[1:])
    else:
        cost = int(cost_part) if cost_part.lstrip('-').isdigit() else 0

    return (cost, effect.strip())


def parse_decklist(decklist_txt: str, deck_name: str = None) -> Tuple[List[Card], List[Card], str, str]:
    """
    Parse an MTGO-format decklist.

    Format:
        4 Card Name
        2 Another Card
        // Comments ignored

        4 Sideboard Card

    Returns: (maindeck, sideboard, deck_name, archetype)
    """
    cards = []
    sideboard = []
    unknown_cards = []

    lines = decklist_txt.strip().split('\n')
    in_sideboard = False
    detected_name = deck_name
    blank_seen = False

    creature_count = 0
    spell_count = 0
    creature_costs = []

    for line in lines:
        line = line.strip()

        if not line:
            blank_seen = True
            continue

        if line.startswith('//') or line.startswith('#'):
            continue

        # Deck name detection
        if not detected_name and ('_AI' in line or '_ai' in line):
            detected_name = line.replace('_AI', '').replace('_ai', '').replace('_', ' ')
            continue

        if line.lower().startswith('sideboard'):
            in_sideboard = True
            continue

        # Parse "N Card Name"
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if not match:
            continue

        # Detect sideboard by blank line after enough maindeck cards
        if blank_seen and len(cards) >= 40:
            in_sideboard = True

        count = int(match.group(1))
        card_name = match.group(2).strip()

        card_data = get_card_data(card_name)

        if card_name not in CARD_DATABASE:
            lower_match = False
            for k in CARD_DATABASE:
                if k.lower() == card_name.lower():
                    lower_match = True
                    break
            if not lower_match:
                unknown_cards.append(card_name)

        # Parse mana cost
        cost_str = card_data.get("mana_cost", card_data.get("cost", ""))
        if isinstance(cost_str, int):
            # Old format: just a number
            mana_cost = ManaCost(generic=cost_str)
        else:
            mana_cost = ManaCost.parse(str(cost_str))

        card_type = card_data.get("type", "creature")

        # Detect land colors
        produces = []
        if card_type == "land":
            produces = card_data.get("produces", detect_land_colors(card_name))

        # Get or generate loyalty abilities for planeswalkers
        loyalty_abilities = list(card_data.get("loyalty_abilities", []))
        if card_type == "planeswalker" and not loyalty_abilities:
            # Auto-generate loyalty abilities from regular abilities
            loyalty_abilities = _generate_loyalty_abilities(card_data)

        for _ in range(count):
            card = Card(
                name=card_name,
                mana_cost=mana_cost.copy(),
                card_type=card_type,
                subtype=str(card_data.get("subtype", "")),
                power=int(card_data.get("power", 0)),
                toughness=int(card_data.get("toughness", 0)),
                keywords=list(card_data.get("keywords", [])),
                abilities=list(card_data.get("abilities", [])),
                loyalty=int(card_data.get("loyalty", 0)),
                produces=list(produces),
                loyalty_abilities=list(loyalty_abilities),
                grants=list(card_data.get("grants", [])),
                equip_cost=str(card_data.get("equip_cost", "")),
                return_to_hand=bool(card_data.get("return_to_hand", False))
            )

            # Handle MDFC - create back face if "//" in name
            if is_mdfc_card(card_name):
                _, back_name = parse_mdfc_faces(card_name)
                back_data = card_data.get("back", {})
                if not back_data and back_name:
                    back_data = {"type": "land", "produces": detect_land_colors(back_name), "enters_tapped": True}
                if back_data:
                    create_mdfc_back_face(card, back_data, back_name)

            if in_sideboard:
                sideboard.append(card)
            else:
                cards.append(card)
                if card.card_type == "creature":
                    creature_count += 1
                    creature_costs.append(card.cmc())
                elif card.card_type not in ["land"]:
                    spell_count += 1

    if unknown_cards:
        unique = list(set(unknown_cards))[:10]
        print(f"\n[WARNING] Unknown cards: {unique}{'...' if len(set(unknown_cards)) > 10 else ''}")
        print("   Add to card_database.py for accurate stats.\n")
    
    # Detect archetype
    avg_cost = sum(creature_costs) / len(creature_costs) if creature_costs else 3
    if creature_count >= 24 and avg_cost <= 2.5:
        archetype = "aggro"
    elif creature_count <= 12 and spell_count >= 16:
        archetype = "control"
    else:
        archetype = "midrange"
    
    if not detected_name:
        detected_name = f"Deck ({len(cards)} cards)"

    return cards, sideboard, detected_name, archetype


# =============================================================================
# AI DECISION ENGINE
# =============================================================================

class AI:
    def __init__(self, player: Player, opponent: Player, log: Log):
        self.me = player
        self.opp = opponent
        self.log = log
    
    def board_eval(self) -> Dict:
        opp_creatures = self.opp.creatures()
        
        threats = []
        for c in opp_creatures:
            threat = c.eff_power()
            if "magebane" in c.abilities:
                threat += 15
            if "deathtouch" in c.keywords:
                threat += 3
            if c.eff_power() >= 4:
                threat += 2
            threats.append((c, threat))
        threats.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "my_power": self.me.total_power(),
            "opp_power": self.opp.total_power(),
            "threats": threats,
            "top_threat": threats[0][0] if threats else None,
            "can_lethal": self.me.total_power() >= self.opp.life,
            "archetype": self.me.archetype
        }
    
    def score_card(self, card: Card, board: Dict, mana_pool: ManaPool) -> float:
        score = 0.0
        arch = board["archetype"]

        # Can't cast = 0 score
        if not mana_pool.can_pay(card.mana_cost):
            return -100

        if card.card_type == "creature":
            score = card.eff_power() + card.eff_toughness() * 0.5
            if card.has_keyword("haste"):
                score += 2
            if card.has_keyword("trample"):
                score += 1.5
            if card.has_keyword("flying"):
                score += 1.5
            if card.has_keyword("first_strike") or card.has_keyword("first strike"):
                score += 1
            if card.has_keyword("deathtouch"):
                score += 2
            if card.has_keyword("lifelink"):
                score += 1
            if card.has_keyword("vigilance"):
                score += 0.5
            if arch == "aggro":
                score += 2

        elif card.card_type in ["instant", "sorcery"]:
            has_removal = any(a.startswith("damage_") or a in ["destroy_creature", "exile", "bite", "fight"]
                             for a in card.abilities)
            if has_removal and board["top_threat"]:
                score = 10 + board["threats"][0][1]
            elif has_removal:
                score = 3

            if any("draw" in a for a in card.abilities):
                score = 6 if arch == "control" else 4

            if "bounce" in str(card.abilities) and board["top_threat"]:
                score = 7

        elif card.card_type == "enchantment":
            if card.is_saga():
                # Saga value based on number and quality of chapters
                score = self._evaluate_saga(card, board)
            elif "token_on_spell" in card.abilities or "spell_trigger" in card.abilities:
                score = 6
            else:
                score = 4

        elif card.card_type == "planeswalker":
            score = 8

        return score

    def _evaluate_saga(self, saga: Card, board: Dict) -> float:
        """Evaluate saga value based on its chapter abilities and current game state"""
        score = 0.0
        has_opponent_creatures = board.get("top_threat") is not None
        has_own_graveyard = len(self.me.graveyard) > 0

        for chapter_ability in saga.chapters:
            ab = chapter_ability.lower()
            # Removal effects
            if "sacrifice" in ab and "opponent" in ab:
                score += 4 if has_opponent_creatures else 1
            elif "destroy" in ab or "exile" in ab:
                score += 3
            # Card advantage
            elif "draw" in ab:
                score += 3
            elif "discard" in ab and "opponent" in ab:
                score += 2
            # Recursion effects
            elif "reanimate" in ab or "return" in ab:
                score += 4 if has_own_graveyard else 2
            # Token creation
            elif "token" in ab or "create" in ab:
                score += 2.5
            # Damage
            elif "damage" in ab:
                score += 2
            # Life gain
            elif "life" in ab or "gain" in ab:
                score += 1.5
            # Generic value
            else:
                score += 1.5

        # Sagas provide guaranteed value over multiple turns
        score += len(saga.chapters) * 0.5
        return score

    def determine_x_value(self, card: Card, mana_pool: ManaPool, target: Any = None) -> int:
        """
        Determine optimal X value for X spells based on card type and game state.
        AI logic considers:
        - Damage spells: target's toughness or opponent life
        - Draw spells: spend all extra mana
        - Token creation: maximize value
        - Creature P/T: maximize stats
        """
        if not card.mana_cost.has_x():
            return 0

        max_x = mana_pool.max_x_value(card.mana_cost)
        if max_x <= 0:
            return 0

        abilities = card.abilities

        # Damage spells - aim for lethal or just enough to kill target
        for ab in abilities:
            if "damage_X" in ab or ab == "damage_X_any":
                if target == "face":
                    # Go for lethal if possible, otherwise spend all
                    return min(max_x, self.opp.life)
                elif isinstance(target, Card):
                    # Just enough to kill + 1 for safety, or max
                    needed = target.eff_toughness() - target.damage_marked
                    return min(max_x, max(needed, 1))
                # Default: spend all for face damage
                return max_x

        # Draw spells - spend all extra mana
        for ab in abilities:
            if "draw_X" in ab or "draw_half_X" in ab:
                return max_x

        # Token creation - maximize tokens
        for ab in abilities:
            if "create_X_tokens" in ab or "token_X" in ab:
                return max_x

        # Creatures with X in cost (like Hydroid Krasis) - maximize
        if card.card_type == "creature":
            return max_x

        # ETB effects with X - maximize
        for ab in abilities:
            if "etb_" in ab and "_X" in ab:
                return max_x

        # Default: spend all available mana on X
        return max_x

    def find_flashback_spells(self, mana_pool: ManaPool) -> List[Tuple[Card, ManaCost]]:
        """Find castable flashback spells from graveyard. Returns (card, flashback_cost) pairs."""
        result = []
        for card in self.me.graveyard:
            if card.flashback and card.card_type in ["instant", "sorcery"]:
                fb_cost = ManaCost.parse(card.flashback)
                if mana_pool.can_pay(fb_cost):
                    result.append((card, fb_cost))
        return result

    def find_escape_spells(self, mana_pool: ManaPool) -> List[Tuple[Card, ManaCost, int]]:
        """
        Find castable escape spells from graveyard.
        Returns (card, escape_cost, cards_to_exile) tuples.
        Only returns spells where we have enough other cards to exile.
        """
        result = []
        graveyard_size = len(self.me.graveyard)
        for card in self.me.graveyard:
            if card.escape and card.escape_exile > 0:
                escape_cost = ManaCost.parse(card.escape)
                # Need enough OTHER cards in graveyard to exile
                other_cards = graveyard_size - 1
                if mana_pool.can_pay(escape_cost) and other_cards >= card.escape_exile:
                    result.append((card, escape_cost, card.escape_exile))
        return result

    def find_adventure_creatures(self, mana_pool: ManaPool) -> List[Tuple[Card, ManaCost]]:
        """Find adventure creatures that can be cast from exile (on_adventure=True)."""
        result = []
        for card in self.me.exile:
            if card.on_adventure and card.card_type == "creature":
                if mana_pool.can_pay(card.mana_cost):
                    result.append((card, card.mana_cost))
        return result

    def find_adventure_spells(self, mana_pool: ManaPool) -> List[Tuple[Card, ManaCost, List[str]]]:
        """
        Find adventure cards in hand where we can cast the adventure part.
        Returns (card, adventure_cost, adventure_abilities) tuples.
        """
        result = []
        for card in self.me.hand:
            if card.adventure and card.card_type == "creature":
                adv_cost = ManaCost.parse(card.adventure.get("cost", ""))
                if mana_pool.can_pay(adv_cost):
                    abilities = card.adventure.get("abilities", [])
                    result.append((card, adv_cost, abilities))
        return result

    def evaluate_alternative_cost(self, card: Card, alt_type: str, board: Dict) -> float:
        """
        Score whether to use alternative casting cost.
        Higher = prefer alternative, lower = prefer normal cast (or skip).
        """
        base_score = self.score_card(card, board, self.me.available_mana())

        if alt_type == "flashback":
            # Flashback from graveyard is free value - prioritize removal
            if any(a in ["destroy_creature", "damage_3", "damage_4"] for a in card.abilities):
                return base_score + 3  # Bonus for removal from graveyard
            return base_score + 1  # Small bonus for reusing any spell

        elif alt_type == "escape":
            # Escape costs cards - only worth it for strong effects
            graveyard_value = len(self.me.graveyard) * 0.3  # Cards have some value
            if card.card_type == "creature" and card.eff_power() >= 3:
                return base_score + 2 - graveyard_value
            return base_score - graveyard_value

        elif alt_type == "overload":
            # Overload is better when opponent has multiple targets
            target_count = len([c for c in self.opp.battlefield if c.card_type == "creature"])
            if target_count >= 3:
                return base_score + 5
            elif target_count >= 2:
                return base_score + 2
            return base_score - 2  # Worse if only 1 target

        elif alt_type == "adventure":
            # Adventure: prefer creature if we need board presence, spell if not
            my_creatures = len(self.me.creatures())
            if my_creatures < 2:
                return base_score - 2  # Prefer casting creature directly
            return base_score + 1  # Spell first, creature later is value

        return base_score

    def find_target(self, card: Card, board: Dict):
        """
        Find a valid target for this card, respecting hexproof/ward/protection.
        Returns the target, or None if no valid target exists.
        Ward cost is tracked but for simplicity, AI will pay life if worth it.
        """
        abilities = card.abilities

        # Filter threats to only include targetable creatures
        valid_threats = []
        for threat, score in board["threats"]:
            can_target, ward_cost = self.can_target(card, threat, self.me)
            if can_target:
                # Adjust score for ward cost (ward 2 = -2 score)
                adjusted_score = score - ward_cost
                valid_threats.append((threat, adjusted_score, ward_cost))

        for ab in abilities:
            if ab.startswith("damage_"):
                try:
                    dmg = int(ab.split("_")[1])
                except:
                    dmg = 3

                # Find best target that damage can kill
                for threat, _, ward_cost in valid_threats:
                    if threat.eff_toughness() <= dmg:
                        # Worth paying ward if it kills the threat
                        if ward_cost > 0 and ward_cost < threat.eff_power():
                            return (threat, ward_cost)  # Include ward cost
                        elif ward_cost == 0:
                            return threat

                # If no killable target, go face or hit biggest threat
                if not valid_threats:
                    return "face"
                # Return biggest threat we can target
                if valid_threats:
                    best = valid_threats[0][0]
                    ward = valid_threats[0][2]
                    if ward > 0:
                        return (best, ward)
                    return best
                return "face"

        if any(a in abilities for a in ["destroy_creature", "exile"]):
            if valid_threats:
                best = valid_threats[0][0]
                ward = valid_threats[0][2]
                # Pay ward if threat is significant
                if ward > 0 and ward <= best.eff_power():
                    return (best, ward)
                elif ward == 0:
                    return best
            return None

        if "bounce" in str(abilities):
            if valid_threats:
                best = valid_threats[0][0]
                ward = valid_threats[0][2]
                if ward == 0:
                    return best
                elif ward <= 2:  # Pay small ward for bounce
                    return (best, ward)
            return None

        if "bite" in abilities or "fight" in abilities:
            my_c = self.me.creatures()
            if my_c and valid_threats:
                best_threat = valid_threats[0][0]
                ward = valid_threats[0][2]
                if ward == 0:
                    return (max(my_c, key=lambda c: c.eff_power()), best_threat)
                # Pay ward if our creature can win the fight
                best_mine = max(my_c, key=lambda c: c.eff_power())
                if best_mine.eff_power() >= best_threat.eff_toughness() and ward <= 2:
                    return (best_mine, best_threat, ward)

        return None
    
    def needs_target(self, card: Card) -> bool:
        targeting = ["damage_", "destroy_", "exile", "bounce", "bite", "fight", "counter"]
        return any(any(t in a for t in targeting) for a in card.abilities)

    def can_target(self, source: Card, target: Card, targeting_player: Player) -> Tuple[bool, int]:
        """
        Check if source can legally target target creature.
        Returns (can_target, ward_cost) - ward_cost is life to pay if ward applies.

        Hexproof: Can't be targeted by opponents
        Ward N: Opponent must pay N life (or spell is countered)
        Protection from X: Can't be targeted by X (color, type, etc.)
        Shroud: Can't be targeted by anyone (including controller)
        """
        if target.controller == targeting_player.player_id:
            # Targeting own creature - hexproof doesn't apply
            if target.has_keyword("shroud"):
                return (False, 0)
            return (True, 0)

        # Targeting opponent's creature
        if target.has_keyword("hexproof"):
            return (False, 0)

        if target.has_keyword("shroud"):
            return (False, 0)

        # Check ward
        ward_cost = 0
        for kw in target.keywords:
            kw_lower = kw.lower()
            if kw_lower.startswith("ward"):
                # Extract ward cost (e.g., "ward 2" -> 2 life)
                try:
                    parts = kw_lower.split()
                    if len(parts) >= 2:
                        ward_cost = int(parts[1])
                    else:
                        ward_cost = 2  # Default ward cost
                except (ValueError, IndexError):
                    ward_cost = 2

        # Check protection
        for kw in target.keywords:
            kw_lower = kw.lower()
            if kw_lower.startswith("protection"):
                # Check what it has protection from
                prot_from = kw_lower.replace("protection from ", "").replace("protection_", "")

                # Color protection
                color_map = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
                if prot_from in color_map:
                    protected_color = color_map[prot_from]
                    # Check if source has that color
                    source_colors = source.mana_cost.colors()
                    if protected_color in source_colors:
                        return (False, 0)

                # Protection from everything
                if prot_from == "everything":
                    return (False, 0)

        return (True, ward_cost)

    def choose_mdfc_face(self, card: Card, mana_pool: ManaPool, board: Dict) -> str:
        """Decide MDFC face: 'front' or 'back'. Mana-screwed=land, flooded=spell."""
        if not card.is_mdfc or not card.mdfc_back:
            return "front"
        lands = len([c for c in self.me.battlefield if c.card_type == "land"])
        if lands < 3 and len(self.me.hand) > 4 and card.mdfc_back.card_type == "land":
            return "back"
        if lands >= 6 and mana_pool.can_pay(card.mana_cost):
            return "front"
        if mana_pool.can_pay(card.mana_cost) and self.score_card(card, board, mana_pool) > 5:
            return "front"
        if card.mdfc_back.card_type == "land" and not self.me.land_played:
            return "back"
        return "front"

    def find_instants(self, mana_pool: ManaPool) -> List[Card]:
        """Find castable instant-speed spells from hand"""
        return [c for c in self.me.hand
                if c.card_type == "instant" and mana_pool.can_pay(c.mana_cost)]

    def find_flash_creatures(self, mana_pool: ManaPool) -> List[Card]:
        """Find castable creatures with flash from hand"""
        return [c for c in self.me.hand
                if c.card_type == "creature" and c.has_keyword("flash")
                and mana_pool.can_pay(c.mana_cost)]

    def combat_trick_decision(self, attackers: List[Card], blockers: List[Card],
                              mana_pool: ManaPool) -> Optional[Tuple[Card, Any]]:
        """
        Decide whether to cast a combat trick (instant during combat).
        Returns (spell, target) or None.
        """
        instants = self.find_instants(mana_pool)
        if not instants:
            return None

        board = self.board_eval()

        for spell in instants:
            abilities = spell.abilities

            # Pump spell - use on attacking/blocking creature
            if any("pump" in ab.lower() or "+1" in ab or "+2" in ab for ab in abilities):
                # Find best creature to pump
                my_creatures = attackers if attackers else blockers
                if my_creatures:
                    # Pump creature that would trade badly otherwise
                    for c in my_creatures:
                        if c.eff_power() > 0:
                            return (spell, c)

            # Damage spell - use on blocker or attacker
            for ab in abilities:
                if ab.startswith("damage_"):
                    try:
                        dmg = int(ab.split("_")[1])
                    except:
                        dmg = 2

                    # Kill a blocker to get damage through
                    for b in blockers:
                        can_target, ward = self.can_target(spell, b, self.me)
                        if can_target and b.eff_toughness() <= dmg:
                            return (spell, b if ward == 0 else (b, ward))

        return None

    def main_phase(self) -> List[Tuple[str, Card, Any]]:
        actions = []
        board = self.board_eval()

        # Play a land first - includes MDFC back faces as land options
        lands = [c for c in self.me.hand if c.card_type == "land"]
        mdfc_lands = [c for c in self.me.hand if c.is_mdfc and c.mdfc_back and c.mdfc_back.card_type == "land"]
        land_to_play = None
        mdfc_as_land = None
        if (lands or mdfc_lands) and not self.me.land_played:
            needed_colors = set()
            for c in self.me.hand:
                if c.card_type != "land" and not c.is_mdfc:
                    needed_colors.update(c.mana_cost.colors())
            if lands:
                best_land = lands[0]
                for land in lands:
                    if land.produces:
                        for color in land.produces:
                            if color in needed_colors:
                                best_land = land
                                break
                land_to_play = best_land
                actions.append(("land", land_to_play, None))
            elif mdfc_lands:
                temp_pool = self.me.available_mana()
                for mdfc in mdfc_lands:
                    if self.choose_mdfc_face(mdfc, temp_pool, board) == "back":
                        mdfc_as_land = mdfc
                        break
                if mdfc_as_land:
                    actions.append(("mdfc_land", mdfc_as_land, None))

        # Calculate available mana (including land we're about to play)
        mana_pool = self.me.available_mana()
        if land_to_play and land_to_play.produces:
            mana_pool.add(land_to_play.produces[0])
        elif land_to_play:
            # Guess from land name
            colors = detect_land_colors(land_to_play.name)
            if colors:
                mana_pool.add(colors[0])
        # Add mana from MDFC played as land (if untapped)
        if mdfc_as_land and mdfc_as_land.mdfc_back and not mdfc_as_land.mdfc_back.mdfc_enters_tapped:
            if mdfc_as_land.mdfc_back.produces:
                mana_pool.add(mdfc_as_land.mdfc_back.produces[0])

        # Build list of all castable options: (card, score, cast_type, cost, extra_data)
        # cast_type: "normal", "flashback", "escape", "overload", "adventure", "adventure_creature"
        all_options = []

        # Normal hand casts
        for c in self.me.hand:
            if c.card_type != "land" and mana_pool.can_pay(c.mana_cost):
                score = self.score_card(c, board, mana_pool)
                all_options.append((c, score, "normal", c.mana_cost, None))
                # Check overload option
                if c.overload:
                    ol_cost = ManaCost.parse(c.overload)
                    if mana_pool.can_pay(ol_cost):
                        ol_score = self.evaluate_alternative_cost(c, "overload", board)
                        all_options.append((c, ol_score, "overload", ol_cost, None))
                # Check adventure option (cast spell part, creature goes to exile)
                if c.adventure and c.card_type == "creature":
                    adv_cost = ManaCost.parse(c.adventure.get("cost", ""))
                    if mana_pool.can_pay(adv_cost):
                        adv_score = self.evaluate_alternative_cost(c, "adventure", board)
                        all_options.append((c, adv_score, "adventure", adv_cost, c.adventure.get("abilities", [])))

        # Flashback from graveyard
        for card, fb_cost in self.find_flashback_spells(mana_pool):
            score = self.evaluate_alternative_cost(card, "flashback", board)
            all_options.append((card, score, "flashback", fb_cost, None))

        # Escape from graveyard
        for card, esc_cost, exile_count in self.find_escape_spells(mana_pool):
            score = self.evaluate_alternative_cost(card, "escape", board)
            all_options.append((card, score, "escape", esc_cost, exile_count))

        # Adventure creatures from exile
        for card, cost in self.find_adventure_creatures(mana_pool):
            score = self.score_card(card, board, mana_pool)
            all_options.append((card, score, "adventure_creature", cost, None))

        if not all_options:
            return actions

        # Sort by score descending
        all_options.sort(key=lambda x: x[1], reverse=True)

        used = set()
        working_pool = mana_pool.copy()

        for card, score, cast_type, cost, extra in all_options:
            if score < 0:
                continue
            if card.instance_id in used:
                continue
            if not working_pool.can_pay(cost):
                continue

            target = self.find_target(card, board)
            if cast_type != "overload" and self.needs_target(card) and target is None:
                continue

            # Add action with cast type info
            actions.append(("cast", card, target, cast_type, extra))
            used.add(card.instance_id)

            # Deduct mana from working pool
            working_pool.W = max(0, working_pool.W - cost.W)
            working_pool.U = max(0, working_pool.U - cost.U)
            working_pool.B = max(0, working_pool.B - cost.B)
            working_pool.R = max(0, working_pool.R - cost.R)
            working_pool.G = max(0, working_pool.G - cost.G)
            generic = cost.generic
            for color in COLORS:
                if generic <= 0:
                    break
                avail = getattr(working_pool, color)
                deduct = min(avail, generic)
                setattr(working_pool, color, avail - deduct)
                generic -= deduct

        return actions

    def choose_loyalty_ability(self, pw: Card) -> Optional[Tuple[int, str, Any]]:
        """
        Choose which loyalty ability to activate for a planeswalker.
        Returns (ability_index, effect, target) or None if no ability should be used.
        Only call during main phase when stack is empty (sorcery speed).
        """
        if pw.activated_this_turn:
            return None

        if not pw.loyalty_abilities:
            return None

        current_loyalty = pw.current_loyalty()
        board = self.board_eval()

        # Evaluate each ability
        best_choice = None
        best_score = -100

        for i, ability in enumerate(pw.loyalty_abilities):
            cost, effect = parse_loyalty_ability(ability)

            # Can we pay this cost?
            new_loyalty = current_loyalty + cost
            if new_loyalty < 0:
                continue  # Can't activate, would go negative

            score = self._score_loyalty_ability(cost, effect, new_loyalty, board)
            if score > best_score:
                best_score = score
                target = self._find_loyalty_target(effect, board)
                best_choice = (i, effect, target)

        # Only use ability if score is positive
        if best_choice and best_score > 0:
            return best_choice
        return None

    def _score_loyalty_ability(self, cost: int, effect: str, new_loyalty: int, board: Dict) -> float:
        """Score a loyalty ability based on game state."""
        score = 0.0

        # Base scoring for effect type
        if "draw" in effect:
            score += 5.0
        if "damage" in effect:
            score += 4.0 if board["threats"] else 2.0
        if "destroy" in effect:
            score += 6.0 if board["threats"] else 1.0
        if "create_token" in effect:
            score += 4.0
        if "exile" in effect:
            score += 5.0 if board["threats"] else 1.0

        # Adjust based on cost
        if cost > 0:
            # Plus ability - safer, builds loyalty
            score += 2.0
            # Check if we're under pressure (opponent has more power)
            if board.get("opp_power", 0) > board.get("my_power", 0):
                score -= 1.0  # Less safe when under pressure
        elif cost < 0:
            # Minus ability - more powerful but risky
            if new_loyalty <= 1:
                score -= 3.0  # Very risky
            elif new_loyalty <= 2:
                score -= 1.0  # Somewhat risky

            # Ultimate check (big minus abilities)
            if cost <= -5:
                score += 5.0  # Ultimates are usually game-winning

        return score

    def _find_loyalty_target(self, effect: str, board: Dict) -> Any:
        """Find a target for a loyalty ability effect."""
        if "damage" in effect or "destroy" in effect or "exile" in effect:
            if board["threats"]:
                return board["threats"][0][0]  # Best threat
            return "face"
        return None

    def planeswalker_actions(self) -> List[Tuple[Card, int, str, Any]]:
        """
        Get list of planeswalker ability activations for this turn.
        Returns list of (planeswalker, ability_index, effect, target).
        """
        actions = []
        for pw in self.me.planeswalkers():
            if pw.activated_this_turn:
                continue
            choice = self.choose_loyalty_ability(pw)
            if choice:
                ability_idx, effect, target = choice
                actions.append((pw, ability_idx, effect, target))
        return actions


    def should_crew(self, vehicle: Card, available_creatures: List[Card]) -> Optional[List[Card]]:
        """Determine if we should crew a vehicle. Prefers summoning-sick creatures."""
        if not vehicle.is_vehicle() or vehicle.is_tapped or vehicle.is_crewed:
            return None
        crew_cost = vehicle.crew
        if crew_cost <= 0:
            return None
        available = [c for c in available_creatures if not c.is_tapped]
        if not available:
            return None
        sick = [c for c in available if c.summoning_sick and not c.has_keyword("haste")]
        ready = [c for c in available if not c.summoning_sick or c.has_keyword("haste")]

        def find_crew(pool: List[Card], target: int) -> Optional[List[Card]]:
            for c in sorted(pool, key=lambda x: x.eff_power()):
                if c.eff_power() >= target:
                    return [c]
            pool_sorted = sorted(pool, key=lambda x: -x.eff_power())
            total, selected = 0, []
            for c in pool_sorted:
                selected.append(c)
                total += c.eff_power()
                if total >= target:
                    return selected
            return None

        crew_selection = find_crew(sick, crew_cost)
        if crew_selection:
            return crew_selection
        crew_selection = find_crew(ready, crew_cost)
        if crew_selection and vehicle.eff_power() > sum(c.eff_power() for c in crew_selection):
            return crew_selection
        crew_selection = find_crew(sick + ready, crew_cost)
        if crew_selection:
            ready_power = sum(c.eff_power() for c in crew_selection if c in ready)
            if vehicle.eff_power() > ready_power:
                return crew_selection
        return None

    def crew_vehicles(self) -> List[Tuple[Card, List[Card]]]:
        """Decide which vehicles to crew. Returns list of (vehicle, crew_creatures)."""
        vehicles = self.me.vehicles()
        if not vehicles:
            return []
        available = [c for c in self.me.battlefield if c.card_type == "creature" and not c.is_tapped]
        results, used = [], set()
        for v in sorted(vehicles, key=lambda x: -x.eff_power()):
            remaining = [c for c in available if c.instance_id not in used]
            crew_selection = self.should_crew(v, remaining)
            if crew_selection:
                results.append((v, crew_selection))
                used.update(c.instance_id for c in crew_selection)
        return results

    def attackers(self) -> List[Card]:
        available = self.me.attackers_available()
        if not available:
            return []

        board = self.board_eval()
        blockers = [c for c in self.opp.creatures() if not c.is_tapped]

        if board["can_lethal"]:
            return available

        if board["archetype"] == "aggro":
            return available

        result = []
        for a in available:
            if "flying" in a.keywords and not any("flying" in b.keywords or "reach" in b.keywords for b in blockers):
                result.append(a)
            elif "trample" in a.keywords and a.eff_power() >= 4:
                result.append(a)
            elif not blockers:
                result.append(a)
            elif a.eff_power() >= 3:
                result.append(a)

        return result

    def declare_attackers(self) -> Tuple[List[Card], Dict[int, Optional[int]]]:
        """
        Declare attackers and their targets (player or planeswalker).
        Returns:
            - List of attacking creatures
            - Dict mapping attacker instance_id to target:
              - None means attacking the player
              - int (planeswalker instance_id) means attacking that planeswalker
        """
        attackers = self.attackers()
        if not attackers:
            return [], {}

        targets: Dict[int, Optional[int]] = {}
        opp_pws = self.opp.planeswalkers()

        # If opponent has no planeswalkers, all attack player
        if not opp_pws:
            for a in attackers:
                targets[a.instance_id] = None
            return attackers, targets

        # Simple AI: prioritize killing low-loyalty planeswalkers
        # Sort planeswalkers by loyalty (lowest first - easiest to kill)
        pws_by_loyalty = sorted(opp_pws, key=lambda pw: pw.loyalty)

        remaining_attackers = list(attackers)

        for pw in pws_by_loyalty:
            if not remaining_attackers:
                break

            # Assign enough attackers to kill this planeswalker
            pw_loyalty = pw.loyalty
            assigned_power = 0
            assigned_to_pw = []

            for a in remaining_attackers[:]:
                if assigned_power >= pw_loyalty:
                    break
                # Prefer flying creatures for planeswalker attacks (harder to block)
                if a.has_keyword("flying") or a.has_keyword("trample"):
                    assigned_to_pw.append(a)
                    assigned_power += a.eff_power()
                    remaining_attackers.remove(a)

            # If flying/trample not enough, add more
            for a in remaining_attackers[:]:
                if assigned_power >= pw_loyalty:
                    break
                assigned_to_pw.append(a)
                assigned_power += a.eff_power()
                remaining_attackers.remove(a)

            # Assign these attackers to the planeswalker
            for a in assigned_to_pw:
                targets[a.instance_id] = pw.instance_id

        # Remaining attackers go for the player
        for a in remaining_attackers:
            targets[a.instance_id] = None

        return attackers, targets

    def blockers(self, attackers: List[Card], attack_targets: Dict[int, Optional[int]] = None) -> Dict[int, List[int]]:
        """
        Assign blockers to attackers. Returns dict mapping attacker_id to list of blocker_ids.
        Supports gang blocking (multiple blockers on one attacker).
        Handles menace (must be blocked by 2+ creatures).
        """
        blocks: Dict[int, List[int]] = {}
        if not attackers:
            return blocks

        my_blockers = [c for c in self.me.creatures() if not c.is_tapped]
        if not my_blockers:
            return blocks

        # Sort attackers by threat level (power + keywords)
        def threat_score(a: Card) -> float:
            score = a.eff_power()
            if a.has_keyword("trample"):
                score += 3
            if a.has_keyword("lifelink"):
                score += 2
            if a.has_keyword("deathtouch"):
                score += 4
            if a.has_keyword("double strike") or a.has_keyword("double_strike"):
                score += a.eff_power()  # Effectively doubles damage
            if a.has_keyword("menace"):
                score += 1  # Slightly harder to block
            return score

        sorted_att = sorted(attackers, key=threat_score, reverse=True)
        used = set()

        for att in sorted_att:
            has_menace = att.has_keyword("menace")
            att_power = att.eff_power()
            att_tough = att.eff_toughness()

            # Find available blockers
            available = [b for b in my_blockers if b.instance_id not in used]
            if not available:
                continue

            # For menace, we need at least 2 blockers
            if has_menace and len(available) < 2:
                continue  # Can't legally block menace with 1 creature

            # Filter out blockers that can't legally block due to flying/protection
            legal_blockers = []
            for b in available:
                can_block = True
                # Check if attacker has flying - only flying or reach can block
                if att.has_keyword("flying"):
                    if not b.has_keyword("flying") and not b.has_keyword("reach"):
                        can_block = False
                # Check if attacker has protection from this blocker's colors
                if can_block:
                    for kw in att.keywords:
                        kw_lower = kw.lower()
                        if kw_lower.startswith("protection"):
                            prot_from = kw_lower.replace("protection from ", "").replace("protection_", "")
                            color_map = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
                            if prot_from in color_map:
                                protected_color = color_map[prot_from]
                                blocker_colors = b.mana_cost.colors()
                                if protected_color in blocker_colors:
                                    can_block = False
                                    break
                            if prot_from == "everything":
                                can_block = False
                                break
                            if prot_from == "creatures":
                                can_block = False
                                break
                if can_block:
                    legal_blockers.append(b)
            available = legal_blockers
            if not available:
                continue

            assigned_blockers = []

            # Strategy: try to kill the attacker while minimizing losses
            # First pass: find a single blocker that wins the trade
            best_single = None
            best_single_score = -100

            for b in available:
                kills = b.eff_power() >= att_tough or b.has_keyword("deathtouch")
                survives = b.eff_toughness() > att_power and not att.has_keyword("deathtouch")

                score = 0
                if kills and survives:
                    score = 15
                elif kills:
                    score = 8
                elif survives:
                    score = 3
                else:
                    score = -3

                if b.has_keyword("deathtouch"):
                    score += 6
                if b.has_keyword("first strike") or b.has_keyword("first_strike"):
                    score += 3

                score -= b.cmc() * 0.4

                if score > best_single_score:
                    best_single_score = score
                    best_single = b

            # For menace: need at least 2 blockers
            if has_menace:
                # Find best pair of blockers
                if len(available) >= 2:
                    best_pair = None
                    best_pair_score = -100

                    for i, b1 in enumerate(available):
                        for b2 in available[i+1:]:
                            combined_power = b1.eff_power() + b2.eff_power()
                            kills = combined_power >= att_tough or b1.has_keyword("deathtouch") or b2.has_keyword("deathtouch")

                            # Either survives?
                            b1_survives = b1.eff_toughness() > att_power and not att.has_keyword("deathtouch")
                            b2_survives = b2.eff_toughness() > att_power and not att.has_keyword("deathtouch")

                            score = 0
                            if kills:
                                score = 10
                                if b1_survives or b2_survives:
                                    score += 5
                            else:
                                score = -5  # Trading 2 for 1 bad

                            score -= (b1.cmc() + b2.cmc()) * 0.3

                            if score > best_pair_score:
                                best_pair_score = score
                                best_pair = (b1, b2)

                    if best_pair and (best_pair_score > 0 or att_power >= self.me.life):
                        assigned_blockers = list(best_pair)
            else:
                # Non-menace: can use single blocker or gang block
                # Check if gang blocking makes sense (kill big threat with small creatures)
                if att_power >= 4 and best_single_score < 5:
                    # Try gang blocking
                    sorted_available = sorted(available, key=lambda b: b.eff_power(), reverse=True)
                    gang = []
                    total_power = 0
                    for b in sorted_available:
                        gang.append(b)
                        total_power += b.eff_power()
                        if total_power >= att_tough or any(g.has_keyword("deathtouch") for g in gang):
                            break

                    if len(gang) <= 3 and (total_power >= att_tough or any(g.has_keyword("deathtouch") for g in gang)):
                        # Gang block is worth it
                        gang_cost = sum(b.cmc() for b in gang)
                        if gang_cost <= att.cmc() + 2 or att_power >= self.me.life // 2:
                            assigned_blockers = gang

                # Fall back to single blocker if gang block not assigned
                if not assigned_blockers and best_single and (best_single_score > 0 or att_power >= self.me.life):
                    assigned_blockers = [best_single]

            # Assign blockers
            if assigned_blockers:
                blocks[att.instance_id] = [b.instance_id for b in assigned_blockers]
                for b in assigned_blockers:
                    used.add(b.instance_id)

        return blocks

    def should_mulligan(self, hand: List[Card], mulligans_taken: int) -> bool:
        """
        Decide whether to mulligan this hand.
        London mulligan: always draw 7, put X cards back after keeping.
        """
        # Never mull below 4 cards
        if mulligans_taken >= 3:
            return False

        lands = [c for c in hand if c.card_type == "land"]
        spells = [c for c in hand if c.card_type != "land"]
        land_count = len(lands)

        # Critical land count rules
        if land_count == 0:
            return True  # 0 lands = always mull
        if land_count == 1 and mulligans_taken < 2:
            return True  # 1 land = mull unless already at 5 cards
        if land_count >= 6:
            return True  # 6+ lands = always mull
        if land_count == 5 and mulligans_taken < 2:
            return True  # 5 lands = mull unless already low

        # Check for playable spells (can cast with opening lands)
        playable = 0
        available_colors = set()
        for land in lands:
            if land.produces:
                available_colors.update(land.produces)
            else:
                colors = detect_land_colors(land.name)
                available_colors.update(colors)

        for spell in spells:
            if spell.cmc() <= 3:  # Could cast in first few turns
                needed_colors = spell.mana_cost.colors()
                if all(c in available_colors or c == "C" for c in needed_colors):
                    playable += 1

        # Need at least 1-2 playable spells
        if playable == 0 and mulligans_taken < 2:
            return True

        return False

    def choose_cards_to_bottom(self, hand: List[Card], count: int) -> List[Card]:
        """
        Choose which cards to put on the bottom of library after keeping.
        """
        if count <= 0:
            return []

        # Score each card - lower score = put on bottom
        scored = []
        lands = len([c for c in hand if c.card_type == "land"])

        for card in hand:
            score = 0
            if card.card_type == "land":
                # Keep 2-4 lands ideally
                if lands <= 2:
                    score = 100  # Need this land
                elif lands <= 4:
                    score = 50
                else:
                    score = 10  # Excess land
            else:
                # Prefer low-cost playable spells
                score = 20 - card.cmc() * 3
                if card.cmc() <= 2:
                    score += 20
                if card.cmc() >= 5:
                    score -= 10

            scored.append((card, score))

        # Sort by score ascending - bottom the lowest scored cards
        scored.sort(key=lambda x: x[1])

        return [c for c, _ in scored[:count]]

    def scry_decision(self, top_card: Card) -> bool:
        """
        Scry 1: return True to keep on top, False to put on bottom.
        """
        # Keep lands if we need them
        lands_in_hand = len([c for c in self.me.hand if c.card_type == "land"])
        if top_card.card_type == "land":
            if lands_in_hand <= 2:
                return True  # Keep land
            elif lands_in_hand >= 4:
                return False  # Bottom excess land
            return True

        # Keep cheap spells, bottom expensive ones early
        if top_card.cmc() <= 3:
            return True
        if top_card.cmc() >= 5 and len(self.me.hand) <= 5:
            return False

        return True  # Default keep

    # =========================================================================
    # MODAL SPELLS & KICKER AI LOGIC
    # =========================================================================

    def choose_modes(self, card: Card, available_targets: Dict[str, Any]) -> List[str]:
        """
        Choose modes for a modal spell based on board state.
        Returns list of chosen mode strings.
        """
        if not card.modes:
            return []

        num_modes = 2 if card.choose_two else 1
        scored_modes = []

        for mode in card.modes:
            score = self._score_mode(mode, available_targets)
            scored_modes.append((mode, score))

        # Sort by score descending, take top N modes
        scored_modes.sort(key=lambda x: x[1], reverse=True)
        chosen = [m for m, s in scored_modes[:num_modes] if s > 0]

        # If we need 2 modes but only 1 is viable, still return what we have
        if card.choose_two and len(chosen) < 2:
            chosen = [m for m, _ in scored_modes[:2]]

        return chosen if chosen else [scored_modes[0][0]]

    def _score_mode(self, mode: str, targets: Dict[str, Any]) -> float:
        """Score a single mode based on current board state."""
        score = 0.0

        if mode.startswith("damage_"):
            try:
                dmg = int(mode.split("_")[1])
            except:
                dmg = 3
            if self.opp.life <= dmg * 2:
                score += dmg * 2
            else:
                score += dmg * 0.5
            for c in self.opp.creatures():
                if c.eff_toughness() <= dmg:
                    score += c.eff_power() + 2
                    break

        elif mode.startswith("draw_"):
            try:
                n = int(mode.split("_")[1])
            except:
                n = 1
            score += n * 2
            if len(self.me.hand) <= 2:
                score += n * 2

        elif mode.startswith("scry_"):
            try:
                n = int(mode.split("_")[1])
            except:
                n = 1
            score += n * 0.5

        elif mode == "destroy_creature" or mode == "destroy_artifact":
            if mode == "destroy_creature" and self.opp.creatures():
                top_threat = max(self.opp.creatures(), key=lambda c: c.eff_power())
                score += top_threat.eff_power() + 3
            elif mode == "destroy_artifact":
                artifacts = [c for c in self.opp.battlefield if c.card_type == "artifact"]
                if artifacts:
                    score += 3

        elif mode in ["bounce", "return_creature"]:
            if self.opp.creatures():
                top_threat = max(self.opp.creatures(), key=lambda c: c.eff_power())
                score += top_threat.cmc() + 2

        elif mode == "gain_life":
            score += 3 if self.me.life <= 10 else 1

        return score

    def should_kick(self, card: Card, mana_pool: ManaPool) -> bool:
        """Decide whether to pay kicker cost."""
        if not card.kicker:
            return False

        kicker_cost = ManaCost.parse(card.kicker)
        total_cost = card.mana_cost.copy()
        total_cost.add(kicker_cost)

        if not mana_pool.can_pay(total_cost):
            return False

        if card.if_kicked:
            kick_value = 0
            for effect in card.if_kicked:
                if effect.startswith("damage_"):
                    try:
                        kick_value += int(effect.split("_")[1]) * 1.5
                    except:
                        kick_value += 3
                elif effect.startswith("draw_"):
                    try:
                        kick_value += int(effect.split("_")[1]) * 3
                    except:
                        kick_value += 3
                else:
                    kick_value += 2
            if kick_value >= kicker_cost.cmc():
                return True
        return False

    def multikicker_count(self, card: Card, mana_pool: ManaPool) -> int:
        """Determine how many times to pay multikicker."""
        if not card.multikicker:
            return 0

        mk_cost = ManaCost.parse(card.multikicker)
        base_cost = card.mana_cost.copy()
        remaining = mana_pool.copy()

        if not remaining.pay_cost(base_cost):
            return 0

        count = 0
        while count < 5 and remaining.can_pay(mk_cost):
            remaining.pay_cost(mk_cost)
            count += 1
        return count

    # =========================================================================
    # COUNTERSPELL AI LOGIC
    # =========================================================================

    def find_counterspells(self, mana_pool: ManaPool) -> List[Card]:
        """Find castable counterspells from hand"""
        counters = []
        for c in self.me.hand:
            if c.card_type != "instant":
                continue
            if not mana_pool.can_pay(c.mana_cost):
                continue
            has_counter = any(ab.startswith("counter") for ab in c.abilities)
            if has_counter:
                counters.append(c)
        return counters

    def can_counter_target(self, counterspell: Card, target: 'StackItem') -> bool:
        """Check if counterspell can legally counter the target spell"""
        abilities = counterspell.abilities
        if "counter_spell" in abilities:
            return True
        if "counter_creature" in abilities:
            return target.is_creature_spell()
        if "counter_noncreature" in abilities:
            return target.is_noncreature_spell()
        if "counter_unless" in abilities:
            return True
        return False

    def get_counter_cost(self, counterspell: Card) -> int:
        """Get the 'unless pay' cost for conditional counters (0 = hard counter)"""
        for ab in counterspell.abilities:
            if ab.startswith("counter_unless_"):
                try:
                    return int(ab.split("_")[-1])
                except ValueError:
                    pass
        if "counter_unless" in counterspell.abilities:
            cmc = counterspell.cmc()
            return 2 if cmc <= 1 else (3 if cmc == 2 else 4)
        return 0

    def opponent_can_pay(self, amount: int) -> bool:
        """Check if opponent has enough untapped mana to pay"""
        return self.opp.available_mana().total() >= amount

    def score_spell_threat(self, stack_item: 'StackItem') -> float:
        """Score how threatening a spell is (higher = more worth countering)"""
        card = stack_item.card
        score = 0.0
        if card.card_type == "creature":
            score = card.eff_power() + card.eff_toughness() * 0.5
            if card.has_keyword("haste"): score += 3
            if card.has_keyword("flying"): score += 2
            if card.has_keyword("hexproof"): score += 4
            if card.has_keyword("indestructible"): score += 5
        elif card.card_type == "planeswalker":
            score = 8 + card.loyalty * 0.5
        elif card.card_type in ["instant", "sorcery"]:
            if any(ab in ["destroy_creature", "exile"] for ab in card.abilities):
                my_best = max((c.eff_power() for c in self.me.creatures()), default=0)
                score = 4 + my_best * 0.5
            if any("draw" in ab for ab in card.abilities):
                score = max(score, 3)
            if any("sweep" in ab for ab in card.abilities):
                score = max(score, 10)
        score += card.cmc() * 0.3
        return score

    def should_counter(self, counterspell: Card, stack_item: 'StackItem') -> bool:
        """Decide whether to counter a spell"""
        if not self.can_counter_target(counterspell, stack_item):
            return False
        threat_score = self.score_spell_threat(stack_item)
        counter_cost = self.get_counter_cost(counterspell)
        if counter_cost > 0 and self.opponent_can_pay(counter_cost) and threat_score < 6:
            return False
        if threat_score >= 5:
            return True
        if self.me.archetype == "control" and threat_score >= 3:
            return True
        board = self.board_eval()
        if board["opp_power"] > board["my_power"] and threat_score >= 4:
            return True
        return threat_score >= 6

    def choose_counter_response(self, stack_item: 'StackItem', mana_pool: ManaPool) -> Optional[Tuple[Card, 'StackItem']]:
        """Choose whether and which counterspell to use"""
        counterspells = self.find_counterspells(mana_pool)
        if not counterspells:
            return None
        best_counter = None
        best_score = -100
        for counter in counterspells:
            if not self.can_counter_target(counter, stack_item):
                continue
            if not self.should_counter(counter, stack_item):
                continue
            score = 10 - counter.cmc()
            if self.get_counter_cost(counter) == 0:
                score += 3
            elif not self.opponent_can_pay(self.get_counter_cost(counter)):
                score += 2
            if score > best_score:
                best_score = score
                best_counter = counter
        return (best_counter, stack_item) if best_counter else None

    def should_pay_counter_cost(self, cost: int) -> bool:
        """Decide whether to pay the cost to prevent being countered"""
        mana = self.me.available_mana()
        return mana.total() >= cost

    def should_respond(self, stack: List['StackItem'], mana_pool: ManaPool) -> Optional[Tuple[Card, Any]]:
        """
        Decide whether to respond to something on the stack with an instant-speed spell.
        Checks for instants, flash creatures, and activated abilities.
        Returns (spell, target) if should respond, None otherwise.
        """
        if not stack:
            return None

        top_item = stack[-1]  # Look at top of stack

        # First, check for counterspells (handled by choose_counter_response)
        counter_response = self.choose_counter_response(top_item, mana_pool)
        if counter_response:
            return counter_response

        # Check for instant-speed removal or combat tricks
        instants = self.find_instants(mana_pool)
        flash_creatures = self.find_flash_creatures(mana_pool)

        # If opponent is casting a big creature or threat, consider flash response
        if top_item.card.card_type == "creature":
            threat_power = top_item.card.eff_power()

            # Deploy flash creature if opponent cast a threat and we want blockers
            if flash_creatures and threat_power >= 3:
                # Evaluate if flashing in a creature makes sense
                best_flash = None
                best_value = 0
                for fc in flash_creatures:
                    value = fc.eff_power() + fc.eff_toughness()
                    if value > best_value:
                        best_value = value
                        best_flash = fc
                # Only flash in if it's a decent response
                if best_flash and best_value >= 3:
                    return (best_flash, None)

        # Check for removal instants we might want to hold
        # (Most removal targets permanents, which aren't valid while on stack)

        return None

    def find_activated_abilities(self, mana_pool: ManaPool) -> List[Tuple[Card, str]]:
        """
        Find activated abilities that can be activated at instant speed.
        Returns list of (permanent, ability_string) tuples.
        Excludes mana abilities (they don't use the stack).
        """
        abilities = []
        for permanent in self.me.battlefield:
            # Skip tapped creatures for most activated abilities
            if permanent.is_tapped and permanent.card_type == "creature":
                continue

            for ab in permanent.abilities:
                # Look for costed abilities (format: "cost:effect")
                if ":" in ab:
                    parts = ab.split(":")
                    if len(parts) >= 2:
                        cost_str = parts[0].strip()
                        # Skip mana abilities (they don't use stack)
                        if "add_" in parts[1].lower() or "mana" in parts[1].lower():
                            continue
                        # Check if we can pay (simplified - just check if it needs tap)
                        if "T" in cost_str or "tap" in cost_str.lower():
                            if permanent.is_tapped:
                                continue
                        abilities.append((permanent, ab))

        return abilities


# =============================================================================
# GAME ENGINE
# =============================================================================

class Game:
    def __init__(self, cards1: List[Card], name1: str, arch1: str,
                 cards2: List[Card], name2: str, arch2: str, verbose: bool = True):
        self.log = Log(verbose)
        self.next_id = 1
        self.next_stack_id = 1
        self.stack: List[StackItem] = []  # The spell stack (LIFO)
        self.trigger_queue: List[Tuple[str, Card, Player, Any]] = []  # (trigger_type, source, controller, data)
        self.replacement_effects: List[ReplacementEffect] = []  # Active replacement effects (Rule 614)
        self.control_manager = ControlChangeManager(self)  # Control-changing effects (Layer 2)
        self.layer_system = LayerSystem(self)  # Continuous effects layer system (Rule 613)

        self.p1 = Player(1, name1, arch1)
        self.p2 = Player(2, name2, arch2)

        for c in cards1:
            card = c.copy()
            card.instance_id = self.next_id
            card.controller = 1
            card.owner = 1  # Owner is set at game start and never changes
            self.next_id += 1
            self.p1.library.append(card)
        
        for c in cards2:
            card = c.copy()
            card.instance_id = self.next_id
            card.controller = 2
            card.owner = 2  # Owner is set at game start and never changes
            self.next_id += 1
            self.p2.library.append(card)
        
        random.shuffle(self.p1.library)
        random.shuffle(self.p2.library)
        
        self.turn = 0
        self.active_id = 1
        self.winner = None
    
    def active(self) -> Player:
        return self.p1 if self.active_id == 1 else self.p2
    
    def opponent(self) -> Player:
        return self.p2 if self.active_id == 1 else self.p1

    # =========================================================================
    # REPLACEMENT EFFECTS SYSTEM (MTG Rule 614)
    # =========================================================================

    def register_replacement_effect(self, effect: ReplacementEffect) -> None:
        """Register a replacement effect to be checked for future events."""
        self.replacement_effects.append(effect)
        self.log.log(f"    [Replacement] Registered: {effect.description}")

    def unregister_replacement_effect(self, source: Card) -> None:
        """Remove all replacement effects from a source (when it leaves play)."""
        before_count = len(self.replacement_effects)
        self.replacement_effects = [
            e for e in self.replacement_effects
            if e.source.instance_id != source.instance_id
        ]
        removed = before_count - len(self.replacement_effects)
        if removed > 0:
            self.log.log(f"    [Replacement] Removed {removed} effect(s) from {source.name}")

    def process_event_with_replacements(self, event: GameEvent, affected_player: Player) -> GameEvent:
        """
        Process an event through all applicable replacement effects.
        Per MTG Rule 614: self-replacements first, then affected player chooses order.
        """
        max_iterations = 20
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            applicable: List[ReplacementEffect] = []
            for effect in self.replacement_effects:
                if effect.applies_to(event, self):
                    applicable.append(effect)
            if not applicable:
                break
            self_replacements = [
                e for e in applicable
                if e.self_replacement and event.card and e.source.instance_id == event.card.instance_id
            ]
            other_replacements = [e for e in applicable if e not in self_replacements]
            for effect in self_replacements:
                event = effect.apply(event, self)
                self.log.log(f"    [Replacement] Applied (self): {effect.description}")
                if event.is_cancelled:
                    return event
            if other_replacements:
                other_replacements.sort(
                    key=lambda e: (0 if e.controller_id == affected_player.player_id else 1, e.source.instance_id)
                )
                effect = other_replacements[0]
                event = effect.apply(event, self)
                self.log.log(f"    [Replacement] Applied: {effect.description}")
                if event.is_cancelled:
                    return event
        if iteration >= max_iterations:
            self.log.log(f"    [Warning] Replacement effect loop limit reached")
        return event

    def create_die_event(self, creature: Card, controller: Player, destination: str = "graveyard") -> GameEvent:
        """Create a 'die' event for a creature/permanent about to die."""
        return GameEvent(event_type='die', card=creature, controller=controller,
                        origin_zone='battlefield', destination_zone=destination)

    def create_etb_event(self, card: Card, controller: Player, source: Optional[Card] = None) -> GameEvent:
        """Create an ETB event for a permanent about to enter the battlefield."""
        return GameEvent(event_type='etb', card=card, controller=controller, source=source,
                        origin_zone='stack' if card.card_type not in ['land'] else 'hand',
                        destination_zone='battlefield')

    def create_draw_event(self, player: Player, count: int = 1, source: Optional[Card] = None) -> GameEvent:
        """Create a draw event for a player about to draw cards."""
        return GameEvent(event_type='draw', player=player, source=source, draw_count=count)

    def create_damage_event(self, source: Card, target: Any, amount: int) -> GameEvent:
        """Create a damage event for damage about to be dealt."""
        target_player = target if isinstance(target, Player) else None
        target_card = target if isinstance(target, Card) else None
        return GameEvent(event_type='damage', source=source, card=target_card,
                        player=target_player, damage_target=target, damage_amount=amount)

    def create_discard_event(self, card: Card, player: Player, source: Optional[Card] = None) -> GameEvent:
        """Create a discard event for a card about to be discarded."""
        return GameEvent(event_type='discard', card=card, player=player, source=source,
                        origin_zone='hand', destination_zone='graveyard')

    def create_rest_in_peace_effect(self, source: Card, controller_id: int) -> ReplacementEffect:
        """Rest in Peace: exile instead of graveyard."""
        def condition(event: GameEvent, game: 'Game') -> bool:
            return event.destination_zone == 'graveyard' and event.card is not None
        def replacement(event: GameEvent, game: 'Game') -> GameEvent:
            event.destination_zone = 'exile'
            return event
        return ReplacementEffect(source=source, effect_id=f"{source.instance_id}_rest_in_peace",
            event_type='die', condition=condition, replacement=replacement,
            self_replacement=False, controller_id=controller_id,
            description=f"{source.name}: exile instead of graveyard")

    def create_leyline_of_the_void_effect(self, source: Card, controller_id: int) -> ReplacementEffect:
        """Leyline of the Void: exile opponent's cards instead of graveyard."""
        def condition(event: GameEvent, game: 'Game') -> bool:
            if event.destination_zone != 'graveyard' or event.card is None:
                return False
            if event.controller is None:
                return False
            return event.controller.player_id != controller_id
        def replacement(event: GameEvent, game: 'Game') -> GameEvent:
            event.destination_zone = 'exile'
            return event
        return ReplacementEffect(source=source, effect_id=f"{source.instance_id}_leyline_void",
            event_type='die', condition=condition, replacement=replacement,
            self_replacement=False, controller_id=controller_id,
            description=f"{source.name}: exile opponent's cards instead of graveyard")

    def create_panharmonicon_effect(self, source: Card, controller_id: int) -> ReplacementEffect:
        """Panharmonicon: ETB triggers twice for artifacts/creatures."""
        def condition(event: GameEvent, game: 'Game') -> bool:
            if event.event_type != 'etb' or event.card is None:
                return False
            if event.card.card_type not in ['artifact', 'creature']:
                return False
            if event.controller is None or event.controller.player_id != controller_id:
                return False
            return True
        def replacement(event: GameEvent, game: 'Game') -> GameEvent:
            event.etb_trigger_count += 1
            return event
        return ReplacementEffect(source=source, effect_id=f"{source.instance_id}_panharmonicon",
            event_type='etb', condition=condition, replacement=replacement,
            self_replacement=False, controller_id=controller_id,
            description=f"{source.name}: ETB triggers twice for artifacts/creatures")

    def create_damage_prevention_effect(self, source: Card, controller_id: int,
                                        prevent_amount: int = -1) -> ReplacementEffect:
        """Damage prevention effect. -1 means prevent all."""
        def condition(event: GameEvent, game: 'Game') -> bool:
            return event.event_type == 'damage' and event.damage_amount > 0
        def replacement(event: GameEvent, game: 'Game') -> GameEvent:
            if prevent_amount == -1:
                event.damage_amount = 0
            else:
                event.damage_amount = max(0, event.damage_amount - prevent_amount)
            return event
        desc = "prevent all damage" if prevent_amount == -1 else f"prevent {prevent_amount} damage"
        return ReplacementEffect(source=source, effect_id=f"{source.instance_id}_damage_prevent",
            event_type='damage', condition=condition, replacement=replacement,
            self_replacement=False, controller_id=controller_id, description=f"{source.name}: {desc}")

    def create_damage_doubling_effect(self, source: Card, controller_id: int) -> ReplacementEffect:
        """Damage doubling effect (like Furnace of Rath)."""
        def condition(event: GameEvent, game: 'Game') -> bool:
            return event.event_type == 'damage' and event.damage_amount > 0
        def replacement(event: GameEvent, game: 'Game') -> GameEvent:
            event.damage_amount *= 2
            return event
        return ReplacementEffect(source=source, effect_id=f"{source.instance_id}_damage_double",
            event_type='damage', condition=condition, replacement=replacement,
            self_replacement=False, controller_id=controller_id,
            description=f"{source.name}: double all damage")

    # =========================================================================
    # CARD DRAWING
    # =========================================================================

    def draw(self, player: Player, n: int = 1) -> bool:
        """
        Draw n cards from player's library.
        If library is empty when drawing, mark for SBA check (player loses).
        Returns False if drawing failed (empty library).
        """
        for _ in range(n):
            if not player.library:
                # Per MTG rules: attempting to draw from empty library is SBA loss
                player.attempted_draw_from_empty = True
                self.log.log(f"  P{player.player_id} cannot draw - library empty!")
                return False
            player.hand.append(player.library.pop(0))
        return True
    
    def deal_hands(self):
        """
        London Mulligan implementation:
        1. Draw 7 cards
        2. Decide to keep or mulligan
        3. If mulligan: shuffle hand back, draw 7 new cards
        4. After keeping: put X cards on bottom (X = mulligans taken)
        5. If mulliganed at all: scry 1
        """
        self._mulligan_player(self.p1)
        self._mulligan_player(self.p2)

    def _mulligan_player(self, player: Player):
        """Handle mulligan decisions for one player"""
        mulligans = 0
        max_mulligans = 3  # Down to 4 cards

        # Create a temporary AI for mulligan decisions
        other = self.p2 if player.player_id == 1 else self.p1
        ai = AI(player, other, self.log)

        while mulligans <= max_mulligans:
            # Draw 7 cards
            player.hand = []
            for _ in range(7):
                if player.library:
                    player.hand.append(player.library.pop(0))

            # Check if should mulligan
            if ai.should_mulligan(player.hand, mulligans):
                self.log.log(f"  P{player.player_id} mulligans (#{mulligans + 1})")
                # Put hand back and shuffle
                player.library.extend(player.hand)
                player.hand = []
                random.shuffle(player.library)
                mulligans += 1
            else:
                break

        # After keeping, put cards on bottom
        if mulligans > 0:
            to_bottom = ai.choose_cards_to_bottom(player.hand, mulligans)
            for card in to_bottom:
                player.hand.remove(card)
                player.library.append(card)  # Put on bottom
            self.log.log(f"  P{player.player_id} keeps {len(player.hand)} (put {mulligans} on bottom)")

            # Scry 1 after mulligan
            if player.library:
                top_card = player.library[0]
                keep_on_top = ai.scry_decision(top_card)
                if not keep_on_top:
                    player.library.pop(0)
                    player.library.append(top_card)
                    self.log.log(f"  P{player.player_id} scrys {top_card.name} to bottom")
                else:
                    self.log.log(f"  P{player.player_id} scrys {top_card.name} to top")
        else:
            self.log.log(f"  P{player.player_id} keeps 7")
    
    def tap_lands(self, player: Player, n: int):
        tapped = 0
        for c in player.battlefield:
            if c.card_type == "land" and not c.is_tapped and tapped < n:
                c.is_tapped = True
                tapped += 1

    def activate_mana_ability(self, card: Card, player: Player, color_choice: str = None) -> bool:
        """
        Activate a mana ability on a card (mana dork).
        Mana abilities don't use the stack - they resolve immediately.

        Args:
            card: The creature with the mana ability
            player: The controlling player
            color_choice: For 'tap_for_any', which color to produce

        Returns:
            True if mana was added, False if activation failed
        """
        if card.is_tapped:
            return False
        if card.card_type == "creature" and card.summoning_sick and not card.has_keyword("haste"):
            return False

        produces = player.mana_dork_produces(card)
        if not produces:
            return False

        # Tap the creature
        card.is_tapped = True

        # Add mana to pool
        if "any" in produces:
            # For 'tap_for_any', use color_choice or default to G
            color = color_choice.upper() if color_choice else "G"
            if color in COLORS:
                player.mana_pool.add(color)
            else:
                player.mana_pool.add("G")
        else:
            # Add first color the dork produces
            for color in produces:
                if color in COLORS:
                    player.mana_pool.add(color)
                    break  # Most dorks only add 1 mana

        return True

    def tap_mana_sources_for_cost(self, player: Player, cost: ManaCost) -> bool:
        """
        Tap lands and mana dorks to pay for a spell cost.
        Adds mana to the player's mana pool, then pays the cost.
        Returns True if cost was paid successfully.
        """
        # First, fill the mana pool from all untapped sources
        # Tap lands first
        for land in player.untapped_lands():
            if land.produces:
                player.mana_pool.add(land.produces[0])
            else:
                colors = detect_land_colors(land.name)
                if colors and colors[0] != "C":
                    player.mana_pool.add(colors[0])
                else:
                    player.mana_pool.C += 1
            land.is_tapped = True

        # Tap mana dorks
        for dork in player.untapped_mana_dorks():
            produces = player.mana_dork_produces(dork)
            if produces and produces[0] != "any":
                player.mana_pool.add(produces[0])
            elif produces:
                # 'any' color - pick based on what's still needed
                player.mana_pool.add("G")
            dork.is_tapped = True

        # Pay the cost from the pool
        return player.mana_pool.pay_cost(cost)

    # =========================================================================
    # TRIGGER SYSTEM
    # =========================================================================

    def queue_trigger(self, trigger_type: str, source: Card, controller: Player, data: Any = None):
        """Add a trigger to the queue"""
        self.trigger_queue.append((trigger_type, source, controller, data))

    def process_triggers(self):
        """Process all queued triggers in APNAP order (CR 603.3b)"""
        if not self.trigger_queue:
            return

        # Get active player (whose turn it is)
        active_player = self.active()

        # Sort by APNAP: Active player's triggers first (go on stack first, resolve last)
        def apnap_order(trigger):
            trigger_type, source, controller, data = trigger
            # Active player = 0, Non-active = 1 (lower goes on stack first)
            return 0 if controller == active_player else 1

        sorted_triggers = sorted(self.trigger_queue, key=apnap_order)
        self.trigger_queue.clear()

        # Process in APNAP order
        for trigger_type, source, controller, data in sorted_triggers:
            self._resolve_trigger(trigger_type, source, controller, data)

    def _resolve_trigger(self, trigger_type: str, source: Card, controller: Player, data: Any):
        """Resolve a single trigger"""
        opp = self.p2 if controller.player_id == 1 else self.p1

        # Check source abilities for matching triggers
        for ab in source.abilities:
            ab_lower = ab.lower()

            # ETB triggers
            if trigger_type == "etb":
                if "etb_" in ab_lower or ab_lower.startswith("enters_"):
                    self._process_etb_trigger(ab, source, controller, opp)

            # Dies triggers
            elif trigger_type == "dies":
                if "dies_" in ab_lower or "death_" in ab_lower:
                    self._process_dies_trigger(ab, source, controller, opp)

            # Attack triggers
            elif trigger_type == "attack":
                if "attack_" in ab_lower or "attacks_" in ab_lower:
                    self._process_attack_trigger(ab, source, controller, opp)

            # Landfall triggers
            elif trigger_type == "landfall":
                if "landfall" in ab_lower:
                    self._process_landfall_trigger(ab, source, controller, opp, data)

            # Prowess / spell cast triggers
            elif trigger_type == "spell_cast":
                if "prowess" in ab_lower:
                    source.counters["+1/+1_temp"] = source.counters.get("+1/+1_temp", 0) + 1
                    source.power += 1
                    source.toughness += 1
                    self.log.log(f"    Prowess! {source.name} gets +1/+1")

        # Saga chapter triggers (not ability-based, uses chapters list)
        if trigger_type == "saga_chapter":
            self._process_saga_chapter(source, controller, opp, data)

    def _process_saga_chapter(self, saga: Card, controller: Player, opp: Player, chapter: int):
        """Process a saga chapter ability when it triggers"""
        if not saga.is_saga() or chapter < 1 or chapter > len(saga.chapters):
            return

        chapter_ability = saga.chapters[chapter - 1]
        self.log.log(f"    Saga: {saga.name} Chapter {chapter} - {chapter_ability}")

        # Process the chapter ability using the same ability processing system
        self._process_ability(chapter_ability, controller, opp, saga, None)

        # Check if final chapter - saga will be sacrificed after it resolves
        if chapter >= saga.final_chapter():
            self._sacrifice_saga(saga, controller)

    def _sacrifice_saga(self, saga: Card, controller: Player):
        """Sacrifice a saga after its final chapter resolves"""
        if saga in controller.battlefield:
            controller.battlefield.remove(saga)
            controller.graveyard.append(saga)
            self.log.log(f"    {saga.name} completes its story and is sacrificed")

    def _process_etb_trigger(self, ab: str, source: Card, controller: Player, opp: Player):
        """Handle ETB (enters the battlefield) triggers"""
        ab_lower = ab.lower()

        # ETB draw
        if "etb_draw" in ab_lower or "enters_draw" in ab_lower:
            try:
                n = int(ab.split("_")[-1]) if ab[-1].isdigit() else 1
            except:
                n = 1
            for _ in range(n):
                if controller.library:
                    drawn = controller.library.pop(0)
                    controller.hand.append(drawn)
                    self.log.log(f"    ETB: {source.name} draws {drawn.name}")

        # ETB damage
        elif "etb_damage" in ab_lower:
            try:
                dmg = int(ab.split("_")[-1])
            except:
                dmg = 2
            opp.life -= dmg
            self.log.log(f"    ETB: {source.name} deals {dmg} to P{opp.player_id}")

        # ETB create token
        elif "etb_token" in ab_lower:
            try:
                parts = ab.split("_")
                p, t = int(parts[-2]), int(parts[-1])
            except:
                p, t = 1, 1
            self.create_token(controller, p, t, "Token")

        # ETB gain life
        elif "etb_life" in ab_lower or "etb_gain" in ab_lower:
            try:
                life = int(ab.split("_")[-1])
            except:
                life = 2
            controller.life += life
            self.log.log(f"    ETB: {source.name} gains {life} life")

        # ETB +1/+1 counter
        elif "etb_counter" in ab_lower:
            source.counters["+1/+1"] = source.counters.get("+1/+1", 0) + 1
            self.log.log(f"    ETB: {source.name} gets +1/+1 counter")

    def _process_dies_trigger(self, ab: str, source: Card, controller: Player, opp: Player):
        """Handle dies triggers"""
        ab_lower = ab.lower()

        # Dies draw
        if "dies_draw" in ab_lower or "death_draw" in ab_lower:
            if controller.library:
                drawn = controller.library.pop(0)
                controller.hand.append(drawn)
                self.log.log(f"    Dies: {source.name} draws {drawn.name}")

        # Dies create token
        elif "dies_token" in ab_lower:
            try:
                parts = ab.split("_")
                p, t = int(parts[-2]), int(parts[-1])
            except:
                p, t = 1, 1
            self.create_token(controller, p, t, "Spirit")

        # Dies damage
        elif "dies_damage" in ab_lower:
            try:
                dmg = int(ab.split("_")[-1])
            except:
                dmg = 2
            opp.life -= dmg
            self.log.log(f"    Dies: {source.name} deals {dmg}")

    def _process_attack_trigger(self, ab: str, source: Card, controller: Player, opp: Player):
        """Handle attack triggers"""
        ab_lower = ab.lower()

        # Attack draw
        if "attack_draw" in ab_lower or "attacks_draw" in ab_lower:
            if controller.library:
                drawn = controller.library.pop(0)
                controller.hand.append(drawn)
                self.log.log(f"    Attacks: {source.name} draws {drawn.name}")

        # Attack damage
        elif "attack_damage" in ab_lower:
            try:
                dmg = int(ab.split("_")[-1])
            except:
                dmg = 1
            opp.life -= dmg
            self.log.log(f"    Attacks: {source.name} deals {dmg}")

        # Attack +1/+1 until EOT
        elif "attack_pump" in ab_lower:
            source.counters["+1/+1_temp"] = source.counters.get("+1/+1_temp", 0) + 1
            source.power += 1
            source.toughness += 1
            self.log.log(f"    Attacks: {source.name} gets +1/+1")

    def _process_landfall_trigger(self, ab: str, source: Card, controller: Player, opp: Player, land: Card):
        """Handle landfall triggers"""
        ab_lower = ab.lower()

        # Landfall +1/+1 counter
        if "landfall_counter" in ab_lower:
            source.counters["+1/+1"] = source.counters.get("+1/+1", 0) + 1
            self.log.log(f"    Landfall: {source.name} gets +1/+1 counter")

        # Landfall +2/+2 until EOT
        elif "landfall_pump" in ab_lower:
            source.power += 2
            source.toughness += 2
            source.counters["+2/+2_temp"] = 1
            self.log.log(f"    Landfall: {source.name} gets +2/+2")

        # Landfall create token
        elif "landfall_token" in ab_lower:
            self.create_token(controller, 1, 1, "Plant")

        # Landfall gain life
        elif "landfall_life" in ab_lower:
            controller.life += 1
            self.log.log(f"    Landfall: gain 1 life")

        # Landfall draw
        elif "landfall_draw" in ab_lower:
            if controller.library:
                drawn = controller.library.pop(0)
                controller.hand.append(drawn)
                self.log.log(f"    Landfall: draws {drawn.name}")

    def fire_etb(self, creature: Card, controller: Player):
        """
        Fire ETB triggers for a creature entering the battlefield.
        Uses the replacement effects system to check for trigger modifiers (Panharmonicon, etc.)
        """
        # Create ETB event and process through replacement effects
        etb_event = self.create_etb_event(creature, controller)
        processed_event = self.process_event_with_replacements(etb_event, controller)

        # If event was cancelled, don't fire triggers
        if processed_event.is_cancelled:
            return

        # Determine how many times to queue the trigger (Panharmonicon effect)
        trigger_count = processed_event.etb_trigger_count

        for c in controller.battlefield:
            if any("etb" in ab.lower() or "enters" in ab.lower() for ab in c.abilities):
                if c.instance_id == creature.instance_id:
                    # Queue trigger multiple times if Panharmonicon-style effect is active
                    for _ in range(trigger_count):
                        self.queue_trigger("etb", c, controller, creature)

    def fire_dies(self, creature: Card, controller: Player, last_known_info: dict = None):
        """Fire dies triggers with last known information (CR 603.10)"""
        if last_known_info is None:
            # Capture current state as last known (fallback)
            # Note: In proper implementation, this should have been captured BEFORE moving zones
            all_bf = self.p1.battlefield + self.p2.battlefield
            p, t, kws = self.get_creature_with_bonuses(creature, all_bf)
            last_known_info = {
                'power': p,
                'toughness': t,
                'keywords': kws,
                'counters': creature.counters.copy()
            }

        # Queue trigger with last known info
        self.queue_trigger("dies", creature, controller, last_known_info)
        # Handle auras/equipment attached to this creature
        self.handle_creature_death_attachments(creature, controller)

        # Handle persist: returns with -1/-1 counter if no -1/-1 counters on it
        if creature.has_keyword("persist"):
            minus_counters = creature.counters.get("-1/-1", 0)
            if minus_counters == 0:
                # Return creature from graveyard to battlefield with -1/-1 counter
                if creature in controller.graveyard:
                    controller.graveyard.remove(creature)
                    creature.damage_marked = 0
                    creature.deathtouch_damage = False
                    creature.summoning_sick = True
                    creature.is_tapped = False
                    creature.counters["-1/-1"] = 1
                    controller.battlefield.append(creature)
                    self.log.log(f"    Persist: {creature.name} returns with -1/-1 counter")
                    self.fire_etb(creature, controller)

        # Handle undying: returns with +1/+1 counter if no +1/+1 counters on it
        elif creature.has_keyword("undying"):
            plus_counters = creature.counters.get("+1/+1", 0)
            if plus_counters == 0:
                # Return creature from graveyard to battlefield with +1/+1 counter
                if creature in controller.graveyard:
                    controller.graveyard.remove(creature)
                    creature.damage_marked = 0
                    creature.deathtouch_damage = False
                    creature.summoning_sick = True
                    creature.is_tapped = False
                    creature.counters["+1/+1"] = 1
                    controller.battlefield.append(creature)
                    self.log.log(f"    Undying: {creature.name} returns with +1/+1 counter")
                    self.fire_etb(creature, controller)

    def fire_attack(self, attacker: Card, controller: Player):
        """Fire attack triggers"""
        if any("attack" in ab.lower() for ab in attacker.abilities):
            self.queue_trigger("attack", attacker, controller, None)

    def fire_landfall(self, land: Card, controller: Player):
        """Fire landfall triggers for all creatures with landfall"""
        for c in controller.battlefield:
            if c.card_type == "creature" and any("landfall" in ab.lower() for ab in c.abilities):
                self.queue_trigger("landfall", c, controller, land)

    def fire_spell_cast(self, spell: Card, controller: Player):
        """Fire spell cast triggers (prowess, etc.)"""
        if spell.card_type not in ["creature", "land"]:
            for c in controller.battlefield:
                if c.card_type == "creature" and any("prowess" in ab.lower() for ab in c.abilities):
                    self.queue_trigger("spell_cast", c, controller, spell)

    # =========================================================================
    # AURA & EQUIPMENT SYSTEM
    # =========================================================================

    def equip(self, equipment: Card, creature: Card, player: Player) -> bool:
        """
        Equip an equipment to a creature. Activated ability at sorcery speed.

        Args:
            equipment: The equipment card (must be on player's battlefield)
            creature: The creature to equip (must be on player's battlefield)
            player: The player who controls the equipment

        Returns:
            True if equip succeeded, False otherwise
        """
        # Validate equipment is on battlefield and is equipment
        if equipment not in player.battlefield:
            self.log.log(f"    Cannot equip - {equipment.name} not on battlefield")
            return False
        if not equipment.is_equipment():
            self.log.log(f"    Cannot equip - {equipment.name} is not equipment")
            return False

        # Validate creature is on player's battlefield
        if creature not in player.battlefield or creature.card_type != "creature":
            self.log.log(f"    Cannot equip - {creature.name} not a valid target")
            return False

        # Check equip cost
        equip_cost = ManaCost.parse(equipment.equip_cost)
        available = player.available_mana()
        if not available.can_pay(equip_cost):
            self.log.log(f"    Cannot equip - insufficient mana (need {equipment.equip_cost})")
            return False

        # Pay the equip cost
        self._tap_lands_for_cost(player, equip_cost)

        # Detach from current creature if equipped
        equipment.attached_to = creature.instance_id
        self.log.log(f"    {equipment.name} equipped to {creature.name}")
        return True

    def crew_vehicle(self, player: Player, vehicle: Card, creatures: List[Card]) -> bool:
        """
        Crew a vehicle with the specified creatures. Tap creatures, vehicle becomes creature.
        """
        if not vehicle.is_vehicle():
            self.log.log(f"    Cannot crew - {vehicle.name} is not a vehicle")
            return False
        if vehicle not in player.battlefield:
            self.log.log(f"    Cannot crew - {vehicle.name} not on battlefield")
            return False
        if vehicle.is_crewed:
            self.log.log(f"    {vehicle.name} is already crewed")
            return False
        total_power = sum(c.eff_power() for c in creatures)
        if total_power < vehicle.crew:
            self.log.log(f"    Cannot crew - need {vehicle.crew} power, have {total_power}")
            return False
        for c in creatures:
            if c not in player.battlefield or c.card_type != "creature":
                self.log.log(f"    Cannot crew - {c.name} not a valid crew member")
                return False
            c.is_tapped = True
        vehicle.is_crewed = True
        crew_names = [c.name for c in creatures]
        self.log.log(f"    {vehicle.name} crewed by {crew_names}")
        return True


    def handle_creature_death_attachments(self, creature: Card, controller: Player):
        """
        Handle attachments when a creature dies.
        - Auras go to graveyard (or hand if return_to_hand)
        - Equipment stays on battlefield unattached
        """
        for card in list(controller.battlefield):
            if card.attached_to == creature.instance_id:
                card.attached_to = None  # Unattach

                if card.is_aura():
                    controller.battlefield.remove(card)
                    if card.return_to_hand:
                        controller.hand.append(card)
                        self.log.log(f"    {card.name} returns to hand")
                    else:
                        controller.graveyard.append(card)
                        self.log.log(f"    {card.name} goes to graveyard")
                elif card.is_equipment():
                    # Equipment stays on battlefield, just unattached
                    self.log.log(f"    {card.name} becomes unattached")

        # Also check opponent's battlefield for auras they control on this creature
        opp = self.opponent() if controller == self.active() else self.active()
        for card in list(opp.battlefield):
            if card.attached_to == creature.instance_id:
                card.attached_to = None
                if card.is_aura():
                    opp.battlefield.remove(card)
                    if card.return_to_hand:
                        opp.hand.append(card)
                        self.log.log(f"    {card.name} returns to hand")
                    else:
                        opp.graveyard.append(card)
                        self.log.log(f"    {card.name} goes to graveyard")

    def get_creature_with_bonuses(self, creature: Card, battlefield: List[Card]) -> Tuple[int, int, List[str]]:
        """
        Get a creature's effective power/toughness including all continuous effects.

        This method uses the Layer System (Rule 613) when active effects exist,
        otherwise falls back to the simpler attachment-based calculation.

        The layer system applies effects in order:
        - Layer 7a: Characteristic-defining abilities (Tarmogoyf)
        - Layer 7b: Set P/T to specific value (Ovinize, Turn to Frog)
        - Layer 7c: +1/+1 and -1/-1 counters
        - Layer 7d: Effects that modify P/T (+2/+2 from equipment, anthems)
        - Layer 7e: P/T switching effects

        Returns:
            Tuple of (effective_power, effective_toughness, all_keywords)
        """
        # Check if there are any active layer effects
        if self.layer_system.effects:
            # Use the full layer system for characteristic calculation
            chars = self.layer_system.calculate_characteristics(creature)
            power = chars.get('power', creature.power)
            toughness = chars.get('toughness', creature.toughness)
            keywords = chars.get('keywords', list(creature.keywords))

            # Still need to apply attachment bonuses for equipment/auras
            # that haven't been registered as layer effects
            p_bonus, t_bonus, granted_kws = apply_attached_bonuses(creature, battlefield)

            # Only add attachment bonuses if they're not already in layer system
            # (check if the attachment has a registered effect)
            attachments = get_attachments(creature, battlefield)
            unregistered_attachments = [
                att for att in attachments
                if not any(e.source.instance_id == att.instance_id for e in self.layer_system.effects)
            ]

            if unregistered_attachments:
                # These attachments don't have layer effects, add their bonuses
                power += p_bonus
                toughness += t_bonus
                for kw in granted_kws:
                    if kw.lower() not in [k.lower() for k in keywords]:
                        keywords.append(kw)

            return (power, toughness, keywords)
        else:
            # No layer effects active - use the original simple calculation
            base_power = creature.eff_power()
            base_toughness = creature.eff_toughness()
            base_keywords = list(creature.keywords)

            p_bonus, t_bonus, granted_kws = apply_attached_bonuses(creature, battlefield)

            return (base_power + p_bonus, base_toughness + t_bonus, base_keywords + granted_kws)

    def creature_has_keyword_with_attachments(self, creature: Card, keyword: str, battlefield: List[Card]) -> bool:
        """
        Check if creature has a keyword, including from attachments and layer effects.

        Uses the Layer System (Rule 613) to check Layer 6 effects that may have
        added or removed abilities.
        """
        # Use layer system if there are active effects
        if self.layer_system.effects:
            keywords = self.layer_system.get_keywords(creature)
            if keyword.lower() in [k.lower() for k in keywords]:
                return True

        # Also check base keywords
        if creature.has_keyword(keyword):
            return True

        # Check attachment bonuses
        _, _, granted_kws = apply_attached_bonuses(creature, battlefield)
        return keyword.lower() in [k.lower() for k in granted_kws]

    def deal_damage_to_creature(self, source: Card, target: Card, damage: int,
                                all_bf: List[Card]) -> None:
        """
        Deal damage from source to target creature, handling wither/infect.

        - Wither: Deals damage to creatures as -1/-1 counters
        - Infect: Deals damage to creatures as -1/-1 counters (to players as poison)
        """
        if damage <= 0:
            return

        has_wither = self.creature_has_keyword_with_attachments(source, "wither", all_bf)
        has_infect = self.creature_has_keyword_with_attachments(source, "infect", all_bf)
        has_deathtouch = self.creature_has_keyword_with_attachments(source, "deathtouch", all_bf)

        if has_wither or has_infect:
            # Damage dealt as -1/-1 counters instead of damage
            target.counters["-1/-1"] = target.counters.get("-1/-1", 0) + damage
            self.log.log(f"    {source.name} deals {damage} -1/-1 counters to {target.name}")
        else:
            # Normal damage
            target.damage_marked += damage

        # Track deathtouch for SBA
        if has_deathtouch and damage > 0:
            target.deathtouch_damage = True

    def deal_damage_to_player(self, source: Card, target_player: Player, damage: int,
                              all_bf: List[Card]) -> int:
        """
        Deal damage from source to player, handling infect (poison counters).
        Returns actual damage dealt (for life total tracking).

        - Infect: Deals damage to players as poison counters instead of life loss
        """
        if damage <= 0:
            return 0

        has_infect = self.creature_has_keyword_with_attachments(source, "infect", all_bf)

        if has_infect:
            # Infect deals poison counters to players instead of damage
            target_player.poison_counters += damage
            self.log.log(f"    {source.name} gives P{target_player.player_id} {damage} poison")
            return 0  # No life loss
        else:
            # Normal damage
            target_player.life -= damage
            return damage

    # =========================================================================
    # STACK SYSTEM
    # =========================================================================

    def put_on_stack(self, card: Card, controller: Player, target: Any = None,
                     chosen_modes: List[str] = None, was_kicked: bool = False,
                     kicker_count: int = 0, x_value: int = 0) -> StackItem:
        """Put a spell on the stack with optional modal/kicker/X info"""
        item = StackItem(
            card=card,
            controller=controller.player_id,
            target=target,
            stack_id=self.next_stack_id,
            chosen_modes=chosen_modes or [],
            was_kicked=was_kicked,
            kicker_count=kicker_count,
            x_value=x_value
        )
        self.next_stack_id += 1
        self.stack.append(item)

        # Log with mode/kicker info
        log_msg = f"    [{card.name}] goes on stack"
        if chosen_modes:
            log_msg += f" (modes: {', '.join(chosen_modes)})"
        if was_kicked:
            log_msg += " [KICKED]"
        if kicker_count > 0:
            log_msg += f" [MULTIKICKED x{kicker_count}]"
        if target:
            log_msg += f" (target: {target})"
        self.log.log(log_msg)
        return item

    def find_stack_item(self, stack_id: int) -> Optional[StackItem]:
        """Find a stack item by its ID"""
        for item in self.stack:
            if item.stack_id == stack_id:
                return item
        return None

    def remove_from_stack(self, item: StackItem):
        """Remove an item from the stack"""
        if item in self.stack:
            self.stack.remove(item)

    def stack_is_empty(self) -> bool:
        """Check if the stack is empty."""
        return len(self.stack) == 0

    def get_stack_top(self) -> Optional[StackItem]:
        """Return the top item on the stack without removing it."""
        if self.stack:
            return self.stack[-1]
        return None

    def resolve_top_of_stack(self) -> bool:
        """
        Resolve the top item on the stack (LIFO order).
        Returns True if something was resolved, False if stack was empty.
        After resolution, active player gets priority again.
        """
        if not self.stack:
            return False

        item = self.stack.pop()  # LIFO - remove from top

        if item.is_countered:
            # Countered spells go to graveyard without effect
            controller = self.p1 if item.controller == 1 else self.p2
            if item.card.card_type in ["instant", "sorcery"]:
                controller.graveyard.append(item.card)
            self.log.log(f"    [Stack] {item.card.name} fizzles (countered)")
            return True

        # Get controller player object
        controller = self.p1 if item.controller == 1 else self.p2

        self.log.log(f"    [Stack] Resolving {item.card.name}")

        # Use resolve_stack_item for modal/kicker support
        if item.chosen_modes or item.was_kicked or item.kicker_count > 0:
            self.resolve_stack_item(controller, item)
        else:
            # Resolve the spell using existing resolve method, passing x_value
            self.resolve(controller, item.card, item.target, item.x_value)

        return True

    def resolve_stack_with_priority(self) -> bool:
        """
        Full priority system: resolve stack with AI responses.
        Both players get priority for each item on the stack.
        Active player gets priority first, then non-active player.
        When both pass, top of stack resolves.
        Returns True when stack fully resolves, False if game ends.
        """
        max_iterations = 100  # Prevent infinite loops
        iterations = 0

        while self.stack and iterations < max_iterations:
            iterations += 1

            # Active player gets priority first
            active = self.active()
            opponent = self.opponent()

            # Check if active player wants to respond
            ai_active = AI(active, opponent, self.log)
            response = ai_active.should_respond(self.stack, active.available_mana())

            if response:
                spell, target = response
                if spell in active.hand:
                    active.hand.remove(spell)
                    self.tap_lands(active, spell.cmc())
                    self.put_on_stack(spell, active, target)
                    continue  # Restart priority after adding to stack

            # Active player passes - opponent gets priority
            ai_opp = AI(opponent, active, self.log)
            response = ai_opp.should_respond(self.stack, opponent.available_mana())

            if response:
                spell, target = response
                if spell in opponent.hand:
                    opponent.hand.remove(spell)
                    self.tap_lands(opponent, spell.cmc())
                    self.put_on_stack(spell, opponent, target)
                    continue  # Restart priority after adding to stack

            # Both players pass - resolve top of stack
            self.resolve_top_of_stack()

            # Check game state after resolution
            if not self.check_state():
                return False

            # Process any triggered abilities that were created
            self.process_triggers()

        return True

    def get_player(self, player_id: int) -> Player:
        """Get player by ID."""
        return self.p1 if player_id == 1 else self.p2

    def pass_priority(self, player: Player) -> None:
        """
        Player passes priority. In the full priority system,
        this is tracked internally by resolve_stack_with_priority.
        This method exists for explicit priority passing in specific scenarios.
        """
        self.log.log(f"    P{player.player_id} passes priority")

    def hold_priority(self, player: Player) -> bool:
        """
        Player holds priority (wants to respond to their own spell).
        Returns True if there's something on the stack to respond to.
        """
        if not self.stack:
            return False
        self.log.log(f"    P{player.player_id} holds priority")
        return True

    def resolve_counterspell(self, counterspell: Card, target_item: StackItem,
                             caster: Player, counter_cost: int = 0) -> bool:
        """
        Resolve a counterspell against a target on the stack.
        Returns True if the target was countered.
        """
        # Check if target is still on stack (hasn't fizzled)
        if target_item not in self.stack:
            self.log.log(f"    {counterspell.name} fizzles - target left stack")
            caster.graveyard.append(counterspell)
            return False

        target_controller = self.p1 if target_item.controller == 1 else self.p2

        # Handle conditional counters (Mana Leak type)
        if counter_cost > 0:
            # Check if opponent can and will pay
            opp_ai = AI(target_controller, caster, self.log)
            if opp_ai.should_pay_counter_cost(counter_cost):
                opp_mana = target_controller.available_mana()
                if opp_mana.total() >= counter_cost:
                    self.log.log(f"    P{target_controller.player_id} pays {counter_cost} to prevent counter")
                    # Tap lands to pay
                    self._tap_for_generic(target_controller, counter_cost)
                    caster.graveyard.append(counterspell)
                    return False

        # Counter the spell
        self.log.log(f"    {counterspell.name} counters {target_item.card.name}!")
        target_item.is_countered = True
        self.stack.remove(target_item)
        target_controller.graveyard.append(target_item.card)
        caster.graveyard.append(counterspell)
        return True

    def _tap_for_generic(self, player: Player, amount: int):
        """Tap lands to pay a generic cost"""
        remaining = amount
        for land in player.untapped_lands():
            if remaining <= 0:
                break
            land.is_tapped = True
            remaining -= 1

    def check_for_responses(self, stack_item: StackItem) -> bool:
        """
        Give opponent a chance to respond to a spell on the stack.
        Returns True if spell was countered.
        """
        caster = self.p1 if stack_item.controller == 1 else self.p2
        responder = self.p2 if stack_item.controller == 1 else self.p1

        # Create AI for responder
        ai = AI(responder, caster, self.log)
        response = ai.choose_counter_response(stack_item, responder.available_mana())

        if response:
            counterspell, target = response
            self.log.log(f"  >>> P{responder.player_id} responds with {counterspell.name}!")

            # Remove counterspell from hand, tap mana
            responder.hand.remove(counterspell)
            self._tap_for_spell(responder, counterspell.mana_cost)

            # Get counter cost for conditional counters
            counter_cost = ai.get_counter_cost(counterspell)

            # Resolve counterspell
            return self.resolve_counterspell(counterspell, target, responder, counter_cost)

        return False

    def cast_with_stack(self, player: Player, card: Card, target: Any = None, x_value: int = 0,
                        chosen_modes: List[str] = None, was_kicked: bool = False,
                        kicker_count: int = 0) -> bool:
        """
        Cast a spell using the stack system with response opportunity.
        Supports modal spells, kicker, and X spells.
        """
        # Put spell on stack with all relevant info
        stack_item = self.put_on_stack(
            card, player, target,
            chosen_modes=chosen_modes, was_kicked=was_kicked,
            kicker_count=kicker_count, x_value=x_value
        )

        # Fire spell cast triggers (prowess, etc.)
        if card.card_type not in ["creature", "land"]:
            self.fire_spell_cast(card, player)
            self.process_triggers()

        # Give opponent chance to respond
        was_countered = self.check_for_responses(stack_item)

        if was_countered:
            return False

        # Spell resolves - remove from stack first
        if stack_item in self.stack:
            self.stack.remove(stack_item)

        # Resolve using appropriate method based on modal/kicker
        if chosen_modes or was_kicked or kicker_count > 0:
            self.resolve_stack_item(player, stack_item)
        else:
            self.resolve(player, card, target, x_value)
        return True

    def cast_with_stack_alt(self, player: Player, card: Card, target: Any = None,
                            cast_with_flashback: bool = False, cast_with_escape: bool = False,
                            cast_with_overload: bool = False, cast_as_adventure: bool = False,
                            adventure_abilities: List[str] = None) -> bool:
        """
        Cast a spell with alternative cost using the stack system.
        Handles flashback, escape, overload, and adventure mechanics.
        """
        # Put spell on stack with alternative cost flags
        stack_item = self.put_on_stack(card, player, target)
        stack_item.cast_with_flashback = cast_with_flashback
        stack_item.cast_with_escape = cast_with_escape
        stack_item.cast_with_overload = cast_with_overload
        stack_item.cast_as_adventure = cast_as_adventure

        # Fire spell cast triggers (prowess, etc.)
        if card.card_type not in ["creature", "land"] or cast_as_adventure:
            self.fire_spell_cast(card, player)
            self.process_triggers()

        # Give opponent chance to respond
        was_countered = self.check_for_responses(stack_item)

        if was_countered:
            # Flashback/escape: card still exiles when countered
            if cast_with_flashback or cast_with_escape:
                player.exile.append(card)
                self.log.log(f"    {card.name} exiled (countered from graveyard)")
            return False

        # Remove from stack
        if stack_item in self.stack:
            self.stack.remove(stack_item)

        # Resolve based on cast type
        if cast_as_adventure:
            # Adventure: resolve the adventure abilities, then exile card
            self._resolve_adventure(player, card, target, adventure_abilities or [])
            card.on_adventure = True
            player.exile.append(card)
            self.log.log(f"    {card.name} exiled on adventure")
        elif cast_with_overload:
            # Overload: affect all valid targets instead of one
            self._resolve_overload(player, card)
        else:
            # Normal resolution for flashback/escape
            self.resolve(player, card, target)

        # Flashback/escape: exile after resolving
        if cast_with_flashback or cast_with_escape:
            # Card should already be resolved; move to exile instead of graveyard
            if card in player.graveyard:
                player.graveyard.remove(card)
            player.exile.append(card)
            self.log.log(f"    {card.name} exiled after flashback/escape")

        return True

    def _resolve_adventure(self, player: Player, card: Card, target: Any, abilities: List[str]):
        """Resolve adventure spell abilities."""
        opp = self.opponent()
        for ab in abilities:
            self._process_ability(ab, player, opp, card, target)

    def _resolve_overload(self, player: Player, card: Card):
        """Resolve overloaded spell - affects all valid targets."""
        opp = self.opponent()
        # Get all opponent creatures as targets
        targets = [c for c in opp.battlefield if c.card_type == "creature"]

        for ab in card.abilities:
            if ab.startswith("damage_"):
                # Deal damage to all creatures
                try:
                    dmg = int(ab.split("_")[1])
                except:
                    dmg = 2
                for t in targets:
                    t.damage_marked += dmg
                    self.log.log(f"    Overload: {dmg} damage to {t.name}")
            elif ab == "bounce":
                # Bounce all creatures
                for t in targets[:]:
                    opp.battlefield.remove(t)
                    opp.hand.append(t)
                    self.log.log(f"    Overload: {t.name} bounced")
            elif ab == "tap_creature":
                # Tap all creatures
                for t in targets:
                    t.is_tapped = True
                    self.log.log(f"    Overload: {t.name} tapped")

        # Spell goes to graveyard
        player.graveyard.append(card)

    def create_token(self, player: Player, power: int, toughness: int, name: str = "Token", keywords: List[str] = None):
        token = Card(
            name=name, mana_cost=ManaCost(), card_type="creature",
            power=power, toughness=toughness, keywords=keywords or [],
            instance_id=self.next_id, controller=player.player_id,
            owner=player.player_id,  # Token owner is the player who created it
            summoning_sick=True,
            is_token=True  # Mark as token for SBA handling
        )
        self.next_id += 1
        player.battlefield.append(token)
        self.log.log(f"    Creates {power}/{toughness} {name}")

    # =========================================================================
    # COPY EFFECTS - Game Integration (MTG Rule 707)
    # =========================================================================

    def create_copy_of_permanent(self, permanent: Card, controller: Player,
                                  modifications: List[Callable[[Card], None]] = None) -> Card:
        """
        Rule 707: Create a copy of a permanent and put it on the battlefield.

        This is used for clone effects like Clone, Clever Impersonator, etc.
        The copy enters as a new permanent under the specified controller.

        Args:
            permanent: The permanent to copy (must be on the battlefield)
            controller: The player who will control the copy
            modifications: Optional list of modifications (for "copy except..." effects)

        Returns:
            The created copy on the battlefield

        Example usage:
            # Clone entering as a copy of target creature
            clone_copy = game.create_copy_of_permanent(
                target_creature,
                casting_player,
                modifications=None
            )

            # Spark Double entering as non-legendary copy with +1/+1 counter
            spark_copy = game.create_copy_of_permanent(
                target_creature,
                casting_player,
                modifications=[
                    modification_not_legendary,
                    modification_add_counter("+1/+1", 1)
                ]
            )
        """
        # Create the copy using the standalone function with game's ID
        copy = create_copy(permanent, modifications, instance_id=self.next_id)
        self.next_id += 1

        # Set controller/owner (copies are controlled by the player who created them)
        copy.controller = controller.player_id
        copy.owner = controller.player_id

        # Put on battlefield
        controller.battlefield.append(copy)

        # Log the copy creation
        self.log.log(f"    P{controller.player_id} creates copy of {permanent.name}")

        # Fire ETB triggers for the copy
        self.fire_etb(copy, controller)

        return copy

    def create_token_copy(self, permanent: Card, controller: Player,
                          modifications: List[Callable[[Card], None]] = None) -> Card:
        """
        Rule 707.2/111.10: Create a token that's a copy of a permanent.

        This is used for effects like Populate, Cackling Counterpart, etc.
        The token copy has all copiable values of the original plus is_token=True.

        Args:
            permanent: The permanent to copy
            controller: The player who will control the token
            modifications: Optional list of modifications

        Returns:
            The created token copy on the battlefield

        Example usage:
            # Populate effect - copy a token
            new_token = game.create_token_copy(existing_token, player)

            # Cackling Counterpart - copy a creature as a token
            token = game.create_token_copy(target_creature, casting_player)
        """
        # Create the copy using the standalone function
        copy = create_copy(permanent, modifications, instance_id=self.next_id)
        self.next_id += 1

        # Mark as token (important for SBA handling - tokens cease to exist outside battlefield)
        copy.is_token = True

        # Set controller/owner
        copy.controller = controller.player_id
        copy.owner = controller.player_id

        # Put on battlefield
        controller.battlefield.append(copy)

        # Log the token copy creation
        self.log.log(f"    P{controller.player_id} creates token copy of {permanent.name}")

        # Fire ETB triggers
        self.fire_etb(copy, controller)

        return copy

    def copy_spell(self, spell_on_stack: StackItem, new_controller: Player,
                   new_target: Any = None,
                   modifications: List[Callable[[Card], None]] = None) -> StackItem:
        """
        Rule 707.10: Copy a spell on the stack.

        This is used for effects like Fork, Twincast, Reverberate.
        The copy is put on the stack above the original.

        Args:
            spell_on_stack: The StackItem representing the spell to copy
            new_controller: The player who will control the copy
            new_target: New target for the copy (if None, uses same target)
            modifications: Optional modifications to apply

        Returns:
            The new StackItem representing the copied spell

        Note: The copied spell will resolve before the original since stack is LIFO.
        """
        # Create copy of the spell card
        spell_copy = copy_spell_on_stack(
            spell_on_stack.card,
            modifications,
            instance_id=self.next_id
        )
        self.next_id += 1

        # Create new stack item for the copy
        copy_stack_item = StackItem(
            card=spell_copy,
            controller=new_controller.player_id,
            target=new_target if new_target is not None else spell_on_stack.target,
            stack_id=self.next_stack_id,
            x_value=spell_on_stack.x_value,  # Copy X value
            chosen_modes=spell_on_stack.chosen_modes.copy(),  # Copy chosen modes
            was_kicked=spell_on_stack.was_kicked,  # Copy kicked status
            kicker_count=spell_on_stack.kicker_count
        )
        self.next_stack_id += 1

        # Put on stack (will resolve before original)
        self.stack.append(copy_stack_item)

        self.log.log(f"    P{new_controller.player_id} copies {spell_on_stack.card.name}")

        return copy_stack_item

    # =========================================================================
    # ETB TRIGGER DOUBLING (Panharmonicon, etc.)
    # =========================================================================

    def get_etb_trigger_count(self, creature: Card, controller: Player) -> int:
        """Get the number of times an ETB trigger should fire for a creature."""
        trigger_count = 1
        for card in controller.battlefield:
            if any(ab in ["double_etb_triggers", "panharmonicon"]
                   for ab in [a.lower() for a in card.abilities]):
                trigger_count = 2
                break
        return trigger_count

    # =========================================================================
    # LAYER SYSTEM (MTG Rule 613)
    # =========================================================================

    def apply_layers(self) -> None:
        """Apply the layer system for characteristic-modifying effects."""
        all_permanents = self.p1.battlefield + self.p2.battlefield
        # Layer 4: Type-changing effects (Blood Moon, etc.)
        for permanent in all_permanents:
            for card in all_permanents:
                if "blood_moon" in [ab.lower() for ab in card.abilities]:
                    if permanent.card_type == "land":
                        if "legendary" not in permanent.keywords and permanent.name not in [
                            "Plains", "Island", "Swamp", "Mountain", "Forest"]:
                            permanent.produces = ["R"]

    def calculate_creature_stats_with_layers(self, creature: Card,
                                              controller: Player) -> Tuple[int, int, List[str]]:
        """Calculate a creature's stats after applying all layer effects."""
        base_power = creature.power
        base_toughness = creature.toughness
        keywords = list(creature.keywords)
        power_bonus = 0
        toughness_bonus = 0
        power_bonus += creature.counters.get("+1/+1", 0)
        toughness_bonus += creature.counters.get("+1/+1", 0)
        power_bonus -= creature.counters.get("-1/-1", 0)
        toughness_bonus -= creature.counters.get("-1/-1", 0)
        for card in controller.battlefield:
            if card.instance_id == creature.instance_id:
                continue
            for ab in card.abilities:
                ab_lower = ab.lower()
                if ab_lower in ["grant_plus1_plus1", "anthem_plus1_plus1", "lord"]:
                    power_bonus += 1
                    toughness_bonus += 1
        all_bf = self.p1.battlefield + self.p2.battlefield
        attach_p, attach_t, attach_kws = apply_attached_bonuses(creature, all_bf)
        power_bonus += attach_p
        toughness_bonus += attach_t
        keywords.extend(attach_kws)
        return (base_power + power_bonus, base_toughness + toughness_bonus, keywords)

    # =========================================================================
    # ADDITIONAL CLONE/COPY METHODS
    # =========================================================================

    def create_clone(self, clone_card: Card, target: Card, controller: Player) -> Card:
        """Create a clone of a target creature."""
        return self.create_copy_of_permanent(target, controller)

    def create_modified_copy(self, original: Card, controller: Player,
                              modifications: List[Callable[[Card], None]] = None) -> Card:
        """Create a copy of a permanent with modifications."""
        return self.create_copy_of_permanent(original, controller, modifications)

    def execute_copy_ability(self, source: Card, trigger_spell: Card,
                              controller: Player) -> List[Card]:
        """Execute a copy ability that copies a spell for each other creature."""
        copies = []
        other_creatures = [c for c in controller.battlefield
                         if c.card_type == "creature"
                         and c.instance_id != source.instance_id]
        for creature in other_creatures:
            for item in self.stack:
                if item.card.instance_id == trigger_spell.instance_id:
                    copy_item = self.copy_spell(item, controller, new_target=creature)
                    copies.append(copy_item.card)
                    break
        if copies:
            self.log.log(f"    {source.name} copies spell for {len(copies)} other creatures")
        return copies

    # =========================================================================
    # CONTROL CHANGE CONVENIENCE METHODS
    # =========================================================================

    def change_control(self, permanent: Card, new_controller_id: int,
                       source: Card = None, duration: str = 'permanent') -> bool:
        """Change control of a permanent. Wrapper for control_manager.change_control."""
        if source is None:
            source = Card(name="Control Effect", instance_id=self.next_id)
            self.next_id += 1
        return self.control_manager.change_control(permanent, new_controller_id, source, duration)

    def grant_temporary_control(self, permanent: Card, new_controller_id: int,
                                 source: Card = None) -> bool:
        """Grant temporary control until end of turn (Act of Treason style)."""
        if source is None:
            source = Card(name="Threaten Effect", instance_id=self.next_id)
            self.next_id += 1
        self.control_manager.threaten_effect(permanent, new_controller_id, source)
        return True

    def apply_layers_to_copy(self, copy: Card, controller: Player) -> Tuple[int, int, List[str]]:
        """Apply layers to a copied creature to get its final stats."""
        return self.calculate_creature_stats_with_layers(copy, controller)

    def apply_layers_with_control_change(self, permanent: Card, new_controller_id: int) -> None:
        """Apply layer system after a control change."""
        self.apply_layers()

    def _validate_target_on_resolution(self, card: Card, target: Any, caster: Player) -> bool:
        """
        Check if target is still legal when spell resolves (CR 608.2b).
        Returns False if spell should fizzle due to all targets being illegal.
        """
        if target is None:
            return True  # Spell has no target

        # Unwrap ward tuples to get actual target
        actual_target = target
        if isinstance(target, tuple):
            if len(target) == 2:
                if isinstance(target[1], int):
                    # (target, ward_cost) - ward is checked at cast time
                    actual_target = target[0]
                else:
                    # (my_creature, their_creature) for fight/bite - check second creature
                    actual_target = target[1]
            elif len(target) == 3:
                # (my_creature, their_creature, ward_cost) for fight with ward
                actual_target = target[1]

        # If target is "face" (player damage), it's always valid
        if actual_target == "face":
            return True

        # If target is a Card (creature/permanent)
        if isinstance(actual_target, Card):
            # Check if target is still on battlefield
            opp = self.p2 if caster == self.p1 else self.p1
            all_permanents = caster.battlefield + opp.battlefield
            if actual_target not in all_permanents:
                return False  # Target left battlefield

            # Check if target gained hexproof/shroud/protection
            # Shroud: Can't be targeted by anyone
            if actual_target.has_keyword("shroud"):
                return False

            # Hexproof: Can't be targeted by opponents
            if actual_target.controller != caster.player_id:
                if actual_target.has_keyword("hexproof"):
                    return False

                # Protection from colors
                for kw in actual_target.keywords:
                    kw_lower = kw.lower()
                    if kw_lower.startswith("protection"):
                        prot_from = kw_lower.replace("protection from ", "").replace("protection_", "")
                        # Color protection
                        color_map = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
                        if prot_from in color_map:
                            protected_color = color_map[prot_from]
                            # Check if source has that color
                            source_colors = card.mana_cost.colors()
                            if protected_color in source_colors:
                                return False
                        # Protection from everything
                        if prot_from == "everything":
                            return False

        return True

    def resolve(self, player: Player, card: Card, target: Any, x_value: int = 0):
        """
        Resolve a spell or ability.
        Target may be:
        - A Card object
        - "face" for player damage
        - A tuple (Card, ward_cost) if ward applies
        - A tuple (my_creature, their_creature) for fight/bite
        - A tuple (my_creature, their_creature, ward_cost) for fight/bite with ward
        x_value: The chosen X value for X spells (0 for non-X spells)
        """
        # CR 608.2b: Check if all targets are still legal on resolution
        if not self._validate_target_on_resolution(card, target, player):
            # Spell fizzles - all targets illegal
            self.log.log(f"  {card.name} fizzles (target no longer legal)")
            player.graveyard.append(card)
            return

        opp = self.opponent()

        # Handle ward cost payment
        ward_cost = 0
        actual_target = target
        if isinstance(target, tuple):
            if len(target) == 2:
                if isinstance(target[1], int):
                    # (target, ward_cost)
                    actual_target = target[0]
                    ward_cost = target[1]
                else:
                    # (my_creature, their_creature) for fight
                    actual_target = target
            elif len(target) == 3:
                # (my_creature, their_creature, ward_cost) for fight with ward
                actual_target = (target[0], target[1])
                ward_cost = target[2]

        # Pay ward cost (life)
        if ward_cost > 0:
            player.life -= ward_cost
            self.log.log(f"    Pays {ward_cost} life for ward")

        if card.card_type in ["instant", "sorcery", "enchantment", "artifact"]:
            player.spells_cast += 1

            for c in opp.battlefield:
                if "magebane" in c.abilities:
                    dmg = player.spells_cast
                    player.life -= dmg
                    self.log.log(f"    ⚡ {c.name} deals {dmg}! (P{player.player_id}: {player.life})")

            for c in player.battlefield:
                if "token_on_spell" in c.abilities or "spell_trigger" in c.abilities:
                    self.create_token(player, 1, 1, "Elemental")

        # Fire prowess triggers for non-creature spells
        if card.card_type not in ["creature", "land"]:
            self.fire_spell_cast(card, player)
            self.process_triggers()

        for ab in card.abilities:
            self._process_ability(ab, player, opp, card, actual_target, x_value)

        # Handle X-based creatures (like Hydroid Krasis)
        if card.card_type == "creature" and card.mana_cost.has_x() and x_value > 0:
            # Add +1/+1 counters based on X (creature enters with X/X stats)
            card.counters["+1/+1"] = card.counters.get("+1/+1", 0) + x_value
            self.log.log(f"    {card.name} enters with {x_value} +1/+1 counters (X={x_value})")

        if card.card_type in ["instant", "sorcery"]:
            player.graveyard.append(card)
        elif card.card_type in ["creature", "enchantment", "artifact", "planeswalker"]:
            if card.card_type == "creature":
                card.summoning_sick = True
            elif card.card_type == "planeswalker":
                # Planeswalker enters with loyalty counters equal to starting loyalty
                card.counters["loyalty"] = card.loyalty
                card.activated_this_turn = False
            elif card.is_aura():
                # Aura must attach to target creature when entering
                if isinstance(actual_target, Card) and actual_target.card_type == "creature":
                    # Check if target is still valid (on battlefield)
                    all_creatures = player.battlefield + opp.battlefield
                    if actual_target in all_creatures:
                        card.attached_to = actual_target.instance_id
                        self.log.log(f"    {card.name} enchants {actual_target.name}")
                    else:
                        # Target no longer valid, aura goes to graveyard
                        player.graveyard.append(card)
                        self.log.log(f"    {card.name} fizzles (no valid target)")
                        return
                else:
                    # No valid target, aura goes to graveyard
                    player.graveyard.append(card)
                    self.log.log(f"    {card.name} fizzles (no valid target)")
                    return
            player.battlefield.append(card)
            # Fire ETB triggers
            if card.card_type == "creature":
                self.fire_etb(card, player)
                self.process_triggers()

    def resolve_stack_item(self, player: Player, item: StackItem):
        """Resolve a stack item with modal/kicker support."""
        card = item.card

        # CR 608.2b: Check if all targets are still legal on resolution
        if not self._validate_target_on_resolution(card, item.target, player):
            # Spell fizzles - all targets illegal
            self.log.log(f"  {card.name} fizzles (target no longer legal)")
            player.graveyard.append(card)
            return

        opp = self.opponent()
        actual_target = item.target

        # Handle ward cost payment
        ward_cost = 0
        if isinstance(item.target, tuple):
            if len(item.target) == 2 and isinstance(item.target[1], int):
                actual_target, ward_cost = item.target[0], item.target[1]
            elif len(item.target) == 3:
                actual_target = (item.target[0], item.target[1])
                ward_cost = item.target[2]

        if ward_cost > 0:
            player.life -= ward_cost
            self.log.log(f"    Pays {ward_cost} life for ward")

        if card.card_type in ["instant", "sorcery", "enchantment", "artifact"]:
            player.spells_cast += 1
            for c in opp.battlefield:
                if "magebane" in c.abilities:
                    dmg = player.spells_cast
                    player.life -= dmg
                    self.log.log(f"    {c.name} deals {dmg}! (P{player.player_id}: {player.life})")
            for c in player.battlefield:
                if "token_on_spell" in c.abilities or "spell_trigger" in c.abilities:
                    self.create_token(player, 1, 1, "Elemental")

        if card.card_type not in ["creature", "land"]:
            self.fire_spell_cast(card, player)
            self.process_triggers()

        # Process modal spell modes OR regular abilities
        if item.chosen_modes:
            for mode in item.chosen_modes:
                self._process_ability(mode, player, opp, card, actual_target)
        else:
            for ab in card.abilities:
                self._process_ability(ab, player, opp, card, actual_target)

        # Process kicker effects
        if item.was_kicked and card.if_kicked:
            self.log.log(f"    Kicker effects!")
            for effect in card.if_kicked:
                self._process_ability(effect, player, opp, card, actual_target)

        # Multikicker: repeat effects for each time kicked
        if item.kicker_count > 0 and card.if_kicked:
            self.log.log(f"    Multikicker x{item.kicker_count}!")
            for _ in range(item.kicker_count):
                for effect in card.if_kicked:
                    self._process_ability(effect, player, opp, card, actual_target)

        # Handle permanent entry / graveyard
        if card.card_type in ["instant", "sorcery"]:
            player.graveyard.append(card)
        elif card.card_type in ["creature", "enchantment", "artifact", "planeswalker"]:
            if card.card_type == "creature":
                card.summoning_sick = True
            elif card.card_type == "planeswalker":
                card.counters["loyalty"] = card.loyalty
                card.activated_this_turn = False
            elif card.is_aura():
                if isinstance(actual_target, Card) and actual_target.card_type == "creature":
                    all_creatures = player.battlefield + opp.battlefield
                    if actual_target in all_creatures:
                        card.attached_to = actual_target.instance_id
                        self.log.log(f"    {card.name} enchants {actual_target.name}")
                    else:
                        player.graveyard.append(card)
                        self.log.log(f"    {card.name} fizzles")
                        return
                else:
                    player.graveyard.append(card)
                    self.log.log(f"    {card.name} fizzles")
                    return
            player.battlefield.append(card)
            if card.card_type == "creature":
                self.fire_etb(card, player)
                self.process_triggers()
            # Saga enters with 1 lore counter and triggers chapter I
            elif card.is_saga():
                self._saga_enters_battlefield(card, player)

    def _saga_enters_battlefield(self, saga: Card, controller: Player):
        """Handle saga entering the battlefield - add lore counter and trigger chapter I"""
        saga.counters["lore"] = 1
        self.log.log(f"    {saga.name} enters with 1 lore counter")
        # Queue chapter I trigger
        self.queue_trigger("saga_chapter", saga, controller, 1)
        self.process_triggers()

    def _add_lore_counter_to_saga(self, saga: Card, controller: Player):
        """Add a lore counter to a saga at the beginning of precombat main phase"""
        if not saga.is_saga() or saga not in controller.battlefield:
            return
        current_lore = saga.counters.get("lore", 0)
        new_lore = current_lore + 1
        saga.counters["lore"] = new_lore
        self.log.log(f"    {saga.name} gains lore counter ({new_lore})")
        # Queue the chapter trigger if we haven't exceeded chapters
        if new_lore <= saga.final_chapter():
            self.queue_trigger("saga_chapter", saga, controller, new_lore)

    def process_saga_upkeep(self, player: Player):
        """Process all sagas for the active player at beginning of precombat main phase"""
        sagas = [c for c in player.battlefield if c.is_saga()]
        for saga in sagas:
            self._add_lore_counter_to_saga(saga, player)
        if sagas:
            self.process_triggers()

    def activate_loyalty_ability(self, player: Player, pw: Card, ability_index: int, target: Any = None):
        """
        Activate a planeswalker's loyalty ability.
        Can only be done once per turn, at sorcery speed (main phase, empty stack).
        """
        if pw not in player.battlefield:
            self.log.log(f"    Cannot activate - {pw.name} not on battlefield")
            return False

        if pw.activated_this_turn:
            self.log.log(f"    Cannot activate - {pw.name} already used this turn")
            return False

        if ability_index >= len(pw.loyalty_abilities):
            self.log.log(f"    Invalid ability index for {pw.name}")
            return False

        ability = pw.loyalty_abilities[ability_index]
        cost, effect = parse_loyalty_ability(ability)

        current_loyalty = pw.current_loyalty()
        new_loyalty = current_loyalty + cost

        if new_loyalty < 0:
            self.log.log(f"    Cannot activate - not enough loyalty on {pw.name}")
            return False

        # Pay the cost (adjust loyalty)
        pw.counters["loyalty"] = new_loyalty
        pw.activated_this_turn = True

        opp = self.p2 if player == self.p1 else self.p1

        self.log.log(f"  >>> {pw.name} [{cost:+d}]: {effect} (loyalty now {new_loyalty})")

        # Process the effect
        self._process_ability(effect, player, opp, pw, target)

        # Check if planeswalker dies (0 loyalty)
        if new_loyalty <= 0:
            self.log.log(f"    {pw.name} has 0 loyalty and dies!")
            player.battlefield.remove(pw)
            player.graveyard.append(pw)

        return True

    def _process_ability(self, ab: str, player: Player, opp: Player, card: Card, target: Any, x_value: int = 0):
        # Handle X-based abilities first
        if "damage_X" in ab:
            dmg = x_value
            if target == "face":
                opp.life -= dmg
                self.log.log(f"    Deals {dmg} to P{opp.player_id} (X={x_value})")
            elif isinstance(target, Card) and target in opp.battlefield:
                target.damage_marked += dmg
                self.log.log(f"    Deals {dmg} to {target.name} (X={x_value})")
                if target.damage_marked >= target.eff_toughness():
                    opp.battlefield.remove(target)
                    opp.graveyard.append(target)
                    self.log.log(f"    {target.name} dies!")
            return

        if "draw_X" in ab and "half" not in ab:
            for _ in range(x_value):
                if player.library:
                    drawn = player.library.pop(0)
                    player.hand.append(drawn)
                    self.log.log(f"    Draws: {drawn.name}")
            return

        if "draw_half_X" in ab:
            draw_count = x_value // 2
            for _ in range(draw_count):
                if player.library:
                    drawn = player.library.pop(0)
                    player.hand.append(drawn)
                    self.log.log(f"    Draws: {drawn.name}")
            return

        if "gain_half_X" in ab or "life_half_X" in ab:
            life_gain = x_value // 2
            player.life += life_gain
            self.log.log(f"    Gains {life_gain} life (X={x_value})")
            return

        if "create_X_tokens" in ab:
            parts = ab.split("_")
            try:
                p, t = int(parts[3]), int(parts[4])
            except:
                p, t = 1, 1
            for _ in range(x_value):
                self.create_token(player, p, t)
            self.log.log(f"    Created {x_value} tokens (X={x_value})")
            return

        # Regular (non-X) damage abilities
        if ab.startswith("damage_"):
            parts = ab.split("_")
            try:
                dmg = int(parts[1])
            except:
                dmg = 3
            
            sweep = "sweep" in ab
            
            if sweep:
                opp.life -= dmg
                self.log.log(f"    Deals {dmg} to P{opp.player_id}")
                for c in list(opp.battlefield):
                    if c.card_type == "creature":
                        c.damage_marked += dmg
                        if c.damage_marked >= c.eff_toughness():
                            opp.battlefield.remove(c)
                            opp.graveyard.append(c)
                            self.log.log(f"    {c.name} dies!")
            elif target == "face":
                opp.life -= dmg
                self.log.log(f"    Deals {dmg} to P{opp.player_id}")
            elif isinstance(target, Card) and target in opp.battlefield:
                target.damage_marked += dmg
                self.log.log(f"    Deals {dmg} to {target.name}")
                if target.damage_marked >= target.eff_toughness():
                    opp.battlefield.remove(target)
                    opp.graveyard.append(target)
                    self.log.log(f"    {target.name} dies!")
        
        elif ab.startswith("draw_"):
            try:
                n = int(ab.split("_")[1])
            except:
                n = 1
            for _ in range(n):
                if player.library:
                    drawn = player.library.pop(0)
                    player.hand.append(drawn)
                    self.log.log(f"    Draws: {drawn.name}")
        
        elif ab in ["destroy_creature", "exile"]:
            if isinstance(target, Card) and target in opp.battlefield:
                opp.battlefield.remove(target)
                if ab == "destroy_creature":
                    opp.graveyard.append(target)
                self.log.log(f"    {'Destroys' if 'destroy' in ab else 'Exiles'} {target.name}")
        
        elif "bounce" in ab:
            if isinstance(target, Card) and target in opp.battlefield:
                opp.battlefield.remove(target)
                opp.hand.append(target)
                self.log.log(f"    Bounces {target.name}")
        
        elif ab in ["bite", "fight"]:
            if isinstance(target, tuple) and len(target) == 2:
                my_c, their_c = target
                if my_c in player.battlefield and their_c in opp.battlefield:
                    their_c.damage_marked += my_c.eff_power()
                    # Track deathtouch damage for SBA checking
                    if my_c.has_keyword("deathtouch") and my_c.eff_power() > 0:
                        their_c.deathtouch_damage = True
                    self.log.log(f"    {my_c.name} hits {their_c.name}")

                    if ab == "fight":
                        my_c.damage_marked += their_c.eff_power()
                        # Track deathtouch damage from their creature
                        if their_c.has_keyword("deathtouch") and their_c.eff_power() > 0:
                            my_c.deathtouch_damage = True

                    if their_c.damage_marked >= their_c.eff_toughness():
                        opp.battlefield.remove(their_c)
                        opp.graveyard.append(their_c)
                        self.log.log(f"    {their_c.name} dies!")

                    if ab == "fight" and my_c.damage_marked >= my_c.eff_toughness():
                        player.battlefield.remove(my_c)
                        player.graveyard.append(my_c)
                        self.log.log(f"    {my_c.name} dies!")
        
        elif ab.startswith("create_token"):
            parts = ab.split("_")
            try:
                p, t = int(parts[2]), int(parts[3])
            except:
                p, t = 1, 1
            self.create_token(player, p, t)

        # Pump spells: +X/+Y until end of turn
        elif ab.startswith("pump_"):
            # Format: pump_X_Y (e.g., pump_2_2 for +2/+2)
            try:
                parts = ab.split("_")
                p_boost = int(parts[1])
                t_boost = int(parts[2]) if len(parts) > 2 else p_boost
            except:
                p_boost, t_boost = 2, 2

            if isinstance(target, Card) and target in player.battlefield:
                target.power += p_boost
                target.toughness += t_boost
                target.counters["pump_temp"] = target.counters.get("pump_temp", 0) + 1
                self.log.log(f"    {target.name} gets +{p_boost}/+{t_boost}")

        # Indestructible until end of turn
        elif ab == "indestructible_eot":
            if isinstance(target, Card) and target in player.battlefield:
                if "indestructible" not in target.keywords:
                    target.keywords.append("indestructible")
                    target.counters["indestructible_temp"] = 1
                    self.log.log(f"    {target.name} gains indestructible")

        # Scry N
        elif ab.startswith("scry_"):
            try:
                n = int(ab.split("_")[1])
            except:
                n = 1
            ai = AI(player, opp, self.log)
            for _ in range(n):
                if player.library:
                    top_card = player.library[0]
                    keep_on_top = ai.scry_decision(top_card)
                    if not keep_on_top:
                        player.library.pop(0)
                        player.library.append(top_card)
                        self.log.log(f"    Scry: {top_card.name} to bottom")
                    else:
                        self.log.log(f"    Scry: {top_card.name} kept on top")

        # Return creature to hand (bounce)
        elif ab == "return_creature":
            if isinstance(target, Card) and target.card_type == "creature":
                if target in opp.battlefield:
                    opp.battlefield.remove(target)
                    opp.hand.append(target)
                    self.log.log(f"    Returns {target.name} to hand")
                elif target in player.battlefield:
                    player.battlefield.remove(target)
                    player.hand.append(target)
                    self.log.log(f"    Returns {target.name} to hand")

        # Control-changing effects (Rule 108.4, Layer 2)
        elif ab == "threaten" or ab == "act_of_treason":
            # Gain control until end of turn, untap, grant haste
            if isinstance(target, Card) and target.card_type == "creature":
                # Find target on any battlefield
                for p in [self.p1, self.p2]:
                    if target in p.battlefield:
                        self.control_manager.threaten_effect(target, player.player_id, card)
                        break

        elif ab == "gain_control" or ab == "mind_control":
            # Permanent control change
            if isinstance(target, Card):
                for p in [self.p1, self.p2]:
                    if target in p.battlefield:
                        self.control_manager.change_control(target, player.player_id, card, duration='permanent')
                        break

        elif ab == "gain_control_eot":
            # Gain control until end of turn (no untap/haste - like blue steal effects)
            if isinstance(target, Card):
                for p in [self.p1, self.p2]:
                    if target in p.battlefield:
                        self.control_manager.change_control(target, player.player_id, card, duration='end_of_turn')
                        break

        elif ab == "gain_control_source":
            # Gain control while source (aura) remains on battlefield
            if isinstance(target, Card):
                for p in [self.p1, self.p2]:
                    if target in p.battlefield:
                        self.control_manager.aura_control_effect(target, card, player.player_id)
                        break

        # Gain life
        elif ab.startswith("gain_life_") or ab.startswith("life_"):
            try:
                if ab.startswith("gain_life_"):
                    n = int(ab.split("_")[2])
                else:
                    n = int(ab.split("_")[1])
            except:
                n = 3
            player.life += n
            self.log.log(f"    Gains {n} life")

    def is_lethal_damage(self, creature: Card, damage: int, source: Card = None) -> bool:
        """Check if damage would be lethal to a creature"""
        # Indestructible creatures don't die from damage
        if creature.has_keyword("indestructible"):
            return False
        # Deathtouch makes any damage lethal
        if source and source.has_keyword("deathtouch") and damage > 0:
            return True
        # Normal lethal check
        return creature.damage_marked + damage >= creature.eff_toughness()

    def deal_damage_to_planeswalker(self, pw: Card, damage: int, opp: Player) -> bool:
        """
        Deal damage to a planeswalker, removing loyalty counters.
        Returns True if the planeswalker dies (loyalty <= 0).
        """
        if damage <= 0:
            return False

        pw.loyalty -= damage
        self.log.log(f"    {pw.name} takes {damage} damage (loyalty: {pw.loyalty})")

        if pw.loyalty <= 0:
            # Planeswalker dies - state-based action
            if pw in opp.battlefield:
                opp.battlefield.remove(pw)
                opp.graveyard.append(pw)
                self.log.log(f"    {pw.name} dies! (0 loyalty)")
            return True
        return False


    def _protection_prevents_damage(self, source: Card, target: Card, battlefield: List[Card]) -> bool:
        """
        Check if target has protection from source's qualities.
        CR 702.16e - Protection prevents all damage from sources with the stated quality.

        Returns True if damage should be prevented, False otherwise.
        """
        # Get target's keywords including from attachments
        _, _, target_keywords = self.get_creature_with_bonuses(target, battlefield)

        for kw in target_keywords:
            kw_lower = kw.lower()
            if kw_lower.startswith("protection from "):
                prot_from = kw_lower.replace("protection from ", "")

                # Protection from everything
                if prot_from == "everything":
                    return True

                # Protection from creatures
                if prot_from == "creatures" and source.card_type == "creature":
                    return True

                # Protection from specific colors
                source_colors = source.mana_cost.colors()
                for color in source_colors:
                    if prot_from == color.lower() or prot_from == color:
                        return True

                # Check for color names (white, blue, black, red, green)
                color_map = {"w": "white", "u": "blue", "b": "black", "r": "red", "g": "green"}
                for color_letter, color_name in color_map.items():
                    if color_letter.upper() in source_colors and prot_from == color_name:
                        return True

        return False

    def choose_damage_assignment_order(self, attacker: Card, blockers: List[Card], battlefield: List[Card]) -> List[Card]:
        """
        AI chooses damage assignment order (CR 510.1c - attacking player announces order).
        Prioritizes killing threats (deathtouch, lifelink), then low toughness creatures.

        Args:
            attacker: The attacking creature
            blockers: List of blocking creatures
            battlefield: Combined battlefield for bonus calculations

        Returns:
            List of blockers in optimal damage assignment order
        """
        def priority_score(blocker):
            _, blocker_t, blocker_kws = self.get_creature_with_bonuses(blocker, battlefield)
            score = blocker_t  # Base: toughness (lower = easier kill)

            # Kill deathtouch blockers first (they can kill any attacker)
            if "deathtouch" in [k.lower() for k in blocker_kws] or blocker.has_keyword("deathtouch"):
                score -= 100

            # Kill lifelink blockers second (prevent life gain)
            if "lifelink" in [k.lower() for k in blocker_kws] or blocker.has_keyword("lifelink"):
                score -= 50

            # Prefer higher power blockers (deal more damage back)
            blocker_p, _, _ = self.get_creature_with_bonuses(blocker, battlefield)
            score -= blocker_p * 5

            return score

        return sorted(blockers, key=priority_score)

    def deal_combat_damage(self, attackers: List[Card], blocks: Dict[int, List[int]],
                           first_strike_step: bool,
                           attack_targets: Dict[int, Optional[int]] = None) -> int:
        """
        Deal combat damage for one step (first strike or regular).
        Returns total damage dealt to defending player.
        Supports multiple blockers per attacker and planeswalker attacks.

        attack_targets: Dict mapping attacker instance_id to target:
            - None means attacking the player
            - int (planeswalker instance_id) means attacking that planeswalker
        """
        act = self.active()
        opp = self.opponent()
        total_dmg = 0

        if attack_targets is None:
            attack_targets = {}

        for att in attackers:
            # Check if this attacker deals damage in this step
            has_first_strike = att.has_keyword("first strike") or att.has_keyword("first_strike")
            has_double_strike = att.has_keyword("double strike") or att.has_keyword("double_strike")

            deals_damage = False
            if first_strike_step:
                deals_damage = has_first_strike or has_double_strike
            else:
                deals_damage = (not has_first_strike) or has_double_strike

            if not deals_damage:
                continue

            # Skip if attacker already died (from first strike step)
            if att not in act.battlefield:
                continue

            blocker_ids = blocks.get(att.instance_id, [])
            blockers = [c for c in opp.battlefield if c.instance_id in blocker_ids]

            # Determine attack target (player or planeswalker)
            target_pw_id = attack_targets.get(att.instance_id, None)
            target_pw = None
            if target_pw_id is not None:
                target_pw = next((pw for pw in opp.battlefield
                                 if pw.instance_id == target_pw_id and pw.card_type == "planeswalker"), None)

            if blockers:
                # Blocked by one or more creatures
                # Get effective power including aura/equipment bonuses
                all_bf = act.battlefield + opp.battlefield
                att_p, att_t, att_kws = self.get_creature_with_bonuses(att, all_bf)
                att_power = att_p
                remaining_damage = att_power

                # Sort blockers by toughness (deal lethal to each in order)
                # This simulates damage assignment order
                blockers_sorted = self.choose_damage_assignment_order(att, blockers, all_bf)

                if first_strike_step:
                    blocker_names = [b.name for b in blockers]
                    self.log.log(f"    {att.name} first strikes {blocker_names}")

                # Assign damage to blockers
                for blocker in blockers_sorted:
                    if remaining_damage <= 0:
                        break
                    if blocker not in opp.battlefield:
                        continue

                    # How much damage to assign to this blocker?
                    # Check for deathtouch from attacker (including from attachments)
                    has_deathtouch = self.creature_has_keyword_with_attachments(att, "deathtouch", all_bf)
                    blocker_p, blocker_t, blocker_kws = self.get_creature_with_bonuses(blocker, all_bf)

                    # Calculate damage to assign (for trample, this is what counts as "lethal")
                    if has_deathtouch:
                        # Deathtouch: 1 damage is lethal
                        assigned_damage = 1
                    else:
                        # Assign lethal damage (blocker's toughness, not accounting for already marked damage
                        # if protection prevented it from being marked)
                        assigned_damage = max(1, blocker_t - blocker.damage_marked)

                    assigned_damage = min(assigned_damage, remaining_damage)

                    # BUG FIX #1: Check if protection prevents this damage
                    if not self._protection_prevents_damage(att, blocker, all_bf):
                        # Damage is not prevented - mark it
                        blocker.damage_marked += assigned_damage
                        # Track deathtouch damage for SBA checking
                        if has_deathtouch and assigned_damage > 0:
                            blocker.deathtouch_damage = True
                    # else: damage prevented by protection, but still counts as assigned for trample

                    # BUG FIX #3: Subtract assigned damage (not marked) for trample calculation
                    # CR 702.19b - assign lethal as if it weren't prevented, then prevent it
                    remaining_damage -= assigned_damage

                # Blockers deal damage back to attacker
                for blocker in blockers:
                    if blocker not in opp.battlefield:
                        continue

                    blocker_p, blocker_t, blocker_kws = self.get_creature_with_bonuses(blocker, all_bf)
                    blocker_first = "first strike" in blocker_kws or "first_strike" in blocker_kws or blocker.has_keyword("first strike")
                    blocker_double = "double strike" in blocker_kws or "double_strike" in blocker_kws or blocker.has_keyword("double strike")
                    blocker_deals = (first_strike_step and (blocker_first or blocker_double)) or \
                                   (not first_strike_step and ((not blocker_first) or blocker_double))

                    if blocker_deals:
                        # BUG FIX #1: Check if attacker has protection from blocker
                        if not self._protection_prevents_damage(blocker, att, all_bf):
                            att.damage_marked += blocker_p
                            # Track deathtouch damage from blocker for SBA checking
                            blocker_deathtouch = "deathtouch" in blocker_kws or blocker.has_keyword("deathtouch")
                            if blocker_deathtouch and blocker_p > 0:
                                att.deathtouch_damage = True

                # Trample: excess damage goes to target (player or planeswalker)
                has_trample = self.creature_has_keyword_with_attachments(att, "trample", all_bf)
                if has_trample and remaining_damage > 0:
                    if target_pw and target_pw in opp.battlefield:
                        self.deal_damage_to_planeswalker(target_pw, remaining_damage, opp)
                    else:
                        opp.life -= remaining_damage
                        total_dmg += remaining_damage
                        self.log.log(f"    Tramples {remaining_damage} to P{opp.player_id}")

                # Lifelink: gain life for all damage dealt
                has_lifelink = self.creature_has_keyword_with_attachments(att, "lifelink", all_bf)
                if has_lifelink:
                    act.life += att_power
            else:
                # Unblocked - deal damage to target (player or planeswalker)
                # Get effective power including attachment bonuses
                all_bf = act.battlefield + opp.battlefield
                att_p, att_t, att_kws = self.get_creature_with_bonuses(att, all_bf)
                dmg = att_p

                if target_pw and target_pw in opp.battlefield:
                    # Attacking a planeswalker
                    self.deal_damage_to_planeswalker(target_pw, dmg, opp)
                else:
                    # Attacking player (or planeswalker already died)
                    opp.life -= dmg
                    total_dmg += dmg

                has_lifelink = self.creature_has_keyword_with_attachments(att, "lifelink", all_bf)
                if has_lifelink:
                    act.life += dmg

        return total_dmg

    def process_combat_deaths(self, attackers: List[Card], blocks: Dict[int, List[int]]):
        """Check for and process combat deaths. Supports multiple blockers."""
        act = self.active()
        opp = self.opponent()
        all_bf = act.battlefield + opp.battlefield

        for att in list(attackers):
            if att not in act.battlefield:
                continue

            blocker_ids = blocks.get(att.instance_id, [])
            blockers = [c for c in opp.battlefield if c.instance_id in blocker_ids]

            # Get attacker's effective toughness with attachments
            att_p, att_t, att_kws = self.get_creature_with_bonuses(att, all_bf)
            has_indestructible = self.creature_has_keyword_with_attachments(att, "indestructible", all_bf)

            # Check if attacker dies
            if not has_indestructible:
                lethal_to_att = False
                # Any blocker with deathtouch that dealt damage kills the attacker
                for blocker in blockers:
                    if self.creature_has_keyword_with_attachments(blocker, "deathtouch", all_bf) and att.damage_marked > 0:
                        lethal_to_att = True
                        break
                if att.damage_marked >= att_t:
                    lethal_to_att = True

                if lethal_to_att and att in act.battlefield:
                    act.battlefield.remove(att)
                    act.graveyard.append(att)
                    self.log.log(f"    {att.name} dies!")
                    self.fire_dies(att, act)

            # Check if each blocker dies
            att_has_deathtouch = self.creature_has_keyword_with_attachments(att, "deathtouch", all_bf)
            for blocker in blockers:
                if blocker not in opp.battlefield:
                    continue

                blocker_p, blocker_t, blocker_kws = self.get_creature_with_bonuses(blocker, all_bf)
                blocker_indestructible = self.creature_has_keyword_with_attachments(blocker, "indestructible", all_bf)
                if blocker_indestructible:
                    continue

                lethal_to_blocker = False
                if att_has_deathtouch and blocker.damage_marked > 0:
                    lethal_to_blocker = True
                elif blocker.damage_marked >= blocker_t:
                    lethal_to_blocker = True

                if lethal_to_blocker:
                    opp.battlefield.remove(blocker)
                    opp.graveyard.append(blocker)
                    self.log.log(f"    {blocker.name} dies!")
                    self.fire_dies(blocker, opp)

        # Process any queued dies triggers
        self.process_triggers()

    def combat(self, attackers: List[Card], blocks: Dict[int, List[int]],
               attack_targets: Dict[int, Optional[int]] = None):
        """
        Execute combat with support for multiple blockers per attacker and planeswalker attacks.
        blocks: Dict mapping attacker instance_id to list of blocker instance_ids
        attack_targets: Dict mapping attacker instance_id to target (None=player, int=pw instance_id)
        """
        act = self.active()
        opp = self.opponent()

        if not attackers:
            return

        # Tap attackers (unless they have vigilance)
        for a in attackers:
            if not a.has_keyword("vigilance"):
                a.is_tapped = True
            # Fire attack triggers
            self.fire_attack(a, act)

        self.log.log(f"  Attackers: {[a.name for a in attackers]}")
        self.process_triggers()  # Process attack triggers

        # Attacker can cast combat tricks before blocks
        ai_act = AI(act, opp, self.log)
        trick = ai_act.combat_trick_decision(attackers, [], act.available_mana())
        if trick:
            spell, target = trick
            self.log.log(f"  ▶ Combat trick: {spell.name}")
            act.hand.remove(spell)
            self.tap_lands(act, spell.cmc())
            self.resolve(act, spell, target)

        # Defender can flash in creatures or cast instants before declaring blocks
        ai_opp = AI(opp, act, self.log)
        opp_mana = opp.available_mana()

        # Flash in a creature
        flash_creatures = ai_opp.find_flash_creatures(opp_mana)
        if flash_creatures:
            # Play first flash creature that can help block
            flash_c = flash_creatures[0]
            self.log.log(f"  ▶ Flash: {flash_c.name}")
            opp.hand.remove(flash_c)
            self.tap_lands(opp, flash_c.cmc())
            flash_c.summoning_sick = False  # Can block immediately
            opp.battlefield.append(flash_c)

        # Defender combat trick
        all_blockers = [c for c in opp.creatures() if not c.is_tapped]
        def_trick = ai_opp.combat_trick_decision([], all_blockers, opp.available_mana())
        if def_trick:
            spell, target = def_trick
            self.log.log(f"  ▶ Combat trick: {spell.name}")
            opp.hand.remove(spell)
            self.tap_lands(opp, spell.cmc())
            self.resolve(opp, spell, target)

        # Log blocking assignments
        for att in attackers:
            blocker_ids = blocks.get(att.instance_id, [])
            if blocker_ids:
                blockers = [c for c in opp.battlefield if c.instance_id in blocker_ids]
                if blockers:
                    blocker_names = [b.name for b in blockers]
                    if len(blockers) > 1:
                        self.log.log(f"    {att.name} gang blocked by {blocker_names}")
                    else:
                        self.log.log(f"    {att.name} blocked by {blocker_names[0]}")

        # Check if any creature has first/double strike
        has_first_strike = any(
            a.has_keyword("first strike") or a.has_keyword("first_strike") or
            a.has_keyword("double strike") or a.has_keyword("double_strike")
            for a in attackers
        )
        # Check blockers too
        for blocker_ids in blocks.values():
            for blocker_id in blocker_ids:
                b = next((c for c in opp.battlefield if c.instance_id == blocker_id), None)
                if b and (b.has_keyword("first strike") or b.has_keyword("first_strike") or
                         b.has_keyword("double strike") or b.has_keyword("double_strike")):
                    has_first_strike = True
                    break
            if has_first_strike:
                break

        total_dmg = 0

        # First strike damage step (if applicable)
        if has_first_strike:
            self.log.log("    -- First Strike Damage --")
            total_dmg += self.deal_combat_damage(attackers, blocks, first_strike_step=True,
                                                  attack_targets=attack_targets)
            self.process_combat_deaths(attackers, blocks)
            if not self.check_state():
                return

        # Regular damage step
        if not has_first_strike:
            self.log.log("    -- Combat Damage --")
        else:
            self.log.log("    -- Regular Damage --")
        total_dmg += self.deal_combat_damage(attackers, blocks, first_strike_step=False,
                                              attack_targets=attack_targets)
        self.process_combat_deaths(attackers, blocks)

        if total_dmg > 0:
            self.log.log(f"  Combat: {total_dmg} total to P{opp.player_id} ({opp.life})")
    
    def check_state(self) -> bool:
        """
        Check and apply all State-Based Actions (SBAs).
        SBAs are checked simultaneously and applied in a loop until none apply.
        Returns True if game continues, False if a player has lost.

        Per MTG Comprehensive Rules 704:
        - SBAs are checked whenever a player would receive priority
        - All applicable SBAs are performed simultaneously
        - Then SBAs are checked again until none apply
        - Then triggered abilities go on the stack (CR 704.3)
        """
        # Keep checking until no SBAs apply
        sba_applied = False
        while self._check_sbas_once():
            sba_applied = True

        # After all SBAs, process any triggers that fired (CR 704.3)
        if self.trigger_queue:
            self.process_triggers()

        # Return whether game should continue
        return self.winner is None

    def _check_sbas_once(self) -> bool:
        """
        Check all SBAs once and apply them simultaneously.
        Returns True if any SBAs were applied (need to check again).
        """
        applied = False
        creatures_to_die: List[Tuple[Card, Player]] = []
        planeswalkers_to_die: List[Tuple[Card, Player]] = []
        permanents_to_remove: List[Tuple[Card, Player]] = []
        tokens_to_remove: List[Tuple[Card, Player, str]] = []  # (card, player, zone)

        # =====================================================================
        # PLAYER SBAs (704.5a-c)
        # =====================================================================

        # 704.5a: Player at 0 or less life loses
        for player in [self.p1, self.p2]:
            if player.life <= 0 and self.winner is None:
                self.winner = 3 - player.player_id
                self.log.log(f"\n  [SBA] P{player.player_id} loses - life at {player.life}")
                applied = True

        # 704.5b: Player with 10+ poison counters loses
        for player in [self.p1, self.p2]:
            if player.poison_counters >= 10 and self.winner is None:
                self.winner = 3 - player.player_id
                self.log.log(f"\n  [SBA] P{player.player_id} loses - {player.poison_counters} poison counters")
                applied = True

        # 704.5c: Player who attempted to draw from empty library loses
        for player in [self.p1, self.p2]:
            if player.attempted_draw_from_empty and self.winner is None:
                self.winner = 3 - player.player_id
                self.log.log(f"\n  [SBA] P{player.player_id} loses - drew from empty library")
                applied = True

        # If game is over, stop checking
        if self.winner is not None:
            winner_name = self.p1.deck_name if self.winner == 1 else self.p2.deck_name
            self.log.log(f"\n  P{self.winner} ({winner_name}) WINS!")
            return applied

        # =====================================================================
        # CREATURE SBAs (704.5f-h)
        # =====================================================================

        for player in [self.p1, self.p2]:
            for creature in list(player.battlefield):
                if creature.card_type != "creature":
                    continue

                should_die = False
                death_reason = ""
                can_regenerate = False

                # 704.5f: Creature with 0 or less toughness dies (indestructible doesn't save from this!)
                if creature.eff_toughness() <= 0:
                    should_die = True
                    death_reason = f"0 toughness ({creature.eff_toughness()})"
                    # -1/-1 counters/effects bypass indestructible AND regeneration

                # Check for damage-based death (indestructible saves from these)
                elif not creature.has_keyword("indestructible"):
                    # 704.5g: Creature with lethal damage marked dies
                    if creature.damage_marked >= creature.eff_toughness():
                        should_die = True
                        death_reason = f"lethal damage ({creature.damage_marked}/{creature.eff_toughness()})"
                        can_regenerate = True

                    # 704.5h: Creature with deathtouch damage dies (any amount > 0)
                    elif creature.deathtouch_damage and creature.damage_marked > 0:
                        should_die = True
                        death_reason = "deathtouch damage"
                        can_regenerate = True

                if should_die:
                    # Check for shield counter (D&D set mechanic) - removes counter instead of dying
                    if creature.shield_counters > 0 and can_regenerate:
                        creature.shield_counters -= 1
                        creature.damage_marked = 0
                        creature.deathtouch_damage = False
                        self.log.log(f"  [SBA] {creature.name} loses shield counter instead of dying")
                        applied = True
                        continue

                    # Check for regeneration shield - taps, removes damage, removes from combat
                    if creature.regenerate_shield > 0 and can_regenerate:
                        creature.regenerate_shield -= 1
                        creature.is_tapped = True
                        creature.damage_marked = 0
                        creature.deathtouch_damage = False
                        self.log.log(f"  [SBA] {creature.name} regenerates (tapped, damage removed)")
                        applied = True
                        continue

                    creatures_to_die.append((creature, player))
                    self.log.log(f"  [SBA] {creature.name} dies - {death_reason}")

        # =====================================================================
        # +1/+1 AND -1/-1 COUNTER ANNIHILATION (704.5q)
        # =====================================================================

        for player in [self.p1, self.p2]:
            for permanent in player.battlefield:
                plus_counters = permanent.counters.get("+1/+1", 0)
                minus_counters = permanent.counters.get("-1/-1", 0)

                if plus_counters > 0 and minus_counters > 0:
                    # Remove equal amounts of each
                    to_remove = min(plus_counters, minus_counters)
                    permanent.counters["+1/+1"] = plus_counters - to_remove
                    permanent.counters["-1/-1"] = minus_counters - to_remove

                    # Clean up zero counters
                    if permanent.counters["+1/+1"] == 0:
                        del permanent.counters["+1/+1"]
                    if permanent.counters["-1/-1"] == 0:
                        del permanent.counters["-1/-1"]

                    self.log.log(f"  [SBA] {permanent.name}: {to_remove} +1/+1 and -1/-1 counters annihilate")
                    applied = True

        # =====================================================================
        # PLANESWALKER SBAs (704.5i, 704.5j)
        # =====================================================================

        for player in [self.p1, self.p2]:
            for pw in list(player.battlefield):
                if pw.card_type != "planeswalker":
                    continue

                # 704.5i: Planeswalker with 0 or less loyalty dies
                if pw.current_loyalty() <= 0:
                    planeswalkers_to_die.append((pw, player))
                    self.log.log(f"  [SBA] {pw.name} dies - 0 loyalty")

        # =====================================================================
        # LEGEND RULE (704.5j)
        # =====================================================================

        for player in [self.p1, self.p2]:
            # Group legendaries by name
            legends_by_name: Dict[str, List[Card]] = {}
            for permanent in player.battlefield:
                if permanent.has_keyword("legendary"):
                    if permanent.name not in legends_by_name:
                        legends_by_name[permanent.name] = []
                    legends_by_name[permanent.name].append(permanent)

            # For each name with 2+ legends, keep one (highest instance_id = most recent)
            for name, legends in legends_by_name.items():
                if len(legends) > 1:
                    # Sort by instance_id descending (keep newest)
                    legends.sort(key=lambda x: x.instance_id, reverse=True)
                    for legend in legends[1:]:
                        permanents_to_remove.append((legend, player))
                        self.log.log(f"  [SBA] Legend rule: {legend.name} goes to graveyard (keeping newer copy)")

        # =====================================================================
        # AURA SBAs (704.5m)
        # =====================================================================

        for player in [self.p1, self.p2]:
            for aura in list(player.battlefield):
                # Check if it's an Aura (enchantment with attached_to set or "aura" subtype)
                if aura.card_type != "enchantment":
                    continue
                if not aura.has_keyword("aura") and aura.attached_to is None:
                    continue

                # Aura must be attached to something
                if aura.attached_to is not None:
                    # Find the attached permanent
                    attached_perm = None
                    attached_controller = None
                    for p in [self.p1, self.p2]:
                        for perm in p.battlefield:
                            if perm.instance_id == aura.attached_to:
                                attached_perm = perm
                                attached_controller = p
                                break
                        if attached_perm:
                            break

                    should_fall_off = False
                    fall_off_reason = ""

                    if attached_perm is None:
                        # Attached permanent no longer exists
                        should_fall_off = True
                        fall_off_reason = "attached permanent left battlefield"
                    else:
                        # Check if attached permanent has protection from Aura's colors or attributes
                        aura_colors = aura.mana_cost.colors()
                        # Map color letters to full names for comparison
                        color_map = {"w": "white", "u": "blue", "b": "black", "r": "red", "g": "green"}
                        aura_color_names = [color_map.get(c.lower(), c.lower()) for c in aura_colors]
                        for kw in attached_perm.keywords:
                            kw_lower = kw.lower()
                            if kw_lower.startswith("protection from "):
                                prot_from = kw_lower.replace("protection from ", "")
                                # Normalize protection target (handle both "r" and "red")
                                prot_normalized = color_map.get(prot_from, prot_from)
                                # Check color protection (match full color name)
                                if prot_normalized in aura_color_names:
                                    should_fall_off = True
                                    fall_off_reason = f"protection from {prot_from}"
                                    break
                                # Check "protection from everything"
                                if prot_from == "everything":
                                    should_fall_off = True
                                    fall_off_reason = "protection from everything"
                                    break
                                # Check "protection from enchantments"
                                if prot_from == "enchantments":
                                    should_fall_off = True
                                    fall_off_reason = "protection from enchantments"
                                    break

                    if should_fall_off:
                        permanents_to_remove.append((aura, player))
                        self.log.log(f"  [SBA] {aura.name} goes to graveyard - {fall_off_reason}")

        # =====================================================================
        # TOKEN SBAs (704.5d)
        # Tokens cease to exist when in a zone other than the battlefield
        # =====================================================================

        for player in [self.p1, self.p2]:
            # Check graveyard for tokens
            for token in list(player.graveyard):
                if token.is_token:
                    tokens_to_remove.append((token, player, "graveyard"))

            # Check exile for tokens
            for token in list(player.exile):
                if token.is_token:
                    tokens_to_remove.append((token, player, "exile"))

            # Check hand for tokens (shouldn't happen normally, but possible with bounce)
            for token in list(player.hand):
                if token.is_token:
                    tokens_to_remove.append((token, player, "hand"))

        # =====================================================================
        # APPLY ALL SBAs SIMULTANEOUSLY
        # =====================================================================

        # Process creature deaths
        for creature, player in creatures_to_die:
            if creature in player.battlefield:
                # Capture last known information BEFORE moving zones (CR 603.10)
                all_bf = self.p1.battlefield + self.p2.battlefield
                p, t, kws = self.get_creature_with_bonuses(creature, all_bf)
                last_known = {
                    'power': p,
                    'toughness': t,
                    'keywords': kws,
                    'counters': creature.counters.copy()
                }

                # Create die event and process through replacement effects (Rule 614)
                # This handles Rest in Peace, Leyline of the Void, etc.
                die_event = self.create_die_event(creature, player)
                processed_event = self.process_event_with_replacements(die_event, player)

                # Notify control manager before removal (for effects sourced by this permanent)
                self.control_manager.on_permanent_leaves(creature)

                player.battlefield.remove(creature)

                if not creature.is_token:
                    # Determine destination based on replacement effects
                    destination = processed_event.destination_zone

                    # Card goes to owner's zone, not controller's (Rule 400.3)
                    owner = self.p1 if creature.owner == 1 else self.p2

                    if destination == 'exile':
                        owner.exile.append(creature)
                        self.log.log(f"    {creature.name} is exiled (replacement effect)")
                    else:
                        # Default: graveyard
                        owner.graveyard.append(creature)

                    # Clear control effects since card changed zones
                    creature.control_effects.clear()
                    creature.controller = creature.owner

                # Fire dies triggers (even if exiled, "dies" still triggers - it's the leaving battlefield)
                # Note: Some effects care about WHERE the card goes, but "dies" just means "went to graveyard"
                # Rest in Peace replaces going to graveyard with exile, so technically it doesn't "die"
                if processed_event.destination_zone == 'graveyard':
                    self.fire_dies(creature, player, last_known)
                applied = True

        # Process planeswalker deaths
        for pw, player in planeswalkers_to_die:
            if pw in player.battlefield:
                # Create die event and process through replacement effects
                die_event = self.create_die_event(pw, player)
                processed_event = self.process_event_with_replacements(die_event, player)

                # Notify control manager before removal
                self.control_manager.on_permanent_leaves(pw)

                player.battlefield.remove(pw)
                if not pw.is_token:
                    owner = self.p1 if pw.owner == 1 else self.p2
                    if processed_event.destination_zone == 'exile':
                        owner.exile.append(pw)
                        self.log.log(f"    {pw.name} is exiled (replacement effect)")
                    else:
                        owner.graveyard.append(pw)
                    pw.control_effects.clear()
                    pw.controller = pw.owner
                applied = True

        # Process other permanents going to graveyard (legend rule, auras)
        for permanent, player in permanents_to_remove:
            if permanent in player.battlefield:
                # Create die event and process through replacement effects
                die_event = self.create_die_event(permanent, player)
                processed_event = self.process_event_with_replacements(die_event, player)

                # Notify control manager before removal
                self.control_manager.on_permanent_leaves(permanent)

                player.battlefield.remove(permanent)
                if not permanent.is_token:
                    owner = self.p1 if permanent.owner == 1 else self.p2
                    if processed_event.destination_zone == 'exile':
                        owner.exile.append(permanent)
                        self.log.log(f"    {permanent.name} is exiled (replacement effect)")
                    else:
                        owner.graveyard.append(permanent)
                    permanent.control_effects.clear()
                    permanent.controller = permanent.owner
                applied = True

        # Process tokens ceasing to exist
        for token, player, zone in tokens_to_remove:
            if zone == "graveyard" and token in player.graveyard:
                player.graveyard.remove(token)
                applied = True
            elif zone == "exile" and token in player.exile:
                player.exile.remove(token)
                applied = True
            elif zone == "hand" and token in player.hand:
                player.hand.remove(token)
                applied = True

        # Clear deathtouch_damage flag after checking (it's per-turn)
        for player in [self.p1, self.p2]:
            for creature in player.battlefield:
                if creature.card_type == "creature":
                    creature.deathtouch_damage = False

        return applied
    
    def play_turn(self) -> bool:
        act = self.active()
        opp = self.opponent()

        self.turn += 1
        self.log.section(f"TURN {self.turn}: P{act.player_id} ({act.deck_name})")
        self.log.log(f"  Life: P1={self.p1.life}, P2={self.p2.life}")

        # Untap step - clear mana pool from previous turn
        act.land_played = False
        act.spells_cast = 0
        act.mana_pool.clear()  # Mana empties between turns

        # Phasing: phased-out permanents phase in, phasing permanents phase out
        for c in act.battlefield:
            if c.phased_out:
                # Phase in at beginning of untap step
                c.phased_out = False
                self.log.log(f"  [Phase] {c.name} phases in")
            elif c.has_keyword("phasing"):
                # Permanents with phasing phase out
                c.phased_out = True
                self.log.log(f"  [Phase] {c.name} phases out")

        for c in act.battlefield:
            # Skip phased-out permanents (treated as not existing)
            if c.phased_out:
                continue
            c.is_tapped = False
            if c.card_type == "creature":
                c.summoning_sick = False
                c.damage_marked = 0
                c.regenerate_shield = 0  # Clear regeneration shields at end of turn
            elif c.card_type == "planeswalker":
                c.activated_this_turn = False  # Reset loyalty ability usage

        for c in opp.battlefield:
            if c.card_type == "creature" and not c.phased_out:
                c.damage_marked = 0

        if not (self.turn == 1 and act.player_id == 1):
            if not self.draw(act):
                return False

        # Process saga lore counters at beginning of precombat main phase
        self.process_saga_upkeep(act)

        self.log.log(f"  Hand: {[c.name for c in act.hand]}")
        self.log.log(f"  Board: {[c.name for c in act.battlefield if c.card_type != 'land']}")

        ai = AI(act, opp, self.log)
        actions = ai.main_phase()

        self.log.log("\n  === MAIN ===")
        for action_tuple in actions:
            # Handle both old format (action, card, target) and new format with cast_type
            if len(action_tuple) == 3:
                action, card, target = action_tuple
                cast_type, extra = "normal", None
            else:
                action, card, target, cast_type, extra = action_tuple

            if action == "land":
                act.hand.remove(card)
                act.battlefield.append(card)
                act.land_played = True
                self.log.log(f"  ▶ Land: {card.name}")
                self.fire_landfall(card, act)
                self.process_triggers()
            elif action == "mdfc_land":
                # Play MDFC as its back face (land)
                act.hand.remove(card)
                back = card.mdfc_back
                back.mdfc_played_as = "back"
                back.instance_id = card.instance_id
                if back.mdfc_enters_tapped:
                    back.is_tapped = True
                act.battlefield.append(back)
                act.land_played = True
                self.log.log(f"  ▶ MDFC Land: {card.name} (as {back.name})")
                self.fire_landfall(back, act)
                self.process_triggers()
            elif action == "cast":
                # Handle alternative casting costs
                if cast_type == "flashback":
                    self.log.log(f"  ▶ Flashback: {card.name}")
                    fb_cost = ManaCost.parse(card.flashback)
                    self._tap_for_spell(act, fb_cost)
                    act.graveyard.remove(card)
                    self.cast_with_stack_alt(act, card, target, cast_with_flashback=True)
                elif cast_type == "escape":
                    self.log.log(f"  ▶ Escape: {card.name} (exiling {extra} cards)")
                    esc_cost = ManaCost.parse(card.escape)
                    self._tap_for_spell(act, esc_cost)
                    act.graveyard.remove(card)
                    # Exile other cards as additional cost
                    cards_to_exile = [c for c in act.graveyard if c.instance_id != card.instance_id][:extra]
                    for c in cards_to_exile:
                        act.graveyard.remove(c)
                        act.exile.append(c)
                    self.cast_with_stack_alt(act, card, target, cast_with_escape=True)
                elif cast_type == "overload":
                    self.log.log(f"  ▶ Overload: {card.name}")
                    ol_cost = ManaCost.parse(card.overload)
                    self._tap_for_spell(act, ol_cost)
                    act.hand.remove(card)
                    self.cast_with_stack_alt(act, card, target, cast_with_overload=True)
                elif cast_type == "adventure":
                    adv_name = card.adventure.get("name", "Adventure")
                    self.log.log(f"  ▶ Adventure: {card.name} ({adv_name})")
                    adv_cost = ManaCost.parse(card.adventure.get("cost", ""))
                    self._tap_for_spell(act, adv_cost)
                    act.hand.remove(card)
                    self.cast_with_stack_alt(act, card, target, cast_as_adventure=True, adventure_abilities=extra)
                elif cast_type == "adventure_creature":
                    self.log.log(f"  ▶ Cast from exile: {card.name}")
                    self._tap_for_spell(act, card.mana_cost)
                    act.exile.remove(card)
                    card.on_adventure = False
                    self.cast_with_stack(act, card, target)
                else:
                    # Normal cast - handle X spells, modal, and kicker
                    x_value = 0
                    chosen_modes = []
                    was_kicked = False
                    kicker_count = 0

                    if card.mana_cost.has_x():
                        x_value = ai.determine_x_value(card, act.available_mana(), target)
                        self.log.log(f"  ▶ Cast: {card.name} (X={x_value})")
                    else:
                        self.log.log(f"  ▶ Cast: {card.name}")

                    # Modal spell mode selection
                    if card.modes:
                        chosen_modes = ai.choose_modes(card, {"target": target})
                        self.log.log(f"    Modes: {', '.join(chosen_modes)}")

                    # Kicker decision
                    available_mana = act.available_mana()
                    if card.kicker:
                        was_kicked = ai.should_kick(card, available_mana)
                        if was_kicked:
                            self.log.log(f"    Paying kicker: {card.kicker}")
                    elif card.multikicker:
                        kicker_count = ai.multikicker_count(card, available_mana)
                        if kicker_count > 0:
                            self.log.log(f"    Multikicker x{kicker_count}")

                    self._tap_for_spell_with_x(act, card.mana_cost, x_value)

                    # Pay kicker cost
                    if was_kicked and card.kicker:
                        kicker_cost = ManaCost.parse(card.kicker)
                        self._tap_for_spell(act, kicker_cost)
                    elif kicker_count > 0 and card.multikicker:
                        mk_cost = ManaCost.parse(card.multikicker)
                        for _ in range(kicker_count):
                            self._tap_for_spell(act, mk_cost)

                    act.hand.remove(card)
                    self.cast_with_stack(act, card, target, x_value, chosen_modes, was_kicked, kicker_count)
                if not self.check_state():
                    return False

        # Planeswalker loyalty ability activations (sorcery speed, after spells)
        pw_actions = ai.planeswalker_actions()
        for pw, ability_idx, effect, target in pw_actions:
            self.activate_loyalty_ability(act, pw, ability_idx, target)
            if not self.check_state():
                return False

        # Clear floating mana before combat (mana empties at phase change)
        act.mana_pool.clear()

        self.log.log("\n  === COMBAT ===")
        # Crew vehicles before declaring attackers
        crew_decisions = ai.crew_vehicles()
        for vehicle, crew_creatures in crew_decisions:
            self.crew_vehicle(act, vehicle, crew_creatures)

        attackers, attack_targets = ai.declare_attackers()

        if attackers:
            # Log planeswalker attack targets
            pw_attacks = {att_id: pw_id for att_id, pw_id in attack_targets.items() if pw_id is not None}
            if pw_attacks:
                for att_id, pw_id in pw_attacks.items():
                    att = next((a for a in attackers if a.instance_id == att_id), None)
                    pw = next((p for p in opp.battlefield if p.instance_id == pw_id), None)
                    if att and pw:
                        self.log.log(f"    {att.name} targets {pw.name}")

            opp_ai = AI(opp, act, self.log)
            blocks = opp_ai.blockers(attackers, attack_targets)
            self.combat(attackers, blocks, attack_targets)
            if not self.check_state():
                return False
        else:
            self.log.log("  No attacks.")

        # End of turn cleanup - remove temporary buffs
        self._end_of_turn_cleanup(act)
        self._end_of_turn_cleanup(opp)

        # Control-changing effects cleanup (Rule 108.4)
        # Remove "until end of turn" control effects and revert control
        self.control_manager.end_of_turn_cleanup()

        self.active_id = 3 - self.active_id
        return True

    def _tap_for_spell(self, player: Player, cost: ManaCost):
        """
        Tap mana sources (lands and dorks) to pay for a spell.
        Smart tapping: prefer lands over dorks, save colored mana when possible.
        """
        # Calculate how much of each color we need
        needed = {
            "W": cost.W, "U": cost.U, "B": cost.B,
            "R": cost.R, "G": cost.G, "generic": cost.generic
        }

        # First pass: tap lands for required colored mana
        for land in player.untapped_lands():
            if land.is_tapped:
                continue
            produces = land.produces if land.produces else detect_land_colors(land.name)
            if not produces:
                produces = ["C"]

            color = produces[0]
            # Tap for colored requirement
            if color in needed and needed[color] > 0:
                land.is_tapped = True
                player.mana_pool.add(color)
                needed[color] -= 1
            # Otherwise save for generic later

        # Second pass: tap mana dorks for remaining colored needs
        for dork in player.untapped_mana_dorks():
            if dork.is_tapped:
                continue
            produces = player.mana_dork_produces(dork)
            if not produces:
                continue

            color = produces[0] if produces[0] != "any" else "G"
            if color in needed and needed[color] > 0:
                dork.is_tapped = True
                player.mana_pool.add(color)
                needed[color] -= 1

        # Third pass: tap remaining lands for generic mana
        for land in player.untapped_lands():
            if land.is_tapped or needed["generic"] <= 0:
                continue
            produces = land.produces if land.produces else detect_land_colors(land.name)
            color = produces[0] if produces else "C"
            land.is_tapped = True
            player.mana_pool.add(color)
            needed["generic"] -= 1

        # Fourth pass: tap remaining dorks for generic mana
        for dork in player.untapped_mana_dorks():
            if dork.is_tapped or needed["generic"] <= 0:
                continue
            produces = player.mana_dork_produces(dork)
            color = produces[0] if produces and produces[0] != "any" else "G"
            dork.is_tapped = True
            player.mana_pool.add(color)
            needed["generic"] -= 1

    def _tap_for_spell_with_x(self, player: Player, cost: ManaCost, x_value: int):
        """
        Tap mana sources for a spell with X in its cost.
        x_value: The chosen value for X (total X cost = cost.X * x_value)
        """
        # Create a modified cost with X added to generic
        total_x_cost = cost.X * x_value
        modified_cost = ManaCost(
            generic=cost.generic + total_x_cost,
            W=cost.W, U=cost.U, B=cost.B, R=cost.R, G=cost.G, X=0
        )
        # Use existing tap logic
        self._tap_for_spell(player, modified_cost)

        # Pay the cost from the pool
        player.mana_pool.pay_cost(cost)

    def _end_of_turn_cleanup(self, player: Player):
        """Remove temporary buffs at end of turn and clear mana pool"""
        # Clear mana pool (mana empties at end of turn)
        player.mana_pool.clear()

        for c in player.battlefield:
            if c.card_type == "creature":
                # Remove prowess temp buffs
                if "+1/+1_temp" in c.counters:
                    buff = c.counters.pop("+1/+1_temp")
                    c.power -= buff
                    c.toughness -= buff
                # Remove landfall temp buffs
                if "+2/+2_temp" in c.counters:
                    c.counters.pop("+2/+2_temp")
                    c.power -= 2
                    c.toughness -= 2
                # Remove pump spell buffs (any amount)
                if "pump_temp" in c.counters:
                    c.counters.pop("pump_temp")
                    # Note: pump amounts vary, so we track them differently
                    # This is simplified - in full implementation track exact amounts
                # Remove temporary indestructible
                if "indestructible_temp" in c.counters:
                    c.counters.pop("indestructible_temp")
                    if "indestructible" in c.keywords:
                        c.keywords.remove("indestructible")
            # Reset crewed vehicles at end of turn
            if c.is_vehicle():
                c.is_crewed = False

    def play(self, max_turns: int = 30) -> int:
        self.deal_hands()
        self.log.log(f"\nP1 hand: {[c.name for c in self.p1.hand]}")
        self.log.log(f"P2 hand: {[c.name for c in self.p2.hand]}")
        
        while self.winner is None and self.turn < max_turns:
            if not self.play_turn():
                break
        
        if self.winner is None:
            if self.p1.life > self.p2.life:
                self.winner = 1
            elif self.p2.life > self.p1.life:
                self.winner = 2
            else:
                self.winner = random.choice([1, 2])
            self.log.log(f"\n⏰ Turn limit. Winner: P{self.winner}")
        
        return self.winner


# =============================================================================
# SIDEBOARD AI
# =============================================================================

class SideboardAI:
    """
    AI for making sideboard decisions between games.
    Uses archetype matchup heuristics to decide what to swap.
    """

    # Cards to bring in vs certain archetypes
    SIDEBOARD_GUIDE = {
        "aggro": {
            "bring_in": ["lifegain", "sweeper", "blocker", "fog", "removal"],
            "take_out": ["slow", "expensive", "greedy", "card_draw"]
        },
        "control": {
            "bring_in": ["threat", "haste", "planeswalker", "discard", "counter"],
            "take_out": ["removal", "sweeper", "lifegain"]
        },
        "midrange": {
            "bring_in": ["removal", "value", "card_advantage"],
            "take_out": ["narrow", "situational"]
        },
        "combo": {
            "bring_in": ["discard", "counter", "graveyard_hate", "artifact_hate"],
            "take_out": ["slow_removal", "lifegain"]
        }
    }

    # Keywords/abilities that indicate card categories
    CARD_CATEGORIES = {
        "lifegain": ["lifelink", "gain_life", "life"],
        "sweeper": ["damage_sweep", "destroy_all", "wrath"],
        "removal": ["destroy_creature", "exile", "damage_", "kill"],
        "counter": ["counter", "negate"],
        "discard": ["discard", "hand"],
        "threat": ["haste", "trample", "flying"],
        "graveyard_hate": ["exile_graveyard", "rest_in_peace"],
        "artifact_hate": ["destroy_artifact", "shatter"]
    }

    def __init__(self, deck: List[Card], sideboard: List[Card], archetype: str):
        self.deck = deck.copy()
        self.sideboard = sideboard.copy()
        self.archetype = archetype

    def categorize_card(self, card: Card) -> List[str]:
        """Determine what categories a card belongs to"""
        categories = []
        card_text = " ".join(card.abilities + card.keywords).lower()
        card_name = card.name.lower()

        for category, indicators in self.CARD_CATEGORIES.items():
            for indicator in indicators:
                if indicator in card_text or indicator in card_name:
                    categories.append(category)
                    break

        # Additional heuristics
        if card.card_type == "creature":
            if card.cmc() >= 5:
                categories.append("expensive")
            if card.cmc() <= 2 and card.eff_power() >= 2:
                categories.append("threat")
            if card.eff_toughness() >= 4:
                categories.append("blocker")

        if "draw" in card_text:
            categories.append("card_draw")
            categories.append("card_advantage")

        if card.cmc() >= 4 and card.card_type != "creature":
            categories.append("slow")

        return categories if categories else ["value"]

    def sideboard_for_matchup(self, opponent_archetype: str) -> Tuple[List[Card], List[Card]]:
        """
        Determine sideboard swaps for a given matchup.
        Returns (cards_in, cards_out).
        """
        guide = self.SIDEBOARD_GUIDE.get(opponent_archetype, self.SIDEBOARD_GUIDE["midrange"])

        # Score sideboard cards for bringing in
        cards_to_bring_in = []
        for card in self.sideboard:
            categories = self.categorize_card(card)
            score = 0
            for cat in categories:
                if cat in guide["bring_in"]:
                    score += 2
            if score > 0:
                cards_to_bring_in.append((card, score))

        # Sort by score, take top cards
        cards_to_bring_in.sort(key=lambda x: x[1], reverse=True)
        max_swaps = min(5, len(cards_to_bring_in))
        in_cards = [c for c, _ in cards_to_bring_in[:max_swaps]]

        # Find cards to take out from maindeck
        cards_to_take_out = []
        for card in self.deck:
            categories = self.categorize_card(card)
            score = 0
            for cat in categories:
                if cat in guide["take_out"]:
                    score += 2
                if cat in guide["bring_in"]:
                    score -= 1  # Don't remove cards that are good in this matchup
            if score > 0:
                cards_to_take_out.append((card, score))

        # Sort by score, take enough to match bring-in count
        cards_to_take_out.sort(key=lambda x: x[1], reverse=True)
        out_cards = [c for c, _ in cards_to_take_out[:len(in_cards)]]

        return in_cards, out_cards

    def apply_sideboard(self, in_cards: List[Card], out_cards: List[Card]):
        """Apply sideboard changes to deck"""
        for card in out_cards:
            # Find and remove one copy from deck
            for i, deck_card in enumerate(self.deck):
                if deck_card.name == card.name:
                    removed = self.deck.pop(i)
                    self.sideboard.append(removed)
                    break

        for card in in_cards:
            # Find and add from sideboard to deck
            for i, sb_card in enumerate(self.sideboard):
                if sb_card.name == card.name:
                    added = self.sideboard.pop(i)
                    self.deck.append(added)
                    break

        return self.deck, self.sideboard


# =============================================================================
# MATCH RUNNER
# =============================================================================

def run_match(deck1_txt: str, deck2_txt: str,
              name1: str = None, name2: str = None,
              matches: int = 5, games: int = 3, verbose: bool = False,
              sideboard: bool = True) -> Dict:
    """
    Run matches between two decks (MTGO .txt format).
    Supports sideboarding between games when sideboard=True.
    """
    cards1_orig, sb1_orig, n1, arch1 = parse_decklist(deck1_txt, name1)
    cards2_orig, sb2_orig, n2, arch2 = parse_decklist(deck2_txt, name2)

    print(f"\n{'#'*70}")
    print(f"  {n1} ({arch1}) vs {n2} ({arch2})")
    print(f"  {matches} best-of-{games}")
    if sideboard and (sb1_orig or sb2_orig):
        print(f"  Sideboarding: ON ({len(sb1_orig)} / {len(sb2_orig)} cards)")
    print(f"{'#'*70}")

    results = {
        "deck1": n1, "deck2": n2,
        "deck1_wins": 0, "deck2_wins": 0,
        "deck1_games": 0, "deck2_games": 0,
    }

    for m in range(1, matches + 1):
        print(f"\n>>> MATCH {m}")
        match = {"d1": 0, "d2": 0}

        # Start each match with original decks
        cards1 = [c.copy() for c in cards1_orig]
        cards2 = [c.copy() for c in cards2_orig]
        sb1 = [c.copy() for c in sb1_orig]
        sb2 = [c.copy() for c in sb2_orig]

        for g in range(1, games + 1):
            # Apply sideboarding after game 1
            if g > 1 and sideboard:
                # Deck 1 sideboards vs Deck 2's archetype
                if sb1:
                    sb_ai1 = SideboardAI(cards1, sb1, arch1)
                    in1, out1 = sb_ai1.sideboard_for_matchup(arch2)
                    if in1:
                        cards1, sb1 = sb_ai1.apply_sideboard(in1, out1)
                        in_names = list(set(c.name for c in in1))
                        print(f"  {n1} sideboards: +{in_names}")

                # Deck 2 sideboards vs Deck 1's archetype
                if sb2:
                    sb_ai2 = SideboardAI(cards2, sb2, arch2)
                    in2, out2 = sb_ai2.sideboard_for_matchup(arch1)
                    if in2:
                        cards2, sb2 = sb_ai2.apply_sideboard(in2, out2)
                        in_names = list(set(c.name for c in in2))
                        print(f"  {n2} sideboards: +{in_names}")

            if g % 2 == 1:
                engine = Game(cards1, n1, arch1, cards2, n2, arch2, verbose)
                d1_is_p1 = True
            else:
                engine = Game(cards2, n2, arch2, cards1, n1, arch1, verbose)
                d1_is_p1 = False

            winner = engine.play()
            d1_won = (winner == 1) == d1_is_p1

            if d1_won:
                match["d1"] += 1
                results["deck1_games"] += 1
                print(f"  Game {g}: {n1}")
            else:
                match["d2"] += 1
                results["deck2_games"] += 1
                print(f"  Game {g}: {n2}")

            needed = (games // 2) + 1
            if match["d1"] >= needed or match["d2"] >= needed:
                break

        if match["d1"] > match["d2"]:
            results["deck1_wins"] += 1
            print(f"  Match: {n1} wins {match['d1']}-{match['d2']}")
        else:
            results["deck2_wins"] += 1
            print(f"  Match: {n2} wins {match['d2']}-{match['d1']}")
    
    total = results["deck1_games"] + results["deck2_games"]
    d1_pct = results["deck1_games"] / total * 100 if total else 0
    d2_pct = results["deck2_games"] / total * 100 if total else 0
    
    print(f"\n{'='*70}")
    print(f"  FINAL RESULTS")
    print(f"{'='*70}")
    print(f"  {n1}: {results['deck1_wins']} matches, {results['deck1_games']} games ({d1_pct:.1f}%)")
    print(f"  {n2}: {results['deck2_wins']} matches, {results['deck2_games']} games ({d2_pct:.1f}%)")
    print(f"\n  WINNER: {n1 if results['deck1_games'] > results['deck2_games'] else n2}")
    print(f"{'='*70}")
    
    return results


def run_match_from_files(file1: str, file2: str,
                         name1: str = None, name2: str = None,
                         matches: int = 5, games: int = 3, verbose: bool = False,
                         sideboarding: bool = True) -> Dict:
    """Run match from .txt deck files. Supports sideboarding for Bo3."""
    with open(file1, 'r') as f:
        deck1 = f.read()
    with open(file2, 'r') as f:
        deck2 = f.read()
    return run_match(deck1, deck2, name1, name2, matches, games, verbose, sideboard=sideboarding)


if __name__ == "__main__":
    gruul = """
4 Magebane Lizard
4 Pugnacious Hammerskull
4 Trumpeting Carnosaur
3 Sentinel of the Nameless City
3 Itzquinth, Firstborn of Gishath
4 Bushwhack
4 Triumphant Chomp
2 Vivien Reid
2 Felidar Retreat
10 Forest
6 Mountain
4 Karplusan Forest
4 Rockface Village
"""
    
    izzet = """
4 Gran-Gran
4 Monument to Endurance
4 Stormchaser's Talent
4 Artist's Talent
4 Accumulate Wisdom
4 Combustion Technique
4 Firebending Lesson
3 Iroh's Demonstration
3 Boomerang Basics
8 Island
6 Mountain
4 Shivan Reef
4 Stormcarved Coast
"""
    
    run_match(gruul, izzet, "Gruul Spell-Punisher", "Izzet Lessons", matches=3, verbose=False)
