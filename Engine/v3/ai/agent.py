"""
MTG Engine V3 - AI Decision-Making System for Rules-Accurate MTG Simulation.

Provides a base AIAgent class and SimpleAI implementation for
making game decisions according to MTG rules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine.game import Game
    from ..engine.objects import Permanent, Card, Spell
    from ..engine.combat import AttackDeclaration, BlockDeclaration
    from ..engine.effects.triggered import PendingTrigger


@dataclass
class Action:
    """Represents an action the AI can take."""
    action_type: str  # "pass", "cast_spell", "activate_ability", "play_land",
                      # "declare_attackers", "declare_blockers", "assign_damage",
                      # "choose_target", "choose_mode"
    card: Optional[Any] = None
    ability: Optional[Any] = None
    targets: List[Any] = field(default_factory=list)
    value: Any = None  # For choices (modes, X values, etc.)

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

    @property
    def is_creature(self) -> bool:
        return "creature" in [t.lower() for t in self.card_types]

    @property
    def is_instant(self) -> bool:
        return "instant" in [t.lower() for t in self.card_types]

    @property
    def is_sorcery(self) -> bool:
        return "sorcery" in [t.lower() for t in self.card_types]

    @property
    def is_land(self) -> bool:
        return "land" in [t.lower() for t in self.card_types]

    @property
    def is_enchantment(self) -> bool:
        return "enchantment" in [t.lower() for t in self.card_types]

    @property
    def is_artifact(self) -> bool:
        return "artifact" in [t.lower() for t in self.card_types]

    @property
    def is_planeswalker(self) -> bool:
        return "planeswalker" in [t.lower() for t in self.card_types]


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

    @property
    def is_creature(self) -> bool:
        return "creature" in [t.lower() for t in self.card_types]

    @property
    def is_land(self) -> bool:
        return "land" in [t.lower() for t in self.card_types]

    @property
    def is_artifact(self) -> bool:
        return "artifact" in [t.lower() for t in self.card_types]

    @property
    def is_enchantment(self) -> bool:
        return "enchantment" in [t.lower() for t in self.card_types]

    @property
    def is_planeswalker(self) -> bool:
        return "planeswalker" in [t.lower() for t in self.card_types]

    @property
    def can_attack(self) -> bool:
        return (self.is_creature and
                not self.is_tapped and
                not self.has_summoning_sickness)

    @property
    def can_block(self) -> bool:
        return self.is_creature and not self.is_tapped

    @property
    def remaining_toughness(self) -> int:
        if self.toughness is None:
            return 0
        return self.toughness - self.damage_marked

    def has_keyword(self, keyword: str) -> bool:
        return keyword.lower() in [k.lower() for k in self.keywords]


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


def build_game_state(game: Any, player: Any) -> GameState:
    """Build a GameState view for a player from the game object."""
    import re

    def get_cmc(cost):
        """Parse mana cost to get CMC. Accepts string or ManaCost object."""
        if not cost:
            return 0
        # If it's a ManaCost object, use its cmc property
        if hasattr(cost, 'cmc'):
            return cost.cmc
        # If it's a string, parse it
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

        # Handle mana_cost - convert to string if it's a ManaCost object
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

    # Get player IDs
    my_id = player.player_id
    opp_id = None
    for pid in game.players:
        if pid != my_id:
            opp_id = pid
            break

    # Build hand info
    my_hand = []
    if hasattr(game.zones, 'hands') and my_id in game.zones.hands:
        hand = game.zones.hands[my_id]
        cards = hand.objects if hasattr(hand, 'objects') else (hand.cards if hasattr(hand, 'cards') else [])
        for card in cards:
            my_hand.append(card_to_info(card))

    # Build battlefield info
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

    # Build graveyard info
    my_graveyard = []
    if hasattr(game.zones, 'graveyards') and my_id in game.zones.graveyards:
        gy = game.zones.graveyards[my_id]
        cards = gy.objects if hasattr(gy, 'objects') else (gy.cards if hasattr(gy, 'cards') else [])
        for card in cards:
            my_graveyard.append(card_to_info(card))

    # Get current step
    current_step = "unknown"
    if hasattr(game, 'current_step') and game.current_step:
        current_step = str(game.current_step.name if hasattr(game.current_step, 'name')
                         else game.current_step)

    # Get mana - use the player's actual mana pool PLUS untapped lands
    # This ensures we see correct mana after casting spells (mana pool is updated)
    # and can also account for lands that haven't been tapped yet
    mana_available = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}

    try:
        from engine.types import Color
        from engine.mana import get_land_mana_color
    except ImportError:
        from ..engine.types import Color
        from ..engine.mana import get_land_mana_color

    # First, add mana currently in the player's mana pool
    # This represents mana that's already been produced and is ready to spend
    if hasattr(player, 'mana_pool') and player.mana_pool:
        pool = player.mana_pool
        if hasattr(pool, 'mana') and isinstance(pool.mana, dict):
            # ManaPool from player.py uses Color enum as keys
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
            # Alternative ManaPool interface
            mana_available["W"] += pool.get(Color.WHITE)
            mana_available["U"] += pool.get(Color.BLUE)
            mana_available["B"] += pool.get(Color.BLACK)
            mana_available["R"] += pool.get(Color.RED)
            mana_available["G"] += pool.get(Color.GREEN)
            mana_available["C"] += pool.get(Color.COLORLESS)

    # Second, add potential mana from untapped lands
    # This represents mana that CAN be produced by tapping lands
    for perm in my_battlefield:
        if perm.is_land and not perm.is_tapped:
            # Use the reference to get actual permanent data for mana color
            actual_perm = perm.reference
            if actual_perm:
                # Get land name and subtypes from the actual permanent
                land_name = ""
                subtypes = set()
                if hasattr(actual_perm, 'characteristics'):
                    chars = actual_perm.characteristics
                    land_name = getattr(chars, 'name', '')
                    subtypes = set(getattr(chars, 'subtypes', []))
                else:
                    land_name = perm.name
                    subtypes = set(perm.subtypes) if perm.subtypes else set()

                # Use the mana system's helper to determine what color this land produces
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
                    # Default to colorless for unknown lands
                    mana_available["C"] += 1
            else:
                # Fallback: use PermanentInfo name if no reference
                # Default to colorless if we can't determine the color
                mana_available["C"] += 1

    # Life totals
    my_life = player.life
    opp_life = game.players[opp_id].life if opp_id else 20

    return GameState(
        my_life=my_life,
        opp_life=opp_life,
        my_hand=my_hand,
        my_battlefield=my_battlefield,
        opp_battlefield=opp_battlefield,
        my_graveyard=my_graveyard,
        stack=[],  # Simplified - stack tracking is complex
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
        """
        Wrapper that builds GameState and calls get_priority_action.
        This is called by the priority system.
        """
        state = build_game_state(game, self.player)
        action = self.get_priority_action(state)

        # Debug output
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
        """Decide what action to take when we have priority."""
        pass

    @abstractmethod
    def choose_attackers(self, state: GameState, available: List[PermanentInfo]) -> List[Any]:
        """Choose which creatures to attack with. Returns list of references."""
        pass

    @abstractmethod
    def choose_blockers(self, state: GameState, attackers: List[PermanentInfo],
                        available: List[PermanentInfo]) -> Dict[Any, List[Any]]:
        """Choose how to assign blockers. Returns {attacker_ref: [blocker_refs]}."""
        pass

    @abstractmethod
    def assign_damage(self, state: GameState, creature: PermanentInfo,
                      blockers: List[PermanentInfo], damage: int) -> List[Tuple[Any, int]]:
        """Assign combat damage. Returns [(target, damage_amount), ...]."""
        pass

    @abstractmethod
    def choose_targets(self, state: GameState, requirements: Any,
                       legal_targets: List[Any]) -> List[Any]:
        """Choose targets for a spell or ability."""
        pass

    @abstractmethod
    def choose_modes(self, state: GameState, card: Any, num_modes: int) -> List[int]:
        """Choose modes for a modal spell."""
        pass

    @abstractmethod
    def choose_order(self, state: GameState, items: List[Any], reason: str) -> List[Any]:
        """Order items (e.g., triggers, blockers for damage assignment)."""
        pass

    @abstractmethod
    def mulligan_decision(self, state: GameState, hand: List[CardInfo],
                          mulligan_count: int) -> bool:
        """Decide whether to mulligan. Returns True to mulligan."""
        pass


class SimpleAI(AIAgent):
    """Basic AI implementation with straightforward heuristics."""

    # Keyword value weights for threat evaluation
    KEYWORD_VALUES: Dict[str, float] = {
        "flying": 1.5,
        "trample": 1.0,
        "deathtouch": 2.0,
        "first strike": 1.5,
        "double strike": 3.0,
        "lifelink": 1.5,
        "vigilance": 0.5,
        "haste": 0.5,
        "hexproof": 2.0,
        "indestructible": 3.0,
        "menace": 1.0,
        "reach": 0.5,
        "protection": 2.0,
        "unblockable": 2.5,
        "shroud": 1.8,
        "flash": 0.5,
        "defender": -2.0,
    }

    def __init__(self, player: Any, game: Any):
        super().__init__(player, game)
        self.land_played_this_turn = False
        # Track mana committed during the current priority pass to prevent over-casting
        # This is reset when we pass priority or a new priority pass begins
        self._mana_committed_this_priority: Dict[str, int] = {
            "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0
        }

    def get_priority_action(self, state: GameState) -> Action:
        """Decide what action to take when we have priority."""
        # If opponent has spell on stack, usually pass (simple AI doesn't counter much)
        if state.stack and state.stack[-1].controller == "opponent":
            # Could add instant-speed response logic here
            self._reset_mana_commitment()
            return Action(action_type="pass")

        # Main phase actions
        if state.is_my_turn and state.is_main_phase:
            # Try to play a land first
            land_action = self._try_play_land(state)
            if land_action:
                return land_action

            # Find best spell to cast (accounts for mana already committed)
            spell_action = self._find_best_spell(state)
            if spell_action:
                return spell_action

            # Try to activate abilities
            ability_action = self._find_best_ability(state)
            if ability_action:
                return ability_action

        # Default: pass priority - reset mana commitment for next priority pass
        self._reset_mana_commitment()
        return Action(action_type="pass")

    def _reset_mana_commitment(self) -> None:
        """Reset the mana committed tracking for a new priority pass."""
        self._mana_committed_this_priority = {
            "W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0
        }

    def _get_effective_mana(self, state: GameState) -> Dict[str, int]:
        """Get available mana minus what's already been committed this priority pass.

        Returns:
            Dict mapping color symbols to available mana amounts.
        """
        effective = {}
        for color in state.mana_available:
            committed = self._mana_committed_this_priority.get(color, 0)
            effective[color] = max(0, state.mana_available.get(color, 0) - committed)
        return effective

    def _commit_mana_for_spell(self, card_cmc: int) -> None:
        """Mark mana as committed for a spell we're about to cast.

        For simplicity, we commit generic mana (colorless) first.
        A more sophisticated implementation would track exact color requirements.

        Args:
            card_cmc: The converted mana cost of the spell being cast.
        """
        # Simple approach: commit CMC amount as generic mana
        # The game engine will handle actual color requirements
        self._mana_committed_this_priority["C"] = (
            self._mana_committed_this_priority.get("C", 0) + card_cmc
        )

    def _try_play_land(self, state: GameState) -> Optional[Action]:
        """Try to play a land from hand."""
        if self.land_played_this_turn:
            return None

        lands_in_hand = [c for c in state.my_hand if c.is_land]
        if not lands_in_hand:
            return None

        # Prefer lands that produce colors we need
        # For now, just play the first land
        best_land = lands_in_hand[0]
        return Action(action_type="play_land", card=best_land.reference)

    def _find_best_spell(self, state: GameState) -> Optional[Action]:
        """Find the best spell to cast.

        Uses effective mana (available minus committed) to prevent over-casting
        when multiple spells could theoretically be cast in one priority pass.
        """
        castable: List[Tuple[CardInfo, float]] = []

        # Calculate effective mana (accounts for mana already committed this priority)
        effective_mana = self._get_effective_mana(state)
        effective_total = sum(effective_mana.values())

        # Debug: show mana available vs effective
        if state.is_my_turn and state.is_main_phase:
            lands = [p for p in state.my_battlefield if p.is_land]
            committed_total = sum(self._mana_committed_this_priority.values())
            print(f"    [AI P{self.player.player_id}] Lands: {len(lands)}, "
                  f"Total Mana: {state.total_mana}, Effective: {effective_total}, "
                  f"Committed: {committed_total}, Hand: {len(state.my_hand)}")

        for card in state.my_hand:
            if card.is_land:
                continue

            # Check if we can afford this spell with EFFECTIVE mana (not total)
            if card.cmc > effective_total:
                continue

            score = self._evaluate_card_to_cast(card, state)
            castable.append((card, score))

        if not castable:
            return None

        # Sort by score descending
        castable.sort(key=lambda x: x[1], reverse=True)
        best_card, best_score = castable[0]

        if best_score > 0:
            # Commit the mana for this spell before returning the action
            # This prevents over-casting if get_priority_action is called again
            # before the spell resolves (e.g., in response scenarios)
            self._commit_mana_for_spell(best_card.cmc)
            return Action(action_type="cast_spell", card=best_card.reference)

        return None

    def _find_best_ability(self, state: GameState) -> Optional[Action]:
        """Find the best activated ability to use."""
        # Simple AI doesn't use many activated abilities
        # Could be extended for more complex behavior
        return None

    def _evaluate_card_to_cast(self, card: CardInfo, state: GameState) -> float:
        """Evaluate how good it would be to cast this card now."""
        score = 0.0

        if card.is_creature:
            # Base score from power/toughness
            power = card.power or 0
            toughness = card.toughness or 0
            score = power * 1.5 + toughness * 0.5

            # Adjust for keywords
            for keyword in card.keywords:
                score += self.KEYWORD_VALUES.get(keyword.lower(), 0)

            # Prefer efficient creatures (high stats for low cost)
            if card.cmc > 0:
                efficiency = (power + toughness) / card.cmc
                score += efficiency * 0.5

            # Bonus for having haste when we can attack
            if "haste" in [k.lower() for k in card.keywords]:
                score += 1.5

        elif card.is_instant:
            # Instants are situational - lower base priority in main phase
            score = 2.0

        elif card.is_sorcery:
            # Sorceries have moderate priority
            score = 3.0 + (6 - min(card.cmc, 6))

        elif card.is_enchantment:
            score = 2.5 + (5 - min(card.cmc, 5))

        elif card.is_artifact:
            score = 2.5 + (5 - min(card.cmc, 5))

        elif card.is_planeswalker:
            # Planeswalkers are high priority
            score = 6.0

        else:
            # Other spells
            score = 3.0 + (6 - min(card.cmc, 6))

        # Reduce score if we'd be tapping out early
        if state.total_mana <= 3 and card.cmc == state.total_mana:
            score *= 0.8

        # Adjust based on board state
        if len(state.my_creatures) > len(state.opp_creatures):
            # We have board advantage, prefer threats
            if card.is_creature:
                score += 1.0
        else:
            # We're behind, prefer removal/interaction
            if not card.is_creature:
                score += 1.0

        return score

    def _evaluate_threat(self, permanent: PermanentInfo) -> float:
        """Evaluate how threatening a permanent is."""
        if not permanent.is_creature:
            # Non-creature permanents have base threat
            if permanent.is_planeswalker:
                return 5.0
            if permanent.is_enchantment:
                return 2.0
            if permanent.is_artifact:
                return 1.5
            return 1.0

        power = permanent.power or 0
        toughness = permanent.toughness or 0

        # Base threat from stats
        threat = power * 2.0 + toughness * 0.5

        # Adjust for keywords
        for keyword in permanent.keywords:
            threat += self.KEYWORD_VALUES.get(keyword.lower(), 0)

        # Adjust for current state
        if permanent.is_tapped:
            threat *= 0.7
        if permanent.has_summoning_sickness:
            threat *= 0.8

        # Evasion makes creatures more threatening
        if permanent.has_keyword("flying"):
            threat *= 1.3
        if permanent.has_keyword("unblockable"):
            threat *= 1.5

        # +1/+1 counters increase threat
        if "+1/+1" in permanent.counters:
            threat += permanent.counters["+1/+1"] * 1.5

        return threat

    def _can_attack_profitably(self, creature: PermanentInfo,
                                blockers: List[PermanentInfo]) -> bool:
        """Determine if a creature can attack without being unfavorably blocked."""
        if not creature.can_attack:
            return False

        power = creature.power or 0
        toughness = creature.toughness or 0

        # Flying creatures can only be blocked by flyers/reach
        if creature.has_keyword("flying"):
            relevant_blockers = [b for b in blockers
                                if b.has_keyword("flying") or b.has_keyword("reach")]
        else:
            relevant_blockers = [b for b in blockers if b.can_block]

        if not relevant_blockers:
            return True

        # Check if creature has evasion
        if creature.has_keyword("menace"):
            # Need at least 2 blockers
            if len(relevant_blockers) < 2:
                return True

        # Unblockable always attacks
        if creature.has_keyword("unblockable"):
            return True

        # Check for favorable trades or survival
        for blocker in relevant_blockers:
            blocker_power = blocker.power or 0
            blocker_toughness = blocker.toughness or 0

            # Would we die?
            if blocker_power >= toughness:
                # Handle first strike
                if creature.has_keyword("first strike") or creature.has_keyword("double strike"):
                    if power >= blocker_toughness:
                        # We kill them before they hit us
                        return True

                # Would we at least trade?
                if power >= blocker_toughness:
                    # Trade is acceptable if our creature is worth less
                    our_value = self._evaluate_threat(creature)
                    their_value = self._evaluate_threat(blocker)
                    if our_value < their_value:
                        return True
                    # Don't want to trade down
                    continue
                # We'd die without trading - bad
                return False

        # We survive or trade favorably
        return True

    def _should_block(self, blocker: PermanentInfo, attacker: PermanentInfo) -> float:
        """Score how good it would be for blocker to block attacker."""
        if not blocker.can_block:
            return -100.0

        blocker_power = blocker.power or 0
        blocker_toughness = blocker.toughness or 0
        attacker_power = attacker.power or 0
        attacker_toughness = attacker.toughness or 0

        score = 0.0

        # Check if we can kill the attacker
        kills_attacker = blocker_power >= attacker_toughness
        if blocker.has_keyword("deathtouch"):
            kills_attacker = blocker_power > 0  # Just need to deal any damage

        # Check if we survive
        survives = blocker_toughness > attacker_power
        if attacker.has_keyword("deathtouch") and attacker_power > 0:
            survives = False
        if blocker.has_keyword("indestructible"):
            survives = True

        # First strike considerations
        if attacker.has_keyword("first strike") or attacker.has_keyword("double strike"):
            if not blocker.has_keyword("first strike") and not blocker.has_keyword("double strike"):
                if attacker_power >= blocker_toughness:
                    # Attacker kills us before we deal damage
                    kills_attacker = False
                    survives = False

        # Our first strike advantage
        if blocker.has_keyword("first strike") or blocker.has_keyword("double strike"):
            if not attacker.has_keyword("first strike") and not attacker.has_keyword("double strike"):
                if blocker_power >= attacker_toughness:
                    # We kill them before they hit us
                    kills_attacker = True
                    survives = True

        if kills_attacker and survives:
            # Best case: kill attacker and survive
            score = 10.0 + self._evaluate_threat(attacker)
        elif kills_attacker:
            # Trade
            our_value = self._evaluate_threat(blocker)
            their_value = self._evaluate_threat(attacker)
            score = their_value - our_value
        elif survives:
            # Just prevent damage
            score = attacker_power * 0.5
        else:
            # Chump block - only good if preventing lethal or blocking big threat
            score = attacker_power * 0.2 - self._evaluate_threat(blocker) * 0.5

        return score

    def choose_attackers(self, state: GameState, available: List[PermanentInfo]) -> List[Any]:
        """Choose which creatures to attack with."""
        if not available:
            return []

        attackers: List[Any] = []
        potential_blockers = [c for c in state.opp_creatures if c.can_block]

        # Calculate total possible damage
        total_damage = sum(c.power or 0 for c in available if c.can_attack)

        # Check for lethal
        if total_damage >= state.opp_life:
            # Attack with everything!
            return [c.reference for c in available if c.can_attack]

        # Evaluate each potential attacker
        for creature in available:
            if not creature.can_attack:
                continue

            # Evasive creatures almost always attack
            if creature.has_keyword("flying"):
                flying_blockers = [b for b in potential_blockers
                                  if b.has_keyword("flying") or b.has_keyword("reach")]
                if not flying_blockers:
                    attackers.append(creature.reference)
                    continue
                elif self._can_attack_profitably(creature, flying_blockers):
                    attackers.append(creature.reference)
                    continue

            # Unblockable always attacks
            if creature.has_keyword("unblockable"):
                attackers.append(creature.reference)
                continue

            # Check if we can attack profitably
            if self._can_attack_profitably(creature, potential_blockers):
                attackers.append(creature.reference)

        return attackers

    def choose_blockers(self, state: GameState, attackers: List[PermanentInfo],
                        available: List[PermanentInfo]) -> Dict[Any, List[Any]]:
        """Choose how to assign blockers. Returns {attacker_ref: [blocker_refs]}."""
        if not attackers or not available:
            return {}

        blocks: Dict[Any, List[Any]] = {}
        used_blockers: set = set()

        # Calculate incoming damage
        total_incoming = sum(a.power or 0 for a in attackers)

        # Check if we need to block to survive
        must_block = total_incoming >= state.my_life

        # Score all possible blocks
        block_options: List[Tuple[PermanentInfo, PermanentInfo, float]] = []
        for attacker in attackers:
            # Check if attacker can be blocked
            if attacker.has_keyword("unblockable"):
                continue

            for blocker in available:
                if id(blocker.reference) in used_blockers:
                    continue

                # Check flying restriction
                if attacker.has_keyword("flying"):
                    if not blocker.has_keyword("flying") and not blocker.has_keyword("reach"):
                        continue

                score = self._should_block(blocker, attacker)
                block_options.append((blocker, attacker, score))

        # Sort by score descending
        block_options.sort(key=lambda x: x[2], reverse=True)

        # Assign blocks greedily
        for blocker, attacker, score in block_options:
            if id(blocker.reference) in used_blockers:
                continue

            # Handle menace - need 2 blockers
            if attacker.has_keyword("menace"):
                attacker_ref = attacker.reference
                if attacker_ref in blocks and len(blocks[attacker_ref]) >= 1:
                    # Already have one blocker, add second
                    blocks[attacker_ref].append(blocker.reference)
                    used_blockers.add(id(blocker.reference))
                    continue
                elif attacker_ref not in blocks:
                    # Need to find a second blocker
                    other_blockers = [
                        (b, s) for b, a, s in block_options
                        if a.reference == attacker_ref
                        and id(b.reference) not in used_blockers
                        and id(b.reference) != id(blocker.reference)
                    ]
                    if other_blockers:
                        # Can assign two blockers
                        blocks[attacker_ref] = [blocker.reference, other_blockers[0][0].reference]
                        used_blockers.add(id(blocker.reference))
                        used_blockers.add(id(other_blockers[0][0].reference))
                    continue

            # Take favorable blocks
            if score > 0 or must_block:
                attacker_ref = attacker.reference
                if attacker_ref not in blocks:
                    blocks[attacker_ref] = []
                blocks[attacker_ref].append(blocker.reference)
                used_blockers.add(id(blocker.reference))

                # Reduce incoming damage tracking
                if must_block:
                    total_incoming -= (attacker.power or 0)
                    if total_incoming < state.my_life:
                        must_block = False

        return blocks

    def assign_damage(self, state: GameState, creature: PermanentInfo,
                      blockers: List[PermanentInfo], damage: int) -> List[Tuple[Any, int]]:
        """Assign combat damage from creature to blockers (and possibly player)."""
        if not blockers:
            # All damage to defending player (or planeswalker if applicable)
            return [("player", damage)]

        assignments: List[Tuple[Any, int]] = []
        remaining_damage = damage
        has_trample = creature.has_keyword("trample")
        has_deathtouch = creature.has_keyword("deathtouch")

        # Sort blockers by toughness (kill small ones first to maximize trample)
        sorted_blockers = sorted(blockers, key=lambda b: b.remaining_toughness)

        for blocker in sorted_blockers:
            if remaining_damage <= 0:
                break

            lethal = blocker.remaining_toughness
            if has_deathtouch:
                lethal = 1  # Only need 1 damage with deathtouch

            # Assign lethal damage
            assigned = min(lethal, remaining_damage)
            assignments.append((blocker.reference, assigned))
            remaining_damage -= assigned

        # Trample excess to player
        if has_trample and remaining_damage > 0:
            assignments.append(("player", remaining_damage))

        return assignments

    def choose_targets(self, state: GameState, requirements: Any,
                       legal_targets: List[Any]) -> List[Any]:
        """Choose targets for a spell or ability."""
        if not legal_targets:
            return []

        targets: List[Any] = []

        # Try to identify target type from requirements or target properties
        # For removal: target highest threat opponent creature
        opp_creatures = []
        my_creatures = []

        for target in legal_targets:
            if hasattr(target, 'controller'):
                if target.controller != self.player:
                    if hasattr(target, 'power'):  # Likely a creature
                        opp_creatures.append(target)
                else:
                    if hasattr(target, 'power'):
                        my_creatures.append(target)

        # If we have opponent creatures, target highest threat (for removal)
        if opp_creatures:
            best_target = max(opp_creatures, key=lambda t: self._evaluate_threat(t)
                             if isinstance(t, PermanentInfo) else
                             (t.power * 2 + t.toughness if hasattr(t, 'power') else 0))
            return [best_target]

        # For buffs: target best attacker we control
        if my_creatures:
            can_attack = [c for c in my_creatures
                         if hasattr(c, 'can_attack') and c.can_attack]
            if can_attack:
                return [can_attack[0]]
            return [my_creatures[0]]

        # Default: first legal target
        return [legal_targets[0]] if legal_targets else []

    def choose_modes(self, state: GameState, card: Any, num_modes: int) -> List[int]:
        """Choose modes for a modal spell."""
        # Simple AI just picks the first N modes
        # More sophisticated AI would evaluate each mode based on game state
        return list(range(num_modes))

    def choose_order(self, state: GameState, items: List[Any], reason: str) -> List[Any]:
        """Order items (e.g., triggers, blockers for damage assignment)."""
        # Simple AI keeps the default order
        # Could be enhanced to order triggers optimally
        return list(items)

    def mulligan_decision(self, state: GameState, hand: List[CardInfo],
                          mulligan_count: int) -> bool:
        """Decide whether to mulligan. Returns True to mulligan."""
        # Count lands
        land_count = sum(1 for c in hand if c.is_land)
        hand_size = len(hand)

        # Always keep if we've mulliganed too much
        if mulligan_count >= 3:
            return False

        # Mulligan no-land or all-land hands
        if land_count == 0:
            return True
        if land_count == hand_size:
            return True

        # Ideal land count is 2-4 for 7 cards, scale down for smaller hands
        ideal_min = max(1, (hand_size * 2) // 7)
        ideal_max = max(2, (hand_size * 4) // 7)

        if land_count < ideal_min or land_count > ideal_max:
            # Consider mulliganing, but factor in mulligan count
            if mulligan_count == 0:
                return True
            elif mulligan_count == 1 and (land_count == 0 or land_count >= hand_size - 1):
                return True

        # Check for playable spells (can cast something in first 3 turns)
        playable_spells = [c for c in hand if not c.is_land and c.cmc <= land_count + 1]
        if not playable_spells and mulligan_count < 2:
            return True

        # Check curve - do we have early plays?
        early_plays = [c for c in hand if not c.is_land and c.cmc <= 2]
        if not early_plays and land_count >= 3 and mulligan_count == 0:
            return True  # No early game, consider mulling

        return False

    def reset_turn_state(self) -> None:
        """Reset per-turn tracking state."""
        self.land_played_this_turn = False
        self._reset_mana_commitment()

    def notify_land_played(self) -> None:
        """Called when a land is played to track land drops."""
        self.land_played_this_turn = True


class RandomAI(AIAgent):
    """AI that makes random legal decisions. Useful for testing."""

    def get_priority_action(self, state: GameState) -> Action:
        """Pass priority most of the time, occasionally cast spells."""
        import random

        if random.random() < 0.7:
            return Action(action_type="pass")

        # Try to play a land
        lands = [c for c in state.my_hand if c.is_land]
        if lands and random.random() < 0.5:
            return Action(action_type="play_land", card=random.choice(lands).reference)

        # Try to cast a spell
        castable = [c for c in state.my_hand
                   if not c.is_land and state.can_afford(c.cmc)]
        if castable:
            return Action(action_type="cast_spell",
                         card=random.choice(castable).reference)

        return Action(action_type="pass")

    def choose_attackers(self, state: GameState, available: List[PermanentInfo]) -> List[Any]:
        """Randomly choose some attackers."""
        import random

        if not available:
            return []

        can_attack = [c for c in available if c.can_attack]
        if not can_attack:
            return []

        # Attack with random subset
        num_attackers = random.randint(0, len(can_attack))
        return [c.reference for c in random.sample(can_attack, num_attackers)]

    def choose_blockers(self, state: GameState, attackers: List[PermanentInfo],
                        available: List[PermanentInfo]) -> Dict[Any, List[Any]]:
        """Randomly assign some blockers."""
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
        """Assign damage evenly-ish to blockers."""
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

    def choose_targets(self, state: GameState, requirements: Any,
                       legal_targets: List[Any]) -> List[Any]:
        """Choose random legal targets."""
        import random

        if not legal_targets:
            return []
        return [random.choice(legal_targets)]

    def choose_modes(self, state: GameState, card: Any, num_modes: int) -> List[int]:
        """Choose random modes."""
        import random

        # Assume modes are 0-indexed up to some maximum
        available_modes = list(range(min(num_modes + 2, 4)))  # Guess at max modes
        return random.sample(available_modes, min(num_modes, len(available_modes)))

    def choose_order(self, state: GameState, items: List[Any], reason: str) -> List[Any]:
        """Return items in random order."""
        import random

        result = list(items)
        random.shuffle(result)
        return result

    def mulligan_decision(self, state: GameState, hand: List[CardInfo],
                          mulligan_count: int) -> bool:
        """Randomly decide to mulligan."""
        import random

        # Less likely to mulligan as count increases
        return random.random() < (0.4 / (mulligan_count + 1))
