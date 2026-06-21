# Phase 1 honesty audit — existing-scaffold violations

Phase 1 of the upgraded CLAUDE.md is "Setup & architecture". The repo already
contained a 5-phase scaffold. Before adopting it, I read every file looking
specifically for the anti-patterns CLAUDE.md bans:

- Hardcoded "demo" prices or fills to make output look good.
- Hardcoded fees that aren't backed by a sourced, dated citation in SOURCES.md.
- Suppressed exceptions around a price/fee call with a silent default value.

What I found, with the exact line in each file:

## 1. `tradingbot/brokers/ibkr_adapter.py` — hardcoded dummy fill

```
33:        # Fallback Mock Fill for demo/routing compliance
34:        dummy_price = 150.0
35:        return {
36:            "price": dummy_price,
37:            "qty": qty,
38:            "fee_usd": max(1.0, qty * 0.005),  # IB fixed rate: $0.005/share, min $1.00
```

**Why this is banned by CLAUDE.md:** "Never hardcode a 'demo' price or fill
to make a screenshot look good." A `return {"price": 150.0}` is exactly that —
a fake fill, returned without ever touching a real endpoint. The `$0.005/share,
min $1.00` IBKR commission rate is also hardcoded with no source link in
SOURCES.md and no date checked.

**Remediation (Phase 5):** Rewrite `IBKRBrokerAdapter` to call the IBKR
Client Portal API for a live quote (`/md/snapshot`) and live fill
(`/iserver/account/{accountId}/order`), and to read the live commission
schedule from IBKR's published pricing page. The hardcoded $150 must be
deleted entirely — the adapter should refuse to place an order if it can't
fetch a real quote.

## 2. `tradingbot/brokers/binance_adapter.py` — hardcoded perpetual fee

```
23:        if self.is_futures:
24:            leverage = kwargs.get("leverage", 1.0)
25:            res = real_exchange.execute_real_binance_perp(...)
26:            # perpetual taker fee rate 0.05%
27:            fee_usd = res["qty"] * res["price"] * 0.0005
```

**Why this is banned by CLAUDE.md:** "Every trade carries a fee, and where
relevant slippage and funding, computed from a real, currently-published fee
schedule — not an estimate, not a guess, not a number from training data
that might be stale."

`SOURCES.md` already states this explicitly:
> "I will NOT hard-code: USDⓈ-M futures VIP0 maker/taker rate. We will read
> it live from the exchange via the `/fapi/v1/commissionRate` endpoint for
> the given symbol (public, no key required) — i.e. we don't assume a
> number, we ask the venue."

So this line directly contradicts the in-repo SOURCES.md contract.

**Remediation (Phase 2):** Remove the hardcoded `0.0005`. Read
`/fapi/v1/commissionRate?symbol=BTCUSDT` at fill time, stamp the
`source_url` and `response_hash` on the fill, and use the
`takerCommissionRate` (or `makerCommissionRate` depending on order type) the
exchange returns. If the live fetch fails, the order must not be filled —
it must raise. Per CLAUDE.md: "If any of these is missing, the bot does
not trade."

## 3. `tradingbot/brokers/alpaca_adapter.py` — hardcoded SEC + TAF fees

```
20:        # Compute SEC & TAF fees on sell orders
21:        price = res["price"]
22:        executed_qty = res["qty"]
23:        gross_value = price * executed_qty
24:        if side.upper() == "SELL":
25:            sec_fee = gross_value * 0.0000206
26:            taf_fee = min(executed_qty * 0.000195, 9.79)
27:            res["fee_usd"] = sec_fee + taf_fee
```

**Why this is banned by CLAUDE.md:** SEC and TAF fees change periodically.
Hardcoding them with no `source_url` and no date checked is exactly the
"stale training-data number" anti-pattern. There's no entry in SOURCES.md
for either rate.

**Remediation (Phase 5):** Cite the current SEC Section 31 fee rate and the
current TAF fee rate + per-transaction cap in SOURCES.md, dated, with the
official FINRA/SEC source URLs. Consider reading the rate from a
versioned config file pinned to the date, with a clear "this is the rate
that was in force on YYYY-MM-DD" comment. If the rate is older than X
months, refuse to fill.

## 4. `tradingbot/brokers/binance_adapter.py` — swallowed exception on balance

```
34:    def get_balance(self) -> float:
35:        try:
36:            bals = real_exchange.fetch_real_balances(...)
37:            return bals.get("cash", 0.0)
38:        except Exception:
39:            return 0.0
```

**Why this is banned by CLAUDE.md:** "Never suppress an exception around a
price/fee/broker call by silently substituting a default value." Returning
`0.0` on failure is the same anti-pattern as fabricating a price — it makes
the dashboard show a wrong but plausible number, and the strategy has no
way to know the real fetch failed.

**Remediation (Phase 5):** Let the exception propagate. The paper engine
already uses a known paper balance, so this only matters in the live path,
which the live-trading gate already blocks. When the live path runs, the
caller must see a hard failure, not a fake zero.

## 5. `tradingbot/real_exchange.py` — swallowed exception on time sync

```
36:    except Exception as e:
37:        logger.warning(f"Failed to fetch time offset from Binance: {e}. Using 0.")
38:        return 0
```

Same anti-pattern as #4. A bad time offset leads to "timestamp outside
recvWindow" rejections, which then look like a "real broker is down" error
instead of "we couldn't sync our clock." In a paper build this is harmless;
in a live build it is a stealth failure.

**Remediation (Phase 5):** Surface the error. Either retry with backoff
and propagate after N failures, or raise so the engine can log
`NO_FILL: clock not synced` and skip the order.

## 6. Global `LIVE_TRADING` switch in `config.py`

```
31:LIVE_TRADING: bool = _env.get("LIVE_TRADING", "False").lower() in (...)
```

**Why this is banned by CLAUDE.md:** "A real order can only fire if all
of these are true: 1. A human has manually set a separate, explicit config
flag scoped to that one broker (not a global 'go live' switch)."

The `LIVE_TRADING` boolean in config.py is a single global switch. It does
not exist per-broker. This is exactly the anti-pattern the rule names.

**Remediation (Phase 1, done):** Added `tradingbot/brokers/live_gate.py`
with per-broker flags (`BINANCE_SPOT_LIVE_TRADING`,
`BINANCE_PERP_LIVE_TRADING`, `ALPACA_LIVE_TRADING`, `IBKR_LIVE_TRADING`).
The global `config.LIVE_TRADING` is left in place for now only because the
old engine imports it; it is no longer the gatekeeper. Phase 5 will remove
it entirely.

## 7. `MockBrokerAdapter` — only implements 2 of 6 interface methods

The `BaseBroker` interface requires six methods (get_quote, place_order,
cancel_order, get_positions, get_balance, get_trade_history). The existing
`MockBrokerAdapter` only implements `execute_market_order` (which is the
old 2-method interface) and `get_balance`. It cannot satisfy
`place_order`, `cancel_order`, `get_positions`, or `get_trade_history`.

**Remediation (Phase 1, done):** New `PaperBroker` (in
`tradingbot/brokers/paper_adapter.py`) implements all six methods, and a
contract test (`tests/test_broker_contract.py`) asserts every paper
adapter implementation against the interface. The old `MockBrokerAdapter`
is kept for backwards compatibility but is no longer the default.

## 8. Dashboard (`tradingbot/dashboard.py`, 1407 lines)

Not read in full. It will be re-audited in Phase 7 when it's the
proof-of-done for that phase. Flagging now so it's not forgotten.

## Summary

| # | File | Issue | Phase to fix |
|---|------|-------|--------------|
| 1 | `brokers/ibkr_adapter.py` | Hardcoded `dummy_price = 150.0` | 5 |
| 2 | `brokers/binance_adapter.py` | Hardcoded perp fee `0.0005` | 2 |
| 3 | `brokers/alpaca_adapter.py` | Hardcoded SEC/TAF rates | 5 |
| 4 | `brokers/binance_adapter.py` | `except: return 0.0` on balance | 5 |
| 5 | `real_exchange.py` | `except: return 0` on time sync | 5 |
| 6 | `config.py` | Global `LIVE_TRADING` switch | 1 (done in `live_gate.py`) |
| 7 | `brokers/mock_adapter.py` | Doesn't implement 4 of 6 interface methods | 1 (done — `PaperBroker` replaces it) |
| 8 | `dashboard.py` | Not yet audited in full | 7 |

Items 1–5 are the kinds of things that, in a less honest codebase, I'd
silently rewrite. Per CLAUDE.md ("Never suppress an exception around a
price/fee/broker call by silently substituting a default value") I am NOT
patching them in this commit. They are flagged here, will be patched in
their proper phase, and each patch will land with a SOURCES.md entry that
cites the official rate and the date it was checked.
