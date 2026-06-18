from __future__ import annotations
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

from .models import OHLCV

logger = logging.getLogger(__name__)

BIRDEYE_OHLCV = "https://public-api.birdeye.so/defi/ohlcv"
DEXSCREENER_PAIRS = "https://api.dexscreener.com/latest/dex/tokens/{address}"

INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
    "1w": "1W",
}


class PriceFetcher:
    """Fetches historical OHLCV data from multiple sources for Jupiter-listed tokens."""

    def __init__(
        self,
        birdeye_api_key: Optional[str] = None,
        cache_dir: str = ".cache/price_data",
    ):
        self._birdeye_key = birdeye_api_key or os.environ.get("BIRDEYE_API_KEY", "")
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(timeout=30.0)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _cache_key(self, token: str, interval: str, start: int, end: int) -> Path:
        h = hashlib.md5(f"{token}:{interval}:{start}:{end}".encode()).hexdigest()[:12]
        return self._cache_dir / f"{token[:8]}_{interval}_{h}.json"

    def _load_cache(self, path: Path) -> Optional[list[dict]]:
        if path.exists():
            age_hours = (time.time() - path.stat().st_mtime) / 3600
            if age_hours < 6:
                with open(path) as f:
                    return json.load(f)
        return None

    def _save_cache(self, path: Path, data: list[dict]):
        with open(path, "w") as f:
            json.dump(data, f)

    def fetch_birdeye(
        self,
        token_address: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[OHLCV]:
        if not self._birdeye_key:
            logger.warning("No Birdeye API key set — set BIRDEYE_API_KEY env var")
            return []

        now = int(datetime.now(timezone.utc).timestamp())
        time_from = int(start_time.timestamp()) if start_time else now - 30 * 86400
        time_to = int(end_time.timestamp()) if end_time else now

        birdeye_interval = INTERVAL_MAP.get(interval, "1H")

        cache_path = self._cache_key(token_address, interval, time_from, time_to)
        cached = self._load_cache(cache_path)
        if cached:
            return [self._dict_to_ohlcv(c) for c in cached]

        headers = {
            "X-API-KEY": self._birdeye_key,
            "x-chain": "solana",
        }
        params = {
            "address": token_address,
            "type": birdeye_interval,
            "time_from": time_from,
            "time_to": time_to,
        }
        resp = self._client.get(BIRDEYE_OHLCV, headers=headers, params=params)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("items", [])

        candles = []
        for item in items:
            candles.append(
                OHLCV(
                    timestamp=datetime.fromtimestamp(item["unixTime"], tz=timezone.utc),
                    open=float(item.get("o", 0)),
                    high=float(item.get("h", 0)),
                    low=float(item.get("l", 0)),
                    close=float(item.get("c", 0)),
                    volume=float(item.get("v", 0)),
                )
            )

        self._save_cache(cache_path, [c.to_dict() for c in candles])
        logger.info("Fetched %d candles from Birdeye for %s", len(candles), token_address[:8])
        return candles

    def fetch_dexscreener(self, token_address: str) -> list[OHLCV]:
        """Fetch recent price data from DexScreener (limited history, no API key needed)."""
        url = DEXSCREENER_PAIRS.format(address=token_address)
        resp = self._client.get(url)
        resp.raise_for_status()
        pairs = resp.json().get("pairs", [])
        if not pairs:
            return []

        pair = max(pairs, key=lambda p: float(p.get("volume", {}).get("h24", 0) or 0))
        price_usd = float(pair.get("priceUsd", 0))
        price_change = pair.get("priceChange", {})

        now = datetime.now(timezone.utc)
        candles = [
            OHLCV(
                timestamp=now,
                open=price_usd,
                high=price_usd,
                low=price_usd,
                close=price_usd,
                volume=float(pair.get("volume", {}).get("h24", 0) or 0),
            )
        ]
        logger.info("Fetched DexScreener snapshot for %s: $%.6f", token_address[:8], price_usd)
        return candles

    def fetch(
        self,
        token_address: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        candles = self.fetch_birdeye(token_address, interval, start_time, end_time)
        if not candles:
            logger.info("Birdeye returned no data, trying DexScreener")
            candles = self.fetch_dexscreener(token_address)
        if not candles:
            return pd.DataFrame()
        return self.to_dataframe(candles)

    def load_csv(self, filepath: str) -> pd.DataFrame:
        df = pd.read_csv(filepath, parse_dates=["timestamp"])
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            raise ValueError(f"CSV must contain columns: {required}")
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    @staticmethod
    def to_dataframe(candles: list[OHLCV]) -> pd.DataFrame:
        df = pd.DataFrame([c.to_dict() for c in candles])
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    @staticmethod
    def generate_synthetic(
        days: int = 90,
        interval: str = "1h",
        start_price: float = 100.0,
        volatility: float = 0.02,
        trend: float = 0.0001,
        seed: int | None = None,
    ) -> pd.DataFrame:
        """Generate synthetic OHLCV data for strategy testing without API keys."""
        import numpy as np

        if seed is not None:
            np.random.seed(seed)

        interval_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "4h": 240, "1d": 1440, "1w": 10080,
        }
        mins = interval_minutes.get(interval, 60)
        num_candles = (days * 24 * 60) // mins

        now = datetime.now(timezone.utc)
        start = datetime.fromtimestamp(now.timestamp() - days * 86400, tz=timezone.utc)

        timestamps = [
            datetime.fromtimestamp(start.timestamp() + i * mins * 60, tz=timezone.utc)
            for i in range(num_candles)
        ]

        returns = np.random.normal(trend, volatility, num_candles)
        prices = start_price * np.exp(np.cumsum(returns))

        rows = []
        for i, ts in enumerate(timestamps):
            p = prices[i]
            noise = np.random.uniform(0.005, 0.02) * p
            h = p + abs(np.random.normal(0, noise))
            l = p - abs(np.random.normal(0, noise))
            o = np.random.uniform(l, h)
            vol = abs(np.random.normal(1_000_000, 500_000))
            rows.append({
                "timestamp": ts,
                "open": round(o, 6),
                "high": round(h, 6),
                "low": round(l, 6),
                "close": round(p, 6),
                "volume": round(vol, 2),
            })

        return pd.DataFrame(rows)

    def _dict_to_ohlcv(self, d: dict) -> OHLCV:
        ts = d["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts, tz=timezone.utc)
        return OHLCV(
            timestamp=ts,
            open=d["open"],
            high=d["high"],
            low=d["low"],
            close=d["close"],
            volume=d["volume"],
        )
