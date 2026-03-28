"""
trend_runner.py — Pure logic for Cook-The-Book_v0.1

Phase 2: This module does ONE thing:
  run_trend() — queries SQLite by spread range, computes ATS results

Phase 6: Expanded to support optional filters (team, season, week, game_type).
  The SQL query is now built dynamically — clauses are appended only when
  the caller provides a filter.  Spread range is still REQUIRED.

Phase 1's load_games() is gone.  The CSV is no longer read at runtime.
Data lives in data/ctb.db, populated by import_games.py (run once).

It has ZERO knowledge of Flask, routes, or HTTP.
That separation is intentional (see CLAUDE.md: Architecture Rules).
"""

import sqlite3


# ---------------------------------------------------------------------------
# SQL BUILDING — Phase 6 dynamic WHERE clause construction
# ---------------------------------------------------------------------------
#
# Phase 2 had a hardcoded FILTER_SQL with one WHERE condition.
# Phase 6 builds the query at runtime because filters are optional.
#
# The pattern:
#   1. Start with a list of WHERE clauses and a parallel list of params.
#   2. Spread range is ALWAYS the first clause (it's required).
#   3. For each optional filter the user provides, append a clause + params.
#   4. Join clauses with AND, assemble the full SELECT.
#
# SAFETY: The f-string only builds the SQL skeleton (column names, AND/OR).
# All USER-PROVIDED VALUES go through ? placeholders — never concatenated.
# This prevents SQL injection.

# Columns we SELECT — Phase 6 adds game_type, Phase 6b adds result + total_line.
# result = home_score - away_score (imported from CSV, not computed at runtime).
# total_line = sportsbook over/under line (available for future O/U filtering).
_COLUMNS = (
    "season, week, game_type, home_team, away_team, "
    "home_score, away_score, home_spread, result, total_line"
)


def _build_query(spread_min, spread_max, team=None,
                 season_min=None, season_max=None,
                 week_min=None, week_max=None, game_type=None):
    """
    Build a SELECT query with dynamic WHERE clauses.

    Returns (sql_string, params_list).

    Every filter that is not None adds a clause.  Spread is always present,
    so there's always at least one clause — no need for the WHERE 1=1 trick.
    """
    # --- Required filter: spread range (always present) ---
    clauses = ["home_spread BETWEEN ? AND ?"]
    params = [spread_min, spread_max]

    # --- Optional: team (home OR away) ---
    # We use OR because the user wants ALL games involving this team,
    # regardless of whether they were home or away.
    if team:
        clauses.append("(home_team = ? OR away_team = ?)")
        params.extend([team, team])

    # --- Optional: season range ---
    # Both bounds must be provided.  app.py validates this.
    if season_min is not None and season_max is not None:
        clauses.append("season BETWEEN ? AND ?")
        params.extend([season_min, season_max])

    # --- Optional: week range ---
    if week_min is not None and week_max is not None:
        clauses.append("week BETWEEN ? AND ?")
        params.extend([week_min, week_max])

    # --- Optional: game type (REG, WC, DIV, CON, SB) ---
    if game_type:
        clauses.append("game_type = ?")
        params.append(game_type)

    # --- Assemble ---
    # " AND ".join turns ["A", "B", "C"] into "A AND B AND C".
    where = " AND ".join(clauses)
    sql = f"SELECT {_COLUMNS} FROM games WHERE {where} ORDER BY id"

    return sql, params


# ---------------------------------------------------------------------------
# TREND EVALUATION
# ---------------------------------------------------------------------------


def run_trend(db_path: str, spread_min: float, spread_max: float,
              team: str = None, season_min: int = None, season_max: int = None,
              week_min: int = None, week_max: int = None,
              game_type: str = None) -> dict:
    """
    Query games from SQLite by spread range + optional filters,
    compute ATS stats, return results.

    Parameters:
      db_path     — path to the SQLite database (data/ctb.db)
      spread_min  — lower bound of home_spread (inclusive, signed)  [REQUIRED]
      spread_max  — upper bound of home_spread (inclusive, signed)  [REQUIRED]
      team        — team abbreviation, e.g. "KC"                   [optional]
      season_min  — first season to include, e.g. 2020             [optional]
      season_max  — last season to include, e.g. 2024              [optional]
      week_min    — first week to include, e.g. 1                  [optional]
      week_max    — last week to include, e.g. 18                  [optional]
      game_type   — "REG", "WC", "DIV", "CON", or "SB"            [optional]

    Sign convention (from CLAUDE.md):
      home_spread is negative when home team is favored.
      spread_min and spread_max use the SAME sign.

    Phase 6 — team filter (Option B):
      When a team is selected, results include games where the team is home
      AND games where the team is away.  ATS math flips for away games:
        away perspective:  margin = away_score - home_score
                           ats_value = margin + (-home_spread)
      This gives the bettor the team's ATS record from THEIR perspective.

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

    # --- Step A: Build the dynamic query and execute it ---
    sql, params = _build_query(
        spread_min, spread_max,
        team=team, season_min=season_min, season_max=season_max,
        week_min=week_min, week_max=week_max, game_type=game_type,
    )

    # Phase 3: wrap DB calls in try/except.  If the DB file is missing,
    # corrupted, or locked, we raise a RuntimeError instead of letting
    # a raw sqlite3 exception escape.  This module doesn't know about HTTP —
    # it raises, and the route handler translates that to a JSON 500.
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        matched = conn.execute(sql, params).fetchall()
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Database error: {e}") from e

    # --- Step B: Classify each matched game ---
    # Phase 6: ATS math accounts for perspective.
    # Phase 6b: uses the `result` column (home margin) from the DB
    # instead of computing home_score - away_score in Python.
    #
    # Home perspective (default):
    #   ats_value = result + home_spread
    #
    # Away perspective (team filter, team is away):
    #   away_margin = -result  (flip the home margin)
    #   away_spread = -home_spread
    #   ats_value   = -result + (-home_spread)
    covers = 0
    pushes = 0
    no_covers = 0

    for g in matched:
        if team and g["away_team"] == team:
            # AWAY perspective: flip margin and spread.
            ats_value = -g["result"] + (-g["home_spread"])
        else:
            # HOME perspective (default).
            ats_value = g["result"] + g["home_spread"]

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
