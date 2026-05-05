
import cv2, numpy as np
def compute(trans):
    m=max(abs(trans[:,0]).max(),abs(trans[:,1]).max())
    return 1-min(0.4,m*0.1)
def apply(f,c):
    h,w=f.shape[:2]
    nh,nw=int(h*c),int(w*c)
    y,x=(h-nh)//2,(w-nw)//2
    return cv2.resize(f[y:y+nh,x:x+nw],(w,h))
