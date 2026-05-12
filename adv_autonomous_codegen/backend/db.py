import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "history.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            task TEXT,
            model TEXT,
            status TEXT,
            summary TEXT,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            log_type TEXT,
            content TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_session(session_id: str, task: str, model: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO sessions (session_id, task, model, status, created_at) VALUES (?, ?, ?, ?, ?)",
              (session_id, task, model, "running", datetime.now().isoformat()))
    conn.commit()
    conn.close()

def append_log(session_id: str, log_type: str, content: dict | str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    content_str = json.dumps(content) if isinstance(content, dict) else content
    c.execute("INSERT INTO logs (session_id, log_type, content, timestamp) VALUES (?, ?, ?, ?)",
              (session_id, log_type, content_str, datetime.now().isoformat()))
    conn.commit()
    conn.close()