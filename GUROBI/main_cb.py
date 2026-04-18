import pandas as pd
import copy as copy
import os
from gb3_limit import solve_multidimensional_knapsack
# from gb3 import solve_multidimensional_knapsack
import numpy as np
import re 
class main:
    # <===============读取.dat 文件===============>
    def __init__(self):
        self.batch_directory = ["OR5x100","OR5x250","OR5x500","OR10x100","OR10x250","OR10x500"] # 問題資料夾
        self.batch_files = [os.listdir(f"data/{file_list}") for file_list in self.batch_directory] # 使用 os.listdir 获取目录中的所有文件名
        # print(self.batch_files)

        # 執行參數
        self.problem = ["1","2","3","4","5"]
        self.output_folder = "output/gurobi/CB"  # 设置输出資料夾路径
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
        
        for i, batch_lst in enumerate(self.batch_directory):
            # print(batch_lst)
            for file_name in self.batch_files[i]:
                # print(file_name[:-4])
                match = re.search(r"_(\d+)", file_name)
                # print(match)
                if match:
                    pro_num = match.group(1)
                    # print(pro_num)
                    if int(pro_num) <=5:
                        file_path = os.path.join(f"data/{batch_lst}", file_name) # 構建完整的文件路徑
                        # print(file_path)
                        if file_name.endswith(".dat"):
                            with open(file_path, 'r') as batch_file:
                                content = batch_file.read() # readlines() 跟 read() 有差
                                # print(content)
                            file_list = self.transfrom(content) #
                            # print(file_list)
                            self.items = int(file_list[0]) # 物品數量
                            self.dim = int(file_list[1]) # 維度
                            self.values = file_list[3: 3 + self.items] # 利潤
                            self.weights = file_list[3 + self.items: 3 + self.items +self.items * self.dim].reshape((self.dim,self.items)).T# 資源
                            self.capacities = file_list[3 + self.items +self.items * self.dim: 3 + self.items +self.items * self.dim + self.dim] # 容量
                            
                            # print("w",self.weights,len(self.weights))
                            sol_lst,sol_index,fit = solve_multidimensional_knapsack(self.values, self.weights, self.capacities, self.items, self.dim)

                            # <===========================輸出===============================>
                            if not os.path.exists(f"{self.output_folder}/{batch_lst}"):
                                os.makedirs(f"{self.output_folder}/{batch_lst}") 
                            

                            result_name = f"{self.output_folder}/{batch_lst}/{file_name[:-4]}.csv"
                            with open(result_name, 'w') as file:
                                file.write(str(fit) + "\n")
                                for lst in sol_lst:
                                    file.write(str(lst) + ',')         

if __name__ == "__main__":
    main().exe() # 這裡放置只有在該文件作為主程序運行時才執行的代碼