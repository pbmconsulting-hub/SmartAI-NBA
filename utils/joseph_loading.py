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
import json
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
# NBA Fun Facts Pool — 180+ facts about NBA history, players,
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
    "Ja Morant recorded the highest-scoring game by a Grizzlies player with 52 points against the Spurs in 2023.",
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

    # ── Rivalries & iconic matchups ──────────────────────────
    "The Lakers-Celtics rivalry is the most storied in NBA history — they've met 12 times in the Finals.",
    "The 1990s Bulls-Knicks rivalry was so intense that their playoff games averaged under 90 points per team.",
    "Bird and Magic's rivalry began in the 1979 NCAA championship game and carried into the NBA for a decade.",
    "The Pistons' 'Bad Boys' era featured the 'Jordan Rules' — a set of physical defensive strategies designed to stop Michael Jordan.",
    "The 2002 Western Conference Finals between the Kings and Lakers is considered one of the most controversial series ever.",
    "The Knicks and Heat rivalry in the 1990s was so physical that it led to multiple rule changes about hand-checking.",
    "The Celtics-76ers rivalry dates back to the 1960s when Bill Russell and Wilt Chamberlain battled for Eastern supremacy.",
    "Tim Duncan's block on Shaq's dunk attempt in the 2003 playoffs is one of the greatest defensive plays in NBA history.",
    "The 'Malice at the Palace' brawl in 2004 between Pistons and Pacers led to the NBA's strictest-ever suspensions.",
    "LeBron James and Stephen Curry met in four consecutive NBA Finals from 2015 to 2018.",

    # ── International basketball & global impact ─────────────
    "Yao Ming was the #1 overall pick in 2002 and helped grow the NBA's popularity in China to over 300 million viewers.",
    "Dirk Nowitzki was the first European-born player to win NBA Finals MVP in 2011.",
    "The 1992 'Dream Team' featuring Jordan, Bird, and Magic is considered the greatest sports team ever assembled.",
    "Manu Ginóbili is the only player to have won an Olympic gold medal, a EuroLeague title, and an NBA championship.",
    "Luka Dončić won the EuroLeague MVP at age 19 before being drafted 3rd overall by the Dallas Mavericks.",
    "Giannis Antetokounmpo moved from Nigeria to Greece as a child and didn't start playing basketball until age 12.",
    "Tony Parker, born in Belgium and raised in France, won four NBA championships and a Finals MVP with the Spurs.",
    "Pau Gasol won two NBA championships with the Lakers and is Spain's all-time leading scorer in international play.",
    "Hakeem Olajuwon, born in Nigeria, learned basketball playing soccer — his footwork in the post was legendary.",
    "The NBA has featured players from over 40 different countries since 2000.",

    # ── Iconic individual moments ────────────────────────────
    "Michael Jordan's 'Last Shot' in the 1998 Finals — a pull-up jumper over Bryon Russell — clinched his sixth title.",
    "Kawhi Leonard's buzzer-beater against the 76ers in 2019 bounced four times on the rim before going in.",
    "Ray Allen's corner three-pointer in Game 6 of the 2013 Finals saved the Heat's season and is known as 'The Shot.'",
    "Derek Fisher hit a game-winning shot with 0.4 seconds left against the Spurs in the 2004 Western Conference Semis.",
    "Dame Lillard waved goodbye to the Thunder after hitting a 37-foot series-clinching three in the 2019 playoffs.",
    "Vince Carter's dunk over 7'2\" Frédéric Weis at the 2000 Olympics is called 'Le Dunk de la Mort' — the Dunk of Death.",
    "Julius Erving's baseline reverse layup in the 1980 Finals is one of the most replayed highlights in NBA history.",
    "Devin Booker scored 70 points against the Celtics in 2017, becoming the youngest player to reach that mark.",
    "Steph Curry hit 402 three-pointers in a single season in 2015-16, shattering his own record of 286.",
    "Willis Reed limped onto the court for Game 7 of the 1970 Finals despite a torn thigh muscle, inspiring the Knicks to a championship.",

    # ── Arenas, courts & venues ──────────────────────────────
    "Madison Square Garden in New York City is known as 'The Mecca of Basketball' and has been open since 1968.",
    "The Staples Center (now Crypto.com Arena) hosted both the Lakers and Clippers under the same roof for over 20 years.",
    "Oracle Arena in Oakland was nicknamed 'Roaracle' because Warriors fans were considered the loudest in the NBA.",
    "The Chicago Bulls play at the United Center, which features a bronze statue of Michael Jordan out front.",
    "The Boston Celtics' TD Garden hangs 17 championship banners from the rafters — more than any other NBA arena.",
    "The San Antonio Spurs' arena once had a resident bat colony that occasionally flew onto the court during games.",
    "Every NBA court is made of hard maple wood, specifically sugar maple from forests in the northern United States.",
    "The Milwaukee Bucks' Fiserv Forum was designed with the largest outdoor public plaza of any NBA arena.",
    "The Phoenix Suns' arena has a retractable roof section that can let in natural sunlight during daytime events.",
    "The NBA mandates specific court dimensions, but teams can customize the paint, logo, and sideline designs.",

    # ── Jerseys, shoes & style ───────────────────────────────
    "Michael Jordan's Air Jordan sneakers were originally banned by the NBA for violating uniform rules. Nike paid the fines.",
    "The NBA introduced the 'City Edition' jersey concept in 2017, allowing teams to create unique alternate designs each year.",
    "Allen Iverson's cultural impact extended beyond basketball — his cornrows and baggy clothes led to the NBA's dress code in 2005.",
    "LeBron James signed a lifetime deal with Nike worth over $1 billion — the largest athlete endorsement in history.",
    "Wilt Chamberlain wore #13 throughout his career, a number most players avoided due to superstition.",
    "The original NBA jerseys were made of wool, which made players incredibly hot during games.",
    "Chuck Taylor All-Stars were the most popular basketball shoe for decades before modern signature sneakers took over.",
    "The NBA switched from short shorts to baggy ones in the 1990s largely due to Michael Jordan's preference for longer shorts.",
    "Kobe Bryant wore #8 for his first 10 seasons, then switched to #24 — both numbers are retired by the Lakers.",
    "The NBA has no rule against the number 69. However, Dennis Rodman requested it and was denied by the league.",

    # ── Analytics & strategy evolution ────────────────────────
    "The Houston Rockets' 'Moreyball' era popularized the strategy of shooting only threes and layups, minimizing mid-range shots.",
    "In the 2022-23 season, NBA teams averaged 34.2 three-point attempts per game, up from 18.0 in the 2004-05 season.",
    "The 'Hack-a-Shaq' strategy led to rule changes limiting intentional fouling away from the ball in the final two minutes.",
    "PER (Player Efficiency Rating) was created by John Hollinger and became one of the first widely-used advanced stats.",
    "The Golden State Warriors' 'Death Lineup' small-ball unit changed NBA strategy by proving a team could win without a true center.",
    "True Shooting Percentage accounts for free throws and three-pointers, giving a more accurate picture than regular FG%.",
    "The concept of 'pace and space' — spreading the floor with shooters — has become the dominant offensive philosophy in modern NBA.",
    "Win Shares, developed by basketball statistician Dean Oliver, attempts to distribute credit for team wins among individual players.",
    "The corner three-pointer is the most efficient shot in basketball — it's the shortest three-point distance at 22 feet.",
    "Box Plus/Minus (BPM) estimates a player's contribution per 100 possessions relative to an average player.",

    # ── Records that may never be broken ─────────────────────
    "Wilt Chamberlain had 55 rebounds in a single game in 1960 — a record that seems virtually unbreakable.",
    "Scott Skiles dished out 30 assists in a single game in 1990 — nobody has come within 6 assists of that record since.",
    "The 1995-96 Bulls went 72-10, a record that stood for 20 years until the Warriors' 73-9 in 2015-16.",
    "John Stockton's 15,806 career assists are nearly 4,000 ahead of Jason Kidd in second place.",
    "Wilt Chamberlain averaged 48.5 minutes per game in the 1961-62 season — NBA games are only 48 minutes long.",
    "Bill Russell grabbed 51 rebounds in a single game in 1960 — modern big men rarely get 20 in a game.",
    "The Celtics' 8 consecutive championships from 1959-1966 is a record that no team will likely ever approach.",
    "Elgin Baylor scored 61 points in an NBA Finals game in 1962 — a Finals record that stood for over 30 years.",
    "AC Green played 1,192 consecutive games — the NBA's all-time 'Iron Man' streak spanning 16 seasons.",
    "Bob Cousy dished 28 assists in a game in 1959 — a record that stood for 31 years until Scott Skiles broke it.",

    # ── Basketball science & physicality ─────────────────────
    "The average NBA player can jump roughly 28 inches vertically; elite leapers like Zach LaVine exceed 46 inches.",
    "An NBA regulation basketball has a circumference of 29.5 inches and is inflated to between 7.5 and 8.5 PSI.",
    "Studies show NBA players make about 4,000 decisions per game involving passing, shooting, or movement.",
    "The fastest recorded sprint speed by an NBA player during a game is approximately 20.5 mph.",
    "NBA players experience forces of up to 7 times their body weight when landing from a dunk.",
    "The average NBA game features over 200 possessions combined between both teams.",
    "A perfectly shot basketball enters the hoop at an angle of roughly 45 degrees for the highest probability of going in.",
    "Professional basketball players typically have a wingspan-to-height ratio above 1.06 — longer arms than average.",
    "Studies have found that NBA players' reaction times average about 200 milliseconds — 30% faster than the general population.",
    "The 'hot hand' phenomenon in basketball was debated for decades until 2018 research confirmed it exists statistically.",

    # ── Front office, trades & business ──────────────────────
    "The NBA generates over $10 billion in annual revenue, with each franchise valued at over $2 billion on average.",
    "The most lopsided trade in NBA history is often cited as the 1996 deal that sent Kobe Bryant to the Lakers for Vlade Divac.",
    "The NBA's luxury tax system penalizes teams that exceed the salary cap, with repeat offenders paying quadruple the overage.",
    "The Boston Celtics fleeced the Brooklyn Nets in a 2013 trade that netted picks which became Jayson Tatum and Jaylen Brown.",
    "The Harden-for-everyone trade from OKC to Houston in 2012 is considered one of the worst trades for the Thunder.",
    "NBA teams spend millions on sports science departments including sleep specialists, nutritionists, and biomechanics experts.",
    "The NBA's two-way contract was introduced in 2017, allowing teams to shuttle players between the NBA and G League.",
    "The Cleveland Cavaliers won the #1 draft pick four times in a 14-year span (2003, 2011, 2013, 2014).",
    "The Golden State Warriors' value increased from $450 million in 2012 to over $7 billion by 2024.",
    "Pat Riley's 'Big Three' concept in Miami — assembling LeBron, Wade, and Bosh — changed how NBA superstars form teams.",

    # ── All-Star Game & celebrations ─────────────────────────
    "The NBA All-Star Game was first played in 1951 in Boston, with the East beating the West 111-94.",
    "The 2003 All-Star Game in Atlanta featured Michael Jordan's last All-Star appearance — he scored 20 points.",
    "The Slam Dunk Contest debuted in 1984 and was won by Larry Nance Sr. — but it became iconic when Jordan entered in 1987.",
    "Vince Carter's 2000 Slam Dunk Contest performance is widely considered the greatest dunk contest of all time.",
    "Kobe Bryant and Tim Duncan were co-MVPs of the 2001 All-Star Game — the last time the award was shared.",
    "The NBA Three-Point Contest has been won by Larry Bird, Craig Hodges, and Steph Curry — each winning it multiple times.",
    "The All-Star Weekend's Skills Challenge tests big men against guards in dribbling, passing, and shooting drills.",
    "The Rising Stars Challenge showcases the best rookies and sophomores — LeBron dominated it in both his appearances.",
    "Anthony Davis scored 52 points in the 2017 All-Star Game, breaking Wilt Chamberlain's All-Star scoring record of 42.",
    "In 2020, the NBA renamed the All-Star MVP award to the Kobe Bryant MVP Award after Kobe's tragic passing.",

    # ── Underdogs & sleeper stories ──────────────────────────
    "The 2011 Mavericks were the biggest underdog to win the title in modern NBA history, upsetting the LeBron-Wade-Bosh Heat.",
    "Jimmy Butler went undrafted out of high school, was homeless as a teen, and became a six-time All-Star.",
    "The 2004 Pistons had no player average over 17 points per game but won the championship through elite team defense.",
    "Isaiah Thomas (5'9\") averaged 28.9 PPG for the Celtics in 2016-17 despite being one of the shortest players in the league.",
    "Ben Wallace went undrafted in 1996 and became a four-time Defensive Player of the Year and NBA champion.",
    "The 1994 and 1995 Rockets won back-to-back titles — the only championships won without a top-2 seed in the West.",
    "Udonis Haslem went undrafted, played for a league in France, and came back to win three NBA championships with the Heat.",
    "The 2007 Warriors pulled off a historic first-round upset of the top-seeded Dallas Mavericks as the 8th seed.",
    "Fred VanVleet went undrafted in 2016 and became a key starter on the 2019 champion Toronto Raptors.",
    "The 1999 Knicks became the first 8th seed to reach the NBA Finals, led by Patrick Ewing's injured replacement, Allan Houston.",

    # ── Forgotten legends & hidden gems ──────────────────────
    "Pete Maravich averaged 44.2 PPG in college without a three-point line and a shot clock — still the NCAA record.",
    "George Mikan was so dominant in the 1940s-50s that the NBA widened the lane from 6 feet to 12 feet because of him.",
    "Nate Archibald is the only player in NBA history to lead the league in both scoring and assists in the same season.",
    "Bob Pettit was the first NBA player to score 20,000 career points and the first to win the All-Star Game MVP.",
    "Elvin Hayes scored 39 points against Lew Alcindor (Kareem) in the 1968 'Game of the Century' watched by 52,000 fans.",
    "Walt Frazier's Game 7 performance in the 1970 Finals — 36 points, 19 assists — is one of the greatest Finals games ever.",
    "Dave Cowens, at just 6'9\", won MVP in 1973 as one of the shortest centers to ever dominate the league.",
    "Moses Malone's famous '4-4-4' prediction for the 1983 playoffs almost came true — the Sixers went 12-1.",
    "Earl Monroe was nicknamed 'Black Jesus' for his mesmerizing playground-style moves that revolutionized guard play.",
    "Rick Barry shot free throws underhanded ('granny style') and holds one of the highest career free throw percentages ever.",

    # ── Coaching strategy & philosophy ────────────────────────
    "Phil Jackson used Zen Buddhism and Native American spirituality to motivate players — earning him the nickname 'Zen Master.'",
    "The 'Triangle Offense' used by Phil Jackson was actually created by assistant coach Tex Winter.",
    "Don Nelson pioneered 'Nellie Ball' — a fast-paced, three-point-heavy style that was decades ahead of its time.",
    "The Detroit Pistons' 'Bad Boys' defense under Chuck Daly was so physical it led to changes in how referees called fouls.",
    "Rick Carlisle is known for making more in-game adjustments than almost any other coach in NBA history.",
    "Doc Rivers earned his nickname from his grandmother and Julius Erving — it has nothing to do with his coaching style.",
    "Mike D'Antoni's 'Seven Seconds or Less' offense with the Suns in the mid-2000s was the precursor to today's pace-and-space NBA.",
    "Red Holzman's coaching philosophy was simple: 'See the ball, hit the open man' — it won two championships for the Knicks.",
    "Larry Brown is the only coach to win both an NCAA championship and an NBA championship.",
    "Tyronn Lue was the first rookie head coach to win an NBA title since Pat Riley in 1982.",

    # ── Wild stats & oddities ────────────────────────────────
    "In 1983, the Denver Nuggets and Detroit Pistons combined for 370 points in a triple-overtime game — the highest-scoring NBA game ever.",
    "The NBA once had a rule where the team that was behind could choose which basket to shoot at to start the 4th quarter.",
    "Rasheed Wallace holds the record for most technical fouls in a single season with 41 in 2000-01.",
    "Ron Artest (Metta World Peace) legally changed his name and thanked his psychiatrist in his championship acceptance speech.",
    "The NBA's shortest-ever game delay was caused by a bat flying around the court in San Antonio.",
    "Draymond Green is the only player in NBA history to record a triple-double without scoring in double figures.",
    "In 1998, the Vancouver Grizzlies and Toronto Raptors played an NBA game in Tokyo, Japan.",
    "Karl Malone and John Stockton played together for 18 seasons — the longest-tenured duo in NBA history.",
    "James Harden once recorded a 60-point triple-double, joining Wilt Chamberlain as the only players to do so at the time.",
    "The NBA once considered adding a 4-point line at 30 feet but ultimately rejected the idea.",
)

# Number of facts to embed in each loading screen (cycled via JS)
_FACTS_PER_SCREEN = 15


# ═════════════════════════════════════════════════════════════
# CSS — loading screen styles (glassmorphic dark theme)
# ═════════════════════════════════════════════════════════════

JOSEPH_LOADING_CSS = """<style>
/* ── Joseph Loading Screen ────────────────────────────────── */
@keyframes josephBounceIn {
    0%   { opacity:0; transform:scale(0.3) translateY(40px); }
    40%  { opacity:1; transform:scale(1.12) translateY(-12px); }
    65%  { transform:scale(0.95) translateY(4px); }
    85%  { transform:scale(1.03) translateY(-2px); }
    100% { opacity:1; transform:scale(1) translateY(0); }
}
@keyframes josephPulseGlow {
    0%, 100% { box-shadow:0 0 20px rgba(255,94,0,0.35),
                          0 0 60px rgba(255,94,0,0.08),
                          inset 0 0 15px rgba(255,94,0,0.05); }
    50%      { box-shadow:0 0 35px rgba(255,94,0,0.55),
                          0 0 90px rgba(255,94,0,0.15),
                          inset 0 0 20px rgba(255,94,0,0.10); }
}
@keyframes avatarRingRotate {
    0%   { transform:translate(-50%,-50%) rotate(0deg); }
    100% { transform:translate(-50%,-50%) rotate(360deg); }
}
@keyframes basketballBounce {
    0%, 100% { transform:translateY(0) rotate(0deg); }
    25%      { transform:translateY(-14px) rotate(90deg); }
    50%      { transform:translateY(0) rotate(180deg); }
    75%      { transform:translateY(-8px) rotate(270deg); }
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
    0%, 100% { opacity:0.12; }
    50%      { opacity:0.28; }
}
@keyframes particleDrift {
    0%   { transform:translateY(0) translateX(0) scale(1); opacity:0; }
    15%  { opacity:0.6; }
    85%  { opacity:0.3; }
    100% { transform:translateY(-200px) translateX(40px) scale(0.3); opacity:0; }
}
@keyframes shimmerSlide {
    0%   { background-position:-200% center; }
    100% { background-position:200% center; }
}
@keyframes progressPulse {
    0%, 100% { opacity:0.7; width:20%; }
    50%      { opacity:1; width:60%; }
}
@keyframes glowBreath {
    0%, 100% { filter:blur(30px) brightness(0.8); }
    50%      { filter:blur(45px) brightness(1.2); }
}

/* ── Outer wrapper ───────────────────────────────────────── */
.joseph-loading-overlay {
    position:relative;
    width:100%;
    min-height:400px;
    background:
        radial-gradient(ellipse at 50% 0%, rgba(255,94,0,0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 80%, rgba(0,240,255,0.04) 0%, transparent 40%),
        radial-gradient(ellipse at 20% 90%, rgba(200,0,255,0.03) 0%, transparent 40%),
        linear-gradient(180deg, #080c18 0%, #0a1020 40%, #0d1428 70%, #101830 100%);
    border:1px solid rgba(255,94,0,0.20);
    border-radius:20px;
    overflow:hidden;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    padding:36px 28px 32px;
    margin:16px 0;
    backdrop-filter:blur(2px);
    -webkit-backdrop-filter:blur(2px);
}

/* ── Ambient glow behind avatar ──────────────────────────── */
.joseph-loading-ambient-glow {
    position:absolute;
    top:35%; left:50%;
    width:220px; height:220px;
    border-radius:50%;
    background:radial-gradient(circle,
        rgba(255,94,0,0.18) 0%,
        rgba(255,94,0,0.06) 40%,
        transparent 70%);
    transform:translate(-50%,-50%);
    animation:glowBreath 4s ease-in-out infinite;
    pointer-events:none;
    z-index:0;
}

/* ── Basketball court lines (decorative background) ──────── */
.joseph-loading-overlay::before {
    content:'';
    position:absolute;
    top:50%; left:50%;
    width:200px; height:200px;
    border:2px solid rgba(255,94,0,0.08);
    border-radius:50%;
    transform:translate(-50%,-50%);
    animation:courtLineGlow 3.5s ease-in-out infinite;
    pointer-events:none;
}
.joseph-loading-overlay::after {
    content:'';
    position:absolute;
    top:0; left:50%;
    width:1px; height:100%;
    background:linear-gradient(180deg,
        transparent 0%,
        rgba(255,94,0,0.07) 25%,
        rgba(255,94,0,0.07) 75%,
        transparent 100%);
    animation:courtLineGlow 3.5s ease-in-out infinite 1.5s;
    pointer-events:none;
}

/* ── Free-throw semi-circle ──────────────────────────────── */
.joseph-loading-court-ft {
    position:absolute;
    top:50%; left:50%;
    width:120px; height:60px;
    border:1.5px solid rgba(255,94,0,0.06);
    border-bottom:none;
    border-radius:120px 120px 0 0;
    transform:translate(-50%,-70%);
    animation:courtLineGlow 3.5s ease-in-out infinite 0.8s;
    pointer-events:none;
}

/* ── Three-point arc ─────────────────────────────────────── */
.joseph-loading-court-arc {
    position:absolute;
    top:50%; left:50%;
    width:280px; height:140px;
    border:1.5px solid rgba(255,94,0,0.04);
    border-bottom:none;
    border-radius:280px 280px 0 0;
    transform:translate(-50%,-55%);
    animation:courtLineGlow 3.5s ease-in-out infinite 2s;
    pointer-events:none;
}

/* ── Floating particles ──────────────────────────────────── */
.joseph-loading-particles {
    position:absolute; inset:0;
    overflow:hidden; pointer-events:none; z-index:0;
}
.joseph-loading-particle {
    position:absolute;
    width:3px; height:3px;
    border-radius:50%;
    background:rgba(255,94,0,0.35);
    animation:particleDrift 6s ease-in-out infinite;
}
.joseph-loading-particle:nth-child(2) {
    left:20%; bottom:10%; animation-delay:1s; animation-duration:7s;
    background:rgba(0,240,255,0.25); width:2px; height:2px;
}
.joseph-loading-particle:nth-child(3) {
    left:70%; bottom:20%; animation-delay:2.5s; animation-duration:8s;
    background:rgba(255,94,0,0.25);
}
.joseph-loading-particle:nth-child(4) {
    left:85%; bottom:5%; animation-delay:0.5s; animation-duration:5.5s;
    background:rgba(0,240,255,0.20); width:2px; height:2px;
}
.joseph-loading-particle:nth-child(5) {
    left:35%; bottom:15%; animation-delay:3.5s; animation-duration:9s;
    background:rgba(200,0,255,0.15);
}
.joseph-loading-particle:nth-child(6) {
    left:55%; bottom:8%; animation-delay:4s; animation-duration:6.5s;
    background:rgba(255,94,0,0.20); width:2px; height:2px;
}

/* ── Basketball emoji ────────────────────────────────────── */
.joseph-loading-ball {
    font-size:1.8rem;
    animation:basketballBounce 2s ease-in-out infinite;
    margin-bottom:6px;
    filter:drop-shadow(0 0 10px rgba(255,140,0,0.5));
    z-index:1;
}

/* ── Avatar container ────────────────────────────────────── */
.joseph-loading-avatar-wrap {
    position:relative;
    animation:josephBounceIn 0.9s cubic-bezier(0.34,1.56,0.64,1) both;
    margin-bottom:14px;
    z-index:1;
}
/* Animated ring around avatar */
.joseph-loading-avatar-ring {
    position:absolute;
    top:50%; left:50%;
    width:140px; height:140px;
    border-radius:50%;
    border:2px solid transparent;
    border-top:2px solid rgba(255,94,0,0.6);
    border-right:2px solid rgba(0,240,255,0.4);
    border-bottom:2px solid rgba(255,94,0,0.3);
    border-left:2px solid rgba(0,240,255,0.2);
    animation:avatarRingRotate 4s linear infinite;
    pointer-events:none;
}
.joseph-loading-avatar {
    width:120px; height:120px;
    border-radius:50%;
    object-fit:cover;
    border:3px solid rgba(255,94,0,0.5);
    animation:josephPulseGlow 3s ease-in-out infinite;
    background:#0d1425;
}

/* ── Name badge ──────────────────────────────────────────── */
.joseph-loading-name {
    font-family:'Orbitron','Montserrat',sans-serif;
    font-size:0.9rem;
    font-weight:700;
    color:#ff5e00;
    letter-spacing:2px;
    text-transform:uppercase;
    margin-bottom:2px;
    text-shadow:0 0 16px rgba(255,94,0,0.35);
    z-index:1;
}
.joseph-loading-subtitle {
    font-family:'Montserrat',sans-serif;
    font-size:0.65rem;
    font-weight:500;
    color:rgba(0,240,255,0.55);
    letter-spacing:3px;
    text-transform:uppercase;
    margin-bottom:12px;
    z-index:1;
}

/* ── "Did you know?" label ───────────────────────────────── */
.joseph-loading-label {
    font-family:'Montserrat',sans-serif;
    font-size:0.7rem;
    font-weight:700;
    color:#00f0ff;
    letter-spacing:2.5px;
    text-transform:uppercase;
    margin-bottom:10px;
    opacity:0.9;
    z-index:1;
    text-shadow:0 0 10px rgba(0,240,255,0.2);
}

/* ── Fun fact card (glassmorphic) ────────────────────────── */
.joseph-loading-fact-container {
    position:relative;
    min-height:80px;
    max-width:580px;
    width:100%;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    z-index:1;
}
.joseph-loading-fact {
    font-family:'Montserrat',sans-serif;
    font-size:0.92rem;
    line-height:1.6;
    color:#e8edf5;
    padding:16px 24px;
    background:rgba(255,255,255,0.03);
    backdrop-filter:blur(12px);
    -webkit-backdrop-filter:blur(12px);
    border:1px solid rgba(255,94,0,0.12);
    border-radius:14px;
    transition:opacity 0.5s ease, transform 0.5s ease;
    width:100%;
    box-shadow:0 4px 24px rgba(0,0,0,0.25),
               inset 0 1px 0 rgba(255,255,255,0.04);
    position:relative;
    overflow:hidden;
}
/* Holographic shimmer overlay on fact card */
.joseph-loading-fact::before {
    content:'';
    position:absolute; inset:0;
    background:linear-gradient(110deg,
        transparent 20%,
        rgba(255,94,0,0.04) 40%,
        rgba(0,240,255,0.03) 60%,
        transparent 80%);
    background-size:200% 100%;
    animation:shimmerSlide 6s linear infinite;
    pointer-events:none;
    border-radius:14px;
}

/* ── Animated progress bar ───────────────────────────────── */
.joseph-loading-progress-wrap {
    width:100%;
    max-width:320px;
    height:3px;
    background:rgba(255,255,255,0.05);
    border-radius:3px;
    margin-top:18px;
    overflow:hidden;
    z-index:1;
}
.joseph-loading-progress-bar {
    height:100%;
    border-radius:3px;
    background:linear-gradient(90deg,
        rgba(255,94,0,0.7),
        rgba(0,240,255,0.6),
        rgba(255,94,0,0.7));
    background-size:200% 100%;
    animation:progressPulse 3s ease-in-out infinite,
             shimmerSlide 2s linear infinite;
}

/* ── Status text below fact ──────────────────────────────── */
.joseph-loading-status {
    font-family:'Montserrat',sans-serif;
    font-size:0.73rem;
    color:rgba(226,232,240,0.45);
    margin-top:10px;
    letter-spacing:0.5px;
    z-index:1;
}
.joseph-loading-status::after {
    content:'...';
    animation:dotsAnimation 1.5s steps(3,end) infinite;
}

/* ── Responsive adjustments ──────────────────────────────── */
@media (max-width: 600px) {
    .joseph-loading-overlay { min-height:340px; padding:24px 16px 22px; }
    .joseph-loading-avatar { width:100px; height:100px; }
    .joseph-loading-avatar-ring { width:120px; height:120px; }
    .joseph-loading-fact { font-size:0.84rem; padding:12px 16px; }
    .joseph-loading-name { font-size:0.78rem; }
    .joseph-loading-fact-container { max-width:95%; }
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
    facts_json = json.dumps(facts)

    # Unique ID to avoid collisions if multiple loading screens exist
    uid = f"jl_{random.randint(10000, 99999)}"

    html_block = f"""{JOSEPH_LOADING_CSS}
<div class="joseph-loading-overlay" id="{uid}_overlay">
    <!-- Decorative court elements -->
    <div class="joseph-loading-court-ft"></div>
    <div class="joseph-loading-court-arc"></div>
    <div class="joseph-loading-ambient-glow"></div>
    <!-- Floating particles -->
    <div class="joseph-loading-particles">
        <div class="joseph-loading-particle" style="left:10%;bottom:5%"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
    </div>
    <div class="joseph-loading-ball">🏀</div>
    <div class="joseph-loading-avatar-wrap">
        <div class="joseph-loading-avatar-ring"></div>
        {avatar_html}
    </div>
    <div class="joseph-loading-name">Joseph M. Smith</div>
    <div class="joseph-loading-subtitle">Your NBA Analytics Expert</div>
    <div class="joseph-loading-label">🏀 Did You Know? 🏀</div>
    <div class="joseph-loading-fact-container">
        <div class="joseph-loading-fact" id="{uid}_fact">
            {_html.escape(facts[0])}
        </div>
    </div>
    <div class="joseph-loading-progress-wrap">
        <div class="joseph-loading-progress-bar"></div>
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
