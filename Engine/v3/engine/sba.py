"""
State-Based Actions (SBA) implementation per Comprehensive Rules 704.

State-based actions are game actions that happen automatically whenever certain
conditions are met. They are checked whenever a player would receive priority.
"""

from dataclasses import dataclass, field
from typing import Any, List, Dict, TYPE_CHECKING
from collections import defaultdict
from .types import *

if TYPE_CHECKING:
    from .game import Game
    from .objects import Permanent
    from .player import Player


@dataclass
class SBAResult:
    """
    Result of state-based action checks.

    Tracks all changes made during SBA processing for game state tracking
    and potential triggered ability handling.
    """
    actions_performed: int = 0
    players_lost: List[Any] = field(default_factory=list)
    creatures_died: List[Any] = field(default_factory=list)
    other_changes: List[str] = field(default_factory=list)

    def merge(self, other: 'SBAResult') -> 'SBAResult':
        """Merge another SBAResult into this one."""
        return SBAResult(
            actions_performed=self.actions_performed + other.actions_performed,
            players_lost=self.players_lost + other.players_lost,
            creatures_died=self.creatures_died + other.creatures_died,
            other_changes=self.other_changes + other.other_changes
        )

    def __bool__(self) -> bool:
        """Returns True if any actions were performed."""
        return self.actions_performed > 0


class StateBasedActionChecker:
    """
    Checks and performs state-based actions per CR 704.

    State-based actions are checked whenever a player would receive priority.
    All applicable SBAs are performed simultaneously, then checked again
    until no more SBAs apply.

    CR 704.3: Whenever a player would get priority, the game checks for any
    of the listed conditions for state-based actions, then performs all
    applicable state-based actions simultaneously as a single event.
    """

    def __init__(self, game: 'Game'):
        """
        Initialize the SBA checker with a game reference.

        Args:
            game: The game instance to check and modify
        """
        self.game = game

    def check_and_perform(self) -> SBAResult:
        """
        Perform all applicable state-based actions simultaneously.

        CR 704.3: The game checks for all applicable SBAs and performs
        them simultaneously as a single event.

        Returns:
            SBAResult containing all actions performed
        """
        result = SBAResult()

        # Player SBAs (CR 704.5a-c)
        self._check_life_loss(result)
        self._check_draw_from_empty(result)
        self._check_poison(result)

        # Token SBAs (CR 704.5d)
        self._check_token_in_other_zones(result)

        # Creature SBAs (CR 704.5f-h)
        self._check_zero_toughness(result)
        self._check_lethal_damage(result)
        self._check_deathtouch_damage(result)

        # Planeswalker SBAs (CR 704.5i)
        self._check_zero_loyalty(result)

        # Legend Rule (CR 704.5j)
        self._check_legend_rule(result)

        # Attachment SBAs (CR 704.5m-n)
        self._check_aura_attached(result)
        self._check_equipment_attached(result)

        # Counter SBAs (CR 704.5q)
        self._check_counter_annihilation(result)

        return result

    def run_until_stable(self) -> SBAResult:
        """
        Repeatedly check and perform SBAs until game state is stable.

        CR 704.3: After performing SBAs, the game checks again. This
        process repeats until no state-based actions are performed.

        Returns:
            Combined SBAResult of all iterations
        """
        combined_result = SBAResult()

        while True:
            result = self.check_and_perform()
            if not result:
                # No SBAs performed, game state is stable
                break
            combined_result = combined_result.merge(result)

        return combined_result

    # =========================================================================
    # Player SBAs (CR 704.5a-c)
    # =========================================================================

    def _check_life_loss(self, result: SBAResult) -> None:
        """
        CR 704.5a: If a player has 0 or less life, that player loses the game.

        Note: This doesn't apply if an effect says the player can't lose
        the game (e.g., Platinum Angel).
        """
        for player in self.game.players.values():
            if not player.is_alive():
                continue

            # Check for effects that prevent losing the game
            if getattr(player, 'cannot_lose_game', False):
                continue

            if player.life <= 0:
                player.lose_game("life <= 0")
                result.players_lost.append(player)
                result.actions_performed += 1
                result.other_changes.append(
                    f"{player.name} loses the game: life total is {player.life}"
                )

    def _check_draw_from_empty(self, result: SBAResult) -> None:
        """
        CR 704.5b: If a player attempted to draw a card from an empty library
        since the last time SBAs were checked, that player loses the game.

        Note: The flag is set when a draw is attempted from empty library.
        """
        for player in self.game.players.values():
            if not player.is_alive():
                continue

            if getattr(player, 'cannot_lose_game', False):
                continue

            if player.drew_from_empty_library:
                player.lose_game("drew from empty library")
                result.players_lost.append(player)
                result.actions_performed += 1
                result.other_changes.append(
                    f"{player.name} loses the game: attempted to draw from empty library"
                )

    def _check_poison(self, result: SBAResult) -> None:
        """
        CR 704.5c: If a player has ten or more poison counters, that player
        loses the game.

        Note: The threshold is 10 in normal games but can be modified.
        """
        poison_threshold = getattr(self.game, 'poison_threshold', 10)

        for player in self.game.players.values():
            if not player.is_alive():
                continue

            if getattr(player, 'cannot_lose_game', False):
                continue

            if player.poison_counters >= poison_threshold:
                player.lose_game(f"{poison_threshold}+ poison counters")
                result.players_lost.append(player)
                result.actions_performed += 1
                result.other_changes.append(
                    f"{player.name} loses the game: has {player.poison_counters} poison counters"
                )

    # =========================================================================
    # Creature SBAs (CR 704.5f-h)
    # =========================================================================

    def _check_zero_toughness(self, result: SBAResult) -> None:
        """
        CR 704.5f: If a creature has toughness 0 or less, it's put into its
        owner's graveyard. Regeneration can't replace this event.

        Note: This is not destruction - it's a direct zone change.
        """
        from .events import DiesEvent

        creatures_to_die = []

        for creature in self.game.zones.battlefield.creatures():
            if creature.eff_toughness() <= 0:
                creatures_to_die.append(creature)

        for creature in creatures_to_die:
            # Zero toughness bypasses indestructible and regeneration
            self.game.zones.battlefield.remove(creature)
            self.game.zones.graveyards[creature.owner_id].add(creature)

            self.game.events.emit(DiesEvent(
                permanent_id=creature.object_id,
                permanent=creature
            ))

            result.creatures_died.append(creature)
            result.actions_performed += 1
            result.other_changes.append(
                f"{creature.characteristics.name} dies: toughness reduced to "
                f"{creature.eff_toughness()}"
            )

    def _check_lethal_damage(self, result: SBAResult) -> None:
        """
        CR 704.5g: If a creature has toughness greater than 0, and the total
        damage marked on it is greater than or equal to its toughness, that
        creature has been dealt lethal damage and is destroyed.

        Note: Regeneration can replace this destruction.
        """
        from .events import DiesEvent

        creatures_to_destroy = []

        for creature in self.game.zones.battlefield.creatures():
            toughness = creature.eff_toughness()
            # Only check if toughness > 0 (otherwise _check_zero_toughness handles it)
            if toughness > 0 and creature.damage_marked >= toughness:
                creatures_to_destroy.append(creature)

        for creature in creatures_to_destroy:
            # Check for indestructible
            if creature.has_keyword("indestructible"):
                continue

            # Check for regeneration shield
            if getattr(creature, 'regeneration_shield', False):
                creature.regeneration_shield = False
                creature.damage_marked = 0
                creature.tap()
                # Remove from combat if applicable
                if hasattr(creature, 'remove_from_combat'):
                    creature.remove_from_combat()
                result.actions_performed += 1
                result.other_changes.append(
                    f"{creature.characteristics.name} regenerates"
                )
                continue

            self.game.zones.battlefield.remove(creature)
            self.game.zones.graveyards[creature.owner_id].add(creature)

            self.game.events.emit(DiesEvent(
                permanent_id=creature.object_id,
                permanent=creature
            ))

            result.creatures_died.append(creature)
            result.actions_performed += 1
            result.other_changes.append(
                f"{creature.characteristics.name} dies: lethal damage "
                f"({creature.damage_marked} damage, {creature.eff_toughness()} toughness)"
            )

    def _check_deathtouch_damage(self, result: SBAResult) -> None:
        """
        CR 704.5h: If a creature has been dealt damage by a source with
        deathtouch since the last time SBAs were checked, that creature
        is destroyed.

        Note: Any amount of damage from deathtouch is lethal. Regeneration
        can replace this destruction.
        """
        from .events import DiesEvent

        creatures_to_destroy = []

        for creature in self.game.zones.battlefield.creatures():
            # Check if dealt damage by deathtouch and has damage marked
            if creature.dealt_damage_by_deathtouch and creature.damage_marked > 0:
                creatures_to_destroy.append(creature)

        for creature in creatures_to_destroy:
            # Check for indestructible
            if creature.has_keyword("indestructible"):
                creature.dealt_damage_by_deathtouch = False
                continue

            # Check for regeneration shield
            if getattr(creature, 'regeneration_shield', False):
                creature.regeneration_shield = False
                creature.damage_marked = 0
                creature.tap()
                creature.dealt_damage_by_deathtouch = False
                if hasattr(creature, 'remove_from_combat'):
                    creature.remove_from_combat()
                result.actions_performed += 1
                result.other_changes.append(
                    f"{creature.characteristics.name} regenerates from deathtouch"
                )
                continue

            self.game.zones.battlefield.remove(creature)
            self.game.zones.graveyards[creature.owner_id].add(creature)

            self.game.events.emit(DiesEvent(
                permanent_id=creature.object_id,
                permanent=creature
            ))

            result.creatures_died.append(creature)
            result.actions_performed += 1
            result.other_changes.append(
                f"{creature.characteristics.name} dies: damage from source with deathtouch"
            )

    # =========================================================================
    # Planeswalker SBAs (CR 704.5i)
    # =========================================================================

    def _check_zero_loyalty(self, result: SBAResult) -> None:
        """
        CR 704.5i: If a planeswalker has loyalty 0, it's put into its
        owner's graveyard.
        """
        from .events import LeavesBattlefieldEvent

        planeswalkers_to_die = []

        for planeswalker in self.game.zones.battlefield.planeswalkers():
            loyalty = planeswalker.counters.get(CounterType.LOYALTY, 0)
            if loyalty <= 0:
                planeswalkers_to_die.append(planeswalker)

        for pw in planeswalkers_to_die:
            self.game.zones.battlefield.remove(pw)

            if not (hasattr(pw, 'is_token') and pw.is_token):
                self.game.zones.graveyards[pw.owner_id].add(pw)

            self.game.events.emit(LeavesBattlefieldEvent(
                object_id=pw.object_id,
                to_zone=Zone.GRAVEYARD
            ))

            result.actions_performed += 1
            result.other_changes.append(
                f"{pw.characteristics.name} (planeswalker) put into graveyard: "
                f"loyalty reduced to 0"
            )

    # =========================================================================
    # Legend Rule (CR 704.5j)
    # =========================================================================

    def _check_legend_rule(self, result: SBAResult) -> None:
        """
        CR 704.5j: If a player controls two or more legendary permanents
        with the same name, that player chooses one of them, and the rest
        are put into their owners' graveyards.

        Note: This is per-player, and the player chooses which to keep.
        """
        from .events import LeavesBattlefieldEvent

        for player_id in self.game.players:
            legends: Dict[str, List[Any]] = defaultdict(list)

            for permanent in self.game.zones.battlefield.legendaries(player_id):
                legends[permanent.characteristics.name].append(permanent)

            for name, copies in legends.items():
                if len(copies) > 1:
                    # Player chooses one to keep
                    player = self.game.get_player(player_id)
                    if player.ai:
                        to_keep = player.ai.choose_legend_to_keep(copies)
                    else:
                        to_keep = copies[0]  # Default: keep first

                    for copy in copies:
                        if copy != to_keep:
                            self.game.zones.battlefield.remove(copy)

                            if not (hasattr(copy, 'is_token') and copy.is_token):
                                self.game.zones.graveyards[copy.owner_id].add(copy)

                            self.game.events.emit(LeavesBattlefieldEvent(
                                object_id=copy.object_id,
                                to_zone=Zone.GRAVEYARD
                            ))

                            result.actions_performed += 1
                            result.other_changes.append(
                                f"{name} (legendary) put into graveyard: legend rule"
                            )

    # =========================================================================
    # Attachment SBAs (CR 704.5m-n)
    # =========================================================================

    def _check_aura_attached(self, result: SBAResult) -> None:
        """
        CR 704.5m: If an Aura is attached to an illegal object or player,
        or is not attached to an object or player, that Aura is put into
        its owner's graveyard.
        """
        from .events import LeavesBattlefieldEvent

        auras_to_die = []

        for permanent in self.game.zones.battlefield.enchantments():
            if "Aura" in permanent.characteristics.subtypes:
                if permanent.attached_to_id is None:
                    auras_to_die.append((permanent, "not attached to anything"))
                else:
                    # Check if attached permanent still exists and is valid
                    attached = self.game.zones.battlefield.get_by_id(permanent.attached_to_id)
                    if attached is None:
                        auras_to_die.append((permanent, "attached object left battlefield"))
                    elif hasattr(permanent, 'can_enchant') and not permanent.can_enchant(attached):
                        auras_to_die.append((permanent, "attached to illegal object"))

        for aura, reason in auras_to_die:
            self.game.zones.battlefield.remove(aura)

            if not (hasattr(aura, 'is_token') and aura.is_token):
                self.game.zones.graveyards[aura.owner_id].add(aura)

            self.game.events.emit(LeavesBattlefieldEvent(
                object_id=aura.object_id,
                to_zone=Zone.GRAVEYARD
            ))

            result.actions_performed += 1
            result.other_changes.append(
                f"{aura.characteristics.name} (Aura) put into graveyard: {reason}"
            )

    def _check_equipment_attached(self, result: SBAResult) -> None:
        """
        CR 704.5n: If an Equipment or Fortification is attached to an illegal
        permanent or isn't attached to a permanent, it becomes unattached and
        remains on the battlefield.

        Note: Unlike Auras, Equipment doesn't go to graveyard - it just
        becomes unattached.
        """
        for permanent in self.game.zones.battlefield.artifacts():
            if "Equipment" in permanent.characteristics.subtypes:
                if permanent.attached_to_id:
                    attached = self.game.zones.battlefield.get_by_id(permanent.attached_to_id)

                    # Equipment becomes unattached if:
                    # - Attached permanent no longer exists
                    # - Attached permanent is not a creature
                    if attached is None:
                        permanent.attached_to_id = None
                        result.actions_performed += 1
                        result.other_changes.append(
                            f"{permanent.characteristics.name} (Equipment) became unattached: "
                            f"equipped creature left battlefield"
                        )
                    elif not attached.characteristics.is_creature():
                        permanent.attached_to_id = None
                        result.actions_performed += 1
                        result.other_changes.append(
                            f"{permanent.characteristics.name} (Equipment) became unattached: "
                            f"attached to non-creature"
                        )

    # =========================================================================
    # Counter SBAs (CR 704.5q)
    # =========================================================================

    def _check_counter_annihilation(self, result: SBAResult) -> None:
        """
        CR 704.5q: If a permanent has both a +1/+1 counter and a -1/-1 counter
        on it, N +1/+1 and N -1/-1 counters are removed from it, where N is
        the smaller of the number of +1/+1 and -1/-1 counters on it.

        Note: This only applies to +1/+1 and -1/-1 counters, not other
        counter types that might affect power/toughness.
        """
        for permanent in self.game.zones.battlefield.permanents():
            plus_counters = permanent.counters.get(CounterType.PLUS_ONE_PLUS_ONE, 0)
            minus_counters = permanent.counters.get(CounterType.MINUS_ONE_MINUS_ONE, 0)

            if plus_counters > 0 and minus_counters > 0:
                # Remove the smaller number of each
                to_remove = min(plus_counters, minus_counters)

                permanent.counters[CounterType.PLUS_ONE_PLUS_ONE] -= to_remove
                permanent.counters[CounterType.MINUS_ONE_MINUS_ONE] -= to_remove

                # Clean up zero counters
                if permanent.counters[CounterType.PLUS_ONE_PLUS_ONE] == 0:
                    del permanent.counters[CounterType.PLUS_ONE_PLUS_ONE]
                if permanent.counters[CounterType.MINUS_ONE_MINUS_ONE] == 0:
                    del permanent.counters[CounterType.MINUS_ONE_MINUS_ONE]

                result.actions_performed += 1
                result.other_changes.append(
                    f"{permanent.characteristics.name}: {to_remove} +1/+1 and "
                    f"{to_remove} -1/-1 counters annihilated"
                )

    # =========================================================================
    # Token SBAs (CR 704.5d)
    # =========================================================================

    def _check_token_in_other_zones(self, result: SBAResult) -> None:
        """
        CR 704.5d: If a token is in a zone other than the battlefield, it
        ceases to exist.

        Note: This happens as a state-based action. The token is not put
        anywhere - it simply ceases to exist.
        """
        # Check zone dictionaries (hands, graveyards, libraries)
        for zone_dict in [self.game.zones.hands, self.game.zones.graveyards,
                          self.game.zones.libraries]:
            for zone in zone_dict.values():
                tokens_to_remove = []
                for obj in list(zone.objects):
                    if hasattr(obj, 'is_token') and obj.is_token:
                        tokens_to_remove.append(obj)

                for token in tokens_to_remove:
                    zone.remove(token)
                    result.actions_performed += 1
                    token_name = getattr(token.characteristics, 'name', 'Token')
                    result.other_changes.append(
                        f"Token '{token_name}' ceased to exist in zone"
                    )

        # Check single zones (exile, stack)
        for zone in [self.game.zones.exile, self.game.zones.stack]:
            tokens_to_remove = []
            for obj in list(zone.objects):
                if hasattr(obj, 'is_token') and obj.is_token:
                    tokens_to_remove.append(obj)

            for token in tokens_to_remove:
                zone.remove(token)
                result.actions_performed += 1
                token_name = getattr(token.characteristics, 'name', 'Token')
                result.other_changes.append(
                    f"Token '{token_name}' ceased to exist in zone"
                )


# =============================================================================
# Legacy function-based API for backwards compatibility
# =============================================================================

def check_state_based_actions(game: 'Game') -> bool:
    """
    Check and perform all state-based actions (CR 704).
    Returns True if any SBAs were performed.
    Must be called repeatedly until returns False.

    This is a legacy wrapper around StateBasedActionChecker for backwards
    compatibility.
    """
    checker = StateBasedActionChecker(game)
    result = checker.check_and_perform()
    return result.actions_performed > 0


def run_sba_loop(game: 'Game') -> SBAResult:
    """
    Run SBA checks until stable.

    This is a legacy wrapper around StateBasedActionChecker for backwards
    compatibility.
    """
    checker = StateBasedActionChecker(game)
    return checker.run_until_stable()
