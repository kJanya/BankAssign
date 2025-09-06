import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parents[1] / "data.sqlite3"))

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    # Students table (keeps raw input and fingerprint for dedupe)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students(
        student_id TEXT PRIMARY KEY,
        fp TEXT NOT NULL,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        desired_course TEXT NOT NULL,
        request_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_fp ON students(fp)")
    # Decisions table (stores the computed output)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS decisions(
        decision_id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        eligible INTEGER NOT NULL,
        reasons TEXT NOT NULL,
        recommendations TEXT NOT NULL,
        response_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
    )
    """)
    # Logs table (stores request/response logs independently)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs(
        log_id TEXT PRIMARY KEY,
        direction TEXT NOT NULL, -- 'in' or 'out'
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()
