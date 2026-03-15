# CLAUDE.md — Cook-The-Book_v0.1

This document defines architectural constraints and expectations for Claude while assisting development.

Claude must follow this strictly unless explicitly told otherwise.

---

# Project Identity

Cook-The-Book_v0.1 is:

A minimal trend evaluation engine for team-level spread betting.

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
→ sqlite3 query via run_trend(db_path, spread_min, spread_max)
→ JSON response
→ Client-side render

The app does not load CSV at startup.
The app does not hold a GAMES list in RAM.
All game queries go through sqlite3. No ORM. No SQLAlchemy.

games table schema (locked):
  id          INTEGER PRIMARY KEY
  season      INTEGER NOT NULL
  week        INTEGER NOT NULL
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

# Current Phase: Phase 4 — Deploy (Lightsail + Nginx + DNS)

Phase 4 deploys CTB to an AWS Lightsail instance. No new features. No code changes to app.py or trend_runner.py.
The goal is: the app is reachable from the internet at http://cookthebook.net.

Rules for this phase:

Deployment stack:
- AWS Lightsail instance: Ubuntu 22.04, us-east-1, $3.50-5/mo plan
- Gunicorn replaces app.run() — app:app --bind 127.0.0.1:8000 --workers 2
- Nginx reverse proxy: port 80 → Gunicorn port 8000
- systemd service keeps Gunicorn alive (auto-start on boot, auto-restart on crash)
- Static IP attached to the Lightsail instance

Code transport:
- GitHub repo as single source of truth
- git clone on server for initial deploy
- git pull + systemctl restart ctb for updates

DNS:
- GoDaddy domain: cookthebook.net
- A record pointed to Lightsail static IP
- Nginx server_name: cookthebook.net

Security:
- Lightsail firewall: port 80 open to all, port 22 open to deployer's IP only
- Port 5000 and 8000 are NOT exposed to the internet
- Gunicorn binds to 127.0.0.1 (localhost only), NOT 0.0.0.0
- .pem key file is never committed to git

Code changes:
- Only change: add gunicorn to requirements.txt
- No changes to app.py, trend_runner.py, import_games.py, or templates
- data/ctb.db is regenerated on server via import_games.py (or copied)

Non-goals (Phase 4):
- No HTTPS/TLS certificates (Phase 5 — Let's Encrypt)
- No Docker or containers
- No CI/CD pipeline
- No auto-scaling or load balancing

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

home_margin = home_score - away_score

ats_value = home_margin + home_spread

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

Cook-The-Book_v0.1 is a spine.

It must remain clean, minimal, and conceptually tight.
