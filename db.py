import sqlite3
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "assistant.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                voice_profile TEXT,
                created_at REAL,
                last_seen REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()

def save_message(session_id, role, content):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time())
        )
        conn.commit()

def get_messages(session_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        ).fetchall()
        return [dict(row) for row in rows]

def clear_session_messages(session_id):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()

def ensure_session(session_id):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        now = time.time()
        if not row:
            conn.execute(
                "INSERT INTO sessions (id, created_at, last_seen) VALUES (?, ?, ?)",
                (session_id, now, now)
            )
        else:
            conn.execute(
                "UPDATE sessions SET last_seen = ? WHERE id = ?",
                (now, session_id)
            )
        conn.commit()

def update_session_profile(session_id, voice_profile):
    with get_db() as conn:
        conn.execute(
            "UPDATE sessions SET voice_profile = ? WHERE id = ?",
            (voice_profile, session_id)
        )
        conn.commit()

def get_session_profile(session_id):
    with get_db() as conn:
        row = conn.execute("SELECT voice_profile FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row["voice_profile"] if row else None

init_db()
