# ============================================================
# FILE: utils/joseph_loading.py
# PURPOSE: Joseph M. Smith animated loading screen that displays
#          fun NBA facts while pages load or analyses run.
#          Shows Joseph's avatar with a basketball-themed
#          background and rotating fun facts to keep users
#          entertained during wait times.
# CONNECTS TO: pages/helpers/joseph_live_desk.py (avatar loader),
#              styles/theme.py (theme consistency)
# ============================================================

import html as _html
import logging
import random
import time as _time

try:
    import streamlit as st
except ImportError:  # pragma: no cover – unit-test environments
    st = None

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Avatar loader (safe import) ──────────────────────────────
try:
    from pages.helpers.joseph_live_desk import get_joseph_avatar_b64
    _AVATAR_AVAILABLE = True
except ImportError:
    _AVATAR_AVAILABLE = False

    def get_joseph_avatar_b64() -> str:
        return ""


# ═════════════════════════════════════════════════════════════
# NBA Fun Facts Pool — 80+ facts about NBA history, players,
# coaches, records, and basketball culture
# ═════════════════════════════════════════════════════════════

NBA_FUN_FACTS = (
    # ── All-time records ─────────────────────────────────────
    "Wilt Chamberlain scored 100 points in a single game on March 2, 1962 — a record that still stands today.",
    "The longest NBA game ever lasted 78 minutes — Indianapolis Olympians vs. Rochester Royals in 1951 with 6 overtimes.",
    "Kareem Abdul-Jabbar held the all-time scoring record for 39 years before LeBron James broke it in 2023.",
    "The Golden State Warriors set the regular season record with 73 wins in the 2015-16 season.",
    "Wilt Chamberlain averaged 50.4 points per game for the entire 1961-62 season. Nobody has come close since.",
    "The Boston Celtics won 8 consecutive NBA championships from 1959 to 1966 — the longest streak in NBA history.",

    # ── Player legends ───────────────────────────────────────
    "Michael Jordan was cut from his high school varsity basketball team as a sophomore.",
    "LeBron James has played in 10 NBA Finals and was the first player to score 40,000 career points.",
    "Kobe Bryant scored 81 points against the Toronto Raptors on January 22, 2006 — the second-highest single-game total ever.",
    "Magic Johnson won the NBA Finals MVP as a rookie in 1980, playing center in place of the injured Kareem Abdul-Jabbar.",
    "Stephen Curry revolutionized basketball with the three-point shot, holding the record for most career three-pointers made.",
    "Shaquille O'Neal made only one three-pointer in his entire 19-year NBA career.",
    "Tim Duncan was originally a competitive swimmer and only started playing basketball at age 14 after a hurricane destroyed his pool.",
    "Allen Iverson, listed at just 6'0\", won four NBA scoring titles and was the 2001 MVP.",
    "Hakeem Olajuwon is the NBA's all-time leader in blocked shots with 3,830.",
    "Dennis Rodman led the league in rebounds per game for seven consecutive seasons (1992-1998).",
    "Oscar Robertson averaged a triple-double for an entire season in 1961-62 — a feat unmatched for 55 years until Russell Westbrook did it in 2017.",
    "Larry Bird won three consecutive MVP awards from 1984 to 1986.",
    "Dirk Nowitzki played his entire 21-year career with the Dallas Mavericks — the longest tenure with one team in NBA history.",
    "Vince Carter's career spanned 22 seasons and four decades (1998–2020), the longest in NBA history.",

    # ── Draft & young players ────────────────────────────────
    "Kobe Bryant was drafted straight out of high school at age 17 — the youngest player in NBA history at the time.",
    "LeBron James was the #1 overall pick in the 2003 NBA Draft, straight out of high school.",
    "The 1984 NBA Draft class included Michael Jordan, Hakeem Olajuwon, Charles Barkley, and John Stockton.",
    "The 1996 Draft class featured Kobe Bryant, Allen Iverson, Steve Nash, and Ray Allen.",
    "Giannis Antetokounmpo was the 15th pick in the 2013 Draft. He won back-to-back MVP awards in 2019 and 2020.",
    "Nikola Jokić was picked 41st overall in 2014 — the lowest draft position for a player who won MVP.",

    # ── Coaching legends ─────────────────────────────────────
    "Phil Jackson won 11 NBA championships as a head coach — 6 with the Bulls and 5 with the Lakers.",
    "Red Auerbach lit a victory cigar on the bench when he felt a win was secured. He won 9 titles with the Celtics.",
    "Pat Riley coined the term 'three-peat' and actually trademarked it.",
    "Gregg Popovich has coached the San Antonio Spurs since 1996 — the longest active tenure with one team in major North American sports.",
    "Steve Kerr has won NBA championships both as a player (5 rings) and as a head coach.",
    "Erik Spoelstra became the first Asian-American head coach in any major U.S. professional sport.",

    # ── Team history & culture ───────────────────────────────
    "The NBA was founded on June 6, 1946 as the Basketball Association of America (BAA).",
    "The Toronto Raptors are the only current NBA team based outside the United States.",
    "The original Celtics parquet floor was made from scraps of wood left over from World War II.",
    "The Los Angeles Lakers were originally from Minneapolis — the 'Land of 10,000 Lakes.'",
    "The Jazz moved from New Orleans to Utah in 1979, keeping their name despite Utah not being known for jazz music.",
    "The Cleveland Cavaliers were named through a fan contest in 1970.",
    "The Miami Heat retired Michael Jordan's #23 jersey even though he never played for them — out of respect.",
    "The Harlem Globetrotters were actually from Chicago, not Harlem.",

    # ── Rules & gameplay ─────────────────────────────────────
    "The three-point line was introduced to the NBA in the 1979-80 season.",
    "The shot clock was introduced in 1954 to prevent teams from stalling. It was set at 24 seconds.",
    "The NBA didn't allow zone defense until the 2001-02 season.",
    "A regulation NBA basketball must bounce between 49 and 54 inches when dropped from 6 feet.",
    "NBA courts are exactly 94 feet long and 50 feet wide.",
    "The basketball itself weighs between 20 and 22 ounces.",

    # ── Playoffs & Finals ────────────────────────────────────
    "The Boston Celtics have the most NBA championships with 17 titles.",
    "The 2016 NBA Finals saw the Cleveland Cavaliers come back from a 3-1 deficit — the only team to ever do so in Finals history.",
    "LeBron James's block on Andre Iguodala in Game 7 of the 2016 Finals is one of the most iconic plays in NBA history.",
    "Michael Jordan never lost an NBA Finals series — he was 6-0.",
    "Bill Russell won 11 championships in 13 seasons — the most by any player in NBA history.",
    "The 2014 Spurs defeated the Heat by an average margin of 14 points in the Finals — the most dominant performance in modern Finals history.",

    # ── Stat milestones ──────────────────────────────────────
    "Only five players have recorded a quadruple-double in NBA history.",
    "John Stockton holds the all-time assists record with 15,806 — nearly 4,000 more than second place.",
    "Reggie Miller scored 8 points in 8.9 seconds against the Knicks in the 1995 playoffs.",
    "Tracy McGrady scored 13 points in 35 seconds against the Spurs in 2004.",
    "Russell Westbrook holds the record for most triple-doubles in NBA history with 198+.",
    "Robert Horry won 7 NBA championships with three different teams — the most by a non-Celtic player.",

    # ── Modern era ───────────────────────────────────────────
    "The NBA's salary cap for the 2024-25 season is approximately $141 million.",
    "Victor Wembanyama was the #1 pick in 2023 — at 7'4\" he's one of the tallest #1 picks ever.",
    "Nikola Jokić became the first center to win MVP since Shaq in 2000 when he won it in 2021.",
    "Luka Dončić recorded a 60-point triple-double in 2022 — only the second in NBA history.",
    "Ja Morant's explosive dunking ability earned him the nickname 'Ja Morant' — yes, his real name is just that iconic.",
    "The Phoenix Suns' Kevin Durant became the youngest player ever to reach 28,000 career points.",

    # ── Off-court & culture ──────────────────────────────────
    "The NBA ball is made by Wilson, who took over from Spalding starting in the 2021-22 season.",
    "NBA players run an average of 2.5 miles per game.",
    "The tallest player in NBA history was Gheorghe Mureșan at 7'7\".",
    "Muggsy Bogues, at 5'3\", is the shortest player in NBA history — and he blocked Patrick Ewing's shot.",
    "The NBA's longest winning streak is 33 games, set by the 1971-72 Los Angeles Lakers.",
    "Manute Bol and Muggsy Bogues were once teammates on the Washington Bullets — a 28-inch height difference.",

    # ── Fun trivia ───────────────────────────────────────────
    "The first NBA game was played on November 1, 1946 — the New York Knickerbockers vs. the Toronto Huskies.",
    "Wilt Chamberlain claims he never fouled out of an NBA game in his entire career.",
    "Kareem Abdul-Jabbar's skyhook is considered the most unstoppable shot in basketball history.",
    "Michael Jordan's 'Flu Game' in the 1997 Finals is one of the most legendary performances in sports history.",
    "The phrase 'and one' refers to a player being fouled while making a basket — getting the shot plus a free throw.",
    "The Boston Garden's famous parquet floor had dead spots that the Celtics memorized to gain a home-court advantage.",
    "A 'brick' in basketball slang means a badly missed shot that clangs off the rim.",
    "Charles Barkley once said 'I am not a role model' in a famous Nike commercial — sparking a national debate.",
    "The NBA Draft Lottery was introduced in 1985 after teams were accused of losing on purpose to get top picks.",
    "Shaq was so dominant that teams invented 'Hack-a-Shaq' — intentionally fouling him because he was a poor free throw shooter.",
    "The term 'triple-double' wasn't commonly used until Magic Johnson popularized the stat line in the 1980s.",
    "The NBA's G League was originally called the D-League (Development League) before Gatorade sponsored it.",
    "Klay Thompson once scored 37 points in a single quarter against the Sacramento Kings in 2015.",
    "Before the shot clock, the lowest-scoring NBA game was 19-18 (Fort Wayne Pistons vs. Minneapolis Lakers in 1950).",
)

# Number of facts to embed in each loading screen (cycled via JS)
_FACTS_PER_SCREEN = 12


# ═════════════════════════════════════════════════════════════
# CSS — loading screen styles
# ═════════════════════════════════════════════════════════════

JOSEPH_LOADING_CSS = """<style>
/* ── Joseph Loading Screen ────────────────────────────────── */
@keyframes josephBounceIn {
    0%   { opacity:0; transform:scale(0.3) translateY(40px); }
    50%  { opacity:1; transform:scale(1.08) translateY(-8px); }
    70%  { transform:scale(0.95) translateY(2px); }
    100% { opacity:1; transform:scale(1) translateY(0); }
}
@keyframes josephPulseGlow {
    0%, 100% { box-shadow:0 0 20px rgba(255,94,0,0.4), 0 0 60px rgba(255,94,0,0.1); }
    50%      { box-shadow:0 0 30px rgba(255,94,0,0.6), 0 0 80px rgba(255,94,0,0.2); }
}
@keyframes basketballSpin {
    0%   { transform:rotate(0deg); }
    100% { transform:rotate(360deg); }
}
@keyframes factFadeIn {
    0%   { opacity:0; transform:translateY(12px); }
    100% { opacity:1; transform:translateY(0); }
}
@keyframes factFadeOut {
    0%   { opacity:1; transform:translateY(0); }
    100% { opacity:0; transform:translateY(-12px); }
}
@keyframes dotsAnimation {
    0%   { content:'.'; }
    33%  { content:'..'; }
    66%  { content:'...'; }
}
@keyframes courtLineGlow {
    0%, 100% { opacity:0.15; }
    50%      { opacity:0.30; }
}

.joseph-loading-overlay {
    position:relative;
    width:100%;
    min-height:340px;
    background:
        radial-gradient(circle at 50% 120%, rgba(255,94,0,0.08) 0%, transparent 60%),
        radial-gradient(circle at 20% 20%, rgba(0,240,255,0.04) 0%, transparent 40%),
        linear-gradient(180deg, #0a0f1a 0%, #0d1425 50%, #111b2e 100%);
    border:1px solid rgba(255,94,0,0.25);
    border-radius:16px;
    overflow:hidden;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    padding:32px 24px;
    margin:16px 0;
}

/* ── Basketball court lines (decorative background) ──────── */
.joseph-loading-overlay::before {
    content:'';
    position:absolute;
    top:50%; left:50%;
    width:180px; height:180px;
    border:2px solid rgba(255,94,0,0.12);
    border-radius:50%;
    transform:translate(-50%,-50%);
    animation:courtLineGlow 3s ease-in-out infinite;
    pointer-events:none;
}
.joseph-loading-overlay::after {
    content:'';
    position:absolute;
    top:0; left:50%;
    width:2px; height:100%;
    background:linear-gradient(180deg,
        transparent 0%,
        rgba(255,94,0,0.10) 30%,
        rgba(255,94,0,0.10) 70%,
        transparent 100%);
    animation:courtLineGlow 3s ease-in-out infinite 1.5s;
    pointer-events:none;
}

/* ── Basketball emoji spinner ────────────────────────────── */
.joseph-loading-ball {
    font-size:2rem;
    animation:basketballSpin 2s linear infinite;
    margin-bottom:8px;
    filter:drop-shadow(0 0 8px rgba(255,140,0,0.4));
}

/* ── Avatar container ────────────────────────────────────── */
.joseph-loading-avatar-wrap {
    position:relative;
    animation:josephBounceIn 0.8s cubic-bezier(0.34,1.56,0.64,1) both;
    margin-bottom:16px;
}
.joseph-loading-avatar {
    width:120px; height:120px;
    border-radius:50%;
    object-fit:cover;
    border:3px solid rgba(255,94,0,0.6);
    animation:josephPulseGlow 2.5s ease-in-out infinite;
    background:#0d1425;
}

/* ── Name badge ──────────────────────────────────────────── */
.joseph-loading-name {
    font-family:'Orbitron','Montserrat',sans-serif;
    font-size:0.85rem;
    font-weight:700;
    color:#ff5e00;
    letter-spacing:1.5px;
    text-transform:uppercase;
    margin-bottom:4px;
    text-shadow:0 0 12px rgba(255,94,0,0.3);
}

/* ── "Did you know?" label ───────────────────────────────── */
.joseph-loading-label {
    font-family:'Montserrat',sans-serif;
    font-size:0.72rem;
    font-weight:600;
    color:#00f0ff;
    letter-spacing:2px;
    text-transform:uppercase;
    margin-bottom:10px;
    opacity:0.85;
}

/* ── Fun fact text ───────────────────────────────────────── */
.joseph-loading-fact-container {
    position:relative;
    min-height:72px;
    max-width:560px;
    width:100%;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
}
.joseph-loading-fact {
    font-family:'Montserrat',sans-serif;
    font-size:0.92rem;
    line-height:1.55;
    color:#e2e8f0;
    padding:14px 20px;
    background:rgba(255,94,0,0.06);
    border:1px solid rgba(255,94,0,0.15);
    border-radius:12px;
    transition:opacity 0.5s ease, transform 0.5s ease;
    width:100%;
}

/* ── Status text below fact ──────────────────────────────── */
.joseph-loading-status {
    font-family:'Montserrat',sans-serif;
    font-size:0.75rem;
    color:rgba(226,232,240,0.5);
    margin-top:14px;
    letter-spacing:0.5px;
}
.joseph-loading-status::after {
    content:'...';
    animation:dotsAnimation 1.5s steps(3,end) infinite;
}
</style>"""


# ═════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════

def get_random_facts(count: int = _FACTS_PER_SCREEN) -> list:
    """Return *count* unique random NBA fun facts from the pool."""
    pool = list(NBA_FUN_FACTS)
    random.shuffle(pool)
    return pool[:count]


def render_joseph_loading_screen(
    status_text: str = "Crunching the numbers",
    fact_count: int = _FACTS_PER_SCREEN,
    rotation_seconds: int = 6,
) -> None:
    """Render Joseph's animated loading screen with rotating NBA fun facts.

    Parameters
    ----------
    status_text : str
        The action label shown below the fact (e.g. "Running analysis").
    fact_count : int
        Number of fun facts to embed (cycled via JavaScript).
    rotation_seconds : int
        Seconds between fact rotations.
    """
    if st is None:
        return  # pragma: no cover

    # ── Load avatar ──────────────────────────────────────────
    avatar_b64 = get_joseph_avatar_b64() if _AVATAR_AVAILABLE else ""
    if avatar_b64:
        avatar_html = (
            f'<img class="joseph-loading-avatar" '
            f'src="data:image/png;base64,{avatar_b64}" '
            f'alt="Joseph M. Smith" />'
        )
    else:
        # Fallback: basketball emoji if avatar isn't available
        avatar_html = (
            '<div class="joseph-loading-avatar" '
            'style="display:flex;align-items:center;justify-content:center;'
            'font-size:3rem;">🏀</div>'
        )

    # ── Pick random facts ────────────────────────────────────
    facts = get_random_facts(fact_count)
    safe_status = _html.escape(status_text)

    # Build JSON-safe facts list (escape for JS embedding)
    import json
    facts_json = json.dumps(facts)

    # Unique ID to avoid collisions if multiple loading screens exist
    uid = f"jl_{random.randint(10000, 99999)}"

    html_block = f"""{JOSEPH_LOADING_CSS}
<div class="joseph-loading-overlay" id="{uid}_overlay">
    <div class="joseph-loading-ball">🏀</div>
    <div class="joseph-loading-avatar-wrap">
        {avatar_html}
    </div>
    <div class="joseph-loading-name">Joseph M. Smith</div>
    <div class="joseph-loading-label">🏀 Did You Know? 🏀</div>
    <div class="joseph-loading-fact-container">
        <div class="joseph-loading-fact" id="{uid}_fact">
            {_html.escape(facts[0])}
        </div>
    </div>
    <div class="joseph-loading-status">{safe_status}</div>
</div>
<script>
(function() {{
    var facts = {facts_json};
    var idx = 0;
    var el = document.getElementById("{uid}_fact");
    if (!el || facts.length < 2) return;
    setInterval(function() {{
        el.style.opacity = "0";
        el.style.transform = "translateY(-12px)";
        setTimeout(function() {{
            idx = (idx + 1) % facts.length;
            el.textContent = facts[idx];
            el.style.transform = "translateY(12px)";
            /* Force reflow before animating in */
            void el.offsetWidth;
            el.style.opacity = "1";
            el.style.transform = "translateY(0)";
        }}, 500);
    }}, {rotation_seconds * 1000});
}})();
</script>"""

    st.markdown(html_block, unsafe_allow_html=True)


def joseph_loading_placeholder(
    status_text: str = "Crunching the numbers",
    fact_count: int = _FACTS_PER_SCREEN,
    rotation_seconds: int = 6,
):
    """Create a Streamlit placeholder with Joseph's loading screen.

    Returns the ``st.empty()`` placeholder so callers can clear it
    when the operation completes::

        loader = joseph_loading_placeholder("Running analysis")
        # ... do work ...
        loader.empty()

    Parameters
    ----------
    status_text : str
        Action label shown below the fact card.
    fact_count : int
        Number of fun facts to embed.
    rotation_seconds : int
        Seconds between fact rotations.

    Returns
    -------
    streamlit.delta_generator.DeltaGenerator
        The ``st.empty()`` container (call ``.empty()`` to dismiss).
    """
    if st is None:
        return None  # pragma: no cover

    placeholder = st.empty()
    with placeholder.container():
        render_joseph_loading_screen(
            status_text=status_text,
            fact_count=fact_count,
            rotation_seconds=rotation_seconds,
        )
    return placeholder
