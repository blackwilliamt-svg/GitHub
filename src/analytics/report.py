from __future__ import annotations
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

from .metrics import PerformanceMetrics

if TYPE_CHECKING:
    from ..engine.backtester import BacktestResult


class ReportGenerator:
    """Generates rich terminal reports from backtest results."""

    def __init__(self):
        self.console = Console()

    def print_summary(self, result: BacktestResult):
        metrics = PerformanceMetrics.from_result(result)
        self.console.print()
        self._print_header(result)
        self._print_returns_table(metrics)
        self._print_risk_table(metrics)
        self._print_trade_stats(metrics)
        self._print_cost_analysis(metrics)
        self.console.print()

    def _print_header(self, result: BacktestResult):
        eq = result.equity_df
        start = eq["timestamp"].iloc[0] if not eq.empty else "N/A"
        end = eq["timestamp"].iloc[-1] if not eq.empty else "N/A"
        header = Text()
        header.append(f"Strategy: ", style="bold")
        header.append(f"{result.strategy_name}\n", style="bold cyan")
        header.append(f"Period: {start} -> {end}\n")
        header.append(f"Initial Capital: ${result.config.initial_capital:,.2f}")
        self.console.print(Panel(header, title="Backtest Report", border_style="blue"))

    def _print_returns_table(self, m: PerformanceMetrics):
        table = Table(title="Returns", show_header=True, header_style="bold green")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        color = "green" if m.total_return >= 0 else "red"
        table.add_row("Total Return", f"[{color}]{m.total_return:+.2%}[/{color}]")
        color = "green" if m.annualized_return >= 0 else "red"
        table.add_row("Annualized Return", f"[{color}]{m.annualized_return:+.2%}[/{color}]")
        table.add_row("Sharpe Ratio", f"{m.sharpe_ratio:.3f}")
        table.add_row("Sortino Ratio", f"{m.sortino_ratio:.3f}")
        table.add_row("Profit Factor", f"{m.profit_factor:.3f}")
        table.add_row("Expectancy", f"${m.expectancy:,.2f}")
        self.console.print(table)

    def _print_risk_table(self, m: PerformanceMetrics):
        table = Table(title="Risk Metrics", show_header=True, header_style="bold yellow")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Max Drawdown", f"[red]{m.max_drawdown:.2%}[/red]")
        table.add_row("Max DD Duration", f"{m.max_drawdown_duration} bars")
        table.add_row("Calmar Ratio", f"{m.calmar_ratio:.3f}")
        table.add_row("Recovery Factor", f"{m.recovery_factor:.3f}")
        table.add_row("Ulcer Index", f"{m.ulcer_index:.3f}")
        self.console.print(table)

    def _print_trade_stats(self, m: PerformanceMetrics):
        table = Table(title="Trade Statistics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Total Trades", str(m.total_trades))
        table.add_row("Win Rate", f"{m.win_rate:.1%}")
        table.add_row("Avg Trade P&L", f"${m.avg_trade_pnl:,.2f}")
        table.add_row("Best Trade", f"[green]${m.best_trade:,.2f}[/green]")
        table.add_row("Worst Trade", f"[red]${m.worst_trade:,.2f}[/red]")
        table.add_row("Avg Winner", f"[green]${m.avg_winner:,.2f}[/green]")
        table.add_row("Avg Loser", f"[red]${m.avg_loser:,.2f}[/red]")
        table.add_row("Best Trade %", f"[green]{m.largest_winner_pct:+.2%}[/green]")
        table.add_row("Worst Trade %", f"[red]{m.largest_loser_pct:+.2%}[/red]")
        table.add_row("Max Consecutive Wins", str(m.consecutive_wins))
        table.add_row("Max Consecutive Losses", str(m.consecutive_losses))
        table.add_row("Avg Holding Period", f"{m.avg_holding_period:.1f} bars")
        self.console.print(table)

    def _print_cost_analysis(self, m: PerformanceMetrics):
        table = Table(title="Cost Analysis", show_header=True, header_style="bold red")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Total Commission", f"${m.total_commission:,.2f}")
        table.add_row("Total Slippage", f"${m.total_slippage:,.2f}")
        table.add_row("Total Costs", f"${m.total_commission + m.total_slippage:,.2f}")
        self.console.print(table)

    def compare(self, results: list[BacktestResult]):
        table = Table(title="Strategy Comparison", show_header=True, header_style="bold cyan")
        table.add_column("Strategy", style="bold")
        table.add_column("Return", justify="right")
        table.add_column("Sharpe", justify="right")
        table.add_column("Max DD", justify="right")
        table.add_column("Win Rate", justify="right")
        table.add_column("Trades", justify="right")
        table.add_column("Profit Factor", justify="right")
        table.add_column("Calmar", justify="right")

        for r in sorted(results, key=lambda x: x.total_return, reverse=True):
            m = PerformanceMetrics.from_result(r)
            color = "green" if m.total_return >= 0 else "red"
            table.add_row(
                r.strategy_name,
                f"[{color}]{m.total_return:+.2%}[/{color}]",
                f"{m.sharpe_ratio:.3f}",
                f"[red]{m.max_drawdown:.2%}[/red]",
                f"{m.win_rate:.1%}",
                str(m.total_trades),
                f"{m.profit_factor:.2f}",
                f"{m.calmar_ratio:.3f}",
            )

        self.console.print()
        self.console.print(table)
        self.console.print()
