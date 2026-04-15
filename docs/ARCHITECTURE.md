# SmartAI-NBA Architecture Blueprint

> **Author**: Senior Architecture Review — April 14, 2026  
> **Status**: Living document — updated as refactors complete  
> **Codebase**: ~65,000 lines across 100+ Python files

---

## 1. Current State Assessment

### 1.1 God Files (>1000 lines — violate Single Responsibility Principle)

| Lines | File | Responsibilities | Severity |
|-------|------|-----------------|----------|
| 10,634 | `styles/theme.py` | CSS themes (acceptable for CSS) | LOW |
| 6,166 | `engine/joseph_brain.py` | Reasoning, grading, strategy, tickets | **CRITICAL** |
| 3,163 | `pages/11_Bet_Tracker.py` | 8 tabs of UI + bet resolution logic | **HIGH** |
| 3,142 | `pages/3_QAM.py` | Analysis orchestration + UI display | **HIGH** |
| 2,899 | `tracking/bet_tracker.py` | Bet CRUD + performance analytics | **HIGH** |
| 2,822 | `data/live_data_fetcher.py` | 10+ data fetching responsibilities | **HIGH** |
| 2,818 | `data/platform_fetcher.py` | 3 platform fetchers + matching logic | **HIGH** |
| 2,735 | `tracking/database.py` | SQLite ORM + settings + analytics | **HIGH** |
| 2,430 | `data/db_service.py` | DB gateway (too many methods) | MEDIUM |
| 2,352 | `Smart_Picks_Pro_Home.py` | Home page + global setup | MEDIUM |
| 2,168 | `pages/1_Live_Games.py` | Live game analysis + UI | MEDIUM |
| 2,134 | `engine/simulation.py` | QME + combos + fantasy + sensitivity | **HIGH** |
| 1,911 | `data/nba_live_fetcher.py` | NBA API wrapper (duplicate of nba_stats_service) | MEDIUM |
| 1,788 | `data/data_manager.py` | CSV loading/caching | MEDIUM |
| 1,747 | `engine/edge_detection.py` | Edge + forces + directional analysis | MEDIUM |

### 1.2 Duplicate Code

- **`_safe_float()`**: Copied verbatim in **21 files** instead of importing from one place
- **NBA API wrappers**: `nba_live_fetcher.py` and `nba_stats_service.py` both wrap `nba_api` with identical TTL caching patterns
- **DB access**: `db_service.py` and `etl_data_service.py` both read from `smartpicks.db`
- **`nba_data_service.py`**: 1,241-line facade that re-exports 60+ functions from `live_data_fetcher.py`
- **`sportsbook_service.py`**: Pure pass-through facade over `platform_fetcher.py`

### 1.3 Layer Violations

- **Business logic in pages**: QAM page contains ~2,000 lines of analysis orchestration (simulation, projection, edge detection, force analysis, scoring) that belongs in the engine layer
- **UI concerns in engine**: None found (good)
- **Data layer imports engine**: `platform_fetcher.py` imports from `engine.odds_engine`, `advanced_metrics.py` imports from `engine.math_helpers`
- **No service layer**: Pages directly import from `data/` and `engine/` — no abstraction boundary

### 1.4 Configuration Management

- **Scattered**: Thresholds in `config/thresholds.py`, auth in `utils/auth.py`, logging in `utils/logger.py`, user settings in `tracking/database.py`, simulation defaults in `engine/simulation.py`
- **No `.env` loading**: Environment variables read ad-hoc across files
- **No feature flags**: Functionality toggled via commented code or session state
- **No validation**: Settings accepted without schema validation

---

## 2. Target Architecture

```
SmartAI-NBA/
├── config/                          # Centralized configuration
│   ├── __init__.py
│   ├── settings.py                  # Pydantic settings (env + defaults)
│   ├── thresholds.py                # Scoring/tier thresholds
│   └── constants.py                 # App-wide constants
│
├── data/                            # Data Access Layer (I/O only)
│   ├── __init__.py
│   ├── db_gateway.py                # Single SQLite interface (merge db_service + etl_data_service)
│   ├── nba_api_client.py            # Single NBA API wrapper (merge nba_live_fetcher + nba_stats_service)
│   ├── platform_fetchers/           # One file per sportsbook
│   │   ├── __init__.py
│   │   ├── prizepicks.py
│   │   ├── underdog.py
│   │   └── draftkings.py
│   ├── player_resolver.py           # Player ID/name resolution (merge player_id_cache + player_profile)
│   ├── roster_engine.py             # Roster/injury data
│   ├── data_manager.py              # CSV persistence
│   ├── game_log_cache.py            # Game log JSON cache
│   ├── platform_mappings.py         # Stat normalization
│   └── validators.py                # Data validation
│
├── engine/                          # Pure Business Logic (no I/O, no UI)
│   ├── __init__.py                  # Stat type constants + re-exports
│   ├── core/                        # Foundation layer
│   │   ├── __init__.py
│   │   ├── math_helpers.py          # All math utilities + _safe_float
│   │   ├── stat_distributions.py    # Distribution type selection
│   │   └── odds.py                  # Odds conversion, edge calculation
│   │
│   ├── simulation/                  # Quantum Matrix Engine
│   │   ├── __init__.py              # Re-exports for backward compat
│   │   ├── qme_core.py              # run_quantum_matrix_simulation
│   │   ├── scenarios.py             # Game scenarios + spread-total matrix
│   │   ├── combo_stats.py           # Correlated combo/fantasy/DD/TD sims
│   │   ├── sensitivity.py           # Sensitivity analysis
│   │   └── enhanced.py              # run_enhanced_simulation (blend)
│   │
│   ├── analysis/                    # Scoring & classification
│   │   ├── __init__.py
│   │   ├── projections.py           # Player stat projections
│   │   ├── edge_detection.py        # Directional forces
│   │   ├── confidence.py            # SAFE score calculation
│   │   ├── calibration.py           # Historical calibration
│   │   └── explainer.py             # Pick explanation generation
│   │
│   ├── strategy/                    # Joseph M. Smith engine
│   │   ├── __init__.py
│   │   ├── brain.py                 # Core reasoning (split from 6166-line file)
│   │   ├── evaluation.py            # Player grading
│   │   ├── game_strategy.py         # Game-level strategy
│   │   ├── ticket_builder.py        # Ticket/parlay construction
│   │   └── bet_tracker.py           # Bet tracking logic
│   │
│   ├── market/                      # Market analysis
│   │   ├── __init__.py
│   │   ├── arbitrage.py
│   │   ├── line_movement.py
│   │   ├── platform_compare.py
│   │   └── clv_tracker.py
│   │
│   ├── features/                    # Feature engineering (existing)
│   ├── models/                      # ML models (existing)
│   ├── pipeline/                    # ML pipeline (existing)
│   ├── predict/                     # Prediction serving (existing)
│   └── scrapers/                    # Web scrapers (existing)
│
├── orchestrator/                    # Coordination layer
│   ├── __init__.py
│   ├── analysis_flow.py             # QAM analysis orchestration
│   ├── live_game_flow.py            # Live game analysis orchestration
│   └── betting_flow.py              # Bet tracking orchestration
│
├── pages/                           # Pure UI (Streamlit)
│   ├── helpers/                     # Page-specific UI helpers
│   └── [0-14]_*.py                  # Thin pages that call orchestrators
│
├── utils/                           # Cross-cutting utilities (existing — well-organized)
├── etl/                             # Data pipelines (existing — clean)
├── api/                             # REST API (existing — clean)
├── agent/                           # AI persona (existing — clean)
├── tracking/                        # Persistence layer (existing)
├── styles/                          # CSS themes
└── tests/                           # Test suite
```

### 2.1 Dependency Rules

```
pages/ → orchestrator/ → engine/ → (nothing)
pages/ → utils/
pages/ → data/ (read-only, for display)
orchestrator/ → engine/
orchestrator/ → data/
engine/ → engine/core/ (math_helpers only)
engine/ → config/ (thresholds only)
data/ → config/ (settings only)
utils/ → config/
```

**FORBIDDEN**:
- `engine/` → `data/` (engine must not do I/O)
- `engine/` → `pages/` or `utils/` (no UI awareness)
- `data/` → `engine/` (no business logic in data layer)
- `pages/` → `engine/` directly for analysis orchestration (use orchestrator/)

---

## 3. Migration Plan (Phased)

### Phase 1: Foundation (LOW RISK) ✅ IN PROGRESS
1. ~~Consolidate `_safe_float` into `engine/math_helpers.py`~~ → Import everywhere
2. Create `config/settings.py` for centralized configuration
3. Split `engine/simulation.py` into `engine/simulation/` subpackage

### Phase 2: Engine Decomposition (MEDIUM RISK)
4. Split `engine/joseph_brain.py` (6,166 lines) into strategy/ subpackage
5. Merge `engine/odds_engine.py` + edge calculation into `engine/core/odds.py`

### Phase 3: Data Layer Cleanup (MEDIUM RISK)
6. Merge `nba_live_fetcher.py` + `nba_stats_service.py` → `nba_api_client.py`
7. Merge `db_service.py` + `etl_data_service.py` → `db_gateway.py`
8. Split `platform_fetcher.py` → `platform_fetchers/` subpackage
9. Delete `sportsbook_service.py` facade (redirect imports)

### Phase 4: Orchestrator Extraction (HIGH IMPACT)
10. Extract QAM analysis loop → `orchestrator/analysis_flow.py`
11. Extract Bet Tracker logic → `orchestrator/betting_flow.py`
12. Extract Live Games analysis → `orchestrator/live_game_flow.py`

### Phase 5: Page Thinning (HIGHEST IMPACT)
13. QAM page: ~3,142 → ~800 lines (UI only)
14. Bet Tracker page: ~3,163 → ~600 lines (UI only)
15. Live Games page: ~2,168 → ~500 lines (UI only)

### Phase 6: Polish
16. Add type hints to all public APIs
17. Add integration tests for orchestrator flows
18. Add error boundaries per page
19. Add structured logging with correlation IDs

---

## 4. Backward Compatibility Strategy

Every module split uses the **re-export pattern** to maintain backward compatibility:

```python
# engine/simulation/__init__.py
# All existing imports continue to work
from engine.simulation.qme_core import run_quantum_matrix_simulation
from engine.simulation.combo_stats import simulate_combo_stat, simulate_fantasy_score
from engine.simulation.enhanced import run_enhanced_simulation
# etc.
```

This means:
- `from engine.simulation import run_quantum_matrix_simulation` still works
- No pages or tests need updating immediately
- Migration can be done file-by-file over time

---

## 5. Key Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Max file size | 6,166 lines | <500 lines |
| `_safe_float` copies | 21 | 1 |
| Data service duplicates | 3 API wrappers | 1 |
| Business logic in pages | ~5,000 lines | 0 |
| Config locations | 6+ files | 1 (`config/settings.py`) |
| Avg God file reduction | N/A | 60-80% smaller |
