"""
refresh_data.py — Fetch nflverse data and rebuild ctb.db

Phase 7: Replaces the manual workflow of downloading a CSV from nflverse,
scp'ing it to the server, and running import_games.py.

Now it's one command:
    python refresh_data.py                    # all seasons (1999-present)
    python refresh_data.py --seasons 2024 2025  # specific seasons only

What this script does:
  1. Uses nflreadpy to fetch game data from nflverse's GitHub data releases
  2. Filters to played games only (drops rows with null scores)
  3. Applies the same transformations as import_games.py:
     - Sign flip on spread_line (nflverse uses away perspective, we use home)
     - Type casting (int/float) for all columns
  4. Drops and re-creates the games table in ctb.db
  5. Inserts all rows

The old import_games.py still works as a FALLBACK — if nflverse is down or
nflreadpy breaks, you can manually download the CSV and run import_games.py.

Dependencies: nflreadpy (pip install nflreadpy)
"""

import argparse
import os
import sqlite3

import nflreadpy as nfl


# ---------------------------------------------------------------------------
# PATHS — same as import_games.py
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(SCRIPT_DIR, "data", "ctb.db")


# ---------------------------------------------------------------------------
# SCHEMA — identical to import_games.py (must stay in sync)
# ---------------------------------------------------------------------------

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
    home_spread REAL    NOT NULL,
    result      INTEGER NOT NULL,
    total_line  REAL    NOT NULL
);
"""

INSERT_SQL = """
INSERT INTO games (season, week, game_type, home_team, away_team, home_score, away_score, home_spread, result, total_line)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    # --- Parse command-line arguments ---
    # argparse lets users pass --seasons 2024 2025 from the command line.
    # If no seasons are specified, we fetch ALL available data (1999-present).
    parser = argparse.ArgumentParser(description="Fetch nflverse data and rebuild ctb.db")
    parser.add_argument(
        "--seasons", nargs="*", type=int, default=None,
        help="Seasons to fetch (e.g., --seasons 2024 2025). Omit for all seasons."
    )
    args = parser.parse_args()

    # --- Step 1: Fetch data from nflverse ---
    # nflreadpy returns a Polars DataFrame.  seasons=True means "all available."
    # If the user specified seasons, pass them as a list.
    if args.seasons:
        print(f"Fetching seasons: {args.seasons}")
        games = nfl.load_schedules(seasons=args.seasons)
    else:
        print("Fetching all seasons...")
        games = nfl.load_schedules(seasons=True)

    print(f"Fetched {games.shape[0]} rows from nflverse")

    # --- Step 2: Filter to played games only ---
    # nflverse includes scheduled games that haven't been played yet
    # (home_score is null).  We only want completed games with real scores.
    played = games.filter(games["home_score"].is_not_null())
    dropped = games.shape[0] - played.shape[0]
    if dropped > 0:
        print(f"Dropped {dropped} unplayed games (null scores)")
    print(f"Played games to import: {played.shape[0]}")

    # --- Step 3: Drop old table and create fresh ---
    # We always rebuild from scratch.  For 7,276 rows this takes < 1 second.
    # Why not UPDATE/UPSERT?  Simpler, no edge cases, and our dataset is small.
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted old {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE_SQL)
    print("Created games table")

    # --- Step 4: Insert rows ---
    # We iterate over the Polars DataFrame row by row.
    # .row(i, named=True) returns a dict-like named tuple for each row.
    # Same transformations as import_games.py:
    #   - spread_line is NEGATED (nflverse = away perspective, we = home perspective)
    #   - result and total_line are imported directly from nflverse
    count = 0
    for i in range(played.shape[0]):
        row = played.row(i, named=True)
        conn.execute(INSERT_SQL, (
            int(row["season"]),
            int(row["week"]),
            str(row["game_type"]).strip(),
            str(row["home_team"]).strip(),
            str(row["away_team"]).strip(),
            int(row["home_score"]),
            int(row["away_score"]),
            # SIGN FLIP — same as import_games.py.
            # nflverse spread_line is the AWAY team's line.
            -float(row["spread_line"]),
            int(row["result"]),
            float(row["total_line"]),
        ))
        count += 1

    # --- Step 5: Commit and close ---
    conn.commit()
    conn.close()

    print(f"Done. Inserted {count} games into {DB_PATH}")


if __name__ == "__main__":
    main()
