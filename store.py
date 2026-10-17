"""The SQLite file and the committed blade list it is built from.

blades.db is local state (your answers) and stays out of git. data/blades.json
is the blade list from the last scrape; it is committed so a fresh checkout
(or a Railway deploy) can build the database without crawling oarspotter.com.
"""
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).parent
DB = ROOT / "blades.db"
SEED = ROOT / "data" / "blades.json"

BLADE_COLUMNS = ("id", "name", "short", "code", "location", "country", "category", "section",
                 "image_url", "club_url", "source_url", "solid", "wr_code", "wr_name")

SCHEMA = """
CREATE TABLE IF NOT EXISTS blades (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    short TEXT,
    code TEXT,
    location TEXT,
    country TEXT NOT NULL,
    category TEXT NOT NULL,
    section TEXT,
    image_url TEXT NOT NULL,
    club_url TEXT,
    source_url TEXT NOT NULL,
    solid INTEGER NOT NULL DEFAULT 0,
    UNIQUE (name, image_url)
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY,
    blade_id INTEGER NOT NULL REFERENCES blades(id),
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    correct INTEGER NOT NULL,
    hints INTEGER NOT NULL DEFAULT 0,
    tries INTEGER NOT NULL DEFAULT 1,
    last_guess TEXT
);
"""


def migrate(con):
    con.executescript(SCHEMA)
    have = {r[1] for r in con.execute("PRAGMA table_info(blades)")}
    for col in ("wr_code", "wr_name"):
        if col not in have:
            con.execute(f"ALTER TABLE blades ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")


def export_seed(con):
    rows = con.execute(f"SELECT {', '.join(BLADE_COLUMNS)} FROM blades ORDER BY id").fetchall()
    SEED.parent.mkdir(exist_ok=True)
    SEED.write_text(json.dumps([dict(zip(BLADE_COLUMNS, r)) for r in rows], ensure_ascii=False, indent=0) + "\n")


def ensure_db():
    """Create blades.db if needed and bring its blades up to date with the seed."""
    con = sqlite3.connect(DB)
    try:
        migrate(con)
        if SEED.exists():
            cols = ", ".join(BLADE_COLUMNS)
            updates = ", ".join(f"{c}=excluded.{c}" for c in BLADE_COLUMNS if c != "id")
            con.executemany(
                f"INSERT INTO blades ({cols}) VALUES ({', '.join(':' + c for c in BLADE_COLUMNS)}) "
                f"ON CONFLICT (id) DO UPDATE SET {updates}",
                json.loads(SEED.read_text()),
            )
        con.commit()
        if not con.execute("SELECT count(*) FROM blades").fetchone()[0]:
            raise SystemExit("No blades: run `uv run scrape.py` first")
    finally:
        con.close()
