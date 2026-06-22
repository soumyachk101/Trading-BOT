# 🤖 Honest Paper Trading Bot

<div align="center">

![Status](https://img.shields.io/badge/Phase-1%20Complete-3fb950?style=for-the-badge&logo=check&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Honesty](https://img.shields.io/badge/Prime%20Directive-NEVER%20FAKE-ff3860?style=for-the-badge)

### *Real prices · Fake money · Real fees · Real learning*

> A paper-trading bot whose **only rule is honesty** — no faked fills, no rounded-away losses, no paraphrased-as-real news.

[✨ Features](#-features) · [🏗️ Architecture](#%EF%B8%8F-architecture) · [🚀 Quick Start](#-quick-start) · [📊 Workflows](#-workflow-graphs)

</div>

---

## 🎬 What is this?

Imagine you want to learn trading **without losing real money**. That's what a *paper trading bot* does — it trades with **fake money** using **real market prices** so you can practice and validate strategies safely.

But here's the catch: most paper trading bots **cheat**. They:
- ❌ Fake fills at nicer prices than reality
- ❌ Hide fees ("oh that trade was free!")
- ❌ Round away losses to make the chart look pretty
- ❌ Make up "news" to justify trades

**This bot refuses to cheat.** It's built on a single prime directive:

> ### 🔒 *Never fake a fill, a price, a fee, or a P&L number.*

Every trade, every fee, every price comes from a **real, verified source** with a timestamp and a hash you can audit later.

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🎯 Core
- ✅ **Real-time prices** from Binance, Yahoo Finance, Stooq
- ✅ **Real fees** from published exchange schedules (VIP0)
- ✅ **Slippage model** derived from live order book spreads
- ✅ **Perpetual funding** applied at venue's real cadence
- ✅ **Immutable trade ledger** — corrections are new rows, never edits

</td>
<td width="50%">

### 🛡️ Safety
- 🔒 **Per-broker live gate** — no global "go live" switch
- 🔒 **Human-only flag flips** — code can never enable live trading
- 🔒 **NO_FILL protocol** — bot refuses to trade if data is missing
- 🔒 **Sourced fees** — every number cited in `SOURCES.md`
- 🔒 **Audit trail** — every fill has `source_url` + `response_hash`

</td>
</tr>
<tr>
<td width="50%">

### 🧠 Strategies
- 📈 **SMA Crossover** — classic trend follower
- 📊 **RSI Mean Reversion** — buy oversold, sell overbought
- 🚀 **Donchian Breakout** — trade the range break
- 🤖 **ML Predictor** — online logistic regression

</td>
<td width="50%">

### 📊 Dashboard
- 🌐 **Glassmorphic web UI** at `localhost:8000`
- 📉 **Live equity curve** with Chart.js
- 💼 **Open positions** + **trade history**
- 📰 **News feed** with source links
- 🎛️ **Pause/resume** + manual order controls

</td>
</tr>
</table>

---

## 🎬 Animated Demo — How a Trade Flows

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#1a1a2e','lineColor':'#58a6ff'}}}%%
sequenceDiagram
    participant U as 👤 User
    participant S as 🧠 Strategy
    participant E as ⚙️ Engine
    participant P as 💰 Paper Broker
    participant X as 🏦 Binance API

    U->>S: Configure: "Trade BTCUSDT with SMA"
    activate S
    S->>E: next(price, history) → "BUY"
    deactivate S

    activate E
    E->>X: GET /api/v3/ticker/bookTicker
    X-->>E: {bid: 64180, ask: 64202, ...}
    E->>P: place_order(BUY, qty, envelope)
    deactivate E

    activate P
    P->>P: Fill at ask (64202)
    P->>P: Calculate fee (0.1% taker)
    P->>P: Add slippage buffer
    P->>P: Write immutable ledger row
    P-->>E: {fill_price, fee, hash, source}
    deactivate P

    E-->>U: ✅ Trade executed: 0.001 BTC @ 64,202

    Note over U,X: 🕐 5 minutes later...

    S->>E: next(new_price) → "SELL"
    E->>X: GET /api/v3/ticker/price
    X-->>E: {price: 64250}
    E->>P: place_order(SELL, qty, envelope)
    P->>P: Fill at bid (64248)
    P->>P: Record P&L: +0.046 - 0.13 fee
    P-->>U: 📈 Closed for +$0.046 profit
```

---

## 🏗️ Architecture

### System Overview

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#0d1117','lineColor':'#58a6ff','fontSize':'14px'}}}%%
flowchart TB
    subgraph UI["🖥️ DASHBOARD LAYER"]
        DASH[("🌐 Web Dashboard<br/>localhost:8000")]
    end

    subgraph CORE["⚙️ CORE LAYER"]
        ENG[("🧠 HonestEngine<br/>balances, ledger, P&L")]
        SIZE[("📏 SizingManager<br/>Kelly + reset loop")]
        BACK[("⏪ Backtester<br/>real history")]
    end

    subgraph STRAT["🧩 STRATEGY LAYER"]
        S1["📈 SMA Crossover"]
        S2["📊 RSI Mean Reversion"]
        S3["🚀 Donchian Breakout"]
        S4["🤖 ML Predictor"]
    end

    subgraph BROK["🔌 BROKER LAYER (pluggable)"]
        BASE["📜 BaseBroker<br/>(the contract)"]
        PAPER["💰 PaperBroker<br/>(default, always on)"]
        BIN["🟡 Binance"]
        ALP["🦙 Alpaca"]
        IBK["🏛️ IBKR"]
    end

    subgraph DATA["🌍 DATA SOURCES"]
        BINAPI[("🏦 Binance API<br/>(public, no key)")]
        YF[("📈 Yahoo Finance")]
        NEWS[("📰 News APIs")]
    end

    subgraph SAFE["🛡️ SAFETY GATES"]
        GATE["🚦 Live-Trading Gate<br/>(per-broker, human-only)"]
    end

    DASH --> ENG
    ENG --> STRAT
    STRAT --> BASE
    BASE --> PAPER
    BASE -.->|🔒 gated by| GATE
    GATE -.->|if opened| BIN
    GATE -.->|if opened| ALP
    GATE -.->|if opened| IBK
    PAPER --> BINAPI
    PAPER --> YF
    STRAT -.-> NEWS
    ENG --> SIZE
    BACK --> BINAPI

    classDef gate fill:#ff3860,stroke:#fff,stroke-width:2px,color:#fff
    classDef core fill:#58a6ff,stroke:#fff,stroke-width:2px,color:#000
    classDef safe fill:#3fb950,stroke:#fff,stroke-width:2px,color:#000
    class GATE gate
    class ENG,SIZE core
    class PAPER,BIN,ALP,IBK safe
```

</div>

### The Broker-Agnostic Contract

Every broker — paper or real — must implement **exactly 6 methods**:

```mermaid
%%{init: {'theme':'dark'}}%%
flowchart LR
    A[Any Adapter] -->|must implement| B[BaseBroker]
    B --> M1["📊 get_quote()"]
    B --> M2["📝 place_order()"]
    B --> M3["❌ cancel_order()"]
    B --> M4["💼 get_positions()"]
    B --> M5["💵 get_balance()"]
    B --> M6["📜 get_trade_history()"]

    style B fill:#58a6ff,stroke:#fff,stroke-width:3px,color:#000
    style M1 fill:#0d1117,stroke:#58a6ff
    style M2 fill:#0d1117,stroke:#58a6ff
    style M3 fill:#0d1117,stroke:#58a6ff
    style M4 fill:#0d1117,stroke:#58a6ff
    style M5 fill:#0d1117,stroke:#58a6ff
    style M6 fill:#0d1117,stroke:#58a6ff
```

---

## 📊 Workflow Graphs

### 1️⃣ Full Trading Cycle

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#161b22','lineColor':'#3fb950'}}}%%
flowchart TD
    START(["⏰ Timer fires<br/>(every 1m)"]) --> FETCH[("🌐 Fetch live prices<br/>Binance/Yahoo")]
    FETCH --> CHECK{All sources<br/>OK?}
    CHECK -->|❌ No| SKIP["🚫 Log NO_FILL<br/>wait for next tick"]
    CHECK -->|✅ Yes| STRATEGY[("🧠 Strategy evaluates<br/>SMA/RSI/Donchian/ML")]
    STRATEGY --> SIGNAL{Decision?}
    SIGNAL -->|"HOLD"| WAIT["⏸️ Do nothing"]
    SIGNAL -->|"BUY"| SIZING[("📏 Calculate size<br/>Kelly fraction")]
    SIGNAL -->|"SELL"| SIZING
    SIZING --> RISK{Drawdown<br/>safe?}
    RISK -->|❌ No| RESET["🛑 Reset & re-learn<br/>shrink size 50%"]
    RISK -->|✅ Yes| ORDER[("📝 Place paper order<br/>at live touch")]
    ORDER --> FILL[("💰 Simulate fill<br/>+ fee + slippage")]
    FILL --> LEDGER[("📜 Write ledger row<br/>immutable")]
    LEDGER --> DASH[("📊 Update dashboard")]
    DASH -.-> START

    style START fill:#3fb950,stroke:#fff,color:#000
    style SKIP fill:#ff3860,stroke:#fff,color:#fff
    style WAIT fill:#58a6ff,stroke:#fff,color:#000
    style RESET fill:#ffa500,stroke:#fff,color:#000
    style FILL fill:#3fb950,stroke:#fff,color:#000
```

</div>

### 2️⃣ Honesty Check (What Must Be True Before a Fill)

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#161b22','lineColor':'#58a6ff'}}}%%
flowchart TD
    FILL["📝 About to record a fill"] --> Q1{Has live price<br/>from official REST?}
    Q1 -->|❌| HALT1["🚫 NO_FILL: no price"]
    Q1 -->|✅| Q2{Has fetched_at_utc<br/>timestamp?}
    Q2 -->|❌| HALT2["🚫 NO_FILL: no timestamp"]
    Q2 -->|✅| Q3{Has source_url<br/>+ response_hash?}
    Q3 -->|❌| HALT3["🚫 NO_FILL: unauditable"]
    Q3 -->|✅| Q4{Has real fee<br/>from schedule?}
    Q4 -->|❌| HALT4["🚫 NO_FILL: fee unknown"]
    Q4 -->|✅| Q5{Perp?<br/>Has funding rate?}
    Q5 -->|"Yes & ❌"| HALT5["🚫 NO_FILL: no funding"]
    Q5 -->|"No/✅"| Q6{Has slippage<br/>from book?}
    Q6 -->|❌| HALT6["🚫 NO_FILL: no slippage"]
    Q6 -->|✅| OK["✅ Record fill to ledger"]

    style OK fill:#3fb950,stroke:#fff,color:#000
    style HALT1 fill:#ff3860,stroke:#fff,color:#fff
    style HALT2 fill:#ff3860,stroke:#fff,color:#fff
    style HALT3 fill:#ff3860,stroke:#fff,color:#fff
    style HALT4 fill:#ff3860,stroke:#fff,color:#fff
    style HALT5 fill:#ff3860,stroke:#fff,color:#fff
    style HALT6 fill:#ff3860,stroke:#fff,color:#fff
```

</div>

### 3️⃣ Live-Trading Safety Gate

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#161b22','lineColor':'#ff3860'}}}%%
flowchart TD
    ORDER["📝 place_order() called"] --> CHECK1{Broker = paper?}
    CHECK1 -->|"✅ Yes"| ALLOW["✅ Always allowed<br/>(fake money)"]
    CHECK1 -->|"❌ No (real)"| CHECK2{Human set<br/>broker-specific flag?}
    CHECK2 -->|"❌ No"| BLOCK1["🛑 BLOCKED<br/>no human approval"]
    CHECK2 -->|"✅ Yes"| CHECK3{API key has<br/>min permissions?}
    CHECK3 -->|"❌ No"| BLOCK2["🛑 BLOCKED<br/>key too permissive"]
    CHECK3 -->|"✅ Yes"| CHECK4{Phase 8 honest<br/>verdict delivered?}
    CHECK4 -->|"❌ No"| BLOCK3["🛑 BLOCKED<br/>no paper verdict"]
    CHECK4 -->|"✅ Yes"| ALLOW2["✅ Allowed to place<br/>real order"]

    style ALLOW fill:#3fb950,stroke:#fff,color:#000
    style ALLOW2 fill:#3fb950,stroke:#fff,color:#000
    style BLOCK1 fill:#ff3860,stroke:#fff,color:#fff
    style BLOCK2 fill:#ff3860,stroke:#fff,color:#fff
    style BLOCK3 fill:#ff3860,stroke:#fff,color:#fff
```

</div>

### 4️⃣ Strategy Backtest Flow

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#161b22','lineColor':'#ffa500'}}}%%
flowchart LR
    A["🌐 Fetch real klines<br/>Binance /fapi/v1/klines"] --> B["📊 Run strategy<br/>on every candle"]
    B --> C["💰 Simulate fills<br/>at candle close"]
    C --> D["📉 Apply real fees<br/>+ slippage + funding"]
    D --> E["📈 Compute metrics<br/>return, drawdown, Sharpe"]
    E --> F{Sample size<br/>> 30 trades?}
    F -->|❌| G["⚠️ NOT enough data<br/>discard strategy"]
    F -->|✅| H{Max drawdown<br/>< 25%?}
    H -->|❌| I["⚠️ Too risky<br/>discard strategy"]
    H -->|✅| J["✅ Promote to<br/>live paper trading"]

    style A fill:#58a6ff,stroke:#fff,color:#000
    style J fill:#3fb950,stroke:#fff,color:#000
    style G fill:#ff3860,stroke:#fff,color:#fff
    style I fill:#ff3860,stroke:#fff,color:#fff
```

</div>

### 5️⃣ Kelly Sizing + Reset Loop

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#161b22','lineColor':'#3fb950'}}}%%
flowchart TD
    PNL["💵 Trade P&L recorded"] --> TRACK["📊 Update peak balance<br/>+ drawdown %"]
    TRACK --> CHECK{Drawdown<br/>> 30%?}
    CHECK -->|❌ No| KELLY["📏 Compute Kelly size<br/>f* = W - 1-W / R"]
    CHECK -->|✅ Yes| PAUSE["⏸️ Pause trading"]
    PAUSE --> SHRINK["📉 Shrink size to 50%"]
    SHRINK --> RELEARN["🧠 Re-run backtest<br/>on last 100 trades"]
    RELEARN --> VALIDATE{Strategy still<br/>passes honesty bar?}
    VALIDATE -->|❌ No| STOP["🛑 Stop strategy<br/>log to history"]
    VALIDATE -->|✅ Yes| RESUME["▶️ Resume with<br/>smaller size"]
    KELLY --> NEXT["⏭️ Next trade"]
    RESUME --> NEXT
    STOP --> NEXT

    style KELLY fill:#58a6ff,stroke:#fff,color:#000
    style PAUSE fill:#ffa500,stroke:#fff,color:#000
    style RESUME fill:#3fb950,stroke:#fff,color:#000
    style STOP fill:#ff3860,stroke:#fff,color:#fff
```

</div>

### 6️⃣ Build Phases (Roadmap)

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#161b22'}}}%%
gantt
    title 🚧 Build Roadmap (8 Phases)
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Done
    Phase 1 — Setup & architecture     :done, p1, 2026-06-21, 1d

    section Next
    Phase 2 — Honest engine            :active, p2, 2026-06-22, 2d
    Phase 3 — Strategies + backtest     :p3, after p2, 3d
    Phase 4 — Sizing + reset loop       :p4, after p3, 2d
    Phase 5 — Multi-broker              :p5, after p4, 4d
    Phase 6 — News & sentiment          :p6, after p5, 3d
    Phase 7 — Adaptive learning + UI    :p7, after p6, 4d
    Phase 8 — Paper run + verdict       :p8, after p7, 5d
```

</div>

---

## 🧩 The Strategies Explained (Beginner-Friendly)

<div align="center">

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor':'#161b22'}}}%%
flowchart LR
    subgraph SMA["📈 SMA Crossover"]
        SMA1["20-candle avg"] --- SMA2["50-candle avg"]
        SMA2 -->|crosses above| SMA3["BUY 📈"]
        SMA1 -->|crosses below| SMA4["SELL 📉"]
    end

    subgraph RSI["📊 RSI Mean Reversion"]
        RSI1["Price drops"] --> RSI2["RSI &lt; 30<br/>(oversold)"]
        RSI2 --> RSI3["BUY (expect bounce)"]
        RSI4["Price spikes"] --> RSI5["RSI &gt; 70<br/>(overbought)"]
        RSI5 --> RSI6["SELL (expect dip)"]
    end

    subgraph DON["🚀 Donchian Breakout"]
        DON1["Track 20-candle high/low"] --> DON2{"Price breaks<br/>20-high?"}
        DON2 -->|✅ Yes| DON3["BUY momentum"]
        DON2 -->|❌ No| DON4{"Price breaks<br/>20-low?"}
        DON4 -->|✅ Yes| DON5["SELL momentum"]
    end

    style SMA3 fill:#3fb950,color:#000
    style SMA4 fill:#ff3860,color:#fff
    style RSI3 fill:#3fb950,color:#000
    style RSI6 fill:#ff3860,color:#fff
    style DON3 fill:#3fb950,color:#000
    style DON5 fill:#ff3860,color:#fff
```

</div>

| Strategy | When it works | When it fails |
|----------|---------------|---------------|
| **SMA Crossover** | Strong trends | Choppy sideways markets (whipsaw) |
| **RSI Mean Reversion** | Range-bound markets | Strong trends (catches falling knife) |
| **Donchian Breakout** | Volatility expansion | False breakouts in low volume |
| **ML Predictor** | Adaptive, learns from P&L | Needs >100 trades to stabilize |

---

## 📂 Project Structure

```
Trading Bot/
├── 🐍 tradingbot/                  # Main package
│   ├── __init__.py
│   ├── ⚙️ config.py                # Loads .env, paper balance defaults
│   ├── 🧠 engine.py                # HonestEngine — balances, ledger, fills
│   ├── 📏 sizing.py                # Kelly criterion + drawdown reset
│   ├── 💵 prices.py                # Live price/fee/funding fetchers
│   ├── 🏦 real_exchange.py         # Real-API wrapper (Binance/Alpaca)
│   ├── ⏪ backtest.py              # Backtester on real klines
│   ├── 🌐 dashboard.py             # Glassmorphic web UI
│   ├── 💬 sentiment.py             # Lexicon-based news scoring
│   ├── 🔌 brokers/
│   │   ├── 📜 base.py              # The 6-method contract
│   │   ├── 💰 paper_adapter.py     # Default broker (always on)
│   │   ├── 🟡 binance_adapter.py   # Real Binance (gated)
│   │   ├── 🦙 alpaca_adapter.py    # Real Alpaca (gated)
│   │   ├── 🏛️ ibkr_adapter.py      # Real IBKR (gated)
│   │   ├── 🚦 live_gate.py         # Per-broker safety gate
│   │   └── 🎭 mock_adapter.py      # For tests
│   └── 🧩 strategies/
│       ├── 📜 base.py              # BaseStrategy ABC
│       ├── 📈 sma_crossover.py
│       ├── 📊 rsi_mean_reversion.py
│       ├── 🚀 breakout.py
│       └── 🤖 ml_predictor.py
├── 🧪 tests/
│   └── ✅ test_broker_contract.py  # 5/5 contract tests
├── 🛠️ scripts/
│   ├── 1️⃣ step1_smoke.py
│   ├── 2️⃣ step2_cycle.py
│   ├── 3️⃣ step3_backtest.py
│   └── 4️⃣ step4_paper_run.py
├── 📋 CLAUDE.md                    # Project rules (read first!)
├── 📊 PHASE1_AUDIT.md              # Honesty audit findings
├── 📝 PROGRESS.md                  # Phase todo list
├── 📚 SOURCES.md                   # Every fee/endpoint cited
├── 📦 requirements.txt
├── 🚀 run.sh                       # Launch script
└── 📖 README.md                    # ← you are here
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.14+
- ~50MB disk space
- Internet connection (for live price feeds)

### Installation

```bash
# 1. Clone or enter the project
cd "/Users/soumyachakraborty/Documents/D/Trading Bot"

# 2. Create virtual env (if not done)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Run the Test Suite (proves the honesty contract)

```bash
PYTHONPATH=. .venv/bin/python tests/test_broker_contract.py
```

**Expected output:** ✅ 5/5 tests pass, including a **live paper BUY of BTCUSDT** at the real Binance ask price.

### Run a Single Trade Cycle

```bash
.venv/bin/python scripts/step2_cycle.py
```

### Launch the Dashboard

```bash
.venv/bin/python tradingbot/dashboard.py
# Open http://localhost:8000 in your browser
```

---

## 📐 How Position Sizing Works (For Beginners)

> *"How much of my fake money should I bet on this trade?"*

We use the **Fractional Kelly Criterion** — a math formula that says:

```
f* = W − (1 − W) / R

Where:
  f* = fraction of bankroll to bet
  W  = win rate (% of trades that profit)
  R  = payout ratio (avg win ÷ avg loss)
```

**Example:** If you win 60% of trades and your wins are 2× your losses, you should bet **40%** of your bankroll per trade. We use **¼ of that** (10%) to be safer.

```mermaid
%%{init: {'theme':'dark'}}%%
pie title Kelly Example: Win 60%, R = 2
    "Bet 10% per trade" : 10
    "Keep 90% in cash" : 90
```

If the bot loses >30% of its peak balance, it **pauses, shrinks size by 50%, and re-validates the strategy** before resuming.

---

## 🤝 Contributing

This project is in active development across 8 phases. Before contributing:

1. 📖 Read [`CLAUDE.md`](./CLAUDE.md) — the rules are non-negotiable
2. 📋 Check [`PROGRESS.md`](./PROGRESS.md) for current phase
3. 📚 Check [`SOURCES.md`](./SOURCES.md) before adding any new fee/endpoint
4. 🧪 All broker adapters must pass `tests/test_broker_contract.py`
5. 🚫 **Never** hardcode a price, fee, or news item

---

## 📜 License

MIT — see `LICENSE` file. (Add one if missing.)

---

<div align="center">

### 🌟 Star this repo if you believe paper trading should be honest.

**Built with 🛡️ honesty by a bot that refuses to lie to itself.**

</div>
