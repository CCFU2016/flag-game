"""Answer history in SQLite (quiz.db, not committed). Keyed by World Rowing code."""
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).parent
DB = ROOT / "quiz.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    correct INTEGER NOT NULL,
    hints INTEGER NOT NULL DEFAULT 0,
    tries INTEGER NOT NULL DEFAULT 1,
    last_guess TEXT
);
CREATE INDEX IF NOT EXISTS answers_code ON answers (code, id);
"""


def ensure_db():
    con = sqlite3.connect(DB)
    try:
        con.executescript(SCHEMA)
    finally:
        con.close()
