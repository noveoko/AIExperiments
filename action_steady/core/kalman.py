
import numpy as np
class Kalman1D:
    def __init__(self):
        self.x=0; self.P=1; self.Q=1e-4; self.R=1e-2
    def update(self,z):
        self.P+=self.Q
        K=self.P/(self.P+self.R)
        self.x=self.x+K*(z-self.x)
        self.P=(1-K)*self.P
        return self.x
def smooth(curve):
    k=Kalman1D()
    return np.array([k.update(v) for v in curve])
