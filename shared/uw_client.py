"""Small Unusual Whales API client shared by all agents. Stdlib only."""
import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://api.unusualwhales.com/api"


def _load_key():
    key = os.environ.get("UW_API_KEY")
    if key:
        return key
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("UW_API_KEY="):
                return line.split("=", 1)[1]
    raise SystemExit("No UW_API_KEY found (env var or .env in project root)")


class UWClient:
    def __init__(self, key=None, pause=0.4):
        self.key = key or _load_key()
        self.pause = pause  # polite gap between calls, seconds

    def get(self, path, **params):
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        url = f"{BASE}/{path}" + (f"?{qs}" if qs else "")
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
        })
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read().decode())
                    time.sleep(self.pause)
                    return data
            except urllib.error.HTTPError as e:
                if e.code == 429:  # rate limited: back off and retry
                    time.sleep(5 * (attempt + 1))
                    continue
                raise SystemExit(f"UW API error {e.code} on {path}: {e.read().decode()[:200]}")
        raise SystemExit(f"UW API rate-limited repeatedly on {path}")

    # --- endpoints agents use ---
    def stock_info(self, ticker):
        return self.get(f"stock/{ticker}/info")["data"]

    def iv_rank(self, ticker):
        """Daily series: close, volatility, iv_rank_1y. Last row = most recent."""
        return self.get(f"stock/{ticker}/iv-rank")["data"]

    def expirations(self, ticker):
        return self.get(f"stock/{ticker}/expiry-breakdown")["data"]

    def call_chain(self, ticker, expiry):
        return self.get(f"stock/{ticker}/option-contracts",
                        expiry=expiry, option_type="call", limit=500)["data"]
