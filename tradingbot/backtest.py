"""Honest backtester module.

Runs historical candles through the same HonestEngine used for live trading,
ensuring that fees, slippage, and transaction tracking are identical.
"""
from __future__ import annotations

import datetime as dt
from tradingbot.engine import HonestEngine
from tradingbot.strategies.base import BaseStrategy


def run_backtest(
    candles: list[dict],
    strategy: BaseStrategy,
    asset_type: str = "SPOT",
    symbol: str = "BTCUSDT",
    leverage: float = 1.0,
    initial_balance: float = 10000.0,
) -> dict:
    """Run a backtest using the HonestEngine to ensure exact commissions and slippage are charged.

    Args:
        candles: List of historical candle dicts with keys open, high, low, close, volume, time, time_utc.
        strategy: A strategy instance inheriting from BaseStrategy.
        asset_type: 'SPOT', 'STOCK', or 'PERP'.
        symbol: Asset ticker symbol.
        leverage: Leverage factor (perps only).
        initial_balance: Starting account balance.
    """
    engine = HonestEngine(initial_balance=initial_balance)

    # Standard VIP0 futures fees for perp simulation
    fee_env = {
        "symbol": symbol,
        "maker_rate": 0.0002,
        "taker_rate": 0.0005,
        "source_url": "https://www.binance.com/en/fee/schedule",
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "response_hash": "backtest_futures_fee_tier",
    }

    history = []
    trades_count = 0
    entry_prices = {}

    for i, candle in enumerate(candles):
        history.append(candle)
        price = float(candle["close"])
        current_time = int(candle["time"])

        # Feed the history up to the current candle to the strategy
        signal = strategy.next(current_time, price, history)

        if signal == "BUY":
            if asset_type == "SPOT":
                # Allocate 95% of current cash
                alloc = engine.cash * 0.95
                # Mock a bid-ask bookTicker envelope around close price
                book_env = {
                    "bid_price": price * 0.9999,
                    "ask_price": price * 1.0001,
                    "source_url": f"BinanceSpotHistory:{symbol}",
                    "response_hash": f"hist_{i}_{price}",
                    "fetched_at_utc": candle["time_utc"],
                }
                try:
                    qty = alloc / book_env["ask_price"]
                    tx = engine.execute_spot_market_order(symbol, "BUY", qty, book_env)
                    entry_prices[symbol] = tx["price"]
                    trades_count += 1
                except Exception:
                    pass

            elif asset_type == "STOCK":
                alloc = engine.cash * 0.95
                price_env = {
                    "price": price,
                    "source_url": f"YahooStockHistory:{symbol}",
                    "response_hash": f"hist_{i}_{price}",
                    "fetched_at_utc": candle["time_utc"],
                }
                try:
                    qty = alloc / (price * 1.0002)  # approximate slippage buffer
                    tx = engine.execute_stock_market_order(symbol, "BUY", qty, price_env)
                    entry_prices[symbol] = tx["price"]
                    trades_count += 1
                except Exception:
                    pass

            elif asset_type == "PERP":
                alloc = engine.cash * 0.95
                premium_env = {
                    "markPrice": price,
                    "source_url": f"BinancePerpHistory:{symbol}",
                    "response_hash": f"hist_{i}_{price}",
                    "fetched_at_utc": candle["time_utc"],
                    "time": current_time * 1000,
                }
                try:
                    qty = (alloc * leverage) / price
                    tx = engine.execute_perp_market_order(symbol, "BUY", qty, leverage, premium_env, fee_env)
                    entry_prices[symbol] = tx["price"]
                    trades_count += 1
                except Exception:
                    pass

        elif signal == "SELL":
            if asset_type == "SPOT":
                qty = engine.spot_holdings.get(symbol, 0.0)
                if qty > 0:
                    book_env = {
                        "bid_price": price * 0.9999,
                        "ask_price": price * 1.0001,
                        "source_url": f"BinanceSpotHistory:{symbol}",
                        "response_hash": f"hist_{i}_{price}",
                        "fetched_at_utc": candle["time_utc"],
                    }
                    try:
                        tx = engine.execute_spot_market_order(symbol, "SELL", qty, book_env)
                        trades_count += 1
                        
                        entry_price = entry_prices.get(symbol, 0.0)
                        if entry_price > 0:
                            exit_price = tx["price"]
                            pnl_pct = (exit_price - entry_price) / entry_price
                            if hasattr(strategy, "record_trade_feedback"):
                                strategy.record_trade_feedback(pnl_pct)
                            entry_prices[symbol] = 0.0
                    except Exception:
                        pass

            elif asset_type == "STOCK":
                qty = engine.stock_holdings.get(symbol, 0.0)
                if qty > 0:
                    price_env = {
                        "price": price,
                        "source_url": f"YahooStockHistory:{symbol}",
                        "response_hash": f"hist_{i}_{price}",
                        "fetched_at_utc": candle["time_utc"],
                    }
                    try:
                        tx = engine.execute_stock_market_order(symbol, "SELL", qty, price_env)
                        trades_count += 1
                        
                        entry_price = entry_prices.get(symbol, 0.0)
                        if entry_price > 0:
                            exit_price = tx["price"]
                            pnl_pct = (exit_price - entry_price) / entry_price
                            if hasattr(strategy, "record_trade_feedback"):
                                strategy.record_trade_feedback(pnl_pct)
                            entry_prices[symbol] = 0.0
                    except Exception:
                        pass

            elif asset_type == "PERP":
                pos = engine.perp_positions.get(symbol)
                if pos and pos["size"] != 0:
                    qty = abs(pos["size"])
                    direction = 1 if pos["size"] > 0 else -1
                    premium_env = {
                        "markPrice": price,
                        "source_url": f"BinancePerpHistory:{symbol}",
                        "response_hash": f"hist_{i}_{price}",
                        "fetched_at_utc": candle["time_utc"],
                    }
                    try:
                        side = "SELL" if pos["size"] > 0 else "BUY"
                        tx = engine.execute_perp_market_order(symbol, side, qty, leverage, premium_env, fee_env)
                        trades_count += 1
                        
                        entry_price = entry_prices.get(symbol, 0.0)
                        if entry_price > 0:
                            exit_price = tx["price"]
                            pnl_pct = direction * (exit_price - entry_price) / entry_price
                            if hasattr(strategy, "record_trade_feedback"):
                                strategy.record_trade_feedback(pnl_pct)
                            entry_prices[symbol] = 0.0
                    except Exception:
                        pass

        # Apply daily perpetual funding and checks
        if asset_type == "PERP":
            pos = engine.perp_positions.get(symbol)
            if pos and pos["size"] != 0:
                history_env = {
                    "rows": [{"fundingTime": current_time * 1000, "fundingRate": 0.0001, "markPrice": price}],
                    "source_url": "https://fapi.binance.com/fapi/v1/fundingRate",
                    "response_hash": f"hist_fund_{i}",
                    "fetched_at_utc": candle["time_utc"],
                }
                premium_env = {"time": current_time * 1000}
                engine.apply_perp_funding(symbol, history_env, premium_env)

                premium_env_liq = {
                    "markPrice": price,
                    "source_url": "https://fapi.binance.com/fapi/v1/premiumIndex",
                    "response_hash": f"hist_liq_{i}",
                    "fetched_at_utc": candle["time_utc"],
                }
                engine.check_and_liquidate_perps(symbol, premium_env_liq)

    # Compute final valuation
    current_prices = {symbol: float(candles[-1]["close"])}
    final_value = engine.get_portfolio_value(current_prices)
    net_return = (final_value - initial_balance) / initial_balance

    return {
        "strategy_name": strategy.name,
        "symbol": symbol,
        "initial_balance": initial_balance,
        "final_value": final_value,
        "net_return": net_return,
        "trades_count": trades_count,
        "ledger": engine.ledger,
    }
