import streamlit as st
import pandas as pd
from statsbombpy import sb
from mplsoccer import Pitch
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from io import BytesIO
from scipy.ndimage import gaussian_filter

# --- Configuration and Setup ---

# Set IDs for Euro 2024 (based on StatsBomb open data)
COMPETITION_ID = 55
SEASON_ID = 282
TARGET_PLAYER = "Lamine Yamal Nasraoui Ebana"
TARGET_TEAM = "Spain" 

# Set a page config for a better looking app
st.set_page_config(layout="wide", page_title="Euro 2024 Analysis")

# --- Helper Functions ---

# Function to fetch data (cached for speed)
@st.cache_data
def load_euro_data(comp_id, season_id):
    """Loads all match events for the specified competition and season."""
    try:
        # Load all matches for Euro 2024
        matches_df = sb.matches(competition_id=comp_id, season_id=season_id)
        
        # Get all match IDs
        match_ids = matches_df['match_id'].tolist()
        
        # Load all events from all matches (this can be slow and might require logging in for the first time)
        st.info("Fetching StatsBomb event data for all Euro 2024 matches. This may take a moment...")
        all_events_list = []
        
        # Fetching all events, match by match, to handle potential API limits better
        for match_id in match_ids:
            try:
                events = sb.events(match_id=match_id)
                all_events_list.append(events)
            except Exception as e:
                st.warning(f"Could not load events for match ID {match_id}: {e}")
                continue
                
        if not all_events_list:
            st.error("No event data could be loaded. Please ensure `statsbombpy` is configured and data is available.")
            return pd.DataFrame()
            
        full_events_df = pd.concat(all_events_list, ignore_index=True)
        st.success(f"Successfully loaded {len(full_events_df):,} events from the tournament.")
        return full_events_df
    
    except Exception as e:
        st.error(f"Error during data loading. Please ensure you have run 'pip install statsbombpy streamlit mplsoccer pandas matplotlib' in your Colab environment. Details: {e}")
        return pd.DataFrame()

# Function to generate the shot/pass map
def plot_player_actions(df_player, action_type, title_suffix):
    """Plots all specified actions on a football pitch.
    
    Returns the Matplotlib Figure object (fig) and an error message (None).
    """
    # Filter for the action type
    df_actions = df_player[df_player['type'].str.contains(action_type, case=False, na=False)].copy()
    
    if df_actions.empty:
        # Return None for the figure and the error message
        return None, f"No {action_type.lower()} data found for {TARGET_PLAYER}."

    # StatsBomb coordinates are 0-120 (x) and 0-80 (y). mplsoccer handles this.
    df_actions['x'] = df_actions['location'].apply(lambda x: x[0])
    df_actions['y'] = df_actions['location'].apply(lambda x: x[1])

    # Create pitch
    pitch = Pitch(pitch_color='#22312b', line_color='white', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 7))
    
    # Plotting actions
    if action_type == 'Shot':
        # Filter for goals
        df_goals = df_actions[df_actions['shot_outcome'] == 'Goal']
        
        # Plot shots (not goals)
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
        # Plot goals
        pitch.scatter(
            df_goals['x'],
            df_goals['y'],
            s=350,
            marker='football',
            ax=ax,
            label='Goal'
        )
        
    elif action_type == 'Pass':
        # Filter successful and unsuccessful passes
        df_success = df_actions[df_actions['pass_outcome'].isnull()]
        df_fail = df_actions[df_actions['pass_outcome'].notnull()]
        
        # Successful passes
        pitch.lines(
            df_success['x'],
            df_success['y'],
            df_success['pass_end_location'].apply(lambda x: x[0]),
            df_success['pass_end_location'].apply(lambda x: x[1]),
            lw=3,
            color='#00FF00', # Correctly using 'color' for pitch.lines()
            zorder=1,
            alpha=0.6,
            ax=ax,
            label='Successful Pass'
        )
        
        # Failed passes
        pitch.lines(
            df_fail['x'],
            df_fail['y'],
            df_fail['pass_end_location'].apply(lambda x: x[0]),
            df_fail['pass_end_location'].apply(lambda x: x[1]),
            lw=3,
            color='#FF0000', # Correctly using 'color' for pitch.lines()
            linestyle=':',
            zorder=1,
            alpha=0.6,
            ax=ax,
            label='Unsuccessful Pass'
        )
        
        # Add a starting point for passes
        pitch.scatter(df_actions['x'], df_actions['y'], s=50, c='lightblue', edgecolors='k', ax=ax)
    
    ax.set_title(f"{TARGET_PLAYER}'s {title_suffix} (Euro 2024)", color='white', fontsize=18)
    ax.legend(facecolor='#22312b', edgecolor='white', labelcolor='white')
    
    # *** CHANGE: Return the Matplotlib Figure object instead of converting to a PIL Image ***
    # Streamlit's st.pyplot() handles display, cleanup, and provides the download feature.
    return fig, None

# Function to calculate overall player stats
def get_player_stats(df, player_name):
    """Calculates key attacking stats for a given player."""
    df_player = df[df['player'] == player_name].copy()
    
    # Passes
    df_passes = df_player[df_player['type'] == 'Pass']
    total_passes = len(df_passes)
    successful_passes = len(df_passes[df_passes['pass_outcome'].isnull()])
    pass_success_rate = (successful_passes / total_passes * 100) if total_passes > 0 else 0
    
    # Shots
    df_shots = df_player[df_player['type'] == 'Shot']
    total_shots = len(df_shots)
    xG_sum = df_shots['shot_statsbomb_xg'].sum()
    goals = len(df_shots[df_shots['shot_outcome'] == 'Goal'])
    
    # Dribbles
    df_dribbles = df_player[df_player['type'] == 'Dribble']
    total_dribbles = len(df_dribbles)
    successful_dribbles = len(df_dribbles[df_dribbles['dribble_outcome'] == 'Complete'])
    dribble_success_rate = (successful_dribbles / total_dribbles * 100) if total_dribbles > 0 else 0
    
    return {
        "Name": player_name,
        "Team": df_player['team'].iloc[0] if not df_player.empty else TARGET_TEAM,
        "Goals": goals,
        "Total Shots": total_shots,
        "Total xG": round(xG_sum, 2),
        "Passes Completed": successful_passes,
        "Pass Success Rate (%)": round(pass_success_rate, 1),
        "Dribbles Completed": successful_dribbles,
        "Dribble Success Rate (%)": round(dribble_success_rate, 1)
    }

# Function to get comparative stats (e.g., top 5)
def get_comparative_stats(df, stat_col, num_players=5):
    """Aggregates and ranks players based on a given statistic."""
    
    # Filter to only players who have taken shots (as a minimum filter)
    df_filtered = df[df['type'].isin(['Shot', 'Pass', 'Dribble'])]
    
    # Calculate player stats (requires a more complex aggregation for comparison)
    player_data = []
    
    # Get all unique players who played
    players = df_filtered['player'].unique()
    
    for player in players:
        player_data.append(get_player_stats(df_filtered, player))

    df_comp = pd.DataFrame(player_data)
    
    # Rank by the desired column, excluding the target player if ranking
    df_comp = df_comp.sort_values(by=stat_col, ascending=False).reset_index(drop=True)
    
    return df_comp.head(num_players)

# --- Streamlit App Layout ---

def main():
    # FIX: Move global declaration to the start of the function scope
    global TARGET_PLAYER 

    st.title("⚽ Lamine Yamal's Euro 2024 Performance Analyzer")
    st.markdown("---")

    # 1. Data Loading Section
    full_events_df = load_euro_data(COMPETITION_ID, SEASON_ID)
    
    if full_events_df.empty:
        st.stop() # Stop if data loading failed

    df_yamal = full_events_df[full_events_df['player'] == TARGET_PLAYER]
    
    # Robust check for the correct player name if the hardcoded one fails (for Streamlit deployment flexibility)
    if df_yamal.empty:
        potential_players = full_events_df['player'].dropna().unique()
        corrected_name = None
        
        # Simple fuzzy match check (e.g., matching "Lamine" or "Yamal")
        for player_name in potential_players:
            if TARGET_PLAYER.split()[0] in player_name or TARGET_PLAYER.split()[-1] in player_name:
                corrected_name = player_name
                break
        
        if corrected_name:
            # global TARGET_PLAYER # Original line (removed)
            st.warning(f"Note: Player name '{TARGET_PLAYER}' not found in the dataset. Using best match: '{corrected_name}' instead.")
            TARGET_PLAYER = corrected_name
            df_yamal = full_events_df[full_events_df['player'] == TARGET_PLAYER]
        
            if df_yamal.empty:
                 st.error(f"Could not find event data for {TARGET_PLAYER}. He may not have played in the available matches.")
                 st.stop()
        else:
            st.error(f"Could not find event data for {TARGET_PLAYER}. He may not have played in the available matches.")
            st.stop()
        
    st.sidebar.header("Player Analysis Options")
    
    # Player Selection for Comparison
    all_players = full_events_df['player'].dropna().unique()
    player_options = [p for p in all_players if p != TARGET_PLAYER]
    
    selected_comparison_players = st.sidebar.multiselect(
        "Select players for comparison:",
        options=player_options,
        default=[]
    )
    
    players_to_analyze = [TARGET_PLAYER] + selected_comparison_players
    
    # 2. Player Action Map Section
    st.header("1. Action Map: Passes & Shots (Downloadable)")
    
    col1, col2 = st.columns(2)
    
    # Pass Map
    # *** CHANGE: Now expects a Matplotlib Figure object (pass_fig) ***
    pass_fig, pass_error = plot_player_actions(df_yamal, 'Pass', 'Passes')
    with col1:
        if pass_fig:
            # *** CHANGE: Use st.pyplot() to display the Matplotlib figure with built-in download support ***
            st.pyplot(pass_fig, clear_figure=True)
            st.caption(f"{TARGET_PLAYER}'s Pass Map (Euro 2024)")
        else:
            st.warning(pass_error)

    # Shot Map
    # *** CHANGE: Now expects a Matplotlib Figure object (shot_fig) ***
    shot_fig, shot_error = plot_player_actions(df_yamal, 'Shot', 'Shots')
    with col2:
        if shot_fig:
            # *** CHANGE: Use st.pyplot() to display the Matplotlib figure with built-in download support ***
            st.pyplot(shot_fig, clear_figure=True)
            st.caption(f"{TARGET_PLAYER}'s Shot Map (Euro 2024)")
        else:
            st.warning(shot_error)

    st.markdown("---")

    # 3. Key Statistics Section
    st.header(f"2. Key Statistics for {TARGET_PLAYER}")
    
    # Calculate Yamal's stats
    yamal_stats = get_player_stats(full_events_df, TARGET_PLAYER)
    
    stats_cols = st.columns(4)
    stats_cols[0].metric("Goals", yamal_stats['Goals'])
    stats_cols[1].metric("Total Shots", yamal_stats['Total Shots'])
    stats_cols[2].metric("Total xG", yamal_stats['Total xG'])
    stats_cols[3].metric("Pass Success Rate", f"{yamal_stats['Pass Success Rate (%)']}%")

    st.markdown("---")
    
    # 4. Comparative Analysis Section
    st.header("3. Comparative Analysis: Top Performers")
    
    comparison_stat = st.selectbox(
        "Select statistic to compare:",
        options=["Goals", "Total Shots", "Total xG", "Pass Success Rate (%)", "Dribble Success Rate (%)"],
        index=2 # Default to xG
    )

    df_comp = get_comparative_stats(full_events_df, comparison_stat, num_players=10)
    
    # Highlight the target player in the comparison table
    def highlight_player(s):
        is_yamal = s['Name'] == TARGET_PLAYER
        # Ensure the styling is applied to the row based on the 'Name' column value
        return ['background-color: #fce8a6' if is_yamal else '' for _ in s]

    st.subheader(f"Top 10 Players by {comparison_stat}")
    
    # Display the styled dataframe
    st.dataframe(
        df_comp.style.apply(highlight_player, axis=1),
        hide_index=True
    )

    st.markdown("""
        *Note: StatsBomb data uses a 0-120 x-axis and 0-80 y-axis for pitch coordinates. 
        `mplsoccer` automatically handles this to display the pitch correctly.*
    """)

if __name__ == '__main__':
    main()