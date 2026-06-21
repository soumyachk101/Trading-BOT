"""Base Broker Abstraction class."""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseBroker(ABC):
    @abstractmethod
    def execute_market_order(self, symbol: str, side: str, qty: float, **kwargs) -> dict:
        """Execute a market order on the broker/exchange.

        Args:
            symbol: Asset symbol (e.g. BTCUSDT, AAPL).
            side: 'BUY' or 'SELL'.
            qty: Quantity to trade.
            **kwargs: Extra parameters like leverage.

        Returns:
            A dictionary containing: price (float), qty (float), fee_usd (float), raw_response (dict).
        """
        pass

    @abstractmethod
    def get_balance(self) -> float:
        """Retrieve available cash or buying power from the account."""
        pass
