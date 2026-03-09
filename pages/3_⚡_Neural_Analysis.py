# ============================================================
# FILE: pages/3_⚡_Neural_Analysis.py
# PURPOSE: The main analysis page. Runs Monte Carlo simulation
#          for each prop and shows probability, edge, tier, and
#          directional forces in the Quantum Design System (QDS) UI.
# CONNECTS TO: engine/ (all modules), data_manager.py, session state
# ============================================================

import streamlit as st  # Main UI framework
import streamlit.components.v1 as _components  # For Full Breakdown iframe rendering
import math             # For rounding in display
import html as _html   # For safe HTML escaping in inline cards
import datetime         # For analysis result freshness timestamps

# Import our engine modules
from engine.simulation import run_monte_carlo_simulation, build_histogram_from_results
from engine.projections import build_player_projection, get_stat_standard_deviation, calculate_teammate_out_boost
from engine.edge_detection import analyze_directional_forces, should_avoid_prop, detect_correlated_props, detect_trap_line, detect_line_sharpness
from engine.confidence import calculate_confidence_score, get_tier_color
from engine.math_helpers import calculate_edge_percentage, clamp_probability
from engine.explainer import generate_pick_explanation
from engine.calibration import get_calibration_adjustment   # C10: historical calibration
from engine.clv_tracker import store_opening_line            # C12: closing line value tracking

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
    GLOSSARY,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Neural Analysis — SmartBetPro NBA",
    page_icon="⚡",
    layout="wide",
)

# Inject global CSS + QDS CSS
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

# ─── Session State Initialization ────────────────────────────
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "injury_status_map" not in st.session_state:
    st.session_state["injury_status_map"] = load_injury_status()

# ─── Auto-refresh injury data if empty or stale (>4 hours) ──
_INJURY_STALE_HOURS = 4
_should_auto_refresh_injuries = not st.session_state["injury_status_map"]
if not _should_auto_refresh_injuries:
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
        from data.web_scraper import fetch_all_injury_data as _fetch_injuries
        _scraped_inj = _fetch_injuries()
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
    """Build entry strategy matrix entries from top results (2–6 legs)."""
    top = [
        r for r in results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and abs(r.get("edge_percentage", 0)) >= 5.0
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

    entries = []
    for num_legs in range(2, 7):
        if len(top) < num_legs:
            continue
        picks = top[:num_legs]
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
            return '<span style="color:#8b949e;font-size:0.85rem;">None detected</span>'
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
        return "".join(parts) if parts else '<span style="color:#8b949e;font-size:0.85rem;">None detected</span>'

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
        '<div style="color:#8b949e;font-size:0.75rem;">10th pct</div>'
        '<div style="color:#ff5e00;font-weight:700;font-size:1rem;">' + f"{p10:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#8b949e;font-size:0.75rem;">Median</div>'
        '<div style="color:#00f0ff;font-weight:700;font-size:1rem;">' + f"{p50:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#8b949e;font-size:0.75rem;">90th pct</div>'
        '<div style="color:#ff5e00;font-weight:700;font-size:1rem;">' + f"{p90:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#8b949e;font-size:0.75rem;">Std Dev</div>'
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
    # Estimate height: collapsed summary bar ~50px + expanded content ~350px
    _components.html(breakdown_html, height=420, scrolling=False)


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
    '<p style="color:#a0b4d0;margin-top:0;">SmartBetPro Neural Engine™ — '
    'Monte Carlo Prop Analysis with Quantum Design System</p>',
    unsafe_allow_html=True,
)

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
        st.info(f"📋 **{len(current_props)} props** loaded and ready for analysis.")
    else:
        st.warning("⚠️ No props loaded. Go to **📥 Import Props** first.")

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
        use_container_width=True,
        disabled=(len(current_props) == 0),
        help="Analyze all loaded props with Monte Carlo simulation",
    )

with filter_col:
    show_all_or_top = st.radio(
        "Show:",
        ["All picks", "Top picks only (edge ≥ threshold)"],
        horizontal=True,
        index=1,
    )

if run_analysis:
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

    total_props_count    = len(props_to_analyze)
    if total_props_count == 0:
        st.warning("⚠️ No props remain after filtering to tonight's teams / injury status. Check your games and props.")
        progress_bar.empty()
        st.stop()

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

        simulation_output = run_monte_carlo_simulation(
            projected_stat_average=projected_stat,
            stat_standard_deviation=stat_std,
            prop_line=prop_line,
            number_of_simulations=simulation_depth,
            blowout_risk_factor=projection_result.get("blowout_risk", 0.15),
            pace_adjustment_factor=projection_result.get("pace_factor", 1.0),
            matchup_adjustment_factor=projection_result.get("defense_factor", 1.0),
            home_away_adjustment=projection_result.get("home_away_factor", 0.0),
            rest_adjustment_factor=projection_result.get("rest_factor", 1.0),
            stat_type=stat_type,
            projected_minutes=projection_result.get("projected_minutes"),
            minutes_std=4.0,
            recent_game_logs=recent_game_log_values if len(recent_game_log_values) >= 15 else None,
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
            "player_is_out":    False,
            "player_status":    player_status,
            "player_status_note": player_status_info.get("injury_note", ""),
        }

        analysis_results_list.append(full_result)

    # Detect correlated props
    correlation_warnings = detect_correlated_props(analysis_results_list)
    for idx, warning in correlation_warnings.items():
        if idx < len(analysis_results_list):
            analysis_results_list[idx]["_correlation_warning"] = warning

    st.session_state["analysis_results"] = analysis_results_list
    st.session_state["analysis_timestamp"] = datetime.datetime.now()
    progress_bar.empty()
    st.success(f"✅ Analysis complete! {len(analysis_results_list)} props analyzed.")

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
        print(f"Auto-log error (non-fatal): {_auto_log_err}")

    st.rerun()

# ============================================================
# END SECTION: Analysis Runner
# ============================================================

# ============================================================
# SECTION: Display Analysis Results
# ============================================================

analysis_results = st.session_state.get("analysis_results", [])

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

    # Sort by confidence score descending
    displayed_results.sort(
        key=lambda r: r.get("confidence_score", 0),
        reverse=True,
    )

    # ── Summary metrics ────────────────────────────────────────
    total_analyzed   = len(analysis_results)
    total_over_picks = sum(1 for r in displayed_results if r.get("direction") == "OVER")
    total_under_picks= sum(1 for r in displayed_results if r.get("direction") == "UNDER")
    platinum_count   = sum(1 for r in displayed_results if r.get("tier") == "Platinum")
    gold_count       = sum(1 for r in displayed_results if r.get("tier") == "Gold")
    avg_edge         = (
        sum(abs(r.get("edge_percentage", 0)) for r in displayed_results) / len(displayed_results)
        if displayed_results else 0
    )
    unmatched_count  = sum(1 for r in analysis_results if not r.get("player_matched", True))

    st.subheader(f"📊 Results: {len(displayed_results)} picks (of {total_analyzed} analyzed)")

    sum_col1, sum_col2, sum_col3, sum_col4, sum_col5 = st.columns(5)
    sum_col1.metric("Showing",     len(displayed_results))
    sum_col2.metric("⬆️ OVER",    total_over_picks)
    sum_col3.metric("⬇️ UNDER",   total_under_picks)
    sum_col4.metric("💎 Platinum", platinum_count)
    sum_col5.metric("🥇 Gold",     gold_count)

    if unmatched_count > 0:
        unmatched_names = [
            r.get("player_name", "") for r in analysis_results
            if not r.get("player_matched", True)
        ]
        st.warning(
            f"⚠️ **{unmatched_count} player(s) not found** in database — "
            + ", ".join(unmatched_names)
            + " — results may be less accurate."
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
        st.markdown("---")

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
                f"Layer 5 injury validation and Monte Carlo simulation align on these selections."
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
        st.warning("⚠️ No props loaded. Go to **📥 Import Props** to add props first.")

# ============================================================
# END SECTION: Display Analysis Results
# ============================================================
