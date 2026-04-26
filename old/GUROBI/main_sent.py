import pandas as pd
import copy as copy
import os
from gb3 import solve_multidimensional_knapsack
import numpy as np

class main:
    # <===============读取.dat 文件===============>
    def __init__(self):
        self.batch_directory = "data\SENT"
        self.batch_files = os.listdir(self.batch_directory) # 使用 os.listdir 获取目录中的所有文件名
        # print(batch_files)

        # 執行參數
        self.problem = ["01","02"]
        # self.problem = ["30"]
        self.output_folder = "output\gurobi\SENT"  # 设置输出資料夾路径

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
        
        for prob in self.problem:

            file_path = os.path.normpath(os.path.join(self.batch_directory, f"sent{prob}.dat")) # 構建完整的文件路徑
            # 讀取題庫
            with open(file_path, 'r') as batch_file:
                content = batch_file.read() # readlines() 跟 read() 有差 
                # print(content)
            
            file_list = self.transfrom(content) # 
            # print(file_list)

            # # 問題參數
            self.items = int(file_list[0]) # 物品數量
            self.dim = int(file_list[1]) # 維度
            # self.glbal_best = file_list[2] # 全局最佳
            self.values = file_list[3: 3 + self.items] # 利潤
            self.weights = file_list[3 + self.items: 3 + self.items +self.items * self.dim].reshape((self.dim,self.items)).T # 資源
            self.capacities = file_list[3 + self.items +self.items * self.dim: 3 + self.items +self.items * self.dim + self.dim] # 容量

            sol_lst,sol_index,fit,exe_time = solve_multidimensional_knapsack(self.values, self.weights, self.capacities, self.items, self.dim)

            # <===========================輸出===============================>
            if not os.path.exists(f"{self.output_folder}"):
                os.makedirs(self.output_folder) 
            
            result_name = f"{self.output_folder}\sent{prob}.csv"
            with open(result_name, 'w') as file:
                file.write(str(fit) + "\n")
                file.write(str(exe_time) + "\n")
                for lst in sol_lst:
                    file.write(str(lst) + ',')
                file.write("\n")
                for index in sol_index:
                    file.write(str(index) + ',')                

if __name__ == "__main__":
    main().exe() # 這裡放置只有在該文件作為主程序運行時才執行的代碼