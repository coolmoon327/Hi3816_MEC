import numpy as np
from Environment import Arm_Env
import time

class Manual_Control:
    def __init__(self) -> None:
        self.env = Arm_Env()
    
    def execute(self):
        s = self.env.get_state()
        if s is None:
            print("No human face detected. Now reseting the robot arm.")
            time.sleep(0.5)
            return
            
        
        print("state: ",s)

        right, left, bottom, top = s
        x_center = (left + right)/2
        y_center = (top + bottom)/2
        w = np.abs(right - left)
        h = np.abs(bottom - top)

        # 根据 x 调整左右
        act2 = int((1 - x_center/self.env.screen_width) * self.env.action_space[1].n)  # 假设 act2 0-9 是机械臂从最左到最右的位置 (人面对看), 人脸在照片的左边, 说明机械臂应该移动到右边

        # TODO 根据 y_center 与 w*h 调整上下、前后
        pass
        act1 = 9

        action = np.array([act1, act2])
        self.env.step(action=action)
    
    def train(self):
        pass

