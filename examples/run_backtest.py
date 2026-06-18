#!/usr/bin/env python3
"""
Example: Run a full backtest comparison using synthetic data.

This demonstrates the bot's capabilities without needing any API keys.
For real Jupiter DEX data, set BIRDEYE_API_KEY and use the CLI:

    python -m src.main backtest ma_crossover --token SOL --days 90
    python -m src.main compare --token JUP --days 60 --synthetic
"""
import sys
sys.path.insert(0, ".")

from src.data.price_fetcher import PriceFetcher
from src.engine.backtester import Backtester, BacktestConfig
from src.analytics.report import ReportGenerator
from src.visualization.charts import ChartGenerator
from src.strategies import (
    MACrossover,
    RSIStrategy,
    MACDStrategy,
    BollingerStrategy,
    VWAPStrategy,
    DCAStrategy,
    MeanReversionStrategy,
)


def main():
    print("Generating 90 days of synthetic price data (1h candles)...\n")
    data = PriceFetcher.generate_synthetic(
        days=90,
        interval="1h",
        start_price=150.0,
        volatility=0.015,
        trend=0.0002,
        seed=42,
    )
    print(f"Generated {len(data)} candles")
    print(f"Price range: ${data['close'].min():.2f} - ${data['close'].max():.2f}\n")

    strategies = [
        MACrossover(fast_period=12, slow_period=26),
        RSIStrategy(period=14, oversold=30, overbought=70),
        MACDStrategy(fast_period=12, slow_period=26, signal_period=9),
        BollingerStrategy(period=20, std_dev=2.0),
        VWAPStrategy(deviation_pct=0.02, reset_period=24),
        DCAStrategy(buy_interval=24),
        MeanReversionStrategy(lookback=50, entry_z=-2.0, exit_z=0.0),
    ]

    config = BacktestConfig(
        initial_capital=10_000.0,
        commission_pct=0.003,
        slippage_pct=0.005,
        stop_loss_pct=0.08,
        trailing_stop_pct=0.05,
    )

    results = []
    for strategy in strategies:
        engine = Backtester(config=config)
        result = engine.run(strategy, data)
        results.append(result)
        print(f"  {strategy.name:<20} Return: {result.total_return:+.2%}  "
              f"Sharpe: {result.sharpe_ratio:.3f}  "
              f"Trades: {result.total_trades}")

    reporter = ReportGenerator()
    print("\n" + "=" * 70)
    reporter.compare(results)

    for result in results:
        reporter.print_summary(result)

    charts = ChartGenerator(output_dir="output")

    for result in results:
        path = charts.plot_full_report(result, filename=f"{result.strategy_name}_report.png")
        print(f"Chart saved: {path}")

    comparison_path = charts.plot_comparison(results, filename="strategy_comparison.png")
    print(f"Comparison chart saved: {comparison_path}")


if __name__ == "__main__":
    main()
