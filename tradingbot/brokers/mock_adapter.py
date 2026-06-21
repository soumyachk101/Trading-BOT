"""Mock Paper Broker Adapter."""
from __future__ import annotations

from tradingbot.brokers.base import BaseBroker
from tradingbot.engine import HonestEngine


class MockBrokerAdapter(BaseBroker):
    def __init__(self, engine: HonestEngine, asset_type: str = "SPOT"):
        self.engine = engine
        self.asset_type = asset_type

    def execute_market_order(self, symbol: str, side: str, qty: float, **kwargs) -> dict:
        """Mock order execution using HonestEngine paper logic."""
        if self.asset_type == "SPOT":
            book_env = kwargs.get("book_envelope")
            if not book_env:
                raise ValueError("Spot order requires a book_envelope parameter")
            res = self.engine.execute_spot_market_order(symbol, side, qty, book_env)
        elif self.asset_type == "STOCK":
            price_env = kwargs.get("price_envelope")
            if not price_env:
                raise ValueError("Stock order requires a price_envelope parameter")
            res = self.engine.execute_stock_market_order(symbol, side, qty, price_env)
        elif self.asset_type == "PERP":
            leverage = kwargs.get("leverage", 1.0)
            premium_env = kwargs.get("premium_envelope")
            fee_env = kwargs.get("fee_envelope")
            if not premium_env or not fee_env:
                raise ValueError("Perp order requires premium_envelope and fee_envelope parameters")
            res = self.engine.execute_perp_market_order(symbol, side, qty, leverage, premium_env, fee_env)
        else:
            raise ValueError(f"Unknown asset type: {self.asset_type}")

        return {
            "price": res["price"],
            "qty": res["qty"],
            "fee_usd": res["fee_usd"],
            "raw_response": res,
        }

    def get_balance(self) -> float:
        """Returns the paper simulation cash balance."""
        return self.engine.cash
