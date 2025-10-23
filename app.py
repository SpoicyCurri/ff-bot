import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from config import Config


# Initialize configuration
config = Config()
st.set_page_config(page_title=config.PAGE_TITLE, layout=config.PAGE_LAYOUT)
alt.data_transformers.disable_max_rows()


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


def sidebar_filters(df):
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
    selections = {
        'metric': selected_metric,
        'n_players': top_n,
        'n_weeks': recent_weeks
    }
    return selections


def get_selected_data(df, selections):
    max_gameweek = df["gameweek_number"].max()
    recent_data = df[df["gameweek_number"] > (max_gameweek - selections.get('n_weeks'))]
    metric_totals = (
        recent_data.groupby("Player")[selections.get('metric')]
        .sum()
        .sort_values(ascending=False)
    )
    top_players = metric_totals.head(selections.get('n_players')).index.tolist()
    return recent_data, top_players


def get_player_comparisons(recent_data, top_players, selections):
    # Prepare comparison data
    comparison_data = []
    
    for player in top_players:
        # Filter for recent weeks first
        player_stats = recent_data[recent_data["Player"] == player]
        player_stats = player_stats.sort_values("gameweek_number")
        
        # Reset index to ensure proper cumulative calculation
        player_stats = player_stats.reset_index(drop=True)
        # Calculate cumulative sum starting from 0 for the selected period
        cumulative_value = player_stats[selections.get('metric')].cumsum()
        
        for idx, row in player_stats.iterrows():
            comparison_data.append({
                "Player": player,
                "Team": row["Team"],
                "Opponent": row["Opponent"],
                "Gameweek": row["gameweek_number"],
                "Value": cumulative_value[idx],
                "Game Value": row[selections.get('metric')],
            })
    
    comparison_df = pd.DataFrame(comparison_data)
    
    return comparison_df


def get_comparison_chart(comparison_df, selections):
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
            y=alt.Y("Value:Q", title=f"Cumulative {selections.get('metric')}"),
            color=alt.Color(
                "Player:N",
                sort=None,
                scale=alt.Scale(scheme=config.CHART_COLOR_SCHEME)
            ),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
            tooltip=["Player", "Team", "Opponent", "Value", "Game Value"],
        )
        .properties(height=config.CHART_HEIGHT, title=f"Cumulative {selections.get('metric')} Over Time")
        .add_params(selection)
    )
    return comparison_chart


def get_summary_stats(recent_data, top_players, selections):
    summary_stats = (
        recent_data.groupby("Player")
        .agg({selections.get('metric'): ["sum", "mean", "max"]})
        .round(2)
    )
    summary_stats.columns = ["Total", "Average", "Best in Game"]
    summary_stats = summary_stats.loc[top_players]

    # Add per 90 minutes stats
    minutes_played = recent_data.groupby("Player")["Min"].sum()
    summary_stats["Per 90"] = (
        summary_stats["Total"] / minutes_played[top_players] * 90
    ).round(2)
    return summary_stats


def app():
    st.title("⚽ Premier League Player Statistics")
    
    # Load all data
    df = load_data()

    # Sidebar filters
    st.sidebar.header("Filters")
    selections = sidebar_filters(df)
    
    # Get selected data
    recent_data, top_players = get_selected_data(df, selections)

    # Display page header
    st.header(f"Top {selections.get('n_players')} Players - {selections.get('metric')} (Last {selections.get('n_weeks')} Weeks)")
    
    # Player comparison visualisation
    comparison_df = get_player_comparisons(recent_data, top_players, selections)
    comparison_chart = get_comparison_chart(comparison_df, selections)
    st.altair_chart(comparison_chart, use_container_width=True)

    # PLayer summary statistics
    st.subheader("Summary Statistics")
    summary_stats = get_summary_stats(recent_data, top_players, selections)
    st.dataframe(summary_stats.sort_values("Total", ascending=False), width="stretch")


if __name__ == '__main__':
    app()