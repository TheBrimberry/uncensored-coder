"""
Broker / execution abstraction.

One uniform `Broker` interface across the venues the user asked for:
  * TradeLocker  (multi-asset FX/CFD/crypto brokers)
  * MetaTrader 5 (FX/"4X", CFD, futures)
  * ccxt         (crypto exchanges)
  * Alpaca       (US stocks/crypto, paper trading)

Safety model
------------
Every broker defaults to **paper / dry-run** mode. Placing a *live* order
requires explicitly constructing the broker with `live=True` AND valid
credentials. Without credentials the broker simulates fills locally so the full
agent loop can be exercised without risking capital.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class Order:
    symbol: str
    side: OrderSide
    qty: float
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class OrderResult:
    accepted: bool
    broker: str
    order: Order
    broker_order_id: Optional[str] = None
    simulated: bool = True
    message: str = ""


@dataclass
class Position:
    symbol: str
    qty: float
    avg_price: float


class Broker:
    """Base broker. Subclasses override `_submit_live`; base simulates."""

    name = "base"

    def __init__(self, live: bool = False, credentials: Optional[Dict[str, str]] = None):
        self.live = live
        self.credentials = credentials or {}
        self._paper_positions: Dict[str, Position] = {}
        self._connected = False

    # -- public API --------------------------------------------------------
    def connect(self) -> bool:
        """Attempt a real connection; fall back to paper mode on failure."""
        if self.live and self.credentials:
            try:
                self._connected = self._connect_live()
                return self._connected
            except Exception as e:  # noqa: BLE001
                self._connected = False
                self._last_error = str(e)
        self._connected = False
        return False

    def place_order(self, order: Order) -> OrderResult:
        self._validate(order)
        if self.live and self._connected:
            return self._submit_live(order)
        return self._simulate(order)

    def positions(self) -> List[Position]:
        if self.live and self._connected:
            return self._positions_live()
        return list(self._paper_positions.values())

    # -- guards ------------------------------------------------------------
    def _validate(self, order: Order) -> None:
        if order.qty <= 0:
            raise ValueError("Order quantity must be positive.")
        if order.order_type == OrderType.LIMIT and order.price is None:
            raise ValueError("Limit orders require a price.")

    # -- paper simulation --------------------------------------------------
    def _simulate(self, order: Order) -> OrderResult:
        fill = order.price or 0.0
        pos = self._paper_positions.get(order.symbol)
        signed = order.qty if order.side == OrderSide.BUY else -order.qty
        if pos is None:
            self._paper_positions[order.symbol] = Position(order.symbol, signed, fill)
        else:
            pos.qty += signed
        return OrderResult(
            accepted=True, broker=self.name, order=order, simulated=True,
            message=f"[PAPER] {order.side.value} {order.qty} {order.symbol} simulated.",
        )

    # -- live hooks (overridden by subclasses) -----------------------------
    def _connect_live(self) -> bool:  # pragma: no cover - needs creds
        raise NotImplementedError

    def _submit_live(self, order: Order) -> OrderResult:  # pragma: no cover
        raise NotImplementedError

    def _positions_live(self) -> List[Position]:  # pragma: no cover
        return []


class TradeLockerBroker(Broker):
    """TradeLocker REST integration (FX/CFD/crypto multi-asset brokers)."""

    name = "tradelocker"

    def _connect_live(self) -> bool:  # pragma: no cover - needs creds
        from tradelocker import TLAPI  # type: ignore
        self._api = TLAPI(
            environment=self.credentials.get("environment", "https://demo.tradelocker.com"),
            username=self.credentials["username"],
            password=self.credentials["password"],
            server=self.credentials["server"],
        )
        return True

    def _submit_live(self, order: Order) -> OrderResult:  # pragma: no cover
        instrument_id = self._api.get_instrument_id_from_symbol_name(order.symbol)
        oid = self._api.create_order(
            instrument_id=instrument_id,
            quantity=order.qty,
            side=order.side.value,
            type_=order.order_type.value,
            price=order.price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
        )
        return OrderResult(True, self.name, order, str(oid), simulated=False,
                           message="TradeLocker order submitted.")


class MetaTrader5Broker(Broker):
    """MetaTrader 5 integration for FX/'4X' and CFDs."""

    name = "metatrader5"

    def _connect_live(self) -> bool:  # pragma: no cover - needs MT5 terminal
        import MetaTrader5 as mt5  # type: ignore
        self._mt5 = mt5
        return bool(mt5.initialize(
            login=int(self.credentials["login"]),
            password=self.credentials["password"],
            server=self.credentials["server"],
        ))

    def _submit_live(self, order: Order) -> OrderResult:  # pragma: no cover
        mt5 = self._mt5
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.qty,
            "type": mt5.ORDER_TYPE_BUY if order.side == OrderSide.BUY else mt5.ORDER_TYPE_SELL,
            "sl": order.stop_loss or 0.0,
            "tp": order.take_profit or 0.0,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(ok, self.name, order,
                           str(getattr(result, "order", "")), simulated=False,
                           message=getattr(result, "comment", "MT5 order sent."))


class CCXTBroker(Broker):
    """Crypto execution via ccxt across 100+ exchanges."""

    name = "ccxt"

    def __init__(self, exchange: str = "binance", live: bool = False,
                 credentials: Optional[Dict[str, str]] = None):
        super().__init__(live, credentials)
        self.exchange_id = exchange

    def _connect_live(self) -> bool:  # pragma: no cover - needs api keys
        import ccxt  # type: ignore
        klass = getattr(ccxt, self.exchange_id)
        self._ex = klass({
            "apiKey": self.credentials.get("apiKey"),
            "secret": self.credentials.get("secret"),
            "enableRateLimit": True,
        })
        return True

    def _submit_live(self, order: Order) -> OrderResult:  # pragma: no cover
        res = self._ex.create_order(order.symbol, order.order_type.value,
                                    order.side.value, order.qty, order.price)
        return OrderResult(True, self.name, order, str(res.get("id")), simulated=False,
                           message="ccxt order created.")


class AlpacaBroker(Broker):
    """US stocks/crypto via Alpaca (defaults to paper endpoint)."""

    name = "alpaca"

    def _connect_live(self) -> bool:  # pragma: no cover - needs keys
        from alpaca.trading.client import TradingClient  # type: ignore
        self._client = TradingClient(
            self.credentials["api_key"], self.credentials["secret_key"],
            paper=self.credentials.get("paper", True),
        )
        return True

    def _submit_live(self, order: Order) -> OrderResult:  # pragma: no cover
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest  # type: ignore
        from alpaca.trading.enums import OrderSide as ApSide, TimeInForce  # type: ignore
        side = ApSide.BUY if order.side == OrderSide.BUY else ApSide.SELL
        if order.order_type == OrderType.LIMIT:
            req = LimitOrderRequest(symbol=order.symbol, qty=order.qty, side=side,
                                    time_in_force=TimeInForce.DAY, limit_price=order.price)
        else:
            req = MarketOrderRequest(symbol=order.symbol, qty=order.qty, side=side,
                                     time_in_force=TimeInForce.DAY)
        res = self._client.submit_order(req)
        return OrderResult(True, self.name, order, str(res.id), simulated=False,
                           message="Alpaca order submitted.")


BROKERS: Dict[str, type] = {
    "tradelocker": TradeLockerBroker,
    "metatrader5": MetaTrader5Broker,
    "ccxt": CCXTBroker,
    "alpaca": AlpacaBroker,
    "paper": Broker,
}


def get_broker(name: str, **kwargs) -> Broker:
    """Factory. Unknown names fall back to the safe paper broker."""
    klass = BROKERS.get(name.lower(), Broker)
    return klass(**kwargs)
