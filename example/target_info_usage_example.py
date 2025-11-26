#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
target_info 返回值使用示例
详细演示如何使用 run_step() 返回的目标信息字典
"""

import carla
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from agents.navigation.local_planner import LocalPlanner, RoadOption


# ========================================
# 示例1: 基本使用
# ========================================
def example_basic_usage(local_planner, vehicle):
    """基本使用示例"""
    
    print("=== 示例1: 基本使用 ===\n")
    
    # 获取目标路点信息
    target_info = local_planner.run_step()
    
    # 打印返回的字典内容
    print("target_info 字典内容:")
    print(f"  target_waypoint: {target_info['target_waypoint']}")
    print(f"  target_road_option: {target_info['target_road_option']}")
    print(f"  target_speed: {target_info['target_speed']} km/h")
    print(f"  queue_length: {target_info['queue_length']}")
    print(f"  is_empty: {target_info['is_empty']}")
    
    """
    输出示例:
    target_info 字典内容:
      target_waypoint: <carla.libcarla.Waypoint object at 0x7f8b2c3d4e90>
      target_road_option: RoadOption.LANEFOLLOW
      target_speed: 30.0 km/h
      queue_length: 92
      is_empty: False
    """


# ========================================
# 示例2: 检查队列状态
# ========================================
def example_check_status(local_planner):
    """检查队列状态示例"""
    
    print("\n=== 示例2: 检查队列状态 ===\n")
    
    target_info = local_planner.run_step()
    
    # 检查是否到达目的地
    if target_info['is_empty']:
        print("✓ 队列为空，已到达目的地！")
        return True
    
    # 检查剩余路点数量
    if target_info['queue_length'] < 10:
        print(f"⚠️  警告：剩余路点较少 ({target_info['queue_length']})")
    
    # 检查道路动作
    if target_info['target_road_option'] in [RoadOption.LEFT, RoadOption.RIGHT]:
        print(f"📍 即将执行转向: {target_info['target_road_option'].name}")
    
    return False


# ========================================
# 示例3: 提取路点位置信息
# ========================================
def example_extract_waypoint_info(target_info, vehicle):
    """提取路点位置信息示例"""
    
    print("\n=== 示例3: 提取路点位置信息 ===\n")
    
    if target_info['is_empty']:
        print("队列为空，无路点信息")
        return
    
    # 获取目标路点
    target_waypoint = target_info['target_waypoint']
    
    # 提取位置信息
    target_location = target_waypoint.transform.location
    target_rotation = target_waypoint.transform.rotation
    
    print(f"目标路点位置:")
    print(f"  x: {target_location.x:.2f} 米")
    print(f"  y: {target_location.y:.2f} 米")
    print(f"  z: {target_location.z:.2f} 米")
    
    print(f"\n目标路点朝向:")
    print(f"  pitch: {target_rotation.pitch:.2f} 度")
    print(f"  yaw: {target_rotation.yaw:.2f} 度")
    print(f"  roll: {target_rotation.roll:.2f} 度")
    
    # 计算到目标的距离
    vehicle_location = vehicle.get_location()
    distance = vehicle_location.distance(target_location)
    print(f"\n距离目标路点: {distance:.2f} 米")
    
    """
    输出示例:
    目标路点位置:
      x: 152.35 米
      y: 195.67 米
      z: 0.50 米
    
    目标路点朝向:
      pitch: 0.00 度
      yaw: 180.23 度
      roll: 0.00 度
    
    距离目标路点: 3.45 米
    """


# ========================================
# 示例4: 根据道路动作调整控制
# ========================================
def example_action_based_control(target_info, vehicle):
    """根据道路动作调整控制示例"""
    
    print("\n=== 示例4: 根据道路动作调整控制 ===\n")
    
    if target_info['is_empty']:
        print("紧急停车")
        return (0.0, 1.0, 0.0)
    
    road_option = target_info['target_road_option']
    target_speed = target_info['target_speed']
    
    # 根据道路动作调整目标速度
    if road_option == RoadOption.LEFT:
        adjusted_speed = target_speed * 0.7  # 左转减速30%
        print(f"左转: 目标速度 {target_speed:.1f} → {adjusted_speed:.1f} km/h")
        
    elif road_option == RoadOption.RIGHT:
        adjusted_speed = target_speed * 0.8  # 右转减速20%
        print(f"右转: 目标速度 {target_speed:.1f} → {adjusted_speed:.1f} km/h")
        
    elif road_option == RoadOption.STRAIGHT:
        adjusted_speed = target_speed * 0.9  # 直行减速10%
        print(f"交叉口直行: 目标速度 {target_speed:.1f} → {adjusted_speed:.1f} km/h")
        
    elif road_option in [RoadOption.CHANGELANELEFT, RoadOption.CHANGELANERIGHT]:
        adjusted_speed = target_speed * 0.95  # 变道减速5%
        print(f"变道: 目标速度 {target_speed:.1f} → {adjusted_speed:.1f} km/h")
        
    else:  # LANEFOLLOW
        adjusted_speed = target_speed
        print(f"车道跟随: 保持目标速度 {target_speed:.1f} km/h")
    
    # 使用调整后的速度计算控制
    throttle, brake, steer = compute_control(
        vehicle, 
        target_info['target_waypoint'], 
        adjusted_speed
    )
    
    return (throttle, brake, steer)


# ========================================
# 示例5: 完整的导航循环
# ========================================
def example_navigation_loop(local_planner, vehicle, world):
    """完整的导航循环示例"""
    
    print("\n=== 示例5: 完整的导航循环 ===\n")
    
    step = 0
    
    while step < 100:  # 限制步数用于演示
        world.tick()
        
        # ========== 步骤1: 获取目标信息 ==========
        target_info = local_planner.run_step()
        
        # ========== 步骤2: 检查队列状态 ==========
        if target_info['is_empty']:
            print(f"\n步骤 {step}: 已到达目的地！")
            break
        
        # ========== 步骤3: 提取关键信息 ==========
        target_waypoint = target_info['target_waypoint']
        target_speed = target_info['target_speed']
        road_option = target_info['target_road_option']
        queue_length = target_info['queue_length']
        
        # ========== 步骤4: 计算控制指令 ==========
        throttle, brake, steer = compute_control(
            vehicle,
            target_waypoint,
            target_speed
        )
        
        # ========== 步骤5: 应用控制 ==========
        local_planner.apply_control(throttle, brake, steer)
        
        # ========== 步骤6: 打印状态（每10步） ==========
        if step % 10 == 0:
            current_speed = get_vehicle_speed(vehicle)
            print(f"步骤 {step:3d} | "
                  f"速度: {current_speed:5.1f} km/h | "
                  f"油门: {throttle:.2f} | "
                  f"刹车: {brake:.2f} | "
                  f"转向: {steer:+.2f} | "
                  f"动作: {road_option.name:15s} | "
                  f"剩余: {queue_length:3d}")
        
        step += 1


# ========================================
# 示例6: 使用字典解包
# ========================================
def example_dict_unpacking(local_planner):
    """使用字典解包示例"""
    
    print("\n=== 示例6: 使用字典解包 ===\n")
    
    target_info = local_planner.run_step()
    
    # 方法1: 直接访问
    waypoint = target_info['target_waypoint']
    speed = target_info['target_speed']
    
    # 方法2: 使用变量名解包
    target_waypoint = target_info['target_waypoint']
    target_road_option = target_info['target_road_option']
    target_speed = target_info['target_speed']
    queue_length = target_info['queue_length']
    is_empty = target_info['is_empty']
    
    print(f"解包后的变量:")
    print(f"  target_waypoint: {target_waypoint}")
    print(f"  target_road_option: {target_road_option}")
    print(f"  target_speed: {target_speed}")
    print(f"  queue_length: {queue_length}")
    print(f"  is_empty: {is_empty}")
    
    # 方法3: 使用 .get() 方法（带默认值）
    waypoint = target_info.get('target_waypoint', None)
    speed = target_info.get('target_speed', 0.0)
    
    print(f"\n使用 .get() 方法:")
    print(f"  waypoint: {waypoint}")
    print(f"  speed: {speed}")


# ========================================
# 示例7: 错误处理
# ========================================
def example_error_handling(local_planner, vehicle):
    """错误处理示例"""
    
    print("\n=== 示例7: 错误处理 ===\n")
    
    try:
        # 获取目标信息
        target_info = local_planner.run_step()
        
        # 检查1: 队列是否为空
        if target_info['is_empty']:
            print("⚠️  队列为空，执行紧急停车")
            local_planner.apply_control(0.0, 1.0, 0.0)
            return
        
        # 检查2: 路点是否有效
        if target_info['target_waypoint'] is None:
            print("⚠️  目标路点无效，执行紧急停车")
            local_planner.apply_control(0.0, 1.0, 0.0)
            return
        
        # 检查3: 目标速度是否合理
        if target_info['target_speed'] <= 0:
            print("⚠️  目标速度无效，设置为默认值")
            target_speed = 20.0  # 默认速度
        else:
            target_speed = target_info['target_speed']
        
        # 检查4: 队列长度是否足够
        if target_info['queue_length'] < 5:
            print(f"⚠️  警告：剩余路点较少 ({target_info['queue_length']})")
        
        # 正常计算控制
        throttle, brake, steer = compute_control(
            vehicle,
            target_info['target_waypoint'],
            target_speed
        )
        
        # 检查5: 控制值是否合理
        if not (0.0 <= throttle <= 1.0):
            print(f"⚠️  油门值异常: {throttle:.2f}，限制到 [0, 1]")
            throttle = np.clip(throttle, 0.0, 1.0)
        
        if not (0.0 <= brake <= 1.0):
            print(f"⚠️  刹车值异常: {brake:.2f}，限制到 [0, 1]")
            brake = np.clip(brake, 0.0, 1.0)
        
        if not (-1.0 <= steer <= 1.0):
            print(f"⚠️  转向值异常: {steer:.2f}，限制到 [-1, 1]")
            steer = np.clip(steer, -1.0, 1.0)
        
        # 应用控制
        local_planner.apply_control(throttle, brake, steer)
        print("✓ 控制指令已成功应用")
        
    except KeyError as e:
        print(f"❌ 字典键错误: {e}")
        local_planner.apply_control(0.0, 1.0, 0.0)
        
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        local_planner.apply_control(0.0, 1.0, 0.0)


# ========================================
# 示例8: 与其他系统集成
# ========================================
def example_integration_with_external_systems(local_planner, vehicle):
    """与其他系统集成示例"""
    
    print("\n=== 示例8: 与其他系统集成 ===\n")
    
    target_info = local_planner.run_step()
    
    if not target_info['is_empty']:
        # 1. 传递给外部控制器
        external_controller_input = {
            'waypoint_x': target_info['target_waypoint'].transform.location.x,
            'waypoint_y': target_info['target_waypoint'].transform.location.y,
            'waypoint_yaw': target_info['target_waypoint'].transform.rotation.yaw,
            'target_speed': target_info['target_speed'],
            'action_type': target_info['target_road_option'].value,
        }
        print("传递给外部控制器的数据:")
        print(f"  {external_controller_input}")
        
        # 2. 记录日志
        log_entry = {
            'timestamp': get_timestamp(),
            'target_waypoint': str(target_info['target_waypoint'].transform.location),
            'target_speed': target_info['target_speed'],
            'road_option': target_info['target_road_option'].name,
            'queue_length': target_info['queue_length'],
        }
        print(f"\n日志记录: {log_entry}")
        
        # 3. 发送到机器学习模型
        ml_features = extract_ml_features(vehicle, target_info)
        print(f"\nML模型输入特征: {ml_features}")


# ========================================
# 辅助函数
# ========================================

def compute_control(vehicle, target_waypoint, target_speed):
    """简化的控制计算函数"""
    # 这里是简化版本，实际应该使用完整的控制器
    if target_waypoint is None:
        return (0.0, 1.0, 0.0)
    
    # 简单的比例控制
    current_speed = get_vehicle_speed(vehicle)
    speed_error = target_speed - current_speed
    
    if speed_error > 0:
        throttle = min(speed_error / 10.0, 0.75)
        brake = 0.0
    else:
        throttle = 0.0
        brake = min(-speed_error / 10.0, 0.5)
    
    # 简单的转向控制
    vehicle_location = vehicle.get_location()
    target_location = target_waypoint.transform.location
    
    dx = target_location.x - vehicle_location.x
    dy = target_location.y - vehicle_location.y
    angle = np.arctan2(dy, dx)
    
    vehicle_yaw = np.radians(vehicle.get_transform().rotation.yaw)
    angle_diff = angle - vehicle_yaw
    
    # 标准化到 [-pi, pi]
    while angle_diff > np.pi:
        angle_diff -= 2 * np.pi
    while angle_diff < -np.pi:
        angle_diff += 2 * np.pi
    
    steer = np.clip(angle_diff * 2.0, -0.8, 0.8)
    
    return (throttle, brake, steer)


def get_vehicle_speed(vehicle):
    """获取车辆速度 (km/h)"""
    velocity = vehicle.get_velocity()
    speed = 3.6 * np.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    return speed


def get_timestamp():
    """获取时间戳"""
    import time
    return time.time()


def extract_ml_features(vehicle, target_info):
    """提取机器学习特征"""
    if target_info['is_empty']:
        return []
    
    vehicle_location = vehicle.get_location()
    target_location = target_info['target_waypoint'].transform.location
    
    features = [
        target_location.x - vehicle_location.x,  # dx
        target_location.y - vehicle_location.y,  # dy
        get_vehicle_speed(vehicle),              # current_speed
        target_info['target_speed'],             # target_speed
        target_info['target_road_option'].value, # action_type
        target_info['queue_length'],             # queue_length
    ]
    
    return features


# ========================================
# 完整的演示主函数
# ========================================

def main_demo():
    """完整的演示"""
    
    print("=" * 60)
    print("target_info 返回值使用示例演示")
    print("=" * 60)
    
    # 注意：以下代码需要实际的CARLA连接才能运行
    # 这里仅展示代码结构
    
    print("\n这些示例展示了如何使用 run_step() 返回的 target_info 字典\n")
    
    print("target_info 字典结构:")
    print("=" * 60)
    print("""
    {
        'target_waypoint': carla.Waypoint,  # 目标路点对象
        'target_road_option': RoadOption,   # 道路动作枚举
        'target_speed': float,              # 建议速度 (km/h)
        'queue_length': int,                # 剩余路点数量
        'is_empty': bool                    # 队列是否为空
    }
    """)
    
    print("\n使用场景:")
    print("=" * 60)
    print("1. 基本使用 - 获取和打印目标信息")
    print("2. 检查状态 - 判断是否到达目的地")
    print("3. 提取位置 - 获取路点的具体位置信息")
    print("4. 动作调整 - 根据道路动作调整控制策略")
    print("5. 导航循环 - 完整的导航流程")
    print("6. 字典操作 - 不同的字典访问方式")
    print("7. 错误处理 - 安全的错误处理机制")
    print("8. 系统集成 - 与外部系统交互")
    
    print("\n" + "=" * 60)
    print("请参考上述示例函数了解详细用法")
    print("=" * 60)


if __name__ == '__main__':
    main_demo()

