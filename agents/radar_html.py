"""Convert reports/premium-scan-2026-09-07.md into a styled artifact page."""
import re

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "reports", "premium-scan-latest.md")
OUT = os.path.join(ROOT, "docs", "index.html")

md = open(SRC).read()
sections = re.findall(r"## (.+?)\n((?:\|.*\n)+)", md)

def rows_html(block):
    lines = [l for l in block.strip().split("\n") if l.startswith("|")][2:]
    rows = [[x.strip() for x in l.strip("|").split("|")] for l in lines]
    # 12 cols: rank,ticker,price,strike,expiry,premium,yield,ann,iv,oi,spread,flags
    # 11 cols (older reports): same without expiry
    parsed = []
    for c in rows:
        if len(c) >= 12:
            parsed.append((c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8], c[9], c[10], c[11]))
        else:
            parsed.append((c[0], c[1], c[2], c[3], "", c[4], c[5], c[6], c[7], c[8], c[9], c[10]))
    top = max((float(p[6].rstrip("%")) for p in parsed), default=1) or 1
    out = []
    for rank, tk, price, strike, expiry, prem, yld_s, ann, iv, oi, spread, flags_s in parsed:
        bar = min(float(yld_s.rstrip("%")) / top, 1) * 100
        flag = ""
        if "⚠️E" in flags_s:
            date = flags_s.replace("⚠️E", "").replace("⚠️", "").strip()
            flag = f'<span class="pill">earnings {date[5:]}</span>'
        out.append(f"""<tr>
<td class="rank">{rank}</td>
<td class="tk">{tk}</td>
<td class="num">{price}</td>
<td class="num">{strike}</td>
<td class="num dim">{expiry[5:] if expiry else ""}</td>
<td class="num prem">{prem}</td>
<td class="num yld"><span class="bar" style="--w:{bar:.0f}%"></span>{yld_s}</td>
<td class="num dim">{ann}</td>
<td class="num dim">{iv}</td>
<td class="num dim">{oi}</td>
<td class="num dim">{spread}</td>
<td>{flag}</td>
</tr>""")
    return "\n".join(out), len(lines)

tables = []
for title, block in sections:
    body, n = rows_html(block)
    label = title.split("—")[0].strip()
    if n == 0:
        empty = ("No individual-stock options expire in this window — single names list "
                 "Wednesday and Friday expirations only (the biggest tickers), or just Fridays.")
        tables.append(f"""<section>
<div class="sec-head"><h2>{label}</h2></div>
<p class="note">{empty}</p>
</section>""")
        continue
    note = "" if n == 20 else f'<span class="count">{n} names pass the filters at this expiry</span>'
    tables.append(f"""<section>
<div class="sec-head"><h2>{label}</h2>{note}</div>
<div class="scroll"><table>
<thead><tr><th></th><th class="l">Ticker</th><th>Price</th><th>Strike</th><th>Expiry</th><th>Premium</th><th>Yield</th><th>Annualized</th><th>IV</th><th>OI</th><th>Spread</th><th class="l"></th></tr></thead>
<tbody>{body}</tbody>
</table></div>
</section>""")

html = """<title>Premium Radar</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Instrument+Sans:wght@400;500;600&family=Spline+Sans+Mono:wght@400;500&display=swap">
<style>
:root{
  --paper:#F6F8F6; --ink:#17201C; --muted:#5B6663; --line:#DDE3DF;
  --accent:#0E7A5E; --accent-soft:#0E7A5E22; --warn-bg:#F5E5CB; --warn-ink:#7A4E0B;
  --card:#FFFFFF; --head:#EDF1EE;
}
:root:not([data-theme="light"]){}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#111614; --ink:#E6ECE9; --muted:#93A09B; --line:#28312D;
    --accent:#43C298; --accent-soft:#43C29826; --warn-bg:#3A2E14; --warn-ink:#E8B96A;
    --card:#171D1A; --head:#1C2320;
  }
}
:root[data-theme="dark"]{
  --paper:#111614; --ink:#E6ECE9; --muted:#93A09B; --line:#28312D;
  --accent:#43C298; --accent-soft:#43C29826; --warn-bg:#3A2E14; --warn-ink:#E8B96A;
  --card:#171D1A; --head:#1C2320;
}
body{background:var(--paper);color:var(--ink);font-family:"Instrument Sans",system-ui,sans-serif;
  margin:0;padding:2.5rem 1.25rem 4rem;line-height:1.5;}
.wrap{max-width:960px;margin:0 auto;}
h1{font-family:"Bricolage Grotesque","Instrument Sans",sans-serif;font-weight:700;
  font-size:clamp(1.9rem,4.5vw,2.6rem);margin:0 0 .3rem;letter-spacing:-.01em;text-wrap:balance;}
.sub{color:var(--muted);max-width:62ch;margin:0 0 1.1rem;}
.meta{display:flex;flex-wrap:wrap;gap:.5rem;margin:0 0 2.4rem;}
.chip{font-size:.78rem;font-weight:500;border:1px solid var(--line);border-radius:999px;
  padding:.22rem .7rem;color:var(--muted);background:var(--card);}
.chip b{color:var(--ink);font-weight:600;}
section{margin:0 0 2.6rem;}
.sec-head{display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap;margin:0 0 .6rem;}
h2{font-family:"Bricolage Grotesque","Instrument Sans",sans-serif;font-weight:700;
  font-size:1.25rem;margin:0;}
.count{color:var(--muted);font-size:.82rem;}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card);}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:.87rem;}
th{font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
  font-weight:600;text-align:right;padding:.55rem .65rem;background:var(--head);white-space:nowrap;}
th.l{text-align:left;}
td{padding:.42rem .65rem;border-top:1px solid var(--line);white-space:nowrap;}
.num{text-align:right;font-family:"Spline Sans Mono",monospace;font-variant-numeric:tabular-nums;font-size:.83rem;}
.rank{color:var(--muted);text-align:right;font-family:"Spline Sans Mono",monospace;font-size:.78rem;width:1.6rem;}
.tk{font-family:"Spline Sans Mono",monospace;font-weight:500;}
.prem{font-weight:500;}
.dim{color:var(--muted);}
.yld{font-weight:600;color:var(--accent);position:relative;}
.bar{display:inline-block;vertical-align:middle;height:.55rem;width:56px;border-radius:3px;
  background:linear-gradient(to right,var(--accent) var(--w),var(--accent-soft) var(--w));
  margin-right:.55rem;}
.pill{font-size:.72rem;font-weight:600;background:var(--warn-bg);color:var(--warn-ink);
  border-radius:999px;padding:.14rem .55rem;}
.note{border-left:3px solid var(--accent);padding:.15rem 0 .15rem 1rem;color:var(--muted);
  max-width:68ch;margin:0 0 2.2rem;font-size:.92rem;}
.note b{color:var(--ink);}
footer{color:var(--muted);font-size:.8rem;border-top:1px solid var(--line);padding-top:1rem;max-width:68ch;}
</style>
<div class="wrap">
<h1>Premium Radar</h1>
<p class="sub">The 20 richest covered-call premiums expiring today and at the next three Friday
expirations, out to two weeks — individual stocks only, no ETFs or indexes — scanned across
350 of the highest-implied-volatility liquid US names.</p>
<div class="meta">
<span class="chip">Updated <b>__STAMP__</b>__REFRESH__</span>
<span class="chip">Source <b>Unusual Whales</b></span>
<span class="chip">Mcap ≥ <b>$500M</b></span>
<span class="chip">Price ≥ <b>$5</b></span>
<span class="chip">Volume ≥ <b>3M shares</b> (30d avg or today)</span>
<span class="chip">Contract OI ≥ <b>100</b></span>
<span class="chip">Spread ≤ <b>10%</b> of mid</span>
</div>
<p class="note"><b>How to read it:</b> Premium is the mid of the nearest at-or-above-the-money
call — pure extrinsic, the income a covered call keeps. Yield is premium ÷ stock price for
that period; Annualized scales it to a year. An <span class="pill">earnings</span> pill means
the company reports before that expiry, so the premium is inflated by gap risk.
Names that repeat across every bucket are usually correlated (crypto miners and
bitcoin-treasury stocks move together) — several covered calls on them is one bet, not many.</p>
__TABLES__
<footer>Generated by agents/premium_scan.py in the option-trading-agent-team project.
Quotes are mids as of the scan time in the header; live fills will differ. Analysis, not trading advice.</footer>
</div>
"""
import datetime, sys
from zoneinfo import ZoneInfo
stamp = datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%a %b %-d, %-I:%M %p ET")
# The 30-min claim is only honest while a session is actually looping refresh_radar.sh.
refresh = " · auto-refreshes every 30 min" if "--looping" in sys.argv else ""
html = (html.replace("__STAMP__", stamp).replace("__REFRESH__", refresh)
        .replace("__TABLES__", "\n".join(tables)))
open(OUT, "w").write(html)
print("wrote", OUT)
