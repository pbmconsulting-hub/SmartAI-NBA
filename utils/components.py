# ============================================================
# FILE: utils/components.py
# PURPOSE: Shared UI components for the SmartBetPro NBA app.
#          Contains the global settings popover that can be
#          injected into any page's sidebar or header.
# ============================================================

import streamlit as st


def render_global_settings():
    """Render an inline settings popover for edge threshold and simulation depth.

    Uses ``st.popover`` so users can adjust core engine parameters without
    leaving the current page.  Widget values are bound directly to
    ``st.session_state`` keys that the analysis engine already reads
    (``minimum_edge_threshold``, ``simulation_depth``), so changes
    propagate instantly on the next rerun.
    """
    with st.popover("⚙️ Settings"):
        st.markdown(
            "**Quantum Matrix Engine 5.6 — Quick Settings**"
        )

        # ── Simulation Depth ──────────────────────────────────────
        st.number_input(
            "Simulation Depth",
            min_value=100,
            max_value=10000,
            step=100,
            value=st.session_state.get("simulation_depth", 1000),
            key="sim_depth_widget",
            help="Number of Monte Carlo simulations per prop. Higher = more accurate but slower.",
            on_change=_sync_sim_depth,
        )

        # ── Minimum Edge Threshold ────────────────────────────────
        st.number_input(
            "Min Edge Threshold (%)",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            value=float(st.session_state.get("minimum_edge_threshold", 5.0)),
            key="edge_threshold_widget",
            help="Only display props with an edge at or above this percentage.",
            on_change=_sync_edge_threshold,
        )

        # ── Entry Fee ─────────────────────────────────────────────
        st.number_input(
            "Entry Fee ($)",
            min_value=1.0,
            max_value=1000.0,
            step=1.0,
            value=float(st.session_state.get("entry_fee", 10.0)),
            key="entry_fee_widget",
            help="Default dollar amount per entry for EV calculations.",
            on_change=_sync_entry_fee,
        )

        st.caption("Changes apply on next analysis run.")


# ── on_change callbacks ──────────────────────────────────────────
# These propagate widget values into the canonical session-state keys
# that the rest of the app reads (simulation_depth, minimum_edge_threshold,
# entry_fee).

def _sync_sim_depth():
    st.session_state["simulation_depth"] = st.session_state["sim_depth_widget"]


def _sync_edge_threshold():
    st.session_state["minimum_edge_threshold"] = st.session_state["edge_threshold_widget"]


def _sync_entry_fee():
    st.session_state["entry_fee"] = st.session_state["entry_fee_widget"]
