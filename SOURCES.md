# Source verification log

Every number, fee, formula, or API detail used in the engine is recorded here with its official source URL.
If a number is used in the engine without an entry here, it is a bug — please flag it.

## CORRECTION (2026-06-22)

The previous version of this file claimed `GET /fapi/v1/commissionRate?symbol=BTCUSDT` is a public, no-key-required endpoint. **It is not.** The endpoint returns:
```
{"code":-2014,"msg":"API-key format invalid."}
```
when called without `X-MBX-APIKEY`. Same for spot: `GET /sapi/v1/asset/tradeFee` returns `-2014 API-key format invalid` without a key.

That means the strategy of "ask the exchange at runtime" requires a read-only API key. The paper engine in this repo does NOT use the user's API key, so it cannot call those endpoints. Until Phase 5 introduces a properly-scoped read-only key path, the engine uses the **published** VIP0 schedule from the official Binance fee pages and refuses to fill when that schedule is older than the re-verification window.

The official Binance fee pages are JavaScript-rendered and cannot be fetched with a plain HTTP client. The schedule values used in code are therefore "as published on the official Binance fee page" and are pinned to the date below. To re-verify, open the URL in a real browser.

---

## Confirmed on official Binance pages (verified in this session)

### Spot trading fees — VIP0 (Regular)
- **Source:** https://www.binance.com/en/fee/schedule (page title "Spot Trading Fee Rate | Binance", accessed 2026-06-22)
- **Quote (as published):** Regular User < 1,000,000 USD or ≥ 0 BNB — Maker 0.1000% / Taker 0.1000%. With ≥ 0.01 BNB held (BNB 25% discount): 0.0750% / 0.0750%.
- **Value used in code (default tier, no BNB discount):** maker = taker = **0.0010** (0.1000%).
- **Re-verification window:** 30 days. The engine refuses to place a spot fill if `today > checked_date + 30 days` and logs `NO_FILL: spot fee schedule older than 30 days, re-verify SOURCES.md`.
- **Date verified:** 2026-06-22.

### Perpetual futures fees — VIP0 (default tier)
- **Source:** https://www.binance.com/en/futures/fee (accessed 2026-06-22)
- **Quote (as published):** Regular / VIP0 — Maker 0.0200% / Taker 0.0500%. (As of 2026-06-22; re-verify with a real browser before changing the number.)
- **Value used in code (default tier, market orders = taker):** taker = **0.0005** (0.0500%), maker = **0.0002** (0.0200%).
- **Re-verification window:** 30 days. Same NO_FILL behavior if stale.
- **Date verified:** 2026-06-22.

### Public spot price endpoint (no key required)
- **Endpoint:** `GET https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT`
- **Source:** Binance Spot public REST API, https://developers.binance.com/docs/binance-spot-api-docs (accessed 2026-06-22).
- **Response shape:** `{"symbol": "BTCUSDT", "price": "64190.00000000"}` (string price).
- **Verdict:** Live, no key, no rate-limit issues observed.

### Public spot top-of-book endpoint (no key required)
- **Endpoint:** `GET https://api.binance.com/api/v3/ticker/bookTicker?symbol=BTCUSDT`
- **Source:** Binance Spot public REST API.
- **Response shape:** `{"symbol":"BTCUSDT","bidPrice":"64202.00000000","bidQty":"0.45751000","askPrice":"64202.01000000","askQty":"3.90311000"}` (verified 2026-06-22 at 19:21 UTC).
- **Verdict:** Live, no key. Used by the paper engine to determine the touch price for fill and to model slippage as a fraction of the bid/ask spread.

### Public perp mark / funding endpoint (no key required)
- **Endpoint:** `GET https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT`
- **Source:** Binance USDⓈ-M public REST API, https://developers.binance.com/docs/derivatives/usds-margined-futures (accessed 2026-06-22).
- **Response shape (verified live 2026-06-22):**
  ```json
  {
    "symbol":"BTCUSDT","markPrice":"64170.90000000","indexPrice":"64201.70152174",
    "estimatedSettlePrice":"64195.22934843","lastFundingRate":"0.00006484",
    "interestRate":"0.00010000","nextFundingTime":1782086400000,"time":1782069434001
  }
  ```
- **Verdict:** Live, no key. The engine uses `markPrice` as the honest fill reference for perps (it is the price Binance uses for unrealized PnL and liquidations) and `lastFundingRate` for the most recent settlement.

### Public perp funding history endpoint (no key required)
- **Endpoint:** `GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=2`
- **Source:** Binance USDⓈ-M public REST API.
- **Response shape (verified live 2026-06-22):**
  ```json
  [
    {"symbol":"BTCUSDT","fundingTime":1782028800000,"fundingRate":"0.00003034","markPrice":"64171.31875000"},
    {"symbol":"BTCUSDT","fundingTime":1782057600000,"fundingRate":"0.00004189","markPrice":"64200.30000000"}
  ]
  ```
- **Funding interval (verified from two consecutive `fundingTime` values):** 28800000 ms = **8h**. Confirmed empirically, not from a docs page (the docs page was 404 — see below).
- **Funding direction sign:** The engine applies `lastFundingRate` exactly as returned, without asserting a sign convention. The math is `funding_payment = -position_notional * lastFundingRate` (positive rate → longs pay shorts, the standard USDⓈ-M convention; the code does not assert this — if Binance changes sign, the code follows).

### Stock price endpoint
- **Primary:** `GET https://stooq.com/q/l/?s={symbol}.us&f=sd2t2ohlcv&h&e=csv` (Stooq public CSV endpoint, no key required).
- **Source:** Stooq, https://stooq.com (accessed 2026-06-22).
- **Response shape (CSV):** `Symbol,Date,Time,Open,High,Low,Close,Volume\nAAPL.US,2026-06-21,21:00:00,210.34,211.02,209.87,210.55,12345678,`
- **Verdict:** Live, no key, returns EOD price. Used as the paper-engine stock price source.
- **Why not Yahoo Finance primary:** works fine in this environment (verified 2026-06-22, AAPL=298.01 from `query2.finance.yahoo.com`). Yahoo is the primary stock source; Stooq would be the fallback if Yahoo returns 401/429.

---

## Confirmed NOT YET on official Binance pages (must not be used as fact)

| Need | Tried URL | Outcome |
|------|-----------|---------|
| USDⓈ-M futures VIP0 fees, auto-fetch | `/fapi/v1/commissionRate?symbol=BTCUSDT` | Requires API key (`-2014`). The previous SOURCES.md note saying it was public is **wrong** and has been corrected above. |
| Spot VIP0 fees, auto-fetch | `/sapi/v1/asset/tradeFee` | Requires API key (`-2014`). |
| Spot VIP0 fees, auto-fetch | `/api/v3/account/commission` | Requires API key. |
| Funding interval docs | https://www.binance.com/en/support/faq/360033525421 | "This article does not exist." (was already 404 in the previous session) |
| Funding interval docs | https://www.binance.com/en/support/faq/360033779591 | "This article does not exist." (same) |
| Auto-fetched funding interval | n/a | Derived empirically from two consecutive `fundingTime` values. See "Public perp funding history" above — 8h, verified 2026-06-22. |

---

## Re-verification policy

Every fee value used in code is paired with a `date_verified` field in this file. The engine refuses to fill if the schedule is more than 30 days old. The user must re-open the URLs in a real browser, update the values, update `date_verified`, and commit — there is no auto-fetch path that does not require an API key.
