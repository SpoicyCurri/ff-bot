import streamlit as st


def app():
    players = st.Page("pages/player_page.py", title="Players", icon="🥸", default=True)
    team = st.Page("pages/team_page.py", title="Teams", icon="👨🏾‍🤝‍👨🏼")
    
    pg = st.navigation([players, team])
    
    pg.run()


if __name__ == '__main__':
    app()