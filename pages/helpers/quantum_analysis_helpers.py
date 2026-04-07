# ============================================================
# FILE: pages/helpers/quantum_analysis_helpers.py
# PURPOSE: Helper functions for the Quantum Analysis Matrix page.
#          Extracted from pages/3_⚡_Quantum_Analysis_Matrix.py to
#          reduce page size and improve maintainability.
# ============================================================
import html as _html

from styles.theme import get_education_box_html


# ── Constants ─────────────────────────────────────────────────────────────────

JOSEPH_DESK_SIZE_CSS = """<style>
.joseph-live-desk{
    padding:10px 12px !important;
    margin:10px 0 !important;
    font-size:0.85rem !important;
    max-height:40vh;
    overflow-y:auto;
}
.joseph-live-desk .joseph-desk-avatar{
    width:40px !important;height:40px !important;
}
.joseph-live-desk h3,.joseph-live-desk h4{
    font-size:0.85rem !important;margin:4px 0 !important;
}
.joseph-live-desk .joseph-desk-title{
    font-size:0.9rem !important;
}
</style>"""

IMPACT_COLORS = {"high": "#ff4444", "medium": "#ffd700", "low": "#8b949e"}

CATEGORY_EMOJI = {
    "injury": "🏥", "trade": "🔄", "performance": "📈",
    "suspension": "🚫", "contract": "💰", "roster": "📋",
}

SIGNAL_COLORS = {"sharp_buy": "#00ff9d", "sharp_fade": "#ff6b6b", "neutral": "#8b949e"}

SIGNAL_LABELS = {
    "sharp_buy": "🟢 SHARP BUY",
    "sharp_fade": "🔴 SHARP FADE",
    "neutral": "⚪ NEUTRAL",
}

PARLAY_STARS = {2: "⭐", 3: "⭐⭐", 4: "⭐⭐⭐", 5: "⭐⭐⭐", 6: "⭐⭐⭐"}

PARLAY_LABELS = {
    2: "Best 2-Leg Parlay",
    3: "Best 3-Leg Parlay",
    4: "Best 4-Leg Parlay",
    5: "Best 5-Leg Parlay",
    6: "Max Entry (6-Leg)",
}


# ── DFS Flex Edge ─────────────────────────────────────────────────────────────

def render_dfs_flex_edge_html(beats_be_count: int, total_dfs: int,
                              avg_dfs_edge: float) -> str:
    """Return the DFS FLEX EDGE inline card HTML."""
    edge_c = "#00ff9d" if avg_dfs_edge > 0 else "#ff5e00"
    return (
        f'<div style="background:linear-gradient(135deg,#0f1424,#14192b);'
        f'border:1px solid rgba(0,255,157,0.2);border-radius:8px;padding:10px 16px;margin:6px 0;">'
        f'<span style="color:#64748b;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;">'
        f'📈 DFS FLEX EDGE</span>'
        f'<span style="color:#475569;font-size:0.68rem;margin-left:8px;">'
        f'{beats_be_count}/{total_dfs} legs beat breakeven</span>'
        f'<span style="color:{edge_c};font-size:0.82rem;font-weight:800;margin-left:12px;'
        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;\">"
        f'Avg Edge: {avg_dfs_edge:+.1f}%</span>'
        f'</div>'
    )


# ── Tier Distribution + Best Pick ─────────────────────────────────────────────

def render_tier_distribution_html(platinum_count: int, gold_count: int,
                                  silver_count: int, bronze_count: int,
                                  avg_edge: float, best_pick: dict | None) -> str:
    """Return the slate-summary tier-distribution dashboard HTML."""
    tier_bar = (
        f'<span style="color:#c800ff;font-weight:700;">💎 {platinum_count} Platinum</span>'
        f' &nbsp;·&nbsp; <span style="color:#ffd700;font-weight:600;">🥇 {gold_count} Gold</span>'
        f' &nbsp;·&nbsp; <span style="color:#b0bec5;">🥈 {silver_count} Silver</span>'
        f' &nbsp;·&nbsp; <span style="color:#b0bec5;">🥉 {bronze_count} Bronze</span>'
    )
    best_html = ""
    if best_pick:
        bp_name = _html.escape(str(best_pick.get("player_name", "")))
        bp_stat = _html.escape(str(best_pick.get("stat_type", "")).title())
        bp_line = best_pick.get("line", 0)
        bp_dir = "More" if best_pick.get("direction") == "OVER" else "Less"
        bp_conf = best_pick.get("confidence_score", 0)
        bp_tier = best_pick.get("tier", "")
        bp_emoji = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}.get(bp_tier, "🏀")
        best_html = (
            f'<div style="margin-top:10px;padding:10px 14px;background:rgba(255,94,0,0.08);'
            f'border-radius:6px;border-left:3px solid #ff5e00;">'
            f'<span style="color:#ff5e00;font-weight:700;font-size:0.85rem;">🏆 Best Pick: </span>'
            f'<span style="color:#e0e7ef;font-weight:600;">{bp_emoji} {bp_name} — {bp_dir} {bp_line} {bp_stat}</span>'
            f'<span style="color:#00f0ff;font-weight:700;margin-left:10px;">{bp_conf:.0f}/100</span>'
            f'</div>'
        )
    return (
        f'<div style="background:linear-gradient(135deg,#0f1424,#14192b);border:1px solid rgba(255,94,0,0.25);'
        f'border-radius:8px;padding:14px 18px;margin:8px 0 14px;">'
        f'<div style="font-size:0.9rem;font-weight:600;color:#e0e7ef;margin-bottom:6px;">'
        f'🗂️ Tier Distribution &nbsp;·&nbsp; '
        f'<span style="color:#00f0ff;">Avg Edge: {avg_edge:.1f}%</span>'
        f'</div>'
        f'<div style="font-size:0.85rem;">{tier_bar}</div>'
        + best_html
        + f'</div>'
    )


# ── Player News Alert Card ───────────────────────────────────────────────────

def render_news_alert_html(news_item: dict) -> str:
    """Return HTML for a single player-news alert card."""
    title = news_item.get("title", "")
    player = news_item.get("player_name", "")
    body = news_item.get("body", "")
    category = news_item.get("category", "")
    impact = news_item.get("impact", "").lower()
    pub = news_item.get("published_at", "")[:10]

    color = IMPACT_COLORS.get(impact, "#555")
    emoji = CATEGORY_EMOJI.get(category, "📰")

    return (
        f'<div style="background:#0d1117;border-left:4px solid {color};'
        f'border-radius:6px;padding:10px 14px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:#e0e7ef;font-weight:700;">{emoji} {_html.escape(title[:80])}</span>'
        f'<span style="background:{color};color:#000;border-radius:4px;'
        f'padding:1px 6px;font-size:0.72rem;font-weight:700;">'
        f'{impact.upper() if impact else "NEWS"}</span>'
        f'</div>'
        f'<div style="color:#8b949e;font-size:0.78rem;margin-top:4px;">'
        f'<strong style="color:#c0d0e8;">{_html.escape(player)}</strong>'
        + (f' · {_html.escape(pub)}' if pub else "")
        + f'</div>'
        + (f'<div style="color:#a0b4d0;font-size:0.82rem;margin-top:6px;">'
           f'{_html.escape(body[:200])}'
           + ("…" if len(body) > 200 else "")
           + f'</div>' if body else "")
        + f'</div>'
    )


# ── Market Movement Alert Card ────────────────────────────────────────────────

def render_market_movement_html(result: dict) -> str:
    """Return HTML for a single market-movement alert card."""
    mm = result.get("market_movement", {})
    player = result.get("player_name", "")
    stat = result.get("stat_type", "")
    direction = mm.get("direction", "")
    shift = mm.get("line_shift", 0)
    signal = mm.get("signal", "neutral")
    adj = mm.get("confidence_adjustment", 0)

    sig_c = SIGNAL_COLORS.get(signal, "#8b949e")
    sig_lbl = SIGNAL_LABELS.get(signal, "⚪ NEUTRAL")

    return (
        f'<div style="background:#0d1117;border-left:4px solid {sig_c};'
        f'border-radius:6px;padding:10px 14px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:#e0e7ef;font-weight:700;">'
        f'{_html.escape(player)} — {_html.escape(stat.title())} {_html.escape(direction)}</span>'
        f'<span style="color:{sig_c};font-weight:700;font-size:0.85rem;">{sig_lbl}</span>'
        f'</div>'
        f'<div style="color:#8b949e;font-size:0.78rem;margin-top:4px;">'
        f'Line shift: <strong style="color:#c0d0e8;">{shift:+.1f}</strong>'
        + (f' · Confidence adj: <strong style="color:{sig_c};">{adj:+.1f}</strong>' if adj else '')
        + f'</div></div>'
    )


# ── Uncertain Pick Warning Header ─────────────────────────────────────────────

def render_uncertain_header_html() -> str:
    """Return the explanatory header + education box for the Uncertain Picks section."""
    header = (
        '<div style="background:rgba(255,193,7,0.10);border:2px solid #ffc107;'
        'border-radius:10px;padding:14px 18px;margin-bottom:14px;">'
        '<strong style="color:#ffc107;font-size:1.0rem;">UNCERTAIN PICKS — Conflicting Signals</strong><br>'
        '<span style="color:#ffe082;font-size:0.85rem;">These picks have hidden structural risks: '
        'conflicting forces, high variance with low edge, fatigue combos, or hot-streak regression. '
        'They are automatically added to your Avoid List.</span>'
        '</div>'
    )
    education = get_education_box_html(
        "What are Uncertain Picks (Risk Flags)?",
        "Uncertain picks have one or more hidden risk signals that make them dangerous despite "
        "appearing to have edge.<br><br>"
        "<strong>There are 4 risk patterns:</strong><br>"
        "1. <strong>Conflicting Forces:</strong> The model's forces are fighting each other — "
        "nearly 50/50 MORE vs LESS. It's a coin flip disguised as an edge.<br>"
        "2. <strong>High Variance:</strong> High-variance stat (3-pointers, steals, blocks) "
        "with a tiny edge (&lt;8%). These stats are too random game-to-game.<br>"
        "3. <strong>Fatigue:</strong> Back-to-back game + big spread (blowout expected). "
        "Player will likely rest in the 4th quarter.<br>"
        "4. <strong>Regression:</strong> The line is set at a hot streak value (125%+ of "
        "season average). The player is due to come back to earth.<br><br>"
        "Uncertain picks are <em>automatically added to your Avoid List</em>.",
    )
    return header + education


# ── Uncertain Pick Card ──────────────────────────────────────────────────────

def _classify_flag_type(flags: list) -> str:
    """Classify the risk type from flag text list."""
    for ft in flags:
        ftl = str(ft).lower()
        if "conflict" in ftl:
            return "Conflicting Forces"
        if "variance" in ftl or "high-variance" in ftl:
            return "High Variance"
        if "fatigue" in ftl or "back-to-back" in ftl:
            return "Fatigue Risk"
        if "regression" in ftl or "hot streak" in ftl or "inflated" in ftl:
            return "Regression Risk"
    return "Uncertain"


def render_uncertain_pick_html(pick: dict, inline_breakdown_html: str = "") -> str:
    """Return HTML for a single uncertain-pick risk-warning card.

    Parameters
    ----------
    pick : dict
        Full analysis result dict for the uncertain pick.
    inline_breakdown_html : str
        Pre-rendered inline breakdown HTML (from ``render_inline_breakdown_html``).
    """
    name = _html.escape(str(pick.get("player_name", "")))
    team = _html.escape(str(pick.get("player_team", pick.get("team", ""))))
    stat = _html.escape(str(pick.get("stat_type", "")).title())
    direction = _html.escape(str(pick.get("direction", "OVER")))
    line = pick.get("line", 0)
    proj = pick.get("adjusted_projection", 0)
    edge = pick.get("edge_percentage", 0)
    flags = pick.get("risk_flags", pick.get("bet_type_reasons", []))

    team_badge = (
        f'<span style="background:rgba(255,193,7,0.15);color:#ffe082;padding:1px 7px;'
        f'border-radius:4px;font-size:0.78rem;font-weight:600;margin-left:7px;'
        f'border:1px solid rgba(255,193,7,0.3);">{team}</span>'
        if team else ""
    )

    flags_html = "".join(
        f'<li style="color:#ffe082;font-size:0.82rem;">{_html.escape(str(r))}</li>'
        for r in flags
    )

    flag_type = _classify_flag_type(flags)

    return (
        f'<div style="background:rgba(255,193,7,0.06);border:1px solid rgba(255,193,7,0.35);'
        f'border-radius:8px;padding:12px 16px;margin-bottom:10px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div>'
        f'<span style="color:#ffc107;font-weight:700;">⚠️ {name}</span>'
        f'{team_badge}'
        f'<span style="background:#ffc107;color:#333;padding:2px 8px;border-radius:4px;'
        f'font-size:0.72rem;font-weight:700;margin-left:8px;">{flag_type}</span>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<span style="color:#ffe082;font-size:0.85rem;">{direction} {line} {stat} '
        f'(Proj: {proj:.1f})</span>'
        f'<br><span style="color:#ffc107;font-size:0.8rem;font-weight:600;">'
        f'Edge: {edge:+.1f}%</span>'
        f'</div>'
        f'</div>'
        f'<div style="margin-top:8px;">'
        f'<span style="color:#ffc107;font-size:0.75rem;font-weight:600;">RISK FLAGS (AVOID):</span>'
        f'<ul style="margin:4px 0 0 16px;padding:0;">{flags_html}</ul>'
        f'</div>'
        + inline_breakdown_html
        + f'</div>'
    )


# ── Gold Tier Banner ──────────────────────────────────────────────────────────

def render_gold_tier_banner_html() -> str:
    """Return the Gold Tier picks banner HTML."""
    return (
        '<div style="background:linear-gradient(135deg,#1a1200,#231800);'
        'border:2px solid #ffd700;border-radius:10px;padding:14px 18px;margin-bottom:4px;">'
        '<h3 style="color:#ffd700;font-family:Orbitron,sans-serif;margin:0 0 4px;">🥇 Gold Tier Picks</h3>'
        '<p style="color:#ffe082;font-size:0.85rem;margin:0;">'
        'High-confidence picks with strong model projections and favorable matchups. '
        'Gold picks are ideal for your core entry legs.'
        '</p>'
        '</div>'
    )


# ── Best Single Bets Header ──────────────────────────────────────────────────

def render_best_single_bets_header_html() -> str:
    """Return the Best Single Bets section header HTML."""
    return (
        '<div style="background:linear-gradient(135deg,#0f1a2e,#14192b);'
        'border:2px solid #00f0ff;border-radius:10px;padding:16px 20px;margin-bottom:20px;">'
        '<h3 style="color:#00f0ff;font-family:Orbitron,sans-serif;margin:0 0 6px;">🏆 Best Single Bets</h3>'
        '<p style="color:#a0b4d0;font-size:0.85rem;margin:0;">Top individual picks ranked by SAFE Score™ — Silver tier and above</p>'
        '</div>'
    )


# ── Strongly Suggested Parlays Header ─────────────────────────────────────────

def render_parlays_header_html() -> str:
    """Return the Strongly Suggested Parlays section header HTML."""
    return (
        '<div style="background:linear-gradient(135deg,#0f1a2e,#14192b);'
        'border:2px solid #ff5e00;border-radius:10px;padding:16px 20px;margin-bottom:20px;">'
        '<h3 style="color:#ff5e00;font-family:Orbitron,sans-serif;margin:0 0 6px;">🎯 Strongly Suggested Parlays</h3>'
        '<p style="color:#a0b4d0;font-size:0.85rem;margin:0;">Optimized multi-leg combos ranked by combined EDGE Score™</p>'
        '</div>'
    )


# ── Parlay Combo Card ────────────────────────────────────────────────────────

def render_parlay_card_html(entry: dict, card_index: int) -> str:
    """Return HTML for a single parlay-combo entry card.

    Parameters
    ----------
    entry : dict
        Parlay entry with keys: num_legs, combo_type, picks, reasons,
        strategy, combined_prob, avg_edge, safe_avg.
    card_index : int
        Zero-based index; top-2 entries get a glow border.
    """
    num = entry.get("num_legs", 0)
    label = PARLAY_LABELS.get(num, entry.get("combo_type", ""))
    star = PARLAY_STARS.get(num, "")
    glow = "box-shadow:0 0 14px rgba(255,94,0,0.45);" if card_index < 2 else ""

    picks_html = ""
    for pick_str in entry.get("picks", []):
        parts = pick_str.split(" ", 1)
        pname = _html.escape(parts[0]) if parts else ""
        rest = _html.escape(parts[1]) if len(parts) > 1 else ""
        picks_html += (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'<span style="color:#ff5e00;font-weight:600;">{pname}</span>'
            f'<span style="color:#c0d0e8;">{rest}</span>'
            f'</div>'
        )

    reasons = entry.get("reasons", [])
    reason_text = (
        _html.escape(" | ".join(reasons))
        if reasons
        else _html.escape(entry.get("strategy", ""))
    )
    combined = entry.get("combined_prob", 0)
    avg_edge = entry.get("avg_edge", 0)
    avg_conf = entry.get("safe_avg", "—")

    return (
        f'<div style="background:#14192b;border-radius:8px;padding:15px 18px;'
        f'margin-bottom:14px;border-left:4px solid #ff5e00;{glow}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
        f'<h4 style="color:#ff5e00;margin:0;font-family:Orbitron,sans-serif;">'
        f'{star} {label}</h4>'
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
        f'</div>'
    )
