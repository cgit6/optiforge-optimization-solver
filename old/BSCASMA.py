import numpy as np
import copy as copy
import random
import math
import time
from scipy.optimize import linprog
from scipy.special import erf
from scipy.stats import norm

""" 目前的改進是基於SMAFA 混合算法的背景下進行的。嘗試加入強化學習的機制去優化選擇策略。"""

class BRLSMASCA:
    def __init__(self,items,dim,glbal_best,values,weights,capacities,seed=None):
        # 問題參數
        self.items = items # 物品+數量
        self.dim = dim # 維度
        self.glbal_best = glbal_best # 全局最佳
        # print(glbal_best)
        self.values = values # 利潤
        self.weights = weights # 資源限制
        # print(self.weights)
        self.capacities = capacities # 容量
        self.seed = seed # 隨機種子

        # 算法參數
        self.pop_size = 20
        self.max_iter = 5000
        self.cp_list = self.pseudo_utility() # cp 值
        self.cp_list_old = self.cp_list # 舊的 cp 值
        # 按照 偏好排序下來可以拿到的最後一個物品
        self.cp_list_sol, self.cp_list_total_fit, self.cp_list_sol_index, self.cp_list_last_item = self.cp_list_state() # cp 值的狀態
        # print(self.cp_list_last_item)
        self.std = int(self.items * 0.15) # 選擇概率
        self.appect_prob = self.accept_prob_func()
        print(self.appect_prob)

        # SMA 參數
        self.z = 0.03 # 轉換機率  
        self.W = np.zeros([self.pop_size,self.items]) # 權重參數
        self.a = None
        self.b = None

        # SCA 參數
        self.a = 2
        self.p = 0.5 # 策略轉換概率
        self.r1 = None

        # 算法變數
        self.pop_fit = np.zeros([self.pop_size], dtype = int) # 適應值(T)
        self.pop_fit_new = np.zeros([self.pop_size], dtype = int) # 適應值(T+1)
        self.pop_sol = None # 編碼
        
        # 個體最佳表現
        self.individual_best_sol = np.zeros([self.pop_size, self.items], dtype = int) # 當前個體的最佳解
        self.individual_best_fit = np.zeros([self.pop_size], dtype = int) # 當前個體的最佳適應值

        self.Gbest_sol, self.Gbest_fit, self.Gbest_index_sol = self.cp_list_sol, self.cp_list_total_fit, self.cp_list_sol_index # 全局最佳解
        print(self.Gbest_fit)

        self.initial_pop() # 生成離散可行解
        # print(self.pop_fit)

        # 強化學習參數
        self.prob_arr = np.array([0.04, 0.46, 0.25, 0.25] * self.pop_size) # action 的機率分布
        self.state = self.update_state() # 狀態
        self.table = np.zeros([self.pop_size,9,4])
        # print(self.state)
        self.alpha = 0.1
        self.gama = 0.9

        self.basic_line = None # 讓結果有正有負
        self.density_ranges = [(0, 0.333), (0.334, 0.666), (0.667, 1)] # 分三等
        self.distance_ranges = [(0, 0.333), (0.334, 0.666), (0.667, 1)] # 分三等

        self.policy_log = np.zeros([self.pop_size,self.max_iter], dtype=int) # 紀錄策略
        self.reward = np.zeros([self.pop_size], dtype=int) # 獎勵


    # 取得狀態範圍 (把算好的距離與密度傳進來當參數)
    def get_state(self, density, distance):
        density_range = next(i for i, r in enumerate(self.density_ranges) if density <= r[1])

        distance_range = next(i for i, r in enumerate(self.distance_ranges) if distance <= r[1])
        return density_range * 3 + distance_range

    # 取得 r1 r3 範圍
    def get_action(self, state, i):
        # state 是當前狀態下的所有動作的組合
        acts = self.table[i,state, :]
        # 找出當前狀態下所有動作大最大值
        max_val = np.max(acts)
        # Create a boolean mask that identifies all elements with the maximum value
        # 反正就是選到最大值的那個動作組合
        max_indices = np.where(acts == max_val)[0]
        # 使用 np.random.choice 從索引清單中隨機選擇具有最大值的索引
        # print(np.random.choice(max_indices))
        return np.random.choice(max_indices)

    def update_state(self):
        state = np.zeros([self.pop_size,2]) # 初始化強化學習的狀態

        for i in range(self.pop_size):
            # print(self.pop_sol[i].astype(int))
            # 計算當前個體與已知最佳解的漢明距離
            xor_result = self.Gbest_sol.astype(int) ^ self.pop_sol[i].astype(int)
            distance = np.sum(xor_result)

            # 標準化
            state[i,0] = distance / self.items

        ## 計算密度
        mean_values = np.mean(self.pop_sol, axis=0)
        # print(mean_values)
        # 生成平均编码
        average_encoding = np.where(mean_values >= 0.5, 1, 0)
        # print(average_encoding)
        hamming_distances = [np.sum(np.abs(self.pop_sol[i, :] - average_encoding)) for i in range(self.pop_size)]
        density = sum(np.sqrt(hd) for hd in hamming_distances) / (self.pop_size * self.items)
        state[:,1] = density
        # print(state)
        return state


    # # 更新 table
    def update(self, state, action, reward, alpha=0.1, gama=0.9):
        # 利用公式 3 計算當前的值
        self.table[state][action] += alpha * (reward + gama * np.max(self.table[state]) - self.table[state][action]) 

    def pseudo_utility(self):
        constraints = np.concatenate((self.capacities, np.ones(self.items)))
        i_weight = - np.concatenate((self.weights, np.eye(self.items)), axis=1)
        i_profit = self.values * -1
        result = linprog(constraints, i_weight, i_profit)
        shadow_price = result.x[:len(self.capacities)]
        pseudo_utilities = (-i_profit).T / (np.matmul(shadow_price.T, self.weights.T))
        return (- pseudo_utilities).argsort()

    def accept_prob_func(self):
        # 利用常態分布去定義可接受概率，希望越中間可更新的概率要更高

        # 建立一個索引數組
        indices = np.arange(self.items)

        # 使用以center_index為中心的常態分佈計算機率
        probabilities = norm.pdf(indices, loc = self.cp_list_last_item, scale = self.std)

        # 找出機率中的最大值和最小值
        max_prob = max(probabilities)
        min_prob = min(probabilities)

        # 將機率標準化為 0 到 1 範圍
        scaled_probabilities = (probabilities - min_prob) / (max_prob - min_prob)

        return scaled_probabilities
    
    def cp_list_state(self):
        # 如果依照線性鬆弛解出來後去測試限制條件能拿到多少東西跟最佳解?
        total_fit = 0 # 累積適應值
        surplus_cap = self.capacities # 剩餘容量
        sol_index = [] # 選擇的陣列
        sol = np.zeros([self.items])
        last_item = None
        # 裝到違反限制為止
        for item in self.cp_list:
            if np.all(surplus_cap >= self.weights[item]):
                sol_index.append(item) # 放入的物品集合
                sol[item] = 1 # 二元編碼

                # 更新剩餘重量
                surplus_cap = surplus_cap - self.weights[item]
                # 更新累積的利潤
                total_fit = total_fit + self.values[item]
                # 最後一個物品
                last_item = item 
            else:
                break

        return sol, total_fit, sol_index, last_item

    def initial_pop(self):
        self.pop_sol = np.zeros([self.pop_size,self.items]) # 初始化

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
                        self.pop_sol[i,j] = 1 # 拿取

            self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i])) # 計算適應值

            # 更新個體當前最佳解
            self.individual_best_sol[i] = self.pop_sol[i]
            self.individual_best_fit[i] = self.pop_fit[i]

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
    
    # ❗ 記得做單元測試
    def sort_pop(self):
        pop_sol = np.zeros([self.pop_size,self.items], dtype=int)
        pop_fit = np.zeros([self.pop_size], dtype=int)
        sorted_indices = np.argsort(self.pop_fit)[::-1]

        # 生成一個空的個體最佳陣列
        individual_best_sol = np.zeros([self.pop_size,self.items], dtype=int)
        individual_best_fit = np.zeros([self.pop_size], dtype=int)
        
        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]] # 當前個體解 
            pop_fit[i] = self.pop_fit[sorted_indices[i]] # 當前個體適應值

            # 更新當前個體最佳解
            individual_best_sol[i] = self.individual_best_sol[sorted_indices[i]]
            individual_best_fit[i] = self.individual_best_fit[sorted_indices[i]]
        
        return pop_sol, pop_fit, individual_best_sol, individual_best_fit
    
    
    def update_prob(self, index, policy):
        # 更新選擇參數
        self.pop_fit[index] # 當前個體的適應值
        self.sma_exe # SMA 執行次數
        self.sca_exe # SCA 執行次數

        step = 0.001
        temp = (self.pop_fit_new[index] - self.pop_fit[index]) / self.pop_fit[index]

        if temp > 0:
            if policy == 0:
                self.prob_arr[index, 0] = min(self.prob_arr[index, 0] + temp, 1) # 更新SMA選擇概率
                self.prob_arr[index, 1] = 1 - self.prob_arr[index, 0] # 更新 SCA 選擇概率 

            if policy == 1:
                self.prob_arr[index, 1] = min(self.prob_arr[index, 1] + temp, 1) # 更新 SCA 選擇概率
                self.prob_arr[index, 0] = 1 - self.prob_arr[index, 1] # 更新 SMA 選擇概率

    # sma 參數更新
    def update_sma_weight(self):
        # 更新 SMA 權重
        self.W = np.zeros([self.pop_size,self.items]) # 初始化 
        worstFit = self.pop_fit[-1] # 當前迭代的最差表現
        bestFit = self.pop_fit[0] # 當前迭代的最佳表現
        S = bestFit - worstFit # 當前最優適應度於最差適應度的差值，10E-8為極小值，避免分母為0

        for i in range(self.pop_size):
            if i < self.pop_size / 2: 
                # 適應度排前一半的 W 計算
                self.W[i,:]= 1 + np.random.random([self.items]) * np.log10((bestFit - self.pop_fit[i])/(S)+1)
            else: # 適應度排後一半的 W 計算
                self.W[i,:]= 1 - np.random.random([self.items]) * np.log10((bestFit - self.pop_fit[i])/(S)+1)

    def sma_global(self,i):
        # 執行 sma 全局更新
        self.pop_sol[i] = np.zeros(self.items) # 初始化
        accumulated_resources = np.zeros([self.dim]) # 累積重量
        # 偽效用降序排列
        for j in self.cp_list:  
            # 測試所有累積的資源 + 新物件是否劣於ks的約束
            if random.uniform(0, 1) < 0.5 :
                # 檢查該物品加入背包後是否違反限制
                accumulated_resources += self.weights[j]
                if np.all(accumulated_resources <= self.capacities):
                    self.pop_sol[i,j] = 1 # 拿取

    def sma_local(self,i,iter):
        # print(i,iter)
        # sma 參數，慣性因子a,b
        a = np.arctanh(-1 * ((iter + 1) / self.max_iter) + 1) # 0~3
        b = 1 - (iter + 1) / self.max_iter # 0~1

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
            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                self.pop_sol[i,j] = 1
            else:
                self.pop_sol[i,j] = 0

    def sca_sin(self,i):
        # 對物品決策更新
        for j in range(self.items):
            r2 = math.pi * random.uniform(0.0, 2.0) 
            r3 = random.uniform(0.0, 2.0)
            # r4 = random.uniform(0.0, 1.0)
            
            self.pop_sol[i,j] = self.individual_best_sol[i,j] + (self.r1 * math.sin(r2) * abs(r3 * self.Gbest_sol[j] - self.individual_best_sol[i,j]))

            # 轉換函數
            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                self.pop_sol[i,j] = 1
            else:
                self.pop_sol[i,j] = 0

    def sca_cos(self,i):
        # 對物品決策更新
        for j in range(self.items):
            # if self.appect_prob[j]
            r2 = math.pi * random.uniform(0.0, 2.0) 
            r3 = random.uniform(0.0, 2.0)
            # r4 = random.uniform(0.0, 1.0)
            
            self.pop_sol[i,j] = self.individual_best_sol[i,j] + (self.r1 * math.cos(r2) * abs(r3 * self.Gbest_sol[j] - self.individual_best_sol[i,j]))

            # 轉換函數
            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                self.pop_sol[i,j] = 1
            else:
                self.pop_sol[i,j] = 0

    # def local_search(self,i):
        


    # ❗ 記得做單元測試
    def update_cp_list(self,Gbest_sol):
        # 更新偏好順序
        # 需要邊界，符合限制下的集合，不符合現制下的集合
        Gbest_index_sol = np.where(Gbest_sol == 1)[0] # 有拿的部分
        
        drop = np.array(list(set(self.Gbest_index_sol) - set(Gbest_index_sol))) # 原本有但當前最佳解沒有
        take = np.array(list(set(Gbest_index_sol) - set(self.Gbest_index_sol))) # 原本沒有但當前最佳解有

        # 先移除
        clear_cp_list = self.cp_list[~np.isin(self.cp_list, drop)]
        clear_cp_list = clear_cp_list[~np.isin(clear_cp_list, take)]

        # 以 cp_list 可行解範圍的最後一個物品為中心更新偏好
        # 找當前中心點
        cp_list_last_item = self.cp_list_last_item - len(drop)


        # 更新偏好順序
        clear_cp_list = np.insert(clear_cp_list, cp_list_last_item+1, drop) # 先放剛拿出的物品
        clear_cp_list = np.insert(clear_cp_list, cp_list_last_item, take) # 再放剛放入的物品

        # print(clear_cp_list)

        self.cp_list_old = self.cp_list # 更新舊 cp 值

        self.cp_list = clear_cp_list # 

        # 更新偏好狀態
        self.cp_list_sol, self.cp_list_total_fit, self.cp_list_sol_index, self.cp_list_last_item = self.cp_list_state() # cp 值的狀態
        # 更新選擇概率
        self.appect_prob = self.accept_prob_func()

        # 要檢查邊界嗎?

    def run(self):

        self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop() # 排序
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解        

        for iter in range(self.max_iter):

            self.update_sma_weight() # 更新sma 權重
            self.r1 = self.a - self.a * (iter / self.max_iter) # 更新 sca_r1 目前是線性遞減
            
            # 個體更新
            for i in range(self.pop_size): 
                state = self.get_state(self.state[i,0], self.state[i,1]) # 選擇策略(蒙地卡羅?)
                action = self.get_action(state, i) # 狀態 >> 取得個體的動作，這裡返回的是 Q table col 索引
                
                # 如果等於 0 執行 SMA
                if action == 0:
                    # 執行sma 全局更新
                    self.sma_global(i)
                        
                # 執行 sma 局部更新
                elif action == 1:
                    self.sma_local(i,iter)

                # 如果等於 1 執行 SCA              
                elif action == 2:
                    self.sca_sin(i)
                
                elif action == 3:
                    self.sca_cos(i)
                
                else:
                    print("out of 3")             

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i])) # 計算適應值
                self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i],self.pop_fit[i]) # 修復與改進運算元
                self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop() # 排序

                # 更新個體最佳解
                if  self.pop_fit[i] > self.individual_best_fit[i]:
                    self.individual_best_sol[i] = copy.deepcopy(self.pop_sol[0])
                    self.individual_best_fit [i] = copy.deepcopy(self.pop_fit[0])
                    
                    # 更新 Q_table
                    self.update(state, action, reward=1, alpha=self.alpha, gama=self.gama) # 更新 Q_table
                else:
                    # 更新 Q_table
                    self.update(state, action, reward=-1, alpha=self.alpha, gama=self.gama) # 更新 Q_table

                # 更新全局最佳解
                if self.pop_fit[0] > self.Gbest_fit:
                    print("更新全局最佳解",self.Gbest_fit, "=>", self.pop_fit[0])
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解  

                # 如果找到最佳解則提早結束
                if self.Gbest_fit == self.glbal_best:
                    return self.Gbest_sol,self.Gbest_fit

            if iter % 50 == 0:
                print(iter," ",self.Gbest_fit)
            if iter == 500:
                print()

        return self.Gbest_sol,self.Gbest_fit



class BRLSMASCATest:
    def __init__(self,items,dim,glbal_best,values,weights,capacities,seed=None):
        # 問題參數
        self.items = items # 物品+數量
        self.dim = dim # 維度
        self.glbal_best = glbal_best # 全局最佳
        # print(glbal_best)
        self.values = values # 利潤
        self.weights = weights # 資源限制
        # print(self.weights)
        self.capacities = capacities # 容量
        self.seed = seed # 隨機種子

        # 算法參數
        self.pop_size = 20
        self.max_iter = 5000
        self.cp_list = self.pseudo_utility() # cp 值
        self.cp_list_old = self.cp_list # 舊的 cp 值
        # 按照 偏好排序下來可以拿到的最後一個物品
        # self.cp_list_sol, self.cp_list_total_fit, self.cp_list_sol_index, self.cp_list_last_item = self.cp_list_state() # cp 值的狀態
        # print(self.cp_list_last_item)
        self.std = int(self.items * 0.15) # 選擇概率
        # self.appect_prob = self.accept_prob_func()
        # print(self.appect_prob)

        # SMA 參數
        self.z = 0.03 # 轉換機率  
        self.W = np.zeros([self.pop_size,self.items]) # 權重參數
        self.a = None
        self.b = None

        # SCA 參數
        self.a = 2
        self.p = 0.5 # 策略轉換概率
        self.r1 = None

        # 算法變數
        self.pop_fit = np.zeros([self.pop_size], dtype = int) # 適應值(T)
        self.pop_fit_new = np.zeros([self.pop_size], dtype = int) # 適應值(T+1)
        self.pop_sol = None # 編碼
        

        # 個體最佳表現
        self.individual_best_sol = np.zeros([self.pop_size, self.items], dtype = int) # 當前個體的最佳解
        self.individual_best_fit = np.zeros([self.pop_size], dtype = int) # 當前個體的最佳適應值

        self.Gbest_sol = None # 全局最佳解
        self.Gbest_fit = None # 全局最佳解
        self.initial_pop() # 生成離散可行解

        
        # print(self.pop_fit)

        # 強化學習參數
        self.prob_arr = np.array([0.04, 0.46, 0.25, 0.25] * self.pop_size) # action 的機率分布
        self.exe_time = np.zeros([self.pop_size,4], dtype=int) # 紀錄每種方法的執行次數
        self.best_method = self.init_best_method()
        # print(self.best_method)

    def init_best_method(self):
        probabilities = [0.04, 0.46, 0.25, 0.25]
        elements = [0, 1, 2, 3]
        # 生成长度为20的数组，根据指定的概率分布选择元素
        random_selection = np.random.choice(elements, size=self.pop_size, p=probabilities)
        return random_selection
    

    def pseudo_utility(self):
        constraints = np.concatenate((self.capacities, np.ones(self.items)))
        i_weight = - np.concatenate((self.weights, np.eye(self.items)), axis=1)
        i_profit = self.values * -1
        result = linprog(constraints, i_weight, i_profit)
        shadow_price = result.x[:len(self.capacities)]
        pseudo_utilities = (-i_profit).T / (np.matmul(shadow_price.T, self.weights.T))
        return (- pseudo_utilities).argsort()

    # def accept_prob_func(self):
    #     # 利用常態分布去定義可接受概率，希望越中間可更新的概率要更高

    #     # 建立一個索引數組
    #     indices = np.arange(self.items)

    #     # 使用以center_index為中心的常態分佈計算機率
    #     probabilities = norm.pdf(indices, loc = self.cp_list_last_item, scale = self.std)

    #     # 找出機率中的最大值和最小值
    #     max_prob = max(probabilities)
    #     min_prob = min(probabilities)

    #     # 將機率標準化為 0 到 1 範圍
    #     scaled_probabilities = (probabilities - min_prob) / (max_prob - min_prob)

    #     return scaled_probabilities

    def initial_pop(self):
        self.pop_sol = np.zeros([self.pop_size,self.items]) # 初始化

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
                        self.pop_sol[i,j] = 1 # 拿取

            self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i])) # 計算適應值

            # 更新個體當前最佳解
            self.individual_best_sol[i] = self.pop_sol[i]
            self.individual_best_fit[i] = self.pop_fit[i]

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
    
    # ❗ 記得做單元測試
    def sort_pop(self):
        pop_sol = np.zeros([self.pop_size,self.items], dtype=int)
        pop_fit = np.zeros([self.pop_size], dtype=int)
        sorted_indices = np.argsort(self.pop_fit)[::-1]

        # 生成一個空的個體最佳陣列
        individual_best_sol = np.zeros([self.pop_size,self.items], dtype=int)
        individual_best_fit = np.zeros([self.pop_size], dtype=int)
        
        for i in range(self.pop_size):
            pop_sol[i] = self.pop_sol[sorted_indices[i]] # 當前個體解 
            pop_fit[i] = self.pop_fit[sorted_indices[i]] # 當前個體適應值

            # 更新當前個體最佳解
            individual_best_sol[i] = self.individual_best_sol[sorted_indices[i]]
            individual_best_fit[i] = self.individual_best_fit[sorted_indices[i]]
        
        return pop_sol, pop_fit, individual_best_sol, individual_best_fit
    
    def policy(self,i):
        r = random.uniform(0, 1)
        action = None
        if r < 0.9:
            action = self.best_method[i]
        else:
            array = [0, 1, 2, 3]
            filtered_array = [x for x in array if x != self.best_method[i]]
            action = random.choice(filtered_array)

        return action

    # sma 參數更新
    def update_sma_weight(self):
        # 更新 SMA 權重
        self.W = np.zeros([self.pop_size,self.items]) # 初始化 
        worstFit = self.pop_fit[-1] # 當前迭代的最差表現
        bestFit = self.pop_fit[0] # 當前迭代的最佳表現
        S = bestFit - worstFit # 當前最優適應度於最差適應度的差值，10E-8為極小值，避免分母為0

        for i in range(self.pop_size):
            if i < self.pop_size / 2: 
                # 適應度排前一半的 W 計算
                self.W[i,:]= 1 + np.random.random([self.items]) * np.log10((bestFit - self.pop_fit[i])/(S)+1)
            else: # 適應度排後一半的 W 計算
                self.W[i,:]= 1 - np.random.random([self.items]) * np.log10((bestFit - self.pop_fit[i])/(S)+1)

    def sma_global(self,i):
        # 執行 sma 全局更新
        self.pop_sol[i] = np.zeros(self.items) # 初始化
        accumulated_resources = np.zeros([self.dim]) # 累積重量
        # 偽效用降序排列
        for j in self.cp_list:  
            # 測試所有累積的資源 + 新物件是否劣於ks的約束
            if random.uniform(0, 1) < 0.5 :
                # 檢查該物品加入背包後是否違反限制
                accumulated_resources += self.weights[j]
                if np.all(accumulated_resources <= self.capacities):
                    self.pop_sol[i,j] = 1 # 拿取
        
        self.exe_time[i,0] += 1 # 更新值行紀錄

    def sma_local(self,i,iter):
        # print(i,iter)
        # sma 參數，慣性因子a,b
        a = np.arctanh(-1 * ((iter + 1) / self.max_iter) + 1) # 0~3
        b = 1 - (iter + 1) / self.max_iter # 0~1

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
            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                self.pop_sol[i,j] = 1
            else:
                self.pop_sol[i,j] = 0
        
        self.exe_time[i,1] += 1 # 更新值行紀錄

    def sca_sin(self,i):
        # 對物品決策更新
        for j in range(self.items):
            r2 = math.pi * random.uniform(0.0, 2.0) 
            r3 = random.uniform(0.0, 2.0)
            # r4 = random.uniform(0.0, 1.0)
            
            self.pop_sol[i,j] = self.individual_best_sol[i,j] + (self.r1 * math.sin(r2) * abs(r3 * self.Gbest_sol[j] - self.individual_best_sol[i,j]))

            # 轉換函數
            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                self.pop_sol[i,j] = 1
            else:
                self.pop_sol[i,j] = 0
        
        self.exe_time[i,2] += 1 # 更新值行紀錄

    def sca_cos(self,i):
        # 對物品決策更新
        for j in range(self.items):
            # if self.appect_prob[j]
            r2 = math.pi * random.uniform(0.0, 2.0) 
            r3 = random.uniform(0.0, 2.0)
            # r4 = random.uniform(0.0, 1.0)
            
            self.pop_sol[i,j] = self.individual_best_sol[i,j] + (self.r1 * math.cos(r2) * abs(r3 * self.Gbest_sol[j] - self.individual_best_sol[i,j]))

            # 轉換函數
            if random.uniform(0, 1) < np.abs(np.tanh(self.pop_sol[i,j])):
                self.pop_sol[i,j] = 1
            else:
                self.pop_sol[i,j] = 0
        
        self.exe_time[i,3] += 1 # 更新值行紀錄

    def run(self):

        self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop() # 排序
        self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
        self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解        

        for iter in range(self.max_iter):

            self.update_sma_weight() # 更新sma 權重
            self.r1 = self.a - self.a * (iter / self.max_iter) # 更新 sca_r1 目前是線性遞減
            
            # 個體更新
            for i in range(self.pop_size): 
                # 建構一個選擇策略
                action = self.policy(i) 
                
                # 如果等於 0 執行 SMA
                if action == 0:
                    # 執行sma 全局更新
                    self.sma_global(i)
                        
                # 執行 sma 局部更新
                elif action == 1:
                    self.sma_local(i,iter)

                # 如果等於 1 執行 SCA              
                elif action == 2:
                    self.sca_sin(i)
                
                elif action == 3:
                    self.sca_cos(i)
                
                else:
                    print("out of 3")             

                self.pop_fit[i] = np.sum(np.multiply(self.values, self.pop_sol[i])) # 計算適應值
                self.pop_sol[i], self.pop_fit[i] = self.repair(self.pop_sol[i],self.pop_fit[i]) # 修復與改進運算元
                self.pop_sol, self.pop_fit, self.individual_best_sol, self.individual_best_fit = self.sort_pop() # 排序

                # 更新個體最佳解
                if self.pop_fit[i] > self.individual_best_fit[i]:
                    self.individual_best_sol[i] = copy.deepcopy(self.pop_sol[0])
                    self.individual_best_fit[i] = copy.deepcopy(self.pop_fit[0])
                    self.best_method[i] = action # 更新最佳表現

                # 更新全局最佳解
                if self.pop_fit[0] > self.Gbest_fit:
                    self.Gbest_sol = copy.deepcopy(self.pop_sol[0]) # 全局最佳解
                    self.Gbest_fit = copy.deepcopy(self.pop_fit[0]) # 全局最佳解  

                # 如果找到最佳解則提早結束
                if self.Gbest_fit == self.glbal_best:
                    return self.Gbest_sol,self.Gbest_fit

            if iter % 50 == 0:
                print(iter," ",self.Gbest_fit)

        return self.Gbest_sol,self.Gbest_fit
