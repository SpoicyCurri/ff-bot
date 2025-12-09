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
        df[['home_score', 'away_score']] = df['score'].str.split('–', n=1, expand=True)
        df = df[["gameweek", "home_team", "away_team", "home_xg", "away_xg", 'home_score', 'away_score']]
        df_home = df.rename(columns={
            "home_team": "team",
            "home_xg": "xg",
            "home_score": "goals_scored",
            "away_team": "opponent",
            "away_xg": "xg_against",
            "away_score": "goals_conceded"
        }).assign(home_away="home_team")
        df_away = df.rename(columns={
            "away_team": "team",
            "away_xg": "xg",
            "away_score": "goals_scored",
            "home_team": "opponent",
            "home_xg": "xg_against",
            "home_score": "goals_conceded"
        }).assign(home_away="away_team")
        df = pd.concat([df_home, df_away], ignore_index=True)
        df = df.rename(columns={"gameweek": 'gameweek_number'}).sort_values(['gameweek_number', "team"])

        df['attack_overperformance'] = df['goals_scored'].astype(int) - df['xg']
        df['defence_overperformance'] = df['xg_against'] - df['goals_conceded'].astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error loading team data: {str(e)}")
        return pd.DataFrame()


def sidebar_filters(df):
    # Get the maximum gameweek number
    max_gameweek = df["gameweek_number"].max()
    
    selected_metric = st.sidebar.selectbox(
        "Metric to Compare", config.TEAM_METRICS, index=1,
        key="team_metric_select"
    )
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
    """Get team-level data"""
    max_gameweek = df["gameweek_number"].max()
    recent_data = df[df["gameweek_number"] > (max_gameweek - selections.get('n_weeks'))]

    metric_multiplier = -1 if selections.get('metric') == "xg_against" else 1
    recent_data.loc[:, selections.get('metric')] = recent_data.loc[:, selections.get('metric')].astype(float) * metric_multiplier
    
    # Get total metric for each team to determine top teams
    team_totals = (
        recent_data.groupby("team")[selections.get('metric')]
        .sum()
        .sort_values(ascending=False)
    )
    top_teams = team_totals.head(selections.get('n_players')).index.tolist()
    
    return recent_data, top_teams


def get_team_comparisons(team_data, top_teams, selections):
    """Prepare team comparison data with cumulative metric"""
    comparison_data = []
    
    for team in top_teams:
        team_stats = team_data[team_data["team"] == team].sort_values("gameweek_number")
        team_stats = team_stats.reset_index(drop=True)
        
        # Calculate cumulative sum
        cumulative_metric = team_stats[selections.get('metric')].cumsum()
        
        for idx, row in team_stats.iterrows():
            comparison_data.append({
                "team": team,
                "gameweek": row["gameweek_number"],
                "opponent": row["opponent"],
                "cum value": cumulative_metric[idx],
                "game value": row[selections.get('metric')],
            })
    
    return pd.DataFrame(comparison_data)


def get_comparison_chart(comparison_df, selections):
    # Create a selection for the legend
    selection = alt.selection_point(
        fields=["team"],
        bind='legend'
    )
    metric_name = selections.get('metric')
    
    # Create comparison chart with selectable legend
    comparison_chart = (
        alt.Chart(comparison_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("gameweek:Q", title="Gameweek"),
            y=alt.Y("cum value:Q", title=f"Cumulative {metric_name}"),
            color=alt.Color(
                f"team:N",
                sort=None,
                scale=alt.Scale(scheme=config.CHART_COLOR_SCHEME)
            ),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
            tooltip=["team", "cum value", "opponent", "game value"],
        )
        .properties(height=config.CHART_HEIGHT, title=f"Cumulative {metric_name} Over Time")
        .add_params(selection)
    )
    return comparison_chart


def get_team_summary_stats(team_data, top_teams, selections):
    """Get summary statistics for team data"""
    summary_stats = (
        team_data.groupby("team")[selections.get('metric')]
        .agg(["sum", "mean", "min", "max"])
        .round(2)
    )
    summary_stats.columns = ["Total", "Average", "Worst Game", "Best Game"]
    summary_stats = summary_stats.loc[top_teams]
    
    return summary_stats


def app():
    """Main application function"""
    st.title("⚽FPL Stats - Team Analysis")
    
    df = load_team_data()
    
    # Sidebar filters for teams
    st.sidebar.header("Team Filters")
    selections = sidebar_filters(df)
    
    # Get team data
    team_data, top_teams = get_team_data(df, selections)

    # Display page header
    st.header(f"Top {selections.get('n_players')} Teams - {selections.get('metric')} (Last {selections.get('n_weeks')} Weeks)")
    
    # Team comparison visualisation
    comparison_df = get_team_comparisons(team_data, top_teams, selections)
    comparison_chart = get_comparison_chart(comparison_df, selections)
    st.altair_chart(comparison_chart, use_container_width=True)

    # Team summary statistics
    st.subheader("Summary Statistics")
    summary_stats = get_team_summary_stats(team_data, top_teams, selections)
    st.dataframe(summary_stats.sort_values("Total", ascending=False), width='stretch')


if __name__ == '__main__':
    app()