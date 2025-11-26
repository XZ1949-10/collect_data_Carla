#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LocalPlanner 初始化简单示例
展示如何正确初始化 LocalPlanner
"""

import carla
import sys
import os

# 添加agents路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from agents.navigation.local_planner import LocalPlanner


# ============================================
# 示例1: 最简单的初始化（只传入车辆）
# ============================================
def example1_minimal():
    """最简单的初始化方式"""
    print("=== 示例1: 最简单的初始化 ===\n")
    
    # 连接CARLA
    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    
    # 生成车辆
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
    spawn_point = world.get_map().get_spawn_points()[0]
    vehicle = world.spawn_actor(vehicle_bp, spawn_point)
    
    # 初始化 LocalPlanner（只需要车辆对象）
    local_planner = LocalPlanner(vehicle)
    
    print("✓ LocalPlanner 初始化成功")
    print(f"  - 默认目标速度: {local_planner._target_speed} km/h")
    print(f"  - 默认采样半径: {local_planner._sampling_radius} 米")
    print(f"  - 默认偏移: {local_planner._offset} 米")
    
    # 清理
    vehicle.destroy()
    
    return local_planner


# ============================================
# 示例2: 自定义速度和路点间距
# ============================================
def example2_custom_speed():
    """自定义速度和路点间距"""
    print("\n=== 示例2: 自定义速度和路点间距 ===\n")
    
    client = carla.Client('localhost', 2000)
    world = client.get_world()
    
    # 生成车辆
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
    spawn_point = world.get_map().get_spawn_points()[0]
    vehicle = world.spawn_actor(vehicle_bp, spawn_point)
    
    # 自定义配置
    opt_dict = {
        'target_speed': 40.0,      # 40 km/h
        'sampling_radius': 1.5,    # 路点间距1.5米
    }
    
    # 初始化
    local_planner = LocalPlanner(vehicle, opt_dict=opt_dict)
    
    print("✓ LocalPlanner 初始化成功")
    print(f"  - 目标速度: {local_planner._target_speed} km/h")
    print(f"  - 采样半径: {local_planner._sampling_radius} 米")
    
    vehicle.destroy()
    return local_planner


# ============================================
# 示例3: 完整配置（推荐）
# ============================================
def example3_full_config():
    """完整配置（推荐使用）"""
    print("\n=== 示例3: 完整配置（推荐）===\n")
    
    client = carla.Client('localhost', 2000)
    world = client.get_world()
    carla_map = world.get_map()  # 提前获取地图
    
    # 生成车辆
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
    spawn_point = carla_map.get_spawn_points()[0]
    vehicle = world.spawn_actor(vehicle_bp, spawn_point)
    
    # 完整配置
    opt_dict = {
        'target_speed': 30.0,           # 目标速度 30 km/h
        'sampling_radius': 2.0,         # 路点间距 2米
        'offset': 0.0,                  # 车道中心
        'base_min_distance': 3.0,       # 基础清理距离 3米
        'distance_ratio': 0.5,          # 距离比率
        'follow_speed_limits': False,   # 不跟随速度限制
    }
    
    # 初始化（传入所有3个参数）
    local_planner = LocalPlanner(
        vehicle=vehicle,        # 必需：车辆对象
        opt_dict=opt_dict,      # 可选：配置字典
        map_inst=carla_map      # 可选：地图对象（性能优化）
    )
    
    print("✓ LocalPlanner 初始化成功")
    print(f"  - 目标速度: {local_planner._target_speed} km/h")
    print(f"  - 采样半径: {local_planner._sampling_radius} 米")
    print(f"  - 车道偏移: {local_planner._offset} 米")
    print(f"  - 基础距离: {local_planner._base_min_distance} 米")
    print(f"  - 距离比率: {local_planner._distance_ratio}")
    
    vehicle.destroy()
    return local_planner


# ============================================
# 示例4: 不同场景的配置
# ============================================
def example4_scenarios():
    """不同场景的配置示例"""
    print("\n=== 示例4: 不同场景的配置 ===\n")
    
    client = carla.Client('localhost', 2000)
    world = client.get_world()
    carla_map = world.get_map()
    
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
    spawn_point = carla_map.get_spawn_points()[0]
    
    # 场景A: 城市低速驾驶
    print("场景A: 城市低速驾驶")
    vehicle_a = world.spawn_actor(vehicle_bp, spawn_point)
    planner_a = LocalPlanner(vehicle_a, opt_dict={
        'target_speed': 20.0,
        'sampling_radius': 1.0,
        'offset': 0.0,
    })
    print(f"  配置: 速度={planner_a._target_speed}, 路点间距={planner_a._sampling_radius}\n")
    
    # 场景B: 高速公路
    print("场景B: 高速公路")
    vehicle_b = world.spawn_actor(vehicle_bp, spawn_point)
    planner_b = LocalPlanner(vehicle_b, opt_dict={
        'target_speed': 80.0,
        'sampling_radius': 3.0,
    })
    print(f"  配置: 速度={planner_b._target_speed}, 路点间距={planner_b._sampling_radius}\n")
    
    # 场景C: 靠右行驶
    print("场景C: 靠右行驶")
    vehicle_c = world.spawn_actor(vehicle_bp, spawn_point)
    planner_c = LocalPlanner(vehicle_c, opt_dict={
        'target_speed': 30.0,
        'offset': 1.5,  # 向右偏移1.5米
    })
    print(f"  配置: 速度={planner_c._target_speed}, 偏移={planner_c._offset}\n")
    
    # 清理
    vehicle_a.destroy()
    vehicle_b.destroy()
    vehicle_c.destroy()


# ============================================
# 参数说明
# ============================================
def print_parameters_info():
    """打印参数说明"""
    print("\n" + "="*60)
    print("LocalPlanner 初始化参数说明")
    print("="*60)
    
    print("""
初始化签名：
    LocalPlanner(vehicle, opt_dict={}, map_inst=None)

参数说明：
┌─────────────────────────────────────────────────────────┐
│ 1. vehicle (必需)                                      │
│    - 类型: carla.Vehicle                               │
│    - 说明: CARLA车辆对象                               │
│    - 获取: world.spawn_actor(vehicle_bp, spawn_point)  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 2. opt_dict (可选)                                     │
│    - 类型: dict                                        │
│    - 默认: {}                                          │
│    - 说明: 配置参数字典                                │
│                                                         │
│    可用配置:                                           │
│    ┌───────────────────────────────────────────────┐  │
│    │ 'target_speed': float (默认20.0)             │  │
│    │   - 目标速度 (km/h)                          │  │
│    │                                               │  │
│    │ 'sampling_radius': float (默认2.0)           │  │
│    │   - 路点间距 (米)                            │  │
│    │                                               │  │
│    │ 'offset': float (默认0.0)                    │  │
│    │   - 车道偏移 (米, 正值向右, 负值向左)       │  │
│    │                                               │  │
│    │ 'base_min_distance': float (默认3.0)         │  │
│    │   - 基础清理距离 (米)                        │  │
│    │                                               │  │
│    │ 'distance_ratio': float (默认0.5)            │  │
│    │   - 速度相关距离系数                         │  │
│    │                                               │  │
│    │ 'follow_speed_limits': bool (默认False)      │  │
│    │   - 是否跟随道路速度限制                     │  │
│    └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 3. map_inst (可选)                                     │
│    - 类型: carla.Map                                   │
│    - 默认: None (自动获取)                             │
│    - 说明: CARLA地图对象                               │
│    - 获取: world.get_map()                             │
│    - 用途: 性能优化，避免重复获取地图                  │
└─────────────────────────────────────────────────────────┘
    """)


# ============================================
# 主函数
# ============================================
def main():
    """运行所有示例"""
    
    print("LocalPlanner 初始化示例")
    print("="*60)
    
    # 打印参数说明
    print_parameters_info()
    
    print("\n注意：以下示例需要CARLA服务器正在运行")
    print("按 Ctrl+C 跳过实际运行\n")
    
    try:
        # 运行示例（需要CARLA服务器）
        # example1_minimal()
        # example2_custom_speed()
        # example3_full_config()
        # example4_scenarios()
        
        print("\n提示: 取消注释上面的示例函数来运行实际代码")
        
    except Exception as e:
        print(f"\n错误: {e}")
        print("请确保CARLA服务器正在运行")


if __name__ == '__main__':
    main()

