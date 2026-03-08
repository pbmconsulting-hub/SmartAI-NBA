# ============================================================
# FILE: pages/10_🔮_Player_Simulator.py
# PURPOSE: Player Simulator — run Monte Carlo simulations for
#          selected players to project their full stat line and
#          surface "dark horse" upside picks for tonight's slate.
# CONNECTS TO: engine/ (simulation, projections), data_manager.py
# ============================================================

import streamlit as st
import html as _html

from data.data_manager import (
    load_players_data,
    load_teams_data,
    load_defensive_ratings_data,
)
from engine.projections import build_player_projection, get_stat_standard_deviation
from engine.simulation import run_monte_carlo_simulation

# ─── Page config ────────────────────────────────────────────
st.set_page_config(
    page_title="Player Simulator — SmartBetPro NBA",
    page_icon="🔮",
    layout="wide",
)

from styles.theme import get_global_css, get_qds_css
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

# ─── Header ─────────────────────────────────────────────────
st.markdown(
    '<h2 style="font-family:\'Orbitron\',sans-serif;color:#00ffd5;margin-bottom:4px;">'
    '🔮 Player Simulator</h2>'
    '<p style="color:#a0b4d0;margin-top:0;">'
    'Select active players and simulate their full stat line for tonight\'s game. '
    'Identifies <strong style="color:#ff5e00;">dark horse</strong> upside picks automatically.</p>',
    unsafe_allow_html=True,
)

# ─── Load data ───────────────────────────────────────────────
players_data = load_players_data()
teams_data = load_teams_data()
defensive_ratings_data = load_defensive_ratings_data()
todays_games = st.session_state.get("todays_games", [])

# ─── Derive tonight's playing teams ─────────────────────────
playing_teams: set = set()
for game in todays_games:
    playing_teams.add(game.get("home_team", "").upper())
    playing_teams.add(game.get("away_team", "").upper())
playing_teams.discard("")

if playing_teams:
    tonight_players = [p for p in players_data if p.get("team", "").upper() in playing_teams]
else:
    tonight_players = players_data  # Fallback — no games loaded yet

if not tonight_players:
    st.warning(
        "⚠️ No player data loaded. Go to **📡 Live Games** and click "
        "**Auto-Load Tonight's Games** first."
    )
    st.stop()

if not playing_teams:
    st.warning(
        "⚠️ No tonight's games configured. Go to **📡 Live Games** and load tonight's slate "
        "to restrict simulation to active players only."
    )

# ─── Helper: find opponent for a player ─────────────────────
def _find_opponent(team: str, games: list) -> str:
    for g in games:
        if g.get("home_team", "").upper() == team.upper():
            return g.get("away_team", "")
        if g.get("away_team", "").upper() == team.upper():
            return g.get("home_team", "")
    return ""


def _find_game_context(team: str, games: list) -> dict:
    for g in games:
        home = g.get("home_team", "").upper()
        away = g.get("away_team", "").upper()
        if team.upper() == home:
            return {
                "opponent": g.get("away_team", ""),
                "is_home": True,
                "game_total": g.get("game_total", 220.0),
                "vegas_spread": g.get("vegas_spread", 0.0),
                "rest_days": 2,
            }
        if team.upper() == away:
            return {
                "opponent": g.get("home_team", ""),
                "is_home": False,
                "game_total": g.get("game_total", 220.0),
                "vegas_spread": -float(g.get("vegas_spread", 0.0)),
                "rest_days": 2,
            }
    return {"opponent": "", "is_home": True, "game_total": 220.0, "vegas_spread": 0.0, "rest_days": 2}


# ─── Stat types to simulate ──────────────────────────────────
_STAT_TYPES = ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"]
_STAT_EMOJI = {
    "points": "🏀", "rebounds": "📊", "assists": "🎯",
    "threes": "🎯", "steals": "⚡", "blocks": "🛡️", "turnovers": "❌",
}

# ─── Controls ────────────────────────────────────────────────
player_names_sorted = sorted(p.get("name", "") for p in tonight_players if p.get("name"))

col_select, col_depth, col_dark_horse = st.columns([3, 1, 1])
with col_select:
    selected_names = st.multiselect(
        "Select players to simulate",
        player_names_sorted,
        max_selections=10,
        placeholder="Search for a player…",
    )
with col_depth:
    sim_depth = st.slider("Simulation depth", min_value=500, max_value=5000, value=2000, step=500)
with col_dark_horse:
    run_dark_horse = st.button(
        "🌑 Dark Horse Finder",
        use_container_width=True,
        help="Scan ALL tonight's players and rank by upside vs season average",
    )

run_sim = st.button(
    "🚀 Run Simulation",
    type="primary",
    use_container_width=False,
    disabled=not selected_names,
)

st.divider()


# ─── Simulation runner ───────────────────────────────────────
def _simulate_player(player_data: dict, sim_depth: int, todays_games: list) -> dict:
    """Run simulation for all stat types for one player."""
    team = player_data.get("team", "")
    ctx = _find_game_context(team, todays_games)
    results = {}
    for stat in _STAT_TYPES:
        projection = build_player_projection(
            player_data=player_data,
            opponent_team_abbreviation=ctx.get("opponent", ""),
            is_home_game=ctx.get("is_home", True),
            rest_days=ctx.get("rest_days", 2),
            game_total=ctx.get("game_total", 220.0),
            defensive_ratings_data=defensive_ratings_data,
            teams_data=teams_data,
            vegas_spread=ctx.get("vegas_spread", 0.0),
        )
        projected_val = projection.get(
            f"projected_{stat}",
            float(player_data.get(f"{stat}_avg", 0) or 0),
        )
        stat_std = get_stat_standard_deviation(player_data, stat)
        sim_out = run_monte_carlo_simulation(
            projected_stat_average=projected_val,
            stat_standard_deviation=stat_std,
            prop_line=projected_val,  # Use projected as line for percentile calculation
            number_of_simulations=sim_depth,
            blowout_risk_factor=projection.get("blowout_risk", 0.15),
            pace_adjustment_factor=projection.get("pace_factor", 1.0),
            matchup_adjustment_factor=projection.get("defense_factor", 1.0),
            home_away_adjustment=projection.get("home_away_factor", 0.0),
            rest_adjustment_factor=projection.get("rest_factor", 1.0),
            stat_type=stat,
        )
        season_avg = float(player_data.get(f"{stat}_avg", 0) or 0)
        p90 = sim_out.get("percentile_90", projected_val)
        upside_ratio = (p90 / season_avg) if season_avg > 0.5 else 1.0
        results[stat] = {
            "projected": round(sim_out.get("simulated_mean", projected_val), 1),
            "p10": round(sim_out.get("percentile_10", 0), 1),
            "p50": round(sim_out.get("percentile_50", projected_val), 1),
            "p90": round(p90, 1),
            "season_avg": round(season_avg, 1),
            "upside_ratio": round(upside_ratio, 2),
        }
    return {
        "player": player_data,
        "context": ctx,
        "stats": results,
    }


def _render_sim_card(sim_result: dict):
    """Render a styled simulation result card for one player."""
    player_data = sim_result["player"]
    ctx = sim_result["context"]
    stats = sim_result["stats"]

    player_name = player_data.get("name", "")
    team = player_data.get("team", "")
    opponent = ctx.get("opponent", "?")
    player_id = player_data.get("player_id", "")

    # Dark horse check: any stat with upside_ratio ≥ 1.5 (90th pct ≥ 150% of season avg)
    is_dark_horse = any(
        s["upside_ratio"] >= 1.5 for s in stats.values() if s["season_avg"] > 0.5
    )

    headshot_url = (
        f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
        if player_id else ""
    )
    fallback_svg = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "width='60' height='60' viewBox='0 0 60 60'%3E"
        "%3Ccircle cx='30' cy='30' r='30' fill='%23141a2d'/%3E"
        "%3Ccircle cx='30' cy='22' r='10' fill='%23a0b4d0'/%3E"
        "%3Cellipse cx='30' cy='50' rx='16' ry='12' fill='%23a0b4d0'/%3E"
        "%3C/svg%3E"
    )
    img_src = headshot_url if headshot_url else fallback_svg
    safe_name = _html.escape(player_name)
    safe_team = _html.escape(team)
    safe_opp = _html.escape(opponent)

    dark_horse_badge = (
        '<span style="background:#ff5e00;color:#0a0f1a;padding:3px 10px;border-radius:4px;'
        'font-size:0.78rem;font-weight:700;margin-left:8px;">🌑 DARK HORSE</span>'
        if is_dark_horse else ""
    )

    # Build stat rows
    stat_rows = ""
    for stat in _STAT_TYPES:
        s = stats.get(stat, {})
        proj = s.get("projected", 0)
        p10 = s.get("p10", 0)
        p50 = s.get("p50", 0)
        p90 = s.get("p90", 0)
        avg = s.get("season_avg", 0)
        ratio = s.get("upside_ratio", 1.0)
        emoji = _STAT_EMOJI.get(stat, "📊")
        # Upside highlight
        upside_color = "#ff5e00" if ratio >= 1.5 else ("#00ff9d" if ratio >= 1.2 else "#c0d0e8")
        stat_label = _html.escape(stat.replace("_", " ").title())
        stat_rows += (
            f'<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">'
            f'<td style="padding:6px 8px;color:#c0d0e8;">{emoji} {stat_label}</td>'
            f'<td style="padding:6px 8px;color:{upside_color};font-weight:700;">{proj}</td>'
            f'<td style="padding:6px 8px;color:#8a9bb8;">{p10}</td>'
            f'<td style="padding:6px 8px;color:#c0d0e8;">{p50}</td>'
            f'<td style="padding:6px 8px;color:#00ff9d;">{p90}</td>'
            f'<td style="padding:6px 8px;color:#8a9bb8;">{avg}</td>'
            f'</tr>'
        )

    card_html = f"""
<div style="background:#14192b;border-radius:8px;padding:20px;margin-bottom:20px;
            border-top:3px solid #ff5e00;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
        <img src="{img_src}"
             onerror="this.onerror=null;this.src='{fallback_svg}'"
             style="width:64px;height:64px;border-radius:50%;object-fit:cover;
                    border:2px solid #ff5e00;flex-shrink:0;"
             alt="{safe_name}">
        <div>
            <div style="font-family:'Orbitron',sans-serif;color:#ff5e00;font-size:1.1rem;font-weight:700;">
                {safe_name}
                <span style="font-size:0.8rem;background:rgba(255,255,255,0.1);padding:2px 6px;
                             border-radius:4px;color:white;font-family:inherit;">{safe_team}</span>
                {dark_horse_badge}
            </div>
            <div style="color:#c0d0e8;font-size:0.9rem;margin-top:4px;">
                vs <strong style="color:white;">{safe_opp}</strong>
                {'&nbsp;🏠 Home' if ctx.get('is_home') else '&nbsp;✈️ Away'}
                &nbsp;| Game Total: {ctx.get('game_total', 220):.0f}
            </div>
        </div>
    </div>
    <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:0.88rem;">
            <thead>
                <tr style="border-bottom:1px solid rgba(255,94,0,0.4);">
                    <th style="padding:6px 8px;text-align:left;color:#ff5e00;">Stat</th>
                    <th style="padding:6px 8px;text-align:left;color:#ff5e00;">Projected</th>
                    <th style="padding:6px 8px;text-align:left;color:#8a9bb8;">10th%</th>
                    <th style="padding:6px 8px;text-align:left;color:#c0d0e8;">Median</th>
                    <th style="padding:6px 8px;text-align:left;color:#00ff9d;">90th%</th>
                    <th style="padding:6px 8px;text-align:left;color:#8a9bb8;">Season Avg</th>
                </tr>
            </thead>
            <tbody>
                {stat_rows}
            </tbody>
        </table>
    </div>
</div>
"""
    st.markdown(card_html, unsafe_allow_html=True)


# ─── Run simulation for selected players ────────────────────
if run_sim and selected_names:
    st.subheader(f"📊 Simulation Results — {len(selected_names)} Player(s)")
    with st.spinner("🔮 Running Monte Carlo simulations…"):
        for pname in selected_names:
            pdata = next((p for p in tonight_players if p.get("name") == pname), None)
            if pdata is None:
                st.warning(f"⚠️ Could not find data for **{pname}**.")
                continue
            sim_result = _simulate_player(pdata, sim_depth, todays_games)
            _render_sim_card(sim_result)


# ─── Dark Horse Finder ───────────────────────────────────────
if run_dark_horse:
    st.subheader("🌑 Dark Horse Finder — All Tonight's Players")
    st.caption(
        "Players ranked by their highest 90th-percentile upside ratio "
        "(90th pct projection ÷ season average). Ratio ≥ 1.5 = Dark Horse."
    )

    with st.spinner("🔮 Scanning all tonight's players for dark horses…"):
        dark_horses = []
        for pdata in tonight_players:
            if not pdata.get("name"):
                continue
            sim_result = _simulate_player(pdata, min(sim_depth, 1000), todays_games)
            stats = sim_result["stats"]
            # Compute max upside ratio across all meaningful stats
            best_ratio = max(
                (s["upside_ratio"] for s in stats.values() if s["season_avg"] > 0.5),
                default=1.0,
            )
            best_stat = max(
                ((stat, s["upside_ratio"]) for stat, s in stats.items() if s["season_avg"] > 0.5),
                key=lambda x: x[1],
                default=("points", 1.0),
            )
            dark_horses.append({
                "player": pdata,
                "context": sim_result["context"],
                "stats": stats,
                "best_ratio": best_ratio,
                "best_stat": best_stat[0],
                "best_p90": stats.get(best_stat[0], {}).get("p90", 0),
                "best_avg": stats.get(best_stat[0], {}).get("season_avg", 0),
            })

        # Sort by upside ratio descending
        dark_horses.sort(key=lambda x: x["best_ratio"], reverse=True)

    # Show top 10 dark horses
    st.markdown(f"**Top Dark Horses Tonight (out of {len(dark_horses)} players):**")
    for rank, dh in enumerate(dark_horses[:10], start=1):
        pdata = dh["player"]
        pname = pdata.get("name", "")
        team = pdata.get("team", "")
        opp = dh["context"].get("opponent", "?")
        ratio = dh["best_ratio"]
        stat = dh["best_stat"]
        p90 = dh["best_p90"]
        avg = dh["best_avg"]
        emoji = _STAT_EMOJI.get(stat, "📊")
        is_dh = ratio >= 1.5
        badge = "🌑 DARK HORSE" if is_dh else "📈 Upside"
        color = "#ff5e00" if is_dh else "#00ff9d"
        st.markdown(
            f'<div style="background:#14192b;border-radius:6px;padding:10px 14px;'
            f'margin-bottom:8px;border-left:3px solid {color};">'
            f'<span style="color:{color};font-weight:700;margin-right:8px;">#{rank} {badge}</span>'
            f'<strong style="color:white;">{_html.escape(pname)}</strong>'
            f'<span style="color:#8a9bb8;margin:0 6px;">{_html.escape(team)} vs {_html.escape(opp)}</span>'
            f'<span style="color:#c0d0e8;">'
            f'{emoji} {stat.title()} — 90th pct: <strong style="color:{color};">{p90}</strong>'
            f' vs avg {avg} (upside {ratio:.2f}x)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("**Full simulation cards for top 3 dark horses:**")
    for dh in dark_horses[:3]:
        sim_full = _simulate_player(dh["player"], sim_depth, todays_games)
        _render_sim_card(sim_full)
