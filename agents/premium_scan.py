"""Top-20 highest ATM call premium (as % of stock) for ~1/2/3/4 week expiries.

Universe: UW screener, top-IV common stocks, marketcap >= $500M, price >= $5,
total option OI >= 2000. Premium = mid of ATM call NBBO at Friday 2026-09-04 close.
"""
import sys, json, datetime, re
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shared.uw_client import UWClient

from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
TODAY = datetime.datetime.now(ET).date()
_days_to_fri = (4 - TODAY.weekday()) % 7 or 7
_fridays = [TODAY + datetime.timedelta(days=_days_to_fri + 7 * k) for k in range(3)]
TARGETS = [TODAY.isoformat()] + [d.isoformat() for d in _fridays]
LABELS = ([f"Same day / nearest ({TODAY.strftime('%b')} {TODAY.day} onward)"]
          + [f"{name} ({d.strftime('%b')} {d.day})"
             for name, d in zip(("This Friday", "Next Friday", "Two weeks out"), _fridays)])
N_CANDIDATES = 350
MIN_CONTRACT_OI = 100
MAX_SPREAD_PCT = 10.0
FAST = "--fast" in sys.argv  # reprice yesterday's discovered names with live quotes only
UNIVERSE_PATH = os.path.join(ROOT, "signals", "radar_universe.json")
# Git does not track empty dirs, so these may not exist on a fresh checkout.
os.makedirs(os.path.join(ROOT, "signals"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)

_c = UWClient(pause=0.2)


class Retrying:
    """Wrap UWClient.get with retries on transient network errors (SSL/timeout)."""
    def get(self, path, **params):
        import urllib.error
        for attempt in range(4):
            try:
                return _c.get(path, **params)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                if attempt == 3:
                    raise
                time_mod.sleep(5 * (attempt + 1))


import time as time_mod
c = Retrying()


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def strike_from_symbol(sym):
    m = re.search(r"[CP](\d{8})$", sym)
    return int(m.group(1)) / 1000 if m else None


# --- 1. universe: cursor down the IV ladder (screener caps at 250 rows/call) ---
# Fast mode skips discovery entirely: reprice the names the last full scan found active.
if FAST:
    data = json.load(open(UNIVERSE_PATH))
    cands = [e for e in data["tickers"] if e.get("active")]
    print(f"fast mode: repricing {len(cands)} active names from full scan of {data['date']}", flush=True)
cands = cands if FAST else []
seen_tk, max_vol = set(), None
IV_FLOOR = 0.45  # stop once IV drops below 45% — premium too thin to rank
while not FAST and len(cands) < N_CANDIDATES:
    batch = c.get("screener/stocks", order="volatility", order_direction="desc",
                  limit=250, min_marketcap=500000000, max_volatility=max_vol)["data"]
    fresh = [r for r in batch if r["ticker"] not in seen_tk]
    if not fresh:
        break
    seen_tk.update(r["ticker"] for r in fresh)
    for r in fresh:
        if r.get("issue_type") not in ("Common Stock", "ADR"):
            continue
        close, oi = f(r.get("close")), r.get("total_open_interest") or 0
        if not close or close < 5 or oi < 10000:  # need a real options market
            continue
        # >= 3M shares/day: 30-day average, or today's tape for names just picking up volume
        avg_vol = max(f(r.get("avg30_volume")) or 0, f(r.get("stock_volume")) or 0)
        if avg_vol < 3_000_000:
            continue
        cands.append({
            "ticker": r["ticker"], "close": close, "iv": f(r.get("volatility")),
            "mcap": f(r.get("marketcap")), "earnings": r.get("next_earnings_date"),
            "sector": r.get("sector"), "avg_vol": avg_vol,
        })
        if len(cands) >= N_CANDIDATES:
            break
    vols = [f(r.get("volatility")) for r in fresh if f(r.get("volatility"))]
    if not vols or min(vols) < IV_FLOOR:
        break
    max_vol = min(vols)
    print(f"cursor: {len(cands)} candidates, IV down to {max_vol:.2f}", flush=True)
print(f"universe: {len(cands)} candidates", flush=True)

# Mega-caps with midweek (Mon/Wed) expirations: always include, even below the IV floor,
# so the "Same day / nearest" bucket has names on non-Fridays.
MEGA_MIDWEEK = ["TSLA", "NVDA", "AAPL", "META", "AMZN", "AMD", "MSFT", "GOOGL",
                "AVGO", "NFLX", "PLTR", "MU", "INTC"]
if not FAST:
    have = {s["ticker"] for s in cands}
    for tkr in MEGA_MIDWEEK:
        if tkr in have:
            continue
        try:
            st = c.get(f"stock/{tkr}/stock-state")["data"]
            close = f(st.get("close")) or f(st.get("prev_close"))
            iv_rows = c.get(f"stock/{tkr}/iv-rank")["data"]
            iv = (f(iv_rows[-1].get("volatility")) if iv_rows else None) or 0
            info = c.get(f"stock/{tkr}/info")["data"]
        except (SystemExit, KeyError, IndexError):
            continue
        avg_vol = max(f(info.get("avg30_volume")) or 0, f(st.get("total_volume")) or 0)
        if not close or avg_vol < 3_000_000:
            continue
        cands.append({"ticker": tkr, "close": close, "iv": iv,
                      "mcap": f(info.get("marketcap")), "earnings": info.get("next_earnings_date"),
                      "sector": info.get("sector"), "mega": True, "avg_vol": avg_vol})
    print(f"universe with mega-cap midweek names: {len(cands)}", flush=True)

# --- 2. price ATM calls per target expiry ---
results = {t: [] for t in TARGETS}
for i, s in enumerate(cands):
    tkr, spot = s["ticker"], s["close"]
    if FAST:  # live tape price so stock and option quotes are from the same moment
        try:
            live = f(c.get(f"stock/{tkr}/stock-state")["data"].get("close"))
            if live:
                spot = s["close"] = live
        except (SystemExit, KeyError):
            pass  # fall back to stored close
    if s.get("expiries"):
        expiries = s["expiries"]
    else:
        try:
            exp_rows = c.get(f"stock/{tkr}/expiry-breakdown")["data"]
        except SystemExit as e:
            print(f"{tkr}: expiry-breakdown failed ({e})", flush=True)
            continue
        expiries = s["expiries"] = sorted({e for e in (r.get("expires") for r in exp_rows) if e})
    chain_cache = {}
    s["active"] = False
    for t in TARGETS:
        td = datetime.date.fromisoformat(t)
        if t == TARGETS[0]:  # same-day or nearest listing strictly before this Friday's bucket
            upcoming = [e for e in expiries if t <= e < TARGETS[1]]
            if not upcoming:
                continue
            best = min(upcoming)
        else:
            best = min(expiries, key=lambda e: abs((datetime.date.fromisoformat(e) - td).days), default=None)
            if not best or abs((datetime.date.fromisoformat(best) - td).days) > 4:
                continue
        if best not in chain_cache:
            try:
                chain_cache[best] = c.get(f"stock/{tkr}/option-contracts",
                                          expiry=best, option_type="call", limit=500)["data"]
            except SystemExit as e:
                print(f"{tkr} {best}: chain failed ({e})", flush=True)
                chain_cache[best] = []
        chain = chain_cache[best]
        usable = []
        for k in chain:
            strike = strike_from_symbol(k.get("option_symbol", ""))
            bid, ask = f(k.get("nbbo_bid")), f(k.get("nbbo_ask"))
            if not (strike and bid and ask and ask > 0 and bid > 0.05):
                continue
            oi_k = k.get("open_interest") or 0
            mid_k = (bid + ask) / 2
            if oi_k < MIN_CONTRACT_OI or (ask - bid) / mid_k * 100 > MAX_SPREAD_PCT:
                continue
            usable.append((strike, bid, ask, oi_k))
        # covered-call convention: nearest strike AT or ABOVE spot -> premium is pure extrinsic
        otm = [u for u in usable if u[0] >= spot]
        if not otm:
            continue
        strike, bid, ask, oi = min(otm, key=lambda u: u[0] - spot)
        if (strike - spot) / spot > 0.10:  # no strike near the money
            continue
        mid = (bid + ask) / 2
        dte = (datetime.date.fromisoformat(best) - TODAY).days
        yld = mid / spot * 100
        s["active"] = True
        results[t].append({
            **{k: v for k, v in s.items() if k != "expiries"},
            "expiry": best, "dte": dte, "strike": strike, "mid": mid,
            "bid": bid, "ask": ask, "oi": oi, "yield": yld,
            "ann": yld * 365 / max(dte, 1),
            "spread_pct": (ask - bid) / mid * 100 if mid else 0,
        })
    print(f"[{i+1}/{len(cands)}] {tkr} done", flush=True)

if not FAST:  # persist the discovered universe so intraday runs can reprice it quickly
    json.dump({"date": TODAY.isoformat(), "tickers": cands}, open(UNIVERSE_PATH, "w"))
    print(f"universe saved: {UNIVERSE_PATH} ({sum(1 for s in cands if s.get('active'))} active)", flush=True)

# --- 3. report ---
_mode = "live tape prices + live option quotes" if FAST else "screener closes + live option quotes (daily discovery pass)"
out = [f"# Highest ATM call premium — scan of {TODAY} ({_mode})", ""]
out.append(f"Universe: top-IV US common stocks/ADRs, mcap ≥ $500M, price ≥ $5, volume ≥ 3M shares/day (30d avg or today), total option OI ≥ 10000 ({len(cands)} names scanned).")
out.append("Premium = mid of the nearest at/above-the-money call (pure extrinsic). Yield = premium / stock price.")
out.append("Hard filters: contract OI >= 100, bid/ask spread <= 10% of mid. ⚠️E = earnings before expiry.")
out.append("")
for t, label in zip(TARGETS, LABELS):
    rows = sorted(results[t], key=lambda r: -r["yield"])[:20]
    out.append(f"## {label}")
    out.append("| # | Ticker | Price | Strike | Expiry | Premium (mid) | Yield | Annualized | IV | OI | Spread | Flags |")
    out.append("|--:|--------|------:|-------:|--------|--------------:|------:|-----------:|---:|---:|-------:|-------|")
    for n, r in enumerate(rows, 1):
        flags = []
        if r["earnings"] and TODAY.isoformat() <= r["earnings"] <= r["expiry"]:
            flags.append("⚠️E " + r["earnings"])
        out.append(f"| {n} | {r['ticker']} | ${r['close']:.2f} | ${r['strike']:g} | {r['expiry']} | ${r['mid']:.2f} "
                   f"| {r['yield']:.1f}% | {r['ann']:.0f}% | {r['iv']*100:.0f}% | {r['oi']} "
                   f"| {r['spread_pct']:.0f}% | {' '.join(flags)} |")
    out.append("")

report = "\n".join(out)
path = os.path.join(ROOT, "reports", "premium-scan-latest.md")
open(path, "w").write(report)
print("saved:", path, flush=True)
print(report)
