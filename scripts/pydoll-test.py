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
    


async def turnstile_example():
    options = ChromiumOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    # options.headless = True

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
            col_heads = [col.get_attribute("data-stat") for col in cols]
            col_texts = [await col.text for col in cols]
            row_data.append(dict(zip(col_heads, col_texts)))
        
        row_data_df = pd.DataFrame(row_data)
        row_data_df.to_csv("data/test-data/fixtures_raw.csv", index=False)
        print("Saved raw fixtures data to fixtures_raw.csv")
        
        # fixtures = clean_fixture_data(fixtures)
        
        # # Continue with your automation
        # html_content = await io.StringIO(tab.content())
        # tables = await pd.read_html(html_content)
        # print(await tables)

asyncio.run(turnstile_example())