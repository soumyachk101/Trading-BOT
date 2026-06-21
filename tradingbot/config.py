"""Central config. Handles paper balance defaults and environment loading for real trading."""
from __future__ import annotations

import os

# Helper to load .env variables without external packages
def _load_env() -> dict[str, str]:
    env = {}
    # Search in project root (parent of tradingbot folder)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(root, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
        except Exception:
            pass
    return env

_env = _load_env()

# Mode Switch
LIVE_TRADING: bool = _env.get("LIVE_TRADING", "False").lower() in ("true", "1", "yes")

# API Keys
BINANCE_API_KEY: str | None = _env.get("BINANCE_API_KEY")
BINANCE_API_SECRET: str | None = _env.get("BINANCE_API_SECRET")
ALPACA_API_KEY: str | None = _env.get("ALPACA_API_KEY")
ALPACA_API_SECRET: str | None = _env.get("ALPACA_API_SECRET")
ALPACA_IS_PAPER: bool = _env.get("ALPACA_IS_PAPER", "True").lower() in ("true", "1", "yes")

# Paper-only money configurations
PAPER_BALANCE_USD: float = 10_000.0

# Asset configuration defaults
DEFAULT_CRYPTO_SYMBOL: str = "BTCUSDT"      # Binance spot ticker
DEFAULT_PERP_SYMBOL: str = "BTCUSDT"        # Binance USDⓈ-M perpetual ticker
DEFAULT_STOCK_SYMBOL: str = "AAPL"          # Yahoo / Stooq

# Slippage model buffer on top of the live top-of-book spread, in basis points.
SLIPPAGE_BUFFER_BPS: float = 2.0