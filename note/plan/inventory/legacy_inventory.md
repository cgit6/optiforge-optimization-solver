# Legacy Inventory

`old/` 視為歷史參考；目前主流程以 `cli/`、`engine/`、`simulator/`、`machine/`、`solver/` 為準。

## Files

| Path | Lines/Cells | Purpose |
|---|---:|---|
| `old/BSCA.py` | 271 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/BSCASMA.py` | 774 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/BSMA.py` | 176 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/Friedman_test.ipynb` | 12 | 歷史 notebook，用於分析、繪圖或統計檢定。 |
| `old/GUROBI/gb3.py` | 76 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/gb3_limit.py` | 74 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/gb_relaxation.py` | 153 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/gurobi.ipynb` | 2 | 歷史 notebook，用於分析、繪圖或統計檢定。 |
| `old/GUROBI/main_cb.py` | 80 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/main_gk.py` | 111 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/main_hp.py` | 74 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/main_pb.py` | 75 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/main_sent.py` | 76 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/main_weing.py` | 106 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/main_weish.py` | 106 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/GUROBI/scipy.py` | 19 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/algo_analysis.ipynb` | 21 | 歷史 notebook，用於分析、繪圖或統計檢定。 |
| `old/draw.ipynb` | 2 | 歷史 notebook，用於分析、繪圖或統計檢定。 |
| `old/initial_analysis.ipynb` | 29 | 歷史 notebook，用於分析、繪圖或統計檢定。 |
| `old/main1cb.py` | 100 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/main1gk.py` | 102 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/main1hp.py` | 100 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/main1pb.py` | 100 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/main1pet.py` | 123 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/main1sent.py` | 110 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/main1weing.py` | 99 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/main1weish.py` | 97 | 歷史 solver/實驗腳本或 Gurobi 對照程式。 |
| `old/static_test.ipynb` | 7 | 歷史 notebook，用於分析、繪圖或統計檢定。 |
| `old/transform.py` | 44 | 歷史轉換片段；目前頂層縮排不合法，API reference 只能記錄 parse error。 |

## Notebooks

| Path | Cells | Code Cells | Markdown Cells | Imports |
|---|---:|---:|---:|---|
| `old/Friedman_test.ipynb` | 12 | 7 | 5 | import numpy as np, from scipy.stats import friedmanchisquare, from scipy.stats import friedmanchisquare, rankdata, from itertools import combinations, from statsmodels.stats.multicomp import pairwise_tukeyhsd, from scipy.stats import wilcoxon |
| `old/GUROBI/gurobi.ipynb` | 2 | 2 | 0 | import time, import os, import pandas as pd, import numpy as np, from gurobipy import * |
| `old/algo_analysis.ipynb` | 21 | 12 | 9 | import numpy as np, import pandas as pd, import matplotlib.pyplot as plt, import re, import csv, from scipy.stats import wilcoxon |
| `old/draw.ipynb` | 2 | 2 | 0 | import matplotlib.pyplot as plt, import numpy as np |
| `old/initial_analysis.ipynb` | 29 | 17 | 12 | import numpy as np, import pandas as pd, from initial_main1 import main, import random, import os, from initial import initial1,initial2,initial3,initial3_1,initial3_3 |
| `old/static_test.ipynb` | 7 | 5 | 2 | import numpy as np, from scipy.stats import friedmanchisquare, from scipy.stats import wilcoxon |
