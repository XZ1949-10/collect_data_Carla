#!/usr/bin/env python
# coding=utf-8
'''
作者: AI Assistant
日期: 2025-11-25
说明: NavigationPlanner 适配器
      使用 agents 模块的 GlobalRoutePlanner 替代原有的 NavigationPlanner
'''

import random
import numpy as np
import carla
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from agents.navigation.global_route_planner import GlobalRoutePlanner
from agents.navigation.local_planner import RoadOption


class NavigationPlannerAdapter:
    """
    NavigationPlanner 适配器类
    
    将 agents 模块的 GlobalRoutePlanner 适配为原有 NavigationPlanner 的接口
    保持与原代码的兼容性
    """
    
    def __init__(self, world, sampling_resolution=2.0):
        """
        初始化导航规划器
        
        参数:
            world: carla.World 实例
            sampling_resolution: 路径采样分辨率（米）
        """
        self._world = world
        self._map = world.get_map()
        self._sampling_resolution = sampling_resolution
        
        # 创建全局路径规划器
        self._global_planner = GlobalRoutePlanner(self._map, sampling_resolution)
        
        # 路线相关
        self._route = []  # 路线：[(waypoint, road_option), ...]
        self._current_waypoint_index = 0
        self._destination = None
        
        # 命令映射：RoadOption -> 训练数据命令编码
        self._road_option_to_command = {
            RoadOption.LEFT: 3,           # 左转
            RoadOption.RIGHT: 4,          # 右转
            RoadOption.STRAIGHT: 5,       # 直行
            RoadOption.LANEFOLLOW: 2,     # 跟车/车道保持
            RoadOption.CHANGELANELEFT: 2, # 变道左 -> 跟车
            RoadOption.CHANGELANERIGHT: 2,# 变道右 -> 跟车
            RoadOption.VOID: 2            # 未定义 -> 跟车
        }
        
        print(f"NavigationPlannerAdapter 初始化完成 (采样分辨率: {sampling_resolution}m)")
    
    def set_destination(self, vehicle, destination):
        """
        设置目的地并规划路线
        
        参数:
            vehicle: carla.Vehicle 实例
            destination: carla.Location 目的地位置
            
        返回:
            bool: 是否成功规划路线
        """
        try:
            # 获取起点和终点
            start_location = vehicle.get_location()
            
            # 使用全局规划器规划路线
            self._route = self._global_planner.trace_route(start_location, destination)
            
            if not self._route or len(self._route) == 0:
                print("⚠️ 无法规划路线：路线为空")
                return False
            
            self._destination = destination
            self._current_waypoint_index = 0
            
            # 计算路线总长度
            total_distance = self._calculate_route_length()
            
            print(f"✓ 路线规划成功：{len(self._route)} 个路点，总长度 {total_distance:.1f}m")
            return True
            
        except Exception as e:
            print(f"⚠️ 路线规划失败: {e}")
            return False
    
    def set_random_destination(self, vehicle):
        """
        设置随机目的地
        
        参数:
            vehicle: carla.Vehicle 实例
            
        返回:
            bool: 是否成功规划路线
        """
        spawn_points = self._map.get_spawn_points()
        
        if len(spawn_points) == 0:
            print("⚠️ 地图上没有可用的生成点")
            return False
        
        # 随机选择一个目的地（避免选择当前位置附近）
        current_location = vehicle.get_location()
        
        # 过滤掉距离太近的点（小于50米）
        valid_destinations = [
            sp.location for sp in spawn_points
            if current_location.distance(sp.location) > 50.0
        ]
        
        if not valid_destinations:
            # 如果所有点都太近，就使用所有点
            valid_destinations = [sp.location for sp in spawn_points]
        
        destination = random.choice(valid_destinations)
        
        return self.set_destination(vehicle, destination)
    
    def get_navigation_command(self, vehicle):
        """
        获取当前导航命令
        
        参数:
            vehicle: carla.Vehicle 实例
            
        返回:
            int: 命令编码 (2=跟车, 3=左转, 4=右转, 5=直行)
        """
        if not self._route or len(self._route) == 0:
            return 2  # 默认返回跟车命令
        
        # 更新当前路点索引
        self._update_current_waypoint(vehicle)
        
        # 获取当前路点的道路选项
        if self._current_waypoint_index < len(self._route):
            _, road_option = self._route[self._current_waypoint_index]
            command = self._road_option_to_command.get(road_option, 2)
            return command
        
        return 2  # 默认返回跟车命令
    
    def get_route_info(self, vehicle):
        """
        获取路线信息
        
        参数:
            vehicle: carla.Vehicle 实例
            
        返回:
            dict: 包含路线信息的字典
        """
        if not self._route or len(self._route) == 0:
            return {
                'current_command': 2,
                'progress': 0.0,
                'remaining_distance': 0.0,
                'total_distance': 0.0
            }
        
        # 更新当前路点索引
        self._update_current_waypoint(vehicle)
        
        # 计算进度
        current_location = vehicle.get_location()
        
        # 计算已行驶距离
        traveled_distance = 0.0
        for i in range(self._current_waypoint_index):
            if i + 1 < len(self._route):
                wp1 = self._route[i][0].transform.location
                wp2 = self._route[i + 1][0].transform.location
                traveled_distance += wp1.distance(wp2)
        
        # 加上到当前路点的距离
        if self._current_waypoint_index < len(self._route):
            current_waypoint = self._route[self._current_waypoint_index][0]
            traveled_distance += current_location.distance(current_waypoint.transform.location)
        
        # 计算剩余距离
        remaining_distance = 0.0
        for i in range(self._current_waypoint_index, len(self._route) - 1):
            wp1 = self._route[i][0].transform.location
            wp2 = self._route[i + 1][0].transform.location
            remaining_distance += wp1.distance(wp2)
        
        # 总距离
        total_distance = traveled_distance + remaining_distance
        
        # 进度百分比
        progress = (traveled_distance / total_distance * 100.0) if total_distance > 0 else 0.0
        
        # 当前命令
        current_command = self.get_navigation_command(vehicle)
        
        return {
            'current_command': current_command,
            'progress': progress,
            'remaining_distance': remaining_distance,
            'total_distance': total_distance
        }
    
    def is_route_completed(self, vehicle, threshold=5.0):
        """
        检查是否到达目的地
        
        参数:
            vehicle: carla.Vehicle 实例
            threshold: 距离阈值（米）
            
        返回:
            bool: 是否到达目的地
        """
        if not self._route or len(self._route) == 0:
            return True
        
        if self._destination is None:
            return True
        
        current_location = vehicle.get_location()
        distance_to_destination = current_location.distance(self._destination)
        
        return distance_to_destination < threshold
    
    def _update_current_waypoint(self, vehicle):
        """
        更新当前路点索引（找到最近的路点）
        
        参数:
            vehicle: carla.Vehicle 实例
        """
        if not self._route or len(self._route) == 0:
            return
        
        current_location = vehicle.get_location()
        
        # 从当前索引开始向前查找最近的路点
        min_distance = float('inf')
        best_index = self._current_waypoint_index
        
        # 搜索范围：当前索引 到 当前索引+20（避免全局搜索）
        search_start = self._current_waypoint_index
        search_end = min(self._current_waypoint_index + 20, len(self._route))
        
        for i in range(search_start, search_end):
            waypoint = self._route[i][0]
            distance = current_location.distance(waypoint.transform.location)
            
            if distance < min_distance:
                min_distance = distance
                best_index = i
        
        self._current_waypoint_index = best_index
    
    def _calculate_route_length(self):
        """
        计算路线总长度
        
        返回:
            float: 路线长度（米）
        """
        if not self._route or len(self._route) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(len(self._route) - 1):
            wp1 = self._route[i][0].transform.location
            wp2 = self._route[i + 1][0].transform.location
            total_length += wp1.distance(wp2)
        
        return total_length
