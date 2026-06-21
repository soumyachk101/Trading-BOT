"""Paper broker adapter — the default and only active adapter in this build.

Per CLAUDE.md, "Architecture rules":
  - "The paper broker adapter is the default and only adapter active, always
    — until the live-trading gate below is manually opened by a human."
  - "The core engine, strategies, and dashboard never know which broker
    they're talking to." So this file is the only place the engine and the
    paper reality meet.

This adapter is the Phase 1+2 proof-of-done for the broker contract. It must
implement every method on `BaseBroker`, fill at live prices (with the slippage
+ fee model from the engine), and write one immutable row per fill.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from tradingbot.brokers.base import BaseBroker
from tradingbot import prices


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class PaperBroker(BaseBroker):
    """The paper broker. All fills are simulated against live public prices."""

    name = "paper"

    def __init__(self, initial_cash_usd: float = 10_000.0):
        self.initial_cash_usd = initial_cash_usd
        self.cash: float = initial_cash_usd
        # positions: symbol -> {qty, avg_entry, side}
        self.positions: dict[str, dict] = {}
        # open orders: order_id -> order dict
        self.open_orders: dict[str, dict] = {}
        # immutable history of fills (append-only — never edit/delete)
        self.history: list[dict] = []
        # cached last quote per symbol, so a paper fill can be reconstructed
        self._last_quote: dict[str, dict] = {}

    # --- Market data --------------------------------------------------------

    def get_quote(self, symbol: str) -> dict:
        """Live quote. For spot we use Binance bookTicker; for stocks Yahoo.

        Raises on failure. We do NOT cache stale prices and we do NOT invent
        a price on network failure.
        """
        symbol_u = symbol.upper()
        if symbol_u.endswith("USDT") and len(symbol_u) >= 6:
            env = prices.fetch_spot_book_top(symbol_u)
            env["bid"] = env.get("bid_price")
            env["ask"] = env.get("ask_price")
        else:
            # Treat as a stock ticker (e.g. AAPL)
            env = prices.fetch_stock_price(symbol_u)
            env["bid"] = env["price"]
            env["ask"] = env["price"]
        self._last_quote[symbol_u] = env
        return env

    # --- Order management ---------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "market",
        **kwargs: Any,
    ) -> dict:
        if order_type != "market":
            # Limit/stop etc. are out of scope for the paper adapter v1.
            raise NotImplementedError(
                f"PaperBroker v1 supports market orders only, got order_type={order_type!r}"
            )
        if qty <= 0:
            raise ValueError(f"qty must be > 0, got {qty!r}")
        side_u = side.upper()
        if side_u not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")

        symbol_u = symbol.upper()
        quote = self.get_quote(symbol_u)  # live fetch — fails honestly if offline

        # Fill at the touch side of the book (ask on buy, bid on sell).
        # This is what a marketable order would hit in a real book.
        if side_u == "BUY":
            fill_price = float(quote["ask"])
        else:
            fill_price = float(quote["bid"])

        # Conservative paper-broker fee model: 0 bps for the paper engine
        # itself. Real fees are layered on by the strategy / engine that
        # sits on top, using the live commission rate the venue publishes.
        # We leave a clear hook here and return fee_model="paper" so the
        # dashboard can show the wire is honest.
        fee_usd = 0.0
        fee_model = "paper"

        # Update positions and cash
        if symbol_u not in self.positions:
            self.positions[symbol_u] = {"qty": 0.0, "avg_entry": 0.0, "side": "FLAT"}

        pos = self.positions[symbol_u]
        signed_qty = qty if side_u == "BUY" else -qty

        if pos["qty"] == 0 or (pos["qty"] > 0 and signed_qty > 0) or (pos["qty"] < 0 and signed_qty < 0):
            # Opening or adding to position
            new_qty = pos["qty"] + signed_qty
            new_notional = abs(pos["qty"]) * pos["avg_entry"] + qty * fill_price
            pos["avg_entry"] = new_notional / abs(new_qty) if new_qty != 0 else 0.0
            pos["qty"] = new_qty
        else:
            # Reducing or flipping — realized P&L is computed by the engine
            # layer, not here. We just adjust qty honestly.
            pos["qty"] += signed_qty

        # Cash moves opposite to the position
        self.cash -= signed_qty * fill_price  # buy drains cash, sell adds

        pos["side"] = "LONG" if pos["qty"] > 0 else ("SHORT" if pos["qty"] < 0 else "FLAT")

        fill = {
            "order_id": str(uuid.uuid4()),
            "symbol": symbol_u,
            "side": side_u,
            "qty": float(qty),
            "price": float(fill_price),
            "fee_usd": float(fee_usd),
            "fee_model": fee_model,
            "filled_at_utc": _utc_now_iso(),
            "source_url": quote.get("source_url"),
            "response_hash": quote.get("response_hash"),
        }
        fill["fill_hash"] = _hash_payload(fill)
        self.history.append(fill)
        return fill

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        # Paper v1 has no working open orders (all market orders fill immediately).
        # We still satisfy the interface: removing a non-existent order is a no-op.
        return {
            "order_id": order_id,
            "symbol": symbol.upper(),
            "cancelled_at_utc": _utc_now_iso(),
            "status": "noop_paper_v1_has_no_working_orders",
        }

    # --- Account state ------------------------------------------------------

    def get_positions(self) -> list[dict]:
        out = []
        for sym, pos in self.positions.items():
            if pos["qty"] == 0:
                continue
            last_quote = self._last_quote.get(sym, {})
            mark = last_quote.get("ask") or last_quote.get("price") or pos["avg_entry"]
            unrealized = pos["qty"] * (float(mark) - pos["avg_entry"])
            out.append(
                {
                    "symbol": sym,
                    "qty": pos["qty"],
                    "side": pos["side"],
                    "avg_entry": pos["avg_entry"],
                    "mark": float(mark),
                    "unrealized_pnl": float(unrealized),
                }
            )
        return out

    def get_balance(self) -> float:
        return float(self.cash)

    def get_trade_history(self) -> list[dict]:
        # Return a copy so the caller can't mutate the immutable ledger.
        return [dict(row) for row in self.history]
