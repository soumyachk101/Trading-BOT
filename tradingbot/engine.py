"""Honest paper trading engine & live API routing controller.

Manages cash balances, asset positions, commissions, funding, and liquidations.
When LIVE_TRADING is enabled, routes orders to real_exchange.py and formats real
exchanges responses back into the auditable Honesty Envelope structures.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import time
from typing import Dict, List, Any
from tradingbot import config
from tradingbot import real_exchange
from tradingbot.config import PAPER_BALANCE_USD, SLIPPAGE_BUFFER_BPS


class HonestEngine:
    def __init__(self, initial_balance: float = PAPER_BALANCE_USD):
        self.live_mode: bool = config.LIVE_TRADING

        # If live mode, synchronize starting balance from active API keys
        if self.live_mode:
            try:
                real_bals = real_exchange.fetch_real_balances(
                    config.BINANCE_API_KEY,
                    config.BINANCE_API_SECRET,
                    config.ALPACA_API_KEY,
                    config.ALPACA_API_SECRET,
                    config.ALPACA_IS_PAPER
                )
                self.cash: float = real_bals.get("cash", initial_balance)
            except Exception:
                self.cash = initial_balance
        else:
            self.cash = initial_balance

        # Active settings flags
        self.is_paused: bool = False
        self.kelly_fraction: float = 0.25
        self.slippage_bps: float = SLIPPAGE_BUFFER_BPS

        # Spot holdings: {symbol: quantity}
        self.spot_holdings: Dict[str, float] = {}

        # Stock holdings: {symbol: share_count}
        self.stock_holdings: Dict[str, float] = {}

        # Perp positions: {symbol: perp_position_dict}
        # perp_position_dict: {size: float, entry_price: float, margin: float, leverage: float, last_funding_time: int}
        self.perp_positions: Dict[str, Dict[str, Any]] = {}

        # Unified ledger for auditing every transaction
        self.ledger: List[Dict[str, Any]] = []

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate the total net asset value of the portfolio at current prices."""
        val = self.cash
        # Add spot value
        for sym, qty in self.spot_holdings.items():
            if qty > 0:
                price = current_prices.get(sym, 0.0)
                val += qty * price

        # Add stock value
        for sym, shares in self.stock_holdings.items():
            if shares > 0:
                price = current_prices.get(sym, 0.0)
                val += shares * price

        # Add perp unrealized PnL and margin
        for sym, pos in self.perp_positions.items():
            size = pos["size"]
            if size != 0:
                price = current_prices.get(sym, 0.0)
                if price > 0:
                    # Unrealized PnL: size * (mark_price - entry_price) for longs,
                    # size is negative for shorts, so size * (price - entry) is correct for both.
                    unrealized_pnl = size * (price - pos["entry_price"])
                    val += unrealized_pnl

        return val

    def execute_spot_market_order(self, symbol: str, side: str, qty: float, book_envelope: dict) -> dict:
        """Execute a spot market order.

        If live mode, places order on Binance Spot. Otherwise, simulates locally.
        """
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}")

        if self.live_mode:
            if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
                raise ValueError("Binance API credentials are missing for live spot order execution")

            # Place order on real exchange via adapter
            from tradingbot.brokers.binance_adapter import BinanceBrokerAdapter
            adapter = BinanceBrokerAdapter(
                api_key=config.BINANCE_API_KEY,
                api_secret=config.BINANCE_API_SECRET,
                is_futures=False
            )
            real_res = adapter.execute_market_order(symbol, side, qty)
            fill_price = real_res["price"]
            executed_qty = real_res["qty"]
            fee_usd = real_res["fee_usd"]

            # Reconcile our portfolio state
            gross_cost = executed_qty * fill_price
            if side == "BUY":
                self.cash -= gross_cost
                fee_asset = executed_qty * 0.0010  # Standard spot fee
                net_qty = executed_qty - fee_asset
                self.spot_holdings[symbol] = self.spot_holdings.get(symbol, 0.0) + net_qty
            else:
                self.spot_holdings[symbol] = max(0.0, self.spot_holdings.get(symbol, 0.0) - executed_qty)
                self.cash += (gross_cost - fee_usd)
                net_qty = -executed_qty

            tx = {
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "action": side,
                "asset_type": "SPOT",
                "symbol": symbol,
                "qty": executed_qty,
                "net_qty": net_qty,
                "price": fill_price,
                "slippage_bps": 0.0,
                "fee_usd": fee_usd,
                "net_cash_change": -gross_cost if side == "BUY" else (gross_cost - fee_usd),
                "source_url": "https://api.binance.com/api/v3/order (Live API)",
                "response_hash": hashlib.sha256(str(real_res["raw_response"]).encode("utf-8")).hexdigest(),
                "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            self.ledger.append(tx)
            return tx

        else:
            # Paper trading simulation
            bid = book_envelope["bid_price"]
            ask = book_envelope["ask_price"]
            src_url = book_envelope["source_url"]
            resp_hash = book_envelope["response_hash"]
            fetched_at = book_envelope["fetched_at_utc"]

            fee_rate = 0.0010

            if side == "BUY":
                fill_price = ask
                gross_cost = qty * fill_price

                if gross_cost > self.cash:
                    raise ValueError(f"Insufficient cash for spot buy: cost={gross_cost:.4f}, cash={self.cash:.4f}")

                self.cash -= gross_cost
                fee_asset = qty * fee_rate
                net_qty = qty - fee_asset
                self.spot_holdings[symbol] = self.spot_holdings.get(symbol, 0.0) + net_qty

                tx = {
                    "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "action": "BUY",
                    "asset_type": "SPOT",
                    "symbol": symbol,
                    "qty": qty,
                    "net_qty": net_qty,
                    "price": fill_price,
                    "slippage_bps": 0.0,
                    "fee_usd": fee_asset * fill_price,
                    "net_cash_change": -gross_cost,
                    "source_url": src_url,
                    "response_hash": resp_hash,
                    "fetched_at_utc": fetched_at,
                }
                self.ledger.append(tx)
                return tx

            else:
                fill_price = bid
                current_holding = self.spot_holdings.get(symbol, 0.0)
                if qty > current_holding:
                    raise ValueError(f"Insufficient spot balance to sell: holding={current_holding:.6f}, sell_qty={qty:.6f}")

                self.spot_holdings[symbol] = current_holding - qty
                gross_proceeds = qty * fill_price
                fee_usd = gross_proceeds * fee_rate
                net_proceeds = gross_proceeds - fee_usd
                self.cash += net_proceeds

                tx = {
                    "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "action": "SELL",
                    "asset_type": "SPOT",
                    "symbol": symbol,
                    "qty": qty,
                    "net_qty": -qty,
                    "price": fill_price,
                    "slippage_bps": 0.0,
                    "fee_usd": fee_usd,
                    "net_cash_change": net_proceeds,
                    "source_url": src_url,
                    "response_hash": resp_hash,
                    "fetched_at_utc": fetched_at,
                }
                self.ledger.append(tx)
                return tx

    def execute_stock_market_order(self, symbol: str, side: str, qty: float, price_envelope: dict) -> dict:
        """Execute a stock market order.

        If live mode, routes order to Alpaca REST API. Otherwise, simulates locally.
        """
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}")

        if self.live_mode:
            import os
            stock_broker = os.environ.get("STOCK_BROKER", "ALPACA").upper()
            if stock_broker == "IBKR":
                from tradingbot.brokers.ibkr_adapter import IBKRBrokerAdapter
                adapter = IBKRBrokerAdapter(account_id=os.environ.get("IBKR_ACCOUNT_ID"))
            else:
                if not config.ALPACA_API_KEY or not config.ALPACA_API_SECRET:
                    raise ValueError("Alpaca API credentials are missing for live stock order execution")
                from tradingbot.brokers.alpaca_adapter import AlpacaBrokerAdapter
                adapter = AlpacaBrokerAdapter(
                    api_key=config.ALPACA_API_KEY,
                    api_secret=config.ALPACA_API_SECRET,
                    is_paper=config.ALPACA_IS_PAPER
                )
            
            real_res = adapter.execute_market_order(symbol, side, qty)
            fill_price = real_res["price"]
            executed_qty = real_res["qty"]

            gross_value = executed_qty * fill_price

            if side == "BUY":
                fee_usd = 0.0
                total_cost = gross_value
                self.cash -= total_cost
                self.stock_holdings[symbol] = self.stock_holdings.get(symbol, 0.0) + executed_qty
                net_cash = -total_cost
            else:
                sec_fee = gross_value * 0.0000206
                taf_fee = min(executed_qty * 0.000195, 9.79)
                fee_usd = sec_fee + taf_fee
                net_proceeds = gross_value - fee_usd
                self.cash += net_proceeds
                self.stock_holdings[symbol] = max(0.0, self.stock_holdings.get(symbol, 0.0) - executed_qty)
                net_cash = net_proceeds

            tx = {
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "action": side,
                "asset_type": "STOCK",
                "symbol": symbol,
                "qty": executed_qty,
                "net_qty": executed_qty if side == "BUY" else -executed_qty,
                "price": fill_price,
                "slippage_bps": self.slippage_bps,
                "fee_usd": fee_usd,
                "net_cash_change": net_cash,
                "source_url": "https://paper-api.alpaca.markets/v2/orders (Live API)" if config.ALPACA_IS_PAPER else "https://api.alpaca.markets/v2/orders (Live API)",
                "response_hash": hashlib.sha256(str(real_res["raw_response"]).encode("utf-8")).hexdigest(),
                "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            self.ledger.append(tx)
            return tx

        else:
            # Paper trading simulation
            mid_price = price_envelope["price"]
            src_url = price_envelope["source_url"]
            resp_hash = price_envelope["response_hash"]
            fetched_at = price_envelope["fetched_at_utc"]

            slippage_factor = self.slippage_bps / 10000.0

            if side == "BUY":
                fill_price = mid_price * (1.0 + slippage_factor)
                gross_cost = qty * fill_price
                fee_usd = 0.0
                total_cost = gross_cost + fee_usd

                if total_cost > self.cash:
                    raise ValueError(f"Insufficient cash for stock buy: cost={total_cost:.4f}, cash={self.cash:.4f}")

                self.cash -= total_cost
                self.stock_holdings[symbol] = self.stock_holdings.get(symbol, 0.0) + qty

                tx = {
                    "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "action": "BUY",
                    "asset_type": "STOCK",
                    "symbol": symbol,
                    "qty": qty,
                    "net_qty": qty,
                    "price": fill_price,
                    "slippage_bps": self.slippage_bps,
                    "fee_usd": fee_usd,
                    "net_cash_change": -total_cost,
                    "source_url": src_url,
                    "response_hash": resp_hash,
                    "fetched_at_utc": fetched_at,
                }
                self.ledger.append(tx)
                return tx

            else:
                fill_price = mid_price * (1.0 - slippage_factor)
                current_shares = self.stock_holdings.get(symbol, 0.0)
                if qty > current_shares:
                    raise ValueError(f"Insufficient stock shares to sell: shares={current_shares:.4f}, sell_qty={qty:.4f}")

                self.stock_holdings[symbol] = current_shares - qty
                gross_proceeds = qty * fill_price

                sec_fee = gross_proceeds * 0.0000206
                taf_fee = min(qty * 0.000195, 9.79)

                fee_usd = sec_fee + taf_fee
                net_proceeds = gross_proceeds - fee_usd
                self.cash += net_proceeds

                tx = {
                    "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "action": "SELL",
                    "asset_type": "STOCK",
                    "symbol": symbol,
                    "qty": qty,
                    "net_qty": -qty,
                    "price": fill_price,
                    "slippage_bps": self.slippage_bps,
                    "fee_usd": fee_usd,
                    "net_cash_change": net_proceeds,
                    "source_url": src_url,
                    "response_hash": resp_hash,
                    "fetched_at_utc": fetched_at,
                }
                self.ledger.append(tx)
                return tx

    def execute_perp_market_order(
        self, symbol: str, side: str, qty: float, leverage: float, premium_envelope: dict, fee_envelope: dict
    ) -> dict:
        """Execute a perpetual futures market order.

        If live mode, places order on Binance USD-M Futures. Otherwise, simulates locally.
        """
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}")

        if self.live_mode:
            if not config.BINANCE_API_KEY or not config.BINANCE_API_SECRET:
                raise ValueError("Binance API credentials are missing for live perp order execution")

            from tradingbot.brokers.binance_adapter import BinanceBrokerAdapter
            adapter = BinanceBrokerAdapter(
                api_key=config.BINANCE_API_KEY,
                api_secret=config.BINANCE_API_SECRET,
                is_futures=True
            )
            real_res = adapter.execute_market_order(symbol, side, qty, leverage=leverage)
            fill_price = real_res["price"]
            executed_qty = real_res["qty"]

            trade_size = executed_qty if side == "BUY" else -executed_qty
            taker_rate = fee_envelope["taker_rate"]
            fee_usd = executed_qty * fill_price * taker_rate
            margin_required = (executed_qty * fill_price) / leverage

            # Reconcile our portfolio state
            pos = self.perp_positions.get(
                symbol,
                {
                    "size": 0.0,
                    "entry_price": 0.0,
                    "margin": 0.0,
                    "leverage": leverage,
                    "last_funding_time": None,
                },
            )

            current_size = pos["size"]
            current_entry = pos["entry_price"]
            current_margin = pos["margin"]
            new_size = current_size + trade_size

            if current_size == 0:
                new_entry = fill_price
                new_margin = margin_required
                self.cash -= (new_margin + fee_usd)
                net_cash_chg = -(margin_required + fee_usd)
            elif (current_size > 0 and trade_size > 0) or (current_size < 0 and trade_size < 0):
                total_qty = abs(current_size) + executed_qty
                new_entry = ((abs(current_size) * current_entry) + (executed_qty * fill_price)) / total_qty
                new_margin = current_margin + margin_required
                self.cash -= (margin_required + fee_usd)
                net_cash_chg = -(margin_required + fee_usd)
            else:
                closed_qty = min(abs(current_size), executed_qty)
                direction = 1 if current_size > 0 else -1
                realized_pnl = closed_qty * direction * (fill_price - current_entry)
                margin_released = (closed_qty / abs(current_size)) * current_margin
                new_margin = current_margin - margin_released
                self.cash += (margin_released + realized_pnl - fee_usd)
                net_cash_chg = (margin_released + realized_pnl - fee_usd)

                if math.isclose(new_size, 0.0, abs_tol=1e-9):
                    new_size = 0.0
                    new_entry = 0.0
                    new_margin = 0.0
                else:
                    new_entry = current_entry

            pos.update(
                {
                    "size": new_size,
                    "entry_price": new_entry,
                    "margin": new_margin,
                    "leverage": leverage,
                    "last_funding_time": pos.get("last_funding_time") or int(time.time() * 1000),
                }
            )
            self.perp_positions[symbol] = pos

            tx = {
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "action": side,
                "asset_type": "PERP",
                "symbol": symbol,
                "qty": executed_qty,
                "net_qty": trade_size,
                "price": fill_price,
                "slippage_bps": 0.0,
                "fee_usd": fee_usd,
                "net_cash_change": net_cash_chg,
                "source_url": "https://fapi.binance.com/fapi/v1/order (Live API)",
                "response_hash": hashlib.sha256(str(real_res["raw_response"]).encode("utf-8")).hexdigest(),
                "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            self.ledger.append(tx)
            return tx

        else:
            # Paper trading simulation
            mark_price = premium_envelope["markPrice"]
            if mark_price is None:
                raise ValueError("Mark price is missing from premium envelope")

            src_url = premium_envelope["source_url"]
            resp_hash = premium_envelope["response_hash"]
            fetched_at = premium_envelope["fetched_at_utc"]

            taker_rate = fee_envelope["taker_rate"]

            trade_size = qty if side == "BUY" else -qty
            fee_usd = qty * mark_price * taker_rate
            margin_required = (qty * mark_price) / leverage

            if self.cash < (margin_required + fee_usd):
                raise ValueError(
                    f"Insufficient balance to open perp: margin={margin_required:.4f}, fee={fee_usd:.4f}, cash={self.cash:.4f}"
                )

            pos = self.perp_positions.get(
                symbol,
                {
                    "size": 0.0,
                    "entry_price": 0.0,
                    "margin": 0.0,
                    "leverage": leverage,
                    "last_funding_time": None,
                },
            )

            current_size = pos["size"]
            current_entry = pos["entry_price"]
            current_margin = pos["margin"]
            new_size = current_size + trade_size

            if current_size == 0:
                new_entry = mark_price
                new_margin = margin_required
                self.cash -= (new_margin + fee_usd)
            elif (current_size > 0 and trade_size > 0) or (current_size < 0 and trade_size < 0):
                total_qty = abs(current_size) + qty
                new_entry = ((abs(current_size) * current_entry) + (qty * mark_price)) / total_qty
                new_margin = current_margin + margin_required
                self.cash -= (margin_required + fee_usd)
            else:
                closed_qty = min(abs(current_size), qty)
                direction = 1 if current_size > 0 else -1
                realized_pnl = closed_qty * direction * (mark_price - current_entry)

                margin_released = (closed_qty / abs(current_size)) * current_margin
                new_margin = current_margin - margin_released

                self.cash += (margin_released + realized_pnl - fee_usd)

                if math.isclose(new_size, 0.0, abs_tol=1e-9):
                    new_size = 0.0
                    new_entry = 0.0
                    new_margin = 0.0
                else:
                    new_entry = current_entry

            pos.update(
                {
                    "size": new_size,
                    "entry_price": new_entry,
                    "margin": new_margin,
                    "leverage": leverage,
                    "last_funding_time": (
                        premium_envelope.get("time")
                        if pos.get("last_funding_time") is None
                        else pos["last_funding_time"]
                    ),
                }
            )

            self.perp_positions[symbol] = pos

            tx = {
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "action": side,
                "asset_type": "PERP",
                "symbol": symbol,
                "qty": qty,
                "net_qty": trade_size,
                "price": mark_price,
                "slippage_bps": 0.0,
                "fee_usd": fee_usd,
                "net_cash_change": (
                    -(margin_required + fee_usd)
                    if (
                        current_size == 0
                        or (current_size > 0 and trade_size > 0)
                        or (current_size < 0 and trade_size < 0)
                    )
                    else (margin_released + realized_pnl - fee_usd)
                ),
                "source_url": src_url,
                "response_hash": resp_hash,
                "fetched_at_utc": fetched_at,
            }
            self.ledger.append(tx)
            return tx

    def apply_perp_funding(self, symbol: str, history_envelope: dict, premium_envelope: dict) -> dict | None:
        """Apply perpetual futures funding payments if a new funding interval has passed.

        Funding is calculated on the nominal position value: size * mark_price * funding_rate.
        Long pays short if funding_rate is positive, short pays long if negative.
        """
        pos = self.perp_positions.get(symbol)
        if not pos or pos["size"] == 0.0:
            return None

        # Get historical rates
        rows = history_envelope.get("data") if history_envelope.get("_kind") == "list" else history_envelope.get("rows")
        if not rows:
            return None

        last_funding = pos["last_funding_time"]
        if last_funding is None:
            pos["last_funding_time"] = min(int(r["fundingTime"]) for r in rows)
            return None

        newest_funding_row = max(rows, key=lambda r: int(r["fundingTime"]))
        newest_funding_time = int(newest_funding_row["fundingTime"])

        if newest_funding_time <= last_funding:
            return None

        funding_rate = newest_funding_row["fundingRate"]
        mark_price = newest_funding_row["markPrice"]

        size = pos["size"]
        cash_change = -(size * mark_price * funding_rate)

        self.cash += cash_change
        pos["last_funding_time"] = newest_funding_time

        tx = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "action": "FUNDING",
            "asset_type": "PERP",
            "symbol": symbol,
            "qty": abs(size),
            "net_qty": 0.0,
            "price": mark_price,
            "slippage_bps": 0.0,
            "fee_usd": 0.0,
            "net_cash_change": cash_change,
            "source_url": history_envelope["source_url"],
            "response_hash": history_envelope["response_hash"],
            "fetched_at_utc": history_envelope["fetched_at_utc"],
        }
        self.ledger.append(tx)
        return tx

    def check_and_liquidate_perps(self, symbol: str, premium_envelope: dict) -> dict | None:
        """Check maintenance margin of perp position and liquidate if necessary.

        Binance BTCUSDT perpetual liquidation clearance fee is 1.25%.
        If unrealized loss exceeds allocated margin, or if total cash goes negative,
        we liquidate the position immediately at markPrice.
        """
        pos = self.perp_positions.get(symbol)
        if not pos or pos["size"] == 0.0:
            return None

        mark_price = premium_envelope["markPrice"]
        if mark_price is None:
            return None

        size = pos["size"]
        entry_price = pos["entry_price"]
        margin = pos["margin"]

        # Unrealized PnL
        unrealized_pnl = size * (mark_price - entry_price)

        # Maintenance margin is 0.5%
        maint_margin_rate = 0.005
        maint_margin = abs(size) * mark_price * maint_margin_rate

        # Remaining margin after PnL
        remaining_margin = margin + unrealized_pnl

        # Trigger condition: remaining margin < maintenance margin or total cash < 0
        if remaining_margin < maint_margin or self.cash < 0:
            liquidate_size = abs(size)

            # Binance liquidation clearance fee is 1.25% (0.0125) of position nominal value
            clearance_fee = liquidate_size * mark_price * 0.0125

            # Realized loss at liquidation mark_price
            realized_loss = size * (mark_price - entry_price)

            # Resolve cash impact: release initial margin, realize the loss, and deduct liquidation fee
            self.cash += margin + realized_loss - clearance_fee

            # Position is zeroed out
            pos.update(
                {
                    "size": 0.0,
                    "entry_price": 0.0,
                    "margin": 0.0,
                }
            )

            tx = {
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                "action": "LIQUIDATION",
                "asset_type": "PERP",
                "symbol": symbol,
                "qty": liquidate_size,
                "net_qty": -size,
                "price": mark_price,
                "slippage_bps": 0.0,
                "fee_usd": clearance_fee,
                "net_cash_change": margin + realized_loss - clearance_fee,
                "source_url": premium_envelope["source_url"],
                "response_hash": premium_envelope["response_hash"],
                "fetched_at_utc": premium_envelope["fetched_at_utc"],
            }
            self.ledger.append(tx)
            return tx

        return None
