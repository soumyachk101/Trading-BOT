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

        import datetime as dt
        time_str = dt.datetime.fromtimestamp(current_time, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sentiment = getattr(self, "latest_sentiment", 0.0)
        signal = "HOLD"
        reason = f"Fast SMA ({fast_now:.2f}) vs Slow SMA ({slow_now:.2f}). (Sentiment: {sentiment:+.2f})"

        # Crossover BUY signal: fast SMA crosses above slow SMA
        if fast_prev <= slow_prev and fast_now > slow_now:
            # Vet with news sentiment if available
            if sentiment < -0.25:
                import logging
                logging.getLogger("honest-bot.strategies.sma").info(
                    f"[{self.name}] BUY signal vetoed due to negative news sentiment: {sentiment:.2f}"
                )
                signal = "HOLD"
                reason = f"SMA Crossover BUY signal vetoed due to negative news sentiment ({sentiment:+.2f} < -0.25)"
            elif not self.position_open:
                self.position_open = True
                signal = "BUY"
                reason = f"SMA Crossover BUY triggered: Fast SMA ({fast_now:.2f}) crossed above Slow SMA ({slow_now:.2f}) (Sentiment: {sentiment:+.2f})"
            else:
                signal = "HOLD"
                reason = f"SMA Crossover BUY signal generated but position is already open"

        # Crossunder SELL signal: fast SMA crosses below slow SMA
        elif fast_prev >= slow_prev and fast_now < slow_now:
            if self.position_open:
                self.position_open = False
                signal = "SELL"
                reason = f"SMA Crossunder SELL triggered: Fast SMA ({fast_now:.2f}) crossed below Slow SMA ({slow_now:.2f}) (Sentiment: {sentiment:+.2f})"
            else:
                signal = "HOLD"
                reason = f"SMA Crossunder SELL signal generated but no active position to close"

        self.decision_memory.append({
            "timestamp": time_str,
            "price": price,
            "signal": signal,
            "fast_sma": fast_now,
            "slow_sma": slow_now,
            "sentiment": sentiment,
            "reason": reason
        })
        if len(self.decision_memory) > 100:
            self.decision_memory.pop(0)

        return signal
