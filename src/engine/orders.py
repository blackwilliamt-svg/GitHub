from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    side: OrderSide
    size: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    timestamp: Optional[datetime] = None
    filled: bool = False
    fill_price: float = 0.0
    fill_timestamp: Optional[datetime] = None
    commission: float = 0.0
    slippage: float = 0.0
    tag: str = ""

    @property
    def total_cost(self) -> float:
        return self.fill_price * self.size + self.commission + self.slippage

    def fill(self, price: float, timestamp: datetime, commission: float, slippage: float):
        self.filled = True
        self.fill_price = price
        self.fill_timestamp = timestamp
        self.commission = commission
        self.slippage = slippage


@dataclass
class Trade:
    entry_order: Order
    exit_order: Optional[Order] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_periods: int = 0
    max_favorable: float = 0.0
    max_adverse: float = 0.0

    @property
    def is_closed(self) -> bool:
        return self.exit_order is not None and self.exit_order.filled

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0

    @property
    def side(self) -> OrderSide:
        return self.entry_order.side
