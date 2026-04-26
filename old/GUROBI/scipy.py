from scipy.optimize import linprog
import numpy as np



def solve(values, weights, capacities,items,dimensions):
    constraints = np.concatenate((capacities, np.ones(items)))
    i_weight = - np.concatenate((weights, np.eye(items)), axis=1)
    i_profit = values * -1
    bounds = [(0, 1)] * (len(capacities) + items)  # 为每个决策变量设置界限
    result = linprog(constraints, i_weight, i_profit, bounds=bounds)

    print(result)
    shadow_price = result.x[:len(capacities)]
    pseudo_utilities = (-i_profit).T / (np.matmul(shadow_price.T, weights.T))
    return (-pseudo_utilities).argsort()

# 调用函数
sorted_items = solve()
