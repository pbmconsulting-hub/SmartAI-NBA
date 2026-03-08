# ============================================================
# FILE: pages/1_🏀_Todays_Games.py
# PURPOSE: Show tonight's NBA matchups as rich visual game cards.
#          Auto-loads games and lets user enter Vegas lines.
# CONNECTS TO: app.py (session state), Analysis page (uses games)
# ============================================================

import streamlit as st
import datetime
import threading
import time

from data.data_manager import load_teams_data, get_all_team_abbreviations, find_players_by_team, load_players_data
from data.live_data_fetcher import fetch_todays_games, fetch_todays_players_only, fetch_all_todays_data

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Live Games — SmartBetPro NBA",
    page_icon="📡",
    layout="wide",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)

# ─── Custom CSS ────────────────────────────────────────────
st.markdown("""
<style>
/* Game card wrapper — enhanced dark glass with cyan glow */
.game-card {
    background: linear-gradient(135deg, rgba(13,18,40,0.95) 0%, rgba(11,18,35,0.98) 100%);
    border: 1px solid rgba(0,240,255,0.18);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 0 20px rgba(0,240,255,0.07), 0 4px 20px rgba(0,0,0,0.5);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.game-card:hover {
    border-color: rgba(0,240,255,0.40);
    box-shadow: 0 0 30px rgba(0,240,255,0.15), 0 6px 24px rgba(0,0,0,0.6);
    transform: translateY(-3px);
    transition: all 0.2s ease;
}
/* Team badge */
.team-badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 1px;
    color: #ffffff;
    background: rgba(0,240,255,0.12);
    border: 1px solid rgba(0,240,255,0.25);
    margin-right: 6px;
}
.home-badge { background: rgba(0,240,255,0.12); border-color: rgba(0,240,255,0.25); }
.away-badge { background: rgba(200,0,255,0.12); border-color: rgba(200,0,255,0.25); }
/* Record text */
.record-text { color: #8a9bb8; font-size: 0.9rem; }
/* Streak positive/negative */
.streak-hot { color: #00ff9d; font-weight: 700; text-shadow: 0 0 6px rgba(0,255,157,0.5); }
.streak-cold { color: #ff6b6b; font-weight: 700; }
.streak-neutral { color: rgba(255,255,255,0.85); font-weight: 600; }
/* Game meta info */
.game-meta { color: #8a9bb8; font-size: 0.85rem; margin-top: 4px; }
/* Divider */
.vs-divider {
    text-align: center;
    font-size: 1.5rem;
    color: #ff5e00;
    font-weight: 800;
    padding: 0 10px;
    text-shadow: 0 0 10px rgba(255,94,0,0.6);
}
/* Key players row */
.key-players { margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(0,240,255,0.12); }
.key-players-title { color: #8a9bb8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; }
.player-stat { color: rgba(255,255,255,0.85); font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("📡 Live Games")
st.markdown(f"**{datetime.date.today().strftime('%A, %B %d, %Y')}** — Tonight's NBA Slate")

# ============================================================
# SECTION: Auto-Load Tonight's Games
# ============================================================

auto_col, fetch_col, info_col = st.columns([1, 1, 2])

with auto_col:
    auto_load_clicked = st.button(
        "🔄 Auto-Load Tonight's Games",
        use_container_width=True,
        type="primary",
        help="ONE CLICK: fetch tonight's games + current rosters + player stats + team stats",
    )

with fetch_col:
    fetch_players_clicked = st.button(
        "⚡ Fetch Players Only",
        use_container_width=True,
        help="Re-fetch player stats for tonight's teams (games must already be loaded)",
    )

with info_col:
    st.caption(
        "**Auto-Load** = one click does everything: games + rosters + player stats. "
        "Use **Fetch Players Only** to refresh player data when games are already loaded."
    )


def _run_auto_load_background():
    """Run the auto-load in a background thread, storing progress in session state."""
    try:
        st.session_state["autoload_status"] = "running"
        st.session_state["autoload_progress"] = "Starting one-click load…"

        def progress_cb(current, total, message):
            st.session_state["autoload_progress"] = (
                f"Step {current}/{total} — {message}"
            )

        result = fetch_all_todays_data(progress_callback=progress_cb)

        games_loaded = result.get("games", [])
        if games_loaded:
            st.session_state["todays_games"] = games_loaded
            players_ok = result.get("players_updated", False)
            teams_ok = result.get("teams_updated", False)
            st.session_state["autoload_result_msg"] = (
                f"✅ Loaded **{len(games_loaded)} game(s)** for tonight! "
                f"Players: {'✅' if players_ok else '⚠️ failed'} | "
                f"Teams: {'✅' if teams_ok else '⚠️ failed'}"
            )
            st.session_state["autoload_status"] = "done"
        else:
            st.session_state["autoload_result_msg"] = (
                "⚠️ Could not auto-load games. Possible reasons:\n"
                "- `nba_api` is not installed (run: `pip install nba_api`)\n"
                "- No games scheduled tonight\n"
                "- No internet connection\n\n"
                "Please enter games manually using the form below."
            )
            st.session_state["autoload_status"] = "no_games"

        st.session_state["autoload_progress"] = "Complete!"
    except Exception as exc:
        st.session_state["autoload_status"] = "error"
        st.session_state["autoload_progress"] = str(exc)
        st.session_state["autoload_result_msg"] = str(exc)


if auto_load_clicked:
    if st.session_state.get("autoload_status") != "running":
        st.session_state["autoload_status"] = "running"
        st.session_state["autoload_progress"] = "Starting…"
        st.session_state["autoload_result_msg"] = ""
        thread = threading.Thread(target=_run_auto_load_background, daemon=True)
        thread.start()

# ── Polling display while background load is running ──────────
_autoload_status = st.session_state.get("autoload_status")


def _parse_progress_fraction(progress_text):
    """Parse 'Step X/Y — ...' string and return fraction (0.0–1.0)."""
    import re
    m = re.search(r"Step\s+(\d+)\s*/\s*(\d+)", progress_text or "")
    if m:
        current, total = int(m.group(1)), int(m.group(2))
        if total > 0:
            return min(1.0, current / total)
    return 0.0


if _autoload_status == "running":
    progress_text = st.session_state.get("autoload_progress", "Loading…")
    frac = _parse_progress_fraction(progress_text)
    st.progress(frac, text=f"⏳ {progress_text}")
    time.sleep(2)
    st.rerun()
elif _autoload_status == "done":
    st.success(st.session_state.get("autoload_result_msg", "✅ Auto-load complete!"))
    st.session_state["autoload_status"] = None
    st.rerun()
elif _autoload_status == "no_games":
    st.warning(st.session_state.get("autoload_result_msg", "⚠️ No games found."))
    st.session_state["autoload_status"] = None
elif _autoload_status == "error":
    st.error(f"❌ Auto-load failed: {st.session_state.get('autoload_result_msg', 'Unknown error')}")
    st.session_state["autoload_status"] = None

if fetch_players_clicked:
    todays_games_for_fetch = st.session_state.get("todays_games", [])
    if not todays_games_for_fetch:
        st.warning(
            "⚠️ No games loaded yet. Click **Auto-Load Tonight's Games** first, "
            "or add games manually below."
        )
    else:
        progress_bar2 = st.progress(0, text="Fetching player data for tonight's teams...")
        status_text2 = st.empty()

        def _fetch_players_progress(current, total, message):
            frac = current / max(total, 1)
            progress_bar2.progress(frac, text=message)
            status_text2.caption(message)

        with st.spinner("⚡ Fetching current rosters and player stats..."):
            success = fetch_todays_players_only(
                todays_games_for_fetch,
                progress_callback=_fetch_players_progress,
            )

        progress_bar2.empty()
        status_text2.empty()

        if success:
            st.success("✅ Player stats refreshed for tonight's teams!")
            st.rerun()
        else:
            st.error(
                "❌ Could not fetch player stats. Check your internet connection "
                "or try the Update Data page."
            )

st.divider()

st.markdown(get_education_box_html(
    "📖 Understanding NBA Game Context",
    """
    <strong>Spread</strong>: The Vegas point spread. A spread of +5 means the home team is expected to win by 5 points. 
    Useful for estimating blowout risk — in a blowout, stars often sit the 4th quarter.<br><br>
    <strong>Game Total (O/U)</strong>: The Vegas over/under for combined score of both teams. 
    A high total (e.g., 230+) means Vegas expects a fast-paced, high-scoring game, boosting all players' stat projections.<br><br>
    <strong>Why it matters</strong>: These numbers adjust our AI projections — a high total gives players +5-8% stat boost, 
    while a large spread increases blowout risk and reduces projected minutes for stars.
    """
), unsafe_allow_html=True)

# ============================================================
# SECTION: Display Current Games as Rich Cards
# ============================================================

current_games = st.session_state.get("todays_games", [])
players_data = load_players_data()

if current_games:
    st.subheader(f"🏟️ Tonight's Slate — {len(current_games)} Game(s)")
    st.markdown("")

    for game in current_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        home_name = game.get("home_team_name", home)
        away_name = game.get("away_team_name", away)

        home_w = game.get("home_wins", 0)
        home_l = game.get("home_losses", 0)
        away_w = game.get("away_wins", 0)
        away_l = game.get("away_losses", 0)

        home_streak = game.get("home_streak", "")
        away_streak = game.get("away_streak", "")
        game_time = game.get("game_time_et", "")
        arena = game.get("arena", "")
        spread = game.get("vegas_spread", 0.0)
        total = game.get("game_total", 220.0)

        # Format streak with color class
        def streak_html(s):
            if not s:
                return ""
            if s.startswith("W"):
                return f'<span class="streak-hot">🔥 {s} streak</span>'
            elif s.startswith("L"):
                return f'<span class="streak-cold">❄️ {s} streak</span>'
            return f'<span class="streak-neutral">{s}</span>'

        # Top 2 players for each team
        home_players = find_players_by_team(players_data, home)[:2]
        away_players = find_players_by_team(players_data, away)[:2]

        def player_line(players):
            if not players:
                return "<em style='color:#718096'>No data loaded</em>"
            parts = []
            for p in players:
                name_parts = p.get("name", "").split()
                short_name = f"{name_parts[0][0]}. {' '.join(name_parts[1:])}" if len(name_parts) > 1 else p.get("name", "")
                pts = p.get("points_avg", "—")
                parts.append(f"<span class='player-stat'>{short_name} ({pts} PPG)</span>")
            return " &nbsp;|&nbsp; ".join(parts)

        # Spread display
        if spread > 0:
            spread_text = f"{home} -{spread}"
        elif spread < 0:
            spread_text = f"{away} -{abs(spread)}"
        else:
            spread_text = "Pick'em"

        # Build game meta line
        meta_parts = []
        if game_time:
            meta_parts.append(f"🕐 {game_time}")
        if arena:
            meta_parts.append(f"📍 {arena}")
        meta_line = " &nbsp;•&nbsp; ".join(meta_parts) if meta_parts else ""

        # Lines info
        lines_parts = []
        if spread != 0:
            lines_parts.append(f"Spread: {spread_text}")
        lines_parts.append(f"O/U: {total}")
        lines_line = " &nbsp;|&nbsp; ".join(lines_parts)

        # Render card
        card_html = f"""
<div class="game-card">
  <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
    <span class="team-badge away-badge">🚌 {away}</span>
    <span style="color:#a0aec0; font-size:1rem;">{away_name}</span>
    <span style="color:#718096; font-size:0.9rem;">({away_w}-{away_l})</span>
    {streak_html(away_streak)}
  </div>
  <div class="vs-divider" style="margin:8px 0;">VS</div>
  <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
    <span class="team-badge home-badge">🏠 {home}</span>
    <span style="color:#a0aec0; font-size:1rem;">{home_name}</span>
    <span style="color:#718096; font-size:0.9rem;">({home_w}-{home_l})</span>
    {streak_html(home_streak)}
  </div>
  {f'<div class="game-meta">{meta_line}</div>' if meta_line else ''}
  <div class="game-meta" style="margin-top:6px;">📊 {lines_line}</div>
  <div class="key-players">
    <div class="key-players-title">Key Players</div>
    <div style="margin-top:6px; display:flex; gap:20px; flex-wrap:wrap;">
      <div><span style="color:#63b3ed; font-weight:600;">{away}:</span> {player_line(away_players)}</div>
      <div><span style="color:#68d391; font-weight:600;">{home}:</span> {player_line(home_players)}</div>
    </div>
  </div>
</div>
"""
        st.markdown(card_html, unsafe_allow_html=True)

    # Edit spreads/totals inline
    with st.expander("✏️ Edit Spreads & Totals", expanded=False):
        st.markdown("Adjust Vegas lines for each game:")
        updated_games = []
        for i, game in enumerate(current_games):
            col_label, col_spread, col_total = st.columns([3, 2, 2])
            with col_label:
                st.markdown(f"**{game['away_team']} @ {game['home_team']}**")
            with col_spread:
                new_spread = st.number_input(
                    "Spread (Home)",
                    min_value=-30.0, max_value=30.0,
                    value=float(game.get("vegas_spread", 0.0)), step=0.5,
                    key=f"edit_spread_{i}",
                )
            with col_total:
                new_total = st.number_input(
                    "Total (O/U)",
                    min_value=180.0, max_value=270.0,
                    value=float(game.get("game_total", 220.0)), step=0.5,
                    key=f"edit_total_{i}",
                )
            updated_game = dict(game)
            updated_game["vegas_spread"] = new_spread
            updated_game["game_total"] = new_total
            updated_games.append(updated_game)

        col_save, col_clear = st.columns([1, 1])
        with col_save:
            if st.button("💾 Save Changes", type="primary"):
                st.session_state["todays_games"] = updated_games
                st.success("✅ Lines updated!")
                st.rerun()
        with col_clear:
            if st.button("🗑️ Clear All Games"):
                st.session_state["todays_games"] = []
                st.rerun()

else:
    st.info(
        "👆 No games loaded yet. Click **Auto-Load Tonight's Games** above, "
        "or use the manual form below."
    )

st.divider()

# ============================================================
# SECTION: Manual Game Entry Form
# ============================================================

with st.expander("➕ Manually Add Games", expanded=not bool(current_games)):
    all_teams_data = load_teams_data()
    team_options = []
    for team in all_teams_data:
        abbreviation = team.get("abbreviation", "")
        full_name = team.get("team_name", "")
        if abbreviation and full_name:
            team_options.append(f"{abbreviation} — {full_name}")
    team_options.sort()

    with st.form("games_entry_form"):
        st.markdown("**How many games tonight?**")
        number_of_games = st.number_input(
            "Number of games",
            min_value=1, max_value=8, value=3, step=1,
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

            clean_game = {
                "game_id": f"{home_abbrev}_vs_{away_abbrev}",
                "home_team": home_abbrev,
                "away_team": away_abbrev,
                "home_team_full": home,
                "away_team_full": away,
                "home_team_name": home.split(" — ")[1] if " — " in home else home,
                "away_team_name": away.split(" — ")[1] if " — " in away else away,
                "vegas_spread": float(entry["vegas_spread"]),
                "game_total": float(entry["game_total"]),
                "game_date": datetime.date.today().isoformat(),
                "home_wins": 0, "home_losses": 0, "home_streak": "",
                "away_wins": 0, "away_losses": 0, "away_streak": "",
            }
            valid_games.append(clean_game)

        for warning in validation_warnings:
            st.warning(f"⚠️ {warning}")

        if valid_games:
            existing = st.session_state.get("todays_games", [])
            combined = existing + valid_games
            st.session_state["todays_games"] = combined
            st.success(f"✅ Added {len(valid_games)} game(s)!")
            st.rerun()
        else:
            st.error("No valid games entered. Please select home and away teams.")

# ============================================================
# SECTION: Tips
# ============================================================

with st.expander("💡 Tips for Best Results"):
    st.markdown("""
    - **Vegas Spread:** Positive = home favored, negative = away favored.
      E.g., +5.5 means the home team is favored by 5.5 points.

    - **Total (O/U):** The Vegas over/under for the game (usually 210–235).

    - **Auto-Load**: Fetches live game data + team records (W-L, streaks) from the NBA API.

    - **Key Players**: Loaded from your player database. Go to **Update Data** to
      refresh with today's team rosters.
    """)
