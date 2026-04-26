import numpy as np
# np.set_printoptions(suppress=True) # 設定列印選項，關閉科學記數法
import copy as copy
from scipy.optimize import linprog
from scipy.special import erf

class BSMA_V1_008:
    def __init__(self,items,dim,glbal_best,values,weights,capacities,seed=None):
        # 問題參數
        self.items = items # 物品+數量
        self.dim = dim # 維度
        self.glbal_best = glbal_best # 全局最佳
        self.values = values # 利潤
        self.weights = weights # 資源限制
        self.capacities = capacities # 容量
        # print(self.capacities)
        self.seed = seed

        # 算法參數
        self.pop_size = 20
        self.max_iter = 5000
        self.cp_list = self.pseudo_utility() # cp 值
        # print(self.cp_list)
        self.z = 0.08 # 轉換機率  
        self.W = np.zeros([self.pop_size,self.items]) # 權重參數


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
                if np.random.uniform(0.0, 1.0) < 0.5:
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
                else:
                    break
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
        np.random.seed(self.seed)

        self.pop_sol,self.pop_fit = self.sort_pop() # 排序
        # print(self.pop_sol)
        # print(self.pop_fit)

        self.Gbest_sol = self.pop_sol[0] # 最佳解
        self.Gbest_fit = self.pop_fit[0] # 最佳適應值

        for iter in range(self.max_iter):

            # 更新權重
            self.W = np.zeros([self.pop_size,self.items]) # 初始化 
            worstFit = self.pop_fit[-1] # w 參數
            bestFit = self.pop_fit[0] # w 參數
            S = bestFit - worstFit if bestFit - worstFit > 0 else 0.0001 # 當前最優適應度於最差適應度的差值，10E-8為極小值，避免分母為0；
            for i in range(self.pop_size):
                if i < self.pop_size / 2: 
                    # 適應度排前一半的 W 計算
                    self.W[i,:]= 1 + np.random.random([self.items]) * np.log10((bestFit - self.pop_fit[i])/(S)+1)
                else: # 適應度排後一半的 W 計算
                    self.W[i,:]= 1 - np.random.random([self.items]) * np.log10((bestFit - self.pop_fit[i])/(S)+1)

            # 慣性因子a,b
            a = np.arctanh(-1 * ((iter + 1) / self.max_iter) + 1)
            b = 1 - (iter + 1) / self.max_iter 

            # 位置更新
            for i in range(self.pop_size):
                if np.random.random() < self.z:
                    # print("self.pop_sol[i]",self.pop_sol[i])
                    # 全局搜索

                    self.pop_sol[i] = np.zeros(self.items) # 初始化
                    accumulated_resources = np.zeros([self.dim]) # 累積重量
                    for j in self.cp_list: 
                        # 偽效用降序排列
                        # 測試所有累積的資源+新物件是否劣於ks的約束
                        if np.random.uniform(0.0, 1.0) < 0.5:
                            # 檢查該物品加入背包後是否違反限制
                            accumulated_resources += self.weights[j]
                            if np.all(accumulated_resources <= self.capacities):
                                self.pop_sol[i,j] = 1 # 拿取

                else:
                    p = np.tanh(abs(self.pop_fit[i] - self.Gbest_fit)) # 決定執行局部公式 1 或 2
                    vb = np.random.uniform(-a, a, self.items) # 參數
                    vc = np.random.uniform(-b, b, self.items) # 參數

                    for j in range(self.items):
                        r = np.random.random() # 隨機值
                        A,B = np.random.choice(list(set(range(0, self.pop_size)) - {i}), 2, replace=False)
                        if r < p:
                            self.pop_sol[i,j] = self.Gbest_sol[j] + vb[j] * (self.W[i,j] * self.pop_sol[A,j] - self.pop_sol[B,j])   
                        else:
                            self.pop_sol[i,j] = vc[j] * self.pop_sol[i, j] 

                        # 轉換函數
                        if np.random.uniform(0.0, 1.0) < np.abs(np.tanh(self.pop_sol[i,j])):
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
            # 提早結束
            if self.Gbest_fit == self.glbal_best:
                return self.Gbest_sol,self.Gbest_fit

            if iter % 50 == 0:
                # self.pop_sol = self.initial_pop() # 重新初始化
                print(iter," ",self.Gbest_fit)
        return self.Gbest_sol,self.Gbest_fit