"""Step 2 Cycle: Demonstrate one complete honest trade cycle.

Fetches real live prices, simulates trading with paper balance, applies real fees,
funding, and slippage, closes positions truthfully on live prices, and prints
the complete audit ledger showing source_url and response_hash validation parameters.
"""
from __future__ import annotations

import json
import time
import sys
from tradingbot.engine import HonestEngine
from tradingbot import prices


def main() -> int:
    print("==================================================")
    print("           HONEST ENGINE TRADE CYCLE              ")
    print("==================================================\n")

    # Initialize Engine
    engine = HonestEngine(initial_balance=10000.0)
    print(f"Engine Initialized. Cash Balance: ${engine.cash:.2f} USD\n")

    # --- PART 1: FETCH LIVE DATA ---
    print("--- 1. Fetching Live Prices & Info ---")
    try:
        # Crypto Spot Book Top (Binance)
        print("Fetching Binance spot book ticker for BTCUSDT...")
        spot_book = prices.fetch_spot_book_top("BTCUSDT")
        print(f"  Spot Bid: {spot_book['bid_price']:.2f} | Spot Ask: {spot_book['ask_price']:.2f}")

        # Stock Price (Yahoo Finance)
        print("Fetching Yahoo Finance stock price for AAPL...")
        stock_price = prices.fetch_stock_price("AAPL")
        print(f"  Stock Price: {stock_price['price']:.2f}")

        # Crypto Perp Premium Index & Commission Rates (Binance)
        print("Fetching Binance USDⓈ-M Futures premium index for BTCUSDT...")
        perp_prem = prices.fetch_perp_premium("BTCUSDT")
        print(f"  Perp Mark Price: {perp_prem['markPrice']:.2f}")

        print("Fetching Binance USDⓈ-M Futures VIP0 commission rate...")
        perp_fee = prices.fetch_perp_commission_rate("BTCUSDT")
        print(f"  Futures Taker Rate: {perp_fee['taker_rate'] * 100:.3f}% | Maker Rate: {perp_fee['maker_rate'] * 100:.3f}%")
        print()

    except Exception as e:
        print(f"Error fetching live prices: {e}", file=sys.stderr)
        return 1

    # --- PART 2: EXECUTE BUY ORDERS ---
    print("--- 2. Executing Buy Orders ---")
    try:
        # A. Spot Order
        spot_qty = 0.05
        print(f"Executing Spot Market BUY of {spot_qty} BTCUSDT...")
        spot_buy_tx = engine.execute_spot_market_order("BTCUSDT", "BUY", spot_qty, spot_book)
        print(f"  Spot Filled at Ask: {spot_buy_tx['price']:.2f}")
        print(f"  Fee charged (in BTC): {spot_buy_tx['fee_usd'] / spot_buy_tx['price']:.6f} BTC (${spot_buy_tx['fee_usd']:.2f} USD)")

        # B. Stock Order
        stock_qty = 10.0
        print(f"\nExecuting Stock Market BUY of {stock_qty} shares of AAPL...")
        stock_buy_tx = engine.execute_stock_market_order("AAPL", "BUY", stock_qty, stock_price)
        print(f"  Stock Filled at: {stock_buy_tx['price']:.2f} (includes {stock_buy_tx['slippage_bps']:.1f} bps slippage)")
        print(f"  Fee charged: ${stock_buy_tx['fee_usd']:.2f} USD")

        # C. Perpetual Futures Order
        perp_qty = 0.02
        leverage = 10.0
        print(f"\nExecuting Perp Futures 10x leverage BUY of {perp_qty} BTCUSDT...")
        perp_buy_tx = engine.execute_perp_market_order("BTCUSDT", "BUY", perp_qty, leverage, perp_prem, perp_fee)
        print(f"  Perp Filled at Mark: {perp_buy_tx['price']:.2f}")
        print(f"  Margin Allocated: ${engine.perp_positions['BTCUSDT']['margin']:.2f} USD")
        print(f"  Futures Taker Fee: ${perp_buy_tx['fee_usd']:.2f} USD")
        print()

    except Exception as e:
        print(f"Execution error during Buy: {e}", file=sys.stderr)
        return 1

    # Log Intermediate State
    print("--- Intermediate Portfolio State ---")
    print(f"Cash Balance: ${engine.cash:.2f} USD")
    print("Spot Holdings:", engine.spot_holdings)
    print("Stock Holdings:", engine.stock_holdings)
    print("Perp Positions:")
    for sym, pos in engine.perp_positions.items():
        print(f"  {sym}: Size {pos['size']}, Entry {pos['entry_price']:.2f}, Margin {pos['margin']:.2f}")
    print()

    # --- PART 3: SIMULATING POSITION CLOSING ---
    # We wait a moment and fetch new prices to simulate a truthful close
    print("Sleeping for 2 seconds to simulate market time delay...")
    time.sleep(2)
    print()

    print("--- 3. Fetching New Live Prices for Truthful Close ---")
    try:
        spot_book_new = prices.fetch_spot_book_top("BTCUSDT")
        stock_price_new = prices.fetch_stock_price("AAPL")
        perp_prem_new = prices.fetch_perp_premium("BTCUSDT")

        print(f"  New Spot Bid: {spot_book_new['bid_price']:.2f}")
        print(f"  New Stock Price: {stock_price_new['price']:.2f}")
        print(f"  New Perp Mark Price: {perp_prem_new['markPrice']:.2f}")
        print()
    except Exception as e:
        print(f"Error fetching new prices: {e}", file=sys.stderr)
        return 1

    print("--- 4. Executing Close (Sell) Orders ---")
    try:
        # A. Spot Sell (We sell all spot holdings)
        sell_spot_qty = engine.spot_holdings["BTCUSDT"]
        print(f"Executing Spot Market SELL of {sell_spot_qty:.6f} BTCUSDT...")
        spot_sell_tx = engine.execute_spot_market_order("BTCUSDT", "SELL", sell_spot_qty, spot_book_new)
        print(f"  Spot Sell Filled at Bid: {spot_sell_tx['price']:.2f}")
        print(f"  Taker fee charged: ${spot_sell_tx['fee_usd']:.2f} USD")

        # B. Stock Sell
        sell_stock_qty = engine.stock_holdings["AAPL"]
        print(f"\nExecuting Stock Market SELL of {sell_stock_qty} shares of AAPL...")
        stock_sell_tx = engine.execute_stock_market_order("AAPL", "SELL", sell_stock_qty, stock_price_new)
        print(f"  Stock Sell Filled at: {stock_sell_tx['price']:.2f} (includes {stock_sell_tx['slippage_bps']:.1f} bps slippage)")
        print(f"  Regulatory fees charged (SEC + FINRA TAF): ${stock_sell_tx['fee_usd']:.4f} USD")

        # C. Perpetual Futures Sell
        sell_perp_qty = abs(engine.perp_positions["BTCUSDT"]["size"])
        print(f"\nExecuting Perp Futures SELL of {sell_perp_qty} BTCUSDT to close position...")
        perp_sell_tx = engine.execute_perp_market_order("BTCUSDT", "SELL", sell_perp_qty, leverage, perp_prem_new, perp_fee)
        print(f"  Perp Closed at Mark: {perp_sell_tx['price']:.2f}")
        print(f"  Taker fee charged: ${perp_sell_tx['fee_usd']:.2f} USD")
        print()

    except Exception as e:
        print(f"Execution error during Sell: {e}", file=sys.stderr)
        return 1

    # --- PART 4: AUDIT LEDGER AND PORTFOLIO VALUE ---
    # Retrieve current prices to map total value
    current_prices = {
        "BTCUSDT": spot_book_new["bid_price"],
        "AAPL": stock_price_new["price"],
    }
    final_val = engine.get_portfolio_value(current_prices)
    net_pnl = final_val - 10000.0

    print("--- Final Portfolio State ---")
    print(f"Final Portfolio Net Value: ${final_val:.4f} USD")
    print(f"Total Net profit/loss: ${net_pnl:.4f} USD")
    print(f"Final Cash Balance: ${engine.cash:.4f} USD")
    print()

    print("--- 5. The Auditable Honesty Log (First 3 Ledger entries shown) ---")
    for idx, tx in enumerate(engine.ledger[:3]):
        print(f"\nTransaction #{idx+1}:")
        print(f"  Timestamp:     {tx['timestamp']}")
        print(f"  Action:        {tx['action']} {tx['symbol']} ({tx['asset_type']})")
        print(f"  Quantity:      {tx['qty']}")
        print(f"  Price:         ${tx['price']:.4f}")
        print(f"  Fees Charged:  ${tx['fee_usd']:.4f}")
        print(f"  Slippage Bps:  {tx['slippage_bps']:.1f}")
        print(f"  Net Cash Chg:  ${tx['net_cash_change']:.4f}")
        print(f"  Source URL:    {tx['source_url']}")
        print(f"  Response Hash: {tx['response_hash']}")

    print("\nAll trades are logged truthfully. Fills correspond to real endpoints, real fees, and real prices.")
    print("Step 2 completed successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
