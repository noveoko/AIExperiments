
import numpy as np, cv2
def slerp(q1,q2,t):
    dot=np.dot(q1,q2)
    if dot<0: q2=-q2; dot=-dot
    theta=np.arccos(dot)
    if theta<1e-5: return q1
    return (np.sin((1-t)*theta)*q1+np.sin(t*theta)*q2)/np.sin(theta)
def quat_to_affine(q):
    _,_,_,z=q
    a=2*np.arctan2(z,np.sqrt(1-z*z))
    c,s=np.cos(a),np.sin(a)
    return np.array([[c,-s,0],[s,c,0]],np.float32)
def warp_rs(frame,q1,q2):
    h,w=frame.shape[:2]; out=np.zeros_like(frame)
    for y in range(h):
        t=y/h; q=slerp(q1,q2,t)
        M=quat_to_affine(q)
        row=cv2.warpAffine(frame,M,(w,h))
        out[y:y+1]=row[y:y+1]
    return out
