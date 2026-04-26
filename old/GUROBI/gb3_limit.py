from gurobipy import *
import numpy as np
import time # 時間
np.set_printoptions(suppress=True) # 設定列印選項，關閉科學記數法


def solve_multidimensional_knapsack(values, weights, capacities,items,dimensions):
    # print(values)
    start_time = time.time() # 算法開始時間
    mode = Model("MultidimensionalKnapsack") # 建立新的 Gurobi 模型
    sol = mode.addVars(items, vtype = GRB.BINARY, name="x") # 創建二元決策變數
    
    mode.setObjective(quicksum(values[i] * sol[i] for i in range(items)), GRB.MAXIMIZE) # 目標函數：最大化總價值
   
    for dim in range(dimensions):
        mode.addConstr(quicksum(weights[i][dim] * sol[i] for i in range(items)) <= capacities[dim], f"capacity_{dim}") # 約束：每個維度的容量約束
    mode.setParam(GRB.Param.TimeLimit, 600.0)
    mode.optimize() # 解決最佳化問題



    sol_lst = np.zeros(items,dtype=int)
    sol_index = np.empty((0),dtype=int)
    for i in sol:
        if sol[i].x == 1:
            sol_lst[i] = 1 # 二元編碼
            sol_index = np.append(sol_index,i) # 輸出 選擇的物品
    fit = int(mode.objVal) # 適應值
    end_time = time.time() # 算法結束時間
    exe_time = end_time - start_time
    return sol_lst,sol_index,fit


if __name__ == "__main__":
    # Example data
    values = np.array([360, 83, 59, 130, 431, 67, 230, 52, 93, 125, 670, 892, 600, 38, 48, 147, 78, 256, 63, 17, 120, 164, 432, 35, 92, 110, 22, 42, 50, 323])
    weights = np.array([
        [7, 8, 3, 21, 94],
        [0, 66, 74, 40, 86],
        [30, 98, 88, 0, 80],
        [22, 50, 50, 6, 92],
        [80, 0, 55, 82, 31],
        [94, 30, 19, 91, 17],
        [11, 0, 0, 43, 65],
        [81, 88, 6, 30, 51],
        [70, 15, 30, 62, 46],
        [64, 37, 62, 91, 66],
        [59, 26, 17, 10, 44],
        [18, 72, 81, 41, 3],
        [0, 61, 25, 12, 26],
        [36, 57, 46, 4, 0],
        [3, 17, 67, 80, 39],
        [8, 27, 28, 77, 20],
        [15, 83, 36, 98, 11],
        [42, 3, 8, 50, 6],
        [9, 9, 1, 78, 55],
        [0, 66, 52, 35, 70],
        [42, 97, 19, 7, 11],
        [47, 42, 37, 1, 75],
        [52, 2, 27, 96, 82],
        [32, 44, 62, 67, 35],
        [26, 71, 39, 85, 47],
        [48, 11, 84, 4, 99],
        [55, 25, 16, 23, 5],
        [6, 74, 14, 38, 14],
        [29, 90, 21, 2, 23],
        [84, 20, 5, 57, 38]
    ])
    capacities = np.array([400, 500, 500, 600, 600])
    items = 30
    dimensions = 5
    
    sol_lst,sol_index,fit = solve_multidimensional_knapsack(values, weights, capacities, items, dimensions) # 解決多維背包問題
    # print(sol_lst,sol_index,fit)
