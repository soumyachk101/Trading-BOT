"""Per-broker live-trading gate, per CLAUDE.md "Live-trading safety gate".

The rules, in plain English:
  1. A real order can only fire if a human has manually set a per-broker flag
     (e.g. BINANCE_LIVE_TRADING=True) in config or .env — NOT a global switch.
  2. That broker's adapter uses its own API key with the minimum possible
     permissions (no withdrawal, position-size caps where the broker supports it).
  3. Phase 8's honest paper-trading verdict has been delivered and read.

This module is the single chokepoint. Real adapters call `assert_live_ok(broker)`
before placing any real order. If the per-broker flag is off, the call raises
`LiveTradingNotEnabled` and the order is refused. No code path — including the
adaptive learning layer — can flip the flag. Only a human, by hand, in a config
file outside the bot's own write access.
"""
from __future__ import annotations

import os
from typing import Literal


BrokerName = Literal["binance-spot", "binance-perp", "alpaca", "ibkr"]


class LiveTradingNotEnabled(RuntimeError):
    """Raised when a real order is attempted without a per-broker live flag."""


def _env_flag(broker: str) -> bool:
    """Read the per-broker flag from the environment. Strictly opt-in."""
    key = f"{broker.upper().replace('-', '_')}_LIVE_TRADING"
    val = os.environ.get(key, "false").lower()
    return val in ("true", "1", "yes")


def is_live_enabled(broker: BrokerName) -> bool:
    """Public read-only check. Used by the dashboard, NOT by adapters to gate."""
    return _env_flag(broker)


def assert_live_ok(broker: BrokerName) -> None:
    """The gate. Real adapters call this before placing a real order.

    Raises LiveTradingNotEnabled if the per-broker flag is not set. Never
    silently allows a real order through, never silently substitutes a paper
    fill (which would be the exact anti-pattern CLAUDE.md bans).
    """
    if not _env_flag(broker):
        raise LiveTradingNotEnabled(
            f"Live trading is OFF for broker '{broker}'. "
            f"Set {broker.upper().replace('-', '_')}_LIVE_TRADING=True in your "
            f"environment (and only after Phase 8's honest paper-trading verdict) "
            f"to enable real orders. See CLAUDE.md 'Live-trading safety gate'."
        )
