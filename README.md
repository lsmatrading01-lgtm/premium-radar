# Premium Radar

The 20 richest covered-call premiums expiring today and at the next three Friday
expirations, scanned across ~350 of the highest-implied-volatility liquid US names.

**Live page: https://lsmatrading01-lgtm.github.io/premium-radar/**

Refreshes itself every 30 minutes during US market hours via GitHub Actions — no
laptop required. (It previously ran from a cron on a Mac and had to be republished
by hand by a live session, so it went stale whenever the machine slept.)

## How it works

| Step | File | What it does |
|------|------|--------------|
| 1 | `agents/premium_scan.py` | Pulls the Unusual Whales screener, prices the nearest at/above-money call at each target expiry, ranks by extrinsic yield |
| 2 | `agents/radar_html.py` | Renders `reports/premium-scan-latest.md` into `docs/index.html` |
| 3 | `.github/workflows/radar.yml` | Runs 1+2 on schedule, commits the result; GitHub Pages serves `docs/` |

Two scan modes, chosen automatically:

- **Full discovery** (~10 min, ~1500 API calls) — first run of each trading day, or
  forced. Rediscovers the universe and writes `signals/radar_universe.json`.
- **Fast repricing** (~2 min) — every run after that, repricing the day's universe
  with live quotes.

Pure standard library. No `pip install`, no `requirements.txt`.

## Setup

1. Repo secret `UW_API_KEY` — your Unusual Whales key. *(Settings → Secrets and
   variables → Actions.)* Never lands in the page or the repo.
2. Pages: Settings → Pages → Source = **Deploy from a branch**, branch `main`, folder `/docs`.

## Running it by hand

Actions → *Refresh Premium Radar* → **Run workflow**. This bypasses the market-hours
gate, and ticking `full_scan` forces a full discovery pass.

Locally:

```bash
export UW_API_KEY=...
python3 agents/premium_scan.py          # add --fast to reprice today's universe
python3 agents/radar_html.py --looping
open docs/index.html
```

## Filters

mcap ≥ $500M · price ≥ $5 · volume ≥ 3M shares/day · contract OI ≥ 100 · spread ≤ 10% of mid.
Individual stocks only — no ETFs or indexes. An `earnings` pill means the company
reports before that expiry, so the premium is inflated by gap risk.

## Known limitations

- **Market holidays aren't detected.** The gate only checks weekday + 9:30–16:00 ET, so
  on a holiday it will run and restamp the page with the prior close. Harmless, but the
  timestamp looks fresher than the data is.
- **Scheduled runs can be late.** GitHub delays cron under load; 30 minutes is a target,
  not a guarantee.
- **Schedules disable after 60 days of repo inactivity.** The bot's own refresh commits
  count as activity, so this only bites if the workflow is already failing.
- Prices are as of the scan time in the header; live fills will differ.

Analysis, not trading advice.
