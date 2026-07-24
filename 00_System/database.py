# =============================================================================
# database.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Defines and creates every table in Workbrain's single shared database
#   file, `brain_state.db`. Nearly every other file in this project that
#   needs to read or store structured data (contacts, class schedules, exam
#   marks, workflow definitions, etc.) goes through the connection this
#   file hands out, and the tables this file defines.
#
#   "SQLite" (the database technology used here) is a simple, file-based
#   database: unlike bigger database systems, there's no separate server
#   program to install or run -- the entire database is just one file
#   (`brain_state.db`) sitting on disk, and any program that knows how to
#   read that file format can open and query it directly.
#
# WHAT IT INTERACTS WITH
#   - `brain_state.db`, created automatically (if it doesn't already exist)
#     right next to this file, in `00_System_Core`.
#   - Nearly every other .py file in this project imports
#     `get_db_connection()` from here whenever it needs to read or write
#     something to that shared database.
#
# KEY FUNCTIONALITY NOTES
#   - `initialize_database()` is written to be safe to run over and over --
#     every `CREATE TABLE IF NOT EXISTS` only actually creates a table the
#     very first time it's missing; running it again later does nothing
#     destructive, it just confirms everything already exists. This file's
#     own `if __name__ == "__main__":` block at the bottom runs exactly
#     that function, so `python database.py` is a safe, repeatable way to
#     make sure the database is fully set up.
#   - Several tables also get a small amount of starter ("seed") example
#     data inserted automatically the first time, purely so the app has
#     something to display and test against immediately, without requiring
#     you to manually enter records first.
#   - "PRIMARY KEY" marks the column (or combination of columns) that
#     uniquely identifies each row in a table -- like a row's ID number.
#     "FOREIGN KEY" marks a column whose value is expected to match a
#     primary key in a different table, which is how two related tables
#     stay linked together (e.g. an exam attempt row references which
#     specific class it belongs to). "UNIQUE" means the database itself
#     will refuse to let two rows share the same value in that column
#     (or combination of columns).
#   - "CREATE INDEX" near the bottom doesn't create a new table or new
#     data -- it just tells the database to build an internal shortcut for
#     looking things up by certain columns much faster, similar in spirit
#     to an index at the back of a book.
# =============================================================================

import sqlite3
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
DB_PATH = CURRENT_DIR / "cortex.db"

def get_db_connection():
    # Opens a fresh connection to the shared brain_state.db file. Setting
    # row_factory to sqlite3.Row means query results can be accessed both
    # by column name (row["email"]) and by position (row[1]) -- more
    # readable for the rest of the codebase than positional-only access.
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    # Creates every table (and a bit of starter data) this project relies
    # on, if they don't already exist. Safe to call repeatedly/on every
    # server startup -- see the file-level notes above.
    conn = get_db_connection()
    cursor = conn.cursor()

    # Enable foreign keys. SQLite doesn't enforce FOREIGN KEY relationships
    # by default unless this is turned on for the connection -- without it,
    # the database would silently allow rows that reference a
    # non-existent parent row.
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Base Search Index (utilized by FOIP search query)
    # This is a special "full-text search" table (the fts5 part), purpose-built
    # for fast free-text keyword searching across many records at once --
    # unlike a normal table, it's optimized specifically for "find rows
    # containing these words" style queries rather than exact matches.
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS global_search_index USING fts5(
            origin_id,
            content_type,
            body_text
        );
    """)

    # 2. Historical Registrations Table (actuals baseline data)
    # One row per (trade, year) combination: how many apprentices actually
    # registered for that trade in that year, historically.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT NOT NULL,
            period INTEGER NOT NULL,
            count INTEGER NOT NULL,
            UNIQUE(trade_id, period)
        );
    """)

    # 3. Projected Registrations Table (Scenario runs tracker)
    # Similar to the table above, but for hypothetical FUTURE projections
    # rather than historical fact -- scenario_label lets more than one
    # "what if" projection scenario be stored side by side for the same
    # trade/year without overwriting each other.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projected_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_label TEXT NOT NULL,
            trade_id TEXT NOT NULL,
            period INTEGER NOT NULL,
            projected_count REAL NOT NULL,
            growth_rate_applied REAL NOT NULL,
            UNIQUE(scenario_label, trade_id, period)
        );
    """)

    # 4. Training Classes Metadata
    # One row per class offering: which trade, which training provider,
    # which exam it leads to. class_code is this class's unique ID number
    # and is what other tables below reference to link back to it.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_classes (
            class_code INTEGER PRIMARY KEY,
            training_provider TEXT NOT NULL,
            trade TEXT NOT NULL,
            period INTEGER NOT NULL,
            exam_name TEXT NOT NULL,
            ref_ver TEXT NOT NULL
        );
    """)

    # 5. Apprentice Exam Attempts (1 Row per Session Attempt)
    # One row per individual apprentice's attempt at an exam for a given
    # class. FOREIGN KEY (class_code) ties each attempt back to the
    # training_classes row it belongs to.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apprentice_exam_attempts (
            class_code INTEGER NOT NULL,
            ait_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,
            class_mark REAL,
            ait_exam_mark REAL,
            is_rewrite INTEGER NOT NULL,
            PRIMARY KEY (class_code, ait_id, exam_date),
            FOREIGN KEY (class_code) REFERENCES training_classes(class_code)
        );
    """)

    # 6. Individual Section Scores per Attempt
    # Exams are broken into sections (e.g. separate topic areas); this
    # table holds the finer-grained per-section marks belonging to one
    # specific exam attempt from the table above.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apprentice_section_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code INTEGER NOT NULL,
            ait_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,
            section REAL NOT NULL,
            class_section_name TEXT,
            exam_section_name TEXT,
            class_section_mark REAL,
            exam_section_mark REAL,
            FOREIGN KEY (class_code, ait_id, exam_date) REFERENCES apprentice_exam_attempts(class_code, ait_id, exam_date)
        );
    """)

    # 7. Exam Pass/Fail Aggregates Table
    # Summary-level counts (rather than individual attempts) of pass/fail
    # outcomes, grouped by trade/exam/classification.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exam_pass_fail_aggregates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade TEXT NOT NULL,
            exam_name TEXT NOT NULL,
            classification TEXT,
            exam_type TEXT,
            ref_ver TEXT
        );
    """)

    # 8. Transcripts Metadata Table
    # Tracks meeting/interview transcripts that have been indexed into the
    # vault (title, which trade it relates to, and where it came from),
    # used e.g. by the Copilot bridge's transcript picker.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            trade TEXT,
            source_type TEXT NOT NULL
        );
    """)

    # 9. Advanced CRM Contact Management Table
    # A simple contacts/relationship-tracking table -- name, how to reach
    # them, which trade/company they're associated with, and a running
    # count of how many times they've been engaged with.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            company TEXT,
            trade TEXT NOT NULL,
            total_engagements INTEGER DEFAULT 0,
            last_contact_date TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Active'
        );
    """)

    # 10. Class Schedule Catalogue (scraped from tradesecrets.alberta.ca training catalogue)
    # This is the table query_schedules.py's search tool reads from -- one
    # row per scheduled class section (trade, provider, campus, dates).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_year TEXT NOT NULL,
            trade TEXT NOT NULL,
            trade_code TEXT NOT NULL,
            training_provider TEXT NOT NULL,
            campus TEXT NOT NULL,
            period INTEGER NOT NULL,
            class_code INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            UNIQUE(class_code, trade_code, school_year)
        );
    """)

    # 11. Process Tag Registry (colored tags used to group/filter the Processes page)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL
        );
    """)

    # 12. Process/Task/Workflow <-> Tag Assignments (many-to-many; an item may carry
    # several tags). This is a "join table": an item can have several tags, and a tag
    # can apply to several items, so this table just stores each valid
    # (category, tool_id, tag) pairing as its own row rather than trying to cram a
    # list of tags into a single column. `category` ('process' | 'task' | 'workflow')
    # scopes each assignment to its own activity list even though Processes, Tasks,
    # and Workflows all share the one process_tags registry above -- so a Task and a
    # Process that happen to share a tool_id don't leak tag assignments into each other.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_tag_links (
            category TEXT NOT NULL DEFAULT 'process',
            tool_id TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (category, tool_id, tag_id),
            FOREIGN KEY (tag_id) REFERENCES process_tags(id) ON DELETE CASCADE
        );
    """)
    # This table existed before the `category` column was added to it (back when it
    # only ever tracked Processes). SQLite can't add a column into an existing
    # PRIMARY KEY, so if an older copy of the database is missing it, rebuild the
    # table -- preserving existing rows as category='process', the only category
    # that existed before Tasks and Workflows got their own tag lists.
    cursor.execute("PRAGMA table_info(process_tag_links);")
    if "category" not in {row[1] for row in cursor.fetchall()}:
        cursor.execute("ALTER TABLE process_tag_links RENAME TO process_tag_links_old;")
        cursor.execute("""
            CREATE TABLE process_tag_links (
                category TEXT NOT NULL DEFAULT 'process',
                tool_id TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (category, tool_id, tag_id),
                FOREIGN KEY (tag_id) REFERENCES process_tags(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("""
            INSERT INTO process_tag_links (category, tool_id, tag_id)
            SELECT 'process', tool_id, tag_id FROM process_tag_links_old;
        """)
        cursor.execute("DROP TABLE process_tag_links_old;")

    # 13. Agentic Workflow (Agent Builder Console) JSON Template Registry.
    # The template's raw JSON text lives in `content` -- no on-disk file, brain_state.db
    # is the single source of truth so templates travel with the database (backups, sync, etc).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS abc_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL DEFAULT (datetime('now')),
            updated TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    # This table existed before the `content` column was added to it. This
    # checks whether an older copy of the database is missing that column
    # and, if so, adds it on the fly -- a lightweight, manual version of
    # what's normally called a database "migration," so older databases
    # created before this column existed don't break.
    cursor.execute("PRAGMA table_info(abc_templates);")
    if "content" not in {row[1] for row in cursor.fetchall()}:
        cursor.execute("ALTER TABLE abc_templates ADD COLUMN content TEXT NOT NULL DEFAULT '';")

    # 14. Agentic Workflow Uploader Settings (singleton row; target console URL)
    # "Singleton row" means this table is only ever meant to hold exactly
    # one row (enforced by CHECK (id = 1)) -- it's used like a small
    # settings/configuration record rather than a normal list of many rows.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS abc_uploader_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            service_url TEXT NOT NULL DEFAULT ''
        );
    """)

    # 15. Workflow Builder: saved visual pipeline definitions (Drawflow graph export +
    # per-node parameter values, both as JSON blobs so the DB stays schema-agnostic
    # as node types evolve).
    # Storing the whole workflow as one big JSON blob (rather than many
    # separate columns/tables) means new kinds of workflow nodes can be
    # added later without needing to change this table's structure.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            graph_json TEXT NOT NULL DEFAULT '{}',
            created TEXT NOT NULL DEFAULT (datetime('now')),
            updated TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    # 16. Documents Metadata Table (scraped from DOCX/PDF reports dropped in
    # 01_inbox/documents). trades and extracted_fields are stored as JSON
    # text -- trades because one document can list several trades (avoids a
    # join table; query with SQLite's built-in json_each(trades)), and
    # extracted_fields because each report's exact field set varies file to
    # file, same schema-agnostic-JSON approach already used above for
    # abc_templates.content and workflow_definitions.graph_json.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            doc_date TEXT,
            trades TEXT NOT NULL DEFAULT '[]',
            source_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            extracted_fields TEXT NOT NULL DEFAULT '{}',
            created TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    # 17. Workflow Checkpoints Table ("Awaiting Review" queue). One row per
    # human-review-checkpoint function that has paused a workflow run,
    # waiting on a person to open file_path, make edits, and mark it
    # reviewed. Populated by 13_Functions/human_review_checkpoint.py, read
    # by the Review Queue page.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_label TEXT NOT NULL,
            node_title TEXT NOT NULL,
            instructions TEXT,
            file_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created TEXT NOT NULL DEFAULT (datetime('now')),
            reviewed TEXT
        );
    """)

    # Blazing-Fast Performance Query Indexes
    # These don't add new data -- they tell SQLite to pre-build a fast
    # lookup shortcut for these specific columns, since the tables above
    # are frequently searched/filtered by them. Without an index, the
    # database would have to scan every single row to answer those
    # searches; with one, it can jump straight to matching rows.
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_trade ON training_classes(trade, period);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedules_lookup ON class_schedules(school_year, trade);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_lookup ON apprentice_exam_attempts(ait_id, exam_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores_lookup ON apprentice_section_scores(class_code, ait_id, exam_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_trade ON contacts(trade);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON workflow_checkpoints(status);")

    # Insert seeds if baseline table is empty to keep testing instant.
    # The next few blocks each check "is this table completely empty?" and,
    # only if so, insert a small handful of realistic example rows -- this
    # means a brand-new copy of the database isn't blank/empty when you
    # first open the app, and the UI has something real to display right
    # away without you needing to manually create test data first.
    cursor.execute("SELECT COUNT(*) FROM historical_registrations;")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            ("Electrical", 2023, 120),
            ("Electrical", 2024, 132),
            ("Electrical", 2025, 145),
            ("Carpentry", 2023, 90),
            ("Carpentry", 2024, 98),
            ("Carpentry", 2025, 105),
            ("Plumbing", 2023, 80),
            ("Plumbing", 2024, 85),
            ("Plumbing", 2025, 92)
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO historical_registrations (trade_id, period, count)
            VALUES (?, ?, ?);
        """, seed_data)

    # Insert initial mock contacts if the contacts table is empty
    cursor.execute("SELECT COUNT(*) FROM contacts;")
    if cursor.fetchone()[0] == 0:
        contact_seeds = [
            ("Marcus Vance", "marcus.vance@industrycorp.local", "555-0192", "Vance Gas & Mechanical", "Gasfitter Class A", 14, "2026-07-12", "Lead consultant for complex thermal setups.", "Active"),
            ("Elena Rostova", "e.rostova@hvacsystems.local", "555-0143", "Apex Air Solutions", "Refrigeration Airconditioning Mechanic (RACM)", 8, "2026-06-28", "Assisting with commercial refrigeration lab parameters.", "Active"),
            ("David Kim", "dkim@urbanlandscapes.local", "555-0188", "Metro Horticulture Group", "Landscape Horticulturist", 22, "2026-07-14", "Regular master class program examiner.", "Active"),
            ("Sarah Jenkins", "s.jenkins@interstateutility.local", "555-0211", "Interstate Gas Corp", "Gas Utility Operator", 4, "2026-05-19", "Liaison for field safety operations pipeline.", "Active")
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO contacts (name, email, phone, company, trade, total_engagements, last_contact_date, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, contact_seeds)

    # Seed the default Process tag registry if empty
    cursor.execute("SELECT COUNT(*) FROM process_tags;")
    if cursor.fetchone()[0] == 0:
        tag_seeds = [
            ("System", "oklch(0.70 0.14 220)"),
            ("Database", "oklch(0.72 0.17 150)"),
            ("Contacts", "oklch(0.80 0.15 85)"),
            ("AEP", "oklch(0.68 0.18 300)")
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO process_tags (name, color) VALUES (?, ?);
        """, tag_seeds)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Running this file directly (`python database.py`) sets up/repairs the
    # database schema on demand, without needing to start the whole Cortex
    # web server first.
    initialize_database()
    print("[INIT] Database schemas successfully established with baseline data seeds.")
