from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

from .portfolio import Portfolio
from .orders import Order, OrderSide
from ..strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission_pct: float = 0.003
    slippage_pct: float = 0.005
    position_size_pct: float = 0.95
    max_position_pct: float = 1.0
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None


class Backtester:
    """Core backtesting engine — feeds OHLCV data through a Strategy and tracks results."""

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self.portfolio: Optional[Portfolio] = None
        self.results: Optional[pd.DataFrame] = None

    def run(self, strategy: Strategy, data: pd.DataFrame) -> BacktestResult:
        if data.empty:
            raise ValueError("Cannot backtest on empty data")

        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(data.columns):
            raise ValueError(f"Data must contain columns: {required}")

        data = data.sort_values("timestamp").reset_index(drop=True)

        self.portfolio = Portfolio(
            initial_capital=self.config.initial_capital,
            commission_pct=self.config.commission_pct,
            slippage_pct=self.config.slippage_pct,
            max_position_pct=self.config.max_position_pct,
        )

        strategy.initialize(data)

        trailing_stop_price = 0.0
        signals_log = []

        for i in range(len(data)):
            row = data.iloc[i]
            ts = row["timestamp"]
            price = row["close"]
            high = row["high"]
            low = row["low"]

            if self.config.stop_loss_pct and self.portfolio.is_long:
                stop_price = self.portfolio.position_avg_price * (1 - self.config.stop_loss_pct)
                if low <= stop_price:
                    order = Order(side=OrderSide.SELL, size=self.portfolio.position_size, tag="stop_loss")
                    self.portfolio.execute_order(order, stop_price, ts)
                    signals_log.append({"timestamp": ts, "signal": "stop_loss", "price": stop_price})
                    self.portfolio.snapshot(ts, price)
                    continue

            if self.config.take_profit_pct and self.portfolio.is_long:
                tp_price = self.portfolio.position_avg_price * (1 + self.config.take_profit_pct)
                if high >= tp_price:
                    order = Order(side=OrderSide.SELL, size=self.portfolio.position_size, tag="take_profit")
                    self.portfolio.execute_order(order, tp_price, ts)
                    signals_log.append({"timestamp": ts, "signal": "take_profit", "price": tp_price})
                    self.portfolio.snapshot(ts, price)
                    continue

            if self.config.trailing_stop_pct and self.portfolio.is_long:
                current_trail = high * (1 - self.config.trailing_stop_pct)
                trailing_stop_price = max(trailing_stop_price, current_trail)
                if low <= trailing_stop_price:
                    order = Order(side=OrderSide.SELL, size=self.portfolio.position_size, tag="trailing_stop")
                    self.portfolio.execute_order(order, trailing_stop_price, ts)
                    signals_log.append({"timestamp": ts, "signal": "trailing_stop", "price": trailing_stop_price})
                    trailing_stop_price = 0.0
                    self.portfolio.snapshot(ts, price)
                    continue

            signal = strategy.generate_signal(i, data.iloc[: i + 1])

            if signal == Signal.BUY and self.portfolio.is_flat:
                size = (self.portfolio.cash * self.config.position_size_pct) / price
                if size > 0:
                    order = Order(side=OrderSide.BUY, size=size, tag=strategy.name)
                    self.portfolio.execute_order(order, price, ts)
                    signals_log.append({"timestamp": ts, "signal": "buy", "price": price})
                    if self.config.trailing_stop_pct:
                        trailing_stop_price = price * (1 - self.config.trailing_stop_pct)

            elif signal == Signal.SELL and self.portfolio.is_long:
                order = Order(side=OrderSide.SELL, size=self.portfolio.position_size, tag=strategy.name)
                self.portfolio.execute_order(order, price, ts)
                signals_log.append({"timestamp": ts, "signal": "sell", "price": price})
                trailing_stop_price = 0.0

            self.portfolio.snapshot(ts, price)

        last_row = data.iloc[-1]
        self.portfolio.close_all(last_row["close"], last_row["timestamp"])

        return BacktestResult(
            portfolio=self.portfolio,
            data=data,
            signals=pd.DataFrame(signals_log) if signals_log else pd.DataFrame(),
            config=self.config,
            strategy_name=strategy.name,
        )


@dataclass
class BacktestResult:
    portfolio: Portfolio
    data: pd.DataFrame
    signals: pd.DataFrame
    config: BacktestConfig
    strategy_name: str

    @property
    def equity_df(self) -> pd.DataFrame:
        if not self.portfolio.equity_curve:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "timestamp": s.timestamp,
                "cash": s.cash,
                "position_value": s.position_value,
                "total_equity": s.total_equity,
                "unrealized_pnl": s.unrealized_pnl,
            }
            for s in self.portfolio.equity_curve
        ])

    @property
    def total_return(self) -> float:
        if not self.portfolio.equity_curve:
            return 0.0
        final = self.portfolio.equity_curve[-1].total_equity
        return (final - self.config.initial_capital) / self.config.initial_capital

    @property
    def total_trades(self) -> int:
        return len(self.portfolio.trades)

    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.portfolio.trades if t.is_winner)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.portfolio.trades)

    @property
    def max_drawdown(self) -> float:
        return self.portfolio._max_drawdown

    @property
    def sharpe_ratio(self) -> float:
        eq = self.equity_df
        if eq.empty or len(eq) < 2:
            return 0.0
        returns = eq["total_equity"].pct_change().dropna()
        if returns.std() == 0:
            return 0.0
        periods_per_year = min(len(returns), 365 * 24)
        return float(np.sqrt(periods_per_year) * returns.mean() / returns.std())

    @property
    def sortino_ratio(self) -> float:
        eq = self.equity_df
        if eq.empty or len(eq) < 2:
            return 0.0
        returns = eq["total_equity"].pct_change().dropna()
        downside = returns[returns < 0]
        if downside.empty or downside.std() == 0:
            return 0.0
        periods_per_year = min(len(returns), 365 * 24)
        return float(np.sqrt(periods_per_year) * returns.mean() / downside.std())

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.portfolio.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.portfolio.trades if t.pnl < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def avg_trade_pnl(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    @property
    def best_trade(self) -> float:
        if not self.portfolio.trades:
            return 0.0
        return max(t.pnl for t in self.portfolio.trades)

    @property
    def worst_trade(self) -> float:
        if not self.portfolio.trades:
            return 0.0
        return min(t.pnl for t in self.portfolio.trades)
