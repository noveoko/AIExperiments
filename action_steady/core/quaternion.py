
import numpy as np
def quat_multiply(q1, q2):
    w1,x1,y1,z1=q1; w2,x2,y2,z2=q2
    return np.array([
        w1*w2-x1*x2-y1*y2-z1*z2,
        w1*x2+x1*w2+y1*z2-z1*y2,
        w1*y2-x1*z2+y1*w2+z1*x2,
        w1*z2+x1*y2-y1*x2+z1*w2
    ])
def gyro_to_quaternion(gyro, dt):
    q=np.array([1,0,0,0],float); out=[]
    for g in gyro:
        dq=0.5*quat_multiply(q, np.array([0,*g]))
        q=q+dq*dt; q=q/np.linalg.norm(q); out.append(q.copy())
    return np.array(out)
