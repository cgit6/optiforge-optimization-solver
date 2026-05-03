"""實驗編排與批次執行：`Simulator` 整合 ProblemBank、Registry、驗證；輸出由 stat 模組接手。"""

from .core import Simulator, SimulatorResult, SimulatorRunRow

__all__ = ["Simulator", "SimulatorResult", "SimulatorRunRow"]
