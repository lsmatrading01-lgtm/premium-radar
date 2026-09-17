# Premium Radar

The 20 richest covered-call premiums expiring today and at the next three Friday
expirations, scanned across ~350 of the highest-implied-volatility liquid US names.

**Live page: https://lsmatrading01-lgtm.github.io/premium-radar/**

Refreshes itself every 30 minutes during US market hours via GitHub Actions — no
laptop required. (It previously ran from a cron on a Mac and had to be republished
by hand by a live session, so it went stale whenever the machine slept.)

## Schedule

**09:35 ET → 15:55 ET, every 30 min, Mon–Fri**, driven by an external cron service that
calls the `workflow_dispatch` API (see *Setup*). A market-hours guard in Eastern time
does the real gating, so the trigger can fire on any minute without being silently
dropped, and anything outside the session exits in ~8 seconds.

**Why not GitHub's own cron?** Because it does not run. Measured 2026-09-15..17: of ~23
scheduled firings due in the 13:00–18:00 UTC window — 9am–2pm ET, the first half of the
session — **zero** ran. GitHub sheds scheduled workflows under load on the shared runner
pool, and that window is peak US business hours. Late-day firings landed ~6 of 20. API
dispatches, by contrast, have run within seconds every time. The `schedule:` blocks are
kept only as a free backstop for the hours GitHub does honour.

The cron blocks that remain are still deliberately wide, because GitHub cron is UTC and
ignores DST. **Do not tighten them to "match market hours"** — that breaks at the next
DST flip. Widen the cron, narrow the gate.

A freshness floor in the gate skips any scan landing within 12 minutes of the previous
one, so the backstop cron and the external trigger overlapping costs ~8 seconds rather
than a duplicate repricing pass. Do not raise it to 20: the stamp is written when a scan
finishes, and the 15:55 near-close trigger is only ~18 minutes behind the 15:35 one, so a
20-minute floor would silently eat the closing scan.

Note that the first scan of each day is a full discovery pass, so it takes ~6 minutes to
land; until it does, the page still shows the prior session, honestly stamped.

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
3. **External trigger** — this is what actually runs the radar during the session.

   a. Create a **fine-grained** personal access token (Settings → Developer settings →
      Personal access tokens → Fine-grained): *Repository access* = **only this repo**,
      *Permissions* → **Actions: Read and write**, and nothing else. That is enough to
      dispatch this workflow and nothing more — it cannot push code, read `UW_API_KEY`,
      or touch any other repo. Set an expiry and diarise the renewal; the radar goes
      quiet when the token lapses.

   b. Point any cron service (cron-job.org, a Cloudflare Worker, etc.) at:

      ```
      POST https://api.github.com/repos/lsmatrading01-lgtm/premium-radar/actions/workflows/radar.yml/dispatches
      Accept:        application/vnd.github+json
      Authorization: Bearer <token>
      Body:          {"ref":"main"}
      ```

      Expect **HTTP 204** with an empty body. Two jobs:

      | Job | Crontab | Gives you |
      |---|---|---|
      | every 30 min | `5,35 9-15 * * 1-5` | 09:35 → 15:35 ET |
      | near-close   | `55 15 * * 1-5`     | 15:55 ET |

      **If the service supports a per-job timezone, set it to `America/New_York`
      and use the crontabs above as-is** — DST is then handled for you, which is
      strictly better than DST-proofing by hand. (cron-job.org has this under
      ADVANCED → Time zone; it is what this radar runs on.) If your service is
      UTC-only, shift to `5,35 13-20 * * 1-5` and `55 19,20 * * 1-5` and let the
      ET guard do the gating — widen the cron, narrow the gate, as above.

      The 09:05 firing lands before the open and is skipped; that is expected.

      Verified working 2026-09-17: a success returns 204 and the response carries
      `X-RateLimit-Limit: 5000` and `x-accepted-github-permissions: actions=write`.
      **A limit of 60 means the request arrived anonymous** — the `Authorization`
      header is not reaching GitHub — and GitHub answers that with a misleading
      `404 Not Found` rather than a 401, because it will not confirm a resource
      exists to a caller with no rights to it. Check the header before the URL.

      Do **not** send `{"inputs":{"force":true}}` on the schedule — that bypasses the
      market-hours guard and would restamp the page with post-close and weekend quotes.

## Running it by hand

Actions → *Refresh Premium Radar* → **Run workflow**. Tick `force` to bypass the
market-hours gate and the freshness floor, and `full_scan` to force a full discovery
pass instead of repricing today's universe.

Note the change: a plain dispatch now **respects** the gate, because the external trigger
uses plain dispatches and must not scan outside the session. Only `force` bypasses it.

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
