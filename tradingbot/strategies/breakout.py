"""Donchian Channel Breakout Strategy."""
from __future__ import annotations
from tradingbot.strategies.base import BaseStrategy


class DonchianBreakout(BaseStrategy):
    def __init__(self, period: int = 20):
        super().__init__(name=f"Donchian_Breakout_{period}")
        self.period = period
        self.position_open = False

    def next(self, current_time: int, price: float, history: list[dict]) -> str:
        if len(history) < self.period + 1:
            return "HOLD"

        # Previous N candles (excluding the current one at index -1)
        prev_candles = history[-(self.period + 1) : -1]
        highs = [float(c["high"]) for c in prev_candles]
        lows = [float(c["low"]) for c in prev_candles]

        channel_high = max(highs)
        channel_low = min(lows)

        # Breakout BUY signal
        if price > channel_high:
            if not self.position_open:
                self.position_open = True
                return "BUY"

        # Breakout SELL signal
        elif price < channel_low:
            if self.position_open:
                self.position_open = False
                return "SELL"

        return "HOLD"
