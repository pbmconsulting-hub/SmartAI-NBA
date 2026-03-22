# ============================================================
# FILE: styles/live_theme.py
# PURPOSE: Glassmorphic card and neon progress-bar CSS for the
#          Live Sweat dashboard.
# USAGE:
#   from styles.live_theme import get_live_sweat_css
#   st.markdown(get_live_sweat_css(), unsafe_allow_html=True)
# ============================================================


def get_live_sweat_css() -> str:
    """Return a ``<style>`` block with Live Sweat dashboard classes."""
    return """<style>
/* ── Live Sweat Card ──────────────────────────────────────── */
.sweat-card {
    background: rgba(15, 23, 42, 0.8);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 14px;
    transition: box-shadow 0.3s ease;
}
.sweat-card:hover {
    box-shadow: 0 0 18px rgba(0, 240, 255, 0.15);
}

/* ── Progress bar base track ─────────────────────────────── */
.progress-base {
    background: rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    height: 22px;
    width: 100%;
    overflow: hidden;
    position: relative;
}

/* ── Progress fill variants ──────────────────────────────── */
.progress-fill-blue {
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
    height: 100%;
    border-radius: 8px;
    transition: width 0.6s ease;
}

.progress-fill-orange {
    background: linear-gradient(90deg, #f97316, #fb923c);
    height: 100%;
    border-radius: 8px;
    transition: width 0.6s ease;
}

.progress-fill-red {
    background: linear-gradient(90deg, #ef4444, #f87171);
    height: 100%;
    border-radius: 8px;
    animation: pulse-red 1.2s ease-in-out infinite;
    transition: width 0.6s ease;
}

.progress-fill-green {
    background: linear-gradient(90deg, #22c55e, #4ade80);
    height: 100%;
    border-radius: 8px;
    box-shadow: 0 0 14px rgba(34, 197, 94, 0.6), 0 0 28px rgba(34, 197, 94, 0.3);
    transition: width 0.6s ease;
}

/* ── Progress percentage label ───────────────────────────── */
.progress-pct-label {
    position: absolute;
    right: 8px;
    top: 0;
    height: 22px;
    line-height: 22px;
    font-size: 0.7rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.9);
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
    pointer-events: none;
    z-index: 1;
}

/* ── Animations ──────────────────────────────────────────── */
@keyframes pulse-red {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.65; }
}

/* ── Stat label / value layout ───────────────────────────── */
.sweat-stat-label {
    color: rgba(255, 255, 255, 0.55);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.sweat-stat-value {
    color: #f0f4f8;
    font-size: 1.3rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
}

/* ── Direction badges ────────────────────────────────────── */
.sweat-badge-over {
    display: inline-block;
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}
.sweat-badge-under {
    display: inline-block;
    background: rgba(168, 85, 247, 0.2);
    color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}

/* ── Alert badges ────────────────────────────────────────── */
.sweat-badge-blowout {
    display: inline-block;
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}
.sweat-badge-foul {
    display: inline-block;
    background: rgba(234, 179, 8, 0.2);
    color: #facc15;
    border: 1px solid rgba(234, 179, 8, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}
.sweat-badge-cashed {
    display: inline-block;
    background: rgba(34, 197, 94, 0.2);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
}
.sweat-badge-ot {
    display: inline-block;
    background: rgba(245, 158, 11, 0.2);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}

/* ── Cashed overlay ──────────────────────────────────────── */
.sweat-card-cashed {
    background: rgba(34, 197, 94, 0.12);
    border: 1px solid rgba(34, 197, 94, 0.4);
}

/* ── Awaiting tipoff card ────────────────────────────────── */
.sweat-card-waiting {
    background: rgba(30, 41, 59, 0.6);
    border: 1px dashed rgba(255, 255, 255, 0.12);
    opacity: 0.7;
}
</style>"""


def render_progress_bar(pct: float, color_tier: str) -> str:
    """
    Return an HTML snippet for a neon progress bar with percentage label.

    Parameters
    ----------
    pct : float
        Percentage (0-100+) of target achieved.
    color_tier : str
        One of ``blue``, ``orange``, ``red``, ``green``.
    """
    clamped = max(0, min(pct, 100))
    css_class = f"progress-fill-{color_tier}"
    return (
        f'<div class="progress-base">'
        f'<div class="{css_class}" style="width:{clamped:.1f}%;"></div>'
        f'<span class="progress-pct-label">{pct:.0f}%</span>'
        f'</div>'
    )


def render_sweat_card(
    player_name: str,
    stat_type: str,
    current_stat: float,
    target_stat: float,
    projected_final: float,
    pct_of_target: float,
    color_tier: str,
    blowout_risk: bool = False,
    foul_trouble: bool = False,
    cashed: bool = False,
    minutes_played: float = 0.0,
    direction: str = "OVER",
    minutes_remaining: float = 0.0,
    is_overtime: bool = False,
) -> str:
    """
    Render one glassmorphic sweat card as an HTML string.
    """
    import html as _html

    safe_name = _html.escape(str(player_name))
    safe_stat = _html.escape(str(stat_type).replace("_", " ").title())

    card_class = "sweat-card sweat-card-cashed" if cashed else "sweat-card"

    # Direction badge
    dir_upper = str(direction).upper().strip()
    if dir_upper == "UNDER":
        dir_badge = '<span class="sweat-badge-under">⬇ UNDER</span>'
    else:
        dir_badge = '<span class="sweat-badge-over">⬆ OVER</span>'

    # Alert badges
    badges = ""
    if cashed:
        badges += '<span class="sweat-badge-cashed">✅ CASHED</span>'
    if is_overtime:
        badges += '<span class="sweat-badge-ot">⏱️ OT</span>'
    if blowout_risk:
        badges += '<span class="sweat-badge-blowout">🚨 Blowout Risk</span>'
    if foul_trouble:
        badges += '<span class="sweat-badge-foul">⚠️ Foul Trouble</span>'

    progress_html = render_progress_bar(pct_of_target, color_tier)

    remaining_txt = f" · {minutes_remaining:.0f} MIN left" if minutes_remaining > 0 else ""

    return f"""
    <div class="{card_class}">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div>
                <div style="font-size:1.1rem;font-weight:700;color:#c8d8f0;">{safe_name}</div>
                <div class="sweat-stat-label">{safe_stat} {dir_badge}</div>
            </div>
            <div style="text-align:right;">
                <div class="sweat-stat-value">{current_stat:.1f} / {target_stat:.1f}</div>
                <div class="sweat-stat-label">{minutes_played:.0f} MIN{remaining_txt}</div>
            </div>
        </div>
        {progress_html}
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
            <div class="sweat-stat-label">Projected: <strong style="color:#00f0ff;">{projected_final:.1f}</strong></div>
            <div>{badges}</div>
        </div>
    </div>
    """


def render_waiting_card(player_name: str, stat_type: str,
                        target_stat: float, direction: str = "OVER") -> str:
    """
    Render a dimmed card for a bet whose game hasn't tipped off yet.
    """
    import html as _html

    safe_name = _html.escape(str(player_name))
    safe_stat = _html.escape(str(stat_type).replace("_", " ").title())
    dir_upper = str(direction).upper().strip()
    dir_label = "UNDER" if dir_upper == "UNDER" else "OVER"

    return f"""
    <div class="sweat-card sweat-card-waiting">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <div style="font-size:1.05rem;font-weight:700;color:#8a9bb8;">{safe_name}</div>
                <div class="sweat-stat-label">{safe_stat} · {dir_label} {target_stat:.1f}</div>
            </div>
            <div style="text-align:right;">
                <div class="sweat-stat-label" style="color:#64748b;">🕐 Awaiting Tip-Off</div>
            </div>
        </div>
    </div>
    """
