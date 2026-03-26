"""
import_games.py — Standalone script: CSV → SQLite

This script reads nfl_games.csv and populates the 'games' table in data/ctb.db.
It is NOT part of the Flask app.  Run it once to seed the database.

Usage:
    python import_games.py

To re-import (e.g., after updating the CSV):
    1. Delete data/ctb.db
    2. Run this script again

Data flow:
    nfl_games.csv  →  this script  →  data/ctb.db
"""

import csv
import os
import sqlite3


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

# os.path.dirname(__file__) = the folder THIS script lives in.
# We build absolute paths so the script works no matter where you run it from.
SCRIPT_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(SCRIPT_DIR, "data", "nfl_games.csv")
DB_PATH = os.path.join(SCRIPT_DIR, "data", "ctb.db")


# ---------------------------------------------------------------------------
# SCHEMA — matches CLAUDE.md exactly
# ---------------------------------------------------------------------------

# IF NOT EXISTS = safety net.  If you accidentally run this script twice
# without deleting ctb.db, it won't crash — it'll skip table creation
# and try to insert (which may cause duplicate rows, so delete first).
#
# Phase 6: added game_type column ("REG" or "POST") for playoff filtering.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY,
    season      INTEGER NOT NULL,
    week        INTEGER NOT NULL,
    game_type   TEXT    NOT NULL,
    home_team   TEXT    NOT NULL,
    away_team   TEXT    NOT NULL,
    home_score  INTEGER NOT NULL,
    away_score  INTEGER NOT NULL,
    home_spread REAL    NOT NULL
);
"""

# Parameterized INSERT — the 8 '?' placeholders map to the 8 non-id columns.
# We don't provide 'id' because SQLite auto-assigns it (1, 2, 3, ...).
# NEVER use f-strings here — '?' protects against SQL injection.
INSERT_SQL = """
INSERT INTO games (season, week, game_type, home_team, away_team, home_score, away_score, home_spread)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    # --- Step 1: Make sure the CSV exists before we do anything ---
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV not found at {CSV_PATH}")
        return

    # --- Step 2: Connect to the database ---
    # sqlite3.connect() creates the .db file if it doesn't exist yet.
    # After this line, ctb.db exists on disk (but it's empty).
    conn = sqlite3.connect(DB_PATH)
    print(f"Connected to {DB_PATH}")

    # --- Step 3: Create the games table ---
    conn.execute(CREATE_TABLE_SQL)
    print("Table 'games' ready.")

    # --- Step 4: Read CSV and insert each row ---
    # This mirrors Phase 1's load_games() exactly — same columns, same
    # type-casting, same sign flip.  The only difference: instead of
    # appending to a Python list, we INSERT into the database.
    count = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conn.execute(INSERT_SQL, (
                int(row["season"]),
                int(row["week"]),
                # Phase 6: game_type is "REG" or "POST" in nflverse.
                # We store it as-is — no transformation needed.
                row["game_type"].strip(),
                row["home_team"].strip(),
                row["away_team"].strip(),
                int(row["home_score"]),
                int(row["away_score"]),
                # SIGN FLIP — same as Phase 1's load_games().
                # nflverse spread_line is the AWAY team's line.
                # Negate to get home perspective: -4.5 away → +4.5 home.
                -float(row["spread_line"]),
            ))
            count += 1

    # --- Step 5: Commit and close ---
    # commit() writes ALL 7,276 inserts to disk in ONE transaction.
    # If we called commit() inside the loop, that would be 7,276
    # separate disk writes — much slower for no benefit.
    conn.commit()
    conn.close()

    print(f"Done. Inserted {count} games into {DB_PATH}")


# This guard means the code only runs when you execute the script directly
# (python import_games.py), NOT when another file imports it.
if __name__ == "__main__":
    main()
