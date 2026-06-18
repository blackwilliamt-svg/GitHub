#!/usr/bin/env python3
"""Jupiter DEX Backtesting Bot — CLI entry point."""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml

from .data.jupiter_client import JupiterClient
from .data.price_fetcher import PriceFetcher
from .engine.backtester import Backtester, BacktestConfig
from .analytics.metrics import PerformanceMetrics
from .analytics.report import ReportGenerator
from .visualization.charts import ChartGenerator
from .strategies import (
    MACrossover,
    RSIStrategy,
    MACDStrategy,
    BollingerStrategy,
    VWAPStrategy,
    DCAStrategy,
    MeanReversionStrategy,
)

STRATEGIES = {
    "ma_crossover": MACrossover,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
    "vwap": VWAPStrategy,
    "dca": DCAStrategy,
    "mean_reversion": MeanReversionStrategy,
}


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            return yaml.safe_load(f)
    return {}


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool):
    """Jupiter DEX Backtesting Bot"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
def tokens():
    """List top Jupiter-verified tokens by daily volume."""
    with JupiterClient() as jup:
        token_list = jup.get_token_list()

    token_list.sort(key=lambda t: t.daily_volume, reverse=True)
    click.echo(f"\nTop 30 Jupiter tokens by 24h volume:\n")
    click.echo(f"{'Symbol':<10} {'Name':<25} {'Volume (24h)':>15} {'Address'}")
    click.echo("-" * 90)
    for t in token_list[:30]:
        vol = f"${t.daily_volume:,.0f}" if t.daily_volume else "N/A"
        click.echo(f"{t.symbol:<10} {t.name[:24]:<25} {vol:>15} {t.address}")


@cli.command()
@click.argument("token_address")
def price(token_address: str):
    """Get current Jupiter price for a token."""
    config = load_config()
    token_map = config.get("tokens", {})

    if token_address.upper() in token_map:
        token_address = token_map[token_address.upper()]

    with JupiterClient() as jup:
        p = jup.get_price(token_address)
        if p:
            click.echo(f"Price: ${p:.8f}")
        else:
            click.echo("Could not fetch price")


@cli.command()
@click.argument("strategy_name", type=click.Choice(list(STRATEGIES.keys())))
@click.option("--token", "-t", default="SOL", help="Token symbol or mint address")
@click.option("--days", "-d", default=90, help="Days of historical data")
@click.option("--interval", "-i", default="1h", help="Candle interval (1m,5m,15m,1h,4h,1d)")
@click.option("--capital", "-c", default=10000.0, help="Initial capital in USD")
@click.option("--commission", default=0.003, help="Commission percentage (0.003 = 0.3%)")
@click.option("--slippage", default=0.005, help="Slippage percentage")
@click.option("--stop-loss", default=None, type=float, help="Stop loss percentage (e.g. 0.05 = 5%)")
@click.option("--take-profit", default=None, type=float, help="Take profit percentage")
@click.option("--trailing-stop", default=None, type=float, help="Trailing stop percentage")
@click.option("--csv", "csv_path", default=None, help="Load data from CSV instead of API")
@click.option("--synthetic", is_flag=True, help="Use synthetic data (no API key needed)")
@click.option("--chart/--no-chart", default=True, help="Generate chart")
@click.option("--output", "-o", default="output", help="Output directory for charts")
def backtest(
    strategy_name: str,
    token: str,
    days: int,
    interval: str,
    capital: float,
    commission: float,
    slippage: float,
    stop_loss: float | None,
    take_profit: float | None,
    trailing_stop: float | None,
    csv_path: str | None,
    synthetic: bool,
    chart: bool,
    output: str,
):
    """Run a backtest with the specified strategy."""
    config = load_config()
    token_map = config.get("tokens", {})

    if token.upper() in token_map:
        token_address = token_map[token.upper()]
        token_symbol = token.upper()
    else:
        token_address = token
        token_symbol = token[:8]

    fetcher = PriceFetcher()

    if csv_path:
        click.echo(f"Loading data from {csv_path}...")
        data = fetcher.load_csv(csv_path)
    elif synthetic:
        click.echo(f"Generating {days} days of synthetic data ({interval} candles)...")
        data = PriceFetcher.generate_synthetic(days=days, interval=interval, seed=42)
    else:
        click.echo(f"Fetching {days} days of {interval} data for {token_symbol}...")
        end = datetime.now(timezone.utc)
        start = datetime.fromtimestamp(end.timestamp() - days * 86400, tz=timezone.utc)
        data = fetcher.fetch(token_address, interval=interval, start_time=start, end_time=end)

    if data.empty:
        click.echo("No data available. Use --synthetic for testing without API keys, or set BIRDEYE_API_KEY.")
        sys.exit(1)

    click.echo(f"Loaded {len(data)} candles")

    strategy = STRATEGIES[strategy_name]()
    bt_config = BacktestConfig(
        initial_capital=capital,
        commission_pct=commission,
        slippage_pct=slippage,
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
        trailing_stop_pct=trailing_stop,
    )

    engine = Backtester(config=bt_config)
    result = engine.run(strategy, data)

    reporter = ReportGenerator()
    reporter.print_summary(result)

    if chart:
        charts = ChartGenerator(output_dir=output)
        chart_path = charts.plot_full_report(result, filename=f"{strategy_name}_{token_symbol}.png")
        click.echo(f"\nChart saved to: {chart_path}")


@cli.command()
@click.option("--token", "-t", default="SOL", help="Token symbol or mint address")
@click.option("--days", "-d", default=90, help="Days of historical data")
@click.option("--interval", "-i", default="1h", help="Candle interval")
@click.option("--capital", "-c", default=10000.0, help="Initial capital in USD")
@click.option("--csv", "csv_path", default=None, help="Load from CSV")
@click.option("--synthetic", is_flag=True, help="Use synthetic data")
@click.option("--output", "-o", default="output", help="Output directory")
def compare(token: str, days: int, interval: str, capital: float, csv_path: str | None, synthetic: bool, output: str):
    """Compare all strategies head-to-head on the same data."""
    config = load_config()
    token_map = config.get("tokens", {})

    if token.upper() in token_map:
        token_address = token_map[token.upper()]
        token_symbol = token.upper()
    else:
        token_address = token
        token_symbol = token[:8]

    fetcher = PriceFetcher()

    if csv_path:
        data = fetcher.load_csv(csv_path)
    elif synthetic:
        click.echo(f"Generating {days} days of synthetic data...")
        data = PriceFetcher.generate_synthetic(days=days, interval=interval, seed=42)
    else:
        end = datetime.now(timezone.utc)
        start = datetime.fromtimestamp(end.timestamp() - days * 86400, tz=timezone.utc)
        data = fetcher.fetch(token_address, interval=interval, start_time=start, end_time=end)

    if data.empty:
        click.echo("No data available. Use --synthetic or set BIRDEYE_API_KEY.")
        sys.exit(1)

    click.echo(f"Running all {len(STRATEGIES)} strategies on {len(data)} candles...\n")

    bt_config = BacktestConfig(initial_capital=capital)
    results = []

    for name, strategy_cls in STRATEGIES.items():
        strategy = strategy_cls()
        engine = Backtester(config=bt_config)
        result = engine.run(strategy, data)
        results.append(result)
        ret = result.total_return
        color = "green" if ret >= 0 else "red"
        click.echo(f"  {name:<20} {ret:+.2%}")

    reporter = ReportGenerator()
    reporter.compare(results)

    charts = ChartGenerator(output_dir=output)
    chart_path = charts.plot_comparison(results, filename=f"comparison_{token_symbol}.png")
    click.echo(f"\nComparison chart saved to: {chart_path}")


@cli.command()
@click.argument("token_address")
@click.option("--output-mint", default="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", help="Output token mint")
@click.option("--amount", "-a", type=float, required=True, help="Amount to swap")
def quote(token_address: str, output_mint: str, amount: float):
    """Get a Jupiter swap quote."""
    config = load_config()
    token_map = config.get("tokens", {})

    if token_address.upper() in token_map:
        token_address = token_map[token_address.upper()]
    if output_mint.upper() in token_map:
        output_mint = token_map[output_mint.upper()]

    with JupiterClient() as jup:
        token_info = jup.get_token_info(token_address)
        decimals = token_info.decimals if token_info else 9
        raw_amount = int(amount * (10 ** decimals))

        result = jup.get_quote(token_address, output_mint, raw_amount)
        if result:
            out_amount = int(result.get("outAmount", 0))
            impact = result.get("priceImpactPct", "N/A")
            click.echo(f"Input:  {amount}")
            click.echo(f"Output: {out_amount / 1e6:.6f} USDC")
            click.echo(f"Price Impact: {impact}%")
            routes = result.get("routePlan", [])
            if routes:
                click.echo(f"Route: {' -> '.join(r.get('swapInfo', {}).get('label', '?') for r in routes)}")
        else:
            click.echo("Failed to get quote")


def main():
    cli()


if __name__ == "__main__":
    main()
