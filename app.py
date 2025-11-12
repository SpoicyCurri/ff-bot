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
def load_player_data():
    """Load player summary data and fixture data"""
    try:
        # Load player data
        df = pd.read_csv(config.PLAYERS_FILE)
        # Load fixture data
        fixtures_df = pd.read_csv(config.FIXTURES_FILE)
        # Load FPL data
        fpl_df = pd.read_csv(config.FPL_FILE)

        # Merge player data with fixture data to get team information and gameweek
        df = pd.merge(
            df, fixtures_df[["game_id", "home_team", "away_team", "gameweek"]], on="game_id", how="left"
        )
        df = df.rename(columns={"gameweek": "gameweek_number"})

        # Merge with FPL data to get additional player info
        df = df.drop(columns=["position"], errors="ignore")
        df = pd.merge(df, fpl_df[["fbref_name", 'position', 'fpl_cost']], left_on="player", right_on="fbref_name", how="inner")

        # Add team and opponent columns based on home flag
        df["team"] = np.where(df["home"], df["home_team"], df["away_team"])
        df["opponent"] = np.where(df["home"], df["away_team"], df["home_team"])

        # Add derived statistics
        df['Defensive Contributions'] = df['tackles'] + df['interceptions'] + df['blocks']
        df['xGI'] = df["xg"] + df["xg_assist"]
        df["Minutes_Per_Goal"] = df["minutes"] / df["goals"].replace(0, np.nan)
        df["Goal_Involvement"] = df["goals"] + df["assists"]
        df["xG_Overperformance"] = df["goals"] - df["xg"]
        df["Shot_Conversion"] = (df["goals"] / df["shots"] * 100).round(1)
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()
    
    
@st.cache_data
def load_team_data():
    """Load team-level data"""
    try:
        df = pd.read_csv(config.FIXTURES_FILE)
        df = df[df['game_played']]
        df = df[["gameweek", "home_team", "home_xg", "away_team", "away_xg"]]
        df_home = df[["gameweek", "home_team", "home_xg", "away_xg"]].rename(columns={
            "home_team": "team",
            "home_xg": "xg",
            "away_xg": "xg_against"
        }).assign(home_away="home_team")
        df_away = df[["gameweek", "away_team", "home_xg", "away_xg"]].rename(columns={
            "away_team": "team",
            "away_xg": "xg",
            "home_xg": "xg_against"
        }).assign(home_away="away_team")
        df = pd.concat([df_home, df_away], ignore_index=True)
        df = df.rename(columns={"gameweek": 'gameweek_number'}).sort_values(['gameweek_number', "team"])
        return df
    except Exception as e:
        st.error(f"Error loading team data: {str(e)}")
        return pd.DataFrame()


def sidebar_filters(df, is_team_tab=False):
    # Get the maximum gameweek number
    max_gameweek = df["gameweek_number"].max()
    
    # Comparison settings
    if is_team_tab:
        selected_metric = "xg_against"  # Fixed metric for team tab
        st.sidebar.write("**Metric:** xG Conceded")
        top_n = st.sidebar.slider(
            "Number of Teams to Compare", 
            5, 
            20, 
            10,
            key="team_slider_n"
        )
        recent_weeks = st.sidebar.slider(
            "Consider Last N Weeks", 1, max_gameweek, max_gameweek,
            key="team_weeks_slider"
        )

        return {
            'metric': selected_metric,
            'n_players': top_n,
            'n_weeks': recent_weeks
            }
    
    else:
        selected_metric = st.sidebar.selectbox(
            "Select Metric to Compare", config.METRICS, index=0,
            key="player_metric_select"
        )
        top_n = st.sidebar.slider(
            "Number of Players to Compare", 
            config.MIN_PLAYERS, 
            config.MAX_PLAYERS, 
            config.DEFAULT_PLAYERS,
            key="player_slider_n"
        )
        recent_weeks = st.sidebar.slider(
            "Consider Last N Weeks", 1, max_gameweek, max_gameweek,
            key="player_weeks_slider"
        )
        fpl_position = st.sidebar.selectbox(
            "Select FPL Position", 
            config.FPL_POSITIONS,
            index=0,
            key="player_position_select"
        )
        fpl_price = st.sidebar.slider(
            "Maximum FPL Price", 
            df["fpl_cost"].min(), 
            df["fpl_cost"].max(),
            df["fpl_cost"].max(),
            step=0.1,
            key="player_price_select"
        )

        return {
            'metric': selected_metric,
            'n_players': top_n,
            'n_weeks': recent_weeks,
            'fpl_position': fpl_position,
            'fpl_price': fpl_price
            }


def get_selected_data(df, selections):
    df = df[df['position'] == selections.get('fpl_position')]
    df = df[df['fpl_cost'] <= selections.get('fpl_price')]
    max_gameweek = df["gameweek_number"].max()
    recent_data = df[df["gameweek_number"] > (max_gameweek - selections.get('n_weeks'))]
    metric_totals = (
        recent_data.groupby("player")[selections.get('metric')]
        .sum()
        .sort_values(ascending=False)
    )
    top_players = metric_totals.head(selections.get('n_players')).index.tolist()
    return recent_data, top_players


def get_team_data(df, selections):
    """Get team-level xG conceded data"""
    max_gameweek = df["gameweek_number"].max()
    recent_data = df[df["gameweek_number"] > (max_gameweek - selections.get('n_weeks'))]
    recent_data.loc[:, "xg_against"] = recent_data.loc[:, "xg_against"].astype(float) * -1
    
    # Get total xGA for each team to determine top teams
    team_totals = (
        recent_data.groupby("team")["xg_against"]
        .sum()
        .sort_values(ascending=False)
    )
    top_teams = team_totals.head(selections.get('n_players')).index.tolist()
    
    return recent_data, top_teams


def get_player_comparisons(recent_data, top_players, selections):
    # Prepare comparison data
    comparison_data = []
    
    for player in top_players:
        # Filter for recent weeks first
        player_stats = recent_data[recent_data["player"] == player]
        player_stats = player_stats.sort_values("gameweek_number")
        
        # Reset index to ensure proper cumulative calculation
        player_stats = player_stats.reset_index(drop=True)
        # Calculate cumulative sum starting from 0 for the selected period
        cumulative_value = player_stats[selections.get('metric')].cumsum()
        
        for idx, row in player_stats.iterrows():
            comparison_data.append({
                "player": player,
                "team": row["team"],
                "opponent": row["opponent"],
                "gameweek": row["gameweek_number"],
                "value": cumulative_value[idx],
                "game value": row[selections.get('metric')],
            })
    
    comparison_df = pd.DataFrame(comparison_data)
    
    return comparison_df


def get_team_comparisons(team_xga, top_teams):
    """Prepare team comparison data with cumulative xG conceded"""
    comparison_data = []
    
    for team in top_teams:
        team_stats = team_xga[team_xga["team"] == team].sort_values("gameweek_number")
        team_stats = team_stats.reset_index(drop=True)
        
        # Calculate cumulative sum
        cumulative_xga = team_stats["xg_against"].cumsum()
        
        for idx, row in team_stats.iterrows():
            comparison_data.append({
                "team": team,
                "gameweek": row["gameweek_number"],
                "value": cumulative_xga[idx],
                "game value": row["xg_against"],
            })
    
    return pd.DataFrame(comparison_data)


def get_comparison_chart(comparison_df, selections, is_team_tab=False):
    # Create a selection for the legend
    selection = alt.selection_point(
        fields=["team" if is_team_tab else "player"],
        bind='legend'
    )
    
    entity_field = "team" if is_team_tab else "player"
    metric_name = "xG Conceded" if is_team_tab else selections.get('metric')
    
    # Create comparison chart with selectable legend
    comparison_chart = (
        alt.Chart(comparison_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("gameweek:Q", title="Gameweek"),
            y=alt.Y("value:Q", title=f"Cumulative {metric_name}"),
            color=alt.Color(
                f"{entity_field}:N",
                sort=None,
                scale=alt.Scale(scheme=config.CHART_COLOR_SCHEME)
            ),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
            tooltip=[entity_field, "value", "game value"] if is_team_tab 
                    else ["player", "team", "opponent", "value", "game value"],
        )
        .properties(height=config.CHART_HEIGHT, title=f"Cumulative {metric_name} Over Time")
        .add_params(selection)
    )
    return comparison_chart


def get_summary_stats(recent_data, top_players, selections):
    summary_stats = (
        recent_data.groupby("player")
        .agg({selections.get('metric'): ["sum", "mean", "max"]})
        .round(2)
    )
    summary_stats.columns = ["Total", "Average", "Best in Game"]
    summary_stats = summary_stats.loc[top_players]

    # Add per 90 minutes stats
    minutes_played = recent_data.groupby("player")["minutes"].sum()
    summary_stats["Per 90"] = (
        summary_stats["Total"] / minutes_played[top_players] * 90
    ).round(2)
    return summary_stats


def get_team_summary_stats(team_xga, top_teams):
    """Get summary statistics for team xG conceded"""
    summary_stats = (
        team_xga.groupby("team")["xg_against"]
        .agg(["sum", "mean", "max"])
        .round(2)
    )
    summary_stats.columns = ["Total", "Average", "Worst in Game"]
    summary_stats = summary_stats.loc[top_teams]
    
    # Calculate per game average
    games_played = team_xga.groupby("team").size()
    summary_stats["Per Game"] = (
        summary_stats["Total"] / games_played[top_teams]
    ).round(2)
    
    return summary_stats


def player_tab(df):
    """Player analysis tab content"""
    # Sidebar filters
    selections = sidebar_filters(df, is_team_tab=False)
    
    # Get selected data
    recent_data, top_players = get_selected_data(df, selections)

    # Display page header
    st.header(f"Top {selections.get('n_players')} {selections.get('fpl_position')}s - {selections.get('metric')} (Last {selections.get('n_weeks')} Weeks)")
    
    # Player comparison visualisation
    comparison_df = get_player_comparisons(recent_data, top_players, selections)
    comparison_chart = get_comparison_chart(comparison_df, selections, is_team_tab=False)
    st.altair_chart(comparison_chart, use_container_width=True)

    # Player summary statistics
    st.subheader("Summary Statistics")
    summary_stats = get_summary_stats(recent_data, top_players, selections)
    st.dataframe(summary_stats.sort_values("Total", ascending=False), width='stretch')


def teams_tab(df):
    """Team xG conceded analysis tab content"""
    # Sidebar filters for teams
    selections = sidebar_filters(df, is_team_tab=True)
    
    # Get team data
    team_xga, top_teams = get_team_data(df, selections)

    # Display page header
    st.header(f"Top {selections.get('n_players')} Teams - xG Conceded (Last {selections.get('n_weeks')} Weeks)")
    
    # Team comparison visualisation
    comparison_df = get_team_comparisons(team_xga, top_teams)
    comparison_chart = get_comparison_chart(comparison_df, selections, is_team_tab=True)
    st.altair_chart(comparison_chart, use_container_width=True)

    # Team summary statistics
    st.subheader("Summary Statistics")
    summary_stats = get_team_summary_stats(team_xga, top_teams)
    st.dataframe(summary_stats.sort_values("Total", ascending=False), width='stretch')



def app():
    st.title("⚽ Fantasy Premier League Analysis")
    
    # Load all data
    df = load_player_data()
    df_team = load_team_data()
    
    # Create tabs
    tab1, tab2 = st.tabs(["Player Comps", "Team Comps"])
    
    with tab1:
        st.sidebar.header("Player Filters")
        player_tab(df)
    
    with tab2:
        st.sidebar.header("Team Filters")
        teams_tab(df_team)


if __name__ == '__main__':
    app()