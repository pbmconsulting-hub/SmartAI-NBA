# ============================================================
# FILE: pages/1_🏀_Todays_Games.py
# PURPOSE: Let the user select which NBA teams are playing
#          tonight and enter Vegas lines (spread + total).
#          This context is used by the simulation engine.
# CONNECTS TO: app.py (session state), Analysis page (uses games)
# CONCEPTS COVERED: Forms, multiselect, session state, data tables
# ============================================================

# Import streamlit for the UI
import streamlit as st

# Standard library imports
import datetime  # For today's date

# Import our data manager to get team names
from data.data_manager import load_teams_data, get_all_team_abbreviations

# Import the live games fetcher
# BEGINNER NOTE: We import this here so the button can call it.
# If nba_api is not installed, only the button will fail gracefully —
# the rest of the page (manual entry) still works perfectly.
from data.live_data_fetcher import fetch_todays_games

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Today's Games — SmartAI-NBA",
    page_icon="🏀",
    layout="wide",
)

st.title("🏀 Today's Games")
st.markdown("Select tonight's NBA matchups and enter Vegas lines for each game.")

# ============================================================
# SECTION: Auto-Load Tonight's Games Button
# Fetch real games from the NBA API with one click.
# ============================================================

# BEGINNER NOTE: This button calls the live data fetcher to automatically
# populate tonight's games. It's the fastest way to set up the page!
# If nba_api isn't installed or the API fails, it falls back gracefully.

auto_col, info_col = st.columns([1, 3])  # Button on left, info on right

with auto_col:
    # The Auto-Load button
    auto_load_clicked = st.button(
        "🔄 Auto-Load Tonight's Games",
        use_container_width=True,
        type="primary",   # Make it stand out as the recommended action
        help="Automatically fetch tonight's real NBA matchups from the NBA API",
    )

with info_col:
    # Remind user about the fallback
    st.caption(
        "Click to automatically fetch tonight's real games from the NBA API "
        "(nba_api must be installed). Or use the manual form below."
    )

# Handle the auto-load button click
if auto_load_clicked:
    # Show a spinner while we fetch
    with st.spinner("Fetching tonight's games from NBA API..."):
        fetched_games = fetch_todays_games()  # Call the live fetcher

    if fetched_games:
        # Save to session state so the page updates
        st.session_state["todays_games"] = fetched_games
        st.success(
            f"✅ Loaded **{len(fetched_games)} game(s)** for tonight! "
            "Edit the spreads and totals below if needed."
        )
        # Rerun to refresh the page with the new games showing
        st.rerun()
    else:
        # The API returned nothing — show a helpful message
        st.warning(
            "⚠️ Could not auto-load games. Possible reasons:\n"
            "- `nba_api` is not installed (run: `pip install nba_api`)\n"
            "- No games scheduled tonight\n"
            "- No internet connection\n\n"
            "Please enter games manually using the form below."
        )

# ============================================================
# END SECTION: Auto-Load Tonight's Games Button
# ============================================================

st.divider()

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Load Available Teams
# ============================================================

# Load team data from CSV
all_teams_data = load_teams_data()

# Build a list of team options for the multiselect
# Format: "LAL — Los Angeles Lakers"
team_options = []
for team in all_teams_data:
    abbreviation = team.get("abbreviation", "")
    full_name = team.get("team_name", "")
    if abbreviation and full_name:
        team_options.append(f"{abbreviation} — {full_name}")

# Sort the options alphabetically
team_options.sort()

# ============================================================
# END SECTION: Load Available Teams
# ============================================================

# ============================================================
# SECTION: Game Entry Form
# ============================================================

st.subheader("🏟️ Enter Tonight's Matchups")
st.markdown("Select pairs of teams. Each pair = one game.")

# Use a form so all inputs submit together with one button
with st.form("games_entry_form"):
    st.markdown("**How many games tonight?**")

    # Let user choose how many games to enter (1-8)
    number_of_games = st.number_input(
        "Number of games",
        min_value=1,
        max_value=8,
        value=3,
        step=1,
        help="How many NBA games are being played tonight?",
    )

    st.divider()

    # We'll store the game entries here
    game_entries_from_form = []

    # Create input rows for each game dynamically
    # BEGINNER NOTE: range(int(n)) creates [0, 1, 2, ..., n-1]
    for game_index in range(int(number_of_games)):
        # Each game gets its own row of inputs
        st.markdown(f"**Game {game_index + 1}**")

        # Three columns: home team, away team, and game lines
        col_home, col_away, col_lines = st.columns([2, 2, 3])

        with col_home:
            home_team_selection = st.selectbox(
                f"Home Team",
                options=["— Select —"] + team_options,
                key=f"home_team_{game_index}",  # Unique key for each widget
            )

        with col_away:
            away_team_selection = st.selectbox(
                f"Away Team",
                options=["— Select —"] + team_options,
                key=f"away_team_{game_index}",
            )

        with col_lines:
            # Two sub-columns for spread and total
            col_spread, col_total = st.columns(2)
            with col_spread:
                vegas_spread = st.number_input(
                    "Spread (Home)",
                    min_value=-30.0,
                    max_value=30.0,
                    value=0.0,
                    step=0.5,
                    key=f"spread_{game_index}",
                    help="Positive = home favored, negative = away favored",
                )
            with col_total:
                game_total = st.number_input(
                    "Total (O/U)",
                    min_value=180.0,
                    max_value=270.0,
                    value=220.0,
                    step=0.5,
                    key=f"total_{game_index}",
                    help="Vegas over/under total for this game",
                )

        # Store this game's data temporarily
        # We'll validate it after the form submits
        game_entries_from_form.append({
            "game_index": game_index,
            "home_team_selection": home_team_selection,
            "away_team_selection": away_team_selection,
            "vegas_spread": vegas_spread,
            "game_total": game_total,
        })

        # Small divider between games
        if game_index < int(number_of_games) - 1:
            st.markdown("---")

    # Form submit button
    submit_games_button = st.form_submit_button(
        "✅ Save Tonight's Games",
        use_container_width=True,
        type="primary",
    )

# ============================================================
# END SECTION: Game Entry Form
# ============================================================

# ============================================================
# SECTION: Process Form Submission
# ============================================================

if submit_games_button:
    # Validate and clean the game entries
    valid_games = []
    validation_warnings = []

    for entry in game_entries_from_form:
        home = entry["home_team_selection"]
        away = entry["away_team_selection"]

        # Skip games where teams weren't selected
        if home == "— Select —" or away == "— Select —":
            continue

        # Warn about duplicate team selections
        if home == away:
            validation_warnings.append(
                f"Game {entry['game_index'] + 1}: Home and away team are the same!"
            )
            continue

        # Extract just the abbreviation (before the " — ")
        home_abbrev = home.split(" — ")[0]
        away_abbrev = away.split(" — ")[0]

        # Build a clean game dictionary
        clean_game = {
            "game_id": f"{home_abbrev}_vs_{away_abbrev}",
            "home_team": home_abbrev,
            "away_team": away_abbrev,
            "home_team_full": home,
            "away_team_full": away,
            "vegas_spread": float(entry["vegas_spread"]),
            "game_total": float(entry["game_total"]),
            "game_date": datetime.date.today().isoformat(),
        }
        valid_games.append(clean_game)

    # Show warnings if any
    for warning in validation_warnings:
        st.warning(f"⚠️ {warning}")

    if valid_games:
        # Save to session state so other pages can access it
        st.session_state["todays_games"] = valid_games
        st.success(f"✅ Saved {len(valid_games)} game(s) for tonight!")
    else:
        st.error("No valid games entered. Please select home and away teams.")

# ============================================================
# END SECTION: Process Form Submission
# ============================================================

# ============================================================
# SECTION: Display Current Games
# Show the games that have been entered (persists across sessions)
# ============================================================

current_games = st.session_state.get("todays_games", [])

if current_games:
    st.divider()
    st.subheader(f"🏟️ Tonight's {len(current_games)} Game(s)")

    # Display each game as a row
    for game in current_games:
        col_matchup, col_spread, col_total = st.columns([3, 1, 1])

        with col_matchup:
            # Show the matchup with a vs. format
            st.markdown(
                f"**{game['away_team']}** @ **{game['home_team']}**"
            )

        with col_spread:
            # Format the spread (positive = home favored)
            spread_value = game.get("vegas_spread", 0)
            if spread_value > 0:
                spread_text = f"Home -{spread_value}"
            elif spread_value < 0:
                spread_text = f"Away -{abs(spread_value)}"
            else:
                spread_text = "PK (Pick'em)"
            st.caption(f"Spread: {spread_text}")

        with col_total:
            st.caption(f"Total: {game.get('game_total', 220)}")

    # Button to clear all games
    if st.button("🗑️ Clear All Games"):
        st.session_state["todays_games"] = []
        st.rerun()  # Refresh the page to show empty state

else:
    # Show helpful message when no games are entered
    st.info(
        "👆 No games entered yet. Select teams above and click **Save Tonight's Games**."
        "\n\nThe game context (spread, total, home/away) improves the model's accuracy."
    )

# ============================================================
# END SECTION: Display Current Games
# ============================================================

# ============================================================
# SECTION: Help / Tips
# ============================================================

with st.expander("💡 Tips for Best Results"):
    st.markdown("""
    - **Vegas Spread:** Enter as the home team's spread.
      - If Lakers are favored by 5.5, enter **+5.5**
      - If Lakers are a 5.5-point underdog, enter **-5.5**

    - **Total (O/U):** The Vegas over/under for the game (usually 210-235).
      High totals (230+) mean a fast-paced, high-scoring game is expected.

    - **Why it matters:** The model uses this to:
      - Adjust for blowout risk (large spreads = more garbage time)
      - Adjust for pace and scoring environment (total)
      - Set home/away bonuses for each player

    - **Don't have the lines?** Just skip this page.
      The model will use default (neutral) values.
    """)

# ============================================================
# END SECTION: Help / Tips
# ============================================================
