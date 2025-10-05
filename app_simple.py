import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# Set page config
st.set_page_config(page_title="Premier League Player Stats", layout="wide")

# Configure Altair to handle larger datasets
alt.data_transformers.disable_max_rows()

# Load data
@st.cache_data
def load_data():
    """Load player summary data and fixture data"""
    try:
        # Load player data
        df = pd.read_csv('data/players/players_summary.csv')
        # Load fixture data
        fixtures_df = pd.read_csv('data/fixture_data.csv')
        
        # Merge player data with fixture data to get team information and gameweek
        df = pd.merge(df, fixtures_df[['game_id', 'Home', 'Away', 'Wk']], on='game_id', how='left')
        df = df.rename(columns={'Wk': 'gameweek_number'})
        
        # Add team and opponent columns based on home flag
        df['Team'] = np.where(df['home'], df['Home'], df['Away'])
        df['Opponent'] = np.where(df['home'], df['Away'], df['Home'])
        
        # Add derived statistics
        df['Minutes_Per_Goal'] = df['Min'] / df['Gls'].replace(0, np.nan)
        df['Goal_Involvement'] = df['Gls'] + df['Ast']
        df['xG_Overperformance'] = df['Gls'] - df['xG']
        df['Shot_Conversion'] = (df['Gls'] / df['Sh'] * 100).round(1)
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
    
    # View selection
    view_type = st.sidebar.radio("Select View", ["Player Comparison", "Individual Player"], index=0)
    
    if view_type == "Individual Player":
        # Player filter
        players = sorted(df['Player'].unique())
        selected_player = st.sidebar.selectbox("Select Player", players)
    else:
        # Comparison settings
        all_metrics = ['xG', 'Gls', 'Ast', 'xAG', 'Sh', 'SoT', 'Min', 'Carries', 'PrgC', 'PrgP', 
                      'Cmp%', 'SCA', 'GCA', 'Tkl', 'Int', 'Blocks', 'Touches']
        selected_metric = st.sidebar.selectbox("Select Metric to Compare", all_metrics, index=0)
        top_n = st.sidebar.slider("Number of Players to Compare", 5, 20, 10)
        
        # Get the maximum gameweek number
        max_gameweek = df['gameweek_number'].max()
        # Add filter for recent weeks
        recent_weeks = st.sidebar.slider("Consider Last N Weeks", 1, max_gameweek, max_gameweek)
        recent_data = df[df['gameweek_number'] > (max_gameweek - recent_weeks)]
        
        # Get top players for the selected metric in recent weeks
        metric_totals = recent_data.groupby('Player')[selected_metric].sum().sort_values(ascending=False)
        top_players = metric_totals.head(top_n).index.tolist()
        selected_player = None  # No individual player selection in comparison mode
    
    # Show stats based on view type
    if view_type == "Individual Player" and selected_player:
        # Get player data
        player_data = df[df['Player'] == selected_player]
        # Get most recent team
        current_team = player_data.iloc[-1]['Team']
        
        st.header(f"{selected_player} - {current_team}")
        
        # Basic metrics in two rows
        col1, col2, col3, col4 = st.columns(4)
        
        # First row - Match stats
        with col1:
            matches_played = len(player_data)
            total_minutes = player_data['Min'].sum()
            st.metric("Matches Played", matches_played, 
                     delta=f"{total_minutes} mins")
        
        with col2:
            goals = player_data['Gls'].sum()
            xg = player_data['xG'].sum()
            st.metric("Goals", goals, 
                     delta=f"xG: {xg:.1f}")
        
        with col3:
            assists = player_data['Ast'].sum()
            xag = player_data['xAG'].sum()
            st.metric("Assists", assists,
                     delta=f"xAG: {xag:.1f}")
        
        with col4:
            goal_inv = player_data['Goal_Involvement'].sum()
            shots = player_data['Sh'].sum()
            st.metric("Goal Involvements", goal_inv,
                     delta=f"Shots: {shots}")
        
        # Second row - Advanced stats
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            shot_conv = player_data['Shot_Conversion'].mean()
            st.metric("Shot Conversion %", f"{shot_conv:.1f}")
        
        with col6:
            sca = player_data['SCA'].sum()
            gca = player_data['GCA'].sum()
            st.metric("Shot Creating Actions", sca,
                     delta=f"Goal Creating: {gca}")
        
        with col7:
            touches = player_data['Touches'].mean()
            carries = player_data['Carries'].mean()
            st.metric("Avg Touches", f"{touches:.1f}",
                     delta=f"Carries: {carries:.1f}")
        
        with col8:
            prog_carries = player_data['PrgC'].sum()
            prog_passes = player_data['PrgP'].sum()
            st.metric("Progressive Carries", prog_carries,
                     delta=f"Prog Passes: {prog_passes}")
        
        # Performance Analysis
        st.subheader("Performance Analysis")
        
        # Create tabs for different analysis views
        tab1, tab2, tab3 = st.tabs(["Goal Involvement", "Progression", "Defensive"])
        
        with tab1:
            goals_metrics = ['Gls', 'Ast', 'xG', 'xAG', 'Sh', 'SoT']
            selected_goal_metrics = st.multiselect(
                "Select Goal Metrics",
                goals_metrics,
                default=['Gls', 'xG', 'Sh']
            )
        
        with tab2:
            progression_metrics = ['Carries', 'PrgC', 'PrgP', 'Cmp%', 'SCA', 'GCA']
            selected_prog_metrics = st.multiselect(
                "Select Progression Metrics",
                progression_metrics,
                default=['Carries', 'PrgC', 'SCA']
            )
            
        with tab3:
            defensive_metrics = ['Tkl', 'Int', 'Blocks', 'Touches']
            selected_def_metrics = st.multiselect(
                "Select Defensive Metrics",
                defensive_metrics,
                default=['Tkl', 'Int', 'Blocks']
            )
        
        # Create visualizations for each tab
        if selected_goal_metrics:
            with tab1:
                goal_data = player_data.melt(
                    id_vars=['gameweek_number', 'Opponent'],
                    value_vars=selected_goal_metrics,
                    var_name='Metric',
                    value_name='Value'
                )
                
                chart1 = alt.Chart(goal_data).mark_bar().encode(
                    x=alt.X('gameweek_number:O', title='Gameweek'),
                    y=alt.Y('Value:Q'),
                    color='Metric:N',
                    tooltip=['Metric', 'Value', 'Opponent']
                ).properties(
                    height=400,
                    title="Goal Involvement Metrics"
                ).interactive()
                
                st.altair_chart(chart1, use_container_width=True)
        
        if selected_prog_metrics:
            with tab2:
                prog_data = player_data.melt(
                    id_vars=['gameweek_number', 'Opponent'],
                    value_vars=selected_prog_metrics,
                    var_name='Metric',
                    value_name='Value'
                )
                
                chart2 = alt.Chart(prog_data).mark_line(point=True).encode(
                    x=alt.X('gameweek_number:O', title='Gameweek'),
                    y=alt.Y('Value:Q'),
                    color='Metric:N',
                    tooltip=['Metric', 'Value']
                ).properties(
                    height=400,
                    title="Progression Metrics"
                ).interactive()
                
                st.altair_chart(chart2, use_container_width=True)
                
        if selected_def_metrics:
            with tab3:
                def_data = player_data.melt(
                    id_vars=['gameweek_number', 'Opponent'],
                    value_vars=selected_def_metrics,
                    var_name='Metric',
                    value_name='Value'
                )
                
                chart3 = alt.Chart(def_data).mark_area(opacity=0.5).encode(
                    x=alt.X('gameweek_number:O', title='Gameweek'),
                    y=alt.Y('Value:Q'),
                    color='Metric:N',
                    tooltip=['Metric', 'Value']
                ).properties(
                    height=400,
                    title="Defensive Metrics"
                ).interactive()
                
                st.altair_chart(chart3, use_container_width=True)
        
        # Show match history
        st.subheader("Match History")
        cols_to_show = ['Team', 'Opponent', 'Min', 'Gls', 'Ast', 'CrdY', 'CrdR', 'xG', 'xAG']
        formatted_data = player_data[cols_to_show].sort_values('Min', ascending=False)
        st.dataframe(formatted_data, width='stretch')
        
        # End of player analysis section
    
    elif view_type == "Player Comparison":
        period_text = "All Season" if recent_weeks == max_gameweek else f"Last {recent_weeks} Weeks"
        st.header(f"Top {top_n} Players - {selected_metric} ({period_text})")
        
        # Create comparison dataframe
        comparison_data = []
        for player in top_players:
            player_stats = df[df['Player'] == player]
            # Filter for recent weeks
            player_stats = player_stats[player_stats['gameweek_number'] > (max_gameweek - recent_weeks)]
            player_stats = player_stats.sort_values('gameweek_number')
            # Calculate cumulative sum for the metric within the selected period
            cumulative_value = player_stats[selected_metric].cumsum()
            for idx, row in player_stats.iterrows():
                comparison_data.append({
                    'Player': player,
                    'Team': row['Team'],
                    'Opponent': row['Opponent'],
                    'Gameweek': row['gameweek_number'],
                    'Value': cumulative_value[idx],
                    'Game Value': row[selected_metric]  # Individual game value for tooltip
                })
        comparison_df = pd.DataFrame(comparison_data)
        
        # Create comparison chart
        comparison_chart = alt.Chart(comparison_df).mark_line(point=True).encode(
            x=alt.X('Gameweek:O', title='Gameweek'),
            y=alt.Y('Value:Q', title=f'Cumulative {selected_metric}'),
            color=alt.Color('Player:N', sort=None),
            tooltip=['Player', 'Team', 'Opponent', 'Value', 'Game Value']
        ).properties(
            height=500,
            title=f"Cumulative {selected_metric} Over Time"
        ).interactive()
        
        st.altair_chart(comparison_chart, use_container_width=True)
        
        # Show summary statistics
        st.subheader("Summary Statistics")
        summary_stats = recent_data.groupby('Player').agg({
            selected_metric: ['sum', 'mean', 'max']
        }).round(2)
        summary_stats.columns = ['Total', 'Average', 'Best in Game']
        summary_stats = summary_stats.loc[top_players]
        
        # Add per 90 minutes stats
        minutes_played = recent_data.groupby('Player')['Min'].sum()
        summary_stats['Per 90'] = (summary_stats['Total'] / minutes_played[top_players] * 90).round(2)
        st.dataframe(summary_stats.sort_values(('Total'), ascending=False), width='stretch')
        
else:
    st.error("No data available. Please check if the data file exists in the data folder.")