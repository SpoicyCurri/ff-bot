import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from config import Config

# Initialize configuration
config = Config()

# Set page config
st.set_page_config(page_title=config.PAGE_TITLE, layout=config.PAGE_LAYOUT)

# Configure Altair to handle larger datasets
alt.data_transformers.disable_max_rows()

# Load data
@st.cache_data
def load_data():
    """Load player summary data and fixture data"""
    try:
        # Load player data
        df = pd.read_csv(config.PLAYERS_FILE)
        # Load fixture data
        fixtures_df = pd.read_csv(config.FIXTURES_FILE)

        # Merge player data with fixture data to get team information and gameweek
        df = pd.merge(
            df, fixtures_df[["game_id", "Home", "Away", "Wk"]], on="game_id", how="left"
        )
        df = df.rename(columns={"Wk": "gameweek_number"})

        # Add team and opponent columns based on home flag
        df["Team"] = np.where(df["home"], df["Home"], df["Away"])
        df["Opponent"] = np.where(df["home"], df["Away"], df["Home"])

        # Add derived statistics
        df["Minutes_Per_Goal"] = df["Min"] / df["Gls"].replace(0, np.nan)
        df["Goal_Involvement"] = df["Gls"] + df["Ast"]
        df["xG_Overperformance"] = df["Gls"] - df["xG"]
        df["Shot_Conversion"] = (df["Gls"] / df["Sh"] * 100).round(1)
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

# Load the data
df = load_data()

if not df.empty:
    st.title("⚽ Premier League Player Statistics")

    # Sidebar filters
    st.sidebar.header("Filters")

    # Comparison settings
    selected_metric = st.sidebar.selectbox(
        "Select Metric to Compare", config.METRICS, index=0
    )
    top_n = st.sidebar.slider(
        "Number of Players to Compare", 
        config.MIN_PLAYERS, 
        config.MAX_PLAYERS, 
        config.DEFAULT_PLAYERS
    )

    # Get the maximum gameweek number
    max_gameweek = df["gameweek_number"].max()
    # Add filter for recent weeks
    recent_weeks = st.sidebar.slider(
        "Consider Last N Weeks", 1, max_gameweek, max_gameweek
    )
    recent_data = df[df["gameweek_number"] > (max_gameweek - recent_weeks)]

    # Get top players for the selected metric in recent weeks
    metric_totals = (
        recent_data.groupby("Player")[selected_metric]
        .sum()
        .sort_values(ascending=False)
    )
    top_players = metric_totals.head(top_n).index.tolist()

    # Display header
    period_text = (
        "All Season"
        if recent_weeks == max_gameweek
        else f"Last {recent_weeks} Weeks"
    )
    st.header(f"Top {top_n} Players - {selected_metric} ({period_text})")
    
    # Prepare comparison data
    comparison_data = []
    
    for player in top_players:
        # Filter for recent weeks first
        player_stats = recent_data[recent_data["Player"] == player]
        player_stats = player_stats.sort_values("gameweek_number")
        
        # Reset index to ensure proper cumulative calculation
        player_stats = player_stats.reset_index(drop=True)
        # Calculate cumulative sum starting from 0 for the selected period
        cumulative_value = player_stats[selected_metric].cumsum()
        
        for idx, row in player_stats.iterrows():
            comparison_data.append({
                "Player": player,
                "Team": row["Team"],
                "Opponent": row["Opponent"],
                "Gameweek": row["gameweek_number"],
                "Value": cumulative_value[idx],
                "Game Value": row[selected_metric],
            })
    
    comparison_df = pd.DataFrame(comparison_data)

    # Create a selection for the legend
    selection = alt.selection_point(
        fields=['Player'],
        bind='legend'
    )
    
    # Create comparison chart with selectable legend
    comparison_chart = (
        alt.Chart(comparison_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Gameweek:Q", title="Gameweek"),
            y=alt.Y("Value:Q", title=f"Cumulative {selected_metric}"),
            color=alt.Color(
                "Player:N",
                sort=None,
                scale=alt.Scale(scheme=config.CHART_COLOR_SCHEME)
            ),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
            tooltip=["Player", "Team", "Opponent", "Value", "Game Value"],
        )
        .properties(height=config.CHART_HEIGHT, title=f"Cumulative {selected_metric} Over Time")
        .add_params(selection)
    )

    st.altair_chart(comparison_chart, use_container_width=True)

    # Show summary statistics
    st.subheader("Summary Statistics")
    summary_stats = (
        recent_data.groupby("Player")
        .agg({selected_metric: ["sum", "mean", "max"]})
        .round(2)
    )
    summary_stats.columns = ["Total", "Average", "Best in Game"]
    summary_stats = summary_stats.loc[top_players]

    # Add per 90 minutes stats
    minutes_played = recent_data.groupby("Player")["Min"].sum()
    summary_stats["Per 90"] = (
        summary_stats["Total"] / minutes_played[top_players] * 90
    ).round(2)
    st.dataframe(
        summary_stats.sort_values("Total", ascending=False), 
        width="stretch"
    )
    
else:
    st.error(
        "No data available. Please check if the data file exists in the data folder."
    )
