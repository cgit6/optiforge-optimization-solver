


class ExperimentResult:
    

class Experiment:
    """實驗模組"""
    def __init__():
        self.cfg # 實驗的設定
        self.eval # 評估實驗是否通過的函數
        self.result # 實驗結果
        self.solvers # 算法清單
        self.Problems # 題庫

    def run():
        """執行實驗"""
        pass

def build():
    # 1. 讀取 exp_cfg.yaml 轉成物件保存在 cfg 變數中
    # 2. 創建 Experiment 物件，把 cfg 保存在物件中
    # 3. 獲取設定檔中提到的求解器
    # 4. 創建實驗結果物件 ExperimentResult
    # 5. 返回 組合好的 Experiment 物件
    return Experiment(
        cfg=cfg,
        result=ExperimentResult,
        eval= eval.eval(),
        solvers=,
        Problems=
    )


