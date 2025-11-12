import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from config import Config


# Initialize configuration
config = Config()
st.set_page_config(page_title=config.TEAM_TITLE, layout=config.PAGE_LAYOUT)
alt.data_transformers.disable_max_rows()
    
    
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


def sidebar_filters(df):
    # Get the maximum gameweek number
    max_gameweek = df["gameweek_number"].max()
    
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


def app():
    """Main application function"""
    st.title("⚽FPL Stats - Team Analysis")
    
    df = load_team_data()
    
    # Sidebar filters for teams
    st.sidebar.header("Team Filters")
    selections = sidebar_filters(df)
    
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


if __name__ == '__main__':
    app()