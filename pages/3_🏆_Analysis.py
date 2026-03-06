# ============================================================
# FILE: pages/3_🏆_Analysis.py
# PURPOSE: The main analysis page. Runs Monte Carlo simulation
#          for each prop and shows probability, edge, tier, and
#          directional forces. The heart of the application.
# CONNECTS TO: engine/ (all modules), data_manager.py, session state
# CONCEPTS COVERED: Monte Carlo simulation, edge detection,
#                   confidence scoring, results display
# ============================================================

import streamlit as st  # Main UI framework
import math             # For rounding in display

# Import our engine modules (all built from scratch!)
from engine.simulation import run_monte_carlo_simulation, build_histogram_from_results
from engine.projections import build_player_projection, get_stat_standard_deviation
from engine.edge_detection import analyze_directional_forces, should_avoid_prop
from engine.confidence import calculate_confidence_score, get_tier_color
from engine.math_helpers import calculate_edge_percentage, clamp_probability

# Import data loading functions
from data.data_manager import (
    load_players_data,
    load_defensive_ratings_data,
    load_teams_data,
    find_player_by_name,
    load_props_from_session,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Analysis — SmartAI-NBA",
    page_icon="🏆",
    layout="wide",
)

st.title("🏆 Analysis")
st.markdown("Run the Monte Carlo simulation to find the highest-probability picks.")
st.divider()

# ─── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
/* Analysis card */
.analysis-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #0f3460;
    border-radius: 12px;
    padding: 18px 22px;
    margin-bottom: 16px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.4);
}
/* Team badge in analysis card */
.team-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.85rem;
    color: #fff;
    background: #0f3460;
    margin-left: 6px;
    vertical-align: middle;
}
/* Tier badge */
.tier-platinum { background: linear-gradient(135deg,#7b2ff7,#9b59b6); color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:1rem; }
.tier-gold     { background: linear-gradient(135deg,#f39c12,#e67e22); color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:1rem; }
.tier-silver   { background: linear-gradient(135deg,#95a5a6,#7f8c8d); color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:1rem; }
.tier-bronze   { background: linear-gradient(135deg,#cd6836,#a04020); color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:1rem; }
/* Probability bar */
.prob-bar-wrap { background:#2d3748; border-radius:8px; height:14px; margin-top:4px; overflow:hidden; }
.prob-bar-fill-over  { background:linear-gradient(90deg,#48bb78,#38a169); height:100%; border-radius:8px; }
.prob-bar-fill-under { background:linear-gradient(90deg,#fc8181,#e53e3e); height:100%; border-radius:8px; }
/* Recent form dots */
.form-dot-over  { display:inline-block; width:12px; height:12px; border-radius:50%; background:#48bb78; margin:1px; }
.form-dot-under { display:inline-block; width:12px; height:12px; border-radius:50%; background:#fc8181; margin:1px; }
/* Stat chips */
.stat-chip {
    display:inline-block; background:#2d3748; border-radius:6px;
    padding:4px 10px; margin-right:8px; color:#e2e8f0; font-size:0.85rem;
}
/* Direction badge */
.dir-over  { background:#276749; color:#9ae6b4; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.9rem; }
.dir-under { background:#742a2a; color:#feb2b2; padding:3px 10px; border-radius:12px; font-weight:700; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Setup
# ============================================================


# ============================================================
# SECTION: Helper Functions
# IMPORTANT: These are defined FIRST so they can be called below.
# Python requires functions to be defined before they are called.
# ============================================================

def find_game_context_for_player(player_team, todays_games_list):
    """
    Find tonight's game context for a given team.

    Looks through todays_games to find the game this team is in.
    Returns a default context if no game found.

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
            # Player is on the home team
            return {
                "opponent": away_team,
                "is_home": True,
                "rest_days": 2,  # Default: 2 days rest
                "game_total": game.get("game_total", 220.0),
                "vegas_spread": game.get("vegas_spread", 0.0),
            }
        elif player_team == away_team:
            # Player is on the away team
            return {
                "opponent": home_team,
                "is_home": False,
                "rest_days": 2,
                "game_total": game.get("game_total", 220.0),
                "vegas_spread": -game.get("vegas_spread", 0.0),  # Flip for away
            }

    # No game found — return neutral defaults
    return {
        "opponent": "",
        "is_home": True,
        "rest_days": 2,
        "game_total": 220.0,
        "vegas_spread": 0.0,
    }


def display_prop_analysis_card(result):
    """
    Display a rich, visually styled analysis card for one prop result.

    Shows team badge, probability gauge, recent form dots, tier badge,
    and force breakdown in a dark-themed card.

    Args:
        result (dict): Full analysis result from the simulation loop
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

    # Season averages (from enriched prop data)
    pts_avg = result.get("season_pts_avg", result.get("points_avg", 0))
    reb_avg = result.get("season_reb_avg", result.get("rebounds_avg", 0))
    ast_avg = result.get("season_ast_avg", result.get("assists_avg", 0))

    # Probability percentage (in the direction we're betting)
    prob_pct = prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100
    direction_arrow = "⬆️" if direction == "OVER" else "⬇️"

    # Tier CSS class
    tier_class = {
        "Platinum": "tier-platinum",
        "Gold": "tier-gold",
        "Silver": "tier-silver",
        "Bronze": "tier-bronze",
    }.get(tier, "tier-bronze")

    # Direction CSS class
    dir_class = "dir-over" if direction == "OVER" else "dir-under"

    # Platform color
    platform_colors = {
        "PrizePicks": "#276749",
        "Underdog": "#553c9a",
        "DraftKings": "#2b6cb0",
    }
    plat_color = platform_colors.get(platform, "#2d3748")

    # Probability bar width
    bar_fill_class = "prob-bar-fill-over" if direction == "OVER" else "prob-bar-fill-under"
    bar_width = int(min(100, max(0, prob_pct)))

    # Team badge
    team_badge = f'<span class="team-pill">{team}</span>' if team else ""

    # Recent form dots (last 5 game results vs the line)
    recent_results = result.get("recent_form_results", [])
    form_dots_html = ""
    if recent_results:
        stat_key = stat.lower()
        stat_map = {"points": "pts", "rebounds": "reb", "assists": "ast",
                    "threes": "fg3m", "steals": "stl", "blocks": "blk", "turnovers": "tov"}
        mapped_key = stat_map.get(stat_key, "pts")
        for g in recent_results[:5]:
            val = g.get(mapped_key, g.get("pts", 0))
            if val >= line:
                form_dots_html += '<span class="form-dot-over" title="Over"></span>'
            else:
                form_dots_html += '<span class="form-dot-under" title="Under"></span>'

    # Over/under force counts
    over_forces = result.get("forces", {}).get("over_forces", [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    total_over_strength = sum(f.get("strength", 1) for f in over_forces)
    total_under_strength = sum(f.get("strength", 1) for f in under_forces)
    total_force = total_over_strength + total_under_strength or 1
    over_bar_pct = int(total_over_strength / total_force * 100)

    # Percentile display
    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)

    # Opponent info
    opponent = result.get("opponent", "")
    matchup_text = f"vs {opponent}" if opponent else ""

    # Line vs average context
    line_vs_avg = result.get("line_vs_avg_pct", 0)
    if line_vs_avg != 0:
        line_context = f"Line is {abs(line_vs_avg):.0f}% {'above' if line_vs_avg > 0 else 'below'} season avg"
    else:
        line_context = ""

    # Render the main card header
    st.markdown(f"""
<div class="analysis-card">
  <!-- Header row: player name + team badge + tier -->
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
    <div>
      <span style="font-size:1.25rem; font-weight:700; color:#e2e8f0;">{player}</span>
      {team_badge}
      {f'<span style="color:#718096; font-size:0.85rem; margin-left:8px;">{position}</span>' if position else ""}
    </div>
    <span class="{tier_class}">{tier_emoji} {tier}</span>
  </div>

  <!-- Stat type + platform + matchup -->
  <div style="margin-top:8px; display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
    <span style="background:{plat_color}; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:600;">{platform}</span>
    <span style="color:#a0aec0; font-size:0.9rem;">{stat} | Line: <strong style="color:#e2e8f0;">{line}</strong></span>
    {f'<span style="color:#718096; font-size:0.85rem;">{matchup_text}</span>' if matchup_text else ""}
    {f'<span style="color:#718096; font-size:0.8rem; font-style:italic;">{line_context}</span>' if line_context else ""}
  </div>

  <!-- Season stats chips -->
  {f"""<div style="margin-top:10px;">
    <span class="stat-chip">🏀 {pts_avg} PPG</span>
    <span class="stat-chip">📊 {reb_avg} RPG</span>
    <span class="stat-chip">🎯 {ast_avg} APG</span>
    <span class="stat-chip">📐 Proj: {proj}</span>
  </div>""" if pts_avg or reb_avg or ast_avg else ""}

  <!-- Probability gauge row -->
  <div style="margin-top:14px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
      <span class="{dir_class}">{direction_arrow} {direction}</span>
      <span style="color:#e2e8f0; font-weight:700; font-size:1.1rem;">{prob_pct:.1f}%</span>
      <span style="color:#718096; font-size:0.85rem;">Edge: <strong style="color:#68d391;">+{abs(edge):.1f}%</strong></span>
      <span style="color:#718096; font-size:0.85rem;">Confidence: <strong style="color:#e2e8f0;">{confidence:.0f}/100</strong></span>
    </div>
    <div class="prob-bar-wrap">
      <div class="{bar_fill_class}" style="width:{bar_width}%;"></div>
    </div>
  </div>

  <!-- Recent form dots + force bar -->
  <div style="margin-top:12px; display:flex; gap:20px; align-items:center; flex-wrap:wrap;">
    {f'''<div>
      <span style="color:#718096; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px;">Last 5 vs Line</span><br/>
      {form_dots_html}
    </div>''' if form_dots_html else ""}
    <div style="flex:1; min-width:160px;">
      <span style="color:#718096; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px;">Over/Under Forces</span>
      <div style="display:flex; margin-top:4px; height:8px; border-radius:4px; overflow:hidden; background:#2d3748;">
        <div style="width:{over_bar_pct}%; background:#48bb78;"></div>
        <div style="width:{100-over_bar_pct}%; background:#fc8181;"></div>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#718096; margin-top:2px;">
        <span>⬆️ OVER ({len(over_forces)})</span>
        <span>UNDER ({len(under_forces)}) ⬇️</span>
      </div>
    </div>
    <!-- Distribution range -->
    <div style="text-align:right;">
      <span style="color:#718096; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px;">Range</span><br/>
      <span style="color:#fc8181; font-size:0.8rem;">{p10:.1f}</span>
      <span style="color:#718096; font-size:0.8rem;"> — </span>
      <span style="color:#e2e8f0; font-size:0.8rem;">{p50:.1f}</span>
      <span style="color:#718096; font-size:0.8rem;"> — </span>
      <span style="color:#48bb78; font-size:0.8rem;">{p90:.1f}</span>
      <div style="color:#718096; font-size:0.7rem;">10th / 50th / 90th</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Detailed expander (forces breakdown, histogram)
    with st.expander(f"🔍 Full Breakdown — {player} {stat}"):
        detail_col1, detail_col2, detail_col3 = st.columns(3)

        with detail_col1:
            st.markdown("**📊 Distribution**")
            st.caption(f"10th pct (bad game): **{p10:.1f}**")
            st.caption(f"50th pct (median): **{p50:.1f}**")
            st.caption(f"90th pct (great game): **{p90:.1f}**")
            std = result.get("simulated_std", 0)
            st.caption(f"Simulated std dev: **{std:.1f}**")

            histogram = result.get("histogram", [])
            if histogram:
                max_count = max(b["count"] for b in histogram) or 1
                st.markdown("**Distribution (█ = over line)**")
                for bucket in histogram[-10:]:
                    bar_length = int((bucket["count"] / max_count) * 15)
                    bar_char = "█" if bucket["is_over_line"] else "░"
                    bar = bar_char * bar_length
                    st.caption(f"{bucket['bucket_label']:>5} {bar}")

        with detail_col2:
            st.markdown("**⬆️ Forces OVER**")
            if over_forces:
                for force in over_forces:
                    strength_stars = "⭐" * max(1, round(force.get("strength", 1)))
                    st.caption(f"{strength_stars} **{force['name']}**")
                    st.caption(f"   _{force['description']}_")
            else:
                st.caption("No OVER forces detected")

        with detail_col3:
            st.markdown("**⬇️ Forces UNDER**")
            if under_forces:
                for force in under_forces:
                    strength_stars = "⭐" * max(1, round(force.get("strength", 1)))
                    st.caption(f"{strength_stars} **{force['name']}**")
                    st.caption(f"   _{force['description']}_")
            else:
                st.caption("No UNDER forces detected")

        if result.get("should_avoid", False):
            st.warning("⚠️ **Avoid List:** " + " | ".join(result.get("avoid_reasons", [])))

        breakdown = result.get("score_breakdown", {})
        if breakdown:
            st.markdown("**🔬 Confidence Score Breakdown**")
            breakdown_cols = st.columns(len(breakdown))
            for i, (factor, score) in enumerate(breakdown.items()):
                with breakdown_cols[i]:
                    factor_label = factor.replace("_score", "").replace("_", " ").title()
                    st.metric(factor_label, f"{score:.0f}/100")


# ============================================================
# END SECTION: Helper Functions
# ============================================================


# ============================================================
# SECTION: Load All Required Data
# ============================================================

# Load all the CSV data files once (these are small, fast)
players_data = load_players_data()
teams_data = load_teams_data()
defensive_ratings_data = load_defensive_ratings_data()

# Get current props and games from session state
current_props = load_props_from_session(st.session_state)
todays_games = st.session_state.get("todays_games", [])

# Get settings from session state
simulation_depth = st.session_state.get("simulation_depth", 1000)
minimum_edge = st.session_state.get("minimum_edge_threshold", 5.0)

# ============================================================
# END SECTION: Load All Required Data
# ============================================================

# ============================================================
# SECTION: Pre-Run Status Check
# Show what data is available before running analysis
# ============================================================

status_col, settings_col = st.columns([2, 1])

with status_col:
    # Show how many props are loaded
    if current_props:
        st.info(f"📋 **{len(current_props)} props** loaded and ready for analysis.")
    else:
        st.warning("⚠️ No props loaded. Go to **📥 Import Props** first.")

    if todays_games:
        st.success(f"🏟️ **{len(todays_games)} game(s)** configured for tonight.")
    else:
        st.caption("💡 No games configured — using default (neutral) game context.")

with settings_col:
    st.caption(f"⚙️ Simulations: **{simulation_depth:,}**")
    st.caption(f"⚙️ Min Edge: **{minimum_edge}%**")
    st.caption("Change on the ⚙️ Settings page")

# ============================================================
# END SECTION: Pre-Run Status Check
# ============================================================

st.divider()

# ============================================================
# SECTION: Analysis Runner
# The "Run Analysis" button triggers the full simulation loop
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
    # Filter options for the results
    show_all_or_top = st.radio(
        "Show:",
        ["All picks", "Top picks only (edge ≥ threshold)"],
        horizontal=True,
        index=1,  # Default to top picks
    )

if run_analysis:
    # ============================================================
    # SECTION: Run the Simulation Loop
    # Loop through every prop and run full analysis
    # ============================================================

    # Progress bar to show the user something is happening
    progress_bar = st.progress(0, text="Starting analysis...")

    analysis_results_list = []  # Will hold all results

    # How many props total (used for progress calculation)
    total_props_count = len(current_props)

    for prop_index, prop in enumerate(current_props):
        # Update the progress bar
        # BEGINNER NOTE: (index + 1) / total gives 0-1 progress fraction
        progress_fraction = (prop_index + 1) / total_props_count
        progress_bar.progress(
            progress_fraction,
            text=f"Analyzing {prop.get('player_name', 'Player')}... ({prop_index + 1}/{total_props_count})"
        )

        # Step 1: Get player data from our database
        player_name = prop.get("player_name", "")
        stat_type = prop.get("stat_type", "points").lower()
        prop_line = float(prop.get("line", 0))
        platform = prop.get("platform", "PrizePicks")

        # Find the player in our player database
        player_data = find_player_by_name(players_data, player_name)

        if player_data is None:
            # Player not in our database — create generic data from the line
            player_data = {
                "name": player_name,
                "team": prop.get("team", ""),
                "position": "SF",  # Default position
                f"{stat_type}_avg": str(prop_line),
                f"{stat_type}_std": str(prop_line * 0.35),
            }

        # Step 2: Find tonight's game context for this player
        player_team = player_data.get("team", prop.get("team", ""))
        game_context = find_game_context_for_player(player_team, todays_games)

        # Step 3: Build the projection (adjusted for tonight)
        projection_result = build_player_projection(
            player_data=player_data,
            opponent_team_abbreviation=game_context.get("opponent", ""),
            is_home_game=game_context.get("is_home", True),
            rest_days=game_context.get("rest_days", 2),
            game_total=game_context.get("game_total", 220.0),
            defensive_ratings_data=defensive_ratings_data,
            teams_data=teams_data,
        )

        # Step 4: Run Monte Carlo simulation
        stat_std = get_stat_standard_deviation(player_data, stat_type)
        # Get projected value for this stat type; fall back to the line if unknown
        projected_stat = projection_result.get(
            f"projected_{stat_type}",
            float(player_data.get(f"{stat_type}_avg", prop_line))
        )

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
        )

        # Step 5: Analyze directional forces
        forces_result = analyze_directional_forces(
            player_data=player_data,
            prop_line=prop_line,
            stat_type=stat_type,
            projection_result=projection_result,
            game_context=game_context,
        )

        # Step 6: Calculate edge and confidence
        probability_over = simulation_output.get("probability_over", 0.5)
        edge_pct = calculate_edge_percentage(probability_over)

        confidence_output = calculate_confidence_score(
            probability_over=probability_over,
            edge_percentage=edge_pct,
            directional_forces=forces_result,
            defense_factor=projection_result.get("defense_factor", 1.0),
            stat_standard_deviation=stat_std,
            stat_average=float(player_data.get(f"{stat_type}_avg", prop_line)),
            simulation_results=simulation_output,
        )

        # Step 7: Check if this should be on the avoid list
        should_avoid, avoid_reasons = should_avoid_prop(
            probability_over=probability_over,
            directional_forces_result=forces_result,
            edge_percentage=edge_pct,
            stat_standard_deviation=stat_std,
            stat_average=float(player_data.get(f"{stat_type}_avg", prop_line)),
        )

        # Step 8: Build the histogram for charting
        histogram_data = build_histogram_from_results(
            simulation_output.get("simulated_results", []),
            prop_line,
            number_of_buckets=15,
        )

        # Step 9: Compile the full result
        full_result = {
            # Basic prop info
            "player_name": player_name,
            "team": player_team,
            "player_team": player_team,
            "player_position": player_data.get("position", ""),
            "stat_type": stat_type,
            "line": prop_line,
            "platform": platform,
            # Season averages for display
            "season_pts_avg": float(player_data.get("points_avg", 0) or 0),
            "season_reb_avg": float(player_data.get("rebounds_avg", 0) or 0),
            "season_ast_avg": float(player_data.get("assists_avg", 0) or 0),
            "points_avg": float(player_data.get("points_avg", 0) or 0),
            "rebounds_avg": float(player_data.get("rebounds_avg", 0) or 0),
            "assists_avg": float(player_data.get("assists_avg", 0) or 0),
            # Opponent context
            "opponent": game_context.get("opponent", ""),
            # Simulation results
            "probability_over": round(probability_over, 4),
            "probability_under": round(1.0 - probability_over, 4),
            "simulated_mean": round(simulation_output.get("simulated_mean", 0), 1),
            "simulated_std": round(simulation_output.get("simulated_std", 0), 1),
            "percentile_10": round(simulation_output.get("percentile_10", 0), 1),
            "percentile_50": round(simulation_output.get("percentile_50", 0), 1),
            "percentile_90": round(simulation_output.get("percentile_90", 0), 1),
            # Projection info
            "adjusted_projection": round(projected_stat, 1),
            "overall_adjustment": round(projection_result.get("overall_adjustment", 1.0), 3),
            # Edge and confidence
            "edge_percentage": round(edge_pct, 1),
            "confidence_score": confidence_output.get("confidence_score", 50),
            "tier": confidence_output.get("tier", "Bronze"),
            "tier_emoji": confidence_output.get("tier_emoji", "🥉"),
            "direction": confidence_output.get("direction", "OVER"),
            "recommendation": confidence_output.get("recommendation", ""),
            # Forces
            "forces": forces_result,
            # Avoid list
            "should_avoid": should_avoid,
            "avoid_reasons": avoid_reasons,
            # Chart data
            "histogram": histogram_data,
            # Score breakdown (for transparency)
            "score_breakdown": confidence_output.get("score_breakdown", {}),
            # Line vs season average
            "line_vs_avg_pct": prop.get("line_vs_avg_pct", 0),
            # Recent form game results (if available in enriched prop)
            "recent_form_results": prop.get("recent_form_results", []),
        }

        analysis_results_list.append(full_result)

    # Save results to session state
    st.session_state["analysis_results"] = analysis_results_list

    # Clear the progress bar
    progress_bar.empty()

    st.success(f"✅ Analysis complete! {len(analysis_results_list)} props analyzed.")
    st.rerun()  # Refresh to show results

    # ============================================================
    # END SECTION: Run the Simulation Loop
    # ============================================================


# ============================================================
# SECTION: Display Analysis Results
# Show the results if analysis has been run
# ============================================================

analysis_results = st.session_state.get("analysis_results", [])

if analysis_results:
    st.divider()

    # Filter results based on user selection
    if show_all_or_top == "Top picks only (edge ≥ threshold)":
        # Only show picks with meaningful edge in either direction
        displayed_results = [
            r for r in analysis_results
            if abs(r.get("edge_percentage", 0)) >= minimum_edge
            and not r.get("should_avoid", False)
        ]
    else:
        displayed_results = analysis_results

    # Sort by confidence score (highest first)
    displayed_results.sort(
        key=lambda r: r.get("confidence_score", 0),
        reverse=True
    )

    # Summary metrics
    total_analyzed = len(analysis_results)
    total_over_picks = sum(1 for r in displayed_results if r.get("direction") == "OVER")
    total_under_picks = sum(1 for r in displayed_results if r.get("direction") == "UNDER")
    platinum_count = sum(1 for r in displayed_results if r.get("tier") == "Platinum")
    gold_count = sum(1 for r in displayed_results if r.get("tier") == "Gold")

    st.subheader(f"📊 Results: {len(displayed_results)} picks shown (of {total_analyzed} analyzed)")

    # Summary row
    sum_col1, sum_col2, sum_col3, sum_col4, sum_col5 = st.columns(5)
    sum_col1.metric("Showing", len(displayed_results))
    sum_col2.metric("⬆️ OVER", total_over_picks)
    sum_col3.metric("⬇️ UNDER", total_under_picks)
    sum_col4.metric("💎 Platinum", platinum_count)
    sum_col5.metric("🥇 Gold", gold_count)

    st.divider()

    # Display each result card
    for result in displayed_results:
        display_prop_analysis_card(result)
        st.markdown("---")  # Divider between cards

elif not run_analysis:
    # Show message if no results and analysis hasn't been run
    if current_props:
        st.info("👆 Click **Run Analysis** to analyze all loaded props.")
    else:
        st.warning("⚠️ No props loaded. Go to **📥 Import Props** to add props first.")

# ============================================================
# END SECTION: Display Analysis Results
# ============================================================
