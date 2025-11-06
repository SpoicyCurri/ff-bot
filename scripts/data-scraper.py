"""
FBRef Data Scraper

This module handles the scraping of football statistics from FBRef.com.
It collects fixture data and detailed player statistics for various metrics.
"""

import argparse
import asyncio
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError
import os

import numpy as np
import pandas as pd
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions

# Type aliases
DataFrameType = pd.DataFrame
TableType = Dict[str, Dict[str, int]]
LeagueType = Dict[str, Tuple[str, str]]


@dataclass
class ScraperConfig:
    """Configuration settings for the scraper."""

    base_url: str = "https://fbref.com"
    data_dir: Path = Path.cwd() / "data"
    players_dir: Path = Path("players_v2")
    min_delay: float = 6.0
    max_delay: float = 10.0
    season: Optional[str] = None
    options: ChromiumOptions = None
    
    def __post_init__(self):
        """Create necessary directories after initialization."""
        self.data_dir.mkdir(exist_ok=True)
        
        # Create season-specific directories if season is specified
        if self.season:
            self.data_dir = self.data_dir / self.season
        else:
            self.data_dir = self.data_dir / "2025-2026"  # Default to current season

        self.players_dir = self.data_dir / self.players_dir
        self.data_dir.mkdir(exist_ok=True)
        self.players_dir.mkdir(exist_ok=True)
        
        # Set up browser options
        self.options = self.get_pydoll_options()
        
    def get_pydoll_options(self) -> ChromiumOptions:
        """Generate options for pydoll browser."""
        options = ChromiumOptions()
        
        # Detect CI/GitHub Actions environment
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        
        # Base options for all environments
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        
        if is_github_actions:
            # CI-specific options for better compatibility
            options.headless = False  # Use Xvfb instead of headless for full rendering
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--remote-debugging-port=9222')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
           # Try to find Chrome in common locations
            chrome_paths = [
                os.getenv('CHROME_PATH'),  # From environment
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable', 
                '/usr/bin/chrome',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium',
                '/opt/google/chrome/chrome'  # Sometimes installed here
            ]
            
            for path in chrome_paths:
                if path and os.path.exists(path) and os.access(path, os.X_OK):
                    options.binary_location = path
                    break
        else:
            # Local development - keep visible browser
            options.headless = False
        
        return options


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
        "defense": {"home": 15, "away": 22},
        "possession": {"home": 16, "away": 23},
        "misc": {"home": 17, "away": 24},
        "keeper": {"home": 18, "away": 25},
    }

    def __init__(self, config: Optional[ScraperConfig] = None):
        """Initialize the scraper with configuration."""
        self.config = config or ScraperConfig()
        self.logger = self._setup_logging()
        self._browser = None
        self._tab = None

    def _setup_logging(self) -> logging.Logger:
        """Configure and return logger instance."""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(formatter)
            logger.addHandler(ch)

            # Do not save logs to file; keep logs only in the console
            logger.propagate = False

        return logger

    async def _random_delay(self) -> None:
        """Add random delay between requests to avoid rate limiting."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        await asyncio.sleep(delay)

    async def _setup_browser(self):
        """Set up and return pydoll browser."""
        if not self._browser:
            # Debug Chrome path in CI
            if os.getenv('GITHUB_ACTIONS') == 'true':
                chrome_path = getattr(self.config.options, 'binary_location', None)
                self.logger.info(f"Using Chrome binary at: {chrome_path}")
                if chrome_path and os.path.exists(chrome_path):
                    self.logger.info(f"Chrome binary exists and is executable: {os.access(chrome_path, os.X_OK)}")
                else:
                    self.logger.error(f"Chrome binary not found at: {chrome_path}")
            
            self._browser = Chrome(options=self.config.options)
        
        try:
            await self._browser.__aenter__()
            self._tab = await self._browser.start()
            
            # In CI, give extra time for browser initialization
            if os.getenv('GITHUB_ACTIONS') == 'true':
                await asyncio.sleep(2)
                
            return self._browser, self._tab
        except Exception as e:
            self.logger.error(f"Failed to setup browser: {e}")
            # In CI, provide more debugging info
            if os.getenv('GITHUB_ACTIONS') == 'true':
                self.logger.error(f"Chrome options: {self.config.options}")
                self.logger.error(f"DISPLAY environment: {os.getenv('DISPLAY')}")
            raise

    async def _cleanup_browser(self) -> None:
        """Clean up browser resources."""
        if self._browser:
            await self._browser.__aexit__(None, None, None)

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

    async def get_fixture_data(self, url: str) -> Optional[DataFrameType]:
        """Scrape and process fixture data from the given URL."""
        self.logger.info("Getting fixture data...")

        try:
            _, tab = await self._setup_browser()
            
            # Handle captcha and navigate
            # async with tab.expect_and_bypass_cloudflare_captcha():
            await tab.go_to(url)
            
            self.logger.info("Captcha bypass complete!")
            await self._random_delay()

            self.logger.info("Beginning to process fixture table")
            fixtures = await self._process_fixture_table(tab)

            # Save to CSV
            fixture_path = self.config.data_dir / "fixture_data__pydoll.csv"
            fixtures.to_csv(fixture_path, index=False)
            self.logger.info(f"Fixture data saved to {fixture_path}")

            return fixtures

        except Exception as e:
            self.logger.error(f"Error fetching fixture data: {e}", exc_info=True)
            return None

        finally:
            await self._cleanup_browser()

    async def _process_fixture_table(self, tab) -> DataFrameType:
        """Process the fixture table from the page content."""
        # Find tables using pydoll
        tables = await tab.find(tag_name="table", find_all=True)
        self.logger.info(f"Found {len(tables)} tables on page")

        # Get the fixture table (adjust index as needed)
        if len(tables) < 1:
            raise ValueError("No tables found on page")
            
        table_body = await tables[0].find(tag_name="tbody")
        rows = await table_body.find(tag_name="tr", find_all=True)
        
        # Extract table data
        self.logger.info(f"Extracting table data from fixture table")
        row_data = []
        for row in rows:
            cols_th = await row.find(tag_name="th", find_all=True)
            cols_tr = await row.find(tag_name="td", find_all=True)
            cols = cols_th + cols_tr
            
            col_heads = [col.get_attribute("data-stat") for col in cols]
            col_texts = [await col.text for col in cols]
            
            match_report_links = await self._get_match_links(cols)
            col_heads.append("match_report_link")
            if match_report_links:
                col_texts.append(f"{self.config.base_url}{match_report_links[0]}")
            else:
                col_texts.append("no-link")

            row_data.append(dict(zip(col_heads, col_texts)))

        fixtures = pd.DataFrame(row_data)
        self.logger.info(f"Fixture table shape: {fixtures.shape}")

        # Clean up fixtures data
        fixtures = self._clean_fixture_data(fixtures)

        return fixtures

    async def _get_match_links(self, cols) -> List[str]:
        """Extract match report links from the page."""
        # Extract match report links
        col_links = []
        for col in cols:
            try:
                data_stat = col.get_attribute("data-stat")
                if data_stat == "match_report":
                    # Find the <a> tag within this td
                    link_element = await col.find(tag_name="a")
                    if link_element:
                        href = link_element.get_attribute("href")
                        col_links.append(href if href else "")
                    else:
                        col_links.append("")
                else:
                    col_links.append("")
            except Exception as e:
                col_links.append("")
        
        # Add match report link if found
        match_report_links = [link for link in col_links if link]
        return match_report_links

    def _clean_fixture_data(self, fixtures: DataFrameType) -> DataFrameType:
        """Clean and process fixture data."""
        self.logger.info(f"Clean and process fixture data")        
        fixtures = fixtures.drop(columns=["notes", "referee", "attendance", "venue", "match_report"])

        # Filter valid rows
        fixtures = fixtures[pd.to_numeric(fixtures["gameweek"], errors='coerce').notna()]

        # Add computed columns
        fixtures["game_played"] = np.where((fixtures["match_report_link"].str.startswith('https://fbref.com/en/matches/')), True, False)
        
        # Create a deterministic game_id by combining home team, away team, and date
        # Remove any spaces and special characters, then join with underscores
        fixtures["game_id"] = fixtures.apply(
            lambda row: "_".join([
                str(row["home_team"]).replace(" ", ""),
                str(row["away_team"]).replace(" ", ""),
                str(row["date"]).replace("-", "")
            ]),
            axis=1,
        )

        return fixtures

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
                existing_game_ids = set()

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

    async def get_player_data(self, fixtures: DataFrameType) -> None:
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
        match_links = new_games["match_report_link"]
        game_ids = new_games["game_id"]

        try:
            _, tab = await self._setup_browser()

            # Initialize with empty DataFrames only for missing stat types
            for stat_type in self.PLAYER_TABLES.keys():
                if stat_type not in player_data_dict:
                    player_data_dict[stat_type] = pd.DataFrame([])

            for count, (link, game_id) in enumerate(zip(match_links, game_ids)):
                await self._process_match(
                    tab, link, game_id, count, len(match_links), player_data_dict
                )
                await self._random_delay()

        except Exception as e:
            self.logger.error(
                f"Fatal error in player data collection: {e}", exc_info=True
            )

        finally:
            await self._cleanup_browser()

    def get_table_ids(self, tables, keyword):
        """Get table IDs containing the specified keyword."""
        if keyword=="keeper":
            return [table.id for table in tables if keyword in str(table.id)]
        else:
            return [table.id for table in tables if str(table.id).split("_", 3)[-1] == keyword]
    
    async def _process_match(
        self,
        tab,
        link: str,
        game_id: str,
        count: int,
        total: int,
        player_data_dict: Dict[str, DataFrameType],
    ) -> None:
        """Process a single match's player data."""
        try:
            self.logger.info(f"Processing match {count + 1}/{total}: {link}")
            
            # Handle captcha and navigate - more robust for CI
            try:
                async with tab.expect_and_bypass_cloudflare_captcha():
                    await tab.go_to(link)
            except Exception as captcha_error:
                # Fallback for CI environments where captcha bypass might fail
                self.logger.warning(f"Captcha bypass failed, trying direct navigation: {captcha_error}")
                await tab.go_to(link)
                await self._random_delay()  # Extra delay to avoid rate limiting

            # Find all product cards
            tables = await tab.find(tag_name="table", find_all=True)
            print(f"Found {len(tables)} tables on the page.")

            await self._extract_and_save_player_stats(tables, game_id, player_data_dict)

        except Exception as e:
            self.logger.error(f"Error processing match {link}: {e}", exc_info=True)

    async def _extract_and_save_player_stats(
        self,
        tables: List[DataFrameType],
        game_id: str,
        player_data_dict: Dict[str, DataFrameType],
    ) -> None:
        """Extract and save player statistics for all stat types."""
        for keyword in ["summary", "passing", "passing_types", "defense", "possession", "misc", "keeper"]:
            clean_table_ids = self.get_table_ids(tables, keyword)

            row_data = list()
            for index, table in enumerate([t for t in tables if t.id in clean_table_ids]):
                print(f"Processing table ID: {table.id}")
                table_body = await table.find(tag_name="tbody")
                rows = await table_body.find(tag_name="tr", find_all=True)

                for row in rows:
                    cols_th = await row.find(tag_name="th", find_all=True)
                    cols_tr = await row.find(tag_name="td", find_all=True)
                    cols = cols_th + cols_tr
                    
                    col_heads = [col.get_attribute("data-stat") for col in cols] + ["home"]
                    col_texts = [await col.text for col in cols] + ([True] if index % 2 == 0 else [False])
                    
                    row_dict = dict(zip(col_heads, col_texts))
                    row_data.append(row_dict)
        
            row_data_df = pd.DataFrame(row_data)
            row_data_df["game_id"] = game_id

            prev_rows = len(player_data_dict[keyword])
            
            # Remove any existing data for this game_id to avoid duplicates
            if not player_data_dict[keyword].empty:
                player_data_dict[keyword] = player_data_dict[keyword][
                    player_data_dict[keyword]["game_id"] != game_id
                ]
            
            # Append new data
            player_data_dict[keyword] = pd.concat(
                [player_data_dict[keyword], row_data_df], ignore_index=True
            )
            new_rows = len(player_data_dict[keyword]) - prev_rows
            self.logger.info(
                f"Added {new_rows} rows to {keyword} data "
                f"(total: {len(player_data_dict[keyword])})"
            )

            file_path = self.config.players_dir / f"players_{keyword}.csv"
            player_data_dict[keyword].to_csv(file_path, index=False)
            self.logger.info(f"Saved {keyword} data to {file_path}")

    async def run(self, league_name: str = "Premier League") -> None:
        """Main method to run the scraper."""
        self.logger.info(f"Starting FBRef data collection for {league_name}")

        try:
            url, league = self.get_league_url(league_name)
            self.logger.info(f"Processing league: {league} from {url}")

            fixtures = await self.get_fixture_data(url)
            if fixtures is not None:
                self.logger.info(f"Successfully retrieved {len(fixtures)} fixtures")
                await self.get_player_data(fixtures)
                self.logger.info("Data collection completed successfully")

        except Exception as e:
            self.logger.error(f"An error occurred: {e}", exc_info=True)


async def main() -> None:
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
        await scraper.run()
    except HTTPError:
        logging.error("The website refused access, try again later")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
