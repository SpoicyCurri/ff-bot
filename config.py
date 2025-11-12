from dataclasses import dataclass, field
from pathlib import Path
from typing import List

@dataclass
class Config:
    """Application configuration settings."""
    # Page settings
    PLAYER_TITLE: str = "⚽FPL Stats"
    TEAM_TITLE: str = "⚽FPL Stats"
    PAGE_LAYOUT: str = "wide"
    
    # File paths
    DATA_DIR: Path = Path.cwd().joinpath("data")
    PLAYERS_FILE: Path = DATA_DIR / "2025-2026" / "players_v2" / "players_summary.csv"
    FIXTURES_FILE: Path = DATA_DIR / "2025-2026" / "fixture_data__pydoll.csv"
    FPL_FILE: Path = DATA_DIR / "fpl" / "fpl_players.csv"
    
    # Chart settings
    CHART_HEIGHT: int = 400
    CHART_COLOR_SCHEME: str = "darkred"
    
    # Player comparison settings
    MIN_PLAYERS: int = 5
    MAX_PLAYERS: int = 20
    DEFAULT_PLAYERS: int = 10
    
    # Available metrics
    METRICS: List[str] = field(default_factory=lambda: [
        "xg", "npxg", "xg_assist", "xGI", "Defensive Contributions", 
        "goals", "assists", "shots", "shots_on_target", "sca", "gca",
    ])
    
    # FPL Positions
    FPL_POSITIONS: List[str] = field(default_factory=lambda: [
        "FWD", "MID", "DEF",  "GK",
    ])