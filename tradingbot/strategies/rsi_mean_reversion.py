"""Relative Strength Index (RSI) Mean Reversion Strategy."""
from __future__ import annotations
from tradingbot.strategies.base import BaseStrategy


class RSIMeanReversion(BaseStrategy):
    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        super().__init__(name=f"RSI_Mean_Reversion_{period}")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.position_open = False

    def _calc_rsi(self, history: list[dict]) -> float | None:
        if len(history) < self.period + 1:
            return None

        closes = [float(c["close"]) for c in history]

        # Calculate gains and losses
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff > 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))

        # Initial average gain/loss
        avg_gain = sum(gains[:self.period]) / self.period
        avg_loss = sum(losses[:self.period]) / self.period

        # Wilder's smoothing recursion
        for i in range(self.period, len(gains)):
            avg_gain = (avg_gain * (self.period - 1) + gains[i]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i]) / self.period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def next(self, current_time: int, price: float, history: list[dict]) -> str:
        rsi = self._calc_rsi(history)
        if rsi is None:
            return "HOLD"

        # Buy when oversold
        if rsi < self.oversold:
            if not self.position_open:
                self.position_open = True
                return "BUY"

        # Sell when overbought
        elif rsi > self.overbought:
            if self.position_open:
                self.position_open = False
                return "SELL"

        return "HOLD"
