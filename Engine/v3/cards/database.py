"""MTG Engine V3 - Enhanced Card Database System

This module provides a comprehensive card database system that:
- Stores card data in structured dataclasses
- Supports loading from V1 database format
- Provides JSON import/export
- Offers search and filtering capabilities
- Creates engine Card objects from database entries
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, ClassVar, Any, TYPE_CHECKING
from pathlib import Path
import re
import json
import ast
import hashlib

from ..engine.types import (
    Color, CardType, Supertype, AbilityType, Zone,
    ObjectId, PlayerId
)

if TYPE_CHECKING:
    from ..engine.objects import Card, Token, Permanent, Characteristics, ManaCost


# =============================================================================
# Security: Database Hash Verification (SEC-003)
# =============================================================================

# SEC-003: Known good SHA-256 hashes for trusted database files
# Add hashes of verified database files here for integrity checking
TRUSTED_DATABASE_HASHES: set = set()

# SEC-003: Enable strict mode to require hash verification
STRICT_DATABASE_VERIFICATION: bool = False


def register_trusted_database_hash(file_hash: str) -> None:
    """
    SEC-003: Register a SHA-256 hash as trusted for database loading.

    Args:
        file_hash: SHA-256 hex digest of a trusted database file
    """
    TRUSTED_DATABASE_HASHES.add(file_hash.lower())


def _compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def _verify_database_integrity(path: Path) -> bool:
    """
    SEC-003: Verify database file integrity using SHA-256 hash.

    Args:
        path: Path to the database file

    Returns:
        True if hash matches a trusted hash, or if no hashes are registered

    Raises:
        ValueError: If STRICT_DATABASE_VERIFICATION is True and hash doesn't match
    """
    if not TRUSTED_DATABASE_HASHES:
        # No hashes registered - allow loading (development mode)
        return True

    file_hash = _compute_file_hash(path)

    if file_hash in TRUSTED_DATABASE_HASHES:
        return True

    if STRICT_DATABASE_VERIFICATION:
        raise ValueError(
            f"SEC-003: Database integrity check failed for {path}. "
            f"Hash {file_hash} is not in the trusted list. "
            f"This may indicate file tampering."
        )

    # Warn but allow in non-strict mode
    import warnings
    warnings.warn(
        f"SEC-003: Database file {path} has unknown hash {file_hash}. "
        f"Consider verifying the file and registering its hash.",
        SecurityWarning
    )
    return False


class SecurityWarning(UserWarning):
    """Warning for security-related issues."""
    pass


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AbilityData:
    """
    Structured ability data for card abilities.

    Attributes:
        ability_type: Type of ability ("triggered", "activated", "static", "mana", "keyword")
        text: The full ability text
        cost: Optional activation cost for activated abilities (e.g., "{2}{U}, {T}")
        trigger: Optional trigger condition for triggered abilities
    """
    ability_type: str  # "triggered", "activated", "static", "mana", "keyword"
    text: str
    cost: Optional[str] = None  # For activated abilities
    trigger: Optional[str] = None  # For triggered abilities

    def is_triggered(self) -> bool:
        return self.ability_type == "triggered"

    def is_activated(self) -> bool:
        return self.ability_type == "activated"

    def is_static(self) -> bool:
        return self.ability_type == "static"

    def is_mana_ability(self) -> bool:
        return self.ability_type == "mana"

    def is_keyword(self) -> bool:
        return self.ability_type == "keyword"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "ability_type": self.ability_type,
            "text": self.text
        }
        if self.cost:
            result["cost"] = self.cost
        if self.trigger:
            result["trigger"] = self.trigger
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AbilityData':
        """Create from dictionary."""
        return cls(
            ability_type=data.get("ability_type", "static"),
            text=data.get("text", ""),
            cost=data.get("cost"),
            trigger=data.get("trigger")
        )


@dataclass
class CardData:
    """
    Complete card data structure matching MTG card properties.

    Attributes:
        name: Card name
        mana_cost: Mana cost string (e.g., "{2}{U}{U}")
        cmc: Converted mana cost / mana value
        types: List of card types (e.g., ["Creature"])
        subtypes: List of subtypes (e.g., ["Human", "Wizard"])
        supertypes: List of supertypes (e.g., ["Legendary"])
        oracle_text: Full oracle text
        power: Power for creatures (can be "*" or "X")
        toughness: Toughness for creatures
        loyalty: Starting loyalty for planeswalkers
        colors: List of colors
        color_identity: Color identity for Commander
        keywords: List of keyword abilities
        abilities: List of parsed AbilityData
    """
    name: str
    mana_cost: str = ""  # e.g., "{2}{U}{U}"
    cmc: int = 0
    types: List[str] = field(default_factory=list)  # e.g., ["Creature"]
    subtypes: List[str] = field(default_factory=list)  # e.g., ["Human", "Wizard"]
    supertypes: List[str] = field(default_factory=list)  # e.g., ["Legendary"]
    oracle_text: str = ""
    power: Optional[str] = None  # Can be "*" or "X"
    toughness: Optional[str] = None
    loyalty: Optional[int] = None
    colors: List[str] = field(default_factory=list)
    color_identity: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    abilities: List[AbilityData] = field(default_factory=list)

    # Additional metadata
    rarity: str = "common"
    set_code: str = ""
    collector_number: str = ""

    def is_creature(self) -> bool:
        return "Creature" in self.types or "creature" in self.types

    def is_instant(self) -> bool:
        return "Instant" in self.types or "instant" in self.types

    def is_sorcery(self) -> bool:
        return "Sorcery" in self.types or "sorcery" in self.types

    def is_enchantment(self) -> bool:
        return "Enchantment" in self.types or "enchantment" in self.types

    def is_artifact(self) -> bool:
        return "Artifact" in self.types or "artifact" in self.types

    def is_land(self) -> bool:
        return "Land" in self.types or "land" in self.types

    def is_planeswalker(self) -> bool:
        return "Planeswalker" in self.types or "planeswalker" in self.types

    def is_legendary(self) -> bool:
        return "Legendary" in self.supertypes or "legendary" in self.supertypes

    def is_permanent_type(self) -> bool:
        """Check if this card becomes a permanent when it resolves."""
        permanent_types = {"creature", "artifact", "enchantment", "land", "planeswalker", "battle"}
        return any(t.lower() in permanent_types for t in self.types)

    def has_keyword(self, keyword: str) -> bool:
        """Check if card has a keyword ability."""
        return keyword.lower() in [k.lower() for k in self.keywords]

    def get_power_value(self) -> Optional[int]:
        """Get numeric power value, or None if variable."""
        if self.power is None:
            return None
        if self.power in ("*", "X", "?"):
            return 0  # Variable power treated as 0 in most contexts
        try:
            return int(self.power)
        except ValueError:
            return 0

    def get_toughness_value(self) -> Optional[int]:
        """Get numeric toughness value, or None if variable."""
        if self.toughness is None:
            return None
        if self.toughness in ("*", "X", "?"):
            return 0
        try:
            return int(self.toughness)
        except ValueError:
            return 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "mana_cost": self.mana_cost,
            "cmc": self.cmc,
            "types": self.types,
            "subtypes": self.subtypes,
            "supertypes": self.supertypes,
            "oracle_text": self.oracle_text,
            "colors": self.colors,
            "color_identity": self.color_identity,
            "keywords": self.keywords,
            "abilities": [a.to_dict() for a in self.abilities]
        }
        if self.power is not None:
            result["power"] = self.power
        if self.toughness is not None:
            result["toughness"] = self.toughness
        if self.loyalty is not None:
            result["loyalty"] = self.loyalty
        if self.rarity != "common":
            result["rarity"] = self.rarity
        if self.set_code:
            result["set_code"] = self.set_code
        if self.collector_number:
            result["collector_number"] = self.collector_number
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CardData':
        """Create from dictionary."""
        abilities = [
            AbilityData.from_dict(a) if isinstance(a, dict) else a
            for a in data.get("abilities", [])
        ]
        return cls(
            name=data.get("name", ""),
            mana_cost=data.get("mana_cost", ""),
            cmc=data.get("cmc", 0),
            types=data.get("types", []),
            subtypes=data.get("subtypes", []),
            supertypes=data.get("supertypes", []),
            oracle_text=data.get("oracle_text", ""),
            power=data.get("power"),
            toughness=data.get("toughness"),
            loyalty=data.get("loyalty"),
            colors=data.get("colors", []),
            color_identity=data.get("color_identity", []),
            keywords=data.get("keywords", []),
            abilities=abilities,
            rarity=data.get("rarity", "common"),
            set_code=data.get("set_code", ""),
            collector_number=data.get("collector_number", "")
        )


# =============================================================================
# Card Database (Singleton)
# =============================================================================

class CardDatabase:
    """
    Singleton card database with ability parsing and search capabilities.

    The database stores CardData objects and provides methods for:
    - Adding and retrieving cards
    - Loading from V1 database format
    - JSON import/export
    - Searching and filtering cards
    """

    _instance: ClassVar[Optional['CardDatabase']] = None

    def __new__(cls) -> 'CardDatabase':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the database (only once due to singleton)."""
        if self._initialized:
            return

        self.cards: Dict[str, CardData] = {}
        self._name_index: Dict[str, str] = {}  # lowercase -> actual name
        self._type_index: Dict[str, List[str]] = {}  # type -> card names
        self._keyword_index: Dict[str, List[str]] = {}  # keyword -> card names
        self._initialized = True

        # Try to load the V1 database on initialization
        self._load_v1_database_if_exists()

    def get(self, name: str) -> Optional[CardData]:
        """
        Get card data by name (case-insensitive).

        Args:
            name: Card name to look up

        Returns:
            CardData if found, None otherwise
        """
        # Exact match first
        if name in self.cards:
            return self.cards[name]

        # Case-insensitive lookup
        name_lower = name.lower()
        if name_lower in self._name_index:
            actual_name = self._name_index[name_lower]
            return self.cards.get(actual_name)

        return None

    def add(self, card: CardData):
        """
        Add a card to the database.

        Args:
            card: CardData to add
        """
        self.cards[card.name] = card
        self._name_index[card.name.lower()] = card.name

        # Update type index
        for card_type in card.types:
            type_lower = card_type.lower()
            if type_lower not in self._type_index:
                self._type_index[type_lower] = []
            if card.name not in self._type_index[type_lower]:
                self._type_index[type_lower].append(card.name)

        # Update keyword index
        for keyword in card.keywords:
            kw_lower = keyword.lower()
            if kw_lower not in self._keyword_index:
                self._keyword_index[kw_lower] = []
            if card.name not in self._keyword_index[kw_lower]:
                self._keyword_index[kw_lower].append(card.name)

    def remove(self, name: str) -> bool:
        """
        Remove a card from the database.

        Args:
            name: Card name to remove

        Returns:
            True if removed, False if not found
        """
        card = self.get(name)
        if card is None:
            return False

        # Remove from main storage
        del self.cards[card.name]

        # Remove from name index
        self._name_index.pop(card.name.lower(), None)

        # Remove from type index
        for card_type in card.types:
            type_lower = card_type.lower()
            if type_lower in self._type_index:
                if card.name in self._type_index[type_lower]:
                    self._type_index[type_lower].remove(card.name)

        # Remove from keyword index
        for keyword in card.keywords:
            kw_lower = keyword.lower()
            if kw_lower in self._keyword_index:
                if card.name in self._keyword_index[kw_lower]:
                    self._keyword_index[kw_lower].remove(card.name)

        return True

    def load_from_v1_database(self, path: str):
        """
        Load cards from V1 card_database.py format.

        SEC-003: Uses SHA-256 hash verification before loading untrusted data.

        The V1 format is a Python dict literal:
        CARD_DATABASE = {
            "Card Name": {"type": "creature", "cost": 3.0, ...},
            ...
        }

        Args:
            path: Path to the V1 database file

        Raises:
            FileNotFoundError: If the database file doesn't exist
            ValueError: If hash verification fails in strict mode (SEC-003)
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"V1 database not found: {path}")

        # SEC-003: Verify database integrity before loading
        _verify_database_integrity(path_obj)

        content = path_obj.read_text(encoding='utf-8')

        # Extract the CARD_DATABASE dictionary
        # Look for CARD_DATABASE = { ... }
        match = re.search(r'CARD_DATABASE\s*=\s*(\{.+\})', content, re.DOTALL)
        if not match:
            raise ValueError("Could not find CARD_DATABASE in file")

        # SEC-003: Parse the dictionary using ast.literal_eval
        # Note: ast.literal_eval is safe for literals but we add hash
        # verification as defense in depth against file tampering
        try:
            v1_db = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"Failed to parse V1 database: {e}")

        # Validate the parsed data structure
        if not isinstance(v1_db, dict):
            raise ValueError("SEC-003: Database must be a dictionary")

        # Convert each entry
        for name, data in v1_db.items():
            if not isinstance(name, str) or not isinstance(data, dict):
                raise ValueError(f"SEC-003: Invalid entry format for '{name}'")
            card = parse_v1_entry(name, data)
            self.add(card)

    def load_from_json(self, path: str):
        """
        Load cards from a JSON file.

        Args:
            path: Path to JSON file
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")

        with open(path_obj, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            # List of card objects
            for card_dict in data:
                card = CardData.from_dict(card_dict)
                self.add(card)
        elif isinstance(data, dict):
            # Dictionary keyed by card name
            for name, card_dict in data.items():
                if "name" not in card_dict:
                    card_dict["name"] = name
                card = CardData.from_dict(card_dict)
                self.add(card)

    def save_to_json(self, path: str, indent: int = 2):
        """
        Save all cards to a JSON file.

        Args:
            path: Path to output file
            indent: JSON indentation level
        """
        data = {name: card.to_dict() for name, card in self.cards.items()}

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

    def search(self, query: str) -> List[CardData]:
        """
        Search for cards matching a query string.

        Searches card names and oracle text (case-insensitive).

        Args:
            query: Search query

        Returns:
            List of matching CardData
        """
        query_lower = query.lower()
        results = []

        for card in self.cards.values():
            # Search in name
            if query_lower in card.name.lower():
                results.append(card)
                continue

            # Search in oracle text
            if query_lower in card.oracle_text.lower():
                results.append(card)
                continue

            # Search in keywords
            if any(query_lower in kw.lower() for kw in card.keywords):
                results.append(card)
                continue

        return results

    def get_by_type(self, card_type: str) -> List[CardData]:
        """
        Get all cards of a specific type.

        Args:
            card_type: Type to filter by (e.g., "Creature", "Instant")

        Returns:
            List of matching CardData
        """
        type_lower = card_type.lower()
        if type_lower in self._type_index:
            return [self.cards[name] for name in self._type_index[type_lower]
                    if name in self.cards]
        return []

    def get_by_keyword(self, keyword: str) -> List[CardData]:
        """
        Get all cards with a specific keyword.

        Args:
            keyword: Keyword to filter by (e.g., "flying", "trample")

        Returns:
            List of matching CardData
        """
        kw_lower = keyword.lower()
        if kw_lower in self._keyword_index:
            return [self.cards[name] for name in self._keyword_index[kw_lower]
                    if name in self.cards]
        return []

    def get_by_cmc(self, cmc: int) -> List[CardData]:
        """
        Get all cards with a specific converted mana cost.

        Args:
            cmc: Mana value to filter by

        Returns:
            List of matching CardData
        """
        return [card for card in self.cards.values() if card.cmc == cmc]

    def get_by_color(self, color: str) -> List[CardData]:
        """
        Get all cards containing a specific color.

        Args:
            color: Color to filter by (e.g., "W", "U", "B", "R", "G")

        Returns:
            List of matching CardData
        """
        color_upper = color.upper()
        return [card for card in self.cards.values() if color_upper in card.colors]

    def get_creatures(self) -> List[CardData]:
        """Get all creature cards."""
        return self.get_by_type("creature")

    def get_instants(self) -> List[CardData]:
        """Get all instant cards."""
        return self.get_by_type("instant")

    def get_sorceries(self) -> List[CardData]:
        """Get all sorcery cards."""
        return self.get_by_type("sorcery")

    def get_lands(self) -> List[CardData]:
        """Get all land cards."""
        return self.get_by_type("land")

    def __len__(self) -> int:
        """Return number of cards in database."""
        return len(self.cards)

    def __contains__(self, name: str) -> bool:
        """Check if a card is in the database."""
        return self.get(name) is not None

    def __iter__(self):
        """Iterate over all cards."""
        return iter(self.cards.values())

    def _load_v1_database_if_exists(self):
        """Try to load the V1 database if it exists."""
        v1_path = Path(__file__).parent.parent.parent / "V1_mtg_sim_package" / "card_database.py"
        if v1_path.exists():
            try:
                self.load_from_v1_database(str(v1_path))
            except Exception as e:
                # Log error but don't crash
                print(f"Warning: Failed to load V1 database: {e}")


# =============================================================================
# V1 Database Adapter
# =============================================================================

def parse_v1_entry(name: str, data: dict) -> CardData:
    """
    Parse a V1 database entry into CardData.

    V1 format:
    {"type": "creature", "cost": 3.0, "power": 3, "toughness": 2,
     "keywords": [...], "abilities": [...]}

    Args:
        name: Card name
        data: V1 data dictionary

    Returns:
        CardData object
    """
    # Map V1 type to proper type names
    type_mapping = {
        "creature": "Creature",
        "instant": "Instant",
        "sorcery": "Sorcery",
        "enchantment": "Enchantment",
        "artifact": "Artifact",
        "land": "Land",
        "planeswalker": "Planeswalker",
        "battle": "Battle"
    }

    v1_type = data.get("type", "creature").lower()
    types = [type_mapping.get(v1_type, v1_type.capitalize())]

    # Parse cost into mana cost string and CMC
    raw_cost = data.get("cost", 0)
    cmc = int(raw_cost) if isinstance(raw_cost, (int, float)) else 0

    # Estimate mana cost string from CMC (simplified)
    mana_cost = f"{{{cmc}}}" if cmc > 0 else ""

    # Get keywords (normalize to lowercase)
    keywords_raw = data.get("keywords", [])
    keywords = [kw.replace("_", " ") for kw in keywords_raw]

    # Parse abilities
    abilities = []
    v1_abilities = data.get("abilities", [])
    for ab in v1_abilities:
        ability_data = _parse_v1_ability(ab)
        abilities.append(ability_data)

    # Create keyword abilities for each keyword
    for kw in keywords:
        abilities.append(AbilityData(
            ability_type="keyword",
            text=kw
        ))

    # Get power/toughness
    power = data.get("power")
    toughness = data.get("toughness")

    # Convert to string if present
    power_str = str(power) if power is not None else None
    toughness_str = str(toughness) if toughness is not None else None

    # Get loyalty for planeswalkers
    loyalty = data.get("loyalty")

    # Estimate colors from mana cost (simplified - would need proper parsing)
    colors = _estimate_colors_from_keywords(keywords)

    return CardData(
        name=name,
        mana_cost=mana_cost,
        cmc=cmc,
        types=types,
        subtypes=[],  # V1 doesn't have subtypes
        supertypes=[],  # V1 doesn't have supertypes
        oracle_text="",  # V1 doesn't have oracle text
        power=power_str,
        toughness=toughness_str,
        loyalty=loyalty,
        colors=colors,
        color_identity=colors,
        keywords=keywords,
        abilities=abilities
    )


def _parse_v1_ability(ability_text: str) -> AbilityData:
    """
    Parse a V1 ability string into AbilityData.

    V1 abilities are simple strings like:
    - "draw_1", "draw_2", "draw_3"
    - "damage_3", "damage_variable"
    - "create_token", "create_token_1_1", "create_token_2_2"
    - "destroy_creature", "destroy_artifact"
    - "counter_spell"
    - "exile"
    - "bounce"
    - "pump_2_2"
    - "mana_dork"
    - "landfall"
    - "spell_trigger"
    - "fight", "bite"

    Args:
        ability_text: V1 ability string

    Returns:
        AbilityData object
    """
    text = ability_text.lower().replace("_", " ")

    # Determine ability type based on text patterns
    if "trigger" in text or "landfall" in text:
        ability_type = "triggered"
        trigger = _infer_trigger(ability_text)
    elif "mana dork" in text or text.startswith("add "):
        ability_type = "mana"
        trigger = None
    else:
        # Most V1 abilities are effects of activated/triggered abilities
        ability_type = "activated"
        trigger = None

    # Generate readable text
    readable_text = _v1_ability_to_text(ability_text)

    return AbilityData(
        ability_type=ability_type,
        text=readable_text,
        trigger=trigger
    )


def _infer_trigger(ability_text: str) -> str:
    """Infer trigger condition from V1 ability."""
    text_lower = ability_text.lower()

    if "landfall" in text_lower:
        return "Whenever a land enters the battlefield under your control"
    if "spell_trigger" in text_lower:
        return "Whenever you cast a spell"
    if "etb" in text_lower:
        return "When this enters the battlefield"
    if "dies" in text_lower:
        return "When this dies"
    if "attack" in text_lower:
        return "Whenever this creature attacks"

    return "When triggered"


def _v1_ability_to_text(ability_text: str) -> str:
    """Convert V1 ability code to readable text."""
    text = ability_text.lower()

    # Draw abilities
    if text.startswith("draw_"):
        try:
            count = int(text.split("_")[1])
            return f"Draw {count} card{'s' if count > 1 else ''}."
        except (IndexError, ValueError):
            return "Draw a card."

    # Damage abilities
    if text.startswith("damage_"):
        parts = text.split("_")
        if len(parts) > 1:
            if parts[1] == "variable":
                return "Deal X damage."
            try:
                amount = int(parts[1])
                return f"Deal {amount} damage."
            except ValueError:
                pass
        return "Deal damage."

    # Token creation
    if text.startswith("create_token"):
        parts = text.split("_")
        if len(parts) >= 4:
            try:
                power = int(parts[2])
                toughness = int(parts[3])
                return f"Create a {power}/{toughness} creature token."
            except ValueError:
                pass
        return "Create a token."

    # Destruction
    if text == "destroy_creature":
        return "Destroy target creature."
    if text == "destroy_artifact":
        return "Destroy target artifact."

    # Counter
    if text == "counter_spell":
        return "Counter target spell."

    # Exile
    if text == "exile":
        return "Exile target permanent."

    # Bounce
    if text == "bounce":
        return "Return target permanent to its owner's hand."

    # Pump
    if text.startswith("pump_"):
        parts = text.split("_")
        if len(parts) >= 3:
            try:
                power = int(parts[1])
                toughness = int(parts[2])
                return f"Target creature gets +{power}/+{toughness} until end of turn."
            except ValueError:
                pass
        return "Target creature gets +X/+X until end of turn."

    # Mana abilities
    if text == "mana_dork":
        return "Tap: Add one mana of any color."

    # Landfall
    if text == "landfall":
        return "Landfall - Whenever a land enters the battlefield under your control, trigger an effect."

    # Fight/Bite
    if text == "fight":
        return "Target creature you control fights another target creature."
    if text == "bite":
        return "Target creature you control deals damage equal to its power to target creature."

    # Default
    return ability_text.replace("_", " ").capitalize() + "."


def _estimate_colors_from_keywords(keywords: List[str]) -> List[str]:
    """
    Estimate card colors from keywords (very rough heuristic).

    This is a placeholder - proper color determination requires mana cost parsing.
    """
    colors = []

    # These are rough associations, not rules
    keyword_color_hints = {
        "flying": ["W", "U"],
        "lifelink": ["W", "B"],
        "vigilance": ["W", "G"],
        "first strike": ["W", "R"],
        "double strike": ["W", "R"],
        "flash": ["U"],
        "hexproof": ["U", "G"],
        "deathtouch": ["B", "G"],
        "menace": ["B", "R"],
        "haste": ["R"],
        "trample": ["G", "R"],
        "reach": ["G"],
    }

    # Don't actually assign colors based on keywords - return empty
    # This is just for reference
    return colors


# =============================================================================
# Card Factory
# =============================================================================

def create_card_from_data(data: CardData, object_id: ObjectId = 0,
                          owner_id: PlayerId = 0) -> 'Card':
    """
    Create an engine Card object from CardData.

    Args:
        data: CardData to convert
        object_id: Unique object ID for the card
        owner_id: Player ID of the card owner

    Returns:
        Card object ready for use in the engine
    """
    # Import here to avoid circular imports
    from ..engine.objects import Card, Characteristics, ManaCost as MC

    # Parse mana cost
    mana_cost = MC.parse(data.mana_cost) if data.mana_cost else MC()

    # Convert types to CardType enum
    types = set()
    type_mapping = {
        "creature": CardType.CREATURE,
        "instant": CardType.INSTANT,
        "sorcery": CardType.SORCERY,
        "enchantment": CardType.ENCHANTMENT,
        "artifact": CardType.ARTIFACT,
        "land": CardType.LAND,
        "planeswalker": CardType.PLANESWALKER,
        "battle": CardType.BATTLE,
    }
    for t in data.types:
        if t.lower() in type_mapping:
            types.add(type_mapping[t.lower()])

    # Convert supertypes to Supertype enum
    supertypes = set()
    supertype_mapping = {
        "legendary": Supertype.LEGENDARY,
        "basic": Supertype.BASIC,
        "snow": Supertype.SNOW,
        "world": Supertype.WORLD,
    }
    for st in data.supertypes:
        if st.lower() in supertype_mapping:
            supertypes.add(supertype_mapping[st.lower()])

    # Convert colors to Color enum
    colors = set()
    color_mapping = {
        "W": Color.WHITE,
        "U": Color.BLUE,
        "B": Color.BLACK,
        "R": Color.RED,
        "G": Color.GREEN,
    }
    for c in data.colors:
        if c.upper() in color_mapping:
            colors.add(color_mapping[c.upper()])

    # Get power/toughness as integers
    power = data.get_power_value()
    toughness = data.get_toughness_value()

    # Create characteristics
    characteristics = Characteristics(
        name=data.name,
        mana_cost=mana_cost,
        colors=colors,
        types=types,
        subtypes=set(data.subtypes),
        supertypes=supertypes,
        rules_text=data.oracle_text,
        power=power,
        toughness=toughness,
        loyalty=data.loyalty
    )

    # Create the card
    card = Card(
        object_id=object_id,
        owner_id=owner_id,
        controller_id=owner_id,
        characteristics=characteristics,
        printed_characteristics=characteristics.copy(),
        zone=Zone.LIBRARY
    )

    return card


def create_token(name: str, power: int, toughness: int,
                 types: List[str], colors: List[str] = None,
                 keywords: List[str] = None,
                 owner_id: PlayerId = 0,
                 controller_id: PlayerId = 0,
                 object_id: ObjectId = 0) -> 'Token':
    """
    Create a token with the specified characteristics.

    Args:
        name: Token name (e.g., "Soldier", "Zombie")
        power: Token power
        toughness: Token toughness
        types: Card types (typically ["Creature"] plus creature types)
        colors: Colors (e.g., ["W"], ["B"])
        keywords: Keyword abilities (e.g., ["flying", "lifelink"])
        owner_id: Owner player ID
        controller_id: Controller player ID
        object_id: Unique object ID

    Returns:
        Token object
    """
    # Import here to avoid circular imports
    from ..engine.objects import Token as TokenClass, Characteristics

    colors = colors or []
    keywords = keywords or []

    # Convert types
    type_set = set()
    type_mapping = {
        "creature": CardType.CREATURE,
        "artifact": CardType.ARTIFACT,
        "enchantment": CardType.ENCHANTMENT,
    }
    subtypes = set()

    for t in types:
        t_lower = t.lower()
        if t_lower in type_mapping:
            type_set.add(type_mapping[t_lower])
        else:
            # Treat as subtype (creature type)
            subtypes.add(t)

    # If no main types specified, default to Creature
    if not type_set:
        type_set.add(CardType.CREATURE)

    # Convert colors
    color_set = set()
    color_mapping = {
        "W": Color.WHITE,
        "U": Color.BLUE,
        "B": Color.BLACK,
        "R": Color.RED,
        "G": Color.GREEN,
    }
    for c in colors:
        if c.upper() in color_mapping:
            color_set.add(color_mapping[c.upper()])

    # Create characteristics
    characteristics = Characteristics(
        name=f"{name} Token",
        types=type_set,
        subtypes=subtypes,
        colors=color_set,
        power=power,
        toughness=toughness
    )

    # Create token
    token = TokenClass(
        object_id=object_id,
        owner_id=owner_id,
        controller_id=controller_id,
        characteristics=characteristics,
        zone=Zone.BATTLEFIELD,
        token_definition_name=name
    )

    # Add keywords
    for kw in keywords:
        token.add_keyword(kw)

    return token


# =============================================================================
# Ability Parser
# =============================================================================

class AbilityParser:
    """Parse Oracle text into structured abilities."""

    KEYWORDS = [
        'flying', 'trample', 'haste', 'vigilance', 'reach', 'deathtouch',
        'lifelink', 'first strike', 'double strike', 'menace', 'hexproof',
        'indestructible', 'flash', 'defender', 'ward', 'protection',
        'shroud', 'fear', 'intimidate', 'shadow', 'horsemanship',
        'infect', 'wither', 'prowess', 'convoke', 'delve', 'cascade',
        'flashback', 'madness', 'cycling', 'kicker', 'multikicker'
    ]

    TRIGGER_PATTERNS = [
        (r'^When(ever)?\s+(.+?),\s*(.+)$', 'triggered'),
        (r'^At the beginning of (.+?),\s*(.+)$', 'triggered_phase'),
        (r'^Whenever\s+(.+?),\s*(.+)$', 'triggered'),
    ]

    ACTIVATED_PATTERN = r'^(.+?):\s*(.+)$'

    def parse(self, oracle_text: str, card_name: str = "") -> List[AbilityData]:
        """
        Parse Oracle text into abilities.

        Args:
            oracle_text: The Oracle text to parse
            card_name: Card name for self-reference resolution

        Returns:
            List of AbilityData objects
        """
        abilities = []

        # Split into paragraphs
        paragraphs = oracle_text.split('\n')

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Replace card name with "this"
            if card_name:
                para = para.replace(card_name, "this")

            # Check for keywords
            keywords_found = self._extract_keywords(para)
            for kw in keywords_found:
                abilities.append(AbilityData(
                    ability_type="keyword",
                    text=kw
                ))

            # Check for triggered abilities
            for pattern, ab_type in self.TRIGGER_PATTERNS:
                match = re.match(pattern, para, re.IGNORECASE)
                if match:
                    if ab_type == 'triggered_phase':
                        abilities.append(AbilityData(
                            ability_type="triggered",
                            text=para,
                            trigger=f"At the beginning of {match.group(1)}"
                        ))
                    else:
                        trigger = match.group(2) if len(match.groups()) > 2 else match.group(1)
                        abilities.append(AbilityData(
                            ability_type="triggered",
                            text=para,
                            trigger=trigger
                        ))
                    break

            # Check for activated abilities
            if ':' in para:
                match = re.match(self.ACTIVATED_PATTERN, para)
                if match:
                    cost = match.group(1)
                    effect = match.group(2)

                    # Check if it's a mana ability
                    if 'add' in effect.lower() and any(c in effect for c in 'WUBRG'):
                        ab_type = "mana"
                    else:
                        ab_type = "activated"

                    abilities.append(AbilityData(
                        ability_type=ab_type,
                        text=para,
                        cost=cost
                    ))

        return abilities

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keyword abilities from text."""
        found = []
        text_lower = text.lower()

        for keyword in self.KEYWORDS:
            if keyword in text_lower:
                # Check it's a standalone keyword
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    found.append(keyword)

        return found


# =============================================================================
# Global Database Instance and Helpers
# =============================================================================

def get_database() -> CardDatabase:
    """Get the global card database instance."""
    return CardDatabase()


def get_card(name: str) -> Optional[CardData]:
    """
    Get a card by name from the global database.

    Args:
        name: Card name

    Returns:
        CardData if found, None otherwise
    """
    return get_database().get(name)


def search_cards(query: str) -> List[CardData]:
    """
    Search for cards in the global database.

    Args:
        query: Search query

    Returns:
        List of matching CardData
    """
    return get_database().search(query)


# =============================================================================
# V1 Database Path
# =============================================================================

V1_DATABASE_PATH = Path(__file__).parent.parent.parent / "V1_mtg_sim_package" / "card_database.py"


# =============================================================================
# Module Initialization
# =============================================================================

# Create the singleton instance on module load
_database: Optional[CardDatabase] = None


def _init_database():
    """Initialize the global database."""
    global _database
    if _database is None:
        _database = CardDatabase()
    return _database


# Initialize on import
_init_database()
