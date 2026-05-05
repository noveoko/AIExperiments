
import numpy as np
def estimate_time_offset(v,g):
    v=v-np.mean(v); g=g-np.mean(g)
    c=np.correlate(v,g,mode='full')
    return np.argmax(c)-len(v)+1
