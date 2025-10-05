# ⚽ Football Analytics Dashboard

A Python-based analytics dashboard for visualizing and comparing Premier League player statistics. The project consists of two main components:
1. 🤖 A data scraper that collects player statistics from FBRef
2. 📊 A Streamlit web application for interactive data visualization and analysis

## ✨ Features

- Player comparison with customizable metrics
- Individual player analysis with detailed statistics
- Time-based filtering for recent form analysis
- Per 90 minutes statistics
- Interactive visualizations using Altair
- Multiple view types: Goal Involvement, Progression, and Defensive metrics

## 🚀 Setup

This project uses `uv` for Python package management. If you haven't installed `uv` yet, you can get it from: https://github.com/astral-sh/uv

### 📥 Installation

1. Clone the repository:
```bash
git clone [your-repo-url]
cd ff-bot
```

2. Create and activate a new virtual environment using uv:
```bash
uv venv
.venv/Scripts/activate  # On Windows
source .venv/bin/activate  # On Unix/MacOS
```

3. Install dependencies:
```bash
uv pip install pandas numpy playwright streamlit altair
playwright install chromium
```

This will install:
- 🐼 pandas: For data manipulation
- 🔢 numpy: For numerical computations
- 🎭 playwright: For web scraping
- 📊 streamlit: For the web dashboard
- 📈 altair: For interactive visualizations

## 🎮 Usage

### 🤖 Data Scraper

The data scraper uses Playwright to collect player statistics from FBRef. To update the data:

```bash
python data-scraper.py
```

This will:
- 📥 Fetch the latest Premier League fixture data
- 🔄 Update player statistics across 7 categories:
  - Summary stats
  - Passing stats
  - Passing types
  - Defensive actions
  - Possession stats
  - Miscellaneous stats
  - Goalkeeper stats
- 💾 Store the data in CSV format in the `data/` directory
- 📝 Log all operations to `data/fbref_scraper.log`

The scraper includes anti-blocking measures with random delays between requests.

### 📊 Streamlit Dashboard

To run the analytics dashboard:

```bash
streamlit run app.py
```

The dashboard provides two main views:

1. 🔄 Player Comparison
   - 📊 Select from 17 key metrics including:
     - xG, Goals, Assists, xAG
     - Shots, Shots on Target
     - Carries, Progressive Carries/Passes
     - Shot/Goal Creating Actions
     - Defensive metrics (Tackles, Interceptions)
   - 🔢 Customize display (5-20 players)
   - ⏰ Filter by gameweek range
   - 📈 View both cumulative and per-90 statistics
   - 📊 Interactive charts with hover details

2. 👤 Individual Player Analysis
   - 📋 Real-time performance metrics:
     - Match count and minutes played
     - Goals vs xG comparison
     - Assists vs xAG comparison
     - Shot conversion rate
   - 📊 Three detailed analysis tabs:
     - ⚽ Goal Involvement (customizable bar charts)
     - 🎯 Progression (line charts with tooltips)
     - 🛡️ Defensive Actions (area charts)
   - 📝 Complete match history table

## 📁 Data Structure

The scraped data is organized in the following structure:
```
data/
├── fbref_scraper.log        # Detailed scraping logs
├── fixture_data.csv         # Match schedule and results
└── players/                 # Player statistics by category
    ├── players_summary.csv      # Key performance metrics
    ├── players_passing.csv      # Detailed passing stats
    ├── players_passing_types.csv # Pass types analysis
    ├── players_defensive_actions.csv # Defensive metrics
    ├── players_possession.csv    # Ball control stats
    ├── players_miscellaneous.csv # Additional metrics
    └── players_goalkeeper.csv    # Goalkeeper statistics
```

Each player statistics file includes:
- Player identification
- Team information
- Match-specific stats
- Home/Away indicator
- Game ID for fixture linking

## ⚙️ Customization

The dashboard can be customized through several components:

### 📊 Available Metrics
Core metrics available for comparison include:
```python
all_metrics = [
    'xG',    # Expected Goals
    'Gls',   # Goals Scored
    'Ast',   # Assists
    'xAG',   # Expected Assisted Goals
    'Sh',    # Total Shots
    'SoT',   # Shots on Target
    'Min',   # Minutes Played
    'Carries', # Ball Carries
    'PrgC',  # Progressive Carries
    'PrgP',  # Progressive Passes
    'Cmp%',  # Pass Completion %
    'SCA',   # Shot-Creating Actions
    'GCA',   # Goal-Creating Actions
    'Tkl',   # Tackles
    'Int',   # Interceptions
    'Blocks', # Blocks
    'Touches' # Ball Touches
]
```

### 📈 Derived Statistics
The dashboard automatically calculates:
- Minutes per goal
- Goal involvement (Goals + Assists)
- xG overperformance
- Shot conversion rate (%)

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.
