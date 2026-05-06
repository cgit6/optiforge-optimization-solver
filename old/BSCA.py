import numpy as np
import copy as copy
import random
import math
import time
from scipy.optimize import linprog
from scipy.special import erf

# 鬆弛 + SCA 演算法
class BSCA_V1_25:
    def __init__(self,items,dim,glbal_best,values,weights,capacities):
        # 問題參數
        self.items = items # 物品+數量
        self.dim = dim # 維度
        self.glbal_best = glbal_best # 全局最佳
        self.values = values # 利潤
        self.weights = weights # 資源限制
        self.capacities = capacities # 容量

        # 算法參數
        self.pop_size = 20
        self.max_iter = 5000
        self.cp_list = self.pseudo_utility() # cp 值
        self.a = 2.5 # SCA 參數

        # 算法變數
        self.pop_fit = np.zeros([self.pop_size], dtype = int) # 適應值
        self.pop_sol = self.initial_pop() # 生成離散可行解
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解

    def pseudo_utility(self):
        constraints = np.concatenate((self.capacities, np.ones(self.items)))
        i_weight = - np.concatenate((self.weights, np.eye(self.items)), axis=1)
        i_profit = self.values * -1
        result = linprog(constraints, i_weight, i_profit)
        shadow_price = result.x[:len(self.capacities)]
        pseudo_utilities = (-i_profit).T / (np.matmul(shadow_price.T, self.weights.T))
        return (- pseudo_utilities).argsort()
    
    def initial_pop(self):
        population = np.zeros([self.pop_size,self.items]) # 初始化

        # 生成初始解
        for i in range(self.pop_size):
            accumulated_resources = np.zeros([self.dim]) # 累積重量
            for j in self.cp_list:
                # 偽效用降序排列
                # 測試所有累積的資源+新物件是否劣於ks的約束
                if random.uniform(0, 1) < 0.5 :
                    # 檢查該物品加入背包後是否違反限制
                    accumulated_resources += self.weights[j]
                    if np.all(accumulated_resources <= self.capacities):
                        population[i,j] = 1 # 拿取

            self.pop_fit[i] = np.sum(np.multiply(self.values, population[i])) # 計算適應值
        return population
    
    def repair(self,trial_sol,trial_fit):
        # 計算當前的重量
        resource_consumption = np.sum(np.multiply(self.weights.T,trial_sol),axis=1)
        # print("resource_consumption",resource_consumption)
        # 修復: 從 cp 值最低的開始判斷
        for i in np.flip(self.cp_list):
            if np.any(resource_consumption > self.capacities):
                if trial_sol[i] == 1:
                    trial_sol[i] = 0
                    resource_consumption -= self.weights[i] # 更新當前重量
                    trial_fit -= self.values[i] # 更新適應值
            else:
                break

        # 改進
        for i in self.cp_list:
            if trial_sol[i] == 0:
                if np.all(resource_consumption+self.weights[i] <= self.capacities):
                    trial_sol[i] = 1
                    resource_consumption += self.weights[i] # 更新當前重量
                    trial_fit += self.values[i] # 更新適應值
        return trial_sol,trial_fit
    
    def sort_pop(self):
        pop_sol = np.zeros([self.pop_size,self.items])
        pop_fit = np.zeros([self.pop_size])
        sorted_indices = np.argsort(self.pop_fit)[::-1]
        
        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]]
            pop_fit[i] = self.pop_fit[sorted_indices[i]]
        
        return pop_sol,pop_fit

    def run(self):

        self.pop_sol,self.pop_fit = self.sort_pop() # 排序
        self.Gbest_sol = self.pop_sol[0] # 最佳解
        self.Gbest_fit = self.pop_fit[0] # 最佳適應值

        for iter in range(self.max_iter):
            # 位置更新
            for i in range(self.pop_size):
                r1 = self.a - self.a * (iter / self.max_iter) # radius:隨著迭代過程線性遞減

                # 對每個決策變數更新
                for j in range(self.items):
                    r2 = math.pi * random.uniform(0.0, 2.0)
                    r3 = random.uniform(0.0, 2.0) # weight
                    r4 = random.uniform(0.0, 1.0)
                    
                    if r4 < 0.5:
                        self.pop_sol[i,j] = self.pop_sol[i,j] + (r1 * math.sin(r2) * abs(r3 * self.Gbest_sol[j] - self.pop_sol[i,j]))
                    else:
                        self.pop_sol[i,j] = self.pop_sol[i,j] + (r1 * math.cos(r2) * abs(r3 * self.Gbest_sol[j] - self.pop_sol[i,j]))
                    
                    # 轉換函數
                    if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                        self.pop_sol[i,j] = 1
                    else:
                        self.pop_sol[i,j] = 0

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i])) # 計算適應值
                self.pop_sol[i],self.pop_fit[i] = self.repair(self.pop_sol[i],self.pop_fit[i]) # 修復與改進運算元
                self.pop_sol,self.pop_fit = self.sort_pop() # 排序
            
                # 更新全局最佳解
                if self.pop_fit[0] > self.Gbest_fit:
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解                             
                
                # 如果找到理論最佳解則提早結束
                if self.Gbest_fit == self.glbal_best:
                    return self.Gbest_sol,self.Gbest_fit

            if iter % 500 == 0:
                print(iter," ",self.Gbest_fit)
        return self.Gbest_sol,self.Gbest_fit

# 鬆弛 + SCA 演算法
class BSCA:
    def __init__(self,items,dim,glbal_best,values,weights,capacities):
        # 問題參數
        self.items = items # 物品+數量
        self.dim = dim # 維度
        self.glbal_best = glbal_best # 全局最佳
        self.values = values # 利潤
        self.weights = weights # 資源限制
        self.capacities = capacities # 容量

        # 算法參數
        self.pop_size = 20
        self.max_iter = 5000
        self.cp_list = self.pseudo_utility() # cp 值

        self.a = 2.0 # SCA 參數



        # 算法變數
        self.pop_fit = np.zeros([self.pop_size], dtype = int) # 適應值
        self.pop_sol = self.initial_pop() # 生成離散可行解
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解

    def pseudo_utility(self):
        constraints = np.concatenate((self.capacities, np.ones(self.items)))
        i_weight = - np.concatenate((self.weights, np.eye(self.items)), axis=1)
        i_profit = self.values * -1
        result = linprog(constraints, i_weight, i_profit)
        shadow_price = result.x[:len(self.capacities)]
        pseudo_utilities = (-i_profit).T / (np.matmul(shadow_price.T, self.weights.T))
        return (- pseudo_utilities).argsort()
    
    def initial_pop(self):
        population = np.zeros([self.pop_size,self.items]) # 初始化

        # 生成初始解
        for i in range(self.pop_size):
            accumulated_resources = np.zeros([self.dim]) # 累積重量
            for j in self.cp_list:
                # 偽效用降序排列
                # 測試所有累積的資源+新物件是否劣於ks的約束
                if random.uniform(0, 1) < 0.5 :
                    # 檢查該物品加入背包後是否違反限制
                    accumulated_resources += self.weights[j]
                    if np.all(accumulated_resources <= self.capacities):
                        population[i,j] = 1 # 拿取

            self.pop_fit[i] = np.sum(np.multiply(self.values, population[i])) # 計算適應值
        return population
    
    def repair(self,trial_sol,trial_fit):
        # 計算當前的重量
        resource_consumption = np.sum(np.multiply(self.weights.T,trial_sol),axis=1)
        # print("resource_consumption",resource_consumption)
        # 修復: 從 cp 值最低的開始判斷
        for i in np.flip(self.cp_list):
            if np.any(resource_consumption > self.capacities):
                if trial_sol[i] == 1:
                    trial_sol[i] = 0
                    resource_consumption -= self.weights[i] # 更新當前重量
                    trial_fit -= self.values[i] # 更新適應值
            else:
                break

        # 改進
        for i in self.cp_list:
            if trial_sol[i] == 0:
                if np.all(resource_consumption+self.weights[i] <= self.capacities):
                    trial_sol[i] = 1
                    resource_consumption += self.weights[i] # 更新當前重量
                    trial_fit += self.values[i] # 更新適應值
        return trial_sol,trial_fit
    
    def sort_pop(self):
        pop_sol = np.zeros([self.pop_size,self.items])
        pop_fit = np.zeros([self.pop_size])
        sorted_indices = np.argsort(self.pop_fit)[::-1]
        
        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]]
            pop_fit[i] = self.pop_fit[sorted_indices[i]]
        
        return pop_sol,pop_fit

    def run(self):

        self.pop_sol,self.pop_fit = self.sort_pop() # 排序
        # print(self.pop_sol)
        # print(self.pop_fit)

        self.Gbest_sol = self.pop_sol[0] # 最佳解
        self.Gbest_fit = self.pop_fit[0] # 最佳適應值

        for iter in range(self.max_iter):
            # 位置更新
            for i in range(self.pop_size):
                r1 = self.a - self.a * (iter / self.max_iter) # radius:隨著迭代過程線性遞減

                # 對每個決策變數更新
                for j in range(self.items):
                    r2 = math.pi * random.uniform(0.0, 2.0)
                    r3 = random.uniform(0.0, 2.0) # weight
                    r4 = random.uniform(0.0, 1.0)
                    
                    if r4 < 0.5:
                        self.pop_sol[i,j] = self.pop_sol[i,j] + (abs(r1 * math.sin(r2)) * r3 * self.Gbest_sol[j] - self.pop_sol[i,j])
                    else:
                        self.pop_sol[i,j] = self.pop_sol[i,j] + (abs(r1 * math.cos(r2)) * r3 * self.Gbest_sol[j] - self.pop_sol[i,j])
                    
                    # 轉換函數
                    if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                        self.pop_sol[i,j] = 1
                    else:
                        self.pop_sol[i,j] = 0

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i])) # 計算適應值
                self.pop_sol[i],self.pop_fit[i] = self.repair(self.pop_sol[i],self.pop_fit[i]) # 修復與改進運算元
                self.pop_sol,self.pop_fit = self.sort_pop() # 排序
            
                # 更新全局最佳解
                if self.pop_fit[0] > self.Gbest_fit:
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解                             
                
                # 如果找到理論最佳解則提早結束
                if self.Gbest_fit == self.glbal_best:
                    return self.Gbest_sol,self.Gbest_fit

            if iter % 500 == 0:
                print(iter," ",self.Gbest_fit)
        return self.Gbest_sol,self.Gbest_fit
