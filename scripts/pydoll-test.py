import asyncio
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
import pandas as pd
import io

def clean_fixture_data(fixtures):
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


def get_table_ids(tables, keyword):
    clean_table_ids = [
        table.id for table in tables if keyword in table.id
    ]
    return clean_table_ids


async def players():
    options = ChromiumOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.headless = False
    
    matches_link = "https://fbref.com/en/matches/bb37daa2/Sunderland-Everton-November-3-2025-Premier-League"

    async with Chrome(options=options) as browser:
        tab = await browser.start()

        # Context manager handles captcha automatically
        async with tab.expect_and_bypass_cloudflare_captcha():
            await tab.go_to(matches_link)

        # This code only runs after captcha is clicked
        print("Turnstile captcha interaction complete!")

        # Find all product cards
        tables = await tab.find(tag_name="table", find_all=True)
        print(f"Found {len(tables)} tables on the page.")

        for keyword in ["summary", "passing", "passing_types", "defense", "possession", "misc", "keeper"]:
            clean_table_ids = get_table_ids(tables, keyword)

            row_data = list()
            for index, table in enumerate([t for t in tables if t.id in clean_table_ids]):
                print(f"Processing table ID: {table.id}")
                table_body = await table.find(tag_name="tbody")
                rows = await table_body.find(tag_name="tr", find_all=True)

                for row in rows:
                    cols_th = await row.find(tag_name="th", find_all=True)
                    cols_tr = await row.find(tag_name="td", find_all=True)
                    cols = cols_th + cols_tr
                    
                    col_heads = [col.get_attribute("data-stat") for col in cols] + ["home_away"]
                    col_texts = [await col.text for col in cols] + (["home"] if index % 2 == 0 else ["away"])
                    
                    row_dict = dict(zip(col_heads, col_texts))
                    row_data.append(row_dict)
        
            row_data_df = pd.DataFrame(row_data)
            row_data_df.to_csv(f"data/test-data/players_{keyword}_raw.csv", index=False)
            print(f"Saved raw {keyword} data to players_{keyword}_raw.csv")


async def fixtures():
    options = ChromiumOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.headless = False

    async with Chrome(options=options) as browser:
        tab = await browser.start()

        # Context manager handles captcha automatically
        async with tab.expect_and_bypass_cloudflare_captcha():
            await tab.go_to('https://fbref.com/en/comps/9/schedule/Premier-League-Scores-and-Fixtures')

        # This code only runs after captcha is clicked
        print("Turnstile captcha interaction complete!")

        # Find all product cards
        tables = await tab.find(tag_name="table", find_all=True)
        print(f"Found {len(tables)} tables on the page.")
        
        table_ids = [table.id for table in tables]
        print(f"Table IDs: {table_ids}")
        # fixtures = await tables.find(
        #     id="sched_2025-2026_9_1"
        # )
        
        fixtures = table_ids[0]
        print(f"Fixtures table: {fixtures}")
        
        table_body = await tables[0].find(tag_name="tbody")
        rows = await table_body.find(tag_name="tr", find_all=True)
        
        row_data = list()
        for row in rows:
            cols_th = await row.find(tag_name="th", find_all=True)
            cols_tr = await row.find(tag_name="td", find_all=True)
            cols = cols_th + cols_tr
            
            col_heads = [await col.get_attribute("data-stat") for col in cols]
            col_texts = [await col.text for col in cols]
            
            # Extract match report links
            col_links = []
            for col in cols:
                data_stat = await col.get_attribute("data-stat")
                if data_stat == "match_report":
                    # Find the <a> tag within this td
                    link_element = await col.find(tag_name="a")
                    if link_element:
                        href = await link_element.get_attribute("href")
                        col_links.append(href if href else "")
                    else:
                        col_links.append("")
                else:
                    col_links.append("")
            
            # Create row dictionary with texts and links
            row_dict = dict(zip(col_heads, col_texts))
            
            # Add match report link if found
            match_report_links = [link for link in col_links if link]
            if match_report_links:
                row_dict["Match Report Link"] = f"https://fbref.com{match_report_links[0]}"
            
            row_data.append(row_dict)
        
        row_data_df = pd.DataFrame(row_data)
        row_data_df.to_csv("data/test-data/fixtures_raw.csv", index=False)
        print("Saved raw fixtures data to fixtures_raw.csv")

# asyncio.run(players())

def import_all_csvs_from_test_data(folder_path):
    """Import all CSV files from data/test-data folder into a dictionary of DataFrames."""
    import os
    from pathlib import Path
    
    filename_mapping = {
        # Raw data files (from test-data folder)
        "players_defense_raw": "defensive_actions",
        "players_keeper_raw": "goalkeeper", 
        "players_misc_raw": "miscellaneous",
        "players_passing_raw": "passing",
        "players_passing_types_raw": "passing_types",
        "players_possession_raw": "possession",
        "players_summary_raw": "summary",

        # Historical/processed data files (from 2025-2026/players folder)
        "players_defensive_actions": "defensive_actions",
        "players_goalkeeper": "goalkeeper",
        "players_miscellaneous": "miscellaneous", 
        "players_passing": "passing",
        "players_passing_types": "passing_types",
        "players_possession": "possession",
        "players_summary": "summary"
    }
    
    # Define the folder path
    test_data_folder = Path(folder_path)
    
    # Dictionary to store all DataFrames
    csv_data = {}
    
    # Check if folder exists
    if not test_data_folder.exists():
        print(f"Folder {test_data_folder} does not exist!")
        return csv_data
    
    # Get all CSV files in the folder
    csv_files = list(test_data_folder.glob("*.csv"))
    csv_files = [f for f in csv_files if "players_" in f.name]
    
    if not csv_files:
        print(f"No CSV files found in {test_data_folder}")
        return csv_data
    
    print(f"Found {len(csv_files)} CSV files:")
    
    # Import each CSV file
    for csv_file in csv_files:
        try:
            # Use filename (without extension) as dictionary key
            key_name = filename_mapping.get(csv_file.stem, csv_file.stem)
            
            # Read the CSV file
            df = pd.read_csv(csv_file)
            csv_data[key_name] = df
            
            print(f"✓ Imported {csv_file.name}: {df.shape[0]} rows, {df.shape[1]} columns")
            
        except Exception as e:
            print(f"✗ Error importing {csv_file.name}: {e}")
    
    return csv_data


def get_table_ids(tables, keyword):
        """Get table IDs containing the specified keyword."""
        if keyword=="keeper":
            return [table.id for table in tables if keyword in str(table.id)]
        else:
            return [table.id for table in tables if str(table.id).split("_", 3)[-1] == keyword]
    
    
# Example usage and testing
if __name__ == "__main__":
    # Import all CSV files from test-data folder
    print("🔄 Importing CSV files from data/test-data folder...")
    test = "data/test-data"
    test_csv_data = import_all_csvs_from_test_data(test)
    
    historic = "data/2025-2026/players"
    historic_csv_data = import_all_csvs_from_test_data(historic)

    for file, df in historic_csv_data.items():
        print(f"Processing file: {file}")
        test_df = test_csv_data.get(file)
        if test_df is not None:
            if df.columns.equals(test_df.columns):
                print(f"Columns match for {file}: {df.columns.tolist()}")
            else:
                print(f"Columns do not match for {file}:")
                print(f"  Column counts -> Historic: {len(df.columns)}, Test: {len(test_df.columns)}, Diff: {len(df.columns) - len(test_df.columns)}")
                print(f"  Historic: {df.columns.tolist()}")
                print(f"  Test: {test_df.columns.tolist()}")


# To run the CSV import function separately, uncomment the line below:
# asyncio.run(turnstile_example())