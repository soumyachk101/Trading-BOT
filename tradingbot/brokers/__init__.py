"""Broker package.

This package is the single chokepoint between the engine/strategies/dashboard
and the outside world. Per CLAUDE.md, "Architecture rules":

  - "Every broker — paper or real — implements one common interface."
  - "The paper broker adapter is the default and only adapter active, always
    — until the live-trading gate below is manually opened by a human."

The per-broker live-trading gate lives in `tradingbot.brokers.live_gate`. The
paper adapter is the only one active in this build.
"""
from __future__ import annotations

from tradingbot.brokers.base import BaseBroker
from tradingbot.brokers.paper_adapter import PaperBroker
from tradingbot.brokers.live_gate import (
    BrokerName,
    LiveTradingNotEnabled,
    assert_live_ok,
    is_live_enabled,
)

# Existing adapters are kept in the tree as code, but they are NOT active in
# this build. They will be hardened in Phase 5 (cite every fee in SOURCES.md,
# remove the hardcoded numbers, stop swallowing exceptions) and gated behind
# the per-broker live flag.
from tradingbot.brokers.binance_adapter import BinanceBrokerAdapter
from tradingbot.brokers.alpaca_adapter import AlpacaBrokerAdapter
from tradingbot.brokers.ibkr_adapter import IBKRBrokerAdapter
from tradingbot.brokers.mock_adapter import MockBrokerAdapter


__all__ = [
    "BaseBroker",
    "PaperBroker",
    "BrokerName",
    "LiveTradingNotEnabled",
    "assert_live_ok",
    "is_live_enabled",
    "BinanceBrokerAdapter",
    "AlpacaBrokerAdapter",
    "IBKRBrokerAdapter",
    "MockBrokerAdapter",
]
