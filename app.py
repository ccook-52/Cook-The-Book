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


@app.route("/api/run-trend", methods=["POST"])
def api_run_trend():
    """
    Accept a JSON body like:
      { "spread_min": -10, "spread_max": -3 }

    Return JSON:
      { "n": ..., "covers": ..., "pushes": ..., "no_covers": ...,
        "hit_rate": ..., "last_10": [...] }

    Why POST?  We're sending structured parameters.  GET with query strings
    would work too, but POST + JSON is cleaner for future expansion.
    """
    # --- Parse and validate input ---
    # Validation is a GATE: reject bad input before it reaches run_trend().
    # Every error returns HTTP 400 (caller's fault) with a JSON body.
    # silent=True tells Flask not to throw a 400 if the JSON is malformed —
    # instead it returns None, and we handle it cleanly below.
    data = request.get_json(silent=True)

    # Check 1: Is there a JSON body at all? (covers missing body AND malformed JSON)
    if not data:
        return jsonify({"error": "Request body must be JSON", "status": 400}), 400

    # Check 2: Are both fields present and numeric?
    try:
        spread_min = float(data["spread_min"])
        spread_max = float(data["spread_max"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "spread_min and spread_max are required (numbers)", "status": 400}), 400

    # Check 3: Is the range valid?
    if spread_min > spread_max:
        return jsonify({"error": "spread_min must be <= spread_max", "status": 400}), 400

    # --- Run the trend logic (all the real work happens here) ---
    # Phase 3: catch RuntimeError from trend_runner if the DB fails.
    # 400 errors (bad input) are handled above.  This catches 500 errors (our fault).
    try:
        result = run_trend(DB_PATH, spread_min, spread_max)
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
