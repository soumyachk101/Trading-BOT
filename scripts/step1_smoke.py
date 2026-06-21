"""Step 1 smoke test: hit Binance's public REST API and print a real BTCUSDT price.

We deliberately use the *public, unauthenticated* endpoint so this script needs no API key.
The endpoint, parameter names, and response shape are pinned to Binance's official docs.

Endpoint (verified against Binance Spot API docs, public endpoint, no key required):
  GET https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT
Response: {"symbol": "BTCUSDT", "price": "xxxxx.xxxx"}

If the docs URL has moved by the time we re-verify in Step 2, we'll re-fetch and update this docstring.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import urllib.request
import urllib.error

BINANCE_SPOT_BASE = "https://api.binance.com"


def fetch_spot_price(symbol: str = "BTCUSDT", timeout: float = 5.0) -> dict:
    """Fetch a live spot price from Binance's public REST API.

    Returns a dict with: symbol, price (float), fetched_at_utc (ISO), source_url, response_hash.
    Raises urllib.error.URLError on network failure — we never invent a price.
    """
    url = f"{BINANCE_SPOT_BASE}/api/v3/ticker/price?symbol={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "honest-paper-bot/0.1 (step1)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    if "price" not in data:
        raise ValueError(f"Unexpected response shape from {url}: {data!r}")
    return {
        "symbol": data["symbol"],
        "price": float(data["price"]),
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_url": url,
        "response_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    try:
        tick = fetch_spot_price("BTCUSDT")
    except urllib.error.URLError as e:
        print(f"NO_FILL: could not reach Binance public API: {e}", file=sys.stderr)
        return 1
    print("Step 1 smoke test — live spot price fetched from Binance public REST:")
    print(json.dumps(tick, indent=2))
    print("\nHonesty check:")
    print(f"  source: {tick['source_url']}")
    print(f"  fetched_at_utc: {tick['fetched_at_utc']}")
    print(f"  response_hash: {tick['response_hash'][:16]}...")
    print("  This number is real. We did not round or invent it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())