# ============================================================
# FILE: pages/2_📥_Import_Props.py
# PURPOSE: Allow users to enter prop lines manually or upload
#          a CSV file. Stores props in session state for Analysis.
# CONNECTS TO: data_manager.py (load/save), Analysis page
# CONCEPTS COVERED: Forms, file upload, data tables, CSV parsing
# ============================================================

import streamlit as st  # Main UI framework
import datetime         # For today's date

# Import our data manager functions
from data.data_manager import (
    load_players_data,
    load_props_data,
    load_props_from_session,
    save_props_to_session,
    get_all_player_names,
    parse_props_from_csv_text,
    get_csv_template,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Import Props — SmartAI-NBA",
    page_icon="📥",
    layout="wide",
)

st.title("📥 Import Props")
st.markdown("Enter prop lines manually or upload a CSV. Sample props are pre-loaded!")
st.divider()

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Load Available Data
# ============================================================

# Load player data to provide a dropdown for player names
players_data = load_players_data()
all_player_names = get_all_player_names(players_data)

# Valid stat types the model supports
valid_stat_types = ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"]

# Valid platforms
valid_platforms = ["PrizePicks", "Underdog", "DraftKings"]

# ============================================================
# END SECTION: Load Available Data
# ============================================================

# ============================================================
# SECTION: Current Props Table
# Show what's currently loaded (sample or user-entered)
# ============================================================

# Get current props from session state (or sample data if none)
current_props = load_props_from_session(st.session_state)

st.subheader(f"📋 Current Props ({len(current_props)} loaded)")

if current_props:
    # Show the props in a formatted table
    # Create display data with formatted values
    display_rows = []
    for i, prop in enumerate(current_props):
        display_rows.append({
            "#": i + 1,
            "Player": prop.get("player_name", prop.get("player_name", "")),
            "Team": prop.get("team", ""),
            "Stat": prop.get("stat_type", "").capitalize(),
            "Line": prop.get("line", ""),
            "Platform": prop.get("platform", ""),
            "Date": prop.get("game_date", ""),
        })

    # Display as a table
    # BEGINNER NOTE: st.dataframe makes a scrollable, sortable table
    st.dataframe(
        display_rows,
        use_container_width=True,
        hide_index=True,
    )

    # Buttons to manage current props
    col_clear, col_load_sample, _ = st.columns([1, 1, 3])
    with col_clear:
        if st.button("🗑️ Clear All Props"):
            st.session_state["current_props"] = []
            st.session_state["analysis_results"] = []  # Clear old results too
            st.rerun()
    with col_load_sample:
        if st.button("📦 Load Sample Props"):
            # Reset to sample data
            sample_props = load_props_data()
            save_props_to_session(sample_props, st.session_state)
            st.success(f"Loaded {len(sample_props)} sample props!")
            st.rerun()
else:
    st.info("No props loaded. Use the forms below to add props.")

# ============================================================
# END SECTION: Current Props Table
# ============================================================

st.divider()

# ============================================================
# SECTION: Manual Entry Form
# ============================================================

st.subheader("✏️ Add Props Manually")
st.markdown("Enter one prop at a time. Click **Add Prop** to save each one.")

with st.form("manual_prop_entry", clear_on_submit=True):
    # Four columns for the main inputs
    col1, col2, col3, col4 = st.columns([3, 1, 1, 2])

    with col1:
        # Player name dropdown (or type manually)
        selected_player = st.selectbox(
            "Player Name *",
            options=["— Type or select —"] + all_player_names,
            help="Select from the list or type a player name",
        )
        # Allow typing a custom name if not in the list
        custom_player_name = st.text_input(
            "Or type player name:",
            placeholder="e.g., LeBron James",
            help="Use this if the player isn't in the dropdown",
        )

    with col2:
        stat_type_selection = st.selectbox(
            "Stat Type *",
            options=valid_stat_types,
            help="Which stat are you betting on?",
        )

    with col3:
        prop_line_value = st.number_input(
            "Line *",
            min_value=0.0,
            max_value=100.0,
            value=24.5,
            step=0.5,
            help="The over/under line (e.g., 24.5 points)",
        )

    with col4:
        platform_selection = st.selectbox(
            "Platform *",
            options=valid_platforms,
            help="Which platform is this prop from?",
        )

    # Second row: team and date (optional)
    col5, col6, col7 = st.columns([2, 2, 3])
    with col5:
        team_input = st.text_input(
            "Team (optional)",
            placeholder="e.g., LAL",
            help="3-letter team abbreviation",
        )
    with col6:
        game_date_input = st.date_input(
            "Game Date",
            value=datetime.date.today(),
        )

    # Submit button
    add_prop_button = st.form_submit_button(
        "➕ Add Prop",
        use_container_width=True,
        type="primary",
    )

# Process the manual entry submission
if add_prop_button:
    # Determine the player name to use
    # Prefer the custom typed name if provided
    if custom_player_name.strip():
        final_player_name = custom_player_name.strip()
    elif selected_player != "— Type or select —":
        final_player_name = selected_player
    else:
        final_player_name = ""

    # Validate: player name is required
    if not final_player_name:
        st.error("Please enter or select a player name.")
    elif prop_line_value <= 0:
        st.error("Prop line must be greater than 0.")
    else:
        # Build the new prop dictionary
        new_prop = {
            "player_name": final_player_name,
            "team": team_input.strip().upper() if team_input else "",
            "stat_type": stat_type_selection,
            "line": prop_line_value,
            "platform": platform_selection,
            "game_date": game_date_input.isoformat(),
        }

        # Get current props and add the new one
        current_props_for_update = load_props_from_session(st.session_state)
        current_props_for_update.append(new_prop)

        # Save back to session state
        save_props_to_session(current_props_for_update, st.session_state)

        st.success(f"✅ Added: {final_player_name} | {stat_type_selection} | {prop_line_value} | {platform_selection}")
        st.rerun()

# ============================================================
# END SECTION: Manual Entry Form
# ============================================================

st.divider()

# ============================================================
# SECTION: CSV Upload
# ============================================================

st.subheader("📤 Upload Props CSV")

# Show the template first so users know the format
st.markdown("**Required CSV format:**")
st.code(
    "player_name,team,stat_type,line,platform,game_date\n"
    "LeBron James,LAL,points,24.5,PrizePicks,2026-03-05\n"
    "Stephen Curry,GSW,threes,3.5,Underdog,2026-03-05",
    language="csv",
)

# Download template button
template_csv = get_csv_template()
st.download_button(
    label="⬇️ Download CSV Template",
    data=template_csv,
    file_name="props_template.csv",
    mime="text/csv",
    help="Download a blank template to fill in your props",
)

st.markdown("---")

# File uploader widget
uploaded_file = st.file_uploader(
    "Upload your props CSV file",
    type=["csv"],
    help="Upload a CSV file with prop lines. Must match the template format.",
)

if uploaded_file is not None:
    # Read the file content
    # BEGINNER NOTE: uploaded_file is a file-like object.
    # .read() gets the bytes, .decode('utf-8') converts to text string
    file_content = uploaded_file.read().decode("utf-8")

    # Parse the CSV text
    parsed_props, parse_errors = parse_props_from_csv_text(file_content)

    # Show parsing errors if any
    if parse_errors:
        for error in parse_errors:
            st.warning(f"⚠️ {error}")

    if parsed_props:
        st.success(f"✅ Parsed {len(parsed_props)} props from upload!")

        # Show preview of what was parsed
        st.markdown("**Preview of uploaded props:**")
        preview_rows = [
            {
                "Player": p.get("player_name", ""),
                "Stat": p.get("stat_type", ""),
                "Line": p.get("line", ""),
                "Platform": p.get("platform", ""),
            }
            for p in parsed_props[:10]  # Show max 10 rows in preview
        ]
        st.dataframe(preview_rows, use_container_width=True, hide_index=True)

        if len(parsed_props) > 10:
            st.caption(f"... and {len(parsed_props) - 10} more")

        # Confirmation buttons
        col_replace, col_add, col_cancel = st.columns([1, 1, 2])

        with col_replace:
            if st.button("🔄 Replace All Props", type="primary"):
                save_props_to_session(parsed_props, st.session_state)
                st.success(f"Replaced all props with {len(parsed_props)} from upload!")
                st.rerun()

        with col_add:
            if st.button("➕ Add to Existing"):
                existing = load_props_from_session(st.session_state)
                combined = existing + parsed_props
                save_props_to_session(combined, st.session_state)
                st.success(f"Added {len(parsed_props)} props. Total: {len(combined)}")
                st.rerun()
    else:
        st.error("No valid props found in the uploaded file.")

# ============================================================
# END SECTION: CSV Upload
# ============================================================

st.divider()

# ============================================================
# SECTION: Quick Add Multiple Props
# Allow adding multiple props quickly with a text area
# ============================================================

st.subheader("⚡ Quick Add (Paste CSV data)")
st.markdown("Paste prop lines directly as CSV text:")

quick_add_text = st.text_area(
    "Paste CSV data here",
    placeholder="player_name,team,stat_type,line,platform\nLeBron James,LAL,points,24.5,PrizePicks\nStephen Curry,GSW,threes,3.5,Underdog",
    height=150,
    help="Paste CSV-formatted props. Headers optional if in correct order.",
)

if st.button("⚡ Parse & Add Props") and quick_add_text.strip():
    parsed_props_quick, errors_quick = parse_props_from_csv_text(quick_add_text)

    for error in errors_quick:
        st.warning(f"⚠️ {error}")

    if parsed_props_quick:
        existing = load_props_from_session(st.session_state)
        combined = existing + parsed_props_quick
        save_props_to_session(combined, st.session_state)
        st.success(f"✅ Added {len(parsed_props_quick)} props! Total: {len(combined)}")
        st.rerun()
    else:
        st.error("Could not parse any props from the input.")

# ============================================================
# END SECTION: Quick Add Multiple Props
# ============================================================
