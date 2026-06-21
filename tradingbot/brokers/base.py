"""Base Broker Abstraction — the only thing the core engine, strategies, and
dashboard ever see. New brokers are added by writing one adapter against this
interface. See CLAUDE.md, "Architecture rules" + "Live-trading safety gate".

This interface is the contract every broker adapter must satisfy. The Phase 1
proof-of-done is `tests/test_broker_contract.py` — that the paper adapter
passes every method, and the interface itself is importable and stable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseBroker(ABC):
    """Broker-agnostic interface. Every paper or real broker implements this."""

    name: str  # subclass sets: "paper", "binance-spot", "binance-perp", "alpaca", "ibkr"

    # --- Market data --------------------------------------------------------

    @abstractmethod
    def get_quote(self, symbol: str) -> dict:
        """Return a live quote envelope for `symbol`.

        Required keys: symbol, bid, ask (or price), fetched_at_utc, source_url,
        response_hash. The envelope is the honesty contract — the same shape
        `tradingbot.prices` returns — so any fill can be re-checked later.

        Raises on network failure. NEVER returns a fabricated price.
        """
        raise NotImplementedError

    # --- Order management ---------------------------------------------------

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        **kwargs: Any,
    ) -> dict:
        """Place an order. Returns an honesty-envelope fill record.

        For the paper adapter, the fill is simulated against the latest live
        quote (with the slippage/fee model from the engine). For real adapters,
        this method must be a no-op unless that broker's live-trading flag is
        explicitly set (see CLAUDE.md, "Live-trading safety gate").

        Required return keys: order_id, symbol, side, qty, price, fee_usd,
        fee_model (str: "maker"/"taker"/"sec_taf"/etc), filled_at_utc,
        source_url, response_hash.
        """
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel an open order. Returns a small receipt dict."""
        raise NotImplementedError

    # --- Account state ------------------------------------------------------

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Return list of open position dicts: symbol, qty, side, avg_entry,
        unrealized_pnl (computed at the latest live quote)."""
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> float:
        """Available cash / buying power in the account's settlement currency."""
        raise NotImplementedError

    @abstractmethod
    def get_trade_history(self) -> list[dict]:
        """Return immutable, append-only history of fills. See CLAUDE.md,
        "Trade history & audit": a row is never edited or deleted."""
        raise NotImplementedError
