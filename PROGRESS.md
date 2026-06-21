# Build progress — phase todo (survives context compaction)

Honesty rules: see CLAUDE.md. Never fake a fill/price/fee/PnL. Live-trading gate
is human-only. Web-verify every fee/API before coding it; log it in SOURCES.md.

## Phases
- [x] **Phase 1 — Setup & architecture.** Broker-agnostic `BaseBroker` (6 methods),
      `PaperBroker` default + only active, per-broker `live_gate`, contract suite
      5/5 green on live Binance data. CLAUDE.md saved to disk. Committed.
- [ ] **Phase 2 — Honest engine.** Real fees (web-verified, in SOURCES.md), slippage
      from the live book, funding for perps, truthful close on every trade. Run one
      full open→close cycle on live data; fee>0 on every fill; recorded close ==
      fetched price. Fix `fetch_perp_commission_rate` fake response_hash (audit #2).
- [ ] **Phase 3 — Strategies + backtest.** 2–3 simple strategies on real Binance
      klines. Report sample size, max drawdown, overfit risk. Keep only honest
      passers; say plainly if none pass.
- [ ] **Phase 4 — Sizing + reset loop.** Fractional Kelly sizing, reset-and-learn
      after a big loss.
- [ ] **Phase 5 — Multi-broker connectivity.** Harden Binance/Alpaca/IBKR adapters
      behind the same interface + same contract suite. Orders paper-routed only.
      Remove global `config.LIVE_TRADING` (audit #6). Cite SEC/TAF/IBKR fees (#1,#3).
- [ ] **Phase 6 — News & market data.** Real cited+timestamped news feed; optional
      signal validated like any strategy. No fabricated/paraphrased headlines.
- [ ] **Phase 7 — Adaptive learning + dashboard.** Shadow-mode self-tuning with
      guardrails (≤10%/wk move, logged, rollback, noise check). Full dashboard
      (positions, history, equity curve, per-strategy stats, news panel).
- [ ] **Phase 8 — Paper run + honest verdict.** Real paper run, honest performance
      report, exact preconditions/risks before any live flag is ever touched.

## Open flags
- `prices.fetch_perp_commission_rate` fabricates response_hash — fix in Phase 2.
- `config.LIVE_TRADING` global still present — remove in Phase 5.
- Machine clock ~1 day behind session date — note for timestamp checks.
- Setup answers assumed as defaults: crypto-only Binance, $10k, brokers
  Binance/Alpaca/IBKR, default Next.js+FastAPI+Postgres stack. Change anytime.
