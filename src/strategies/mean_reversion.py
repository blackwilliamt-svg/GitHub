from __future__ import annotations
import pandas as pd
import numpy as np
from .base import Strategy, Signal


class MeanReversionStrategy(Strategy):
    """Z-score mean reversion — buys when price deviates below mean, sells above."""

    name = "mean_reversion"

    def __init__(
        self,
        lookback: int = 50,
        entry_z: float = -2.0,
        exit_z: float = 0.0,
    ):
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self._zscore: pd.Series = pd.Series(dtype=float)

    def initialize(self, data: pd.DataFrame):
        close = data["close"]
        rolling_mean = close.rolling(window=self.lookback).mean()
        rolling_std = close.rolling(window=self.lookback).std()
        self._zscore = (close - rolling_mean) / rolling_std.replace(0, np.inf)

    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        if index < self.lookback:
            return Signal.HOLD

        z = self._zscore.iloc[index]
        z_prev = self._zscore.iloc[index - 1]

        if z_prev > self.entry_z and z <= self.entry_z:
            return Signal.BUY
        if z_prev < self.exit_z and z >= self.exit_z:
            return Signal.SELL
        if z >= -self.entry_z:
            return Signal.SELL
        return Signal.HOLD
