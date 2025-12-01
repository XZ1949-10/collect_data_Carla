#!/usr/bin/env python
# coding=utf-8
'''
作者: AI Assistant  
日期: 2025-11-03
说明: 基于命令分段的交互式数据收集
      当导航命令变化时暂停，询问用户是否保存该段数据
      每段数据按200条切片保存
'''

import glob
import os
import sys
import time
import random
import numpy as np
import cv2
import h5py
from collections import deque

# 设置Windows编码（安全版本）
if sys.platform == 'win32':
    try:
        import io
        # 只在需要时重定向，避免重复重定向
        if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        # 如果已经被重定向，跳过
        pass


import carla

# 添加父目录到 Python 路径，以便能导入 agents 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入 agents 模块
try:
    from agents.navigation.basic_agent import BasicAgent
    from agents.navigation.local_planner import RoadOption
    AGENTS_AVAILABLE = True
except ImportError as e:
    AGENTS_AVAILABLE = False
    print(f"⚠️  警告: 无法导入 agents 模块: {e}")
    print("⚠️  将使用自动驾驶模式（可能不按规划路线行驶）")


class CommandBasedDataCollector:
    """
    基于命令分段的数据收集器
    
    特点：
    1. 检测导航命令变化
    2. 命令变化时暂停并询问是否保存
    3. 每段数据按200条切片保存
    4. 支持跳过不需要的命令段
    """
    
    def __init__(self, host='localhost', port=2000, town='Town01',
                 ignore_traffic_lights=True, ignore_signs=True, 
                 ignore_vehicles_percentage=80):
        """初始化
        
        参数:
            ignore_traffic_lights: 是否忽略红绿灯
            ignore_signs: 是否忽略停车标志
            ignore_vehicles_percentage: 忽略其他车辆的百分比（0-100）
        """
        self.host = host
        self.port = port
        self.town = town
        
        # 交通规则配置
        self.ignore_traffic_lights = ignore_traffic_lights
        self.ignore_signs = ignore_signs
        self.ignore_vehicles_percentage = ignore_vehicles_percentage
        
        # Carla对象
        self.client = None
        self.world = None
        self.blueprint_library = None
        self.vehicle = None
        self.camera = None
        self.traffic_manager = None
        self.agent = None  # BasicAgent 用于按规划路线控制车辆
        
        # 数据缓冲
        self.image_buffer = deque(maxlen=1)
        self.current_segment_data = {
            'rgb': [],
            'targets': []
        }
        
        # 摄像头配置
        self.image_width = 200
        self.image_height = 88
        
        # 命令追踪
        self.current_command = None
        self.previous_command = None
        self.segment_count = 0  # 当前段的帧数
        
        # 保存统计
        self.total_saved_segments = 0
        self.total_saved_frames = 0
        self.command_names = {2: 'Follow', 3: 'Left', 4: 'Right', 5: 'Straight'}
        
        # RoadOption 到数值命令的映射
        self.road_option_to_command = {
            RoadOption.LANEFOLLOW: 2.0,      # Follow
            RoadOption.LEFT: 3.0,            # Left
            RoadOption.RIGHT: 4.0,           # Right
            RoadOption.STRAIGHT: 5.0,        # Straight
            RoadOption.CHANGELANELEFT: 2.0,  # 变道也算Follow
            RoadOption.CHANGELANERIGHT: 2.0,
            RoadOption.VOID: 0.0             # 到达目标
        }
        
        # 可视化
        self.enable_visualization = False
        
    def connect(self):
        """连接到Carla服务器"""
        print(f"正在连接到Carla服务器 {self.host}:{self.port}...")
        
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(10.0)
        
        print(f"正在加载地图 {self.town}...")
        self.world = self.client.load_world(self.town)
        
        self.blueprint_library = self.world.get_blueprint_library()
        
        # 设置同步模式
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05  # 20FPS
        self.world.apply_settings(settings)
        
        print("成功连接到Carla服务器！")
        
    def spawn_vehicle(self, spawn_index, destination_index):
        """生成车辆并规划路线"""
        print(f"正在生成车辆...")
        
        vehicle_bp = self.blueprint_library.filter('vehicle.tesla.model3')[0]
        spawn_points = self.world.get_map().get_spawn_points()
        
        if spawn_index >= len(spawn_points) or destination_index >= len(spawn_points):
            print(f"❌ 索引超出范围！最大索引: {len(spawn_points)-1}")
            return False
        
        spawn_point = spawn_points[spawn_index]
        destination = spawn_points[destination_index].location
        
        self.vehicle = self.world.try_spawn_actor(vehicle_bp, spawn_point)
        
        if self.vehicle is None:
            print("生成车辆失败！")
            return False
            
        print(f"车辆生成成功！")
        
        # 等待车辆稳定
        for _ in range(5):
            self.world.tick()
            time.sleep(0.05)
        
        # 使用 BasicAgent 来控制车辆按规划路线行驶
        if AGENTS_AVAILABLE:
            print(f"正在配置 BasicAgent（按规划路线行驶）...")
            
            # 创建 BasicAgent 配置
            opt_dict = {
                'target_speed': 30.0,
                'ignore_traffic_lights': self.ignore_traffic_lights,
                'ignore_stop_signs': self.ignore_signs,
                'ignore_vehicles': (self.ignore_vehicles_percentage > 50),
                'sampling_resolution': 2.0
            }
            
            # 创建 BasicAgent
            self.agent = BasicAgent(
                self.vehicle, 
                target_speed=30,
                opt_dict=opt_dict,
                map_inst=self.world.get_map()
            )
            
            print(f"  ✅ BasicAgent 已创建")
            if self.ignore_traffic_lights:
                print(f"  ✅ BasicAgent 忽略红绿灯")
            if self.ignore_signs:
                print(f"  ✅ BasicAgent 忽略停车标志")
            if self.ignore_vehicles_percentage > 0:
                print(f"  ✅ BasicAgent 忽略其他车辆: {self.ignore_vehicles_percentage}%")
            
            # 设置目的地（BasicAgent 会自动规划并跟随路线）
            start_location = spawn_point.location
            self.agent.set_destination(destination, start_location=start_location)
            print(f"  ✅ BasicAgent 已设置目的地")
            
        else:
            # 降级方案：使用 Traffic Manager + 自动驾驶
            print(f"正在配置 Traffic Manager（自动驾驶模式）...")
            print(f"  ⚠️  注意：车辆可能不会严格按照规划路线行驶")
            
            # 获取 Traffic Manager
            self.traffic_manager = self.client.get_trafficmanager()
            
            # 启用自动驾驶
            self.vehicle.set_autopilot(True, self.traffic_manager.get_port())
            
            # 配置 Traffic Manager
            if self.ignore_traffic_lights:
                self.traffic_manager.ignore_lights_percentage(self.vehicle, 100)
                print(f"  ✅ 忽略红绿灯: 100%")
            
            if self.ignore_signs:
                self.traffic_manager.ignore_signs_percentage(self.vehicle, 100)
                print(f"  ✅ 忽略停车标志: 100%")
            
            if self.ignore_vehicles_percentage > 0:
                self.traffic_manager.ignore_vehicles_percentage(self.vehicle, self.ignore_vehicles_percentage)
                print(f"  ✅ 忽略其他车辆: {self.ignore_vehicles_percentage}%")
            
            # 设置车辆保持在车道内
            self.traffic_manager.auto_lane_change(self.vehicle, False)
        
        return True
        
    def setup_camera(self):
        """设置摄像头"""
        print("正在设置摄像头...")
        
        camera_bp = self.blueprint_library.find('sensor.camera.rgb')
        camera_bp.set_attribute('image_size_x', str(self.image_width))
        camera_bp.set_attribute('image_size_y', str(self.image_height))
        camera_bp.set_attribute('fov', '90')
        
        camera_transform = carla.Transform(
            carla.Location(x=2.0, z=1.4),
            carla.Rotation(pitch=-15)
        )
        
        self.camera = self.world.spawn_actor(
            camera_bp, 
            camera_transform, 
            attach_to=self.vehicle,
            attachment_type=carla.AttachmentType.Rigid
        )
        
        self.camera.listen(lambda image: self._on_camera_update(image))
        
        print("摄像头设置完成！")
        
    def _on_camera_update(self, image):
        """摄像头回调"""
        array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
        array = np.reshape(array, (image.height, image.width, 4))
        array = array[:, :, :3]
        array = array[:, :, ::-1]
        self.image_buffer.append(array)
    
    def _ask_user_save_segment(self, command, segment_size, show_visualization=False, 
                                current_image=None, speed=0.0, current_frame=0, total_frames=0):
        """
        询问用户是否保存当前数据段
        
        在询问期间，车辆和CARLA画面会暂停（停止调用world.tick()）
        如果启用了可视化，会在询问前显示当前画面
        
        参数:
            command: 当前命令
            segment_size: 当前段的帧数
            show_visualization: 是否显示可视化
            current_image: 当前图像（用于可视化）
            speed: 当前速度（用于可视化）
            current_frame: 当前帧数（用于可视化）
            total_frames: 总帧数（用于可视化）
            
        返回:
            bool: True=保存, False=丢弃, None=停止收集
        """
        # 如果启用了可视化，先显示当前画面（车辆暂停状态）
        # 暂停状态下不显示 is_collecting，因为用户正在做决定
        if show_visualization and current_image is not None:
            self._visualize_frame(current_image, speed, command, current_frame, total_frames, 
                                paused=True, is_collecting=True)
        
        print("\n" + "="*70)
        print(f"⏸️  车辆已暂停 - 检测到命令: {self.command_names.get(command, 'Unknown')} (命令{command})")
        print("="*70)
        print(f"\n💡 提示：车辆已停止，等待你的指令")
        print(f"   - CARLA画面已冻结")
        print(f"   - 可视化窗口显示当前画面（暂停状态）")
        print(f"   - 输入选择后执行对应操作\n")
        print(f"请选择操作:")
        print(f"  ✅ '保存' 或 's' → 收集200帧 → 自动保存")
        print(f"  ❌ '跳过' 或 'n' → 跳过此命令段，等待命令变化")
        print(f"  ⏹️  '停止' 或 'q' → 停止收集并退出")
        
        while True:
            try:
                choice = input(f"\n👉 你的选择: ").strip().lower()
                
                if choice in ['保存', 'save', 's', 'y', 'yes']:
                    print(f"✅ 将保存这段数据")
                    print(f"▶️  车辆继续行驶...\n")
                    return True
                elif choice in ['跳过', 'skip', 'n', 'no']:
                    print(f"❌ 将丢弃这段数据")
                    print(f"▶️  车辆继续行驶...\n")
                    return False
                elif choice in ['停止', 'stop', 'q', 'quit']:
                    print(f"⏹️  停止收集")
                    return None
                else:
                    print(f"❌ 无效选择！请输入 '保存' (s)、'跳过' (n) 或 '停止' (q)")
                    # 在无效输入后，重新显示可视化（保持窗口打开）
                    if show_visualization and current_image is not None:
                        self._visualize_frame(current_image, speed, command, current_frame, total_frames, 
                                            paused=True, is_collecting=True)
                    
            except KeyboardInterrupt:
                print("\n⏹️  收到中断信号")
                return None
    
    def _save_segment(self, save_path, command):
        """
        保存当前数据段（按200条切片）
        
        参数:
            save_path: 保存目录
            command: 命令类型
        """
        if len(self.current_segment_data['rgb']) == 0:
            print("当前段无数据，跳过保存")
            return
        
        print(f"\n正在保存数据段...")
        
        # 转换为numpy数组
        rgb_array = np.array(self.current_segment_data['rgb'], dtype=np.uint8)
        targets_array = np.array(self.current_segment_data['targets'], dtype=np.float32)
        
        total_samples = rgb_array.shape[0]
        print(f"  总样本数: {total_samples}")
        
        # 按200条切片保存
        num_chunks = (total_samples + 199) // 200
        print(f"  将分割成: {num_chunks} 个文件（每个最多200条）")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        command_name = self.command_names.get(command, 'Unknown')
        
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * 200
            end_idx = min((chunk_idx + 1) * 200, total_samples)
            
            chunk_rgb = rgb_array[start_idx:end_idx]
            chunk_targets = targets_array[start_idx:end_idx]
            
            # 生成文件名
            filename = os.path.join(
                save_path,
                f"carla_cmd{command}_{command_name}_{timestamp}_part{chunk_idx+1:03d}.h5"
            )
            
            # 保存
            with h5py.File(filename, 'w') as hf:
                hf.create_dataset('rgb', data=chunk_rgb, compression='gzip', compression_opts=4)
                hf.create_dataset('targets', data=chunk_targets, compression='gzip', compression_opts=4)
            
            file_size_mb = os.path.getsize(filename) / 1024 / 1024
            print(f"    ✓ {os.path.basename(filename)} ({end_idx-start_idx} 样本, {file_size_mb:.2f} MB)")
            
            self.total_saved_segments += 1
            self.total_saved_frames += (end_idx - start_idx)
        
        print(f"✅ 数据段保存完成！")
        
    def collect_data_interactive(self, max_frames=50000, save_path='./carla_data', visualize=True):
        """
        交互式数据收集（简化流程）
        
        工作流程：
        1. 询问是否收集当前命令段
        2. 如果选择"保存"→ 收集200帧 → 自动保存
        3. 自动保存后 → 继续询问下一段
        4. 循环执行直到用户停止或到达终点
        
        参数:
            max_frames: 最大帧数（防止无限收集）
            save_path: 保存路径
            visualize: 是否可视化
        """
        self.enable_visualization = visualize
        
        print("\n" + "="*70)
        print("📊 基于命令的交互式数据收集（简化流程）")
        print("="*70)
        print(f"最大帧数: {max_frames}")
        print(f"保存路径: {save_path}")
        print(f"可视化: {'开启' if visualize else '关闭'}")
        print(f"流程: 询问 → 收集200帧 → 自动保存 → 循环")
        print("="*70)
        
        os.makedirs(save_path, exist_ok=True)
        
        # 等待第一帧
        print("\n等待第一帧图像...")
        while len(self.image_buffer) == 0:
            if AGENTS_AVAILABLE and self.agent is not None:
                control = self.agent.run_step()
                self.vehicle.apply_control(control)
            self.world.tick()
            time.sleep(0.01)
        
        print("摄像头就绪！\n")
        
        collected_frames = 0
        self.current_segment_data = {'rgb': [], 'targets': []}
        self.segment_count = 0
        
        # 获取初始命令（从 BasicAgent 的 local_planner）
        self.current_command = self._get_navigation_command()
        self.previous_command = self.current_command
        
        # 先推进几帧，获取初始图像和速度（用于可视化）
        print(f"\n{'='*70}")
        print(f"🎬 准备开始收集")
        print(f"{'='*70}")
        print(f"初始命令: {self.command_names.get(self.current_command, 'Unknown')} (命令{self.current_command})")
        print("正在获取初始画面...")
        
        initial_image = None
        initial_speed = 0.0
        
        for _ in range(10):  # 推进几帧获取稳定的图像
            if AGENTS_AVAILABLE and self.agent is not None:
                control = self.agent.run_step()
                self.vehicle.apply_control(control)
            self.world.tick()
            if len(self.image_buffer) > 0:
                initial_image = self.image_buffer[-1]
                vehicle_velocity = self.vehicle.get_velocity()
                initial_speed = 3.6 * np.sqrt(
                    vehicle_velocity.x**2 + 
                    vehicle_velocity.y**2 + 
                    vehicle_velocity.z**2
                )
            time.sleep(0.05)
        
        print("\n开始数据收集循环...")
        
        try:
            # 主循环：询问 → 收集 → 保存 → 询问
            while collected_frames < max_frames:
                # 获取当前命令
                self.current_command = self._get_navigation_command()
                
                # 获取当前图像和速度用于可视化
                current_image_for_ask = self.image_buffer[-1] if len(self.image_buffer) > 0 else initial_image
                vehicle_velocity = self.vehicle.get_velocity()
                current_speed = 3.6 * np.sqrt(
                    vehicle_velocity.x**2 + 
                    vehicle_velocity.y**2 + 
                    vehicle_velocity.z**2
                )
                
                # ⏸️ 步骤1：询问是否收集这一段
                user_choice = self._ask_user_save_segment(
                    command=self.current_command,
                    segment_size=0,
                    show_visualization=self.enable_visualization,
                    current_image=current_image_for_ask,
                    speed=current_speed,
                    current_frame=collected_frames,
                    total_frames=max_frames
                )
                
                if user_choice is None:  # 用户选择停止
                    print("✅ 用户选择停止收集")
                    break
                
                if not user_choice:  # 用户选择跳过
                    print(f"❌ 跳过 {self.command_names[self.current_command]} 命令段")
                    print("⏭️  继续下一段...\n")
                    
                    # 跳过模式：等待命令变化
                    print("🔄 等待命令变化...")
                    skip_frames = 0
                    while skip_frames < 500:  # 最多跳过500帧
                        if AGENTS_AVAILABLE and self.agent is not None:
                            control = self.agent.run_step()
                            self.vehicle.apply_control(control)
                        self.world.tick()
                        
                        # 检查终点
                        if self._is_route_completed():
                            print(f"\n🎯 已到达目的地！")
                            return
                        
                        # 检查命令变化
                        new_command = self._get_navigation_command()
                        if new_command != self.current_command:
                            print(f"✅ 命令已变化: {self.command_names.get(self.current_command, 'Unknown')} → "
                                  f"{self.command_names.get(new_command, 'Unknown')}\n")
                            break
                        
                        skip_frames += 1
                        collected_frames += 1
                        
                        # 可视化（跳过模式）
                        if self.enable_visualization and len(self.image_buffer) > 0:
                            current_image = self.image_buffer[-1]
                            vehicle_velocity = self.vehicle.get_velocity()
                            speed_kmh = 3.6 * np.sqrt(
                                vehicle_velocity.x**2 + 
                                vehicle_velocity.y**2 + 
                                vehicle_velocity.z**2
                            )
                            self._visualize_frame(current_image, speed_kmh, new_command, 
                                                collected_frames, max_frames, is_collecting=False)
                        
                        if skip_frames % 50 == 0:
                            print(f"  [跳过中] 帧数: {skip_frames}, 当前命令: {self.command_names.get(new_command, 'Unknown')}")
                    
                    continue  # 返回询问下一段
                
                # ▶️ 步骤2：用户选择保存，开始收集200帧
                save_command = self.current_command  # 记录用户选择保存时的命令（用于文件名）
                print(f"✅ 开始收集 {self.command_names[save_command]} 命令段（目标：200帧）...")
                
                self.current_segment_data = {'rgb': [], 'targets': []}
                self.segment_count = 0
                
                # 收集200帧
                while self.segment_count < 200 and collected_frames < max_frames:
                    # 推进模拟
                    if AGENTS_AVAILABLE and self.agent is not None:
                        control = self.agent.run_step()
                        self.vehicle.apply_control(control)
                    self.world.tick()
                    
                    # 检查终点（使用 BasicAgent 的 done() 方法）
                    if self._is_route_completed():
                        print(f"\n🎯 已到达目的地！")
                        break
                    
                    if len(self.image_buffer) == 0:
                        continue
                    
                    # 获取数据
                    current_image = self.image_buffer[-1]
                    vehicle_velocity = self.vehicle.get_velocity()
                    vehicle_control = self.vehicle.get_control()
                    
                    speed_kmh = 3.6 * np.sqrt(
                        vehicle_velocity.x**2 + 
                        vehicle_velocity.y**2 + 
                        vehicle_velocity.z**2
                    )
                    
                    # 获取当前命令（可能会变化，但仍然收集）
                    current_cmd = self._get_navigation_command()
                    
                    # 构建targets（使用当前实际命令）
                    targets = np.zeros(25, dtype=np.float32)
                    targets[0] = vehicle_control.steer
                    targets[1] = vehicle_control.throttle
                    targets[2] = vehicle_control.brake
                    targets[10] = speed_kmh
                    targets[24] = current_cmd
                    
                    # 数据质量检查
                    if current_image.mean() < 5 or speed_kmh > 150:
                        continue
                    
                    # 添加到当前段
                    self.current_segment_data['rgb'].append(current_image)
                    self.current_segment_data['targets'].append(targets)
                    self.segment_count += 1
                    collected_frames += 1
                    
                    # 可视化
                    if self.enable_visualization:
                        self._visualize_frame(current_image, speed_kmh, current_cmd, 
                                            collected_frames, max_frames, is_collecting=True)
                    
                    # 进度显示
                    if self.segment_count % 50 == 0:
                        print(f"  [收集中] 进度: {self.segment_count}/200 帧, "
                              f"当前命令: {self.command_names.get(current_cmd, 'Unknown')}, "
                              f"速度: {speed_kmh:.1f} km/h")
                
                # ✅ 步骤3：自动保存（使用用户选择保存时的命令名）
                if self.segment_count > 0:
                    print(f"\n💾 自动保存数据段（{self.segment_count} 帧）...")
                    self._save_segment(save_path, save_command)  # 使用保存时的命令
                    print(f"✅ 已保存！继续下一段...\n")
                
                # 检查是否到达终点
                if self._is_route_completed():
                    break
            
            print(f"\n{'='*70}")
            print(f"✅ 数据收集完成！")
            print(f"{'='*70}")
            print(f"总收集帧数: {collected_frames}")
            print(f"总保存帧数: {self.total_saved_frames}")
            print(f"保存段数: {self.total_saved_segments}")
            print(f"跳过帧数: {collected_frames - self.total_saved_frames}")
            print(f"{'='*70}\n")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断收集...")
            
            # 询问是否保存当前段
            if self.segment_count > 0:
                save_final = input(f"\n当前段有 {self.segment_count} 帧，是否保存？(y/n): ").strip().lower()
                if save_final in ['y', 'yes', '保存']:
                    self._save_segment(save_path, self.current_command)
        
        finally:
            if self.enable_visualization:
                cv2.destroyAllWindows()
    
    def _visualize_frame(self, image, speed, command, current_frame, total_frames, 
                         paused=False, is_collecting=True):
        """简化的可视化
        
        参数:
            paused: 是否处于暂停状态
            is_collecting: 是否正在收集数据（保存模式）
        """
        command_names = {2: 'Follow', 3: 'Left', 4: 'Right', 5: 'Straight'}
        command_colors = {2: (100, 255, 100), 3: (100, 100, 255), 
                         4: (255, 100, 100), 5: (255, 255, 100)}
        
        # 放大图像
        display_image = cv2.resize(image, (800, 600))
        display_image = cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
        
        # 如果暂停，添加半透明覆盖层
        if paused:
            overlay = display_image.copy()
            cv2.rectangle(overlay, (0, 0), (800, 600), (0, 0, 0), -1)
            display_image = cv2.addWeighted(display_image, 0.6, overlay, 0.4, 0)
        
        # 创建信息面板
        panel_width = 300
        panel_height = 600
        info_panel = np.zeros((panel_height, panel_width, 3), dtype=np.uint8)
        info_panel[:] = (40, 40, 40)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        y_pos = 40
        
        # 标题
        cv2.putText(info_panel, "Command-Based Collection", (10, y_pos), 
                   font, 0.5, (255, 255, 255), 1)
        y_pos += 40
        
        # 暂停状态提示
        if paused:
            cv2.putText(info_panel, "*** PAUSED ***", (10, y_pos), 
                       font, 0.7, (0, 165, 255), 2)  # 橙色
            y_pos += 40
        
        # 收集状态显示
        if not paused:  # 只在非暂停状态显示
            if is_collecting:
                status_text = "SAVING"
                status_color = (100, 255, 100)  # 绿色
            else:
                status_text = "SKIPPING"
                status_color = (100, 100, 255)  # 蓝色
            cv2.putText(info_panel, f"*** {status_text} ***", (10, y_pos), 
                       font, 0.6, status_color, 2)
            y_pos += 40
        
        # 进度
        progress = current_frame / total_frames if total_frames > 0 else 0
        cv2.putText(info_panel, f"Progress: {current_frame}/{total_frames}", (10, y_pos), 
                   font, 0.5, (200, 200, 200), 1)
        y_pos += 35
        
        # 当前段帧数
        cv2.putText(info_panel, f"Segment: {self.segment_count} frames", (10, y_pos), 
                   font, 0.5, (200, 200, 200), 1)
        y_pos += 50
        
        # 命令
        cmd_name = command_names.get(command, 'Unknown')
        cmd_color = command_colors.get(command, (255, 255, 255))
        cv2.putText(info_panel, f"Command: {cmd_name}", (10, y_pos), 
                   font, 0.7, cmd_color, 2)
        y_pos += 50
        
        # 速度
        speed_color = (100, 255, 100) if speed < 60 else (255, 200, 100)
        cv2.putText(info_panel, f"Speed: {speed:.1f} km/h", (10, y_pos), 
                   font, 0.6, speed_color, 2)
        y_pos += 60
        
        # 统计
        cv2.putText(info_panel, "=== Statistics ===", (10, y_pos), 
                   font, 0.5, (200, 200, 200), 1)
        y_pos += 30
        
        cv2.putText(info_panel, f"Saved: {self.total_saved_frames}", (10, y_pos), 
                   font, 0.5, (100, 255, 100), 1)
        y_pos += 25
        
        cv2.putText(info_panel, f"Segments: {self.total_saved_segments}", (10, y_pos), 
                   font, 0.5, (200, 200, 200), 1)
        
        # 合并
        combined = np.hstack([display_image, info_panel])
        
        # 如果暂停，在图像上叠加大号暂停文字
        if paused:
            cv2.putText(combined, "PAUSED", (300, 300), 
                       cv2.FONT_HERSHEY_DUPLEX, 2, (0, 165, 255), 4)
            cv2.putText(combined, "Waiting for your command...", (150, 360), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        else:
            # 在右上角显示当前状态
            if is_collecting:
                status_text = "SAVING DATA"
                status_color = (100, 255, 100)  # 绿色
            else:
                status_text = "SKIPPING"
                status_color = (100, 100, 255)  # 蓝色
            
            # 添加半透明背景
            text_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.rectangle(combined, (800 - text_size[0] - 20, 10), 
                         (800, 50), (0, 0, 0), -1)
            cv2.rectangle(combined, (800 - text_size[0] - 20, 10), 
                         (800, 50), status_color, 2)
            cv2.putText(combined, status_text, (800 - text_size[0] - 10, 35), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        
        cv2.imshow("Command-Based Data Collection", combined)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            self.enable_visualization = False
            cv2.destroyAllWindows()
    
    def _get_navigation_command(self):
        """
        从 BasicAgent 的 local_planner 获取当前导航命令
        
        返回:
            float: 命令数值 (2.0=Follow, 3.0=Left, 4.0=Right, 5.0=Straight, 0.0=VOID)
        """
        if not AGENTS_AVAILABLE or self.agent is None:
            # 降级方案：返回默认命令
            return 2.0  # Follow
        
        try:
            # 从 BasicAgent 的 local_planner 获取 RoadOption
            local_planner = self.agent.get_local_planner()
            if local_planner is None:
                return 2.0
            
            # 获取当前目标路点的 RoadOption
            road_option = local_planner.target_road_option
            if road_option is None:
                road_option = RoadOption.LANEFOLLOW
            
            # 映射到数值命令
            command = self.road_option_to_command.get(road_option, 2.0)
            return command
            
        except Exception as e:
            print(f"⚠️  获取导航命令失败: {e}")
            return 2.0  # 默认返回 Follow
    
    def _is_route_completed(self):
        """
        检查是否到达目的地
        
        返回:
            bool: True=已到达, False=未到达
        """
        if not AGENTS_AVAILABLE or self.agent is None:
            return False
        
        try:
            return self.agent.done()
        except Exception as e:
            print(f"⚠️  检查路线完成状态失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        print("正在清理资源...")
        
        # 停止 BasicAgent
        if self.agent is not None:
            self.agent = None
        
        if self.camera is not None:
            self.camera.stop()
            self.camera.destroy()
            
        if self.vehicle is not None:
            self.vehicle.destroy()
            
        if self.world is not None:
            settings = self.world.get_settings()
            settings.synchronous_mode = False
            self.world.apply_settings(settings)
            
        print("清理完成！")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='基于命令的交互式数据收集')
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--town', type=str, default='Town01')
    parser.add_argument('--spawn-index', type=int, required=True)
    parser.add_argument('--dest-index', type=int, required=True)
    parser.add_argument('--max-frames', type=int, default=50000)
    parser.add_argument('--save-path', type=str, default='./carla_data')
    parser.add_argument('--visualize', action='store_true')
    
    args = parser.parse_args()
    
    collector = CommandBasedDataCollector(args.host, args.port, args.town)
    
    try:
        # 初始化
        collector.connect()
        
        if not collector.spawn_vehicle(args.spawn_index, args.dest_index):
            print("无法生成车辆！")
            return
        
        collector.setup_camera()
        
        # 等待传感器准备
        time.sleep(1.0)
        
        # 开始交互式收集
        collector.collect_data_interactive(
            max_frames=args.max_frames,
            save_path=args.save_path,
            visualize=args.visualize
        )
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        collector.cleanup()
        print("程序结束")


if __name__ == '__main__':
    """
    使用说明：
    
    基本用法：
        python command_based_data_collection.py --spawn-index 0 --dest-index 50 --visualize
    
    工作流程：
        1. 车辆开始行驶，获取初始命令（如Follow）
        2. 询问：是否保存Follow命令段？
           - 保存 → 开始收集Follow数据
           - 跳过 → 不收集，等待命令变化
           - 停止 → 退出程序
        
        3. 车辆行驶，实时收集数据
           - 每200帧自动保存一次
           - 显示可视化窗口
        
        4. 检测到命令变化（如Follow → Left）
           - 暂停收集
           - 保存/丢弃之前的Follow数据段
           - 询问：是否保存Left命令段？
           - 继续收集或跳过
        
        5. 重复步骤3-4，直到到达终点或用户停止
    
    优势：
        ✅ 精确控制收集哪些命令的数据
        ✅ 避免收集不需要的场景
        ✅ 每段按200条切片保存（匹配训练loader）
        ✅ 文件命名包含命令类型，易于管理
        ✅ 可以专门收集某个命令的数据
    
    示例：
        # 收集多个命令的数据
        python command_based_data_collection.py --spawn-index 0 --dest-index 50 --visualize
        # 提示保存Follow时选"保存"，其他命令选"跳过"
        
        # 收集转弯数据
        python command_based_data_collection.py --spawn-index 10 --dest-index 80 --visualize
        # 只在Left和Right命令时选择"保存"
    
    文件命名格式：
        carla_cmd2_Follow_20251103_143025_part001.h5     (Follow命令，第1段)
        carla_cmd2_Follow_20251103_143025_part002.h5     (Follow命令，第2段)
        carla_cmd3_Left_20251103_143156_part001.h5       (Left命令，第1段)
        carla_cmd4_Right_20251103_143245_part001.h5      (Right命令，第1段)
    """
    main()
