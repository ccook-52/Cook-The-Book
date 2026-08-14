# Cook-The-Book

A multi-filter trend evaluation engine for NFL spread and over/under betting.

**Live at [cookthebook.net](https://cookthebook.net)**

## What it does

Query 25+ seasons of NFL games (1999–present, [nflverse](https://github.com/nflverse) data)
by spread range, team, season, week, game type, and total line. Get back
against-the-spread and over/under hit rates, with the last 10 matching games.

Example: *Home favorites of 3 to 10 points cover 47.8% ATS across 3,370 games.*

## How it works

- **Backend:** Flask + SQLite (no ORM), served by Gunicorn behind Nginx
- **Frontend:** a single HTML page, vanilla JS, no framework
- **Data:** `refresh_data.py` pulls played games from nflverse via `nflreadpy` into SQLite
- **Hosting:** AWS Lightsail (Ubuntu 22.04), HTTPS via Let's Encrypt
- **Deploy:** push to `master` → GitHub Actions SSHes into the server, pulls, restarts

## Rule contract

Spreads are from the home team's perspective: `home_spread` is **negative when the
home team is favored**. A query filters `spread_min <= home_spread <= spread_max` —
no sign flipping, no magnitude conversions.

## Running locally

```
pip install -r requirements.txt
python refresh_data.py   # builds data/ctb.db from nflverse
python app.py            # http://localhost:5000
```

---

Built as a learning-first project — small functions, explicit math, no magic.
