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

PARLAY_STARS = {2: "", 3: "", 4: "", 5: "", 6: ""}

PARLAY_LABELS = {
    2: "2-Leg Power Play",
    3: "3-Leg Triple Lock",
    4: "4-Leg Precision",
    5: "5-Leg Mega Entry",
    6: "6-Leg Max Entry",
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

_QEG_LINE_DEVIATION_THRESHOLD = 25.0  # Minimum |line_vs_avg_pct| to qualify

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
    over_pct = (over_ct / total * 100) if total else 0

    # Edge stats — always meaningful (edge_percentage present on every pick)
    edges = [abs(float(p.get("edge_percentage", 0))) for p in picks]
    avg_edge = sum(edges) / total if total else 0
    peak_edge = max(edges) if edges else 0

    # Line deviation — only from picks that actually have deviation data
    devs = [abs(float(p.get("line_vs_avg_pct", 0))) for p in picks
            if float(p.get("line_vs_avg_pct", 0)) != 0]
    dev_count = len(devs)
    avg_dev = sum(devs) / dev_count if devs else 0

    # Confidence
    confs = [float(p.get("confidence_score", 0)) for p in picks]
    avg_conf = sum(confs) / total if total else 0

    _thr = int(_QEG_LINE_DEVIATION_THRESHOLD)

    # Build optional bottom sub-stat chips
    _sub_parts: list[str] = []
    _sub_parts.append(
        f'<span class="qeg-sub-chip">'
        f'<span class="qeg-sub-icon">🎯</span>'
        f'{avg_conf:.0f} Avg Confidence</span>'
    )
    if dev_count > 0:
        _sub_parts.append(
            f'<span class="qeg-sub-chip">'
            f'<span class="qeg-sub-icon">📊</span>'
            f'{dev_count} Line Dev{"s" if dev_count != 1 else ""}'
            f' ({avg_dev:.1f}% avg)</span>'
        )

    return (
        '<div class="qeg-banner-v2">'
        '<div class="qeg-banner-v2-inner">'
        # Scanline overlay
        '<div class="qeg-scanline-overlay"></div>'
        # Header
        '<div class="qeg-v2-header">'
        '<div class="qeg-v2-icon-ring"><span>⚡</span></div>'
        '<div class="qeg-v2-title-block">'
        f'<h3 class="qeg-v2-title">QUANTUM EDGE GAP</h3>'
        f'<p class="qeg-v2-subtitle">Extreme-value signals where model edge ≥ {_thr}%</p>'
        '</div>'
        '</div>'
        # Main metrics row
        '<div class="qeg-v2-metrics">'
        # Count block
        '<div class="qeg-v2-count-block">'
        f'<span class="qeg-v2-count-num">{total}</span>'
        '<span class="qeg-v2-count-label">SIGNALS</span>'
        '</div>'
        # Over/Under split bar
        '<div class="qeg-v2-split-block">'
        '<div class="qeg-v2-split-labels">'
        f'<span class="qeg-v2-split-over">{over_ct} OVER</span>'
        f'<span class="qeg-v2-split-under">{under_ct} UNDER</span>'
        '</div>'
        f'<div class="qeg-v2-split-bar">'
        f'<div class="qeg-v2-split-fill-over" style="width:{over_pct:.1f}%"></div>'
        f'<div class="qeg-v2-split-fill-under" style="width:{100 - over_pct:.1f}%"></div>'
        '</div>'
        '</div>'
        # Edge metrics
        '<div class="qeg-v2-edge-block">'
        '<div class="qeg-v2-edge-stat">'
        f'<span class="qeg-v2-edge-val">{avg_edge:.1f}%</span>'
        '<span class="qeg-v2-edge-lbl">AVG EDGE</span>'
        '</div>'
        '<div class="qeg-v2-edge-divider"></div>'
        '<div class="qeg-v2-edge-stat">'
        f'<span class="qeg-v2-edge-val qeg-v2-peak">{peak_edge:.1f}%</span>'
        '<span class="qeg-v2-edge-lbl">PEAK</span>'
        '</div>'
        '</div>'
        '</div>'
        # Sub-stats
        '<div class="qeg-v2-sub">'
        + ''.join(_sub_parts)
        + '</div>'
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

    # Probability — direction-aware so we show the relevant side
    prob_over = result.get("probability_over", 0)
    try:
        _prob_raw = float(prob_over)
    except (ValueError, TypeError):
        _prob_raw = 0.5
    _prob_dir = _prob_raw if direction == "OVER" else (1.0 - _prob_raw)
    prob_pct = f"{_prob_dir * 100:.1f}%"

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
    over_pct = max(0, min(100, _prob_raw * 100))
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
          • **OVER**: ``line_vs_avg_pct <= -threshold`` (line 25–100 % below avg).
          • **UNDER**: ``line_vs_avg_pct >= +threshold`` (line 25–100 % above avg).

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
        '<div class="espn-parlay-section-header">'
        '<div class="espn-parlay-section-left">'
        '<div class="espn-parlay-section-icon">AI</div>'
        '<div>'
        '<h3 class="espn-parlay-section-title">AI-Optimized Parlays</h3>'
        '<p class="espn-parlay-section-sub">Multi-leg combos ranked by combined EDGE Score\u2122 &mdash; diversified across games</p>'
        '</div>'
        '</div>'
        '<div class="espn-parlay-section-badge">SMARTAI</div>'
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
    top_pick = " espn-parlay-top" if card_index < 2 else ""

    # ── Build picks, grouped by game when available ──────────
    game_groups = entry.get("game_groups", {})
    raw_picks = entry.get("raw_picks", [])

    picks_html = ""
    if game_groups:
        for matchup, group_data in game_groups.items():
            if isinstance(group_data, dict):
                legs = group_data.get("picks", [])
                meta = group_data.get("meta", {})
            else:
                legs = group_data
                meta = {}

            game_label_html = _render_game_group_label(str(matchup), meta)
            picks_html += (
                f'<div class="espn-parlay-game-group">'
                f'{game_label_html}'
            )
            for leg in legs:
                picks_html += _render_single_leg_html(leg, raw_picks)
            picks_html += '</div>'
    else:
        for pick_str in entry.get("picks", []):
            picks_html += _render_leg_from_string(pick_str, raw_picks)

    # ── Reason tags ──────────────────────────────────────────
    reasons = entry.get("reasons", [])
    reason_html = ""
    if reasons:
        tags = "".join(
            f'<span class="espn-parlay-tag">{_html.escape(r)}</span>'
            for r in reasons
        )
        reason_html = f'<div class="espn-parlay-tags">{tags}</div>'
    elif entry.get("strategy"):
        tag = f'<span class="espn-parlay-tag">{_html.escape(entry["strategy"])}</span>'
        reason_html = f'<div class="espn-parlay-tags">{tag}</div>'

    # ── Stats footer ─────────────────────────────────────────
    combined = entry.get("combined_prob", 0)
    avg_edge = entry.get("avg_edge", 0)
    avg_conf = entry.get("safe_avg", "—")

    edge_color = _POSITIVE_COLOR if avg_edge > 0 else _NEGATIVE_COLOR

    # Rank label
    rank_labels = {0: "TOP PICK", 1: "RUNNER-UP"}
    rank_label = rank_labels.get(card_index, f"#{card_index + 1}")

    # SVG confidence ring (90-degree arc segment based on combined prob)
    ring_pct = min(combined / 100.0, 1.0)
    dash = ring_pct * 188.5  # circumference of r=30 circle ≈ 188.5
    gap = 188.5 - dash

    return (
        f'<div class="espn-parlay-card{top_pick}">'
        # Top bar
        f'<div class="espn-parlay-topbar">'
        f'<span class="espn-parlay-rank">{_html.escape(rank_label)}</span>'
        f'<span class="espn-parlay-label">{_html.escape(label)}</span>'
        f'</div>'
        # Main content
        f'<div class="espn-parlay-body">'
        # Left: confidence ring
        f'<div class="espn-parlay-ring-wrap">'
        f'<svg class="espn-parlay-ring" viewBox="0 0 70 70">'
        f'<circle cx="35" cy="35" r="30" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="4.5"/>'
        f'<circle cx="35" cy="35" r="30" fill="none" stroke="url(#espnGrad{card_index})" '
        f'stroke-width="4.5" stroke-linecap="round" '
        f'stroke-dasharray="{dash:.1f} {gap:.1f}" '
        f'transform="rotate(-90 35 35)"/>'
        f'<defs><linearGradient id="espnGrad{card_index}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="#00C6FF"/>'
        f'<stop offset="100%" stop-color="#00ff9d"/>'
        f'</linearGradient></defs>'
        f'<text x="35" y="33" text-anchor="middle" fill="#f8fafc" '
        f'font-size="14" font-weight="800" font-family="JetBrains Mono,monospace">'
        f'{combined:.0f}%</text>'
        f'<text x="35" y="45" text-anchor="middle" fill="#8b96a9" '
        f'font-size="7.5" font-weight="700" letter-spacing="0.5">PROB</text>'
        f'</svg>'
        f'</div>'
        # Right: picks
        f'<div class="espn-parlay-picks">'
        f'{picks_html}'
        f'</div>'
        f'</div>'
        # Tags
        f'{reason_html}'
        # Footer stats
        f'<div class="espn-parlay-footer">'
        f'<div class="espn-parlay-stat">'
        f'<span class="espn-parlay-stat-num" style="color:{edge_color};">{avg_edge:+.1f}%</span>'
        f'<span class="espn-parlay-stat-lbl">AVG EDGE</span>'
        f'</div>'
        f'<div class="espn-parlay-stat">'
        f'<span class="espn-parlay-stat-num">{num}</span>'
        f'<span class="espn-parlay-stat-lbl">LEGS</span>'
        f'</div>'
        f'<div class="espn-parlay-stat">'
        f'<span class="espn-parlay-stat-num espn-parlay-safe">{avg_conf}</span>'
        f'<span class="espn-parlay-stat-lbl">SAFE SCORE</span>'
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

        away_rec_html = f' <span class="espn-parlay-team-rec">({away_rec})</span>' if away_rec else ""
        home_rec_html = f' <span class="espn-parlay-team-rec">({home_rec})</span>' if home_rec else ""

        return (
            f'<div class="espn-parlay-matchup">'
            f'<div class="espn-parlay-team">'
            f'<img class="espn-parlay-team-logo" '
            f'src="{away_logo}" alt="{safe_away}" '
            f'onerror="this.onerror=null;this.src=\'{_NBA_LOGO_FALLBACK}\'">'
            f'<span class="espn-parlay-team-name" style="color:{away_color};">{safe_away}</span>'
            f'{away_rec_html}'
            f'</div>'
            f'<span class="espn-parlay-vs">@</span>'
            f'<div class="espn-parlay-team">'
            f'<img class="espn-parlay-team-logo" '
            f'src="{home_logo}" alt="{safe_home}" '
            f'onerror="this.onerror=null;this.src=\'{_NBA_LOGO_FALLBACK}\'">'
            f'<span class="espn-parlay-team-name" style="color:{home_color};">{safe_home}</span>'
            f'{home_rec_html}'
            f'</div>'
            f'</div>'
        )

    # Fallback: plain text label (no game context available)
    safe_matchup = _html.escape(matchup)
    return (
        f'<div class="espn-parlay-matchup">'
        f'<span class="espn-parlay-team-name" style="color:#94A3B8;">{safe_matchup}</span>'
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

    dir_cls = "espn-leg-over" if direction == "OVER" else "espn-leg-under"
    dir_label = _html.escape(direction) if direction else ""

    tier_html = ""
    if tier in ("platinum", "gold", "silver"):
        tier_html = f'<span class="espn-leg-tier espn-leg-tier-{tier}">{tier.title()}</span>'

    edge_color = _POSITIVE_COLOR if edge > 0 else _NEGATIVE_COLOR

    return (
        f'<div class="espn-leg-row">'
        f'<div class="espn-leg-left">'
        f'<span class="espn-leg-player">{pname}</span>'
        f'<span class="espn-leg-dir {dir_cls}">{dir_label}</span>'
        f'<span class="espn-leg-detail">{line} {stat}</span>'
        f'{tier_html}'
        f'</div>'
        f'<span class="espn-leg-edge" style="color:{edge_color};">{edge:+.1f}%</span>'
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

    dir_cls = "espn-leg-over" if direction == "OVER" else "espn-leg-under"
    dir_label = _html.escape(direction)

    # Remove direction from rest to avoid duplication
    rest_cleaned = rest
    if direction and rest.upper().startswith(direction):
        rest_cleaned = rest[len(direction):].strip()

    tier_html = ""
    if tier in ("platinum", "gold", "silver"):
        tier_html = f'<span class="espn-leg-tier espn-leg-tier-{tier}">{tier.title()}</span>'

    edge_color = _POSITIVE_COLOR if edge > 0 else _NEGATIVE_COLOR

    return (
        f'<div class="espn-leg-row">'
        f'<div class="espn-leg-left">'
        f'<span class="espn-leg-player">{pname}</span>'
        f'<span class="espn-leg-dir {dir_cls}">{dir_label}</span>'
        f'<span class="espn-leg-detail">{_html.escape(rest_cleaned)}</span>'
        f'{tier_html}'
        f'</div>'
        f'<span class="espn-leg-edge" style="color:{edge_color};">{edge:+.1f}%</span>'
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


# ═══════════════════════════════════════════════════════════════
# TOP 3 TONIGHT — Hero Cards
# ═══════════════════════════════════════════════════════════════

def render_hero_section_html(top_picks: list) -> str:
    """Build the Top 3 Tonight hero section HTML.

    Parameters
    ----------
    top_picks : list
        Up to 3 analysis result dicts, pre-sorted by confidence descending.

    Returns
    -------
    str
        Complete HTML for the hero section (empty string if no picks).
    """
    if not top_picks:
        return ""

    cards: list[str] = []
    for idx, r in enumerate(top_picks[:3]):
        name = _html.escape(r.get("player_name", "Unknown"))
        team = _html.escape((r.get("player_team", "") or "").upper())
        opp = r.get("opponent", "")
        team_line = f'{team} vs {_html.escape(opp)}' if opp else team

        raw_stat = (r.get("stat_type", "") or "").lower().strip()
        stat = _html.escape(_display_stat_name(raw_stat))
        direction = (r.get("direction", "OVER") or "OVER").upper()
        dir_label = "MORE" if direction == "OVER" else "LESS"
        try:
            line_val_num = float(r.get("prop_line", r.get("line", 0)))
            line_val = f'{line_val_num:g}'
        except (ValueError, TypeError):
            line_val_num = 0
            line_val = "\u2014"

        tier = r.get("tier", "Gold")
        conf = r.get("confidence_score", 0)
        edge = r.get("edge_percentage", 0)
        # Direction-aware probability: OVER uses probability_over,
        # UNDER uses (1 - probability_over).  Value is 0-1 fraction.
        _prob_over_raw = float(r.get("probability_over", 0) or 0)
        prob = (_prob_over_raw if direction == "OVER" else 1.0 - _prob_over_raw) * 100

        # Confidence color
        if conf >= 80:
            conf_color = "#00f0ff"
        elif conf >= 65:
            conf_color = "#FFD700"
        else:
            conf_color = "#00b4ff"

        # ── Projection ───────────────────────────────────────
        try:
            proj_val = float(r.get("adjusted_projection", 0) or 0)
        except (ValueError, TypeError):
            proj_val = 0
        proj_display = f'{proj_val:.1f}' if proj_val else "\u2014"

        # Projection vs Line bar (visual gap indicator)
        proj_bar_html = ""
        if proj_val and line_val_num:
            diff = proj_val - line_val_num
            diff_pct = (diff / line_val_num * 100) if line_val_num else 0
            bar_color = "#00ff9d" if diff > 0 else "#ff5e00"
            bar_label = f'+{diff:.1f}' if diff > 0 else f'{diff:.1f}'
            bar_width = min(abs(diff_pct), 100)
            proj_bar_html = (
                f'<div class="qam-hero-proj-bar">'
                f'<div class="qam-hero-proj-bar-label">'
                f'<span style="color:#64748b;">Line {_html.escape(line_val)}</span>'
                f'<span style="color:{bar_color};font-weight:700;">'
                f'Proj {proj_display} ({bar_label})</span>'
                f'</div>'
                f'<div class="qam-hero-proj-bar-track">'
                f'<div class="qam-hero-proj-bar-fill" '
                f'style="width:{bar_width:.0f}%;background:{bar_color};"></div>'
                f'</div>'
                f'</div>'
            )

        # ── Verdict ──────────────────────────────────────────
        verdict_raw = r.get("verdict", "") or ""
        verdict_emoji = r.get("verdict_emoji", "") or ""
        verdict_html = ""
        if verdict_raw:
            v_upper = verdict_raw.upper().replace("_", " ")
            v_cls = verdict_raw.lower().replace(" ", "-").replace("_", "-")
            verdict_html = (
                f'<span class="qam-hero-verdict" data-verdict="{_html.escape(v_cls)}">'
                f'{verdict_emoji} {_html.escape(v_upper)}</span>'
            )

        # ── Season Average (stat-matched) ────────────────────
        season_avg = 0
        avg_key_map = {
            "points": "season_pts_avg", "rebounds": "season_reb_avg",
            "assists": "season_ast_avg", "threes": "season_threes_avg",
            "three pointers made": "season_threes_avg",
            "steals": "season_stl_avg", "blocks": "season_blk_avg",
        }
        avg_key = avg_key_map.get(raw_stat, "")
        if avg_key:
            try:
                season_avg = float(r.get(avg_key, 0) or 0)
            except (ValueError, TypeError):
                season_avg = 0
        # Fallback: try generic keys
        if not season_avg:
            for k in (f"{raw_stat}_avg", "points_avg", "rebounds_avg", "assists_avg"):
                try:
                    season_avg = float(r.get(k, 0) or 0)
                    if season_avg:
                        break
                except (ValueError, TypeError):
                    continue
        season_avg_display = f'{season_avg:.1f}' if season_avg else "\u2014"

        # ── Headshot ─────────────────────────────────────────
        player_id = r.get("player_id", "") or ""
        if player_id:
            headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
        else:
            headshot_url = ""
        headshot_html = (
            f'<img class="qam-hero-headshot" '
            f'src="{headshot_url}" alt="" '
            f'onerror="this.style.display=\'none\'">'
        ) if headshot_url else ""

        # ── Simulation range ─────────────────────────────────
        try:
            p10 = float(r.get("percentile_10", 0) or 0)
        except (ValueError, TypeError):
            p10 = 0
        try:
            p90 = float(r.get("percentile_90", 0) or 0)
        except (ValueError, TypeError):
            p90 = 0
        range_html = ""
        if p10 and p90:
            range_html = (
                f'<div class="qam-hero-range">'
                f'<span class="qam-hero-range-label">SIM RANGE</span>'
                f'<span class="qam-hero-range-vals">'
                f'{p10:.1f} — {p90:.1f}</span>'
                f'</div>'
            )

        # ── Joseph take ──────────────────────────────────────
        joseph_take = ""
        take_text = r.get("joseph_take", "") or r.get("joseph_short_take", "")
        if take_text:
            joseph_take = (
                f'<div class="qam-hero-joseph">'
                f'{_html.escape(str(take_text)[:220])}'
                f'</div>'
            )

        cards.append(
            f'<div class="qam-hero-card" data-tier="{_html.escape(tier)}" '
            f'style="animation-delay:{idx * 120}ms;">'
            f'<span class="qam-hero-rank">#{idx + 1}</span>'
            f'<div class="qam-hero-top">'
            f'{headshot_html}'
            f'<div>'
            f'<div class="qam-hero-name">{name}</div>'
            f'<div class="qam-hero-team">{team_line}</div>'
            f'<div class="qam-hero-badges">'
            f'<span class="qam-hero-tier" data-tier="{_html.escape(tier)}">'
            f'{_html.escape(tier)}</span>'
            f'{verdict_html}'
            f'</div>'
            f'</div>'
            f'</div>'
            f'<div class="qam-hero-body">'
            f'<div>'
            f'<span class="qam-hero-line">{_html.escape(line_val)}</span>'
            f'<span class="qam-hero-dir" data-dir="{_html.escape(direction)}">{dir_label}</span>'
            f'</div>'
            f'<div class="qam-hero-stat">{stat}</div>'
            f'</div>'
            f'{proj_bar_html}'
            f'<div class="qam-hero-metrics">'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val" style="color:{conf_color};">{conf:.0f}</div>'
            f'<div class="qam-hero-metric-label">Confidence</div>'
            f'</div>'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val">{edge:+.1f}%</div>'
            f'<div class="qam-hero-metric-label">Edge</div>'
            f'</div>'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val">{prob:.0f}%</div>'
            f'<div class="qam-hero-metric-label">Probability</div>'
            f'</div>'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val" style="color:#00f0ff;">{proj_display}</div>'
            f'<div class="qam-hero-metric-label">Projection</div>'
            f'</div>'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val">{season_avg_display}</div>'
            f'<div class="qam-hero-metric-label">Avg</div>'
            f'</div>'
            f'</div>'
            f'{range_html}'
            f'{joseph_take}'
            f'</div>'
        )

    return (
        f'<div class="qam-hero-section">'
        f'<div class="qam-hero-label">🏆 Top {len(cards)} Tonight</div>'
        f'<div class="qam-hero-grid">{"".join(cards)}</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════
# QUICK VIEW — Compact one-line-per-pick table
# ═══════════════════════════════════════════════════════════════

def render_quick_view_html(results: list, best_pick_keys: set | None = None) -> str:
    """Build the Quick View compact table HTML.

    Parameters
    ----------
    results : list
        Analysis result dicts (active only, pre-sorted).
    best_pick_keys : set or None
        Set of (player_name, stat_type_lower, line) tuples that are top picks.

    Returns
    -------
    str
        Complete HTML table for Quick View mode.
    """
    if not results:
        return ""

    best_pick_keys = best_pick_keys or set()
    rows: list[str] = []

    for r in results:
        if r.get("player_is_out", False):
            continue

        name = _html.escape(r.get("player_name", "Unknown"))
        raw_stat = (r.get("stat_type", "") or "").lower().strip()
        stat = _html.escape(_display_stat_name(raw_stat))
        direction = (r.get("direction", "OVER") or "OVER").upper()
        dir_label = "MORE" if direction == "OVER" else "LESS"
        try:
            line_val = f'{float(r.get("prop_line", r.get("line", 0))):g}'
        except (ValueError, TypeError):
            line_val = "—"

        tier = r.get("tier", "Bronze")
        conf = r.get("confidence_score", 0)
        edge = r.get("edge_percentage", 0)

        # Confidence color
        if conf >= 80:
            conf_color = "#00f0ff"
        elif conf >= 65:
            conf_color = "#FFD700"
        elif conf >= 50:
            conf_color = "#00b4ff"
        else:
            conf_color = "#94A3B8"

        # Badges
        badges = ""
        rk = (
            r.get("player_name", ""),
            (r.get("stat_type", "") or "").lower(),
            r.get("prop_line", r.get("line", 0)),
        )
        if rk in best_pick_keys:
            badges += '<span class="qam-quick-badge qam-quick-badge-top">⭐ TOP</span>'
        if r.get("should_avoid", False):
            badges += '<span class="qam-quick-badge qam-quick-badge-avoid">⚠️</span>'

        rows.append(
            f'<tr>'
            f'<td><span class="qam-quick-player">{name}</span>{badges}</td>'
            f'<td><span class="qam-quick-stat">{stat}</span></td>'
            f'<td><span class="qam-quick-line">{_html.escape(line_val)}</span></td>'
            f'<td><span class="qam-quick-dir" data-dir="{_html.escape(direction)}">'
            f'{dir_label}</span></td>'
            f'<td><span class="qam-quick-conf" style="color:{conf_color};">'
            f'{conf:.0f}</span></td>'
            f'<td><span class="qam-quick-edge">{edge:+.1f}%</span></td>'
            f'<td><span class="qam-quick-tier" data-tier="{_html.escape(tier)}">'
            f'{_html.escape(tier)}</span></td>'
            f'</tr>'
        )

    return (
        f'<table class="qam-quick-table">'
        f'<thead><tr>'
        f'<th>Player</th><th>Stat</th><th>Line</th>'
        f'<th>Dir</th><th>Conf</th><th>Edge</th><th>Tier</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table>'
    )
