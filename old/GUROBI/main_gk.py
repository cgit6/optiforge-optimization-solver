import pandas as pd
import copy as copy
import os
from gb3 import solve_multidimensional_knapsack # 二元解
from gb_relaxation import solve_multidimensional_knapsack_relaxation1,solve_multidimensional_knapsack_relaxation2 # 鬆弛解
import numpy as np

class main:
    # <===============读取.dat 文件===============>
    def __init__(self):
        self.batch_directory = "data/GK2"
        self.batch_files = os.listdir(self.batch_directory) # 使用 os.listdir 获取目录中的所有文件名
        # print(self.batch_files)

        # 執行參數
        # self.problem = ["01","02","03","04","05","06","07","08","09","10","11"]
        self.problem = ["01"]
        self.output_folder = "output/gurobi/GK"  # 设置输出資料夾路径
         # 問題參數
        self.items = None # 物品數量
        self.dim = None # 物品數量
        self.glbal_best = None # 理論最佳解
        self.values = None # 利潤
        self.weights = None # 資源限制
        self.capacities = None # 容量限制  

    # 轉換格式
    def transfrom(self,lines):
        # 將每行轉換為陣列
        data_arrays = np.array([],dtype=int)
        
        values = np.fromstring(lines, sep=' ')  # 移除换行符，并按空格分割
        row_array = np.array([value for value in values],dtype=int)
        # 移除最後一個未知元素
        data_arrays = np.append(data_arrays,row_array)
        return data_arrays
    
    def exe(self):
        pass

        for prob in self.problem:

            file_path = os.path.join(self.batch_directory, f"mk_gk{prob}.txt") # 構建完整的文件路徑
            # 讀取題庫
            with open(file_path, 'r') as batch_file:
                content = batch_file.read() # readlines() 跟 read() 有差 
                # print(content)
            
            file_list = self.transfrom(content) # 
            # print(file_list)

            # 問題參數
            self.items = int(file_list[0]) # 物品數量
            self.dim = int(file_list[1]) # 維度
            # self.glbal_best = file_list[2] # 全局最佳
            temp = file_list[2: 2 + (self.dim + 1) * self.items].reshape(( self.items, self.dim + 1))

            self.values = temp[:,0] # 利潤
            self.weights = temp[:,1:] # 資源
            self.capacities = file_list[2 + (self.dim + 1) * self.items: 2 + (self.dim + 1) * self.items + self.dim] # 容量

            # print(self.capacities)

            # 求離散解
            sol_lst,sol_index,fit = solve_multidimensional_knapsack(self.values, self.weights, self.capacities, self.items, self.dim)
            # 求鬆弛解(編碼限於0~1)
            sol_lst_r1,sol_index_r1,fit_r1 = solve_multidimensional_knapsack_relaxation1(self.values, self.weights, self.capacities, self.items, self.dim)
            # 求鬆弛解(編碼限於0~2)
            sol_lst_r2,sol_index_r2,fit_r2 = solve_multidimensional_knapsack_relaxation2(self.values, self.weights, self.capacities, self.items, self.dim)

            count1_y = 0
            count1_n = 0

            count2_y = 0
            count2_n = 0
            for i in range(len(sol_lst)):
                if sol_lst[i] == 1 and sol_lst_r1[i] == 0:
                    # print(sol_lst[i],sol_lst_r1[i])
                    count1_y += 1
                
                if sol_lst[i] == 0 and sol_lst_r1[i] != 0:
                    count1_n += 1

                if sol_lst[i] == 1 and sol_lst_r2[i] == 0:
                    # print(sol_lst[i],sol_lst_r2[i])
                    count2_y += 1

                if sol_lst[i] == 0 and sol_lst_r2[i] != 0:
                    count2_n += 1

            # print(f'正解有但鬆弛解1沒有 prob{prob}:',count1_y)
            # print(f'正解沒有但鬆弛解1有 prob{prob}:',count1_n)
            print(" ")
            print(f'正解有但鬆弛解2沒有 prob{prob}:',count2_y)
            print(f'正解沒有但鬆弛解2有 prob{prob}:',count2_n)

            # # <===========================輸出===============================>
            if not os.path.exists(f"{self.output_folder}"):
                os.makedirs(self.output_folder) 
            
            result_name = f"{self.output_folder}/mk_gk{prob}.csv"
            with open(result_name, 'w') as file:
                file.write(str(fit) + "\n")
                for lst in sol_lst:
                    file.write(str(lst) + ',')
                file.write("\n")
                for index in sol_index:
                    file.write(str(index) + ',')                

if __name__ == "__main__":
    main().exe() # 這裡放置只有在該文件作為主程序運行時才執行的代碼