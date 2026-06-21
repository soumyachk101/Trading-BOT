"""Position Sizing and Safety Control.

Implements the Fractional Kelly Criterion based on historical strategy results and
defines a Reset-and-Learn Loop to halt, recalculate risk parameters, and scale
down position sizing when drawdown exceeds safe thresholds.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any

logger = logging.getLogger("honest-bot.sizing")


def calculate_kelly_fraction(wins: List[float], losses: List[float], fraction: float = 0.25) -> float:
    """Calculate the position size fraction using the Fractional Kelly Criterion.

    Formula: f* = W - (1 - W) / R
    where W is win rate, R is average win / average loss.
    """
    total_trades = len(wins) + len(losses)
    if total_trades == 0:
        return 0.01  # Default small starter size: 1%

    win_rate = len(wins) / total_trades
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0

    if avg_loss == 0.0:
        return 0.05 if win_rate > 0 else 0.0

    payout_ratio = avg_win / avg_loss
    if payout_ratio == 0.0:
        return 0.0

    raw_kelly = win_rate - (1.0 - win_rate) / payout_ratio
    kelly_fraction = max(0.0, min(raw_kelly, 1.0))

    return kelly_fraction * fraction


class SizingManager:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        drawdown_limit_pct: float = 0.30,  # 30% drawdown triggers reset
        kelly_fraction: float = 0.25,
    ):
        self.initial_balance = initial_balance
        self.drawdown_limit_pct = drawdown_limit_pct
        self.kelly_fraction = kelly_fraction
        
        self.peak_balance = initial_balance
        self.reset_count = 0
        self.is_paused = False

    def check_safety_reset(self, current_balance: float, ledger: List[Dict[str, Any]]) -> bool:
        """Monitor equity drawdown and trigger a safety reset if it exceeds the limit."""
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

        drawdown = (self.peak_balance - current_balance) / self.peak_balance

        if drawdown >= self.drawdown_limit_pct and not self.is_paused:
            self.reset_count += 1
            self.is_paused = True
            
            # Reset-and-Learn logic: Scale down Kelly fraction by half
            old_fraction = self.kelly_fraction
            self.kelly_fraction = max(0.01, self.kelly_fraction * 0.5)
            
            logger.warning(
                f"SAFETY RESET TRIGGERED! Drawdown: {drawdown*100:.2f}% (Limit: {self.drawdown_limit_pct*100:.2f}%). "
                f"Halving Kelly fraction: {old_fraction:.3f} -> {self.kelly_fraction:.3f}. Pausing trading."
            )
            return True

        return False

    def update_parameters(self, ledger: List[Dict[str, Any]]) -> float:
        """Extract win/loss stats from ledger and update Kelly sizing parameters."""
        wins = []
        losses = []

        # Find closed trade segments from ledger to calculate PnL
        # A trade segment is represented by a net cash change in transactions
        for tx in ledger:
            # We look at non-opening transactions that result in profit or loss
            # To be simple and robust: we can look at the positive or negative PnLs logged.
            # In engine ledger, Net Cash Change represents cost/proceeds.
            # For simplicity, let's categorize each non-funding transaction's net profit/loss.
            if tx.get("action") == "SELL" and tx.get("asset_type") != "FUNDING":
                # Average profit/loss can be derived from matching buys/sells.
                # If we don't have matching details, we look at the transaction net cash change.
                # To be precise, let's extract PnL:
                # If net cash change is positive, it's a cash receipt (which could be profit or loss),
                # but we can look at actual realized PnL values if they exist, or estimate.
                # In engine.py perp orders realizd_pnl was calculated, but let's make it general:
                pass

        # If we can't reconstruct trades perfectly from raw ledger, we can calculate daily equity changes
        # Let's write a simple trade analyzer:
        # We can group trades by symbol and track net returns.
        trade_pnls = []
        buy_costs = {}
        
        for tx in ledger:
            sym = tx["symbol"]
            action = tx["action"]
            asset_type = tx["asset_type"]
            price = tx["price"]
            qty = tx["qty"]
            
            if action == "BUY":
                buy_costs[sym] = buy_costs.get(sym, []) + [(price, qty)]
            elif action == "SELL":
                # Compute PnL against FIFO buys
                buys = buy_costs.get(sym, [])
                if buys:
                    # Simple FIFO matching for PnL calculation
                    realized_pnl = 0.0
                    sell_qty_left = qty
                    while sell_qty_left > 0 and buys:
                        buy_price, buy_qty = buys[0]
                        fill_qty = min(buy_qty, sell_qty_left)
                        
                        # Realized PnL = quantity * (sell_price - buy_price)
                        realized_pnl += fill_qty * (price - buy_price)
                        
                        sell_qty_left -= fill_qty
                        if buy_qty == fill_qty:
                            buys.pop(0)
                        else:
                            buys[0] = (buy_price, buy_qty - fill_qty)
                            
                    buy_costs[sym] = buys
                    trade_pnls.append(realized_pnl)

        for pnl in trade_pnls:
            if pnl > 0:
                wins.append(pnl)
            elif pnl < 0:
                losses.append(pnl)

        # Update fraction
        new_fraction = calculate_kelly_fraction(wins, losses, self.kelly_fraction)
        return new_fraction
