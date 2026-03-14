# ============================================================
# FILE: pages/3_⚡_Neural_Analysis.py
# PURPOSE: The main analysis page. Runs Quantum Matrix Engine 5.6 simulation
#          for each prop and shows probability, edge, tier, and
#          directional forces in the Quantum Design System (QDS) UI.
# CONNECTS TO: engine/ (all modules), data_manager.py, session state
# ============================================================

import streamlit as st  # Main UI framework
import streamlit.components.v1 as _components  # For Full Breakdown iframe rendering
import math             # For rounding in display
import html as _html   # For safe HTML escaping in inline cards
import datetime         # For analysis result freshness timestamps
import time             # For elapsed-time measurement
import os               # For logo path resolution

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# Import our engine modules
from engine.simulation import (
    run_monte_carlo_simulation,
    build_histogram_from_results,
    simulate_combo_stat,
    simulate_fantasy_score,
    simulate_double_double,
    simulate_triple_double,
)
from engine import COMBO_STAT_TYPES, FANTASY_STAT_TYPES, YESNO_STAT_TYPES
from engine.projections import build_player_projection, get_stat_standard_deviation, calculate_teammate_out_boost
from engine.edge_detection import analyze_directional_forces, should_avoid_prop, detect_correlated_props, detect_trap_line, detect_line_sharpness, classify_bet_type

try:
    from engine.rotation_tracker import track_minutes_trend
    _rotation_tracker_available = True
except ImportError:
    _rotation_tracker_available = False
from engine.confidence import calculate_confidence_score, get_tier_color
from engine.math_helpers import calculate_edge_percentage, clamp_probability
from engine.explainer import generate_pick_explanation
from engine.calibration import get_calibration_adjustment   # C10: historical calibration
from engine.clv_tracker import store_opening_line, get_stat_type_clv_penalties  # C12: CLV + penalties

try:
    from engine.market_movement import detect_line_movement  # F9: Sharp money
except ImportError:
    detect_line_movement = None

try:
    from engine.matchup_history import calculate_matchup_adjustment, get_matchup_force_signal  # F2
except ImportError:
    calculate_matchup_adjustment = None
    get_matchup_force_signal = None

# Import data loading functions
from data.data_manager import (
    load_players_data,
    load_defensive_ratings_data,
    load_teams_data,
    find_player_by_name,
    load_props_from_session,
    get_roster_health_report,
    validate_props_against_roster,
    get_player_status,
    get_status_badge_html,
    load_injury_status,
)

# Import the theme helpers — including new QDS generators
from styles.theme import (
    get_global_css,
    get_roster_health_html,
    get_best_bets_section_html,
    get_qds_css,
    get_qds_confidence_bar_html,
    get_qds_metrics_grid_html,
    get_qds_prop_card_html,
    get_qds_matchup_header_html,
    get_qds_team_card_html,
    get_qds_strategy_table_html,
    get_qds_framework_logic_html,
    get_qds_final_verdict_html,
    get_education_box_html,
    GLOSSARY,
)

from data.platform_mappings import COMBO_STATS, FANTASY_SCORING

# ── Section logo paths ────────────────────────────────────────────────────────
# Logos are stored in assets/ and loaded via st.image() for efficient serving.
_ASSETS_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_GOBLIN_LOGO_PATH = os.path.join(_ASSETS_DIR, "Goblin_Logo.png")
_DEMON_LOGO_PATH  = os.path.join(_ASSETS_DIR, "Demon_Logo.png")
_GOLD_LOGO_PATH   = os.path.join(_ASSETS_DIR, "Gold_Logo.png")


st.set_page_config(
    page_title="Neural Analysis — SmartBetPro NBA",
    page_icon="⚡",
    layout="wide",
)

# Inject global CSS + QDS CSS
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

# ── Premium Status (partial gate — free users capped at 3 props) ──
from utils.auth import is_premium_user as _is_premium_user
try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
except Exception:
    _PREM_PATH = "/6_%F0%9F%92%8E_Premium"
_FREE_ANALYSIS_LIMIT = 3   # Free users can analyze up to 3 props
_user_is_premium = _is_premium_user()
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "injury_status_map" not in st.session_state:
    st.session_state["injury_status_map"] = load_injury_status()

# ── Analysis Session Persistence — Rehydrate from DB if session empty ──────
# If the user's session state has no analysis results (e.g. after inactivity
# or a page refresh), reload the most recently saved session from SQLite so
# they never have to re-run analysis just because time passed.
if not st.session_state.get("analysis_results"):
    try:
        from tracking.database import load_latest_analysis_session as _load_session
        _saved_session = _load_session()
        if _saved_session and _saved_session.get("analysis_results"):
            st.session_state["analysis_results"] = _saved_session["analysis_results"]
            if _saved_session.get("todays_games") and not st.session_state.get("todays_games"):
                st.session_state["todays_games"] = _saved_session["todays_games"]
            if _saved_session.get("selected_picks") and not st.session_state.get("selected_picks"):
                st.session_state["selected_picks"] = _saved_session["selected_picks"]
            # Record the timestamp so the UI can show when the session was saved
            st.session_state["_analysis_session_reloaded_at"] = _saved_session.get("analysis_timestamp", "")
    except Exception:
        pass  # Non-fatal — just show empty state

# ─── Auto-refresh injury data if empty or stale (>4 hours) ──
# Use a 30-minute in-session cooldown to avoid re-fetching on every
# page navigation, while still updating when data is genuinely stale.
_INJURY_STALE_HOURS = 4
_INJURY_REFRESH_COOLDOWN_SECS = 1800  # 30 minutes

_should_auto_refresh_injuries = not st.session_state["injury_status_map"]
if not _should_auto_refresh_injuries:
    # Check if we already refreshed recently in this session
    _last_refresh_ts = st.session_state.get("_injury_last_refreshed_at")
    if _last_refresh_ts is not None:
        import time as _time_mod
        _mins_since = (_time_mod.time() - _last_refresh_ts) / 60
        if _mins_since < 30:
            _should_auto_refresh_injuries = False
        else:
            # Been 30+ minutes since last refresh — re-check file age
            try:
                import datetime as _dt
                from pathlib import Path as _Path
                _inj_json_path = _Path(__file__).parent.parent / "data" / "injury_status.json"
                if _inj_json_path.exists():
                    _inj_age_hours = (
                        _dt.datetime.now().timestamp() - _inj_json_path.stat().st_mtime
                    ) / 3600.0
                    _should_auto_refresh_injuries = _inj_age_hours > _INJURY_STALE_HOURS
            except Exception:
                pass
    else:
        # No record of a refresh this session — check file age
        try:
            import datetime as _dt
            from pathlib import Path as _Path
            _inj_json_path = _Path(__file__).parent.parent / "data" / "injury_status.json"
            if _inj_json_path.exists():
                _inj_age_hours = (
                    _dt.datetime.now().timestamp() - _inj_json_path.stat().st_mtime
                ) / 3600.0
                _should_auto_refresh_injuries = _inj_age_hours > _INJURY_STALE_HOURS
        except Exception:
            pass  # Staleness check is best-effort

if _should_auto_refresh_injuries:
    try:
        import time as _time_mod
        from data.roster_engine import RosterEngine as _RosterEngine
        _re = _RosterEngine()
        _re.refresh()
        _scraped_inj = _re.get_injury_report()
        if _scraped_inj:
            _auto_status_map = {
                _k: {
                    "status":        _v.get("status", "Active"),
                    "injury_note":   _v.get("injury", ""),
                    "games_missed":  0,
                    "return_date":   _v.get("return_date", ""),
                    "last_game_date": "",
                    "gp_ratio":      1.0,
                    "injury":        _v.get("injury", ""),
                    "source":        _v.get("source", ""),
                    "comment":       _v.get("comment", ""),
                }
                for _k, _v in _scraped_inj.items()
            }
            st.session_state["injury_status_map"] = _auto_status_map
        # Record this refresh so subsequent page navigations skip it
        st.session_state["_injury_last_refreshed_at"] = _time_mod.time()
    except Exception:
        pass  # Non-fatal — analysis page works without auto-refresh

# ============================================================
# END SECTION: Page Setup
# ============================================================


# ============================================================
# SECTION: Helper Functions
# ============================================================

def find_game_context_for_player(player_team, todays_games_list):
    """
    Find tonight's game context for a given team.

    Args:
        player_team (str): Team abbreviation like 'LAL'
        todays_games_list (list of dict): Tonight's configured games

    Returns:
        dict: Game context with opponent, home/away, spread, total
    """
    for game in todays_games_list:
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")

        if player_team == home_team:
            return {
                "opponent": away_team,
                "is_home": True,
                "rest_days": 2,
                "game_total": game.get("game_total", 220.0),
                "vegas_spread": game.get("vegas_spread", 0.0),
            }
        elif player_team == away_team:
            return {
                "opponent": home_team,
                "is_home": False,
                "rest_days": 2,
                "game_total": game.get("game_total", 220.0),
                "vegas_spread": -game.get("vegas_spread", 0.0),
            }

    return {
        "opponent": "",
        "is_home": True,
        "rest_days": 2,
        "game_total": 220.0,
        "vegas_spread": 0.0,
    }


# Stat emoji map
_STAT_EMOJI = {
    "points": "🏀", "rebounds": "📊", "assists": "🎯",
    "threes": "🎯", "steals": "⚡", "blocks": "🛡️", "turnovers": "❌",
}


def _build_result_metrics(result):
    """Build the 4-item metrics list for a QDS prop card."""
    stat_type  = result.get("stat_type", "points").lower()
    avg_map    = {
        "points": "season_pts_avg", "rebounds": "season_reb_avg",
        "assists": "season_ast_avg", "threes": "season_threes_avg",
    }
    season_avg = result.get(avg_map.get(stat_type, ""), 0) or 0
    line       = result.get("line", 0)
    projection = result.get("adjusted_projection") or result.get("projected_stat") or 0
    edge_pct   = result.get("edge_percentage", 0)
    defense_f  = result.get("overall_adjustment", 1.0)
    form_ratio = result.get("recent_form_ratio")

    # Situational: season avg vs line
    line_diff  = round(float(line) - float(season_avg), 1)
    sit_val    = (
        f"Avg {season_avg:.1f} / Line {line} "
        f"({'▲' if line_diff > 0 else '▼'}{abs(line_diff):.1f})"
    )

    # Archetype matchup: defense factor as multiplier
    matchup_val = (
        f"{'Favorable' if float(defense_f) < 1.0 else 'Tough'} "
        f"({float(defense_f):.2f}x)"
    )

    # Form: recent form ratio
    if form_ratio is not None:
        form_label = "Hot 🔥" if float(form_ratio) > 1.05 else (
            "Cold 🧊" if float(form_ratio) < 0.95 else "Neutral"
        )
        form_val = f"{float(form_ratio):.2f}x ({form_label})"
    else:
        form_val = "N/A"

    # Edge vs line
    edge_sign = "+" if float(edge_pct) >= 0 else ""
    edge_val  = f"{edge_sign}{float(edge_pct):.1f}%"

    return [
        {"icon": "📊", "label": "Situational",      "value": sit_val},
        {"icon": "🛡️", "label": "Archetype Matchup", "value": matchup_val},
        {"icon": "🔥", "label": "Form (5-game)",     "value": form_val},
        {"icon": "⚡", "label": "Edge vs Line",       "value": edge_val},
    ]


def _build_bonus_factors(result):
    """Build the bonus factors list for a QDS prop card."""
    bonus = []
    over_forces  = result.get("forces", {}).get("over_forces",  [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    direction    = result.get("direction", "OVER")
    forces_to_show = over_forces if direction == "OVER" else under_forces
    for f in forces_to_show[:4]:
        lbl  = f.get("name", f.get("label", f.get("factor", "")))
        desc = f.get("description", f.get("detail", ""))
        if lbl:
            bonus.append(f"{lbl}" + (f" — {desc}" if desc else ""))

    # Append traps / warnings as bonus notes
    trap = result.get("trap_line_result", {})
    if trap and trap.get("is_trap"):
        bonus.append(f"⚠️ {trap.get('warning_message', 'Possible trap line')}")

    ls_force = result.get("line_sharpness_force")
    if ls_force:
        bonus.append(f"📐 Sharp line: {ls_force.get('description', '')}")

    teammate_notes = result.get("teammate_out_notes", [])
    for note in teammate_notes[:2]:
        bonus.append(f"👥 {note}")

    return bonus[:6]  # cap at 6 items


def _build_entry_strategy(results):
    """Build entry strategy matrix entries from top results (2–6 legs).

    Enforces unique players per parlay (no repeating the same player on
    multiple props) and excludes fantasy-score variants from parlay legs.
    """
    top = [
        r for r in results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and abs(r.get("edge_percentage", 0)) >= 3.0
        # Exclude fantasy-score composite stats from parlay legs
        and not str(r.get("stat_type", "")).startswith("fantasy_score")
    ]
    top = sorted(top, key=lambda r: r.get("confidence_score", 0), reverse=True)

    _LEG_LABELS = {
        2: "Power Play (2-Leg)",
        3: "Triple Threat (3-Leg)",
        4: "Quad Stack (4-Leg)",
        5: "High Roller (5-Leg)",
        6: "Max Entry (6-Leg)",
    }
    _LEG_STRATEGIES = {
        2: "Highest-confidence 2-leg — best win rate.",
        3: "Top-3 picks, balanced risk vs. reward.",
        4: "Aggressive 4-leg for elevated payout.",
        5: "High ceiling, diversified 5-leg.",
        6: "Max multiplier — only for high-edge slates.",
    }

    def _pick_unique_players(candidates, num_legs):
        """Return up to num_legs picks with no repeated players."""
        seen_players: set = set()
        selected = []
        for r in candidates:
            pname = r.get("player_name", "")
            if pname and pname in seen_players:
                continue
            seen_players.add(pname)
            selected.append(r)
            if len(selected) == num_legs:
                break
        return selected

    entries = []
    for num_legs in range(2, 7):
        picks = _pick_unique_players(top, num_legs)
        if len(picks) < num_legs:
            continue
        avg_conf = round(sum(r.get("confidence_score", 0) for r in picks) / num_legs, 1)

        # Combined probability (independent legs)
        combined_prob = 1.0
        for p in picks:
            prob = p.get("confidence_score", 50) / 100.0
            combined_prob *= max(0.01, min(0.99, prob))
        combined_prob_pct = round(combined_prob * 100, 1)

        avg_edge = round(
            sum(p.get("edge_percentage", 0) for p in picks) / num_legs, 1
        )

        # Reasoning tags
        reasons = []
        if all(p.get("edge_percentage", 0) > 5 for p in picks):
            reasons.append("All legs 5%+ edge")
        if any(p.get("tier") == "Platinum" for p in picks):
            reasons.append("Anchored by Platinum pick")
        teams_in_parlay = {p.get("team", p.get("player_team", "")) for p in picks}
        if len(teams_in_parlay) >= num_legs:
            reasons.append("Diversified across games")
        reasons.append("Unique players per leg")

        entries.append({
            "combo_type":    _LEG_LABELS.get(num_legs, f"{num_legs}-Leg"),
            "num_legs":      num_legs,
            "picks": [
                f"{r['player_name']} {r['direction']} {r['line']} {r['stat_type'].title()}"
                for r in picks
            ],
            "safe_avg":      f"{avg_conf:.1f}",
            "combined_prob": combined_prob_pct,
            "avg_edge":      avg_edge,
            "strategy":      _LEG_STRATEGIES.get(num_legs, ""),
            "reasons":       reasons,
            "raw_picks":     picks,
        })

    return entries


def _render_qds_full_breakdown_html(result):
    """Generate QDS-styled HTML for the full breakdown section.

    Uses the same colour palette as the Game Report's QDS dark-card CSS:
    background #14192b, primary #ff5e00, cyan #00f0ff, text #c0d0e8.
    Wrapped in a native <details>/<summary> element so it collapses
    inside the existing dark-card visual context without a plain Streamlit
    expander frame breaking the design.

    Rendered via streamlit.components.v1.html() to avoid st.markdown
    stripping complex inline styles or mis-rendering grid/flex containers.

    Args:
        result (dict): Full analysis result from the simulation loop.

    Returns:
        str: Full standalone HTML document ready for components.html().
    """
    player = _html.escape(str(result.get("player_name", "Unknown")))
    stat   = _html.escape(str(result.get("stat_type", "points")).title())

    p10 = result.get("percentile_10", 0) or 0
    p50 = result.get("percentile_50", 0) or 0
    p90 = result.get("percentile_90", 0) or 0
    std = result.get("simulated_std", result.get("std_dev", 0)) or 0

    over_forces  = result.get("forces", {}).get("over_forces",  []) or []
    under_forces = result.get("forces", {}).get("under_forces", []) or []
    breakdown    = result.get("score_breakdown", {}) or {}
    explanation  = result.get("explanation") or {}
    should_avoid = result.get("should_avoid", False)
    avoid_reasons = result.get("avoid_reasons", []) or []

    # ── Forces HTML ──────────────────────────────────────────────
    def _forces_html(forces):
        if not forces:
            return '<span style="color:#b0bec5;font-size:0.85rem;">None detected</span>'
        parts = []
        for f in (forces or []):
            if not isinstance(f, dict):
                continue
            stars = "⭐" * max(1, min(5, round(float(f.get("strength", 1) or 1))))
            name  = _html.escape(str(f.get("name", "") or ""))
            desc  = _html.escape(str(f.get("description", "") or ""))
            parts.append(
                '<div style="margin-bottom:6px;padding:4px 0;">'
                '<span style="color:#00f0ff;">' + stars + '</span> '
                '<strong style="color:#ff5e00;">' + name + '</strong><br>'
                '<span style="color:#c0d0e8;font-size:0.8rem;">' + desc + '</span>'
                '</div>'
            )
        return "".join(parts) if parts else '<span style="color:#b0bec5;font-size:0.85rem;">None detected</span>'

    # ── Score-breakdown bars ─────────────────────────────────────
    breakdown_rows = []
    if breakdown:
        for factor, score in breakdown.items():
            label = _html.escape(
                factor.replace("_score", "").replace("_", " ").title()
            )
            bar_w = min(100, max(0, float(score or 0)))
            if bar_w >= 70:
                bar_c = "#00f0ff"
            elif bar_w >= 40:
                bar_c = "#ff5e00"
            else:
                bar_c = "#ff4444"
            bar_c_fade = bar_c + "88"
            breakdown_rows.append(
                '<div style="margin-bottom:8px;">'
                '<div style="display:flex;justify-content:space-between;font-size:0.8rem;color:#c0d0e8;margin-bottom:3px;">'
                '<span>' + label + '</span>'
                '<span style="color:#ff5e00;font-weight:600;">' + f"{score:.0f}" + '/100</span>'
                '</div>'
                '<div style="height:6px;background:#1a2035;border-radius:3px;">'
                '<div style="height:6px;width:' + f"{bar_w:.1f}" + '%;background:linear-gradient(90deg,' + bar_c + ',' + bar_c_fade + ');border-radius:3px;"></div>'
                '</div></div>'
            )
    breakdown_html = ""
    if breakdown_rows:
        breakdown_html = (
            '<div style="margin-bottom:15px;">'
            '<div style="color:#ff5e00;font-weight:600;font-size:0.9rem;margin-bottom:10px;">🔬 Confidence Score Breakdown</div>'
            + "".join(breakdown_rows)
            + '</div>'
        )

    # ── Explanation sections ─────────────────────────────────────
    explain_parts = []
    if explanation:
        sections = [
            ("📊 Season Avg vs Line",  "average_vs_line"),
            ("🛡️ Matchup Analysis",    "matchup_explanation"),
            ("⚡ Game Pace",            "pace_explanation"),
            ("🏠 Home/Away",           "home_away_explanation"),
            ("😴 Rest Days",           "rest_explanation"),
            ("💰 Vegas Lines",         "vegas_explanation"),
        ]
        for label, key in sections:
            text = explanation.get(key, "")
            if text:
                explain_parts.append(
                    '<div style="margin-bottom:8px;padding:8px;background:rgba(20,25,43,0.5);border-radius:4px;border-left:2px solid #ff5e00;">'
                    '<div style="color:#ff5e00;font-weight:600;font-size:0.8rem;">' + label + '</div>'
                    '<div style="color:#c0d0e8;font-size:0.85rem;margin-top:4px;">' + _html.escape(str(text)) + '</div>'
                    '</div>'
                )
    explain_html = "".join(explain_parts)

    # ── Avoid warning ────────────────────────────────────────────
    avoid_html = ""
    if should_avoid and avoid_reasons:
        reasons_str = _html.escape(" | ".join(str(r) for r in avoid_reasons))
        avoid_html = (
            '<div style="margin-bottom:10px;padding:8px 12px;background:rgba(255,68,68,0.1);border-radius:6px;border-left:3px solid #ff4444;color:#ff4444;font-size:0.85rem;">'
            '⚠️ <strong>Avoid List:</strong> ' + reasons_str +
            '</div>'
        )

    # ── Distribution grid (table-based for universal compatibility) ─
    dist_html = (
        '<div style="margin-bottom:15px;">'
        '<div style="color:#ff5e00;font-weight:600;font-size:0.9rem;margin-bottom:8px;">📊 Distribution</div>'
        '<table style="width:100%;border-collapse:separate;border-spacing:4px;">'
        '<tr>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#b0bec5;font-size:0.75rem;">10th pct</div>'
        '<div style="color:#ff5e00;font-weight:700;font-size:1rem;">' + f"{p10:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#b0bec5;font-size:0.75rem;">Median</div>'
        '<div style="color:#00f0ff;font-weight:700;font-size:1rem;">' + f"{p50:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#b0bec5;font-size:0.75rem;">90th pct</div>'
        '<div style="color:#ff5e00;font-weight:700;font-size:1rem;">' + f"{p90:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#b0bec5;font-size:0.75rem;">Std Dev</div>'
        '<div style="color:#ffffff;font-weight:700;font-size:1rem;">' + f"{std:.1f}" + '</div>'
        '</td>'
        '</tr>'
        '</table>'
        '</div>'
    )

    # ── Forces grid (table-based for universal compatibility) ────
    forces_html = (
        '<table style="width:100%;border-collapse:separate;border-spacing:8px;margin-bottom:15px;">'
        '<tr>'
        '<td style="padding:12px;background:rgba(0,240,255,0.05);border-radius:6px;border-left:3px solid #00f0ff;vertical-align:top;width:50%;">'
        '<div style="color:#00f0ff;font-weight:600;font-size:0.85rem;margin-bottom:8px;">🔵 Forces OVER</div>'
        + _forces_html(over_forces) +
        '</td>'
        '<td style="padding:12px;background:rgba(255,94,0,0.05);border-radius:6px;border-left:3px solid #ff5e00;vertical-align:top;width:50%;">'
        '<div style="color:#ff5e00;font-weight:600;font-size:0.85rem;margin-bottom:8px;">🔴 Forces UNDER</div>'
        + _forces_html(under_forces) +
        '</td>'
        '</tr>'
        '</table>'
    )

    # ── Full breakdown wrapped in <details>/<summary> ────────────
    inner_content = dist_html + forces_html + avoid_html + breakdown_html + explain_html

    body_html = (
        '<details style="margin-top:4px;">'
        '<summary style="cursor:pointer;padding:10px 14px;'
        'background:#14192b;border:1px solid rgba(255,94,0,0.2);border-radius:6px;'
        'color:#ff5e00;font-weight:600;font-size:0.9rem;list-style:none;'
        'user-select:none;">'
        '&#128202; Full Breakdown &#8212; ' + player + ' ' + stat +
        '</summary>'
        '<div style="padding:14px 15px 16px;background:#0f1424;border:1px solid rgba(255,94,0,0.15);'
        'border-top:none;border-radius:0 0 6px 6px;color:#c0d0e8;font-size:0.85rem;line-height:1.7;">'
        + inner_content +
        '</div>'
        '</details>'
    )

    # Wrap in a full standalone HTML document so components.html() renders it correctly.
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<style>'
        'body{margin:0;padding:0;background:transparent;font-family:Montserrat,sans-serif;}'
        'details summary::-webkit-details-marker{display:none;}'
        '</style></head><body>'
        + body_html +
        '</body></html>'
    )


def display_prop_analysis_card_qds(result):
    """
    Display a QDS-styled analysis card for one prop result.

    OUT / IR players show a prominent error banner and return early.
    Questionable / Day-to-Day players show a warning.
    All other players get the full QDS prop card with metrics grid,
    confidence bar, bonus factors, and an Add to Entry button.

    Args:
        result (dict): Full analysis result from the simulation loop.
    """
    player   = result.get("player_name", "Unknown")
    stat     = result.get("stat_type", "").lower()
    line     = result.get("line", 0)
    direction = result.get("direction", "OVER")
    confidence = result.get("confidence_score", 50)
    should_avoid = result.get("should_avoid", False)
    platform = result.get("platform", "")
    team     = result.get("player_team", result.get("team", ""))

    # ── OUT / Injured Reserve ────────────────────────────────────
    if result.get("player_is_out", False):
        player_status = result.get("player_status", "Out")
        status_note   = result.get("player_status_note", "")
        st.error(
            f"❌ **{player}** is **{player_status}** — prop skipped. "
            + (f"_{status_note}_" if status_note else "")
            + "\n\nRemove this prop from your list."
        )
        return

    # ── Warn for Questionable / Day-to-Day ──────────────────────
    player_status = result.get("player_status") or (
        get_player_status(player, st.session_state.get("injury_status_map", {}))
        .get("status", "Active")
    )
    if player_status in ("Questionable", "Day-to-Day", "GTD", "Doubtful"):
        note = result.get("player_status_note", "")
        st.warning(
            f"⚠️ **{player}** is listed as **{player_status}**"
            + (f" — {note}" if note else "")
            + ". Monitor status before betting."
        )

    # ── Tier badge icon ──────────────────────────────────────────
    tier = result.get("tier", "Bronze")
    tier_icon_map = {"Platinum": "💎", "Gold": "🔒", "Silver": "✓", "Bronze": "⭐"}
    tier_icon = tier_icon_map.get(tier, "⭐")

    # ── Goblin / Demon badge ─────────────────────────────────────
    bet_type       = result.get("bet_type", "normal")
    bet_type_emoji = result.get("bet_type_emoji", "")
    bet_type_label = result.get("bet_type_label", "")
    bet_type_reasons = result.get("bet_type_reasons", []) or []

    if bet_type == "goblin":
        _goblin_reasons_str = " | ".join(bet_type_reasons[:2]) if bet_type_reasons else ""
        st.markdown(
            f'<div style="background:rgba(76,175,80,0.12);border:1px solid #4caf50;border-radius:6px;'
            f'padding:8px 14px;margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.3rem;">🧌</span>'
            f'<div>'
            f'<span style="color:#4caf50;font-weight:700;font-size:0.9rem;">GOBLIN BET — Easy Money</span>'
            + (f'<br><span style="color:#a5d6a7;font-size:0.78rem;">{_html.escape(_goblin_reasons_str)}</span>'
               if _goblin_reasons_str else "")
            + f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif bet_type == "demon":
        _demon_reasons_str = " | ".join(bet_type_reasons[:2]) if bet_type_reasons else ""
        st.markdown(
            f'<div style="background:rgba(255,68,68,0.10);border:1px solid #ff4444;border-radius:6px;'
            f'padding:8px 14px;margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.3rem;">👿</span>'
            f'<div>'
            f'<span style="color:#ff4444;font-weight:700;font-size:0.9rem;">DEMON BET — AVOID (Dangerous Trap)</span>'
            + (f'<br><span style="color:#ffb0b0;font-size:0.78rem;">{_html.escape(_demon_reasons_str)}</span>'
               if _demon_reasons_str else "")
            + f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── True odds / implied probability display ───────────────────
    _over_odds  = result.get("over_odds",  -110)
    _under_odds = result.get("under_odds", -110)
    _odds_for_dir = _over_odds if direction == "OVER" else _under_odds
    if _odds_for_dir and _odds_for_dir != 0:
        _odds_str = f"+{_odds_for_dir}" if int(_odds_for_dir) > 0 else str(int(_odds_for_dir))
        # Implied probability from odds
        _abs_odds = abs(float(_odds_for_dir))
        if float(_odds_for_dir) < 0:
            _implied_prob = _abs_odds / (_abs_odds + 100.0) * 100.0
        else:
            _implied_prob = 100.0 / (float(_odds_for_dir) + 100.0) * 100.0
        _model_prob = (result.get("probability_over", 0.5) if direction == "OVER"
                       else 1.0 - result.get("probability_over", 0.5)) * 100.0
        _true_edge_pct = _model_prob - _implied_prob
        _proj_val = result.get("adjusted_projection", 0)

        # Minutes trend indicator (from Feature 6 rotation tracking)
        _mt_indicator = result.get("minutes_trend_indicator", "")
        _mt_info      = result.get("minutes_trend")
        _mt_extra = ""
        if _mt_info and _mt_info.get("games_analyzed", 0) > 0 and _mt_indicator in ("🔺", "🔻"):
            _mt_recent = _mt_info.get("recent_avg_minutes", 0)
            _mt_season = _mt_info.get("season_avg_minutes", 0)
            _mt_dir    = "up" if _mt_indicator == "🔺" else "down"
            _mt_extra  = (
                f' &nbsp;|&nbsp; <span style="color:#{"69f0ae" if _mt_dir == "up" else "ff9966"};'
                f'font-weight:600;">'
                f'{_mt_indicator} Min Trend: {_mt_recent:.0f} vs {_mt_season:.0f} avg</span>'
            )

        st.markdown(
            f'<div style="background:rgba(0,240,255,0.05);border:1px solid rgba(0,240,255,0.2);'
            f'border-radius:6px;padding:6px 12px;margin-bottom:6px;font-size:0.78rem;color:#a0c0d8;">'
            f'<span style="color:#00f0ff;font-weight:600;">Platform Line:</span> '
            f'{direction.title()} {line} &nbsp;|&nbsp; '
            f'<span style="color:#00f0ff;font-weight:600;">Odds:</span> {_odds_str} &nbsp;|&nbsp; '
            f'<span style="color:#00f0ff;font-weight:600;">Model Proj:</span> {_proj_val:.1f} &nbsp;|&nbsp; '
            f'<span style="color:#00f0ff;font-weight:600;">Breakeven:</span> {_implied_prob:.1f}% &nbsp;|&nbsp; '
            f'<span style="color:#{"4caf50" if _true_edge_pct > 0 else "ff4444"};font-weight:600;">'
            f'True Edge: {_true_edge_pct:+.1f}%</span>'
            + _mt_extra +
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Prop description string ──────────────────────────────────
    stat_emoji = _STAT_EMOJI.get(stat, "🏀")
    dir_label  = "Over" if direction == "OVER" else "Under"
    prop_text  = f"{stat_emoji} {dir_label} {line} {stat.title()}"

    # ── Build metrics & bonus factors ────────────────────────────
    metrics       = _build_result_metrics(result)
    bonus_factors = _build_bonus_factors(result)

    # ── Render QDS prop card ─────────────────────────────────────
    player_id = result.get("player_id", "") or ""
    card_html = get_qds_prop_card_html(
        player_name=player,
        team=team,
        prop_text=prop_text,
        score=confidence,
        tier=tier,
        metrics=metrics,
        bonus_factors=bonus_factors,
        player_id=player_id if player_id else None,
    )
    st.markdown(card_html, unsafe_allow_html=True)

    # ── Confidence bar (standalone) ──────────────────────────────
    conf_bar_html = get_qds_confidence_bar_html(
        label=f"{player} — {prop_text}",
        percentage=confidence,
        tier_icon=tier_icon,
    )
    # (Already embedded in prop card — skip duplicate)

    # ── Add to Entry button ──────────────────────────────────────
    pick_key = f"{player}_{stat}_{line}_{direction}"
    selected_picks = st.session_state.get("selected_picks", [])
    already_added  = any(p.get("key") == pick_key for p in selected_picks)

    btn_label    = "✅ Added" if already_added else "➕ Add to Entry"
    btn_disabled = already_added
    if st.button(btn_label, key=f"add_pick_{pick_key}", disabled=btn_disabled):
        st.session_state["selected_picks"].append({
            "key":             pick_key,
            "player_name":     player,
            "stat_type":       stat,
            "line":            line,
            "direction":       direction,
            "confidence_score": confidence,
            "tier":            tier,
            "tier_emoji":      tier_icon,
            "platform":        platform,
            "edge_percentage": result.get("edge_percentage", 0),
        })
        st.rerun()

    # ── Full Breakdown (QDS-styled HTML rendered via iframe to avoid st.markdown stripping) ─
    breakdown_html = _render_qds_full_breakdown_html(result)
    # Dynamic height: base + per-section additions so content is never cut off
    _over_forces  = len(result.get("forces", {}).get("over_forces",  []) or [])
    _under_forces = len(result.get("forces", {}).get("under_forces", []) or [])
    _breakdown_n  = len(result.get("score_breakdown", {}) or {})
    _explain_n    = len([v for v in (result.get("explanation") or {}).values() if v])
    _est_height = (
        60                              # summary bar / <details> toggle
        + 130                           # distribution grid
        + max(_over_forces, _under_forces, 1) * 55 + 80  # forces grid
        + _breakdown_n * 28 + (40 if _breakdown_n else 0)
        + _explain_n   * 60 + (20 if _explain_n   else 0)
        + (50 if result.get("should_avoid") else 0)
    )
    _est_height = max(200, min(900, _est_height))
    _components.html(breakdown_html, height=_est_height, scrolling=True)


# ============================================================
# END SECTION: Helper Functions
# ============================================================

# ============================================================
# SECTION: Load All Required Data
# ============================================================

players_data           = load_players_data()
teams_data             = load_teams_data()
defensive_ratings_data = load_defensive_ratings_data()

current_props  = load_props_from_session(st.session_state)
todays_games   = st.session_state.get("todays_games", [])

simulation_depth = st.session_state.get("simulation_depth", 1000)
minimum_edge     = st.session_state.get("minimum_edge_threshold", 5.0)

# ============================================================
# END SECTION: Load All Required Data
# ============================================================

# ============================================================
# SECTION: QDS Page Header
# ============================================================

st.markdown(
    '<h2 style="font-family:\'Orbitron\',sans-serif;color:#00ffd5;'
    'margin-bottom:4px;">⚡ Neural Analysis</h2>'
    '<p style="color:#a0b4d0;margin-top:0;">SmartBetPro Neural Engine™ — Powered by N.A.N. (Neural Analysis Network) — '
    'Quantum Matrix Engine 5.6 Prop Analysis with Quantum Design System</p>',
    unsafe_allow_html=True,
)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Neural Analysis — Understanding Your Results
    
    **Running Analysis:**
    1. Ensure props are loaded (from Prop Scanner or Live Games page)
    2. Click "▶️ Run Analysis" to start Quantum Matrix Engine 5.6 simulation
    3. Each prop is simulated 1,000+ times to calculate probability
    
    **Reading Results:**
    - **Probability**: % chance the stat goes OVER the line (>55% = meaningful edge)
    - **Edge**: How much better than 50/50 your edge is (higher = better value)
    - **Confidence Score**: 0-100 composite score (70+ = high confidence)
    - **Tier**: Platinum (85+) > Gold (70+) > Silver (55+) > Bronze
    
    **Directional Forces:**
    - Green arrows = factors pushing OVER (weak defense, fast pace, etc.)
    - Red arrows = factors pushing UNDER (tough defense, injury risk, etc.)
    
    💡 **Pro Tips:**
    - Focus on Platinum and Gold tier picks for best results
    - Avoid picks with ⚠️ "should avoid" flags
    - Select picks to send to Entry Builder for parlay optimization
    """)

# ── Matchup header (shown when games are configured) ──────────
if len(todays_games) == 1:
    g = todays_games[0]
    st.markdown(
        get_qds_matchup_header_html(
            away_team=g.get("away_team", "AWAY"),
            home_team=g.get("home_team", "HOME"),
            game_info=(
                f"Tonight · Tip-off: {g.get('game_time', '')}"
                if g.get("game_time") else "Tonight"
            ),
        ),
        unsafe_allow_html=True,
    )
elif len(todays_games) > 1:
    # Multiple games — show count instead of a single matchup header
    st.markdown(
        f'<div style="background:rgba(0,255,213,0.06);border-radius:8px;'
        f'padding:10px 16px;border:1px solid rgba(0,255,213,0.12);'
        f'color:#a0b4d0;font-size:0.85rem;margin-bottom:12px;">'
        f'🏀 {len(todays_games)} games configured for tonight.'
        f'</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# END SECTION: QDS Page Header
# ============================================================

# ============================================================
# SECTION: Pre-Run Status Check
# ============================================================

status_col, settings_col = st.columns([2, 1])

with status_col:
    if current_props:
        # Show per-platform breakdown of loaded props
        _prerun_plat_counts: dict = {}
        for _pp in current_props:
            _plat = _pp.get("platform", "Unknown")
            _prerun_plat_counts[_plat] = _prerun_plat_counts.get(_plat, 0) + 1
        _plat_detail = " · ".join(
            f"**{_pl}**: {_n}" for _pl, _n in sorted(_prerun_plat_counts.items())
        )
        st.info(
            f"📋 **{len(current_props)} props** loaded and ready for analysis — {_plat_detail}."
        )
    else:
        st.warning(
            "⚠️ No props loaded. Go to **🔬 Prop Scanner** → "
            "**🤖 Auto-Generate Props for Tonight's Games** or import props manually."
        )

    if todays_games:
        st.success(f"🏟️ **{len(todays_games)} game(s)** configured for tonight.")
    else:
        st.warning(
            "⚠️ No games loaded for today. Click **🔄 Auto-Load Tonight's Games** "
            "on the Live Games page first to ensure only tonight's players are analyzed."
        )

    if current_props and players_data:
        validation     = validate_props_against_roster(current_props, players_data)
        total          = validation["total"]
        matched_count  = validation["matched_count"]

        if validation["unmatched"] or validation["fuzzy_matched"]:
            with st.expander(
                f"⚠️ Roster Health: {matched_count}/{total} players matched "
                f"({int(matched_count / max(total, 1) * 100)}%) — click to see details"
            ):
                st.markdown(
                    get_roster_health_html(
                        validation["matched"],
                        validation["fuzzy_matched"],
                        validation["unmatched"],
                    ),
                    unsafe_allow_html=True,
                )
        else:
            st.success(f"✅ All {total} players matched in database.")

with settings_col:
    st.caption(f"⚙️ Simulations: **{simulation_depth:,}**")
    st.caption(f"⚙️ Min Edge: **{minimum_edge}%**")
    _shown_platforms = st.session_state.get("selected_platforms", ["PrizePicks", "Underdog", "DraftKings"])
    st.caption(f"⚙️ Platforms: **{', '.join(_shown_platforms)}**")
    st.caption("Change on the ⚙️ Settings page")

# ============================================================
# END SECTION: Pre-Run Status Check
# ============================================================

st.divider()

# ── Framework Logic (collapsible) ──────────────────────────────
with st.expander("📖 How Neural Analysis Works — Framework Logic"):
    st.markdown(get_qds_framework_logic_html(), unsafe_allow_html=True)

# ============================================================
# SECTION: Analysis Runner
# ============================================================

run_col, filter_col = st.columns([1, 2])

with run_col:
    run_analysis = st.button(
        "🚀 Run Analysis",
        type="primary",
        width="stretch",
        disabled=(len(current_props) == 0),
        help="Analyze all loaded props with Quantum Matrix Engine 5.6",
    )

with filter_col:
    show_all_or_top = st.radio(
        "Show:",
        ["All picks", "Top picks only (edge ≥ threshold)"],
        horizontal=True,
        index=1,
    )

if run_analysis:
    _analysis_start_time = time.time()
    progress_bar         = st.progress(0, text="Starting analysis...")
    analysis_results_list = []

    # ── Filter props to only tonight's teams (with abbreviation aliases) ──
    # Build expanded playing-teams set that covers all known alias variants
    # (e.g. "GS" ↔ "GSW", "NY" ↔ "NYK") so team-abbreviation mismatches
    # don't silently drop valid props.
    ABBREV_ALIASES = {
        "GS": "GSW", "GSW": "GS",
        "NY": "NYK", "NYK": "NY",
        "NO": "NOP", "NOP": "NO",
        "SA": "SAS", "SAS": "SA",
        "UTAH": "UTA", "UTA": "UTAH",
        "WSH": "WAS", "WAS": "WSH",
        "BKN": "BRK", "BRK": "BKN",
        "PHX": "PHO", "PHO": "PHX",
        "CHA": "CHO", "CHO": "CHA",
        "NJ": "BKN",
    }

    playing_teams_expanded: set = set()
    for _g in todays_games:
        for _abbrev in (
            _g.get("home_team", "").upper().strip(),
            _g.get("away_team", "").upper().strip(),
        ):
            if not _abbrev:
                continue
            playing_teams_expanded.add(_abbrev)
            # Add known alias for this abbreviation (if any)
            _alias = ABBREV_ALIASES.get(_abbrev)
            if _alias:
                playing_teams_expanded.add(_alias)
    playing_teams_expanded.discard("")

    if playing_teams_expanded:
        props_to_analyze = [
            p for p in current_props
            if (
                not playing_teams_expanded  # if no games loaded, include all
                or p.get("team", "").upper().strip() in playing_teams_expanded
                or not p.get("team", "").strip()  # include props with no team set
            )
        ]
        skipped_count = len(current_props) - len(props_to_analyze)
        if skipped_count > 0:
            st.info(
                f"ℹ️ Skipping **{skipped_count}** prop(s) for teams not playing tonight. "
                f"Analyzing **{len(props_to_analyze)}** prop(s) for tonight's {len(todays_games)} game(s)."
            )
    else:
        props_to_analyze = current_props  # Fallback: no games loaded

    # ── Also skip confirmed Out/IR/Doubtful players via injury map ─────
    # If injury_map_pre is empty (failed to load), do NOT filter — just proceed.
    injury_map_pre = st.session_state.get("injury_status_map", {})
    _INACTIVE_STATUSES = frozenset({
        "Out", "Doubtful", "Injured Reserve", "Out (No Recent Games)",
        "Suspended", "Not With Team",
        "G League - Two-Way", "G League - On Assignment", "G League",
    })
    if injury_map_pre:
        before_inj = len(props_to_analyze)
        props_to_analyze = [
            p for p in props_to_analyze
            if injury_map_pre.get(
                p.get("player_name", "").lower().strip(), {}
            ).get("status", "Active") not in _INACTIVE_STATUSES
        ]
        inj_skipped = before_inj - len(props_to_analyze)
        if inj_skipped > 0:
            st.info(f"ℹ️ Skipping **{inj_skipped}** prop(s) for confirmed Out/IR/Doubtful players.")

    # ── Filter to selected platforms (from ⚙️ Settings) ──────────────
    _selected_platforms = st.session_state.get(
        "selected_platforms", ["PrizePicks", "Underdog", "DraftKings"]
    )
    if _selected_platforms:
        before_plat = len(props_to_analyze)
        props_to_analyze = [
            p for p in props_to_analyze
            if not p.get("platform", "").strip()          # include props with no platform
            or p.get("platform", "") in _selected_platforms
        ]
        plat_skipped = before_plat - len(props_to_analyze)
        if plat_skipped > 0:
            st.info(
                f"ℹ️ Skipping **{plat_skipped}** prop(s) for platforms not in your "
                f"selection ({', '.join(_selected_platforms)}). "
                "Change platforms on the ⚙️ Settings page."
            )

    # ── Show per-platform prop count summary ─────────────────────────
    if props_to_analyze:
        _plat_counts = {}
        for _p in props_to_analyze:
            _plat = _p.get("platform", "Unknown")
            _plat_counts[_plat] = _plat_counts.get(_plat, 0) + 1
        _plat_summary = " · ".join(
            f"**{_plat}**: {_n}" for _plat, _n in sorted(_plat_counts.items())
        )
        st.caption(f"📊 Analyzing: {_plat_summary}")

    total_props_count    = len(props_to_analyze)
    if total_props_count == 0:
        st.warning("⚠️ No props remain after filtering to tonight's teams / injury status. Check your games and props.")
        progress_bar.empty()
        st.stop()

    # ── Free tier: cap analysis at _FREE_ANALYSIS_LIMIT props ────
    if not _user_is_premium and total_props_count > _FREE_ANALYSIS_LIMIT:
        st.warning(
            f"⚠️ **Free plan** is limited to **{_FREE_ANALYSIS_LIMIT} props** per analysis run. "
            f"Analyzing the first {_FREE_ANALYSIS_LIMIT} props. "
            f"[**Upgrade to Premium**]({_PREM_PATH}) for unlimited analysis. 💎"
        )
        props_to_analyze  = props_to_analyze[:_FREE_ANALYSIS_LIMIT]
        total_props_count = _FREE_ANALYSIS_LIMIT

    for prop_index, prop in enumerate(props_to_analyze):
        progress_fraction = (prop_index + 1) / total_props_count
        progress_bar.progress(
            progress_fraction,
            text=f"Analyzing {prop.get('player_name', 'Player')}… ({prop_index + 1}/{total_props_count})"
        )

        player_name = prop.get("player_name", "")
        stat_type   = prop.get("stat_type", "points").lower()
        prop_line   = float(prop.get("line", 0))
        platform    = prop.get("platform", "PrizePicks")

        # ── Injury gate ───────────────────────────────────────────
        injury_map        = st.session_state.get("injury_status_map", {})
        player_status_info = get_player_status(player_name, injury_map)
        player_status      = player_status_info.get("status", "Active")

        if player_status in (
            "Out", "Injured Reserve", "Out (No Recent Games)",
            "Suspended", "Not With Team",
            "G League - Two-Way", "G League - On Assignment", "G League",
        ):
            injury_note = player_status_info.get("injury_note", "Player is not active")
            analysis_results_list.append({
                "player_name":   player_name,
                "team":          prop.get("team", ""),
                "player_team":   prop.get("team", ""),
                "player_position": "",
                "stat_type":     stat_type,
                "line":          prop_line,
                "platform":      platform,
                "season_pts_avg": 0, "season_reb_avg": 0, "season_ast_avg": 0,
                "points_avg": 0, "rebounds_avg": 0, "assists_avg": 0,
                "opponent":      "",
                "probability_over": 0.0, "probability_under": 1.0,
                "simulated_mean": 0.0, "simulated_std": 0.0,
                "percentile_10": 0.0, "percentile_50": 0.0, "percentile_90": 0.0,
                "adjusted_projection": 0.0, "overall_adjustment": 1.0,
                "recent_form_ratio": None, "games_played": None,
                "edge_percentage": -50.0, "confidence_score": 0,
                "tier": "Bronze", "tier_emoji": "🥉",
                "direction": "UNDER",
                "recommendation": f"SKIP — {player_name} is {player_status}",
                "forces": {"over_forces": [], "under_forces": []},
                "should_avoid": True,
                "avoid_reasons": [f"Player is {player_status}: {injury_note}"],
                "histogram": [], "score_breakdown": {},
                "line_vs_avg_pct": 0, "recent_form_results": [],
                "player_matched": False, "explanation": None,
                "line_sharpness_force": None, "line_sharpness_penalty": 0.0,
                "trap_line_result": {}, "trap_line_penalty": 0.0,
                "teammate_out_notes": [], "minutes_adjustment_factor": 1.0,
                "player_is_out": True,
                "player_status": player_status,
                "player_status_note": injury_note,
                "player_id": "",
            })
            continue

        # ── Find player in database ───────────────────────────────
        player_data    = find_player_by_name(players_data, player_name)
        player_matched = player_data is not None

        if player_data is None:
            player_data = {
                "name":            player_name,
                "team":            prop.get("team", ""),
                "position":        "SF",
                f"{stat_type}_avg": str(prop_line),
                f"{stat_type}_std": str(prop_line * 0.35),
            }

        player_team  = player_data.get("team", prop.get("team", ""))
        game_context = find_game_context_for_player(player_team, todays_games)

        recent_form_games  = prop.get("recent_form_results", [])

        # ── Feature 6: Minutes Trend — compute using rotation_tracker ──
        # If game logs contain minutes (MIN field), detect trend vs season avg.
        _minutes_trend = None
        _minutes_trend_indicator = "➡️"  # default: stable
        if _rotation_tracker_available and recent_form_games:
            try:
                _minutes_trend = track_minutes_trend(recent_form_games, window=5)
                _td = _minutes_trend.get("trend_direction", "stable")
                _minutes_trend_indicator = "🔺" if _td == "up" else ("🔻" if _td == "down" else "➡️")
            except Exception:
                _minutes_trend = None

        # ── C4: Teammate-Out Usage Adjustment ────────────────────
        # Check if a high-usage teammate is OUT and boost this player's
        # projection accordingly (+8% primary option, +5% secondary, cap +15%).
        teammate_boost, teammate_boost_notes = calculate_teammate_out_boost(
            player_data=player_data,
            injury_status_map=injury_map,
            teammates_data=players_data,
        )

        projection_result  = build_player_projection(
            player_data=player_data,
            opponent_team_abbreviation=game_context.get("opponent", ""),
            is_home_game=game_context.get("is_home", True),
            rest_days=game_context.get("rest_days", 2),
            game_total=game_context.get("game_total", 220.0),
            defensive_ratings_data=defensive_ratings_data,
            teams_data=teams_data,
            recent_form_games=recent_form_games if recent_form_games else None,
            vegas_spread=game_context.get("vegas_spread", 0.0),
            minutes_adjustment_factor=teammate_boost,
            teammate_out_notes=teammate_boost_notes,
        )

        stat_std      = get_stat_standard_deviation(player_data, stat_type)
        projected_stat = projection_result.get(
            f"projected_{stat_type}",
            float(player_data.get(f"{stat_type}_avg", prop_line))
        )

        # ── C8: Minutes-Stat Correlation — pass projected_minutes to sim ─
        # ── C11: KDE from Game Logs — pass recent_game_logs to sim ──────
        # Build stat-specific game log list from recent_form_games for KDE.
        # Maps stat_type keys to the game-log column names.
        _stat_log_key_map = {
            "points": "pts", "rebounds": "reb", "assists": "ast",
            "threes": "fg3m", "steals": "stl", "blocks": "blk",
            "turnovers": "tov",
        }
        _log_key = _stat_log_key_map.get(stat_type, stat_type)
        recent_game_log_values = []
        for _g in (recent_form_games or []):
            _v = _g.get(_log_key, _g.get(stat_type))
            if _v is not None:
                try:
                    recent_game_log_values.append(float(_v))
                except (TypeError, ValueError):
                    pass

        # ── Simulation dispatch: use specialist functions for combo/fantasy/yesno ──
        # Combo stats (PRA, Pts+Rebs, etc.) use correlated Cholesky simulation (C7).
        # Fantasy score stats use the platform-specific weighted-sum formula.
        # Double/triple-double props use threshold-counting simulation.
        # Simple stats fall back to the standard Quantum Matrix Engine 5.6 path.
        _sim_kwargs = dict(
            blowout_risk_factor=projection_result.get("blowout_risk", 0.15),
            pace_adjustment_factor=projection_result.get("pace_factor", 1.0),
            matchup_adjustment_factor=projection_result.get("defense_factor", 1.0),
            home_away_adjustment=projection_result.get("home_away_factor", 0.0),
            rest_adjustment_factor=projection_result.get("rest_factor", 1.0),
        )

        if stat_type in COMBO_STAT_TYPES:
            # Build component projections from the per-stat projection outputs
            _combo_stat_components = COMBO_STATS.get(stat_type, [])
            _comp_proj = {
                s: projection_result.get(
                    f"projected_{s}",
                    float(player_data.get(f"{s}_avg", 0) or 0),
                )
                for s in _combo_stat_components
            }
            _comp_std = {
                s: get_stat_standard_deviation(player_data, s)
                for s in _combo_stat_components
            }
            simulation_output = simulate_combo_stat(
                component_projections=_comp_proj,
                component_std_devs=_comp_std,
                prop_line=prop_line,
                number_of_simulations=simulation_depth,
                **_sim_kwargs,
            )
            # Update projected_stat to the adjusted combo sum for edge calc
            projected_stat = simulation_output.get("adjusted_projection", sum(_comp_proj.values()))

        elif stat_type in FANTASY_STAT_TYPES:
            # Use the platform's weighted-sum fantasy formula
            _formula = FANTASY_SCORING.get(stat_type, {})
            _stat_proj = {
                s: projection_result.get(
                    f"projected_{s}",
                    float(player_data.get(f"{s}_avg", 0) or 0),
                )
                for s in _formula
            }
            _stat_std = {
                s: get_stat_standard_deviation(player_data, s)
                for s in _formula
            }
            simulation_output = simulate_fantasy_score(
                stat_projections=_stat_proj,
                stat_std_devs=_stat_std,
                fantasy_formula=_formula,
                prop_line=prop_line,
                number_of_simulations=simulation_depth,
                **_sim_kwargs,
            )
            projected_stat = simulation_output.get("adjusted_projection", projected_stat)

        elif stat_type == "double_double":
            _dd_stats = ["points", "rebounds", "assists", "blocks", "steals"]
            _dd_proj = {
                s: projection_result.get(
                    f"projected_{s}",
                    float(player_data.get(f"{s}_avg", 0) or 0),
                )
                for s in _dd_stats
            }
            _dd_std = {s: get_stat_standard_deviation(player_data, s) for s in _dd_stats}
            simulation_output = simulate_double_double(
                stat_projections=_dd_proj,
                stat_std_devs=_dd_std,
                number_of_simulations=simulation_depth,
                **_sim_kwargs,
            )

        elif stat_type == "triple_double":
            _td_stats = ["points", "rebounds", "assists"]
            _td_proj = {
                s: projection_result.get(
                    f"projected_{s}",
                    float(player_data.get(f"{s}_avg", 0) or 0),
                )
                for s in _td_stats
            }
            _td_std = {s: get_stat_standard_deviation(player_data, s) for s in _td_stats}
            simulation_output = simulate_triple_double(
                stat_projections=_td_proj,
                stat_std_devs=_td_std,
                number_of_simulations=simulation_depth,
                **_sim_kwargs,
            )

        else:
            # Simple stat: standard Quantum Matrix Engine 5.6 simulation (C5 skew-normal, C8 minutes, C11 KDE)
            simulation_output = run_monte_carlo_simulation(
                projected_stat_average=projected_stat,
                stat_standard_deviation=stat_std,
                prop_line=prop_line,
                number_of_simulations=simulation_depth,
                stat_type=stat_type,
                projected_minutes=projection_result.get("projected_minutes"),
                minutes_std=4.0,
                recent_game_logs=recent_game_log_values if len(recent_game_log_values) >= 15 else None,
                **_sim_kwargs,
            )

        forces_result = analyze_directional_forces(
            player_data=player_data,
            prop_line=prop_line,
            stat_type=stat_type,
            projection_result=projection_result,
            game_context=game_context,
        )

        season_avg_for_stat  = float(player_data.get(f"{stat_type}_avg", 0) or 0)
        line_sharpness_force = detect_line_sharpness(
            prop_line=prop_line,
            season_average=season_avg_for_stat if season_avg_for_stat > 0 else None,
            stat_type=stat_type,
        )
        line_sharpness_penalty = 0.0
        if line_sharpness_force is not None:
            line_sharpness_penalty = min(8.0, line_sharpness_force.get("strength", 0) * 2.5)

        trap_line_result = detect_trap_line(
            prop_line=prop_line,
            season_average=season_avg_for_stat if season_avg_for_stat > 0 else None,
            defense_factor=projection_result.get("defense_factor", 1.0),
            rest_factor=projection_result.get("rest_factor", 1.0),
            game_total=game_context.get("game_total", 220.0),
            blowout_risk=projection_result.get("blowout_risk", 0.15),
            stat_type=stat_type,
        )
        trap_line_penalty = trap_line_result.get("confidence_penalty", 0.0)

        probability_over  = simulation_output.get("probability_over", 0.5)
        edge_pct          = calculate_edge_percentage(probability_over)

        # C10: Historical calibration — adjust confidence score based on
        # how well-calibrated the model has been historically at this
        # probability level.  Returns 0.0 on cold start (no history yet).
        calibration_adj = get_calibration_adjustment(probability_over)

        confidence_output = calculate_confidence_score(
            probability_over=probability_over,
            edge_percentage=edge_pct,
            directional_forces=forces_result,
            defense_factor=projection_result.get("defense_factor", 1.0),
            stat_standard_deviation=stat_std,
            stat_average=season_avg_for_stat,
            simulation_results=simulation_output,
            games_played=int(player_data.get("games_played", 0) or 0) or None,
            recent_form_ratio=projection_result.get("recent_form_ratio"),
            line_sharpness_penalty=line_sharpness_penalty,
            trap_line_penalty=trap_line_penalty,
            calibration_adjustment=calibration_adj,  # C10
        )

        # C12: Closing Line Value — record the model's opening projection and
        # recommendation at analysis time.  Callers can later call
        # engine.clv_tracker.update_closing_line() with the final closing line
        # to compute CLV and validate the model's edge.
        try:
            store_opening_line(
                player_name=player_name,
                stat_type=stat_type,
                opening_line=prop_line,
                model_projection=projected_stat,
                model_direction=confidence_output.get("direction", "OVER"),
                confidence_score=confidence_output.get("confidence_score", 0.0),
                tier=confidence_output.get("tier", "Bronze"),
                edge_percentage=edge_pct,
            )
        except Exception:
            pass  # CLV recording is non-critical; never block analysis

        # F9: Store initial line snapshot for market movement tracking
        try:
            _snap_key = f"{player_name}_{stat_type}"
            if "line_snapshots" not in st.session_state:
                st.session_state["line_snapshots"] = {}
            if _snap_key not in st.session_state["line_snapshots"]:
                st.session_state["line_snapshots"][_snap_key] = {
                    "initial_line": prop_line,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
        except Exception:
            pass

        should_avoid_flag, avoid_reasons = should_avoid_prop(
            probability_over=probability_over,
            directional_forces_result=forces_result,
            edge_percentage=edge_pct,
            stat_standard_deviation=stat_std,
            stat_average=float(player_data.get(f"{stat_type}_avg", prop_line)),
        )

        # Merge kill-switch flags from confidence engine (C2/C3) with
        # should_avoid_prop() results so all sources are surfaced in the UI.
        if confidence_output.get("should_avoid"):
            should_avoid_flag = True
        for extra_reason in confidence_output.get("avoid_reasons", []):
            if extra_reason and extra_reason not in avoid_reasons:
                avoid_reasons.append(extra_reason)

        histogram_data = build_histogram_from_results(
            simulation_output.get("simulated_results", []),
            prop_line,
            number_of_buckets=15,
        )

        explanation = generate_pick_explanation(
            player_data=player_data,
            prop_line=prop_line,
            stat_type=stat_type,
            direction=confidence_output.get("direction", "OVER"),
            projection_result=projection_result,
            simulation_results=simulation_output,
            forces=forces_result,
            confidence_result=confidence_output,
            game_context=game_context,
            platform=platform,
            recent_form_games=prop.get("recent_form_results", []),
            should_avoid=should_avoid_flag,
            avoid_reasons=avoid_reasons,
            trap_line_result=trap_line_result,
            line_sharpness_info=line_sharpness_force,
            teammate_out_notes=projection_result.get("teammate_out_notes", []),
        )

        full_result = {
            "player_name":      player_name,
            "team":             player_team,
            "player_team":      player_team,
            "player_position":  player_data.get("position", ""),
            "stat_type":        stat_type,
            "line":             prop_line,
            "platform":         platform,
            "player_id":        player_data.get("player_id", ""),
            "season_pts_avg":   float(player_data.get("points_avg",   0) or 0),
            "season_reb_avg":   float(player_data.get("rebounds_avg", 0) or 0),
            "season_ast_avg":   float(player_data.get("assists_avg",  0) or 0),
            "points_avg":       float(player_data.get("points_avg",   0) or 0),
            "rebounds_avg":     float(player_data.get("rebounds_avg", 0) or 0),
            "assists_avg":      float(player_data.get("assists_avg",  0) or 0),
            "opponent":         game_context.get("opponent", ""),
            "probability_over": round(probability_over, 4),
            "probability_under":round(1.0 - probability_over, 4),
            "simulated_mean":   round(simulation_output.get("simulated_mean", 0), 1),
            "simulated_std":    round(simulation_output.get("simulated_std",  0), 1),
            "percentile_10":    round(simulation_output.get("percentile_10",  0), 1),
            "percentile_50":    round(simulation_output.get("percentile_50",  0), 1),
            "percentile_90":    round(simulation_output.get("percentile_90",  0), 1),
            "adjusted_projection": round(projected_stat, 1),
            "overall_adjustment":  round(projection_result.get("overall_adjustment", 1.0), 3),
            "recent_form_ratio":   projection_result.get("recent_form_ratio"),
            "games_played":        int(player_data.get("games_played", 0) or 0) or None,
            "edge_percentage":     round(edge_pct, 1),
            "confidence_score":    confidence_output.get("confidence_score", 50),
            "tier":                confidence_output.get("tier", "Bronze"),
            "tier_emoji":          confidence_output.get("tier_emoji", "🥉"),
            "direction":           confidence_output.get("direction", "OVER"),
            "recommendation":      confidence_output.get("recommendation", ""),
            "forces":              forces_result,
            "should_avoid":        should_avoid_flag,
            "avoid_reasons":       avoid_reasons,
            "histogram":           histogram_data,
            "score_breakdown":     confidence_output.get("score_breakdown", {}),
            "line_vs_avg_pct":     prop.get("line_vs_avg_pct", 0),
            "recent_form_results": prop.get("recent_form_results", []),
            "player_matched":      player_matched,
            "explanation":         explanation,
            "line_sharpness_force":   line_sharpness_force,
            "line_sharpness_penalty": round(line_sharpness_penalty, 1),
            "trap_line_result":       trap_line_result,
            "trap_line_penalty":      round(trap_line_penalty, 1),
            "teammate_out_notes":     projection_result.get("teammate_out_notes", []),
            "minutes_adjustment_factor": round(projection_result.get("minutes_adjustment_factor", 1.0), 4),
            "minutes_trend":           _minutes_trend,
            "minutes_trend_indicator": _minutes_trend_indicator,
            "player_is_out":    False,
            "player_status":    player_status,
            "player_status_note": player_status_info.get("injury_note", ""),
        }

        # ── Goblin / Demon Bet Classification ────────────────────────
        # Classify each pick as a Goblin (easy money), Demon (trap/avoid),
        # or Normal bet based on statistical criteria.
        try:
            _season_avg_for_classify = float(player_data.get(f"{stat_type}_avg", 0) or 0) or None
            _bet_classification = classify_bet_type(
                probability_over=probability_over,
                edge_percentage=edge_pct,
                stat_standard_deviation=stat_std,
                projected_stat=projected_stat,
                prop_line=prop_line,
                stat_type=stat_type,
                directional_forces_result=forces_result,
                rest_days=game_context.get("rest_days", 1),
                vegas_spread=game_context.get("vegas_spread", 0.0),
                recent_form_ratio=projection_result.get("recent_form_ratio"),
                season_average=_season_avg_for_classify,
            )
            full_result["bet_type"]        = _bet_classification.get("bet_type", "normal")
            full_result["bet_type_emoji"]  = _bet_classification.get("bet_type_emoji", "")
            full_result["bet_type_label"]  = _bet_classification.get("bet_type_label", "Normal Bet")
            full_result["bet_type_reasons"]= _bet_classification.get("reasons", [])
            full_result["std_devs_from_line"] = _bet_classification.get("std_devs_from_line", 0.0)
            # Demon bets should be added to the avoid list automatically
            if _bet_classification.get("demon") and not full_result.get("should_avoid"):
                full_result["should_avoid"] = True
                full_result["avoid_reasons"] = list(full_result.get("avoid_reasons", [])) + [
                    f"👿 Demon Bet: {'; '.join(_bet_classification.get('reasons', []))}"
                ]
        except Exception:
            full_result["bet_type"]         = "normal"
            full_result["bet_type_emoji"]   = ""
            full_result["bet_type_label"]   = "Normal Bet"
            full_result["bet_type_reasons"] = []
            full_result["std_devs_from_line"] = 0.0

        # ── Capture odds from the original prop (for display) ────────
        full_result["over_odds"]  = prop.get("over_odds",  -110)
        full_result["under_odds"] = prop.get("under_odds", -110)


        try:
            _clv_penalties = get_stat_type_clv_penalties(days=90)
            _clv_stat_penalty = _clv_penalties.get(stat_type, 0.0)
            if _clv_stat_penalty > 0:
                full_result["confidence_score"] = max(0.0, full_result["confidence_score"] - _clv_stat_penalty)
                full_result["clv_stat_penalty"] = _clv_stat_penalty
        except Exception:
            pass

        # ── Feature 9: Market movement adjustment ────────────────────
        try:
            if detect_line_movement is not None:
                _opening_snap = st.session_state.get("line_snapshots", {}).get(
                    f"{player_name}_{stat_type}", {}
                )
                if _opening_snap:
                    _mv = detect_line_movement(
                        player_name, stat_type,
                        _opening_snap.get("initial_line", prop_line),
                        prop_line,
                        full_result.get("direction", "OVER"),
                    )
                    _mv_adj = _mv.get("confidence_adjustment", 0.0)
                    if _mv_adj != 0.0:
                        full_result["confidence_score"] = max(0.0, min(100.0, full_result["confidence_score"] + _mv_adj))
                        full_result["market_movement"] = _mv
        except Exception:
            pass

        analysis_results_list.append(full_result)

    # Detect correlated props
    correlation_warnings = detect_correlated_props(analysis_results_list)
    for idx, warning in correlation_warnings.items():
        if idx < len(analysis_results_list):
            analysis_results_list[idx]["_correlation_warning"] = warning

    # ── Auto-trigger Smart Update if >20% of players are unmatched ─
    # Unmatched players use skeleton stats which reduces accuracy.
    # Fetching fresh rosters resolves most mismatches without user action.
    _unmatched_players = list(dict.fromkeys(
        r.get("player_name", "")
        for r in analysis_results_list
        if not r.get("player_matched", True) and not r.get("player_is_out", False)
    ))
    _total_non_out = sum(
        1 for r in analysis_results_list if not r.get("player_is_out", False)
    )
    _unmatched_ratio = len(_unmatched_players) / max(_total_non_out, 1)
    if _unmatched_ratio > 0.20 and todays_games:
        st.info(
            f"🔄 **{len(_unmatched_players)} player(s) not found** in local database "
            f"({_unmatched_ratio*100:.0f}% of props). Triggering Smart Roster Update…"
        )
        try:
            from data.live_data_fetcher import fetch_todays_players_only as _fetch_today
            _roster_result = _fetch_today(todays_games, progress_callback=None)
            if _roster_result:
                # Reload players data after the update
                _refreshed_players = load_players_data()
                # Re-match previously-unmatched players
                _rematched = 0
                for _r in analysis_results_list:
                    if not _r.get("player_matched", True) and not _r.get("player_is_out", False):
                        _pd = find_player_by_name(_refreshed_players, _r.get("player_name", ""))
                        if _pd is not None:
                            _r["player_matched"] = True
                            _rematched += 1
                if _rematched:
                    st.success(f"✅ Smart Update matched {_rematched} additional player(s).")
        except Exception as _su_err:
            # Non-fatal — proceed with existing results
            _logger.warning(f"Smart Update error (non-fatal): {_su_err}")

    st.session_state["analysis_results"] = analysis_results_list
    st.session_state["analysis_timestamp"] = datetime.datetime.now()

    # ── Persist analysis session to SQLite (survives page refresh/inactivity) ──
    try:
        from tracking.database import save_analysis_session as _save_session
        _save_session(
            analysis_results=analysis_results_list,
            todays_games=st.session_state.get("todays_games", []),
            selected_picks=st.session_state.get("selected_picks", []),
        )
    except Exception as _persist_err:
        pass  # Non-fatal — session state still has results
    progress_bar.empty()
    _analysis_elapsed = time.time() - _analysis_start_time
    st.success(
        f"✅ Analysis complete! **{len(analysis_results_list)}** props analyzed "
        f"in **{_analysis_elapsed:.1f}s**."
    )

    # ── Store ALL picks to all_analysis_picks table ──────────────
    try:
        from tracking.database import insert_analysis_picks as _insert_picks
        _stored = _insert_picks(analysis_results_list)
        if _stored > 0:
            _logger.info(f"Stored {_stored} analysis picks to all_analysis_picks table.")
    except Exception as _store_err:
        _logger.warning(f"Store analysis picks error (non-fatal): {_store_err}")

    # ── Auto-log all qualifying picks to the Bet Tracker ────────
    try:
        from tracking.bet_tracker import auto_log_analysis_bets as _auto_log
        _auto_logged = _auto_log(analysis_results_list, minimum_edge=minimum_edge)
        if _auto_logged > 0:
            st.info(
                f"📊 Auto-logged **{_auto_logged}** qualifying pick(s) to the Bet Tracker."
            )
    except Exception as _auto_log_err:
        # Auto-logging is best-effort — never block the main analysis flow
        _logger.warning(f"Auto-log error (non-fatal): {_auto_log_err}")

    st.rerun()

# ============================================================
# END SECTION: Analysis Runner
# ============================================================

# ============================================================
# SECTION: Display Analysis Results
# ============================================================

analysis_results = st.session_state.get("analysis_results", [])

# Show a notice if results were reloaded from the saved session
if analysis_results and st.session_state.get("_analysis_session_reloaded_at"):
    _reloaded_ts = st.session_state["_analysis_session_reloaded_at"]
    st.info(
        f"💾 **Analysis restored from saved session** (last run: {_reloaded_ts}). "
        "Results are preserved from your last analysis run — click **🚀 Run Analysis** above to refresh."
    )

if analysis_results:
    st.divider()

    # Filter results
    if show_all_or_top == "Top picks only (edge ≥ threshold)":
        displayed_results = [
            r for r in analysis_results
            if abs(r.get("edge_percentage", 0)) >= minimum_edge
            and not r.get("should_avoid", False)
        ]
    else:
        displayed_results = analysis_results

    # ── Tier Filter & Bet Classification Filter ──────────────────────────
    _na_filter_col1, _na_filter_col2 = st.columns(2)
    with _na_filter_col1:
        _na_tier_filter = st.multiselect(
            "Filter by Tier",
            ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"],
            default=[],
            key="na_tier_filter",
            help="Show only picks matching the selected tiers. Leave empty to show all tiers.",
        )
    with _na_filter_col2:
        _na_bet_type_filter = st.multiselect(
            "Bet Classification",
            ["🧌 Goblin — Easy Money", "⚡ Normal", "👿 Demon — Trap/Avoid"],
            default=[],
            key="na_bet_type_filter",
            help="Filter by bet type. Leave empty to show all. Select 'Goblin — Easy Money' to see only the strongest picks.",
        )
    if _na_tier_filter:
        _na_tier_names = [t.split(" ")[0] for t in _na_tier_filter]
        displayed_results = [r for r in displayed_results if r.get("tier") in _na_tier_names]
    if _na_bet_type_filter:
        _na_bt_map = {
            "🧌 Goblin — Easy Money": "goblin",
            "👿 Demon — Trap/Avoid": "demon",
            "⚡ Normal": "normal",
        }
        _na_bt_values = [_na_bt_map[t] for t in _na_bet_type_filter if t in _na_bt_map]
        displayed_results = [r for r in displayed_results if r.get("bet_type", "normal") in _na_bt_values]

    # Sort by confidence score descending
    displayed_results.sort(
        key=lambda r: r.get("confidence_score", 0),
        reverse=True,
    )

    # ── Deduplicate by (player_name, stat_type, line, direction) ──
    # Prevents duplicate player cards and duplicate Streamlit element keys
    # when the same prop appears multiple times (e.g. from multiple platforms).
    _seen_result_keys: set = set()
    _deduped: list = []
    for _r in displayed_results:
        _rkey = (
            _r.get("player_name", ""),
            _r.get("stat_type", ""),
            _r.get("line", 0),
            _r.get("direction", "OVER"),
        )
        if _rkey not in _seen_result_keys:
            _seen_result_keys.add(_rkey)
            _deduped.append(_r)
    displayed_results = _deduped

    # ── Summary metrics ────────────────────────────────────────
    total_analyzed   = len(analysis_results)
    total_over_picks = sum(1 for r in displayed_results if r.get("direction") == "OVER")
    total_under_picks= sum(1 for r in displayed_results if r.get("direction") == "UNDER")
    platinum_count   = sum(1 for r in displayed_results if r.get("tier") == "Platinum")
    gold_count       = sum(1 for r in displayed_results if r.get("tier") == "Gold")
    goblin_count     = sum(1 for r in analysis_results if r.get("bet_type") == "goblin")
    demon_count      = sum(1 for r in analysis_results if r.get("bet_type") == "demon")
    avg_edge         = (
        sum(abs(r.get("edge_percentage", 0)) for r in displayed_results) / len(displayed_results)
        if displayed_results else 0
    )
    unmatched_count  = sum(1 for r in analysis_results if not r.get("player_matched", True))

    st.subheader(f"📊 Results: {len(displayed_results)} picks (of {total_analyzed} analyzed)")

    sum_col1, sum_col2, sum_col3, sum_col4, sum_col5, sum_col6, sum_col7 = st.columns(7)
    sum_col1.metric("Showing",     len(displayed_results))
    sum_col2.metric("⬆️ OVER",    total_over_picks)
    sum_col3.metric("⬇️ UNDER",   total_under_picks)
    sum_col4.metric("💎 Platinum", platinum_count)
    sum_col5.metric("🥇 Gold",     gold_count)
    sum_col6.metric("🧌 Goblin",   goblin_count)
    sum_col7.metric("👿 Demon",    demon_count)

    # ── Slate Summary Dashboard ────────────────────────────────
    silver_count  = sum(1 for r in displayed_results if r.get("tier") == "Silver")
    bronze_count  = sum(1 for r in displayed_results if r.get("tier") == "Bronze")
    best_pick     = max(
        (r for r in displayed_results if not r.get("player_is_out", False)),
        key=lambda r: r.get("confidence_score", 0),
        default=None,
    )
    _tier_bar_html = (
        f'<span style="color:#c800ff;font-weight:700;">💎 {platinum_count} Platinum</span>'
        f' &nbsp;·&nbsp; <span style="color:#ffd700;font-weight:600;">🥇 {gold_count} Gold</span>'
        f' &nbsp;·&nbsp; <span style="color:#b0bec5;">🥈 {silver_count} Silver</span>'
        f' &nbsp;·&nbsp; <span style="color:#b0bec5;">🥉 {bronze_count} Bronze</span>'
    )
    _best_html = ""
    if best_pick:
        _bp_name  = _html.escape(str(best_pick.get("player_name", "")))
        _bp_stat  = _html.escape(str(best_pick.get("stat_type", "")).title())
        _bp_line  = best_pick.get("line", 0)
        _bp_dir   = "Over" if best_pick.get("direction") == "OVER" else "Under"
        _bp_conf  = best_pick.get("confidence_score", 0)
        _bp_tier  = best_pick.get("tier", "")
        _bp_emoji = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}.get(_bp_tier, "🏀")
        _best_html = (
            f'<div style="margin-top:10px;padding:10px 14px;background:rgba(255,94,0,0.08);'
            f'border-radius:6px;border-left:3px solid #ff5e00;">'
            f'<span style="color:#ff5e00;font-weight:700;font-size:0.85rem;">🏆 Best Pick: </span>'
            f'<span style="color:#e0e7ef;font-weight:600;">{_bp_emoji} {_bp_name} — {_bp_dir} {_bp_line} {_bp_stat}</span>'
            f'<span style="color:#00f0ff;font-weight:700;margin-left:10px;">{_bp_conf:.0f}/100</span>'
            f'</div>'
        )
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#0f1424,#14192b);border:1px solid rgba(255,94,0,0.25);'
        f'border-radius:8px;padding:14px 18px;margin:8px 0 14px;">'
        f'<div style="font-size:0.9rem;font-weight:600;color:#e0e7ef;margin-bottom:6px;">'
        f'🗂️ Tier Distribution &nbsp;·&nbsp; '
        f'<span style="color:#00f0ff;">Avg Edge: {avg_edge:.1f}%</span>'
        f'</div>'
        f'<div style="font-size:0.85rem;">{_tier_bar_html}</div>'
        + _best_html +
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Quick-select buttons ───────────────────────────────────
    _qb_col1, _qb_col2, _qb_col3 = st.columns([1, 1, 2])
    with _qb_col1:
        if st.button("💎 Select All Platinum", help="Add all Platinum tier picks to Entry Builder"):
            _plat_picks = [
                r for r in displayed_results
                if r.get("tier") == "Platinum"
                and not r.get("player_is_out", False)
                and not r.get("should_avoid", False)
            ]
            _existing_keys = {p.get("key") for p in st.session_state.get("selected_picks", [])}
            _added = 0
            for r in _plat_picks:
                _stat     = r.get("stat_type", "").lower()
                _line     = r.get("line", 0)
                _dir      = r.get("direction", "OVER")
                _pick_key = f"{r.get('player_name', '')}_{_stat}_{_line}_{_dir}"
                if _pick_key not in _existing_keys:
                    st.session_state.setdefault("selected_picks", []).append({
                        "key":             _pick_key,
                        "player_name":     r.get("player_name", ""),
                        "stat_type":       _stat,
                        "line":            _line,
                        "direction":       _dir,
                        "confidence_score": r.get("confidence_score", 0),
                        "tier":            r.get("tier", "Platinum"),
                        "tier_emoji":      "💎",
                        "platform":        r.get("platform", ""),
                        "edge_percentage": r.get("edge_percentage", 0),
                    })
                    _added += 1
            if _added:
                st.success(f"✅ Added {_added} Platinum pick(s).")
                st.rerun()
            else:
                st.info("All Platinum picks already added.")
    with _qb_col2:
        if st.button("🥇 Select All Gold+", help="Add all Gold and Platinum tier picks to Entry Builder"):
            _gold_picks = [
                r for r in displayed_results
                if r.get("tier") in ("Platinum", "Gold")
                and not r.get("player_is_out", False)
                and not r.get("should_avoid", False)
            ]
            _existing_keys = {p.get("key") for p in st.session_state.get("selected_picks", [])}
            _added = 0
            for r in _gold_picks:
                _stat     = r.get("stat_type", "").lower()
                _line     = r.get("line", 0)
                _dir      = r.get("direction", "OVER")
                _pick_key = f"{r.get('player_name', '')}_{_stat}_{_line}_{_dir}"
                if _pick_key not in _existing_keys:
                    _t_emoji = "💎" if r.get("tier") == "Platinum" else "🥇"
                    st.session_state.setdefault("selected_picks", []).append({
                        "key":             _pick_key,
                        "player_name":     r.get("player_name", ""),
                        "stat_type":       _stat,
                        "line":            _line,
                        "direction":       _dir,
                        "confidence_score": r.get("confidence_score", 0),
                        "tier":            r.get("tier", "Gold"),
                        "tier_emoji":      _t_emoji,
                        "platform":        r.get("platform", ""),
                        "edge_percentage": r.get("edge_percentage", 0),
                    })
                    _added += 1
            if _added:
                st.success(f"✅ Added {_added} Gold+ pick(s).")
                st.rerun()
            else:
                st.info("All Gold+ picks already added.")

    if unmatched_count > 0:
        # Deduplicate: same player may have multiple stat types, each flagged separately.
        # Only count and list each unique player name once.
        unmatched_names_deduped = list(dict.fromkeys(
            r.get("player_name", "") for r in analysis_results
            if not r.get("player_matched", True)
            and not r.get("player_is_out", False)  # exclude confirmed-out players
        ))
        unmatched_unique_count = len(unmatched_names_deduped)
        if unmatched_unique_count > 0:
            _display_names = unmatched_names_deduped[:10]
            _overflow = unmatched_unique_count - len(_display_names)
            _inline = ", ".join(_display_names) + (f" and {_overflow} more" if _overflow > 0 else "")
            st.warning(
                f"⚠️ **{unmatched_unique_count} player(s) not found** in database — "
                + _inline
                + " — results may be less accurate. Run a **Smart Update** on the Data Feed page to refresh roster data."
            )
            if _overflow > 0:
                with st.expander(f"See all {unmatched_unique_count} unmatched players"):
                    st.write(", ".join(unmatched_names_deduped))

    st.divider()

    # ============================================================
    # SECTION: 🧌 Goblin Picks — Extreme Edge "Easy Money" Bets
    # ============================================================
    _goblin_picks = [
        r for r in displayed_results
        if r.get("bet_type") == "goblin"
        and not r.get("player_is_out", False)
    ]
    _goblin_picks = sorted(
        _goblin_picks,
        key=lambda r: (abs(r.get("edge_percentage", 0)), r.get("confidence_score", 0)),
        reverse=True,
    )

    if _goblin_picks:
        _gcol_logo, _gcol_title = st.columns([1, 6])
        with _gcol_logo:
            if os.path.exists(_GOBLIN_LOGO_PATH):
                st.image(_GOBLIN_LOGO_PATH, width=110)
        with _gcol_title:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#0d1a0d,#102010);'
                'border:2px solid #4caf50;border-radius:10px;padding:16px 20px;margin-bottom:12px;">'
                '<h3 style="color:#4caf50;font-family:Orbitron,sans-serif;margin:0 0 6px;">🧌 Goblin Picks — Easy Money</h3>'
                '<p style="color:#a0d0a0;font-size:0.85rem;margin:0;">'
                'Extreme-edge bets where the model projection is far beyond the line — '
                'massive edge, high probability, the closest thing to a sure bet in sports.'
                '</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            get_education_box_html(
                "What is a Goblin Bet? 🧌",
                "A <strong>Goblin bet</strong> is a bet where the platform's line is so far from "
                "reality that it's almost free money. Think of it like finding a $20 bill on the "
                "ground — the sportsbook set the line at a number that's <em>WAY</em> below (or "
                "above) where the player is actually likely to land.<br><br>"
                "<strong>Example:</strong> LeBron James OVER 12.5 points when he averages 25 and our "
                "model projects 26.8. The line is absurdly low — there's an 88% chance he goes over. "
                "That's a Goblin. 🧌<br><br>"
                "<strong>Criteria:</strong> Model projection is 2+ standard deviations from the line, "
                "probability ≥80%, edge ≥25%.",
            ),
            unsafe_allow_html=True,
        )
        for _gp in _goblin_picks:
            _gp_name   = _html.escape(str(_gp.get("player_name", "")))
            _gp_team   = _html.escape(str(_gp.get("player_team", _gp.get("team", ""))))
            _gp_stat   = _html.escape(str(_gp.get("stat_type", "")).title())
            _gp_dir    = _html.escape(str(_gp.get("direction", "OVER")))
            _gp_line   = _gp.get("line", 0)
            _gp_proj   = _gp.get("adjusted_projection", _gp.get("projected_stat", 0))
            _gp_prob   = _gp.get("probability_over", 0.5) if _gp_dir == "OVER" else 1.0 - _gp.get("probability_over", 0.5)
            _gp_edge   = abs(_gp.get("edge_percentage", 0))
            _gp_conf   = _gp.get("confidence_score", 0)
            _gp_sigma  = abs(_gp.get("std_devs_from_line", 0))
            _gp_tier   = _html.escape(str(_gp.get("tier", "")))
            _gp_tier_emoji = _gp.get("tier_emoji", "")
            # Season average for the stat
            _gp_stat_key = _gp.get("stat_type", "points").lower()
            _gp_avg_map = {
                "points": "season_pts_avg", "rebounds": "season_reb_avg",
                "assists": "season_ast_avg", "threes": "season_threes_avg",
            }
            _gp_season_avg = float(_gp.get(_gp_avg_map.get(_gp_stat_key, ""), 0) or 0)
            _gp_reasons_html = "".join(
                f'<li style="color:#c8e6c9;font-size:0.8rem;">{_html.escape(str(r))}</li>'
                for r in _gp.get("bet_type_reasons", [])
            )
            _over_odds  = _gp.get("over_odds",  -110)
            _under_odds = _gp.get("under_odds", -110)
            _odds_for_dir = _over_odds if _gp_dir == "OVER" else _under_odds
            _odds_str = f"+{_odds_for_dir}" if _odds_for_dir > 0 else str(_odds_for_dir)
            # Plain-English reason sentence
            _gp_plain_reason = (
                f"Line is set at {_gp_line}"
                + (f", but {_gp_name} averages {_gp_season_avg:.1f} and we project {_gp_proj:.1f}." if _gp_season_avg else f", but we project {_gp_proj:.1f}.")
                + " The gap is massive — easy money."
            )
            _gp_team_badge = (
                f'<span style="background:rgba(76,175,80,0.2);color:#81c784;padding:1px 7px;'
                f'border-radius:4px;font-size:0.78rem;font-weight:600;margin-left:7px;'
                f'border:1px solid rgba(76,175,80,0.4);">{_gp_team}</span>'
                if _gp_team else ""
            )
            st.markdown(
                f'<div style="background:#0d1a0d;border:2px solid #4caf50;border-radius:8px;'
                f'padding:14px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                f'<div>'
                f'<span style="color:#4caf50;font-weight:800;font-size:1.05rem;">🧌 {_gp_name}</span>'
                f'{_gp_team_badge}'
                f'<span style="color:#c8e6c9;font-size:0.9rem;margin-left:10px;">'
                f'{_gp_dir} {_gp_line} {_gp_stat}</span>'
                f'<span style="color:#a0d0a0;font-size:0.8rem;margin-left:8px;">'
                f'(Proj: <strong style="color:#4caf50;">{_gp_proj:.1f}</strong>'
                + (f' &nbsp;|&nbsp; Avg: {_gp_season_avg:.1f}' if _gp_season_avg else "")
                + f' &nbsp;|&nbsp; {_gp_sigma:.1f}σ from line)</span>'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<span style="background:#4caf50;color:#0a1a0a;padding:3px 10px;border-radius:4px;'
                f'font-size:0.8rem;font-weight:700;margin-right:6px;">SAFE {_gp_conf:.0f}/100</span>'
                f'<span style="color:#81c784;font-size:0.8rem;">Edge {_gp_edge:+.1f}%</span>'
                f'<br><span style="color:#69f0ae;font-size:0.75rem;">'
                f'P({_gp_dir.title()}): {_gp_prob*100:.0f}%</span>'
                f'<span style="color:#a0d0a0;font-size:0.75rem;margin-left:8px;">'
                f'Odds: {_odds_str}</span>'
                f'</div>'
                f'</div>'
                f'<div style="margin-top:8px;padding:6px 10px;background:rgba(76,175,80,0.08);'
                f'border-radius:4px;color:#a5d6a7;font-size:0.8rem;font-style:italic;">'
                f'💡 {_html.escape(_gp_plain_reason)}'
                f'</div>'
                f'<div style="margin-top:8px;">'
                f'<span style="color:#388e3c;font-size:0.75rem;font-weight:600;">WHY IT\'S A GOBLIN:</span>'
                f'<ul style="margin:4px 0 0 16px;padding:0;">{_gp_reasons_html}</ul>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(f"*{len(_goblin_picks)} Goblin pick(s) found on this slate.*")
        st.divider()

    # ============================================================
    # SECTION: 👿 Demon Bets Warning Section
    # ============================================================
    _demon_picks = [
        r for r in analysis_results  # Use ALL results, not just displayed
        if r.get("bet_type") == "demon"
        and not r.get("player_is_out", False)
    ]
    if _demon_picks:
        with st.expander(
            f"👿 Demon Bets Detected ({len(_demon_picks)}) — Click to See Traps to AVOID",
            expanded=False,
        ):
            _dcol_logo, _dcol_title = st.columns([1, 6])
            with _dcol_logo:
                if os.path.exists(_DEMON_LOGO_PATH):
                    st.image(_DEMON_LOGO_PATH, width=110)
            with _dcol_title:
                st.markdown(
                    '<div style="background:rgba(180,0,0,0.15);border:2px solid #ff4444;'
                    'border-radius:10px;padding:14px 18px;margin-bottom:14px;">'
                    '<strong style="color:#ff4444;font-size:1.0rem;">👿 Demon Bets Warning</strong><br>'
                    '<span style="color:#ffb0b0;font-size:0.85rem;">These picks LOOK appealing but are statistically dangerous. '
                    'Demon bets have hidden structural risks — hot streak regression, back-to-back fatigue, '
                    'conflicting forces, or high-variance stats with tiny edges. '
                    'They are automatically added to your Avoid List.</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                get_education_box_html(
                    "What is a Demon Bet? 👿",
                    "A <strong>Demon bet</strong> LOOKS appealing — maybe a star player has a nice "
                    "edge — but has hidden danger signals that make it a likely loser. It's a trap.<br><br>"
                    "<strong>There are 4 types of Demons:</strong><br>"
                    "1. <strong>Conflict Demon:</strong> The model's forces are fighting each other — "
                    "nearly 50/50 OVER vs UNDER. It's a coin flip disguised as an edge.<br>"
                    "2. <strong>Variance Demon:</strong> High-variance stat (3-pointers, steals, blocks) "
                    "with a tiny edge (&lt;8%). These stats are too random game-to-game.<br>"
                    "3. <strong>Fatigue Demon:</strong> Back-to-back game + big spread (blowout expected). "
                    "Player will likely rest in the 4th quarter.<br>"
                    "4. <strong>Regression Demon:</strong> The line is set at a hot streak value (125%+ of "
                    "season average). The player is due to come back to earth.<br><br>"
                    "Demon bets are <em>automatically added to your Avoid List</em>.",
                ),
                unsafe_allow_html=True,
            )
            for _dp in _demon_picks:
                _dp_name  = _html.escape(str(_dp.get("player_name", "")))
                _dp_team  = _html.escape(str(_dp.get("player_team", _dp.get("team", ""))))
                _dp_stat  = _html.escape(str(_dp.get("stat_type", "")).title())
                _dp_dir   = _html.escape(str(_dp.get("direction", "OVER")))
                _dp_line  = _dp.get("line", 0)
                _dp_proj  = _dp.get("adjusted_projection", 0)
                _dp_edge  = _dp.get("edge_percentage", 0)
                # Detect demon type from reasons list
                _dp_reasons_list = _dp.get("bet_type_reasons", [])
                _dp_demon_type = "Demon"
                _dp_type_color = "#ff4444"
                for _r_text in _dp_reasons_list:
                    _r_lower = str(_r_text).lower()
                    if "conflict" in _r_lower or "50/50" in _r_lower or "conflicting" in _r_lower:
                        _dp_demon_type = "Conflict Demon"
                        break
                    elif "variance" in _r_lower or "high-variance" in _r_lower or "random" in _r_lower:
                        _dp_demon_type = "Variance Demon"
                        break
                    elif "fatigue" in _r_lower or "back-to-back" in _r_lower or "b2b" in _r_lower:
                        _dp_demon_type = "Fatigue Demon"
                        break
                    elif "regression" in _r_lower or "hot streak" in _r_lower or "125%" in _r_lower:
                        _dp_demon_type = "Regression Demon"
                        break
                _dp_type_descriptions = {
                    "Conflict Demon": "Forces nearly 50/50 — a coin flip disguised as an edge.",
                    "Variance Demon": "High-variance stat with a tiny edge — too random to rely on.",
                    "Fatigue Demon": "Back-to-back game — player may rest late in a blowout.",
                    "Regression Demon": "Line set at hot-streak value — player is due to regress.",
                    "Demon": "Hidden structural risk makes this pick dangerous.",
                }
                _dp_type_desc = _dp_type_descriptions.get(_dp_demon_type, "")
                _dp_reasons_html = "".join(
                    f'<li style="color:#ffb0b0;font-size:0.82rem;">{_html.escape(str(r))}</li>'
                    for r in _dp_reasons_list
                )
                _dp_team_badge = (
                    f'<span style="background:rgba(255,68,68,0.15);color:#ff8a80;padding:1px 7px;'
                    f'border-radius:4px;font-size:0.78rem;font-weight:600;margin-left:7px;'
                    f'border:1px solid rgba(255,68,68,0.3);">{_dp_team}</span>'
                    if _dp_team else ""
                )
                st.markdown(
                    f'<div style="background:rgba(180,0,0,0.08);border:1px solid rgba(255,68,68,0.35);'
                    f'border-radius:8px;padding:12px 16px;margin-bottom:10px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div>'
                    f'<span style="color:#ff6666;font-weight:700;">👿 {_dp_name}</span>'
                    f'{_dp_team_badge}'
                    f'<span style="background:#ff4444;color:#fff;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.72rem;font-weight:700;margin-left:8px;">{_dp_demon_type}</span>'
                    f'</div>'
                    f'<div style="text-align:right;">'
                    f'<span style="color:#ffb0b0;font-size:0.85rem;">{_dp_dir} {_dp_line} {_dp_stat} '
                    f'(Proj: {_dp_proj:.1f})</span>'
                    f'<br><span style="color:#ff4444;font-size:0.8rem;font-weight:600;">'
                    f'Edge: {_dp_edge:+.1f}%</span>'
                    f'</div>'
                    f'</div>'
                    + (
                        f'<div style="margin-top:6px;padding:5px 9px;background:rgba(255,68,68,0.06);'
                        f'border-radius:4px;color:#ffb0b0;font-size:0.79rem;font-style:italic;">'
                        f'⚠️ {_html.escape(_dp_type_desc)}'
                        f'</div>'
                        if _dp_type_desc else ""
                    )
                    + f'<div style="margin-top:8px;">'
                    f'<span style="color:#ff4444;font-size:0.75rem;font-weight:600;">WHY IT\'S A DEMON (AVOID):</span>'
                    f'<ul style="margin:4px 0 0 16px;padding:0;">{_dp_reasons_html}</ul>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

    # ── 🏆 Best Single Bets (shown before parlays for maximum visibility) ─
    _single_bet_pool = [
        r for r in displayed_results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and r.get("tier", "Bronze") in {"Platinum", "Gold", "Silver"}
    ]
    _single_bet_pool = sorted(
        _single_bet_pool,
        key=lambda r: (r.get("confidence_score", 0), abs(r.get("edge_percentage", 0))),
        reverse=True,
    )[:8]  # Show top 8

    if _single_bet_pool:
        # ── Gold tier banner (with Gold_Logo.png) ──────────────────────
        _gold_pool = [r for r in _single_bet_pool if r.get("tier") in ("Gold", "Platinum")]
        if _gold_pool:
            _goldcol_logo, _goldcol_title = st.columns([1, 6])
            with _goldcol_logo:
                if os.path.exists(_GOLD_LOGO_PATH):
                    st.image(_GOLD_LOGO_PATH, width=110)
            with _goldcol_title:
                st.markdown(
                    '<div style="background:linear-gradient(135deg,#1a1200,#231800);'
                    'border:2px solid #ffd700;border-radius:10px;padding:14px 18px;margin-bottom:4px;">'
                    '<h3 style="color:#ffd700;font-family:Orbitron,sans-serif;margin:0 0 4px;">🥇 Gold Tier Picks</h3>'
                    '<p style="color:#ffe082;font-size:0.85rem;margin:0;">'
                    'High-confidence picks with strong model projections and favorable matchups. '
                    'Gold picks are ideal for your core entry legs.'
                    '</p>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            '<div style="background:linear-gradient(135deg,#0f1a2e,#14192b);'
            'border:2px solid #00f0ff;border-radius:10px;padding:16px 20px;margin-bottom:20px;">'
            '<h3 style="color:#00f0ff;font-family:Orbitron,sans-serif;margin:0 0 6px;">🏆 Best Single Bets</h3>'
            '<p style="color:#a0b4d0;font-size:0.85rem;margin:0;">Top individual picks ranked by SAFE Score™ — Silver tier and above</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        _TIER_COLORS = {"Platinum": "#c800ff", "Gold": "#ff5e00", "Silver": "#b0c0d8"}
        for _sb in _single_bet_pool:
            _sb_tier = _sb.get("tier", "Bronze")
            _sb_color = _TIER_COLORS.get(_sb_tier, "#b0c0d8")
            _sb_name  = _html.escape(str(_sb.get("player_name", "")))
            _sb_stat  = _html.escape(str(_sb.get("stat_type", "")).title())
            _sb_dir   = _html.escape(str(_sb.get("direction", "OVER")))
            _sb_line  = _sb.get("line", _sb.get("prop_line", ""))
            _sb_conf  = _sb.get("confidence_score", 0)
            _sb_edge  = _sb.get("edge_percentage", 0)
            _sb_emoji = _sb.get("tier_emoji", "🥈")
            st.markdown(
                f'<div style="background:#14192b;border-radius:8px;padding:12px 16px;'
                f'margin-bottom:10px;border-left:4px solid {_sb_color};">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div>'
                f'<span style="color:{_sb_color};font-weight:700;font-size:1rem;">{_sb_emoji} {_sb_name}</span>'
                f'<span style="color:#c0d0e8;font-size:0.9rem;margin-left:10px;">'
                f'{_sb_dir} {_sb_line} {_sb_stat}</span>'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<span style="background:{_sb_color};color:#0a0f1a;padding:2px 8px;border-radius:4px;'
                f'font-size:0.78rem;font-weight:700;">SAFE {_sb_conf:.0f}/100</span>'
                f'<span style="color:#00f0ff;font-size:0.78rem;margin-left:8px;">Edge {_sb_edge:+.1f}%</span>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── 🎯 Strongly Suggested Parlays (at TOP for maximum visibility) ─
    strategy_entries = _build_entry_strategy(displayed_results)
    if strategy_entries:
        st.markdown(
            '<div style="background:linear-gradient(135deg,#0f1a2e,#14192b);'
            'border:2px solid #ff5e00;border-radius:10px;padding:16px 20px;margin-bottom:20px;">'
            '<h3 style="color:#ff5e00;font-family:Orbitron,sans-serif;margin:0 0 6px;">🎯 Strongly Suggested Parlays</h3>'
            '<p style="color:#a0b4d0;font-size:0.85rem;margin:0;">Optimized multi-leg combos ranked by combined EDGE Score™</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        _PARLAY_STARS = {2: "⭐", 3: "⭐⭐", 4: "⭐⭐⭐", 5: "⭐⭐⭐", 6: "⭐⭐⭐"}
        _PARLAY_LABEL = {
            2: "Best 2-Leg Parlay",
            3: "Best 3-Leg Parlay",
            4: "Best 4-Leg Parlay",
            5: "Best 5-Leg Parlay",
            6: "Max Entry (6-Leg)",
        }
        for _i, entry in enumerate(strategy_entries):
            _num     = entry.get("num_legs", 0)
            _label   = _PARLAY_LABEL.get(_num, entry.get("combo_type", ""))
            _star    = _PARLAY_STARS.get(_num, "")
            # Top 2 entries get a glow border
            _glow = "box-shadow:0 0 14px rgba(255,94,0,0.45);" if _i < 2 else ""
            picks_html = ""
            for pick_str in entry.get("picks", []):
                parts = pick_str.split(" ", 1)
                pname = _html.escape(parts[0]) if parts else ""
                rest  = _html.escape(parts[1]) if len(parts) > 1 else ""
                picks_html += (
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                    f'<span style="color:#ff5e00;font-weight:600;">{pname}</span>'
                    f'<span style="color:#c0d0e8;">{rest}</span>'
                    f'</div>'
                )
            reasons = entry.get("reasons", [])
            reason_text = _html.escape(" | ".join(reasons)) if reasons else _html.escape(entry.get("strategy", ""))
            combined = entry.get("combined_prob", 0)
            avg_edge = entry.get("avg_edge", 0)
            avg_conf = entry.get("safe_avg", "—")
            st.markdown(
                f'<div style="background:#14192b;border-radius:8px;padding:15px 18px;'
                f'margin-bottom:14px;border-left:4px solid #ff5e00;{_glow}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
                f'<h4 style="color:#ff5e00;margin:0;font-family:Orbitron,sans-serif;">'
                f'{_star} {_label}</h4>'
                f'<span style="background:#ff5e00;color:#0a0f1a;padding:3px 10px;border-radius:4px;'
                f'font-size:0.8rem;font-weight:700;">SAFE: {avg_conf}/100</span>'
                f'</div>'
                f'{picks_html}'
                f'<div style="margin-top:10px;padding:7px 10px;background:rgba(20,25,43,0.7);border-radius:4px;">'
                f'<span style="color:#00c8ff;font-size:0.82rem;">💡 {reason_text}</span>'
                f'</div>'
                f'<div style="display:flex;gap:18px;margin-top:8px;font-size:0.8rem;color:#c0d0e8;">'
                f'<span>Combined prob: {combined:.1f}%</span>'
                f'<span>Avg edge: {avg_edge:+.1f}%</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Not enough high-edge picks to build parlay combinations. Lower the edge threshold or add more props.")

    st.divider()

    # ── Confidence Bars: sorted ranking ─────────────────────────
    non_out_results = [r for r in displayed_results if not r.get("player_is_out", False)]
    if non_out_results:
        with st.expander("📈 Confidence Rankings (all picks)", expanded=True):
            _tier_icon_map = {
                "Platinum": "💎", "Gold": "🔒", "Silver": "✓", "Bronze": "⭐"
            }
            for r in non_out_results:
                _stat     = r.get("stat_type", "")
                _emoji    = _STAT_EMOJI.get(_stat, "🏀")
                _dir      = "Over" if r.get("direction") == "OVER" else "Under"
                _label    = (
                    f"{r.get('player_name', '')} — "
                    f"{_emoji} {_dir} {r.get('line', '')} {_stat.title()}"
                )
                st.markdown(
                    get_qds_confidence_bar_html(
                        label=_label,
                        percentage=r.get("confidence_score", 50),
                        tier_icon=_tier_icon_map.get(r.get("tier", "Bronze"), "⭐"),
                    ),
                    unsafe_allow_html=True,
                )

    # ── Team Breakdown (when single game) ────────────────────────
    if len(todays_games) == 1:
        g = todays_games[0]
        home_t = g.get("home_team", "")
        away_t = g.get("away_team", "")
        if home_t and away_t:
            with st.expander("🏀 Team Matchup Breakdown"):
                tc1, tc2 = st.columns(2)
                from styles.theme import get_team_colors
                home_color, _ = get_team_colors(home_t)
                away_color, _ = get_team_colors(away_t)
                hw = g.get("home_wins"); hl = g.get("home_losses")
                aw = g.get("away_wins"); al = g.get("away_losses")
                home_record = f"{hw}-{hl}" if hw is not None and hl is not None and (hw > 0 or hl > 0) else "N/A"
                away_record = f"{aw}-{al}" if aw is not None and al is not None and (aw > 0 or al > 0) else "N/A"

                home_players = [
                    r.get("player_name", "") for r in analysis_results
                    if r.get("player_team") == home_t and not r.get("player_is_out", False)
                ][:5]
                away_players = [
                    r.get("player_name", "") for r in analysis_results
                    if r.get("player_team") == away_t and not r.get("player_is_out", False)
                ][:5]

                with tc1:
                    st.markdown(
                        get_qds_team_card_html(
                            team_name=home_t,
                            team_abbrev=home_t,
                            record=home_record,
                            stats=[
                                {"label": "Game Total", "value": str(g.get("game_total", "N/A"))},
                                {"label": "Spread",     "value": str(g.get("vegas_spread", "N/A"))},
                            ],
                            key_players=home_players,
                            team_color=home_color,
                        ),
                        unsafe_allow_html=True,
                    )
                with tc2:
                    st.markdown(
                        get_qds_team_card_html(
                            team_name=away_t,
                            team_abbrev=away_t,
                            record=away_record,
                            stats=[
                                {"label": "Game Total", "value": str(g.get("game_total", "N/A"))},
                                {"label": "Spread",     "value": str(g.get("vegas_spread", "N/A"))},
                            ],
                            key_players=away_players,
                            team_color=away_color,
                        ),
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ── Prop Cards (sorted by confidence) ────────────────────────
    for result in displayed_results:
        display_prop_analysis_card_qds(result)
        st.markdown(
            '<div style="height:6px;"></div>',
            unsafe_allow_html=True,
        )

    # ── Final Verdict ─────────────────────────────────────────────
    st.divider()
    with st.expander("🏁 Final Verdict", expanded=True):
        top_picks_for_verdict = [
            r for r in displayed_results
            if not r.get("player_is_out", False)
            and not r.get("should_avoid", False)
        ][:3]

        if top_picks_for_verdict:
            top_names  = ", ".join(r.get("player_name", "") for r in top_picks_for_verdict)
            avg_conf   = round(
                sum(r.get("confidence_score", 0) for r in top_picks_for_verdict)
                / len(top_picks_for_verdict), 1
            )
            summary    = (
                f"The Neural Engine identified {len(top_picks_for_verdict)} high-confidence "
                f"props led by {top_names}, with a composite confidence score of {avg_conf}/100. "
                f"Layer 5 injury validation and Quantum Matrix Engine 5.6 simulation align on these selections."
            )
        else:
            summary = (
                "No high-confidence picks were identified in the current analysis. "
                "Review injury status updates and consider adjusting your prop list."
            )

        recs = [
            "Focus on Platinum and Gold tier picks for maximum confidence.",
            "Avoid props flagged on the avoid list or with active GTD designations.",
            "Use the Entry Strategy Matrix to build 2-, 3-, or 5-leg combos.",
            "Confirm injury status via the 🔄 Data Feed before placing bets.",
        ]
        st.markdown(
            get_qds_final_verdict_html(summary, recs),
            unsafe_allow_html=True,
        )

    # ── Floating selected-picks counter ──────────────────────────
    selected_count = len(st.session_state.get("selected_picks", []))
    if selected_count > 0:
        st.success(
            f"✅ {selected_count} pick(s) selected for Entry Builder → "
            "Go to 🧬 Entry Builder to build your entry!"
        )

    if st.session_state.get("selected_picks"):
        if st.button("🗑️ Clear Selected Picks"):
            st.session_state["selected_picks"] = []
            st.rerun()

elif not run_analysis:
    if current_props:
        st.info("👆 Click **Run Analysis** to analyze all loaded props.")
    else:
        _has_games = bool(st.session_state.get("todays_games"))
        if _has_games:
            st.warning(
                "⚠️ No props loaded yet. "
                "Go to **🔬 Prop Scanner** and click **🤖 Auto-Generate Props for Tonight** "
                "to instantly create props for all active players on tonight's teams — "
                "or click **🔄 Auto-Load Tonight's Games** on the **📡 Live Games** page "
                "to reload games and auto-generate props in one step."
            )
        else:
            st.warning(
                "⚠️ No props loaded and no games found. "
                "Start on the **📡 Live Games** page — click **🔄 Auto-Load Tonight's Games** "
                "to fetch tonight's schedule and auto-generate props for all active players."
            )

# ============================================================
# END SECTION: Display Analysis Results
# ============================================================
