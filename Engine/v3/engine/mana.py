"""MTG Engine V3 - Mana System Implementation

This module implements the complete mana system per Comprehensive Rules 106-107.
Handles mana symbols, mana costs, mana pools, and general costs for abilities.

CR 106 - Mana
CR 107 - Numbers and Symbols
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Iterator, TYPE_CHECKING
)

from .types import Color, ObjectId

if TYPE_CHECKING:
    pass


# =============================================================================
# Mana Symbol
# =============================================================================

@dataclass
class ManaSymbol:
    """Represents a single mana symbol in a mana cost.

    Per CR 107.4, mana symbols represent mana or mana costs.

    Examples:
        - "W" - White mana
        - "2" - Generic mana (2)
        - "X" - Variable generic mana
        - "W/U" - Hybrid white/blue
        - "2/W" - Hybrid generic/white
        - "W/P" - Phyrexian white (pay W or 2 life)
        - "C" - Colorless mana (specifically colorless, not generic)
        - "S" - Snow mana

    Attributes:
        symbol: The string representation of the symbol.
        is_generic: True if this is a generic mana cost (can be paid with any color).
        generic_amount: For generic costs, the numeric amount required.
        colors: Set of colors this symbol represents or can be paid with.
        is_x: True if this is an X (variable) mana symbol.
        is_hybrid: True if this is a hybrid mana symbol.
        is_phyrexian: True if this can be paid with 2 life instead of mana.
    """
    symbol: str = ""
    is_generic: bool = False
    generic_amount: int = 0
    colors: Set[Color] = field(default_factory=set)
    is_x: bool = False
    is_hybrid: bool = False
    is_phyrexian: bool = False
    is_snow: bool = False
    is_colorless: bool = False  # Specifically colorless (C), not generic

    # For hybrid symbols, store the two options
    hybrid_options: Tuple[str, str] = field(default=("", ""))

    def __post_init__(self):
        """Ensure colors is a set."""
        if not isinstance(self.colors, set):
            self.colors = set(self.colors) if self.colors else set()

    def __hash__(self) -> int:
        return hash((self.symbol, self.is_generic, self.generic_amount,
                     frozenset(self.colors), self.is_x, self.is_hybrid,
                     self.is_phyrexian, self.is_snow, self.is_colorless))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ManaSymbol):
            return False
        return (self.symbol == other.symbol and
                self.is_generic == other.is_generic and
                self.generic_amount == other.generic_amount and
                self.colors == other.colors and
                self.is_x == other.is_x and
                self.is_hybrid == other.is_hybrid and
                self.is_phyrexian == other.is_phyrexian)

    @classmethod
    def parse(cls, symbol_str: str) -> 'ManaSymbol':
        """Parse a mana symbol string into a ManaSymbol object.

        Args:
            symbol_str: The symbol string (e.g., "W", "2", "X", "W/U", "2/W", "W/P")

        Returns:
            A ManaSymbol object representing the parsed symbol.
        """
        symbol_str = symbol_str.strip().upper()

        # X cost (variable)
        if symbol_str == 'X':
            return cls(
                symbol='X',
                is_generic=True,
                is_x=True
            )

        # Snow mana
        if symbol_str == 'S':
            return cls(
                symbol='S',
                is_snow=True
            )

        # Colorless mana (specifically colorless, e.g., from Eldrazi)
        if symbol_str == 'C':
            return cls(
                symbol='C',
                is_colorless=True,
                colors=set([Color.COLORLESS])
            )

        # Generic mana (numeric)
        if symbol_str.isdigit():
            amount = int(symbol_str)
            return cls(
                symbol=symbol_str,
                is_generic=True,
                generic_amount=amount
            )

        # Phyrexian mana (e.g., "W/P", "U/P", "P/W", "PW")
        phyrexian_match = re.match(r'^([WUBRG])/P$|^P/([WUBRG])$|^P([WUBRG])$|^([WUBRG])P$',
                                   symbol_str)
        if phyrexian_match:
            color_char = (phyrexian_match.group(1) or
                         phyrexian_match.group(2) or
                         phyrexian_match.group(3) or
                         phyrexian_match.group(4))
            color = _char_to_color(color_char)
            return cls(
                symbol=f'{color_char}/P',
                is_phyrexian=True,
                colors=set([color]) if color else set()
            )

        # Hybrid mana (e.g., "W/U", "2/W")
        hybrid_match = re.match(r'^([WUBRGC2])/([WUBRGC])$', symbol_str)
        if hybrid_match:
            opt1, opt2 = hybrid_match.groups()
            colors = set()
            is_generic = False

            # First option
            if opt1.isdigit():
                is_generic = True
            else:
                c1 = _char_to_color(opt1)
                if c1 and c1 != Color.COLORLESS:
                    colors.add(c1)

            # Second option
            c2 = _char_to_color(opt2)
            if c2 and c2 != Color.COLORLESS:
                colors.add(c2)

            return cls(
                symbol=symbol_str,
                is_hybrid=True,
                colors=colors,
                hybrid_options=(opt1, opt2)
            )

        # Single colored mana
        color = _char_to_color(symbol_str)
        if color and color != Color.COLORLESS:
            return cls(
                symbol=symbol_str,
                colors=set([color])
            )

        # Unknown symbol - treat as generic 0
        return cls(
            symbol=symbol_str,
            is_generic=True,
            generic_amount=0
        )

    @classmethod
    def from_color(cls, color: Color) -> 'ManaSymbol':
        """Create a ManaSymbol from a Color.

        Args:
            color: The Color enum value.

        Returns:
            A ManaSymbol for that color.
        """
        if color == Color.COLORLESS:
            return cls(
                symbol='C',
                is_colorless=True,
                colors=set([Color.COLORLESS])
            )

        symbol = color.value
        return cls(
            symbol=symbol,
            colors=set([color])
        )

    def can_be_paid_with(self, color: Color) -> bool:
        """Check if this symbol can be paid with mana of the given color.

        Args:
            color: The color of mana to check.

        Returns:
            True if this symbol can be paid with the given color.
        """
        # Generic can be paid with any color
        if self.is_generic and not self.is_colorless:
            return True

        # Colorless specifically requires colorless
        if self.is_colorless:
            return color == Color.COLORLESS

        # Snow can be paid with any snow mana (simplified - any mana from snow source)
        if self.is_snow:
            return True  # In full implementation, check if mana is from snow source

        # Phyrexian can be paid with the color or 2 life
        if self.is_phyrexian:
            return color in self.colors

        # Hybrid can be paid with either option
        if self.is_hybrid:
            opt1, opt2 = self.hybrid_options
            if opt1.isdigit():
                return True  # Generic option means any color works
            c1 = _char_to_color(opt1)
            c2 = _char_to_color(opt2)
            return color == c1 or color == c2

        # Regular colored mana
        return color in self.colors

    def cmc_contribution(self) -> int:
        """Get this symbol's contribution to converted mana cost.

        Per CR 202.3, each mana symbol contributes to mana value.

        Returns:
            The mana value contribution of this symbol.
        """
        if self.is_x:
            return 0  # X is 0 except on stack
        if self.is_generic:
            return self.generic_amount
        if self.is_hybrid:
            # Hybrid symbols contribute 1 or 2 (for 2/X hybrids)
            opt1, _ = self.hybrid_options
            if opt1.isdigit():
                return int(opt1)
            return 1
        # All other symbols (colored, phyrexian, snow, colorless) contribute 1
        return 1

    def __str__(self) -> str:
        return f'{{{self.symbol}}}'

    def __repr__(self) -> str:
        return f'ManaSymbol({self.symbol!r})'


# =============================================================================
# Mana Cost
# =============================================================================

@dataclass
class ManaCost:
    """Represents a complete mana cost.

    Per CR 202, a mana cost is a characteristic that defines what mana
    must be paid to cast a spell.

    Examples:
        - "{2}{U}{U}" - 2 generic, 2 blue (Counterspell)
        - "{W}{U}{B}{R}{G}" - WUBRG (Sliver Overlord)
        - "{X}{R}{R}" - X and 2 red (Blaze)

    Attributes:
        symbols: List of ManaSymbol objects comprising this cost.
        original_string: The original string representation of this cost.
    """
    symbols: List[ManaSymbol] = field(default_factory=list)
    original_string: str = ""

    def __post_init__(self):
        """Parse original_string if symbols not provided."""
        if self.original_string and not self.symbols:
            parsed = ManaCost.parse(self.original_string)
            self.symbols = parsed.symbols

    @property
    def cmc(self) -> int:
        """Calculate converted mana cost / mana value.

        Per CR 202.3, the mana value is the total amount of mana in a cost.

        Returns:
            The total mana value of this cost.
        """
        return sum(s.cmc_contribution() for s in self.symbols)

    @property
    def mana_value(self) -> int:
        """Alias for cmc (mana value is the current terminology)."""
        return self.cmc

    @property
    def colors(self) -> Set[Color]:
        """Get all colors in this mana cost.

        Per CR 202.2, a card's color is determined by its mana cost
        (among other things like color indicators).

        Returns:
            Set of colors in this cost.
        """
        result: Set[Color] = set()
        for symbol in self.symbols:
            result.update(c for c in symbol.colors if c != Color.COLORLESS)
        return result

    @property
    def is_free(self) -> bool:
        """Check if this cost is free (zero mana).

        Returns:
            True if this cost requires no mana to pay.
        """
        return len(self.symbols) == 0 or all(
            s.is_x or (s.is_generic and s.generic_amount == 0)
            for s in self.symbols
        )

    @property
    def has_x(self) -> bool:
        """Check if this cost contains X.

        Returns:
            True if the cost contains an X symbol.
        """
        return any(s.is_x for s in self.symbols)

    @property
    def x_count(self) -> int:
        """Count the number of X symbols in the cost.

        Returns:
            Number of X symbols.
        """
        return sum(1 for s in self.symbols if s.is_x)

    @classmethod
    def parse(cls, cost_str: str) -> 'ManaCost':
        """Parse a mana cost string into a ManaCost object.

        Args:
            cost_str: The cost string (e.g., "{2}{U}{U}", "2UU", "WUBRG")

        Returns:
            A ManaCost object representing the parsed cost.
        """
        if not cost_str:
            return cls(symbols=[], original_string="")

        original = cost_str
        symbols: List[ManaSymbol] = []

        # Handle curly brace format: {2}{U}{U}
        brace_pattern = r'\{([^}]+)\}'
        brace_matches = re.findall(brace_pattern, cost_str)

        if brace_matches:
            for match in brace_matches:
                symbols.append(ManaSymbol.parse(match))
        else:
            # Handle compact format: 2UU, WUBRG
            i = 0
            while i < len(cost_str):
                c = cost_str[i].upper()

                # Check for multi-digit generic
                if c.isdigit():
                    num_str = c
                    while i + 1 < len(cost_str) and cost_str[i + 1].isdigit():
                        i += 1
                        num_str += cost_str[i]
                    symbols.append(ManaSymbol.parse(num_str))

                # Check for hybrid (next char is /)
                elif i + 2 < len(cost_str) and cost_str[i + 1] == '/':
                    hybrid_str = cost_str[i:i + 3]
                    symbols.append(ManaSymbol.parse(hybrid_str))
                    i += 2

                # Check for Phyrexian with P prefix
                elif c == 'P' and i + 1 < len(cost_str):
                    phyrexian_str = cost_str[i:i + 2]
                    symbols.append(ManaSymbol.parse(phyrexian_str))
                    i += 1

                # Single character
                elif c in 'WUBRGCSX':
                    symbols.append(ManaSymbol.parse(c))

                i += 1

        return cls(symbols=symbols, original_string=original)

    def can_be_paid_with(self, pool: 'ManaPool') -> bool:
        """Check if this cost can be paid with the given mana pool.

        Args:
            pool: The mana pool to check against.

        Returns:
            True if the pool contains enough mana to pay this cost.
        """
        return pool.can_pay(self)

    def get_payment_options(self, pool: 'ManaPool') -> List[Dict[Color, int]]:
        """Get possible ways to pay this cost from the pool.

        For costs with multiple payment options (hybrid, phyrexian),
        returns all valid payment combinations.

        Args:
            pool: The mana pool to pay from.

        Returns:
            List of payment dictionaries mapping Color to amount used.
        """
        if not self.symbols:
            return [{}]  # Free cost has one trivial payment

        # Build list of requirements
        requirements: List[List[Tuple[Color, int]]] = []

        for symbol in self.symbols:
            options: List[Tuple[Color, int]] = []

            if symbol.is_x:
                # X can be paid with any amount of any mana
                # For get_payment_options, we treat X as 0 (caller specifies x_value)
                continue

            if symbol.is_generic:
                # Generic can be paid with any color
                for color in Color:
                    options.append((color, symbol.generic_amount))
                requirements.append(options)

            elif symbol.is_hybrid:
                opt1, opt2 = symbol.hybrid_options
                if opt1.isdigit():
                    # 2/W style - can pay with 2 generic or 1 colored
                    amount = int(opt1)
                    for color in Color:
                        options.append((color, amount))
                    c2 = _char_to_color(opt2)
                    if c2:
                        options.append((c2, 1))
                else:
                    c1 = _char_to_color(opt1)
                    c2 = _char_to_color(opt2)
                    if c1:
                        options.append((c1, 1))
                    if c2:
                        options.append((c2, 1))
                requirements.append(options)

            elif symbol.is_phyrexian:
                # Phyrexian can be paid with color or 2 life (life handled separately)
                for color in symbol.colors:
                    options.append((color, 1))
                requirements.append(options)

            elif symbol.is_colorless:
                # Must be paid with colorless
                options.append((Color.COLORLESS, 1))
                requirements.append(options)

            else:
                # Regular colored mana
                for color in symbol.colors:
                    options.append((color, 1))
                requirements.append(options)

        # Generate valid payment combinations
        # This is a simplified version - full implementation would use
        # backtracking to find all valid combinations
        valid_payments: List[Dict[Color, int]] = []

        def backtrack(idx: int, current_payment: Dict[Color, int],
                      remaining: Dict[Color, int]) -> None:
            if idx == len(requirements):
                valid_payments.append(current_payment.copy())
                return

            for color, amount in requirements[idx]:
                if remaining.get(color, 0) >= amount:
                    current_payment[color] = current_payment.get(color, 0) + amount
                    new_remaining = remaining.copy()
                    new_remaining[color] = new_remaining.get(color, 0) - amount
                    backtrack(idx + 1, current_payment, new_remaining)
                    current_payment[color] = current_payment.get(color, 0) - amount
                    if current_payment[color] == 0:
                        del current_payment[color]

        # Get available mana from pool
        available = {
            Color.WHITE: pool.get_amount(Color.WHITE),
            Color.BLUE: pool.get_amount(Color.BLUE),
            Color.BLACK: pool.get_amount(Color.BLACK),
            Color.RED: pool.get_amount(Color.RED),
            Color.GREEN: pool.get_amount(Color.GREEN),
            Color.COLORLESS: pool.get_amount(Color.COLORLESS),
        }

        backtrack(0, {}, available)
        return valid_payments

    def __str__(self) -> str:
        if not self.symbols:
            return "{0}"
        return ''.join(str(s) for s in self.symbols)

    def __repr__(self) -> str:
        return f'ManaCost({str(self)!r})'

    def __add__(self, other: 'ManaCost') -> 'ManaCost':
        """Combine two mana costs."""
        return ManaCost(
            symbols=self.symbols + other.symbols,
            original_string=str(self) + str(other)
        )

    def __bool__(self) -> bool:
        """A cost is truthy if it's not free."""
        return not self.is_free


# =============================================================================
# Mana (Single Unit)
# =============================================================================

@dataclass
class Mana:
    """Represents a single unit of mana in a mana pool.

    Per CR 106.1, mana is the primary resource in Magic.
    Mana can have restrictions on how it can be spent.

    Attributes:
        color: The color of this mana.
        source: The permanent that produced this mana (for tracking).
        restrictions: List of spending restrictions (e.g., "only for creature spells").
    """
    color: Color
    source: Optional[Any] = None
    restrictions: List[str] = field(default_factory=list)
    is_snow: bool = False

    def __post_init__(self):
        """Ensure restrictions is a list."""
        if self.restrictions is None:
            self.restrictions = []

    def can_pay_for(self, spell_or_ability: Any = None,
                    restriction_checker: Optional[callable] = None) -> bool:
        """Check if this mana can be used to pay for something.

        Args:
            spell_or_ability: The thing being paid for.
            restriction_checker: Optional function to check restrictions.

        Returns:
            True if this mana can be used for the payment.
        """
        if not self.restrictions:
            return True

        if restriction_checker:
            return restriction_checker(self.restrictions, spell_or_ability)

        # Without a checker, assume restricted mana cannot be used
        return False

    def __str__(self) -> str:
        prefix = "S" if self.is_snow else ""
        return f'{prefix}{self.color.value}'

    def __repr__(self) -> str:
        return f'Mana({self.color!r}, source={self.source!r})'


# =============================================================================
# Mana Pool
# =============================================================================

@dataclass
class ManaPool:
    """Represents a player's mana pool.

    Per CR 106.4, a mana pool is where mana is stored until spent.
    Mana empties from pools at the end of each step and phase.

    This implementation tracks individual Mana objects to support
    restrictions and snow mana tracking.

    Attributes:
        mana: List of Mana objects in the pool.
    """
    mana: List[Mana] = field(default_factory=list)

    def add(self, color: Color, amount: int = 1, source: Any = None,
            restrictions: Optional[List[str]] = None, is_snow: bool = False) -> None:
        """Add mana to the pool.

        Args:
            color: The color of mana to add.
            amount: How many mana of that color to add.
            source: The permanent that produced this mana.
            restrictions: Any spending restrictions.
            is_snow: Whether this is snow mana.
        """
        for _ in range(amount):
            self.mana.append(Mana(
                color=color,
                source=source,
                restrictions=restrictions or [],
                is_snow=is_snow
            ))

    def add_mana(self, mana: Mana) -> None:
        """Add a Mana object directly to the pool.

        Args:
            mana: The Mana object to add.
        """
        self.mana.append(mana)

    def get_amount(self, color: Color) -> int:
        """Get the amount of mana of a specific color.

        Args:
            color: The color to count.

        Returns:
            Number of mana of that color in the pool.
        """
        return sum(1 for m in self.mana if m.color == color)

    def total(self) -> int:
        """Get total mana in the pool.

        Returns:
            Total count of all mana in the pool.
        """
        return len(self.mana)

    def can_pay(self, cost: ManaCost, x_value: int = 0) -> bool:
        """Check if this pool can pay a mana cost.

        Args:
            cost: The mana cost to check.
            x_value: The value chosen for X.

        Returns:
            True if the pool can pay the cost.
        """
        # Build requirement list
        requirements = self._build_requirements(cost, x_value)

        # Try to find a valid assignment
        available = self._get_available_by_color()
        return self._can_satisfy_requirements(requirements, available)

    def pay(self, cost: ManaCost, x_value: int = 0) -> bool:
        """Pay a mana cost from this pool.

        Uses the same backtracking algorithm as can_pay() to find a valid
        payment configuration, then removes exactly those mana from the pool.

        Args:
            cost: The mana cost to pay.
            x_value: The value chosen for X.

        Returns:
            True if the cost was paid successfully.
        """
        requirements = self._build_requirements(cost, x_value)

        # Find exact mana to remove using backtracking
        mana_indices_to_remove = self._find_payment(requirements)

        if mana_indices_to_remove is None:
            return False

        # Remove mana in reverse index order to preserve indices during removal
        for idx in sorted(mana_indices_to_remove, reverse=True):
            self.mana.pop(idx)

        return True

    def _find_payment(self, requirements: List[Set[Color]]) -> Optional[List[int]]:
        """Find which mana to remove to satisfy requirements.

        Uses backtracking to find a valid assignment of mana pool indices
        to requirements, matching the algorithm used by can_pay().

        Args:
            requirements: List of acceptable color sets for each mana to pay.

        Returns:
            List of mana pool indices to remove, or None if no valid payment exists.
        """
        if not requirements:
            return []

        # Sort requirements by restrictiveness (fewer options first)
        # Keep track of original indices
        sorted_reqs = sorted(enumerate(requirements), key=lambda x: len(x[1]))

        # Build a mapping of color -> list of mana pool indices with that color
        color_to_indices: Dict[Color, List[int]] = {}
        for idx, m in enumerate(self.mana):
            if m.color not in color_to_indices:
                color_to_indices[m.color] = []
            color_to_indices[m.color].append(idx)

        # Result will be stored here if found
        result: Optional[List[int]] = None

        def backtrack(req_idx: int, used_indices: Set[int],
                      assignment: List[Tuple[int, int]]) -> bool:
            """
            Try to satisfy requirements starting from req_idx.

            Args:
                req_idx: Current position in sorted_reqs
                used_indices: Set of mana pool indices already assigned
                assignment: List of (original_req_idx, mana_pool_idx) pairs

            Returns:
                True if a valid assignment was found.
            """
            nonlocal result

            if req_idx == len(sorted_reqs):
                # All requirements satisfied - extract the mana indices
                result = [mana_idx for _, mana_idx in assignment]
                return True

            original_idx, acceptable_colors = sorted_reqs[req_idx]

            for color in acceptable_colors:
                if color not in color_to_indices:
                    continue
                for mana_idx in color_to_indices[color]:
                    if mana_idx not in used_indices:
                        # Try using this mana
                        used_indices.add(mana_idx)
                        assignment.append((original_idx, mana_idx))

                        if backtrack(req_idx + 1, used_indices, assignment):
                            return True

                        # Backtrack
                        assignment.pop()
                        used_indices.remove(mana_idx)

            return False

        backtrack(0, set(), [])
        return result

    def empty(self) -> None:
        """Empty the mana pool.

        Per CR 106.4b, mana empties from pools at the end of each step and phase.
        """
        self.mana.clear()

    def colors_available(self) -> Set[Color]:
        """Get colors of mana available in the pool.

        Returns:
            Set of colors present in the pool.
        """
        return {m.color for m in self.mana}

    def _build_requirements(self, cost: ManaCost, x_value: int) -> List[Set[Color]]:
        """Build a list of color requirements from a mana cost.

        Each requirement is a set of colors that can satisfy that part of the cost.

        Args:
            cost: The mana cost.
            x_value: The value for X.

        Returns:
            List of sets of acceptable colors for each mana to pay.
        """
        requirements: List[Set[Color]] = []
        all_colors = set(Color)

        for symbol in cost.symbols:
            if symbol.is_x:
                # Add x_value generic requirements
                for _ in range(x_value):
                    requirements.append(all_colors)

            elif symbol.is_generic:
                # Generic can be paid with any color
                for _ in range(symbol.generic_amount):
                    requirements.append(all_colors)

            elif symbol.is_colorless:
                # Must be paid with colorless
                requirements.append({Color.COLORLESS})

            elif symbol.is_hybrid:
                opt1, opt2 = symbol.hybrid_options
                acceptable = set()

                if opt1.isdigit():
                    # 2/W style hybrid
                    amount = int(opt1)
                    # For simplicity, treat as "pay 1 of this color OR pay N generic"
                    c2 = _char_to_color(opt2)
                    if c2:
                        acceptable.add(c2)
                    # Add generic option (any color)
                    acceptable.update(all_colors)
                    requirements.append(acceptable)
                else:
                    c1 = _char_to_color(opt1)
                    c2 = _char_to_color(opt2)
                    if c1:
                        acceptable.add(c1)
                    if c2:
                        acceptable.add(c2)
                    requirements.append(acceptable)

            elif symbol.is_phyrexian:
                # Phyrexian can be paid with color (life payment handled elsewhere)
                requirements.append(symbol.colors.copy())

            else:
                # Regular colored mana
                requirements.append(symbol.colors.copy())

        return requirements

    def _get_available_by_color(self) -> Dict[Color, int]:
        """Get count of available mana by color.

        Returns:
            Dictionary mapping colors to available amounts.
        """
        available: Dict[Color, int] = {}
        for m in self.mana:
            available[m.color] = available.get(m.color, 0) + 1
        return available

    def _can_satisfy_requirements(self, requirements: List[Set[Color]],
                                   available: Dict[Color, int]) -> bool:
        """Check if requirements can be satisfied with available mana.

        Uses a greedy algorithm with backtracking for correctness.

        Args:
            requirements: List of acceptable color sets for each mana.
            available: Available mana counts by color.

        Returns:
            True if all requirements can be satisfied.
        """
        if not requirements:
            return True

        # Sort by restrictiveness (fewer options first)
        sorted_reqs = sorted(enumerate(requirements), key=lambda x: len(x[1]))

        def backtrack(idx: int, remaining: Dict[Color, int]) -> bool:
            if idx == len(sorted_reqs):
                return True

            _, acceptable = sorted_reqs[idx]
            for color in acceptable:
                if remaining.get(color, 0) > 0:
                    new_remaining = remaining.copy()
                    new_remaining[color] -= 1
                    if backtrack(idx + 1, new_remaining):
                        return True

            return False

        return backtrack(0, available.copy())

    def __str__(self) -> str:
        """String representation of the mana pool.

        Returns a readable format like "2W 1U 1B 1R" or "Empty".
        """
        if not self.mana:
            return "Empty"

        counts: Dict[Color, int] = {}
        for m in self.mana:
            counts[m.color] = counts.get(m.color, 0) + 1

        # Order: W U B R G C
        order = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN, Color.COLORLESS]
        parts = []
        for color in order:
            if color in counts:
                parts.append(f"{counts[color]}{color.value}")

        return ' '.join(parts) if parts else "Empty"

    def __repr__(self) -> str:
        counts = {}
        for m in self.mana:
            counts[m.color] = counts.get(m.color, 0) + 1
        return f"ManaPool({counts})"

    def __len__(self) -> int:
        return len(self.mana)

    def __bool__(self) -> bool:
        return len(self.mana) > 0

    def __iter__(self) -> Iterator[Mana]:
        return iter(self.mana)


# =============================================================================
# Cost (General Ability Costs)
# =============================================================================

@dataclass
class Cost:
    """Represents the total cost to activate an ability or cast a spell.

    Costs can include mana costs and additional costs like tapping,
    sacrificing permanents, paying life, or discarding cards.

    Per CR 118, costs are actions or payments required to take actions.

    Attributes:
        mana_cost: The mana component of the cost (if any).
        tap_cost: Whether tapping the source is required.
        sacrifice_cost: Description of what must be sacrificed (if any).
        life_cost: Amount of life that must be paid.
        discard_cost: Number of cards that must be discarded.
    """
    mana_cost: Optional[ManaCost] = None
    tap_cost: bool = False
    sacrifice_cost: Optional[str] = None  # Description, e.g., "a creature"
    life_cost: int = 0
    discard_cost: int = 0
    exile_cost: Optional[str] = None  # Description of what to exile
    additional_costs: List[str] = field(default_factory=list)  # Other costs as text

    def can_pay(self, player: Any, source: Any = None) -> bool:
        """Check if a player can pay this cost.

        Args:
            player: The player who would pay the cost.
            source: The source of the ability (for tap costs).

        Returns:
            True if the player can pay all components of this cost.
        """
        # Check mana cost
        if self.mana_cost and not self._can_pay_mana(player):
            return False

        # Check tap cost
        if self.tap_cost and not self._can_tap_source(player, source):
            return False

        # Check life cost
        if self.life_cost > 0 and not self._can_pay_life(player):
            return False

        # Check discard cost
        if self.discard_cost > 0 and not self._can_discard(player):
            return False

        # Check sacrifice cost (requires more context to fully evaluate)
        if self.sacrifice_cost and not self._can_sacrifice(player):
            return False

        return True

    def pay(self, player: Any, source: Any = None) -> bool:
        """Pay this cost.

        Args:
            player: The player paying the cost.
            source: The source of the ability (for tap costs).

        Returns:
            True if the cost was paid successfully.
        """
        if not self.can_pay(player, source):
            return False

        # Pay mana cost
        if self.mana_cost:
            if not self._pay_mana(player):
                return False

        # Pay tap cost
        if self.tap_cost:
            if not self._pay_tap(source):
                return False

        # Pay life cost
        if self.life_cost > 0:
            if not self._pay_life(player):
                return False

        # Pay discard cost
        if self.discard_cost > 0:
            if not self._pay_discard(player):
                return False

        # Sacrifice cost requires game interaction (handled by game engine)

        return True

    def _can_pay_mana(self, player: Any) -> bool:
        """Check if player can pay the mana cost."""
        if hasattr(player, 'mana_pool') and self.mana_cost:
            return player.mana_pool.can_pay(self.mana_cost)
        return True

    def _can_tap_source(self, player: Any, source: Any) -> bool:
        """Check if the source can be tapped."""
        if source is None:
            return False
        # Check if source is untapped and can be tapped
        if hasattr(source, 'is_tapped'):
            return not source.is_tapped
        if hasattr(source, 'status'):
            # Assume status has a TAPPED flag
            from .types import ObjectStatus
            return not (source.status & ObjectStatus.TAPPED)
        return True

    def _can_pay_life(self, player: Any) -> bool:
        """Check if player can pay the life cost."""
        if hasattr(player, 'life'):
            # Can pay life as long as player has enough (or if it's a cost,
            # can always attempt - being at 0 doesn't stop payment)
            return player.life >= self.life_cost
        return True

    def _can_discard(self, player: Any) -> bool:
        """Check if player can discard required cards."""
        if hasattr(player, 'hand'):
            return len(player.hand) >= self.discard_cost
        return True

    def _can_sacrifice(self, player: Any) -> bool:
        """Check if player can sacrifice required permanents."""
        # This is simplified - full implementation needs game context
        # to determine if valid sacrifice targets exist
        return True

    def _pay_mana(self, player: Any) -> bool:
        """Pay the mana cost from player's pool."""
        if hasattr(player, 'mana_pool') and self.mana_cost:
            return player.mana_pool.pay(self.mana_cost)
        return True

    def _pay_tap(self, source: Any) -> bool:
        """Tap the source."""
        if source is None:
            return False
        if hasattr(source, 'tap'):
            return source.tap()
        if hasattr(source, 'is_tapped'):
            source.is_tapped = True
            return True
        return True

    def _pay_life(self, player: Any) -> bool:
        """Pay life from player."""
        if hasattr(player, 'life'):
            player.life -= self.life_cost
            return True
        return True

    def _pay_discard(self, player: Any) -> bool:
        """Discard cards from player's hand."""
        # This is simplified - full implementation needs player choice
        if hasattr(player, 'hand') and hasattr(player, 'discard'):
            for _ in range(self.discard_cost):
                if player.hand:
                    card = player.hand[0]  # Should be player choice
                    player.discard(card)
        return True

    @property
    def is_free(self) -> bool:
        """Check if this cost is free (no costs required)."""
        return (
            (self.mana_cost is None or self.mana_cost.is_free) and
            not self.tap_cost and
            self.sacrifice_cost is None and
            self.life_cost == 0 and
            self.discard_cost == 0 and
            self.exile_cost is None and
            not self.additional_costs
        )

    def __str__(self) -> str:
        parts = []

        if self.mana_cost and not self.mana_cost.is_free:
            parts.append(str(self.mana_cost))

        if self.tap_cost:
            parts.append("{T}")

        if self.life_cost > 0:
            parts.append(f"Pay {self.life_cost} life")

        if self.sacrifice_cost:
            parts.append(f"Sacrifice {self.sacrifice_cost}")

        if self.discard_cost > 0:
            cards = "card" if self.discard_cost == 1 else "cards"
            parts.append(f"Discard {self.discard_cost} {cards}")

        if self.exile_cost:
            parts.append(f"Exile {self.exile_cost}")

        parts.extend(self.additional_costs)

        return ", ".join(parts) if parts else "Free"

    def __repr__(self) -> str:
        return f'Cost({str(self)!r})'


# =============================================================================
# Helper Functions
# =============================================================================

def _char_to_color(char: str) -> Optional[Color]:
    """Convert a mana character to a Color enum.

    Args:
        char: Single character representing a color.

    Returns:
        The corresponding Color, or None if invalid.
    """
    char = char.upper()
    mapping = {
        'W': Color.WHITE,
        'U': Color.BLUE,
        'B': Color.BLACK,
        'R': Color.RED,
        'G': Color.GREEN,
        'C': Color.COLORLESS,
    }
    return mapping.get(char)


def parse_mana_cost(cost_str: str) -> ManaCost:
    """Convenience function to parse a mana cost string.

    Args:
        cost_str: The cost string (e.g., "{2}{U}{U}").

    Returns:
        A ManaCost object.
    """
    return ManaCost.parse(cost_str)


def create_mana(color_str: str, amount: int = 1, source: Any = None) -> List[Mana]:
    """Create a list of Mana objects.

    Args:
        color_str: Color character (W, U, B, R, G, C).
        amount: Number of mana to create.
        source: The source permanent.

    Returns:
        List of Mana objects.
    """
    color = _char_to_color(color_str)
    if color is None:
        color = Color.COLORLESS

    return [Mana(color=color, source=source) for _ in range(amount)]


# =============================================================================
# Basic Land Mana Production
# =============================================================================

BASIC_LAND_MANA = {
    "Plains": Color.WHITE,
    "Island": Color.BLUE,
    "Swamp": Color.BLACK,
    "Mountain": Color.RED,
    "Forest": Color.GREEN,
}


def get_land_mana_color(land_name: str, subtypes: Set[str]) -> Color:
    """Get the mana color a land produces based on basic land types.

    Args:
        land_name: The name of the land.
        subtypes: The set of subtypes the land has.

    Returns:
        The Color the land produces. Returns COLORLESS for unknown lands
        so they can still tap for mana.
    """
    # Check basic land types in subtypes
    if "Plains" in subtypes:
        return Color.WHITE
    if "Island" in subtypes:
        return Color.BLUE
    if "Swamp" in subtypes:
        return Color.BLACK
    if "Mountain" in subtypes:
        return Color.RED
    if "Forest" in subtypes:
        return Color.GREEN

    # Check by name for basic lands
    for name, color in BASIC_LAND_MANA.items():
        if name in land_name:
            return color

    # Default to colorless for non-basic lands without basic types
    return Color.COLORLESS


# =============================================================================
# Mana Ability Manager
# =============================================================================

class ManaAbilityManager:
    """Manages mana abilities (CR 605).

    Mana abilities are special abilities that add mana to a player's mana pool.
    They don't use the stack and resolve immediately (CR 605.3).
    """

    def __init__(self, game: Any):
        """Initialize the mana ability manager.

        Args:
            game: The game instance this manager belongs to.
        """
        self.game = game

    def activate_mana_ability(self, player_id: int, permanent_id: int) -> bool:
        """Activate a mana ability.

        Mana abilities don't use the stack (CR 605.3).

        Args:
            player_id: The ID of the player activating the ability.
            permanent_id: The ID of the permanent with the mana ability.

        Returns:
            True if the ability was successfully activated.
        """
        from .events import ManaAddedEvent, TapEvent

        # Find permanent
        permanent = self.game.zones.battlefield.get_by_id(permanent_id)
        if not permanent:
            return False

        # Check controller
        if permanent.controller_id != player_id:
            return False

        # Check if tapped (most mana abilities require tap)
        if permanent.is_tapped:
            return False

        # Determine mana produced (defaults to colorless for unknown lands)
        mana_color = get_land_mana_color(
            permanent.characteristics.name,
            permanent.characteristics.subtypes
        )

        # Tap the permanent
        permanent.tap()
        self.game.events.emit(TapEvent(permanent=permanent))

        # Add mana to pool
        player = self.game.get_player(player_id)
        player.mana_pool.add(mana_color, source=permanent_id)

        # Emit event
        self.game.events.emit(ManaAddedEvent(
            player_id=player_id,
            color=mana_color,
            amount=1,
            source_id=permanent_id
        ))

        return True

    def tap_lands_for_mana(self, player_id: int, amount: int) -> int:
        """Tap lands to produce mana, return amount produced.

        Args:
            player_id: The ID of the player tapping lands.
            amount: The amount of mana desired.

        Returns:
            The actual amount of mana produced.
        """
        lands = self.game.zones.battlefield.untapped_lands(player_id)
        produced = 0

        for land in lands:
            if produced >= amount:
                break
            if self.activate_mana_ability(player_id, land.object_id):
                produced += 1

        return produced

    def auto_pay_cost(self, player_id: int, cost: ManaCost) -> bool:
        """Automatically tap lands to pay a mana cost.

        Args:
            player_id: The ID of the player paying the cost.
            cost: The mana cost to pay.

        Returns:
            True if the cost was successfully paid.
        """
        player = self.game.get_player(player_id)

        # Already have enough mana?
        if player.mana_pool.can_pay(cost):
            return player.mana_pool.pay(cost)

        # Need to tap lands
        lands = self.game.zones.battlefield.untapped_lands(player_id)

        # Calculate what we need
        needed_colors: Dict[Color, int] = {}
        generic_needed = 0

        for symbol in cost.symbols:
            if symbol.colors and Color.COLORLESS not in symbol.colors:
                for color in symbol.colors:
                    needed_colors[color] = needed_colors.get(color, 0) + 1
                    break  # Only count once for hybrid
            elif symbol.is_generic:
                generic_needed += symbol.generic_amount

        # Tap lands for colored mana first
        # Note: Must use list() and index into dict to properly track remaining needed
        for color in list(needed_colors.keys()):
            for land in lands:
                if needed_colors[color] <= 0:
                    break
                mana_color = get_land_mana_color(
                    land.characteristics.name,
                    land.characteristics.subtypes
                )
                if mana_color == color and not land.is_tapped:
                    if self.activate_mana_ability(player_id, land.object_id):
                        needed_colors[color] -= 1

        # Tap lands for generic mana
        for land in lands:
            if generic_needed <= 0:
                break
            if not land.is_tapped:
                self.activate_mana_ability(player_id, land.object_id)
                generic_needed -= 1

        # Try to pay
        return player.mana_pool.pay(cost)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Classes
    'ManaSymbol',
    'ManaCost',
    'Mana',
    'ManaPool',
    'Cost',
    'ManaAbilityManager',

    # Helper functions
    'parse_mana_cost',
    'create_mana',
    'get_land_mana_color',

    # Constants
    'BASIC_LAND_MANA',
]
