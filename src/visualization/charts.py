from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from ..engine.backtester import BacktestResult


class ChartGenerator:
    """Generates backtest visualization charts."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use("dark_background")

    def plot_full_report(self, result: BacktestResult, filename: str = "backtest_report.png") -> str:
        fig, axes = plt.subplots(4, 1, figsize=(16, 20), gridspec_kw={"height_ratios": [3, 1.5, 1.5, 1]})
        fig.suptitle(f"Backtest: {result.strategy_name}", fontsize=16, fontweight="bold", y=0.98)

        self._plot_equity_and_price(axes[0], result)
        self._plot_drawdown(axes[1], result)
        self._plot_trade_pnl(axes[2], result)
        self._plot_monthly_returns(axes[3], result)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        path = self.output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return str(path)

    def _plot_equity_and_price(self, ax: plt.Axes, result: BacktestResult):
        eq = result.equity_df
        if eq.empty:
            return

        ax.set_title("Equity Curve vs Price", fontsize=12)
        ax.plot(eq["timestamp"], eq["total_equity"], color="#00d4ff", linewidth=1.5, label="Portfolio Equity")
        ax.fill_between(eq["timestamp"], result.config.initial_capital, eq["total_equity"],
                       alpha=0.15, color="#00d4ff")
        ax.axhline(y=result.config.initial_capital, color="gray", linestyle="--", alpha=0.5, label="Initial Capital")

        if not result.signals.empty:
            buys = result.signals[result.signals["signal"] == "buy"]
            sells = result.signals[result.signals["signal"].isin(["sell", "stop_loss", "take_profit", "trailing_stop"])]

            price_scale = eq["total_equity"].mean() / result.data["close"].mean()
            if not buys.empty:
                buy_equity = []
                for _, b in buys.iterrows():
                    match = eq[eq["timestamp"] == b["timestamp"]]
                    buy_equity.append(match["total_equity"].iloc[0] if not match.empty else eq["total_equity"].iloc[0])
                ax.scatter(buys["timestamp"], buy_equity, marker="^", color="#00ff88",
                          s=80, zorder=5, label="Buy")
            if not sells.empty:
                sell_equity = []
                for _, s in sells.iterrows():
                    match = eq[eq["timestamp"] == s["timestamp"]]
                    sell_equity.append(match["total_equity"].iloc[0] if not match.empty else eq["total_equity"].iloc[-1])
                ax.scatter(sells["timestamp"], sell_equity, marker="v", color="#ff4444",
                          s=80, zorder=5, label="Sell")

        ax.legend(loc="upper left", fontsize=9)
        ax.set_ylabel("Equity ($)")
        ax.grid(True, alpha=0.2)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    def _plot_drawdown(self, ax: plt.Axes, result: BacktestResult):
        eq = result.equity_df
        if eq.empty:
            return

        equities = eq["total_equity"].values
        peak = np.maximum.accumulate(equities)
        drawdown = (equities - peak) / peak

        ax.set_title("Drawdown", fontsize=12)
        ax.fill_between(eq["timestamp"], drawdown, 0, color="#ff4444", alpha=0.4)
        ax.plot(eq["timestamp"], drawdown, color="#ff4444", linewidth=1)
        ax.set_ylabel("Drawdown %")
        ax.grid(True, alpha=0.2)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    def _plot_trade_pnl(self, ax: plt.Axes, result: BacktestResult):
        trades = result.portfolio.trades
        if not trades:
            ax.set_title("Trade P&L", fontsize=12)
            ax.text(0.5, 0.5, "No trades", ha="center", va="center", transform=ax.transAxes)
            return

        pnls = [t.pnl for t in trades]
        colors = ["#00ff88" if p > 0 else "#ff4444" for p in pnls]

        ax.set_title("Trade P&L Distribution", fontsize=12)
        ax.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
        ax.axhline(y=0, color="gray", linestyle="-", alpha=0.5)
        ax.set_xlabel("Trade #")
        ax.set_ylabel("P&L ($)")
        ax.grid(True, alpha=0.2)

    def _plot_monthly_returns(self, ax: plt.Axes, result: BacktestResult):
        eq = result.equity_df
        if eq.empty:
            ax.set_title("Monthly Returns", fontsize=12)
            return

        eq_copy = eq.copy()
        eq_copy["timestamp"] = pd.to_datetime(eq_copy["timestamp"])
        eq_copy = eq_copy.set_index("timestamp")
        monthly = eq_copy["total_equity"].resample("ME").last().pct_change().dropna()

        if monthly.empty:
            ax.set_title("Monthly Returns", fontsize=12)
            return

        colors = ["#00ff88" if r > 0 else "#ff4444" for r in monthly.values]
        labels = [d.strftime("%b %y") for d in monthly.index]

        ax.set_title("Monthly Returns", fontsize=12)
        ax.bar(range(len(monthly)), monthly.values * 100, color=colors, alpha=0.7)
        ax.set_xticks(range(len(monthly)))
        ax.set_xticklabels(labels, rotation=45, fontsize=7)
        ax.axhline(y=0, color="gray", linestyle="-", alpha=0.5)
        ax.set_ylabel("Return %")
        ax.grid(True, alpha=0.2)

    def plot_comparison(self, results: list[BacktestResult], filename: str = "comparison.png") -> str:
        fig, axes = plt.subplots(2, 1, figsize=(16, 10))
        fig.suptitle("Strategy Comparison", fontsize=16, fontweight="bold")

        colors = ["#00d4ff", "#ff4444", "#00ff88", "#ffaa00", "#ff66ff", "#66ffff", "#ff8800", "#88ff00"]

        for i, result in enumerate(results):
            eq = result.equity_df
            if eq.empty:
                continue
            color = colors[i % len(colors)]
            normalized = eq["total_equity"] / result.config.initial_capital
            axes[0].plot(eq["timestamp"], normalized, color=color, linewidth=1.5, label=result.strategy_name)

        axes[0].set_title("Normalized Equity Curves")
        axes[0].set_ylabel("Portfolio Value (normalized)")
        axes[0].legend(fontsize=9)
        axes[0].grid(True, alpha=0.2)
        axes[0].axhline(y=1.0, color="gray", linestyle="--", alpha=0.5)

        names = [r.strategy_name for r in results]
        returns = [r.total_return * 100 for r in results]
        bar_colors = ["#00ff88" if r > 0 else "#ff4444" for r in returns]
        axes[1].barh(names, returns, color=bar_colors, alpha=0.7)
        axes[1].set_title("Total Returns by Strategy")
        axes[1].set_xlabel("Return %")
        axes[1].grid(True, alpha=0.2)
        axes[1].axvline(x=0, color="gray", linestyle="-", alpha=0.5)

        plt.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return str(path)
