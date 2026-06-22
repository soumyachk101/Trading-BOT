"""AI Machine Learning Predictor Strategy with Online Feedback.

Implements a pure-Python Logistic Regression model that learns online from
its actual trading performance (PnL feedback loop).
"""
from __future__ import annotations

import math
import logging
from tradingbot.strategies.base import BaseStrategy

logger = logging.getLogger("honest-bot.strategies.ml_predictor")


class LogisticRegressionModel:
    def __init__(self, lookback: int = 5, train_window: int = 100):
        self.lookback = lookback
        self.train_window = train_window
        self.weights = [0.0] * (lookback + 1)  # weights + bias
        self.trained = False
        self.weights_history: list[dict] = []

    def _sigmoid(self, z: float) -> float:
        z = max(-50.0, min(50.0, z))
        return 1.0 / (1.0 + math.exp(-z))

    def train(self, history: list[dict]):
        if len(history) < self.train_window + self.lookback + 1:
            return

        closes = [float(c["close"]) for c in history]
        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            returns.append((closes[i] - prev) / prev if prev != 0 else 0.0)

        # Build feature matrix X and label vector y
        X = []
        y = []
        for i in range(self.lookback, len(returns)):
            features = returns[i - self.lookback : i]
            X.append(features)
            y.append(1.0 if returns[i] > 0 else 0.0)

        # Slice to train window size
        X = X[-self.train_window :]
        y = y[-self.train_window :]

        # Train weights using Stochastic Gradient Descent (SGD)
        self.weights = [0.0] * (self.lookback + 1)
        learning_rate = 0.05
        epochs = 100

        for _ in range(epochs):
            for i in range(len(X)):
                z = self.weights[0]
                for j in range(self.lookback):
                    z += X[i][j] * self.weights[j + 1]

                pred = self._sigmoid(z)
                error = y[i] - pred

                self.weights[0] += learning_rate * error * 1.0
                for j in range(self.lookback):
                    self.weights[j + 1] += learning_rate * error * X[i][j]

        self.trained = True

    def adjust_weights_from_pnl(self, X_entry: list[float], pnl_pct: float):
        """Online Feedback: Adjust weights dynamically based on closed-trade PnL."""
        if len(X_entry) != self.lookback:
            return
 
        learning_rate = 0.05
        # Feedback multiplier: positive reinforcement for profit, negative for loss
        direction = 1.0 if pnl_pct >= 0.0 else -1.0
        magnitude = min(1.5, abs(pnl_pct) * 10.0)  # scale updates by PnL size
 
        old_weights = list(self.weights)
 
        # Apply online SGD step adjustment
        self.weights[0] += learning_rate * direction * magnitude * 1.0  # bias
        for j in range(self.lookback):
            self.weights[j + 1] += learning_rate * direction * magnitude * X_entry[j]
 
        import datetime as dt
        self.weights_history.append({
            "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pnl_pct": pnl_pct,
            "weights": list(self.weights),
            "bias_delta": self.weights[0] - old_weights[0]
        })
        if len(self.weights_history) > 100:
            self.weights_history.pop(0)

        logger.info(
            f"Online Learning Step applied. PnL Return: {pnl_pct*100:+.2f}%. "
            f"Weights shifted. Bias delta: {self.weights[0] - old_weights[0]:+.4f}"
        )

    def predict(self, history: list[dict]) -> float | None:
        if not self.trained or len(history) < self.lookback + 1:
            return None

        closes = [float(c["close"]) for c in history[-(self.lookback + 1) :]]
        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            returns.append((closes[i] - prev) / prev if prev != 0 else 0.0)

        # Compute dot product
        z = self.weights[0]
        for j in range(self.lookback):
            z += returns[j] * self.weights[j + 1]

        return self._sigmoid(z)


class MLPredictorStrategy(BaseStrategy):
    def __init__(self, lookback: int = 5, train_window: int = 100):
        super().__init__(name=f"AI_ML_Predictor_{lookback}")
        self.lookback = lookback
        self.train_window = train_window
        self.model = LogisticRegressionModel(lookback, train_window)
        self.position_open = False
        self.ticks_since_train = 0
        self.last_buy_features: list[float] | None = None

    def record_trade_feedback(self, pnl_pct: float):
        """Callback from engine to enforce the online feedback loop."""
        if self.last_buy_features is not None:
            self.model.adjust_weights_from_pnl(self.last_buy_features, pnl_pct)
            self.last_buy_features = None

    def next(self, current_time: int, price: float, history: list[dict]) -> str:
        if len(history) < self.train_window + self.lookback + 2:
            return "HOLD"
 
        if not self.model.trained or self.ticks_since_train >= 10:
            self.model.train(history[:-1])
            self.ticks_since_train = 0
        else:
            self.ticks_since_train += 1
 
        pred = self.model.predict(history)
        if pred is None:
            return "HOLD"
 
        import datetime as dt
        time_str = dt.datetime.fromtimestamp(current_time, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sentiment = getattr(self, "latest_sentiment", 0.0)
        signal = "HOLD"
        reason = f"ML Predictor probability is {pred*100:.1f}%. (Sentiment: {sentiment:+.2f})"

        # BUY trigger: probability > 55%
        if pred > 0.55:
            # Vet with news sentiment if available
            if sentiment < -0.25:
                signal = "HOLD"
                reason = f"ML Predictor BUY signal vetoed due to negative news sentiment ({sentiment:+.2f} < -0.25)"
                logger.info(f"[{self.name}] BUY signal vetoed due to negative news sentiment: {sentiment:.2f}")
            elif not self.position_open:
                # Capture feature values at entry point
                closes = [float(c["close"]) for c in history[-(self.lookback + 1) :]]
                returns = []
                for k in range(1, len(closes)):
                    prev = closes[k - 1]
                    returns.append((closes[k] - prev) / prev if prev != 0 else 0.0)
                self.last_buy_features = returns
                
                self.position_open = True
                signal = "BUY"
                reason = f"ML Predictor BUY triggered with probability {pred*100:.1f}% (Sentiment: {sentiment:+.2f})"
            else:
                signal = "HOLD"
                reason = f"ML Predictor BUY signal generated but position is already open"
                
        # SELL trigger: probability < 45%
        elif pred < 0.45:
            if self.position_open:
                self.position_open = False
                signal = "SELL"
                reason = f"ML Predictor SELL triggered with probability {pred*100:.1f}% (Sentiment: {sentiment:+.2f})"
            else:
                signal = "HOLD"
                reason = f"ML Predictor SELL signal generated but no active position to close"

        self.decision_memory.append({
            "timestamp": time_str,
            "price": price,
            "signal": signal,
            "probability": pred,
            "sentiment": sentiment,
            "reason": reason
        })
        if len(self.decision_memory) > 100:
            self.decision_memory.pop(0)

        return signal
