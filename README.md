# Honest Paper Trading Bot

A paper trading bot whose only rule is honesty: **real live prices, fake money, real fees / funding / slippage, never a faked fill or a rounded-away loss.**

## Project rules

The full project rules are in the CLAUDE.md attached to the user's message. The short version:

- **Prime directive:** never fake a fill, a price, a fee, or a P&L number.
- **Broker-agnostic by design.** Every broker — paper or real — implements one common interface. The core engine, strategies, and dashboard never know which broker they're talking to.
- **Live-trading safety gate.** A real order can only fire if a human has manually set a separate, explicit per-broker config flag. No code path — including the adaptive learning layer — may set, flip, or widen that flag.
- **News & data integrity.** Every headline the bot shows comes from a real, freshly fetched source with a working link and timestamp. Never a paraphrased-as-real headline.
- **Build in 8 phases.** Stop at the end of every phase, show real output, and wait for explicit go-ahead before starting the next phase. Commit message format: `phase-N: <what changed>`.

## Status

**Phase 1 — Setup & architecture** (this commit)

Done:
- Formal broker-agnostic interface (`tradingbot/brokers/base.py`) with the six methods CLAUDE.md requires: `get_quote`, `place_order`, `cancel_order`, `get_positions`, `get_balance`, `get_trade_history`.
- Paper adapter (`tradingbot/brokers/paper_adapter.py`) implements all six methods, fills at the live touch of the book, and writes one immutable history row per fill.
- Per-broker live-trading gate (`tradingbot/brokers/live_gate.py`) — replaces the old global `LIVE_TRADING` switch. Default OFF. Each broker flips independently.
- Contract test suite (`tests/test_broker_contract.py`) — 5/5 passing, including a live round-trip BUY of BTCUSDT at the real Binance bookTicker ask ($64,178.01 at the time of the run). Every honesty invariant is asserted.
- Honesty audit (`PHASE1_AUDIT.md`) — flags 8 violations in the existing scaffold (hardcoded fills, hardcoded fees, swallowed exceptions, global live switch). The audit is the patch list for phases 2 and 5. No silent fixes.

Up next (waiting for explicit go-ahead before starting):
- **Phase 2 — honest engine:** wire real fees via `/fapi/v1/commissionRate` (not the hardcoded 0.0005), add funding and slippage models, run a full honest cycle end-to-end.
- **Phase 3 — strategies + backtest:** 2–3 simple strategies, backtested on real Binance historical klines, keep only what honestly passes (and say clearly if none do).
- **Phase 4 — sizing + reset loop:** fractional Kelly position sizing and a reset-and-learn behavior after a big loss.
- **Phase 5 — multi-broker connectivity:** harden the Binance, Alpaca, and IBKR adapters behind the same interface. Orders still route through paper mode only.
- **Phase 6 — news & market-data integration:** real, cited news/sentiment feed, treated as an optional signal validated like any strategy.
- **Phase 7 — adaptive learning + full dashboard:** shadow-mode self-tuning with the guardrails in CLAUDE.md; complete dashboard (positions, history, equity curve, strategy breakdown, news panel).
- **Phase 8 — paper run + honest verdict:** run it for real on paper, report performance honestly, lay out exactly what would need to change and what the real risk is before any live-trading flag is ever touched.

## The honesty contract

Before any fill is recorded, the engine must have::

1. A live price fetched from an official public REST endpoint at a logged timestamp.
2. The venue's official fee schedule for the user's tier (default VIP0), recorded as a number not a guess — and ideally fetched live from the exchange, not hardcoded.
3. For perpetuals: a real funding rate from the venue's funding endpoint, applied at the venue's real funding cadence.
4. A slippage model that comes from the order book, not a vibes-based bps.
5. A `source_url`, `fetched_at_utc`, and `response_hash` on every price event, so any fill can be re-checked.

If any of these is missing, the bot **does not trade**. It logs `NO_FILL: <reason>` and waits.

## How to run (Phase 1 proof-of-done)

```bash
cd "/Users/soumyachakraborty/Documents/D/Trading Bot"
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/python tests/test_broker_contract.py
```

Expected output: 5/5 tests pass, including a live paper BUY of BTCUSDT with the real Binance ask printed to the terminal.
