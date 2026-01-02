"""
MTG Engine V3 - AI Decision-Making System for Rules-Accurate MTG Simulation.

Provides a base AIAgent class and SimpleAI implementation for
making game decisions according to MTG rules.

ENHANCED VERSION with:
- MoveType enum and Move dataclass for minimax
- CombatSimulationResult for combat simulation
- PositionEvaluator class with comprehensive evaluation
- Enhanced _evaluate_threat with clock impact, evasion multipliers, infect detection
- simulate_combat() method with proper first strike/deathtouch/trample handling
- generate_legal_moves() for minimax foundation
- GameState.clone() for state cloning
"""

from abc import ABC, abstractmethod
import functools
import math
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine.game import Game
    from ..engine.objects import Permanent, Card, Spell
    from ..engine.combat import AttackDeclaration, BlockDeclaration
    from ..engine.effects.triggered import PendingTrigger


# =============================================================================
# MOVE TYPES FOR MINIMAX
# =============================================================================

class MoveType(Enum):
    """Types of moves for minimax search."""
    PASS = auto()
    CAST_SPELL = auto()
    PLAY_LAND = auto()
    ACTIVATE_ABILITY = auto()
    DECLARE_ATTACKERS = auto()
    DECLARE_BLOCKERS = auto()


@dataclass
class Move:
    """Represents a move for minimax search."""
    move_type: MoveType
    card: Optional[Any] = None
    targets: List[Any] = field(default_factory=list)
    attackers: List[Any] = field(default_factory=list)
    block_assignments: Dict[Any, List[Any]] = field(default_factory=dict)

    def to_action(self) -> 'Action':
        """Convert this Move to an Action for the game engine."""
        if self.move_type == MoveType.PASS:
            return Action(action_type="pass")
        elif self.move_type == MoveType.CAST_SPELL:
            return Action(action_type="cast_spell", card=self.card, targets=self.targets)
        elif self.move_type == MoveType.PLAY_LAND:
            return Action(action_type="play_land", card=self.card)
        elif self.move_type == MoveType.ACTIVATE_ABILITY:
            return Action(action_type="activate_ability", card=self.card, targets=self.targets)
        elif self.move_type == MoveType.DECLARE_ATTACKERS:
            return Action(action_type="declare_attackers", targets=self.attackers)
        elif self.move_type == MoveType.DECLARE_BLOCKERS:
            return Action(action_type="declare_blockers", value=self.block_assignments)
        else:
            return Action(action_type="pass")


# =============================================================================
# COMBAT SIMULATION
# =============================================================================

@dataclass
class CombatSimulationResult:
    """Result of simulating combat."""
    damage_to_opponent: int = 0
    damage_to_me: int = 0
    my_creatures_that_die: List[Any] = field(default_factory=list)
    opp_creatures_that_die: List[Any] = field(default_factory=list)
    net_card_advantage: int = 0

    @property
    def is_favorable(self) -> bool:
        """Check if this combat result is favorable for us."""
        if self.net_card_advantage > 0:
            return True
        if self.net_card_advantage == 0 and self.damage_to_opponent > self.damage_to_me:
            return True
        if not self.my_creatures_that_die and self.damage_to_opponent > 0:
            return True
        return False

    @property
    def is_profitable_trade(self) -> bool:
        """Check if we're trading up (killing more valuable creatures)."""
        return self.net_card_advantage > 0


# =============================================================================
# POSITION EVALUATOR
# =============================================================================

class PositionEvaluator:
    """
    Comprehensive position evaluation for MTG game states.

    Evaluates position across multiple dimensions:
    - Material: Creature stats and permanent values
    - Tempo: Development relative to turn number
    - Card Advantage: Hand size and resources
    - Board Control: Ability to attack/block favorably
    - Life Pressure: Clock and life total considerations
    """

    MATERIAL_WEIGHT = 1.0
    TEMPO_WEIGHT = 0.8
    CARD_ADVANTAGE_WEIGHT = 0.7
    BOARD_CONTROL_WEIGHT = 0.9
    LIFE_PRESSURE_WEIGHT = 1.2

    def evaluate(self, state: 'GameState') -> float:
        """Evaluate the overall position. Positive = ahead, negative = behind."""
        material = self._evaluate_material(state) * self.MATERIAL_WEIGHT
        tempo = self._evaluate_tempo(state) * self.TEMPO_WEIGHT
        card_adv = self._evaluate_card_advantage(state) * self.CARD_ADVANTAGE_WEIGHT
        board_ctrl = self._evaluate_board_control(state) * self.BOARD_CONTROL_WEIGHT
        life_press = self._evaluate_life_pressure(state) * self.LIFE_PRESSURE_WEIGHT
        return material + tempo + card_adv + board_ctrl + life_press

    def _evaluate_material(self, state: 'GameState') -> float:
        """Evaluate material advantage (creature stats, permanent values)."""
        score = 0.0
        keyword_values = {
            "flying": 1.5, "trample": 1.0, "deathtouch": 2.0, "first strike": 1.5,
            "double strike": 3.0, "lifelink": 1.5, "vigilance": 0.5, "haste": 0.5,
            "hexproof": 2.0, "indestructible": 3.0, "menace": 1.0, "reach": 0.5, "infect": 2.5,
        }
        for creature in state.my_creatures:
            power = creature.power or 0
            toughness = creature.toughness or 0
            creature_value = power * 2.0 + toughness * 1.0
            for keyword in creature.keywords:
                creature_value += keyword_values.get(keyword.lower(), 0)
            if "+1/+1" in creature.counters:
                creature_value += creature.counters["+1/+1"] * 1.5
            score += creature_value
        for creature in state.opp_creatures:
            power = creature.power or 0
            toughness = creature.toughness or 0
            creature_value = power * 2.0 + toughness * 1.0
            for keyword in creature.keywords:
                creature_value += keyword_values.get(keyword.lower(), 0)
            if "+1/+1" in creature.counters:
                creature_value += creature.counters["+1/+1"] * 1.5
            score -= creature_value
        for perm in state.my_battlefield:
            if perm.is_planeswalker:
                score += 5.0
            elif perm.is_enchantment:
                score += 2.0
            elif perm.is_artifact and not perm.is_creature:
                score += 1.5
        for perm in state.opp_battlefield:
            if perm.is_planeswalker:
                score -= 5.0
            elif perm.is_enchantment:
                score -= 2.0
            elif perm.is_artifact and not perm.is_creature:
                score -= 1.5
        return score

    def _evaluate_tempo(self, state: 'GameState') -> float:
        """Evaluate tempo (development relative to turn number)."""
        turn = max(1, state.total_mana)
        our_mana_value = sum(self._get_mana_value(p) for p in state.my_battlefield if p.is_creature)
        opp_mana_value = sum(self._get_mana_value(p) for p in state.opp_battlefield if p.is_creature)
        expected_mana_value = turn * (turn + 1) / 2
        our_tempo = (our_mana_value / expected_mana_value) if expected_mana_value > 0 else 1.0
        opp_tempo = (opp_mana_value / expected_mana_value) if expected_mana_value > 0 else 1.0
        score = (our_tempo - opp_tempo) * 5.0
        if turn <= 4:
            board_diff = len(state.my_creatures) - len(state.opp_creatures)
            score += board_diff * 1.5
        return score

    def _get_mana_value(self, perm: 'PermanentInfo') -> int:
        """Estimate mana value of a permanent."""
        if not perm.is_creature:
            return 2
        power = perm.power or 0
        toughness = perm.toughness or 0
        base_value = max(1, (power + toughness) // 2)
        keyword_bonus = 0
        for keyword in perm.keywords:
            kw = keyword.lower()
            if kw in ("flying", "trample", "lifelink", "vigilance", "deathtouch", "first strike", "haste"):
                keyword_bonus += 1
            elif kw in ("double strike", "hexproof", "indestructible"):
                keyword_bonus += 2
        return base_value + keyword_bonus

    def _evaluate_card_advantage(self, state: 'GameState') -> float:
        """Evaluate card advantage (hand size and resources)."""
        assumed_opp_hand = 4
        hand_diff = len(state.my_hand) - assumed_opp_hand
        score = hand_diff * 2.0
        graveyard_value = len(state.my_graveyard) * 0.2
        score += graveyard_value
        playable = sum(1 for card in state.my_hand if card.cmc <= state.total_mana)
        score += playable * 0.5
        return score

    def _evaluate_board_control(self, state: 'GameState') -> float:
        """Evaluate board control (ability to attack/block favorably)."""
        score = 0.0
        our_attackers = sum(1 for c in state.my_creatures if c.can_attack)
        opp_blockers = sum(1 for c in state.opp_creatures if c.can_block)
        our_blockers = sum(1 for c in state.my_creatures if c.can_block)
        opp_attackers = sum(1 for c in state.opp_creatures if not c.has_summoning_sickness and not c.is_tapped)
        our_flyers = sum(1 for c in state.my_creatures if c.has_keyword("flying") and c.can_attack)
        opp_flying_blockers = sum(1 for c in state.opp_creatures if (c.has_keyword("flying") or c.has_keyword("reach")) and c.can_block)
        if our_attackers > opp_blockers:
            score += (our_attackers - opp_blockers) * 1.5
        if our_flyers > opp_flying_blockers:
            score += (our_flyers - opp_flying_blockers) * 2.0
        if our_blockers >= opp_attackers:
            score += 2.0
        else:
            score -= (opp_attackers - our_blockers) * 1.0
        return score

    def _evaluate_life_pressure(self, state: 'GameState') -> float:
        """Evaluate life pressure (clock and life total considerations)."""
        score = 0.0
        our_power = sum(c.power or 0 for c in state.my_creatures if c.can_attack)
        opp_power = sum(c.power or 0 for c in state.opp_creatures if not c.has_summoning_sickness and not c.is_tapped)
        our_clock = math.ceil(state.opp_life / our_power) if our_power > 0 else float('inf')
        opp_clock = math.ceil(state.my_life / opp_power) if opp_power > 0 else float('inf')
        if our_clock < opp_clock:
            score += (opp_clock - our_clock) * 3.0
        elif opp_clock < our_clock:
            score -= (our_clock - opp_clock) * 3.0
        life_diff = state.my_life - state.opp_life
        score += life_diff * 0.2
        if state.my_life <= 5:
            score -= 5.0
        if state.opp_life <= 5:
            score += 5.0
        if our_power >= state.opp_life:
            score += 20.0
        if opp_power >= state.my_life:
            score -= 15.0
        return score


# =============================================================================
# AI CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class AIConfig:
    """
    Configuration constants for AI decision-making.

    Centralizes magic numbers used throughout the AI system for easier
    tuning and maintainability.
    """
    # Board development bonuses
    FIRST_CREATURE_BONUS: float = 5.0
    DEVELOPING_BOARD_BONUS: float = 2.0
    CURVE_BONUS: float = 2.0
    HASTE_BONUS: float = 2.5
    SMALL_DEATHTOUCH_BONUS: float = 2.0

    # Board state adjustments
    BEHIND_ON_BOARD_CREATURE_BONUS: float = 3.0
    BEHIND_ON_BOARD_PENALTY: float = 2.0
    AHEAD_ON_BOARD_BONUS: float = 1.0
    LOW_LIFE_BLOCKER_BONUS: float = 3.0

    # Removal evaluation
    REMOVAL_BASE_VALUE: float = 3.0
    SORCERY_REMOVAL_BASE: float = 3.5
    THREAT_MULTIPLIER: float = 0.5

    # Mana efficiency
    PERFECT_MANA_BONUS: float = 0.5
    WASTED_MANA_PENALTY: float = 0.5

    # Creature evaluation weights
    POWER_WEIGHT: float = 2.0
    TOUGHNESS_WEIGHT: float = 1.0
    EFFICIENCY_WEIGHT: float = 1.0

    # Threat evaluation
    TAPPED_THREAT_MULTIPLIER: float = 0.7
    SUMMONING_SICK_MULTIPLIER: float = 0.8
    FLYING_THREAT_MULTIPLIER: float = 1.3
    UNBLOCKABLE_THREAT_MULTIPLIER: float = 1.5
    COUNTER_VALUE: float = 1.5

    # Enhanced threat evaluation
    EVASION_NO_BLOCKERS_MULTIPLIER: float = 2.0
    INFECT_BASE_MULTIPLIER: float = 2.5
    INFECT_LETHAL_MULTIPLIER: float = 3.0
    MUST_ANSWER_THRESHOLD: float = 5
    PROTECTION_THREAT_BONUS: float = 1.5

    @classmethod
    def default(cls) -> "AIConfig":
        """Return the default configuration."""
        return cls()


# Global default config - can be replaced for testing/tuning
DEFAULT_AI_CONFIG = AIConfig.default()


@dataclass
class Action:
    """Represents an action the AI can take."""
    action_type: str  # "pass", "cast_spell", "activate_ability", "play_land",
                      # "declare_attackers", "declare_blockers", "assign_damage",
                      # "choose_target", "choose_mode"
    card: Optional["Card"] = None
    ability: Optional[str] = None  # Ability identifier or description
    targets: List[Union["Permanent", "Card", int]] = field(default_factory=list)
    value: Optional[Union[int, str, List[int]]] = None  # For choices (modes, X values, etc.)

    def __repr__(self) -> str:
        parts = [f"Action({self.action_type}"]
        if self.card:
            parts.append(f", card={self.card}")
        if self.ability:
            parts.append(f", ability={self.ability}")
        if self.targets:
            parts.append(f", targets={self.targets}")
        if self.value is not None:
            parts.append(f", value={self.value}")
        parts.append(")")
        return "".join(parts)


@dataclass
class CardInfo:
    """Read-only card information for AI decisions."""
    name: str
    card_types: List[str]
    subtypes: List[str]
    mana_cost: str
    cmc: int
    power: Optional[int] = None
    toughness: Optional[int] = None
    abilities: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    reference: Any = None  # Reference to actual card object

    # Cache for lowercased card types (computed once in __post_init__)
    _types_lower: List[str] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Pre-compute lowercased types for faster lookups."""
        object.__setattr__(self, '_types_lower', [t.lower() for t in self.card_types])

    @functools.cached_property
    def is_creature(self) -> bool:
        return "creature" in self._types_lower

    @functools.cached_property
    def is_instant(self) -> bool:
        return "instant" in self._types_lower

    @functools.cached_property
    def is_sorcery(self) -> bool:
        return "sorcery" in self._types_lower

    @functools.cached_property
    def is_land(self) -> bool:
        return "land" in self._types_lower

    @functools.cached_property
    def is_enchantment(self) -> bool:
        return "enchantment" in self._types_lower

    @functools.cached_property
    def is_artifact(self) -> bool:
        return "artifact" in self._types_lower

    @functools.cached_property
    def is_planeswalker(self) -> bool:
        return "planeswalker" in self._types_lower


@dataclass
class PermanentInfo:
    """Read-only permanent information for AI decisions."""
    name: str
    card_types: List[str]
    subtypes: List[str]
    power: Optional[int] = None
    toughness: Optional[int] = None
    damage_marked: int = 0
    is_tapped: bool = False
    is_attacking: bool = False
    is_blocking: bool = False
    has_summoning_sickness: bool = False
    keywords: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)
    counters: Dict[str, int] = field(default_factory=dict)
    attached_to: Optional[Any] = None
    attachments: List[Any] = field(default_factory=list)
    controller: str = ""
    reference: Any = None  # Reference to actual permanent object
    protection_colors: Set[str] = field(default_factory=set)  # Colors this has protection from

    # Cache for lowercased types and keywords (computed once in __post_init__)
    _types_lower: List[str] = field(default_factory=list, repr=False, compare=False)
    _keywords_lower: List[str] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Pre-compute lowercased types and keywords for faster lookups."""
        object.__setattr__(self, '_types_lower', [t.lower() for t in self.card_types])
        object.__setattr__(self, '_keywords_lower', [k.lower() for k in self.keywords])

        # Parse protection from keywords
        protection_colors: Set[str] = set()
        for keyword in self.keywords:
            kw_lower = keyword.lower()
            if kw_lower.startswith("protection from"):
                color_part = kw_lower.replace("protection from ", "")
                if color_part in ("white", "blue", "black", "red", "green"):
                    protection_colors.add(color_part)
                elif color_part == "all colors":
                    protection_colors.update(["white", "blue", "black", "red", "green"])
        object.__setattr__(self, 'protection_colors', protection_colors)

    @functools.cached_property
    def is_creature(self) -> bool:
        return "creature" in self._types_lower

    @functools.cached_property
    def is_land(self) -> bool:
        return "land" in self._types_lower

    @functools.cached_property
    def is_artifact(self) -> bool:
        return "artifact" in self._types_lower

    @functools.cached_property
    def is_enchantment(self) -> bool:
        return "enchantment" in self._types_lower

    @functools.cached_property
    def is_planeswalker(self) -> bool:
        return "planeswalker" in self._types_lower

    @functools.cached_property
    def can_attack(self) -> bool:
        return (self.is_creature and
                not self.is_tapped and
                not self.has_summoning_sickness)

    @functools.cached_property
    def can_block(self) -> bool:
        return self.is_creature and not self.is_tapped

    @property
    def remaining_toughness(self) -> int:
        if self.toughness is None:
            return 0
        return self.toughness - self.damage_marked

    def has_keyword(self, keyword: str) -> bool:
        return keyword.lower() in self._keywords_lower

    def has_protection_from(self, color: str) -> bool:
        """Check if this permanent has protection from a specific color."""
        return color.lower() in self.protection_colors


@dataclass
class StackInfo:
    """Read-only stack item information for AI decisions."""
    name: str
    controller: str  # "me" or "opponent"
    card_types: List[str]
    targets: List[Any] = field(default_factory=list)
    reference: Any = None


@dataclass
class GameState:
    """Read-only game state view for AI decision-making."""
    my_life: int
    opp_life: int
    my_hand: List[CardInfo]
    my_battlefield: List[PermanentInfo]
    opp_battlefield: List[PermanentInfo]
    my_graveyard: List[CardInfo]
    stack: List[StackInfo]
    current_step: str
    is_my_turn: bool
    mana_available: Dict[str, int]
    priority_holder: str  # "me" or "opponent"

    @property
    def my_creatures(self) -> List[PermanentInfo]:
        return [p for p in self.my_battlefield if p.is_creature]

    @property
    def opp_creatures(self) -> List[PermanentInfo]:
        return [p for p in self.opp_battlefield if p.is_creature]

    @property
    def my_lands(self) -> List[PermanentInfo]:
        return [p for p in self.my_battlefield if p.is_land]

    @property
    def opp_lands(self) -> List[PermanentInfo]:
        return [p for p in self.opp_battlefield if p.is_land]

    @property
    def total_mana(self) -> int:
        return sum(self.mana_available.values())

    def can_afford(self, cmc: int) -> bool:
        return self.total_mana >= cmc

    @property
    def is_main_phase(self) -> bool:
        return self.current_step in (
            "main1", "main2", "precombat_main", "postcombat_main",
            "PRECOMBAT_MAIN", "POSTCOMBAT_MAIN"
        )

    @property
    def stack_is_empty(self) -> bool:
        return len(self.stack) == 0

    def clone(self) -> 'GameState':
        """Create a deep copy of this game state for minimax simulation."""
        return GameState(
            my_life=self.my_life,
            opp_life=self.opp_life,
            my_hand=deepcopy(self.my_hand),
            my_battlefield=deepcopy(self.my_battlefield),
            opp_battlefield=deepcopy(self.opp_battlefield),
            my_graveyard=deepcopy(self.my_graveyard),
            stack=deepcopy(self.stack),
            current_step=self.current_step,
            is_my_turn=self.is_my_turn,
            mana_available=deepcopy(self.mana_available),
            priority_holder=self.priority_holder
        )


def build_game_state(game: Any, player: Any) -> GameState:
    """Build a GameState view for a player from the game object."""
    import re

    def get_cmc(cost):
        """Parse mana cost to get CMC. Accepts string or ManaCost object."""
        if not cost:
            return 0
        if hasattr(cost, 'cmc'):
            return cost.cmc
        cost_str = str(cost)
        total = 0
        for m in re.findall(r'\{(\d+)\}', cost_str):
            total += int(m)
        total += len(re.findall(r'\{[WUBRG]\}', cost_str))
        return total

    def card_to_info(card) -> CardInfo:
        """Convert a Card to CardInfo."""
        chars = card.characteristics if hasattr(card, 'characteristics') else card
        types = []
        if hasattr(chars, 'types'):
            types = [str(t.name).lower() if hasattr(t, 'name') else str(t).lower()
                    for t in chars.types]
        subtypes = list(chars.subtypes) if hasattr(chars, 'subtypes') else []
        keywords = list(chars.keywords) if hasattr(chars, 'keywords') else []
        mana_cost = ""
        if hasattr(chars, 'mana_cost') and chars.mana_cost:
            mana_cost = str(chars.mana_cost) if not isinstance(chars.mana_cost, str) else chars.mana_cost
        return CardInfo(
            name=chars.name if hasattr(chars, 'name') else str(card),
            card_types=types,
            subtypes=[str(s) for s in subtypes],
            mana_cost=mana_cost,
            cmc=get_cmc(chars.mana_cost) if hasattr(chars, 'mana_cost') else 0,
            power=chars.power if hasattr(chars, 'power') else None,
            toughness=chars.toughness if hasattr(chars, 'toughness') else None,
            keywords=[str(k) for k in keywords],
            reference=card
        )

    def perm_to_info(perm, controller_id) -> PermanentInfo:
        """Convert a Permanent to PermanentInfo."""
        chars = perm.characteristics if hasattr(perm, 'characteristics') else perm
        types = []
        if hasattr(chars, 'types'):
            types = [str(t.name).lower() if hasattr(t, 'name') else str(t).lower()
                    for t in chars.types]
        keywords = list(chars.keywords) if hasattr(chars, 'keywords') else []
        return PermanentInfo(
            name=chars.name if hasattr(chars, 'name') else str(perm),
            card_types=types,
            subtypes=[],
            power=chars.power if hasattr(chars, 'power') else None,
            toughness=chars.toughness if hasattr(chars, 'toughness') else None,
            damage_marked=getattr(perm, 'damage_marked', 0),
            is_tapped=getattr(perm, 'is_tapped', False),
            is_attacking=getattr(perm, 'is_attacking', False),
            is_blocking=getattr(perm, 'is_blocking', False),
            has_summoning_sickness=getattr(perm, 'summoning_sick', False),
            keywords=[str(k) for k in keywords],
            controller="me" if controller_id == player.player_id else "opponent",
            reference=perm
        )

    my_id = player.player_id
    opp_id = None
    for pid in game.players:
        if pid != my_id:
            opp_id = pid
            break

    my_hand = []
    if hasattr(game.zones, 'hands') and my_id in game.zones.hands:
        hand = game.zones.hands[my_id]
        cards = hand.objects if hasattr(hand, 'objects') else (hand.cards if hasattr(hand, 'cards') else [])
        for card in cards:
            my_hand.append(card_to_info(card))

    my_battlefield = []
    opp_battlefield = []
    if hasattr(game.zones, 'battlefield'):
        bf = game.zones.battlefield
        for perm in (bf.objects if hasattr(bf, 'objects') else []):
            ctrl_id = getattr(perm, 'controller_id', None)
            if ctrl_id == my_id:
                my_battlefield.append(perm_to_info(perm, ctrl_id))
            elif ctrl_id == opp_id:
                opp_battlefield.append(perm_to_info(perm, ctrl_id))

    my_graveyard = []
    if hasattr(game.zones, 'graveyards') and my_id in game.zones.graveyards:
        gy = game.zones.graveyards[my_id]
        cards = gy.objects if hasattr(gy, 'objects') else (gy.cards if hasattr(gy, 'cards') else [])
        for card in cards:
            my_graveyard.append(card_to_info(card))

    current_step = "unknown"
    if hasattr(game, 'current_step') and game.current_step:
        current_step = str(game.current_step.name if hasattr(game.current_step, 'name') else game.current_step)

    mana_available = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}
    try:
        from engine.types import Color
        from engine.mana import get_land_mana_color
    except ImportError:
        from ..engine.types import Color
        from ..engine.mana import get_land_mana_color

    if hasattr(player, 'mana_pool') and player.mana_pool:
        pool = player.mana_pool
        if hasattr(pool, 'mana') and isinstance(pool.mana, dict):
            for color, amount in pool.mana.items():
                if amount > 0:
                    if color == Color.WHITE:
                        mana_available["W"] += amount
                    elif color == Color.BLUE:
                        mana_available["U"] += amount
                    elif color == Color.BLACK:
                        mana_available["B"] += amount
                    elif color == Color.RED:
                        mana_available["R"] += amount
                    elif color == Color.GREEN:
                        mana_available["G"] += amount
                    elif color == Color.COLORLESS:
                        mana_available["C"] += amount
        elif hasattr(pool, 'get'):
            mana_available["W"] += pool.get(Color.WHITE)
            mana_available["U"] += pool.get(Color.BLUE)
            mana_available["B"] += pool.get(Color.BLACK)
            mana_available["R"] += pool.get(Color.RED)
            mana_available["G"] += pool.get(Color.GREEN)
            mana_available["C"] += pool.get(Color.COLORLESS)

    for perm in my_battlefield:
        if perm.is_land and not perm.is_tapped:
            actual_perm = perm.reference
            if actual_perm:
                land_name = ""
                subtypes = set()
                if hasattr(actual_perm, 'characteristics'):
                    chars = actual_perm.characteristics
                    land_name = getattr(chars, 'name', '')
                    subtypes = set(getattr(chars, 'subtypes', []))
                else:
                    land_name = perm.name
                    subtypes = set(perm.subtypes) if perm.subtypes else set()
                mana_color = get_land_mana_color(land_name, subtypes)
                if mana_color == Color.WHITE:
                    mana_available["W"] += 1
                elif mana_color == Color.BLUE:
                    mana_available["U"] += 1
                elif mana_color == Color.BLACK:
                    mana_available["B"] += 1
                elif mana_color == Color.RED:
                    mana_available["R"] += 1
                elif mana_color == Color.GREEN:
                    mana_available["G"] += 1
                else:
                    mana_available["C"] += 1
            else:
                mana_available["C"] += 1

    my_life = player.life
    opp_life = game.players[opp_id].life if opp_id else 20

    return GameState(
        my_life=my_life,
        opp_life=opp_life,
        my_hand=my_hand,
        my_battlefield=my_battlefield,
        opp_battlefield=opp_battlefield,
        my_graveyard=my_graveyard,
        stack=[],
        current_step=current_step,
        is_my_turn=(game.active_player_id == my_id),
        mana_available=mana_available,
        priority_holder="me"
    )


class AIAgent(ABC):
    """Abstract base class for AI agents."""

    def __init__(self, player: Any, game: Any):
        self.player = player
        self.game = game

    def decide_priority(self, game: Any) -> Optional['Action']:
        """Wrapper that builds GameState and calls get_priority_action."""
        state = build_game_state(game, self.player)
        action = self.get_priority_action(state)
        if action and action.action_type != "pass":
            print(f"  [AI P{self.player.player_id}] Action: {action.action_type}", end="")
            if action.card:
                name = action.card.characteristics.name if hasattr(action.card, 'characteristics') else str(action.card)
                print(f" - {name}")
            else:
                print()
        if action and action.action_type == "pass":
            return None
        return action

    @abstractmethod
    def get_priority_action(self, state: GameState) -> Action:
        pass

    @abstractmethod
    def choose_attackers(self, state: GameState, available: List[PermanentInfo]) -> List[Any]:
        pass

    @abstractmethod
    def choose_blockers(self, state: GameState, attackers: List[PermanentInfo],
                        available: List[PermanentInfo]) -> Dict[Any, List[Any]]:
        pass

    @abstractmethod
    def assign_damage(self, state: GameState, creature: PermanentInfo,
                      blockers: List[PermanentInfo], damage: int) -> List[Tuple[Any, int]]:
        pass

    @abstractmethod
    def choose_targets(self, state: GameState, requirements: Any,
                       legal_targets: List[Any]) -> List[Any]:
        pass

    @abstractmethod
    def choose_modes(self, state: GameState, card: Any, num_modes: int) -> List[int]:
        pass

    @abstractmethod
    def choose_order(self, state: GameState, items: List[Any], reason: str) -> List[Any]:
        pass

    @abstractmethod
    def mulligan_decision(self, state: GameState, hand: List[CardInfo],
                          mulligan_count: int) -> bool:
        pass


class SimpleAI(AIAgent):
    """Basic AI implementation with straightforward heuristics."""

    KEYWORD_VALUES: Dict[str, float] = {
        "flying": 1.5, "trample": 1.0, "deathtouch": 2.0, "first strike": 1.5,
        "double strike": 3.0, "lifelink": 1.5, "vigilance": 0.5, "haste": 0.5,
        "hexproof": 2.0, "indestructible": 3.0, "menace": 1.0, "reach": 0.5,
        "protection": 2.0, "unblockable": 2.5, "shroud": 1.8, "flash": 0.5,
        "defender": -2.0, "infect": 3.0,
    }

    def __init__(self, player: Any, game: Any, config: Optional[AIConfig] = None):
        super().__init__(player, game)
        self.config = config or DEFAULT_AI_CONFIG
        self.land_played_this_turn = False
        self._mana_committed_this_priority: Dict[str, int] = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}

    def get_priority_action(self, state: GameState) -> Action:
        if state.stack and state.stack[-1].controller == "opponent":
            self._reset_mana_commitment()
            return Action(action_type="pass")
        if state.is_my_turn and state.is_main_phase:
            land_action = self._try_play_land(state)
            if land_action:
                return land_action
            spell_action = self._find_best_spell(state)
            if spell_action:
                return spell_action
            ability_action = self._find_best_ability(state)
            if ability_action:
                return ability_action
        self._reset_mana_commitment()
        return Action(action_type="pass")

    def _reset_mana_commitment(self) -> None:
        self._mana_committed_this_priority = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}

    def _get_effective_mana(self, state: GameState) -> Dict[str, int]:
        effective = {}
        for color in state.mana_available:
            committed = self._mana_committed_this_priority.get(color, 0)
            effective[color] = max(0, state.mana_available.get(color, 0) - committed)
        return effective

    def _commit_mana_for_spell(self, card_cmc: int) -> None:
        self._mana_committed_this_priority["C"] = self._mana_committed_this_priority.get("C", 0) + card_cmc

    def _try_play_land(self, state: GameState) -> Optional[Action]:
        if self.land_played_this_turn:
            return None
        lands_in_hand = [c for c in state.my_hand if c.is_land]
        if not lands_in_hand:
            return None
        return Action(action_type="play_land", card=lands_in_hand[0].reference)

    def _find_best_spell(self, state: GameState) -> Optional[Action]:
        castable: List[Tuple[CardInfo, float]] = []
        effective_mana = self._get_effective_mana(state)
        effective_total = sum(effective_mana.values())
        for card in state.my_hand:
            if card.is_land:
                continue
            if card.cmc > effective_total:
                continue
            score = self._evaluate_card_to_cast(card, state)
            castable.append((card, score))
        if not castable:
            return None
        castable.sort(key=lambda x: x[1], reverse=True)
        best_card, best_score = castable[0]
        if best_score > 0:
            self._commit_mana_for_spell(best_card.cmc)
            return Action(action_type="cast_spell", card=best_card.reference)
        return None

    def _find_best_ability(self, state: GameState) -> Optional[Action]:
        return None

    def _evaluate_card_to_cast(self, card: CardInfo, state: GameState) -> float:
        cfg = self.config
        score = 0.0
        my_creature_count = len(state.my_creatures)
        opp_creature_count = len(state.opp_creatures)
        turn_approximation = state.total_mana

        if card.is_creature:
            power = card.power or 0
            toughness = card.toughness or 0
            score = power * cfg.POWER_WEIGHT + toughness * cfg.TOUGHNESS_WEIGHT
            for keyword in card.keywords:
                score += self.KEYWORD_VALUES.get(keyword.lower(), 0)
            if card.cmc > 0:
                efficiency = (power + toughness) / card.cmc
                score += efficiency * cfg.EFFICIENCY_WEIGHT
            if my_creature_count == 0:
                score += cfg.FIRST_CREATURE_BONUS
            elif my_creature_count < 3:
                score += cfg.DEVELOPING_BOARD_BONUS
            if card.cmc == state.total_mana and turn_approximation <= 4:
                score += cfg.CURVE_BONUS
            if "haste" in [k.lower() for k in card.keywords]:
                score += cfg.HASTE_BONUS
            if "deathtouch" in [k.lower() for k in card.keywords]:
                if power <= 2:
                    score += cfg.SMALL_DEATHTOUCH_BONUS
        elif card.is_instant:
            has_removal_ability = any(ability in str(card.abilities).lower() for ability in ['destroy', 'damage', 'exile', 'bounce']) if hasattr(card, 'abilities') else False
            if has_removal_ability and opp_creature_count > 0:
                max_threat = max((self._evaluate_threat(c) for c in state.opp_creatures), default=0)
                score = cfg.REMOVAL_BASE_VALUE + max_threat * cfg.THREAT_MULTIPLIER
            else:
                score = 1.0
        elif card.is_sorcery:
            has_removal = any(ability in str(card.abilities).lower() for ability in ['destroy', 'damage', 'exile']) if hasattr(card, 'abilities') else False
            if has_removal and opp_creature_count > 0:
                max_threat = max((self._evaluate_threat(c) for c in state.opp_creatures), default=0)
                score = cfg.SORCERY_REMOVAL_BASE + max_threat * cfg.THREAT_MULTIPLIER
            else:
                score = 2.5
        elif card.is_enchantment:
            score = 3.0 if my_creature_count > 0 else 1.5
        elif card.is_artifact:
            is_equipment = 'equip' in str(card.abilities).lower() if hasattr(card, 'abilities') else False
            if is_equipment and my_creature_count > 0:
                score = 2.5
            elif is_equipment:
                score = 0.5
            else:
                score = 1.0 + (3 - min(card.cmc, 3)) * 0.3
        elif card.is_planeswalker:
            score = 7.0 if my_creature_count >= opp_creature_count else 4.0
        else:
            score = 2.0

        if opp_creature_count > my_creature_count + 1:
            if card.is_creature:
                score += cfg.BEHIND_ON_BOARD_CREATURE_BONUS
            elif not (card.is_instant or card.is_sorcery):
                score -= cfg.BEHIND_ON_BOARD_PENALTY
        if my_creature_count > opp_creature_count + 2:
            if not card.is_creature:
                score += cfg.AHEAD_ON_BOARD_BONUS
        if state.my_life <= 5:
            if card.is_creature and (card.toughness or 0) >= 2:
                score += cfg.LOW_LIFE_BLOCKER_BONUS
        leftover_mana = state.total_mana - card.cmc
        if leftover_mana == 0:
            score += cfg.PERFECT_MANA_BONUS
        elif leftover_mana >= 2 and turn_approximation <= 3:
            score -= cfg.WASTED_MANA_PENALTY
        return score

    def _evaluate_threat(self, permanent: PermanentInfo, state: Optional[GameState] = None) -> float:
        """
        Enhanced threat evaluation with:
        - Clock impact calculation (turns until death)
        - Evasion multipliers (flying without blockers = 2x)
        - Must-answer threat detection (infect with power 5+)
        - Protection from colors check
        """
        cfg = self.config
        if not permanent.is_creature:
            if permanent.is_planeswalker:
                return 5.0
            if permanent.is_enchantment:
                return 2.0
            if permanent.is_artifact:
                return 1.5
            return 1.0

        power = permanent.power or 0
        toughness = permanent.toughness or 0
        threat = power * cfg.POWER_WEIGHT + toughness * 0.5

        for keyword in permanent.keywords:
            threat += self.KEYWORD_VALUES.get(keyword.lower(), 0)

        if permanent.is_tapped:
            threat *= cfg.TAPPED_THREAT_MULTIPLIER
        if permanent.has_summoning_sickness:
            threat *= cfg.SUMMONING_SICK_MULTIPLIER

        # Clock impact - turns until death
        if state is not None and power > 0:
            my_life = state.my_life
            turns_to_kill = math.ceil(my_life / power) if power > 0 else float('inf')
            if turns_to_kill <= 2:
                threat *= 1.5
            elif turns_to_kill <= 3:
                threat *= 1.3
            elif turns_to_kill <= 4:
                threat *= 1.1

        # Evasion multipliers
        has_flying = permanent.has_keyword("flying")
        has_unblockable = permanent.has_keyword("unblockable")

        if state is not None:
            flying_blockers = [c for c in state.my_creatures if c.can_block and (c.has_keyword("flying") or c.has_keyword("reach"))]
            if has_flying and not flying_blockers:
                threat *= cfg.EVASION_NO_BLOCKERS_MULTIPLIER
            elif has_flying:
                threat *= cfg.FLYING_THREAT_MULTIPLIER
            if has_unblockable:
                threat *= cfg.UNBLOCKABLE_THREAT_MULTIPLIER
        else:
            if has_flying:
                threat *= cfg.FLYING_THREAT_MULTIPLIER
            if has_unblockable:
                threat *= cfg.UNBLOCKABLE_THREAT_MULTIPLIER

        # Infect - must-answer threat
        has_infect = permanent.has_keyword("infect")
        if has_infect:
            if power >= 10:
                threat *= cfg.INFECT_LETHAL_MULTIPLIER
            elif power >= cfg.MUST_ANSWER_THRESHOLD:
                threat *= cfg.INFECT_BASE_MULTIPLIER
            else:
                threat *= 2.0

        # Protection from colors
        if permanent.protection_colors and state is not None:
            protection_count = len(permanent.protection_colors)
            if protection_count >= 3:
                threat *= cfg.PROTECTION_THREAT_BONUS * 1.5
            elif protection_count >= 1:
                threat *= cfg.PROTECTION_THREAT_BONUS

        if "+1/+1" in permanent.counters:
            threat += permanent.counters["+1/+1"] * cfg.COUNTER_VALUE

        return threat

    def _can_attack_profitably(self, creature: PermanentInfo, blockers: List[PermanentInfo]) -> bool:
        if not creature.can_attack:
            return False
        power = creature.power or 0
        toughness = creature.toughness or 0
        if creature.has_keyword("flying"):
            relevant_blockers = [b for b in blockers if b.has_keyword("flying") or b.has_keyword("reach")]
        else:
            relevant_blockers = [b for b in blockers if b.can_block]
        if not relevant_blockers:
            return True
        if creature.has_keyword("menace"):
            if len(relevant_blockers) < 2:
                return True
        if creature.has_keyword("unblockable"):
            return True
        for blocker in relevant_blockers:
            blocker_power = blocker.power or 0
            blocker_toughness = blocker.toughness or 0
            if blocker_power >= toughness:
                if creature.has_keyword("first strike") or creature.has_keyword("double strike"):
                    if power >= blocker_toughness:
                        return True
                if power >= blocker_toughness:
                    our_value = self._evaluate_threat(creature)
                    their_value = self._evaluate_threat(blocker)
                    if our_value < their_value:
                        return True
                    continue
                return False
        return True

    def _should_block(self, blocker: PermanentInfo, attacker: PermanentInfo) -> float:
        if not blocker.can_block:
            return -100.0
        blocker_power = blocker.power or 0
        blocker_toughness = blocker.toughness or 0
        attacker_power = attacker.power or 0
        attacker_toughness = attacker.toughness or 0
        score = 0.0
        kills_attacker = blocker_power >= attacker_toughness
        if blocker.has_keyword("deathtouch"):
            kills_attacker = blocker_power > 0
        survives = blocker_toughness > attacker_power
        if attacker.has_keyword("deathtouch") and attacker_power > 0:
            survives = False
        if blocker.has_keyword("indestructible"):
            survives = True
        if attacker.has_keyword("first strike") or attacker.has_keyword("double strike"):
            if not blocker.has_keyword("first strike") and not blocker.has_keyword("double strike"):
                if attacker_power >= blocker_toughness:
                    kills_attacker = False
                    survives = False
        if blocker.has_keyword("first strike") or blocker.has_keyword("double strike"):
            if not attacker.has_keyword("first strike") and not attacker.has_keyword("double strike"):
                if blocker_power >= attacker_toughness:
                    kills_attacker = True
                    survives = True
        if kills_attacker and survives:
            score = 10.0 + self._evaluate_threat(attacker)
        elif kills_attacker:
            our_value = self._evaluate_threat(blocker)
            their_value = self._evaluate_threat(attacker)
            score = their_value - our_value
        elif survives:
            score = attacker_power * 0.5
        else:
            score = attacker_power * 0.2 - self._evaluate_threat(blocker) * 0.5
        return score

    def choose_attackers(self, state: GameState, available: List[PermanentInfo]) -> List[Any]:
        if not available:
            return []
        attackers: List[Any] = []
        potential_blockers = [c for c in state.opp_creatures if c.can_block]
        total_damage = sum(c.power or 0 for c in available if c.can_attack)
        if total_damage >= state.opp_life:
            return [c.reference for c in available if c.can_attack]
        for creature in available:
            if not creature.can_attack:
                continue
            if creature.has_keyword("flying"):
                flying_blockers = [b for b in potential_blockers if b.has_keyword("flying") or b.has_keyword("reach")]
                if not flying_blockers:
                    attackers.append(creature.reference)
                    continue
                elif self._can_attack_profitably(creature, flying_blockers):
                    attackers.append(creature.reference)
                    continue
            if creature.has_keyword("unblockable"):
                attackers.append(creature.reference)
                continue
            if self._can_attack_profitably(creature, potential_blockers):
                attackers.append(creature.reference)
        return attackers

    def choose_blockers(self, state: GameState, attackers: List[PermanentInfo],
                        available: List[PermanentInfo]) -> Dict[Any, List[Any]]:
        if not attackers or not available:
            return {}
        blocks: Dict[Any, List[Any]] = {}
        used_blockers: set = set()
        total_incoming = sum(a.power or 0 for a in attackers)
        must_block = total_incoming >= state.my_life
        block_options: List[Tuple[PermanentInfo, PermanentInfo, float]] = []
        for attacker in attackers:
            if attacker.has_keyword("unblockable"):
                continue
            for blocker in available:
                if id(blocker.reference) in used_blockers:
                    continue
                if attacker.has_keyword("flying"):
                    if not blocker.has_keyword("flying") and not blocker.has_keyword("reach"):
                        continue
                score = self._should_block(blocker, attacker)
                block_options.append((blocker, attacker, score))
        block_options.sort(key=lambda x: x[2], reverse=True)
        for blocker, attacker, score in block_options:
            if id(blocker.reference) in used_blockers:
                continue
            if attacker.has_keyword("menace"):
                attacker_ref = attacker.reference
                if attacker_ref in blocks and len(blocks[attacker_ref]) >= 1:
                    blocks[attacker_ref].append(blocker.reference)
                    used_blockers.add(id(blocker.reference))
                    continue
                elif attacker_ref not in blocks:
                    other_blockers = [(b, s) for b, a, s in block_options
                                      if a.reference == attacker_ref
                                      and id(b.reference) not in used_blockers
                                      and id(b.reference) != id(blocker.reference)]
                    if other_blockers:
                        blocks[attacker_ref] = [blocker.reference, other_blockers[0][0].reference]
                        used_blockers.add(id(blocker.reference))
                        used_blockers.add(id(other_blockers[0][0].reference))
                    continue
            if score > 0 or must_block:
                attacker_ref = attacker.reference
                if attacker_ref not in blocks:
                    blocks[attacker_ref] = []
                blocks[attacker_ref].append(blocker.reference)
                used_blockers.add(id(blocker.reference))
                if must_block:
                    total_incoming -= (attacker.power or 0)
                    if total_incoming < state.my_life:
                        must_block = False
        return blocks

    def assign_damage(self, state: GameState, creature: PermanentInfo,
                      blockers: List[PermanentInfo], damage: int) -> List[Tuple[Any, int]]:
        if not blockers:
            return [("player", damage)]
        assignments: List[Tuple[Any, int]] = []
        remaining_damage = damage
        has_trample = creature.has_keyword("trample")
        has_deathtouch = creature.has_keyword("deathtouch")
        sorted_blockers = sorted(blockers, key=lambda b: b.remaining_toughness)
        for blocker in sorted_blockers:
            if remaining_damage <= 0:
                break
            lethal = blocker.remaining_toughness
            if has_deathtouch:
                lethal = 1
            assigned = min(lethal, remaining_damage)
            assignments.append((blocker.reference, assigned))
            remaining_damage -= assigned
        if has_trample and remaining_damage > 0:
            assignments.append(("player", remaining_damage))
        return assignments

    def choose_targets(self, state: GameState, requirements: Any, legal_targets: List[Any]) -> List[Any]:
        if not legal_targets:
            return []
        opp_creatures = []
        my_creatures = []
        for target in legal_targets:
            if hasattr(target, 'controller'):
                if target.controller != self.player:
                    if hasattr(target, 'power'):
                        opp_creatures.append(target)
                else:
                    if hasattr(target, 'power'):
                        my_creatures.append(target)
        if opp_creatures:
            best_target = max(opp_creatures, key=lambda t: self._evaluate_threat(t) if isinstance(t, PermanentInfo) else (t.power * 2 + t.toughness if hasattr(t, 'power') else 0))
            return [best_target]
        if my_creatures:
            can_attack = [c for c in my_creatures if hasattr(c, 'can_attack') and c.can_attack]
            if can_attack:
                return [can_attack[0]]
            return [my_creatures[0]]
        return [legal_targets[0]] if legal_targets else []

    def choose_modes(self, state: GameState, card: Any, num_modes: int) -> List[int]:
        return list(range(num_modes))

    def choose_order(self, state: GameState, items: List[Any], reason: str) -> List[Any]:
        return list(items)

    def mulligan_decision(self, state: GameState, hand: List[CardInfo], mulligan_count: int) -> bool:
        land_count = sum(1 for c in hand if c.is_land)
        hand_size = len(hand)
        if mulligan_count >= 3:
            return False
        if land_count == 0 or land_count == hand_size:
            return True
        ideal_min = max(1, (hand_size * 2) // 7)
        ideal_max = max(2, (hand_size * 4) // 7)
        if land_count < ideal_min or land_count > ideal_max:
            if mulligan_count == 0:
                return True
            elif mulligan_count == 1 and (land_count == 0 or land_count >= hand_size - 1):
                return True
        playable_spells = [c for c in hand if not c.is_land and c.cmc <= land_count + 1]
        if not playable_spells and mulligan_count < 2:
            return True
        early_plays = [c for c in hand if not c.is_land and c.cmc <= 2]
        if not early_plays and land_count >= 3 and mulligan_count == 0:
            return True
        return False

    def reset_turn_state(self) -> None:
        self.land_played_this_turn = False
        self._reset_mana_commitment()

    def notify_land_played(self) -> None:
        self.land_played_this_turn = True

    # ========================================
    # COMBAT SIMULATION
    # ========================================

    def simulate_combat(self, attackers: List[PermanentInfo],
                        block_assignments: Dict[Any, List[PermanentInfo]],
                        state: GameState) -> CombatSimulationResult:
        """
        Simulate combat to calculate outcomes.
        Handles first strike, deathtouch, and trample properly.
        """
        result = CombatSimulationResult()
        damage_to_attacker: Dict[Any, int] = {}
        damage_to_blocker: Dict[Any, int] = {}

        # Phase 1: First Strike Damage
        for attacker in attackers:
            attacker_ref = attacker.reference
            has_first_strike = attacker.has_keyword("first strike") or attacker.has_keyword("double strike")
            if not has_first_strike:
                continue
            blockers = block_assignments.get(attacker_ref, [])
            if not blockers:
                result.damage_to_opponent += attacker.power or 0
            else:
                remaining_damage = attacker.power or 0
                has_deathtouch = attacker.has_keyword("deathtouch")
                has_trample = attacker.has_keyword("trample")
                sorted_blockers = sorted(blockers, key=lambda b: b.toughness or 0)
                for blocker in sorted_blockers:
                    if remaining_damage <= 0:
                        break
                    blocker_ref = blocker.reference
                    lethal = blocker.remaining_toughness
                    if has_deathtouch:
                        lethal = 1
                    assigned = min(lethal, remaining_damage)
                    damage_to_blocker[blocker_ref] = damage_to_blocker.get(blocker_ref, 0) + assigned
                    remaining_damage -= assigned
                if has_trample and remaining_damage > 0:
                    result.damage_to_opponent += remaining_damage

        # Blockers deal first strike damage back
        for attacker in attackers:
            attacker_ref = attacker.reference
            blockers = block_assignments.get(attacker_ref, [])
            for blocker in blockers:
                has_first_strike = blocker.has_keyword("first strike") or blocker.has_keyword("double strike")
                if has_first_strike:
                    damage_to_attacker[attacker_ref] = damage_to_attacker.get(attacker_ref, 0) + (blocker.power or 0)

        # Check for first strike kills
        first_strike_killed_attackers = set()
        first_strike_killed_blockers = set()

        for attacker in attackers:
            attacker_ref = attacker.reference
            damage_taken = damage_to_attacker.get(attacker_ref, 0)
            toughness = attacker.toughness or 0
            blockers = block_assignments.get(attacker_ref, [])
            killed_by_deathtouch = any(b.has_keyword("deathtouch") and (b.has_keyword("first strike") or b.has_keyword("double strike")) and (b.power or 0) > 0 for b in blockers)
            if damage_taken >= toughness or killed_by_deathtouch:
                first_strike_killed_attackers.add(attacker_ref)
                result.my_creatures_that_die.append(attacker_ref)

        for attacker in attackers:
            attacker_ref = attacker.reference
            blockers = block_assignments.get(attacker_ref, [])
            for blocker in blockers:
                blocker_ref = blocker.reference
                damage_taken = damage_to_blocker.get(blocker_ref, 0)
                toughness = blocker.toughness or 0
                has_attacker_deathtouch = attacker.has_keyword("deathtouch")
                attacker_has_first_strike = attacker.has_keyword("first strike") or attacker.has_keyword("double strike")
                killed_by_deathtouch = has_attacker_deathtouch and attacker_has_first_strike and damage_taken > 0
                if damage_taken >= toughness or killed_by_deathtouch:
                    first_strike_killed_blockers.add(blocker_ref)
                    result.opp_creatures_that_die.append(blocker_ref)

        # Phase 2: Regular Damage
        for attacker in attackers:
            attacker_ref = attacker.reference
            if attacker_ref in first_strike_killed_attackers:
                continue
            has_first_strike_only = attacker.has_keyword("first strike") and not attacker.has_keyword("double strike")
            if has_first_strike_only:
                continue
            blockers = block_assignments.get(attacker_ref, [])
            alive_blockers = [b for b in blockers if b.reference not in first_strike_killed_blockers]
            if not alive_blockers:
                result.damage_to_opponent += attacker.power or 0
            else:
                remaining_damage = attacker.power or 0
                has_deathtouch = attacker.has_keyword("deathtouch")
                has_trample = attacker.has_keyword("trample")
                sorted_blockers = sorted(alive_blockers, key=lambda b: b.toughness or 0)
                for blocker in sorted_blockers:
                    if remaining_damage <= 0:
                        break
                    blocker_ref = blocker.reference
                    existing_damage = damage_to_blocker.get(blocker_ref, 0)
                    remaining_toughness = (blocker.toughness or 0) - existing_damage
                    lethal = remaining_toughness
                    if has_deathtouch:
                        lethal = 1
                    assigned = min(lethal, remaining_damage)
                    damage_to_blocker[blocker_ref] = existing_damage + assigned
                    remaining_damage -= assigned
                if has_trample and remaining_damage > 0:
                    result.damage_to_opponent += remaining_damage

        # Blockers deal regular damage
        for attacker in attackers:
            attacker_ref = attacker.reference
            if attacker_ref in first_strike_killed_attackers:
                continue
            blockers = block_assignments.get(attacker_ref, [])
            for blocker in blockers:
                blocker_ref = blocker.reference
                if blocker_ref in first_strike_killed_blockers:
                    continue
                has_first_strike_only = blocker.has_keyword("first strike") and not blocker.has_keyword("double strike")
                if has_first_strike_only:
                    continue
                damage_to_attacker[attacker_ref] = damage_to_attacker.get(attacker_ref, 0) + (blocker.power or 0)

        # Final casualty check
        for attacker in attackers:
            attacker_ref = attacker.reference
            if attacker_ref in first_strike_killed_attackers:
                continue
            damage_taken = damage_to_attacker.get(attacker_ref, 0)
            toughness = attacker.toughness or 0
            blockers = block_assignments.get(attacker_ref, [])
            killed_by_deathtouch = any(b.has_keyword("deathtouch") and (b.power or 0) > 0 and b.reference not in first_strike_killed_blockers for b in blockers)
            if damage_taken >= toughness or killed_by_deathtouch:
                if attacker_ref not in result.my_creatures_that_die:
                    result.my_creatures_that_die.append(attacker_ref)

        for attacker in attackers:
            attacker_ref = attacker.reference
            blockers = block_assignments.get(attacker_ref, [])
            for blocker in blockers:
                blocker_ref = blocker.reference
                if blocker_ref in first_strike_killed_blockers:
                    continue
                damage_taken = damage_to_blocker.get(blocker_ref, 0)
                toughness = blocker.toughness or 0
                has_attacker_deathtouch = attacker.has_keyword("deathtouch")
                killed_by_deathtouch = has_attacker_deathtouch and damage_taken > 0
                if damage_taken >= toughness or killed_by_deathtouch:
                    if blocker_ref not in result.opp_creatures_that_die:
                        result.opp_creatures_that_die.append(blocker_ref)

        result.net_card_advantage = len(result.opp_creatures_that_die) - len(result.my_creatures_that_die)
        return result

    # ========================================
    # MINIMAX FOUNDATION - MOVE GENERATION
    # ========================================

    def generate_legal_moves(self, state: GameState) -> List[Move]:
        """Generate all legal moves for the current game state (minimax foundation)."""
        moves: List[Move] = []
        moves.append(Move(move_type=MoveType.PASS))

        if not state.is_my_turn:
            return moves

        if state.is_main_phase:
            if not self.land_played_this_turn:
                for card in state.my_hand:
                    if card.is_land:
                        moves.append(Move(move_type=MoveType.PLAY_LAND, card=card.reference))
            for card in state.my_hand:
                if card.is_land:
                    continue
                if state.can_afford(card.cmc):
                    moves.append(Move(move_type=MoveType.CAST_SPELL, card=card.reference))

        current_step_lower = state.current_step.lower()
        if "attack" in current_step_lower or "combat" in current_step_lower:
            can_attack = [c for c in state.my_creatures if c.can_attack]
            if can_attack:
                if len(can_attack) <= 6:
                    for i in range(1 << len(can_attack)):
                        attack_combo = []
                        for j in range(len(can_attack)):
                            if i & (1 << j):
                                attack_combo.append(can_attack[j].reference)
                        if attack_combo:
                            moves.append(Move(move_type=MoveType.DECLARE_ATTACKERS, attackers=attack_combo))
                else:
                    moves.append(Move(move_type=MoveType.DECLARE_ATTACKERS, attackers=[c.reference for c in can_attack]))
                    evasive = [c.reference for c in can_attack if c.has_keyword("flying") or c.has_keyword("unblockable")]
                    if evasive:
                        moves.append(Move(move_type=MoveType.DECLARE_ATTACKERS, attackers=evasive))

        return moves


class RandomAI(AIAgent):
    """AI that makes random legal decisions. Useful for testing."""

    def get_priority_action(self, state: GameState) -> Action:
        import random
        if random.random() < 0.7:
            return Action(action_type="pass")
        lands = [c for c in state.my_hand if c.is_land]
        if lands and random.random() < 0.5:
            return Action(action_type="play_land", card=random.choice(lands).reference)
        castable = [c for c in state.my_hand if not c.is_land and state.can_afford(c.cmc)]
        if castable:
            return Action(action_type="cast_spell", card=random.choice(castable).reference)
        return Action(action_type="pass")

    def choose_attackers(self, state: GameState, available: List[PermanentInfo]) -> List[Any]:
        import random
        if not available:
            return []
        can_attack = [c for c in available if c.can_attack]
        if not can_attack:
            return []
        num_attackers = random.randint(0, len(can_attack))
        return [c.reference for c in random.sample(can_attack, num_attackers)]

    def choose_blockers(self, state: GameState, attackers: List[PermanentInfo],
                        available: List[PermanentInfo]) -> Dict[Any, List[Any]]:
        import random
        if not attackers or not available:
            return {}
        blocks: Dict[Any, List[Any]] = {}
        can_block = [c for c in available if c.can_block]
        for attacker in attackers:
            if can_block and random.random() < 0.5:
                blocker = random.choice(can_block)
                blocks[attacker.reference] = [blocker.reference]
                can_block.remove(blocker)
        return blocks

    def assign_damage(self, state: GameState, creature: PermanentInfo,
                      blockers: List[PermanentInfo], damage: int) -> List[Tuple[Any, int]]:
        if not blockers:
            return [("player", damage)]
        assignments: List[Tuple[Any, int]] = []
        remaining = damage
        for blocker in blockers:
            if remaining <= 0:
                break
            assigned = min(blocker.remaining_toughness, remaining)
            assignments.append((blocker.reference, assigned))
            remaining -= assigned
        if remaining > 0 and creature.has_keyword("trample"):
            assignments.append(("player", remaining))
        return assignments

    def choose_targets(self, state: GameState, requirements: Any, legal_targets: List[Any]) -> List[Any]:
        import random
        if not legal_targets:
            return []
        return [random.choice(legal_targets)]

    def choose_modes(self, state: GameState, card: Any, num_modes: int) -> List[int]:
        import random
        available_modes = list(range(min(num_modes + 2, 4)))
        return random.sample(available_modes, min(num_modes, len(available_modes)))

    def choose_order(self, state: GameState, items: List[Any], reason: str) -> List[Any]:
        import random
        result = list(items)
        random.shuffle(result)
        return result

    def mulligan_decision(self, state: GameState, hand: List[CardInfo], mulligan_count: int) -> bool:
        import random
        return random.random() < (0.4 / (mulligan_count + 1))


class ExpertAI(SimpleAI):
    """
    Expert-level AI implementing high-level MTG strategy.
    Based on: "Who's the Beatdown" (Mike Flores), tempo and card advantage.
    """

    ROLE_BEATDOWN = "beatdown"
    ROLE_CONTROL = "control"
    ROLE_UNKNOWN = "unknown"
    INFECT_LETHAL_THRESHOLD = 5

    def __init__(self, player: Any, game: Any, config: Optional[AIConfig] = None):
        super().__init__(player, game, config)
        self.current_role = self.ROLE_UNKNOWN
        self.turn_count = 0
        self.damage_dealt_this_game = 0
        self.damage_taken_this_game = 0
        self.position_evaluator = PositionEvaluator()

    def _assess_role(self, state: GameState) -> str:
        """Determine if we're the beatdown or control."""
        our_power = sum(c.power or 0 for c in state.my_creatures if c.can_attack)
        our_clock = (state.opp_life / our_power) if our_power > 0 else float('inf')
        opp_power = sum(c.power or 0 for c in state.opp_creatures if not c.has_summoning_sickness)
        opp_clock = (state.my_life / opp_power) if opp_power > 0 else float('inf')
        our_future_power = sum((c.power or 0) for c in state.my_hand if c.is_creature and c.cmc <= state.total_mana + 2)
        their_board_growth = opp_power * 0.5
        adjusted_our_clock = our_clock - (our_future_power / max(state.opp_life, 1)) * 2
        adjusted_their_clock = opp_clock - (their_board_growth / max(state.my_life, 1)) * 2
        if state.my_life <= 5:
            return self.ROLE_CONTROL
        if state.opp_life <= 5:
            return self.ROLE_BEATDOWN
        if adjusted_our_clock < adjusted_their_clock - 1:
            return self.ROLE_BEATDOWN
        elif adjusted_their_clock < adjusted_our_clock - 1:
            return self.ROLE_CONTROL
        else:
            if len(state.my_creatures) >= len(state.opp_creatures):
                return self.ROLE_BEATDOWN
            return self.ROLE_CONTROL

    def _evaluate_board_position(self, state: GameState) -> float:
        """Evaluate board position using PositionEvaluator."""
        return self.position_evaluator.evaluate(state)

    def get_priority_action(self, state: GameState) -> Action:
        self.current_role = self._assess_role(state)
        board_score = self._evaluate_board_position(state)
        land_action = self._consider_land_drop(state)
        if land_action:
            return land_action
        if self.current_role == self.ROLE_BEATDOWN:
            return self._beatdown_priority(state, board_score)
        else:
            return self._control_priority(state, board_score)

    def _consider_land_drop(self, state: GameState) -> Optional[Action]:
        lands_in_hand = [c for c in state.my_hand if c.is_land]
        if not lands_in_hand or self.land_played_this_turn:
            return None
        return Action(action_type="play_land", card=lands_in_hand[0].reference)

    def _beatdown_priority(self, state: GameState, board_score: float) -> Action:
        castable = self._get_castable_spells(state)
        if not castable:
            return Action(action_type="pass")
        creatures = [c for c in castable if c.is_creature]
        removal = [c for c in castable if c.is_instant or c.is_sorcery]
        if creatures:
            best_creature = max(creatures, key=lambda c: self._beatdown_creature_value(c, state))
            return Action(action_type="cast_spell", card=best_creature.reference)
        if removal and len(state.opp_creatures) > 0:
            biggest_blocker = max(state.opp_creatures, key=lambda c: c.toughness or 0)
            if (biggest_blocker.toughness or 0) >= 3:
                return Action(action_type="cast_spell", card=removal[0].reference)
        if castable:
            best = max(castable, key=lambda c: self._evaluate_card_to_cast(c, state))
            return Action(action_type="cast_spell", card=best.reference)
        return Action(action_type="pass")

    def _control_priority(self, state: GameState, board_score: float) -> Action:
        castable = self._get_castable_spells(state)
        if not castable:
            return Action(action_type="pass")
        removal = [c for c in castable if c.is_instant or c.is_sorcery]
        creatures = [c for c in castable if c.is_creature]
        if removal and len(state.opp_creatures) > 0:
            biggest_threat = max(state.opp_creatures, key=lambda c: self._evaluate_threat(c, state))
            if self._evaluate_threat(biggest_threat, state) >= 4:
                return Action(action_type="cast_spell", card=removal[0].reference)
        if creatures:
            best_blocker = max(creatures, key=lambda c: self._control_creature_value(c, state))
            return Action(action_type="cast_spell", card=best_blocker.reference)
        if removal and len(state.opp_creatures) > len(state.my_creatures):
            return Action(action_type="cast_spell", card=removal[0].reference)
        if castable:
            best = max(castable, key=lambda c: self._evaluate_card_to_cast(c, state))
            return Action(action_type="cast_spell", card=best.reference)
        return Action(action_type="pass")

    def _beatdown_creature_value(self, card: CardInfo, state: GameState) -> float:
        power = card.power or 0
        toughness = card.toughness or 0
        value = power * 3.0 + toughness * 0.5
        if "haste" in [k.lower() for k in card.keywords]:
            value += power * 2.0
        if "flying" in [k.lower() for k in card.keywords]:
            value += 2.0
        if "trample" in [k.lower() for k in card.keywords]:
            value += 1.5
        if "menace" in [k.lower() for k in card.keywords]:
            value += 1.0
        if "infect" in [k.lower() for k in card.keywords]:
            value += power * 3.0
        if card.cmc > 0:
            value += (power / card.cmc) * 2.0
        return value

    def _control_creature_value(self, card: CardInfo, state: GameState) -> float:
        power = card.power or 0
        toughness = card.toughness or 0
        value = toughness * 2.5 + power * 1.0
        if "deathtouch" in [k.lower() for k in card.keywords]:
            value += 4.0
        if "reach" in [k.lower() for k in card.keywords]:
            has_flyers = any("flying" in [k.lower() for k in c.keywords] for c in state.opp_creatures)
            if has_flyers:
                value += 3.0
        if "lifelink" in [k.lower() for k in card.keywords]:
            value += 2.0
        if "flying" in [k.lower() for k in card.keywords]:
            value += 1.5
        return value

    def _get_castable_spells(self, state: GameState) -> List[CardInfo]:
        castable = []
        for card in state.my_hand:
            if card.is_land:
                continue
            if not state.can_afford(card.cmc):
                continue
            if self._would_overcommit(card, state):
                continue
            castable.append(card)
        return castable

    def _would_overcommit(self, card: CardInfo, state: GameState) -> bool:
        if state.total_mana <= 3:
            return False
        remaining = state.total_mana - card.cmc
        has_instants = any(c.is_instant for c in state.my_hand if c.cmc <= remaining)
        if has_instants and len(state.opp_creatures) > 0:
            return False
        return False

    def choose_attackers(self, state: GameState, available: List[PermanentInfo]) -> List[Any]:
        if not available:
            return []
        self.current_role = self._assess_role(state)
        attackers: List[Any] = []
        potential_blockers = [c for c in state.opp_creatures if c.can_block]
        total_damage = sum(c.power or 0 for c in available if c.can_attack)
        if total_damage >= state.opp_life:
            return [c.reference for c in available if c.can_attack]
        if self.current_role == self.ROLE_BEATDOWN:
            for creature in available:
                if not creature.can_attack:
                    continue
                if creature.has_keyword("flying"):
                    flying_blockers = [b for b in potential_blockers if b.has_keyword("flying") or b.has_keyword("reach")]
                    if not flying_blockers:
                        attackers.append(creature.reference)
                        continue
                if creature.has_keyword("unblockable"):
                    attackers.append(creature.reference)
                    continue
                if self._can_attack_profitably(creature, potential_blockers):
                    attackers.append(creature.reference)
                elif len(state.my_creatures) > len(state.opp_creatures) + 1:
                    attackers.append(creature.reference)
        else:
            for creature in available:
                if not creature.can_attack:
                    continue
                if creature.has_keyword("flying"):
                    flying_blockers = [b for b in potential_blockers if b.has_keyword("flying") or b.has_keyword("reach")]
                    if not flying_blockers:
                        attackers.append(creature.reference)
                        continue
                if creature.has_keyword("unblockable"):
                    attackers.append(creature.reference)
                    continue
                if not potential_blockers:
                    attackers.append(creature.reference)
                elif creature.has_keyword("vigilance"):
                    if self._can_attack_profitably(creature, potential_blockers):
                        attackers.append(creature.reference)
        return attackers

    def mulligan_decision(self, state: GameState, hand: List[CardInfo], mulligan_count: int) -> bool:
        land_count = sum(1 for c in hand if c.is_land)
        spell_count = len(hand) - land_count
        hand_size = len(hand)
        if mulligan_count >= 3:
            return False
        if land_count == 0 or land_count == hand_size:
            return True
        one_drops = sum(1 for c in hand if not c.is_land and c.cmc == 1)
        two_drops = sum(1 for c in hand if not c.is_land and c.cmc == 2)
        three_drops = sum(1 for c in hand if not c.is_land and c.cmc == 3)
        early_plays = one_drops + two_drops + three_drops
        if hand_size == 7:
            if land_count < 2 or land_count > 4:
                return True
            if early_plays == 0:
                return True
            return False
        if hand_size == 6:
            if land_count < 1 or land_count > 4:
                return True
            if early_plays == 0 and mulligan_count == 0:
                return True
            return False
        if hand_size == 5:
            if land_count == 0 or land_count >= 4:
                return True
            return False
        return False
