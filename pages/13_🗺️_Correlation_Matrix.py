# ============================================================
# FILE: pages/13_🗺️_Correlation_Matrix.py
# PURPOSE: Visualize pairwise Pearson correlations between
#          players' Monte Carlo simulation arrays.  Renders an
#          interactive Plotly heatmap with the Quantum
#          Institutional aesthetic.
# CONNECTS TO: engine/correlation.py, engine/odds_engine.py,
#              session state analysis results
# ============================================================

import streamlit as st
import os
import math
import html as _html

# ── App Logo ──────────────────────────────────────────────────
_ROOT_LOGO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Smart_Pick_Pro_Logo.png")
_ASSETS_LOGO = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Smart_Pick_Pro_Logo.png")
_LOGO_PATH = _ROOT_LOGO if os.path.exists(_ROOT_LOGO) else _ASSETS_LOGO
if os.path.exists(_LOGO_PATH):
    st.logo(_LOGO_PATH, size="large")

from styles.theme import get_global_css

st.set_page_config(
    page_title="Correlation Matrix — Smart Pick Pro",
    page_icon="🗺️",
    layout="wide",
)

st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Premium gate (graceful if module unavailable) ─────────────
try:
    from utils.premium_gate import premium_gate
    if not premium_gate("Correlation Matrix"):
        st.stop()
except ImportError:
    pass


# ============================================================
# SECTION: Pearson Correlation for Simulation Arrays
# ============================================================

def pearson_sim_correlation(array_a, array_b):
    """
    Pearson correlation coefficient between two simulation arrays.

    Args:
        array_a (list of float): Player A simulation results.
        array_b (list of float): Player B simulation results.

    Returns:
        float: Pearson r (-1.0 to 1.0), or 0.0 on insufficient data.
    """
    n = min(len(array_a), len(array_b))
    if n < 3:
        return 0.0
    a = array_a[:n]
    b = array_b[:n]
    try:
        mean_a = sum(a) / n
        mean_b = sum(b) / n
        num = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
        den_a = math.sqrt(sum((v - mean_a) ** 2 for v in a))
        den_b = math.sqrt(sum((v - mean_b) ** 2 for v in b))
        if den_a < 1e-9 or den_b < 1e-9:
            return 0.0
        r = num / (den_a * den_b)
        return max(-1.0, min(1.0, round(r, 4)))
    except (ValueError, ZeroDivisionError):
        return 0.0


# ============================================================
# SECTION: Page Header
# ============================================================

st.title("🗺️ Correlation Matrix")
st.markdown(
    '<p style="color:#94a3b8;font-size:0.9rem;">'
    "Pairwise Pearson correlations between players' Monte Carlo "
    "simulation distributions.  Positive correlation means their "
    "outcomes tend to move together; negative means they diverge."
    "</p>",
    unsafe_allow_html=True,
)

# ============================================================
# SECTION: Pull analyzed results from session state
# ============================================================

_results = st.session_state.get("analysis_results", [])
if not _results:
    st.info(
        "Run **Neural Analysis** first to populate simulation data. "
        "Once analysis completes, return here to view the correlation matrix."
    )
    st.stop()

# Build lookup: label → simulated_results array
_label_map = {}
for r in _results:
    sim = r.get("simulated_results", [])
    if not sim or len(sim) < 10:
        continue
    pname = r.get("player_name", "Unknown")
    stype = r.get("stat_type", "").title()
    label = f"{pname} — {stype}"
    _label_map[label] = sim

if len(_label_map) < 2:
    st.warning(
        "At least **2 props with simulation data** are needed to "
        "build a correlation matrix.  Run a larger analysis batch."
    )
    st.stop()

# ============================================================
# SECTION: Player / Prop Selector
# ============================================================

_all_labels = sorted(_label_map.keys())
_selected = st.multiselect(
    "Select props to correlate",
    options=_all_labels,
    default=_all_labels[:min(8, len(_all_labels))],
    help="Choose 2+ props.  Each prop's 1,000-run simulation array is compared pairwise.",
)

if len(_selected) < 2:
    st.info("Select at least 2 props above to generate the matrix.")
    st.stop()

# ============================================================
# SECTION: Compute Pairwise Correlation Matrix
# ============================================================

n = len(_selected)
corr_matrix = [[0.0] * n for _ in range(n)]

for i in range(n):
    for j in range(n):
        if i == j:
            corr_matrix[i][j] = 1.0
        elif j > i:
            r = pearson_sim_correlation(_label_map[_selected[i]], _label_map[_selected[j]])
            corr_matrix[i][j] = r
            corr_matrix[j][i] = r

# ============================================================
# SECTION: Plotly Heatmap Rendering
# ============================================================

try:
    import plotly.graph_objects as go

    # Short labels (first name initial + last + stat)
    short_labels = []
    for lbl in _selected:
        parts = lbl.split(" — ")
        name_parts = parts[0].split()
        short_name = f"{name_parts[0][0]}. {name_parts[-1]}" if len(name_parts) > 1 else parts[0]
        stat = parts[1] if len(parts) > 1 else ""
        short_labels.append(f"{short_name} {stat}")

    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=short_labels,
        y=short_labels,
        colorscale=[
            [0.0, "#0F172A"],
            [0.25, "#1e3a5f"],
            [0.5, "#334155"],
            [0.75, "#059669"],
            [1.0, "#00ff9d"],
        ],
        zmin=-1.0,
        zmax=1.0,
        text=[[f"{corr_matrix[i][j]:+.2f}" for j in range(n)] for i in range(n)],
        texttemplate="%{text}",
        textfont=dict(
            family="JetBrains Mono, monospace",
            size=12,
            color="#e2e8f0",
        ),
        hoverongaps=False,
        colorbar=dict(
            title=dict(text="Pearson r", font=dict(color="#94a3b8")),
            tickfont=dict(color="#64748b", family="JetBrains Mono, monospace"),
        ),
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#e2e8f0"),
        xaxis=dict(
            tickfont=dict(size=10, color="#94a3b8"),
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
        ),
        yaxis=dict(
            tickfont=dict(size=10, color="#94a3b8"),
            showgrid=True,
            gridcolor="rgba(148,163,184,0.08)",
            autorange="reversed",
        ),
        margin=dict(l=10, r=10, t=30, b=10),
        height=max(350, n * 50 + 100),
    )

    st.plotly_chart(fig, use_container_width=True)

except ImportError:
    st.error(
        "Plotly is required for the heatmap.  "
        "Install it with `pip install plotly`."
    )

# ============================================================
# SECTION: Dynamic Text Insights
# ============================================================

# Find highest and lowest off-diagonal correlations
_max_r, _min_r = -2.0, 2.0
_max_pair, _min_pair = ("", ""), ("", "")
for i in range(n):
    for j in range(i + 1, n):
        if corr_matrix[i][j] > _max_r:
            _max_r = corr_matrix[i][j]
            _max_pair = (_selected[i], _selected[j])
        if corr_matrix[i][j] < _min_r:
            _min_r = corr_matrix[i][j]
            _min_pair = (_selected[i], _selected[j])

if _max_r > 0.3:
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(0,255,157,0.25);'
        f'border-radius:8px;padding:12px 16px;margin:12px 0;">'
        f'<span style="color:#00ff9d;font-weight:700;font-size:0.85rem;">🔗 Positive Correlation Detected</span><br>'
        f'<span style="color:#c0d0e8;font-size:0.82rem;">'
        f'<b>{_html.escape(_max_pair[0])}</b> and <b>{_html.escape(_max_pair[1])}</b> '
        f'show <span style="color:#00ff9d;font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
        f'r = {_max_r:+.2f}</span>.  Their simulation distributions move together — '
        f'combining them in a parlay amplifies variance.  Consider diversifying across games.</span></div>',
        unsafe_allow_html=True,
    )

if _min_r < -0.15:
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(255,94,0,0.25);'
        f'border-radius:8px;padding:12px 16px;margin:8px 0;">'
        f'<span style="color:#ff5e00;font-weight:700;font-size:0.85rem;">🔀 Negative Correlation Detected</span><br>'
        f'<span style="color:#c0d0e8;font-size:0.82rem;">'
        f'<b>{_html.escape(_min_pair[0])}</b> and <b>{_html.escape(_min_pair[1])}</b> '
        f'show <span style="color:#ff5e00;font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
        f'r = {_min_r:+.2f}</span>.  These props tend to diverge — one going over '
        f'implies the other is more likely to go under.  Useful for hedging.</span></div>',
        unsafe_allow_html=True,
    )

if _max_r <= 0.3 and _min_r >= -0.15:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(148,163,184,0.15);'
        'border-radius:8px;padding:12px 16px;margin:12px 0;">'
        '<span style="color:#94a3b8;font-weight:700;font-size:0.85rem;">📊 Low Correlation</span><br>'
        '<span style="color:#c0d0e8;font-size:0.82rem;">'
        'No strong pairwise correlations detected.  These props appear '
        'largely independent — parlay math can treat their probabilities '
        'as multiplicative without a significant correlation penalty.</span></div>',
        unsafe_allow_html=True,
    )
