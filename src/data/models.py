from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OHLCV:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass
class TokenInfo:
    address: str
    symbol: str
    name: str
    decimals: int
    logo_uri: str = ""
    tags: list[str] = field(default_factory=list)
    daily_volume: float = 0.0

    def __str__(self) -> str:
        return f"{self.symbol} ({self.name}) - {self.address[:8]}..."


@dataclass
class SwapRoute:
    input_mint: str
    output_mint: str
    in_amount: float
    out_amount: float
    price_impact_pct: float
    route_plan: list[dict] = field(default_factory=list)
