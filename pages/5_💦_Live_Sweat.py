# ============================================================
# FILE: pages/5_💦_Live_Sweat.py
# PURPOSE: Live Sweat in-game dashboard.  Tracks locked pre-game
#          bets against real-time NBA box scores with auto-refresh,
#          glassmorphic cards, neon progress bars, and Joseph M.
#          Smith's live vibe-check reactions.
# DESIGN:  API Firewall (120 s cache) + streamlit-autorefresh
# ============================================================

import streamlit as st
import datetime
import html as _html_mod
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Page Configuration (MUST be first Streamlit call) ─────────

st.set_page_config(
    page_title="Live Sweat — SmartBetPro NBA",
    page_icon="💦",
    layout="wide",
)

# ── Global CSS ────────────────────────────────────────────────

from styles.theme import get_global_css
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Live Sweat CSS (glassmorphic cards + neon progress) ───────

from styles.live_theme import get_live_sweat_css
st.markdown(get_live_sweat_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ──────────────────────────

try:
    from utils.components import inject_joseph_floating, render_joseph_hero_banner
    render_joseph_hero_banner()
    st.session_state["joseph_page_context"] = "page_live_sweat"
    inject_joseph_floating()
except ImportError:
    pass

# ── Auto-Refresh (silent 120 s reload) ───────────────────────

try:
    from streamlit_autorefresh import st_autorefresh
    _tick = st_autorefresh(interval=120_000, key="live_sweat_refresh")
except ImportError:
    _tick = 0

# ============================================================
# SECTION: Imports — Pacing Engine, Tracker, Persona
# ============================================================

from data.live_game_tracker import (
    get_live_boxscores,
    get_all_live_players,
    get_game_for_player,
    match_live_player,
)
from engine.live_math import calculate_live_pace, pace_color_tier
from styles.live_theme import render_sweat_card, render_waiting_card
from agent.live_persona import get_joseph_live_reaction, stream_joseph_text

# ── Pillar 4 Panic Room imports ──────────────────────────────

from agent.payload_builder import build_live_vibe_payload, get_grudge_buffer
from agent.response_parser import parse_vibe_response, generate_vibe_css_class, get_vibe_emoji
from styles.live_theme import get_panic_room_css, render_panic_room_card

# Inject Panic Room CSS
st.markdown(get_panic_room_css(), unsafe_allow_html=True)

# ============================================================
# SECTION: Header
# ============================================================

st.title("💦 Live Sweat Dashboard")
st.markdown(
    f"**{datetime.date.today().strftime('%A, %B %d, %Y')}** — "
    "Tracking your locked bets against real-time box scores.  "
    "Auto-refreshes every **2 minutes**."
)

with st.expander("📖 How to Use the Live Sweat Dashboard", expanded=False):
    st.markdown("""
### What This Page Does
The Live Sweat Dashboard monitors your **locked player prop bets** against
real-time NBA box-score data.  It calculates whether each player is
**on pace** to hit their line (OVER or UNDER) and surfaces Joseph M. Smith's
live vibe-check reactions so you know the emotional temperature of every bet.

### Selecting Your Bets
All your bets from every source are loaded automatically.  Use the
**Select Bets to Sweat** multiselect to pick exactly which bets you want
to track — you don't have to sweat them all at once.

### How Bets Get Here
Your bets are pulled automatically from **three sources** (all merged):
1. **Manual Locks** — props you locked on the Neural Analysis or Prop Scanner pages.
2. **Analysis Results** — the last Neural Analysis run stored in your session.
3. **Bet Tracker Database** — bets recorded through the 📈 Bet Tracker page.

If no bets appear, head to **📡 Live Games → ⚡ Quantum Analysis Matrix** and
lock some props first, or record a bet in the **📈 Bet Tracker**.

### Today's Scoreboard
The scoreboard at the top shows **live scores for all NBA games** today —
including games that haven't tipped off yet and games that are already final.

### Reading the Sweat Cards
| Element | Meaning |
|---------|---------|
| **Pace Bar** | Green = on pace to cash, Red = falling behind |
| **Projected Total** | Current stat total + pace × remaining minutes |
| **OVER / UNDER Badge** | Which direction you bet |
| **🔥 / 😰 Emoji** | Joseph's real-time vibe on this bet |
| **Awaiting Tip-Off** | Game hasn't started yet — card is greyed out |
| **OT Badge** | Game is in overtime — pace recalculated accordingly |

### Tips
- 💡 The dashboard **auto-refreshes every 2 minutes** — no need to manually reload.
- 💡 Pace projections are most reliable after the **first quarter** of play.
- 💡 UNDER bets flip the pace bar — green means the player is staying low.
- 💡 Use this page alongside the **📈 Bet Tracker** to log final results once games finish.
""")

st.divider()

# ============================================================
# SECTION: Resolve Active Bets
# We check three sources in priority order:
#   1. st.session_state["active_bets"] (manual locks)
#   2. st.session_state["analysis_results"] (Neural Analysis)
#   3. Database via load_all_bets (Bet Tracker)
# ============================================================

_STAT_MAP = {
    "points":               "pts",
    "rebounds":             "reb",
    "assists":              "ast",
    "steals":               "stl",
    "blocks":               "blk",
    "turnovers":            "tov",
    "threes":               "fg3m",
    "three_pointers":       "fg3m",
    "pts":                  "pts",
    "reb":                  "reb",
    "ast":                  "ast",
    "stl":                  "stl",
    "blk":                  "blk",
    "tov":                  "tov",
    "fg3m":                 "fg3m",
}

_COMBO_STATS = {
    "points_rebounds":          ("pts", "reb"),
    "points_assists":           ("pts", "ast"),
    "rebounds_assists":         ("reb", "ast"),
    "points_rebounds_assists":  ("pts", "reb", "ast"),
    "blocks_steals":            ("blk", "stl"),
}


def _resolve_current_stat(player_stats: dict, stat_type: str) -> float | None:
    """Extract the correct stat value from a player's live stats dict."""
    st_lower = str(stat_type).lower().strip()
    if st_lower in _COMBO_STATS:
        return sum(player_stats.get(k, 0) for k in _COMBO_STATS[st_lower])
    box_key = _STAT_MAP.get(st_lower)
    if box_key:
        return float(player_stats.get(box_key, 0))
    return None


def _get_active_bets() -> list[dict]:
    """
    Collect the user's active bets from **all** available sources.

    Merges bets from manual locks, Neural Analysis results, and the
    Bet Tracker database so the user can see every bet in one place
    and pick which ones to sweat.

    Each returned dict has at least:
        player_name, stat_type, line (float), direction, source
    """
    seen: set[tuple] = set()
    bets: list[dict] = []

    def _add(player: str, stat: str, line: float, direction: str,
             tier: str, source: str) -> None:
        key = (player.lower().strip(), stat.lower().strip(), line, direction.upper())
        if key in seen or not player:
            return
        seen.add(key)
        bets.append({
            "player_name": player,
            "stat_type":   stat,
            "line":        line,
            "direction":   direction,
            "tier":        tier,
            "source":      source,
        })

    # Source 1: explicit active_bets in session state (manual locks)
    for b in st.session_state.get("active_bets", []):
        _add(
            b.get("player_name", ""), b.get("stat_type", ""),
            float(b.get("line", 0) or 0),
            str(b.get("direction", "OVER")),
            b.get("tier", ""), "Lock",
        )

    # Source 2: analysis_results from Neural Analysis
    for r in st.session_state.get("analysis_results", []):
        if r.get("should_avoid"):
            continue
        _add(
            r.get("player_name", ""), r.get("stat_type", ""),
            float(r.get("line", 0) or 0),
            str(r.get("direction", "OVER")),
            r.get("tier", ""), "Analysis",
        )

    # Source 3: database (today's pending bets)
    try:
        from tracking.bet_tracker import load_all_bets
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        all_db = load_all_bets(limit=200)
        today_bets = [
            b for b in all_db
            if str(b.get("date", "")).startswith(today_str)
            and str(b.get("result", "")).upper() not in ("WIN", "LOSS", "PUSH")
        ]
        for b in today_bets:
            _add(
                b.get("player_name", ""), b.get("stat_type", ""),
                float(b.get("prop_line", 0) or 0),
                str(b.get("direction", "OVER")),
                b.get("tier", ""), "Tracker",
            )
    except Exception:
        pass

    return bets


# ============================================================
# SECTION: Load Live Data & Render Cards
# ============================================================

all_available_bets = _get_active_bets()

if not all_available_bets:
    st.info(
        "📌 **No active bets to track yet.**\n\n"
        "Run **⚡ Neural Analysis** to generate picks, or lock bets "
        "in the **📈 Bet Tracker**, then come back here to monitor them live."
    )
    st.stop()

# ── Bet Selector ──────────────────────────────────────────────
# Build human-readable labels for multiselect

def _bet_label(b: dict) -> str:
    name = b.get("player_name", "Unknown")
    stat = str(b.get("stat_type", "")).replace("_", " ").title()
    line = b.get("line", 0)
    direction = str(b.get("direction", "OVER")).upper()
    source = b.get("source", "")
    source_tag = f" [{source}]" if source else ""
    return f"{name} — {stat} {direction} {line}{source_tag}"


_bet_labels = [_bet_label(b) for b in all_available_bets]
_label_to_bet = dict(zip(_bet_labels, all_available_bets))

st.markdown("### 🎯 Select Bets to Sweat")
selected_labels = st.multiselect(
    "Choose which bets to track live (all selected by default)",
    options=_bet_labels,
    default=_bet_labels,
    key="sweat_bet_selector",
)

active_bets = [_label_to_bet[lbl] for lbl in selected_labels if lbl in _label_to_bet]

if not active_bets:
    st.warning("⬆ Select at least one bet above to start sweating!")
    st.stop()

# Load live box scores (API-firewalled: cached 120 s)
live_games = get_live_boxscores()
all_live_players = get_all_live_players(live_games)

# ============================================================
# SECTION: Live Scoreboard
# ============================================================


def _get_all_todays_games() -> list[dict]:
    """Return all of today's games (live + scheduled + final).

    Uses the live box-scores already fetched and supplements with the
    ScoreboardV2 endpoint so that pre-tipoff and final games also
    appear.
    """
    seen_ids: set[str] = set()
    games: list[dict] = []

    # Include live games we already have
    for g in (live_games or []):
        gid = g.get("game_id", "")
        if gid:
            seen_ids.add(gid)
        games.append({
            "game_id":    gid,
            "home_team":  g.get("home_team", ""),
            "away_team":  g.get("away_team", ""),
            "home_score": int(g.get("home_score", 0) or 0),
            "away_score": int(g.get("away_score", 0) or 0),
            "status":     g.get("status", ""),
            "period":     g.get("period", ""),
        })

    # Supplement with ScoreboardV2 for pre-tipoff / final games
    try:
        from data.nba_data_service import get_todays_scoreboard
        sb = get_todays_scoreboard()
        if sb:
            game_headers = sb.get("game_header", [])
            line_scores = sb.get("line_score", [])
            score_map: dict[tuple, int] = {}
            for ls in line_scores:
                gid = ls.get("GAME_ID", "")
                abbr = ls.get("TEAM_ABBREVIATION", "")
                pts = ls.get("PTS")
                if gid and abbr:
                    score_map[(gid, abbr)] = int(pts) if pts is not None else 0

            for gh in game_headers:
                gid = gh.get("GAME_ID", "")
                if gid in seen_ids:
                    continue
                home_abbr = gh.get("HOME_TEAM_ABBREVIATION", "")
                away_abbr = gh.get("VISITOR_TEAM_ABBREVIATION", "")
                if not home_abbr or not away_abbr:
                    home_tid = gh.get("HOME_TEAM_ID", "")
                    vis_tid = gh.get("VISITOR_TEAM_ID", "")
                    for ls in line_scores:
                        if ls.get("GAME_ID") == gid:
                            if str(ls.get("TEAM_ID")) == str(home_tid):
                                home_abbr = ls.get("TEAM_ABBREVIATION", home_abbr)
                            elif str(ls.get("TEAM_ID")) == str(vis_tid):
                                away_abbr = ls.get("TEAM_ABBREVIATION", away_abbr)
                games.append({
                    "game_id":    gid,
                    "home_team":  home_abbr,
                    "away_team":  away_abbr,
                    "home_score": score_map.get((gid, home_abbr), 0),
                    "away_score": score_map.get((gid, away_abbr), 0),
                    "status":     str(gh.get("GAME_STATUS_TEXT", "")).strip(),
                    "period":     "",
                })
    except Exception:
        pass

    # Fallback: session state todays_games
    if not games:
        for g in st.session_state.get("todays_games", []):
            games.append({
                "game_id":    g.get("game_id", ""),
                "home_team":  g.get("home_team", ""),
                "away_team":  g.get("away_team", ""),
                "home_score": 0,
                "away_score": 0,
                "status":     g.get("game_time_et", "Scheduled"),
                "period":     "",
            })

    return games


def _status_badge(status_text: str) -> str:
    """Return a coloured emoji badge for a game status string."""
    s = str(status_text).upper().strip()
    if "FINAL" in s:
        return "🏁 Final"
    if any(kw in s for kw in ("QTR", "HALF", "OT", "Q1", "Q2", "Q3", "Q4")):
        return "🔴 LIVE"
    return "🗓️ Scheduled"


scoreboard_games = _get_all_todays_games()

if scoreboard_games:
    st.subheader("🏀 Today's Scoreboard")
    _ticker_cards: list[str] = []
    for _tg in scoreboard_games:
        _t_away = _html_mod.escape(str(_tg.get("away_team", "?")))
        _t_home = _html_mod.escape(str(_tg.get("home_team", "?")))
        _t_a_pts = int(_tg.get("away_score", 0) or 0)
        _t_h_pts = int(_tg.get("home_score", 0) or 0)
        _t_badge = _status_badge(_tg.get("status", ""))

        _a_clr = "#00ff9d" if _t_a_pts > _t_h_pts else "#c0d0e8"
        _h_clr = "#00ff9d" if _t_h_pts > _t_a_pts else "#c0d0e8"
        _border_clr = "rgba(255,94,0,0.5)" if "LIVE" in _t_badge else "rgba(0,240,255,0.18)"

        _ticker_cards.append(
            f'<div class="sweat-ticker-card" style="border-color:{_border_clr};">'
            f'<div class="sweat-ticker-status">{_t_badge}</div>'
            f'<div class="sweat-ticker-teams">'
            f'<div class="sweat-ticker-row">'
            f'<span class="sweat-ticker-abbr">{_t_away}</span>'
            f'<span class="sweat-ticker-score" style="color:{_a_clr};">{_t_a_pts}</span></div>'
            f'<div class="sweat-ticker-row">'
            f'<span class="sweat-ticker-abbr">{_t_home}</span>'
            f'<span class="sweat-ticker-score" style="color:{_h_clr};">{_t_h_pts}</span></div>'
            f'</div></div>'
        )

    st.markdown(
        '<div class="sweat-ticker-wrap">' + ''.join(_ticker_cards) + '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

# ── Last Refresh Timestamp ────────────────────────────────────

_now = datetime.datetime.now()
_refresh_col, _btn_col, _ = st.columns([2, 1, 3])
with _refresh_col:
    st.caption(f"🕐 Last refreshed: **{_now.strftime('%I:%M:%S %p')}**")
with _btn_col:
    if st.button("🔄 Refresh Now", key="manual_refresh"):
        st.rerun()

if not live_games:
    st.warning(
        "📡 No live games in progress right now.  "
        "Cards will populate once tonight's games tip off."
    )

# ── Metrics Row ───────────────────────────────────────────────

cashed_count = 0
tracking_count = 0
risk_count = 0
waiting_count = 0

cards_html = ""
waiting_html = ""
vibe_checks: list[tuple[str, dict]] = []  # (player_name, pace_result)

for bet in active_bets:
    player_name = bet.get("player_name", "")
    stat_type = bet.get("stat_type", "")
    target = float(bet.get("line", 0) or 0)
    direction = str(bet.get("direction", "OVER")).upper()

    if not player_name or target <= 0:
        continue

    # Fuzzy-match the player in the live box score
    matched = match_live_player(player_name, all_live_players)
    if matched is None:
        # Player not found in live data — show awaiting card
        waiting_count += 1
        waiting_html += render_waiting_card(
            player_name=player_name,
            stat_type=stat_type,
            target_stat=target,
            direction=direction,
        )
        continue

    tracking_count += 1

    # Get the game context for blowout detection
    game = get_game_for_player(player_name, live_games)
    score_diff = 0.0
    period = ""
    if game:
        score_diff = abs(game.get("home_score", 0) - game.get("away_score", 0))
        period = game.get("period", "")

    current_stat_val = _resolve_current_stat(matched, stat_type)
    if current_stat_val is None:
        continue

    # Run the pacing engine
    pace = calculate_live_pace(
        current_stat=current_stat_val,
        minutes_played=matched.get("minutes", 0),
        target_stat=target,
        live_score_diff=score_diff,
        current_fouls=matched.get("fouls", 0),
        period=period,
        direction=direction,
    )

    color = pace_color_tier(pace["pct_of_target"], direction)

    if pace["cashed"]:
        cashed_count += 1
    if pace["blowout_risk"] or pace["foul_trouble"]:
        risk_count += 1

    # Render card
    cards_html += render_sweat_card(
        player_name=player_name,
        stat_type=stat_type,
        current_stat=pace["current_stat"],
        target_stat=pace["target_stat"],
        projected_final=pace["projected_final"],
        pct_of_target=pace["pct_of_target"],
        color_tier=color,
        blowout_risk=pace["blowout_risk"],
        foul_trouble=pace["foul_trouble"],
        cashed=pace["cashed"],
        minutes_played=pace["minutes_played"],
        direction=direction,
        minutes_remaining=pace["minutes_remaining"],
        is_overtime=pace["is_overtime"],
    )

    vibe_checks.append((player_name, pace))

# ── Top-Level Metrics ─────────────────────────────────────────

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🎯 Active Bets", len(active_bets))
c2.metric("📡 Tracking Live", tracking_count)
c3.metric("✅ Cashed", cashed_count)
c4.metric("🚨 At Risk", risk_count)
c5.metric("🕐 Awaiting", waiting_count)

st.divider()

# ── Balloons for any cashed bet ───────────────────────────────

if cashed_count > 0:
    st.balloons()

# ── Render all sweat cards ────────────────────────────────────

if cards_html:
    st.markdown(cards_html, unsafe_allow_html=True)
elif live_games:
    st.info(
        "📊 No matching box-score data found for your active bets yet. "
        "Stats appear once games tip off and players check in."
    )

# ── Render awaiting tip-off cards ─────────────────────────────

if waiting_html:
    st.markdown(
        '<div style="margin-top:8px;">'
        '<div class="sweat-stat-label" style="margin-bottom:6px;">🕐 Awaiting Tip-Off</div>'
        f'{waiting_html}</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# SECTION: Joseph's Live Vibe Checks (Pillar 4 Panic Room)
# ============================================================

if vibe_checks:
    st.divider()
    st.subheader("🎙️ Joseph's Live Panic Room")

    grudge = get_grudge_buffer()

    panic_cards_html = ""
    for player_name, pace in vibe_checks:
        # Fast-path fragment reaction (always available offline)
        reaction = get_joseph_live_reaction(pace)

        # Build the Pillar 4 structured payload for this bet
        bet_for_payload = next(
            (b for b in active_bets
             if b.get("player_name", "") == player_name),
            {"player_name": player_name, "stat_type": "",
             "line": pace.get("target_stat", 0),
             "direction": pace.get("direction", "OVER")},
        )
        game = get_game_for_player(player_name, live_games)
        matched = match_live_player(player_name, all_live_players)

        payload = build_live_vibe_payload(
            ticket=bet_for_payload,
            live_stats=matched or {},
            game_context=game or {},
            grudge_buffer=grudge,
            pace_result=pace,
        )

        game_state = payload.get("game_state", "")

        # Map game state to a vibe status for the card glow
        from agent.response_parser import _STATE_TO_DEFAULT_VIBE
        vibe_status = _STATE_TO_DEFAULT_VIBE.get(game_state, "Sweating")

        # Generate ticker-tape headline from the game state
        _STATE_HEADLINES = {
            "THE_HOOK":             "DYING ON THE HOOK!",
            "FREE_THROW_MERCHANT":  "FREE THROW MERCHANT!",
            "BENCH_SWEAT":          "BENCH SWEAT ALERT!",
            "USAGE_FREEZE_OUT":     "GIVE HIM THE BALL!",
            "GARBAGE_TIME_MIRACLE": "GARBAGE TIME MIRACLE!",
            "LOCKER_ROOM_TRAGEDY":  "INJURY SCARE!",
            "THE_REF_SHOW":         "BLAME THE REFS!",
            "THE_CLEAN_CASH":       "CASHED IT!",
        }
        headline = _STATE_HEADLINES.get(game_state, "JOSEPH IS SWEATING!")

        # Render the panic room card
        panic_cards_html += render_panic_room_card(
            vibe_status=vibe_status,
            ticker_headline=headline,
            joseph_rant=reaction,
            player_name=player_name,
            game_state=game_state,
        )

        # Push reaction into grudge buffer for anti-repetition
        grudge.add(reaction)

    # Render all panic room cards
    if panic_cards_html:
        st.markdown(panic_cards_html, unsafe_allow_html=True)

    # Still offer the streaming text in expanders for detail
    st.markdown(
        '<div class="sweat-stat-label" style="margin-top:12px;margin-bottom:4px;">'
        '📜 Detailed Reactions</div>',
        unsafe_allow_html=True,
    )
    for player_name, pace in vibe_checks:
        reaction = get_joseph_live_reaction(pace)
        with st.expander(f"🎙️ {player_name}", expanded=pace.get("cashed", False)):
            st.write_stream(stream_joseph_text(reaction))
