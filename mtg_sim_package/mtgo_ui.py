"""
MTGO-Style UI Zone Display System
==================================

Provides ASCII art rendering of MTG game state in MTGO layout format.
Includes zone displays, card rendering, stack visualization, and combat area.

Usage:
------
    from mtgo_ui import MTGODisplay, GameStateDisplay

    # During a game:
    display = game.get_display(viewer_player_id=1)
    print(display.render_full_board())

    # Or use standalone:
    game_display = GameStateDisplay(game)
    print(game_display.format_for_console())
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from mtg_engine import Card, Player, Game, StackItem


# =============================================================================
# ZONE CONFIGURATION
# =============================================================================

@dataclass
class ZoneConfig:
    """Configuration for MTG zones with display properties."""

    ZONES = {
        'library': {
            'icon': '📚',
            'hidden': True,
            'countable': True,
            'description': 'Face-down deck'
        },
        'hand': {
            'icon': '🖐',
            'hidden_to_opponent': True,
            'description': 'Cards in hand'
        },
        'battlefield': {
            'icon': None,
            'rows': ['lands', 'creatures', 'other'],
            'description': 'Permanents in play'
        },
        'graveyard': {
            'icon': '⚰',
            'viewable': True,
            'ordered': True,
            'description': 'Discard pile'
        },
        'exile': {
            'icon': '✖',
            'viewable': True,
            'description': 'Removed from game'
        },
        'stack': {
            'icon': '📜',
            'ordered': True,
            'lifo': True,
            'description': 'Spells and abilities waiting to resolve'
        },
        'command': {
            'icon': '⚑',
            'commanders': True,
            'description': 'Command zone (for Commander format)'
        },
        'effects': {
            'icon': '⛨',
            'emblems': True,
            'description': 'Emblems and continuous effects'
        }
    }

    @classmethod
    def get_zone(cls, zone_name: str) -> dict:
        """Get configuration for a zone by name."""
        return cls.ZONES.get(zone_name, {})

    @classmethod
    def get_icon(cls, zone_name: str) -> str:
        """Get the display icon for a zone."""
        zone = cls.get_zone(zone_name)
        return zone.get('icon', '')


# =============================================================================
# CARD RENDERER
# =============================================================================

class CardRenderer:
    """Render individual cards with state indicators."""

    INDICATORS = {
        'tapped': '↷',
        'summoning_sick': '💤',
        'has_counters': '●',
        'attached': '⟷',
        'targeted': '🎯',
        'phased_out': '◌',
        'regenerate': '♻',
        'shield': '🛡',
    }

    # Compact type abbreviations
    TYPE_ABBREV = {
        'creature': 'CRE',
        'instant': 'INS',
        'sorcery': 'SOR',
        'enchantment': 'ENC',
        'artifact': 'ART',
        'planeswalker': 'PWK',
        'land': 'LND',
    }

    # Mana color symbols for display
    MANA_SYMBOLS = {
        'W': '○',  # White (sun)
        'U': '◇',  # Blue (water drop)
        'B': '◆',  # Black (skull)
        'R': '△',  # Red (fire)
        'G': '▲',  # Green (tree)
        'C': '◇',  # Colorless
    }

    def __init__(self, show_ids: bool = False):
        """
        Initialize card renderer.

        Args:
            show_ids: If True, display instance IDs for debugging
        """
        self.show_ids = show_ids

    def render(self, card: 'Card', width: int = 14, detailed: bool = False) -> List[str]:
        """
        Render a card as a list of lines.

        Args:
            card: The card to render
            width: Box width for the card
            detailed: If True, show full details; otherwise compact

        Returns:
            List of strings representing the card
        """
        lines = []
        inner_width = width - 2

        # Top border
        lines.append('┌' + '─' * inner_width + '┐')

        # Card name (truncated if necessary)
        name = card.name[:inner_width - 1]
        if card.is_tapped:
            name = self.INDICATORS['tapped'] + name[:inner_width - 2]
        lines.append('│' + name.ljust(inner_width) + '│')

        # Cost line (for non-lands)
        if card.card_type != 'land' and card.mana_cost:
            cost_str = self._format_mana_cost(card.mana_cost)[:inner_width]
            lines.append('│' + cost_str.ljust(inner_width) + '│')

        # Type line
        type_abbrev = self.TYPE_ABBREV.get(card.card_type, card.card_type[:3].upper())
        if card.subtype:
            type_line = f"{type_abbrev}-{card.subtype[:inner_width-4]}"
        else:
            type_line = type_abbrev
        lines.append('│' + type_line.ljust(inner_width) + '│')

        # State indicators line
        indicators = self._get_state_indicators(card)
        if indicators:
            lines.append('│' + indicators.ljust(inner_width) + '│')

        # Power/Toughness or Loyalty
        if card.card_type == 'creature' or card.is_crewed:
            pt = f"{card.eff_power()}/{card.eff_toughness()}"
            if card.damage_marked > 0:
                pt += f" (-{card.damage_marked})"
            lines.append('│' + pt.rjust(inner_width) + '│')
        elif card.card_type == 'planeswalker':
            loyalty = card.current_loyalty()
            lines.append('│' + f"[{loyalty}]".rjust(inner_width) + '│')
        elif card.crew > 0 and not card.is_crewed:
            # Uncrewed vehicle
            lines.append('│' + f"Crew {card.crew}".rjust(inner_width) + '│')

        # Counters (if any)
        counters = self._format_counters(card)
        if counters:
            lines.append('│' + counters[:inner_width].ljust(inner_width) + '│')

        # ID (if showing)
        if self.show_ids:
            id_str = f"#{card.instance_id}"
            lines.append('│' + id_str.rjust(inner_width) + '│')

        # Bottom border
        lines.append('└' + '─' * inner_width + '┘')

        return lines

    def render_compact(self, card: 'Card', max_width: int = 20) -> str:
        """
        Render card as a single-line compact representation.

        Args:
            card: The card to render
            max_width: Maximum width of output

        Returns:
            Compact string representation
        """
        parts = []

        # Tapped indicator
        if card.is_tapped:
            parts.append(self.INDICATORS['tapped'])

        # Name
        parts.append(card.name)

        # P/T for creatures
        if card.card_type == 'creature' or card.is_crewed:
            parts.append(f"({card.eff_power()}/{card.eff_toughness()})")
        elif card.card_type == 'planeswalker':
            parts.append(f"[{card.current_loyalty()}]")

        # Counters indicator
        if card.counters:
            parts.append(self.INDICATORS['has_counters'])

        result = ' '.join(parts)
        if len(result) > max_width:
            result = result[:max_width - 1] + '…'

        return result

    def render_hand_card(self, card: 'Card', hidden: bool = False) -> str:
        """
        Render a card in hand format.

        Args:
            card: The card to render
            hidden: If True, show as hidden card back

        Returns:
            String representation
        """
        if hidden:
            return '[???]'

        cost = self._format_mana_cost(card.mana_cost)
        return f"[{card.name}] {cost}"

    def _format_mana_cost(self, mana_cost) -> str:
        """Format a ManaCost as a displayable string."""
        parts = []

        if mana_cost.X > 0:
            parts.append('X' * mana_cost.X)
        if mana_cost.generic > 0:
            parts.append(str(mana_cost.generic))
        if mana_cost.W > 0:
            parts.append('W' * mana_cost.W)
        if mana_cost.U > 0:
            parts.append('U' * mana_cost.U)
        if mana_cost.B > 0:
            parts.append('B' * mana_cost.B)
        if mana_cost.R > 0:
            parts.append('R' * mana_cost.R)
        if mana_cost.G > 0:
            parts.append('G' * mana_cost.G)

        return ''.join(parts) if parts else '0'

    def _get_state_indicators(self, card: 'Card') -> str:
        """Get string of state indicators for a card."""
        indicators = []

        if card.summoning_sick and not card.has_keyword('haste'):
            indicators.append(self.INDICATORS['summoning_sick'])
        if card.phased_out:
            indicators.append(self.INDICATORS['phased_out'])
        if card.regenerate_shield > 0:
            indicators.append(self.INDICATORS['regenerate'])
        if card.shield_counters > 0:
            indicators.append(self.INDICATORS['shield'])
        if card.attached_to is not None:
            indicators.append(self.INDICATORS['attached'])

        return ''.join(indicators)

    def _format_counters(self, card: 'Card') -> str:
        """Format counter display for a card."""
        if not card.counters:
            return ''

        counter_strs = []
        for counter_type, count in card.counters.items():
            if counter_type == 'loyalty':
                continue  # Shown separately for planeswalkers
            if count > 0:
                counter_strs.append(f"{count}x{counter_type[:3]}")

        return ' '.join(counter_strs)


# =============================================================================
# RED ZONE (COMBAT AREA)
# =============================================================================

class RedZone:
    """Combat area display for attackers and blockers."""

    def __init__(self):
        self.attackers: List[Tuple['Card', Any]] = []  # (creature, defending_player_or_planeswalker)
        self.blockers: Dict[int, List['Card']] = {}    # attacker_id -> [blockers]
        self.damage_assignments: Dict[int, List[Tuple['Card', int]]] = {}  # attacker_id -> [(blocker, damage)]

    def clear(self):
        """Clear all combat data."""
        self.attackers = []
        self.blockers = {}
        self.damage_assignments = {}

    def add_attacker(self, creature: 'Card', target: Any = None):
        """
        Add an attacker to the red zone.

        Args:
            creature: The attacking creature
            target: The player or planeswalker being attacked
        """
        self.attackers.append((creature, target))
        self.blockers[creature.instance_id] = []

    def add_blocker(self, blocker: 'Card', attacker: 'Card'):
        """
        Assign a blocker to an attacker.

        Args:
            blocker: The blocking creature
            attacker: The creature being blocked
        """
        if attacker.instance_id in self.blockers:
            self.blockers[attacker.instance_id].append(blocker)

    def assign_damage(self, attacker: 'Card', blocker: 'Card', damage: int):
        """Assign combat damage from attacker to a specific blocker."""
        if attacker.instance_id not in self.damage_assignments:
            self.damage_assignments[attacker.instance_id] = []
        self.damage_assignments[attacker.instance_id].append((blocker, damage))

    def has_combat(self) -> bool:
        """Check if there's any combat happening."""
        return len(self.attackers) > 0

    def render(self, width: int = 60) -> str:
        """
        Render the combat zone as ASCII art.

        Args:
            width: Width of the display area

        Returns:
            Multi-line string showing combat
        """
        if not self.has_combat():
            return self._render_empty(width)

        lines = []
        renderer = CardRenderer()

        # Combat header
        lines.append('═' * 20 + ' RED ZONE ' + '═' * (width - 30))

        for attacker, target in self.attackers:
            # Attacker line
            attacker_str = renderer.render_compact(attacker)
            target_str = self._format_target(target)

            lines.append(f"  ⚔ {attacker_str} → {target_str}")

            # Blockers for this attacker
            blockers = self.blockers.get(attacker.instance_id, [])
            if blockers:
                blocker_strs = [renderer.render_compact(b) for b in blockers]
                lines.append(f"    ↳ Blocked by: {', '.join(blocker_strs)}")
            else:
                lines.append(f"    ↳ (Unblocked)")

        lines.append('═' * width)

        return '\n'.join(lines)

    def _render_empty(self, width: int) -> str:
        """Render empty combat zone."""
        line = '═' * 15 + ' RED ZONE ' + '═' * (width - 25)
        empty = ' ' * (width // 2 - 10) + '(No Combat)' + ' ' * (width // 2 - 11)
        return f"{line}\n{empty}\n{'═' * width}"

    def _format_target(self, target: Any) -> str:
        """Format attack target for display."""
        if target is None:
            return "Opponent"
        if hasattr(target, 'player_id'):
            return f"Player {target.player_id}"
        if hasattr(target, 'name'):
            return target.name  # Planeswalker
        return str(target)


# =============================================================================
# MTGO DISPLAY
# =============================================================================

class MTGODisplay:
    """
    Main MTGO-style display class for rendering full game state.

    Provides ASCII art representation matching MTGO's visual layout.
    """

    def __init__(self, game: 'Game', viewer_player: int = 1):
        """
        Initialize display for a game from a specific player's perspective.

        Args:
            game: The Game object to display
            viewer_player: Player ID (1 or 2) who is viewing
        """
        self.game = game
        self.viewer = viewer_player
        self.red_zone = RedZone()
        self.renderer = CardRenderer()
        self.width = 70

        # Timing info (can be updated externally)
        self.player_timers: Dict[int, int] = {1: 25 * 60, 2: 25 * 60}  # Seconds

        # Current phase/step info
        self.current_phase = "Main 1"
        self.priority_player = 1

    @property
    def viewer_player(self) -> 'Player':
        """Get the Player object for the viewer."""
        return self.game.p1 if self.viewer == 1 else self.game.p2

    @property
    def opponent_player(self) -> 'Player':
        """Get the Player object for the opponent."""
        return self.game.p2 if self.viewer == 1 else self.game.p1

    def render_full_board(self) -> str:
        """
        Render complete game board in MTGO style.

        Returns:
            Multi-line string of the full game state
        """
        lines = []
        w = self.width

        # Top border
        lines.append('┌' + '─' * (w - 2) + '┐')

        # Opponent area
        lines.extend(self._wrap_section(self._render_player_header(self.opponent_player, is_opponent=True)))
        lines.extend(self._wrap_section(self._render_zone_bar(self.opponent_player)))

        # Opponent battlefield
        lines.append('│' + ' ' * (w - 2) + '│')
        lines.extend(self._wrap_section(self._render_battlefield(self.opponent_player, inverted=True)))

        # Separator
        lines.append('├' + '─' * (w - 2) + '┤')

        # Red Zone (Combat area)
        if self.red_zone.has_combat():
            for line in self.red_zone.render(w - 4).split('\n'):
                lines.append('│ ' + line.ljust(w - 4) + ' │')
        else:
            lines.append('│' + '═' * 20 + ' RED ZONE ' + '═' * (w - 32) + '│')
            lines.append('│' + ' ' * (w - 2) + '│')

        # Separator
        lines.append('├' + '─' * (w - 2) + '┤')

        # Viewer battlefield
        lines.extend(self._wrap_section(self._render_battlefield(self.viewer_player, inverted=False)))
        lines.append('│' + ' ' * (w - 2) + '│')
        lines.extend(self._wrap_section(self._render_zone_bar(self.viewer_player)))
        lines.extend(self._wrap_section(self._render_player_header(self.viewer_player, is_opponent=False)))

        # Separator for hand
        lines.append('├' + '─' * (w - 2) + '┤')

        # Hand
        lines.extend(self._wrap_section(self._render_hand(self.viewer_player)))

        # Stack (if non-empty)
        if self.game.stack:
            lines.append('├' + '─' * (w - 2) + '┤')
            lines.extend(self._wrap_section(self.render_stack()))

        # Status bar
        lines.append('├' + '─' * (w - 2) + '┤')
        lines.extend(self._wrap_section(self.render_status_bar()))

        # Bottom border
        lines.append('└' + '─' * (w - 2) + '┘')

        return '\n'.join(lines)

    def render_zone(self, zone_name: str, player: 'Player') -> str:
        """
        Render a single zone's contents.

        Args:
            zone_name: Name of the zone ('hand', 'graveyard', 'exile', etc.)
            player: The player whose zone to render

        Returns:
            Multi-line string of zone contents
        """
        lines = []
        config = ZoneConfig.get_zone(zone_name)
        icon = config.get('icon', '')

        # Zone header
        header = f"{icon} {zone_name.upper()}" if icon else zone_name.upper()
        lines.append(f"=== {header} ===")

        # Get cards based on zone
        if zone_name == 'hand':
            cards = player.hand
            hidden = config.get('hidden_to_opponent', False) and player != self.viewer_player
        elif zone_name == 'library':
            count = len(player.library)
            lines.append(f"  [{count} cards]")
            return '\n'.join(lines)
        elif zone_name == 'graveyard':
            cards = player.graveyard
            hidden = False
        elif zone_name == 'exile':
            cards = player.exile
            hidden = False
        elif zone_name == 'battlefield':
            return self._render_battlefield(player)
        else:
            cards = []
            hidden = False

        # Render cards
        if not cards:
            lines.append("  (empty)")
        else:
            for card in cards:
                if hidden:
                    lines.append("  [???]")
                else:
                    lines.append(f"  {self.renderer.render_compact(card)}")

        return '\n'.join(lines)

    def render_card(self, card: 'Card', show_details: bool = False) -> str:
        """
        Render a single card with full details.

        Args:
            card: The card to render
            show_details: If True, show additional details

        Returns:
            Multi-line string of card
        """
        lines = self.renderer.render(card, detailed=show_details)
        return '\n'.join(lines)

    def render_stack(self) -> str:
        """
        Render the spell stack with resolution order.

        Returns:
            String representation of the stack
        """
        if not self.game.stack:
            return "STACK: (empty)"

        items = []
        for stack_item in reversed(self.game.stack):  # Show top first
            card = stack_item.card
            item_str = f"[{card.name}"

            # Add modifiers
            modifiers = []
            if stack_item.x_value > 0:
                modifiers.append(f"X={stack_item.x_value}")
            if stack_item.was_kicked:
                modifiers.append("kicked")
            if stack_item.cast_with_flashback:
                modifiers.append("flashback")
            if stack_item.chosen_modes:
                modifiers.append(f"modes:{','.join(stack_item.chosen_modes)}")

            if modifiers:
                item_str += f" ({', '.join(modifiers)})"

            # Add target
            if stack_item.target is not None:
                if hasattr(stack_item.target, 'name'):
                    item_str += f" -> {stack_item.target.name}"
                elif hasattr(stack_item.target, 'player_id'):
                    item_str += f" -> P{stack_item.target.player_id}"

            item_str += "]"
            items.append(item_str)

        if len(items) == 1:
            return f"STACK: {items[0]}"

        return "STACK: " + " -> ".join(items)

    def render_status_bar(self) -> str:
        """
        Render the status bar with phase, priority, and shortcuts.

        Returns:
            Status bar string
        """
        # Phase indicator
        phase_str = f"[Phase: {self.current_phase}]"

        # Priority
        priority_str = "[Priority: YOU]" if self.priority_player == self.viewer else "[Priority: OPP]"

        # Timer
        seconds = self.player_timers.get(self.viewer, 0)
        minutes = seconds // 60
        secs = seconds % 60
        timer_str = f"[Timer: {minutes:02d}:{secs:02d}]"

        # Shortcuts
        shortcuts = "[F4] [F6] [F8]"

        return f"{phase_str} {priority_str}  {timer_str} {shortcuts}"

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _wrap_section(self, content: str) -> List[str]:
        """Wrap content lines with box borders."""
        lines = []
        for line in content.split('\n'):
            padded = line[:self.width - 4].ljust(self.width - 4)
            lines.append('│ ' + padded + ' │')
        return lines

    def _render_player_header(self, player: 'Player', is_opponent: bool) -> str:
        """Render player info header."""
        life = player.life
        poison = player.poison_counters

        label = "OPPONENT" if is_opponent else "YOU"
        life_str = f"Life: {life}"
        if poison > 0:
            life_str += f" | Poison: {poison}"

        name = player.deck_name[:20] if player.deck_name else f"Player {player.player_id}"

        return f"{label} [{name}] - {life_str}"

    def _render_zone_bar(self, player: 'Player') -> str:
        """Render the zone bar (exile, GY, library count, etc.)"""
        exile_count = len(player.exile)
        gy_count = len(player.graveyard)
        lib_count = len(player.library)

        parts = [
            f"[Exile {exile_count}]",
            f"[GY ⚰ {gy_count}]",
            f"[Library {lib_count}]",
        ]

        return '  '.join(parts)

    def _render_battlefield(self, player: 'Player', inverted: bool = False) -> str:
        """
        Render player's battlefield organized by card type.

        Args:
            player: The player whose battlefield to render
            inverted: If True, render with lands at bottom (opponent view)

        Returns:
            Multi-line string of battlefield
        """
        # Categorize permanents
        lands = []
        creatures = []
        other = []

        for card in player.battlefield:
            if card.phased_out:
                continue
            if card.card_type == 'land':
                lands.append(card)
            elif card.card_type == 'creature' or card.is_crewed:
                creatures.append(card)
            else:
                other.append(card)

        lines = []

        # Row rendering order depends on perspective
        if inverted:
            rows = [
                ('Lands', lands),
                ('Creatures', creatures),
                ('Other', other),
            ]
        else:
            rows = [
                ('Other', other),
                ('Creatures', creatures),
                ('Lands', lands),
            ]

        for row_name, cards in rows:
            if cards:
                card_strs = [self.renderer.render_compact(c, max_width=15) for c in cards]
                row_content = '  '.join(card_strs)
                if len(row_content) > self.width - 10:
                    # Truncate and add count
                    row_content = row_content[:self.width - 20] + f'... ({len(cards)})'
                lines.append(f"[{row_name}] {row_content}")
            else:
                lines.append(f"[{row_name}]")

        return '\n'.join(lines) if lines else "(Empty battlefield)"

    def _render_hand(self, player: 'Player') -> str:
        """Render player's hand."""
        if not player.hand:
            return "Hand: (empty)"

        cards = []
        for card in player.hand:
            cost = self.renderer._format_mana_cost(card.mana_cost)
            cards.append(f"[{card.name}|{cost}]")

        hand_str = ' '.join(cards)

        # Wrap if too long
        if len(hand_str) > self.width - 10:
            # Show count and abbreviated
            hand_str = f"Hand ({len(player.hand)} cards): "
            for i, card in enumerate(player.hand[:5]):
                hand_str += f"[{card.name[:8]}] "
            if len(player.hand) > 5:
                hand_str += f"...+{len(player.hand) - 5}"
        else:
            hand_str = f"Hand: {hand_str}"

        return hand_str

    def set_combat(self, attackers: List[Tuple['Card', Any]], blockers: Dict[int, List['Card']] = None):
        """
        Set combat state for display.

        Args:
            attackers: List of (attacker_card, target) tuples
            blockers: Dict mapping attacker instance_id to list of blockers
        """
        self.red_zone.clear()
        for attacker, target in attackers:
            self.red_zone.add_attacker(attacker, target)

        if blockers:
            for attacker_id, blocker_list in blockers.items():
                # Find attacker card
                for attacker, _ in self.red_zone.attackers:
                    if attacker.instance_id == attacker_id:
                        for blocker in blocker_list:
                            self.red_zone.add_blocker(blocker, attacker)
                        break

    def update_phase(self, phase: str, priority_player: int):
        """Update the current phase display."""
        self.current_phase = phase
        self.priority_player = priority_player

    def update_timer(self, player_id: int, seconds: int):
        """Update a player's timer."""
        self.player_timers[player_id] = seconds


# =============================================================================
# GAME STATE DISPLAY
# =============================================================================

class GameStateDisplay:
    """
    High-level game state formatter for console output.

    Provides various display formats for different use cases.
    """

    def __init__(self, game: 'Game'):
        """
        Initialize with a game instance.

        Args:
            game: The Game object to display
        """
        self.game = game
        self.renderer = CardRenderer()

    def format_for_console(self, viewer: int = 1, verbose: bool = False) -> str:
        """
        Format complete game state for console output.

        Args:
            viewer: Player ID viewing the game
            verbose: If True, include additional details

        Returns:
            Formatted string for console display
        """
        display = MTGODisplay(self.game, viewer)
        return display.render_full_board()

    def format_compact(self) -> str:
        """
        Format a compact summary of game state.

        Returns:
            Brief summary string
        """
        p1 = self.game.p1
        p2 = self.game.p2

        lines = [
            f"Turn {self.game.turn} | Active: P{self.game.active_id}",
            f"P1 ({p1.deck_name}): {p1.life} life, {len(p1.hand)} cards, {len(p1.library)} library",
            f"  Battlefield: {len([c for c in p1.battlefield if not c.phased_out])} permanents",
            f"P2 ({p2.deck_name}): {p2.life} life, {len(p2.hand)} cards, {len(p2.library)} library",
            f"  Battlefield: {len([c for c in p2.battlefield if not c.phased_out])} permanents",
        ]

        if self.game.stack:
            lines.append(f"Stack: {len(self.game.stack)} items")

        return '\n'.join(lines)

    def format_battlefield_only(self, player: 'Player' = None) -> str:
        """
        Format just the battlefield state.

        Args:
            player: Optional - specific player's battlefield (default: both)

        Returns:
            Battlefield state string
        """
        lines = []

        players = [player] if player else [self.game.p1, self.game.p2]

        for p in players:
            lines.append(f"=== Player {p.player_id} Battlefield ===")

            # Categorize
            for card in p.battlefield:
                if card.phased_out:
                    status = "(phased out)"
                elif card.is_tapped:
                    status = "(tapped)"
                else:
                    status = ""

                card_str = self.renderer.render_compact(card)
                lines.append(f"  {card_str} {status}")

            if not p.battlefield:
                lines.append("  (empty)")

            lines.append("")

        return '\n'.join(lines)

    def format_stack(self) -> str:
        """
        Format the stack contents with full details.

        Returns:
            Stack state string
        """
        if not self.game.stack:
            return "Stack is empty"

        lines = ["=== THE STACK (top to bottom) ==="]

        for i, item in enumerate(reversed(self.game.stack)):
            position = len(self.game.stack) - i
            lines.append(f"\n[{position}] {item.card.name}")
            lines.append(f"    Controller: P{item.controller}")
            lines.append(f"    Type: {item.card.card_type}")

            if item.target:
                if hasattr(item.target, 'name'):
                    lines.append(f"    Target: {item.target.name}")
                elif hasattr(item.target, 'player_id'):
                    lines.append(f"    Target: Player {item.target.player_id}")

            if item.x_value > 0:
                lines.append(f"    X = {item.x_value}")

            if item.chosen_modes:
                lines.append(f"    Modes: {', '.join(item.chosen_modes)}")

            if item.was_kicked:
                lines.append(f"    (Kicked)")

        return '\n'.join(lines)

    def format_graveyard(self, player: 'Player') -> str:
        """
        Format a player's graveyard contents.

        Args:
            player: The player whose graveyard to display

        Returns:
            Graveyard contents string
        """
        lines = [f"=== Player {player.player_id} Graveyard ({len(player.graveyard)} cards) ==="]

        if not player.graveyard:
            lines.append("  (empty)")
        else:
            # Show in order (most recent first for MTGO style)
            for i, card in enumerate(reversed(player.graveyard)):
                type_abbrev = CardRenderer.TYPE_ABBREV.get(card.card_type, card.card_type[:3])
                cost = self.renderer._format_mana_cost(card.mana_cost)
                lines.append(f"  {i+1}. {card.name} [{type_abbrev}] {cost}")

        return '\n'.join(lines)

    def format_exile(self, player: 'Player') -> str:
        """
        Format a player's exile zone.

        Args:
            player: The player whose exile to display

        Returns:
            Exile zone contents string
        """
        lines = [f"=== Player {player.player_id} Exile ({len(player.exile)} cards) ==="]

        if not player.exile:
            lines.append("  (empty)")
        else:
            for card in player.exile:
                type_abbrev = CardRenderer.TYPE_ABBREV.get(card.card_type, card.card_type[:3])

                # Special indicators for exile
                extra = ""
                if card.on_adventure:
                    extra = " (on adventure)"

                lines.append(f"  - {card.name} [{type_abbrev}]{extra}")

        return '\n'.join(lines)

    def format_hand(self, player: 'Player', hidden: bool = False) -> str:
        """
        Format a player's hand.

        Args:
            player: The player whose hand to display
            hidden: If True, show as hidden cards

        Returns:
            Hand contents string
        """
        lines = [f"=== Player {player.player_id} Hand ({len(player.hand)} cards) ==="]

        if not player.hand:
            lines.append("  (empty)")
        elif hidden:
            lines.append(f"  [{len(player.hand)} hidden cards]")
        else:
            for card in player.hand:
                cost = self.renderer._format_mana_cost(card.mana_cost)
                castable = player.can_cast(card)
                status = " [CASTABLE]" if castable else ""
                lines.append(f"  - {card.name} ({cost}){status}")

        return '\n'.join(lines)


# =============================================================================
# GAME CLASS INTEGRATION
# =============================================================================

def add_display_to_game(game_class):
    """
    Add display method to Game class via monkey patching.

    Usage:
        from mtgo_ui import add_display_to_game
        from mtg_engine import Game
        add_display_to_game(Game)

        # Then in game:
        display = game.get_display()
        print(display.render_full_board())
    """
    def get_display(self, viewer_player: int = 1) -> MTGODisplay:
        """
        Get an MTGODisplay instance for this game.

        Args:
            viewer_player: Player ID (1 or 2) viewing the game

        Returns:
            MTGODisplay configured for this game
        """
        return MTGODisplay(self, viewer_player)

    def get_game_state_display(self) -> GameStateDisplay:
        """
        Get a GameStateDisplay instance for this game.

        Returns:
            GameStateDisplay configured for this game
        """
        return GameStateDisplay(self)

    game_class.get_display = get_display
    game_class.get_game_state_display = get_game_state_display


# =============================================================================
# PHASE NAMES
# =============================================================================

PHASE_NAMES = {
    'beginning': {
        'untap': 'Untap',
        'upkeep': 'Upkeep',
        'draw': 'Draw',
    },
    'precombat_main': 'Main 1',
    'combat': {
        'beginning': 'Begin Combat',
        'declare_attackers': 'Declare Attackers',
        'declare_blockers': 'Declare Blockers',
        'first_strike_damage': 'First Strike Damage',
        'damage': 'Combat Damage',
        'end': 'End Combat',
    },
    'postcombat_main': 'Main 2',
    'ending': {
        'end': 'End Step',
        'cleanup': 'Cleanup',
    },
}


def get_phase_name(phase: str, step: str = None) -> str:
    """
    Get human-readable phase name.

    Args:
        phase: Main phase name
        step: Optional step within phase

    Returns:
        Display name for the phase/step
    """
    phase_data = PHASE_NAMES.get(phase)
    if phase_data is None:
        return phase.replace('_', ' ').title()

    if isinstance(phase_data, str):
        return phase_data

    if step and step in phase_data:
        return phase_data[step]

    return phase.replace('_', ' ').title()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def print_game_state(game: 'Game', viewer: int = 1):
    """
    Print the current game state to console.

    Args:
        game: The game to display
        viewer: Player ID viewing the game
    """
    display = GameStateDisplay(game)
    print(display.format_for_console(viewer))


def print_stack(game: 'Game'):
    """Print just the stack contents."""
    display = GameStateDisplay(game)
    print(display.format_stack())


def print_battlefield(game: 'Game'):
    """Print just the battlefield."""
    display = GameStateDisplay(game)
    print(display.format_battlefield_only())


# Export main classes
__all__ = [
    'ZoneConfig',
    'CardRenderer',
    'RedZone',
    'MTGODisplay',
    'GameStateDisplay',
    'add_display_to_game',
    'get_phase_name',
    'print_game_state',
    'print_stack',
    'print_battlefield',
    'PHASE_NAMES',
]
