"""Step 4 Paper Run: Start the live paper trading bot.

Integrates price feeds, strategy signals, fractional Kelly sizing, safety checks,
and runs the browser-based dashboard on http://localhost:8080/.
"""
from __future__ import annotations

import sys
import time
import datetime as dt
from tradingbot.engine import HonestEngine
from tradingbot import prices
from tradingbot import dashboard
from tradingbot.sizing import SizingManager
from tradingbot.strategies import SMACrossover


def main() -> int:
    print("==================================================")
    print("         HONEST PAPER TRADING LIVE RUN            ")
    print("==================================================\n")

    # 1. Initialize Engine & Sizing Manager
    engine = HonestEngine(initial_balance=10000.0)
    sizing = SizingManager(initial_balance=10000.0, drawdown_limit_pct=0.30, kelly_fraction=0.25)
    
    # Track historical candles for the live strategies
    btc_candles = []
    aapl_candles = []
    
    # Prime strategy histories by downloading the last 50 daily candles
    print("Priming strategy histories with historical data...")
    try:
        btc_hist = prices.fetch_historical_crypto("BTCUSDT", interval="1d", limit=50)
        btc_candles.extend(btc_hist["rows"])
        
        aapl_hist = prices.fetch_historical_stock("AAPL", interval="1d", limit=50)
        aapl_candles.extend(aapl_hist["rows"])
        print(f"  Primed {len(btc_candles)} BTCUSDT candles and {len(aapl_candles)} AAPL candles.")
    except Exception as e:
        print(f"Warning: could not prime histories: {e}. Starting fresh.")

    # 2. Instantiate Live Strategies
    # We will use MLPredictorStrategy for BTC to demonstrate online learning, and SMACrossover for AAPL
    from tradingbot.strategies import MLPredictorStrategy
    btc_strategy = MLPredictorStrategy(lookback=5, train_window=50)
    aapl_strategy = SMACrossover(fast_period=10, slow_period=30)

    # 3. Setup Price Callback for Dashboard
    latest_prices = {"BTCUSDT": 0.0, "AAPL": 0.0}
    
    def get_latest_prices():
        return latest_prices

    # 4. Start Dashboard Server
    dashboard_port = 8080
    dashboard_thread = dashboard.start_dashboard(
        engine,
        get_latest_prices,
        strategies={"BTCUSDT": btc_strategy, "AAPL": aapl_strategy},
        port=dashboard_port
    )

    print("\nBot is now running in PAPER mode.")
    print("Close with Ctrl+C.\n")

    ticks_count = 0
    btc_sentiment = 0.0
    aapl_sentiment = 0.0
    sentiment_model = None
    entry_prices = {}

    # 5. Continuous Loop
    try:
        while True:
            current_time = int(time.time())
            time_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{time_str}] Polling live prices...")

            try:
                # Query news sentiment every 6 ticks (60 seconds) or on the first tick
                if ticks_count % 6 == 0:
                    try:
                        from tradingbot.sentiment import LexiconSentimentModel
                        if sentiment_model is None:
                            sentiment_model = LexiconSentimentModel()
                            
                        btc_news = prices.fetch_market_news("BTC")
                        btc_scores = [sentiment_model.analyze_sentiment(item["title"]) for item in btc_news.get("news", [])]
                        btc_sentiment = sum(btc_scores) / len(btc_scores) if btc_scores else 0.0
                        
                        aapl_news = prices.fetch_market_news("AAPL")
                        aapl_scores = [sentiment_model.analyze_sentiment(item["title"]) for item in aapl_news.get("news", [])]
                        aapl_sentiment = sum(aapl_scores) / len(aapl_scores) if aapl_scores else 0.0
                        
                        print(f"  [SENTIMENT] Polled News. BTC: {btc_sentiment:+.2f} | AAPL: {aapl_sentiment:+.2f}")
                    except Exception as ns_err:
                        print(f"  Warning: failed to fetch news sentiment: {ns_err}")
                
                ticks_count += 1
                btc_strategy.latest_sentiment = btc_sentiment
                aapl_strategy.latest_sentiment = aapl_sentiment

                # A. Fetch Live Crypto Prices
                btc_book = prices.fetch_spot_book_top("BTCUSDT")
                btc_price = prices.spot_mid_price(btc_book)
                latest_prices["BTCUSDT"] = btc_price

                # Append live price candle (simulated as current daily candle update)
                btc_candles.append({
                    "time": current_time,
                    "time_utc": btc_book["fetched_at_utc"],
                    "open": btc_price,
                    "high": btc_price,
                    "low": btc_price,
                    "close": btc_price,
                    "volume": btc_book["ask_qty"]
                })
                # Keep history bounded
                if len(btc_candles) > 100:
                    btc_candles.pop(0)

                # B. Fetch Live Stock Prices
                aapl_price_env = prices.fetch_stock_price("AAPL")
                aapl_price = aapl_price_env["price"]
                latest_prices["AAPL"] = aapl_price

                aapl_candles.append({
                    "time": current_time,
                    "time_utc": aapl_price_env["fetched_at_utc"],
                    "open": aapl_price,
                    "high": aapl_price,
                    "low": aapl_price,
                    "close": aapl_price,
                    "volume": 0.0
                })
                if len(aapl_candles) > 100:
                    aapl_candles.pop(0)

                print(f"  BTCUSDT: ${btc_price:.2f} | AAPL: ${aapl_price:.2f}")

                # Check safety loop (drawdown limits)
                portfolio_val = engine.get_portfolio_value(latest_prices)
                if sizing.check_safety_reset(portfolio_val, engine.ledger):
                    print("  [SAFETY ALERT] Reset triggered due to excessive drawdown! Closing positions.")
                    engine.is_paused = True
                    # Close BTC Spot
                    btc_qty = engine.spot_holdings.get("BTCUSDT", 0.0)
                    if btc_qty > 0:
                        engine.execute_spot_market_order("BTCUSDT", "SELL", btc_qty, btc_book)
                    # Close AAPL Stock
                    aapl_qty = engine.stock_holdings.get("AAPL", 0.0)
                    if aapl_qty > 0:
                        engine.execute_stock_market_order("AAPL", "SELL", aapl_qty, aapl_price_env)

                # Sync Kelly fraction with calculations if not paused
                if not engine.is_paused and not sizing.is_paused:
                    calculated_kelly = sizing.update_parameters(engine.ledger)
                    if calculated_kelly > 0:
                        engine.kelly_fraction = calculated_kelly

                # C. Generate Signals and Size Positions
                if not engine.is_paused and not sizing.is_paused:
                    # 1. BTC Spot Strategy
                    btc_signal = btc_strategy.next(current_time, btc_price, btc_candles)
                    if btc_signal == "BUY":
                        kelly_frac = engine.kelly_fraction
                        if kelly_frac <= 0:
                            kelly_frac = 0.02
                        buy_cash = engine.cash * kelly_frac
                        buy_qty = buy_cash / btc_book["ask_price"]
                        print(f"  [SIGNAL] BTCUSDT BUY triggered. Kelly Size: {kelly_frac*100:.1f}% -> ${buy_cash:.2f}")
                        tx = engine.execute_spot_market_order("BTCUSDT", "BUY", buy_qty, btc_book)
                        entry_prices["BTCUSDT"] = tx["price"]
                    elif btc_signal == "SELL":
                        btc_qty = engine.spot_holdings.get("BTCUSDT", 0.0)
                        if btc_qty > 0:
                            print(f"  [SIGNAL] BTCUSDT SELL triggered. Closing holding of {btc_qty:.6f} BTC.")
                            tx = engine.execute_spot_market_order("BTCUSDT", "SELL", btc_qty, btc_book)
                            entry_price = entry_prices.get("BTCUSDT", 0.0)
                            if entry_price > 0:
                                exit_price = tx["price"]
                                pnl_pct = (exit_price - entry_price) / entry_price
                                if hasattr(btc_strategy, "record_trade_feedback"):
                                    btc_strategy.record_trade_feedback(pnl_pct)
                                entry_prices["BTCUSDT"] = 0.0

                    # 2. AAPL Stock Strategy
                    aapl_signal = aapl_strategy.next(current_time, aapl_price, aapl_candles)
                    if aapl_signal == "BUY":
                        kelly_frac = engine.kelly_fraction
                        if kelly_frac <= 0:
                            kelly_frac = 0.02
                        buy_cash = engine.cash * kelly_frac
                        buy_qty = int(buy_cash / (aapl_price * 1.0002))
                        if buy_qty > 0:
                            print(f"  [SIGNAL] AAPL BUY triggered. Kelly Size: {kelly_frac*100:.1f}% -> ${buy_cash:.2f}")
                            tx = engine.execute_stock_market_order("AAPL", "BUY", buy_qty, aapl_price_env)
                            entry_prices["AAPL"] = tx["price"]
                    elif aapl_signal == "SELL":
                        aapl_shares = engine.stock_holdings.get("AAPL", 0.0)
                        if aapl_shares > 0:
                            print(f"  [SIGNAL] AAPL SELL triggered. Closing holding of {aapl_shares} shares.")
                            tx = engine.execute_stock_market_order("AAPL", "SELL", aapl_shares, aapl_price_env)
                            entry_price = entry_prices.get("AAPL", 0.0)
                            if entry_price > 0:
                                exit_price = tx["price"]
                                pnl_pct = (exit_price - entry_price) / entry_price
                                if hasattr(aapl_strategy, "record_trade_feedback"):
                                    aapl_strategy.record_trade_feedback(pnl_pct)
                                entry_prices["AAPL"] = 0.0

                else:
                    status_reason = "Safety reset active" if sizing.is_paused else "Paused via UI"
                    print(f"  [SYSTEM STATUS] Bot is paused ({status_reason}). Risk loop inactive.")

                print(f"  Portfolio Valuation: ${portfolio_val:.2f} | Cash: ${engine.cash:.2f}")

            except Exception as e:
                print(f"  Loop cycle error: {e}", file=sys.stderr)

            # Sleep for 10 seconds per loop
            time.sleep(10)

    except KeyboardInterrupt:
        print("\nStopping paper trading bot. Goodbye!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
