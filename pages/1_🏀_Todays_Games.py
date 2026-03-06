# ============================================================
# FILE: pages/1_🏀_Todays_Games.py
# PURPOSE: Display tonight's NBA games as rich visual cards.
#          Auto-loads games from the NBA API on page visit,
#          shows team records, key players, and streaks.
# CONNECTS TO: app.py (session state), Analysis page (uses games)
# ============================================================

import streamlit as st
import datetime
from data.data_manager import load_teams_data, get_all_team_abbreviations, find_players_by_team, load_players_data
from data.live_data_fetcher import fetch_todays_games, fetch_todays_players_only

# ============================================================
# SECTION: Page Setup & CSS
# ============================================================

st.set_page_config(
    page_title="Today's Games — SmartAI-NBA",
    page_icon="🏀",
    layout="wide",
)

# Custom CSS for game cards
st.markdown("""
<style>
.game-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border: 1px solid #e94560;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    color: #ffffff;
}
.game-header {
    font-size: 1.25rem;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 8px;
}
.team-badge {
    display: inline-block;
    background: #e94560;
    color: white;
    font-weight: 700;
    font-size: 0.9rem;
    padding: 3px 8px;
    border-radius: 6px;
    margin: 0 4px;
}
.record-tag {
    color: #a0aec0;
    font-size: 0.85rem;
}
.game-meta {
    color: #63b3ed;
    font-size: 0.9rem;
    margin: 4px 0;
}
.streak-hot {
    color: #f6ad55;
    font-weight: 600;
}
.streak-cold {
    color: #63b3ed;
    font-weight: 600;
}
.key-players {
    background: rgba(255,255,255,0.07);
    border-radius: 8px;
    padding: 10px 14px;
    margin-top: 10px;
    font-size: 0.88rem;
    color: #e2e8f0;
}
.lines-row {
    color: #68d391;
    font-size: 0.92rem;
    margin-top: 6px;
}
.divider-line {
    border-top: 1px solid rgba(255,255,255,0.15);
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Setup & CSS
# ============================================================

st.title("🏀 Today's Games")
st.markdown(f"**{datetime.date.today().strftime('%A, %B %d, %Y')}** — Tonight's NBA Slate")

# ============================================================
# SECTION: Auto-Load Controls
# ============================================================

auto_col, fetch_col, info_col = st.columns([1, 1, 3])

with auto_col:
    auto_load_clicked = st.button(
        "🔄 Auto-Load Tonight's Games",
        use_container_width=True,
        type="primary",
        help="Fetch tonight's real NBA matchups from the NBA API",
    )

with fetch_col:
    fetch_players_clicked = st.button(
        "⚡ Fetch Players (Today Only)",
        use_container_width=True,
        help="Fetch player stats ONLY for tonight's teams (fast: 1-2 min)",
    )

with info_col:
    st.caption(
        "🔄 Auto-Load fetches tonight's games. "
        "⚡ Fetch Players gets only today's rosters (much faster than full update)."
    )

# Handle auto-load
if auto_load_clicked:
    with st.spinner("Fetching tonight's games from NBA API..."):
        fetched_games = fetch_todays_games()

    if fetched_games:
        st.session_state["todays_games"] = fetched_games
        st.success(
            f"✅ Loaded **{len(fetched_games)} game(s)** for tonight! "
            "Edit the spreads and totals below if needed."
        )
        st.rerun()
    else:
        st.warning(
            "⚠️ Could not auto-load games. Possible reasons:\n"
            "- `nba_api` is not installed (run: `pip install nba_api`)\n"
            "- No games scheduled tonight\n"
            "- No internet connection\n\n"
            "Please enter games manually using the form below."
        )

# Handle targeted player fetch
if fetch_players_clicked:
    current_games = st.session_state.get("todays_games", [])
    if not current_games:
        st.warning("⚠️ Load tonight's games first before fetching players.")
    else:
        progress_bar = st.progress(0, text="Starting targeted player fetch...")

        def _update_progress(current, total, message):
            frac = min(current / max(total, 1), 1.0)
            progress_bar.progress(frac, text=message)

        success = fetch_todays_players_only(current_games, progress_callback=_update_progress)
        progress_bar.empty()
        if success:
            st.success("✅ Player data updated for tonight's teams only!")
        else:
            st.error("❌ Could not fetch player data. Check the console for details.")

st.divider()

# ============================================================
# SECTION: Game Cards Display
# ============================================================

current_games = st.session_state.get("todays_games", [])
players_data = load_players_data()

def get_top_players_for_team(team_abbrev, players, top_n=2):
    """Return top N players by points average for a team."""
    team_players = find_players_by_team(players, team_abbrev)
    team_players_sorted = sorted(team_players, key=lambda p: float(p.get("points_avg", 0) or 0), reverse=True)
    return team_players_sorted[:top_n]


def format_key_players(team_abbrev, players):
    """Format a short string showing key players and their PPG."""
    top_players = get_top_players_for_team(team_abbrev, players, top_n=2)
    if not top_players:
        return "—"
    parts = []
    for p in top_players:
        name_parts = p.get("name", "").split()
        short_name = name_parts[-1] if name_parts else p.get("name", "")
        ppg = p.get("points_avg", "?")
        parts.append(f"{short_name} ({ppg} PPG)")
    return " | ".join(parts)


if current_games:
    st.subheader(f"🏟️ Tonight's {len(current_games)} Game(s)")

    for game in current_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        home_name = game.get("home_team_name", home)
        away_name = game.get("away_team_name", away)
        home_record = game.get("home_record", "")
        away_record = game.get("away_record", "")
        spread = game.get("vegas_spread", 0.0)
        total = game.get("game_total", 220.0)
        game_status = game.get("game_status", "")

        home_record_str = f" ({home_record})" if home_record else ""
        away_record_str = f" ({away_record})" if away_record else ""

        spread_text = "Pick'em"
        if spread > 0:
            spread_text = f"{home} -{spread}"
        elif spread < 0:
            spread_text = f"{away} -{abs(spread)}"

        home_key_players = format_key_players(home, players_data)
        away_key_players = format_key_players(away, players_data)

        game_time_display = ""
        if game_status:
            game_time_display = f"📍 {game_status}"

        card_html = f"""
<div class="game-card">
  <div class="game-header">
    🏠 <span class="team-badge">{home}</span> {home_name}{home_record_str}
    &nbsp;vs&nbsp;
    <span class="team-badge">{away}</span> {away_name}{away_record_str}
  </div>
  <div class="divider-line"></div>
  {f'<div class="game-meta">{game_time_display}</div>' if game_time_display else ''}
  <div class="lines-row">📊 Spread: {spread_text} &nbsp;|&nbsp; O/U: {total}</div>
  <div class="key-players">
    <b>{home}:</b> {home_key_players}<br>
    <b>{away}:</b> {away_key_players}
  </div>
</div>
"""
        st.markdown(card_html, unsafe_allow_html=True)

    # Button to clear
    if st.button("��️ Clear All Games"):
        st.session_state["todays_games"] = []
        st.rerun()

else:
    st.info(
        "👆 No games loaded yet. Click **🔄 Auto-Load Tonight's Games** above, "
        "or enter games manually below."
    )

st.divider()

# ============================================================
# SECTION: Manual Entry Form
# ============================================================

all_teams_data = load_teams_data()
team_options = []
for team in all_teams_data:
    abbreviation = team.get("abbreviation", "")
    full_name = team.get("team_name", "")
    if abbreviation and full_name:
        team_options.append(f"{abbreviation} — {full_name}")
team_options.sort()

with st.expander("✏️ Manual Game Entry", expanded=(not current_games)):
    st.markdown("Enter matchups manually — useful when the auto-loader can't reach the API.")

    with st.form("games_entry_form"):
        st.markdown("**How many games tonight?**")
        number_of_games = st.number_input(
            "Number of games",
            min_value=1,
            max_value=12,
            value=3,
            step=1,
        )

        st.divider()
        game_entries_from_form = []

        for game_index in range(int(number_of_games)):
            st.markdown(f"**Game {game_index + 1}**")
            col_home, col_away, col_lines = st.columns([2, 2, 3])

            with col_home:
                home_team_selection = st.selectbox(
                    "Home Team",
                    options=["— Select —"] + team_options,
                    key=f"home_team_{game_index}",
                )
            with col_away:
                away_team_selection = st.selectbox(
                    "Away Team",
                    options=["— Select —"] + team_options,
                    key=f"away_team_{game_index}",
                )
            with col_lines:
                col_spread, col_total = st.columns(2)
                with col_spread:
                    vegas_spread = st.number_input(
                        "Spread (Home)",
                        min_value=-30.0, max_value=30.0,
                        value=0.0, step=0.5,
                        key=f"spread_{game_index}",
                        help="Positive = home favored",
                    )
                with col_total:
                    game_total = st.number_input(
                        "Total (O/U)",
                        min_value=180.0, max_value=270.0,
                        value=220.0, step=0.5,
                        key=f"total_{game_index}",
                    )

            game_entries_from_form.append({
                "game_index": game_index,
                "home_team_selection": home_team_selection,
                "away_team_selection": away_team_selection,
                "vegas_spread": vegas_spread,
                "game_total": game_total,
            })

            if game_index < int(number_of_games) - 1:
                st.markdown("---")

        submit_games_button = st.form_submit_button(
            "✅ Save Tonight's Games",
            use_container_width=True,
            type="primary",
        )

    if submit_games_button:
        valid_games = []
        validation_warnings = []

        for entry in game_entries_from_form:
            home = entry["home_team_selection"]
            away = entry["away_team_selection"]
            if home == "— Select —" or away == "— Select —":
                continue
            if home == away:
                validation_warnings.append(
                    f"Game {entry['game_index'] + 1}: Home and away team are the same!"
                )
                continue
            home_abbrev = home.split(" — ")[0]
            away_abbrev = away.split(" — ")[0]
            home_full_name = home.split(" — ")[1] if " — " in home else home_abbrev
            away_full_name = away.split(" — ")[1] if " — " in away else away_abbrev

            clean_game = {
                "game_id": f"{home_abbrev}_vs_{away_abbrev}",
                "home_team": home_abbrev,
                "away_team": away_abbrev,
                "home_team_full": home,
                "away_team_full": away,
                "home_team_name": home_full_name,
                "away_team_name": away_full_name,
                "home_record": "",
                "away_record": "",
                "game_status": "",
                "vegas_spread": float(entry["vegas_spread"]),
                "game_total": float(entry["game_total"]),
                "game_date": datetime.date.today().isoformat(),
            }
            valid_games.append(clean_game)

        for warning in validation_warnings:
            st.warning(f"⚠️ {warning}")

        if valid_games:
            st.session_state["todays_games"] = valid_games
            st.success(f"✅ Saved {len(valid_games)} game(s) for tonight!")
            st.rerun()
        else:
            st.error("No valid games entered. Please select home and away teams.")

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

    - **⚡ Fetch Players (Today Only):** After loading games, use this to pull
      CURRENT rosters and recent stats for tonight's teams only.
      Much faster (1-2 min) than the full data update!

    - **Key Players** shown in the cards come from your loaded player data.
      Use ⚡ Fetch Players to ensure these are accurate.
    """)
