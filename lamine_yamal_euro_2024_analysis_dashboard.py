# STREAMLIT VERSION — FULL FEATURE + STREAMLIT CLOUD SAFE

import streamlit as st
import pandas as pd
from statsbombpy import sb
from mplsoccer import Pitch
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

plt.style.use("default")
st.set_page_config(page_title="Euro 2024 Player Analysis", layout="wide")

COMPETITION_ID = 55
SEASON_ID = 282

# --------------------------------------------------
# DATA LOADING (SAFE CACHE)
# --------------------------------------------------
@st.cache_data(show_spinner=True)
def load_match_ids(comp_id, season_id):
    matches = sb.matches(competition_id=comp_id, season_id=season_id)
    return matches["match_id"].tolist()

def load_events(match_ids):
    events = []
    for mid in match_ids:
        try:
            events.append(sb.events(match_id=mid))
        except Exception:
            continue
    return pd.concat(events, ignore_index=True)

# --------------------------------------------------
# MINUTES PLAYED (NO CACHE)
# --------------------------------------------------
def get_minutes_played(events_df):
    player_minutes = {}

    for match_id in events_df['match_id'].unique():
        df = events_df[events_df['match_id'] == match_id].copy()
        df.sort_values(['period', 'minute', 'second'], inplace=True)

        end_time = (
            (df.iloc[-1]['period'] - 1) * 45 * 60
            + df.iloc[-1]['minute'] * 60
            + df.iloc[-1]['second']
        )

        players_on = {}

        for _, row in df[df['type'] == 'Starting XI'].iterrows():
            for p in row.get('tactics', {}).get('lineup', []):
                name = p['player']['name']
                players_on[name] = 0
                player_minutes.setdefault(name, 0)

        for _, row in df.iterrows():
            current_time = (
                (row['period'] - 1) * 45 * 60
                + row['minute'] * 60
                + row['second']
            )

            if row['type'] == 'Substitution':
                off = row.get('player')
                on = row.get('substitution', {}).get('replacement', {}).get('name')

                if off in players_on:
                    player_minutes[off] += (current_time - players_on[off]) / 60
                    players_on.pop(off)

                if on:
                    players_on[on] = current_time
                    player_minutes.setdefault(on, 0)

        for p, start in players_on.items():
            player_minutes[p] += (end_time - start) / 60

    return pd.DataFrame(player_minutes.items(), columns=['player', 'minutes_played'])

# --------------------------------------------------
# UTILITY: COORDINATE SANITIZER
# --------------------------------------------------
def extract_xy(df, col):
    return pd.DataFrame(df[col].tolist(), columns=['x', 'y'], index=df.index)

# --------------------------------------------------
# PASS MAP (WITH ARROWS + LEGEND)
# --------------------------------------------------
def plot_pass_map(df):
    df = df[df['type'] == 'Pass'].copy()
    df = df[df['pass_end_location'].apply(lambda x: isinstance(x, list) and len(x) == 2)]

    if df.empty:
        return None

    df[['x', 'y']] = extract_xy(df, 'location')
    df[['end_x', 'end_y']] = extract_xy(df, 'pass_end_location')

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))

    success = df[df['pass_outcome'].isna()]
    fail = df[df['pass_outcome'].notna()]
    assist = df[df['pass_goal_assist'].notna()]

    pitch.arrows(success.x, success.y, success.end_x, success.end_y,
                 color='green', width=2, ax=ax)
    pitch.arrows(fail.x, fail.y, fail.end_x, fail.end_y,
                 color='red', linestyle=':', width=2, ax=ax)
    pitch.arrows(assist.x, assist.y, assist.end_x, assist.end_y,
                 color='gold', width=3, ax=ax)

    legend = [
        Line2D([0], [0], color='green', lw=3, label='Successful Pass'),
        Line2D([0], [0], color='red', lw=3, linestyle=':', label='Unsuccessful Pass'),
        Line2D([0], [0], color='gold', lw=4, label='Assist'),
    ]
    ax.legend(handles=legend, bbox_to_anchor=(1.02, 1), loc='upper left', frameon=False)
    ax.set_title("Pass Map")

    return fig

# --------------------------------------------------
# SHOT MAP
# --------------------------------------------------
def plot_shot_map(df):
    df = df[df['type'] == 'Shot'].copy()
    if df.empty:
        return None

    df[['x', 'y']] = extract_xy(df, 'location')
    goals = df[df['shot_outcome'] == 'Goal']

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))

    pitch.scatter(df.x, df.y, s=120, color='orange', ax=ax)
    pitch.scatter(goals.x, goals.y, s=300, marker='football', ax=ax)

    ax.legend(
        handles=[
            Patch(facecolor='orange', label='Shot'),
            Patch(facecolor='white', edgecolor='black', label='Goal')
        ],
        bbox_to_anchor=(1.02, 1),
        loc='upper left',
        frameon=False
    )
    ax.set_title("Shot Map")

    return fig

# --------------------------------------------------
# DRIBBLE MAP
# --------------------------------------------------
def plot_dribble_map(df):
    df = df[df['type'] == 'Dribble'].copy()
    if df.empty:
        return None

    df[['x', 'y']] = extract_xy(df, 'location')
    complete = df[df['dribble_outcome'] == 'Complete']
    incomplete = df[df['dribble_outcome'] == 'Incomplete']

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))

    pitch.scatter(complete.x, complete.y, color='green', s=120, ax=ax)
    pitch.scatter(incomplete.x, incomplete.y, color='red', s=120, ax=ax)

    ax.legend(
        handles=[
            Patch(facecolor='green', label='Successful Dribble'),
            Patch(facecolor='red', label='Unsuccessful Dribble')
        ],
        bbox_to_anchor=(1.02, 1),
        loc='upper left',
        frameon=False
    )
    ax.set_title("Dribble Map")

    return fig

# --------------------------------------------------
# ACTION HEATMAP
# --------------------------------------------------
def plot_action_heatmap(df):
    df = df[df['type'].isin(['Pass', 'Shot', 'Dribble'])].copy()
    if df.empty:
        return None

    df[['x', 'y']] = extract_xy(df, 'location')

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))

    pitch.kdeplot(df.x, df.y, fill=True, cmap='hot', ax=ax)
    ax.set_title("Action Heatmap")

    return fig

# --------------------------------------------------
# STREAMLIT APP
# --------------------------------------------------
def main():
    st.title("⚽ Euro 2024 Player Performance Dashboard")

    match_ids = load_match_ids(COMPETITION_ID, SEASON_ID)
    events_df = load_events(match_ids)

    minutes_df = get_minutes_played(events_df)
    minutes = minutes_df.set_index('player')['minutes_played']

    player = st.selectbox("Select Player", sorted(events_df['player'].dropna().unique()))
    df_player = events_df[events_df['player'] == player]

    st.metric("Minutes Played", round(minutes.get(player, 0), 1))

    st.subheader("Pass Map")
    fig = plot_pass_map(df_player)
    if fig:
        st.pyplot(fig); plt.close(fig)

    st.subheader("Shot Map")
    fig = plot_shot_map(df_player)
    if fig:
        st.pyplot(fig); plt.close(fig)

    st.subheader("Dribble Map")
    fig = plot_dribble_map(df_player)
    if fig:
        st.pyplot(fig); plt.close(fig)

    st.subheader("Action Heatmap")
    fig = plot_action_heatmap(df_player)
    if fig:
        st.pyplot(fig); plt.close(fig)

if __name__ == "__main__":
    main()
