from __future__ import annotations
import pandas as pd
import numpy as np
from .base import Strategy, Signal


class VWAPStrategy(Strategy):
    """VWAP deviation strategy — buys below VWAP by threshold, sells above."""

    name = "vwap"

    def __init__(self, deviation_pct: float = 0.02, reset_period: int = 24):
        self.deviation_pct = deviation_pct
        self.reset_period = reset_period
        self._vwap: pd.Series = pd.Series(dtype=float)

    def initialize(self, data: pd.DataFrame):
        typical_price = (data["high"] + data["low"] + data["close"]) / 3
        cum_vol = pd.Series(0.0, index=data.index, dtype=float)
        cum_tp_vol = pd.Series(0.0, index=data.index, dtype=float)
        vwap = pd.Series(0.0, index=data.index, dtype=float)

        running_vol = 0.0
        running_tp_vol = 0.0

        for i in range(len(data)):
            if i % self.reset_period == 0:
                running_vol = 0.0
                running_tp_vol = 0.0

            running_vol += data.iloc[i]["volume"]
            running_tp_vol += typical_price.iloc[i] * data.iloc[i]["volume"]

            vwap.iloc[i] = running_tp_vol / running_vol if running_vol > 0 else typical_price.iloc[i]

        self._vwap = vwap

    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        if index < 2:
            return Signal.HOLD

        close = data.iloc[index]["close"]
        vwap = self._vwap.iloc[index]

        pct_diff = (close - vwap) / vwap if vwap > 0 else 0

        if pct_diff < -self.deviation_pct:
            return Signal.BUY
        if pct_diff > self.deviation_pct:
            return Signal.SELL
        return Signal.HOLD
