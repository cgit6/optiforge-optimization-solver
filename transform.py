    # # S0
    # def sigmoid(self,x):
    #     return 1/(1+math.exp(-x))

    # # S1
    # def sigmoid(self,x):
    #     return 1/(1+math.exp(-2*x))    

    # # S2
    # def sigmoid(self,x):
    #     return 1/(1+math.exp(-x/2)) 
    
    # # S3
    # def sigmoid(self,x):
    #     return 1/(1+math.exp(-x/3)) 

    # # V0
    # def sigmoid(self,x):
    #     return (2/math.pi) * np.arctan((math.pi/2)*x)
    
    # V1
    def sigmoid(self,x):
        return np.tanh(x)

    # # V2
    # def sigmoid(self,x):
    #     return 1/ np.sqrt(1 + x**2)

    # # V3
    # def sigmoid(self,x):
    #     return erf((math.pi/2)*x)

    # # U1
    # def sigmoid(self,x):
    #     return x**1.6
    
    # # U2
    # def sigmoid(self,x):
    #     return x**1.7
    
    # # U3
    # def sigmoid(self,x):
    #     return x**2.0
    