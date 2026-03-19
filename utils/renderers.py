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

    # Bet type + prediction text (Goblin/Demon)
    bet_type = result.get("bet_type", "normal")
    prediction = _escape(result.get("prediction", ""))

    if bet_type == "goblin":
        pred_class = "qcm-prediction-goblin"
        pred_icon = "🟢"
        if not prediction and true_line > 0:
            prediction = _escape(f"I predict the stat will do at LEAST {true_line:g}")
    elif bet_type == "demon":
        pred_class = "qcm-prediction-demon"
        pred_icon = "🔴"
        if not prediction and true_line > 0:
            prediction = _escape(f"I predict the stat will do at MOST {true_line:g}")
    else:
        pred_class = "qcm-prediction-neutral"
        pred_icon = "⚪"

    prediction_html = ""
    if prediction:
        prediction_html = (
            f'<div class="qcm-prediction {pred_class}">'
            f'{pred_icon} {prediction}</div>'
        )

    # Stagger delay: 20ms per card, capped at 2s for 100 cards
    delay_ms = min(index * 20, 2000)

    # Direction label
    direction = result.get("direction", "")
    if not direction:
        direction = "OVER" if prob_over and float(prob_over) >= 0.5 else "UNDER"
    direction_escaped = _escape(direction.upper())

    return f"""<div class="qcm-card" style="animation-delay:{delay_ms}ms;">
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
  </div>
</div>"""


def compile_card_matrix(results, max_cards=50):
    """
    Compile a list of prop-analysis result dicts into a single HTML string
    with CSS Grid layout for high-capacity rendering.

    This function iterates through up to *max_cards* results and wraps
    each in the Quantum Card HTML template. All cards are joined into
    one ``master_html_string`` for injection via a single
    ``st.markdown(html, unsafe_allow_html=True)`` call.

    Args:
        results (list[dict]): Prop analysis results from the engine.
            Each dict should contain keys like ``player_name``,
            ``stat_type``, ``prop_line``, ``tier``, ``confidence_score``,
            ``probability_over``, ``edge_percentage``, ``bet_type``,
            ``prediction``.
        max_cards (int): Maximum number of cards to render. Default 50.
            Prevents WebSocket overload on large datasets.

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

    # Slice to max_cards to prevent WebSocket overload
    display_results = results[:max_cards]

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
