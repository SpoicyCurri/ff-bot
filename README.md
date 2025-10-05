# ⚽ Football Analytics Dashboard

A Python-based analytics dashboard for visualizing and comparing Prem

Feel free to submit issues, fork the repository, and create pull requests for any improvements! League player statistics. The project consists of two main components:
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
uv pip install -r requirements.txt
```

## 🎮 Usage

### 🤖 Data Scraper

The data scraper collects player statistics from FBRef. To update the data:

```bash
python data-scraper.py
```

This will:
- 📥 Fetch the latest fixture data
- 🔄 Update player statistics across multiple categories
- 💾 Store the data in the `data/` directory

### 📊 Streamlit Dashboard

To run the analytics dashboard:

```bash
streamlit run app_simple.py
```

The dashboard provides two main views:

1. 🔄 Player Comparison
   - 📊 Select metrics to compare (xG, Goals, Assists, etc.)
   - 🔢 Choose number of players to display
   - ⏰ Filter by recent weeks
   - 📈 View cumulative statistics and per 90 metrics

2. 👤 Individual Player Analysis
   - 📋 Detailed player statistics
   - 📊 Performance breakdowns by different metrics
   - 📝 Match history
   - 📈 Interactive charts for:
     - ⚽ Goal involvement
     - 🎯 Progressive actions
     - 🛡️ Defensive contributions

## 📁 Data Structure

The scraped data is organized in the following structure:
```
data/
├── fixture_data.csv
└── players/
    ├── players_summary.csv
    ├── players_passing.csv
    ├── players_defensive_actions.csv
    ├── players_possession.csv
    ├── players_miscellaneous.csv
    └── players_goalkeeper.csv
```

## ⚙️ Customization

You can modify the metrics displayed in the dashboard by editing the `all_metrics` list in `app_simple.py`. The current metrics include:
- 🎯 Expected Goals (xG)
- ⚽ Goals (Gls)
- 🎯 Assists (Ast)
- 📊 Expected Assisted Goals (xAG)
- 🎯 Shots (Sh)
- 🎯 Shots on Target (SoT)
- And many more...

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.
