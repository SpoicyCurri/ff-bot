# ⚽ Fantasy Football Analytics Dashboard

A Python-based analytics dashboard for visualizing and comparing Premier League player statistics. The project consists of three main components:
1. 🤖 A data scraper that collects player statistics from FBRef
2. 🤖 A data scraper that collects player statistics from Fantasy Premier League
3. 📊 A Streamlit web application for interactive data visualization and analysis

The app is live and hosted on the Streamlit cloud: https://ff-bot-spoicycurri.streamlit.app/

## ✨ Features

- Automated data scraping! via GitHub Actions at 7am each morning
- Player comparisons: Who has best trending xG?
- Team comparisons: Who has best trending defence?
- Filter players by FPL price and position

## 🚀 Setup

This project uses `uv` for Python package management. If you haven't installed `uv` yet, you can get it from: https://github.com/astral-sh/uv

### 📥 Installation

1. Clone the repository:
```bash
git clone https://github.com/SpoicyCurri/ff-bot.git
cd ff-bot
```

2. Create and activate a new virtual environment using uv:
```bash
uv sync --only-dev 
.venv/Scripts/activate
```

This will install all packages:
- 🐼 pandas: For data manipulation
- ?? rapidfuzz: For data matching
- 🎭 pydoll: For web scraping
- 📊 streamlit: For the web dashboard
- 📈 altair: For interactive visualizations

## 🎮 Usage

### 🤖 Data Scraper

The data scraper uses [Pydoll](https://pydoll.tech/docs/) to navigate FBRef and collect player statistics. To update the data manually:

```bash
uv run scripts/data-scraper.py
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
- 💾 Store the data in CSV format in the `data/` directory, ready to be used by the live application.

The FPL data is extracted from the fantasy premier league api via requests. To update manually:

```bash
uv run scripts/fpl-players.py
```

### 📊 Streamlit Dashboard

To run the analytics dashboard:

```bash
uv run streamlit run app.py
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
   - 📊 Interactive charts with hover details

2. 👤 Team Comparison
  - Team defensive performances via cumulative xG Conceded

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.
