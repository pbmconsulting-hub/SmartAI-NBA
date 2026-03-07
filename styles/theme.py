# ============================================================
# FILE: styles/theme.py
# PURPOSE: All CSS/HTML generators for the SmartBetPro NBA UI.
#          Provides a futuristic "AI Neural Network Lab" bright
#          theme with glassmorphism cards, animated glow
#          effects, and NBA team colors on a clean light
#          AI-lab background for maximum readability.
# BRAND:   SmartBetPro NBA by JM5
# USAGE:
#   from styles.theme import get_global_css, get_player_card_html
#   st.markdown(get_global_css(), unsafe_allow_html=True)
# ============================================================

# Standard library only — no new dependencies
import html as _html
import math as _math


# ============================================================
# SECTION: Glossary
# Plain-English explanations for betting / AI terms shown
# via tooltips and education boxes throughout the UI.
# ============================================================

GLOSSARY = {
    "Monte Carlo Simulation": (
        "We simulate thousands of possible game outcomes using the player's historical "
        "stats, matchup data, and current conditions. The percentage you see reflects "
        "how often the player hit the target across all those simulations."
    ),
    "Edge": (
        "The difference between what we think will happen and what the betting line "
        "implies. A positive edge means our model sees more value than the sportsbook "
        "is offering — the bigger the edge, the better the opportunity."
    ),
    "Confidence Score": (
        "A 0–100 rating of how sure the model is about this pick. It combines sample "
        "size, consistency, matchup clarity, and simulation stability. Above 70 = "
        "high confidence; below 50 = proceed with caution."
    ),
    "Expected Value (EV)": (
        "How much money you'd expect to make (or lose) per dollar bet over time if "
        "you placed this wager repeatedly under the same conditions. Positive EV bets "
        "are profitable long-term even if any single bet can lose."
    ),
    "Coefficient of Variation": (
        "A measure of how consistent a player is. It compares the spread of their "
        "game-to-game stats to their average. Low CV = very consistent; high CV = "
        "boom-or-bust performer who is harder to predict."
    ),
    "Prop Bet": (
        "A bet on whether a player will exceed or fall short of a statistical threshold "
        "(the 'line') set by the platform — for example, scoring more or fewer than "
        "24.5 points in a game."
    ),
    "Over/Under": (
        "Betting on whether a stat will be higher (Over) or lower (Under) than the "
        "line. Our model calculates the true probability of each side so you can "
        "spot when the line is mis-priced."
    ),
    "Line": (
        "The threshold set by the platform for a specific player stat. If the line "
        "for LeBron points is 24.5, you bet whether he scores more (Over) or fewer "
        "(Under) than that number."
    ),
    "Parlay": (
        "A multi-pick bet where ALL selections must be correct to win. The payout "
        "multiplies across legs but so does the risk — one wrong pick loses everything. "
        "Stick to high-confidence legs when building parlays."
    ),
    "Bankroll": (
        "The total amount of money set aside exclusively for betting. Good bankroll "
        "management means never risking more than 1–5% on a single bet, so a losing "
        "streak doesn't wipe you out before the edge plays out."
    ),
}


# ============================================================
# END SECTION: Glossary
# ============================================================


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

_DEFAULT_TEAM_COLORS = ("#0891b2", "#e0f2fe")


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
    Return the full CSS string for the SmartBetPro NBA AI Neural Network Lab theme.

    Implements a bright "high-tech AI lab" light theme with:
    - Clean white / light metallic gray / holographic light-blue backgrounds
    - Neural dot pattern adapted for light backgrounds
    - Glassmorphism cards with cyan-glow borders on white
    - Vibrant high-tech accent colors (cyan, neon green, gold, red) that pop
    - Dark contrasting sidebar for the "lab workstation" feel
    - Futuristic tier badges with glow effects
    - Pulsing live-indicator dot animation
    - Monospace terminal readout class
    - Smooth hover transitions throughout
    - Sidebar "Powered by JM5 Neural Engine" branding
    - Custom scrollbar

    Returns:
        str: Full <style>...</style> block ready for st.markdown()
    """
    return """
<style>
/* ─── Keyframe Animations ─────────────────────────────────── */
@keyframes borderGlow {
    0%, 100% { box-shadow: 0 0 8px rgba(8,145,178,0.18),
                            0 4px 20px rgba(8,145,178,0.08); }
    50%       { box-shadow: 0 0 22px rgba(8,145,178,0.38),
                            0 4px 24px rgba(8,145,178,0.14); }
}
@keyframes pulse-platinum {
    0%, 100% { box-shadow: 0 0 10px rgba(100,116,139,0.35); }
    50%       { box-shadow: 0 0 22px rgba(100,116,139,0.60); }
}
@keyframes pulse-gold {
    0%, 100% { box-shadow: 0 0 10px rgba(217,119,6,0.40); }
    50%       { box-shadow: 0 0 22px rgba(217,119,6,0.70); }
}
@keyframes live-dot-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.4; transform: scale(1.35); }
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes headerShimmer {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* ─── Base / Body ─────────────────────────────────────────── */html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                 'Helvetica Neue', Arial, sans-serif;
    color: #0f172a;
    background-color: #eef2fb;
}
/* Neural dot pattern — subtle circuit nodes on the light lab background */
.stApp {
    background-color: #eef2fb;
    background-image:
        radial-gradient(circle, rgba(8,145,178,0.13) 1px, transparent 1px),
        radial-gradient(circle, rgba(99,102,241,0.07) 1px, transparent 1px);
    background-size: 40px 40px, 80px 80px;
    background-position: 0 0, 20px 20px;
}

/* Streamlit text defaults on light background */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stCaptionContainer"],
.stTextInput label,
.stSelectbox label,
.stSlider label,
.stCheckbox label,
.stRadio label {
    color: #0f172a;
}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h5,
[data-testid="stMarkdownContainer"] h6,
.stHeadingWithActionElements {
    color: #0f172a;
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #e2e8f0; }
::-webkit-scrollbar-thumb { background: rgba(8,145,178,0.35); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(8,145,178,0.60); }

/* ─── Sidebar — dark "lab workstation" panel ──────────────── */
[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: 1px solid rgba(8,145,178,0.25) !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] a {
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"]::after {
    content: "⚡ Powered by JM5 Neural Engine";
    display: block;
    position: fixed;
    bottom: 18px;
    left: 0;
    width: 100%;
    padding: 0 20px;
    box-sizing: border-box;
    text-align: center;
    font-size: 0.68rem;
    font-family: 'Courier New', Courier, monospace;
    font-weight: 700;
    color: rgba(8,145,178,0.65) !important;
    letter-spacing: 0.08em;
    pointer-events: none;
}

/* ─── Streamlit native elements on light bg ───────────────── */
[data-testid="stMetricValue"] { color: #0f172a !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; }
.stAlert { background: rgba(255,255,255,0.85) !important; border-radius: 10px !important; }
.stExpander { background: rgba(255,255,255,0.75) !important; border: 1px solid rgba(8,145,178,0.2) !important; border-radius: 12px !important; }
.stExpander summary { color: #0f172a !important; }
button[kind="primary"] {
    background: linear-gradient(135deg, #0891b2, #4f46e5) !important;
    color: #fff !important;
    border: none !important;
}
.stDataFrame, .stTable { background: #ffffff !important; }

/* ─── Analysis Card (smartai-card) ───────────────────────── */
.smartai-card {
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(8,145,178,0.22);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 2px 12px rgba(8,145,178,0.09), 0 1px 3px rgba(0,0,0,0.06);
    animation: borderGlow 3.5s ease-in-out infinite,
               fadeInUp 0.35s ease both;
    transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}
.smartai-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #0891b2, #06b6d4, #10b981, #f59e0b, #0891b2);
    background-size: 200% 100%;
    animation: headerShimmer 4s ease infinite;
    opacity: 0.9;
}
.smartai-card:hover {
    border-color: rgba(8,145,178,0.50);
    transform: translateY(-2px);
    box-shadow: 0 6px 24px rgba(8,145,178,0.18);
}

/* ─── Neural Header ───────────────────────────────────────── */
.neural-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%);
    border: 1px solid rgba(8,145,178,0.35);
    border-radius: 16px;
    padding: 24px 30px;
    margin-bottom: 20px;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    position: relative;
    overflow: hidden;
    text-align: center;
    box-shadow: 0 4px 24px rgba(8,145,178,0.18);
}
.neural-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #06b6d4, #10b981, #f59e0b, #f43f5e, #06b6d4);
    background-size: 200% 100%;
    animation: headerShimmer 3s linear infinite;
}
.neural-header-title {
    font-size: 2rem;
    font-weight: 900;
    background: linear-gradient(135deg, #06b6d4, #10b981);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
    line-height: 1.15;
}
.neural-header-subtitle {
    font-size: 0.88rem;
    color: rgba(226,232,240,0.75);
    margin-top: 6px;
    font-family: 'Courier New', Courier, monospace;
    letter-spacing: 0.06em;
}
.circuit-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #06b6d4;
    margin: 0 6px;
    vertical-align: middle;
    animation: live-dot-pulse 1.8s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(6,182,212,0.7);
}

/* ─── Player Name & Team Pill ─────────────────────────────── */
.player-name {
    font-size: 1.3rem;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.02em;
}
.team-pill {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.8rem;
    color: #fff;
    background: rgba(8,145,178,0.75);
    margin-left: 8px;
    vertical-align: middle;
    border: 1px solid rgba(8,145,178,0.4);
    box-shadow: 0 1px 4px rgba(8,145,178,0.2);
}
.position-tag {
    color: #64748b;
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
    transition: box-shadow 0.2s ease;
}
.tier-platinum {
    background: linear-gradient(135deg, #94a3b8, #e2e8f0);
    color: #0f172a;
    animation: pulse-platinum 2.5s infinite;
    border: 1px solid rgba(100,116,139,0.4);
}
.tier-gold {
    background: linear-gradient(135deg, #d97706, #fbbf24);
    color: #1c1917;
    animation: pulse-gold 2.8s infinite;
}
.tier-silver {
    background: linear-gradient(135deg, #6b7280, #d1d5db);
    color: #0f172a;
    box-shadow: 0 0 8px rgba(107,114,128,0.3);
}
.tier-bronze {
    background: linear-gradient(135deg, #92400e, #f97316);
    color: #fff;
    box-shadow: 0 0 8px rgba(249,115,22,0.35);
}

/* ─── AI Verdict Card ─────────────────────────────────────── */
.verdict-bet {
    background: rgba(16,185,129,0.08);
    border: 2px solid rgba(16,185,129,0.50);
    border-radius: 14px;
    padding: 16px 20px;
    animation: borderGlow 2.5s ease-in-out infinite;
}
.verdict-avoid {
    background: rgba(239,68,68,0.07);
    border: 2px solid rgba(239,68,68,0.45);
    border-radius: 14px;
    padding: 16px 20px;
}
.verdict-risky {
    background: rgba(245,158,11,0.07);
    border: 2px solid rgba(245,158,11,0.40);
    border-radius: 14px;
    padding: 16px 20px;
}
.verdict-label {
    font-size: 1.4rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-family: 'Courier New', Courier, monospace;
}
.verdict-label-bet   { color: #059669; }
.verdict-label-avoid { color: #dc2626; }
.verdict-label-risky { color: #d97706; }
.verdict-confidence {
    font-size: 0.8rem;
    color: #64748b;
    font-family: 'Courier New', Courier, monospace;
    margin-top: 4px;
}
.verdict-explanation {
    font-size: 0.9rem;
    color: #1e293b;
    margin-top: 10px;
    line-height: 1.55;
    border-top: 1px solid rgba(8,145,178,0.12);
    padding-top: 10px;
}

/* ─── Stat Readout (monospace terminal) ───────────────────── */
.stat-readout {
    font-family: 'Courier New', Courier, monospace;
    background: rgba(8,145,178,0.05);
    border: 1px solid rgba(8,145,178,0.18);
    border-radius: 8px;
    padding: 8px 14px;
    margin: 4px 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background 0.2s ease;
}
.stat-readout:hover {
    background: rgba(8,145,178,0.10);
}
.stat-readout-label {
    color: #64748b;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
}
.stat-readout-value {
    color: #0891b2;
    font-size: 1rem;
    font-weight: 700;
}
.stat-readout-context {
    color: #64748b;
    font-size: 0.75rem;
    margin-left: 10px;
}

/* ─── Education Box ───────────────────────────────────────── */
.education-box {
    background: rgba(224,242,254,0.65);
    border: 1px solid rgba(8,145,178,0.22);
    border-radius: 12px;
    padding: 14px 18px;
    margin: 10px 0;
    transition: background 0.2s ease;
}
.education-box:hover {
    background: rgba(224,242,254,0.90);
}
.education-box-title {
    font-size: 0.88rem;
    font-weight: 700;
    color: #0891b2;
    display: flex;
    align-items: center;
    gap: 7px;
    cursor: pointer;
    user-select: none;
}
.education-box-content {
    font-size: 0.84rem;
    color: #334155;
    margin-top: 9px;
    line-height: 1.6;
    border-top: 1px solid rgba(8,145,178,0.15);
    padding-top: 9px;
}

/* ─── Progress Ring ───────────────────────────────────────── */
.progress-ring-wrap {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}
.progress-ring-label {
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-family: 'Courier New', Courier, monospace;
}

/* ─── Signal Strength Bar ─────────────────────────────────── */
.signal-bar-wrap {
    display: inline-flex;
    align-items: flex-end;
    gap: 3px;
    height: 22px;
    vertical-align: middle;
}
.signal-bar-seg {
    width: 7px;
    border-radius: 2px;
    background: rgba(8,145,178,0.18);
    transition: background 0.2s ease;
}
.signal-bar-seg.active {
    background: linear-gradient(180deg, #0891b2, #06b6d4);
}
.signal-strength-label {
    font-size: 0.72rem;
    color: #64748b;
    font-family: 'Courier New', Courier, monospace;
    margin-left: 6px;
    vertical-align: middle;
}

/* ─── Inline Tooltip ──────────────────────────────────────── */
.edu-tooltip {
    position: relative;
    display: inline-block;
    border-bottom: 1px dashed rgba(8,145,178,0.6);
    color: #0891b2;
    cursor: help;
    font-weight: 600;
}
.edu-tooltip .tooltip-text {
    visibility: hidden;
    opacity: 0;
    width: 260px;
    background: #0f172a;
    border: 1px solid rgba(8,145,178,0.35);
    color: #e2e8f0;
    font-size: 0.8rem;
    font-weight: 400;
    line-height: 1.5;
    border-radius: 10px;
    padding: 10px 14px;
    position: absolute;
    z-index: 999;
    bottom: 130%;
    left: 50%;
    transform: translateX(-50%);
    transition: opacity 0.2s ease;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    pointer-events: none;
}
.edu-tooltip:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
}

/* ─── Platform & Stat Badges ──────────────────────────────── */
.platform-badge {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 5px;
    font-size: 0.78rem;
    font-weight: 700;
    transition: opacity 0.2s ease;
}
.stat-chip {
    display: inline-block;
    background: rgba(8,145,178,0.08);
    border: 1px solid rgba(8,145,178,0.20);
    border-radius: 8px;
    padding: 4px 11px;
    margin-right: 6px;
    margin-top: 4px;
    color: #0f172a;
    font-size: 0.83rem;
    font-weight: 600;
    transition: background 0.2s ease;
}
.stat-chip:hover {
    background: rgba(8,145,178,0.16);
}
.stat-label { color: #64748b; font-size: 0.72rem; }

/* ─── Probability Gauge ───────────────────────────────────── */
.prob-gauge-wrap {
    background: rgba(226,232,240,0.80);
    border-radius: 10px;
    height: 16px;
    overflow: hidden;
    margin-top: 6px;
    border: 1px solid rgba(8,145,178,0.15);
}
.prob-gauge-fill-over {
    background: linear-gradient(90deg, #0891b2, #06b6d4, #10b981);
    height: 100%;
    border-radius: 10px;
    transition: width 0.5s ease;
    box-shadow: 0 0 8px rgba(8,145,178,0.4);
}
.prob-gauge-fill-under {
    background: linear-gradient(90deg, #dc2626, #f87171);
    height: 100%;
    border-radius: 10px;
    transition: width 0.5s ease;
    box-shadow: 0 0 8px rgba(220,38,38,0.35);
}
.prob-value {
    font-size: 1.15rem;
    font-weight: 800;
    color: #0f172a;
    font-family: 'Courier New', Courier, monospace;
}
.edge-badge {
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.82rem;
    font-weight: 700;
    font-family: 'Courier New', Courier, monospace;
}
.edge-positive { background: rgba(16,185,129,0.12); color: #065f46; border: 1px solid rgba(16,185,129,0.35); }
.edge-negative { background: rgba(220,38,38,0.10); color: #991b1b; border: 1px solid rgba(220,38,38,0.30); }

/* ─── Direction Badge ─────────────────────────────────────── */
.dir-over {
    background: rgba(16,185,129,0.12);
    color: #065f46;
    padding: 4px 12px;
    border-radius: 14px;
    font-weight: 800;
    font-size: 0.9rem;
    border: 1px solid rgba(16,185,129,0.35);
    font-family: 'Courier New', Courier, monospace;
}
.dir-under {
    background: rgba(220,38,38,0.10);
    color: #991b1b;
    padding: 4px 12px;
    border-radius: 14px;
    font-weight: 800;
    font-size: 0.9rem;
    border: 1px solid rgba(220,38,38,0.30);
    font-family: 'Courier New', Courier, monospace;
}

/* ─── Force Bar ───────────────────────────────────────────── */
.force-bar-wrap {
    display: flex;
    height: 10px;
    border-radius: 5px;
    overflow: hidden;
    background: rgba(226,232,240,0.80);
    margin-top: 5px;
    border: 1px solid rgba(8,145,178,0.12);
}
.force-bar-over  { background: linear-gradient(90deg, #0891b2, #10b981); }
.force-bar-under { background: linear-gradient(90deg, #dc2626, #f87171); }

/* ─── Distribution Range ──────────────────────────────────── */
.dist-range-wrap { text-align: right; }
.dist-p10  { color: #dc2626; font-size: 0.82rem; font-weight: 700; font-family: 'Courier New', Courier, monospace; }
.dist-p50  { color: #0f172a; font-size: 0.9rem; font-weight: 800; font-family: 'Courier New', Courier, monospace; }
.dist-p90  { color: #0891b2; font-size: 0.82rem; font-weight: 700; font-family: 'Courier New', Courier, monospace; }
.dist-sep  { color: #94a3b8; font-size: 0.82rem; margin: 0 3px; }
.dist-label { color: #94a3b8; font-size: 0.7rem; font-family: 'Courier New', Courier, monospace; }

/* ─── Form Dots ───────────────────────────────────────────── */
.form-dot-over  { display:inline-block; width:11px; height:11px; border-radius:50%;
                  background:#10b981; box-shadow:0 0 5px rgba(16,185,129,0.55);
                  margin:1px; vertical-align:middle; }
.form-dot-under { display:inline-block; width:11px; height:11px; border-radius:50%;
                  background:#ef4444; box-shadow:0 0 5px rgba(239,68,68,0.55);
                  margin:1px; vertical-align:middle; }

/* ─── Summary Cards ───────────────────────────────────────── */
.summary-card {
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(8,145,178,0.18);
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    box-shadow: 0 2px 12px rgba(8,145,178,0.10);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.summary-card:hover {
    border-color: rgba(8,145,178,0.40);
    box-shadow: 0 4px 20px rgba(8,145,178,0.18);
}
.summary-value {
    font-size: 2rem;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
    font-family: 'Courier New', Courier, monospace;
}
.summary-label {
    font-size: 0.75rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-top: 5px;
}

/* ─── Best Bets Card ──────────────────────────────────────── */
.best-bet-card {
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(8,145,178,0.22);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 10px;
    position: relative;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    box-shadow: 0 2px 10px rgba(8,145,178,0.08);
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.best-bet-card:hover {
    border-color: rgba(8,145,178,0.45);
    transform: translateX(3px);
}
.best-bet-rank {
    position: absolute;
    top: -10px; left: 16px;
    background: linear-gradient(135deg, #0891b2, #06b6d4);
    color: #ffffff;
    font-weight: 900;
    font-size: 0.75rem;
    padding: 2px 10px;
    border-radius: 10px;
    font-family: 'Courier New', Courier, monospace;
}

/* ─── Roster Health ───────────────────────────────────────── */
.health-matched {
    display: inline-block;
    background: rgba(16,185,129,0.10);
    border: 1px solid rgba(16,185,129,0.35);
    color: #065f46;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    margin: 2px;
}
.health-fuzzy {
    display: inline-block;
    background: rgba(245,158,11,0.10);
    border: 1px solid rgba(245,158,11,0.40);
    color: #92400e;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    margin: 2px;
    cursor: help;
}
.health-unmatched {
    display: inline-block;
    background: rgba(220,38,38,0.08);
    border: 1px solid rgba(220,38,38,0.30);
    color: #991b1b;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    margin: 2px;
}

/* ─── Live / Sample Badge ─────────────────────────────────── */
.live-badge {
    display: inline-block;
    background: rgba(16,185,129,0.12);
    color: #065f46;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    border: 1px solid rgba(16,185,129,0.35);
}
.live-badge::before {
    content: '';
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #10b981;
    margin-right: 6px;
    vertical-align: middle;
    animation: live-dot-pulse 1.5s ease-in-out infinite;
    box-shadow: 0 0 5px rgba(16,185,129,0.5);
}
.sample-badge {
    display: inline-block;
    background: rgba(245,158,11,0.10);
    color: #92400e;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    border: 1px solid rgba(245,158,11,0.35);
}

/* ─── Correlation Warning ─────────────────────────────────── */
.corr-warning {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.32);
    border-radius: 8px;
    padding: 8px 14px;
    color: #92400e;
    font-size: 0.83rem;
    margin-top: 8px;
}

/* ─── Player Analysis Card ────────────────────────────────── */
.player-analysis-card {
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(8,145,178,0.22);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 2px 12px rgba(8,145,178,0.09), 0 1px 3px rgba(0,0,0,0.05);
    animation: borderGlow 3.5s ease-in-out infinite,
               fadeInUp 0.3s ease both;
    transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}
.player-analysis-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #0891b2, #06b6d4, #10b981, #f59e0b, #0891b2);
    background-size: 200% 100%;
    animation: headerShimmer 4s ease infinite;
    opacity: 0.9;
}
.player-analysis-card:hover {
    border-color: rgba(8,145,178,0.50);
    transform: translateY(-2px);
    box-shadow: 0 6px 24px rgba(8,145,178,0.18);
}
.add-to-slip-btn {
    background: linear-gradient(135deg, #0891b2, #06b6d4);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 800;
    font-size: 0.8rem;
    cursor: pointer;
    font-family: 'Courier New', Courier, monospace;
    transition: opacity 0.2s ease, transform 0.2s ease;
    box-shadow: 0 2px 8px rgba(8,145,178,0.3);
}
.add-to-slip-btn:hover {
    opacity: 0.88;
    transform: scale(1.03);
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
<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#64748b;margin-top:3px;">
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
    conf_color = "#059669" if confidence >= 70 else "#d97706" if confidence >= 50 else "#dc2626"

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
    matchup_html = f'<span style="color:#64748b;font-size:0.82rem;">vs {opponent}</span>' if opponent else ""

    # Line context
    line_vs_avg = result.get("line_vs_avg_pct", 0)
    if line_vs_avg != 0:
        line_ctx = f"Line is {abs(line_vs_avg):.0f}% {'above' if line_vs_avg > 0 else 'below'} season avg"
        line_ctx_html = f'<span style="color:#64748b;font-size:0.78rem;font-style:italic;">{line_ctx}</span>'
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
      <div style="color:#64748b;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Last 5</div>
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
    <span style="color:#64748b;font-size:0.9rem;">{stat} &nbsp;·&nbsp; Line: <strong style="color:#0f172a;">{line}</strong></span>
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
      <span style="color:#64748b;font-size:0.82rem;">Confidence: <strong style="color:{conf_color};">{confidence:.0f}/100</strong></span>
    </div>
    <div class="prob-gauge-wrap">
      <div class="{fill_class}" style="width:{bar_width}%;"></div>
    </div>
  </div>

  <!-- Form + Force bar + Distribution -->
  <div style="margin-top:12px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;">
    {form_html}
    <div style="flex:1;min-width:160px;">
      <div style="color:#64748b;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Over/Under Forces</div>
      {force_bar}
    </div>
    <div style="min-width:110px;">
      <div style="color:#64748b;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Range</div>
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
      <strong style="color:#0f172a;font-size:1.05rem;">{player}</strong>
      <span style="color:#64748b;font-size:0.88rem;margin-left:8px;">{stat} {line}</span>
      <span style="color:#64748b;font-size:0.8rem;margin-left:6px;">{platform}</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <span class="{dir_class}">{arrow} {direction}</span>
      <span class="{tier_class}">{tier_emoji} {tier}</span>
    </div>
  </div>
  <div style="margin-top:6px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
    <span style="color:#0f172a;font-weight:700;font-family:'Courier New',monospace;">{prob_pct:.1f}%</span>
    <span style="color:#059669;font-size:0.82rem;font-family:'Courier New',monospace;">{edge_sign}{edge:.1f}% edge</span>
    <span style="color:#64748b;font-size:0.82rem;font-style:italic;">{rec}</span>
  </div>
</div>
""")

    cards_html = "\n".join(rows)
    return f"""
<div style="background:rgba(255,255,255,0.95);
            border:1px solid rgba(8,145,178,0.22);border-radius:16px;padding:20px 24px;margin-bottom:20px;
            backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
            box-shadow:0 2px 12px rgba(8,145,178,0.10);">
  <div style="font-size:1.15rem;font-weight:800;color:#0f172a;margin-bottom:14px;">
    🏆 Best Bets Today
    <span style="font-size:0.8rem;font-weight:400;color:#64748b;margin-left:10px;">Ranked by confidence score</span>
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
  <div style="color:#059669;font-size:0.8rem;font-weight:700;text-transform:uppercase;
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
  <div style="color:#d97706;font-size:0.8rem;font-weight:700;text-transform:uppercase;
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
  <div style="color:#dc2626;font-size:0.8rem;font-weight:700;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:6px;">
    ❌ Unmatched ({len(unmatched)}) — will use fallback data
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{chips}</div>
</div>""")

    if not sections:
        return '<div style="color:#059669;">✅ All props matched to the player database.</div>'

    inner = "\n".join(sections)
    total = len(matched) + len(fuzzy_matched) + len(unmatched)
    match_pct = int((len(matched) + len(fuzzy_matched)) / max(total, 1) * 100)
    return f"""
<div style="background:rgba(255,255,255,0.95);border:1px solid rgba(8,145,178,0.18);
            border-radius:12px;padding:16px 20px;margin-bottom:16px;
            backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
            box-shadow:0 2px 10px rgba(8,145,178,0.08);">
  <div style="font-size:1rem;font-weight:700;color:#0f172a;margin-bottom:12px;">
    🧬 Roster Health Check
    <span style="font-size:0.8rem;font-weight:400;color:#64748b;margin-left:8px;">
      {len(matched) + len(fuzzy_matched)}/{total} matched ({match_pct}%)
    </span>
  </div>
  {inner}
  <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">
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


# ============================================================
# SECTION: New AI Neural Network Lab Components
# Additional HTML generators for the SmartBetPro NBA UI.
# ============================================================

def get_neural_header_html(title, subtitle):
    """
    Return a glowing circuit-decoration header for page/section headings.

    Args:
        title (str): Main heading text (rendered with gradient)
        subtitle (str): Secondary line shown in monospace below the title

    Returns:
        str: HTML string for the neural header block
    """
    return f"""
<div class="neural-header">
  <div class="neural-header-title">{title}</div>
  <div class="neural-header-subtitle">
    <span class="circuit-dot"></span>
    {subtitle}
    <span class="circuit-dot"></span>
  </div>
</div>
"""


def get_ai_verdict_card_html(verdict, confidence, explanation):
    """
    Return a styled AI verdict card showing BET / AVOID / RISKY.

    Args:
        verdict (str): 'BET', 'AVOID', or 'RISKY'
        confidence (float): Confidence score 0–100
        explanation (str): Plain-English rationale for the verdict

    Returns:
        str: HTML string for the verdict card
    """
    verdict_upper = verdict.upper()
    icons = {"BET": "✅", "AVOID": "🚫", "RISKY": "⚠️"}
    icon = icons.get(verdict_upper, "🔍")
    css_class_map = {"BET": "verdict-bet", "AVOID": "verdict-avoid", "RISKY": "verdict-risky"}
    label_class_map = {"BET": "verdict-label-bet", "AVOID": "verdict-label-avoid", "RISKY": "verdict-label-risky"}
    card_class = css_class_map.get(verdict_upper, "verdict-risky")
    label_class = label_class_map.get(verdict_upper, "verdict-label-risky")
    conf_bar_color = "#059669" if confidence >= 70 else "#d97706" if confidence >= 50 else "#dc2626"
    bar_width = int(min(100, max(0, confidence)))
    return f"""
<div class="{card_class}">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
    <span class="verdict-label {label_class}">{icon} {verdict_upper}</span>
    <div style="text-align:right;">
      <div class="verdict-confidence">CONFIDENCE</div>
      <div style="font-size:1.1rem;font-weight:800;color:{conf_bar_color};
                  font-family:'Courier New',Courier,monospace;">{confidence:.0f}/100</div>
    </div>
  </div>
  <div style="margin-top:8px;background:rgba(226,232,240,0.80);border-radius:6px;height:6px;overflow:hidden;">
    <div style="width:{bar_width}%;height:100%;background:{conf_bar_color};
                border-radius:6px;box-shadow:0 0 6px {conf_bar_color};
                transition:width 0.5s ease;"></div>
  </div>
  <div class="verdict-explanation">{explanation}</div>
</div>
"""


def get_player_analysis_card_html(result, show_add_button=True):
    """
    Return a redesigned player analysis card with the neural network theme.

    Wraps the core stat data in the .player-analysis-card container with
    an optional '+ Add to Slip' button. Internally re-uses the proven
    layout from get_player_card_html but applies the updated CSS class.

    Args:
        result (dict): Full analysis result dict (same schema as get_player_card_html)
        show_add_button (bool): Whether to render the '+ Add to Slip' button

    Returns:
        str: HTML string for the player analysis card
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
        "PrizePicks": "rgba(0,120,70,0.85)",
        "Underdog": "rgba(85,60,154,0.85)",
        "DraftKings": "rgba(43,108,176,0.85)",
    }
    plat_color = platform_colors.get(platform, "rgba(30,40,60,0.85)")
    fill_class = "prob-gauge-fill-over" if direction == "OVER" else "prob-gauge-fill-under"
    bar_width = int(min(100, max(0, prob_pct)))
    primary_color, secondary_color = get_team_colors(team)

    team_badge = (
        f'<span class="team-pill" style="background:rgba(0,212,255,0.15);">{team}</span>'
        if team else ""
    )
    position_tag = f'<span class="position-tag">{position}</span>' if position else ""

    stat_pills = ""
    if pts_avg:
        stat_pills += get_stat_pill_html("PPG", f"{pts_avg:.1f}", "🏀")
    if reb_avg:
        stat_pills += get_stat_pill_html("RPG", f"{reb_avg:.1f}", "📊")
    if ast_avg:
        stat_pills += get_stat_pill_html("APG", f"{ast_avg:.1f}", "🎯")
    if proj:
        stat_pills += get_stat_pill_html("Proj", f"{proj:.1f}", "📐")

    edge_class = "edge-positive" if edge >= 0 else "edge-negative"
    edge_sign = "+" if edge >= 0 else ""
    edge_html = f'<span class="edge-badge {edge_class}">{edge_sign}{edge:.1f}% edge</span>'
    conf_color = "#059669" if confidence >= 70 else "#d97706" if confidence >= 50 else "#dc2626"

    over_forces = result.get("forces", {}).get("over_forces", [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    total_over_strength = sum(f.get("strength", 1) for f in over_forces)
    total_under_strength = sum(f.get("strength", 1) for f in under_forces)
    force_bar = get_force_bar_html(
        total_over_strength, total_under_strength,
        len(over_forces), len(under_forces)
    )

    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)
    dist_range = get_distribution_range_html(p10, p50, p90)

    opponent = result.get("opponent", "")
    matchup_html = f'<span style="color:#64748b;font-size:0.82rem;">vs {opponent}</span>' if opponent else ""

    add_btn = (
        '<button class="add-to-slip-btn">＋ Add to Slip</button>'
        if show_add_button else ""
    )

    corr_warning = result.get("_correlation_warning", "")
    corr_html = f'<div class="corr-warning">⚠️ {corr_warning}</div>' if corr_warning else ""

    return f"""
<div class="player-analysis-card" style="border-top-color:{primary_color};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
    <div>
      <span class="player-name">{player}</span>
      {team_badge}
      {position_tag}
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span class="{tier_class}">{tier_emoji} {tier}</span>
      {add_btn}
    </div>
  </div>
  <div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
    <span class="platform-badge" style="background:{plat_color};color:#fff;">{platform}</span>
    <span style="color:#64748b;font-size:0.9rem;">{stat} &nbsp;·&nbsp;
      Line: <strong style="color:#0f172a;">{line}</strong></span>
    {matchup_html}
  </div>
  {f'<div style="margin-top:10px;">{stat_pills}</div>' if stat_pills else ""}
  <div style="margin-top:14px;">
    <div style="display:flex;justify-content:space-between;align-items:center;
                flex-wrap:wrap;gap:6px;margin-bottom:4px;">
      <span class="{dir_class}">{direction_arrow} {direction}</span>
      <span class="prob-value">{prob_pct:.1f}%</span>
      {edge_html}
      <span style="color:#64748b;font-size:0.82rem;">
        Confidence: <strong style="color:{conf_color};">{confidence:.0f}/100</strong>
      </span>
    </div>
    <div class="prob-gauge-wrap">
      <div class="{fill_class}" style="width:{bar_width}%;"></div>
    </div>
  </div>
  <div style="margin-top:12px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;">
    <div style="flex:1;min-width:160px;">
      <div style="color:#64748b;font-size:0.72rem;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:3px;">Over/Under Forces</div>
      {force_bar}
    </div>
    <div style="min-width:110px;">
      <div style="color:#64748b;font-size:0.72rem;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:3px;">Range</div>
      {dist_range}
    </div>
  </div>
  {corr_html}
</div>
"""


def get_stat_readout_html(label, value, context):
    """
    Return a monospace terminal-style stat readout row.

    Args:
        label (str): Stat name shown on the left (e.g., 'Season AVG')
        value: The stat value to display prominently (e.g., 24.8)
        context (str): Short contextual note shown on the right (e.g., 'last 10 games')

    Returns:
        str: HTML string for the stat readout
    """
    return f"""
<div class="stat-readout">
  <span class="stat-readout-label">{label}</span>
  <span>
    <span class="stat-readout-value">{value}</span>
    <span class="stat-readout-context">{context}</span>
  </span>
</div>
"""


def get_education_box_html(title, content):
    """
    Return a collapsible education info box.

    The box is rendered open by default using an HTML <details> element
    so it works without JavaScript in Streamlit's sandboxed environment.

    Args:
        title (str): Box heading (e.g., 'What is Edge?')
        content (str): Explanation text rendered inside the box

    Returns:
        str: HTML string for the education box
    """
    return f"""
<details class="education-box" open>
  <summary class="education-box-title">
    <span>💡</span> {title}
  </summary>
  <div class="education-box-content">{content}</div>
</details>
"""


def get_progress_ring_html(percentage, label):
    """
    Return an SVG circular confidence/progress ring indicator.

    Args:
        percentage (float): Value 0–100 to fill the ring
        label (str): Text label displayed below the ring

    Returns:
        str: HTML string containing inline SVG ring and label
    """
    pct = max(0.0, min(100.0, float(percentage)))
    radius = 28
    circumference = 2 * _math.pi * radius
    filled = circumference * pct / 100.0
    gap = circumference - filled

    if pct >= 70:
        ring_color = "#059669"
    elif pct >= 50:
        ring_color = "#d97706"
    else:
        ring_color = "#dc2626"

    return f"""
<div class="progress-ring-wrap">
  <svg width="72" height="72" viewBox="0 0 72 72">
    <circle cx="36" cy="36" r="{radius}"
            fill="none" stroke="rgba(8,145,178,0.12)" stroke-width="6"/>
    <circle cx="36" cy="36" r="{radius}"
            fill="none" stroke="{ring_color}" stroke-width="6"
            stroke-linecap="round"
            stroke-dasharray="{filled:.2f} {gap:.2f}"
            stroke-dashoffset="{circumference * 0.25:.2f}"
            style="filter:drop-shadow(0 0 4px {ring_color});transition:stroke-dasharray 0.5s ease;"/>
    <text x="36" y="40" text-anchor="middle"
          font-family="'Courier New',Courier,monospace"
          font-size="13" font-weight="700"
          fill="{ring_color}">{pct:.0f}%</text>
  </svg>
  <span class="progress-ring-label">{label}</span>
</div>
"""


def get_signal_strength_bar_html(strength, label):
    """
    Return a WiFi-style signal-strength bar (5 segments).

    Args:
        strength (float): Signal level 0.0–1.0 (or 0–100)
        label (str): Text label displayed next to the bars

    Returns:
        str: HTML string for the signal strength indicator
    """
    # Normalise to 0–1
    if strength > 1:
        strength = strength / 100.0
    strength = max(0.0, min(1.0, strength))
    active_bars = round(strength * 5)

    heights = [8, 12, 16, 20, 24]  # px heights for each bar segment
    bars_html = ""
    for i, h in enumerate(heights):
        active_class = "active" if i < active_bars else ""
        bars_html += (
            f'<div class="signal-bar-seg {active_class}" '
            f'style="height:{h}px;"></div>'
        )

    return f"""
<span>
  <span class="signal-bar-wrap">{bars_html}</span>
  <span class="signal-strength-label">{label}</span>
</span>
"""


def get_education_tooltip_html(term, explanation):
    """
    Return an inline hover tooltip for a betting/AI term.

    The tooltip uses pure CSS (no JavaScript) and works within
    Streamlit's sandboxed HTML environment.

    Args:
        term (str): The term to underline and make hoverable
        explanation (str): Plain-English explanation shown on hover

    Returns:
        str: HTML string with the tooltip span
    """
    safe_explanation = _html.escape(str(explanation))
    return (
        f'<span class="edu-tooltip">{term}'
        f'<span class="tooltip-text">{safe_explanation}</span>'
        f'</span>'
    )


# ============================================================
# END SECTION: New AI Neural Network Lab Components
# ============================================================
