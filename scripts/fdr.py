"""
A script to generate fixture difficulty ratings for each team. Using team xG to estimate an attacking rating and xG conceded for defensive rating. Then providing a normalised difficulty score for each fixture based on opponent strength.
"""
import pandas as pd
import altair as alt

def main():
    # Load fixture data
    fixtures_df = pd.read_csv("data/fixture_data.csv")
    
    # Standardise data
    home_teams = fixtures_df[['Wk', 'Home', 'xG Home', 'xG Away']].rename(columns={
        'Home': 'Team',
        'xG Home': 'xG',
        'xG Away': 'xGA'
    })
    away_teams = fixtures_df[['Wk', 'Away', 'xG Home', 'xG Away']].rename(columns={
        'Away': 'Team',
        'xG Home': 'xGA',
        'xG Away': 'xG'
    })
    team_stats = pd.concat([home_teams, away_teams], ignore_index=True)

    # Calculate attacking and defensive ratings
    team_stats = team_stats.groupby('Team').agg({
        'xG': 'mean',
        'xGA': 'mean'
    }).rename(columns={'xG': 'Attacking_Rating', 'xGA': 'Defensive_Rating'}).reset_index()

    # Normalize ratings
    team_stats['Attacking_Rating_Norm'] = (team_stats['Attacking_Rating'] - team_stats['Attacking_Rating'].min()) / (team_stats['Attacking_Rating'].max() - team_stats['Attacking_Rating'].min())
    team_stats['Defensive_Rating_Norm'] = (team_stats['Defensive_Rating'].max() - team_stats['Defensive_Rating']) / (team_stats['Defensive_Rating'].max() - team_stats['Defensive_Rating'].min())


    # Calculate difficulty ratings
    # team_stats['Fixture_Difficulty'] = (team_stats['Defensive_Rating_Norm'] + (1 - team_stats['Attacking_Rating_Norm_Opponent'])) / 2

    # Save the updated fixture data with difficulty ratings
    team_stats.to_csv("data/fdr.csv", index=False)
    
    # fdr_plot
    fdr_plot = alt.Chart(team_stats).mark_point().encode(
        x='Defensive_Rating_Norm',
        y='Attacking_Rating_Norm',
        text='Team',
        tooltip=['Team', 'Attacking_Rating_Norm', 'Attacking_Rating', 'Defensive_Rating_Norm', 'Defensive_Rating']
    )

    # Add dashed lines at x=0.5 and y=0.5
    x_rule = alt.Chart(pd.DataFrame({'x': [0.5]})).mark_rule(strokeDash=[5,5], color='gray').encode(x='x')
    y_rule = alt.Chart(pd.DataFrame({'y': [0.5]})).mark_rule(strokeDash=[5,5], color='gray').encode(y='y')

    fdr_plot = (fdr_plot + x_rule + y_rule).properties(
        title='Fixture Difficulty Ratings by Team',
        width=600,
        height=600
    )
    fdr_plot.save("figures/team_quality_ratings.html")
    
    
    fdr_plot = alt.Chart(team_stats).mark_bar().encode(
        x='Attacking_Rating_Norm',
        y=alt.Y('Team', sort='-x'),
        tooltip=['Team', 'Attacking_Rating_Norm', 'Attacking_Rating']
    ).properties(
        title='Attacking Ratings by Team',
        width=600,
        height=600
    )
    fdr_plot.save("figures/team_attack_ratings.html")

    print("Fixture difficulty ratings calculated and saved.")

if __name__ == "__main__":
    main()