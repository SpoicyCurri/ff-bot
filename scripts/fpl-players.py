import requests
import pandas as pd
from rapidfuzz import fuzz, process
from pathlib import Path

print(Path.cwd())

DATA_DIR = Path.cwd() / "data"
FBREF_FILE = DATA_DIR / "players_v2" / "players_summary.csv"
FPL_DIR = DATA_DIR / "fpl"
FPL_FILE = FPL_DIR / "fpl_players.csv"
REF_ALL_FPL_DATAS = FPL_DIR / "ref__all_fpl_datas.csv"
REFERENCE_PLAYER_NAMES = FPL_DIR / "reference_player_names.csv"
FUZZY_MATCHES_DEBUG = FPL_DIR / "fuzzy_matches_debug.csv"

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
UPDATE_REF=False


def get_fbref():
    df = pd.read_csv(FBREF_FILE)
    df = df[['player']].drop_duplicates().reset_index(drop=True)
    return df


def get_fpl_data():
    response = requests.get(URL)
    data = response.json()
    players = data['elements']
    df = pd.DataFrame(players)
    df.to_csv(REF_ALL_FPL_DATAS, index=False)
    
    df = df[COLUMNS.keys()]
    df = df.rename(columns=COLUMNS)
    df['position'] = df['position'].map(POSITIONS)
    df['fpl_cost'] = df['fpl_cost'] / 10
    df['fullname'] = df['first_name'] + ' ' + df['last_name']
    
    df = df[df['total_points'] > 0]
    
    return df


def get_ref_data():
    try:
        return pd.read_csv(REFERENCE_PLAYER_NAMES)
    except FileNotFoundError:
        return pd.DataFrame(columns=['player_code', 'fbref_name', 'fpl_name'])


def print_comparison_metrics(df):
    rows = df.shape[0]
    exact_matches = df['player'].notnull().sum()
    fuzzy_matches = df['Manual Override'].isnull().sum() - exact_matches
    manual_matches = df['Manual Override'].notnull().sum()
    missing_matches = df[df['name_match'].isnull()]['fpl_name'].tolist()
    
    print(f"Total players: {rows}")
    print(f"Exact matches: {exact_matches}; {exact_matches/rows:.1%}")
    print(f"Fuzzy matches: {fuzzy_matches}; {fuzzy_matches/rows:.1%}")
    print(f"Manual matches: {manual_matches}; {manual_matches/rows:.1%}")
    print(f"missing matches: {len(missing_matches)}; {len(missing_matches)/rows:.1%}; {missing_matches}")
    return None


def suggest_fuzzy_matches(fpl_names, fbref_names, threshold=80):
    """
    Perform fuzzy matching between FPL and FBRef player names
    """

    matches = []
    for _, fpl_name in enumerate(fpl_names):
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
    return pd.DataFrame(matches)


def update_reference_names(exact_matches):
    # Fuzzy Matches
    fuzzy_matches = pd.read_csv(FUZZY_MATCHES_DEBUG)
    
    # Combine new matches
    new_matches = pd.merge(
        exact_matches,
        fuzzy_matches[['fpl_name', 'fbref_name', 'Manual Override']],
        left_on='fullname',
        right_on='fpl_name',
        how='left'
    )
    new_matches['name_match'] = new_matches['player'].combine_first(new_matches['Manual Override']).combine_first(new_matches['fbref_name'])
    
    print_comparison_metrics(new_matches)

    new_matches = new_matches[['player_code', 'name_match', 'fullname']]
    new_matches = new_matches.rename(columns={
        'name_match': 'fbref_name',
        'fullname': 'fpl_name'
    })

    # Update reference file
    ref_names = get_ref_data()
    ref_names_new = pd.concat([ref_names, new_matches], ignore_index=True)
    ref_names_new.to_csv(REFERENCE_PLAYER_NAMES, index=False)
    
    return None


def match_player_names(df_fpl):
    df_fbref = get_fbref()
    df_fpl_missing = df_fpl.loc[df_fpl['fbref_name'].isnull(), ['player_code', 'fullname']]
    
    # Exact Matches
    df = pd.merge(df_fbref, df_fpl_missing, left_on='player', right_on='fullname', how='right')
    
    # Fuzzy Matches
    no_matches = df[df['player'].isnull()]['fullname']
    fbref_names = df_fbref['player'].tolist()
    fuzzy_matches = suggest_fuzzy_matches(no_matches, fbref_names, threshold=30)
    
    # Manual Override
    fuzzy_matches['Manual Override'] = fuzzy_matches['fpl_name'].map(PLAYER_NAME_MANUAL)
    
    print("review fuzzy matches and update manual overrides as needed...")
    fuzzy_matches = fuzzy_matches.sort_values(by='score', ascending=False)
    fuzzy_matches.to_csv(FUZZY_MATCHES_DEBUG, index=False)

    return df


def main():
    # Load data
    df_fpl = get_fpl_data()
    ref_names = get_ref_data()
    
    # Match names
    df = pd.merge(df_fpl, ref_names, on='player_code', how='left')

    if df['fbref_name'].isnull().sum() > 0:
        print("Some player names are missing from the reference dataset. Update reference data...")
        df = match_player_names(df)
        
        if UPDATE_REF:
            update_reference_names(df)
            raise ValueError("Reference Data updated. Please re-run the script.")

        raise ValueError(f"Review {FUZZY_MATCHES_DEBUG} for potential matches. Update Manual Overrides as needed, and re-run with UPDATE_REF=True to update reference data.")
    
    df = df[['player_code', 'fbref_name', 'position', 'fpl_cost', 'fpl_form', 'season_ppg', 'total_points']]
    
    return df


if __name__ == "__main__":
    df = main()
    df.to_csv(FPL_FILE, index=False)