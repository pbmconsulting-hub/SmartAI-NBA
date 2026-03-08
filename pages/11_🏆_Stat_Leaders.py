# ============================================================
# FILE: pages/11_🏆_Stat_Leaders.py
# PURPOSE: Show leaderboards for tonight's slate players using
#          data from load_players_data().  5 stat tabs with
#          QDS-styled leaderboard cards, trend indicators, and
#          injury status badges.
# ============================================================

import streamlit as st
import datetime

from data.data_manager import (
    load_players_data,
    load_injury_status,
    get_player_status,
    EXCLUDE_STATUSES,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Stat Leaders — SmartBetPro NBA",
    page_icon="🏆",
    layout="wide",
)

from styles.theme import get_global_css, get_qds_css
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

st.title("🏆 Stat Leaders")
st.markdown("Top performers across key statistical categories for tonight's slate.")

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Data Loading
# ============================================================

players_data = load_players_data()
injury_map = load_injury_status()
todays_games = st.session_state.get("todays_games", [])

# Build set of teams playing tonight
playing_teams: set = set()
for g in todays_games:
    playing_teams.add(g.get("home_team", "").upper())
    playing_teams.add(g.get("away_team", "").upper())
playing_teams.discard("")

# ============================================================
# END SECTION: Data Loading
# ============================================================

# Toggle: Tonight's players only
tonight_only = st.toggle(
    "🏀 Tonight's Players Only",
    value=True,
    help="When ON, only show players on teams playing tonight.",
)

if tonight_only and playing_teams:
    display_players = [
        p for p in players_data
        if p.get("team", "").upper() in playing_teams
    ]
    if not display_players:
        st.warning(
            "⚠️ No players found for tonight's teams. "
            "Load games on **📡 Live Games** first, or turn off the toggle."
        )
        display_players = players_data
elif tonight_only and not playing_teams:
    st.info("💡 No games loaded yet. Showing all players. Load games on **📡 Live Games** first.")
    display_players = players_data
else:
    display_players = players_data

# ============================================================
# SECTION: Helper Functions
# ============================================================

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

def _trend_indicator(recent_avg, season_avg):
    """Compare recent 10-game avg to season avg and return trend arrow."""
    if season_avg <= 0:
        return "→"
    ratio = recent_avg / season_avg
    if ratio >= 1.10:
        return "▲"
    if ratio <= 0.90:
        return "▼"
    return "→"

def _trend_color(indicator):
    return {"▲": "#00ff88", "▼": "#ff3860", "→": "#8a9bb8"}.get(indicator, "#8a9bb8")

def _injury_badge_html(status):
    colors = {
        "Active":          ("#00ff88", "#000"),
        "Probable":        ("#00cc66", "#000"),
        "Questionable":    ("#ffd700", "#000"),
        "GTD":             ("#ffd700", "#000"),
        "Day-to-Day":      ("#ffa500", "#000"),
        "Doubtful":        ("#ff6600", "#fff"),
        "Out":             ("#ff3366", "#fff"),
        "Injured Reserve": ("#cc0033", "#fff"),
    }
    bg, fg = colors.get(status, ("#555", "#fff"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 7px;'
        f'border-radius:4px;font-size:0.72rem;font-weight:700;">{status}</span>'
    )

def _matchup_str(team_abbrev):
    """Return opponent string for tonight, or empty if not playing."""
    for g in todays_games:
        home = g.get("home_team", "").upper()
        away = g.get("away_team", "").upper()
        if team_abbrev.upper() == home:
            return f"vs {away}"
        if team_abbrev.upper() == away:
            return f"@ {home}"
    return ""

def _render_leaderboard(players_sorted, stat_key, stat_label, recent_key=None):
    """Render QDS-styled leaderboard cards for a stat."""
    for rank, player in enumerate(players_sorted[:15], 1):
        name = player.get("name", "Unknown")
        team = player.get("team", "")
        avg = float(player.get(stat_key, 0) or 0)
        recent_avg = float(player.get(recent_key, avg) or avg) if recent_key else avg
        trend = _trend_indicator(recent_avg, avg)
        trend_clr = _trend_color(trend)

        # Injury status
        status_info = get_player_status(name, injury_map)
        status = status_info.get("status", "Active")
        badge_html = _injury_badge_html(status)

        # Matchup
        matchup = _matchup_str(team)

        # Medal / rank
        rank_display = _MEDALS.get(rank, str(rank))

        # Tier color for border (top 3 = gold/silver/bronze, rest = subtle)
        border_color = {1: "#ffcc00", 2: "#a0b4d0", 3: "#ff5e00"}.get(rank, "rgba(0,240,255,0.15)")

        st.markdown(
            f'<div style="display:flex;align-items:center;gap:15px;padding:12px 16px;'
            f'background:rgba(20,25,43,0.7);border-radius:8px;'
            f'border-left:3px solid {border_color};margin-bottom:8px;">'
            f'<span style="font-size:1.5rem;min-width:40px;text-align:center;">{rank_display}</span>'
            f'<div style="flex:1;">'
            f'<strong style="color:#fff;font-size:1rem;">{name}</strong> '
            f'<span style="background:rgba(0,240,255,0.15);color:#c0d0e8;'
            f'padding:1px 6px;border-radius:4px;font-size:0.75rem;font-weight:700;">{team}</span>'
            + (f'<span style="color:#8a9bb8;font-size:0.78rem;margin-left:8px;">{matchup}</span>' if matchup else "")
            + f'</div>'
            f'<div style="text-align:right;margin-right:12px;">'
            f'<div style="font-size:1.4rem;font-weight:700;color:#00ffd5;">{avg:.1f}</div>'
            f'<div style="font-size:0.75rem;color:#8a9bb8;">{stat_label}</div>'
            f'</div>'
            f'<div style="font-size:1.3rem;color:{trend_clr};min-width:24px;text-align:center;">{trend}</div>'
            f'<div style="min-width:80px;">{badge_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ============================================================
# END SECTION: Helper Functions
# ============================================================

# ============================================================
# SECTION: Stat Tabs
# ============================================================

tab_pts, tab_reb, tab_ast, tab_3pt, tab_stblk = st.tabs(
    ["🏀 Points", "💪 Rebounds", "🎯 Assists", "3️⃣ 3-Pointers", "🛡️ Steals+Blocks"]
)

# Points Tab
with tab_pts:
    st.subheader("🏀 Points Per Game Leaders")
    sorted_pts = sorted(
        [p for p in display_players if float(p.get("points_avg", 0) or 0) > 0],
        key=lambda p: float(p.get("points_avg", 0) or 0),
        reverse=True,
    )
    if sorted_pts:
        _render_leaderboard(sorted_pts, "points_avg", "PPG")
    else:
        st.info("No player data available.")

# Rebounds Tab
with tab_reb:
    st.subheader("💪 Rebounds Per Game Leaders")
    sorted_reb = sorted(
        [p for p in display_players if float(p.get("rebounds_avg", 0) or 0) > 0],
        key=lambda p: float(p.get("rebounds_avg", 0) or 0),
        reverse=True,
    )
    if sorted_reb:
        _render_leaderboard(sorted_reb, "rebounds_avg", "RPG")
    else:
        st.info("No player data available.")

# Assists Tab
with tab_ast:
    st.subheader("🎯 Assists Per Game Leaders")
    sorted_ast = sorted(
        [p for p in display_players if float(p.get("assists_avg", 0) or 0) > 0],
        key=lambda p: float(p.get("assists_avg", 0) or 0),
        reverse=True,
    )
    if sorted_ast:
        _render_leaderboard(sorted_ast, "assists_avg", "APG")
    else:
        st.info("No player data available.")

# 3-Pointers Tab
with tab_3pt:
    st.subheader("3️⃣ 3-Pointers Per Game Leaders")
    sorted_3pt = sorted(
        [p for p in display_players if float(p.get("threes_avg", 0) or 0) > 0],
        key=lambda p: float(p.get("threes_avg", 0) or 0),
        reverse=True,
    )
    if sorted_3pt:
        _render_leaderboard(sorted_3pt, "threes_avg", "3PG")
    else:
        st.info("No player data available.")

# Steals+Blocks Tab
with tab_stblk:
    st.subheader("🛡️ Steals + Blocks Per Game Leaders")
    sorted_stblk = sorted(
        [p for p in display_players if (
            float(p.get("steals_avg", 0) or 0) + float(p.get("blocks_avg", 0) or 0)
        ) > 0],
        key=lambda p: float(p.get("steals_avg", 0) or 0) + float(p.get("blocks_avg", 0) or 0),
        reverse=True,
    )
    if sorted_stblk:
        for rank, player in enumerate(sorted_stblk[:15], 1):
            name = player.get("name", "Unknown")
            team = player.get("team", "")
            stl = float(player.get("steals_avg", 0) or 0)
            blk = float(player.get("blocks_avg", 0) or 0)
            combined = stl + blk

            status_info = get_player_status(name, injury_map)
            status = status_info.get("status", "Active")
            badge_html = _injury_badge_html(status)
            matchup = _matchup_str(team)
            rank_display = _MEDALS.get(rank, str(rank))
            border_color = {1: "#ffcc00", 2: "#a0b4d0", 3: "#ff5e00"}.get(rank, "rgba(0,240,255,0.15)")

            st.markdown(
                f'<div style="display:flex;align-items:center;gap:15px;padding:12px 16px;'
                f'background:rgba(20,25,43,0.7);border-radius:8px;'
                f'border-left:3px solid {border_color};margin-bottom:8px;">'
                f'<span style="font-size:1.5rem;min-width:40px;text-align:center;">{rank_display}</span>'
                f'<div style="flex:1;">'
                f'<strong style="color:#fff;font-size:1rem;">{name}</strong> '
                f'<span style="background:rgba(0,240,255,0.15);color:#c0d0e8;'
                f'padding:1px 6px;border-radius:4px;font-size:0.75rem;font-weight:700;">{team}</span>'
                + (f'<span style="color:#8a9bb8;font-size:0.78rem;margin-left:8px;">{matchup}</span>' if matchup else "")
                + f'</div>'
                f'<div style="text-align:right;margin-right:12px;">'
                f'<div style="font-size:1.4rem;font-weight:700;color:#00ffd5;">{combined:.1f}</div>'
                f'<div style="font-size:0.75rem;color:#8a9bb8;">STL+BLK</div>'
                f'<div style="font-size:0.75rem;color:#8a9bb8;">{stl:.1f} stl · {blk:.1f} blk</div>'
                f'</div>'
                f'<div style="min-width:80px;">{badge_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No player data available.")

# ============================================================
# END SECTION: Stat Tabs
# ============================================================
