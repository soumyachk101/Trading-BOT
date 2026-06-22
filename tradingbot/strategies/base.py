"""Base strategy interface."""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name
        self.decision_memory: list[dict] = []

    @abstractmethod
    def next(self, current_time: int, price: float, history: list[dict]) -> str:
        """Process the next candle and return 'BUY', 'SELL', or 'HOLD'.

        Args:
            current_time: UNIX timestamp of the current candle.
            price: Close price of the current candle.
            history: List of preceding candles, including the current one.
        """
        pass
