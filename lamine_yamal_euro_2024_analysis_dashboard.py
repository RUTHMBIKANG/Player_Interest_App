# STREAMLIT VERSION OF YOUR SCRIPT
# Cache ONLY where necessary (data + minutes), NEVER plots

import streamlit as st
import pandas as pd
from statsbombpy import sb
from mplsoccer import Pitch
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

# --------------------------------------------------
# Streamlit & Matplotlib setup
# --------------------------------------------------
plt.style.use("default")
st.set_page_config(page_title="Euro 2024 Player Analysis", layout="wide")

# --------------------------------------------------
# Configuration
# --------------------------------------------------
COMPETITION_ID = 55
SEASON_ID = 282
TARGET_TEAM = "Spain"

# --------------------------------------------------
# DATA LOADING (CACHED)
# --------------------------------------------------
@st.cache_data(show_spinner=True)
def load_euro_data(comp_id, season_id):
    matches_df = sb.matches(competition_id=comp_id, season_id=season_id)
    match_ids = matches_df['match_id'].tolist()

    all_events = []
    for match_id in match_ids:
        try:
            all_events.append(sb.events(match_id=match_id))
        except Exception:
            continue

    if not all_events:
        return pd.DataFrame(), pd.DataFrame()

    return pd.concat(all_events, ignore_index=True), matches_df


# --------------------------------------------------
# MINUTES PLAYED (CACHED + SAFE)
# --------------------------------------------------
@st.cache_data
def get_minutes_played(events_df):
    player_minutes = {}

    for match_id in events_df['match_id'].unique():
        df = events_df[events_df['match_id'] == match_id].copy()
        df.sort_values(['period', 'minute', 'second'], inplace=True)

        if df.empty:
            continue

        end_time = (
            (df.iloc[-1]['period'] - 1) * 45 * 60
            + df.iloc[-1]['minute'] * 60
            + df.iloc[-1]['second']
        )

        players_on = {}

        for _, row in df[df['type'] == 'Starting XI'].iterrows():
            tactics = row.get('tactics')
            if isinstance(tactics, dict):
                for p in tactics.get('lineup', []):
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
                off_player = row.get('player')
                on_player = None

                sub = row.get('substitution')
                if isinstance(sub, dict):
                    rep = sub.get('replacement')
                    if isinstance(rep, dict):
                        on_player = rep.get('name')

                if off_player in players_on:
                    player_minutes[off_player] += (current_time - players_on[off_player]) / 60
                    players_on.pop(off_player)

                if on_player:
                    players_on[on_player] = current_time
                    player_minutes.setdefault(on_player, 0)

        for p, start in players_on.items():
            player_minutes[p] += (end_time - start) / 60

    return pd.DataFrame(player_minutes.items(), columns=['player', 'minutes_played'])


# --------------------------------------------------
# PLOTTING FUNCTIONS (❌ NOT CACHED)
# --------------------------------------------------
def plot_player_actions(df_player, action_type, title):
    df = df_player[df_player['type'] == action_type].copy()
    if df.empty:
        return None

    df['x'] = df['location'].str[0]
    df['y'] = df['location'].str[1]

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    legend_elements = []

    if action_type == 'Pass':
        success = df[df['pass_outcome'].isna()]
        fail = df[df['pass_outcome'].notna()]
        assists = df[df['pass_goal_assist'].notna()]

        pitch.arrows(
            success['x'], success['y'],
            success['pass_end_location'].str[0],
            success['pass_end_location'].str[1],
            width=2, headwidth=6, headlength=6,
            color='green', ax=ax
        )

        pitch.arrows(
            fail['x'], fail['y'],
            fail['pass_end_location'].str[0],
            fail['pass_end_location'].str[1],
            width=2, headwidth=6, headlength=6,
            color='red', linestyle=':', ax=ax
        )

        pitch.arrows(
            assists['x'], assists['y'],
            assists['pass_end_location'].str[0],
            assists['pass_end_location'].str[1],
            width=3, headwidth=8, headlength=8,
            color='gold', ax=ax
        )

        legend_elements = [
            Line2D([0], [0], color='green', lw=3, label='Successful Pass'),
            Line2D([0], [0], color='red', lw=3, linestyle=':', label='Unsuccessful Pass'),
            Line2D([0], [0], color='gold', lw=4, label='Assist')
        ]

    elif action_type == 'Shot':
        goals = df[df['shot_outcome'] == 'Goal']

        pitch.scatter(df['x'], df['y'], s=120, c='orange', ax=ax)
        pitch.scatter(goals['x'], goals['y'], s=300, marker='football', ax=ax)

        legend_elements = [
            Patch(facecolor='orange', label='Shot'),
            Patch(facecolor='white', edgecolor='black', label='Goal')
        ]

    elif action_type == 'Dribble':
        complete = df[df['dribble_outcome'] == 'Complete']
        incomplete = df[df['dribble_outcome'] == 'Incomplete']

        pitch.scatter(complete['x'], complete['y'], c='green', s=120, ax=ax)
        pitch.scatter(incomplete['x'], incomplete['y'], c='red', s=120, ax=ax)

        legend_elements = [
            Patch(facecolor='green', label='Successful Dribble'),
            Patch(facecolor='red', label='Unsuccessful Dribble')
        ]

    if legend_elements:
        ax.legend(
            handles=legend_elements,
            loc='upper left',
            bbox_to_anchor=(1.02, 1),
            frameon=False
        )

    ax.set_title(title)
    return fig


def plot_heatmap(df_player):
    df = df_player[df_player['type'].isin(['Shot', 'Pass', 'Dribble'])].copy()
    if df.empty:
        return None

    df['x'] = df['location'].str[0]
    df['y'] = df['location'].str[1]

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    pitch.kdeplot(df['x'], df['y'], fill=True, cmap='hot', ax=ax)
    ax.set_title("Action Heatmap")

    return fig


# --------------------------------------------------
# STREAMLIT APP
# --------------------------------------------------
def main():
    st.title("⚽ Euro 2024 Player Performance Dashboard")

    events_df, _ = load_euro_data(COMPETITION_ID, SEASON_ID)
    if events_df.empty:
        st.error("Failed to load StatsBomb data")
        return

    minutes_df = get_minutes_played(events_df)
    minutes_series = minutes_df.set_index('player')['minutes_played']

    players = sorted(events_df['player'].dropna().unique())
    player = st.selectbox("Select Player", players)

    df_player = events_df[events_df['player'] == player]

    st.metric("Minutes Played", round(minutes_series.get(player, 0), 1))

    st.subheader("Pass Map")
    fig = plot_player_actions(df_player, 'Pass', 'Pass Map')
    if fig:
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)

    st.subheader("Shot Map")
    fig = plot_player_actions(df_player, 'Shot', 'Shot Map')
    if fig:
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)

    st.subheader("Dribble Map")
    fig = plot_player_actions(df_player, 'Dribble', 'Dribble Map')
    if fig:
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)

    st.subheader("Action Heatmap")
    fig = plot_heatmap(df_player)
    if fig:
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)


if __name__ == '__main__':
    main()
