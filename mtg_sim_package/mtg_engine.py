"""
MTG Universal Simulation Engine v2
===================================

Parses standard MTGO .txt decklists and simulates matches.

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
from typing import List, Dict, Optional, Tuple, Any
from card_database import get_card_data, CARD_DATABASE

ENGINE_VERSION = "2.1"


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

@dataclass
class Card:
    name: str
    mana_cost: int
    card_type: str
    power: int = 0
    toughness: int = 0
    keywords: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)
    loyalty: int = 0
    
    instance_id: int = 0
    is_tapped: bool = False
    damage_marked: int = 0
    summoning_sick: bool = True
    counters: Dict[str, int] = field(default_factory=dict)
    controller: int = 0
    
    def copy(self) -> 'Card':
        return Card(
            name=self.name, mana_cost=self.mana_cost, card_type=self.card_type,
            power=self.power, toughness=self.toughness,
            keywords=self.keywords.copy(), abilities=self.abilities.copy(),
            loyalty=self.loyalty, instance_id=self.instance_id,
            is_tapped=self.is_tapped, damage_marked=self.damage_marked,
            summoning_sick=self.summoning_sick, counters=self.counters.copy(),
            controller=self.controller
        )
    
    def eff_power(self) -> int:
        return self.power + self.counters.get("+1/+1", 0)
    
    def eff_toughness(self) -> int:
        return self.toughness + self.counters.get("+1/+1", 0)


@dataclass  
class Player:
    player_id: int
    deck_name: str
    archetype: str = "midrange"
    life: int = 20
    library: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    battlefield: List[Card] = field(default_factory=list)
    graveyard: List[Card] = field(default_factory=list)
    land_played: bool = False
    spells_cast: int = 0
    
    def untapped_lands(self) -> int:
        return sum(1 for c in self.battlefield if c.card_type == "land" and not c.is_tapped)
    
    def creatures(self) -> List[Card]:
        return [c for c in self.battlefield if c.card_type == "creature"]
    
    def attackers_available(self) -> List[Card]:
        return [c for c in self.creatures() 
                if not c.is_tapped and (not c.summoning_sick or "haste" in c.keywords)]
    
    def total_power(self) -> int:
        return sum(c.eff_power() for c in self.creatures())


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

def parse_decklist(decklist_txt: str, deck_name: str = None) -> Tuple[List[Card], str, str]:
    """
    Parse an MTGO-format decklist.
    
    Format:
        4 Card Name
        2 Another Card
        // Comments ignored
        Sideboard (section ignored)
    """
    cards = []
    unknown_cards = []
    
    lines = decklist_txt.strip().split('\n')
    in_sideboard = False
    detected_name = deck_name
    
    creature_count = 0
    spell_count = 0
    creature_costs = []
    
    for line in lines:
        line = line.strip()
        
        if not line or line.startswith('//') or line.startswith('#'):
            continue
        
        # Deck name detection
        if not detected_name and ('_AI' in line or '_ai' in line):
            detected_name = line.replace('_AI', '').replace('_ai', '').replace('_', ' ')
            continue
        
        if line.lower().startswith('sideboard'):
            in_sideboard = True
            continue
        
        if in_sideboard:
            continue
        
        # Parse "N Card Name"
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if not match:
            continue
        
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
        
        for _ in range(count):
            card = Card(
                name=card_name,
                mana_cost=int(card_data.get("cost", 0)),
                card_type=card_data.get("type", "creature"),
                power=int(card_data.get("power", 0)),
                toughness=int(card_data.get("toughness", 0)),
                keywords=list(card_data.get("keywords", [])),
                abilities=list(card_data.get("abilities", [])),
                loyalty=int(card_data.get("loyalty", 0))
            )
            cards.append(card)
            
            if card.card_type == "creature":
                creature_count += 1
                creature_costs.append(card.mana_cost)
            elif card.card_type not in ["land"]:
                spell_count += 1
    
    if unknown_cards:
        unique = list(set(unknown_cards))[:10]
        print(f"\n⚠️  Unknown cards: {unique}{'...' if len(set(unknown_cards)) > 10 else ''}")
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
    
    return cards, detected_name, archetype


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
    
    def score_card(self, card: Card, board: Dict, mana: int) -> float:
        score = 0.0
        arch = board["archetype"]
        
        if card.card_type == "creature":
            score = card.eff_power() + card.eff_toughness() * 0.5
            if "haste" in card.keywords:
                score += 2
            if "trample" in card.keywords:
                score += 1.5
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
            if "token_on_spell" in card.abilities or "spell_trigger" in card.abilities:
                score = 6
            else:
                score = 4
        
        elif card.card_type == "planeswalker":
            score = 8
        
        return score
    
    def find_target(self, card: Card, board: Dict):
        abilities = card.abilities
        
        for ab in abilities:
            if ab.startswith("damage_"):
                try:
                    dmg = int(ab.split("_")[1])
                except:
                    dmg = 3
                
                for threat, _ in board["threats"]:
                    if threat.eff_toughness() <= dmg:
                        return threat
                
                if not board["top_threat"]:
                    return "face"
                return board["top_threat"]
        
        if any(a in abilities for a in ["destroy_creature", "exile"]):
            return board["top_threat"]
        
        if "bounce" in str(abilities):
            return board["top_threat"]
        
        if "bite" in abilities or "fight" in abilities:
            my_c = self.me.creatures()
            if my_c and board["top_threat"]:
                return (max(my_c, key=lambda c: c.eff_power()), board["top_threat"])
        
        return None
    
    def needs_target(self, card: Card) -> bool:
        targeting = ["damage_", "destroy_", "exile", "bounce", "bite", "fight"]
        return any(any(t in a for t in targeting) for a in card.abilities)
    
    def main_phase(self) -> List[Tuple[str, Card, Any]]:
        actions = []
        mana = self.me.untapped_lands()
        board = self.board_eval()
        
        lands = [c for c in self.me.hand if c.card_type == "land"]
        if lands and not self.me.land_played:
            actions.append(("land", lands[0], None))
            mana += 1
        
        castable = [c for c in self.me.hand if c.card_type != "land" and c.mana_cost <= mana]
        if not castable:
            return actions
        
        scored = [(c, self.score_card(c, board, mana)) for c in castable]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        spent = 0
        used = set()
        
        for card, score in scored:
            if card.instance_id in used:
                continue
            if spent + card.mana_cost > mana:
                continue
            
            target = self.find_target(card, board)
            if self.needs_target(card) and target is None:
                continue
            
            actions.append(("cast", card, target))
            used.add(card.instance_id)
            spent += card.mana_cost
        
        return actions
    
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
    
    def blockers(self, attackers: List[Card]) -> Dict[int, int]:
        blocks = {}
        if not attackers:
            return blocks
        
        my_blockers = [c for c in self.me.creatures() if not c.is_tapped]
        if not my_blockers:
            return blocks
        
        sorted_att = sorted(attackers, key=lambda a: a.eff_power() + (3 if "trample" in a.keywords else 0), reverse=True)
        used = set()
        
        for att in sorted_att:
            best = None
            best_score = -100
            
            for b in my_blockers:
                if b.instance_id in used:
                    continue
                
                kills = b.eff_power() >= att.eff_toughness()
                survives = b.eff_toughness() > att.eff_power()
                
                score = 0
                if kills and survives:
                    score = 10
                elif kills:
                    score = 5
                elif survives:
                    score = 2
                else:
                    score = -5
                
                if "deathtouch" in b.keywords:
                    score += 5
                
                score -= b.mana_cost * 0.5
                
                if score > best_score:
                    best_score = score
                    best = b
            
            if best and (best_score > 0 or att.eff_power() >= self.me.life):
                blocks[att.instance_id] = best.instance_id
                used.add(best.instance_id)
        
        return blocks


# =============================================================================
# GAME ENGINE
# =============================================================================

class Game:
    def __init__(self, cards1: List[Card], name1: str, arch1: str,
                 cards2: List[Card], name2: str, arch2: str, verbose: bool = True):
        self.log = Log(verbose)
        self.next_id = 1
        
        self.p1 = Player(1, name1, arch1)
        self.p2 = Player(2, name2, arch2)
        
        for c in cards1:
            card = c.copy()
            card.instance_id = self.next_id
            card.controller = 1
            self.next_id += 1
            self.p1.library.append(card)
        
        for c in cards2:
            card = c.copy()
            card.instance_id = self.next_id
            card.controller = 2
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
    
    def draw(self, player: Player, n: int = 1) -> bool:
        for _ in range(n):
            if not player.library:
                self.winner = 3 - player.player_id
                return False
            player.hand.append(player.library.pop(0))
        return True
    
    def deal_hands(self):
        for _ in range(7):
            self.p1.hand.append(self.p1.library.pop(0))
            self.p2.hand.append(self.p2.library.pop(0))
    
    def tap_lands(self, player: Player, n: int):
        tapped = 0
        for c in player.battlefield:
            if c.card_type == "land" and not c.is_tapped and tapped < n:
                c.is_tapped = True
                tapped += 1
    
    def create_token(self, player: Player, power: int, toughness: int, name: str = "Token"):
        token = Card(name=name, mana_cost=0, card_type="creature",
                     power=power, toughness=toughness,
                     instance_id=self.next_id, controller=player.player_id,
                     summoning_sick=True)
        self.next_id += 1
        player.battlefield.append(token)
        self.log.log(f"    Creates {power}/{toughness} {name}")
    
    def resolve(self, player: Player, card: Card, target: Any):
        opp = self.opponent()
        
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
        
        for ab in card.abilities:
            self._process_ability(ab, player, opp, card, target)
        
        if card.card_type in ["instant", "sorcery"]:
            player.graveyard.append(card)
        elif card.card_type in ["creature", "enchantment", "artifact", "planeswalker"]:
            if card.card_type == "creature":
                card.summoning_sick = True
            player.battlefield.append(card)
    
    def _process_ability(self, ab: str, player: Player, opp: Player, card: Card, target: Any):
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
                    self.log.log(f"    {my_c.name} hits {their_c.name}")
                    
                    if ab == "fight":
                        my_c.damage_marked += their_c.eff_power()
                    
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
    
    def combat(self, attackers: List[Card], blocks: Dict[int, int]):
        act = self.active()
        opp = self.opponent()
        
        if not attackers:
            return
        
        for a in attackers:
            a.is_tapped = True
        
        self.log.log(f"  Attackers: {[a.name for a in attackers]}")
        
        total_dmg = 0
        
        for att in attackers:
            blocker_id = blocks.get(att.instance_id)
            blocker = next((c for c in opp.battlefield if c.instance_id == blocker_id), None) if blocker_id else None
            
            if blocker:
                self.log.log(f"    {att.name} blocked by {blocker.name}")
                blocker.damage_marked += att.eff_power()
                att.damage_marked += blocker.eff_power()
                
                if "trample" in att.keywords:
                    excess = att.eff_power() - blocker.eff_toughness()
                    if excess > 0:
                        opp.life -= excess
                        self.log.log(f"    Tramples {excess}")
                
                if blocker.damage_marked >= blocker.eff_toughness():
                    opp.battlefield.remove(blocker)
                    opp.graveyard.append(blocker)
                    self.log.log(f"    {blocker.name} dies!")
                if att.damage_marked >= att.eff_toughness():
                    act.battlefield.remove(att)
                    act.graveyard.append(att)
                    self.log.log(f"    {att.name} dies!")
                
                if "lifelink" in att.keywords:
                    act.life += att.eff_power()
            else:
                dmg = att.eff_power()
                opp.life -= dmg
                total_dmg += dmg
                if "lifelink" in att.keywords:
                    act.life += dmg
        
        if total_dmg > 0:
            self.log.log(f"  Combat: {total_dmg} to P{opp.player_id} ({opp.life})")
    
    def check_state(self) -> bool:
        if self.p1.life <= 0:
            self.winner = 2
            self.log.log(f"\n🏆 P2 ({self.p2.deck_name}) WINS! P1 at {self.p1.life}")
            return False
        if self.p2.life <= 0:
            self.winner = 1
            self.log.log(f"\n🏆 P1 ({self.p1.deck_name}) WINS! P2 at {self.p2.life}")
            return False
        return True
    
    def play_turn(self) -> bool:
        act = self.active()
        opp = self.opponent()
        
        self.turn += 1
        self.log.section(f"TURN {self.turn}: P{act.player_id} ({act.deck_name})")
        self.log.log(f"  Life: P1={self.p1.life}, P2={self.p2.life}")
        
        act.land_played = False
        act.spells_cast = 0
        
        for c in act.battlefield:
            c.is_tapped = False
            if c.card_type == "creature":
                c.summoning_sick = False
                c.damage_marked = 0
        
        for c in opp.battlefield:
            if c.card_type == "creature":
                c.damage_marked = 0
        
        if not (self.turn == 1 and act.player_id == 1):
            if not self.draw(act):
                return False
        
        self.log.log(f"  Hand: {[c.name for c in act.hand]}")
        self.log.log(f"  Board: {[c.name for c in act.battlefield if c.card_type != 'land']}")
        
        ai = AI(act, opp, self.log)
        actions = ai.main_phase()
        
        self.log.log("\n  === MAIN ===")
        for action, card, target in actions:
            if action == "land":
                act.hand.remove(card)
                act.battlefield.append(card)
                act.land_played = True
                self.log.log(f"  ▶ Land: {card.name}")
            elif action == "cast":
                self.log.log(f"  ▶ Cast: {card.name} ({card.mana_cost})")
                self.tap_lands(act, card.mana_cost)
                act.hand.remove(card)
                self.resolve(act, card, target)
                if not self.check_state():
                    return False
        
        self.log.log("\n  === COMBAT ===")
        attackers = ai.attackers()
        
        if attackers:
            opp_ai = AI(opp, act, self.log)
            blocks = opp_ai.blockers(attackers)
            self.combat(attackers, blocks)
            if not self.check_state():
                return False
        else:
            self.log.log("  No attacks.")
        
        self.active_id = 3 - self.active_id
        return True
    
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
# MATCH RUNNER
# =============================================================================

def run_match(deck1_txt: str, deck2_txt: str, 
              name1: str = None, name2: str = None,
              matches: int = 5, games: int = 3, verbose: bool = False) -> Dict:
    """
    Run matches between two decks (MTGO .txt format).
    """
    cards1, n1, arch1 = parse_decklist(deck1_txt, name1)
    cards2, n2, arch2 = parse_decklist(deck2_txt, name2)
    
    print(f"\n{'#'*70}")
    print(f"  {n1} ({arch1}) vs {n2} ({arch2})")
    print(f"  {matches} best-of-{games}")
    print(f"{'#'*70}")
    
    results = {
        "deck1": n1, "deck2": n2,
        "deck1_wins": 0, "deck2_wins": 0,
        "deck1_games": 0, "deck2_games": 0,
    }
    
    for m in range(1, matches + 1):
        print(f"\n>>> MATCH {m}")
        match = {"d1": 0, "d2": 0}
        
        for g in range(1, games + 1):
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
                         matches: int = 5, games: int = 3, verbose: bool = False) -> Dict:
    """Run match from .txt deck files."""
    with open(file1, 'r') as f:
        deck1 = f.read()
    with open(file2, 'r') as f:
        deck2 = f.read()
    return run_match(deck1, deck2, name1, name2, matches, games, verbose)


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
