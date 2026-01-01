"""MTG Engine V3 - Deck Parser (MTGO format)

This module provides comprehensive decklist parsing and deck management for the MTG engine.
It handles MTGO-format decklists, validates against the card database, and provides
game-ready Deck objects with shuffle, draw, and search functionality.

MTGO Format:
    [Deck Name]_AI

    4 Card Name
    3 Another Card
    // Comment

    Sideboard
    2 Sideboard Card
"""
import os
import re
import random
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

from ..engine.objects import Card, Characteristics
from ..engine.mana import ManaCost
from ..engine.types import CardType
from .database import get_database, CardDatabase, CardData

if TYPE_CHECKING:
    from .database import CardDatabase


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DecklistEntry:
    """
    A single entry in a decklist representing a card and its count.

    Attributes:
        count: Number of copies of this card
        card_name: The name of the card
        is_sideboard: True if this entry belongs to the sideboard
    """
    count: int
    card_name: str
    is_sideboard: bool = False

    def __post_init__(self):
        """Validate entry data."""
        if self.count < 1:
            raise ValueError(f"Card count must be at least 1, got {self.count}")
        if not self.card_name or not self.card_name.strip():
            raise ValueError("Card name cannot be empty")
        self.card_name = self.card_name.strip()

    def __repr__(self) -> str:
        sb_marker = " (SB)" if self.is_sideboard else ""
        return f"DecklistEntry({self.count}x {self.card_name}{sb_marker})"


@dataclass
class Decklist:
    """
    A parsed decklist containing mainboard and sideboard entries.

    Attributes:
        name: The name of the deck
        entries: List of all DecklistEntry objects (main and sideboard)
        format: The format this deck is for (default: "standard")
    """
    name: str
    entries: List[DecklistEntry] = field(default_factory=list)
    format: str = "standard"

    @property
    def mainboard(self) -> List[DecklistEntry]:
        """Get all mainboard entries."""
        return [e for e in self.entries if not e.is_sideboard]

    @property
    def sideboard(self) -> List[DecklistEntry]:
        """Get all sideboard entries."""
        return [e for e in self.entries if e.is_sideboard]

    @property
    def mainboard_count(self) -> int:
        """Get the total number of cards in the mainboard."""
        return sum(e.count for e in self.mainboard)

    @property
    def sideboard_count(self) -> int:
        """Get the total number of cards in the sideboard."""
        return sum(e.count for e in self.sideboard)

    @property
    def total_count(self) -> int:
        """Get the total number of cards (main + sideboard)."""
        return self.mainboard_count + self.sideboard_count

    def get_card_counts(self) -> Dict[str, int]:
        """
        Get a dictionary mapping card names to their total count.

        Returns:
            Dict mapping card name to total count across main and sideboard
        """
        counts: Dict[str, int] = {}
        for entry in self.entries:
            if entry.card_name in counts:
                counts[entry.card_name] += entry.count
            else:
                counts[entry.card_name] = entry.count
        return counts

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the decklist according to standard constructed rules.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors: List[str] = []

        # Check mainboard size (typically 60 minimum for constructed)
        if self.mainboard_count < 60:
            errors.append(
                f"Mainboard has {self.mainboard_count} cards, minimum is 60"
            )

        # Check sideboard size (maximum 15 for constructed)
        if self.sideboard_count > 15:
            errors.append(
                f"Sideboard has {self.sideboard_count} cards, maximum is 15"
            )

        # Check 4-of rule (excluding basic lands)
        card_counts = self.get_card_counts()
        basic_lands = {
            "Plains", "Island", "Swamp", "Mountain", "Forest",
            "Snow-Covered Plains", "Snow-Covered Island",
            "Snow-Covered Swamp", "Snow-Covered Mountain",
            "Snow-Covered Forest", "Wastes"
        }

        for card_name, count in card_counts.items():
            if card_name not in basic_lands and count > 4:
                errors.append(
                    f"{card_name} has {count} copies, maximum is 4"
                )

        is_valid = len(errors) == 0
        return (is_valid, errors)

    def add_entry(self, count: int, card_name: str, is_sideboard: bool = False):
        """Add an entry to the decklist."""
        self.entries.append(DecklistEntry(count, card_name, is_sideboard))

    def __repr__(self) -> str:
        return (f"Decklist({self.name}: {self.mainboard_count} main, "
                f"{self.sideboard_count} sideboard)")


# =============================================================================
# Decklist Parser
# =============================================================================

class DecklistParser:
    """
    Parser for MTGO-format decklists.

    MTGO Format Rules:
        - Lines starting with // or # are comments (ignored)
        - Empty lines are ignored
        - "Sideboard" or "SB:" marks the beginning of sideboard section
        - Card entries are formatted as "N Card Name" where N is the count
        - Deck name can be detected from filename or first line ending with _AI

    Example:
        [Deck Name]_AI

        4 Lightning Bolt
        4 Monastery Swiftspear
        // This is a comment

        Sideboard
        2 Smash to Smithereens
    """

    # Patterns for parsing
    CARD_PATTERN = re.compile(r'^(\d+)\s+(.+)$')
    SIDEBOARD_MARKERS = {'sideboard', 'sb:', 'side:', 'side board'}
    COMMENT_PREFIXES = ('//', '#')

    def parse(self, text: str, deck_name: Optional[str] = None) -> Decklist:
        """
        Parse an MTGO-format decklist from text.

        Args:
            text: The decklist text in MTGO format
            deck_name: Optional deck name (will try to detect if not provided)

        Returns:
            Parsed Decklist object
        """
        entries: List[DecklistEntry] = []
        in_sideboard = False
        detected_name = deck_name

        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip comments
            if any(line.startswith(prefix) for prefix in self.COMMENT_PREFIXES):
                continue

            # Deck name detection (first line with _AI or containing "Deck")
            if detected_name is None:
                if '_AI' in line or (line and not self.CARD_PATTERN.match(line)):
                    # Could be a deck name line
                    potential_name = line.replace('_AI', '').replace('_', ' ').strip()
                    if potential_name and not self._is_sideboard_marker(potential_name):
                        detected_name = potential_name
                        continue

            # Check for sideboard marker
            if self._is_sideboard_marker(line):
                in_sideboard = True
                continue

            # Parse card entry
            match = self.CARD_PATTERN.match(line)
            if match:
                count = int(match.group(1))
                card_name = match.group(2).strip()

                # Handle potential "SB:" prefix inline
                if card_name.lower().startswith('sb:'):
                    card_name = card_name[3:].strip()
                    in_sideboard = True

                entries.append(DecklistEntry(
                    count=count,
                    card_name=card_name,
                    is_sideboard=in_sideboard
                ))

        # Default name if not detected
        if detected_name is None:
            main_count = sum(e.count for e in entries if not e.is_sideboard)
            detected_name = f"Unnamed Deck ({main_count} cards)"

        return Decklist(
            name=detected_name,
            entries=entries,
            format="standard"
        )

    def parse_file(self, path: str) -> Decklist:
        """
        Parse a decklist from a file.

        Args:
            path: Path to the decklist file

        Returns:
            Parsed Decklist object
        """
        filepath = Path(path)

        if not filepath.exists():
            raise FileNotFoundError(f"Decklist file not found: {path}")

        # Extract deck name from filename
        name = filepath.stem
        name = name.replace('_AI', '').replace('_', ' ')

        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()

        return self.parse(text, deck_name=name)

    def _is_sideboard_marker(self, line: str) -> bool:
        """Check if a line is a sideboard section marker."""
        line_lower = line.lower().strip()
        return line_lower in self.SIDEBOARD_MARKERS or line_lower.startswith('sideboard')


# =============================================================================
# Deck Class (Game-Ready)
# =============================================================================

class Deck:
    """
    A game-ready deck with Card objects for use in the game engine.

    This class wraps a Decklist and provides actual Card objects that can be
    used during gameplay, along with deck manipulation methods like shuffle,
    draw, and search.

    Attributes:
        decklist: The source Decklist object
        cards: List of Card objects in the main deck (library)
        sideboard: List of Card objects in the sideboard
    """

    def __init__(self, decklist: Decklist, cards: List[Card],
                 sideboard: List[Card]):
        """
        Initialize a deck with cards.

        Args:
            decklist: The source Decklist
            cards: List of Card objects for the main deck
            sideboard: List of Card objects for the sideboard
        """
        self.decklist = decklist
        self.cards = cards
        self.sideboard = sideboard
        self._next_id = 1

    @property
    def name(self) -> str:
        """Get the deck name."""
        return self.decklist.name

    @property
    def size(self) -> int:
        """Get the current number of cards in the deck."""
        return len(self.cards)

    @property
    def sideboard_size(self) -> int:
        """Get the number of cards in the sideboard."""
        return len(self.sideboard)

    def shuffle(self) -> None:
        """Shuffle the deck randomly."""
        random.shuffle(self.cards)

    def draw(self, n: int = 1) -> List[Card]:
        """
        Draw cards from the top of the deck.

        Args:
            n: Number of cards to draw

        Returns:
            List of drawn cards (may be fewer if deck doesn't have enough)
        """
        drawn: List[Card] = []
        for _ in range(min(n, len(self.cards))):
            if self.cards:
                drawn.append(self.cards.pop(0))
        return drawn

    def draw_one(self) -> Optional[Card]:
        """
        Draw a single card from the top of the deck.

        Returns:
            The drawn card, or None if deck is empty
        """
        cards = self.draw(1)
        return cards[0] if cards else None

    def put_on_top(self, card: Card) -> None:
        """
        Put a card on top of the deck.

        Args:
            card: The card to put on top
        """
        self.cards.insert(0, card)

    def put_on_bottom(self, card: Card) -> None:
        """
        Put a card on the bottom of the deck.

        Args:
            card: The card to put on bottom
        """
        self.cards.append(card)

    def search(self, filter_func: Callable[[Card], bool]) -> List[Card]:
        """
        Search the deck for cards matching a filter function.

        Note: This does not remove cards from the deck. Use for searching
        then remove/draw as needed.

        Args:
            filter_func: Function that takes a Card and returns True if it matches

        Returns:
            List of cards matching the filter
        """
        return [card for card in self.cards if filter_func(card)]

    def remove_card(self, card: Card) -> bool:
        """
        Remove a specific card from the deck.

        Args:
            card: The card to remove

        Returns:
            True if card was found and removed, False otherwise
        """
        if card in self.cards:
            self.cards.remove(card)
            return True
        return False

    def peek(self, n: int = 1) -> List[Card]:
        """
        Look at the top N cards without removing them.

        Args:
            n: Number of cards to look at

        Returns:
            List of top N cards
        """
        return self.cards[:n]

    def mill(self, n: int = 1) -> List[Card]:
        """
        Mill (remove from top to graveyard) N cards.

        Args:
            n: Number of cards to mill

        Returns:
            List of milled cards
        """
        return self.draw(n)  # Same as draw, caller handles zone change

    def exile_from_top(self, n: int = 1) -> List[Card]:
        """
        Exile N cards from the top of the deck.

        Args:
            n: Number of cards to exile

        Returns:
            List of exiled cards
        """
        return self.draw(n)  # Same as draw, caller handles zone change

    def reveal_top(self, n: int = 1) -> List[Card]:
        """
        Reveal the top N cards (doesn't remove them).

        Args:
            n: Number of cards to reveal

        Returns:
            List of revealed cards
        """
        return self.peek(n)

    def swap_with_sideboard(self, main_card: Card, side_card: Card) -> bool:
        """
        Swap a mainboard card with a sideboard card.

        Args:
            main_card: Card to move to sideboard
            side_card: Card to move to mainboard

        Returns:
            True if swap was successful
        """
        if main_card not in self.cards or side_card not in self.sideboard:
            return False

        self.cards.remove(main_card)
        self.sideboard.remove(side_card)
        self.cards.append(side_card)
        self.sideboard.append(main_card)
        return True

    def reset(self, database: 'CardDatabase') -> None:
        """
        Reset the deck to its original state from the decklist.

        Args:
            database: Card database to recreate cards from
        """
        new_deck = Deck.from_decklist(self.decklist, database)
        self.cards = new_deck.cards
        self.sideboard = new_deck.sideboard

    # =========================================================================
    # Class Methods (Factory Methods)
    # =========================================================================

    @classmethod
    def from_decklist(cls, decklist: Decklist,
                      database: 'CardDatabase') -> 'Deck':
        """
        Create a Deck from a Decklist using the card database.

        Args:
            decklist: The Decklist to convert
            database: CardDatabase to look up card data

        Returns:
            A new Deck with Card objects
        """
        cards: List[Card] = []
        sideboard: List[Card] = []
        next_id = 1

        for entry in decklist.entries:
            card_data = database.get(entry.card_name)

            # Create placeholder if not in database
            if card_data is None:
                card_data = cls._create_unknown_card(entry.card_name)

            # Create N copies of the card
            for _ in range(entry.count):
                card = cls._create_card_from_data(card_data, next_id)
                next_id += 1

                if entry.is_sideboard:
                    sideboard.append(card)
                else:
                    cards.append(card)

        return cls(decklist, cards, sideboard)

    @classmethod
    def from_file(cls, path: str, database: 'CardDatabase') -> 'Deck':
        """
        Create a Deck from a decklist file.

        Args:
            path: Path to the decklist file
            database: CardDatabase to look up card data

        Returns:
            A new Deck with Card objects
        """
        parser = DecklistParser()
        decklist = parser.parse_file(path)
        return cls.from_decklist(decklist, database)

    @classmethod
    def from_text(cls, text: str, database: 'CardDatabase',
                  name: Optional[str] = None) -> 'Deck':
        """
        Create a Deck from decklist text.

        Args:
            text: The decklist text in MTGO format
            database: CardDatabase to look up card data
            name: Optional deck name

        Returns:
            A new Deck with Card objects
        """
        parser = DecklistParser()
        decklist = parser.parse(text, deck_name=name)
        return cls.from_decklist(decklist, database)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def _create_card_from_data(data: CardData, card_id: int) -> Card:
        """Create a Card object from CardData."""
        # Parse mana cost if present
        if data.mana_cost:
            mana_cost = ManaCost.parse(data.mana_cost)
        elif data.cmc > 0:
            # Create generic mana cost placeholder
            mana_cost = ManaCost.parse(f"{{{data.cmc}}}")
        else:
            mana_cost = ManaCost()

        chars = Characteristics(
            name=data.name,
            mana_cost=mana_cost,
            types=data.types.copy() if data.types else set(),
            subtypes=data.subtypes.copy() if data.subtypes else set(),
            supertypes=data.supertypes.copy() if data.supertypes else set(),
            colors=data.colors.copy() if data.colors else set(),
            power=data.power,
            toughness=data.toughness,
            loyalty=data.loyalty,
            rules_text=data.oracle_text
        )

        card = Card(
            object_id=card_id,
            characteristics=chars,
            base_characteristics=chars.copy()
        )

        # Add keywords to cache
        if data.keywords:
            card._keyword_cache = {kw.lower() for kw in data.keywords}

        return card

    @staticmethod
    def _create_unknown_card(name: str) -> CardData:
        """Create a placeholder CardData for unknown cards."""
        return CardData(
            name=name,
            cmc=2,
            types={CardType.CREATURE},
            power=2,
            toughness=2,
            oracle_text=f"(Unknown card: {name})"
        )

    def __repr__(self) -> str:
        return f"Deck({self.name}: {self.size} cards, {self.sideboard_size} sideboard)"

    def __len__(self) -> int:
        return self.size


# =============================================================================
# Helper Functions
# =============================================================================

def load_test_decks(directory: str) -> Dict[str, Deck]:
    """
    Load all .txt decklist files from a directory.

    Args:
        directory: Path to directory containing decklist files

    Returns:
        Dictionary mapping deck name to Deck object
    """
    decks: Dict[str, Deck] = {}
    database = get_database()
    directory_path = Path(directory)

    if not directory_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory_path.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")

    for filepath in directory_path.glob("*.txt"):
        try:
            deck = Deck.from_file(str(filepath), database)
            decks[deck.name] = deck
        except Exception as e:
            # Log warning but continue loading other decks
            print(f"Warning: Failed to load {filepath}: {e}")

    return decks


def find_unknown_cards(decklist: Decklist,
                       database: 'CardDatabase') -> List[str]:
    """
    Find card names in a decklist that are not in the database.

    Args:
        decklist: The Decklist to check
        database: CardDatabase to look up cards in

    Returns:
        List of card names not found in the database
    """
    unknown: List[str] = []

    for entry in decklist.entries:
        if database.get_card(entry.card_name) is None:
            if entry.card_name not in unknown:
                unknown.append(entry.card_name)

    return unknown


def validate_decklist_against_database(decklist: Decklist,
                                       database: 'CardDatabase') -> Tuple[bool, List[str]]:
    """
    Comprehensive validation of a decklist including database lookup.

    Args:
        decklist: The Decklist to validate
        database: CardDatabase to validate against

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    # Start with format validation
    is_valid, errors = decklist.validate()

    # Check for unknown cards
    unknown = find_unknown_cards(decklist, database)
    if unknown:
        for card_name in unknown:
            errors.append(f"Unknown card: {card_name}")
        is_valid = False

    return (is_valid, errors)


# =============================================================================
# Legacy Compatibility Functions
# =============================================================================

def parse_decklist(text: str, name: Optional[str] = None) -> Decklist:
    """
    Parse a decklist string.

    This is a convenience function for backwards compatibility.

    Args:
        text: The decklist text
        name: Optional deck name

    Returns:
        Parsed Decklist object
    """
    parser = DecklistParser()
    return parser.parse(text, deck_name=name)


def load_deck_file(filepath: str) -> Decklist:
    """
    Load a decklist from a file.

    This is a convenience function for backwards compatibility.

    Args:
        filepath: Path to the decklist file

    Returns:
        Parsed Decklist object
    """
    parser = DecklistParser()
    return parser.parse_file(filepath)


# =============================================================================
# Type Exports
# =============================================================================

__all__ = [
    # Data classes
    'DecklistEntry',
    'Decklist',

    # Parser
    'DecklistParser',

    # Game deck
    'Deck',

    # Helper functions
    'load_test_decks',
    'find_unknown_cards',
    'validate_decklist_against_database',

    # Legacy compatibility
    'parse_decklist',
    'load_deck_file',
]
