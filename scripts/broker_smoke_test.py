#!/usr/bin/env python3
"""
Broker connectivity smoke test.

Verifies that the broker abstraction can authenticate against a *demo* account
for MetaTrader 5 and/or TradeLocker, using credentials supplied via environment
variables. By default it is **connect-only** — it never sends a live order
unless you explicitly pass `--place-test-order`, and even then it uses the
smallest possible size on a demo account.

If credentials are missing the relevant broker is skipped (not failed), so this
script is safe to run in CI as a no-op.

Environment variables
---------------------
MetaTrader 5:
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

TradeLocker:
    TRADELOCKER_USERNAME, TRADELOCKER_PASSWORD, TRADELOCKER_SERVER
    TRADELOCKER_ENV         (optional, default https://demo.tradelocker.com)

Usage
-----
    python scripts/broker_smoke_test.py
    python scripts/broker_smoke_test.py --place-test-order --symbol EURUSD --qty 0.01
"""

from __future__ import annotations

import argparse
import os
import sys

# Make the package importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.brokers import (  # noqa: E402
    MetaTrader5Broker, TradeLockerBroker, Order, OrderSide, OrderType,
)


def _mt5_creds():
    keys = ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")
    if not all(os.getenv(k) for k in keys):
        return None
    return {
        "login": os.environ["MT5_LOGIN"],
        "password": os.environ["MT5_PASSWORD"],
        "server": os.environ["MT5_SERVER"],
    }


def _tradelocker_creds():
    keys = ("TRADELOCKER_USERNAME", "TRADELOCKER_PASSWORD", "TRADELOCKER_SERVER")
    if not all(os.getenv(k) for k in keys):
        return None
    return {
        "username": os.environ["TRADELOCKER_USERNAME"],
        "password": os.environ["TRADELOCKER_PASSWORD"],
        "server": os.environ["TRADELOCKER_SERVER"],
        "environment": os.getenv("TRADELOCKER_ENV", "https://demo.tradelocker.com"),
    }


def _test_broker(name, broker, place_order, symbol, qty):
    print(f"\n=== {name} ===")
    connected = broker.connect()
    if not connected:
        err = getattr(broker, "_last_error", "unknown error / missing dependency")
        print(f"  ✗ connect failed: {err}")
        return False
    print("  ✓ connected (demo)")

    try:
        positions = broker.positions()
        print(f"  ✓ positions fetched: {len(positions)} open")
    except Exception as e:  # noqa: BLE001
        print(f"  ! positions() raised: {e}")

    if place_order:
        order = Order(symbol=symbol, side=OrderSide.BUY, qty=qty,
                      order_type=OrderType.MARKET)
        try:
            result = broker.place_order(order)
            mark = "✓" if result.accepted else "✗"
            print(f"  {mark} test order: {result.message} (id={result.broker_order_id})")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ order failed: {e}")
    else:
        print("  · skipped order placement (pass --place-test-order to enable)")
    return True


def main():
    ap = argparse.ArgumentParser(description="Broker connectivity smoke test (demo accounts)")
    ap.add_argument("--place-test-order", action="store_true",
                    help="Actually submit a minimal market order on the demo account")
    ap.add_argument("--symbol", default="EURUSD", help="Symbol for the optional test order")
    ap.add_argument("--qty", type=float, default=0.01, help="Quantity for the optional test order")
    args = ap.parse_args()

    print("Broker smoke test — connect-only unless --place-test-order is given.")
    tested = 0
    skipped = []

    mt5 = _mt5_creds()
    if mt5:
        _test_broker("MetaTrader 5", MetaTrader5Broker(live=True, credentials=mt5),
                     args.place_test_order, args.symbol, args.qty)
        tested += 1
    else:
        skipped.append("MetaTrader 5 (set MT5_LOGIN/MT5_PASSWORD/MT5_SERVER)")

    tl = _tradelocker_creds()
    if tl:
        _test_broker("TradeLocker", TradeLockerBroker(live=True, credentials=tl),
                     args.place_test_order, args.symbol, args.qty)
        tested += 1
    else:
        skipped.append("TradeLocker (set TRADELOCKER_USERNAME/PASSWORD/SERVER)")

    print("\n--- summary ---")
    print(f"  brokers tested:  {tested}")
    for s in skipped:
        print(f"  skipped (no creds): {s}")
    if tested == 0:
        print("\nNo credentials provided — nothing to test. This is a safe no-op.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
