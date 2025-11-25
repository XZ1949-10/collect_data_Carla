#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
当前信息 vs 目标信息 - 演示代码
清楚展示 target_info 返回的是"目标"而不是"当前"
"""

import carla
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from agents.navigation.local_planner import LocalPlanner
from agents.tools.misc import get_speed


def demo_current_vs_target(vehicle, local_planner, carla_map):
    """
    演示当前信息和目标信息的区别
    """
    
    print("=" * 80)
    print("当前信息 vs 目标信息 - 实时对比")
    print("=" * 80)
    
    # ========== 获取目标信息 ==========
    target_info = local_planner.run_step()
    
    # ========== 获取当前信息 ==========
    # 1. 当前位置
    current_location = vehicle.get_location()
    
    # 2. 当前朝向
    current_transform = vehicle.get_transform()
    current_rotation = current_transform.rotation
    
    # 3. 当前速度
    current_speed = get_speed(vehicle)  # km/h
    
    # 4. 当前路点
    current_waypoint = carla_map.get_waypoint(current_location)
    
    # ========== 显示对比 ==========
    print("\n【当前信息】- 车辆实际状态")
    print("-" * 80)
    print(f"📍 当前位置: (x={current_location.x:.2f}, y={current_location.y:.2f}, z={current_location.z:.2f})")
    print(f"🧭 当前朝向: yaw={current_rotation.yaw:.2f}°")
    print(f"⚡ 当前速度: {current_speed:.2f} km/h")
    print(f"🛣️  当前车道: road_id={current_waypoint.road_id}, lane_id={current_waypoint.lane_id}")
    
    print("\n【目标信息】- 应该到达的状态")
    print("-" * 80)
    
    if target_info['is_empty']:
        print("⚠️  队列为空，没有目标")
    else:
        target_waypoint = target_info['target_waypoint']
        target_location = target_waypoint.transform.location
        target_rotation = target_waypoint.transform.rotation
        target_speed = target_info['target_speed']
        target_road_option = target_info['target_road_option']
        
        print(f"📍 目标位置: (x={target_location.x:.2f}, y={target_location.y:.2f}, z={target_location.z:.2f})")
        print(f"🧭 目标朝向: yaw={target_rotation.yaw:.2f}°")
        print(f"⚡ 目标速度: {target_speed:.2f} km/h")
        print(f"🚦 需要动作: {target_road_option.name}")
        
        # ========== 计算差异 ==========
        distance = current_location.distance(target_location)
        speed_diff = target_speed - current_speed
        yaw_diff = target_rotation.yaw - current_rotation.yaw
        
        print("\n【差异分析】- 需要调整的量")
        print("-" * 80)
        print(f"📏 距离目标: {distance:.2f} 米")
        print(f"🏃 速度差异: {speed_diff:+.2f} km/h ({'需要加速 🔼' if speed_diff > 0 else '需要减速 🔽' if speed_diff < 0 else '速度合适 ✓'})")
        print(f"🔄 朝向差异: {yaw_diff:+.2f}°")
    
    print("=" * 80)


def demo_step_by_step(vehicle, local_planner, carla_map):
    """
    逐步演示：展示车辆从当前位置移动到目标位置的过程
    """
    
    print("\n\n" + "=" * 80)
    print("逐步演示：车辆移动过程")
    print("=" * 80)
    
    for step in range(5):
        print(f"\n【步骤 {step}】")
        print("-" * 80)
        
        # 当前信息
        current_loc = vehicle.get_location()
        current_spd = get_speed(vehicle)
        
        # 目标信息
        target_info = local_planner.run_step()
        
        if not target_info['is_empty']:
            target_loc = target_info['target_waypoint'].transform.location
            target_spd = target_info['target_speed']
            
            distance = current_loc.distance(target_loc)
            
            print(f"当前位置: ({current_loc.x:.1f}, {current_loc.y:.1f}) @ {current_spd:.1f} km/h")
            print(f"目标位置: ({target_loc.x:.1f}, {target_loc.y:.1f}) @ {target_spd:.1f} km/h")
            print(f"差距: {distance:.2f} 米")
            print(f"说明: 车辆在 ({current_loc.x:.1f}, {current_loc.y:.1f})，正在向 ({target_loc.x:.1f}, {target_loc.y:.1f}) 移动")
        else:
            print("✓ 已到达目的地")
            break


def visualize_in_text():
    """
    文字可视化：当前位置 vs 目标位置
    """
    
    print("\n\n" + "=" * 80)
    print("文字可视化示意图")
    print("=" * 80)
    
    print("""
场景：车辆在直道上行驶

          当前位置                   目标位置
             ↓                         ↓
    ┌───────🚗─────────────────────────📍──────────────────┐
    │      (100,200)                 (110,200)             │  道路
    │       15 km/h                   30 km/h              │
    │         ↑                         ↑                  │
    │         |                         |                  │
    │    current_location          target_waypoint        │
    │    current_speed             target_speed           │
    │                                                      │
    │    需要做的事：                                      │
    │    1. 前进 10米 到达目标位置                        │
    │    2. 加速 15 km/h 到达目标速度                     │
    │    3. 动作: LANEFOLLOW (保持直行)                   │
    └──────────────────────────────────────────────────────┘

场景：车辆即将左转

          当前位置                   目标位置
             ↓                         ↓
    ─────────🚗                       
             │                        📍 ← 路口，需要左转
             │                       ╱
             │                      ╱
             │                     ╱
             └────────────────────
    
    当前: (100,200) @ 25 km/h, 朝向: 北(0°)
    目标: (105,205) @ 20 km/h, 朝向: 西北(315°)
    动作: LEFT (左转)
    
    说明：
    - target_waypoint (105,205) 是路口位置，不是当前位置
    - target_road_option = LEFT 表示需要左转
    - 当前车辆还在 (100,200)，正在向目标移动
    """)


def print_summary():
    """
    打印总结说明
    """
    
    print("\n\n" + "=" * 80)
    print("总结")
    print("=" * 80)
    
    print("""
target_info 返回的三个值：

1. target_waypoint (目标路点)
   ✅ 是：下一个要到达的路点位置
   ❌ 不是：车辆当前位置
   
   如何理解：GPS导航中显示的"下一个转向点"
   
   获取当前位置：
   current_location = vehicle.get_location()

2. target_road_option (目标动作)
   ✅ 是：到达目标路点需要执行的动作（左转/右转/直行）
   ❌ 不是：车辆当前正在执行的动作
   
   如何理解：GPS导航中的"前方路口左转"
   
   获取当前动作：
   # 无法直接获取，因为"当前动作"是一个过程

3. target_speed (目标速度)
   ✅ 是：建议达到的速度
   ❌ 不是：车辆当前实际速度
   
   如何理解：GPS导航中的"限速30km/h"
   
   获取当前速度：
   from agents.tools.misc import get_speed
   current_speed = get_speed(vehicle)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

关键要点：

target_info 描述的是 "目标状态"（应该到达的地方）
不是                  "当前状态"（现在所在的地方）

控制器的作用就是：根据"当前状态"和"目标状态"的差异，计算控制指令

控制逻辑：
    当前状态 ──┐
               ├──→ 计算差异 ──→ 生成控制指令 ──→ 逐渐接近目标
    目标状态 ──┘
    
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)


def main():
    """主演示程序"""
    
    # 文字可视化
    visualize_in_text()
    
    # 打印总结
    print_summary()
    
    print("\n提示：运行时连接CARLA可以看到实际数值对比")


if __name__ == '__main__':
    main()

