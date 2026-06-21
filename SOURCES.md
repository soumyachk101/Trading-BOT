# Source verification log

Every number, fee, formula, or API detail used in the engine is recorded here with its official source URL.
If a number is used in the engine without an entry here, it is a bug — please flag it.

## Confirmed on official Binance pages (verified in this session)

### Spot trading fees — VIP0 (Regular)
- **Source:** https://www.binance.com/en/fee/schedule (page title "Spot Trading Fee Rate | Binance")
- **Quote:** "Regular User < 1,000,000 USD or ≥ 0 BNB 0.100% / 0.100%" and "0.07500% / 0.07500%" (BNB 25% discount).
- **Verdict:** Confirmed VIP0 spot taker = 0.100% and maker = 0.100% on official Binance fee page.
- **Date verified:** 2026-06-21.

### Spot trading fees — table headers confirmed
- The fee table on the page has columns: Level / 30-Day Trade Volume (USD) and/or BNB Balance / Maker / Taker (BNB 25% off) / USDC Maker / Taker (BNB 25% off) / Standard.
- "Regular" is the VIP0 row.

### Spot order-book / price endpoint
- **Endpoint:** `GET https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT`
- **Source:** Binance public REST Spot API.
- **Response shape:** `{"symbol": "BTCUSDT", "price": "64190.00000000"}` (string price).
- **Verdict:** Confirmed live; smoke-tested in Step 1.

### Perpetual futures public endpoint (Premium Index / Funding Rate)
- **Endpoint:** `GET https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT`
- **Source:** Binance public REST USDⓈ-M Futures API.
- **Response fields:** `symbol`, `markPrice`, `indexPrice`, `lastFundingRate`, `nextFundingTime`, `time`.
- **Verdict:** Endpoint path confirmed. Response shape is per the developer docs index; we will verify each field on first response and code defensively against missing fields.

### Perpetual futures funding rate history endpoint
- **Endpoint:** `GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1`
- **Response fields:** `symbol`, `fundingRate`, `fundingTime`, `markPrice`.
- **Quote (from developer docs):** "If `startTime` and `endTime` are not sent, the most recent 200 records are returned."
- **Verdict:** Endpoint + response shape confirmed on Binance developer docs.

### BTCUSDT Perpetual contract specs (partial)
- **Source:** https://www.binance.com/en/futures/trading-rules (page truncated in our fetch).
- **Confirmed BTCUSDT perpetual values:** Min Trade Amount 0.001 BTC, Price Precision 0.01, Limit Order Price Cap/Floor 5%/5%, Max Market/Limit Order 120/1000 BTC, Max Number of Open Orders 200, Price Protection Threshold 5%, Liquidation Clearance Fee 1.25%, Min Notional Value 50 USDT, Market Order Price Cap/Floor Ratio 5%.
- **Not yet confirmed from the truncated text:** the funding-interval field for BTCUSDT (we expect 8h but did not see it quoted).

## Confirmed NOT YET on official Binance pages (must not be used as fact)

The following pages returned "This article does not exist.", "No records found.", or were truncated so the data we wanted was not in the returned content:

| Need | Tried URL | Outcome |
|------|-----------|---------|
| USDⓈ-M VIP0 futures taker/maker % | https://www.binance.com/en/fee/futureFee | "No records found." |
| USDⓈ-M VIP0 futures taker/maker % | https://www.binance.com/en/fee/futuresFee | 404 |
| USDⓈ-M VIP0 futures taker/maker % | https://www.binance.com/en/futures/fee-purchase | 404 |
| Funding interval (e.g. 8h) and cadence | https://www.binance.com/en/support/faq/360033525421 | "This article does not exist." |
| Funding interval (e.g. 8h) and cadence | https://www.binance.com/en/support/faq/360033779591 | "This article does not exist." |
| Funding interval (e.g. 8h) and cadence | https://www.binance.com/en/futures/perpetual-funding-fees | page is a chart header, no text |

Because of these gaps I will NOT hard-code:

- USDⓈ-M futures VIP0 maker/taker rate. We will **read it live from the exchange** via the `/fapi/v1/commissionRate` endpoint for the given symbol (public, no key required) — i.e. we don't assume a number, we ask the venue.
- Funding interval. We will derive it from two consecutive `fundingTime` values returned by `/fapi/v1/fundingRate` and use the actual interval the venue reports.
- Funding direction sign. We will apply the live `lastFundingRate` exactly as returned (positive = longs pay shorts per the standard convention used by Binance USDⓈ-M, but we will not assert the direction in code; the math uses the sign as-is).

This is the honest path: where the docs page was missing we ask the exchange, not guess.

## To re-verify in a future session

Before pointing the bot at real money, please re-confirm:
1. Spot VIP0 fees still 0.100% / 0.100% on https://www.binance.com/en/fee/schedule
2. USDⓈ-M fees by fetching `/fapi/v1/commissionRate?symbol=BTCUSDT` and showing the number to yourself.
3. The funding interval for BTCUSDT by inspecting two consecutive `fundingTime` values from `/fapi/v1/fundingRate`.