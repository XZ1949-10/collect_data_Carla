#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
外部控制器示例
演示如何使用修改后的 LocalPlanner（无PID版本）配合外部控制器
"""

import carla
import random
import time
import numpy as np
import sys
import os

# 添加agents路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from agents.navigation.global_route_planner import GlobalRoutePlanner
from agents.navigation.local_planner import LocalPlanner, RoadOption


# ============================================
# 示例1: 简单的外部控制器
# ============================================
class SimpleExternalController:
    """
    简单的外部控制器示例
    实现基础的跟踪控制逻辑
    """
    
    def __init__(self, vehicle):
        self.vehicle = vehicle
        
    def compute_control(self, target_waypoint, target_speed):
        """
        计算控制指令
        
        :param target_waypoint: 目标路点
        :param target_speed: 目标速度 (km/h)
        :return: (throttle, brake, steer) 元组
        """
        if target_waypoint is None:
            # 没有目标路点，紧急停车
            return (0.0, 1.0, 0.0)
        
        # 获取车辆当前状态
        vehicle_transform = self.vehicle.get_transform()
        vehicle_location = vehicle_transform.location
        vehicle_velocity = self.vehicle.get_velocity()
        current_speed = 3.6 * np.sqrt(vehicle_velocity.x**2 + 
                                     vehicle_velocity.y**2 + 
                                     vehicle_velocity.z**2)
        
        # ========== 纵向控制（速度控制）==========
        speed_error = target_speed - current_speed
        
        if speed_error > 5:  # 需要加速
            throttle = 0.7
            brake = 0.0
        elif speed_error > 0:  # 需要轻微加速
            throttle = 0.3
            brake = 0.0
        elif speed_error > -5:  # 需要轻微减速
            throttle = 0.0
            brake = 0.2
        else:  # 需要强力减速
            throttle = 0.0
            brake = 0.5
        
        # ========== 横向控制（转向控制）==========
        # 计算车辆到目标路点的方向
        target_location = target_waypoint.transform.location
        target_vector = np.array([
            target_location.x - vehicle_location.x,
            target_location.y - vehicle_location.y
        ])
        target_vector_norm = np.linalg.norm(target_vector)
        
        if target_vector_norm > 0.1:
            target_vector = target_vector / target_vector_norm
            
            # 车辆当前朝向
            forward_vector = vehicle_transform.get_forward_vector()
            vehicle_vector = np.array([forward_vector.x, forward_vector.y])
            
            # 计算转向角度
            cross_product = np.cross(vehicle_vector, target_vector)
            steer = np.clip(cross_product * 2.0, -1.0, 1.0)
        else:
            steer = 0.0
        
        return (throttle, brake, steer)


# ============================================
# 示例2: PID外部控制器
# ============================================
class PIDExternalController:
    """
    PID外部控制器示例
    使用PID算法进行精确控制
    """
    
    def __init__(self, vehicle):
        self.vehicle = vehicle
        
        # 纵向PID参数
        self.speed_kp = 1.0
        self.speed_ki = 0.05
        self.speed_kd = 0.1
        self.speed_error_integral = 0.0
        self.speed_last_error = 0.0
        
        # 横向PID参数
        self.steer_kp = 2.0
        self.steer_ki = 0.0
        self.steer_kd = 0.3
        self.steer_error_integral = 0.0
        self.steer_last_error = 0.0
        
        # 时间步长
        self.dt = 0.05
        
    def compute_control(self, target_waypoint, target_speed):
        """
        使用PID计算控制指令
        
        :param target_waypoint: 目标路点
        :param target_speed: 目标速度 (km/h)
        :return: (throttle, brake, steer) 元组
        """
        if target_waypoint is None:
            return (0.0, 1.0, 0.0)
        
        # 获取车辆当前状态
        vehicle_transform = self.vehicle.get_transform()
        vehicle_location = vehicle_transform.location
        vehicle_velocity = self.vehicle.get_velocity()
        current_speed = 3.6 * np.sqrt(vehicle_velocity.x**2 + 
                                     vehicle_velocity.y**2 + 
                                     vehicle_velocity.z**2)
        
        # ========== 纵向PID控制 ==========
        speed_error = target_speed - current_speed
        self.speed_error_integral += speed_error * self.dt
        speed_error_derivative = (speed_error - self.speed_last_error) / self.dt
        
        acceleration = (self.speed_kp * speed_error + 
                       self.speed_ki * self.speed_error_integral + 
                       self.speed_kd * speed_error_derivative)
        
        self.speed_last_error = speed_error
        
        # 转换为油门/刹车
        if acceleration >= 0.0:
            throttle = np.clip(acceleration, 0.0, 0.75)
            brake = 0.0
        else:
            throttle = 0.0
            brake = np.clip(abs(acceleration), 0.0, 0.5)
        
        # ========== 横向PID控制 ==========
        target_location = target_waypoint.transform.location
        
        # 计算横向误差（简化版）
        forward_vector = vehicle_transform.get_forward_vector()
        vehicle_vector = np.array([forward_vector.x, forward_vector.y, 0.0])
        
        target_vector = np.array([
            target_location.x - vehicle_location.x,
            target_location.y - vehicle_location.y,
            0.0
        ])
        
        target_vector_norm = np.linalg.norm(target_vector)
        if target_vector_norm > 0.1:
            target_vector = target_vector / target_vector_norm
            
            # 计算角度误差
            dot_product = np.dot(vehicle_vector, target_vector)
            cross_product = np.cross(vehicle_vector, target_vector)
            angle_error = np.arctan2(cross_product[2], dot_product)
            
            # PID控制
            self.steer_error_integral += angle_error * self.dt
            steer_error_derivative = (angle_error - self.steer_last_error) / self.dt
            
            steer = (self.steer_kp * angle_error + 
                    self.steer_ki * self.steer_error_integral + 
                    self.steer_kd * steer_error_derivative)
            
            self.steer_last_error = angle_error
            steer = np.clip(steer, -0.8, 0.8)
        else:
            steer = 0.0
        
        return (throttle, brake, steer)


# ============================================
# 主函数：演示如何使用外部控制器
# ============================================
def main():
    print("=== 外部控制器示例 ===\n")
    
    # ========== 1. 连接CARLA服务器 ==========
    print("正在连接CARLA服务器...")
    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    carla_map = world.get_map()
    print(f"当前地图: {carla_map.name}\n")
    
    # 设置同步模式
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)
    
    # ========== 2. 生成车辆 ==========
    print("正在生成车辆...")
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
    spawn_points = carla_map.get_spawn_points()
    start_transform = random.choice(spawn_points)
    vehicle = world.spawn_actor(vehicle_bp, start_transform)
    world.tick()
    print(f"车辆已生成在: {start_transform.location}\n")
    
    # ========== 3. 创建规划器 ==========
    print("初始化规划器...")
    global_planner = GlobalRoutePlanner(carla_map, 2.0)
    
    # 创建局部规划器（无PID版本）
    opt_dict = {
        'target_speed': 30.0,
        'sampling_radius': 2.0,
    }
    local_planner = LocalPlanner(vehicle, opt_dict=opt_dict, map_inst=carla_map)
    print("  ✓ 规划器已就绪\n")
    
    # ========== 4. 创建外部控制器 ==========
    print("创建外部控制器...")
    print("选择控制器类型:")
    print("  1. SimpleExternalController (简单控制器)")
    print("  2. PIDExternalController (PID控制器)")
    
    # 这里默认使用PID控制器
    external_controller = PIDExternalController(vehicle)
    print("  ✓ 使用 PIDExternalController\n")
    
    # ========== 5. 规划路径 ==========
    print("规划路径...")
    start_location = vehicle.get_location()
    end_transform = random.choice(spawn_points)
    while start_location.distance(end_transform.location) < 50.0:
        end_transform = random.choice(spawn_points)
    end_location = end_transform.location
    
    print(f"起点: (x={start_location.x:.1f}, y={start_location.y:.1f})")
    print(f"终点: (x={end_location.x:.1f}, y={end_location.y:.1f})")
    print(f"距离: {start_location.distance(end_location):.2f} 米")
    
    route = global_planner.trace_route(start_location, end_location)
    local_planner.set_global_plan(route, stop_waypoint_creation=True, clean_queue=True)
    print(f"路径已设置，共 {len(route)} 个路点\n")
    
    # ========== 6. 执行导航循环 ==========
    print("开始自动驾驶...\n")
    print("按 Ctrl+C 中断\n")
    
    try:
        step_count = 0
        last_print_time = time.time()
        
        while True:
            world.tick()
            
            # 检查是否到达目的地
            if local_planner.done():
                print("\n✓ 已到达目的地！")
                break
            
            # ========== 核心：外部控制流程 ==========
            # 步骤1: 获取目标路点信息
            target_info = local_planner.run_step(debug=False)
            
            # 步骤2: 使用外部控制器计算控制指令
            throttle, brake, steer = external_controller.compute_control(
                target_waypoint=target_info['target_waypoint'],
                target_speed=target_info['target_speed']
            )
            
            # 步骤3: 应用控制到车辆
            local_planner.apply_control(throttle, brake, steer)
            # ========================================
            
            # 打印状态（每秒一次）
            current_time = time.time()
            if current_time - last_print_time >= 1.0:
                velocity = vehicle.get_velocity()
                speed_kmh = 3.6 * np.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                
                current_location = vehicle.get_location()
                distance_to_goal = current_location.distance(end_location)
                
                road_option_name = target_info['target_road_option'].name
                remaining_waypoints = target_info['queue_length']
                
                print(f"步数: {step_count:5d} | "
                      f"速度: {speed_kmh:5.1f} km/h | "
                      f"油门: {throttle:.2f} | "
                      f"刹车: {brake:.2f} | "
                      f"转向: {steer:+.2f} | "
                      f"动作: {road_option_name:15s} | "
                      f"剩余路点: {remaining_waypoints:4d} | "
                      f"距目标: {distance_to_goal:6.1f}m")
                
                last_print_time = current_time
            
            step_count += 1
            
            # 安全检查
            if step_count > 20000:
                print("\n导航超时")
                break
    
    except KeyboardInterrupt:
        print("\n\n用户中断")
    
    finally:
        # ========== 7. 清理资源 ==========
        print("\n正在清理资源...")
        vehicle.destroy()
        settings.synchronous_mode = False
        world.apply_settings(settings)
        print("完成！")


# ============================================
# 示例3: 使用numpy数组直接设置控制值
# ============================================
def example_direct_control():
    """演示直接设置控制值的方法"""
    print("=== 直接控制示例 ===\n")
    
    # ... 初始化代码类似 ...
    
    # 在导航循环中：
    # target_info = local_planner.run_step()
    
    # 方法1: 使用 apply_control
    # local_planner.apply_control(throttle, brake, steer)
    
    # 方法2: 手动创建VehicleControl
    # control = carla.VehicleControl()
    # control.throttle = throttle
    # control.brake = brake
    # control.steer = steer
    # vehicle.apply_control(control)


if __name__ == '__main__':
    main()

