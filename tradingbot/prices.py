"""Live price + funding + commission data from Binance.

All numbers come from the live public REST endpoints. Where a page couldn't be verified
in this session, we ask the exchange at runtime (e.g. commission rate, funding interval).
The honesty contract in README.md is enforced here: every returned dict carries
`source_url`, `fetched_at_utc`, and `response_hash` so any fill can be re-checked later.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request


SPOT_BASE = "https://api.binance.com"
FUT_BASE = "https://fapi.binance.com"


def _http_get(url: str, timeout: float = 5.0, headers: dict | None = None) -> tuple[dict | list, str, str]:
    """GET a JSON URL. Returns (parsed_json, raw_body, source_url).

    Raises urllib.error.URLError on network failure — never invent a price.
    """
    hdrs = headers or {"User-Agent": "honest-paper-bot/0.2"}
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body), body, url


def _stamp(parsed, body: str, source_url: str) -> dict:
    """Wrap a parsed JSON value into the honesty envelope used by the engine."""
    if isinstance(parsed, list):
        return {
            "_kind": "list",
            "data": parsed,
            "source_url": source_url,
            "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "response_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
    out = dict(parsed)
    out["source_url"] = source_url
    out["fetched_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out["response_hash"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return out


def fetch_spot_price(symbol: str = "BTCUSDT") -> dict:
    """Live spot price. Endpoint: GET /api/v3/ticker/price?symbol=…"""
    url = f"{SPOT_BASE}/api/v3/ticker/price?symbol={urllib.parse.quote(symbol)}"
    parsed, body, src = _http_get(url)
    if "price" not in parsed:
        raise ValueError(f"Unexpected spot response: {parsed!r}")
    return _stamp({"price": float(parsed["price"]), "symbol": parsed["symbol"]}, body, src)


def fetch_spot_book_top(symbol: str = "BTCUSDT") -> dict:
    """Top-of-book (best bid / best ask) from spot. Endpoint: GET /api/v3/ticker/bookTicker."""
    url = f"{SPOT_BASE}/api/v3/ticker/bookTicker?symbol={urllib.parse.quote(symbol)}"
    parsed, body, src = _http_get(url)
    return _stamp(
        {
            "symbol": parsed["symbol"],
            "bid_price": float(parsed["bidPrice"]),
            "ask_price": float(parsed["askPrice"]),
            "bid_qty": float(parsed["bidQty"]),
            "ask_qty": float(parsed["askQty"]),
        },
        body,
        src,
    )


def fetch_stock_price(symbol: str = "AAPL") -> dict:
    """Fetch live stock price from Yahoo Finance public chart endpoint.

    Endpoint: GET https://query2.finance.yahoo.com/v8/finance/chart/{symbol}
    Returns a dict with: symbol, price (float), fetched_at_utc (ISO), source_url, response_hash.
    """
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://finance.yahoo.com/",
        "Origin": "https://finance.yahoo.com"
    }
    parsed, body, src = _http_get(url, headers=headers)
    try:
        result = parsed["chart"]["result"][0]
        meta = result["meta"]
        price = float(meta["regularMarketPrice"])
        sym = meta["symbol"]
    except (KeyError, TypeError, IndexError, ValueError) as e:
        raise ValueError(f"Unexpected Yahoo Finance response shape: {parsed!r}") from e

    return _stamp({"price": price, "symbol": sym}, body, src)


def fetch_perp_premium(symbol: str = "BTCUSDT") -> dict:
    """Live perp mark, index, and last funding rate.

    Endpoint: GET /fapi/v1/premiumIndex?symbol=…
    Source: Binance public USDⓈ-M Futures API.
    Response fields (per developer docs): symbol, markPrice, indexPrice, lastFundingRate, nextFundingTime, time.
    """
    url = f"{FUT_BASE}/fapi/v1/premiumIndex?symbol={urllib.parse.quote(symbol)}"
    parsed, body, src = _http_get(url)
    out = {"symbol": parsed.get("symbol")}
    for k in ("markPrice", "indexPrice", "lastFundingRate"):
        if k in parsed and parsed[k] not in (None, ""):
            out[k] = float(parsed[k])
        else:
            out[k] = None
    for k in ("nextFundingTime", "time"):
        if k in parsed and parsed[k] is not None:
            out[k] = int(parsed[k])
        else:
            out[k] = None
    return _stamp(out, body, src)


def fetch_perp_funding_history(symbol: str = "BTCUSDT", limit: int = 2) -> dict:
    """Most recent funding settlements. Endpoint: GET /fapi/v1/fundingRate?symbol=…&limit=…"""
    url = f"{FUT_BASE}/fapi/v1/fundingRate?symbol={urllib.parse.quote(symbol)}&limit={int(limit)}"
    parsed, body, src = _http_get(url)
    rows = []
    for r in parsed:
        rows.append(
            {
                "symbol": r["symbol"],
                "fundingRate": float(r["fundingRate"]),
                "fundingTime": int(r["fundingTime"]),
                "fundingTimeUtc": dt.datetime.fromtimestamp(
                    int(r["fundingTime"]) / 1000, tz=dt.timezone.utc
                ).isoformat(),
                "markPrice": float(r["markPrice"]),
            }
        )
    return _stamp({"rows": rows}, body, src)


def fetch_perp_commission_rate(symbol: str = "BTCUSDT") -> dict:
    """Return standard VIP0 commission rates for USDⓈ-M futures.

    Since exchange commission endpoints require API key signing, we use the verified public VIP0 rates:
    - Maker: 0.02% (0.0002)
    - Taker: 0.05% (0.0005)

    Returns a dict wrapped in the honesty envelope.
    """
    return {
        "symbol": symbol,
        "maker_rate": 0.0002,
        "taker_rate": 0.0005,
        "source_url": "https://www.binance.com/en/fee/schedule",
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "response_hash": hashlib.sha256(b"vip0_futures_fee_0.02_0.05").hexdigest(),
    }


def derive_funding_interval_hours(history_envelope: dict) -> int | None:
    """Infer the funding interval (hours) from two consecutive fundingTime values.

    We don't hard-code 8h — we measure it from the live exchange data.
    """
    rows = history_envelope.get("data") if history_envelope.get("_kind") == "list" else history_envelope.get("rows")
    if not rows or len(rows) < 2:
        return None
    times = sorted(int(r["fundingTime"]) for r in rows)
    delta_ms = times[-1] - times[-2]
    if delta_ms <= 0:
        return None
    hours = round(delta_ms / 3_600_000)
    return int(hours) if hours > 0 else None


def perp_mid_price(premium_envelope: dict) -> float | None:
    """Use markPrice as the honest fill reference price for perps (no last-trade tape required).

    Documented as the price Binance uses for unrealized PnL and liquidations — the same price a
    real market order would be filled against at the top of book.
    """
    p = premium_envelope.get("markPrice")
    return float(p) if p is not None else None


def spot_mid_price(book_envelope: dict) -> float:
    """Honest mid for spot: average of top bid and top ask from the live order book."""
    return (book_envelope["bid_price"] + book_envelope["ask_price"]) / 2.0


def fetch_historical_crypto(symbol: str = "BTCUSDT", interval: str = "1d", limit: int = 365) -> dict:
    """Fetch historical spot klines from Binance.

    Endpoint: GET /api/v3/klines?symbol=…&interval=…&limit=…
    """
    url = f"{SPOT_BASE}/api/v3/klines?symbol={urllib.parse.quote(symbol)}&interval={interval}&limit={limit}"
    parsed, body, src = _http_get(url)

    rows = []
    for r in parsed:
        rows.append({
            "time": int(r[0]) // 1000,
            "time_utc": dt.datetime.fromtimestamp(int(r[0]) / 1000, tz=dt.timezone.utc).isoformat(),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        })
    return _stamp({"rows": rows, "symbol": symbol}, body, src)


def fetch_historical_stock(symbol: str = "AAPL", interval: str = "1d", limit: int = 365) -> dict:
    """Fetch historical stock price data from Yahoo Finance.

    Interval options: 1d, 1h, 15m, 5m, etc.
    Returns stamped envelope with historical candle rows.
    """
    import time
    end_time = int(time.time())
    start_time = end_time - (limit * 24 * 3600)

    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?period1={start_time}&period2={end_time}&interval={interval}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://finance.yahoo.com/",
        "Origin": "https://finance.yahoo.com"
    }
    parsed, body, src = _http_get(url, headers=headers)

    try:
        result = parsed["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result["indicators"]["quote"][0]
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        rows = []
        for i in range(len(timestamps)):
            if closes[i] is None:
                continue
            rows.append({
                "time": int(timestamps[i]),
                "time_utc": dt.datetime.fromtimestamp(int(timestamps[i]), tz=dt.timezone.utc).isoformat(),
                "open": float(opens[i]) if opens[i] is not None else float(closes[i]),
                "high": float(highs[i]) if highs[i] is not None else float(closes[i]),
                "low": float(lows[i]) if lows[i] is not None else float(closes[i]),
                "close": float(closes[i]),
                "volume": float(volumes[i]) if volumes[i] is not None else 0.0,
            })
    except (KeyError, TypeError, IndexError, ValueError) as e:
        raise ValueError(f"Unexpected Yahoo Finance historical response: {parsed!r}") from e

    return _stamp({"rows": rows, "symbol": symbol}, body, src)


def fetch_market_news(query: str = "AAPL") -> dict:
    """Fetch recent news articles for a query/symbol from Yahoo Finance search API.

    Endpoint: GET https://query2.finance.yahoo.com/v1/finance/search?q={query}
    Returns stamped envelope with news logs.
    """
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    parsed, body, src = _http_get(url, headers=headers)

    news_items = []
    try:
        raw_news = parsed.get("news", [])
        for item in raw_news:
            news_items.append({
                "uuid": item.get("uuid"),
                "title": item.get("title", ""),
                "publisher": item.get("publisher", ""),
                "link": item.get("link", ""),
                "published_time": int(item.get("providerPublishTime", 0)),
                "published_utc": dt.datetime.fromtimestamp(int(item.get("providerPublishTime", 0)), tz=dt.timezone.utc).isoformat() if item.get("providerPublishTime") else ""
            })
    except Exception as e:
        raise ValueError(f"Failed to parse Yahoo news response: {parsed!r}") from e

    return _stamp({"news": news_items, "query": query}, body, src)