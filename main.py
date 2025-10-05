import requests
from urllib.error import HTTPError
import time
import logging
import random
import io

import pandas as pd
import numpy as np
from playwright.sync_api import sync_playwright


BASE_URL = 'https://fbref.com'

LEAGUES = {
    'Premier League': ('Premier-League', '9'),
    'La Liga': ('La-Liga', '12'),
    'Serie A': ('Serie-A', '11'),
    'Ligue 1': ('Ligue-1', '13'),
    'Bundesliga': ('Bundesliga', '20')
}

PLAYER_TABLES = {
    "summary": {"home": 12, "away": 19},
    "passing": {"home": 13, "away": 20},
    "passing_types": {"home": 14, "away": 21},
    "defensive_actions": {"home": 15, "away": 22},
    "possession": {"home": 16, "away": 23},
    "miscellaneous": {"home": 17, "away": 24}, 
    "goalkeeper": {"home": 18, "away": 25}, 
}


def setup_logging():
    """Configure logging settings"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('fbref_scraper.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def random_delay():
    """Add random delay between requests"""
    delay = random.uniform(6, 10)
    time.sleep(delay)


def create_browser_context():
    """Create a browser context with stealth settings"""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    )
    return playwright, browser, context


def get_url(league_selection):
    league, league_id = LEAGUES[league_selection]
    url = f'{BASE_URL}/en/comps/{league_id}/schedule/{league}-Scores-and-Fixtures'
    return url, league


def get_fixture_data(url: str):
    logger = logging.getLogger(__name__)
    logger.info('Getting fixture data...')
    
    playwright, browser, context = create_browser_context()
    
    try:
        page = context.new_page()
        logger.info(f'Navigating to {url}')
        page.goto(url, wait_until='networkidle')
        random_delay()
        
        # Get the table HTML
        html_content = io.StringIO(page.content())
        tables = pd.read_html(html_content)
        logger.info(f'Found {len(tables)} tables on page')
    
        # Get fixtures table
        fixtures = tables[9]
        logger.info(f'Fixture table shape: {fixtures.shape}')
        logger.info(f'Columns found: {fixtures.columns.tolist()}')
        
        selected_columns = [col for col in fixtures.columns if col != 'Match Report']
        for col in selected_columns:
            fixtures[col] = fixtures[col].apply(lambda x: x[0] if isinstance(x, tuple) or isinstance(x, list) else x)
            
        fixtures = fixtures.rename(columns={'xG': 'xG Home', 'xG.1': 'xG Away'})
        fixtures = fixtures.drop(columns=['Notes', 'Referee', 'Attendance', 'Venue'])
        fixtures = fixtures[(~fixtures['Home'].isna()) & (fixtures['Home'] != 'Home')]
        
        fixtures['game_played'] = np.where(fixtures['Score'].isna(), False, True)
        fixtures["game_id"] = fixtures.apply(lambda row: hash((str(row['Home']), str(row['Away']), str(row['Date']))), axis=1)
            
        # Get match report links using Playwright
        match_links = []
        elements = page.query_selector_all('td[data-stat="match_report"] a')
        for element in elements:
            href = element.get_attribute('href')
            if href:
                match_links.append(f"{BASE_URL}{href}")
        logger.info(f'Found {len(match_links)} match report links')
        fixtures['Match Report'] = match_links
        
        logger.info(f'Total fixtures processed: {len(fixtures)}')
        logger.info(f'Games played: {fixtures["game_played"].sum()}')
        
        # export to csv file
        fixtures.to_csv(f'fixture_data.csv', index=False)
        logger.info('Fixture data saved to CSV')
        logger.info(f'Sample of processed data:\n{fixtures.head()}')
        logger.info(f'Sample of processed data from the end:\n{fixtures.tail()}')
        
        return fixtures
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        raise
    
    finally:
        browser.close()
        playwright.stop()


def get_match_links(df):
    logger = logging.getLogger(__name__)
    logger.info('Getting match links...')
    match_links = df[df['game_played']]['Match Report']
    logger.info(f'{len(match_links)} matches found')
    return match_links


def extract_player_data(tables:list, home:bool, stat_type:str):
    index = PLAYER_TABLES[stat_type]['home'] if home else PLAYER_TABLES[stat_type]['away']
    df = tables[index]
    df = df.assign(home=home)
    df = df[~df['Nation'].isna()]
    return df


def get_player_data(match_links: pd.Series, game_id: pd.Series):
    logger = logging.getLogger(__name__)
    logger.info("Starting player data collection")
    
    playwright, browser, context = create_browser_context()
    try:
        page = context.new_page()
        player_data_dict = {name: pd.DataFrame([]) for name in PLAYER_TABLES.keys()}
        
        for count, link in enumerate(match_links):
            try:
                logger.info(f'Processing match {count+1}/{len(match_links)}: {link}')
                page.goto(link, wait_until='networkidle')
                random_delay()
                
                html_content = io.StringIO(page.content())
                tables = pd.read_html(html_content)
                logger.info(f'Found {len(tables)} tables in match report')
                
                for table in tables:
                    try:
                        table.columns = table.columns.droplevel()
                    except Exception:
                        continue
                
                for stat_type in PLAYER_TABLES.keys():
                    team_home = extract_player_data(tables=tables, home=True, stat_type=stat_type)
                    team_away = extract_player_data(tables=tables, home=False, stat_type=stat_type)
                    both_teams = pd.concat([team_home, team_away], ignore_index=True)
                    both_teams['game_id'] = game_id.iloc[count]

                    prev_rows = len(player_data_dict[stat_type])
                    player_data_dict[stat_type] = pd.concat([player_data_dict[stat_type], both_teams], ignore_index=True)
                    new_rows = len(player_data_dict[stat_type]) - prev_rows
                    logger.info(f"Added {new_rows} rows to {stat_type} player data (total: {len(player_data_dict[stat_type])})")
                    player_data_dict[stat_type].to_csv(f'players_{stat_type}.csv', index=False)
                    logger.info(f"Saved {stat_type} player data to players_{stat_type}.csv")
                
            except Exception as e:
                logger.error(f'Error processing match {link}: {str(e)}', exc_info=True)
            
            logger.info('Waiting between requests...')
            time.sleep(random.uniform(5, 8))
    
    except Exception as e:
        logger.error(f'Fatal error in player data collection: {str(e)}', exc_info=True)
        raise
    
    finally:
        browser.close()
        playwright.stop()


def main():
    logger = setup_logging()
    logger.info("Starting FBRef data collection")
    
    try:
        url, league = get_url('Premier League')
        logger.info(f"Processing league: {league} from {url}")
        
        fixtures = get_fixture_data(url)
        if fixtures is not None:
            logger.info(f"Successfully retrieved {len(fixtures)} fixtures")
            get_player_data(get_match_links(fixtures), fixtures['game_id'])
    
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)


if __name__ == '__main__':
    try:
        main()
    except HTTPError:
        logging.error('The website refused access, try again later')
        time.sleep(5)