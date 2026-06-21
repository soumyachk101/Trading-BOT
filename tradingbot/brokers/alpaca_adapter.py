"""Alpaca Broker Adapter implementation."""
from __future__ import annotations

from tradingbot.brokers.base import BaseBroker
from tradingbot import real_exchange


class AlpacaBrokerAdapter(BaseBroker):
    def __init__(self, api_key: str, api_secret: str, is_paper: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_paper = is_paper

    def execute_market_order(self, symbol: str, side: str, qty: float, **kwargs) -> dict:
        """Execute market order on Alpaca."""
        res = real_exchange.execute_real_alpaca_stock(
            symbol, side, qty, self.api_key, self.api_secret, self.is_paper
        )
        # Compute SEC & TAF fees on sell orders
        price = res["price"]
        executed_qty = res["qty"]
        gross_value = price * executed_qty
        if side.upper() == "SELL":
            sec_fee = gross_value * 0.0000206
            taf_fee = min(executed_qty * 0.000195, 9.79)
            res["fee_usd"] = sec_fee + taf_fee
        else:
            res["fee_usd"] = 0.0
        return res

    def get_balance(self) -> float:
        """Retrieve Alpaca available cash balance."""
        try:
            bals = real_exchange.fetch_real_balances(
                None, None, self.api_key, self.api_secret, self.is_paper
            )
            return bals.get("cash", 0.0)
        except Exception:
            return 0.0
