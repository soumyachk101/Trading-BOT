"""Binance Broker Adapter implementation."""
from __future__ import annotations

from tradingbot.brokers.base import BaseBroker
from tradingbot import real_exchange


class BinanceBrokerAdapter(BaseBroker):
    def __init__(self, api_key: str, api_secret: str, is_futures: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_futures = is_futures

    def execute_market_order(self, symbol: str, side: str, qty: float, **kwargs) -> dict:
        """Execute order on Binance Spot or perpetual futures."""
        if self.is_futures:
            leverage = kwargs.get("leverage", 1.0)
            res = real_exchange.execute_real_binance_perp(
                symbol, side, qty, leverage, self.api_key, self.api_secret
            )
            # perpetual taker fee rate 0.05%
            fee_usd = res["qty"] * res["price"] * 0.0005
            res["fee_usd"] = fee_usd
            return res
        else:
            return real_exchange.execute_real_binance_spot(
                symbol, side, qty, self.api_key, self.api_secret
            )

    def get_balance(self) -> float:
        """Retrieve Binance available cash balance."""
        try:
            bals = real_exchange.fetch_real_balances(
                self.api_key, self.api_secret, None, None, True
            )
            return bals.get("cash", 0.0)
        except Exception:
            return 0.0
