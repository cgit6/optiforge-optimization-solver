from gurobipy import *
import numpy as np
import time # 時間
np.set_printoptions(suppress=True) # 設定列印選項，關閉科學記數法

def solve_multidimensional_knapsack_relaxation1(values, weights, capacities,items,dimensions):
    
    mode = Model("MultidimensionalKnapsack") # 建立新的 Gurobi 模型
    mode.setParam('OutputFlag', 0)  # 禁用輸出
    sol = mode.addVars(items, vtype = GRB.CONTINUOUS, name="x",lb=0.0, ub=1.0) # 創建二元決策變數
    
    mode.setObjective(quicksum(values[i] * sol[i] for i in range(items)), GRB.MAXIMIZE) # 加入目標函數：最大化總價值
   
    for dim in range(dimensions):
        mode.addConstr(quicksum(weights[i][dim] * sol[i] for i in range(items)) <= capacities[dim], f"capacity_{dim}") # 限制條件(維度)：每個維度的容量限制
   
    mode.optimize() # 解決最佳化問題
    
    # 打印最優解
    sol_lst = np.zeros(items)
    sol_index = np.empty((0),dtype=int)
    # ??
    for i in sol:
        sol_lst[i] = sol[i].x # 二元編碼
        # print(sol[i].x)
            # sol_index = np.append(sol_index,i) # 輸出 選擇的物品
    fit = int(mode.objVal) # 適應值


    return sol_lst,sol_index,fit

def solve_multidimensional_knapsack_relaxation2(values, weights, capacities,items,dimensions):

    mode = Model("MultidimensionalKnapsack") # 建立新的 Gurobi 模型
    mode.setParam('OutputFlag', 0)  # 禁用輸出
    sol = mode.addVars(items, vtype = GRB.CONTINUOUS, name="x",lb=0.0, ub=0.7) # 創建二元決策變數
    
    mode.setObjective(quicksum(values[i] * sol[i] for i in range(items)), GRB.MAXIMIZE) # 加入目標函數：最大化總價值
   
    for dim in range(dimensions):
        mode.addConstr(quicksum(weights[i][dim] * sol[i] for i in range(items)) <= capacities[dim], f"capacity_{dim}") # 限制條件(維度)：每個維度的容量限制
   
    mode.optimize() # 解決最佳化問題

    # 打印最優解
    sol_lst = np.zeros(items,dtype=int)
    sol_index = np.empty((0),dtype=int)
    for i in sol:
        if sol[i].x == 1:
            sol_lst[i] = 1 # 二元編碼
            sol_index = np.append(sol_index,i) # 輸出 選擇的物品
    fit = int(mode.objVal) # 適應值

    return sol_lst,sol_index,fit


def solve_multidimensional_knapsack_lagrangian(values, weights, capacities, items, dimensions):
    # 初始化拉格朗日乘子
    lambdas = np.ones(dimensions)

    # 设置一个停止条件（例如迭代次数）
    max_iterations = 100
    step_size = 0.001

    best_obj = float('-inf')
    best_sol = None

    for iteration in range(max_iterations):
        mode = Model("MultidimensionalKnapsackRelaxation")
        mode.setParam('OutputFlag', 0)
        sol = mode.addVars(items, vtype=GRB.CONTINUOUS, name="x", lb=1, ub=1)

        # 原始目标函数加上拉格朗日松弛项
        lagrangian_obj = quicksum(values[i] * sol[i] for i in range(items))
        for dim in range(dimensions):
            lagrangian_obj -= lambdas[dim] * (quicksum(weights[i][dim] * sol[i] for i in range(items)) - capacities[dim])

        mode.setObjective(lagrangian_obj, GRB.MAXIMIZE)

        mode.optimize()

        # 检查是否找到了更好的解
        if mode.objVal > best_obj:
            best_obj = mode.objVal
            best_sol = [sol[i].x for i in range(items)]
            # for i in range(items):
            #     print(sol[i].x)

        # 更新拉格朗日乘子
        for dim in range(dimensions):
            violation = sum(weights[i][dim] * sol[i].x for i in range(items)) - capacities[dim]
            lambdas[dim] = max(0, lambdas[dim] - step_size * violation)

    return best_sol, best_obj

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
    
    sol_lst,sol_index,fit = solve_multidimensional_knapsack_relaxation1(values, weights, capacities, items, dimensions) # 解決多維背包問題
    print(sol_lst)
    print(fit)

    # # 接著比較 鬆弛解以外的整數解
    # int_sol = [1,1,0,1,1,0,1,0,0,0,1,1,1,0,0,1,0,1,0,0,0,0,1,0,0,0,0,0,0,1]
    # count = 0
    # for i in range(len(int_sol)):
    #     if int_sol[i] == 1 and sol_lst[i] == 0:
    #         count += 1

    # print(count)

    # print(sol_lst,fit,exe_time)
    best_sol, best_obj = solve_multidimensional_knapsack_lagrangian(values, weights, capacities, items, dimensions)

    print(best_sol)
    print(best_obj)

