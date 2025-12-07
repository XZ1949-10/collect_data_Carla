"""
噪声生成模块（基于帧数版本）

该模块用于在自动驾驶数据收集过程中向控制信号添加噪声。
使用帧数而非实时时间计时，与CARLA同步模式完美配合。

添加噪声的目的是：
1. 增加训练数据的多样性
2. 模拟真实驾驶中的扰动
3. 帮助模型学习从偏离状态恢复的能力（DAgger风格）

支持两种噪声类型：
- Spike: 转向噪声，模拟方向盘的突然偏移
- Throttle: 油门/刹车噪声，模拟速度的突然变化
"""

import random


class Noiser(object):
    """
    基于帧数的噪声生成器
    
    与CARLA同步模式配合，使用帧数而非实时时间来控制噪声。
    噪声以随机帧间隔触发，并在一段帧数内平滑增加然后逐渐消除。
    
    Attributes:
        noise_type (str): 噪声类型，'Spike'（转向）、'Throttle'（油门）或 'None'
        frequency (int): 噪声触发频率，每60帧（约1秒@60fps）的期望触发次数
        fps (int): 模拟帧率，用于计算帧数与时间的对应关系
        intensity (float): 噪声强度
        noise_being_set (bool): 当前是否正在施加噪声
        remove_noise (bool): 是否正在移除噪声
    """

    def __init__(self, noise_type, frequency=15, intensity=10, min_noise_time_amount=2.0, fps=20):
        """
        初始化噪声生成器
        
        Args:
            noise_type (str): 噪声类型
                - 'Spike': 转向噪声
                - 'Throttle': 油门/刹车噪声
                - 'None': 不添加噪声
            frequency (int): 噪声触发频率，每分钟期望触发次数，默认15
            intensity (float): 噪声强度，默认10
            min_noise_time_amount (float): 最小噪声持续时间（秒），默认2.0
            fps (int): 模拟帧率，默认20
        """
        self.noise_type = noise_type
        self.frequency = frequency
        self.fps = fps
        
        # 噪声强度（添加±20%随机扰动）
        self.base_intensity = intensity
        self.intensity = intensity * (1.0 + random.uniform(-0.2, 0.2))
        
        # 将时间转换为帧数
        self.min_noise_frames = int(min_noise_time_amount * fps)
        self._reset_noise_duration()
        
        # 帧计数器
        self.frame_counter = 0              # 总帧数计数
        self.noise_start_frame = 0          # 噪声开始帧
        self.noise_end_frame = 0            # 噪声结束帧（进入衰减阶段）
        self.last_check_frame = 0           # 上次检查触发的帧
        
        # 噪声状态
        self.noise_being_set = False        # 是否正在施加噪声
        self.remove_noise = False           # 是否正在移除噪声
        
        # 噪声方向和值
        self.noise_direction = 1            # 1=正向（右偏/加速），-1=负向（左偏/减速）
        self.current_noise_value = 0.0      # 当前噪声值
        
        # 每fps帧检查一次触发（约每秒检查一次）
        self.check_interval = max(fps // 2, 5)  # 每0.5秒检查一次
    
    def _reset_noise_duration(self):
        """重置噪声持续帧数（添加随机性）"""
        # 持续帧数 = 最小帧数 + 随机增量（0.5-2.0秒对应的帧数）
        extra_frames = int(random.uniform(0.5, 2.0) * self.fps)
        self.noise_duration_frames = self.min_noise_frames + extra_frames
    
    def _should_trigger_noise(self):
        """
        判断是否应该触发新的噪声事件
        
        基于频率参数，以概率方式决定是否触发。
        frequency=30 表示每分钟约30次，即每2秒一次，每次检查约 30/(60/check_interval) 的概率
        """
        # 计算每次检查的触发概率
        # frequency 是每分钟的次数，check_interval 是检查间隔帧数
        checks_per_minute = (60 * self.fps) / self.check_interval
        trigger_probability = self.frequency / checks_per_minute
        
        return random.random() < trigger_probability
    
    def _start_noise(self):
        """开始新的噪声事件"""
        self.noise_being_set = True
        self.remove_noise = False
        self.noise_start_frame = self.frame_counter
        
        # 随机选择噪声方向
        self.noise_direction = random.choice([1, -1])
        
        # 重新随机化强度（±20%）
        self.intensity = self.base_intensity * (1.0 + random.uniform(-0.2, 0.2))
        
        # 重置持续时间
        self._reset_noise_duration()
    
    def _get_noise_progress(self):
        """
        获取噪声进度（0.0 到 1.0）
        
        Returns:
            float: 噪声进度，0.0=刚开始，1.0=达到峰值
        """
        if not self.noise_being_set:
            return 0.0
        
        elapsed_frames = self.frame_counter - self.noise_start_frame
        progress = min(1.0, elapsed_frames / max(1, self.noise_duration_frames))
        return progress
    
    def _get_removal_progress(self):
        """
        获取噪声衰减进度（0.0 到 1.0）
        
        Returns:
            float: 衰减进度，0.0=刚开始衰减，1.0=完全消除
        """
        if not self.remove_noise:
            return 0.0
        
        elapsed_frames = self.frame_counter - self.noise_end_frame
        progress = min(1.0, elapsed_frames / max(1, self.noise_duration_frames))
        return progress
    
    def _calculate_noise_value(self, speed):
        """
        计算当前噪声值
        
        使用平滑的缓入缓出曲线，而非线性增长。
        噪声强度与速度成反比（高速时噪声影响较小）。
        
        Args:
            speed (float): 当前车速（km/h）
            
        Returns:
            float: 噪声值
        """
        # 速度衰减因子：高速时噪声影响稍小，但保持足够强度
        # 新公式：speed=20时约为0.71，speed=50时约为0.57
        speed_factor = 1.0 / (0.02 * speed + 1.0)
        
        # 基础噪声幅度（增大系数让噪声更明显）
        # intensity=10, speed=20 时：max_noise = 0.05 * 10 * 0.71 = 0.355
        # intensity=10, speed=50 时：max_noise = 0.05 * 10 * 0.57 = 0.285
        max_noise = 0.05 * self.intensity * speed_factor
        
        if self.noise_being_set:
            # 施加阶段：使用平滑缓入曲线
            progress = self._get_noise_progress()
            # 使用 smoothstep 曲线：3p² - 2p³
            smooth_progress = progress * progress * (3.0 - 2.0 * progress)
            noise = max_noise * smooth_progress
        elif self.remove_noise:
            # 衰减阶段：使用平滑缓出曲线
            progress = self._get_removal_progress()
            # 反向 smoothstep
            smooth_progress = 1.0 - progress * progress * (3.0 - 2.0 * progress)
            noise = max_noise * smooth_progress
        else:
            noise = 0.0
        
        # 应用方向
        return noise * self.noise_direction
    
    def compute_noise(self, action, speed):
        """
        计算并应用噪声到控制信号（每帧调用一次）
        
        Args:
            action: 控制信号对象，包含 steer、throttle、brake 等属性
            speed (float): 当前车速（km/h）
        
        Returns:
            tuple: (noisy_action, is_recovering, is_noise_active)
                - noisy_action: 添加噪声后的控制信号
                - is_recovering: 是否正在恢复（衰减阶段）
                - is_noise_active: 是否正在施加噪声
        """
        # 增加帧计数
        self.frame_counter += 1
        
        # 无噪声模式
        if self.noise_type == 'None':
            return action, False, False
        
        # 状态机更新
        self._update_state()
        
        # 检查是否触发新噪声
        if not self.noise_being_set and not self.remove_noise:
            if self.frame_counter - self.last_check_frame >= self.check_interval:
                self.last_check_frame = self.frame_counter
                if self._should_trigger_noise():
                    self._start_noise()
        
        # 计算噪声值
        noise_value = self._calculate_noise_value(speed)
        is_active = self.noise_being_set or self.remove_noise
        
        # 应用噪声
        if self.noise_type == 'Spike':
            # 转向噪声
            if is_active:
                noisy_steer = action.steer + noise_value
                action.steer = max(-1.0, min(1.0, noisy_steer))
            return action, self.remove_noise, self.noise_being_set
        
        elif self.noise_type == 'Throttle':
            # 油门/刹车噪声
            if is_active:
                if noise_value > 0:
                    # 正向噪声：增加油门
                    # 如果正在刹车，先减少刹车再增加油门
                    if action.brake > 0:
                        brake_reduction = min(action.brake, noise_value)
                        action.brake = max(0.0, action.brake - brake_reduction)
                        remaining_noise = noise_value - brake_reduction
                        if remaining_noise > 0:
                            action.throttle = max(0.0, min(1.0, action.throttle + remaining_noise))
                    else:
                        action.throttle = max(0.0, min(1.0, action.throttle + noise_value))
                else:
                    # 负向噪声：减少油门或增加刹车
                    # 先减少油门，再增加刹车
                    abs_noise = abs(noise_value)
                    if action.throttle > 0:
                        throttle_reduction = min(action.throttle, abs_noise)
                        action.throttle = max(0.0, action.throttle - throttle_reduction)
                        remaining_noise = abs_noise - throttle_reduction
                        if remaining_noise > 0:
                            action.brake = max(0.0, min(1.0, action.brake + remaining_noise))
                    else:
                        action.brake = max(0.0, min(1.0, action.brake + abs_noise))
            return action, self.remove_noise, self.noise_being_set
        
        return action, False, False
    
    def _update_state(self):
        """更新噪声状态机"""
        if self.noise_being_set:
            # 检查是否应该进入衰减阶段
            elapsed = self.frame_counter - self.noise_start_frame
            if elapsed >= self.noise_duration_frames:
                self.noise_being_set = False
                self.remove_noise = True
                self.noise_end_frame = self.frame_counter
        
        elif self.remove_noise:
            # 检查是否应该完全结束
            elapsed = self.frame_counter - self.noise_end_frame
            if elapsed >= self.noise_duration_frames:
                self.remove_noise = False
                self._reset_noise_duration()
    
    def set_noise_exist(self, noise_exist):
        """手动设置噪声状态"""
        self.noise_being_set = noise_exist
    
    def reset(self):
        """重置噪声器状态"""
        self.frame_counter = 0
        self.noise_start_frame = 0
        self.noise_end_frame = 0
        self.last_check_frame = 0
        self.noise_being_set = False
        self.remove_noise = False
        self.current_noise_value = 0.0
        self._reset_noise_duration()


# ==================== 测试代码 ====================
if __name__ == '__main__':
    """
    噪声生成器测试脚本
    
    模拟500帧的噪声效果，并绘制对比图。
    """
    import matplotlib.pyplot as plt

    # 定义简单的控制类用于测试
    class Control:
        def __init__(self):
            self.steer = 0.0
            self.throttle = 0.0
            self.brake = 0.0
            self.hand_brake = False
            self.reverse = False

    # 存储数据
    noise_input = []
    human_input = []
    noise_active = []
    
    # 创建噪声生成器（模拟20fps）
    noiser = Noiser('Spike', frequency=30, intensity=12, min_noise_time_amount=1.0, fps=20)
    
    # 模拟500帧（25秒@20fps）
    for i in range(500):
        human_action = Control()
        human_action.steer = 0.0
        
        human_input.append(human_action.steer)
        
        # 计算带噪声的动作
        noisy_action, is_removing, is_active = noiser.compute_noise(human_action, speed=20)
        noise_input.append(noisy_action.steer)
        noise_active.append(1.0 if is_active else (0.5 if is_removing else 0.0))

    # 绘制对比图
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    
    ax1.plot(range(500), human_input, 'g-', label='Expert Input', alpha=0.7)
    ax1.plot(range(500), noise_input, 'r-', label='Noisy Input', linewidth=1.5)
    ax1.set_ylabel('Steer Value')
    ax1.set_title('Frame-based Noise Effect on Steering (20 FPS)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-0.6, 0.6)
    
    ax2.fill_between(range(500), noise_active, alpha=0.5, color='orange', label='Noise Active')
    ax2.set_xlabel('Frame')
    ax2.set_ylabel('Noise State')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
