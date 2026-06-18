from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from ..engine.backtester import BacktestResult


@dataclass
class PerformanceMetrics:
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    calmar_ratio: float
    profit_factor: float
    win_rate: float
    total_trades: int
    avg_trade_pnl: float
    best_trade: float
    worst_trade: float
    avg_holding_period: float
    total_commission: float
    total_slippage: float
    recovery_factor: float
    expectancy: float
    avg_winner: float
    avg_loser: float
    largest_winner_pct: float
    largest_loser_pct: float
    consecutive_wins: int
    consecutive_losses: int
    ulcer_index: float

    @classmethod
    def from_result(cls, result: BacktestResult) -> PerformanceMetrics:
        eq = result.equity_df
        trades = result.portfolio.trades

        total_return = result.total_return

        if not eq.empty and len(eq) > 1:
            days = (eq["timestamp"].iloc[-1] - eq["timestamp"].iloc[0]).total_seconds() / 86400
            years = max(days / 365.25, 1 / 365.25)
            annualized = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1.0
        else:
            annualized = 0.0
            years = 0

        max_dd = result.max_drawdown

        dd_duration = 0
        if not eq.empty:
            equities = eq["total_equity"].values
            peak = equities[0]
            current_dd_len = 0
            for e in equities:
                if e >= peak:
                    peak = e
                    current_dd_len = 0
                else:
                    current_dd_len += 1
                    dd_duration = max(dd_duration, current_dd_len)

        calmar = annualized / max_dd if max_dd > 0 else 0.0

        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl <= 0]
        avg_winner = np.mean([t.pnl for t in winners]) if winners else 0.0
        avg_loser = np.mean([t.pnl for t in losers]) if losers else 0.0

        total_commission = sum(o.commission for o in result.portfolio.orders)
        total_slippage = sum(o.slippage for o in result.portfolio.orders)
        avg_holding = np.mean([t.holding_periods for t in trades]) if trades else 0.0

        total_loss = abs(sum(t.pnl for t in losers))
        recovery_factor = result.total_pnl / total_loss if total_loss > 0 else 0.0
        expectancy = result.avg_trade_pnl

        largest_winner_pct = max((t.pnl_pct for t in trades), default=0.0)
        largest_loser_pct = min((t.pnl_pct for t in trades), default=0.0)

        max_consec_wins = 0
        max_consec_losses = 0
        if trades:
            cw = cl = 0
            for t in trades:
                if t.pnl > 0:
                    cw += 1
                    cl = 0
                else:
                    cl += 1
                    cw = 0
                max_consec_wins = max(max_consec_wins, cw)
                max_consec_losses = max(max_consec_losses, cl)

        ulcer = 0.0
        if not eq.empty:
            equities = eq["total_equity"].values
            peak = equities[0]
            sq_drawdowns = []
            for e in equities:
                if e > peak:
                    peak = e
                dd_pct = ((peak - e) / peak) * 100
                sq_drawdowns.append(dd_pct ** 2)
            ulcer = float(np.sqrt(np.mean(sq_drawdowns))) if sq_drawdowns else 0.0

        return cls(
            total_return=total_return,
            annualized_return=annualized,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            max_drawdown=max_dd,
            max_drawdown_duration=dd_duration,
            calmar_ratio=calmar,
            profit_factor=result.profit_factor,
            win_rate=result.win_rate,
            total_trades=result.total_trades,
            avg_trade_pnl=result.avg_trade_pnl,
            best_trade=result.best_trade,
            worst_trade=result.worst_trade,
            avg_holding_period=float(avg_holding),
            total_commission=total_commission,
            total_slippage=total_slippage,
            recovery_factor=recovery_factor,
            expectancy=expectancy,
            avg_winner=float(avg_winner),
            avg_loser=float(avg_loser),
            largest_winner_pct=largest_winner_pct,
            largest_loser_pct=largest_loser_pct,
            consecutive_wins=max_consec_wins,
            consecutive_losses=max_consec_losses,
            ulcer_index=ulcer,
        )
