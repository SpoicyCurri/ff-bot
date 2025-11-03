import requests
import pandas as pd
from rapidfuzz import fuzz, process

URL="https://fantasy.premierleague.com/api/bootstrap-static/"
COLUMNS = {
    'code': 'player_code',
    'element_type': 'position',
    'first_name': 'first_name',
    'second_name': 'last_name',
    'now_cost': 'fpl_cost',
    'form': 'fpl_form',
    'points_per_game': 'season_ppg',
    'total_points': 'total_points'
}
POSITIONS = {
    1: 'GK',
    2: 'DEF',
    3: 'MID',
    4: 'FWD'
}
PLAYER_NAME_MANUAL = {
    # 'FPL Name': 'FBRef Name'
    'Yéremy Pino Santos': 'Yeremi Pino',
    'Endo Wataru': 'Wataru Endo',
    'Carlos Henrique Casimiro': 'Casimiro',
    'Mitoma Kaoru': 'Kaoru Mitoma',
    'Kevin Santos Lopes de Macedo': 'Kevin',
    "Rodrigo 'Rodri' Hernandez Cascante": 'Rodri',
    'Igor Thiago Nascimento Rodrigues': 'Thiago',
    'Lucas Tolentino Coelho de Lima': 'Lucas Paquetá',
    'Murillo Costa dos Santos': 'Murillo',
    'Felipe Rodrigues da Silva': 'Morato',
    'André Trindade da Costa Neto': 'André',
    'Igor Julio dos Santos de Paulo': 'Igor',
    'Sávio Moreira de Oliveira': 'Sávio',
    'Norberto Bercique Gomes Betuncal': 'Beto',
    'João Pedro Ferreira da Silva': 'Jota Silva'
}


def get_fbref():
    filename= "data\players\players_summary.csv"
    df = pd.read_csv(filename)
    df = df[['Player']].drop_duplicates().reset_index(drop=True)
    return df


def get_fpl_data():
    response = requests.get(URL)
    data = response.json()
    players = data['elements']
    df = pd.DataFrame(players)
    df.to_csv("ref__all_fpl_datas.csv", index=False)
    
    df = df[COLUMNS.keys()]
    df = df.rename(columns=COLUMNS)
    df['position'] = df['position'].map(POSITIONS)
    df['fpl_cost'] = df['fpl_cost'] / 10
    df['fullname'] = df['first_name'] + ' ' + df['last_name']
    
    df = df[df['total_points'] > 0]
    
    return df


def print_comparison_metrics(df, fuzzy_df):
    rows = df.shape[0]
    exact_matches = df['Player'].notnull().sum()
    fuzzy_matches = fuzzy_df['Manual Override'].isnull().sum()
    manual_matches = fuzzy_df['Manual Override'].notnull().sum()
    
    print(f"Total players: {rows}")
    print(f"Exact matches: {exact_matches}; {exact_matches/rows:.1%}")
    print(f"Fuzzy matches: {fuzzy_matches}; {fuzzy_matches/rows:.1%}")
    print(f"Manual matches: {manual_matches}; {manual_matches/rows:.1%}")
    return None


def suggest_fuzzy_matches(df_fpl, df_fbref, threshold=80):
    """
    Perform fuzzy matching between FPL and FBRef player names
    """
    fbref_names = df_fbref['Player'].tolist()
    
    matches = []
    for _, fpl_name in enumerate(df_fpl['fullname']):
        # Get best match
        best_match = process.extractOne(
            fpl_name, 
            fbref_names,
            scorer=fuzz.ratio
        )
        
        if best_match and best_match[1] >= threshold:
            matches.append({
                'fpl_name': fpl_name,
                'fbref_name': best_match[0],
                'score': best_match[1]
            })
        else:
            matches.append({
                'fpl_name': fpl_name,
                'fbref_name': None,
                'score': 0
            })
            
    best_matches_df = pd.DataFrame(matches)
    best_matches_df['Manual Override'] = best_matches_df['fpl_name'].map(PLAYER_NAME_MANUAL)
    best_matches_df = best_matches_df.sort_values(by='score', ascending=False)
    best_matches_df.to_csv("fuzzy_matches_debug.csv", index=False)
    return best_matches_df


def main():
    df_fbref = get_fbref()
    df_fpl = get_fpl_data()
    df = pd.merge(df_fbref, df_fpl, left_on='Player', right_on='fullname', how='right')
    missing_players = df[df['Player'].isnull()]
    best_matches_df = suggest_fuzzy_matches(missing_players, df_fbref, threshold=30)
    print_comparison_metrics(df, best_matches_df)
    
    df = pd.merge(
        df,
        best_matches_df[['fpl_name', 'fbref_name', 'Manual Override']],
        left_on='fullname',
        right_on='fpl_name',
        how='left'
    )
    df['name_match'] = df['Player'].combine_first(df['Manual Override']).combine_first(df['fbref_name'])

    df = df[['name_match'] + list(COLUMNS.values())]

    return df


if __name__ == "__main__":
    df = main()
    df.to_csv("fpl_players.csv", index=False)