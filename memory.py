# =============================================================================
# memory.py  –  Long-term (SQLite) and short-term (session state) persistence
# =============================================================================
import json
import os
import sqlite3
from datetime import datetime

import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "user_memory.db")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS resume (
                id         INTEGER PRIMARY KEY,
                text       TEXT,
                updated_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key        TEXT PRIMARY KEY,
                value      TEXT,
                updated_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS job_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                role        TEXT,
                location    TEXT,
                results     TEXT,
                searched_at TEXT
            )
        """)


# ---------------------------------------------------------------------------
# Resume  (long-term)
# ---------------------------------------------------------------------------

def save_resume(text: str) -> None:
    """Persist the user's resume text to SQLite."""
    if not text or not text.strip():
        return
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM resume")
        c.execute(
            "INSERT INTO resume (id, text, updated_at) VALUES (1, ?, ?)",
            (text, datetime.now().isoformat()),
        )


def load_resume() -> str:
    """Return the last-saved resume text, or empty string."""
    init_db()
    with _conn() as c:
        row = c.execute("SELECT text FROM resume WHERE id = 1").fetchone()
    return row["text"] if row else ""


# ---------------------------------------------------------------------------
# Preferences  (long-term)
# ---------------------------------------------------------------------------

def save_preferences(prefs: dict) -> None:
    """Persist a dict of preference key→value to SQLite."""
    init_db()
    now = datetime.now().isoformat()
    with _conn() as c:
        for key, value in prefs.items():
            c.execute(
                "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), now),
            )


def load_preferences() -> dict:
    """Return all saved preferences as a plain dict."""
    init_db()
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM preferences").fetchall()
    return {row["key"]: json.loads(row["value"]) for row in rows}


# ---------------------------------------------------------------------------
# Job-search history  (long-term)
# ---------------------------------------------------------------------------

def save_job_search(role: str, location: str, results: str) -> None:
    """Append a completed job-search result to the history table."""
    init_db()
    with _conn() as c:
        c.execute(
            "INSERT INTO job_history (role, location, results, searched_at) VALUES (?, ?, ?, ?)",
            (role, location, results, datetime.now().isoformat()),
        )


def load_job_history(limit: int = 10) -> list[dict]:
    """Return the *limit* most-recent job searches, newest first."""
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT role, location, results, searched_at "
            "FROM job_history ORDER BY searched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Short-term memory helpers  (Streamlit session state)
# ---------------------------------------------------------------------------

def init_session_resume() -> None:
    """On the very first script run per session, pre-load the saved resume."""
    if "_memory_loaded" in st.session_state:
        return
    saved = load_resume()
    if saved and "resume_text" not in st.session_state:
        st.session_state["resume_text"] = saved
        st.session_state["_resume_from_db"] = True
    st.session_state["_memory_loaded"] = True


def init_session_preferences() -> None:
    """On the very first script run per session, pre-load saved job-search prefs."""
    if "_prefs_loaded" in st.session_state:
        return
    prefs = load_preferences()
    defaults = {
        "pref_role":         prefs.get("desired_role", ""),
        "pref_location":     prefs.get("location", ""),
        "pref_work_type":    prefs.get("work_type", "Any"),
        "pref_experience":   prefs.get("experience", "Any"),
        "pref_industry":     prefs.get("industry", ""),
        "pref_salary":       prefs.get("salary", ""),
        "pref_class_key":    prefs.get("class_standing_key", "N/A"),
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    st.session_state["_prefs_loaded"] = True
