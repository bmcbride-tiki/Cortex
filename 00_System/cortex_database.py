# =============================================================================
# cortex_database.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A second, separate SQLite database file (`cortex.db`, sitting right next
#   to `brain_state.db`) for data that doesn't belong in the main Workbrain
#   database -- starting with web-scraped page content. Kept as its own file
#   (rather than more tables in `brain_state.db`) since scraped page content
#   can grow large and has nothing to do with Workbrain's own trade/exam/
#   contact records.
#
# WHAT IT INTERACTS WITH
#   - `cortex.db`, created automatically (if it doesn't already exist) right
#     next to this file, in `00_System`.
#   - `12_Tasks/webscraper/webscraper.py`, the first (and so far only)
#     consumer, which writes one `web_scrape_jobs` row per run and one
#     `web_scrape_data` row per page it visits.
#
# KEY FUNCTIONALITY NOTES
#   - Same conventions as `database.py`: `initialize_database()` uses
#     `CREATE TABLE IF NOT EXISTS` throughout, so it's safe to call every
#     time before use rather than only once.
# =============================================================================

import sqlite3
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
DB_PATH = CURRENT_DIR / "cortex.db"

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # One row per scraper run: the settings it was given and how far it got.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_scrape_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed_url TEXT NOT NULL,
            max_folders INTEGER NOT NULL,
            max_files INTEGER NOT NULL,
            folders_seen INTEGER NOT NULL DEFAULT 0,
            pages_scanned INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            started TEXT NOT NULL DEFAULT (datetime('now')),
            finished TEXT
        );
    """)

    # One row per page the scraper actually visited and read.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_scrape_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES web_scrape_jobs(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            title TEXT,
            content TEXT,
            links_found INTEGER NOT NULL DEFAULT 0,
            scanned TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(job_id, url)
        );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrape_data_job ON web_scrape_data(job_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrape_data_url ON web_scrape_data(url);")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Running this file directly (`python cortex_database.py`) sets up/repairs
    # the database schema on demand.
    initialize_database()
