"""
噪声生成模块

该模块用于在自动驾驶数据收集过程中向控制信号添加噪声。
添加噪声的目的是：
1. 增加训练数据的多样性
2. 模拟真实驾驶中的扰动
3. 帮助模型学习从偏离状态恢复的能力

支持两种噪声类型：
- Spike: 转向噪声，模拟方向盘的突然偏移
- Throttle: 油门/刹车噪声，模拟速度的突然变化
"""

import time
import random
import copy


class Noiser(object):
    """
    噪声生成器类
    
    该类负责生成和管理控制信号的噪声。噪声以随机时间间隔触发，
    并在一段时间内逐渐增加然后逐渐消除，模拟平滑的扰动效果。
    
    Attributes:
        noise_type (str): 噪声类型，'Spike'（转向）、'Throttle'（油门）或 'None'
        frequency (int): 噪声触发频率，每分钟的噪声事件数
        noise_being_set (bool): 当前是否正在施加噪声
        noise_start_time (float): 噪声开始时间戳
        noise_end_time (float): 噪声结束时间戳
        min_noise_time_amount (float): 最小噪声持续时间（秒）
        noise_time_amount (float): 当前噪声持续时间（秒）
        second_counter (float): 秒计数器，用于频率控制
        steer_noise_time (float): 噪声开始时的转向值
        intensity (int): 噪声强度
        remove_noise (bool): 是否正在移除噪声
        current_noise_mean (float): 当前噪声的平均值（正或负）
    """

    def __init__(self, noise_type, frequency=15, intensity=10, min_noise_time_amount=2.0):
        """
        初始化噪声生成器
        
        Args:
            noise_type (str): 噪声类型
                - 'Spike': 转向噪声
                - 'Throttle': 油门/刹车噪声
                - 'None': 不添加噪声
            frequency (int): 噪声触发频率，默认每分钟 15 次
            intensity (int): 噪声强度，默认 10
            min_noise_time_amount (float): 最小噪声持续时间，默认 2.0 秒
        """
        self.noise_type = noise_type
        self.frequency = frequency
        self.noise_being_set = False                    # 当前是否正在施加噪声
        self.noise_start_time = time.time()             # 噪声开始时间
        self.noise_end_time = time.time() + 1           # 噪声结束时间
        self.min_noise_time_amount = min_noise_time_amount
        # 噪声持续时间 = 最小时间 + 随机增量（0.5-2.0秒）
        self.noise_time_amount = min_noise_time_amount + float(random.randint(50, 200) / 100.0)
        self.second_counter = time.time()               # 用于计算每秒触发概率
        self.steer_noise_time = 0                       # 噪声开始时的转向值
        # 噪声强度添加随机扰动（±2）
        self.intensity = intensity + random.randint(-2, 2)
        self.remove_noise = False                       # 是否正在移除噪声
        self.current_noise_mean = 0                     # 当前噪声方向（正或负）

    def set_noise(self):
        """
        设置噪声方向
        
        随机决定噪声的方向（正向或负向）。
        对于转向噪声，正向表示向右偏，负向表示向左偏。
        """
        # 判断：检查噪声类型是否为 Spike 或 Throttle
        # 作用：只有这两种类型需要设置噪声方向，None 类型不需要处理
        # 目的：避免对无噪声模式进行不必要的计算
        if self.noise_type == 'Spike' or self.noise_type == 'Throttle':
            # 随机决定噪声方向
            coin = random.randint(0, 1)
            # 判断：根据随机数决定噪声方向
            # 作用：coin=0 时设置正向噪声，coin=1 时设置负向噪声
            # 目的：使噪声方向随机化，增加数据多样性，模拟真实驾驶中的随机扰动
            if coin == 0:  # 负向噪声
                self.current_noise_mean = 0.001
            else:  # 正向噪声
                self.current_noise_mean = -0.001

    def get_noise(self):
        """
        获取当前噪声值
        
        噪声值随时间线性增加，模拟逐渐偏离的效果。
        噪声值被限制在 [-0.55, 0.55] 范围内。
        
        Returns:
            float: 当前噪声值
        """
        # 判断：检查噪声类型是否为 Spike 或 Throttle
        # 作用：确保只有有效的噪声类型才计算噪声值
        # 目的：避免对 None 类型进行无意义的计算
        if self.noise_type == 'Spike' or self.noise_type == 'Throttle':
            # 判断：检查噪声方向是否为正向
            # 作用：根据噪声方向决定噪声值的增长方向
            # 目的：正向噪声随时间增大，负向噪声随时间减小（绝对值增大）
            if self.current_noise_mean > 0:
                # 正向噪声：随时间增加
                # min(0.55, ...) 用于限制噪声最大值，防止过度偏离
                return min(0.55,
                           self.current_noise_mean + (
                                   time.time() - self.noise_start_time) * 0.03 * self.intensity)
            else:
                # 负向噪声：随时间减少（绝对值增加）
                # max(-0.55, ...) 用于限制噪声最小值，防止过度偏离
                return max(-0.55,
                           self.current_noise_mean - (
                                   time.time() - self.noise_start_time) * 0.03 * self.intensity)

    def get_noise_removing(self):
        """
        获取噪声移除阶段的噪声值
        
        当噪声持续时间结束后，噪声不会立即消失，而是逐渐减小到零。
        这模拟了驾驶员逐渐纠正偏离的过程。
        
        Returns:
            float: 正在衰减的噪声值
        """
        # 计算噪声达到峰值时的累积量
        added_noise = (self.noise_end_time - self.noise_start_time) * 0.02 * self.intensity
        
        # 判断：检查噪声类型是否为 Spike 或 Throttle
        # 作用：确保只有有效的噪声类型才计算衰减噪声值
        # 目的：避免对 None 类型进行无意义的计算
        if self.noise_type == 'Spike' or self.noise_type == 'Throttle':
            # 判断：检查噪声方向是否为正向
            # 作用：根据噪声方向决定衰减的计算方式
            # 目的：正向噪声从峰值向下衰减，负向噪声从谷值向上衰减
            if self.current_noise_mean > 0:
                # 正向噪声的衰减
                # min(0.55, ...) 确保峰值不超过上限
                added_noise = min(0.55, added_noise + self.current_noise_mean)
                # 从峰值开始，随时间线性减小
                return added_noise - (time.time() - self.noise_end_time) * 0.03 * self.intensity
            else:
                # 负向噪声的衰减
                # max(-0.55, ...) 确保谷值不低于下限
                added_noise = max(-0.55, self.current_noise_mean - added_noise)
                # 从谷值开始，随时间线性增大（向零靠近）
                return added_noise + (time.time() - self.noise_end_time) * 0.03 * self.intensity

    def is_time_for_noise(self, steer):
        """
        判断当前是否应该施加噪声
        
        根据频率参数和随机数决定是否开始新的噪声事件，
        同时管理噪声的施加和移除状态。
        
        Args:
            steer (float): 当前的转向/油门值
        
        Returns:
            bool: 如果当前应该施加噪声返回 True
        """
        # 检查是否过了一秒
        second_passed = False
        # 判断：检查距离上次计数是否已过一秒
        # 作用：用于控制噪声触发的时间粒度
        # 目的：将噪声触发频率控制在"每秒检查一次"的粒度，避免过于频繁的检查
        if time.time() - self.second_counter >= 1.0:
            second_passed = True
            self.second_counter = time.time()

        # 判断：检查噪声是否应该从施加阶段转入移除阶段
        # 条件1：噪声持续时间已达到设定值
        # 条件2：当前不在移除阶段（避免重复进入）
        # 条件3：当前正在施加噪声
        # 作用：管理噪声生命周期，从施加阶段过渡到移除阶段
        # 目的：实现噪声的平滑过渡，先增加后逐渐消除，模拟真实的扰动和恢复过程
        if time.time() - self.noise_start_time >= self.noise_time_amount and not self.remove_noise and self.noise_being_set:
            self.noise_being_set = False
            self.remove_noise = True
            self.noise_end_time = time.time()

        # 判断：检查是否正在施加噪声
        # 作用：如果噪声正在施加中，直接返回 True 继续施加
        # 目的：确保噪声在持续时间内不被中断，保持噪声的连续性
        if self.noise_being_set:
            return True

        # 判断：检查是否处于噪声移除阶段
        # 作用：处理噪声的衰减过程
        # 目的：让噪声逐渐消失而不是突然消失，模拟驾驶员逐渐纠正偏离的过程
        if self.remove_noise:
            # 判断：检查移除时间是否已超过噪声持续时间
            # 作用：决定是否完全结束噪声事件
            # 目的：当衰减时间足够长时，完全停止噪声，准备下一次噪声事件
            if (time.time() - self.noise_end_time) > (self.noise_time_amount):
                self.remove_noise = False
                # 重新计算下一次噪声的持续时间
                self.noise_time_amount = self.min_noise_time_amount + float(
                    random.randint(50, 200) / 100.0)
                return False
            else:
                # 移除阶段未结束，继续返回 True 以应用衰减噪声
                return True

        # 判断：检查是否满足开始新噪声的条件
        # 条件1：已过一秒（时间粒度控制）
        # 条件2：当前没有正在施加的噪声
        # 作用：控制新噪声事件的触发时机
        # 目的：按照设定的频率随机触发新的噪声事件
        if second_passed and not self.noise_being_set:
            # 根据频率计算触发概率（频率/60 的概率）
            seed = random.randint(0, 60)
            # 判断：检查随机数是否小于频率阈值
            # 作用：以 frequency/60 的概率触发噪声
            # 目的：实现按频率参数控制的随机噪声触发，例如 frequency=15 表示每秒约 25% 概率触发
            if seed < self.frequency:
                # 判断：再次确认当前没有正在施加的噪声（双重检查）
                # 作用：防止并发情况下重复设置噪声
                # 目的：确保噪声状态的一致性
                if not self.noise_being_set:
                    self.noise_being_set = True
                    self.set_noise()
                    self.steer_noise_time = steer
                    self.noise_start_time = time.time()
                return True
            else:
                # 随机数未命中，本次不触发噪声
                return False
        else:
            # 未满足触发条件（未过一秒或正在施加噪声）
            return False

    def set_noise_exist(self, noise_exist):
        """
        手动设置噪声状态
        
        Args:
            noise_exist (bool): 是否存在噪声
        """
        self.noise_being_set = noise_exist

    def compute_noise(self, action, speed):
        """
        计算并应用噪声到控制信号
        
        根据噪声类型和当前状态，计算噪声值并应用到控制信号上。
        噪声强度会根据车速进行调整，高速时噪声影响较小。
        
        Args:
            action: 控制信号对象，包含 steer、throttle、brake 等属性
            speed (float): 当前车速（km/h）
        
        Returns:
            tuple: (noisy_action, is_recovering, is_noise_being_applied)
                - noisy_action: 添加噪声后的控制信号
                - is_recovering: 是否正在恢复（当前未使用，始终为 False）
                - is_noise_being_applied: 是否正在施加噪声（非移除阶段）
        """
        # 判断：检查噪声类型是否为 None
        # 作用：如果不需要添加噪声，直接返回原始动作
        # 目的：提供无噪声模式，用于对照实验或正常数据收集
        if self.noise_type == 'None':
            return action, False, False

        # 判断：检查噪声类型是否为 Spike（转向噪声）
        # 作用：处理转向控制信号的噪声
        # 目的：模拟方向盘的突然偏移，训练模型从转向偏离中恢复
        if self.noise_type == 'Spike':
            # 判断：检查当前是否应该施加噪声
            # 作用：根据时间和频率决定是否添加噪声
            # 目的：控制噪声的触发时机和持续时间
            if self.is_time_for_noise(action.steer):
                steer = action.steer

                # 判断：检查是否处于噪声移除阶段
                # 作用：区分噪声增加阶段和噪声衰减阶段
                # 目的：实现噪声的平滑过渡，先增加后逐渐消除
                if self.remove_noise:
                    # 噪声移除阶段：逐渐减小噪声
                    # 噪声强度与速度成反比：25 / (2.3 * speed + 5)
                    # 高速时噪声影响较小，低速时影响较大，符合真实驾驶特性
                    # max(min(..., 1), -1) 确保转向值在 [-1, 1] 范围内
                    steer_noisy = max(
                        min(steer + self.get_noise_removing() * (25 / (2.3 * speed + 5)), 1), -1)
                else:
                    # 噪声施加阶段：逐渐增加噪声
                    steer_noisy = max(min(steer + self.get_noise() * (25 / (2.3 * speed + 5)), 1),
                                      -1)

                # 创建动作副本，避免修改原始对象
                noisy_action = copy.deepcopy(action)
                noisy_action.steer = steer_noisy

                # 返回：带噪声的动作、是否恢复中（始终False）、是否正在施加噪声（非移除阶段）
                return noisy_action, False, not self.remove_noise
            else:
                # 当前不需要施加噪声，返回原始动作
                return action, False, False

        # 判断：检查噪声类型是否为 Throttle（油门/刹车噪声）
        # 作用：处理油门和刹车控制信号的噪声
        # 目的：模拟速度的突然变化，训练模型从速度偏离中恢复
        if self.noise_type == 'Throttle':
            # 判断：检查当前是否应该施加噪声
            # 作用：根据时间和频率决定是否添加噪声
            # 目的：控制噪声的触发时机和持续时间
            if self.is_time_for_noise(action.throttle):
                throttle_noisy = action.throttle
                brake_noisy = action.brake

                # 判断：检查是否处于噪声移除阶段
                # 作用：区分噪声增加阶段和噪声衰减阶段
                # 目的：实现噪声的平滑过渡
                if self.remove_noise:
                    # 噪声移除阶段
                    print(" Throttle noise removing", self.get_noise_removing())
                    noise = self.get_noise_removing()
                    # 判断：检查噪声方向是否为正向
                    # 作用：正向噪声影响油门，负向噪声影响刹车
                    # 目的：分别模拟加速和减速的扰动
                    if noise > 0:
                        # 正向噪声：增加油门
                        # max(min(..., 1), 0) 确保油门值在 [0, 1] 范围内
                        throttle_noisy = max(min(throttle_noisy + noise, 1), 0)
                    else:
                        # 负向噪声：增加刹车
                        # -noise 将负值转为正值用于刹车
                        brake_noisy = max(min(brake_noisy + -noise, 1), 0)
                else:
                    # 噪声施加阶段
                    print(" Throttle noise ", self.get_noise())
                    noise = self.get_noise()
                    # 判断：检查噪声方向是否为正向
                    # 作用：正向噪声影响油门，负向噪声影响刹车
                    # 目的：分别模拟加速和减速的扰动
                    if noise > 0:
                        throttle_noisy = max(min(throttle_noisy + noise, 1), 0)
                    else:
                        brake_noisy = max(min(brake_noisy + -noise, 1), 0)

                # 创建动作副本
                noisy_action = copy.deepcopy(action)
                noisy_action.throttle = throttle_noisy
                noisy_action.brake = brake_noisy

                # 返回：带噪声的动作、是否恢复中（始终False）、是否正在施加噪声（非移除阶段）
                return noisy_action, False, not self.remove_noise
            else:
                # 当前不需要施加噪声，返回原始动作
                return action, False, False


# ==================== 测试代码 ====================
if __name__ == '__main__':
    """
    噪声生成器测试脚本
    
    创建一个 Spike 类型的噪声生成器，模拟 500 帧的噪声效果，
    并使用 matplotlib 绘制原始输入和噪声输入的对比图。
    """
    import matplotlib.pyplot as plt

    # 定义简单的控制类用于测试
    class Control:
        steer = 0
        gas = 0
        brake = 0
        hand_brake = 0
        reverse = 0

    # 存储输入数据
    noise_input = []    # 带噪声的转向值
    human_input = []    # 原始转向值（始终为 0）
    
    # 创建噪声生成器
    noiser = Noiser('Spike')
    
    # 模拟 500 帧
    for i in range(500):
        # 创建零输入的控制信号
        human_action = Control()
        human_action.steer = 0.0
        human_action.gas = 0.0
        human_action.brake = 0.0
        human_action.hand_brake = 0.0
        human_action.reverse = 0.0

        human_input.append(human_action.steer)

        # 计算带噪声的动作
        noisy_action, _, _ = noiser.compute_noise(human_action, speed=20)
        time.sleep(0.01)  # 模拟帧间隔
        noise_input.append(noisy_action.steer)

    # 绘制对比图
    # 绿色：原始输入，红色：带噪声的输入
    plt.plot(range(500), human_input, 'g', range(500), noise_input, 'r')
    plt.xlabel('Frame')
    plt.ylabel('Steer Value')
    plt.title('Noise Effect on Steering')
    plt.legend(['Human Input', 'Noisy Input'])
    plt.show()
