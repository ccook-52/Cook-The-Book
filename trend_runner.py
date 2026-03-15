"""
trend_runner.py — Pure logic for Cook-The-Book_v0.1

Phase 2: This module does ONE thing:
  run_trend() — queries SQLite by spread range, computes ATS results

Phase 1's load_games() is gone.  The CSV is no longer read at runtime.
Data lives in data/ctb.db, populated by import_games.py (run once).

It has ZERO knowledge of Flask, routes, or HTTP.
That separation is intentional (see CLAUDE.md: Architecture Rules).
"""

import sqlite3


# ---------------------------------------------------------------------------
# SQL QUERY — replaces the Phase 1 list comprehension
# ---------------------------------------------------------------------------

# Phase 1 did this in Python:
#   matched = [g for g in games if spread_min <= g["home_spread"] <= spread_max]
#
# Now SQLite does the filtering for us.  BETWEEN is inclusive on both ends,
# so it's equivalent to:  spread_min <= home_spread <= spread_max
#
# ORDER BY id preserves CSV insertion order — this matters for last_10.
FILTER_SQL = """
SELECT season, week, home_team, away_team, home_score, away_score, home_spread
FROM games
WHERE home_spread BETWEEN ? AND ?
ORDER BY id;
"""


# ---------------------------------------------------------------------------
# TREND EVALUATION
# ---------------------------------------------------------------------------


def run_trend(db_path: str, spread_min: float, spread_max: float) -> dict:
    """
    Query games from SQLite by spread range, compute ATS stats, return results.

    Parameters:
      db_path    — path to the SQLite database (data/ctb.db)
      spread_min — lower bound of home_spread (inclusive, signed)
      spread_max — upper bound of home_spread (inclusive, signed)

    Sign convention (from CLAUDE.md):
      home_spread is negative when home team is favored.
      spread_min and spread_max use the SAME sign.
      Example: spread_min=-10, spread_max=-3 means
               "home team favored by 3 to 10 points."

    Returns dict:
      {
        "n":         int,   — total matching games
        "covers":    int,
        "pushes":    int,
        "no_covers": int,
        "hit_rate":  float, — covers / (covers + no_covers), pushes excluded
        "last_10":   list   — last 10 matches in DB insertion order
      }
    """

    # --- Step A: Query the database for matching games ---
    # Phase 3: wrap DB calls in try/except.  If the DB file is missing,
    # corrupted, or locked, we raise a RuntimeError instead of letting
    # a raw sqlite3 exception escape.  This module doesn't know about HTTP —
    # it raises, and the route handler translates that to a JSON 500.
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        matched = conn.execute(FILTER_SQL, (spread_min, spread_max)).fetchall()
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Database error: {e}") from e

    # --- Step B: Classify each matched game ---
    # This is IDENTICAL to Phase 1.  ATS math doesn't change.
    covers = 0
    pushes = 0
    no_covers = 0

    for g in matched:
        # ATS math (CLAUDE.md contract):
        #   home_margin = home_score - away_score
        #   ats_value   = home_margin + home_spread
        home_margin = g["home_score"] - g["away_score"]
        ats_value = home_margin + g["home_spread"]

        if ats_value > 0:
            covers += 1
        elif ats_value == 0:
            pushes += 1
        else:
            no_covers += 1

    # --- Step C: Compute hit rate (pushes excluded per contract) ---
    denominator = covers + no_covers
    hit_rate = (covers / denominator) if denominator > 0 else 0.0

    # --- Step D: Build last_10 ---
    # Same slice as Phase 1.  ORDER BY id in the SQL ensures rows are in
    # CSV insertion order, so matched[-10:] gives us the last 10.
    # dict(g) converts sqlite3.Row objects to plain dicts for JSON serialization.
    last_10 = [dict(g) for g in matched[-10:]]

    return {
        "n": len(matched),
        "covers": covers,
        "pushes": pushes,
        "no_covers": no_covers,
        "hit_rate": round(hit_rate, 4),  # 4 decimal places for display
        "last_10": last_10,
    }
