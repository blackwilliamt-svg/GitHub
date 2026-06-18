from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum

import pandas as pd


class Signal(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0


class Strategy(ABC):
    """Base class for all backtesting strategies."""

    name: str = "base"

    def initialize(self, data: pd.DataFrame):
        """Pre-compute indicators on the full dataset. Called once before backtesting."""
        pass

    @abstractmethod
    def generate_signal(self, index: int, data: pd.DataFrame) -> Signal:
        """Return BUY, SELL, or HOLD for the current bar."""
        ...

    def __repr__(self) -> str:
        return f"<Strategy: {self.name}>"
