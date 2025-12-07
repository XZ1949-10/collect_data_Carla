#!/usr/bin/env python3

# Copyright (c) 2017 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB).
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>

"""
CARLA数据收集主脚本

本脚本用于在CARLA模拟器中收集自动驾驶训练数据。
它支持多种控制代理（人类、前进、车道跟随、命令跟随），
可以自动记录传感器数据、控制信号和车辆状态。

主要功能：
1. 连接CARLA服务器并加载场景
2. 使用指定的控制代理驾驶车辆
3. 记录传感器数据（相机图像等）
4. 添加噪声以增强数据多样性
5. 检测碰撞和超时，自动重置episode
"""

from __future__ import print_function

import os
import sys
import argparse
import logging
import random
import time

try:
    import numpy as np
except ImportError:
    raise RuntimeError('cannot import numpy, make sure numpy package is installed')

from carla.client import make_carla_client

from carla.tcp import TCPConnectionError
from carla_game.carla_game import CarlaGame
from carla.planner import Planner
from carla.agent import HumanAgent, ForwardAgent, CommandFollower, LaneFollower

import modules.data_writer as writer
from modules.noiser import Noiser
from modules.collision_checker import CollisionChecker

# ========== 窗口尺寸常量 ==========
WINDOW_WIDTH = 800  # 主窗口宽度
WINDOW_HEIGHT = 600  # 主窗口高度
MINI_WINDOW_WIDTH = 320  # 小窗口宽度（用于显示其他相机视角）
MINI_WINDOW_HEIGHT = 180  # 小窗口高度

# 车辆从空中落下所需的帧数
# 在CARLA中，车辆会从空中生成然后落到地面，这段时间的数据需要跳过
NUMBER_OF_FRAMES_CAR_FLIES = 25  # 乘以10得到实际毫秒数


def make_controlling_agent(args, town_name):
    """
    创建控制代理对象
    
    根据命令行参数选择并实例化相应的控制代理。
    
    Args:
        args: 命令行参数对象
        town_name: 当前城镇名称，某些代理需要地图信息
    
    Returns:
        控制代理对象实例
    
    可用的代理类型：
        ForwardAgent: 简单的前进代理，只会加速前进
        HumanAgent: 人类控制代理，通过键盘控制
        CommandFollower: 命令跟随代理，根据规划器的高级命令行驶
        LaneFollower: 车道跟随代理，沿车道行驶并避障
    
    Raises:
        ValueError: 如果选择了不存在的代理类型
    """
    if args.controlling_agent == "ForwardAgent":
        return ForwardAgent()
    elif args.controlling_agent == "HumanAgent":
        # TODO: 添加手柄等参数支持
        return HumanAgent()
    elif args.controlling_agent == "CommandFollower":
        return CommandFollower(town_name)
    elif args.controlling_agent == 'LaneFollower':
        return LaneFollower(town_name)
    else:
        raise ValueError("Selected Agent Does not exist")


def get_directions(measurements, target_transform, planner):
    """
    获取高级导航命令和路径点
    
    使用规划器计算从当前位置到目标位置的导航命令。
    路径点对应局部规划，即车辆需要跟随的近距离路径。
    
    Args:
        measurements: CARLA测量数据，包含玩家位置等信息
        target_transform: 目标位置的变换信息
        planner: 路径规划器对象
    
    Returns:
        directions: 高级导航命令（如直行、左转、右转等）
    """
    # 从测量数据中获取当前位置
    current_point = measurements.player_measurements.transform

    # 调用规划器获取下一个命令
    directions = planner.get_next_command(
        # 当前位置坐标 (x, y, z)
        (current_point.location.x,
         current_point.location.y, 0.22),
        # 当前朝向 (x, y, z)
        (current_point.orientation.x,
         current_point.orientation.y,
         current_point.orientation.z),
        # 目标位置坐标
        (target_transform.location.x, target_transform.location.y, 0.22),
        # 目标朝向
        (target_transform.orientation.x, target_transform.orientation.y,
         target_transform.orientation.z)
    )

    return directions


def new_episode(client, carla_settings, position, vehicle_pair, pedestrian_pair, set_of_weathers):
    """
    开始新的CARLA episode
    
    配置并启动一个新的模拟episode，包括设置车辆数量、行人数量和天气。
    
    Args:
        client: 已连接的CARLA客户端
        carla_settings: CARLA设置对象
        position: 玩家起始位置索引
        vehicle_pair: 车辆数量范围 (最小值, 最大值)
        pedestrian_pair: 行人数量范围 (最小值, 最大值)
        set_of_weathers: 可选天气列表
    
    Returns:
        tuple: 包含以下元素：
            - map_name: 地图名称
            - player_start_spots: 所有可用的起始点
            - weather: 选中的天气ID
            - number_of_vehicles: 实际车辆数量
            - number_of_pedestrians: 实际行人数量
            - SeedVehicles: 车辆随机种子
            - SeedPedestrians: 行人随机种子
    """
    # 每次episode使用不同的随机种子
    # 在指定范围内随机选择车辆和行人数量
    number_of_vehicles = random.randint(vehicle_pair[0], vehicle_pair[1])
    number_of_pedestrians = random.randint(pedestrian_pair[0], pedestrian_pair[1])
    # 随机选择天气
    weather = random.choice(set_of_weathers)
    
    # 更新CARLA设置
    carla_settings.set(
        NumberOfVehicles=number_of_vehicles,
        NumberOfPedestrians=number_of_pedestrians,
        WeatherId=weather
    )
    
    # 加载设置并获取场景信息
    scene = client.load_settings(carla_settings)
    # 在指定位置开始episode
    client.start_episode(position)

    return scene.map_name, scene.player_start_spots, weather, number_of_vehicles, number_of_pedestrians, \
           carla_settings.SeedVehicles, carla_settings.SeedPedestrians


def check_episode_has_noise(lat_noise_percent, long_noise_percent):
    """
    检查当前episode是否应该添加噪声
    
    根据配置的概率决定是否在当前episode中添加横向和纵向噪声。
    噪声用于增加数据多样性，帮助模型学习恢复控制。
    
    Args:
        lat_noise_percent: 横向噪声概率（0-100）
        long_noise_percent: 纵向噪声概率（0-100）
    
    Returns:
        tuple: (lat_noise, long_noise) 布尔值元组
    """
    lat_noise = False
    long_noise = False
    
    # 根据概率决定是否添加横向噪声
    if random.randint(0, 101) < lat_noise_percent:
        lat_noise = True

    # 根据概率决定是否添加纵向噪声
    if random.randint(0, 101) < long_noise_percent:
        long_noise = True

    return lat_noise, long_noise


def reach_timeout(current_time, timeout_period):
    """
    检查是否超时
    
    Args:
        current_time: 当前游戏时间（秒）
        timeout_period: 超时阈值（秒）
    
    Returns:
        bool: 如果超时返回True，否则返回False
    """
    if current_time > timeout_period:
        return True
    return False


def calculate_timeout(start_point, end_point, planner):
    """
    计算episode的超时时间
    
    根据起点到终点的路径距离计算合理的超时时间。
    假设平均速度为5km/h，并额外增加10秒缓冲。
    
    Args:
        start_point: 起始点变换信息
        end_point: 终点变换信息
        planner: 路径规划器
    
    Returns:
        float: 超时时间（秒）
    """
    # 获取最短路径距离（米）
    path_distance = planner.get_shortest_path_distance(
        [start_point.location.x, start_point.location.y, 0.22], 
        [start_point.orientation.x, start_point.orientation.y, 0.22], 
        [end_point.location.x, end_point.location.y, end_point.location.z], 
        [end_point.orientation.x, end_point.orientation.y, end_point.orientation.z])

    # 计算超时时间：(距离/1000转换为km) / 5km/h * 3600秒/小时 + 10秒缓冲
    return ((path_distance / 1000.0) / 5.0) * 3600.0 + 10.0


def reset_episode(client, carla_game, settings_module, show_render):
    """
    重置episode
    
    随机选择新的起点和终点，重新配置场景，并初始化游戏状态。
    
    Args:
        client: CARLA客户端
        carla_game: CarlaGame对象，用于渲染和游戏控制
        settings_module: 数据集配置模块
        show_render: 是否显示渲染窗口
    
    Returns:
        dict: episode特征字典，包含：
            - town_name: 城镇名称
            - player_target_transform: 目标位置变换
            - last_episode_time: episode开始时间
            - timeout: 超时时间
            - weather: 天气ID
            - number_of_vehicles: 车辆数量
            - number_of_pedestrians: 行人数量
            - seeds_vehicles: 车辆随机种子
            - seeds_pedestrians: 行人随机种子
    """
    # 从配置的位置列表中随机选择一个起点-终点对
    random_pose = random.choice(settings_module.POSITIONS)
    
    # 启动新episode并获取场景信息
    town_name, player_start_spots, weather, number_of_vehicles, number_of_pedestrians, \
        seeds_vehicles, seeds_pedestrians = new_episode(client,
                                                        settings_module.make_carla_settings(),
                                                        random_pose[0],  # 起点索引
                                                        settings_module.NumberOfVehicles,
                                                        settings_module.NumberOfPedestrians,
                                                        settings_module.set_of_weathers)

    # 初始化游戏界面，verbose模式下显示渲染窗口
    carla_game.initialize_game(town_name, render_mode=show_render)
    carla_game.start_timer()

    # 创建规划器用于计算超时时间
    planner = Planner(town_name)

    # 设置目标位置
    carla_game.set_objective(player_start_spots[random_pose[1]])

    # 获取目标位置的变换信息
    player_target_transform = player_start_spots[random_pose[1]]

    # 记录episode开始时间
    last_episode_time = time.time()

    # 计算超时时间
    timeout = calculate_timeout(player_start_spots[random_pose[0]],
                                player_target_transform, planner)
    
    # 构建episode特征字典
    episode_characteristics = {
        "town_name": town_name,
        "player_target_transform": player_target_transform,
        "last_episode_time": last_episode_time,
        "timeout": timeout,
        "weather": weather,
        "number_of_vehicles": number_of_vehicles,
        "number_of_pedestrians": number_of_pedestrians,
        "seeds_vehicles": seeds_vehicles,
        "seeds_pedestrians": seeds_pedestrians
    }

    return episode_characteristics


def suppress_logs(episode_number):
    """
    重定向日志输出到文件
    
    在大规模数据收集时，将标准输出和错误输出重定向到文件，
    避免控制台输出过多信息。
    
    Args:
        episode_number: 当前episode编号，用于生成唯一的日志文件名
    """
    # 创建日志输出目录
    if not os.path.exists('_output_logs'):
        os.mkdir('_output_logs')
    
    # 重定向标准输出
    sys.stdout = open(os.path.join('_output_logs',
                                   'collect_' + str(os.getpid()) + '_' + str(
                                       episode_number) + ".out"),
                      "a", buffering=1)
    
    # 重定向标准错误
    sys.stderr = open(os.path.join('_output_logs',
                                   'err_collect_' + str(os.getpid()) + '_' + str(
                                       episode_number) + ".out"),
                      "a", buffering=1)


def collect(client, args):
    """
    数据收集主循环
    
    这是数据收集的核心函数，负责：
    1. 初始化收集环境和代理
    2. 循环读取传感器数据
    3. 执行控制并记录数据
    4. 处理碰撞和超时情况
    
    Args:
        client: CARLA客户端对象
        args: 命令行参数对象，包含收集配置
    
    Returns:
        None
    """
    # ========== 加载数据集配置模块 ==========
    # 动态导入配置模块，配置文件名通过参数传入
    settings_module = __import__('dataset_configurations.' + (args.data_configuration_name),
                                 fromlist=['dataset_configurations'])

    # 大规模收集时重定向日志输出到文件
    if not args.verbose:
        suppress_logs(args.episode_number)

    # ========== 初始化游戏界面 ==========
    # CarlaGame用于可视化数据收集过程（调试模式下）
    carla_game = CarlaGame(False, args.debug, WINDOW_WIDTH, WINDOW_HEIGHT, MINI_WINDOW_WIDTH,
                           MINI_WINDOW_HEIGHT)

    # 初始化碰撞检测器
    collision_checker = CollisionChecker()

    # ========== 开始第一个episode ==========
    # 重置episode并获取所有相关信息
    episode_aspects = reset_episode(client, carla_game,
                                    settings_module, args.debug)
    
    # 创建路径规划器
    planner = Planner(episode_aspects["town_name"])
    
    # 根据参数创建控制代理
    controlling_agent = make_controlling_agent(args, episode_aspects["town_name"])

    # ========== 初始化噪声生成器 ==========
    # 纵向噪声器：影响油门控制，模拟加速/减速扰动
    # frequency=15: 噪声频率
    # intensity=10: 噪声强度
    # min_noise_time_amount=2.0: 最小噪声持续时间
    longitudinal_noiser = Noiser('Throttle', frequency=15, intensity=10, min_noise_time_amount=2.0)
    
    # 横向噪声器：影响转向控制，模拟方向盘抖动
    lateral_noiser = Noiser('Spike', frequency=25, intensity=4, min_noise_time_amount=0.5)

    # 检查当前episode是否需要添加噪声
    episode_lateral_noise, episode_longitudinal_noise = check_episode_has_noise(
        settings_module.lat_noise_percent,
        settings_module.long_noise_percent)

    # ========== 初始化数据写入器 ==========
    # 创建数据集保存目录
    writer.make_dataset_path(args.data_path)
    
    # 写入整个数据收集过程的元数据（配置信息）
    writer.add_metadata(args.data_path, settings_module)
    
    # 写入当前episode的元数据
    writer.add_episode_metadata(args.data_path, str(args.episode_number).zfill(5),
                                episode_aspects)

    # 初始化episode计数器  开始的起始数
    episode_number = args.episode_number  
    
    try:
        image_count = 0  # 当前episode的帧计数
        
        # 计算最大episode数
        maximun_episode = int(args.number_of_episodes) + int(args.episode_number)
        
        # ========== 主收集循环 ==========
        while carla_game.is_running() and episode_number < maximun_episode:

            # 从CARLA服务器读取测量数据和传感器数据
            measurements, sensor_data = client.read_data()

            # 运行控制代理的一步，获取控制命令和控制器状态
            control, controller_state = controlling_agent.run_step(measurements,
                                                       sensor_data,
                                                       [],  # 空列表，预留参数
                                                       episode_aspects['player_target_transform'])
            
            # 获取导航方向命令（直行、左转、右转等）
            directions = get_directions(measurements,
                                        episode_aspects['player_target_transform'], planner)

            # 将方向命令添加到控制器状态中，用于后续训练
            controller_state.update({'directions': directions})

            # ========== 添加噪声 ==========
            # 如果当前episode需要纵向噪声，则添加
            if episode_longitudinal_noise:
                control_noise, _, _ = longitudinal_noiser.compute_noise(control,
                                            measurements.player_measurements.forward_speed * 3.6)  # 转换为km/h
            else:
                control_noise = control

            # 如果当前episode需要横向噪声，则添加
            if episode_lateral_noise:
                control_noise_f, _, _ = lateral_noiser.compute_noise(control_noise,
                                            measurements.player_measurements.forward_speed * 3.6)
            else:
                control_noise_f = control_noise

            # ========== 调试模式渲染 ==========
            if args.debug:
                # 准备渲染所需的对象信息
                objects_to_render = controller_state.copy()
                objects_to_render['player_transform'] = measurements.player_measurements.transform
                objects_to_render['agents'] = measurements.non_player_agents
                objects_to_render["draw_pedestrians"] = args.draw_pedestrians
                objects_to_render["draw_vehicles"] = args.draw_vehicles
                objects_to_render["draw_traffic_lights"] = args.draw_traffic_lights
                # 注释以下两行可以显示路径点和路线
                objects_to_render['waypoints'] = None
                objects_to_render['route'] = None

                # 使用相机图像进行渲染
                carla_game.render(sensor_data['CameraRGB'], objects_to_render)

            # ========== 检查episode结束条件 ==========
            # episode结束条件：碰撞、超时、或到达重置区域
            episode_ended = collision_checker.test_collision(measurements.player_measurements) or \
                            reach_timeout(measurements.game_timestamp / 1000.0,
                                          episode_aspects["timeout"]) or \
                            carla_game.is_reset(measurements.player_measurements.transform.location)
            
            # episode成功条件：没有碰撞且没有超时
            episode_success = not (collision_checker.test_collision(
                                   measurements.player_measurements) or
                                   reach_timeout(measurements.game_timestamp / 1000.0,
                                                 episode_aspects["timeout"]))

            # ========== 处理episode结束 ==========
            if episode_ended:
                if episode_success:
                    # 成功完成，递增episode编号
                    episode_number += 1
                else:
                    # 失败的episode，删除已记录的数据
                    if not args.not_record:
                        writer.delete_episode(args.data_path, str(episode_number-1).zfill(5))

                # 为新episode重新检查是否需要噪声
                episode_lateral_noise, episode_longitudinal_noise = check_episode_has_noise(
                    settings_module.lat_noise_percent,
                    settings_module.long_noise_percent)

                # 重置episode
                episode_aspects = reset_episode(client, carla_game,
                                                settings_module, args.debug)

                # 写入新episode的元数据
                writer.add_episode_metadata(args.data_path, str(episode_number).zfill(5),
                                            episode_aspects)

                # 重置帧计数
                image_count = 0

            # ========== 记录数据 ==========
            # 跳过车辆从空中落下的帧，这些帧的数据无效
            if image_count >= NUMBER_OF_FRAMES_CAR_FLIES and not args.not_record:
                writer.add_data_point(measurements, control, control_noise_f, sensor_data,
                                      controller_state,
                                      args.data_path, str(episode_number).zfill(5),
                                      str(image_count - NUMBER_OF_FRAMES_CAR_FLIES),
                                      settings_module.sensors_frequency)
            
            # 发送控制命令到CARLA服务器
            client.send_control(control_noise_f)
            
            # 递增帧计数
            image_count += 1

    except TCPConnectionError as error:
        """
        连接错误处理
        删除当前未完成的episode数据，避免数据不完整
        """
        import traceback
        traceback.print_exc()
        if not args.not_record:
            writer.delete_episode(args.data_path, str(episode_number).zfill(5))
        raise error

    except KeyboardInterrupt:
        """
        用户中断处理（Ctrl+C）
        删除当前未完成的episode数据
        """
        import traceback
        traceback.print_exc()
        if not args.not_record:
            writer.delete_episode(args.data_path, str(episode_number).zfill(5))


def main():
    """
    数据收集主函数
    
    解析命令行参数，建立与CARLA服务器的连接，并启动数据收集。
    如果连接失败会自动重试。
    """
    # ========== 命令行参数定义 ==========
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    
    # 详细输出模式
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='verbose',
        help='打印调试信息')
    
    # CARLA服务器主机地址
    argparser.add_argument(
        '--host',
        metavar='H',
        default='localhost',
        help='CARLA服务器IP地址（默认: localhost）')
    
    # CARLA服务器端口
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='CARLA服务器TCP端口（默认: 2000）')
    
    # 数据保存路径
    argparser.add_argument(
        '-pt','--data-path',
        metavar='H',
        default='.',
        dest='data_path',
        help='数据保存路径')
    
    # 数据集配置文件名
    argparser.add_argument(
        '--data-configuration-name',
        metavar='H',
        default='coil_training_dataset_singlecamera',
        dest='data_configuration_name',
        help='数据集配置文件名（位于dataset_configurations目录下）')
    
    # 控制代理类型
    argparser.add_argument(
        '-c', '--controlling_agent',
        default='CommandFollower',
        help='主车辆使用的控制器类型。'
             '可选项: '
             'HumanAgent - 键盘控制; '
             'ForwardAgent - 简单前进代理; '
             'LaneFollower - 车道跟随并避障; '
             'CommandFollower - 根据规划器命令的车道跟随')
    
    # 调试模式
    argparser.add_argument(
        '-db', '--debug',
        action='store_true',
        help='启用调试屏幕模式，显示代理信息的渲染窗口')
    
    # 绘制行人
    argparser.add_argument(
        '-dp', '--draw-pedestrians',
        dest='draw_pedestrians',
        action='store_true',
        help='在调试屏幕上显示行人')
    
    # 绘制车辆
    argparser.add_argument(
        '-dv', '--draw-vehicles',
        dest='draw_vehicles',
        action='store_true',
        help='在调试屏幕上显示车辆点')
    
    # 绘制交通灯
    argparser.add_argument(
        '-dt', '--draw-traffic-lights',
        dest='draw_traffic_lights',
        action='store_true',
        help='在调试屏幕上显示交通灯点')
    
    # 不记录数据标志
    argparser.add_argument(
        '-nr', '--not-record',
        action='store_true',
        default=False,
        help='不记录数据的标志（用于测试）')
    
    # 起始episode编号
    argparser.add_argument(
        '-e', '--episode-number',
        metavar='E',
        dest='episode_number',
        default=0,
        type=int,
        help='开始记录的episode编号')
    
    # 要运行的episode数量
    argparser.add_argument(
        '-n', '--number-episodes',
        metavar='N',
        dest='number_of_episodes',
        default=999999999,
        help='要运行的episode数量，默认无限')

    # 解析参数
    args = argparser.parse_args()

    # 设置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    # ========== 主连接循环 ==========
    # 持续尝试连接CARLA服务器
    while True:
        try:
            # 创建CARLA客户端连接
            with make_carla_client(args.host, args.port) as client:
                # 开始数据收集
                collect(client, args)
                break  # 收集完成后退出

        except TCPConnectionError as error:
            # 连接失败，等待后重试
            logging.error(error)
            time.sleep(1)


if __name__ == '__main__':
    """
    脚本入口点
    
    捕获键盘中断以优雅退出
    """
    try:
        main()
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')
