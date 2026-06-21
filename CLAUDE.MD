# CLAUDE.md — Paper Trading Bot — Project Rules

## Prime directive
This is a paper trading bot: real live market prices, fake money. Every
other instruction in this file is secondary to this one — **never fake a
fill, a price, a fee, or a P&L number.**

Concrete rules that follow from that:
- A close always uses the live price fetched at the moment of close. A
  losing trade closes as a recorded loss — no rounding, no averaging away,
  no "skip this one," no silent retry that swaps in a friendlier price.
- Every trade carries a fee, and where relevant slippage and funding,
  computed from a real, currently-published fee schedule — not an estimate,
  not a guess, not a number from training data that might be stale.
- If a number, formula, or API behavior can't be verified against an
  official primary source, say so explicitly: *"Could not verify — check
  here: <link>."* Never fill the gap with a plausible-sounding guess.
- Every external fact used in code (a fee %, a rate limit, a formula) needs
  a source — a URL plus the date it was checked — recorded in `SOURCES.md`
  in this repo. Not just mentioned once in chat and forgotten.

## Architecture rules
- **Broker-agnostic by design.** Every broker — paper or real — implements
  one common interface: `get_quote`, `place_order`, `cancel_order`,
  `get_positions`, `get_balance`, `get_trade_history`. New brokers are added
  by writing one adapter against that interface. The core engine,
  strategies, and dashboard never know which broker they're talking to.
- The **paper broker adapter is the default and only adapter active**,
  always — until the live-trading gate below is manually opened by a human.

## Live-trading safety gate
This section exists so the bot can never accidentally place a real order.
- A real order can only fire if **all** of these are true:
  1. A human has manually set a separate, explicit config flag scoped to
     that one broker (not a global "go live" switch).
  2. That broker's adapter uses its own API key with the minimum possible
     permissions (no withdrawal rights, position-size caps at the broker
     level if available).
  3. Phase 8's honest paper-trading verdict has been delivered and read.
- **No code path — including the adaptive learning layer — may set, flip,
  or widen that live-trading flag itself.** Only a human, by hand, in a
  config file outside the bot's own write access.

## News & data integrity
- Every headline or news item the bot uses or displays must come from a
  real, freshly fetched source with a working link and timestamp. Never
  generate, paraphrase-as-fact, or "remember" a headline.
- If a news source is down or rate-limited, the dashboard shows "no fresh
  news available" — never filler text styled to look like real news.
- Sentiment/news signals are one optional input, not a strategy on their
  own — they go through the same Phase 3 honest-backtest bar as any other
  signal before they're allowed to influence a real (paper) trade.

## Adaptive learning guardrails
The bot is allowed to improve its own strategy parameters over time — but
only inside these limits:
- New parameters are tested in **shadow mode** first: running in parallel
  on paper, never touching the live paper engine, until they pass the same
  honest backtest bar as Phase 3 (real history, real fees, reported
  drawdown — not just a higher raw return).
- Cap how much any parameter can move per tuning cycle (e.g. max ~10% per
  week). No sudden large jumps in risk, size, or aggressiveness.
- Every parameter change is logged: old value, new value, the data window
  used to justify it, and the date. Keep one command that rolls back to the
  last human-approved parameter set.
- If a tuning cycle's "improvement" is statistically indistinguishable from
  noise, say so plainly — don't promote it just because the number went up.

## Trade history & audit
- Every trade, from every broker, gets one **immutable** row: timestamp,
  broker, instrument, side, entry/exit price, fee, slippage, P&L, strategy
  tag, and any news item that influenced the decision.
- Never edit or delete a historical row. A correction is a new row that
  references the row it corrects — the original stays visible.

## Dashboard requirements
- One dashboard. Real data only — no placeholder/demo values anywhere in a
  build meant to actually be looked at.
- Must show: live open positions, full sortable/filterable trade history,
  an equity curve, per-strategy performance (P&L, win rate, max drawdown),
  and a news feed panel with source links.
- Default stack (use this unless told otherwise): Next.js front end,
  FastAPI back end, PostgreSQL for trade history, deployed the usual way
  (Vercel + Railway). Dark, minimal, editorial look — near-black
  background, electric cyan / deep violet accents, JetBrains Mono + Space
  Grotesk.

## How to work in this repo
- Use WebSearch / WebFetch before writing any code that depends on a market
  formula, fee schedule, broker API behavior, or news API. These change
  often — don't rely on memory for anything price-, fee-, or API-related.
- Prefer official sources (exchange/broker docs, official API reference)
  over a blog or forum post. Note the date checked.
- Build in phases (below). Stop at the end of each phase, show real output
  (logs, terminal output, or a dashboard screenshot), and wait for explicit
  go-ahead before starting the next phase. Do not self-advance through
  multiple phases in one run.
- Commit to git at the end of every phase that passes its proof-of-done
  check. Commit message format: `phase-N: <what changed>`.
- Keep a todo list of phase/sub-task progress so it survives context
  compaction.
- Re-read this file at the start of every session. If context gets
  compacted mid-build, the honesty rule, the live-trading gate, and the
  phase gates must not get lost.

## Definition of done (every phase)
A phase is not done because the code looks right. It's done when:
1. It actually runs end-to-end against live data (or real historical data
   for the backtester).
2. There's a test or a log proving the honesty invariant for that phase —
   e.g. recorded close price matches the fetched market price; fee > 0 on
   every simulated trade; a new broker adapter passes the same contract
   test suite as the paper adapter.
3. For adaptive-learning changes: a shadow-mode before/after comparison is
   shown, not just claimed.
4. Anything uncertain is flagged out loud, with a source link or an
   explicit "couldn't verify" note — never glossed over.

## The phases
1. **Setup & architecture** — pick the stack, design the broker-agnostic
   adapter interface, explain the plan in plain English before writing code.
2. **Honest engine** — paper broker adapter, live prices, real fees +
   slippage + funding, truthful close on every trade. Run one full cycle.
3. **Strategies + backtest** — 2–3 simple strategies, backtested on real
   history, keep only what honestly passes (say clearly if none do).
4. **Sizing + reset loop** — fractional Kelly position sizing, reset-and-
   learn behavior after a big loss.
5. **Multi-broker connectivity** — add 1–2 real broker adapters behind the
   same interface (e.g. one crypto exchange, one stock broker). Orders still
   route through paper mode only — see the live-trading gate.
6. **News & market-data integration** — real news/sentiment feed, every
   item cited and timestamped, treated as an optional signal validated like
   any strategy.
7. **Adaptive learning + full dashboard** — shadow-mode self-tuning with the
   guardrails above; complete dashboard (positions, history, equity curve,
   strategy breakdown, news panel).
8. **Paper run + honest verdict** — run it for real on paper, report
   performance honestly, lay out exactly what would need to change and what
   the real risk is before any live-trading flag is ever touched.

## Never do this
- Never hardcode a "demo" price, fill, or news item to make a screenshot
  look good.
- Never suppress an exception around a price/fee/broker call by silently
  substituting a default value.
- Never claim a strategy has edge based on a backtest without reporting
  sample size, max drawdown, and the most obvious way it could be overfit.
- Never let the adaptive learning layer touch the live-trading flag, widen
  a risk cap, or skip the shadow-mode bar "because it's clearly better."
- Never show fabricated or paraphrased-as-real news.