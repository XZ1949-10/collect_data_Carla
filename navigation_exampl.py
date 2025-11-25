#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
完整的CARLA自动驾驶导航示例
演示如何使用 GlobalRoutePlanner 和 LocalPlanner

使用函数封装，结构清晰，便于维护和扩展
"""

import carla
import random
import time
import numpy as np

from agents.navigation.global_route_planner import GlobalRoutePlanner
from agents.navigation.local_planner import LocalPlanner, RoadOption


# ========================================
# 配置参数
# ========================================
class NavigationConfig:
    """导航配置参数"""
    # 服务器配置
    CARLA_HOST = 'localhost'
    CARLA_PORT = 2000
    TIMEOUT = 10.0
    
    # 地图配置
    MAP_NAME = None  # None = 使用当前地图, 'Town01' = 加载指定地图
    
    # 车辆配置
    VEHICLE_MODEL = 'vehicle.tesla.model3'
    
    # 起点终点配置
    USE_RANDOM_SPAWN = True  # True = 随机生成, False = 使用指定坐标
    START_LOCATION = carla.Location(x=150.0, y=199.0, z=0.5)
    START_ROTATION = carla.Rotation(pitch=0.0, yaw=180.0, roll=0.0)
    END_LOCATION = carla.Location(x=50.0, y=50.0, z=0.5)
    MIN_DISTANCE = 50.0  # 起点终点最小距离
    
    # 同步模式配置
    SYNCHRONOUS_MODE = True
    FIXED_DELTA_SECONDS = 0.05  # 20 FPS
    
    # 规划器配置
    SAMPLING_RESOLUTION = 2.0  # 全局规划采样分辨率
    TARGET_SPEED = 3.0  # km/h
    
    # 控制器参数
    LATERAL_CONTROL = {
        'K_P': 1.95,
        'K_I': 0.05,
        'K_D': 0.2,
        'dt': 0.05
    }
    
    LONGITUDINAL_CONTROL = {
        'K_P': 1.0,
        'K_I': 0.05,
        'K_D': 0.0,
        'dt': 0.05
    }
    
    MAX_THROTTLE = 0.75
    MAX_BRAKE = 0.3
    MAX_STEERING = 0.8
    LANE_OFFSET = 0.0
    
    # 可视化配置
    CAMERA_HEIGHT = 50  # 观察者相机高度
    CAMERA_PITCH = -90  # 观察者相机俯仰角
    DRAW_WAYPOINTS_INTERVAL = 10  # 每N个路点绘制一个
    VISUALIZATION_LIFETIME = 120.0  # 可视化持续时间(秒)
    
    # 运行配置
    MAX_STEPS = 20000  # 最大运行步数
    PRINT_INTERVAL = 1.0  # 状态打印间隔(秒)


# ========================================
# 连接和初始化函数
# ========================================
def connect_to_carla(config):
    """
    连接到CARLA服务器
    
    Args:
        config: NavigationConfig 配置对象
        
    Returns:
        client: CARLA客户端对象
    """
    print("正在连接CARLA服务器...")
    client = carla.Client(config.CARLA_HOST, config.CARLA_PORT)
    client.set_timeout(config.TIMEOUT)
    print(f"CARLA服务器版本: {client.get_server_version()}")
    return client


def setup_world(client, config):
    """
    设置世界和同步模式
    
    Args:
        client: CARLA客户端对象
        config: NavigationConfig 配置对象
        
    Returns:
        world: CARLA世界对象
        carla_map: CARLA地图对象
    """
    # 加载地图
    if config.MAP_NAME:
        print(f"加载地图 {config.MAP_NAME}...")
        client.load_world(config.MAP_NAME)
    
    world = client.get_world()
    carla_map = world.get_map()
    print(f"当前地图: {carla_map.name}")
    
    # 设置同步模式
    if config.SYNCHRONOUS_MODE:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = config.FIXED_DELTA_SECONDS
        world.apply_settings(settings)
        print(f"同步模式已启用 (FPS: {1.0/config.FIXED_DELTA_SECONDS:.1f})")
    
    return world, carla_map


def spawn_vehicle(world, carla_map, config):
    """
    生成车辆
    
    Args:
        world: CARLA世界对象
        carla_map: CARLA地图对象
        config: NavigationConfig 配置对象
        
    Returns:
        vehicle: 生成的车辆对象
    """
    print("正在生成车辆...")
    
    # 获取车辆蓝图
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter(config.VEHICLE_MODEL)[0]
    
    # 确定生成位置
    if config.USE_RANDOM_SPAWN:
        spawn_points = carla_map.get_spawn_points()
        if len(spawn_points) == 0:
            raise RuntimeError("错误：地图没有生成点！")
        start_transform = random.choice(spawn_points)
        print(f"随机选择生成点: {start_transform.location}")
    else:
        start_transform = carla.Transform(config.START_LOCATION, config.START_ROTATION)
        print(f"指定生成点: {start_transform.location}")
    
    # 生成车辆
    vehicle = world.spawn_actor(vehicle_bp, start_transform)
    print(f"车辆已生成: {vehicle.type_id}")
    
    # 让车辆稳定
    world.tick()
    time.sleep(0.5)
    
    return vehicle


def setup_spectator(world, vehicle, config):
    """
    设置观察者相机
    
    Args:
        world: CARLA世界对象
        vehicle: 车辆对象
        config: NavigationConfig 配置对象
        
    Returns:
        update_func: 更新相机位置的函数
    """
    spectator = world.get_spectator()
    
    def update_spectator():
        """更新观察者相机位置跟随车辆"""
        transform = vehicle.get_transform()
        spectator_transform = carla.Transform(
            transform.location + carla.Location(z=config.CAMERA_HEIGHT),
            carla.Rotation(pitch=config.CAMERA_PITCH)
        )
        spectator.set_transform(spectator_transform)
    
    update_spectator()
    print("观察者相机已设置")
    
    return update_spectator


def create_planners(vehicle, carla_map, config):
    """
    创建全局和局部路径规划器
    
    Args:
        vehicle: 车辆对象
        carla_map: CARLA地图对象
        config: NavigationConfig 配置对象
        
    Returns:
        global_planner: 全局路径规划器
        local_planner: 局部路径规划器
    """
    print("初始化路径规划器...")
    
    # 创建全局规划器
    global_planner = GlobalRoutePlanner(carla_map, config.SAMPLING_RESOLUTION)
    print("  ✓ 全局路径规划器已就绪")
    
    # 创建局部规划器
    # 构建局部规划器参数字典
    opt_dict = {
        'target_speed': config.TARGET_SPEED,                    # 目标速度 (km/h)
        'sampling_radius': config.SAMPLING_RESOLUTION,          # 采样半径：路点间距 (米)
        'lateral_control_dict': config.LATERAL_CONTROL,         # 横向控制参数：转向PID控制器
        'longitudinal_control_dict': config.LONGITUDINAL_CONTROL,  # 纵向控制参数：速度PID控制器
        'max_throttle': config.MAX_THROTTLE,                    # 最大油门：0.0(无油门) ~ 1.0(全油门)
        'max_brake': config.MAX_BRAKE,                          # 最大刹车：0.0(不刹车) ~ 1.0(急刹)
        'max_steering': config.MAX_STEERING,                    # 最大转向角：0.0(不转) ~ 1.0(最大转向)
        'offset': config.LANE_OFFSET                            # 车道偏移：0=车道中心, 正值向右, 负值向左 (米)
    }
    
    local_planner = LocalPlanner(vehicle, opt_dict=opt_dict, map_inst=carla_map)
    print("  ✓ 局部路径规划器已就绪")
    
    return global_planner, local_planner


def plan_route(vehicle, carla_map, global_planner, config):
    """
    规划从起点到终点的路径
    
    Args:
        vehicle: 车辆对象
        carla_map: CARLA地图对象
        global_planner: 全局路径规划器
        config: NavigationConfig 配置对象
        
    Returns:
        route: 路径列表 [(waypoint, RoadOption), ...]
        start_location: 起点位置
        end_location: 终点位置
    """
    print("\n开始路径规划...")
    
    # 确定起点
    start_location = vehicle.get_location()
    print(f"起点: (x={start_location.x:.1f}, y={start_location.y:.1f}, z={start_location.z:.1f})")
    
    # 确定终点
    if config.USE_RANDOM_SPAWN:
        spawn_points = carla_map.get_spawn_points()
        end_transform = random.choice(spawn_points)
        # 确保终点离起点足够远
        while start_location.distance(end_transform.location) < config.MIN_DISTANCE:
            end_transform = random.choice(spawn_points)
        end_location = end_transform.location
        print(f"随机选择终点: (x={end_location.x:.1f}, y={end_location.y:.1f}, z={end_location.z:.1f})")
    else:
        end_location = config.END_LOCATION
        print(f"指定终点: (x={end_location.x:.1f}, y={end_location.y:.1f}, z={end_location.z:.1f})")
    
    distance = start_location.distance(end_location)
    print(f"直线距离: {distance:.2f} 米")
    
    # 计算路径
    print("计算全局路径...")
    route = global_planner.trace_route(start_location, end_location)
    print(f"路径已计算，共 {len(route)} 个路点")
    
    # 分析路径动作
    action_counts = {}
    for waypoint, road_option in route:
        action_name = road_option.name
        action_counts[action_name] = action_counts.get(action_name, 0) + 1
    
    print("路径动作分布:")
    for action, count in sorted(action_counts.items()):
        print(f"  {action:15s}: {count:4d}")
    
    return route, start_location, end_location


def visualize_route(world, route, start_location, end_location, config):
    """
    在CARLA中可视化路径
    
    Args:
        world: CARLA世界对象
        route: 路径列表
        start_location: 起点位置
        end_location: 终点位置
        config: NavigationConfig 配置对象
    """
    print("绘制路径可视化...")
    
    # 绘制路径路点
    for i, (waypoint, road_option) in enumerate(route):
        if i % config.DRAW_WAYPOINTS_INTERVAL == 0:
            # 根据道路选项选择颜色
            if road_option == RoadOption.LEFT:
                color = carla.Color(r=0, g=0, b=255)  # 蓝色-左转
            elif road_option == RoadOption.RIGHT:
                color = carla.Color(r=255, g=255, b=0)  # 黄色-右转
            elif road_option in [RoadOption.CHANGELANELEFT, RoadOption.CHANGELANERIGHT]:
                color = carla.Color(r=255, g=0, b=255)  # 紫色-变道
            else:
                color = carla.Color(r=0, g=255, b=0)  # 绿色-直行
            
            world.debug.draw_string(
                waypoint.transform.location,
                'o',
                draw_shadow=False,
                color=color,
                life_time=config.VISUALIZATION_LIFETIME,
                persistent_lines=True
            )
    
    # 绘制起点
    world.debug.draw_string(
        start_location + carla.Location(z=2),
        'START',
        draw_shadow=False,
        color=carla.Color(r=0, g=255, b=0),
        life_time=config.VISUALIZATION_LIFETIME,
        persistent_lines=True
    )
    
    # 绘制终点
    world.debug.draw_string(
        end_location + carla.Location(z=2),
        'END',
        draw_shadow=False,
        color=carla.Color(r=255, g=0, b=0),
        life_time=config.VISUALIZATION_LIFETIME,
        persistent_lines=True
    )
    
    print(f"路径可视化完成 (显示 {config.VISUALIZATION_LIFETIME:.0f} 秒)")


def navigate(world, vehicle, local_planner, end_location, update_spectator, config):
    """
    执行自动驾驶导航
    
    Args:
        world: CARLA世界对象
        vehicle: 车辆对象
        local_planner: 局部路径规划器
        end_location: 终点位置
        update_spectator: 更新相机函数
        config: NavigationConfig 配置对象
        
    Returns:
        success: 是否成功到达目的地
    """
    print("\n开始自动驾驶导航...\n")
    print("按 Ctrl+C 可以中断导航\n")
    
    step_count = 0
    last_print_time = time.time()
    
    try:
        while True:
            # 更新世界
            world.tick()
            
            # 检查是否到达目的地
            if local_planner.done():
                print("\n✓ 已到达目的地！")
                return True
            
            # 执行一步局部规划
            control = local_planner.run_step(debug=False)
            vehicle.apply_control(control)
            
            # 更新观察者相机
            if step_count % 10 == 0:
                update_spectator()
            
            # 打印状态信息
            current_time = time.time()
            if current_time - last_print_time >= config.PRINT_INTERVAL:
                print_navigation_status(
                    step_count, vehicle, control, local_planner, 
                    end_location, config
                )
                last_print_time = current_time
            
            step_count += 1
            
            # 安全检查
            if step_count > config.MAX_STEPS:
                print(f"\n✗ 导航超时 (超过 {config.MAX_STEPS} 步)")
                return False
    
    except KeyboardInterrupt:
        print("\n\n✗ 用户中断导航")
        return False


def print_navigation_status(step_count, vehicle, control, local_planner, end_location, config):
    """
    打印导航状态信息
    
    Args:
        step_count: 当前步数
        vehicle: 车辆对象
        control: 控制指令
        local_planner: 局部路径规划器
        end_location: 终点位置
        config: NavigationConfig 配置对象
    """
    # 计算速度
    velocity = vehicle.get_velocity()
    speed_kmh = 3.6 * np.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    
    # 计算距离
    current_location = vehicle.get_location()
    distance_to_goal = current_location.distance(end_location)
    
    # 获取当前道路选项
    target_road_option = local_planner.target_road_option
    road_option_name = target_road_option.name if target_road_option else "UNKNOWN"
    
    # 获取剩余路点数
    remaining_waypoints = len(local_planner._waypoints_queue)
    
    # 打印状态
    print(f"步数: {step_count:5d} | "
          f"速度: {speed_kmh:5.1f} km/h | "
          f"油门: {control.throttle:.2f} | "
          f"刹车: {control.brake:.2f} | "
          f"转向: {control.steer:+.2f} | "
          f"动作: {road_option_name:15s} | "
          f"剩余路点: {remaining_waypoints:4d} | "
          f"距目标: {distance_to_goal:6.1f}m")


def cleanup(world, vehicle, config):
    """
    清理资源
    
    Args:
        world: CARLA世界对象
        vehicle: 车辆对象
        config: NavigationConfig 配置对象
    """
    print("\n正在清理资源...")
    
    # 停止车辆
    if vehicle is not None:
        vehicle.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0))
        world.tick()
        
        # 销毁车辆
        vehicle.destroy()
        print("  ✓ 车辆已销毁")
    
    # 恢复异步模式
    if config.SYNCHRONOUS_MODE:
        settings = world.get_settings()
        settings.synchronous_mode = False
        settings.fixed_delta_seconds = None
        world.apply_settings(settings)
        print("  ✓ 已恢复异步模式")


# ========================================
# 主函数
# ========================================
def main():
    """主函数 - 完整的导航流程"""
    config = NavigationConfig()
    
    client = None
    world = None
    vehicle = None
    
    try:
        # 1. 连接服务器
        client = connect_to_carla(config)
        
        # 2. 设置世界
        world, carla_map = setup_world(client, config)
        
        # 3. 生成车辆
        vehicle = spawn_vehicle(world, carla_map, config)
        
        # 4. 设置观察者相机
        update_spectator = setup_spectator(world, vehicle, config)
        
        # 5. 创建规划器
        global_planner, local_planner = create_planners(vehicle, carla_map, config)
        
        # 6. 规划路径
        route, start_location, end_location = plan_route(
            vehicle, carla_map, global_planner, config
        )
        
        # 7. 可视化路径
        visualize_route(world, route, start_location, end_location, config)
        
        # 8. 设置路径到局部规划器
        local_planner.set_global_plan(route, stop_waypoint_creation=True, clean_queue=True)
        print("全局路径已设置到局部规划器")
        
        # 9. 执行导航
        success = navigate(world, vehicle, local_planner, end_location, update_spectator, config)
        
        if success:
            print("\n🎉 导航任务成功完成！")
        else:
            print("\n⚠️  导航任务未完成")
    
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 10. 清理资源
        if world is not None and vehicle is not None:
            cleanup(world, vehicle, config)
        
        print("\n完成！")


# ========================================
# 简化版本：使用BasicAgent
# ========================================
def main_with_basic_agent():
    """使用BasicAgent的简化示例"""
    from agents.navigation.basic_agent import BasicAgent
    
    config = NavigationConfig()
    
    print("正在连接CARLA服务器...")
    client = carla.Client(config.CARLA_HOST, config.CARLA_PORT)
    client.set_timeout(config.TIMEOUT)
    
    world = client.get_world()
    carla_map = world.get_map()
    print(f"当前地图: {carla_map.name}")
    
    # 设置同步模式
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = config.FIXED_DELTA_SECONDS
    world.apply_settings(settings)
    
    # 生成车辆
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter(config.VEHICLE_MODEL)[0]
    spawn_points = carla_map.get_spawn_points()
    start_transform = random.choice(spawn_points)
    vehicle = world.spawn_actor(vehicle_bp, start_transform)
    world.tick()
    
    print("创建BasicAgent...")
    agent = BasicAgent(vehicle, target_speed=config.TARGET_SPEED)
    
    # 设置目的地
    if config.USE_RANDOM_SPAWN:
        destination = random.choice(spawn_points).location
    else:
        destination = config.END_LOCATION
    
    agent.set_destination(destination)
    
    print(f"从 {vehicle.get_location()} 导航到 {destination}")
    print("开始自动驾驶...\n")
    
    try:
        step = 0
        while not agent.done():
            world.tick()
            control = agent.run_step()
            vehicle.apply_control(control)
            
            if step % 20 == 0:
                velocity = vehicle.get_velocity()
                speed = 3.6 * np.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                dist = vehicle.get_location().distance(destination)
                print(f"步数: {step:5d} | 速度: {speed:5.1f} km/h | 距目标: {dist:6.1f}m")
            
            step += 1
        
        print("\n✓ 已到达目的地！")
    
    except KeyboardInterrupt:
        print("\n✗ 用户中断")
    
    finally:
        vehicle.destroy()
        settings.synchronous_mode = False
        world.apply_settings(settings)
        print("完成！")


# ========================================
# 程序入口
# ========================================
if __name__ == '__main__':
    # 运行完整示例（推荐）
    main()
    
    # 或运行简化版本
    # main_with_basic_agent()
