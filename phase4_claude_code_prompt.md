# Claude Code Prompt: Cook-The-Book v0.1 - Phase 4 Development

## Context

I'm building Cook-The-Book v0.1, a lightweight Flask web app that evaluates NFL spread trends against historical data. I'm a "vibe coder" aspiring to become a junior software engineer - I want to understand HOW and WHY things work, not just copy code.

**My learning style:**
- Explain concepts before showing code
- Show me line-by-line what code does and why
- Ask clarifying questions instead of assuming
- Prioritize understanding over speed

## Current State

- Phase 0 (Core Foundations) — complete
- Phase 1 (Trend Runner) — complete and verified
  - CSV loaded into RAM, Python list filtered, ATS math in `trend_runner.py`
- Phase 2 (Persistence Upgrade) — complete and verified
  - `import_games.py` seeds `data/ctb.db` from CSV
  - `trend_runner.py` queries SQLite via raw `sqlite3`, no ORM
  - `app.py` passes `DB_PATH` to `run_trend()` — no GAMES global
  - Verified: `spread_min=-10, spread_max=-3` → `n=3370, hit_rate=0.478`
- Phase 3 (Production Basics) — complete and verified
  - `FLASK_DEBUG` from env var, debug off by default
  - Input validation: missing fields → 400, bad types → 400, reversed range → 400
  - Error handling: DB errors → RuntimeError → 500 JSON, catch-all error handler
  - Request logging: before/after hooks, `flask.g` for timing, `logging.info` to stdout
  - Health check: `GET /health` → `{"status": "ok"}`
  - WSGI concepts understood (Werkzeug vs Gunicorn vs Nginx)
- I understand the full data flow and the full traffic path conceptually

## Phase 4 Goal

Deploy CTB to an AWS Lightsail instance with Gunicorn + Nginx, backed by GitHub, reachable at `http://cookthebook.net`.

No new features. No code changes to the Flask app itself.

Eight things to do:
1. **GitHub setup** — create repo, push code from local machine
2. **Lightsail setup** — launch instance, attach static IP, configure firewall
3. **Server setup** — SSH in, install Python, `git clone` the repo, install deps, seed DB
4. **Gunicorn** — replace `app.run()` with a production WSGI server
5. **systemd** — keep Gunicorn alive as a background service
6. **Nginx** — reverse proxy port 80 → Gunicorn port 8000 with `server_name cookthebook.net`
7. **DNS** — point GoDaddy A record → Lightsail static IP
8. **Deploy workflow** — `git pull` + `systemctl restart ctb` for future updates

Three things to understand (concepts, not just commands):
- **Lightsail firewall** — what it is, why we open port 80 but not 8000
- **The full traffic path** — Browser → DNS → Nginx → Gunicorn → Flask → SQLite → response
- **DNS resolution** — how `cookthebook.net` turns into an IP address

## Your Role as Mentor

You are acting as a **technical mentor, not a code generator**. For each step:

1. **Explain the concept first** - What are we doing and why?
2. **Show the exact commands** - Explain what each flag and argument does
3. **Ask verification questions** - Make sure I understand before moving forward
4. **Point out tradeoffs** - Why this approach over alternatives?
5. **Connect to fundamentals** - How does this relate to networking, Linux, and the request lifecycle?

## Development Approach

**Build in this order (one checkpoint at a time):**

### Checkpoint 1: GitHub Repository

- Explain what Git vs GitHub is (version control vs hosted backup)
- Walk me through creating a new repo on GitHub (public or private)
- Walk me through `git init`, `git add`, `git commit`, `git remote add`, `git push`
- Explain what `.gitignore` does and why `ctb.db`, `.pem`, and `venv/` are excluded
- Verify the code is visible on GitHub

**Stop here and verify with me before continuing.**

### Checkpoint 2: Launch Lightsail Instance

- Explain what AWS Lightsail is (a simpler, fixed-price VM service vs EC2)
- Walk me through creating a Lightsail instance (Ubuntu 22.04, us-east-1)
- Explain instance plans ($3.50 vs $5 — what you get)
- Walk me through creating and attaching a static IP (and why it matters)
- Walk me through the Lightsail firewall (port 22 from my IP, port 80 from anywhere)
- Explain why we do NOT open port 5000 or 8000

**Stop here and verify with me before continuing.**

### Checkpoint 3: SSH + Server Setup

- Walk me through downloading the Lightsail default key pair (`.pem` file)
- Walk me through SSHing into the instance from Windows (Git Bash or Lightsail browser SSH)
- Explain what's happening when SSH connects (key-based auth)
- Walk me through installing Python, pip, venv on Ubuntu
- Walk me through `git clone` to pull code from GitHub onto the server
- Walk me through setting up venv, installing deps, running `import_games.py`
- Verify `python app.py` starts without errors on the server

**Stop here and verify with me before continuing.**

### Checkpoint 4: Gunicorn

- Recap what Gunicorn does (from Phase 3 WSGI concepts)
- Walk me through `pip install gunicorn` (already in requirements.txt)
- Explain the `gunicorn app:app --bind 127.0.0.1:8000 --workers 2` command
- Explain why we bind to `127.0.0.1` (localhost) not `0.0.0.0` (all interfaces)
- Verify `curl http://127.0.0.1:8000/health` works on the server

**Stop here and verify with me before continuing.**

### Checkpoint 5: systemd Service

- Explain what systemd is and why we need it (process dies when terminal closes)
- Walk me through creating `/etc/systemd/system/ctb.service`
- Explain each line of the service file
- Walk me through `systemctl start`, `enable`, `status`
- Show me `journalctl -u ctb -f` and explain where the log data comes from

**Stop here and verify with me before continuing.**

### Checkpoint 6: Nginx Reverse Proxy

- Explain what Nginx does that Gunicorn doesn't (buffering, port 80, static files)
- Walk me through installing Nginx and verifying the default page
- Walk me through the proxy config (`/etc/nginx/sites-available/ctb`)
- Include `server_name cookthebook.net;` in the config
- Explain each line of the Nginx config
- Walk me through enabling the config, removing the default, testing with `nginx -t`
- Verify `http://<static-ip>/health` works from my laptop browser

**Stop here and verify with me before continuing.**

### Checkpoint 7: DNS (GoDaddy → Lightsail)

- Explain how DNS works (domain name → IP address resolution)
- Explain what an A record is
- Walk me through logging into GoDaddy and editing DNS records for `cookthebook.net`
- Set an A record pointing `@` → Lightsail static IP
- Explain TTL (time to live) and why propagation takes time
- Walk me through verifying: `nslookup cookthebook.net` or `dig cookthebook.net`
- Verify `http://cookthebook.net/health` works from my browser
- Verify `http://cookthebook.net/` loads the UI and returns correct results

**Stop here and verify with me before continuing.**

### Checkpoint 8: Deployment Workflow + Exit Exam

- Walk me through how to deploy code changes (`git push` locally → `git pull` on server → `sudo systemctl restart ctb`)
- Ask me the exit exam questions
- Verify I can draw the full traffic path with ports, layers, and DNS

**Stop here. Phase 4 complete.**

## Key Learning Objectives

At each checkpoint, I should be able to answer:

1. **What is this doing?** (command-by-command understanding)
2. **Why this approach?** (tradeoffs vs. alternatives)
3. **What happens when something goes wrong?** (SSH fails, Gunicorn crashes, DNS not resolving)
4. **How does this connect to what I built in Phases 1-3?** (data flow continuity)

## Rules for This Session

1. **No large command dumps** - Show 3-5 commands max, explain each one
2. **Explain before showing** - Concept first, then implementation
3. **One checkpoint at a time** - Don't jump ahead
4. **Verify before proceeding** - Each checkpoint should be testable
5. **Ask if unclear** - If my question is vague, ask clarifying questions

## Architecture (unchanged from Phase 3)

```
/Cook-The-Book_v0.1/
  app.py            ← unchanged (Flask routes, validation, logging)
  trend_runner.py   ← unchanged (SQLite query, ATS math)
  import_games.py   ← unchanged (CSV → SQLite import)
  requirements.txt  ← MODIFIED: added gunicorn
  data/
    ctb.db          ← regenerated on server via import_games.py
  templates/
    index.html      ← unchanged
```

No new Python files. No code changes to app.py or trend_runner.py.
The only code change is adding `gunicorn` to `requirements.txt`.

## Architecture Rules (from CLAUDE.md — enforced this session)

- `app.run()` is NOT used in production — Gunicorn replaces it
- Gunicorn binds to `127.0.0.1:8000` — NOT `0.0.0.0`
- Nginx is the only thing that listens on port 80
- Lightsail firewall does NOT expose port 5000 or 8000
- systemd manages Gunicorn — no running it in a terminal session
- GitHub is the code transport — `git clone` to deploy, `git pull` to update
- No Docker, no CI/CD, no HTTPS in Phase 4

## Phase 4 Exit Criteria (Don't Move to Phase 5 Until...)

- [ ] GitHub repo created with all code pushed
- [ ] Lightsail instance running (Ubuntu 22.04, us-east-1)
- [ ] Static IP attached to instance
- [ ] Firewall: port 80 open to all, port 22 open to my IP only
- [ ] Code on server via `git clone` with venv and dependencies installed
- [ ] `data/ctb.db` on server with 7,276 rows
- [ ] Gunicorn running via systemd service (`sudo systemctl status ctb` → active)
- [ ] Nginx proxying port 80 → Gunicorn port 8000 with `server_name cookthebook.net`
- [ ] GoDaddy A record pointing `cookthebook.net` → Lightsail static IP
- [ ] `http://cookthebook.net/health` → `{"status": "ok"}` from my browser
- [ ] `http://cookthebook.net/` → CTB UI, `spread_min=-10, spread_max=-3` → `n=3370, hit_rate=0.478`
- [ ] I can deploy updates: `git push` → SSH → `git pull` → `sudo systemctl restart ctb`
- [ ] I can explain every step without looking at notes

## Exit Exam Questions (I Should Be Able to Answer)

1. What is a Lightsail firewall? Why do we open port 80 but NOT port 8000?
2. What does the `.pem` file do? What happens if you lose it?
3. What is the difference between `--bind 127.0.0.1:8000` and `--bind 0.0.0.0:8000`?
4. Why do we use a systemd service instead of just running `gunicorn` in the terminal?
5. What does `proxy_pass http://127.0.0.1:8000` do in the Nginx config?
6. After you `git pull` new code onto the server, why must you `sudo systemctl restart ctb`?
7. Name two things Nginx handles that Gunicorn doesn't.
8. What does `journalctl -u ctb -f` show you? Where does that data come from?
9. Draw the full traffic path from browser to Flask and back. Include DNS, Nginx, Gunicorn, and label each port.
10. What happens if the Lightsail instance reboots? Does Gunicorn come back automatically? Why or why not?
11. What is an A record? How does `cookthebook.net` become an IP address?
12. Why do we use GitHub to get code onto the server instead of just copying files?

---

## Let's Begin

Phase 3 is done. The app is hardened: validation, error handling, logging, no debug tracebacks.

I'm ready to start Checkpoint 1. Please:

1. Explain Git vs GitHub — what problem does version control solve?
2. Walk me through creating a repo and pushing my code
3. Ask me a verification question before we move to Checkpoint 2

Remember: I learn by understanding WHY, not just copying WHAT. Teach me like a mentor, not a code generator.
