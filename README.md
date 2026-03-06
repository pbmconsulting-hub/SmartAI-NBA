# 🏀 SmartAI-NBA v7

**Your Personal NBA Prop Betting Analysis Engine — Built Locally, No APIs Needed**

SmartAI-NBA v7 is a local web app (Streamlit) that analyzes PrizePicks, Underdog Fantasy,
and DraftKings Pick6 props to find the highest-probability bets using Monte Carlo simulation
and directional force analysis. All math is built from scratch — no external libraries except Streamlit.

---

## 🚀 Quick Start (Complete Beginner Guide)

### Step 1: Make Sure Python is Installed

1. Open your terminal (Mac: search "Terminal", Windows: search "Command Prompt" or "PowerShell")
2. Type: `python --version` and press Enter
3. You should see something like `Python 3.10.x` or higher
4. If you see an error, download Python from [python.org](https://python.org) and install it

### Step 2: Navigate to the App Folder

In your terminal, type:
```bash
cd path/to/SmartAI-NBA
```

Replace `path/to/SmartAI-NBA` with the actual folder path (e.g., `cd ~/Downloads/SmartAI-NBA`).

### Step 3: Install Dependencies

```bash
pip install streamlit nba_api
```

Or using the requirements file:
```bash
pip install -r requirements.txt
```

### Step 4: Run the App

```bash
streamlit run app.py
```

Your browser will automatically open to `http://localhost:8501` with the app running!

---

## 📁 App Structure

```
SmartAI-NBA/
├── app.py                              # Main entry point — run this!
├── requirements.txt                    # streamlit + nba_api
├── README.md                           # This file
│
├── pages/
│   ├── 1_🏀_Todays_Games.py           # Select tonight's games (+ auto-load)
│   ├── 2_📥_Import_Props.py           # Enter/upload prop lines
│   ├── 3_🏆_Analysis.py               # Run analysis + see top picks
│   ├── 4_🎰_Entry_Builder.py          # Build optimal parlays
│   ├── 5_🚫_Avoid_List.py             # What NOT to bet
│   ├── 6_📊_Model_Health.py           # Track performance
│   ├── 7_⚙️_Settings.py              # Configure settings
│   └── 8_🔄_Update_Data.py           # Fetch live NBA data ← NEW!
│
├── engine/
│   ├── math_helpers.py                 # All math from scratch (no scipy)
│   ├── simulation.py                   # Monte Carlo simulator
│   ├── projections.py                  # Player stat projections
│   ├── edge_detection.py              # Find betting edges
│   ├── entry_optimizer.py             # Build optimal entries
│   └── confidence.py                  # Confidence + tier system
│
├── data/
│   ├── data_manager.py                # Load/save CSV data
│   ├── live_data_fetcher.py           # Live NBA data fetcher ← NEW!
│   ├── sample_players.csv             # Player stats (sample OR live)
│   ├── sample_props.csv               # 40 sample prop lines
│   ├── teams.csv                      # All 30 NBA teams with pace/ratings
│   ├── defensive_ratings.csv          # Team defense by position
│   └── last_updated.json              # Timestamps (created after first update)
│
├── tracking/
│   ├── bet_tracker.py                 # Log bets + results
│   └── database.py                    # SQLite wrapper
│
└── db/
    └── smartai_nba.db                 # Created automatically on first run
```

---

## 📖 What Each Page Does

### 🏠 Home (app.py)
The dashboard. Shows status, quick-start guide, and links to all pages.

### 🏀 Page 1: Today's Games
Select which teams are playing tonight. Enter the Vegas spread (who's favored)
and the over/under total for each game. This helps the model adjust for:
- Blowout risk (large spreads = stars might sit late)
- Game environment (high totals = fast-paced, high-scoring game)
- Home/away advantage

### 📥 Page 2: Import Props
Enter the prop lines from PrizePicks, Underdog, or DraftKings.
You can:
- Add props one at a time using the form
- Upload a CSV file
- Paste CSV data directly into the text box

Sample props are pre-loaded so you can see the app working immediately!

### 🏆 Page 3: Analysis (Main Page)
Click **Run Analysis** to simulate each prop. For every prop you'll see:
- **Probability**: % chance of going over (or under) the line
- **Edge**: How far above 50% the probability is (bigger = better)
- **Tier**: Platinum 💎, Gold 🥇, Silver 🥈, or Bronze 🥉
- **Direction**: OVER or UNDER
- **Forces**: All the factors pushing the stat up or down
- **Distribution**: Range of likely outcomes (10th, 50th, 90th percentile)

### 🎰 Page 4: Entry Builder
Build optimal parlays. The engine tests all combinations of top picks
and finds the ones with the highest **Expected Value (EV)**. You'll see:
- Exact EV in dollars for each entry
- ROI percentage
- Probability breakdown (chance of hitting 2/3, 3/3, etc.)

You can also build custom entries by selecting picks manually.

### 🚫 Page 5: Avoid List
Shows which props to skip and explains exactly WHY:
- "Insufficient edge" = too close to a coin flip
- "High variance stat" = too unpredictable to bet reliably
- "Conflicting forces" = model is uncertain, both sides nearly equal
- "Blowout risk" = player may not play full minutes

### 📊 Page 6: Model Health
After games, log your results here. The app tracks:
- Overall win rate
- Win rate by tier (Platinum should beat Gold, Gold should beat Silver, etc.)
- Win rate by platform and stat type
- Helps you see if the model is working!

### ⚙️ Page 7: Settings
Configure:
- **Simulation Depth**: 500 (fast) to 5,000 (most accurate)
- **Minimum Edge**: How much edge before showing a pick (default: 5%)
- **Entry Fee**: Default dollar amount for EV calculations
- **Advanced factors**: Home court boost, fatigue sensitivity, etc.

### 🔄 Page 8: Update Data *(NEW!)*
Fetch live, real-time NBA data from the official NBA stats API:
- **Fetch Tonight's Games** — Auto-loads tonight's real matchups
- **Update Player Stats** — Pulls current season averages for all players
- **Update Team Stats** — Pulls real pace, ORTG, DRTG for all teams
- **Update Everything** — Does all of the above in one click

See the **Live Data** section below for full details.

---

## 🔴 Live NBA Data

SmartAI-NBA can use **real, up-to-date NBA stats** via the free `nba_api` library.
No API key or account needed!

### Installing nba_api

```bash
python -m pip install nba_api
```

Or install all dependencies at once:
```bash
pip install -r requirements.txt
```

### How to Use Live Data

1. Install `nba_api` (see above)
2. Run the app: `streamlit run app.py`
3. Go to the **🔄 Update Data** page (page 8 in the sidebar)
4. Click **"🔄 Update Everything"** to fetch all live stats
5. Wait a few minutes (the fetcher is polite — it delays 1.5s between calls)
6. All other pages will now use real stats!

### When to Update

- **Before each betting session** for best accuracy
- Player and team situations change throughout the season
- The home page shows when data was last updated

### What Gets Updated

| Data | Source | File Updated |
|------|--------|-------------|
| Player stats (PPG, RPG, APG, etc.) | LeagueDashPlayerStats | `sample_players.csv` |
| Standard deviations | PlayerGameLog (last 20 games) | `sample_players.csv` |
| Team pace + ratings (ORTG/DRTG) | LeagueDashTeamStats | `teams.csv` |
| Defensive ratings by position | Calculated from team drtg | `defensive_ratings.csv` |
| Tonight's games | ScoreboardV2 | Session state |

### Sample Data vs Live Data

The app ships with **sample data** so it works immediately without any setup.
The sample data is from a recent NBA season but may be slightly outdated.

After running **Update Everything**, the CSVs are overwritten with real data.
The home page shows a banner indicating which type of data you're using.

---

## 📊 How to Add Your Own Data

### Adding a New Player
Open `data/sample_players.csv` and add a new row:
```csv
Player Name,TEAM,POS,minutes,pts,reb,ast,3s,stl,blk,to,ft%,usage,pts_std,reb_std,ast_std,3s_std
Jaylen Wells,MEM,SF,28.0,14.5,3.2,2.1,1.8,0.9,0.3,1.2,0.82,18.0,4.2,1.4,1.0,0.8
```

### Updating Stats
Just edit the numbers in `data/sample_players.csv`. The app reads it fresh each time.

### Entering Tonight's Props
Go to **📥 Import Props** and either:
1. Type them in the form (one at a time)
2. Upload a CSV using the template provided
3. Paste CSV text directly

---

## 🔧 Troubleshooting

### "streamlit: command not found"
Run: `pip install streamlit` first.

### "ModuleNotFoundError: No module named 'streamlit'"
Run: `pip install streamlit` and make sure you're using the right Python version.

### "ModuleNotFoundError: No module named 'nba_api'"
Run: `pip install nba_api`. The app works without it (using sample data),
but you need it to fetch live stats on the **🔄 Update Data** page.

### Live data update takes too long
This is normal! The fetcher adds a 1.5-second delay between API calls to avoid
being blocked by the NBA's servers. A full update (all players + game logs) can
take 5-15 minutes. Let it run — don't close the tab.

### "Port 8501 is already in use"
Another Streamlit app is running. Close it, or run on a different port:
```bash
streamlit run app.py --server.port 8502
```

### App shows "No props loaded"
Go to **📥 Import Props** and click "Load Sample Props" or enter your own.

### Analysis results seem off
Check that you have:
1. Games configured on **🏀 Today's Games** page
2. Player names in your props match the names in `sample_players.csv`
3. Stat types are lowercase: `points`, `rebounds`, `assists`, `threes`, etc.

---

## 🧠 How the Math Works (Plain English)

### Monte Carlo Simulation
We simulate 1,000 games for each player. In each game:
1. **Minutes** are randomized (sometimes stars rest, sometimes foul trouble)
2. **Stats** are drawn randomly from a bell curve centered on the projection
3. We record whether that game went OVER or UNDER the line

After 1,000 games: `(# games over line) / 1000 = probability of going over`

### Normal Distribution (Bell Curve)
Player stats follow a bell curve — most games near the average, fewer extreme games.
We use the formula `0.5 * (1 + erf(z / √2))` to calculate probabilities.
This is exactly what scipy.stats.norm.cdf does — we just wrote it ourselves!

### Expected Value (EV)
For a parlay with 3 picks:
```
EV = (P(all 3 hit) × 3-pick payout) + (P(2 hit) × 2-hit payout) + ... - entry fee
```
Positive EV = profitable on average. Negative EV = house wins.

---

## 📦 Dependencies

```
streamlit   # UI framework (required)
nba_api     # Live NBA data (optional but recommended)
```

Install both:
```bash
pip install streamlit nba_api
```

All other functionality uses Python's standard library:
`math`, `random`, `statistics`, `csv`, `sqlite3`, `datetime`, `os`, `pathlib`,
`itertools`, `collections`, `json`, `io`, `copy`

---

## ⚠️ Disclaimer

This app is for **personal entertainment and analysis** only.
Always gamble responsibly. Past model performance does not guarantee future results.
Prop betting involves risk. Never bet more than you can afford to lose.
