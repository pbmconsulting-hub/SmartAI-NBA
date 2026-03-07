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
from engine.edge_detection import analyze_directional_forces, should_avoid_prop, detect_correlated_props
from engine.confidence import calculate_confidence_score, get_tier_color
from engine.math_helpers import calculate_edge_percentage, clamp_probability
from engine.explainer import generate_pick_explanation

# Import data loading functions
from data.data_manager import (
    load_players_data,
    load_defensive_ratings_data,
    load_teams_data,
    find_player_by_name,
    load_props_from_session,
    get_roster_health_report,
    validate_props_against_roster,
)

# Import the theme helpers
from styles.theme import (
    get_global_css,
    get_player_card_html,
    get_best_bets_section_html,
    get_roster_health_html,
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

# ─── Inject Global CSS Theme ──────────────────────────────────
st.markdown(get_global_css(), unsafe_allow_html=True)

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

    Uses the theme module's get_player_card_html() for the main card,
    then adds an expandable section with full forces breakdown.

    Args:
        result (dict): Full analysis result from the simulation loop
    """
    player = result.get("player_name", "Unknown")
    stat = result.get("stat_type", "").capitalize()

    # Render the styled card via theme module
    st.markdown(get_player_card_html(result), unsafe_allow_html=True)

    # Get force/distribution data for the expander
    over_forces = result.get("forces", {}).get("over_forces", [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)

    # Detailed expander (forces breakdown, histogram)
    with st.expander(f"\U0001f50d Full Breakdown — {player} {stat}"):
        detail_col1, detail_col2, detail_col3 = st.columns(3)

        with detail_col1:
            st.markdown("**\U0001f4ca Distribution**")
            st.caption(f"10th pct (bad game): **{p10:.1f}**")
            st.caption(f"50th pct (median): **{p50:.1f}**")
            st.caption(f"90th pct (great game): **{p90:.1f}**")
            std = result.get("simulated_std", 0)
            st.caption(f"Simulated std dev: **{std:.1f}**")

            histogram = result.get("histogram", [])
            if histogram:
                max_count = max(b["count"] for b in histogram) or 1
                st.markdown("**Distribution (\u2588 = over line)**")
                for bucket in histogram[-10:]:
                    bar_length = int((bucket["count"] / max_count) * 15)
                    bar_char = "\u2588" if bucket["is_over_line"] else "\u2591"
                    bar = bar_char * bar_length
                    st.caption(f"{bucket['bucket_label']:>5} {bar}")

            # Recent form info
            form_ratio = result.get("recent_form_ratio")
            if form_ratio is not None:
                form_label = "Hot \U0001f525" if form_ratio > 1.05 else ("Cold \U0001f9ca" if form_ratio < 0.95 else "Neutral")
                st.caption(f"Recent form: **{form_ratio:.2f}x** ({form_label})")

            # Games played sample size
            games_played = result.get("games_played")
            if games_played:
                st.caption(f"Games played: **{games_played}**")

        with detail_col2:
            st.markdown("**\u2b06\ufe0f Forces OVER**")
            if over_forces:
                for force in over_forces:
                    strength_stars = "\u2b50" * max(1, round(force.get("strength", 1)))
                    st.caption(f"{strength_stars} **{force['name']}**")
                    st.caption(f"   _{force['description']}_")
            else:
                st.caption("No OVER forces detected")

        with detail_col3:
            st.markdown("**\u2b07\ufe0f Forces UNDER**")
            if under_forces:
                for force in under_forces:
                    strength_stars = "\u2b50" * max(1, round(force.get("strength", 1)))
                    st.caption(f"{strength_stars} **{force['name']}**")
                    st.caption(f"   _{force['description']}_")
            else:
                st.caption("No UNDER forces detected")

        if result.get("should_avoid", False):
            st.warning("\u26a0\ufe0f **Avoid List:** " + " | ".join(result.get("avoid_reasons", [])))

        breakdown = result.get("score_breakdown", {})
        if breakdown:
            st.markdown("**\U0001f52c Confidence Score Breakdown**")
            breakdown_cols = st.columns(len(breakdown))
            for i, (factor, score) in enumerate(breakdown.items()):
                with breakdown_cols[i]:
                    factor_label = factor.replace("_score", "").replace("_", " ").title()
                    st.metric(factor_label, f"{score:.0f}/100")

        # ── Why This Pick explanation ────────────────────────────
        explanation = result.get("explanation")
        if explanation:
            st.divider()
            st.markdown("**💡 Why This Pick**")

            # TL;DR
            st.info(explanation.get("tldr", ""))

            # Indicators row
            indicators = explanation.get("indicators", [])
            if indicators:
                ind_cols = st.columns(min(len(indicators), 4))
                for j, ind in enumerate(indicators[:4]):
                    with ind_cols[j % len(ind_cols)]:
                        emoji = ind.get("emoji", "⚪")
                        factor = ind.get("factor", "")
                        st.caption(f"{emoji} **{factor}**")

            # Section details
            sections = [
                ("📊 Season Avg vs Line", "average_vs_line"),
                ("🛡️ Matchup Analysis", "matchup_explanation"),
                ("⚡ Game Pace", "pace_explanation"),
                ("🏠 Home/Away", "home_away_explanation"),
                ("😴 Rest Days", "rest_explanation"),
                ("💰 Vegas Lines", "vegas_explanation"),
                ("📐 Projection", "projection_explanation"),
                ("🎲 Simulation", "simulation_narrative"),
                ("⚖️ Forces", "forces_summary"),
                ("🔥 Recent Form", "recent_form_explanation"),
            ]
            for label, key in sections:
                text = explanation.get(key, "")
                if text:
                    st.caption(f"**{label}:** {text}")

            # Risk factors
            risks = explanation.get("risk_factors", [])
            if risks:
                st.markdown("**⚠️ Risk Factors:**")
                for risk in risks:
                    st.caption(f"  {risk}")

            # Verdict
            verdict = explanation.get("verdict", "")
            if verdict:
                st.markdown(f"**🏁 Verdict:** {verdict}")


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

    # Roster health check
    if current_props and players_data:
        validation = validate_props_against_roster(current_props, players_data)
        total = validation["total"]
        matched_count = validation["matched_count"]

        if validation["unmatched"] or validation["fuzzy_matched"]:
            with st.expander(
                f"⚠️ Roster Health: {matched_count}/{total} players matched "
                f"({int(matched_count/max(total,1)*100)}%) — click to see details"
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

        # Find the player in our player database (uses fuzzy/normalized matching)
        player_data = find_player_by_name(players_data, player_name)
        player_matched = player_data is not None

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
        # Pass recent form game logs if available from the prop
        recent_form_games = prop.get("recent_form_results", [])
        projection_result = build_player_projection(
            player_data=player_data,
            opponent_team_abbreviation=game_context.get("opponent", ""),
            is_home_game=game_context.get("is_home", True),
            rest_days=game_context.get("rest_days", 2),
            game_total=game_context.get("game_total", 220.0),
            defensive_ratings_data=defensive_ratings_data,
            teams_data=teams_data,
            recent_form_games=recent_form_games if recent_form_games else None,
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
            games_played=int(player_data.get("games_played", 0) or 0) or None,
            recent_form_ratio=projection_result.get("recent_form_ratio"),
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

        # Step 9: Generate "Why This Pick" explanation
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
            should_avoid=should_avoid,
            avoid_reasons=avoid_reasons,
        )

        # Step 10: Compile the full result
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
            "recent_form_ratio": projection_result.get("recent_form_ratio"),
            # Sample size
            "games_played": int(player_data.get("games_played", 0) or 0) or None,
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
            # Whether player was found in the database
            "player_matched": player_matched,
            # Why This Pick explanation
            "explanation": explanation,
        }

        analysis_results_list.append(full_result)

    # Step 10: Detect correlated props (same-game pairs)
    correlation_warnings = detect_correlated_props(analysis_results_list)
    for idx, warning in correlation_warnings.items():
        if idx < len(analysis_results_list):
            analysis_results_list[idx]["_correlation_warning"] = warning

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
    avg_edge = (
        sum(abs(r.get("edge_percentage", 0)) for r in displayed_results) / len(displayed_results)
        if displayed_results else 0
    )
    unmatched_count = sum(1 for r in analysis_results if not r.get("player_matched", True))

    st.subheader(f"📊 Results: {len(displayed_results)} picks shown (of {total_analyzed} analyzed)")

    # Summary row
    sum_col1, sum_col2, sum_col3, sum_col4, sum_col5 = st.columns(5)
    sum_col1.metric("Showing", len(displayed_results))
    sum_col2.metric("⬆️ OVER", total_over_picks)
    sum_col3.metric("⬇️ UNDER", total_under_picks)
    sum_col4.metric("💎 Platinum", platinum_count)
    sum_col5.metric("🥇 Gold", gold_count)

    # Unmatched player warning
    if unmatched_count > 0:
        unmatched_names = [r.get("player_name", "") for r in analysis_results if not r.get("player_matched", True)]
        st.warning(
            f"⚠️ **{unmatched_count} player(s) not found** in database and used fallback data: "
            + ", ".join(unmatched_names)
            + " — results for these may be less accurate."
        )

    st.divider()

    # Best Bets summary (top 5 by confidence, non-avoid picks)
    best_bets = [
        r for r in analysis_results
        if not r.get("should_avoid", False) and abs(r.get("edge_percentage", 0)) >= minimum_edge
    ]
    best_bets.sort(key=lambda r: r.get("confidence_score", 0), reverse=True)
    if best_bets[:5]:
        st.markdown(get_best_bets_section_html(best_bets[:5]), unsafe_allow_html=True)
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
