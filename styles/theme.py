# ============================================================
# FILE: styles/theme.py
# PURPOSE: All CSS/HTML generators for the SmartAI-NBA UI.
#          Provides a premium dark theme with glassmorphism
#          cards, animated tier badges, and NBA team colors.
# USAGE:
#   from styles.theme import get_global_css, get_player_card_html
#   st.markdown(get_global_css(), unsafe_allow_html=True)
# ============================================================

# Standard library only — no new dependencies


# ============================================================
# SECTION: NBA Team Colors
# Primary and secondary hex colors for each franchise.
# ============================================================

# Maps team abbreviation → (primary_color, secondary_color)
_TEAM_COLORS = {
    "ATL": ("#C8102E", "#FDB927"),
    "BOS": ("#007A33", "#BA9653"),
    "BKN": ("#000000", "#FFFFFF"),
    "CHA": ("#1D1160", "#00788C"),
    "CHI": ("#CE1141", "#000000"),
    "CLE": ("#860038", "#FDBB30"),
    "DAL": ("#00538C", "#002B5E"),
    "DEN": ("#0E2240", "#FEC524"),
    "DET": ("#C8102E", "#1D42BA"),
    "GSW": ("#1D428A", "#FFC72C"),
    "HOU": ("#CE1141", "#000000"),
    "IND": ("#002D62", "#FDBB30"),
    "LAC": ("#C8102E", "#1D428A"),
    "LAL": ("#552583", "#FDB927"),
    "MEM": ("#5D76A9", "#12173F"),
    "MIA": ("#98002E", "#F9A01B"),
    "MIL": ("#00471B", "#EEE1C6"),
    "MIN": ("#0C2340", "#236192"),
    "NOP": ("#0C2340", "#C8102E"),
    "NYK": ("#006BB6", "#F58426"),
    "OKC": ("#007AC1", "#EF3B24"),
    "ORL": ("#0077C0", "#C4CED4"),
    "PHI": ("#006BB6", "#ED174C"),
    "PHX": ("#1D1160", "#E56020"),
    "POR": ("#E03A3E", "#000000"),
    "SAC": ("#5A2D81", "#63727A"),
    "SAS": ("#C4CED4", "#000000"),
    "TOR": ("#CE1141", "#000000"),
    "UTA": ("#002B5C", "#00471B"),
    "WAS": ("#002B5C", "#E31837"),
}

_DEFAULT_TEAM_COLORS = ("#1a1a2e", "#0f3460")


def get_team_colors(team_abbrev):
    """
    Return (primary, secondary) hex colors for an NBA team.

    Args:
        team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL')

    Returns:
        tuple: (primary_color, secondary_color) hex strings
    """
    return _TEAM_COLORS.get(team_abbrev.upper() if team_abbrev else "", _DEFAULT_TEAM_COLORS)


# ============================================================
# END SECTION: NBA Team Colors
# ============================================================


# ============================================================
# SECTION: Global CSS Theme
# Injected once per page via st.markdown(unsafe_allow_html=True)
# ============================================================

def get_global_css():
    """
    Return the full CSS string for the SmartAI-NBA dark theme.

    Includes:
    - Deep navy/purple background gradients
    - Glassmorphism card components
    - Tier badge animations
    - Custom scrollbar
    - Metric cards with gradient borders
    - Badge/pill styling
    - Responsive helpers

    Returns:
        str: Full <style>...</style> block ready for st.markdown()
    """
    return """
<style>
/* ─── Base ────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
    color: #e2e8f0;
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0a0a1a; }
::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4a5568; }

/* ─── Analysis Card ───────────────────────────────────────── */
.smartai-card {
    background: linear-gradient(135deg, rgba(26,26,46,0.95) 0%, rgba(22,33,62,0.95) 100%);
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.45),
                inset 0 1px 0 rgba(255,255,255,0.05);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}
.smartai-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #00ff88, #6366f1, #ffd700);
    opacity: 0.5;
}
.smartai-card:hover {
    border-color: rgba(99,102,241,0.5);
    box-shadow: 0 12px 40px rgba(0,0,0,0.55),
                inset 0 1px 0 rgba(255,255,255,0.08);
}

/* ─── Player Name & Team Pill ─────────────────────────────── */
.player-name {
    font-size: 1.3rem;
    font-weight: 800;
    color: #f0f4ff;
    letter-spacing: -0.02em;
}
.team-pill {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.8rem;
    color: #fff;
    background: rgba(15,52,96,0.9);
    margin-left: 8px;
    vertical-align: middle;
    border: 1px solid rgba(255,255,255,0.12);
}
.position-tag {
    color: #718096;
    font-size: 0.82rem;
    margin-left: 8px;
    vertical-align: middle;
}

/* ─── Tier Badges ─────────────────────────────────────────── */
.tier-badge {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-weight: 800;
    font-size: 0.9rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    position: relative;
}
.tier-platinum {
    background: linear-gradient(135deg, #6d28d9, #8b5cf6);
    color: #fff;
    box-shadow: 0 0 12px rgba(109,40,217,0.55);
    animation: pulse-platinum 2.5s infinite;
}
@keyframes pulse-platinum {
    0%, 100% { box-shadow: 0 0 12px rgba(109,40,217,0.55); }
    50% { box-shadow: 0 0 22px rgba(139,92,246,0.8); }
}
.tier-gold {
    background: linear-gradient(135deg, #d97706, #f59e0b);
    color: #fff;
    box-shadow: 0 0 10px rgba(217,119,6,0.45);
}
.tier-silver {
    background: linear-gradient(135deg, #6b7280, #9ca3af);
    color: #fff;
}
.tier-bronze {
    background: linear-gradient(135deg, #92400e, #b45309);
    color: #fff;
}

/* ─── Platform & Stat Badges ──────────────────────────────── */
.platform-badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 5px;
    font-size: 0.78rem;
    font-weight: 700;
}
.stat-chip {
    display: inline-block;
    background: rgba(45,55,72,0.8);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 4px 11px;
    margin-right: 6px;
    margin-top: 4px;
    color: #e2e8f0;
    font-size: 0.83rem;
    font-weight: 600;
}
.stat-label { color: #718096; font-size: 0.72rem; }

/* ─── Probability Gauge ───────────────────────────────────── */
.prob-gauge-wrap {
    background: rgba(45,55,72,0.6);
    border-radius: 10px;
    height: 16px;
    overflow: hidden;
    margin-top: 6px;
    border: 1px solid rgba(255,255,255,0.06);
}
.prob-gauge-fill-over {
    background: linear-gradient(90deg, #10b981, #34d399);
    height: 100%;
    border-radius: 10px;
    transition: width 0.5s ease;
}
.prob-gauge-fill-under {
    background: linear-gradient(90deg, #ef4444, #f87171);
    height: 100%;
    border-radius: 10px;
    transition: width 0.5s ease;
}
.prob-value {
    font-size: 1.15rem;
    font-weight: 800;
    color: #f0f4ff;
}
.edge-badge {
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.82rem;
    font-weight: 700;
}
.edge-positive { background: rgba(16,185,129,0.18); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
.edge-negative { background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }

/* ─── Direction Badge ─────────────────────────────────────── */
.dir-over {
    background: rgba(39,103,73,0.9);
    color: #9ae6b4;
    padding: 4px 12px;
    border-radius: 14px;
    font-weight: 800;
    font-size: 0.9rem;
    border: 1px solid rgba(154,230,180,0.25);
}
.dir-under {
    background: rgba(116,42,42,0.9);
    color: #feb2b2;
    padding: 4px 12px;
    border-radius: 14px;
    font-weight: 800;
    font-size: 0.9rem;
    border: 1px solid rgba(254,178,178,0.25);
}

/* ─── Force Bar ───────────────────────────────────────────── */
.force-bar-wrap {
    display: flex;
    height: 10px;
    border-radius: 5px;
    overflow: hidden;
    background: rgba(45,55,72,0.6);
    margin-top: 5px;
}
.force-bar-over  { background: linear-gradient(90deg, #10b981, #34d399); }
.force-bar-under { background: linear-gradient(90deg, #f87171, #ef4444); }

/* ─── Distribution Range ──────────────────────────────────── */
.dist-range-wrap { text-align: right; }
.dist-p10  { color: #f87171; font-size: 0.82rem; font-weight: 700; }
.dist-p50  { color: #f0f4ff; font-size: 0.9rem; font-weight: 800; }
.dist-p90  { color: #34d399; font-size: 0.82rem; font-weight: 700; }
.dist-sep  { color: #4a5568; font-size: 0.82rem; margin: 0 3px; }
.dist-label { color: #4a5568; font-size: 0.7rem; }

/* ─── Form Dots ───────────────────────────────────────────── */
.form-dot-over  { display:inline-block; width:11px; height:11px; border-radius:50%; background:#10b981; margin:1px; vertical-align:middle; }
.form-dot-under { display:inline-block; width:11px; height:11px; border-radius:50%; background:#ef4444; margin:1px; vertical-align:middle; }

/* ─── Summary Cards ───────────────────────────────────────── */
.summary-card {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.summary-value {
    font-size: 2rem;
    font-weight: 800;
    color: #f0f4ff;
    line-height: 1.1;
}
.summary-label {
    font-size: 0.75rem;
    color: #718096;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-top: 5px;
}

/* ─── Best Bets Card ──────────────────────────────────────── */
.best-bet-card {
    background: linear-gradient(135deg, rgba(109,40,217,0.15), rgba(251,191,36,0.08));
    border: 1px solid rgba(109,40,217,0.35);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 10px;
    position: relative;
}
.best-bet-rank {
    position: absolute;
    top: -10px; left: 16px;
    background: linear-gradient(135deg, #6d28d9, #f59e0b);
    color: #fff;
    font-weight: 800;
    font-size: 0.75rem;
    padding: 2px 10px;
    border-radius: 10px;
}

/* ─── Roster Health ───────────────────────────────────────── */
.health-matched {
    display: inline-block;
    background: rgba(16,185,129,0.15);
    border: 1px solid rgba(16,185,129,0.35);
    color: #34d399;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    margin: 2px;
}
.health-fuzzy {
    display: inline-block;
    background: rgba(234,179,8,0.12);
    border: 1px solid rgba(234,179,8,0.4);
    color: #fbbf24;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    margin: 2px;
    cursor: help;
}
.health-unmatched {
    display: inline-block;
    background: rgba(239,68,68,0.15);
    border: 1px solid rgba(239,68,68,0.35);
    color: #f87171;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    margin: 2px;
}

/* ─── Live / Sample Badge ─────────────────────────────────── */
.live-badge {
    display: inline-block;
    background: rgba(39,103,73,0.85);
    color: #9ae6b4;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    border: 1px solid rgba(154,230,180,0.2);
}
.sample-badge {
    display: inline-block;
    background: rgba(116,66,16,0.85);
    color: #fbd38d;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    border: 1px solid rgba(251,211,141,0.2);
}

/* ─── Correlation Warning ─────────────────────────────────── */
.corr-warning {
    background: rgba(234,179,8,0.1);
    border: 1px solid rgba(234,179,8,0.35);
    border-radius: 8px;
    padding: 8px 14px;
    color: #fbbf24;
    font-size: 0.83rem;
    margin-top: 8px;
}
</style>
"""


# ============================================================
# END SECTION: Global CSS Theme
# ============================================================


# ============================================================
# SECTION: HTML Component Generators
# Each function returns a self-contained HTML snippet.
# ============================================================

def get_tier_badge_html(tier, tier_emoji=None):
    """
    Return styled HTML for a tier badge.

    Args:
        tier (str): 'Platinum', 'Gold', 'Silver', or 'Bronze'
        tier_emoji (str, optional): Override emoji (default per tier)

    Returns:
        str: HTML span with appropriate CSS class
    """
    tier_emojis = {
        "Platinum": "💎",
        "Gold": "🥇",
        "Silver": "🥈",
        "Bronze": "🥉",
    }
    emoji = tier_emoji or tier_emojis.get(tier, "🏅")
    css_class = f"tier-badge tier-{tier.lower()}"
    return f'<span class="{css_class}">{emoji} {tier}</span>'


def get_probability_gauge_html(probability, direction):
    """
    Return a styled probability progress bar.

    Args:
        probability (float): Raw P(over), 0.0–1.0
        direction (str): 'OVER' or 'UNDER'

    Returns:
        str: HTML div containing the gauge bar
    """
    if direction == "OVER":
        display_pct = probability * 100
        fill_class = "prob-gauge-fill-over"
    else:
        display_pct = (1.0 - probability) * 100
        fill_class = "prob-gauge-fill-under"
    bar_width = int(min(100, max(0, display_pct)))
    return f"""<div class="prob-gauge-wrap">
  <div class="{fill_class}" style="width:{bar_width}%;"></div>
</div>"""


def get_stat_pill_html(label, value, emoji=""):
    """
    Return a styled stat pill chip.

    Args:
        label (str): Stat label (e.g., 'PPG')
        value: Stat value (e.g., 24.8)
        emoji (str): Optional emoji prefix

    Returns:
        str: HTML span
    """
    prefix = f"{emoji} " if emoji else ""
    return f'<span class="stat-chip">{prefix}<strong>{value}</strong> <span class="stat-label">{label}</span></span>'


def get_force_bar_html(over_strength, under_strength, over_count, under_count):
    """
    Return a proportional green/red force bar showing OVER vs UNDER pressure.

    Args:
        over_strength (float): Total strength of OVER forces
        under_strength (float): Total strength of UNDER forces
        over_count (int): Number of OVER forces
        under_count (int): Number of UNDER forces

    Returns:
        str: HTML div with the force bar
    """
    total = (over_strength + under_strength) or 1.0
    over_pct = int(over_strength / total * 100)
    under_pct = 100 - over_pct
    return f"""<div class="force-bar-wrap">
  <div class="force-bar-over" style="width:{over_pct}%;"></div>
  <div class="force-bar-under" style="width:{under_pct}%;"></div>
</div>
<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#718096;margin-top:3px;">
  <span>⬆️ OVER ({over_count})</span>
  <span>UNDER ({under_count}) ⬇️</span>
</div>"""


def get_distribution_range_html(p10, p50, p90):
    """
    Return a styled distribution range display (10th / 50th / 90th pct).

    Args:
        p10 (float): 10th percentile value
        p50 (float): 50th percentile (median)
        p90 (float): 90th percentile value

    Returns:
        str: HTML span block
    """
    return f"""<div class="dist-range-wrap">
  <span class="dist-p10">{p10:.1f}</span>
  <span class="dist-sep">—</span>
  <span class="dist-p50">{p50:.1f}</span>
  <span class="dist-sep">—</span>
  <span class="dist-p90">{p90:.1f}</span>
  <div class="dist-label">10th / 50th / 90th pct</div>
</div>"""


def get_player_card_html(result):
    """
    Build the complete styled analysis card HTML for one prop result.

    Args:
        result (dict): Full analysis result dict from the simulation loop.
            Expected keys: player_name, stat_type, line, direction, tier,
            tier_emoji, probability_over, edge_percentage, confidence_score,
            platform, player_team, player_position, season_pts_avg, etc.

    Returns:
        str: Complete HTML string for the card
    """
    player = result.get("player_name", "Unknown")
    stat = result.get("stat_type", "").capitalize()
    line = result.get("line", 0)
    direction = result.get("direction", "OVER")
    tier = result.get("tier", "Bronze")
    tier_emoji = result.get("tier_emoji", "🥉")
    prob_over = result.get("probability_over", 0.5)
    edge = result.get("edge_percentage", 0)
    confidence = result.get("confidence_score", 50)
    platform = result.get("platform", "")
    team = result.get("player_team", result.get("team", ""))
    position = result.get("player_position", result.get("position", ""))
    proj = result.get("adjusted_projection", 0)

    pts_avg = result.get("season_pts_avg", result.get("points_avg", 0))
    reb_avg = result.get("season_reb_avg", result.get("rebounds_avg", 0))
    ast_avg = result.get("season_ast_avg", result.get("assists_avg", 0))

    prob_pct = prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100
    direction_arrow = "⬆️" if direction == "OVER" else "⬇️"

    tier_class = f"tier-badge tier-{tier.lower()}"
    dir_class = "dir-over" if direction == "OVER" else "dir-under"

    platform_colors = {
        "PrizePicks": "rgba(39,103,73,0.9)",
        "Underdog": "rgba(85,60,154,0.9)",
        "DraftKings": "rgba(43,108,176,0.9)",
    }
    plat_color = platform_colors.get(platform, "rgba(45,55,72,0.9)")

    fill_class = "prob-gauge-fill-over" if direction == "OVER" else "prob-gauge-fill-under"
    bar_width = int(min(100, max(0, prob_pct)))

    primary_color, secondary_color = get_team_colors(team)

    # Team badge
    team_badge = f'<span class="team-pill" style="background:{secondary_color};">{team}</span>' if team else ""
    position_tag = f'<span class="position-tag">{position}</span>' if position else ""

    # Stat pills
    stat_pills = ""
    if pts_avg:
        stat_pills += get_stat_pill_html("PPG", f"{pts_avg:.1f}", "🏀")
    if reb_avg:
        stat_pills += get_stat_pill_html("RPG", f"{reb_avg:.1f}", "📊")
    if ast_avg:
        stat_pills += get_stat_pill_html("APG", f"{ast_avg:.1f}", "🎯")
    if proj:
        stat_pills += get_stat_pill_html("Proj", f"{proj:.1f}", "📐")

    # Edge badge
    edge_class = "edge-positive" if edge >= 0 else "edge-negative"
    edge_sign = "+" if edge >= 0 else ""
    edge_html = f'<span class="edge-badge {edge_class}">{edge_sign}{edge:.1f}% edge</span>'

    # Confidence color
    conf_color = "#34d399" if confidence >= 70 else "#fbbf24" if confidence >= 50 else "#f87171"

    # Force bar
    over_forces = result.get("forces", {}).get("over_forces", [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    total_over_strength = sum(f.get("strength", 1) for f in over_forces)
    total_under_strength = sum(f.get("strength", 1) for f in under_forces)
    force_bar = get_force_bar_html(
        total_over_strength, total_under_strength,
        len(over_forces), len(under_forces)
    )

    # Distribution range
    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)
    dist_range = get_distribution_range_html(p10, p50, p90)

    # Opponent
    opponent = result.get("opponent", "")
    matchup_html = f'<span style="color:#718096;font-size:0.82rem;">vs {opponent}</span>' if opponent else ""

    # Line context
    line_vs_avg = result.get("line_vs_avg_pct", 0)
    if line_vs_avg != 0:
        line_ctx = f"Line is {abs(line_vs_avg):.0f}% {'above' if line_vs_avg > 0 else 'below'} season avg"
        line_ctx_html = f'<span style="color:#718096;font-size:0.78rem;font-style:italic;">{line_ctx}</span>'
    else:
        line_ctx_html = ""

    # Recent form dots
    recent_results = result.get("recent_form_results", [])
    form_html = ""
    if recent_results:
        stat_map = {"points": "pts", "rebounds": "reb", "assists": "ast",
                    "threes": "fg3m", "steals": "stl", "blocks": "blk", "turnovers": "tov"}
        mapped_key = stat_map.get(stat.lower(), "pts")
        dots = ""
        for g in recent_results[:5]:
            val = g.get(mapped_key, g.get("pts", 0))
            dot_cls = "form-dot-over" if val >= line else "form-dot-under"
            dots += f'<span class="{dot_cls}"></span>'
        form_html = f"""<div style="margin-right:16px;">
      <div style="color:#718096;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Last 5</div>
      {dots}
    </div>"""

    # Correlation warning (passed in from caller if applicable)
    corr_warning = result.get("_correlation_warning", "")
    corr_html = f'<div class="corr-warning">⚠️ {corr_warning}</div>' if corr_warning else ""

    return f"""
<div class="smartai-card" style="border-top-color:{primary_color};">
  <!-- Header: Player name + team + tier -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
    <div>
      <span class="player-name">{player}</span>
      {team_badge}
      {position_tag}
    </div>
    <span class="{tier_class}">{tier_emoji} {tier}</span>
  </div>

  <!-- Subheader: Platform + stat + line + matchup -->
  <div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
    <span class="platform-badge" style="background:{plat_color};color:#fff;">{platform}</span>
    <span style="color:#a0aec0;font-size:0.9rem;">{stat} &nbsp;·&nbsp; Line: <strong style="color:#f0f4ff;">{line}</strong></span>
    {matchup_html}
    {line_ctx_html}
  </div>

  <!-- Stat pills -->
  {f'<div style="margin-top:10px;">{stat_pills}</div>' if stat_pills else ""}

  <!-- Probability gauge -->
  <div style="margin-top:14px;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:4px;">
      <span class="{dir_class}">{direction_arrow} {direction}</span>
      <span class="prob-value">{prob_pct:.1f}%</span>
      {edge_html}
      <span style="color:#718096;font-size:0.82rem;">Confidence: <strong style="color:{conf_color};">{confidence:.0f}/100</strong></span>
    </div>
    <div class="prob-gauge-wrap">
      <div class="{fill_class}" style="width:{bar_width}%;"></div>
    </div>
  </div>

  <!-- Form + Force bar + Distribution -->
  <div style="margin-top:12px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;">
    {form_html}
    <div style="flex:1;min-width:160px;">
      <div style="color:#718096;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Over/Under Forces</div>
      {force_bar}
    </div>
    <div style="min-width:110px;">
      <div style="color:#718096;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Range</div>
      {dist_range}
    </div>
  </div>
  {corr_html}
</div>
"""


def get_best_bets_section_html(best_bets):
    """
    Return HTML for the "Best Bets" ranked summary section.

    Args:
        best_bets (list of dict): Top analysis results (ranked)

    Returns:
        str: HTML string for the best-bets section
    """
    if not best_bets:
        return ""

    rank_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    rows = []
    for i, bet in enumerate(best_bets[:5]):
        emoji = rank_emojis[i] if i < len(rank_emojis) else f"{i+1}."
        player = bet.get("player_name", "")
        stat = bet.get("stat_type", "").capitalize()
        line = bet.get("line", 0)
        direction = bet.get("direction", "OVER")
        prob_over = bet.get("probability_over", 0.5)
        prob_pct = prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100
        edge = bet.get("edge_percentage", 0)
        tier = bet.get("tier", "")
        tier_class = f"tier-badge tier-{tier.lower()}"
        tier_emoji = bet.get("tier_emoji", "")
        platform = bet.get("platform", "")
        rec = bet.get("recommendation", "")
        dir_class = "dir-over" if direction == "OVER" else "dir-under"
        arrow = "⬆️" if direction == "OVER" else "⬇️"
        edge_sign = "+" if edge >= 0 else ""

        rows.append(f"""
<div class="best-bet-card">
  <div class="best-bet-rank">{emoji} #{i+1}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-top:6px;">
    <div>
      <strong style="color:#f0f4ff;font-size:1.05rem;">{player}</strong>
      <span style="color:#a0aec0;font-size:0.88rem;margin-left:8px;">{stat} {line}</span>
      <span style="color:#718096;font-size:0.8rem;margin-left:6px;">{platform}</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <span class="{dir_class}">{arrow} {direction}</span>
      <span class="{tier_class}">{tier_emoji} {tier}</span>
    </div>
  </div>
  <div style="margin-top:6px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
    <span style="color:#f0f4ff;font-weight:700;">{prob_pct:.1f}%</span>
    <span style="color:#34d399;font-size:0.82rem;">{edge_sign}{edge:.1f}% edge</span>
    <span style="color:#718096;font-size:0.82rem;font-style:italic;">{rec}</span>
  </div>
</div>
""")

    cards_html = "\n".join(rows)
    return f"""
<div style="background:linear-gradient(135deg,rgba(109,40,217,0.08),rgba(251,191,36,0.05));
            border:1px solid rgba(109,40,217,0.25);border-radius:16px;padding:20px 24px;margin-bottom:20px;">
  <div style="font-size:1.15rem;font-weight:800;color:#f0f4ff;margin-bottom:14px;">
    🏆 Best Bets Today
    <span style="font-size:0.8rem;font-weight:400;color:#718096;margin-left:10px;">Ranked by confidence score</span>
  </div>
  {cards_html}
</div>
"""


def get_roster_health_html(matched, fuzzy_matched, unmatched):
    """
    Return HTML showing prop-to-roster matching status.

    Three categories:
    - ✅ Matched players (green) — definitive match
    - ⚠️ Fuzzy matched (yellow) — probable match with suggestion
    - ❌ Unmatched (red) — no match found, closest suggestion shown

    Args:
        matched (list of dict): Items from validate_props_against_roster()['matched']
            Each has 'prop' (dict) and 'matched_name' (str)
        fuzzy_matched (list of dict): Items from ['fuzzy_matched']
            Each has 'prop', 'matched_name', 'suggestion'
        unmatched (list of dict): Items from ['unmatched']
            Each has 'prop' (dict) and 'suggestion' (str or None)

    Returns:
        str: HTML string for the roster health section
    """
    sections = []

    if matched:
        chips = " ".join(
            f'<span class="health-matched">✅ {item["prop"].get("player_name", "")}</span>'
            for item in matched
        )
        sections.append(f"""
<div style="margin-bottom:12px;">
  <div style="color:#34d399;font-size:0.8rem;font-weight:700;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:6px;">
    ✅ Matched ({len(matched)})
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{chips}</div>
</div>""")

    if fuzzy_matched:
        chips = " ".join(
            f'<span class="health-fuzzy" title="{item.get("suggestion","")}">'
            f'⚠️ {item["prop"].get("player_name", "")}'
            f'<span style="font-size:0.7rem;opacity:0.8;"> → {item.get("matched_name","")}</span>'
            f'</span>'
            for item in fuzzy_matched
        )
        sections.append(f"""
<div style="margin-bottom:12px;">
  <div style="color:#fbbf24;font-size:0.8rem;font-weight:700;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:6px;">
    ⚠️ Fuzzy Matched ({len(fuzzy_matched)}) — using closest match
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{chips}</div>
</div>""")

    if unmatched:
        chips = " ".join(
            f'<span class="health-unmatched" title="Closest: {item.get("suggestion") or "none"}">'
            f'❌ {item["prop"].get("player_name", "")}'
            + (f'<span style="font-size:0.7rem;opacity:0.7;"> (suggest: {item["suggestion"]})</span>'
               if item.get("suggestion") else "")
            + "</span>"
            for item in unmatched
        )
        sections.append(f"""
<div style="margin-bottom:12px;">
  <div style="color:#f87171;font-size:0.8rem;font-weight:700;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:6px;">
    ❌ Unmatched ({len(unmatched)}) — will use fallback data
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{chips}</div>
</div>""")

    if not sections:
        return '<div style="color:#34d399;">✅ All props matched to the player database.</div>'

    inner = "\n".join(sections)
    total = len(matched) + len(fuzzy_matched) + len(unmatched)
    match_pct = int((len(matched) + len(fuzzy_matched)) / max(total, 1) * 100)
    return f"""
<div style="background:rgba(20,20,50,0.7);border:1px solid rgba(255,255,255,0.08);
            border-radius:12px;padding:16px 20px;margin-bottom:16px;">
  <div style="font-size:1rem;font-weight:700;color:#f0f4ff;margin-bottom:12px;">
    🧬 Roster Health Check
    <span style="font-size:0.8rem;font-weight:400;color:#718096;margin-left:8px;">
      {len(matched) + len(fuzzy_matched)}/{total} matched ({match_pct}%)
    </span>
  </div>
  {inner}
  <div style="font-size:0.75rem;color:#718096;margin-top:4px;">
    💡 Add fuzzy-matched names to the alias map for exact matching next time.
    Unmatched props use the prop line as the baseline projection.
  </div>
</div>"""


def get_platform_badge_html(platform):
    """
    Return a styled platform badge for PrizePicks, DraftKings, or Underdog.

    Args:
        platform (str): Platform name

    Returns:
        str: HTML span with platform-specific gradient and styling
    """
    platform_styles = {
        "PrizePicks": (
            "background:linear-gradient(135deg,#276749,#48bb78);color:#f0fff4;"
        ),
        "DraftKings": (
            "background:linear-gradient(135deg,#1a202c,#2b6cb0);color:#bee3f8;"
        ),
        "Underdog": (
            "background:linear-gradient(135deg,#44337a,#805ad5);color:#e9d8fd;"
        ),
    }
    style = platform_styles.get(
        platform,
        "background:rgba(45,55,72,0.9);color:#e2e8f0;",
    )
    return (
        f'<span style="{style}padding:3px 10px;border-radius:6px;'
        f'font-size:0.8rem;font-weight:700;display:inline-block;">{platform}</span>'
    )

# ============================================================
# END SECTION: HTML Component Generators
# ============================================================
