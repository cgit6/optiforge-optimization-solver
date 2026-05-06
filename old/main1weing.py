import numpy as np
import pandas as pd
import copy as copy
import os
import inspect # 找匯入檔中物件名稱
import BSMA
import BSCA
import BSCASMA
 

class main:
    def __init__(self):

        self.batch_directory = "data\WEING"
        self.batch_files = os.listdir(self.batch_directory) # 使用 os.listdir 获取目录中的所有文件名
        # print(batch_files)
        self.algo_file = BSCASMA
        # 使用 inspect 模块获取模块中的自定义物件名称
        self.module_members = inspect.getmembers(self.algo_file, inspect.isclass)
        self.algorithm_list = np.array(self.module_members).T[0] # 列出所有算法["SMA1","SMA2"...]
        self.algorithm_select = [item for item in self.algorithm_list if item.startswith('BSMASCA_V1_RL_015_25')] # 獲取物件名稱

        # 執行參數
        self.problem = ["1","2","3","4","5","6","7","8"]
        # self.problem = ["7"]
        self.output_folder = "output"  # 设置输出資料夾路径
        # 算法參數
        self.run_time = 20 # 執行參數
        self.max_iter = 5000 # 終止條件
        self.pop_size = 20 # 種群

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

        for iter in range(self.run_time):
            for prob in self.problem:
                file_path = os.path.normpath(os.path.join(self.batch_directory, f"weing{prob}.dat")) # 構建完整的文件路徑
                # 讀取題庫
                with open(file_path, 'r') as batch_file:
                    content = batch_file.read() # readlines() 跟 read() 有差 
                    # print(content)
                file_list = self.transfrom(content)
                # print(file_list)

                # # 問題參數
                self.items = int(file_list[0]) # 物品數量
                self.dim = int(file_list[1]) # 維度
                self.glbal_best = file_list[2] # 全局最佳
                self.values = file_list[3: 3 + self.items] # 利潤
                self.weights = file_list[3 + self.items: 3 + self.items +self.items * self.dim].reshape((self.dim,self.items)).T # 資源
                self.capacities = file_list[3 + self.items +self.items * self.dim: 3 + self.items +self.items * self.dim + self.dim] # 容量
                # print(self.items)

                # 調用每个物件
                for name in self.algorithm_select:
                    if hasattr(self.algo_file, name):  # 檢查腳本中是否存在該物件
                        function_to_call = getattr(self.algo_file, name)
                        Gbest_sol, Gbest_fit = function_to_call(self.items,self.dim,self.glbal_best,self.values,self.weights,self.capacities).run() # 調用函數
                    else:
                        print(f"{name} 函數不存在於模組中")
                    
                    # <===========================輸出===============================>
                    if not os.path.exists(self.output_folder):
                        os.makedirs(self.output_folder)


                    BSAM_output_folder = f"{self.output_folder}/{name}/WEING"
                    if not os.path.exists(BSAM_output_folder):
                        os.makedirs(BSAM_output_folder)

                    # 將 DataFrame 寫入 CSV 文件
                    result_name = f"{BSAM_output_folder}/runtime_{iter}_prob_{prob}_algo_{name}.csv" # best 檔案名稱
                    
                    with open(result_name, 'w') as file:
                        file.write(str(Gbest_fit) + str(Gbest_sol))

                    print(f"result_runtime_{iter}_prob_{prob}_algo_{name},已保存")

if __name__ == "__main__":
    # 這裡放置只有在該文件作為主程序運行時才執行的代碼
    main().exe()
