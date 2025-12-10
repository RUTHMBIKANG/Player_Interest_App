import streamlit as st
import pandas as pd
from statsbombpy import sb
from mplsoccer import Pitch
import matplotlib.pyplot as plt
import numpy as np

# --- Configuration and Setup ---
COMPETITION_ID = 55
SEASON_ID = 282

# --- Helper Functions ---

@st.cache_data # Cache data to avoid re-fetching on rerun
def load_euro_data(comp_id, season_id):
    """Loads all match events for the specified competition and season."""
    st.info("Fetching StatsBomb event data for all Euro 2024 matches. This may take a moment...")
    try:
        matches_df = sb.matches(competition_id=comp_id, season_id=season_id)
        match_ids = matches_df['match_id'].tolist()

        all_events_list = []
        for match_id in match_ids:
            try:
                events = sb.events(match_id=match_id)
                all_events_list.append(events)
            except Exception as e:
                st.warning(f"Could not load events for match ID {match_id}: {e}")
                continue

        if not all_events_list:
            st.error("No event data could be loaded. Please ensure `statsbombpy` is configured and data is available.")
            return pd.DataFrame(), pd.DataFrame()

        full_events_df = pd.concat(all_events_list, ignore_index=True)
        st.success(f"Successfully loaded {len(full_events_df):,} events from the tournament.")
        return full_events_df, matches_df

    except Exception as e:
        st.error(f"FATAL ERROR during data loading. Details: {e}")
        return pd.DataFrame(), pd.DataFrame()

@st.cache_data
def get_minutes_played(events_df, matches_df):
    """Calculates total minutes played for each player across all matches."""
    player_total_minutes = {}
    unique_match_ids = events_df['match_id'].unique()

    for match_id in unique_match_ids:
        match_events = events_df[events_df['match_id'] == match_id].copy()
        match_events.sort_values(by=['period', 'minute', 'second'], inplace=True)

        players_on_field = set()
        player_match_start_time = {}

        if not match_events.empty:
            last_event = match_events.iloc[-1]
            max_match_total_seconds = (last_event['period'] - 1) * 45 * 60 + last_event['minute'] * 60 + last_event['second']
        else:
            max_match_total_seconds = 0

        for idx, event in match_events[match_events['type'] == 'Starting XI'].iterrows():
            if 'tactics' in event and isinstance(event['tactics'], dict) and \
               'lineup' in event['tactics'] and isinstance(event['tactics']['lineup'], list):
                for player_data in event['tactics']['lineup']:
                    if isinstance(player_data, dict) and 'player' in player_data and isinstance(player_data['player'], dict) and 'name' in player_data['player']:
                        player_name = player_data['player']['name']
                        players_on_field.add(player_name)
                        player_match_start_time[player_name] = 0
                        player_total_minutes.setdefault(player_name, 0)
            elif 'player' in event and pd.notna(event['player']):
                player_name = event['player']
                players_on_field.add(player_name)
                player_match_start_time[player_name] = 0
                player_total_minutes.setdefault(player_name, 0)

        for idx, event in match_events.iterrows():
            event_type = event['type']
            player_name_event = event['player']
            current_total_seconds = (event['period'] - 1) * 45 * 60 + event['minute'] * 60 + event['second']

            if event_type == 'Substitution':
                player_off = player_name_event
                player_on = None
                substitution_data = event.get('substitution')
                if isinstance(substitution_data, dict):
                    replacement_data = substitution_data.get('replacement')
                    if isinstance(replacement_data, dict):
                        player_on = replacement_data.get('name')

                if player_off in players_on_field:
                    time_on_field_seconds = current_total_seconds - player_match_start_time.get(player_off, 0)
                    player_total_minutes[player_off] = player_total_minutes.get(player_off, 0) + (time_on_field_seconds / 60)
                    players_on_field.remove(player_off)
                    if player_off in player_match_start_time:
                        del player_match_start_time[player_off]

                if player_on and player_on not in players_on_field:
                    players_on_field.add(player_on)
                    player_match_start_time[player_on] = current_total_seconds
                    player_total_minutes.setdefault(player_on, 0)

        for player in players_on_field:
            time_on_field_seconds = max_match_total_seconds - player_match_start_time.get(player, 0)
            player_total_minutes[player] = player_total_minutes.get(player, 0) + (time_on_field_seconds / 60)

    minutes_df = pd.DataFrame(player_total_minutes.items(), columns=['player', 'minutes_played'])
    return minutes_df

def plot_player_actions(df_player, action_type, title_suffix, target_player):
    """Plots all specified actions on a football pitch."""
    df_actions = df_player[df_player['type'].str.contains(action_type, case=False, na=False)].copy()

    if df_actions.empty:
        st.warning(f"No {action_type.lower()} data found for {target_player}.")
        return None

    df_actions['x'] = df_actions['location'].apply(lambda x: x[0])
    df_actions['y'] = df_actions['location'].apply(lambda x: x[1])

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))

    if action_type == 'Shot':
        df_goals = df_actions[df_actions['shot_outcome'] == 'Goal']

        pitch.scatter(
            df_actions[df_actions['shot_outcome'] != 'Goal']['x'],
            df_actions[df_actions['shot_outcome'] != 'Goal']['y'],
            s=150,
            c='yellow',
            edgecolors='k',
            alpha=0.7,
            ax=ax,
            label='Shot (No Goal)'
        )
        pitch.scatter(
            df_goals['x'],
            df_goals['y'],
            s=350,
            marker='football',
            ax=ax,
            label='Goal'
        )

    elif action_type == 'Pass':
        df_success = df_actions[df_actions['pass_outcome'].isnull()]
        df_fail = df_actions[df_actions['pass_outcome'].notnull()]
        df_assists = df_actions[(df_actions['pass_shot_assist'].notnull()) | (df_actions['pass_goal_assist'].notnull())]

        pitch.lines(
            df_success[~((df_success['pass_shot_assist'].notnull()) | (df_success['pass_goal_assist'].notnull()))]['x'],
            df_success[~((df_success['pass_shot_assist'].notnull()) | (df_success['pass_goal_assist'].notnull()))]['y'],
            df_success[~((df_success['pass_shot_assist'].notnull()) | (df_success['pass_goal_assist'].notnull()))]['pass_end_location'].apply(lambda x: x[0]),
            df_success[~((df_success['pass_shot_assist'].notnull()) | (df_success['pass_goal_assist'].notnull()))]['pass_end_location'].apply(lambda x: x[1]),
            lw=3,
            color='#00FF00',
            zorder=1,
            alpha=0.6,
            ax=ax,
            label='Successful Pass'
        )

        pitch.lines(
            df_fail['x'],
            df_fail['y'],
            df_fail['pass_end_location'].apply(lambda x: x[0]),
            df_fail['pass_end_location'].apply(lambda x: x[1]),
            lw=3,
            color='#FF0000',
            linestyle=':',
            zorder=1,
            alpha=0.6,
            ax=ax,
            label='Unsuccessful Pass'
        )

        if not df_assists.empty:
            pitch.lines(
                df_assists['x'],
                df_assists['y'],
                df_assists['pass_end_location'].apply(lambda x: x[0]),
                df_assists['pass_end_location'].apply(lambda x: x[1]),
                lw=4,
                color='#FFFF00',
                zorder=2,
                alpha=0.8,
                ax=ax,
                label='Assist Pass'
            )
            pitch.scatter(
                df_assists['x'],
                df_assists['y'],
                s=100,
                marker='s',
                edgecolors='k',
                facecolors='#FFFF00',
                zorder=3,
                ax=ax
            )

        pitch.scatter(df_actions[~((df_actions['pass_shot_assist'].notnull()) | (df_actions['pass_goal_assist'].notnull()))]['x'],
                      df_actions[~((df_actions['pass_shot_assist'].notnull()) | (df_actions['pass_goal_assist'].notnull()))]['y'],
                      s=50, c='lightblue', edgecolors='k', ax=ax, zorder=1)


    elif action_type == 'Dribble':
        df_complete = df_actions[df_actions['dribble_outcome'] == 'Complete']
        df_incomplete = df_actions[df_actions['dribble_outcome'] == 'Incomplete']

        pitch.scatter(
            df_complete['x'],
            df_complete['y'],
            s=150,
            c='green',
            edgecolors='k',
            alpha=0.7,
            ax=ax,
            label='Successful Dribble'
        )

        pitch.scatter(
            df_incomplete['x'],
            df_incomplete['y'],
            s=150,
            c='red',
            edgecolors='k',
            alpha=0.7,
            ax=ax,
            label='Unsuccessful Dribble'
        )

    ax.set_title(f"{target_player}'s {title_suffix} (Euro 2024)", color='black', fontsize=18)
    ax.legend(facecolor='white', edgecolor='black', labelcolor='black')

    return fig

def plot_action_heatmap(df_player, title_suffix, target_player):
    """Generates a heatmap of player actions (Shots, Passes, Dribbles)."""
    df_actions = df_player[df_player['type'].isin(['Shot', 'Pass', 'Dribble'])].copy()

    if df_actions.empty:
        st.warning(f"No action data found for {target_player} to generate heatmap.")
        return None

    df_actions['x'] = df_actions['location'].apply(lambda x: x[0] if isinstance(x, (list, tuple)) and len(x) > 0 else np.nan)
    df_actions['y'] = df_actions['location'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else np.nan)

    df_actions.dropna(subset=['x', 'y'], inplace=True)

    if df_actions.empty:
        st.warning(f"No valid location data for {target_player} to generate heatmap.")
        return None

    pitch = Pitch(pitch_color='white', line_color='black', stripe=False)
    fig, ax = pitch.draw(figsize=(10, 7))

    pitch.kdeplot(df_actions['x'], df_actions['y'], ax=ax, fill=True, cmap='hot', zorder=0.5)

    ax.set_title(f"{target_player}'s {title_suffix} (Euro 2024)", color='black', fontsize=18)
    ax.tick_params(axis='x', colors='black')
    ax.tick_params(axis='y', colors='black')

    return fig

def plot_zscore_comparison(df_zscores, target_player, metric_columns, title_suffix):
    """Plots a bar chart of the target player's Z-scores for key metrics."""
    player_zscores = df_zscores[df_zscores['Name'] == target_player].iloc[0]

    z_values = [player_zscores[f'Z_{col}'] for col in metric_columns]
    metric_labels = [col.replace(' (%)', '').replace(' per 90', '') for col in metric_columns]

    fig, ax = plt.subplots(figsize=(12, 7))
    colors = ['green' if z > 0 else 'red' for z in z_values]
    ax.barh(metric_labels, z_values, color=colors)

    ax.axvline(0, color='black', linestyle='--', linewidth=0.8)

    ax.set_xlabel('Z-Score (Standard Deviations from Mean)', color='black')
    ax.set_ylabel('Metric', color='black')
    ax.set_title(f'{target_player}: Z-Scores for Key Attacking Metrics (vs. Right Wingers) {title_suffix}', color='black', fontsize=16)

    ax.tick_params(axis='x', colors='black')
    ax.tick_params(axis='y', colors='black')
    ax.set_facecolor('white')
    fig.set_facecolor('white')

    for i, v in enumerate(z_values):
        ax.text(v + 0.1 if v > 0 else v - 0.1, i, f'{v:.2f}', color='black', va='center', ha='left' if v > 0 else 'right')

    plt.tight_layout()
    return fig


def get_player_stats(df, player_name, minutes_played_series, team_name):
    """Calculates key attacking stats for a given player, normalized per 90 minutes."""
    df_player = df[df['player'] == player_name].copy()

    minutes_played = minutes_played_series.get(player_name, 0)
    if minutes_played == 0:
        per_90_factor = 0
    else:
        per_90_factor = minutes_played / 90

    if per_90_factor == 0:
        goals_p90 = 0
        assists_p90 = 0
        total_shots_p90 = 0
        xg_sum_p90 = 0
        successful_passes_p90 = 0
        dribbles_completed_p90 = 0
        pass_success_rate = 0
        dribble_success_rate = 0
    else:
        df_passes = df_player[df_player['type'] == 'Pass']
        total_passes = len(df_passes)
        successful_passes = len(df_passes[df_passes['pass_outcome'].isnull()])
        pass_success_rate = (successful_passes / total_passes * 100) if total_passes > 0 else 0

        assists = len(df_passes[df_passes['pass_shot_assist'].notnull() | df_passes['pass_goal_assist'].notnull()])

        df_shots = df_player[df_player['type'] == 'Shot']
        total_shots = len(df_shots)
        xG_sum = df_shots['shot_statsbomb_xg'].sum()
        goals = len(df_shots[df_shots['shot_outcome'] == 'Goal'])

        df_dribbles = df_player[df_player['type'] == 'Dribble']
        total_dribbles = len(df_dribbles)
        successful_dribbles = len(df_dribbles[df_dribbles['dribble_outcome'] == 'Complete'])
        dribble_success_rate = (successful_dribbles / total_dribbles * 100) if total_dribbles > 0 else 0

        goals_p90 = goals / per_90_factor
        assists_p90 = assists / per_90_factor
        total_shots_p90 = total_shots / per_90_factor
        xg_sum_p90 = xG_sum / per_90_factor
        successful_passes_p90 = successful_passes / per_90_factor
        dribbles_completed_p90 = successful_dribbles / per_90_factor

    return {
        "Name": player_name,
        "Team": df_player['team'].iloc[0] if not df_player.empty else team_name,
        "Minutes Played": round(minutes_played, 1),
        "Goals per 90": round(goals_p90, 2),
        "Assists per 90": round(assists_p90, 2),
        "Total Shots per 90": round(total_shots_p90, 2),
        "Total xG per 90": round(xg_sum_p90, 2),
        "Passes Completed per 90": round(successful_passes_p90, 2),
        "Pass Success Rate (%)": round(pass_success_rate, 1),
        "Dribbles Completed per 90": round(dribbles_completed_p90, 2),
        "Dribble Success Rate (%)": round(dribble_success_rate, 1)
    }

def get_comparative_stats(df, stat_col, minutes_played_series, team_name, num_players=5):
    """Aggregates and ranks players based on a given statistic, using per 90 data."""

    df_filtered_events = df[df['type'].isin(['Shot', 'Pass', 'Dribble'])]

    player_data = []
    players = df_filtered_events['player'].dropna().unique()

    for player in players:
        if minutes_played_series.get(player, 0) > 0:
            player_data.append(get_player_stats(df_filtered_events, player, minutes_played_series, team_name))

    df_comp = pd.DataFrame(player_data)

    if not df_comp.empty:
        df_comp = df_comp.sort_values(by=stat_col, ascending=False).reset_index(drop=True)
    else:
        return pd.DataFrame()

    return df_comp.head(num_players)


def main():
    st.set_page_config(layout="wide", page_title="Euro 2024 Player Analysis")
    st.title("⚽ Euro 2024 Player Performance Analyzer")

    # Sidebar for player selection
    st.sidebar.header("Player Selection")
    full_events_df, matches_df = load_euro_data(COMPETITION_ID, SEASON_ID)

    if full_events_df.empty:
        st.error("Cannot proceed without event data.")
        return

    player_list = sorted(full_events_df['player'].dropna().unique().tolist())
    selected_player = st.sidebar.selectbox("Choose a player for analysis:", player_list, index=player_list.index("Lamine Yamal Nasraoui Ebana"))

    st.sidebar.markdown("---")
    st.sidebar.header("Comparative Analysis Settings")
    comparison_metric_options = [
        "Goals per 90", "Assists per 90", "Total Shots per 90", "Total xG per 90",
        "Passes Completed per 90", "Pass Success Rate (%)",
        "Dribbles Completed per 90", "Dribble Success Rate (%)"
    ]
    selected_comparison_metric = st.sidebar.selectbox("Rank players by:", comparison_metric_options)

    minutes_df = get_minutes_played(full_events_df, matches_df)
    minutes_played_series = minutes_df.set_index('player')['minutes_played']

    st.header(f"Analysis for: {selected_player}")

    # --- 1. Key Statistics ---
    st.subheader("1. Key Statistics (Per 90 Minutes)")
    player_stats = get_player_stats(full_events_df, selected_player, minutes_played_series, team_name="Unknown")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Minutes Played", f"{player_stats['Minutes Played']:.1f}")
    col2.metric("Goals per 90", f"{player_stats['Goals per 90']:.2f}")
    col3.metric("Assists per 90", f"{player_stats['Assists per 90']:.2f}")
    col4.metric("Total xG per 90", f"{player_stats['Total xG per 90']:.2f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Total Shots per 90", f"{player_stats['Total Shots per 90']:.2f}")
    col6.metric("Passes Completed per 90", f"{player_stats['Passes Completed per 90']:.2f}")
    col7.metric("Pass Success Rate", f"{player_stats['Pass Success Rate (%)']:.1f}%")
    col8.metric("Dribbles Completed per 90", f"{player_stats['Dribbles Completed per 90']:.2f}")

    # --- 2. Action Maps ---
    st.subheader("2. Player Action Maps")

    df_player_events = full_events_df[full_events_df['player'] == selected_player]

    col_map1, col_map2 = st.columns(2)
    with col_map1:
        pass_fig = plot_player_actions(df_player_events, 'Pass', 'Passes', selected_player)
        if pass_fig: st.pyplot(pass_fig)
    with col_map2:
        shot_fig = plot_player_actions(df_player_events, 'Shot', 'Shots', selected_player)
        if shot_fig: st.pyplot(shot_fig)

    dribble_fig = plot_player_actions(df_player_events, 'Dribble', 'Dribbles', selected_player)
    if dribble_fig: st.pyplot(dribble_fig)

    # --- 3. Action Heatmap ---
    st.subheader("3. Player Action Heatmap")
    heatmap_fig = plot_action_heatmap(df_player_events, 'Action Heatmap', selected_player)
    if heatmap_fig: st.pyplot(heatmap_fig)

    # --- 4. Comparative Analysis ---
    st.subheader(f"4. Comparative Analysis: Top 10 by {selected_comparison_metric}")
    df_comparative = get_comparative_stats(full_events_df, selected_comparison_metric, minutes_played_series, team_name="Unknown", num_players=10)
    st.dataframe(df_comparative)

    # --- 5. Z-Score Comparison ---
    st.subheader(f"5. {selected_player}: Z-Scores vs. Right Wingers")
    metric_columns = [
        "Goals per 90",
        "Assists per 90",
        "Total Shots per 90",
        "Total xG per 90",
        "Passes Completed per 90",
        "Pass Success Rate (%)",
        "Dribbles Completed per 90",
        "Dribble Success Rate (%)"
    ]

    # Placeholder for right_wingers_list for local execution.
    # In a real app, this list would be dynamically generated or loaded from a pre-defined source.
    right_wingers_list = sorted(full_events_df['player'].dropna().unique().tolist())

    player_stats_list_zscore = []
    for player_name in right_wingers_list:
        stats = get_player_stats(full_events_df, player_name, minutes_played_series, team_name="Unknown")
        player_stats_list_zscore.append(stats)

    df_winger_stats_comparison_zscore = pd.DataFrame(player_stats_list_zscore)

    # Filter out players with 0 minutes to avoid NaN in Z-score calculation if std is 0 for some metrics.
    df_winger_stats_comparison_zscore = df_winger_stats_comparison_zscore[df_winger_stats_comparison_zscore['Minutes Played'] > 0].reset_index(drop=True)

    # Ensure numerical columns are indeed numeric
    for col in metric_columns:
        df_winger_stats_comparison_zscore[col] = pd.to_numeric(df_winger_stats_comparison_zscore[col], errors='coerce')

    means = df_winger_stats_comparison_zscore[metric_columns].mean()
    stds = df_winger_stats_comparison_zscore[metric_columns].std()
    stds = stds.replace(0, 1) # Avoid division by zero

    df_zscores_current = df_winger_stats_comparison_zscore.copy()
    for col in metric_columns:
        df_zscores_current[f'Z_{col}'] = (df_winger_stats_comparison_zscore[col] - means[col]) / stds[col]

    if selected_player in df_zscores_current['Name'].values:
        zscore_fig = plot_zscore_comparison(df_zscores_current, selected_player, metric_columns, title_suffix='(Per 90 Minutes)')
        if zscore_fig: st.pyplot(zscore_fig)
    else:
        st.warning(f"Z-scores cannot be computed for {selected_player} as they are not in the comparison group or have 0 minutes played.")


if __name__ == '__main__':
    main()