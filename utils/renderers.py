# ============================================================
# FILE: utils/renderers.py
# PURPOSE: High-capacity HTML Matrix Compiler for the Neural
#          Analysis page. Compiles up to 500 prop-analysis
#          result dicts into a single HTML string with CSS Grid
#          layout for injection via st.markdown().
#
# USAGE:
#   from utils.renderers import compile_card_matrix
#   html = compile_card_matrix(results)
#   st.markdown(html, unsafe_allow_html=True)
#
# DESIGN:
#   - One single HTML string (no per-card st.container calls)
#   - CSS Grid auto-fill layout scales from mobile → ultrawide
#   - Staggered fade-in-up animation for visual waterfall
#   - Prominently displays True More/Less Line
#   - Shows Goblin/Demon prediction text
# ============================================================

import html as _html

from styles.theme import QUANTUM_CARD_MATRIX_CSS


def _escape(value):
    """Safely HTML-escape a value, returning empty string for None."""
    if value is None:
        return ""
    return _html.escape(str(value))


def _build_single_card_html(result, index=0):
    """
    Build a single Quantum Card HTML string from an analysis result dict.

    Renders the **Full Breakdown** view: distribution percentiles, expected
    value, standard deviation, individual directional forces, score
    breakdown bars, and Demon (👹) / Goblin (🟢) tagging.

    Args:
        result (dict): A single prop analysis result from the engine.
        index (int): The card's position index (used for stagger delay).

    Returns:
        str: The HTML string for this single card.
    """
    player_name = _escape(result.get("player_name", "Unknown"))
    stat_type = _escape(result.get("stat_type", ""))
    team = _escape(result.get("player_team", result.get("team", "")))
    platform = _escape(result.get("platform", ""))
    tier = result.get("tier", "Bronze")
    tier_lower = tier.lower() if tier else "bronze"

    # True Line — the verified More/Less line
    prop_line = result.get("prop_line", result.get("line", 0))
    try:
        true_line = float(prop_line)
        true_line_display = f"{true_line:g}"
    except (ValueError, TypeError):
        true_line = 0
        true_line_display = "—"

    # Confidence / probability / edge
    confidence = result.get("confidence_score", 0)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0
    prob_over = result.get("probability_over", 0)
    try:
        prob_pct = f"{float(prob_over) * 100:.1f}%"
    except (ValueError, TypeError):
        prob_pct = "—"
    edge = result.get("edge_percentage", result.get("edge", 0))
    try:
        edge_display = f"{float(edge):+.1f}%"
    except (ValueError, TypeError):
        edge_display = "—"

    # ── Distribution & EV metrics ────────────────────────────────
    p10 = result.get("percentile_10", 0) or 0
    p50 = result.get("percentile_50", 0) or 0
    p90 = result.get("percentile_90", 0) or 0
    std_dev = result.get("simulated_std", result.get("std_dev", 0)) or 0
    adj_proj = result.get("adjusted_projection", 0) or 0
    try:
        p10_d = f"{float(p10):.1f}"
    except (ValueError, TypeError):
        p10_d = "—"
    try:
        p50_d = f"{float(p50):.1f}"
    except (ValueError, TypeError):
        p50_d = "—"
    try:
        p90_d = f"{float(p90):.1f}"
    except (ValueError, TypeError):
        p90_d = "—"
    try:
        std_d = f"{float(std_dev):.1f}"
    except (ValueError, TypeError):
        std_d = "—"
    try:
        proj_d = f"{float(adj_proj):.1f}"
    except (ValueError, TypeError):
        proj_d = "—"

    # Bet type + prediction text (tiered Goblin/Demon removed — all standard)
    bet_type = result.get("bet_type", "standard")
    prediction = _escape(result.get("prediction", ""))

    pred_class = "qcm-prediction-neutral"
    pred_icon = "⚪"

    prediction_html = ""
    if prediction:
        prediction_html = (
            f'<div class="qcm-prediction {pred_class}">'
            f'{pred_icon} {prediction}</div>'
        )

    # Demon-specific card elements removed (tier system removed)
    demon_card_cls = ""
    demon_ceiling_html = ""

    # Stagger delay: 20ms per card, capped at 2s for 100 cards
    delay_ms = min(index * 20, 2000)

    # Direction label
    direction = result.get("direction", "")
    if not direction:
        try:
            direction = "OVER" if prob_over and float(prob_over) >= 0.5 else "UNDER"
        except (ValueError, TypeError):
            direction = "OVER"
    direction_escaped = _escape(direction.upper())

    # ── Forces HTML (individual force lists) ─────────────────────
    forces = result.get("forces", {}) or {}
    over_forces = forces.get("over_forces", []) or []
    under_forces = forces.get("under_forces", []) or []

    def _force_items(force_list):
        if not force_list:
            return '<span class="qcm-force-none">None</span>'
        parts = []
        for f in force_list:
            if not isinstance(f, dict):
                continue
            strength = max(1, min(5, round(float(f.get("strength", 1)))))
            stars = "⭐" * strength
            name = _escape(str(f.get("name", "") or ""))
            parts.append(f'<div class="qcm-force-item">{stars} {name}</div>')
        return "".join(parts) if parts else '<span class="qcm-force-none">None</span>'

    forces_html = (
        '<div class="qcm-forces">'
        '<div class="qcm-forces-col qcm-forces-over">'
        '<div class="qcm-forces-label">▲ OVER</div>'
        f'{_force_items(over_forces)}'
        '</div>'
        '<div class="qcm-forces-col qcm-forces-under">'
        '<div class="qcm-forces-label">▼ UNDER</div>'
        f'{_force_items(under_forces)}'
        '</div>'
        '</div>'
    )

    # ── Score breakdown bars ─────────────────────────────────────
    breakdown = result.get("score_breakdown", {}) or {}
    breakdown_html = ""
    if breakdown:
        bars = []
        for factor, score in breakdown.items():
            try:
                score_f = float(score or 0)
            except (ValueError, TypeError):
                continue
            label = _escape(
                factor.replace("_score", "").replace("_", " ").title()
            )
            bar_w = min(100, max(0, score_f))
            if bar_w >= 70:
                bar_c = "#00f0ff"
            elif bar_w >= 40:
                bar_c = "#ff5e00"
            else:
                bar_c = "#ff4444"
            bars.append(
                f'<div class="qcm-breakdown-row">'
                f'<span class="qcm-breakdown-label">{label}</span>'
                f'<span class="qcm-breakdown-score">{score_f:.0f}</span>'
                f'<div class="qcm-breakdown-track">'
                f'<div class="qcm-breakdown-fill" style="width:{bar_w:.1f}%;background:{bar_c};"></div>'
                f'</div></div>'
            )
        breakdown_html = '<div class="qcm-breakdown">' + "".join(bars) + '</div>'

    # ── Kelly TARGET ALLOCATION metric ──────────────────────────
    wager_html = ""
    try:
        import streamlit as _st_mod
        from engine.odds_engine import calculate_fractional_kelly
        _dir = direction.upper() if direction else "OVER"
        _odds = (result.get("over_odds", -110)
                 if _dir == "OVER"
                 else result.get("under_odds", -110))
        _prob = (float(prob_over)
                 if _dir == "OVER"
                 else (1.0 - float(prob_over)))
        _bk = float(_st_mod.session_state.get("total_bankroll", 1000.0))
        _km = float(_st_mod.session_state.get("kelly_multiplier", 0.25))
        _kr = calculate_fractional_kelly(_prob, _odds, _km)
        _wager = round(_kr["fractional_kelly"] * _bk, 2)
        if _wager > 0:
            wager_html = (
                f'<div class="qcm-metric">'
                f'<div class="qcm-metric-val" style="color:#00C6FF;">${_wager:,.0f}</div>'
                f'<div class="qcm-metric-lbl">Wager</div>'
                f'</div>'
            )
    except Exception:
        pass

    return f"""<div class="qcm-card{demon_card_cls}" style="animation-delay:{delay_ms}ms;">
  <div class="qcm-card-header">
    <span class="qcm-player-name">{player_name}</span>
    <span class="qcm-tier-badge qcm-tier-{tier_lower}">{_escape(tier)}</span>
  </div>
  <div class="qcm-stat-type">
    {_escape(stat_type.replace('_', ' '))}
    <span class="qcm-team">· {team}</span>
    <span class="qcm-platform">· {platform}</span>
  </div>
  <div class="qcm-true-line-row">
    <span class="qcm-true-line-label">True Line ({direction_escaped})</span>
    <span class="qcm-true-line-value">{true_line_display}</span>
  </div>
  {prediction_html}
  {demon_ceiling_html}
  <div class="qcm-metrics">
    <div class="qcm-metric">
      <div class="qcm-metric-val">{prob_pct}</div>
      <div class="qcm-metric-lbl">Prob</div>
    </div>
    <div class="qcm-metric">
      <div class="qcm-metric-val">{confidence:.0f}</div>
      <div class="qcm-metric-lbl">SAFE</div>
    </div>
    <div class="qcm-metric">
      <div class="qcm-metric-val">{edge_display}</div>
      <div class="qcm-metric-lbl">Edge</div>
    </div>
    {wager_html}
  </div>
  <div class="qcm-dist-row">
    <div class="qcm-dist-cell"><div class="qcm-dist-val">{p10_d}</div><div class="qcm-dist-lbl">P10</div></div>
    <div class="qcm-dist-cell qcm-dist-median"><div class="qcm-dist-val">{p50_d}</div><div class="qcm-dist-lbl">MED</div></div>
    <div class="qcm-dist-cell"><div class="qcm-dist-val">{p90_d}</div><div class="qcm-dist-lbl">P90</div></div>
    <div class="qcm-dist-cell"><div class="qcm-dist-val">{std_d}</div><div class="qcm-dist-lbl">σ</div></div>
    <div class="qcm-dist-cell qcm-dist-proj"><div class="qcm-dist-val">{proj_d}</div><div class="qcm-dist-lbl">Proj</div></div>
  </div>
  {forces_html}
  {breakdown_html}
</div>"""


def compile_card_matrix(results, max_cards=None):
    """
    Compile a list of prop-analysis result dicts into a single HTML string
    with CSS Grid layout for high-capacity rendering.

    This function iterates through *all* results (or up to *max_cards* if
    specified) and wraps each in the Quantum Card HTML template. All cards
    are joined into one ``master_html_string`` for injection via a single
    ``st.markdown(html, unsafe_allow_html=True)`` call.

    Args:
        results (list[dict]): Prop analysis results from the engine.
            Each dict should contain keys like ``player_name``,
            ``stat_type``, ``prop_line``, ``tier``, ``confidence_score``,
            ``probability_over``, ``edge_percentage``, ``bet_type``,
            ``prediction``.
        max_cards (int or None): Maximum number of cards to render.
            Default None renders ALL results.

    Returns:
        str: A single HTML string containing all cards wrapped in a CSS
             Grid container, preceded by the Quantum Card Matrix CSS.
    """
    if not results:
        return (
            f"<style>{QUANTUM_CARD_MATRIX_CSS}</style>"
            '<div style="text-align:center;color:#64748b;padding:40px;">'
            "No analysis results to display.</div>"
        )

    # Render all results (or cap at max_cards when explicitly provided)
    display_results = results if max_cards is None else results[:max_cards]

    # Build all card HTML strings
    card_strings = [
        _build_single_card_html(r, idx)
        for idx, r in enumerate(display_results)
    ]

    # Join into a single master HTML string with CSS Grid wrapper
    master_html = (
        f"<style>{QUANTUM_CARD_MATRIX_CSS}</style>"
        f'<div class="qcm-grid">'
        f'{"".join(card_strings)}'
        f"</div>"
    )

    # Add count banner if results were truncated
    total = len(results)
    shown = len(display_results)
    if total > shown:
        master_html += (
            f'<div style="text-align:center;color:#64748b;font-size:0.78rem;'
            f'padding:12px 0;font-family:\'JetBrains Mono\',monospace;">'
            f"Showing top {shown} of {total} props for rendering stability."
            f"</div>"
        )

    return master_html
