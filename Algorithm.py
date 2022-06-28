import numpy as np

from tensorboardX import SummaryWriter

import torch
from RL.ddpg import DDPG
from RL.normalized_actions import NormalizedActions
from RL.ounoise import OUNoise
from RL.param_noise import AdaptiveParamNoiseSpec, ddpg_distance_metric
from RL.replay_memory import ReplayMemory, Transition

from Environment import Arm_Env

batch_size = 64
updates_per_step = 5

model_suffix = -1            # -1 表示自动加载/保存，否则指定 suffix 对应的网络 model 文件
load_state = True           # 是否加载状态

GAMMA = .9
MAX_OUNOISE_SIGMA = .6
custom_ounoise_sigma = 0.3   # 如果是 -1，则从 MAX_OUNOISE_SIGMA 开始逐渐减小探索度，否则按照指定的值来设置探索度
param_noise_scale = 0.5

replay_size = 100000

class DDPG_Algorithm:
    def __init__(self, lr_actor=1e-4, lr_critic=1e-3):
        self.env = Arm_Env()

        # log 相关
        self.writer = SummaryWriter()
        self.episode_reward = []

        self.exec_timer = 0
        self.train_timer = 0

        self.gamma = GAMMA
        
        if model_suffix == -1:
            self.suffix = model_suffix
        self.env_name = "arm"
        
        self.agent = DDPG(gamma=self.gamma, tau=0.001, hidden_size=128,
                          num_inputs=self.env.n_actions, action_space=self.env.n_observations, lr_actor=lr_actor, lr_critic=lr_critic)
        self.memory = ReplayMemory(replay_size)
        self.ounoise = OUNoise(self.env.n_actions)
        self.param_noise = AdaptiveParamNoiseSpec(initial_stddev=0.05, desired_action_stddev=param_noise_scale, adaptation_coefficient=1.05)

        if load_state:
            try:
                self.load_state()
            except:
                print("There is no local data.")


    def execute(self):
        self.exec_timer += 1

        s = self.env.get_state()
        if s is None:
            return
        
        # 1. 预测 action
        if custom_ounoise_sigma == -1:
            self.ounoise.sigma = max(0.2, MAX_OUNOISE_SIGMA - (self.train_timer/1e5))
        else:
            self.ounoise.sigma = custom_ounoise_sigma
        action_raw = self.agent.select_action(torch.Tensor([s]), self.ounoise)  # (-1., 1.)

        # 2. 修改 action
        if not type(action_raw) is np.ndarray:
            action_raw = action_raw[0, :].detach().numpy()
        action = np.clip(action_raw, -1., 1.)
        for dim in range(self.env.n_actions):
            action[dim] = (action[dim] + 1.)/2. * self.env.action_space[dim].n
            action[dim] = np.int(action[dim])
        
        # 3. 执行 action
        s_, reward, done, info = self.env.step(action=action)
        
        # 4. 记录经验
        self.push_memory(s, action_raw, done, s_, reward)

        print(f"Timer {self.exec_timer} -- raw: {action_raw} -> act: {action} | reward: {reward}")
        self.writer.add_scalar('ddpg_reward/reward', reward, self.exec_timer)

    def train(self):
        memory = self.memory
        if len(memory) > batch_size*3:
            for _ in range(updates_per_step):
                transitions = memory.sample(batch_size)
                batch = Transition(*zip(*transitions))
                value_loss, policy_loss = self.agent.update_parameters(batch)

                self.writer.add_scalar('ddpg_loss/value', value_loss, self.train_timer)
                self.writer.add_scalar('ddpg_loss/policy', policy_loss, self.train_timer)
                self.train_timer += 1

                if self.train_timer % 100 == 99:
                    self.save_state()

    def push_memory(self, state, action, done, next_state, reward):
        """
        将 s a s_ r 记录到 memory 中
        """
        state = torch.Tensor([state])
        action = torch.Tensor(action)
        mask = torch.Tensor([not done])
        next_state = torch.Tensor([next_state])
        reward = torch.Tensor([reward])

        self.memory.push(state, action, mask, next_state, reward)

#####################  load & save  ####################

    def save_model(self):
        self.agent.save_model(env_name=self.env_name, suffix=self.suffix)

    def load_model(self):
        actor_path=f"RL/models/ddpg_actor_{self.env_name}_{self.suffix}.pkl"
        critic_path=f"RL/models/ddpg_critic_{self.env_name}_{self.suffix}.pkl"
        self.agent.load_model(actor_path=actor_path, critic_path=critic_path)
    
    def save_memory(self):
        self.memory.save_memory(env_name=self.env_name, suffix=self.suffix)
    
    def load_memory(self):
        mem_path = "RL/mem/mem_{}_{}.pkl".format(self.env_name, self.suffix)
        self.memory.load_memory(mem_path=mem_path)
    
    def save_state(self):
        self.save_model()
        self.save_memory()
    
    def load_state(self):
        self.load_memory()
        self.load_model()