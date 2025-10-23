"""
FBRef Data Scraper

This module handles the scraping of football statistics from FBRef.com.
It collects fixture data and detailed player statistics for various metrics.
"""

import argparse
import io
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError

import numpy as np
import pandas as pd
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

# Type aliases
DataFrameType = pd.DataFrame
TableType = Dict[str, Dict[str, int]]
LeagueType = Dict[str, Tuple[str, str]]


@dataclass
class ScraperConfig:
    """Configuration settings for the scraper."""

    base_url: str = "https://fbref.com"
    data_dir: Path = Path("data")
    players_dir: Path = Path("players")
    min_delay: float = 6.0
    max_delay: float = 10.0
    viewport_width: int = 1920
    viewport_height: int = 1080
    season: Optional[str] = None
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )

    def __post_init__(self):
        """Create necessary directories after initialization."""
        self.data_dir.mkdir(exist_ok=True)
        
        # Create season-specific directories if season is specified
        if self.season:
            self.data_dir = self.data_dir / self.season
            self.players_dir = self.data_dir / self.players_dir
        
        self.data_dir.mkdir(exist_ok=True)
        self.players_dir.mkdir(exist_ok=True)


class FBRefScraper:
    """Main scraper class for handling FBRef data collection."""

    LEAGUES: LeagueType = {
        "Premier League": ("Premier-League", "9"),
        "La Liga": ("La-Liga", "12"),
        "Serie A": ("Serie-A", "11"),
        "Ligue 1": ("Ligue-1", "13"),
        "Bundesliga": ("Bundesliga", "20"),
    }

    PLAYER_TABLES: TableType = {
        "summary": {"home": 12, "away": 19},
        "passing": {"home": 13, "away": 20},
        "passing_types": {"home": 14, "away": 21},
        "defensive_actions": {"home": 15, "away": 22},
        "possession": {"home": 16, "away": 23},
        "miscellaneous": {"home": 17, "away": 24},
        "goalkeeper": {"home": 18, "away": 25},
    }

    def __init__(self, config: Optional[ScraperConfig] = None):
        """Initialize the scraper with configuration."""
        self.config = config or ScraperConfig()
        self.logger = self._setup_logging()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def _setup_logging(self) -> logging.Logger:
        """Configure and return logger instance."""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

            # File handler
            fh = logging.FileHandler(self.config.data_dir / "fbref_scraper.log")
            fh.setFormatter(formatter)
            logger.addHandler(fh)

            # Console handler
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            logger.addHandler(ch)

        return logger

    def _random_delay(self) -> None:
        """Add random delay between requests to avoid rate limiting."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        time.sleep(delay)

    def _setup_browser(self) -> Tuple[Playwright, Browser, BrowserContext]:
        """Set up and return Playwright browser with stealth settings."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            user_agent=self.config.user_agent,
        )
        return self._playwright, self._browser, self._context

    def _cleanup_browser(self) -> None:
        """Clean up Playwright resources."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def get_league_url(self, league_name: str) -> Tuple[str, str]:
        """Generate URL for specified league's fixtures."""
        if league_name not in self.LEAGUES:
            raise ValueError(f"Unknown league: {league_name}")

        league, league_id = self.LEAGUES[league_name]
        
        # Build URL based on whether a season is specified
        if self.config.season:
            url = (
                f"{self.config.base_url}/en/comps/{league_id}/{self.config.season}/"
                f"schedule/{self.config.season}-{league}-Scores-and-Fixtures"
            )
        else:
            url = (
                f"{self.config.base_url}/en/comps/{league_id}/schedule/"
                f"{league}-Scores-and-Fixtures"
            )
        
        return url, league

    def get_fixture_data(self, url: str) -> Optional[DataFrameType]:
        """Scrape and process fixture data from the given URL."""
        self.logger.info("Getting fixture data...")

        try:
            _, _, context = self._setup_browser()
            page = context.new_page()
            self.logger.info(f"Navigating to {url}")
            page.goto(url, wait_until="networkidle")
            self._random_delay()

            fixtures = self._process_fixture_table(page)

            # Save to CSV
            fixture_path = self.config.data_dir / "fixture_data.csv"
            fixtures.to_csv(fixture_path, index=False)
            self.logger.info(f"Fixture data saved to {fixture_path}")

            return fixtures

        except Exception as e:
            self.logger.error(f"Error fetching fixture data: {e}", exc_info=True)
            return None

        finally:
            self._cleanup_browser()

    def _process_fixture_table(self, page: Page) -> DataFrameType:
        """Process the fixture table from the page content."""
        html_content = io.StringIO(page.content())
        tables = pd.read_html(html_content)
        self.logger.info(f"Found {len(tables)} tables on page")

        fixtures = tables[9]
        self.logger.info(f"Fixture table shape: {fixtures.shape}")

        # Clean up fixtures data
        fixtures = self._clean_fixture_data(fixtures)

        # Add match report links
        fixtures["Match Report"] = self._get_match_links(page)

        return fixtures

    def _clean_fixture_data(self, fixtures: DataFrameType) -> DataFrameType:
        """Clean and process fixture data."""
        # Handle tuple/list values in columns
        selected_columns = [col for col in fixtures.columns if col != "Match Report"]
        for col in selected_columns:
            fixtures[col] = fixtures[col].apply(
                lambda x: x[0] if isinstance(x, (tuple, list)) else x
            )

        # Rename and drop columns
        fixtures = fixtures.rename(columns={"xG": "xG Home", "xG.1": "xG Away"})
        fixtures = fixtures.drop(columns=["Notes", "Referee", "Attendance", "Venue"])

        # Filter valid rows
        fixtures = fixtures[(~fixtures["Home"].isna()) & (fixtures["Home"] != "Home")]

        # Add computed columns
        fixtures["game_played"] = np.where(fixtures["Score"].isna(), False, True)
        
        # Create a deterministic game_id by combining home team, away team, and date
        # Remove any spaces and special characters, then join with underscores
        fixtures["game_id"] = fixtures.apply(
            lambda row: "_".join([
                str(row["Home"]).replace(" ", ""),
                str(row["Away"]).replace(" ", ""),
                str(row["Date"]).replace("-", "")
            ]),
            axis=1,
        )

        return fixtures

    def _get_match_links(self, page: Page) -> List[str]:
        """Extract match report links from the page."""
        elements = page.query_selector_all('td[data-stat="match_report"] a')
        links = []
        for element in elements:
            href = element.get_attribute("href")
            if href:
                links.append(f"{self.config.base_url}{href}")
        self.logger.info(f"Found {len(links)} match report links")
        return links

    def _load_existing_data(self) -> Tuple[Dict[str, DataFrameType], set]:
        """Load existing player data and return existing game IDs."""
        player_data_dict = {}
        existing_game_ids = set()

        # Try to load existing summary data to get game IDs
        summary_path = self.config.players_dir / "players_summary.csv"
        if summary_path.exists():
            try:
                summary_df = pd.read_csv(summary_path)
                existing_game_ids = set(summary_df["game_id"].unique())
                self.logger.info(f"Found {len(existing_game_ids)} existing games")
            except Exception as e:
                self.logger.warning(f"Error loading existing summary data: {e}")

        # Load all existing player data files
        for stat_type in self.PLAYER_TABLES.keys():
            file_path = self.config.players_dir / f"players_{stat_type}.csv"
            if file_path.exists():
                try:
                    player_data_dict[stat_type] = pd.read_csv(file_path)
                    self.logger.info(f"Loaded existing {stat_type} data")
                except Exception as e:
                    self.logger.warning(f"Error loading {stat_type} data: {e}")
                    player_data_dict[stat_type] = pd.DataFrame([])
            else:
                player_data_dict[stat_type] = pd.DataFrame([])

        return player_data_dict, existing_game_ids

    def get_player_data(self, fixtures: DataFrameType) -> None:
        """Collect player data for all matches in fixtures."""
        self.logger.info("Starting player data collection")

        # Load existing data and game IDs
        player_data_dict, existing_game_ids = self._load_existing_data()

        # Filter for only new played games
        played_games = fixtures[fixtures["game_played"]]
        new_games = played_games[~played_games["game_id"].isin(existing_game_ids)]
        
        if new_games.empty:
            self.logger.info("No new games to process")
            return

        self.logger.info(f"Found {len(new_games)} new games to process")
        match_links = new_games["Match Report"]
        game_ids = new_games["game_id"]

        try:
            _, _, context = self._setup_browser()
            page = context.new_page()

            # Initialize with empty DataFrames only for missing stat types
            for stat_type in self.PLAYER_TABLES.keys():
                if stat_type not in player_data_dict:
                    player_data_dict[stat_type] = pd.DataFrame([])

            for count, (link, game_id) in enumerate(zip(match_links, game_ids)):
                self._process_match(
                    page, link, game_id, count, len(match_links), player_data_dict
                )
                self._random_delay()

        except Exception as e:
            self.logger.error(
                f"Fatal error in player data collection: {e}", exc_info=True
            )

        finally:
            self._cleanup_browser()

    def _process_match(
        self,
        page: Page,
        link: str,
        game_id: int,
        count: int,
        total: int,
        player_data_dict: Dict[str, DataFrameType],
    ) -> None:
        """Process a single match's player data."""
        try:
            self.logger.info(f"Processing match {count + 1}/{total}: {link}")
            page.goto(link, wait_until="networkidle")

            html_content = io.StringIO(page.content())
            tables = pd.read_html(html_content)

            # Clean table columns
            for table in tables:
                try:
                    table.columns = table.columns.droplevel()
                except Exception:
                    continue

            self._extract_and_save_player_stats(tables, game_id, player_data_dict)

        except Exception as e:
            self.logger.error(f"Error processing match {link}: {e}", exc_info=True)

    def _extract_and_save_player_stats(
        self,
        tables: List[DataFrameType],
        game_id: str,  # Changed type to str since we now use string game_ids
        player_data_dict: Dict[str, DataFrameType],
    ) -> None:
        """Extract and save player statistics for all stat types."""
        for stat_type in self.PLAYER_TABLES.keys():
            # Get both teams' data
            team_home = self._extract_player_data(tables, True, stat_type)
            team_away = self._extract_player_data(tables, False, stat_type)

            # Ensure both DataFrames have the same columns
            all_columns = list(set(team_home.columns) | set(team_away.columns))
            for df in [team_home, team_away]:
                for col in all_columns:
                    if col not in df.columns:
                        df[col] = None

            # Reset indices before concatenation
            team_home = team_home.reset_index(drop=True)
            team_away = team_away.reset_index(drop=True)
            
            both_teams = pd.concat([team_home, team_away], ignore_index=True)
            both_teams["game_id"] = game_id

            # Update data, keeping all existing data and adding new data
            prev_rows = len(player_data_dict[stat_type])
            
            # Remove any existing data for this game_id to avoid duplicates
            if not player_data_dict[stat_type].empty:
                player_data_dict[stat_type] = player_data_dict[stat_type][
                    player_data_dict[stat_type]["game_id"] != game_id
                ]
            
            # Append new data
            player_data_dict[stat_type] = pd.concat(
                [player_data_dict[stat_type], both_teams], ignore_index=True
            )

            new_rows = len(player_data_dict[stat_type]) - prev_rows
            self.logger.info(
                f"Added {new_rows} rows to {stat_type} data "
                f"(total: {len(player_data_dict[stat_type])})"
            )

            # Save to CSV
            file_path = self.config.players_dir / f"players_{stat_type}.csv"
            player_data_dict[stat_type].to_csv(file_path, index=False)
            self.logger.info(f"Saved {stat_type} data to {file_path}")

    def _extract_player_data(
        self, tables: List[DataFrameType], home: bool, stat_type: str
    ) -> DataFrameType:
        """Extract player data for specific team and stat type."""
        index = (
            self.PLAYER_TABLES[stat_type]["home"]
            if home
            else self.PLAYER_TABLES[stat_type]["away"]
        )
        df = tables[index]
        df = df.assign(home=home)
        
        # Reset index to avoid duplicate index issues
        df = df[~df["Nation"].isna()].reset_index(drop=True)
        
        # Ensure all columns are properly named and no duplicate columns exist
        df = df.loc[:, ~df.columns.duplicated()]
        
        return df

    def run(self, league_name: str = "Premier League") -> None:
        """Main method to run the scraper."""
        self.logger.info(f"Starting FBRef data collection for {league_name}")

        try:
            url, league = self.get_league_url(league_name)
            self.logger.info(f"Processing league: {league} from {url}")

            fixtures = self.get_fixture_data(url)
            if fixtures is not None:
                self.logger.info(f"Successfully retrieved {len(fixtures)} fixtures")
                self.get_player_data(fixtures)
                self.logger.info("Data collection completed successfully")

        except Exception as e:
            self.logger.error(f"An error occurred: {e}", exc_info=True)


def main() -> None:
    """Entry point for the scraper."""
    available_seasons = [
        "2024-2025",
        "2023-2024",
        "2022-2023",
        "2021-2022",
        "2020-2021",
        "2019-2020",
    ]
    
    parser = argparse.ArgumentParser(description='FBRef Data Scraper')
    parser.add_argument('--season', 
                       choices=available_seasons,
                       help='Season to scrape (e.g., "2023-2024")')
    args = parser.parse_args()

    config = ScraperConfig(season=args.season)
    scraper = FBRefScraper(config)

    try:
        scraper.run()
    except HTTPError:
        logging.error("The website refused access, try again later")
        time.sleep(5)


if __name__ == "__main__":
    main()
