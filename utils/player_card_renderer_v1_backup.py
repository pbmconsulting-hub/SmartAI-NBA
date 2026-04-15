"""Fresh self-contained player card renderer for the QAM page.

Produces:
  - Compact one-line player rows (small headshot, name, team, prop count, best edge)
  - Clicking a row expands to reveal all prop analysis cards in a CSS grid
  - Each prop card shows: tier badge, stat/direction, true line, confidence bar,
    metrics (prob/SAFE/edge), distribution (P10/MED/P90/σ/Proj), context pills,
    forces bar, score breakdown bars, and key factors.

All CSS is self-contained via ``PLAYER_CARD_CSS``.
"""

import html as _html
import re as _re
import logging as _logging

_logger = _logging.getLogger("smartai_nba.player_cards")

try:
    from data.player_profile_service import get_headshot_url as _get_headshot_url
except ImportError:
    def _get_headshot_url(name):
        return ""

try:
    from styles.theme import get_team_colors
except ImportError:
    def get_team_colors(team):
        return ("#4a5568", "#2d3748")

_FALLBACK_HEADSHOT = "https://cdn.nba.com/headshots/nba/latest/1040x760/fallback.png"

_e = _html.escape


# ═══════════════════════════════════════════════════════════════════
#  CSS
# ═══════════════════════════════════════════════════════════════════

PLAYER_CARD_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

/* ── Player row grid ─────────────────────────────────────── */
.pc-grid { display:flex; flex-direction:column; gap:6px; padding:8px 0; width:100%; }

/* ── Expandable card ─────────────────────────────────────── */
.pc-card {
  background: rgba(15,18,30,0.92);
  border: 1px solid rgba(255,255,255,0.06);
  border-left: 3px solid transparent;
  border-radius: 10px;
  font-family: 'Inter', sans-serif;
  color: #e0eeff;
  overflow: visible;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.pc-card:hover { border-color: rgba(255,255,255,0.12); }
.pc-card:nth-child(even) { background: rgba(20,24,42,0.92); }
.pc-card[open] {
  border-color: rgba(0,198,255,0.25);
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}

/* ── Summary row (always visible) ────────────────────────── */
.pc-card > summary {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; cursor: pointer;
  list-style: none; user-select: none;
  transition: background 0.15s;
}
.pc-card > summary::-webkit-details-marker { display:none; }
.pc-card > summary::marker { display:none; content:''; }
.pc-card > summary:hover { background: rgba(255,255,255,0.03); }

/* arrow */
.pc-arrow {
  font-size: 0.5rem; color: #4a5568; flex-shrink:0;
  transition: transform 0.25s, color 0.2s;
}
.pc-card[open] .pc-arrow { transform: rotate(90deg); color: #00C6FF; }

/* headshot */
.pc-head {
  width:32px; height:32px; border-radius:50%;
  border: 2px solid rgba(255,255,255,0.15);
  object-fit:cover; flex-shrink:0; background:#1a1d2e;
}
.pc-card[open] .pc-head { border-color: rgba(0,198,255,0.4); }

/* name */
.pc-name {
  font-size:0.95rem; font-weight:700; color:#fff;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  flex-shrink:1; min-width:0;
}

/* summary meta */
.pc-meta {
  font-family:'JetBrains Mono',monospace;
  font-size:0.75rem; font-weight:600; color:#5eead4;
  white-space:nowrap; flex-shrink:0; margin-left:auto;
}

/* ── Expanded identity header ────────────────────────────── */
.pc-identity { display:flex; align-items:center; gap:14px; padding:14px 0 10px; border-bottom:1px solid rgba(255,255,255,0.05); margin-bottom:8px; }
.pc-id-avatar { width:56px; height:56px; border-radius:50%; border:2px solid rgba(0,198,255,0.3); object-fit:cover; background:#1a1d2e; flex-shrink:0; }
.pc-id-info { display:flex; flex-direction:column; gap:2px; }
.pc-id-name { font-size:1.1rem; font-weight:800; color:#fff; }
.pc-id-sub { font-size:0.72rem; color:#8a9bb8; display:flex; align-items:center; gap:6px; }
.pc-id-team-badge { font-size:0.58rem; font-weight:700; padding:2px 8px; border-radius:4px; }
.pc-id-stats { display:flex; gap:6px; margin-left:auto; flex-shrink:0; }
.pc-stat-pill { display:flex; flex-direction:column; align-items:center; padding:4px 10px; border-radius:6px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); }
.pc-stat-pill-val { font-family:'JetBrains Mono',monospace; font-size:0.78rem; font-weight:700; color:#e2e8f0; }
.pc-stat-pill-lbl { font-size:0.46rem; color:#64748b; text-transform:uppercase; letter-spacing:0.04em; }

/* ── Expanded body ───────────────────────────────────────── */
@keyframes pcSlideIn {
  from { opacity:0; transform:translateY(-6px); }
  to   { opacity:1; transform:translateY(0); }
}
.pc-body {
  padding: 0 16px 16px;
  border-top: 1px solid rgba(255,255,255,0.05);
  animation: pcSlideIn 0.25s ease;
}
.pc-prop-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px; padding-top: 12px;
}

/* ── Individual prop card ────────────────────────────────── */
.pc-prop {
  background: rgba(10,15,30,0.85);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; padding: 14px;
  display: flex; flex-direction: column; gap: 10px;
  transition: border-color 0.2s;
}
.pc-prop:hover { border-color: rgba(0,198,255,0.2); }
.pc-prop-platinum { border-color: rgba(200,0,255,0.3); box-shadow: 0 0 18px rgba(200,0,255,0.10), inset 0 0 12px rgba(200,0,255,0.04); }
.pc-prop-gold { border-color: rgba(255,94,0,0.3); box-shadow: 0 0 18px rgba(255,94,0,0.10), inset 0 0 12px rgba(255,94,0,0.04); }

/* prop header row */
.pc-prop-hdr {
  display:flex; align-items:center; gap:8px;
  justify-content:space-between;
}
.pc-prop-left { display:flex; align-items:center; gap:8px; min-width:0; flex:1; }
.pc-tier {
  font-family:'JetBrains Mono',monospace;
  font-size:0.6rem; font-weight:700; letter-spacing:0.06em;
  padding:2px 8px; border-radius:4px; text-transform:uppercase;
  white-space:nowrap; flex-shrink:0;
}
.pc-tier-platinum { background:rgba(200,0,255,0.15); color:#c800ff; }
.pc-tier-gold { background:rgba(255,94,0,0.15); color:#ff5e00; }
.pc-tier-silver { background:rgba(176,192,216,0.15); color:#b0c0d8; }
.pc-tier-bronze { background:rgba(100,116,139,0.15); color:#94a3b8; }
.pc-tier-avoid { background:rgba(239,68,68,0.15); color:#ef4444; }

.pc-stat-label {
  font-size:0.82rem; font-weight:700; color:#e2e8f0;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.pc-platform {
  font-size:0.58rem; color:#64748b; flex-shrink:0;
  font-family:'JetBrains Mono',monospace;
}

/* SAFE score */
.pc-safe {
  display:flex; flex-direction:column; align-items:center;
  flex-shrink:0;
}
.pc-safe-val {
  font-family:'JetBrains Mono',monospace;
  font-size:0.92rem; font-weight:800; color:#00f0ff;
}
.pc-safe-lbl {
  font-size:0.48rem; color:#64748b; text-transform:uppercase;
  letter-spacing:0.05em; font-weight:600;
}

/* badges */
.pc-badges { display:flex; gap:4px; flex-wrap:wrap; }
.pc-badge {
  font-size:0.56rem; font-weight:700; padding:1px 6px;
  border-radius:3px; white-space:nowrap;
}
.pc-badge-best { background:rgba(250,204,21,0.15); color:#facc15; }
.pc-badge-uncertain { background:rgba(251,146,60,0.15); color:#fb923c; }
.pc-badge-avoid { background:rgba(239,68,68,0.15); color:#ef4444; }

/* direction pill */
.pc-dir-pill { font-size:0.60rem; font-weight:800; padding:2px 8px; border-radius:4px; text-transform:uppercase; letter-spacing:0.06em; white-space:nowrap; flex-shrink:0; }
.pc-dir-over { background:rgba(0,255,157,0.12); color:#00ff9d; border:1px solid rgba(0,255,157,0.18); }
.pc-dir-under { background:rgba(255,94,0,0.12); color:#ff5e00; border:1px solid rgba(255,94,0,0.18); }

/* true line row */
.pc-trueline {
  display:flex; justify-content:space-between; align-items:center;
  padding:6px 10px; border-radius:6px;
  background:rgba(0,240,255,0.04);
  border:1px solid rgba(0,240,255,0.1);
}
.pc-trueline-lbl { font-size:0.7rem; color:#8a9bb8; }
.pc-trueline-val {
  font-family:'JetBrains Mono',monospace;
  font-size:0.9rem; font-weight:800; color:#00f0ff;
}

/* prediction pill */
.pc-pred {
  font-size:0.72rem; font-weight:700; padding:4px 10px;
  border-radius:6px; text-align:center;
}
.pc-pred-over { background:rgba(0,255,157,0.1); color:#00ff9d; border:1px solid rgba(0,255,157,0.2); }
.pc-pred-under { background:rgba(255,94,0,0.1); color:#ff5e00; border:1px solid rgba(255,94,0,0.2); }
.pc-pred-neutral { background:rgba(148,163,184,0.1); color:#94a3b8; border:1px solid rgba(148,163,184,0.2); }

/* confidence bar */
.pc-conf-hdr { display:flex; justify-content:space-between; font-size:0.64rem; color:#8a9bb8; }
.pc-conf-pct { font-weight:700; }
.pc-conf-track {
  height:5px; border-radius:3px; background:rgba(255,255,255,0.06);
  overflow:hidden; margin-top:3px;
}
.pc-conf-fill { height:100%; border-radius:3px; transition:width 0.3s; }

/* metrics row */
.pc-metrics { display:flex; gap:6px; justify-content:space-around; }
.pc-m { display:flex; flex-direction:column; align-items:center; }
.pc-m-val {
  font-family:'JetBrains Mono',monospace;
  font-size:0.82rem; font-weight:700; color:#e2e8f0;
}
.pc-m-lbl { font-size:0.5rem; color:#64748b; text-transform:uppercase; letter-spacing:0.04em; }

/* distribution row */
.pc-dist { display:flex; gap:4px; justify-content:space-around; }
.pc-d { display:flex; flex-direction:column; align-items:center; }
.pc-d-val {
  font-family:'JetBrains Mono',monospace;
  font-size:0.72rem; font-weight:700; color:#94a3b8;
}
.pc-d-lbl { font-size:0.48rem; color:#4a5568; text-transform:uppercase; }
.pc-d-med .pc-d-val { color:#e2e8f0; }
.pc-d-proj .pc-d-val { color:#00f0ff; }

/* context pills */
.pc-ctx { display:flex; flex-wrap:wrap; gap:4px; }
.pc-ctx-pill {
  font-size:0.58rem; padding:2px 7px; border-radius:4px;
  background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);
  color:#94a3b8; font-family:'JetBrains Mono',monospace;
}

/* forces */
.pc-forces-bar-wrap { position:relative; margin-bottom:8px; }
.pc-forces-bar {
  display:flex; height:10px; border-radius:5px; overflow:hidden;
  background:rgba(255,255,255,0.04);
}
.pc-forces-over-fill { background:linear-gradient(90deg,#00ff9d,#00d4a8); }
.pc-forces-under-fill { background:linear-gradient(90deg,#ff8844,#ff5e00); }
.pc-forces-pct-row { display:flex; justify-content:space-between; margin-top:2px; }
.pc-forces-pct { font-family:'JetBrains Mono',monospace; font-size:0.54rem; font-weight:700; }
.pc-forces-pct-over { color:#00ff9d; }
.pc-forces-pct-under { color:#ff5e00; }
.pc-forces { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.pc-forces-lbl { font-size:0.56rem; font-weight:700; margin-bottom:2px; }
.pc-forces-lbl-over { color:#00ff9d; }
.pc-forces-lbl-under { color:#ff5e00; }
.pc-force-item { font-size:0.58rem; color:#94a3b8; }
.pc-force-none { font-size:0.58rem; color:#374151; font-style:italic; }

/* breakdown bars */
.pc-breakdown { display:flex; flex-direction:column; gap:4px; }
.pc-bd-row { display:flex; align-items:center; gap:6px; }
.pc-bd-label { font-size:0.56rem; color:#8a9bb8; width:70px; flex-shrink:0; text-align:right; }
.pc-bd-score {
  font-family:'JetBrains Mono',monospace;
  font-size:0.56rem; font-weight:700; color:#e2e8f0; width:22px; text-align:right; flex-shrink:0;
}
.pc-bd-track { flex:1; height:4px; border-radius:2px; background:rgba(255,255,255,0.06); overflow:hidden; }
.pc-bd-fill { height:100%; border-radius:2px; }

/* key factors */
.pc-factors { display:flex; flex-direction:column; gap:2px; }
.pc-factors-title { font-size:0.6rem; font-weight:700; color:#8a9bb8; text-transform:uppercase; letter-spacing:0.04em; }
.pc-factor-item { font-size:0.58rem; color:#94a3b8; }
.pc-factor-item::before { content:'\\2713 '; color:#5eead4; }

/* ── Responsive ──────────────────────────────────────────── */
@media (max-width:768px) {
  .pc-card > summary { gap:8px; padding:10px 12px; }
  .pc-head { width:28px; height:28px; }
  .pc-name { font-size:0.86rem; }
  .pc-meta { font-size:0.64rem; }
  .pc-prop-grid { grid-template-columns:1fr; }
  .pc-body { padding:0 10px 12px; }
  .pc-identity { gap:10px; flex-wrap:wrap; }
  .pc-id-avatar { width:44px; height:44px; }
  .pc-id-stats { width:100%; justify-content:center; }
}
@media (max-width:480px) {
  .pc-card > summary { gap:6px; padding:8px 10px; }
  .pc-head { width:24px; height:24px; }
  .pc-name { font-size:0.80rem; }
  .pc-meta { font-size:0.58rem; }
}
"""


# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════

def _fmt(val, fallback="—"):
    """Format a numeric value to 1 decimal, or return fallback."""
    try:
        return f"{float(val):.1f}"
    except (TypeError, ValueError):
        return fallback


def _conf_color(pct):
    if pct >= 80: return "#00f0ff"
    if pct >= 65: return "#FFD700"
    if pct >= 50: return "#00b4ff"
    return "#94A3B8"


def _bd_color(score):
    if score >= 70: return "#00f0ff"
    if score >= 40: return "#ff5e00"
    return "#ff4444"


_STAT_EMOJI = {
    "points": "🏀", "rebounds": "📊", "assists": "🎯",
    "threes": "🎯", "steals": "⚡", "blocks": "🛡️", "turnovers": "❌",
}


# ═══════════════════════════════════════════════════════════════════
#  SINGLE PROP CARD
# ═══════════════════════════════════════════════════════════════════

def _build_prop_card(result):
    """Build HTML for one prop analysis card."""
    r = result

    # ── Core values ──────────────────────────────────────────
    tier = (r.get("tier") or "Bronze").strip()
    tier_lower = tier.lower()
    confidence = float(r.get("confidence_score") or 0)
    safe_score = f"{min(10.0, confidence / 10.0):.1f}"
    stat_type = (r.get("stat_type") or "").replace("_", " ").title()
    line = _fmt(r.get("line"))
    true_line = _fmt(r.get("adjusted_projection"))
    prob_over = float(r.get("probability_over") or 0.5)
    edge = float(r.get("edge_percentage") or 0)
    platform = _e(str(r.get("platform") or ""))

    direction = (r.get("direction") or "").upper()
    if not direction:
        direction = "OVER" if prob_over >= 0.5 else "UNDER"

    dir_label = "More" if direction == "OVER" else "Less"
    stat_lower = (r.get("stat_type") or "").lower()
    emoji = _STAT_EMOJI.get(stat_lower, "🏀")
    prop_text = f"{emoji} {dir_label} {true_line} {_e(stat_type)}"

    # Glow class
    glow = ""
    if tier_lower in ("platinum", "gold"):
        glow = f" pc-prop-{tier_lower}"

    # ── Header ───────────────────────────────────────────────
    badges = ""
    if r.get("_is_best_pick"):
        badges += '<span class="pc-badge pc-badge-best">⭐ Top Pick</span>'
    if r.get("is_uncertain"):
        badges += '<span class="pc-badge pc-badge-uncertain">⚠️ Uncertain</span>'
    if r.get("should_avoid"):
        badges += '<span class="pc-badge pc-badge-avoid">🚫 Caution</span>'

    dir_cls = "pc-dir-over" if direction == "OVER" else "pc-dir-under"
    dir_pill_html = f'<span class="pc-dir-pill {dir_cls}">{direction}</span>'

    hdr = (
        f'<div class="pc-prop-hdr">'
        f'<div class="pc-prop-left">'
        f'<span class="pc-tier pc-tier-{tier_lower}">{_e(tier)}</span>'
        f'{dir_pill_html}'
        f'<span class="pc-stat-label">{prop_text}</span>'
        f'<span class="pc-platform">{platform}</span>'
        f'</div>'
        f'<div class="pc-safe"><span class="pc-safe-val">{safe_score}</span>'
        f'<span class="pc-safe-lbl">SAFE</span></div>'
        f'</div>'
    )

    if badges:
        hdr += f'<div class="pc-badges">{badges}</div>'

    # ── True line ────────────────────────────────────────────
    trueline = (
        f'<div class="pc-trueline">'
        f'<span class="pc-trueline-lbl">True Line ({_e(direction)})</span>'
        f'<span class="pc-trueline-val">{true_line}</span>'
        f'</div>'
    )

    # ── Prediction pill ──────────────────────────────────────
    prediction = _e(str(r.get("prediction") or ""))
    if "over" in prediction.lower():
        pred_cls = "pc-pred-over"
    elif "under" in prediction.lower():
        pred_cls = "pc-pred-under"
    else:
        pred_cls = "pc-pred-neutral"
    pred_html = f'<div class="pc-pred {pred_cls}">{prediction}</div>' if prediction else ""

    # ── Confidence bar ───────────────────────────────────────
    conf_pct = max(0.0, min(100.0, confidence))
    cc = _conf_color(conf_pct)
    conf = (
        f'<div class="pc-conf-hdr"><span>Confidence</span>'
        f'<span class="pc-conf-pct" style="color:{cc};">{conf_pct:.0f}%</span></div>'
        f'<div class="pc-conf-track">'
        f'<div class="pc-conf-fill" style="width:{conf_pct}%;background:{cc};"></div>'
        f'</div>'
    )

    # ── Metrics ──────────────────────────────────────────────
    prob_pct = f"{prob_over * 100:.0f}%"
    edge_disp = f"{edge:+.1f}%"
    metrics = (
        f'<div class="pc-metrics">'
        f'<div class="pc-m"><span class="pc-m-val">{prob_pct}</span><span class="pc-m-lbl">Prob</span></div>'
        f'<div class="pc-m"><span class="pc-m-val">{confidence:.0f}</span><span class="pc-m-lbl">SAFE</span></div>'
        f'<div class="pc-m"><span class="pc-m-val">{edge_disp}</span><span class="pc-m-lbl">Edge</span></div>'
        f'</div>'
    )

    # ── Distribution ─────────────────────────────────────────
    p10 = _fmt(r.get("percentile_10"))
    p50 = _fmt(r.get("percentile_50"))
    p90 = _fmt(r.get("percentile_90"))
    std = _fmt(r.get("simulated_std"))
    proj = _fmt(r.get("adjusted_projection"))
    dist = (
        f'<div class="pc-dist">'
        f'<div class="pc-d"><span class="pc-d-val">{p10}</span><span class="pc-d-lbl">P10</span></div>'
        f'<div class="pc-d pc-d-med"><span class="pc-d-val">{p50}</span><span class="pc-d-lbl">MED</span></div>'
        f'<div class="pc-d"><span class="pc-d-val">{p90}</span><span class="pc-d-lbl">P90</span></div>'
        f'<div class="pc-d"><span class="pc-d-val">{std}</span><span class="pc-d-lbl">&sigma;</span></div>'
        f'<div class="pc-d pc-d-proj"><span class="pc-d-val">{proj}</span><span class="pc-d-lbl">Proj</span></div>'
        f'</div>'
    )

    # ── Context pills ────────────────────────────────────────
    ctx_items = []
    form = r.get("recent_form_ratio")
    if form is not None:
        try:
            fv = float(form)
            tag = "🔥 Hot" if fv >= 1.05 else ("❄️ Cold" if fv <= 0.95 else "➡️ Neutral")
            ctx_items.append(f"{tag} ({fv:.2f}x)")
        except (ValueError, TypeError):
            pass
    adj = r.get("overall_adjustment")
    if adj is not None:
        try:
            ctx_items.append(f"Matchup {float(adj):.2f}x")
        except (ValueError, TypeError):
            pass
    gp = r.get("games_played")
    if gp is not None:
        ctx_items.append(f"{gp} GP")
    mins = r.get("projected_minutes")
    if mins is not None:
        try:
            ctx_items.append(f"{float(mins):.0f} min proj")
        except (ValueError, TypeError):
            pass
    ctx_html = ""
    if ctx_items:
        pills = "".join(f'<span class="pc-ctx-pill">{_e(c)}</span>' for c in ctx_items)
        ctx_html = f'<div class="pc-ctx">{pills}</div>'

    # ── Forces ───────────────────────────────────────────────
    forces = r.get("forces") or {}
    over_forces = forces.get("over_forces") or []
    under_forces = forces.get("under_forces") or []
    o_str = sum(float(f.get("strength", 1)) for f in over_forces if isinstance(f, dict))
    u_str = sum(float(f.get("strength", 1)) for f in under_forces if isinstance(f, dict))
    total = o_str + u_str
    o_pct = (o_str / total * 100) if total > 0 else 50
    u_pct = 100 - o_pct

    def _fi(flist):
        if not flist:
            return '<span class="pc-force-none">None</span>'
        items = []
        for f in flist:
            if not isinstance(f, dict):
                continue
            s = max(1, min(5, round(float(f.get("strength", 1)))))
            items.append(f'<div class="pc-force-item">{"⭐" * s} {_e(str(f.get("name", "")))}</div>')
        return "".join(items) or '<span class="pc-force-none">None</span>'

    forces_html = (
        f'<div class="pc-forces-bar-wrap">'
        f'<div class="pc-forces-bar">'
        f'<div class="pc-forces-over-fill" style="width:{o_pct:.1f}%;"></div>'
        f'<div class="pc-forces-under-fill" style="width:{u_pct:.1f}%;"></div>'
        f'</div>'
        f'<div class="pc-forces-pct-row">'
        f'<span class="pc-forces-pct pc-forces-pct-over">{o_pct:.0f}%</span>'
        f'<span class="pc-forces-pct pc-forces-pct-under">{u_pct:.0f}%</span>'
        f'</div></div>'
        f'<div class="pc-forces">'
        f'<div><div class="pc-forces-lbl pc-forces-lbl-over">▲ OVER ({len(over_forces)})</div>{_fi(over_forces)}</div>'
        f'<div><div class="pc-forces-lbl pc-forces-lbl-under">▼ UNDER ({len(under_forces)})</div>{_fi(under_forces)}</div>'
        f'</div>'
    )

    # ── Breakdown bars ───────────────────────────────────────
    breakdown = r.get("score_breakdown") or {}
    bd_html = ""
    if breakdown:
        rows = []
        for factor, score in breakdown.items():
            try:
                sv = float(score or 0)
            except (ValueError, TypeError):
                continue
            label = _e(factor.replace("_score", "").replace("_", " ").title())
            w = min(100, max(0, sv))
            rows.append(
                f'<div class="pc-bd-row">'
                f'<span class="pc-bd-label">{label}</span>'
                f'<span class="pc-bd-score">{sv:.0f}</span>'
                f'<div class="pc-bd-track"><div class="pc-bd-fill" style="width:{w:.1f}%;background:{_bd_color(sv)};"></div></div>'
                f'</div>'
            )
        if rows:
            bd_html = f'<div class="pc-breakdown">{"".join(rows)}</div>'

    # ── Key factors ──────────────────────────────────────────
    factors_html = ""
    bonus_factors = []
    if r.get("ensemble_used"):
        bonus_factors.append(f"Ensemble model ({r.get('ensemble_models', '?')} models)")
    gp_val = r.get("games_played")
    if gp_val and int(gp_val) >= 30:
        bonus_factors.append(f"Large sample ({gp_val} games)")
    if r.get("line_verified"):
        bonus_factors.append("Line verified across books")
    teammate_notes = r.get("teammate_out_notes") or []
    for tn in teammate_notes[:2]:
        bonus_factors.append(str(tn))
    if bonus_factors:
        items = "".join(f'<div class="pc-factor-item">{_e(bf)}</div>' for bf in bonus_factors)
        factors_html = f'<div class="pc-factors"><div class="pc-factors-title">Key Factors</div>{items}</div>'

    return (
        f'<div class="pc-prop{glow}">'
        f'{hdr}{trueline}{pred_html}{conf}{metrics}{dist}'
        f'{ctx_html}{forces_html}{bd_html}{factors_html}'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════
#  PLAYER ROW (SUMMARY + EXPANDABLE BODY)
# ═══════════════════════════════════════════════════════════════════

def build_player_card(player_name, vitals, props):
    """Build one expandable player row.

    Args:
        player_name: Display name.
        vitals: Dict with headshot_url, team, position, season_stats, etc.
        props: List of prop analysis result dicts for this player.

    Returns:
        str: ``<details>`` HTML element.
    """
    safe_name = _e(player_name)
    headshot = _e((vitals.get("headshot_url") or "") or "")
    if not headshot:
        headshot = _e(_get_headshot_url(player_name) or "")
    team = _e(vitals.get("team") or "N/A")

    prop_count = len(props)
    prop_label = f"{prop_count} prop{'s' if prop_count != 1 else ''}"

    best_edge = 0.0
    for p in props:
        try:
            e = abs(float(p.get("edge_percentage") or p.get("edge") or 0))
            if e > best_edge:
                best_edge = e
        except (ValueError, TypeError):
            pass
    best_edge_str = f"{best_edge:.1f}%"

    # Determine best tier for accent border
    _TIER_BORDER = {
        "platinum": "#c800ff", "gold": "#ff5e00",
        "silver": "#b0c0d8", "bronze": "#64748b",
    }
    _TIER_RANK = {"platinum": 4, "gold": 3, "silver": 2, "bronze": 1, "avoid": 0}
    best_tier = "bronze"
    for p in props:
        pt = (p.get("tier") or "bronze").strip().lower()
        if _TIER_RANK.get(pt, 0) > _TIER_RANK.get(best_tier, 0):
            best_tier = pt
    border_color = _TIER_BORDER.get(best_tier, "#64748b")

    # Build prop cards
    cards = "".join(_build_prop_card(p) for p in props)

    # Expanded identity header
    position = _e(vitals.get("position") or "")
    pos_label = f" &middot; {position}" if position else ""
    team_colors = get_team_colors(vitals.get("team") or "")
    team_bg = team_colors[0] if team_colors else "#4a5568"

    season = vitals.get("season_stats") or {}
    stat_pills = ""
    for key, label in [("ppg", "PPG"), ("rpg", "RPG"), ("apg", "APG")]:
        val = season.get(key)
        if val is not None:
            try:
                stat_pills += (
                    f'<div class="pc-stat-pill">'
                    f'<span class="pc-stat-pill-val">{float(val):.1f}</span>'
                    f'<span class="pc-stat-pill-lbl">{label}</span></div>'
                )
            except (ValueError, TypeError):
                pass

    stats_section = f'<div class="pc-id-stats">{stat_pills}</div>' if stat_pills else ""
    id_header = (
        f'<div class="pc-identity">'
        f'<img class="pc-id-avatar" src="{headshot}" alt="{safe_name}" '
        f'onerror="this.onerror=null;this.src=\'{_FALLBACK_HEADSHOT}\'">' 
        f'<div class="pc-id-info">'
        f'<span class="pc-id-name">{safe_name}</span>'
        f'<span class="pc-id-sub">'
        f'<span class="pc-id-team-badge" style="background:{team_bg};color:#fff;">{team}</span>'
        f'{pos_label}</span>'
        f'</div>'
        f'{stats_section}'
        f'</div>'
    )

    return (
        f'<details class="pc-card" style="border-left-color:{border_color};">'
        f'<summary>'
        f'<span class="pc-arrow">&#9654;</span>'
        f'<img class="pc-head" src="{headshot}" alt="{safe_name}" '
        f'onerror="this.onerror=null;this.src=\'{_FALLBACK_HEADSHOT}\'">' 
        f'<span class="pc-name">{safe_name}</span>'
        f'<span class="pc-meta">{team} &middot; {prop_label} &middot; Best edge {best_edge_str}</span>'
        f'</summary>'
        f'<div class="pc-body">{id_header}<div class="pc-prop-grid">{cards}</div></div>'
        f'</details>'
    )


# ═══════════════════════════════════════════════════════════════════
#  FULL MATRIX COMPILER
# ═══════════════════════════════════════════════════════════════════

def compile_player_card_matrix(grouped_players):
    """Compile all players into a complete HTML block with embedded CSS.

    Args:
        grouped_players: Dict of player_name -> {"vitals": dict, "props": list[dict]}
            (output of ``group_props_by_player``).

    Returns:
        str: Complete HTML string with ``<style>`` + all player cards.
    """
    if not grouped_players:
        return (
            f"<style>{PLAYER_CARD_CSS}</style>"
            '<div style="text-align:center;color:#64748b;padding:40px;">'
            "No analysis results to display.</div>"
        )

    cards = []
    for name, data in grouped_players.items():
        vitals = data.get("vitals") or {}
        props = data.get("props") or []
        if props:
            cards.append(build_player_card(name, vitals, props))

    return (
        f"<style>{PLAYER_CARD_CSS}</style>"
        f'<div class="pc-grid">{"".join(cards)}</div>'
    )
