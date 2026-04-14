# ============================================================
# FILE: pages/helpers/quantum_analysis_helpers.py
# PURPOSE: Helper functions for the Quantum Analysis Matrix page.
#          Extracted from pages/3_⚡_Quantum_Analysis_Matrix.py to
#          reduce page size and improve maintainability.
# ============================================================
import html as _html
import re as _re

from data.platform_mappings import display_stat_name as _display_stat_name
from styles.theme import get_education_box_html, get_team_colors

# ESPN CDN base for team logos (same as game_report_helpers)
_ESPN_NBA = "https://a.espncdn.com/i/teamlogos/nba/500"
_NBA_LOGO_FALLBACK = "https://cdn.nba.com/logos/leagues/logo-nba.svg"
_SAFE_ABBREV_RE = _re.compile(r"^[A-Za-z0-9]+$")


def _safe_logo_url(team_abbrev: str) -> str:
    """Return an ESPN logo URL only if the abbreviation is safe for a URL."""
    if _SAFE_ABBREV_RE.match(str(team_abbrev)):
        return f"{_ESPN_NBA}/{team_abbrev.lower()}.png"
    return _NBA_LOGO_FALLBACK


# ── Constants ─────────────────────────────────────────────────────────────────

JOSEPH_DESK_SIZE_CSS = """<style>
.joseph-live-desk{
    padding:10px 12px !important;
    margin:10px 0 !important;
    font-size:0.85rem !important;
    overflow-y:visible;
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

# Shared positive/negative accent colors used for edge and direction styling
_POSITIVE_COLOR = "#00ff9d"
_NEGATIVE_COLOR = "#ff6b6b"

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
        f'<div class="qam-dfs-edge">'
        f'<span class="qam-dfs-edge-label">📈 DFS FLEX EDGE</span>'
        f'<span class="qam-dfs-edge-sub">{beats_be_count}/{total_dfs} legs beat breakeven</span>'
        f'<span class="qam-dfs-edge-val" style="color:{edge_c};">'
        f'Avg Edge: {avg_dfs_edge:+.1f}%</span>'
        f'</div>'
    )


# ── Tier Distribution + Best Pick ─────────────────────────────────────────────

def render_tier_distribution_html(platinum_count: int, gold_count: int,
                                  silver_count: int, bronze_count: int,
                                  avg_edge: float, best_pick: dict | None) -> str:
    """Return the slate-summary tier-distribution dashboard HTML."""
    tier_bar = (
        f'<span class="qam-tier-platinum">💎 {platinum_count} Platinum</span>'
        f' &nbsp;·&nbsp; <span class="qam-tier-gold">🥇 {gold_count} Gold</span>'
        f' &nbsp;·&nbsp; <span class="qam-tier-silver">🥈 {silver_count} Silver</span>'
        f' &nbsp;·&nbsp; <span class="qam-tier-bronze">🥉 {bronze_count} Bronze</span>'
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
            f'<div class="qam-best-pick">'
            f'<span class="qam-best-pick-label">🏆 Best Pick: </span>'
            f'<span class="qam-best-pick-detail">{bp_emoji} {bp_name} — {bp_dir} {bp_line} {bp_stat}</span>'
            f'<span class="qam-best-pick-conf">{bp_conf:.0f}/100</span>'
            f'</div>'
        )
    return (
        f'<div class="qam-tier-dist">'
        f'<div class="qam-tier-dist-header">'
        f'🗂️ Tier Distribution &nbsp;·&nbsp; '
        f'<span class="qam-avg-edge">Avg Edge: {avg_edge:.1f}%</span>'
        f'</div>'
        f'<div class="qam-tier-dist-bar">{tier_bar}</div>'
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
        f'<div class="qam-news-alert" style="border-left:4px solid {color};">'
        f'<div class="qam-news-alert-header">'
        f'<span class="qam-news-alert-title">{emoji} {_html.escape(title[:80])}</span>'
        f'<span class="qam-news-alert-badge" style="background:{color};">'
        f'{impact.upper() if impact else "NEWS"}</span>'
        f'</div>'
        f'<div class="qam-news-alert-meta">'
        f'<strong class="qam-news-alert-player">{_html.escape(player)}</strong>'
        + (f' · {_html.escape(pub)}' if pub else "")
        + f'</div>'
        + (f'<div class="qam-news-alert-body">'
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
        f'<div class="qam-market-move" style="border-left:4px solid {sig_c};">'
        f'<div class="qam-market-move-header">'
        f'<span class="qam-market-move-player">'
        f'{_html.escape(player)} — {_html.escape(stat.title())} {_html.escape(direction)}</span>'
        f'<span class="qam-market-move-signal" style="color:{sig_c};">{sig_lbl}</span>'
        f'</div>'
        f'<div class="qam-market-move-detail">'
        f'Line shift: <strong class="qam-detail-value">{shift:+.1f}</strong>'
        + (f' · Confidence adj: <strong style="color:{sig_c};">{adj:+.1f}</strong>' if adj else '')
        + f'</div></div>'
    )


# ── Uncertain Pick Warning Header ─────────────────────────────────────────────

def render_uncertain_header_html() -> str:
    """Return the explanatory header + education box for the Uncertain Picks section."""
    header = (
        '<div class="qam-uncertain-header">'
        '<strong class="qam-uncertain-header-title">UNCERTAIN PICKS — Conflicting Signals</strong><br>'
        '<span class="qam-uncertain-header-desc">These picks have hidden structural risks: '
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
        f'<span class="qam-uncertain-team-badge">{team}</span>'
        if team else ""
    )

    flags_html = "".join(
        f'<li>{_html.escape(str(r))}</li>'
        for r in flags
    )

    flag_type = _classify_flag_type(flags)

    return (
        f'<div class="qam-uncertain-card">'
        f'<div class="qam-uncertain-card-header">'
        f'<div>'
        f'<span class="qam-uncertain-name">⚠️ {name}</span>'
        f'{team_badge}'
        f'<span class="qam-uncertain-flag-type">{flag_type}</span>'
        f'</div>'
        f'<div class="qam-uncertain-card-right">'
        f'<span class="qam-uncertain-prop">{direction} {line} {stat} '
        f'(Proj: {proj:.1f})</span>'
        f'<br><span class="qam-uncertain-edge">'
        f'Edge: {edge:+.1f}%</span>'
        f'</div>'
        f'</div>'
        f'<div class="qam-uncertain-flags">'
        f'<span class="qam-uncertain-flags-label">RISK FLAGS (AVOID):</span>'
        f'<ul>{flags_html}</ul>'
        f'</div>'
        + inline_breakdown_html
        + f'</div>'
    )


# ── Quantum Edge Gap Banner ──────────────────────────────────────────────────

_QEG_LINE_DEVIATION_THRESHOLD = 20.0  # Minimum |line_vs_avg_pct| to qualify

QEG_EDGE_THRESHOLD = _QEG_LINE_DEVIATION_THRESHOLD  # Public alias for page import


def render_quantum_edge_gap_banner_html(
    picks: list,
) -> str:
    """Return the Quantum Edge Gap section banner HTML with summary stats.

    Parameters
    ----------
    picks:
        List of result dicts that qualified for the edge gap (either
        line_vs_avg_pct deviation or edge_percentage ≥ threshold).
    """
    total = len(picks)
    over_ct = sum(1 for p in picks if p.get("direction", "").upper() == "OVER")
    under_ct = total - over_ct
    avg_dev = (
        sum(abs(p.get("line_vs_avg_pct", 0)) for p in picks) / total
        if total
        else 0
    )
    max_dev = (
        max(abs(p.get("line_vs_avg_pct", 0)) for p in picks)
        if total
        else 0
    )
    avg_edge = (
        sum(abs(p.get("edge_percentage", 0)) for p in picks) / total
        if total
        else 0
    )

    _thr = int(_QEG_LINE_DEVIATION_THRESHOLD)

    return (
        '<div class="qam-edge-gap-banner">'
        '<div class="qam-edge-gap-banner-inner">'
        # ── Header row: icon + title ──
        '<div class="qam-edge-gap-banner-header">'
        '<div class="qam-edge-gap-banner-icon">⚡</div>'
        '<h3>Quantum Edge Gap'
        f'<span>±{_thr}%&thinsp;&amp;&thinsp;BEYOND</span></h3>'
        '</div>'
        '<p>'
        f'Standard-line picks where the line deviates ≥&thinsp;{_thr}% from the '
        f'season average (OVER: line {_thr}–100% below avg, '
        f'UNDER: line {_thr}–100% above avg) or the model edge '
        f'is ≥&thinsp;{_thr}%.'
        '</p>'
        '<div class="qeg-stats-row">'
        f'<div class="qeg-stat-pill"><span class="qeg-stat-val">{total}</span>'
        f'<span class="qeg-stat-lbl">Picks</span></div>'
        f'<div class="qeg-stat-pill"><span class="qeg-stat-val">{over_ct}</span>'
        f'<span class="qeg-stat-lbl">Over</span></div>'
        f'<div class="qeg-stat-pill"><span class="qeg-stat-val">{under_ct}</span>'
        f'<span class="qeg-stat-lbl">Under</span></div>'
        f'<div class="qeg-stat-pill"><span class="qeg-stat-val">{avg_dev:.1f}%</span>'
        f'<span class="qeg-stat-lbl">Avg Dev</span></div>'
        f'<div class="qeg-stat-pill"><span class="qeg-stat-val">{max_dev:.1f}%</span>'
        f'<span class="qeg-stat-lbl">Max Dev</span></div>'
        f'<div class="qeg-stat-pill"><span class="qeg-stat-val">{avg_edge:.1f}%</span>'
        f'<span class="qeg-stat-lbl">Avg Edge</span></div>'
        '</div>'
        '</div>'
        '</div>'
    )


_NBA_HEADSHOT_CDN = "https://cdn.nba.com/headshots/nba/latest/260x190"

# SVG circumference for the edge gauge (r=25, C=2*pi*25 ≈ 157)
_GAUGE_CIRCUMFERENCE = 157


_STAT_AVG_KEYS = {
    # Core stats
    "points": "season_pts_avg",
    "rebounds": "season_reb_avg",
    "assists": "season_ast_avg",
    "threes": "season_threes_avg",
    "steals": "season_stl_avg",
    "blocks": "season_blk_avg",
    "turnovers": "season_tov_avg",
    "minutes": "season_minutes_avg",
    # Shooting stats
    "ftm": "season_ftm_avg",
    "fga": "season_fga_avg",
    "fgm": "season_fgm_avg",
    "fta": "season_fta_avg",
    # Rebound splits
    "offensive_rebounds": "season_oreb_avg",
    "defensive_rebounds": "season_dreb_avg",
    # Other
    "personal_fouls": "season_pf_avg",
    # Combo stats (summed from components)
    "points_rebounds": "season_pts_reb_avg",
    "points_assists": "season_pts_ast_avg",
    "rebounds_assists": "season_reb_ast_avg",
    "points_rebounds_assists": "season_pra_avg",
    "blocks_steals": "season_blk_stl_avg",
}


def _edge_gauge_svg(edge_pct: float, display: str) -> str:
    """Return an inline SVG circular gauge for the edge percentage.

    The ring fills proportionally: 0% = empty, ≥50% = full.
    """
    clamped = max(0.0, min(50.0, abs(edge_pct)))
    fill_frac = clamped / 50.0
    offset = _GAUGE_CIRCUMFERENCE * (1 - fill_frac)
    return (
        f'<svg class="qeg-edge-gauge" viewBox="0 0 64 64">'
        f'<circle class="qeg-gauge-bg" cx="32" cy="32" r="25"/>'
        f'<circle class="qeg-gauge-ring" cx="32" cy="32" r="25" '
        f'stroke-dasharray="{_GAUGE_CIRCUMFERENCE}" '
        f'stroke-dashoffset="{offset:.1f}"/>'
        f'<text class="qeg-gauge-text" x="32" y="32">{_html.escape(display)}</text>'
        f'</svg>'
    )


def render_quantum_edge_gap_card_html(result: dict, rank: int = 0) -> str:
    """Return HTML for a single Quantum Edge Gap pick card.

    Parameters
    ----------
    result:
        A single prop analysis result dict from the engine.
    rank:
        1-based position of this pick in the edge gap list (0 = no rank shown).
    """
    player_name = _html.escape(str(result.get("player_name", "Unknown")))
    stat_type = _html.escape(str(result.get("stat_type", "")))
    team = _html.escape(
        str(result.get("player_team", result.get("team", "")))
    )
    platform = _html.escape(str(result.get("platform", "")))
    tier = _html.escape(str(result.get("tier", "Bronze")))

    # Prop line
    prop_line = result.get("prop_line", result.get("line", 0))
    try:
        line_val = float(prop_line)
        line_display = f"{line_val:g}"
    except (ValueError, TypeError):
        line_val = 0
        line_display = "—"

    # Confidence
    confidence = result.get("confidence_score", 0)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0
    conf_pct = max(0, min(100, confidence))

    # Probability
    prob_over = result.get("probability_over", 0)
    try:
        prob_pct = f"{float(prob_over) * 100:.1f}%"
    except (ValueError, TypeError):
        prob_pct = "—"

    # Edge
    edge = result.get("edge_percentage", result.get("edge", 0))
    try:
        edge_val = float(edge)
        edge_display = f"{edge_val:+.1f}%"
    except (ValueError, TypeError):
        edge_val = 0
        edge_display = "—"

    # Direction
    direction = str(result.get("direction", "")).upper()
    dir_label = "OVER" if direction == "OVER" else "UNDER"
    dir_css = "qeg-dir-over" if direction == "OVER" else "qeg-dir-under"
    card_dir_css = "qeg-card-over" if direction == "OVER" else "qeg-card-under"
    dir_arrow = "▲" if direction == "OVER" else "▼"

    # Projection
    projection = result.get("adjusted_projection", 0)
    try:
        proj_val = float(projection)
        proj_display = f"{proj_val:.1f}"
    except (ValueError, TypeError):
        proj_val = 0
        proj_display = "—"

    # Percentiles
    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)
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

    # Season average for this stat type (for comparison)
    stat_key_lower = stat_type.lower().replace(" ", "_")
    season_avg_key = _STAT_AVG_KEYS.get(stat_key_lower, "")
    season_avg = result.get(season_avg_key, 0) if season_avg_key else 0
    try:
        season_avg = float(season_avg)
    except (ValueError, TypeError):
        season_avg = 0
    avg_display = f"{season_avg:.1f}" if season_avg > 0 else ""

    # Headshot
    player_id = result.get("player_id", "")
    headshot_url = (
        f"{_NBA_HEADSHOT_CDN}/{player_id}.png"
        if player_id
        else ""
    )
    headshot_html = (
        f'<img class="qeg-headshot" src="{_html.escape(headshot_url)}" '
        f'alt="{player_name}" loading="lazy">'
        if headshot_url
        else ""
    )

    # Stat type display label
    stat_display = _display_stat_name(stat_type)

    # Tier emoji
    tier_emoji_map = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
    tier_emoji = tier_emoji_map.get(tier, "🥉")

    # Rank badge
    rank_html = (
        f'<div class="qeg-rank">#{rank}</div>'
        if rank > 0
        else ""
    )

    # Season avg sub-text
    avg_sub_html = (
        f'<div class="qeg-stat-block-sub">Avg: {avg_display}</div>'
        if avg_display
        else ""
    )

    # Stagger animation delay
    delay_style = f' style="animation-delay:{(rank - 1) * 0.08:.2f}s;"' if rank > 0 else ""

    # Edge gauge SVG
    gauge_svg = _edge_gauge_svg(edge_val, edge_display)

    # Prop call line (e.g. "▲ OVER 25.5 Points")
    prop_call = f"{dir_arrow} {dir_label} {line_display} {stat_display}"

    # Edge heat bar width: maps [10%, 50%] → [0%, 100%] so picks at the
    # 15% threshold already show visible fill (≈12%).
    abs_edge = abs(edge_val)
    heat_width = max(0, min(100, (abs_edge - 10) / 40 * 100))
    heat_pct_display = f"{abs_edge:.1f}%"

    # Force direction bar: probability split between over/under
    try:
        prob_val = float(prob_over)
    except (ValueError, TypeError):
        prob_val = 0.5
    over_pct = max(0, min(100, prob_val * 100))
    under_pct = 100 - over_pct

    return (
        f'<div class="qeg-card {card_dir_css}"{delay_style}>'
        f'<div class="qeg-card-top">'
        f'{rank_html}'
        # Identity
        f'<div class="qeg-card-identity">'
        f'{headshot_html}'
        f'<div class="qeg-player-info">'
        f'<span class="qeg-player-name">{player_name}</span>'
        f'<span class="qeg-player-meta">{team} · {platform}</span>'
        f'</div>'
        f'</div>'
        # Compact metrics row
        f'<div class="qeg-card-center">'
        f'<span class="qeg-player-prop">{prop_call}</span>'
        f'<div class="qeg-card-metrics">'
        f'<div class="qeg-metric">'
        f'<span class="qeg-direction-badge {dir_css}">{dir_arrow} {dir_label}</span>'
        f'</div>'
        f'<div class="qeg-metric">'
        f'<div class="qeg-metric-val">{proj_display}</div>'
        f'<div class="qeg-metric-lbl">Proj</div>'
        f'</div>'
        f'<div class="qeg-metric">'
        f'<div class="qeg-metric-val">{confidence:.0f}</div>'
        f'<div class="qeg-metric-lbl">SAFE</div>'
        f'</div>'
        f'<div class="qeg-metric">'
        f'<div class="qeg-metric-val">{tier_emoji} {tier}</div>'
        f'<div class="qeg-metric-lbl">Tier</div>'
        f'</div>'
        f'</div>'
        f'</div>'
        # Edge gauge callout
        f'<div class="qeg-edge-highlight">'
        f'{gauge_svg}'
        f'<span class="qeg-edge-highlight-lbl">Edge</span>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


# ── Quantum Edge Gap Filtering, Deduplication & Grouping ─────────────────────


def filter_qeg_picks(
    results: list,
    edge_threshold: float | None = None,
) -> list:
    """Return QEG-qualified picks from *results*.

    Filtering rules:

    1. **Standard lines only** – ``odds_type`` must be ``"standard"`` (or
       absent, which defaults to ``"standard"``).
    2. **Exclude goblins / demons** – any pick whose ``odds_type`` is
       ``"goblin"`` or ``"demon"`` is dropped.
    3. **Qualification** – a pick qualifies if it meets **either** criterion:

       a. **Line deviation** – ``line_vs_avg_pct`` deviates ≥ *threshold* %
          from the season average in the qualifying direction:
          • **OVER**: ``line_vs_avg_pct <= -threshold`` (line 20–100 % below avg).
          • **UNDER**: ``line_vs_avg_pct >= +threshold`` (line 20–100 % above avg).

       b. **Edge percentage** – ``|edge_percentage| >= threshold``.

    4. **No other hiding** – ``should_avoid`` and ``player_is_out`` are
       intentionally *not* checked so extreme-deviation picks are surfaced.

    Parameters
    ----------
    results:
        Full list of analysis result dicts (e.g. ``displayed_results``).
    edge_threshold:
        Minimum threshold %. Defaults to the module-level
        ``_QEG_LINE_DEVIATION_THRESHOLD`` (20.0).
    """
    thr = edge_threshold if edge_threshold is not None else _QEG_LINE_DEVIATION_THRESHOLD
    filtered: list = []
    for r in results:
        odds_type = str(r.get("odds_type", "standard")).strip().lower()
        if odds_type != "standard":
            continue

        line_dev = float(r.get("line_vs_avg_pct", 0))
        direction = str(r.get("direction", "")).upper()
        edge_pct = abs(float(r.get("edge_percentage", 0)))

        # Criterion A: line deviation in the qualifying direction
        line_qualifies = (
            (direction == "OVER" and line_dev <= -thr)
            or (direction == "UNDER" and line_dev >= thr)
        )
        # Criterion B: edge percentage magnitude
        edge_qualifies = edge_pct >= thr

        if line_qualifies or edge_qualifies:
            filtered.append(r)
    return filtered


def deduplicate_qeg_picks(picks: list) -> list:
    """Remove duplicate QEG picks keeping the one with the highest |edge|.

    Duplicates are identified by ``(player_name, stat_type, line)`` tuple.
    """
    seen: dict[tuple, dict] = {}
    for p in picks:
        key = (
            str(p.get("player_name", "")).strip().lower(),
            str(p.get("stat_type", "")).strip().lower(),
            p.get("line", p.get("prop_line", 0)),
        )
        existing = seen.get(key)
        if existing is None or abs(p.get("edge_percentage", 0)) > abs(existing.get("edge_percentage", 0)):
            seen[key] = p
    return list(seen.values())


def render_quantum_edge_gap_grouped_html(picks: list) -> str:
    """Return collapsible HTML grouping QEG picks by player.

    Players with a single prop render as a flat card.
    Players with multiple props are wrapped in a ``<details>`` element
    so the user can expand/collapse their bets, saving vertical space.
    """
    from collections import OrderedDict

    groups: OrderedDict[str, list] = OrderedDict()
    for p in picks:
        name = p.get("player_name", "Unknown")
        groups.setdefault(name, []).append(p)

    parts: list[str] = []
    global_rank = 0
    for player_name, player_picks in groups.items():
        if len(player_picks) == 1:
            global_rank += 1
            parts.append(render_quantum_edge_gap_card_html(player_picks[0], rank=global_rank))
        else:
            # Collapsible group
            best_edge = max(abs(p.get("edge_percentage", 0)) for p in player_picks)
            team = _html.escape(str(player_picks[0].get("player_team", player_picks[0].get("team", ""))))
            player_id = player_picks[0].get("player_id", "")
            headshot_url = (
                f"{_NBA_HEADSHOT_CDN}/{player_id}.png" if player_id else ""
            )
            headshot_img = (
                f'<img class="qeg-headshot" src="{_html.escape(headshot_url)}" '
                f'alt="{_html.escape(player_name)}" loading="lazy">'
                if headshot_url else ""
            )
            summary_line = (
                f'{headshot_img}'
                f'<span class="qeg-group-name">{_html.escape(player_name)}</span>'
                f'<span class="qeg-group-meta">{team} · '
                f'{len(player_picks)} props · '
                f'Best edge {best_edge:.1f}%</span>'
            )
            inner_cards = []
            for pp in player_picks:
                global_rank += 1
                inner_cards.append(render_quantum_edge_gap_card_html(pp, rank=global_rank))
            parts.append(
                f'<details class="qeg-group">'
                f'<summary class="qeg-group-summary">{summary_line}</summary>'
                f'<div class="qeg-group-body">{"".join(inner_cards)}</div>'
                f'</details>'
            )
    return "".join(parts)


# ── Gold Tier Banner ──────────────────────────────────────────────────────────

def render_gold_tier_banner_html() -> str:
    """Return the Gold Tier picks banner HTML."""
    return (
        '<div class="qam-gold-banner">'
        '<h3>🥇 Gold Tier Picks</h3>'
        '<p>'
        'High-confidence picks with strong model projections and favorable matchups. '
        'Gold picks are ideal for your core entry legs.'
        '</p>'
        '</div>'
    )


# ── Best Single Bets Header ──────────────────────────────────────────────────

def render_best_single_bets_header_html() -> str:
    """Return the Best Single Bets section header HTML."""
    return (
        '<div class="qam-section-header qam-section-header-single">'
        '<h3>🏆 Best Single Bets</h3>'
        '<p>Top individual picks ranked by SAFE Score™ — Silver tier and above</p>'
        '</div>'
    )


# ── Strongly Suggested Parlays Header ─────────────────────────────────────────

def render_parlays_header_html() -> str:
    """Return the Strongly Suggested Parlays section header HTML."""
    return (
        '<div class="qam-section-header qam-section-header-parlay">'
        '<h3>🎯 Strongly Suggested Parlays</h3>'
        '<p>Optimized multi-leg combos ranked by combined EDGE Score™ — '
        'grouped by game for easy entry</p>'
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
        Optionally ``raw_picks`` with full result dicts and ``game_groups``
        mapping ``matchup_label → [pick_strings]``.
    card_index : int
        Zero-based index; top-2 entries get a glow border.
    """
    num = entry.get("num_legs", 0)
    label = PARLAY_LABELS.get(num, entry.get("combo_type", ""))
    star = PARLAY_STARS.get(num, "")
    glow_cls = " qam-parlay-card-glow" if card_index < 2 else ""

    # ── Build picks, grouped by game when available ──────────
    game_groups = entry.get("game_groups", {})
    raw_picks = entry.get("raw_picks", [])

    picks_html = ""
    if game_groups:
        for matchup, group_data in game_groups.items():
            # group_data is either a dict with "picks"/"meta" (new)
            # or a plain list of pick dicts (legacy fallback)
            if isinstance(group_data, dict):
                legs = group_data.get("picks", [])
                meta = group_data.get("meta", {})
            else:
                legs = group_data
                meta = {}

            game_label_html = _render_game_group_label(str(matchup), meta)
            picks_html += (
                f'<div class="qam-parlay-game-group">'
                f'{game_label_html}'
            )
            for leg in legs:
                picks_html += _render_single_leg_html(leg, raw_picks)
            picks_html += '</div>'
    else:
        # Fallback: flat pick list (legacy format)
        for pick_str in entry.get("picks", []):
            picks_html += _render_leg_from_string(pick_str, raw_picks)

    # ── Reason tags ──────────────────────────────────────────
    reasons = entry.get("reasons", [])
    reason_html = ""
    if reasons:
        tags = "".join(
            f'<span class="qam-parlay-reason-tag">{_html.escape(r)}</span>'
            for r in reasons
        )
        reason_html = f'<div class="qam-parlay-reason">{tags}</div>'
    elif entry.get("strategy"):
        tag = f'<span class="qam-parlay-reason-tag">{_html.escape(entry["strategy"])}</span>'
        reason_html = f'<div class="qam-parlay-reason">{tag}</div>'

    # ── Stats footer ─────────────────────────────────────────
    combined = entry.get("combined_prob", 0)
    avg_edge = entry.get("avg_edge", 0)
    avg_conf = entry.get("safe_avg", "—")

    edge_color = _POSITIVE_COLOR if avg_edge > 0 else _NEGATIVE_COLOR

    return (
        f'<div class="qam-parlay-card{glow_cls}">'
        f'<div class="qam-parlay-header">'
        f'<h4>{star} {label}</h4>'
        f'<span class="qam-parlay-safe-badge">SAFE {avg_conf}/100</span>'
        f'</div>'
        f'{picks_html}'
        f'{reason_html}'
        f'<div class="qam-parlay-stats">'
        f'<div class="qam-parlay-stat-item">'
        f'<span class="qam-parlay-stat-val">{combined:.1f}%</span>'
        f'<span class="qam-parlay-stat-label">Combined Prob</span>'
        f'</div>'
        f'<div class="qam-parlay-stat-item">'
        f'<span class="qam-parlay-stat-val" style="color:{edge_color};">{avg_edge:+.1f}%</span>'
        f'<span class="qam-parlay-stat-label">Avg Edge</span>'
        f'</div>'
        f'<div class="qam-parlay-stat-item">'
        f'<span class="qam-parlay-stat-val">{num}</span>'
        f'<span class="qam-parlay-stat-label">Legs</span>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _render_game_group_label(matchup: str, meta: dict) -> str:
    """Render the game group header with team logos, abbreviations, and W-L records.

    Parameters
    ----------
    matchup : str
        Matchup label like ``'BOS @ LAL'``.
    meta : dict
        Game metadata with keys: ``home_team``, ``away_team``,
        ``home_record``, ``away_record``, ``home_conf_rank``,
        ``away_conf_rank``.  May be empty for fallback labels.
    """
    away_team = meta.get("away_team", "")
    home_team = meta.get("home_team", "")

    # If we have structured meta, render the rich label with logos
    if away_team and home_team:
        away_color, _ = get_team_colors(away_team)
        home_color, _ = get_team_colors(home_team)
        away_logo = _safe_logo_url(away_team)
        home_logo = _safe_logo_url(home_team)
        away_rec = _html.escape(meta.get("away_record", ""))
        home_rec = _html.escape(meta.get("home_record", ""))
        safe_away = _html.escape(away_team)
        safe_home = _html.escape(home_team)

        away_rec_html = f' <span class="qam-parlay-team-record">({away_rec})</span>' if away_rec else ""
        home_rec_html = f' <span class="qam-parlay-team-record">({home_rec})</span>' if home_rec else ""

        return (
            f'<div class="qam-parlay-game-label">'
            # Away team
            f'<div class="qam-parlay-game-team">'
            f'<img class="qam-parlay-team-logo" '
            f'src="{away_logo}" alt="{safe_away}" '
            f'onerror="this.onerror=null;this.src=\'{_NBA_LOGO_FALLBACK}\'">'
            f'<span class="qam-parlay-team-abbrev" style="color:{away_color};">{safe_away}</span>'
            f'{away_rec_html}'
            f'</div>'
            # VS divider
            f'<span class="qam-parlay-game-vs">@</span>'
            # Home team
            f'<div class="qam-parlay-game-team">'
            f'<img class="qam-parlay-team-logo" '
            f'src="{home_logo}" alt="{safe_home}" '
            f'onerror="this.onerror=null;this.src=\'{_NBA_LOGO_FALLBACK}\'">'
            f'<span class="qam-parlay-team-abbrev" style="color:{home_color};">{safe_home}</span>'
            f'{home_rec_html}'
            f'</div>'
            f'</div>'
        )

    # Fallback: plain text label (no game context available)
    safe_matchup = _html.escape(matchup)
    return (
        f'<div class="qam-parlay-game-label">'
        f'<span class="qam-parlay-team-abbrev" style="color:#00C6FF;">🏀 {safe_matchup}</span>'
        f'</div>'
    )


def _render_single_leg_html(leg_info: dict, raw_picks: list) -> str:
    """Render one pick leg with direction badge and edge info.

    Parameters
    ----------
    leg_info : dict
        Must have ``player_name``, ``direction``, ``line``, ``stat_type``.
        May also have ``edge_percentage`` and ``tier``.
    raw_picks : list
        Full raw pick dicts (used as fallback for edge/tier lookup).
    """
    pname = _html.escape(str(leg_info.get("player_name", "")))
    direction = (leg_info.get("direction", "") or "").upper()
    line = leg_info.get("line", "")
    stat = _html.escape(str(leg_info.get("stat_type", "")).replace("_", " ").title())
    edge = leg_info.get("edge_percentage", 0) or 0
    tier = (leg_info.get("tier", "") or "").lower()

    dir_cls = "qam-parlay-pick-dir-over" if direction == "OVER" else "qam-parlay-pick-dir-under"
    dir_label = _html.escape(direction) if direction else ""

    tier_html = ""
    if tier in ("platinum", "gold", "silver"):
        tier_html = f'<span class="qam-parlay-pick-tier qam-parlay-pick-tier-{tier}">{tier.title()}</span>'

    edge_color = _POSITIVE_COLOR if edge > 0 else _NEGATIVE_COLOR

    return (
        f'<div class="qam-parlay-pick">'
        f'<span class="qam-parlay-pick-name">{pname}</span>'
        f'<span class="qam-parlay-pick-dir {dir_cls}">{dir_label}</span>'
        f'<span class="qam-parlay-pick-detail">{line} {stat}</span>'
        f'{tier_html}'
        f'<span class="qam-parlay-pick-edge" style="color:{edge_color};">{edge:+.1f}%</span>'
        f'</div>'
    )


def _render_leg_from_string(pick_str: str, raw_picks: list) -> str:
    """Render a legacy pick string as a styled leg row.

    Falls back to matching the player name against raw_picks for edge/tier.
    """
    parts = pick_str.split(" ", 1)
    pname = _html.escape(parts[0]) if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    # Try to find matching raw pick for edge/tier
    edge = 0.0
    tier = ""
    direction = ""
    for rp in raw_picks:
        if rp.get("player_name", "") == (parts[0] if parts else ""):
            edge = rp.get("edge_percentage", 0) or 0
            tier = (rp.get("tier", "") or "").lower()
            direction = (rp.get("direction", "") or "").upper()
            break

    # Parse direction from rest string if not found
    if not direction:
        rest_upper = rest.upper()
        if rest_upper.startswith("OVER"):
            direction = "OVER"
        elif rest_upper.startswith("UNDER"):
            direction = "UNDER"

    dir_cls = "qam-parlay-pick-dir-over" if direction == "OVER" else "qam-parlay-pick-dir-under"
    dir_label = _html.escape(direction)

    # Remove direction from rest to avoid duplication
    rest_cleaned = rest
    if direction and rest.upper().startswith(direction):
        rest_cleaned = rest[len(direction):].strip()

    tier_html = ""
    if tier in ("platinum", "gold", "silver"):
        tier_html = f'<span class="qam-parlay-pick-tier qam-parlay-pick-tier-{tier}">{tier.title()}</span>'

    edge_color = _POSITIVE_COLOR if edge > 0 else _NEGATIVE_COLOR

    return (
        f'<div class="qam-parlay-pick">'
        f'<span class="qam-parlay-pick-name">{pname}</span>'
        f'<span class="qam-parlay-pick-dir {dir_cls}">{dir_label}</span>'
        f'<span class="qam-parlay-pick-detail">{_html.escape(rest_cleaned)}</span>'
        f'{tier_html}'
        f'<span class="qam-parlay-pick-edge" style="color:{edge_color};">{edge:+.1f}%</span>'
        f'</div>'
    )


# ── Game Matchup Card (replaces plain expander labels) ───────────────────────

def render_game_matchup_card_html(
    away_team: str,
    home_team: str,
    away_record: str = "",
    home_record: str = "",
    n_players: int = 0,
    n_props: int = 0,
) -> str:
    """Return an HTML matchup banner with team logos, colors, records,
    and prop/player counts for the QAM game group headers.

    Uses a horizontal split-bar layout with team-color gradient accents.
    """
    away_color, _ = get_team_colors(away_team)
    home_color, _ = get_team_colors(home_team)
    away_logo = _safe_logo_url(away_team)
    home_logo = _safe_logo_url(home_team)
    safe_away = _html.escape(str(away_team))
    safe_home = _html.escape(str(home_team))
    safe_away_rec = _html.escape(str(away_record)) if away_record else ""
    safe_home_rec = _html.escape(str(home_record)) if home_record else ""

    away_rec_html = (
        f'<span class="qam-mu-record">{safe_away_rec}</span>'
        if safe_away_rec else ""
    )
    home_rec_html = (
        f'<span class="qam-mu-record">{safe_home_rec}</span>'
        if safe_home_rec else ""
    )

    return (
        f'<div class="qam-mu-bar" style="'
        f'--away-clr:{away_color};--home-clr:{home_color};">'
        # Away side
        f'<div class="qam-mu-side qam-mu-away">'
        f'<img class="qam-mu-logo" src="{away_logo}" alt="{safe_away}" '
        f'onerror="this.onerror=null;this.src=\'{_NBA_LOGO_FALLBACK}\'">'
        f'<div class="qam-mu-team-info">'
        f'<span class="qam-mu-abbrev" style="color:{away_color};">'
        f'{safe_away}</span>'
        f'{away_rec_html}'
        f'</div>'
        f'</div>'
        # Centre divider
        f'<div class="qam-mu-centre">'
        f'<span class="qam-mu-at">@</span>'
        f'<div class="qam-mu-counts">'
        f'<span class="qam-mu-count">'
        f'👤 {n_players}</span>'
        f'<span class="qam-mu-count">'
        f'📋 {n_props}</span>'
        f'</div>'
        f'</div>'
        # Home side
        f'<div class="qam-mu-side qam-mu-home">'
        f'<div class="qam-mu-team-info" style="text-align:right;">'
        f'<span class="qam-mu-abbrev" style="color:{home_color};">'
        f'{safe_home}</span>'
        f'{home_rec_html}'
        f'</div>'
        f'<img class="qam-mu-logo" src="{home_logo}" alt="{safe_home}" '
        f'onerror="this.onerror=null;this.src=\'{_NBA_LOGO_FALLBACK}\'">'
        f'</div>'
        f'</div>'
    )
