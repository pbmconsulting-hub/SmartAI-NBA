# ============================================================
# FILE: utils/joseph_loading.py
# PURPOSE: Joseph M. Smith animated loading screen with rotating
#          NBA fun facts.  Displays the Spinning Basketball avatar
#          with a glowing animated ring, glassmorphism backdrop,
#          floating particles, and a progress bar while pages load.
# USAGE:   placeholder = joseph_loading_placeholder("Analyzing…")
#          ...  # do expensive work
#          placeholder.empty()
# ============================================================

import base64
import html as _html
import os
import random

try:
    import streamlit as st
except ImportError:  # pragma: no cover – unit-test environments
    st = None

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# NBA Fun Facts — displayed during loading screens
# ═══════════════════════════════════════════════════════════════

# Each fact is a short NBA trivia snippet shown while the engine
# crunches data.  Minimum target: 80 facts across diverse categories.

NBA_FUN_FACTS: tuple[str, ...] = (
    # ── Scoring Records ────────────────────────────────────────
    "Wilt Chamberlain scored 100 points in a single game on March 2, 1962.",
    "Kobe Bryant scored 81 points against the Raptors — the second-highest single-game total in NBA history.",
    "The lowest-scoring NBA game in the shot-clock era was 62-57 between the Pacers and Pistons in 2004.",
    "James Harden once had a 60-point triple-double — the only one in NBA history.",
    "Devin Booker scored 70 points in a game at just 20 years old.",
    "LeBron James became the NBA's all-time leading scorer in 2023, passing Kareem Abdul-Jabbar.",
    "Wilt Chamberlain averaged 50.4 points per game in the 1961-62 season.",
    "Kevin Durant scored 30,000 career points faster than any player except Wilt Chamberlain.",
    "Luka Dončić recorded a 60-21-10 game — the only 60-point triple-double with 20+ rebounds.",
    "David Robinson scored 71 points on the final day of the 1993-94 season to win the scoring title.",

    # ── Assists & Playmaking ───────────────────────────────────
    "John Stockton holds the all-time assists record with 15,806.",
    "Scott Skiles set the single-game assist record with 30 assists in 1990.",
    "Magic Johnson averaged 11.2 assists per game for his career.",
    "Chris Paul has more career steals than turnovers — one of the rarest feats in NBA history.",
    "Rajon Rondo recorded 25 assists without a turnover in a single playoff game.",
    "Jason Kidd finished his career with over 12,000 assists.",
    "Nikola Jokić became the first center to lead the league in assists in 2023.",
    "LeBron James is the only player in NBA history with 10,000+ assists and 10,000+ rebounds.",
    "Russell Westbrook holds the record for most career triple-doubles.",
    "Steve Nash won back-to-back MVPs while never averaging more than 19 points per game.",

    # ── Rebounds ────────────────────────────────────────────────
    "Wilt Chamberlain grabbed 55 rebounds in a single game.",
    "Dennis Rodman led the NBA in rebounding for seven consecutive seasons.",
    "Bill Russell averaged 22.5 rebounds per game for his career.",
    "Moses Malone grabbed a record 587 offensive rebounds in a single season.",
    "Andre Drummond has the highest offensive rebounding percentage in NBA history.",

    # ── Defense & Blocks ───────────────────────────────────────
    "Hakeem Olajuwon is the all-time leader in blocks with 3,830.",
    "Mark Eaton blocked 456 shots in a single season (1984-85).",
    "Manute Bol and Hakeem Olajuwon share the single-game block record with 12.",
    "Ben Wallace won four Defensive Player of the Year awards as an undrafted player.",
    "Dikembe Mutombo's famous finger wag became one of the NBA's most iconic celebrations.",

    # ── Three-Point Shooting ───────────────────────────────────
    "Stephen Curry holds the all-time record for three-pointers made.",
    "Klay Thompson once made 14 three-pointers in a single game.",
    "Stephen Curry made 402 threes in the 2015-16 season — the single-season record.",
    "Ray Allen held the all-time three-point record before Curry broke it.",
    "The NBA introduced the three-point line in 1979.",
    "Reggie Miller scored 8 points in 8.9 seconds against the Knicks in 1995.",
    "Damian Lillard hit a 37-foot buzzer-beater to eliminate the Thunder in 2019.",

    # ── Championships & Dynasties ──────────────────────────────
    "Bill Russell won 11 championships in 13 seasons with the Celtics.",
    "The 1995-96 Chicago Bulls went 72-10 — the best regular season record at the time.",
    "The 2015-16 Warriors went 73-9 but lost the NBA Finals to Cleveland.",
    "Michael Jordan went 6-for-6 in NBA Finals appearances.",
    "The Celtics and Lakers have combined for 34 NBA championships.",
    "The 2004 Pistons won the title without a single All-Star on their roster.",
    "Tim Duncan won championships in three different decades.",
    "Kawhi Leonard won Finals MVP with two different teams.",

    # ── Draft & Rookies ────────────────────────────────────────
    "The 2003 NBA Draft class included LeBron, Wade, Melo, and Bosh.",
    "Hakeem Olajuwon was drafted #1 overall in 1984 — ahead of Michael Jordan at #3.",
    "Kobe Bryant was drafted 13th overall and traded to the Lakers on draft night.",
    "Giannis Antetokounmpo was the 15th pick in the 2013 draft.",
    "The Blazers passed on Michael Jordan to draft Sam Bowie in 1984.",
    "Nikola Jokić was picked 41st overall in the 2014 draft — the lowest for an eventual MVP.",

    # ── Streaks & Milestones ───────────────────────────────────
    "The 1971-72 Lakers won 33 consecutive games — the longest winning streak in NBA history.",
    "LeBron James has played in 10 NBA Finals.",
    "Kareem Abdul-Jabbar played 20 NBA seasons and appeared in the All-Star Game 19 times.",
    "Robert Parish played in 1,611 career games — the most in NBA history at his retirement.",
    "Vince Carter's career spanned four decades (1998-2020).",
    "A.C. Green played 1,192 consecutive games — the NBA's ironman record.",
    "The 2023 NBA season saw the Sacramento Kings end a 16-year playoff drought.",

    # ── Analytics & Strategy ───────────────────────────────────
    "The average NBA game pace is about 100 possessions per team.",
    "True Shooting Percentage accounts for free throws and three-pointers in efficiency.",
    "The corner three is the most efficient shot in the NBA behind layups and dunks.",
    "NBA teams average about 25-30 three-point attempts per game in the modern era.",
    "Dean Oliver's Four Factors: eFG%, TOV%, ORB%, and FT Rate explain most team success.",
    "Player Impact Estimate (PIE) measures a player's overall statistical contribution.",
    "The league-average offensive rating is around 113 points per 100 possessions.",
    "Home teams win roughly 57-60% of NBA games historically.",
    "Back-to-back games reduce player efficiency by an average of 2-3%.",
    "Pace-adjusted stats normalize for team speed to allow fair cross-team comparisons.",

    # ── Unique Records ─────────────────────────────────────────
    "Shaquille O'Neal only made one three-pointer in his entire career.",
    "Wilt Chamberlain never fouled out of an NBA game.",
    "The shortest player in NBA history was Muggsy Bogues at 5'3\".",
    "Manute Bol, at 7'7\", is one of the tallest players in NBA history.",
    "Oscar Robertson averaged a triple-double for an entire season in 1961-62.",
    "Rasheed Wallace holds the record for most technical fouls in a single season (41).",
    "Tim Duncan was called 'The Big Fundamental' for his textbook playing style.",
    "Michael Jordan's flu game in the 1997 Finals is one of basketball's most legendary performances.",

    # ── Teams & Franchises ─────────────────────────────────────
    "The Toronto Raptors are the only NBA team based outside the United States.",
    "The Boston Celtics have the most championships with 17.",
    "The Hornets, Pelicans, and Bobcats are all related franchises from Charlotte and New Orleans.",
    "The Seattle SuperSonics relocated to become the Oklahoma City Thunder in 2008.",
    "The NBA has had 30 teams since the Charlotte Bobcats joined in 2004.",
    "The Nets have played in New Jersey, Brooklyn, and started in New York.",

    # ── Salary & Business ──────────────────────────────────────
    "The NBA salary cap for 2024-25 is approximately $140 million.",
    "Michael Jordan earned more in endorsements than his total NBA salary.",
    "The luxury tax was introduced to discourage runaway team spending.",
    "NBA revenue exceeded $10 billion for the first time in the 2022-23 season.",
    "LeBron James became the first active NBA player to reach billionaire status.",
)

_FACTS_PER_SCREEN = 15  # number of facts shown per loading screen rotation


# ═══════════════════════════════════════════════════════════════
# Avatar loader — spinning basketball avatar for loading screens
# ═══════════════════════════════════════════════════════════════

def _get_joseph_avatar_spinning_b64() -> str:
    """Load the Spinning Basketball avatar and return base64-encoded data.

    Falls back to the default avatar if the spinning variant is missing.
    """
    _this = os.path.dirname(os.path.abspath(__file__))
    filenames = [
        "Joseph M Smith Avatar Spinning Basketball.png",
        "Joseph M Smith Avatar.png",
    ]
    for name in filenames:
        candidates = [
            os.path.join(_this, "..", name),
            os.path.join(os.getcwd(), name),
            os.path.join(_this, "..", "assets", name),
        ]
        for path in candidates:
            norm = os.path.normpath(path)
            if os.path.isfile(norm):
                try:
                    with open(norm, "rb") as fh:
                        return base64.b64encode(fh.read()).decode("utf-8")
                except Exception:
                    _logger.debug("Failed reading avatar at %s", norm)
    return ""


def get_random_facts(count: int = _FACTS_PER_SCREEN) -> list[str]:
    """Return *count* unique random NBA fun facts."""
    count = max(1, min(count, len(NBA_FUN_FACTS)))
    return random.sample(NBA_FUN_FACTS, count)


# ═══════════════════════════════════════════════════════════════
# Loading Screen HTML/CSS/JS
# ═══════════════════════════════════════════════════════════════

def _build_loading_html(
    status_text: str = "Loading…",
    rotation_seconds: int = 5,
    fact_count: int = _FACTS_PER_SCREEN,
) -> str:
    """Build the full HTML/CSS/JS for Joseph's animated loading screen.

    Parameters
    ----------
    status_text : str
        Text shown below the avatar (e.g. "Analyzing props…").
    rotation_seconds : int
        Seconds between fun-fact rotations.
    fact_count : int
        Number of unique facts to display in the rotation.
    """
    avatar_b64 = _get_joseph_avatar_spinning_b64()
    facts = get_random_facts(fact_count)
    safe_status = _html.escape(str(status_text))
    safe_facts_js = ", ".join(
        f'"{_html.escape(f)}"' for f in facts
    )

    avatar_img = (
        f'<img src="data:image/png;base64,{avatar_b64}" '
        f'class="jl-avatar" alt="Joseph M. Smith">'
        if avatar_b64
        else '<div class="jl-avatar jl-avatar-fallback">🏀</div>'
    )

    return f"""
<style>
/* ── Joseph Loading Screen — Glassmorphism + Particles ────── */
.jl-container{{
    position:relative;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    min-height:280px;
    padding:32px 24px;
    background:linear-gradient(145deg,rgba(7,10,19,0.95) 0%,rgba(15,23,42,0.92) 50%,rgba(7,10,19,0.95) 100%);
    backdrop-filter:blur(20px);
    -webkit-backdrop-filter:blur(20px);
    border:1px solid rgba(255,94,0,0.20);
    border-radius:20px;
    overflow:hidden;
    box-shadow:0 0 60px rgba(255,94,0,0.06),0 0 120px rgba(0,198,255,0.03);
}}
/* Shimmer top bar */
.jl-container::before{{
    content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,transparent,#ff5e00,#ff9e00,#ff5e00,transparent);
    background-size:200% 100%;
    animation:jlShimmer 3s linear infinite;
}}
@keyframes jlShimmer{{0%{{background-position:-200% 0}}100%{{background-position:200% 0}}}}

/* ── Floating particles ───────────────────────────────────── */
.jl-particle{{
    position:absolute;width:3px;height:3px;border-radius:50%;
    background:rgba(255,94,0,0.25);
    animation:jlFloat 6s ease-in-out infinite;
}}
.jl-particle:nth-child(2){{left:20%;animation-delay:1s;background:rgba(0,198,255,0.2)}}
.jl-particle:nth-child(3){{left:70%;animation-delay:2s}}
.jl-particle:nth-child(4){{left:40%;animation-delay:3s;background:rgba(0,198,255,0.2)}}
.jl-particle:nth-child(5){{left:85%;animation-delay:0.5s}}
@keyframes jlFloat{{
    0%,100%{{transform:translateY(0) scale(1);opacity:0.3}}
    50%{{transform:translateY(-80px) scale(1.5);opacity:0.7}}
}}

/* ── Avatar ring + glow ───────────────────────────────────── */
.jl-avatar-wrapper{{
    position:relative;width:140px;height:140px;
    margin-bottom:16px;
}}
.jl-ring{{
    position:absolute;inset:-8px;border-radius:50%;
    border:3px solid transparent;
    border-top-color:#ff5e00;border-right-color:#ff9e00;
    animation:jlRingSpin 2s linear infinite;
}}
@keyframes jlRingSpin{{0%{{transform:rotate(0deg)}}100%{{transform:rotate(360deg)}}}}

.jl-avatar{{
    width:130px;height:130px;border-radius:50%;
    object-fit:cover;
    position:absolute;top:50%;left:50%;
    transform:translate(-50%,-50%);
    border:3px solid rgba(255,94,0,0.5);
    box-shadow:0 0 24px rgba(255,94,0,0.4),0 0 48px rgba(255,94,0,0.12);
    animation:jlAvatarGlow 3s ease-in-out infinite;
}}
.jl-avatar-fallback{{
    display:flex;align-items:center;justify-content:center;
    font-size:3rem;background:rgba(30,41,59,0.9);
}}
@keyframes jlAvatarGlow{{
    0%,100%{{box-shadow:0 0 24px rgba(255,94,0,0.4),0 0 48px rgba(255,94,0,0.12)}}
    50%{{box-shadow:0 0 32px rgba(255,94,0,0.6),0 0 64px rgba(255,94,0,0.2)}}
}}

/* ── Status text ──────────────────────────────────────────── */
.jl-status{{
    font-family:'Orbitron',sans-serif;
    color:#ff5e00;font-size:0.9rem;font-weight:600;
    letter-spacing:0.6px;margin-bottom:8px;
    text-shadow:0 0 12px rgba(255,94,0,0.3);
}}

/* ── Fun fact area ────────────────────────────────────────── */
.jl-fact{{
    color:#94a3b8;font-size:0.82rem;
    font-family:'Montserrat',sans-serif;
    text-align:center;max-width:500px;line-height:1.5;
    min-height:2.5em;
    transition:opacity 0.4s ease;
}}
.jl-fact-label{{
    color:#ff9e00;font-family:'Orbitron',sans-serif;
    font-size:0.65rem;font-weight:600;
    letter-spacing:1px;margin-bottom:4px;
}}

/* ── Progress bar ─────────────────────────────────────────── */
.jl-progress-wrap{{
    width:220px;height:4px;
    background:rgba(148,163,184,0.15);
    border-radius:4px;margin-top:16px;overflow:hidden;
}}
.jl-progress-bar{{
    height:100%;width:0%;border-radius:4px;
    background:linear-gradient(90deg,#ff5e00,#ff9e00);
    animation:jlProgress {rotation_seconds}s linear infinite;
}}
@keyframes jlProgress{{0%{{width:0%}}100%{{width:100%}}}}
</style>

<div class="jl-container" id="jl-root">
    <div class="jl-particle" style="left:10%;top:80%"></div>
    <div class="jl-particle" style="left:20%;top:60%"></div>
    <div class="jl-particle" style="left:70%;top:75%"></div>
    <div class="jl-particle" style="left:40%;top:90%"></div>
    <div class="jl-particle" style="left:85%;top:70%"></div>

    <div class="jl-avatar-wrapper">
        <div class="jl-ring"></div>
        {avatar_img}
    </div>

    <div class="jl-status">{safe_status}</div>

    <div class="jl-fact-label">🏀 NBA FUN FACT</div>
    <div class="jl-fact" id="jl-fact-text"></div>

    <div class="jl-progress-wrap"><div class="jl-progress-bar"></div></div>
</div>

<script>
(function() {{
    var facts = [{safe_facts_js}];
    var idx = 0;
    var el = document.getElementById('jl-fact-text');
    if (!el || facts.length === 0) return;
    el.textContent = facts[0];
    var iv = setInterval(function() {{
        if (!document.contains(el)) {{ clearInterval(iv); return; }}
        idx = (idx + 1) % facts.length;
        el.style.opacity = '0';
        setTimeout(function() {{
            el.textContent = facts[idx];
            el.style.opacity = '1';
        }}, 400);
    }}, {rotation_seconds * 1000});
}})();
</script>
"""


# ═══════════════════════════════════════════════════════════════
# Public API — joseph_loading_placeholder
# ═══════════════════════════════════════════════════════════════

def joseph_loading_placeholder(
    status_text: str = "Loading…",
    rotation_seconds: int = 5,
    fact_count: int = _FACTS_PER_SCREEN,
):
    """Show Joseph's animated loading screen and return an ``st.empty()`` placeholder.

    Call ``.empty()`` on the returned placeholder to dismiss the loading screen.

    Parameters
    ----------
    status_text : str
        Descriptive status message (e.g. "Analyzing props…").
    rotation_seconds : int
        Seconds between fun-fact rotations (default 5).
    fact_count : int
        Number of unique facts to display per session (default 15).

    Returns
    -------
    streamlit.delta_generator.DeltaGenerator
        The ``st.empty()`` placeholder.  Call ``.empty()`` to dismiss.
    """
    if st is None:
        raise RuntimeError("Streamlit is not available")

    placeholder = st.empty()
    loading_html = _build_loading_html(status_text, rotation_seconds, fact_count)
    placeholder.markdown(loading_html, unsafe_allow_html=True)
    return placeholder
