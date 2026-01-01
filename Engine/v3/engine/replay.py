"""MTG Engine V3 - Replay System

This module provides replay recording and export functionality for the MTG game engine.
It captures game state snapshots at key moments and exports them as JSON for the visual viewer.

Usage:
    from engine.replay import ReplayRecorder

    recorder = ReplayRecorder()
    game = Game(player_ids=[1, 2])
    game.replay_recorder = recorder  # Attach to game

    # ... play game ...

    replay_json = recorder.export_json()
    recorder.save_to_file("game_replay.json")
"""

import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum


@dataclass
class CardSnapshot:
    """Snapshot of a card's state."""
    id: str
    name: str
    tapped: bool = False
    face_down: bool = False
    counters: Dict[str, int] = field(default_factory=dict)
    power: Optional[int] = None
    toughness: Optional[int] = None
    attached_to: Optional[str] = None
    attachments: List[str] = field(default_factory=list)
    summoning_sick: bool = False
    attacking: bool = False
    blocking: Optional[str] = None
    mana_cost: str = ""
    card_types: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class PlayerSnapshot:
    """Snapshot of a player's state."""
    life: int
    hand: List[CardSnapshot]
    battlefield: Dict[str, List[CardSnapshot]]  # lands, creatures, artifacts, etc.
    library: int  # Just the count
    graveyard: List[CardSnapshot]
    exile: List[CardSnapshot]
    mana_pool: Dict[str, int] = field(default_factory=dict)
    poison_counters: int = 0


@dataclass
class ActionSnapshot:
    """Snapshot of a game action."""
    type: str  # play_land, cast_spell, attack, block, activate_ability, etc.
    player: int
    card: Optional[str] = None
    target: Optional[str] = None
    targets: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_description(self) -> str:
        """Convert action to human-readable description."""
        p = f"P{self.player}"

        if self.type == "play_land":
            return f"{p} plays {self.card}"
        elif self.type == "cast_spell":
            if self.targets:
                return f"{p} casts {self.card} targeting {', '.join(self.targets)}"
            return f"{p} casts {self.card}"
        elif self.type == "attack":
            return f"{p} attacks with {self.card}"
        elif self.type == "block":
            return f"{p} blocks {self.details.get('attacker', '?')} with {self.card}"
        elif self.type == "activate_ability":
            return f"{p} activates {self.card}'s ability"
        elif self.type == "pass_priority":
            return f"{p} passes"
        elif self.type == "end_turn":
            return f"End of turn {self.details.get('turn', '?')}"
        elif self.type == "phase_change":
            return f"Phase: {self.details.get('phase', '?')}"
        elif self.type == "draw_card":
            return f"{p} draws a card"
        elif self.type == "discard":
            return f"{p} discards {self.card}"
        elif self.type == "damage":
            amt = self.details.get('amount', '?')
            return f"{self.card} deals {amt} damage to {self.target}"
        elif self.type == "creature_dies":
            return f"{self.card} dies"
        elif self.type == "game_start":
            return "Game begins"
        elif self.type == "game_end":
            winner = self.details.get('winner', '?')
            return f"Game over - Player {winner} wins!"
        else:
            return f"{p}: {self.type}"


@dataclass
class FrameSnapshot:
    """A single frame in the replay."""
    frame_id: int
    turn: int
    phase: str
    active_player: int
    action: Optional[ActionSnapshot]
    players: Dict[int, PlayerSnapshot]
    stack: List[CardSnapshot] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class ReplayMetadata:
    """Metadata about the replay."""
    date: str
    engine_version: str = "V3"
    deck1_name: str = "Player 1"
    deck2_name: str = "Player 2"
    winner: Optional[int] = None
    turns_played: int = 0
    win_reason: str = ""


class ReplayRecorder:
    """
    Records game state snapshots for replay functionality.

    Attach to a Game instance to automatically capture frames during gameplay.
    Export to JSON for use with the visual viewer.
    """

    def __init__(self):
        self.frames: List[FrameSnapshot] = []
        self.metadata = ReplayMetadata(date=datetime.now().isoformat())
        self._frame_counter = 0
        self._game = None

    def attach_to_game(self, game: 'Game'):
        """Attach recorder to a game instance."""
        self._game = game
        game.replay_recorder = self

    def record_frame(
        self,
        action: Optional[ActionSnapshot] = None,
        force: bool = False
    ):
        """
        Record current game state as a frame.

        Args:
            action: The action that led to this state
            force: Force recording even if state hasn't changed
        """
        if self._game is None:
            return

        game = self._game

        # Build player snapshots
        players = {}
        for pid, player in game.players.items():
            players[pid] = self._snapshot_player(player, pid)

        # Get current phase name
        phase_name = "unknown"
        if hasattr(game, 'current_phase') and game.current_phase:
            phase_name = str(game.current_phase.name).lower() if hasattr(game.current_phase, 'name') else str(game.current_phase)

        # Build stack snapshot
        stack = []
        if hasattr(game, 'zones') and hasattr(game.zones, 'stack'):
            for obj in game.zones.stack.objects:
                stack.append(self._snapshot_card(obj))

        frame = FrameSnapshot(
            frame_id=self._frame_counter,
            turn=getattr(game, 'turn_number', 1),
            phase=phase_name,
            active_player=getattr(game, 'active_player_id', 1),
            action=action,
            players=players,
            stack=stack,
            timestamp=datetime.now().isoformat()
        )

        self.frames.append(frame)
        self._frame_counter += 1

    def _snapshot_player(self, player, player_id: int) -> PlayerSnapshot:
        """Create a snapshot of a player's current state."""
        game = self._game

        # Hand
        hand_cards = []
        if hasattr(game, 'zones') and hasattr(game.zones, 'hands'):
            hand_zone = game.zones.hands.get(player_id)
            if hand_zone:
                for card in hand_zone.objects:
                    hand_cards.append(self._snapshot_card(card))

        # Battlefield - categorized
        battlefield = {
            "lands": [],
            "creatures": [],
            "artifacts": [],
            "enchantments": [],
            "planeswalkers": [],
            "other": []
        }

        if hasattr(game, 'zones') and hasattr(game.zones, 'battlefield'):
            for perm in game.zones.battlefield.objects:
                if getattr(perm, 'controller', None) == player or \
                   (hasattr(perm, 'controller') and hasattr(perm.controller, 'player_id') and perm.controller.player_id == player_id):
                    card_snap = self._snapshot_card(perm)

                    # Categorize by type
                    types = card_snap.card_types
                    if "land" in [t.lower() for t in types]:
                        battlefield["lands"].append(card_snap)
                    elif "creature" in [t.lower() for t in types]:
                        battlefield["creatures"].append(card_snap)
                    elif "artifact" in [t.lower() for t in types]:
                        battlefield["artifacts"].append(card_snap)
                    elif "enchantment" in [t.lower() for t in types]:
                        battlefield["enchantments"].append(card_snap)
                    elif "planeswalker" in [t.lower() for t in types]:
                        battlefield["planeswalkers"].append(card_snap)
                    else:
                        battlefield["other"].append(card_snap)

        # Library count
        library_count = 0
        if hasattr(game, 'zones') and hasattr(game.zones, 'libraries'):
            lib = game.zones.libraries.get(player_id)
            if lib:
                library_count = len(lib.objects)

        # Graveyard
        graveyard = []
        if hasattr(game, 'zones') and hasattr(game.zones, 'graveyards'):
            gy = game.zones.graveyards.get(player_id)
            if gy:
                for card in gy.objects:
                    graveyard.append(self._snapshot_card(card))

        # Exile
        exile = []
        if hasattr(game, 'zones') and hasattr(game.zones, 'exile'):
            for card in game.zones.exile.objects:
                if getattr(card, 'owner', None) == player or \
                   (hasattr(card, 'owner') and hasattr(card.owner, 'player_id') and card.owner.player_id == player_id):
                    exile.append(self._snapshot_card(card))

        # Mana pool
        mana_pool = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0}
        if hasattr(player, 'mana_pool') and hasattr(player.mana_pool, 'mana'):
            for mana_obj in player.mana_pool.mana:
                if hasattr(mana_obj, 'color'):
                    color_str = str(mana_obj.color.name)[0] if hasattr(mana_obj.color, 'name') else str(mana_obj.color)[0]
                    if color_str in mana_pool:
                        mana_pool[color_str] += 1

        return PlayerSnapshot(
            life=getattr(player, 'life', 20),
            hand=hand_cards,
            battlefield=battlefield,
            library=library_count,
            graveyard=graveyard,
            exile=exile,
            mana_pool=mana_pool,
            poison_counters=getattr(player, 'poison_counters', 0)
        )

    def _snapshot_card(self, card) -> CardSnapshot:
        """Create a snapshot of a card/permanent."""
        # Get card name
        name = "Unknown"
        if hasattr(card, 'characteristics') and card.characteristics:
            name = getattr(card.characteristics, 'name', 'Unknown')
        elif hasattr(card, 'name'):
            name = card.name

        # Get card ID
        card_id = str(getattr(card, 'object_id', id(card)))

        # Get tapped state
        tapped = getattr(card, 'is_tapped', False)

        # Get P/T
        power = None
        toughness = None
        if hasattr(card, 'characteristics') and card.characteristics:
            power = getattr(card.characteristics, 'power', None)
            toughness = getattr(card.characteristics, 'toughness', None)

        # Get mana cost - convert to string if it's a ManaCost object
        mana_cost = ""
        if hasattr(card, 'characteristics') and card.characteristics:
            mc = getattr(card.characteristics, 'mana_cost', None)
            if mc:
                mana_cost = str(mc) if not isinstance(mc, str) else mc

        # Get card types
        card_types = []
        if hasattr(card, 'characteristics') and card.characteristics:
            types = getattr(card.characteristics, 'types', []) or []
            card_types = [str(t.name) if hasattr(t, 'name') else str(t) for t in types]

        # Get keywords
        keywords = []
        if hasattr(card, 'characteristics') and card.characteristics:
            kws = getattr(card.characteristics, 'keywords', []) or []
            keywords = [str(k) for k in kws]

        # Get counters
        counters = {}
        if hasattr(card, 'counters'):
            for counter_type, count in (card.counters or {}).items():
                counters[str(counter_type)] = count

        # Get combat state
        attacking = getattr(card, 'attacking', False)
        blocking = getattr(card, 'blocking', None)
        if blocking:
            blocking = str(getattr(blocking, 'object_id', blocking))

        # Summoning sickness
        summoning_sick = getattr(card, 'summoning_sick', False)

        return CardSnapshot(
            id=card_id,
            name=name,
            tapped=tapped,
            power=power,
            toughness=toughness,
            mana_cost=mana_cost,
            card_types=card_types,
            keywords=keywords,
            counters=counters,
            attacking=attacking,
            blocking=blocking,
            summoning_sick=summoning_sick
        )

    def record_action(self, action_type: str, player_id: int, **kwargs):
        """
        Record an action and capture the resulting game state.

        Args:
            action_type: Type of action (play_land, cast_spell, attack, etc.)
            player_id: Player performing the action
            **kwargs: Additional action details
        """
        action = ActionSnapshot(
            type=action_type,
            player=player_id,
            card=kwargs.get('card'),
            target=kwargs.get('target'),
            targets=kwargs.get('targets', []),
            details=kwargs.get('details', {})
        )
        self.record_frame(action=action)

    def record_game_start(self, deck1_name: str = None, deck2_name: str = None):
        """Record the start of a game."""
        if deck1_name:
            self.metadata.deck1_name = deck1_name
        if deck2_name:
            self.metadata.deck2_name = deck2_name

        self.record_action("game_start", 0, details={"message": "Game begins"})

    def record_game_end(self, winner_id: int, reason: str = ""):
        """Record the end of a game."""
        self.metadata.winner = winner_id
        self.metadata.win_reason = reason
        if self.frames:
            self.metadata.turns_played = self.frames[-1].turn

        self.record_action("game_end", winner_id, details={
            "winner": winner_id,
            "reason": reason
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert replay to dictionary format."""
        frames_data = []
        for frame in self.frames:
            frame_dict = {
                "frame_id": frame.frame_id,
                "turn": frame.turn,
                "phase": frame.phase,
                "activePlayer": frame.active_player,
                "timestamp": frame.timestamp,
                "players": {}
            }

            # Add action if present
            if frame.action:
                frame_dict["action"] = {
                    "type": frame.action.type,
                    "player": frame.action.player,
                    "description": frame.action.to_description()
                }
                if frame.action.card:
                    frame_dict["action"]["card"] = frame.action.card
                if frame.action.targets:
                    frame_dict["action"]["targets"] = frame.action.targets
                if frame.action.details:
                    frame_dict["action"]["details"] = frame.action.details

            # Add player states
            for pid, pstate in frame.players.items():
                frame_dict["players"][str(pid)] = {
                    "life": pstate.life,
                    "hand": [self._card_to_dict(c) for c in pstate.hand],
                    "battlefield": {
                        zone: [self._card_to_dict(c) for c in cards]
                        for zone, cards in pstate.battlefield.items()
                    },
                    "library": pstate.library,
                    "graveyard": [self._card_to_dict(c) for c in pstate.graveyard],
                    "exile": [self._card_to_dict(c) for c in pstate.exile],
                    "manaPool": pstate.mana_pool,
                    "poisonCounters": pstate.poison_counters
                }

            # Add stack
            if frame.stack:
                frame_dict["stack"] = [self._card_to_dict(c) for c in frame.stack]

            frames_data.append(frame_dict)

        return {
            "metadata": {
                "date": self.metadata.date,
                "engineVersion": self.metadata.engine_version,
                "deck1": self.metadata.deck1_name,
                "deck2": self.metadata.deck2_name,
                "winner": self.metadata.winner,
                "turnsPlayed": self.metadata.turns_played,
                "winReason": self.metadata.win_reason
            },
            "frames": frames_data
        }

    def _card_to_dict(self, card: CardSnapshot) -> Dict[str, Any]:
        """Convert CardSnapshot to dict for JSON."""
        d = {
            "id": card.id,
            "name": card.name
        }

        if card.tapped:
            d["tapped"] = True
        if card.face_down:
            d["faceDown"] = True
        if card.power is not None:
            d["power"] = card.power
        if card.toughness is not None:
            d["toughness"] = card.toughness
        if card.mana_cost:
            d["manaCost"] = card.mana_cost
        if card.card_types:
            d["types"] = card.card_types
        if card.keywords:
            d["keywords"] = card.keywords
        if card.counters:
            d["counters"] = card.counters
        if card.attacking:
            d["attacking"] = True
        if card.blocking:
            d["blocking"] = card.blocking
        if card.summoning_sick:
            d["summoningSick"] = True
        if card.attachments:
            d["attachments"] = card.attachments
        if card.attached_to:
            d["attachedTo"] = card.attached_to

        return d

    def export_json(self, pretty: bool = True) -> str:
        """
        Export replay as JSON string.

        Args:
            pretty: Whether to format with indentation

        Returns:
            JSON string
        """
        if pretty:
            return json.dumps(self.to_dict(), indent=2)
        return json.dumps(self.to_dict())

    def save_to_file(self, filepath: str, pretty: bool = True):
        """
        Save replay to a JSON file.

        Args:
            filepath: Path to output file
            pretty: Whether to format with indentation
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2 if pretty else None)

    def clear(self):
        """Clear all recorded frames."""
        self.frames = []
        self._frame_counter = 0
        self.metadata = ReplayMetadata(date=datetime.now().isoformat())


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

def create_replay_game(game_class, *args, **kwargs):
    """
    Create a game with replay recording enabled.

    Args:
        game_class: The Game class to instantiate
        *args, **kwargs: Arguments for Game constructor

    Returns:
        Tuple of (game, recorder)
    """
    recorder = ReplayRecorder()
    game = game_class(*args, **kwargs)
    recorder.attach_to_game(game)
    return game, recorder


__all__ = [
    'CardSnapshot',
    'PlayerSnapshot',
    'ActionSnapshot',
    'FrameSnapshot',
    'ReplayMetadata',
    'ReplayRecorder',
    'create_replay_game'
]
