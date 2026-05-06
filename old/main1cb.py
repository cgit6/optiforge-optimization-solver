import pandas as pd
import copy as copy
import os
# from gb3 import solve_multidimensional_knapsack
import numpy as np
import re 
import inspect
import BSMA
import BSCASMA # 混合SCA+SMA



class main:
    # <===============读取.dat 文件===============>
    def __init__(self):
        self.batch_directory = ["OR5x100","OR5x250","OR5x500","OR10x100","OR10x250","OR10x500"] # 問題資料夾
        self.batch_files = [os.listdir(f"data/{file_list}") for file_list in self.batch_directory] # 使用 os.listdir 获取目录中的所有文件名
        # print(self.batch_files)

        self.algo_file = BSCASMA
        self.global_best = {"OR5x100-0.25_1.dat":24381, "OR5x100-0.25_2.dat":24274, "OR5x100-0.25_3.dat":23551, "OR5x100-0.25_4.dat":23534, "OR5x100-0.25_5.dat":23991, "OR5x250-0.25_1.dat":59312, "OR5x250-0.25_2.dat":61472, "OR5x250-0.25_3.dat":62130, "OR5x250-0.25_4.dat":59463, "OR5x250-0.25_5.dat":58951, "OR5x500-0.25_1.dat":120148, "OR5x500-0.25_2.dat":117879, "OR5x500-0.25_3.dat":121131, "OR5x500-0.25_4.dat":120804, "OR5x500-0.25_5.dat":122319, "OR10x100-0.25_1.dat":23064, "OR10x100-0.25_2.dat":22801, "OR10x100-0.25_3.dat":22131, "OR10x100-0.25_4.dat":22772,"OR10x100-0.25_5.dat":22751,"OR10x250-0.25_1.dat":59187,"OR10x250-0.25_2.dat":58781,"OR10x250-0.25_3.dat":58097,"OR10x250-0.25_4.dat":61000,"OR10x250-0.25_5.dat":58092,"OR10x500-0.25_1.dat":117821,"OR10x500-0.25_2.dat":119249,"OR10x500-0.25_3.dat":119215,"OR10x500-0.25_4.dat":118829,"OR10x500-0.25_5.dat":116530} # 最佳解
        # 使用 inspect 模块获取模块中的自定义物件名称
        self.module_members = inspect.getmembers(self.algo_file, inspect.isclass)
        self.algorithm_list = np.array(self.module_members).T[0] # 列出所有算法["SMA1","SMA2"...]

        self.algorithm_select = [item for item in self.algorithm_list if item.startswith('BSMASCA_V1_RL_008_25')] # 獲取物件名稱
        
        # 執行參數
        self.problem = ["1","2","3","4","5"]
        self.output_folder = "output"  # 设置输出資料夾路径
         # 問題參數
        self.items = None # 物品數量
        self.dim = None # 物品數量
        self.glbal_best = None # 理論最佳解
        self.values = None # 利潤
        self.weights = None # 資源限制
        self.capacities = None # 容量限制  
        self.run_time = 20 # 執行參數


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
        for iter in range(self.run_time):
            for i, batch_lst in enumerate(self.batch_directory):
                for file_name in self.batch_files[i]:
                    # print(file_name)
                    match = re.search(r"_(\d+)", file_name)
                    if match:
                        pro_num = match.group(1)
                        # print(pro_num)
                        if int(pro_num) <=5:
                            file_path = os.path.join(f"data/{batch_lst}", file_name) # 構建完整的文件路徑
                            print("讀取題目",file_path)
                            if file_name.endswith(".dat"):
                                with open(file_path, 'r') as batch_file:
                                    content = batch_file.read() # readlines() 跟 read() 有差
                                file_list = self.transfrom(content) #
                                self.items = int(file_list[0]) # 物品數量
                                self.dim = int(file_list[1]) # 維度
                                self.glbal_best = self.global_best[file_name]
                                self.values = file_list[3: 3 + self.items] # 利潤
                                self.weights = file_list[3 + self.items: 3 + self.items +self.items * self.dim].reshape((self.dim,self.items)).T# 資源
                                self.capacities = file_list[3 + self.items +self.items * self.dim: 3 + self.items +self.items * self.dim + self.dim] # 容量
                            # 調用每个物件
                            for name in self.algorithm_select:
                                if hasattr(self.algo_file, name):  # 檢查腳本中是否存在該物件
                                    function_to_call = getattr(self.algo_file, name)
                                    Gbest_sol, Gbest_fit = function_to_call(self.items,self.dim,self.glbal_best,self.values,self.weights,self.capacities,iter).run() # 調用函數
                                else:
                                    print(f"{name} 函數不存在於模組中")

                                # <===========================輸出===============================>
                                if not os.path.exists(self.output_folder):
                                    os.makedirs(self.output_folder)


                                output_folder = f"{self.output_folder}/{name}/CB/{batch_lst}"
                                if not os.path.exists(output_folder):
                                    os.makedirs(output_folder)

                                # 將 DataFrame 寫入 CSV 文件
                                result_name = f"{output_folder}/runtime_{iter}_{file_name[:-4]}_algo_{name}.csv" # best 檔案名稱

                                with open(result_name, 'w') as file:
                                    file.write(str(Gbest_fit) + str(Gbest_sol))
                                print(f"result_runtime_{iter}_{file_name[:-4]}_algo_{name},已保存")

if __name__ == "__main__":
    # 這裡放置只有在該文件作為主程序運行時才執行的代碼
    main().exe()
