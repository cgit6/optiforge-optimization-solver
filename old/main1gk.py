import numpy as np
import pandas as pd
import copy as copy
import os
import inspect # 找匯入檔中物件名稱
# 设置 NumPy 打印选项以显示整个数组
np.set_printoptions(threshold=np.inf)
import BSMA
import BSCASMA
import BSCA

class main:
    def __init__(self):
        # data\GK2
        self.batch_directory = "data/GK2"
        self.batch_files = os.listdir(self.batch_directory) # 使用 os.listdir 获取目录中的所有文件名
        # print(batch_files)
        self.algo_file = BSCASMA
        self.global_best = {"01":3766,"02":3958,"03":5656,"04":5767,"05":7560,"06":7677,"07":19221,"08":18806,"09":58089} # 最佳解
        # 使用 inspect 模块获取模块中的自定义物件名称
        self.module_members = inspect.getmembers(self.algo_file, inspect.isclass)
        self.algorithm_list = np.array(self.module_members).T[0] # 列出所有算法["SMA1","SMA2"...]
        self.algorithm_select = [item for item in self.algorithm_list if item.startswith('BSMASCA_V1_RL_008_15')] # 獲取物件名稱

        # 執行參數
        self.problem = ["02","03","04","05","06","07","09"]
        # self.problem = ["01","08"]
        self.output_folder = "output"  # 设置输出資料夾路径
        # 算法參數
        self.run_time = 20 # 執行參數


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

        for iter in range(12,20):
            for prob in self.problem:
                file_path = os.path.normpath(os.path.join(self.batch_directory, f"mk_gk{prob}.txt")) # 構建完整的文件路徑
                # 讀取題庫
                with open(file_path, 'r') as batch_file:
                    content = batch_file.read() # readlines() 跟 read() 有差 
                
                file_list = self.transfrom(content)

                # 問題參數
                self.items = int(file_list[0]) # 物品數量
                self.dim = int(file_list[1]) # 維度
                self.glbal_best = self.global_best[prob]
                temp = file_list[2: 2 + (self.dim + 1) * self.items].reshape(( self.items, self.dim + 1))

                self.values = temp[:,0] # 利潤
                self.weights = temp[:,1:] # 資源
                self.capacities = file_list[2 + (self.dim + 1) * self.items: 2 + (self.dim + 1) * self.items + self.dim] # 容量

                # print(self.capacities)

                # 調用每个物件
                for name in self.algorithm_select:
                    if hasattr(self.algo_file, name):  # 檢查腳本中是否存在該物件
                        function_to_call = getattr(self.algo_file, name)
                        # np.random.seed(0)
                        Gbest_sol, Gbest_fit = function_to_call(self.items,self.dim,self.glbal_best,self.values,self.weights,self.capacities).run() # 調用函數
                    else:
                        print(f"{name} 函數不存在於模組中")
                    
                    # <===========================輸出===============================>
                    if not os.path.exists(self.output_folder):
                        os.makedirs(self.output_folder)


                    output_folder = f"{self.output_folder}/{name}/GK"
                    if not os.path.exists(output_folder):
                        os.makedirs(output_folder)

                    # 將 DataFrame 寫入 CSV 文件
                    result_name = f"{output_folder}/runtime_{iter}_prob_{prob}_algo_{name}.csv" # best 檔案名稱
                    
                    with open(result_name, 'w') as file:
                        file.write(str(Gbest_fit) + str(Gbest_sol))
                    print(f"result_runtime_{iter}_prob_{prob}_algo_{name},已保存")

if __name__ == "__main__":
    # 這裡放置只有在該文件作為主程序運行時才執行的代碼
    main().exe()
