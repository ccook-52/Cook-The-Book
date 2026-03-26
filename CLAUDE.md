# CLAUDE.md — Cook-The-Book

This document defines architectural constraints and expectations for Claude while assisting development.

Claude must follow this strictly unless explicitly told otherwise.

---

# Project Identity

Cook-The-Book is:

A multi-filter trend evaluation engine for NFL spread betting.

It is NOT:
- A data ingestion platform
- A live odds service
- A database-heavy system
- A multi-sport analytics suite
- An AI/ML prediction engine

It is intentionally small and foundational.

---

# Established: Data Layer (Phase 2 — Complete)

Data flow (locked, do not regress):

CSV (disk)
→ import_games.py (run once, standalone script)
→ games table in data/ctb.db
→ sqlite3 query via run_trend(db_path, spread_min, spread_max, **optional_filters)
→ JSON response
→ Client-side render

The app does not load CSV at startup.
The app does not hold a GAMES list in RAM.
All game queries go through sqlite3. No ORM. No SQLAlchemy.

games table schema (Phase 6 — expanded):
  id          INTEGER PRIMARY KEY
  season      INTEGER NOT NULL
  week        INTEGER NOT NULL
  game_type   TEXT    NOT NULL   ← REG, WC, DIV, CON, SB
  home_team   TEXT    NOT NULL
  away_team   TEXT    NOT NULL
  home_score  INTEGER NOT NULL
  away_score  INTEGER NOT NULL
  home_spread REAL    NOT NULL   ← negative when home favored

---

# Established: Production Basics (Phase 3 — Complete)

Phase 3 hardened the app without changing behavior (locked, do not regress):

- debug=True is NOT hardcoded — controlled by FLASK_DEBUG env var, off by default
- Input validation in route handler: missing fields → 400, bad types → 400, reversed range → 400
- DB errors in trend_runner.py raise RuntimeError → route catches → JSON 500
- Catch-all @app.errorhandler(Exception) as safety net — no tracebacks sent to clients
- Request logging via before_request/after_request hooks: method, path, status, ms to stdout
- GET /health returns {"status": "ok"} — simple liveness check

---

# Established: Deploy (Phase 4 — Complete)

Phase 4 deployed CTB to AWS Lightsail (locked, do not regress):

- AWS Lightsail: Ubuntu 22.04, us-east-1, static IP 44.218.123.69
- Gunicorn replaces app.run() — app:app --bind 127.0.0.1:8000 --workers 2
- Nginx reverse proxy: port 80 → Gunicorn port 8000, server_name cookthebook.net
- systemd service (ctb.service) keeps Gunicorn alive (auto-start, auto-restart)
- GitHub repo (ccook-52/Cook-The-Book, branch: master) as single source of truth
- Deploy workflow: git push → SSH → git pull → sudo systemctl restart ctb
- GoDaddy A record: cookthebook.net → 44.218.123.69
- Lightsail firewall: port 80 open to all, port 22 open to deployer's IP only
- Port 5000 and 8000 are NOT exposed to the internet
- Gunicorn binds to 127.0.0.1 (localhost only), NOT 0.0.0.0
- .pem key file is never committed to git
- Live at: http://cookthebook.net

---

# Established: HTTPS (Phase 5 — Complete)

Phase 5 added HTTPS via Let's Encrypt + Certbot (locked, do not regress):

- Certbot with Nginx plugin auto-configured SSL directives
- Certificate: /etc/letsencrypt/live/cookthebook.net/fullchain.pem (expires June 13, 2026)
- Auto-renewal via certbot.timer (systemd), dry-run verified
- Nginx: port 443 SSL with TLS termination, port 80 redirects to HTTPS (301)
- Lightsail firewall: port 443 added (open to all)
- Port 80 stays open (needed for HTTP-01 challenge renewal + redirect)
- Gunicorn unchanged: 127.0.0.1:8000, systemd service unchanged
- Zero changes to app.py, trend_runner.py, import_games.py, or templates
- Live at: https://cookthebook.net

---

# Established: Expanded Filters (Phase 6 — Complete)

Phase 6 expanded CTB from a one-trick tool into a multi-filter trend engine:

- games table expanded: added game_type column (REG, WC, DIV, CON, SB)
- import_games.py updated to import game_type from nflverse CSV
- trend_runner.py: dynamic SQL WHERE clause construction with parameterized queries
  - _build_query() assembles clauses/params from optional filters
  - Spread range remains REQUIRED; all new filters are OPTIONAL
  - f-string builds SQL skeleton only; user values go through ? placeholders
- Four optional filters: team, season range, week range, game type
  - Team filter (Option B): shows all games involving team (home + away)
  - ATS math flips for away perspective: margin = away_score - home_score, spread negated
- app.py validation: VALID_TEAMS (35 teams), VALID_GAME_TYPES (5 types)
  - Optional fields: absent/empty → None (skip), present → validate → pass through
  - Range filters require both bounds (season_min + season_max, week_min + week_max)
- index.html: progressive disclosure (Advanced Filters toggle)
  - Team dropdown, season range, week range, game type dropdown
  - ATS display in last_10 accounts for team perspective flip
- Regression verified: spread -10 to -3 with no filters → n=3370, hit_rate=0.478
- GitHub repo renamed: ccook-52/Cook-The-Book (was Cook-The-Book_v0.1)

---

# Rule Contract (Spread Trends Only)

Sign convention:

home_spread is negative when home team is favored.

Rules use the same signed range:

{
  "spread_min": -10,
  "spread_max": -3
}

Filter logic:

spread_min <= home_spread <= spread_max

No sign flipping.
No magnitude conversions.
No ambiguity.

---

# ATS Math Contract

Home perspective (default):
  home_margin = home_score - away_score
  ats_value = home_margin + home_spread

Away perspective (Phase 6 — when team filter selects an away team):
  away_margin = away_score - home_score
  ats_value = away_margin + (-home_spread)

if ats_value > 0 → cover
if ats_value == 0 → push
if ats_value < 0 → no_cover

hit_rate = covers / (covers + no_covers)

Pushes are excluded from hit_rate.

---

# last_10 Definition

Last 10 matching rows in CSV file order.

No date parsing.
No sorting.
CSV order is trusted.

---

# Architecture Rules

Claude must:

- Separate route logic (app.py) from trend evaluation logic (trend_runner.py)
- Avoid inline heavy logic in route handlers
- Avoid adding new dependencies unless requested
- Avoid ORMs (no SQLAlchemy in v0.1)
- Avoid premature optimization
- Avoid async frameworks
- Avoid adding authentication
- Avoid adding user accounts

Keep the system brutally simple.

---

# Coding Style Expectations

- Small functions
- Pure functions where possible
- Clear naming
- Explicit math
- Heavy comments for learning
- No magic abstractions

This is a learning-first build.

---

# Data Ingestion Boundary

Data gathering (nflverse, scripts, ETL) is separate.

The application consumes CSV.
It does not fetch or sync external data.

Ingestion scripts may exist in /scripts but are not imported into the runtime app.

---

# Teaching Mode

Claude should:
- Explain why code exists
- Explain tradeoffs
- Identify hidden assumptions
- Call out scope creep
- Challenge architecture violations

Claude should not:
- Overbuild
- Add future phases into current phase
- Mix ingestion and runtime layers

---

# North Star

Cook-The-Book is a spine.

It must remain clean, minimal, and conceptually tight.
