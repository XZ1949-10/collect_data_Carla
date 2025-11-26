#!/usr/bin/env python
# coding=utf-8
'''
作者: AI Assistant
日期: 2025-11-25
说明: Carla自动驾驶模型实时推理脚本（模块化版本）
      从Carla实时获取图像和速度，使用训练好的模型预测控制信号，并控制车辆
'''

import os
import sys
import time
import argparse

# 设置标准输出编码为UTF-8，避免Windows下的编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import torch
import carla

# 导入项目模块
from carla_config import *
from carla_sensors import SensorManager
from carla_visualizer import CarlaVisualizer
from navigation_planner_adapter import NavigationPlannerAdapter
from carla_model_loader import ModelLoader
from carla_image_processor import ImageProcessor
from carla_vehicle_controller import VehicleController
from carla_model_predictor import ModelPredictor
from carla_vehicle_spawner import VehicleSpawner
from carla_logger import CarlaLogger


class CarlaInference:
    """
    Carla自动驾驶推理类（模块化版本）
    
    核心功能：
    1. 连接到Carla服务器
    2. 加载训练好的模型
    3. 实时获取传感器数据
    4. 使用模型预测控制信号
    5. 控制车辆行驶
    """
    
    def __init__(self, 
                 model_path,
                 host='localhost',
                 port=2000,
                 town='Town01',
                 gpu_id=0,
                 enable_post_processing=False,
                 post_processor_config=None,
                 enable_image_crop=True):
        """
        初始化推理器
        
        参数:
            model_path (str): 训练好的模型权重路径
            host (str): Carla服务器地址
            port (int): Carla服务器端口
            town (str): 地图名称
            gpu_id (int): GPU ID，-1表示使用CPU
            enable_post_processing (bool): 是否启用后处理
            post_processor_config (dict): 后处理器配置
            enable_image_crop (bool): 是否启用图像裁剪（去除天空和引擎盖）
        """
        # Carla连接参数
        self.host = host
        self.port = port
        self.town = town
        
        # 设备配置
        self.gpu_id = gpu_id
        self.device = torch.device(
            f'cuda:{gpu_id}' if gpu_id >= 0 and torch.cuda.is_available() else 'cpu'
        )
        
        # Carla对象
        self.client = None
        self.world = None
        self.vehicle = None
        
        # 功能模块
        self.model_loader = ModelLoader(model_path, self.device)
        self.image_processor = ImageProcessor(
            self.device,
            enable_crop=enable_image_crop,
            crop_top=115,
            crop_bottom=510
        )
        self.vehicle_controller = VehicleController()
        self.model_predictor = None  # 在加载模型后初始化
        self.vehicle_spawner = None  # 在连接Carla后初始化
        
        # 后处理器配置
        self.enable_post_processing = enable_post_processing
        self.post_processor_config = post_processor_config
        
        # 组件模块
        self.sensor_manager = None
        self.navigation_planner = None
        self.visualizer = CarlaVisualizer()
        self.logger = CarlaLogger()
        
        # 状态
        self.current_command = 2  # 默认命令：2=跟车
        
        print(f"初始化推理器 - 设备: {self.device}")
        
    def load_model(self, net_structure=2):
        """加载训练好的模型"""
        self.model_loader.net_structure = net_structure
        model = self.model_loader.load()
        self.model_predictor = ModelPredictor(
            model, 
            self.device,
            enable_post_processing=self.enable_post_processing,
            post_processor_config=self.post_processor_config
        )
        
    def connect_carla(self):
        """连接到Carla服务器"""
        print(f"正在连接到Carla服务器 {self.host}:{self.port}...")
        
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(10.0)
        
        print(f"正在加载地图 {self.town}...")
        self.world = self.client.load_world(self.town)
        
        # 设置同步模式
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = SYNC_MODE_DELTA_SECONDS
        self.world.apply_settings(settings)
        
        # 初始化车辆生成器
        self.vehicle_spawner = VehicleSpawner(self.world)
        
        # 创建导航规划器
        print("正在初始化导航规划器...")
        self.navigation_planner = NavigationPlannerAdapter(
            self.world, 
            sampling_resolution=ROUTE_SAMPLING_RESOLUTION
        )
        
        print("成功连接到Carla服务器！")
        
    def spawn_vehicle(self, vehicle_filter='vehicle.tesla.model3', 
                      spawn_index=None, destination_index=None, max_retries=5):
        """
        生成车辆并设置路线
        
        参数:
            vehicle_filter (str): 车辆类型
            spawn_index (int): 起点索引，None表示随机
            destination_index (int): 终点索引，None表示随机
            max_retries (int): 最大重试次数
        """
        # 检查重试次数
        if max_retries <= 0:
            raise RuntimeError("无法生成车辆：已达到最大重试次数")
        
        # 生成车辆
        self.vehicle = self.vehicle_spawner.spawn(vehicle_filter, spawn_index)
        
        # 创建传感器管理器
        self.sensor_manager = SensorManager(self.world, self.vehicle)
        
        # 设置碰撞传感器
        self.sensor_manager.setup_collision_sensor()
        
        # 等待传感器初始化
        for _ in range(3):
            self.world.tick()
        
        # 检测初始碰撞
        if self.vehicle_spawner.check_initial_collision(self.sensor_manager):
            self.vehicle.destroy()
            print(f"尝试重新生成车辆... (剩余重试次数: {max_retries-1})")
            return self.spawn_vehicle(vehicle_filter, spawn_index, destination_index, max_retries-1)
        
        # 清空碰撞历史
        self.sensor_manager.clear_collision_history()
        
        # 设置目的地
        if not self._setup_destination(destination_index):
            raise RuntimeError("未能设置有效终点，停止运行")
        
        return True
    
    def _setup_destination(self, destination_index):
        """设置目的地，返回是否成功"""
        print("\n正在规划路线...")
        spawn_points = self.world.get_map().get_spawn_points()
        
        if destination_index is not None and 0 <= destination_index < len(spawn_points):
            destination = spawn_points[destination_index].location
            print(f"使用指定终点索引: {destination_index}")
            if not self.navigation_planner.set_destination(self.vehicle, destination):
                print("⚠️ 警告：无法规划到指定终点，停止运行")
                return False
            return True
        else:
            print("⚠️ 未提供有效终点索引，停止运行")
            return False
        print()
        
    def setup_sensors(self):
        """设置所有传感器"""
        self.sensor_manager.setup_camera()
        self.sensor_manager.setup_collision_sensor()
        
    def run_inference(self, duration=60, visualize=True, auto_replan=True):
        """
        运行实时推理
        
        参数:
            duration (int): 运行时长（秒），-1表示无限运行
            visualize (bool): 是否显示可视化窗口
            auto_replan (bool): 到达目的地后是否自动重新规划路线
        """
        print(f"\n{'='*60}")
        print("开始实时推理控制")
        print(f"{'='*60}")
        print(f"运行时长: {'无限' if duration < 0 else f'{duration}秒'}")
        print(f"可视化: {'开启' if visualize else '关闭'}")
        print(f"自动重新规划: {'开启' if auto_replan else '关闭'}")
        print(f"模型输出: 后处理：{'开启' if self.enable_post_processing else '关闭'}")
        print(f"{'='*60}\n")
        
        # 等待摄像头数据
        print("等待摄像头数据...")
        while not self.sensor_manager.has_image():
            self.world.tick()
            time.sleep(0.01)
        print("摄像头数据就绪！\n")
        
        start_time = time.time()
        self.visualizer.set_start_time(start_time)
        self.logger.set_start_time(start_time)
        
        try:
            while True:
                # 检查超时
                if duration > 0 and time.time() - start_time > duration:
                    print(f"\n已运行 {duration} 秒，停止推理")
                    break
                
                # 推进模拟
                self.world.tick()
                
                if not self.sensor_manager.has_image():
                    continue
                
                # 获取导航命令
                self.current_command = self.navigation_planner.get_navigation_command(self.vehicle)
                
                # 调试：打印命令信息
                if self.logger.frame_count % PRINT_INTERVAL_FRAMES == 0:
                    route_info = self.navigation_planner.get_route_info(self.vehicle)
                    print(f"[DEBUG] Cmd: {self.current_command} "
                          f"({COMMAND_NAMES_EN.get(self.current_command, 'Unknown')}), "
                          f"Branch: {self.current_command - 2}")
                
                # 检查是否到达
                if self.navigation_planner.is_route_completed(self.vehicle):
                    print("\n🎯 已到达目的地！")
                    if auto_replan:
                        print("正在重新规划路线...")
                        if self.navigation_planner.set_random_destination(self.vehicle):
                            print("新路线规划成功，继续行驶\n")
                        else:
                            print("⚠️ 无法规划新路线，停止推理\n")
                            break
                    else:
                        print("停止推理\n")
                        break
                
                # 获取数据
                current_image = self.sensor_manager.get_latest_image()
                # 注意：get_speed_normalized 默认已使用25 m/s，与训练配置一致
                current_speed = self.vehicle_controller.get_speed_normalized(
                    self.vehicle, SPEED_NORMALIZATION_MPS
                )
                
                # 预处理图像
                img_tensor = self.image_processor.preprocess(current_image)
                
                # 预测控制
                control_result = self.model_predictor.predict(
                    img_tensor, current_speed, self.current_command
                )
                
                # 累计推理时间
                self.logger.add_inference_time(control_result['inference_time'])
                
                # 调试：打印所有分支的预测值（包含后处理对比）
                if self.logger.frame_count % PRINT_INTERVAL_FRAMES == 0:
                    self.logger.debug_print_all_branches(self.model_predictor, self.current_command, control_result)
                
                # 应用控制
                self.vehicle_controller.apply_control(
                    self.vehicle,
                    control_result['steer'],
                    control_result['throttle'],
                    control_result['brake']
                )
                
                # 更新计数
                self.logger.increment_frame()
                
                # 打印信息
                if self.logger.frame_count % PRINT_INTERVAL_FRAMES == 0:
                    route_info = self.navigation_planner.get_route_info(self.vehicle)
                    self.logger.print_status(current_speed, control_result, route_info)
                
                # 可视化
                if visualize:
                    route_info = self.navigation_planner.get_route_info(self.vehicle)
                    self.visualizer.visualize(
                        current_image, 
                        control_result, 
                        current_speed,
                        route_info,
                        self.logger.frame_count
                    )
                    
        except KeyboardInterrupt:
            print("\n用户中断推理")
        finally:
            if visualize:
                self.visualizer.close()
    
    def print_statistics(self):
        """打印统计信息"""
        self.logger.print_statistics(self.sensor_manager)
        
    def cleanup(self):
        """清理资源"""
        print("正在清理资源...")
        
        if self.sensor_manager is not None:
            self.sensor_manager.cleanup()
            
        if self.vehicle is not None:
            self.vehicle.destroy()
            
        if self.world is not None:
            settings = self.world.get_settings()
            settings.synchronous_mode = False
            self.world.apply_settings(settings)
            
        print("清理完成！")


def str2bool(v):
    """将字符串转换为布尔值"""
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Carla自动驾驶模型实时推理（模块化版本）')
    
    # 模型参数
    parser.add_argument('--model-path', type=str, default='./model/cil_policy_best.pth',
                        help='训练好的模型权重路径')
    parser.add_argument('--net-structure', type=int, default=2,
                        help='网络结构类型 (1|2|3)')
    parser.add_argument('--gpu', type=int, default=0,
                        help='GPU ID，-1表示使用CPU')
    
    # Carla参数
    parser.add_argument('--host', type=str, default='localhost',
                        help='Carla服务器地址')
    parser.add_argument('--port', type=int, default=2000,
                        help='Carla服务器端口')
    parser.add_argument('--town', type=str, default='Town01',
                        help='地图名称')
    parser.add_argument('--vehicle', type=str, default='vehicle.tesla.model3',
                        help='车辆类型')
    
    # 路线规划参数
    parser.add_argument('--spawn-index', type=int, default=1,
                        help='起点索引')
    parser.add_argument('--dest-index', type=int, default=41,
                        help='终点索引')
    parser.add_argument('--list-spawns', action='store_true',
                        help='列出所有生成点位置后退出')
    
    # 运行参数
    parser.add_argument('--duration', type=int, default=60,
                        help='运行时长（秒），-1表示无限运行')
    
    # 功能开关
    parser.add_argument('--auto-replan', type=str2bool, default=False,
                        help='到达目的地后自动重新规划路线')
    parser.add_argument('--visualize', type=str2bool, default=True,
                        help='显示可视化窗口')
    parser.add_argument('--post-processing', type=str2bool, default=True,
                        help='启用模型输出后处理（启发式规则优化）')
    parser.add_argument('--image-crop', type=str2bool, default=True,
                        help='启用图像裁剪（去除天空和引擎盖，与训练一致）')

    
    args = parser.parse_args()
    
    # 将相对路径转换为基于脚本目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(args.model_path):
        args.model_path = os.path.join(script_dir, args.model_path)
    

    # 创建推理器
    inferencer = CarlaInference(
        model_path=args.model_path,
        host=args.host,
        port=args.port,
        town=args.town,
        gpu_id=args.gpu,
        enable_post_processing=args.post_processing,
        enable_image_crop=args.image_crop
    )
    
    try:
        # 初始化
        inferencer.load_model(net_structure=args.net_structure)
        inferencer.connect_carla()
        
        # 如果是列出生成点模式
        if args.list_spawns:
            spawn_points = inferencer.world.get_map().get_spawn_points()
            print(f"\n{'='*80}")
            print(f"{args.town} 地图的所有生成点（共 {len(spawn_points)} 个）")
            print(f"{'='*80}")
            print(f"{'索引':<6} {'X坐标':<12} {'Y坐标':<12} {'Z坐标':<12} {'朝向(Yaw)':<12}")
            print(f"{'-'*80}")
            
            for i, spawn in enumerate(spawn_points):
                loc = spawn.location
                rot = spawn.rotation
                print(f"{i:<6} {loc.x:<12.2f} {loc.y:<12.2f} {loc.z:<12.2f} {rot.yaw:<12.2f}")
            
            print(f"{'='*80}")
            return
        
        inferencer.spawn_vehicle(
            vehicle_filter=args.vehicle,
            spawn_index=args.spawn_index,
            destination_index=args.dest_index
        )
        inferencer.setup_sensors()
        
        # 等待传感器初始化
        time.sleep(1.0)
        
        # 运行推理
        inferencer.run_inference(
            duration=args.duration,
            visualize=args.visualize,
            auto_replan=args.auto_replan
        )
        
        # 打印统计
        inferencer.print_statistics()
        
    except KeyboardInterrupt:
        print("\n用户中断程序")
        
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        inferencer.cleanup()
        print("程序结束")


if __name__ == '__main__':
    main()
