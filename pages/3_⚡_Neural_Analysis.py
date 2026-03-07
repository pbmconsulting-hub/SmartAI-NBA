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
from engine.edge_detection import analyze_directional_forces, should_avoid_prop, detect_correlated_props, detect_trap_line, detect_line_sharpness
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
    get_player_status,
    get_status_badge_html,
    load_injury_status,
)

# Import the theme helpers
from styles.theme import (
    get_global_css,
    get_player_card_html,
    get_best_bets_section_html,
    get_roster_health_html,
    get_neural_header_html,
    get_ai_verdict_card_html,
    get_education_box_html,
    get_signal_strength_bar_html,
    get_progress_ring_html,
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

st.title("⚡ Neural Analysis")
st.markdown("Run the Monte Carlo simulation to find the highest-probability picks.")
st.divider()

# ─── Inject Global CSS Theme ──────────────────────────────────
st.markdown(get_global_css(), unsafe_allow_html=True)

# ─── Session State Initialization ────────────────────────────
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "injury_status_map" not in st.session_state:
    # Auto-load persisted injury status from disk on first visit so the
    # Analysis page always has the latest status without a manual refresh.
    st.session_state["injury_status_map"] = load_injury_status()

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
    Display a redesigned analysis card for one prop result.

    Shows an AI verdict, player status badge, key numbers grid,
    signal-strength edge bar, confidence ring, plain-English summary,
    and an "Add to Entry" button. Keeps a detailed expander with the
    full forces breakdown.

    OUT/IR players show a prominent ❌ warning and skip the simulation
    display entirely. Questionable/Day-to-Day players show a ⚠️ badge.

    Args:
        result (dict): Full analysis result from the simulation loop
    """
    player = result.get("player_name", "Unknown")
    stat = result.get("stat_type", "").capitalize()
    line = result.get("line", 0)
    direction = result.get("direction", "OVER")
    confidence = result.get("confidence_score", 50)
    should_avoid = result.get("should_avoid", False)
    edge_pct = result.get("edge_percentage", 0)
    platform = result.get("platform", "")
    opponent = result.get("opponent", "")

    # ── OUT / Injured Reserve players — show banner and stop ─────
    if result.get("player_is_out", False):
        player_status = result.get("player_status", "Out")
        status_note = result.get("player_status_note", "")
        st.error(
            f"❌ **{player}** is **{player_status}** — prop skipped. "
            + (f"_{status_note}_" if status_note else "")
            + "\n\nRemove this prop from your list."
        )
        return  # Nothing more to display for an inactive player

    # ── AI Verdict ──────────────────────────────────────────────
    if confidence >= 65 and not should_avoid:
        verdict_key = "BET"
        verdict_text = "STRONG BET ✅"
        style = "bet"
    elif should_avoid or confidence < 40:
        verdict_key = "AVOID"
        verdict_text = "AVOID ❌"
        style = "avoid"
    else:
        verdict_key = "RISKY"
        verdict_text = "RISKY ⚠️"
        style = "risky"

    tldr = result.get("explanation", {}).get("tldr", "") if result.get("explanation") else ""
    st.markdown(
        get_ai_verdict_card_html(verdict_key, confidence, tldr or result.get("recommendation", "")),
        unsafe_allow_html=True,
    )

    # ── Player header row ────────────────────────────────────────
    header_col, badge_col = st.columns([3, 1])
    with header_col:
        tier_emoji = result.get("tier_emoji", "🥉")
        tier = result.get("tier", "Bronze")
        opp_str = f" · vs {opponent}" if opponent else ""
        plat_str = f" · {platform}" if platform else ""
        st.markdown(
            f"**{player}** &nbsp; {tier_emoji} {tier}{opp_str}{plat_str}",
            unsafe_allow_html=True,
        )
    with badge_col:
        # Use status already resolved during the simulation loop when available,
        # otherwise fall back to a live lookup in the session map.
        player_status = result.get("player_status") or (
            get_player_status(player, st.session_state.get("injury_status_map", {})).get("status", "Active")
        )
        st.markdown(get_status_badge_html(player_status), unsafe_allow_html=True)

        # Show ⚠️ inline note for Questionable / Day-to-Day
        if player_status in ("Questionable", "Day-to-Day"):
            note = result.get("player_status_note", "")
            if note:
                st.caption(f"⚠️ {note}")

    # ── Key Numbers grid ─────────────────────────────────────────
    stat_type_lower = result.get("stat_type", "points").lower()
    stat_label_map = {
        "points": "PPG", "rebounds": "RPG", "assists": "APG", "threes": "3PM",
    }
    stat_label = stat_label_map.get(stat_type_lower, stat_type_lower.upper())

    avg_key_map = {
        "points": "season_pts_avg", "rebounds": "season_reb_avg",
        "assists": "season_ast_avg", "threes": "season_threes_avg",
    }
    season_avg = result.get(avg_key_map.get(stat_type_lower, ""), 0) or 0
    projected = result.get("adjusted_projection") or result.get("projected_stat") or 0

    num_col1, num_col2, num_col3 = st.columns(3)
    with num_col1:
        st.metric(f"Season Avg ({stat_label})", f"{season_avg:.1f}")
    with num_col2:
        st.metric("Projected", f"{projected:.1f}")
    with num_col3:
        st.metric("Prop Line", f"{line}")

    # ── Edge signal bar + Confidence ring ────────────────────────
    vis_col1, vis_col2 = st.columns([2, 1])
    with vis_col1:
        edge_norm = min(1.0, abs(edge_pct) / 30.0)
        edge_sign = "+" if edge_pct >= 0 else ""
        st.markdown(
            get_signal_strength_bar_html(edge_norm, f"Edge: {edge_sign}{edge_pct:.1f}%"),
            unsafe_allow_html=True,
        )
    with vis_col2:
        st.markdown(
            get_progress_ring_html(confidence, "Confidence"),
            unsafe_allow_html=True,
        )

    # ── Add to Entry button ──────────────────────────────────────
    pick_key = f"{player}_{stat_type_lower}_{line}_{direction}"
    selected_picks = st.session_state.get("selected_picks", [])
    already_added = any(p.get("key") == pick_key for p in selected_picks)

    btn_label = "✅ Added" if already_added else "➕ Add to Entry"
    btn_disabled = already_added
    if st.button(btn_label, key=f"add_pick_{pick_key}", disabled=btn_disabled):
        st.session_state["selected_picks"].append({
            "key": pick_key,
            "player_name": player,
            "stat_type": stat_type_lower,
            "line": line,
            "direction": direction,
            "confidence_score": confidence,
            "tier": tier,
            "tier_emoji": tier_emoji,
            "platform": platform,
            "edge_percentage": edge_pct,
        })
        st.rerun()

    # ── Detailed expander (forces breakdown) ─────────────────────
    over_forces = result.get("forces", {}).get("over_forces", [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)

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

            form_ratio = result.get("recent_form_ratio")
            if form_ratio is not None:
                form_label = "Hot 🔥" if form_ratio > 1.05 else ("Cold 🧊" if form_ratio < 0.95 else "Neutral")
                st.caption(f"Recent form: **{form_ratio:.2f}x** ({form_label})")

            games_played = result.get("games_played")
            if games_played:
                st.caption(f"Games played: **{games_played}**")

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

        if should_avoid:
            st.warning("⚠️ **Avoid List:** " + " | ".join(result.get("avoid_reasons", [])))

        trap_result = result.get("trap_line_result", {})
        if trap_result and trap_result.get("is_trap"):
            st.error(trap_result.get("warning_message", "⚠️ Possible Trap Line detected"))

        sharpness_force = result.get("line_sharpness_force")
        if sharpness_force:
            st.caption(
                f"📐 **Sharp Line:** {sharpness_force.get('description', '')} "
                f"(−{result.get('line_sharpness_penalty', 0):.0f} confidence pts)"
            )

        teammate_notes = result.get("teammate_out_notes", [])
        if teammate_notes:
            st.info("👥 **Teammate Impact:** " + " | ".join(teammate_notes))

        breakdown = result.get("score_breakdown", {})
        if breakdown:
            st.markdown("**🔬 Confidence Score Breakdown**")
            breakdown_cols = st.columns(len(breakdown))
            for i, (factor, score) in enumerate(breakdown.items()):
                with breakdown_cols[i]:
                    factor_label = factor.replace("_score", "").replace("_", " ").title()
                    st.metric(factor_label, f"{score:.0f}/100")

        explanation = result.get("explanation")
        if explanation:
            st.divider()
            st.markdown("**💡 Why This Pick**")

            indicators = explanation.get("indicators", [])
            if indicators:
                ind_cols = st.columns(min(len(indicators), 4))
                for j, ind in enumerate(indicators[:4]):
                    with ind_cols[j % len(ind_cols)]:
                        emoji = ind.get("emoji", "⚪")
                        factor = ind.get("factor", "")
                        st.caption(f"{emoji} **{factor}**")

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
                ("📐 Line Sharpness", "line_sharpness_explanation"),
                ("⚠️ Trap Line", "trap_line_explanation"),
                ("👥 Teammate Impact", "teammate_impact_explanation"),
            ]
            for label, key in sections:
                text = explanation.get(key, "")
                if text:
                    st.caption(f"**{label}:** {text}")

            risks = explanation.get("risk_factors", [])
            if risks:
                st.markdown("**⚠️ Risk Factors:**")
                for risk in risks:
                    st.caption(f"  {risk}")

            verdict_text_exp = explanation.get("verdict", "")
            if verdict_text_exp:
                st.markdown(f"**🏁 Verdict:** {verdict_text_exp}")


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

# ── Educational section ────────────────────────────────────────
st.markdown(get_education_box_html(
    "📖 How Neural Analysis Works",
    """
    <strong>Monte Carlo Simulation</strong>: We run 2,000 simulated games for each player,
    using their season averages adjusted for tonight's matchup, pace, rest, and home/away factors.<br><br>
    <strong>Edge</strong>: The gap between what our model predicts and what the prop line implies.
    An edge of +10% means we think the player has a 10% better chance of hitting than the line suggests.<br><br>
    <strong>Confidence Tiers</strong>: 💎 Platinum (80+), 🥇 Gold (65-79), 🥈 Silver (50-64), 🥉 Bronze (below 50).
    """
), unsafe_allow_html=True)

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

        # ── Injury / availability gate ────────────────────────────
        # Check the player's status BEFORE running the simulation.
        # If the player is Out or on IR, skip the full simulation and
        # add a minimal "Out" result so the UI can display a clear warning.
        injury_map = st.session_state.get("injury_status_map", {})
        player_status_info = get_player_status(player_name, injury_map)
        player_status = player_status_info.get("status", "Active")

        if player_status in ("Out", "Injured Reserve"):
            injury_note = player_status_info.get("injury_note", "Player is not active")
            analysis_results_list.append({
                "player_name": player_name,
                "team": prop.get("team", ""),
                "player_team": prop.get("team", ""),
                "player_position": "",
                "stat_type": stat_type,
                "line": prop_line,
                "platform": platform,
                "season_pts_avg": 0,
                "season_reb_avg": 0,
                "season_ast_avg": 0,
                "points_avg": 0,
                "rebounds_avg": 0,
                "assists_avg": 0,
                "opponent": "",
                "probability_over": 0.0,
                "probability_under": 1.0,
                "simulated_mean": 0.0,
                "simulated_std": 0.0,
                "percentile_10": 0.0,
                "percentile_50": 0.0,
                "percentile_90": 0.0,
                "adjusted_projection": 0.0,
                "overall_adjustment": 1.0,
                "recent_form_ratio": None,
                "games_played": None,
                "edge_percentage": -50.0,
                "confidence_score": 0,
                "tier": "Bronze",
                "tier_emoji": "🥉",
                "direction": "UNDER",
                "recommendation": f"SKIP — {player_name} is {player_status}",
                "forces": {"over_forces": [], "under_forces": []},
                "should_avoid": True,
                "avoid_reasons": [f"Player is {player_status}: {injury_note}"],
                "histogram": [],
                "score_breakdown": {},
                "line_vs_avg_pct": 0,
                "recent_form_results": [],
                "player_matched": False,
                "explanation": None,
                "line_sharpness_force": None,
                "line_sharpness_penalty": 0.0,
                "trap_line_result": {},
                "trap_line_penalty": 0.0,
                "teammate_out_notes": [],
                "minutes_adjustment_factor": 1.0,
                # Mark explicitly so display logic can show the ❌ OUT badge
                "player_is_out": True,
                "player_status": player_status,
                "player_status_note": injury_note,
            })
            continue  # Skip to next prop — no simulation needed

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
            vegas_spread=game_context.get("vegas_spread", 0.0),  # W6: smart blowout risk
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

        # Step 5b: Detect line sharpness (W1) — is the line priced at true average?
        season_avg_for_stat = float(player_data.get(f"{stat_type}_avg", 0) or 0)
        line_sharpness_force = detect_line_sharpness(
            prop_line=prop_line,
            season_average=season_avg_for_stat if season_avg_for_stat > 0 else None,
            stat_type=stat_type,
        )
        # Extract penalty from the line sharpness force if present
        line_sharpness_penalty = 0.0
        if line_sharpness_force is not None:
            # Strength 0-3 maps to penalty 0-8 points
            line_sharpness_penalty = min(8.0, line_sharpness_force.get("strength", 0) * 2.5)

        # Step 5c: Detect trap lines (W5)
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

        # Step 6: Calculate edge and confidence
        probability_over = simulation_output.get("probability_over", 0.5)
        edge_pct = calculate_edge_percentage(probability_over)

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
            line_sharpness_penalty=line_sharpness_penalty,   # W1
            trap_line_penalty=trap_line_penalty,             # W5
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
            trap_line_result=trap_line_result,              # W5
            line_sharpness_info=line_sharpness_force,       # W1
            teammate_out_notes=projection_result.get("teammate_out_notes", []),  # W8
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
            # Player ID for headshot lookup (from players CSV if available)
            "player_id": player_data.get("player_id", ""),
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
            # W1: Line sharpness info
            "line_sharpness_force": line_sharpness_force,
            "line_sharpness_penalty": round(line_sharpness_penalty, 1),
            # W5: Trap line info
            "trap_line_result": trap_line_result,
            "trap_line_penalty": round(trap_line_penalty, 1),
            # W8: Teammate impact info
            "teammate_out_notes": projection_result.get("teammate_out_notes", []),
            "minutes_adjustment_factor": round(projection_result.get("minutes_adjustment_factor", 1.0), 4),
            # Injury / availability status for this player
            "player_is_out": False,
            "player_status": player_status,
            "player_status_note": player_status_info.get("injury_note", ""),
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

    # ── Floating selected-picks counter ───────────────────────────
    selected_count = len(st.session_state.get("selected_picks", []))
    if selected_count > 0:
        st.success(
            f"✅ {selected_count} pick(s) selected for Entry Builder → "
            "Go to 🧬 Entry Builder to build your entry!"
        )

    # ── Clear picks button ────────────────────────────────────────
    if st.session_state.get("selected_picks"):
        if st.button("🗑️ Clear Selected Picks"):
            st.session_state["selected_picks"] = []
            st.rerun()

elif not run_analysis:
    # Show message if no results and analysis hasn't been run
    if current_props:
        st.info("👆 Click **Run Analysis** to analyze all loaded props.")
    else:
        st.warning("⚠️ No props loaded. Go to **📥 Import Props** to add props first.")

# ============================================================
# END SECTION: Display Analysis Results
# ============================================================
