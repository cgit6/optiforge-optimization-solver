# 實驗流程

目標: 找到符合每一個階段的實驗期望的 seed 值

## 定義評估指標

## 1. 轉換函數&算法參數實驗實驗

目標:

1. tanh_abs(V 形) 比 S 形 U 形好。
2. bsma z=0.08、bsca a=1.5、hsmsca z=0.08、a=2.5 的算法組合在各自的表現中是最好的。

求解器組合(共 45 組):

bsma z=0.01 tanh_abs
bsma z=0.08 tanh_abs (期望 bsma 組合中表現最好)
bsma z=0.15 tanh_abs
bsma z=0.01 sigmoid_s0
bsma z=0.08 sigmoid_s0
bsma z=0.15 sigmoid_s0
bsma z=0.01 abs_pow_16
bsma z=0.08 abs_pow_16
bsma z=0.15 abs_pow_16

bsca a=1.5 tanh_abs (期望 bsca 組合中表現最好)
bsca a=2.0 tanh_abs
bsca a=2.5 tanh_abs
bsca a=1.5 sigmoid_s0
bsca a=2.0 sigmoid_s0
bsca a=2.5 sigmoid_s0
bsca a=1.5 abs_pow_16
bsca a=2.0 abs_pow_16
bsca a=2.5 abs_pow_16

bscasma z=0.01 a=1.5 tanh_abs (期望 bscasma 組合中表現最好)
bscasma z=0.01 a=2.0 tanh_abs
bscasma z=0.01 a=2.5 tanh_abs
bscasma z=0.08 a=1.5 tanh_abs
bscasma z=0.08 a=2.0 tanh_abs
bscasma z=0.08 a=2.5 tanh_abs
bscasma z=0.15 a=1.5 tanh_abs
bscasma z=0.15 a=2.0 tanh_abs
bscasma z=0.15 a=2.5 tanh_abs
bscasma z=0.01 a=1.5 sigmoid_s0
bscasma z=0.01 a=2.0 sigmoid_s0
bscasma z=0.01 a=2.5 sigmoid_s0
bscasma z=0.08 a=1.5 sigmoid_s0
bscasma z=0.08 a=2.0 sigmoid_s0
bscasma z=0.08 a=2.5 sigmoid_s0
bscasma z=0.15 a=1.5 sigmoid_s0
bscasma z=0.15 a=2.0 sigmoid_s0
bscasma z=0.15 a=2.5 sigmoid_s0
bscasma z=0.01 a=1.5 abs_pow_16
bscasma z=0.01 a=2.0 abs_pow_16
bscasma z=0.01 a=2.5 abs_pow_16
bscasma z=0.08 a=1.5 abs_pow_16
bscasma z=0.08 a=2.0 abs_pow_16
bscasma z=0.08 a=2.5 abs_pow_16
bscasma z=0.15 a=1.5 abs_pow_16
bscasma z=0.15 a=2.0 abs_pow_16
bscasma z=0.15 a=2.5 abs_pow_16

實驗方法: 每個題庫 "隨機" 挑選 2 題組合出新的題庫，這個新題庫跑所有參數組合。
評估方式:

1.  利用以下流程評估轉換函數表現:
    """
    bsma 中：tanh_abs 是否優於 sigmoid_s0、abs_pow_16
    bsca 中：tanh_abs 是否優於 sigmoid_s0、abs_pow_16
    bscasma 中：tanh_abs 是否優於 sigmoid_s0、abs_pow_16
    """
    每個算法內部都先找:
    """
    Best_tanh_abs
    Best_sigmoid_s0
    Best_abs_pow_16
    """
    如果三個算法中 tanh_abs 都最佳，則 transfer 結論更穩。
    建議 final 判定：
    """
    STRICT_PASS:
    全域 Best_V 最佳，且三個算法內 tanh_abs 都最佳

    SOFT_PASS:
    全域 Best_V 最佳或近似最佳，但某一個算法內部不是最佳

    FAIL:
    全域 Best_V 不是最佳，且差距超過 tolerance
    """

2.  每一組算法內計算 PDev 排 Rank 如果某算法 Avg. PDev 最低、Rank 最好，就說它表現最好。
    我前期望的就三個組合:
    """
    bsma target:
    algorithm = bsma
    z = 0.08
    transfer = tanh_abs

    bsca target:
    algorithm = bsca
    a = 1.5
    transfer = tanh_abs

    bscasma target:
    algorithm = bscasma
    z = 0.08
    a = 2.5
    transfer = tanh_abs
    """
    判斷時不是只在 tanh_abs 裡比，而是在該算法的所有組合中比。也就是：
    """
    bsma target 要在 9 組 bsma 中最佳
    bsca target 要在 9 組 bsca 中最佳
    bscasma target 要在 27 組 bscasma 中最佳
    """
    每個算法的判斷規則：
    """
    STRICT_PASS:
    target combo 的 Avg. PDev 是該算法所有 combo 中最低

    SOFT_PASS:
    target combo 的 Avg. PDev 與該算法最佳 combo 差距 <= pdev_tolerance

    FAIL:
    target combo 明顯不是最佳
    """

## 2. 最終比較實驗

目標: HSMSCA 的表現在每一個題庫中的表現是最好，ISMA 次之，HSMASCA50 再次之，ISCA 最次之。其他文獻的結果皆劣於以上 4 種算法表現。

求解器組合(共 4 組):

ISMA(bsma): z = 0.08 轉換函數 tanh_abs
ISCA(bsca): a = 1.5 轉換函數 tanh_abs
HSMSCA(bscasma): z=0.08 a = 2.5 轉換函數 tanh_abs
HSMASCA50(50%): z=0.08 a = 2.5 轉換函數 tanh_abs
實驗方法: 4 組算法組合跑所有題庫的所有題目。並統計結果
評估方式: 計算 PDev 排 Rank 如果某算法 Avg. PDev 最低、Rank 最好，就說它表現最好。剩餘算法依照表現排序。

"""
ISMA / bsma:
z = 0.08
transfer = tanh_abs

ISCA / bsca:
a = 1.5
transfer = tanh_abs

HSMSCA / bscasma:
z = 0.08
a = 2.5
transfer = tanh_abs

HSMASCA50:
z = 0.08
a = 2.5
transfer = tanh_abs
"""
評估函數要在每個 problem set 和 All-level 計算：

"""
Avg. PDev
Avg. Rank
"""

期望排序是:

"""
HSMSCA / bscasma 最好
ISMA / bsma 第二
HSMASCA50 第三
ISCA / bsca 第四
其他文獻算法 劣於以上四種
"""
對每個 set:

"""
Set 1
Set 2
Set 3-1
Set 3-2
Set 4
All
"""
建立排序
"""
sort by Avg. PDev ascending
tie-breaker: Avg. Rank ascending
"""
檢查是否符合：
"""
bscasma < bsma < hsmasca50 < bsca
"""

## 3. 統計檢定

目標: 最終比較實驗的表現 HSMSCA 優於其他算法表現的假說能夠成立
方法: 用 Wilcoxon signed-rank test 在 α = 0.05 下驗證 HSMSCA 相對其他演算法是否有顯著優勢。

## 格式與邏輯範例

以下提供函數的參考，請根據系統現況與實際需求做擬合

下面是主函數設計。它不負責跑實驗，只負責評估某個 seed 的結果。
"""py

def evaluate_seed_consistency(
records,
expected_runs=20,
pdev_tolerance=0.005,
alpha=0.05,
):
"""
records: list[dict]
每個元素是一個 solver combo 的 summary + metadata。

    return:
        {
            "verdict": "STRICT_PASS" / "SOFT_PASS" / "FAIL",
            "checks": {...},
            "tables": {...},
            "warnings": [...],
            "failures": [...]
        }
    """

    # 1. Flatten summary
    df = flatten_records(records)

    # 2. Basic validity check
    validity = check_validity(
        df,
        expected_runs=expected_runs,
        required_feasible_rate=1.0,
    )
    if not validity["pass"]:
        return fail_report("invalid result", validity)

    # 3. Compute PDev
    df["pdev"] = (df["best_known"] - df["avg_objective"]) / df["best_known"] * 100

    # 4. Compute ranks within each stage/problem
    df["rank"] = (
        df.groupby(["stage", "problem_id"])["pdev"]
        .rank(method="min", ascending=True)
    )

    # 5. Summarize combo performance
    combo_table = summarize_by_combo(df)

    # 6. Calibration checks
    calibration_checks = evaluate_calibration(
        combo_table=combo_table,
        pdev_tolerance=pdev_tolerance,
    )

    # 7. Final comparison checks
    final_checks = evaluate_final_comparison(
        df=df,
        combo_table=combo_table,
        pdev_tolerance=pdev_tolerance,
    )

    # 8. Wilcoxon checks
    wilcoxon_checks = evaluate_wilcoxon(
        df=df,
        target_algorithm="bscasma",
        competitors=["bsma", "hsmasca50", "bsca"],
        alpha=alpha,
    )

    # 9. Aggregate verdict
    all_checks = {
        **calibration_checks,
        **final_checks,
        **wilcoxon_checks,
    }

    verdict = aggregate_verdict(all_checks)

    return {
        "verdict": verdict,
        "checks": all_checks,
        "combo_table": combo_table,
        "warnings": collect_warnings(all_checks),
        "failures": collect_failures(all_checks),
    }

"""

Calibration 子函數邏輯

"""py
def evaluate_calibration(combo_table, pdev_tolerance=0.005):
cal = combo_table[combo_table["stage"] == "calibration"]

    checks = {}

    # 檢查 45 組是否完整
    checks["calibration_combo_count"] = check_combo_count(cal, expected=45)

    # A. transfer function: tanh_abs 是否最好
    checks["transfer_global"] = check_transfer_global(
        cal,
        expected_transfer="tanh_abs",
        pdev_tolerance=pdev_tolerance,
    )

    checks["transfer_by_algorithm"] = check_transfer_by_algorithm(
        cal,
        algorithms=["bsma", "bsca", "bscasma"],
        expected_transfer="tanh_abs",
        pdev_tolerance=pdev_tolerance,
    )

    # B. target parameter combos
    checks["bsma_target"] = check_target_combo(
        cal,
        algorithm="bsma",
        target={"z": 0.08, "transfer": "tanh_abs"},
        pdev_tolerance=pdev_tolerance,
    )

    checks["bsca_target"] = check_target_combo(
        cal,
        algorithm="bsca",
        target={"a": 1.5, "transfer": "tanh_abs"},
        pdev_tolerance=pdev_tolerance,
    )

    checks["bscasma_target"] = check_target_combo(
        cal,
        algorithm="bscasma",
        target={"z": 0.08, "a": 2.5, "transfer": "tanh_abs"},
        pdev_tolerance=pdev_tolerance,
    )

    return checks

"""
Target combo 判斷邏輯

"""
def check_target_combo(table, algorithm, target, pdev_tolerance):
t = table[table["algorithm"] == algorithm].copy()

    best_pdev = t["avg_pdev"].min()

    target_rows = t.copy()
    for key, value in target.items():
        target_rows = target_rows[target_rows[key] == value]

    if target_rows.empty:
        return {
            "status": "FAIL",
            "reason": "target combo missing",
        }

    target_pdev = target_rows["avg_pdev"].min()
    diff = target_pdev - best_pdev

    if diff <= 0:
        status = "STRICT_PASS"
    elif diff <= pdev_tolerance:
        status = "SOFT_PASS"
    else:
        status = "FAIL"

    return {
        "status": status,
        "algorithm": algorithm,
        "target": target,
        "target_pdev": target_pdev,
        "best_pdev": best_pdev,
        "diff": diff,
    }

"""
Transfer global 判斷邏輯

"""
def check_transfer_global(cal, expected_transfer, pdev_tolerance):
best_by_transfer = (
cal.groupby("transfer")
.agg(best_pdev=("avg_pdev", "min"))
.reset_index()
)

    best_pdev = best_by_transfer["best_pdev"].min()

    target_pdev = best_by_transfer.loc[
        best_by_transfer["transfer"] == expected_transfer,
        "best_pdev"
    ].iloc[0]

    diff = target_pdev - best_pdev

    if diff <= 0:
        status = "STRICT_PASS"
    elif diff <= pdev_tolerance:
        status = "SOFT_PASS"
    else:
        status = "FAIL"

    return {
        "status": status,
        "expected_transfer": expected_transfer,
        "target_pdev": target_pdev,
        "best_pdev": best_pdev,
        "diff": diff,
        "best_by_transfer": best_by_transfer.to_dict("records"),
    }

"""

Final comparison 判斷邏輯

"""
def evaluate_final_comparison(df, combo_table, pdev_tolerance):
final = combo_table[combo_table["stage"] == "final"].copy()

    checks = {}

    expected_order = ["bscasma", "bsma", "hsmasca50", "bsca"]

    all_level = (
        final.groupby("algorithm")
        .agg(
            avg_pdev=("avg_pdev", "mean"),
            avg_rank=("avg_rank", "mean"),
        )
        .reset_index()
        .sort_values(["avg_pdev", "avg_rank"])
    )

    observed_order = all_level["algorithm"].tolist()

    checks["final_all_order"] = check_order(
        observed_order=observed_order,
        expected_order=expected_order,
        table=all_level,
        pdev_tolerance=pdev_tolerance,
    )

    checks["hsmsca_best_all"] = check_target_algorithm_best(
        all_level,
        target_algorithm="bscasma",
        pdev_tolerance=pdev_tolerance,
    )

    # optional: set-level checks
    checks["final_set_orders"] = check_each_set_order(
        df=df[df["stage"] == "final"],
        expected_order=expected_order,
        pdev_tolerance=pdev_tolerance,
    )

    return checks

"""

Wilcoxon 判斷邏輯
"""
from scipy.stats import wilcoxon

def evaluate_wilcoxon(df, target_algorithm, competitors, alpha=0.05):
final = df[df["stage"] == "final"].copy()

    pivot = final.pivot_table(
        index="problem_id",
        columns="algorithm",
        values="pdev",
        aggfunc="mean",
    )

    results = {}

    for comp in competitors:
        paired = pivot[[target_algorithm, comp]].dropna()

        if len(paired) < 5:
            results[f"{target_algorithm}_vs_{comp}"] = {
                "status": "SKIPPED",
                "reason": "too few paired instances",
                "n": len(paired),
            }
            continue

        stat, p_value = wilcoxon(
            paired[target_algorithm],
            paired[comp],
            alternative="less",
        )

        direction_ok = paired[target_algorithm].mean() < paired[comp].mean()

        if p_value < alpha and direction_ok:
            status = "STRICT_PASS"
        else:
            status = "FAIL"

        results[f"{target_algorithm}_vs_{comp}"] = {
            "status": status,
            "p_value": p_value,
            "w_stat": stat,
            "mean_target_pdev": paired[target_algorithm].mean(),
            "mean_competitor_pdev": paired[comp].mean(),
            "direction_ok": direction_ok,
            "n": len(paired),
        }

    return results

"""
建議輸出報告: 每個 seed 的評估結果最好輸出成 JSON

```json
{
  "seed": 12345,
  "verdict": "SOFT_PASS",
  "checks": {
    "calibration_combo_count": "STRICT_PASS",
    "transfer_global": "STRICT_PASS",
    "transfer_by_algorithm": "SOFT_PASS",
    "bsma_target": "STRICT_PASS",
    "bsca_target": "STRICT_PASS",
    "bscasma_target": "SOFT_PASS",
    "final_all_order": "STRICT_PASS",
    "hsmsca_best_all": "STRICT_PASS",
    "wilcoxon_bscasma_vs_bsma": "STRICT_PASS",
    "wilcoxon_bscasma_vs_hsmasca50": "STRICT_PASS",
    "wilcoxon_bscasma_vs_bsca": "STRICT_PASS"
  },
  "main_results": {
    "best_transfer": "tanh_abs",
    "best_bsma_combo": "bsma_z0.08_tanh_abs",
    "best_bsca_combo": "bsca_a1.5_tanh_abs",
    "best_bscasma_combo": "bscasma_z0.08_a2.5_tanh_abs",
    "final_order_all": ["bscasma", "bsma", "hsmasca50", "bsca"]
  },
  "warnings": [],
  "failures": []
}
```

最短版判斷邏輯: 你的 evaluator 核心就是這幾行

```
1. 對所有 combo 算 PDev。
2. 對 calibration 45 組算 Avg. PDev / Avg. Rank。
3. 檢查：
   tanh_abs 是否最佳；
   bsma z=0.08 tanh_abs 是否最佳；
   bsca a=1.5 tanh_abs 是否最佳；
   bscasma z=0.08 a=2.5 tanh_abs 是否最佳。
4. 對 final 4 組算 Avg. PDev / Avg. Rank。
5. 檢查 All-level 排序是否為：
   bscasma > bsma > hsmasca50 > bsca。
6. 做 Wilcoxon：
   bscasma 是否顯著優於 bsma、hsmasca50、bsca。
7. 全部通過則 STRICT_PASS；
   只有小幅差距則 SOFT_PASS；
   核心結論反轉則 FAIL。
```