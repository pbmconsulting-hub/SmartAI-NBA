# ============================================================
# FILE: utils/auth_gate.py
# PURPOSE: Signup / Login gate for Smart Pick Pro.
#          Users must create an account or log in before they
#          can see ANY page in the app.
#
# HOW IT WORKS:
#   1. Call  require_login()  at the very top of every page
#      (after st.set_page_config).
#   2. If the user has NOT logged in this session, the function
#      renders a full-screen signup/login form and returns False.
#      The calling page should then call  st.stop().
#   3. Once the user signs up or logs in, the session-state flag
#      is set and require_login() returns True on all subsequent
#      reruns — no database hit on every page load.
#
# PASSWORD STORAGE:
#   • Passwords are hashed with bcrypt (or hashlib-based PBKDF2
#     fallback if bcrypt is not installed).
#   • Plaintext passwords are NEVER stored or logged.
# ============================================================

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import sqlite3

import streamlit as st

from tracking.database import initialize_database, get_database_connection

_logger = logging.getLogger(__name__)

# ── Session-state keys ────────────────────────────────────────
_SS_LOGGED_IN     = "_auth_logged_in"      # bool
_SS_USER_EMAIL    = "_auth_user_email"     # str
_SS_USER_NAME     = "_auth_user_name"      # str
_SS_USER_ID       = "_auth_user_id"        # int

# ── Password hashing helpers ──────────────────────────────────

try:
    import bcrypt as _bcrypt  # type: ignore
    _HAS_BCRYPT = True
except ImportError:
    _bcrypt = None  # type: ignore
    _HAS_BCRYPT = False


def _hash_password(plain: str) -> str:
    """Hash a plaintext password. Uses bcrypt if available, else PBKDF2."""
    if _HAS_BCRYPT:
        return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    # Fallback: PBKDF2-SHA256
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return f"pbkdf2:sha256:260000${salt}${dk.hex()}"


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    if _HAS_BCRYPT and hashed.startswith("$2"):
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    if hashed.startswith("pbkdf2:"):
        parts = hashed.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected_hex = parts
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 260_000)
        return secrets.compare_digest(dk.hex(), expected_hex)
    return False


# ── Database helpers ──────────────────────────────────────────

def _create_user(email: str, password: str, display_name: str = "") -> bool:
    """Create a new user account. Returns True on success."""
    initialize_database()
    pw_hash = _hash_password(password)
    try:
        with get_database_connection() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                (email.strip().lower(), pw_hash, display_name.strip() or email.split("@")[0]),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Email already registered
    except Exception as exc:
        _logger.error("Failed to create user: %s", exc)
        return False


def _authenticate_user(email: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict on success, None on failure."""
    initialize_database()
    try:
        with get_database_connection() as conn:
            cursor = conn.execute(
                "SELECT user_id, email, password_hash, display_name FROM users WHERE email = ?",
                (email.strip().lower(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            user = dict(row)
            if _verify_password(password, user["password_hash"]):
                # Update last_login_at
                conn.execute(
                    "UPDATE users SET last_login_at = datetime('now') WHERE user_id = ?",
                    (user["user_id"],),
                )
                conn.commit()
                return user
    except Exception as exc:
        _logger.error("Authentication error: %s", exc)
    return None


def _email_exists(email: str) -> bool:
    """Check if an email is already registered."""
    initialize_database()
    try:
        with get_database_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
            return row is not None
    except Exception:
        return False


# ── Validation ────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def _valid_password(pw: str) -> str | None:
    """Return an error message if password is weak, else None."""
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isdigit() for c in pw):
        return "Password must contain at least one number."
    if not any(c.isalpha() for c in pw):
        return "Password must contain at least one letter."
    return None


# ── Session helpers ───────────────────────────────────────────

def _set_logged_in(user: dict) -> None:
    st.session_state[_SS_LOGGED_IN]  = True
    st.session_state[_SS_USER_EMAIL] = user.get("email", "")
    st.session_state[_SS_USER_NAME]  = user.get("display_name", "")
    st.session_state[_SS_USER_ID]    = user.get("user_id", 0)


def is_logged_in() -> bool:
    """Check if the user is logged into an account this session."""
    return bool(st.session_state.get(_SS_LOGGED_IN))


def get_logged_in_email() -> str:
    """Return the logged-in user's email, or ''."""
    return st.session_state.get(_SS_USER_EMAIL, "")


def logout_user() -> None:
    """Clear the login session."""
    for key in (_SS_LOGGED_IN, _SS_USER_EMAIL, _SS_USER_NAME, _SS_USER_ID):
        st.session_state.pop(key, None)


# ── Logo helper ───────────────────────────────────────────────

def _get_logo_b64() -> str:
    """Return base64-encoded SPP logo for inline embedding."""
    import base64 as _b64
    _logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Smart_Pick_Pro_Logo.png")
    try:
        with open(_logo_path, "rb") as f:
            return _b64.b64encode(f.read()).decode()
    except OSError:
        return ""


# ── CSS for the gate ──────────────────────────────────────────
# Theme: PrizePicks × DraftKings Pick6 × AI
# Fonts: Space Grotesk (headlines) + Inter (body) + JetBrains Mono (data)

_GATE_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');

/* ── Reset Streamlit chrome ──────────────────────────────────── */
[data-testid="stSidebar"],
header[data-testid="stHeader"],
[data-testid="stDecoration"],
.stDeployButton,
footer { display: none !important; }
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }

.stApp {
    background: #0B0F19 !important;
}

.stApp > [data-testid="stAppViewContainer"] > section.main .block-container {
    padding: 0 20px !important;
    max-width: 520px !important;
    margin: 0 auto !important;
    position: relative;
    z-index: 10;
}

html, body, .stApp, .stApp * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Keyframes ───────────────────────────────────────────────── */
@keyframes agFadeUp {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes agGlow {
    0%, 100% { opacity: 0.4; }
    50%      { opacity: 0.7; }
}
@keyframes agShimmer {
    0%   { left: -100%; }
    100% { left: 200%; }
}
@keyframes agOrbFloat {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33%      { transform: translate(30px, -20px) scale(1.05); }
    66%      { transform: translate(-20px, 15px) scale(0.95); }
}
@keyframes agBarSlide {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes agPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0, 213, 89, 0.4); }
    50%      { box-shadow: 0 0 0 8px rgba(0, 213, 89, 0); }
}
@keyframes agLogoGlow {
    0%, 100% { filter: drop-shadow(0 0 20px rgba(0, 213, 89, 0.15)) drop-shadow(0 0 40px rgba(45, 158, 255, 0.08)); }
    50%      { filter: drop-shadow(0 0 35px rgba(0, 213, 89, 0.25)) drop-shadow(0 0 60px rgba(45, 158, 255, 0.15)); }
}
@keyframes agTickerScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
@keyframes agLivePulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0, 213, 89, 0.5); }
    50%      { box-shadow: 0 0 0 5px rgba(0, 213, 89, 0); }
}

/* ── Background ──────────────────────────────────────────────── */
.ag-bg {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background: radial-gradient(ellipse at 50% 0%, rgba(0, 213, 89, 0.04) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(45, 158, 255, 0.03) 0%, transparent 40%),
                radial-gradient(ellipse at 20% 60%, rgba(192, 132, 252, 0.02) 0%, transparent 40%),
                #0B0F19;
    overflow: hidden;
}
.ag-orb {
    position: absolute; border-radius: 50%; pointer-events: none;
    filter: blur(100px); opacity: 0.5;
    animation: agOrbFloat 20s ease-in-out infinite;
}
.ag-orb-1 {
    width: 400px; height: 400px; top: -100px; left: -80px;
    background: rgba(0, 213, 89, 0.07);
}
.ag-orb-2 {
    width: 350px; height: 350px; bottom: -80px; right: -60px;
    background: rgba(45, 158, 255, 0.06);
    animation-delay: -7s;
}

/* ── Ticker bar ──────────────────────────────────────────────── */
.ag-ticker {
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    height: 36px; display: flex; align-items: center;
    background: rgba(11, 15, 25, 0.92);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    overflow: hidden;
}
.ag-ticker::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 213, 89, 0.3), rgba(45, 158, 255, 0.2), transparent);
    background-size: 300% 100%;
    animation: agBarSlide 4s linear infinite;
}
.ag-ticker-track {
    display: flex; align-items: center; white-space: nowrap;
    animation: agTickerScroll 45s linear infinite;
}
.ag-ticker-item {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0 28px; font-size: 0.68rem; font-weight: 600;
    color: rgba(255, 255, 255, 0.35);
    font-family: 'JetBrains Mono', monospace;
}
.ag-ticker-item .v { font-weight: 700; color: #00D559; }
.ag-ticker-live {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(0, 213, 89, 0.08);
    border: 1px solid rgba(0, 213, 89, 0.15);
    padding: 2px 8px; border-radius: 100px;
    font-size: 0.6rem; font-weight: 800; color: #00D559;
    text-transform: uppercase;
}
.ag-ticker-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: #00D559; animation: agLivePulse 2s ease-in-out infinite;
}

/* ── Logo ────────────────────────────────────────────────────── */
.ag-logo-section {
    text-align: center;
    padding-top: 56px;
    margin-bottom: 0;
    animation: agFadeUp 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-logo-img {
    width: 220px;
    height: auto;
    animation: agLogoGlow 4s ease-in-out infinite;
}

/* ── Hero ────────────────────────────────────────────────────── */
.ag-hero {
    text-align: center;
    margin: 16px 0 0;
    animation: agFadeUp 0.6s 0.08s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-hero h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.85rem; font-weight: 700;
    line-height: 1.15; letter-spacing: -0.03em;
    color: #fff; margin: 0;
}
.ag-hero .em {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.ag-hero-sub {
    font-size: 0.88rem; color: rgba(255, 255, 255, 0.4);
    line-height: 1.55; margin-top: 10px;
}
.ag-hero-sub strong {
    color: rgba(255, 255, 255, 0.75); font-weight: 700;
}

/* ── Proof bar ───────────────────────────────────────────────── */
.ag-proof {
    display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;
    margin: 20px 0 24px;
    animation: agFadeUp 0.6s 0.14s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-proof-item {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.74rem; color: rgba(255, 255, 255, 0.4);
    font-weight: 600;
}
.ag-proof-val {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 800; color: #00D559; font-size: 0.8rem;
}

/* ── Tabs ────────────────────────────────────────────────────── */
[data-testid="stTabs"] {
    animation: agFadeUp 0.6s 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}
[data-testid="stTabs"] > [data-baseweb="tab-list"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px; padding: 3px; gap: 3px;
    justify-content: center; margin-bottom: 16px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 9px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    padding: 10px 24px !important;
    color: rgba(255, 255, 255, 0.3) !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    transition: all 0.25s ease !important;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(0, 213, 89, 0.08) !important;
    color: #fff !important;
    border-color: rgba(0, 213, 89, 0.2) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}

/* ── Form card ───────────────────────────────────────────────── */
[data-testid="stForm"] {
    background: rgba(255, 255, 255, 0.025) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 18px !important;
    padding: 28px 24px 24px !important;
    backdrop-filter: blur(30px) !important;
    -webkit-backdrop-filter: blur(30px) !important;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4) !important;
    position: relative; overflow: hidden;
}
[data-testid="stForm"]::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 213, 89, 0.3), rgba(45, 158, 255, 0.2), transparent);
}

/* ── Inputs ──────────────────────────────────────────────────── */
[data-testid="stForm"] input {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    color: #fff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important;
    padding: 12px 14px !important;
    transition: all 0.2s ease !important;
    caret-color: #00D559 !important;
}
[data-testid="stForm"] input:focus {
    border-color: rgba(0, 213, 89, 0.4) !important;
    box-shadow: 0 0 0 3px rgba(0, 213, 89, 0.08) !important;
    background: rgba(255, 255, 255, 0.06) !important;
    outline: none !important;
}
[data-testid="stForm"] input::placeholder {
    color: rgba(255, 255, 255, 0.18) !important;
}
[data-testid="stForm"] label {
    color: rgba(255, 255, 255, 0.45) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
}
[data-testid="stForm"] [data-testid="stTextInputRootElement"] button {
    color: rgba(255, 255, 255, 0.3) !important;
}

/* ── CTA button ──────────────────────────────────────────────── */
[data-testid="stForm"] button[kind="primaryFormSubmit"],
[data-testid="stForm"] button[type="submit"] {
    background: linear-gradient(135deg, #00D559 0%, #00B74D 100%) !important;
    color: #fff !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 28px !important;
    margin-top: 8px !important;
    box-shadow: 0 4px 24px rgba(0, 213, 89, 0.3) !important;
    transition: all 0.2s ease !important;
    position: relative; overflow: hidden;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2) !important;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]::after,
[data-testid="stForm"] button[type="submit"]::after {
    content: ''; position: absolute; top: 0; width: 60px; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.15), transparent);
    animation: agShimmer 3s ease-in-out infinite;
}
[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
[data-testid="stForm"] button[type="submit"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 32px rgba(0, 213, 89, 0.4) !important;
}

/* ── Below-fold sections ─────────────────────────────────────── */

/* Section header */
.ag-section-head {
    text-align: center; margin-bottom: 16px;
}
.ag-section-head h3 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.15rem; font-weight: 700;
    color: #fff; margin: 0 0 4px;
    letter-spacing: -0.02em;
}
.ag-section-head p {
    font-size: 0.72rem; color: rgba(255, 255, 255, 0.3);
    margin: 0;
}

/* Comparison table */
.ag-compare {
    margin: 36px 0 0;
    animation: agFadeUp 0.6s 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-tbl {
    width: 100%; border-collapse: separate; border-spacing: 0;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px; overflow: hidden;
    font-size: 0.74rem;
}
.ag-tbl thead th {
    padding: 11px 12px; font-size: 0.65rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: rgba(255, 255, 255, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.ag-tbl thead th:first-child { text-align: left; width: 40%; }
.ag-tbl thead th:nth-child(2) { text-align: center; color: rgba(242, 67, 54, 0.5); }
.ag-tbl thead th:nth-child(3) { text-align: center; color: #00D559; background: rgba(0, 213, 89, 0.03); }
.ag-tbl tbody td {
    padding: 9px 12px; color: rgba(255, 255, 255, 0.45);
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    font-weight: 500;
}
.ag-tbl tbody td:first-child { font-weight: 600; color: rgba(255, 255, 255, 0.6); text-align: left; }
.ag-tbl tbody td:nth-child(2) { text-align: center; color: rgba(242, 67, 54, 0.4); }
.ag-tbl tbody td:nth-child(3) { text-align: center; color: #00D559; background: rgba(0, 213, 89, 0.02); font-weight: 700; }
.ag-tbl tbody tr:last-child td { border-bottom: none; }

/* Feature cards (3-col) */
.ag-features {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-feat {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 14px; padding: 18px 10px 14px;
    text-align: center;
    transition: border-color 0.2s, transform 0.2s;
}
.ag-feat:hover {
    border-color: rgba(255, 255, 255, 0.1);
    transform: translateY(-2px);
}
.ag-feat-ico { font-size: 1.3rem; margin-bottom: 6px; display: block; }
.ag-feat-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.7rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.8);
    line-height: 1.2;
}
.ag-feat-desc {
    font-size: 0.58rem; color: rgba(255, 255, 255, 0.28);
    margin-top: 3px;
}

/* Metric counters */
.ag-stats {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-stat {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px; padding: 14px 8px 10px;
    text-align: center;
}
.ag-stat-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.3rem; font-weight: 700;
    color: #00D559; line-height: 1.1;
}
.ag-stat-label {
    font-size: 0.58rem; color: rgba(255, 255, 255, 0.25);
    font-weight: 600; margin-top: 3px;
    text-transform: uppercase; letter-spacing: 0.05em;
}

/* Testimonials */
.ag-reviews {
    margin: 28px 0 0;
    animation: agFadeUp 0.6s 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-review {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px; padding: 16px 18px;
    margin-bottom: 8px;
}
.ag-review-text {
    font-size: 0.8rem; color: rgba(255, 255, 255, 0.55);
    font-style: italic; line-height: 1.5;
}
.ag-review-author {
    font-size: 0.66rem; font-weight: 700;
    color: rgba(0, 213, 89, 0.6);
    margin-top: 6px;
}
.ag-review-stars {
    color: #F9C62B; font-size: 0.6rem; margin-top: 2px;
}

/* Pricing */
.ag-pricing {
    margin: 32px 0 0;
    animation: agFadeUp 0.6s 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-price-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;
}
.ag-price {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px; padding: 18px 14px;
    text-align: center;
    transition: border-color 0.2s;
}
.ag-price:hover { border-color: rgba(255, 255, 255, 0.1); }
.ag-price.pop {
    border-color: rgba(0, 213, 89, 0.25);
    background: rgba(0, 213, 89, 0.03);
    position: relative;
}
.ag-price.pop::after {
    content: 'MOST POPULAR'; position: absolute; top: -8px; left: 50%;
    transform: translateX(-50%);
    font-size: 0.48rem; font-weight: 800; letter-spacing: 0.1em;
    color: #0B0F19; background: #00D559;
    padding: 2px 8px; border-radius: 100px;
    font-family: 'Space Grotesk', sans-serif;
}
.ag-price-tier {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.68rem; font-weight: 700;
    color: rgba(255, 255, 255, 0.45);
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-bottom: 4px;
}
.ag-price-amount {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem; font-weight: 700; color: #fff;
}
.ag-price-amount .p {
    font-size: 0.55rem; font-weight: 500; color: rgba(255, 255, 255, 0.25);
}
.ag-price-info {
    font-size: 0.58rem; color: rgba(255, 255, 255, 0.3);
    margin-top: 6px; line-height: 1.5;
}
.ag-price-info strong { color: rgba(255, 255, 255, 0.55); }

/* Trust + footer */
.ag-trust {
    display: flex; justify-content: center; gap: 16px;
    margin: 28px 0 6px; flex-wrap: wrap;
    animation: agFadeUp 0.6s 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-trust-item {
    font-size: 0.62rem; font-weight: 600;
    color: rgba(255, 255, 255, 0.22);
    display: flex; align-items: center; gap: 4px;
}
.ag-footer {
    text-align: center; padding: 20px 0 40px;
    font-size: 0.55rem; color: rgba(255, 255, 255, 0.1);
    line-height: 1.7;
    animation: agFadeUp 0.6s 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.ag-footer a { color: rgba(255, 255, 255, 0.15); text-decoration: underline; }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 520px) {
    .ag-hero h1 { font-size: 1.5rem; }
    .ag-logo-img { width: 180px; }
    .ag-features { grid-template-columns: 1fr 1fr; }
    .ag-stats { grid-template-columns: 1fr 1fr; }
    .ag-price-grid { grid-template-columns: 1fr; }
    [data-testid="stForm"] { padding: 22px 18px 20px !important; }
    .ag-proof { gap: 14px; }
}
</style>
"""


# ── Main gate function ────────────────────────────────────────

def require_login() -> bool:
    """Render the Smart Pick Pro auth gate.

    Returns True if authenticated, False otherwise (caller should st.stop()).
    """
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        return True

    if is_logged_in():
        return True

    # ── Inject CSS ────────────────────────────────────────
    st.markdown(_GATE_CSS, unsafe_allow_html=True)

    # ── Logo base64 ───────────────────────────────────────
    _logo_b64 = _get_logo_b64()

    # ── Ticker items ──────────────────────────────────────
    _ticker = (
        '<span class="ag-ticker-live"><span class="ag-ticker-dot"></span> LIVE</span>'
        '<span class="ag-ticker-item">Hit Rate <span class="v">62.4%</span></span>'
        '<span class="ag-ticker-item">Props Scanned <span class="v">347</span></span>'
        '<span class="ag-ticker-item">Models Active <span class="v">6/6</span></span>'
        '<span class="ag-ticker-item">SAFE Score Avg <span class="v">71.2</span></span>'
        '<span class="ag-ticker-item">Edge Detected <span class="v">+4.8%</span></span>'
        '<span class="ag-ticker-item">Bankroll ROI <span class="v">+18.3%</span></span>'
        '<span class="ag-ticker-item">CLV Capture <span class="v">92%</span></span>'
        '<span class="ag-ticker-item">Users Online <span class="v">1,247</span></span>'
    )

    # ── Above-fold: BG + Ticker + Logo + Hero + Proof ─────
    _logo_html = (
        f'<img class="ag-logo-img" src="data:image/png;base64,{_logo_b64}" alt="Smart Pick Pro">'
        if _logo_b64
        else ''
    )

    st.markdown(f"""
    <div class="ag-bg">
      <div class="ag-orb ag-orb-1"></div>
      <div class="ag-orb ag-orb-2"></div>
    </div>

    <div class="ag-ticker">
      <div class="ag-ticker-track">{_ticker}{_ticker}</div>
    </div>

    <div class="ag-logo-section">{_logo_html}</div>

    <div class="ag-hero">
      <h1>The House Has a Problem.<br><span class="em">It&rsquo;s Us.</span></h1>
      <div class="ag-hero-sub">
        <strong>6 AI models. 1 edge.</strong> &mdash; Free forever, no credit card.
      </div>
    </div>

    <div class="ag-proof">
      <div class="ag-proof-item"><span class="ag-proof-val">62%</span> Hit Rate</div>
      <div class="ag-proof-item"><span class="ag-proof-val">6</span> AI Models</div>
      <div class="ag-proof-item"><span class="ag-proof-val">300+</span> Props/Night</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Auth tabs + forms ─────────────────────────────────
    tab_signup, tab_login = st.tabs(["\u26A1  Create Free Account", "\U0001F513  Log In"])

    with tab_signup:
        with st.form("signup_form", clear_on_submit=False):
            su_name = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email Address", placeholder="you@example.com", key="_su_email")
            su_pw = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter password", key="_su_pw2")
            su_submit = st.form_submit_button("\u26A1 Create Free Account", use_container_width=True, type="primary")

        if su_submit:
            if not su_email or not _valid_email(su_email):
                st.error("Please enter a valid email address.")
            elif pw_err := _valid_password(su_pw):
                st.error(pw_err)
            elif su_pw != su_pw2:
                st.error("Passwords don't match.")
            elif _email_exists(su_email):
                st.error("An account with this email already exists. Please log in instead.")
            else:
                ok = _create_user(su_email, su_pw, su_name)
                if ok:
                    user = _authenticate_user(su_email, su_pw)
                    if user:
                        _set_logged_in(user)
                        st.success("Account created! Welcome to Smart Pick Pro.")
                        st.rerun()
                    else:
                        st.error("Account created but login failed. Please try logging in.")
                else:
                    st.error("Could not create account. Please try again.")

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            li_email = st.text_input("Email Address", placeholder="you@example.com", key="_li_email")
            li_pw = st.text_input("Password", type="password", placeholder="Enter your password", key="_li_pw")
            li_submit = st.form_submit_button("\U0001F513 Log In", use_container_width=True, type="primary")

        if li_submit:
            if not li_email or not _valid_email(li_email):
                st.error("Please enter a valid email address.")
            elif not li_pw:
                st.error("Please enter your password.")
            else:
                user = _authenticate_user(li_email, li_pw)
                if user:
                    _set_logged_in(user)
                    st.success(f"Welcome back, {user.get('display_name', '')}!")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

    # ── Below-fold conversion content ─────────────────────
    st.markdown("""
    <div class="ag-compare">
      <div class="ag-section-head">
        <h3>Why Sharps Are Switching</h3>
        <p>What you get that nowhere else offers</p>
      </div>
      <table class="ag-tbl">
        <thead><tr><th>Feature</th><th>Others</th><th>Smart Pick Pro</th></tr></thead>
        <tbody>
          <tr><td>AI Models</td><td>0 &ndash; 1</td><td>6 Fused</td></tr>
          <tr><td>Prop Coverage</td><td>Top 20</td><td>300+ / Night</td></tr>
          <tr><td>Live Tracking</td><td>&#x2717;</td><td>Real-Time</td></tr>
          <tr><td>Confidence Score</td><td>&#x2717;</td><td>SAFE Score 0-100</td></tr>
          <tr><td>Bankroll Tools</td><td>&#x2717;</td><td>Kelly + Custom</td></tr>
          <tr><td>Matchup Analysis</td><td>Basic</td><td>Defensive DNA</td></tr>
          <tr><td>Line Movement</td><td>&#x2717;</td><td>Real-Time Alerts</td></tr>
          <tr><td>Backtesting</td><td>&#x2717;</td><td>Full Archive</td></tr>
          <tr><td>Price</td><td>$30-$300/mo</td><td>Free Forever</td></tr>
          <tr><td>Setup Time</td><td>Hours</td><td>10 Seconds</td></tr>
        </tbody>
      </table>
    </div>

    <div class="ag-features">
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F9E0;</span>
        <div class="ag-feat-name">Quantum Engine</div>
        <div class="ag-feat-desc">6 AI models fused</div>
      </div>
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F3AF;</span>
        <div class="ag-feat-name">SAFE Score</div>
        <div class="ag-feat-desc">0-100 confidence</div>
      </div>
      <div class="ag-feat">
        <span class="ag-feat-ico">&#x1F4E1;</span>
        <div class="ag-feat-name">Live Sweat</div>
        <div class="ag-feat-desc">Real-time tracking</div>
      </div>
    </div>

    <div class="ag-stats">
      <div class="ag-stat">
        <div class="ag-stat-val">62.4%</div>
        <div class="ag-stat-label">Hit Rate</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">+18.3%</div>
        <div class="ag-stat-label">ROI</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">347</div>
        <div class="ag-stat-label">Props / Night</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">92%</div>
        <div class="ag-stat-label">CLV Capture</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">6</div>
        <div class="ag-stat-label">AI Models</div>
      </div>
      <div class="ag-stat">
        <div class="ag-stat-val">10s</div>
        <div class="ag-stat-label">Setup Time</div>
      </div>
    </div>

    <div class="ag-reviews">
      <div class="ag-section-head">
        <h3>What Sharps Are Saying</h3>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">The Quantum Engine literally changed how I bet. I went from random parlays to a real mathematical edge.</div>
        <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
        <div class="ag-review-author">&mdash; @sharpbettor_mike</div>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">SAFE Score saved me from so many bad bets. I only play 80+ rated props now and my bankroll keeps growing.</div>
        <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
        <div class="ag-review-author">&mdash; @datadrivendenver</div>
      </div>
      <div class="ag-review">
        <div class="ag-review-text">Live Sweat Mode is addictive. Watching props track in real-time with AI confidence updates &mdash; nothing else does this.</div>
        <div class="ag-review-stars">&#x2B50;&#x2B50;&#x2B50;&#x2B50;&#x2B50;</div>
        <div class="ag-review-author">&mdash; @nightowl_picks</div>
      </div>
    </div>

    <div class="ag-pricing">
      <div class="ag-section-head">
        <h3>Simple Pricing</h3>
        <p>Start free. Upgrade when you want more.</p>
      </div>
      <div class="ag-price-grid">
        <div class="ag-price">
          <div class="ag-price-tier">Free</div>
          <div class="ag-price-amount">$0 <span class="p">forever</span></div>
          <div class="ag-price-info"><strong>3 props / night</strong><br>Quantum Analysis &middot; SAFE Scores</div>
        </div>
        <div class="ag-price pop">
          <div class="ag-price-tier">Sharp IQ</div>
          <div class="ag-price-amount">$9.99 <span class="p">/mo</span></div>
          <div class="ag-price-info"><strong>Unlimited props</strong><br>Advanced filters &middot; Bankroll tools</div>
        </div>
        <div class="ag-price">
          <div class="ag-price-tier">Smart Money</div>
          <div class="ag-price-amount">$24.99 <span class="p">/mo</span></div>
          <div class="ag-price-info"><strong>Live Sweat</strong><br>Line alerts &middot; Edge detection</div>
        </div>
        <div class="ag-price">
          <div class="ag-price-tier">Insider Circle</div>
          <div class="ag-price-amount">$499 <span class="p">once</span></div>
          <div class="ag-price-info"><strong>Lifetime access</strong><br>Everything + priority support</div>
        </div>
      </div>
    </div>

    <div class="ag-trust">
      <div class="ag-trust-item">&#x1F512; 256-bit Encrypted</div>
      <div class="ag-trust-item">&#x1F4B3; No Credit Card</div>
      <div class="ag-trust-item">&#x1F6AB; Never Sell Data</div>
    </div>

    <div class="ag-footer">
      &copy; 2025 Smart Pick Pro &middot; For entertainment &amp; educational purposes only &middot; 21+<br>
      <a href="https://www.ncpgambling.org/" target="_blank">National Council on Problem Gambling &middot; 1-800-GAMBLER</a>
    </div>
    """, unsafe_allow_html=True)

    return False
