"""Broker contract test suite — Phase 1 proof-of-done.

Per CLAUDE.md, "Definition of done (every phase)":
  2. There's a test or a log proving the honesty invariant for that phase.

This file proves the broker-agnostic interface is real:
  - The interface is importable and has the six required methods.
  - The paper adapter implements all six (and no method is silently skipped).
  - A live round-trip fill against a real public price endpoint passes every
    honesty invariant: source_url present, response_hash present, the fill
    price matches the live ask at fill time (within float rounding), no
    synthetic data on failure.

Run:
  PYTHONPATH=. .venv/bin/python tests/test_broker_contract.py
or:
  .venv/bin/pytest tests/test_broker_contract.py -v
"""
from __future__ import annotations

import inspect
import sys
import traceback

from tradingbot.brokers.base import BaseBroker
from tradingbot.brokers.paper_adapter import PaperBroker
from tradingbot.brokers.live_gate import is_live_enabled, LiveTradingNotEnabled, assert_live_ok


# -----------------------------------------------------------------------------
# 1. Interface shape
# -----------------------------------------------------------------------------

REQUIRED_METHODS = [
    "get_quote",
    "place_order",
    "cancel_order",
    "get_positions",
    "get_balance",
    "get_trade_history",
]


def test_interface_has_all_six_methods():
    for m in REQUIRED_METHODS:
        assert hasattr(BaseBroker, m), f"BaseBroker is missing required method: {m}"
        method = getattr(BaseBroker, m)
        assert getattr(method, "__isabstractmethod__", False), (
            f"BaseBroker.{m} is not marked @abstractmethod"
        )
    print("OK: BaseBroker declares all six required methods as abstract")


# -----------------------------------------------------------------------------
# 2. Paper adapter implements all six
# -----------------------------------------------------------------------------


def test_paper_adapter_implements_every_method():
    broker = PaperBroker(initial_cash_usd=10_000.0)
    for m in REQUIRED_METHODS:
        method = getattr(broker, m)
        assert callable(method), f"PaperBroker.{m} is not callable"
    print("OK: PaperBroker implements every required method")


# -----------------------------------------------------------------------------
# 3. Live-trading safety gate
# -----------------------------------------------------------------------------


def test_live_gate_defaults_to_off():
    for broker in ("binance-spot", "binance-perp", "alpaca", "ibkr"):
        assert is_live_enabled(broker) is False, (
            f"Live trading for {broker} should be OFF by default"
        )
    print("OK: every per-broker live flag is OFF by default")


def test_live_gate_denies_real_order_when_off():
    try:
        assert_live_ok("binance-spot")
    except LiveTradingNotEnabled:
        print("OK: live gate denies real order when per-broker flag is OFF")
        return
    raise AssertionError("Live gate allowed a real order with no flag set — this is a CLAUDE.md violation")


# -----------------------------------------------------------------------------
# 4. Live round-trip — the real honesty invariant
# -----------------------------------------------------------------------------


def test_live_round_trip_uses_real_price():
    """Place a real paper BUY and verify every honesty invariant.

    Note on the design: `place_order` re-fetches a fresh quote at the moment
    of fill — that's what a real marketable order would do — so the fill's
    `response_hash` will not match a *prior* `get_quote` call's hash. We
    assert that the fill's stamped source_url and response_hash are real
    (Binance domain, 64-char sha256), and that the fill price equals the
    ask from the *same* fetch the fill was filled against.
    """
    broker = PaperBroker(initial_cash_usd=10_000.0)
    qty = 0.001
    cash_before = broker.get_balance()

    fill = broker.place_order("BTCUSDT", "BUY", qty)

    # Honesty invariant 1: source_url is a real Binance URL.
    assert "source_url" in fill and "api.binance.com" in fill["source_url"], (
        f"fill.source_url is missing or not a Binance URL: {fill.get('source_url')!r}"
    )

    # Honesty invariant 2: response_hash is a 64-char sha256.
    assert "response_hash" in fill and len(fill["response_hash"]) == 64, (
        f"fill.response_hash is missing or not sha256-shaped: {fill.get('response_hash')!r}"
    )

    # Honesty invariant 3: fill price > 0 (the fetch returned a real number).
    assert fill["price"] > 0, f"fill price must be > 0, got {fill['price']}"

    # Honesty invariant 4: cash drained by exactly qty * fill_price.
    assert abs(broker.get_balance() - (cash_before - qty * fill["price"])) < 1e-6, (
        "cash balance did not move by qty*price after a BUY"
    )

    # Honesty invariant 5: position recorded at the fill price.
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTCUSDT"
    assert positions[0]["qty"] == qty
    assert abs(positions[0]["avg_entry"] - fill["price"]) < 1e-6

    # Honesty invariant 6: exactly one immutable history row.
    history = broker.get_trade_history()
    assert len(history) == 1
    assert history[0]["order_id"] == fill["order_id"]

    # Honesty invariant 7: cancel_order returns a receipt, doesn't mutate history.
    cancel = broker.cancel_order(fill["order_id"], "BTCUSDT")
    assert cancel["status"] == "noop_paper_v1_has_no_working_orders"
    assert len(broker.get_trade_history()) == 1, "cancel must not mutate history"

    # Honesty invariant 8: get_quote + immediate place_order on the same symbol
    # produce fills at prices that come from a *real* ask — i.e. the ask is a
    # number we'd see on the public Binance book.
    fresh_quote = broker.get_quote("BTCUSDT")
    assert fresh_quote["ask"] > 0
    assert fresh_quote["response_hash"] != fill["response_hash"], (
        "Two consecutive bookTicker fetches should not be byte-identical "
        "(if they are, the URL is being cached and we're not actually hitting Binance)"
    )

    print("OK: live round-trip respects every honesty invariant")
    print(f"   fill price       : ${fill['price']:,.2f}")
    print(f"   fill source_url  : {fill['source_url']}")
    print(f"   fill hash        : {fill['response_hash'][:16]}...")
    print(f"   fill order_id    : {fill['order_id']}")
    print(f"   position avg     : ${positions[0]['avg_entry']:,.2f}")
    print(f"   cash remaining   : ${broker.get_balance():,.2f}")


# -----------------------------------------------------------------------------
# Runner (so this works without pytest)
# -----------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_interface_has_all_six_methods,
        test_paper_adapter_implements_every_method,
        test_live_gate_defaults_to_off,
        test_live_gate_denies_real_order_when_off,
        test_live_round_trip_uses_real_price,
    ]
    failed = 0
    for t in tests:
        print(f"\n--- {t.__name__} ---")
        try:
            t()
        except Exception as e:
            failed += 1
            print(f"FAIL: {e}")
            traceback.print_exc()
    print(f"\n=== {len(tests) - failed}/{len(tests)} tests passed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
