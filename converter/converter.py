"""由 MKP 題庫原始檔建立 ProblemModel / 對應 YAML。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from ..problem import ProblemModel

# 定義一個函數的界面(輸入是路徑，輸出是題目)
ProblemPayloadConverter = Callable[[Path], dict[str, Any]]


def _flow_sequence(values: list[Any]) -> CommentedSeq:
    seq = CommentedSeq(values)
    seq.fa.set_flow_style()
    return seq


def _weights_flow_rows(weights: list[list[Any]]) -> CommentedSeq:
    seq = CommentedSeq(_flow_sequence(list(row)) for row in weights)
    return seq


# (內部函數) 原始 dat/txt 資料的路徑
def dat_file_path(*, repo_root: Path, dataset: str, problem_id: str) -> Path:
    return repo_root / "data" / dataset / f"{problem_id}.dat"


# (內部函數) 組合出轉換後的 yaml 保存路徑
def yaml_file_path(*, repo_root: Path, dataset: str, problem_id: str) -> Path:
    return repo_root / "configs/problems" / "mkp" / dataset / f"{problem_id}.yaml"


# 執行轉換操作
def reshape(
    *,
    dataset: str,
    problem_id: str,
    dat_path: Path,
    parser: ProblemPayloadConverter, # 題庫轉換函數
) -> ProblemModel:
    # 1. 執行轉換，給原始檔跟解析函數進行解析
    payload = parser(dat_path)

    # 2. 返回轉換後的題目物件
    # 這裡有問題，返回格式無法兼容所有問題
    return ProblemModel(
        problem_id=problem_id, # 問題編號
        dataset=dataset, # 題庫名稱
        items=int(payload["items"]), # 物品數量
        dim=int(payload["dim"]), # 維度
        values=np.asarray(payload["values"], dtype=int), # 每個物品的價值
        weights=np.asarray(payload["weights"], dtype=int), # 物品的成本
        capacities=np.asarray(payload["capacities"], dtype=int), # 背包容量
        best_known=None if payload["best_known"] is None else int(payload["best_known"]), # 最佳適應值
    )


def transformToMomery(
    *,
    repo_root: Path, # 根路徑
    dataset: str, # 資料庫名稱
    problem_id: str, # 問題編號
    parser: ProblemPayloadConverter, # 解析函數
) -> ProblemModel:
    """dat 轉換後保存到 Momery"""
    # 1. 組合當前原始檔案的原始路徑
    dat_path = dat_file_path(repo_root=repo_root, dataset=dataset, problem_id=problem_id)

    # 2. 執行轉換獲取 ProblemModel 最後返回
    return reshape(
        dataset=dataset,
        problem_id=problem_id,
        dat_path=dat_path,
        parser=parser,
    )


# 獲取 dat 數據進行轉換後保存至 yaml 中
def transformToYaml(
    *,
    repo_root: Path,
    dataset: str,
    problem_id: str,
    parser: ProblemPayloadConverter,
    source_path: Path | None = None,
) -> Path:
    """dat 轉換成 yaml 文件"""
    dat_path = source_path or dat_file_path(repo_root=repo_root, dataset=dataset, problem_id=problem_id)
    payload = parser(dat_path)
    problem_yaml = yaml_file_path(repo_root=repo_root, dataset=dataset, problem_id=problem_id)
    problem_yaml.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "problem_id": problem_id, # 問題編號
        "dataset": dataset, # 題庫名稱
        "problem_type": "mkp",
        "items": payload["items"], # 物品數量
        "dim": payload["dim"], # 維度數量
        "values": _flow_sequence(list(payload["values"])), # 物品價值
        "weights": _weights_flow_rows(payload["weights"]), # 物品成本
        "capacities": _flow_sequence(list(payload["capacities"])), # 背包容量
        "best_known": payload["best_known"], # 題目給的最佳解
    }
    yaml = YAML()
    yaml.default_flow_style = False
    with problem_yaml.open("w", encoding="utf-8") as fh:
        yaml.dump(body, fh)
    return problem_yaml
