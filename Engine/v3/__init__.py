"""MTG Simulation Engine v3 - Rules-Accurate Competitive Simulator"""
from .engine.game import Game, GameConfig, GameResult
from .engine.match import Match, MatchRunner, run_matchup
from .cards.parser import Decklist, DecklistParser, Deck
from .cards.database import CardDatabase

__version__ = "3.0.0"
__all__ = ["Game", "GameConfig", "GameResult", "Match", "MatchRunner",
           "run_matchup", "Decklist", "Deck", "CardDatabase"]
