"""Simple Moving Average (SMA) Crossover Strategy."""
from __future__ import annotations
from tradingbot.strategies.base import BaseStrategy


class SMACrossover(BaseStrategy):
    def __init__(self, fast_period: int = 10, slow_period: int = 50):
        super().__init__(name=f"SMA_Crossover_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position_open = False  # Track simple state for backtest signaling

    def _calc_sma(self, history: list[dict], period: int) -> float | None:
        if len(history) < period:
            return None
        closes = [float(c["close"]) for c in history[-period:]]
        return sum(closes) / period

    def next(self, current_time: int, price: float, history: list[dict]) -> str:
        # We need enough historical candles
        if len(history) < self.slow_period + 1:
            return "HOLD"

        # Calculate current SMA values
        fast_now = self._calc_sma(history, self.fast_period)
        slow_now = self._calc_sma(history, self.slow_period)

        # Calculate previous SMA values (shifting history by 1)
        fast_prev = self._calc_sma(history[:-1], self.fast_period)
        slow_prev = self._calc_sma(history[:-1], self.slow_period)

        if fast_now is None or slow_now is None or fast_prev is None or slow_prev is None:
            return "HOLD"

        # Crossover BUY signal: fast SMA crosses above slow SMA
        if fast_prev <= slow_prev and fast_now > slow_now:
            # Vet with news sentiment if available
            sentiment = getattr(self, "latest_sentiment", 0.0)
            if sentiment < -0.25:
                import logging
                logging.getLogger("honest-bot.strategies.sma").info(
                    f"[{self.name}] BUY signal vetoed due to negative news sentiment: {sentiment:.2f}"
                )
                return "HOLD"
            if not self.position_open:
                self.position_open = True
                return "BUY"

        # Crossunder SELL signal: fast SMA crosses below slow SMA
        elif fast_prev >= slow_prev and fast_now < slow_now:
            if self.position_open:
                self.position_open = False
                return "SELL"

        return "HOLD"
