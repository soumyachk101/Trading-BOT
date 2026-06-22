# Honest Paper Trading Bot

A paper trading bot whose only rule is honesty: **real live prices, fake money, real fees / funding / slippage, never a faked fill or a rounded-away loss.**

## Status

We are at **Step 1** — project scaffold. The bot does not place trades yet.

Steps:
1. **Step 1 — scaffold** *(this step)*: project layout, smoke test against a real public price endpoint.
2. **Step 2 — honest engine**: live crypto + stock prices, fake-money fills, real fees, funding, slippage, truthful losing closes.
3. **Step 3 — strategies + backtest**: 2–3 strategies over real history, keep only the ones that honestly pass.
4. **Step 4 — fractional Kelly sizing, reset-and-learn loop, browser dashboard.**
5. **Step 5 — paper run + honest pre-real-money brief.**

## The honesty contract

Before any fill is recorded, the engine must have::

1. A live price fetched from an official public REST endpoint at a logged timestamp.
2. The venue's official fee schedule for the user's tier (default VIP0), recorded as a number not a guess.
3. For perpetuals: a real funding rate from the venue's funding endpoint, applied at the venue's real funding cadence.
4. A slippage model that comes from the order book, not a vibes-based bps.
5. A `source_url`, `fetched_at_utc`, and `response_hash` on every price event, so any fill can be re-checked.

If any of these is missing, the bot **does not trade**. It logs `NO_FILL: <reason>` and waits.

## How to run (Step 1)

```bash
cd "/Users/soumyachakraborty/Documents/D/Trading Bot"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/step1_smoke.py
```

The smoke test prints a real BTCUSDT price fetched from Binance's public REST API and exits.

## Layout

```
tradingbot/
  config.py        # symbols, paper balance, default fee tier
  prices.py        # live price clients (crypto via Binance, stocks via Yahoo/Stooq)
  engine.py        # honest fill, PnL, fees, funding, slippage (Step 2)
  strategies/      # strategies (Step 3)
  backtest.py      # backtester (Step 3)
  sizing.py        # fractional Kelly (Step 4)
  dashboard.py     # browser dashboard (Step 4)
scripts/
  step1_smoke.py
  step2_cycle.py        # Step 2
  step3_backtest.py     # Step 3
  step4_paper_run.py    # Step 4
```
