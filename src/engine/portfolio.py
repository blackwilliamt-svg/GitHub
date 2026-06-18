from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .orders import Order, OrderSide, OrderType, Trade

logger = logging.getLogger(__name__)


@dataclass
class PositionSnapshot:
    timestamp: datetime
    cash: float
    position_size: float
    position_value: float
    total_equity: float
    unrealized_pnl: float


class Portfolio:
    """Tracks cash, positions, orders, and equity curve throughout a backtest."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission_pct: float = 0.003,
        slippage_pct: float = 0.005,
        max_position_pct: float = 1.0,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.max_position_pct = max_position_pct

        self.position_size: float = 0.0
        self.position_avg_price: float = 0.0
        self.position_side: Optional[OrderSide] = None

        self.orders: list[Order] = []
        self.trades: list[Trade] = []
        self.equity_curve: list[PositionSnapshot] = []
        self._open_trade: Optional[Trade] = None
        self._peak_equity: float = initial_capital
        self._max_drawdown: float = 0.0

    @property
    def total_equity(self) -> float:
        return self.cash + self.position_value

    @property
    def position_value(self) -> float:
        return self.position_size * self.position_avg_price

    @property
    def is_flat(self) -> bool:
        return self.position_size == 0

    @property
    def is_long(self) -> bool:
        return self.position_side == OrderSide.BUY and self.position_size > 0

    @property
    def is_short(self) -> bool:
        return self.position_side == OrderSide.SELL and self.position_size > 0

    def execute_order(self, order: Order, current_price: float, timestamp: datetime) -> bool:
        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and current_price > order.limit_price:
                return False
            if order.side == OrderSide.SELL and current_price < order.limit_price:
                return False

        if order.order_type == OrderType.STOP_LOSS:
            if order.side == OrderSide.SELL and current_price > order.stop_price:
                return False
            if order.side == OrderSide.BUY and current_price < order.stop_price:
                return False

        slippage_mult = 1 + self.slippage_pct if order.side == OrderSide.BUY else 1 - self.slippage_pct
        fill_price = current_price * slippage_mult
        commission = fill_price * order.size * self.commission_pct
        slippage_cost = abs(fill_price - current_price) * order.size

        if order.side == OrderSide.BUY:
            total_cost = fill_price * order.size + commission
            max_size = (self.cash * self.max_position_pct) / (fill_price * (1 + self.commission_pct))
            if order.size > max_size:
                if max_size <= 0:
                    return False
                order.size = max_size
                total_cost = fill_price * order.size + commission

            self.cash -= total_cost
            if self.position_side == OrderSide.SELL and self.position_size > 0:
                self._close_position(fill_price, timestamp, commission, slippage_cost, order)
            else:
                self._add_to_position(OrderSide.BUY, order.size, fill_price)
                self._open_new_trade(order, fill_price, timestamp, commission, slippage_cost)

        elif order.side == OrderSide.SELL:
            if self.position_size <= 0:
                return False
            sell_size = min(order.size, self.position_size)
            order.size = sell_size
            proceeds = fill_price * sell_size - commission
            self.cash += proceeds
            self._close_position(fill_price, timestamp, commission, slippage_cost, order)

        order.fill(fill_price, timestamp, commission, slippage_cost)
        self.orders.append(order)
        return True

    def _add_to_position(self, side: OrderSide, size: float, price: float):
        if self.position_size == 0:
            self.position_side = side
            self.position_avg_price = price
            self.position_size = size
        else:
            total_cost = self.position_avg_price * self.position_size + price * size
            self.position_size += size
            self.position_avg_price = total_cost / self.position_size

    def _close_position(self, price: float, timestamp: datetime, commission: float, slippage: float, order: Order):
        if self._open_trade:
            pnl = (price - self.position_avg_price) * self.position_size - commission - slippage
            pnl_pct = pnl / (self.position_avg_price * self.position_size) if self.position_avg_price > 0 else 0
            self._open_trade.exit_order = order
            self._open_trade.pnl = pnl
            self._open_trade.pnl_pct = pnl_pct
            self.trades.append(self._open_trade)
            self._open_trade = None

        self.position_size = 0
        self.position_avg_price = 0
        self.position_side = None

    def _open_new_trade(self, order: Order, fill_price: float, timestamp: datetime, commission: float, slippage: float):
        if self._open_trade is None:
            self._open_trade = Trade(entry_order=order)

    def snapshot(self, timestamp: datetime, current_price: float):
        position_val = self.position_size * current_price
        equity = self.cash + position_val
        unrealized = (current_price - self.position_avg_price) * self.position_size if self.position_size > 0 else 0

        if self._open_trade and self.position_size > 0:
            if unrealized > self._open_trade.max_favorable:
                self._open_trade.max_favorable = unrealized
            if unrealized < -self._open_trade.max_adverse:
                self._open_trade.max_adverse = abs(unrealized)
            self._open_trade.holding_periods += 1

        if equity > self._peak_equity:
            self._peak_equity = equity
        dd = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0
        if dd > self._max_drawdown:
            self._max_drawdown = dd

        self.equity_curve.append(
            PositionSnapshot(
                timestamp=timestamp,
                cash=self.cash,
                position_size=self.position_size,
                position_value=position_val,
                total_equity=equity,
                unrealized_pnl=unrealized,
            )
        )

    def close_all(self, current_price: float, timestamp: datetime):
        if self.position_size > 0:
            order = Order(side=OrderSide.SELL, size=self.position_size, tag="close_all")
            self.execute_order(order, current_price, timestamp)
