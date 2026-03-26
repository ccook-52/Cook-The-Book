"""
app.py — Flask routes for Cook-The-Book_v0.1

This file is a THIN layer.  It does three things:
  1. Serve the single-page UI              (GET /)
  2. Accept trend queries and return JSON   (POST /api/run-trend)
  3. Log every request with timing          (before_request / after_request)

No CSV loading at startup.  Data lives in data/ctb.db (SQLite).
All actual logic lives in trend_runner.py.
"""

import logging
import os
import time

from flask import Flask, g, render_template, request, jsonify
from trend_runner import run_trend

# ---------------------------------------------------------------------------
# APP SETUP
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Path to the SQLite database, created by import_games.py.
# Replaces the Phase 1 CSV_PATH + GAMES list.
# No data is loaded into RAM at startup — queries hit the DB on demand.
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "ctb.db")

# Phase 3: configure logging to stdout.
# level=INFO means INFO, WARNING, ERROR, CRITICAL are shown; DEBUG is filtered out.
# format gives us: "2026-03-03 14:32:01,423 INFO POST /api/run-trend 200 14.7ms"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)


# ---------------------------------------------------------------------------
# REQUEST HOOKS — log every request with timing
# ---------------------------------------------------------------------------

@app.before_request
def start_timer():
    """Record when the request started.  g is Flask's per-request storage —
    it lives for exactly one request and is reset automatically."""
    g.start_time = time.time()


@app.after_request
def log_request(response):
    """Log method, path, status code, and elapsed time for every request.
    This runs AFTER the route handler returns a response.
    IMPORTANT: must return the response object — it's a pipeline, not a dead end."""
    elapsed_ms = round((time.time() - g.start_time) * 1000, 2)
    logging.info(f"{request.method} {request.path} {response.status_code} {elapsed_ms}ms")
    return response


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    """Simple liveness check — confirms the Flask process is running.
    Used by load balancers and monitoring tools to decide whether to
    route traffic here.  Phase 3: no DB check, just 'I'm alive.'"""
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    """Serve the single-page UI."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# VALID VALUES — Phase 6 whitelists for optional filters
# ---------------------------------------------------------------------------

# All 32 current NFL team abbreviations (nflverse format).
# Used to validate the team filter — rejects typos before they hit the DB.
# frozenset = an immutable set.  Faster lookup than a list, can't be modified.
VALID_TEAMS = frozenset({
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB",  "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV",  "MIA", "MIN", "NE",  "NO",  "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF",  "TB",  "TEN", "WAS",
    # Historic abbreviations that appear in our 1999-2025 data.
    # Teams relocated or rebranded — nflverse uses these for older seasons.
    "OAK", "SD",  "STL",
})

# nflverse game_type values (5 total, not just REG/POST).
VALID_GAME_TYPES = frozenset({"REG", "WC", "DIV", "CON", "SB"})


@app.route("/api/run-trend", methods=["POST"])
def api_run_trend():
    """
    Accept a JSON body like:
      { "spread_min": -10, "spread_max": -3 }

    Phase 6 — optional filters can be added:
      { "spread_min": -10, "spread_max": -3,
        "team": "KC", "season_min": 2020, "season_max": 2024,
        "week_min": 1, "week_max": 9, "game_type": "REG" }

    All new fields are optional.  If omitted or empty, the filter is skipped.
    The app works exactly as before if only spread_min/spread_max are sent.

    Return JSON:
      { "n": ..., "covers": ..., "pushes": ..., "no_covers": ...,
        "hit_rate": ..., "last_10": [...] }
    """
    # --- Parse JSON body ---
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON", "status": 400}), 400

    # --- REQUIRED: spread range (unchanged from Phase 3) ---
    try:
        spread_min = float(data["spread_min"])
        spread_max = float(data["spread_max"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "spread_min and spread_max are required (numbers)", "status": 400}), 400

    if spread_min > spread_max:
        return jsonify({"error": "spread_min must be <= spread_max", "status": 400}), 400

    # --- OPTIONAL: team ---
    # data.get() returns None if the key is missing — no KeyError.
    # .strip() removes whitespace, .upper() normalizes case ("kc" → "KC").
    # Empty string after strip → treat as "no filter" (None).
    team = None
    raw_team = data.get("team")
    if raw_team and str(raw_team).strip():
        team = str(raw_team).strip().upper()
        if team not in VALID_TEAMS:
            return jsonify({"error": f"Invalid team: {team}", "status": 400}), 400

    # --- OPTIONAL: season range ---
    # Both must be provided together, or neither.  One without the other is a 400.
    season_min = None
    season_max = None
    raw_smin = data.get("season_min")
    raw_smax = data.get("season_max")
    # Check if either is provided (not None and not empty string).
    has_smin = raw_smin is not None and str(raw_smin).strip() != ""
    has_smax = raw_smax is not None and str(raw_smax).strip() != ""

    if has_smin or has_smax:
        # If one is provided, both must be.
        if not (has_smin and has_smax):
            return jsonify({"error": "season_min and season_max must be provided together", "status": 400}), 400
        try:
            season_min = int(raw_smin)
            season_max = int(raw_smax)
        except (ValueError, TypeError):
            return jsonify({"error": "season_min and season_max must be integers", "status": 400}), 400
        if season_min > season_max:
            return jsonify({"error": "season_min must be <= season_max", "status": 400}), 400

    # --- OPTIONAL: week range ---
    # Same pattern as season range: both or neither.
    week_min = None
    week_max = None
    raw_wmin = data.get("week_min")
    raw_wmax = data.get("week_max")
    has_wmin = raw_wmin is not None and str(raw_wmin).strip() != ""
    has_wmax = raw_wmax is not None and str(raw_wmax).strip() != ""

    if has_wmin or has_wmax:
        if not (has_wmin and has_wmax):
            return jsonify({"error": "week_min and week_max must be provided together", "status": 400}), 400
        try:
            week_min = int(raw_wmin)
            week_max = int(raw_wmax)
        except (ValueError, TypeError):
            return jsonify({"error": "week_min and week_max must be integers", "status": 400}), 400
        if week_min > week_max:
            return jsonify({"error": "week_min must be <= week_max", "status": 400}), 400

    # --- OPTIONAL: game type ---
    game_type = None
    raw_gt = data.get("game_type")
    if raw_gt and str(raw_gt).strip():
        game_type = str(raw_gt).strip().upper()
        if game_type not in VALID_GAME_TYPES:
            return jsonify({"error": f"Invalid game_type: {game_type}. Must be REG, WC, DIV, CON, or SB", "status": 400}), 400

    # --- Run the trend logic ---
    # Phase 6: pass all filters (optional ones are None if not provided).
    # run_trend() ignores None filters — the query is identical to Phase 5
    # if no optional filters are sent.
    try:
        result = run_trend(
            DB_PATH, spread_min, spread_max,
            team=team, season_min=season_min, season_max=season_max,
            week_min=week_min, week_max=week_max, game_type=game_type,
        )
    except RuntimeError:
        return jsonify({"error": "internal server error", "status": 500}), 500

    return jsonify(result)


# ---------------------------------------------------------------------------
# ERROR HANDLER — safety net for anything the routes didn't catch
# ---------------------------------------------------------------------------

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """
    Catch-all for unhandled exceptions.  This runs ONLY if an exception
    escapes the route handler (e.g., a bug we didn't anticipate).
    It should NEVER be the primary error path — it's the safety net.

    No traceback is sent to the client.  The error is logged to stdout.
    """
    app.logger.error(f"Unhandled exception: {e}")
    return jsonify({"error": "internal server error", "status": 500}), 500


# ---------------------------------------------------------------------------
# ENTRY POINT (for `python app.py` — flask run also works)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Phase 3: debug mode is controlled by the FLASK_DEBUG environment variable.
    # Default is "0" (off).  Set FLASK_DEBUG=1 in your terminal to enable it.
    # NEVER leave debug=True hardcoded — the interactive debugger lets anyone
    # execute arbitrary Python on your machine if they can trigger an error.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
