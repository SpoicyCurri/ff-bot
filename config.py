from dataclasses import dataclass, field
from pathlib import Path
from typing import List

@dataclass
class Config:
    """Application configuration settings."""
    # Page settings
    PAGE_TITLE: str = "Premier League Player Statistics"
    PAGE_LAYOUT: str = "wide"
    
    # File paths
    DATA_DIR: Path = Path.cwd().joinpath("data")
    PLAYERS_FILE: Path = DATA_DIR / "players" / "players_summary.csv"
    FIXTURES_FILE: Path = DATA_DIR / "fixture_data.csv"
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
        "xG", "xAG", "xGI", "Defensive Contributions", 
        "Gls", "Ast", "Sh", "SoT", "SCA", "GCA",
    ])
    
    # FPL Positions
    FPL_POSITIONS: List[str] = field(default_factory=lambda: [
        "FWD", "MID", "DEF",  "GK",
    ])