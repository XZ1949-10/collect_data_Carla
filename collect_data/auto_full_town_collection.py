#!/usr/bin/env python
# coding=utf-8
'''
作者: AI Assistant
日期: 2025-12-01
说明: 全自动Town01场景数据收集器
      自动遍历所有生成点组合，收集完整的Town01场景数据
      无需人工干预，智能选择路线并自动保存
'''

import os
import sys
import time
import random
import numpy as np
import json
import cv2
from datetime import datetime

# 导入基类
from base_collector import BaseDataCollector, AGENTS_AVAILABLE

import carla

# 导入agents模块
try:
    from agents.navigation.global_route_planner import GlobalRoutePlanner
    from agents.navigation.local_planner import RoadOption
except ImportError:
    pass


class AutoFullTownCollector(BaseDataCollector):
    """全自动Town01数据收集器"""
    
    def __init__(self, host='localhost', port=2000, town='Town01',
                 ignore_traffic_lights=True, ignore_signs=True,
                 ignore_vehicles_percentage=80, target_speed=10.0,
                 simulation_fps=20, spawn_npc_vehicles=False, num_npc_vehicles=0,
                 spawn_npc_walkers=False, num_npc_walkers=0, weather_config=None):
        
        super().__init__(host, port, town, ignore_traffic_lights, ignore_signs,
                        ignore_vehicles_percentage, target_speed, simulation_fps)
        
        # NPC配置
        self.spawn_npc_vehicles = spawn_npc_vehicles
        self.num_npc_vehicles = num_npc_vehicles
        self.spawn_npc_walkers = spawn_npc_walkers
        self.num_npc_walkers = num_npc_walkers
        self.weather_config = weather_config or {}
        
        # NPC列表
        self.npc_vehicles = []
        self.npc_walkers = []
        self.walker_controllers = []
        
        # 路线规划
        self.spawn_points = []
        self.route_planner = None
        
        # 收集策略
        self.min_distance = 50.0
        self.max_distance = 500.0
        self.frames_per_route = 1000
        self.target_routes = 200
        self.overlap_threshold = 0.5
        
        # 统计
        self.total_routes_attempted = 0
        self.total_routes_completed = 0
        self.total_frames_collected = 0
        self.failed_routes = []
        
        self.route_generation_strategy = 'smart'
        
        # 内部收集器引用
        self._inner_collector = None
        
        # 噪声配置（会传递给内部收集器）
        self.noise_enabled = False
        self.lateral_noise_enabled = True
        self.longitudinal_noise_enabled = False
        
        # 噪声参数（默认值与 auto_collection_config.json 保持一致）
        self.lateral_frequency = 25
        self.lateral_intensity = 10
        self.lateral_min_time = 1.0
        self.longitudinal_frequency = 15
        self.longitudinal_intensity = 10
        self.longitudinal_min_time = 2.0
    
    def connect(self):
        """连接到CARLA服务器（扩展版）"""
        print("\n" + "="*70)
        print("🚗 全自动Town01数据收集器")
        print("="*70)
        print(f"正在连接到CARLA服务器 {self.host}:{self.port}...")
        
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(10.0)
        
        self.world = self.client.get_world()
        current_map_name = self.world.get_map().name.split('/')[-1]
        
        if current_map_name != self.town:
            print(f"正在加载地图 {self.town}...")
            self.world = self.client.load_world(self.town)
        else:
            print(f"✅ 已连接到地图 {self.town}")
        
        self.blueprint_library = self.world.get_blueprint_library()
        self.spawn_points = self.world.get_map().get_spawn_points()
        print(f"✅ 成功连接！共找到 {len(self.spawn_points)} 个生成点")
        
        self._print_config()
        self._set_weather()
        
        if self.spawn_npc_vehicles and self.num_npc_vehicles > 0:
            self._spawn_npc_vehicles()
        if self.spawn_npc_walkers and self.num_npc_walkers > 0:
            self._spawn_npc_walkers()
        
        if AGENTS_AVAILABLE:
            try:
                self.route_planner = GlobalRoutePlanner(self.world.get_map(), sampling_resolution=2.0)
                print("✅ 路径规划器初始化成功")
            except Exception as e:
                print(f"⚠️  路径规划器初始化失败: {e}")
        print()
    
    def _print_config(self):
        """打印配置信息"""
        print(f"\n📋 配置信息:")
        print(f"  • 忽略红绿灯: {'✅' if self.ignore_traffic_lights else '❌'}")
        print(f"  • 忽略停车标志: {'✅' if self.ignore_signs else '❌'}")
        print(f"  • 目标速度: {self.target_speed:.1f} km/h")
        print(f"  • 模拟帧率: {self.simulation_fps} FPS")
        if self.spawn_npc_vehicles:
            print(f"  • NPC车辆: {self.num_npc_vehicles}")
        if self.spawn_npc_walkers:
            print(f"  • NPC行人: {self.num_npc_walkers}")
    
    def _set_weather(self):
        """设置天气"""
        if not self.weather_config:
            return
        
        preset = self.weather_config.get('preset')
        weather_presets = {
            # 正午天气
            'ClearNoon': carla.WeatherParameters.ClearNoon,
            'CloudyNoon': carla.WeatherParameters.CloudyNoon,
            'WetNoon': carla.WeatherParameters.WetNoon,
            'WetCloudyNoon': carla.WeatherParameters.WetCloudyNoon,
            'SoftRainNoon': carla.WeatherParameters.SoftRainNoon,
            'MidRainyNoon': carla.WeatherParameters.MidRainyNoon,
            'HardRainNoon': carla.WeatherParameters.HardRainNoon,
            # 日落天气
            'ClearSunset': carla.WeatherParameters.ClearSunset,
            'CloudySunset': carla.WeatherParameters.CloudySunset,
            'WetSunset': carla.WeatherParameters.WetSunset,
            'WetCloudySunset': carla.WeatherParameters.WetCloudySunset,
            'SoftRainSunset': carla.WeatherParameters.SoftRainSunset,
            'MidRainSunset': carla.WeatherParameters.MidRainSunset,
            'HardRainSunset': carla.WeatherParameters.HardRainSunset,
            # 夜晚天气
            'ClearNight': carla.WeatherParameters.ClearNight,
            'CloudyNight': carla.WeatherParameters.CloudyNight,
            'WetNight': carla.WeatherParameters.WetNight,
            'WetCloudyNight': carla.WeatherParameters.WetCloudyNight,
            'SoftRainNight': carla.WeatherParameters.SoftRainNight,
            'MidRainyNight': carla.WeatherParameters.MidRainyNight,
            'HardRainNight': carla.WeatherParameters.HardRainNight,
            # 特殊天气
            'DustStorm': carla.WeatherParameters.DustStorm,
        }
        
        if preset and preset in weather_presets:
            self.world.set_weather(weather_presets[preset])
            print(f"  天气: {preset}")
        elif preset:
            print(f"  ⚠️ 未知天气预设: {preset}，使用默认天气")
    
    def _spawn_npc_vehicles(self):
        """生成NPC车辆"""
        print(f"\n🚗 正在生成 {self.num_npc_vehicles} 辆NPC车辆...")
        
        blueprints = [x for x in self.blueprint_library.filter('vehicle.*')
                      if int(x.get_attribute('number_of_wheels')) == 4]
        spawn_points = self.world.get_map().get_spawn_points()
        random.shuffle(spawn_points)
        
        for i in range(min(self.num_npc_vehicles, len(spawn_points))):
            bp = random.choice(blueprints)
            if bp.has_attribute('color'):
                bp.set_attribute('color', random.choice(bp.get_attribute('color').recommended_values))
            
            npc = self.world.try_spawn_actor(bp, spawn_points[i])
            if npc:
                npc.set_autopilot(True)
                self.npc_vehicles.append(npc)
        
        print(f"✅ 成功生成 {len(self.npc_vehicles)} 辆NPC车辆")
    
    def _spawn_npc_walkers(self):
        """生成NPC行人"""
        print(f"\n🚶 正在生成 {self.num_npc_walkers} 个NPC行人...")
        
        walker_bps = self.blueprint_library.filter('walker.pedestrian.*')
        spawn_points = []
        
        for _ in range(self.num_npc_walkers):
            loc = self.world.get_random_location_from_navigation()
            if loc:
                spawn_points.append(carla.Transform(location=loc))
        
        batch = [carla.command.SpawnActor(random.choice(walker_bps), sp) for sp in spawn_points]
        results = self.client.apply_batch_sync(batch, True)
        walker_ids = [r.actor_id for r in results if not r.error]
        
        controller_bp = self.blueprint_library.find('controller.ai.walker')
        batch = [carla.command.SpawnActor(controller_bp, carla.Transform(), wid) for wid in walker_ids]
        results = self.client.apply_batch_sync(batch, True)
        self.walker_controllers = [r.actor_id for r in results if not r.error]
        
        self.world.tick()
        for ctrl in self.world.get_actors(self.walker_controllers):
            ctrl.start()
            ctrl.go_to_location(self.world.get_random_location_from_navigation())
            ctrl.set_max_speed(1.0 + random.random())
        
        self.npc_walkers = list(self.world.get_actors(walker_ids))
        print(f"✅ 成功生成 {len(self.npc_walkers)} 个NPC行人")
    
    def _cleanup_npcs(self):
        """清理NPC"""
        for ctrl_id in self.walker_controllers:
            try:
                ctrl = self.world.get_actor(ctrl_id)
                if ctrl:
                    ctrl.stop()
                    ctrl.destroy()
            except:
                pass
        
        for walker in self.npc_walkers:
            try:
                walker.destroy()
            except:
                pass
        
        for vehicle in self.npc_vehicles:
            try:
                vehicle.destroy()
            except:
                pass
        
        self.npc_vehicles = []
        self.npc_walkers = []
        self.walker_controllers = []
    
    def generate_route_pairs(self):
        """生成路线对"""
        print("\n" + "="*70)
        print("🛣️ 生成路线对")
        print("="*70)
        
        if self.route_generation_strategy == 'smart':
            route_pairs = self._generate_smart_routes()
        else:
            route_pairs = self._generate_exhaustive_routes()
        
        if route_pairs:
            self._print_route_statistics(route_pairs)
        
        return route_pairs
    
    def _generate_smart_routes(self):
        """智能路线生成"""
        print(f"策略: 🧠 智能选择")
        
        if not AGENTS_AVAILABLE or self.route_planner is None:
            return self._generate_basic_routes()
        
        candidates = self._analyze_candidate_routes()
        if not candidates:
            return []
        
        selected = self._select_balanced_routes(candidates)
        return self._deduplicate_routes(selected)
    
    def _analyze_candidate_routes(self):
        """分析候选路线（优化版：添加进度显示和采样）"""
        print("\n🔍 分析候选路线...")
        
        candidates = []
        command_map = {'LANEFOLLOW': 2, 'LEFT': 3, 'RIGHT': 4, 'STRAIGHT': 5,
                       'CHANGELANELEFT': 2, 'CHANGELANERIGHT': 2}
        
        num_spawns = len(self.spawn_points)
        total_pairs = num_spawns * (num_spawns - 1)
        
        # 如果组合太多，使用采样策略
        max_candidates_to_check = 5000  # 最多检查5000条路线
        use_sampling = total_pairs > max_candidates_to_check
        
        if use_sampling:
            print(f"  ⚡ 组合数过多 ({total_pairs})，使用采样策略...")
            # 随机采样起点-终点对
            all_pairs = [(i, j) for i in range(num_spawns) for j in range(num_spawns) if i != j]
            random.shuffle(all_pairs)
            pairs_to_check = all_pairs[:max_candidates_to_check]
        else:
            pairs_to_check = [(i, j) for i in range(num_spawns) for j in range(num_spawns) if i != j]
        
        checked = 0
        last_progress = 0
        
        for start_idx, end_idx in pairs_to_check:
            checked += 1
            
            # 每10%显示进度
            progress = int(checked / len(pairs_to_check) * 100)
            if progress >= last_progress + 10:
                print(f"  📊 进度: {progress}% ({checked}/{len(pairs_to_check)}), 已找到 {len(candidates)} 条")
                last_progress = progress
            
            start_loc = self.spawn_points[start_idx].location
            end_loc = self.spawn_points[end_idx].location
            distance = self._calculate_distance(start_loc, end_loc)
            
            if distance < self.min_distance * 0.5 or distance > self.max_distance * 1.5:
                continue
            
            try:
                route = self.route_planner.trace_route(start_loc, end_loc)
                if not route or len(route) < 2:
                    continue
                
                commands = {2: 0, 3: 0, 4: 0, 5: 0}
                waypoints = []
                route_distance = 0.0
                prev_cmd = None
                
                for i, (wp, road_option) in enumerate(route):
                    if i > 0:
                        route_distance += wp.transform.location.distance(route[i-1][0].transform.location)
                    waypoints.append((wp.transform.location.x, wp.transform.location.y))
                    
                    cmd_name = road_option.name if hasattr(road_option, 'name') else str(road_option)
                    cmd = command_map.get(cmd_name, 2)
                    if cmd != prev_cmd:
                        commands[cmd] += 1
                        prev_cmd = cmd
                
                if route_distance < self.min_distance or route_distance > self.max_distance:
                    continue
                
                candidates.append({
                    'start_idx': start_idx, 'end_idx': end_idx,
                    'distance': distance, 'route_distance': route_distance,
                    'commands': commands, 'waypoints': waypoints,
                    'turn_count': commands[3] + commands[4]
                })
                
                # 如果已经找到足够多的候选路线，提前结束
                # 注意：target_routes=0 表示不限制，不应提前退出
                if self.target_routes > 0 and len(candidates) >= self.target_routes * 3:
                    print(f"  ⚡ 已找到足够候选路线，提前结束分析")
                    break
                    
            except:
                pass
        
        print(f"  ✅ 找到 {len(candidates)} 条候选路线")
        return candidates
    
    def _select_balanced_routes(self, candidates):
        """命令平衡选择"""
        total_commands = {2: 0, 3: 0, 4: 0, 5: 0}
        for c in candidates:
            for cmd, count in c['commands'].items():
                total_commands[cmd] += count
        
        total = sum(total_commands.values()) or 1
        scarcity = {cmd: 1.0 - (count / total) for cmd, count in total_commands.items()}
        
        for c in candidates:
            c['priority'] = sum(count * scarcity[cmd] * (3 if cmd in [3, 4] else 1)
                               for cmd, count in c['commands'].items())
        
        candidates.sort(key=lambda x: x['priority'], reverse=True)
        
        selected = []
        used_starts = {}
        max_per_start = max(3, self.target_routes // len(self.spawn_points) + 1)
        
        for c in candidates:
            if used_starts.get(c['start_idx'], 0) < max_per_start:
                selected.append(c)
                used_starts[c['start_idx']] = used_starts.get(c['start_idx'], 0) + 1
                # 注意：target_routes=0 表示不限制，选择所有候选路线
                if self.target_routes > 0 and len(selected) >= self.target_routes:
                    break
        
        return selected
    
    def _deduplicate_routes(self, routes):
        """路径去重"""
        if len(routes) <= 1:
            return [(r['start_idx'], r['end_idx'], r.get('route_distance', r['distance'])) for r in routes]
        
        routes.sort(key=lambda x: (-x.get('turn_count', 0), -x.get('priority', 0)))
        
        deduplicated = []
        for route in routes:
            is_overlapping = False
            route_wps = route.get('waypoints', [])
            
            if route_wps:
                for selected in deduplicated:
                    sel_wps = selected.get('waypoints', [])
                    if sel_wps and self._calculate_overlap(route_wps, sel_wps) > self.overlap_threshold:
                        is_overlapping = True
                        break
            
            if not is_overlapping:
                deduplicated.append(route)
        
        result = [(r['start_idx'], r['end_idx'], r.get('route_distance', r['distance'])) for r in deduplicated]
        random.shuffle(result)
        return result
    
    def _calculate_overlap(self, wps1, wps2, grid_size=10.0):
        """计算路径重叠度"""
        def to_grid(wps):
            return set((int(x / grid_size), int(y / grid_size)) for x, y in wps)
        
        g1, g2 = to_grid(wps1), to_grid(wps2)
        if not g1 or not g2:
            return 0.0
        return len(g1 & g2) / len(g1 | g2)
    
    def _generate_basic_routes(self):
        """基础路线生成"""
        route_pairs = []
        for start_idx, sp in enumerate(self.spawn_points):
            valid_ends = []
            for end_idx, ep in enumerate(self.spawn_points):
                if start_idx != end_idx:
                    d = self._calculate_distance(sp.location, ep.location)
                    if self.min_distance <= d <= self.max_distance:
                        valid_ends.append((end_idx, d))
            
            if valid_ends:
                valid_ends.sort(key=lambda x: x[1])
                for idx in [0, len(valid_ends)//2, len(valid_ends)-1]:
                    if idx < len(valid_ends):
                        route_pairs.append((start_idx, valid_ends[idx][0], valid_ends[idx][1]))
        
        random.shuffle(route_pairs)
        return route_pairs
    
    def _generate_exhaustive_routes(self):
        """穷举路线生成 - 生成所有满足距离条件的起点-终点组合"""
        print(f"策略: 📋 穷举模式")
        
        route_pairs = []
        num_spawns = len(self.spawn_points)
        
        print(f"  正在分析 {num_spawns * (num_spawns - 1)} 个起点-终点组合...")
        
        for start_idx, sp in enumerate(self.spawn_points):
            for end_idx, ep in enumerate(self.spawn_points):
                if start_idx == end_idx:
                    continue
                
                # 计算直线距离作为初步筛选
                d = self._calculate_distance(sp.location, ep.location)
                if self.min_distance <= d <= self.max_distance:
                    # 如果有路径规划器，验证路线可达性并获取实际距离
                    if AGENTS_AVAILABLE and self.route_planner is not None:
                        try:
                            route = self.route_planner.trace_route(sp.location, ep.location)
                            if route and len(route) >= 2:
                                # 计算实际路径距离
                                route_distance = sum(
                                    route[i][0].transform.location.distance(route[i-1][0].transform.location)
                                    for i in range(1, len(route))
                                )
                                if self.min_distance <= route_distance <= self.max_distance:
                                    route_pairs.append((start_idx, end_idx, route_distance))
                        except:
                            # 规划失败，使用直线距离
                            route_pairs.append((start_idx, end_idx, d))
                    else:
                        route_pairs.append((start_idx, end_idx, d))
            
            # 显示进度
            if (start_idx + 1) % 50 == 0:
                print(f"  进度: {start_idx + 1}/{num_spawns}, 已找到 {len(route_pairs)} 条路线")
        
        print(f"  ✅ 穷举完成，共找到 {len(route_pairs)} 条有效路线")
        
        # 如果设置了目标路线数，随机选择
        if self.target_routes > 0 and len(route_pairs) > self.target_routes:
            random.shuffle(route_pairs)
            route_pairs = route_pairs[:self.target_routes]
            print(f"  📊 已随机选择 {self.target_routes} 条路线")
        else:
            random.shuffle(route_pairs)
        
        return route_pairs
    
    def _calculate_distance(self, loc1, loc2):
        """计算两点距离"""
        return np.sqrt((loc2.x - loc1.x)**2 + (loc2.y - loc1.y)**2)
    
    def _print_route_statistics(self, route_pairs):
        """打印路线统计"""
        distances = [d for _, _, d in route_pairs]
        print(f"\n📊 路线统计:")
        print(f"  • 总路线数: {len(route_pairs)}")
        print(f"  • 平均距离: {np.mean(distances):.1f}m")
        print(f"  • 预计耗时: {len(route_pairs) * 2:.0f}分钟")

    def collect_route_data(self, start_idx, end_idx, save_path):
        """收集单条路线数据"""
        print(f"\n{'='*70}")
        print(f"📊 收集路线: {start_idx} → {end_idx}")
        print(f"{'='*70}")
        
        try:
            # 创建内部收集器
            from command_based_data_collection import CommandBasedDataCollector
            self._inner_collector = CommandBasedDataCollector(
                host=self.host, port=self.port, town=self.town,
                ignore_traffic_lights=self.ignore_traffic_lights,
                ignore_signs=self.ignore_signs,
                ignore_vehicles_percentage=self.ignore_vehicles_percentage,
                target_speed=self.target_speed,
                simulation_fps=self.simulation_fps
            )
            
            # 复用连接
            self._inner_collector.client = self.client
            self._inner_collector.world = self.world
            self._inner_collector.blueprint_library = self.blueprint_library
            
            # 设置同步模式
            settings = self.world.get_settings()
            if not settings.synchronous_mode:
                settings.synchronous_mode = True
                settings.fixed_delta_seconds = 1.0 / self.simulation_fps
                self.world.apply_settings(settings)
            
            if not self._inner_collector.spawn_vehicle(start_idx, end_idx):
                return False
            
            self._inner_collector.setup_camera()
            time.sleep(1.0)
            
            # 配置噪声（从自身配置传递到内部收集器，包括参数）
            self._inner_collector.configure_noise(
                enabled=self.noise_enabled,
                lateral_enabled=self.lateral_noise_enabled,
                longitudinal_enabled=self.longitudinal_noise_enabled,
                lateral_frequency=self.lateral_frequency,
                lateral_intensity=self.lateral_intensity,
                lateral_min_time=self.lateral_min_time,
                longitudinal_frequency=self.longitudinal_frequency,
                longitudinal_intensity=self.longitudinal_intensity,
                longitudinal_min_time=self.longitudinal_min_time
            )
            
            success = self._auto_collect(save_path)
            return success
            
        except Exception as e:
            print(f"❌ 收集出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._cleanup_inner_collector()
    
    def _cleanup_inner_collector(self):
        """清理内部收集器"""
        if self._inner_collector:
            try:
                if self._inner_collector.camera:
                    self._inner_collector.camera.stop()
                    self._inner_collector.camera.destroy()
            except:
                pass
            try:
                if self._inner_collector.vehicle:
                    self._inner_collector.vehicle.destroy()
            except:
                pass
            self._inner_collector = None
    
    def _auto_collect(self, save_path):
        """自动收集数据"""
        os.makedirs(save_path, exist_ok=True)
        
        self._inner_collector.enable_visualization = True
        self._inner_collector.wait_for_first_frame()
        
        collected_frames = 0
        segment_data = {'rgb': [], 'targets': []}
        segment_count = 0
        segment_start_cmd = None  # 记录segment开始时的command
        
        try:
            while collected_frames < self.frames_per_route:
                self._inner_collector.step_simulation()
                
                if self._inner_collector._is_route_completed():
                    print(f"\n🎯 已到达目的地！")
                    break
                
                if len(self._inner_collector.image_buffer) == 0:
                    continue
                
                current_image = self._inner_collector.image_buffer[-1].copy()
                speed_kmh = self._inner_collector._get_vehicle_speed()
                current_cmd = self._inner_collector._get_navigation_command()
                
                if current_image.mean() < 5 or speed_kmh > 150:
                    continue
                
                targets = self._inner_collector._build_targets(speed_kmh, current_cmd)
                
                # 记录segment开始时的command（用于文件命名）
                if segment_count == 0:
                    segment_start_cmd = current_cmd
                
                segment_data['rgb'].append(current_image)
                segment_data['targets'].append(targets)
                segment_count += 1
                collected_frames += 1
                
                if self._inner_collector.enable_visualization:
                    self._inner_collector.segment_count = segment_count
                    self._inner_collector._visualize_frame(
                        current_image, speed_kmh, current_cmd,
                        collected_frames, self.frames_per_route, is_collecting=True
                    )
                
                # 每200帧保存，使用segment开始时的command
                if segment_count >= 200:
                    self._save_segment_auto(segment_data, save_path, segment_start_cmd)
                    segment_data = {'rgb': [], 'targets': []}
                    segment_count = 0
                    segment_start_cmd = None
                
                if collected_frames % 100 == 0:
                    print(f"  [收集中] 帧数: {collected_frames}/{self.frames_per_route}")
            
            # 保存剩余数据，使用segment开始时的command
            if segment_count > 0:
                self._save_segment_auto(segment_data, save_path, segment_start_cmd if segment_start_cmd else current_cmd)
            
            print(f"✅ 路线完成！帧数: {collected_frames}")
            self.total_frames_collected += collected_frames
            return True
            
        except Exception as e:
            print(f"❌ 自动收集出错: {e}")
            return False
        finally:
            cv2.destroyAllWindows()
    
    def _save_segment_auto(self, segment_data, save_path, command):
        """自动保存数据段"""
        if len(segment_data['rgb']) == 0:
            return
        
        self._inner_collector._save_data_to_h5(
            segment_data['rgb'], segment_data['targets'],
            save_path, command
        )
    
    def validate_route(self, start_idx, end_idx):
        """验证路线可行性"""
        if not AGENTS_AVAILABLE or self.route_planner is None:
            return True, None, 0.0
        
        try:
            route = self.route_planner.trace_route(
                self.spawn_points[start_idx].location,
                self.spawn_points[end_idx].location
            )
            
            if not route:
                return False, None, 0.0
            
            route_distance = sum(
                route[i][0].transform.location.distance(route[i-1][0].transform.location)
                for i in range(1, len(route))
            )
            return True, route, route_distance
        except:
            return False, None, 0.0
    
    def run(self, save_path='./auto_collected_data', strategy='smart'):
        """运行全自动收集"""
        self.route_generation_strategy = strategy
        
        try:
            self.connect()
            route_pairs = self.generate_route_pairs()
            
            if not route_pairs:
                print("❌ 没有生成任何路线！")
                return
            
            print("\n" + "="*70)
            print("🚀 开始全自动数据收集")
            print("="*70)
            print(f"总路线数: {len(route_pairs)}")
            print(f"保存路径: {save_path}")
            print("="*70 + "\n")
            
            start_time = time.time()
            
            for idx, (start_idx, end_idx, distance) in enumerate(route_pairs):
                self.total_routes_attempted += 1
                
                print(f"\n📍 路线 {idx+1}/{len(route_pairs)}: {start_idx} → {end_idx} ({distance:.1f}m)")
                
                valid, _, route_dist = self.validate_route(start_idx, end_idx)
                if not valid:
                    self.failed_routes.append((start_idx, end_idx, "不可达"))
                    continue
                
                if self.collect_route_data(start_idx, end_idx, save_path):
                    self.total_routes_completed += 1
                else:
                    self.failed_routes.append((start_idx, end_idx, "收集失败"))
                
                # 进度
                elapsed = time.time() - start_time
                remaining = elapsed / (idx + 1) * (len(route_pairs) - idx - 1)
                print(f"📊 进度: {idx+1}/{len(route_pairs)}, 成功: {self.total_routes_completed}, "
                      f"剩余: {remaining/60:.1f}分钟")
            
            self._print_final_statistics(time.time() - start_time, save_path)
            
        except KeyboardInterrupt:
            print("\n⚠️  收到中断信号...")
        finally:
            self._cleanup_npcs()
            if self.world:
                try:
                    settings = self.world.get_settings()
                    settings.synchronous_mode = False
                    self.world.apply_settings(settings)
                except:
                    pass
    
    def _print_final_statistics(self, total_time, save_path):
        """打印最终统计"""
        print("\n" + "="*70)
        print("📊 收集完成 - 最终统计")
        print("="*70)
        print(f"总路线: {self.total_routes_attempted}")
        print(f"成功: {self.total_routes_completed}")
        print(f"失败: {len(self.failed_routes)}")
        print(f"总帧数: {self.total_frames_collected}")
        print(f"耗时: {total_time/60:.1f}分钟")
        print("="*70)
        
        # 保存统计
        stats = {
            'total_routes': self.total_routes_attempted,
            'completed': self.total_routes_completed,
            'frames': self.total_frames_collected,
            'time_seconds': total_time,
            'failed': [{'start': s, 'end': e, 'reason': r} for s, e, r in self.failed_routes],
            'timestamp': datetime.now().isoformat()
        }
        
        stats_file = os.path.join(save_path, 'collection_statistics.json')
        os.makedirs(save_path, exist_ok=True)
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)
        print(f"✅ 统计已保存: {stats_file}")


def load_config(config_path='auto_collection_config.json'):
    """加载配置文件"""
    default_config = {
        'carla_settings': {'host': 'localhost', 'port': 2000, 'town': 'Town01'},
        'traffic_rules': {'ignore_traffic_lights': True, 'ignore_signs': True, 'ignore_vehicles_percentage': 80},
        'world_settings': {'spawn_npc_vehicles': False, 'num_npc_vehicles': 0,
                          'spawn_npc_walkers': False, 'num_npc_walkers': 0},
        'weather_settings': {'preset': 'ClearNoon'},
        'route_generation': {'strategy': 'smart', 'min_distance': 50.0, 'max_distance': 500.0,
                            'target_routes': 200, 'overlap_threshold': 0.5},
        'collection_settings': {'frames_per_route': 1000, 'save_path': './auto_collected_data',
                               'simulation_fps': 20, 'target_speed_kmh': 10.0},
        'noise_settings': {'enabled': False, 'lateral_noise': True, 'longitudinal_noise': False,
                          'lateral_frequency': 25, 'lateral_intensity': 10, 'lateral_min_time': 1.0,
                          'longitudinal_frequency': 15, 'longitudinal_intensity': 10, 'longitudinal_min_time': 2.0}
    }
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, config_path)
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            for section in default_config:
                if section in loaded:
                    default_config[section].update(loaded[section])
            print(f"✅ 已加载配置: {config_file}")
        except Exception as e:
            print(f"⚠️  加载配置失败: {e}")
    
    return default_config


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='全自动数据收集器')
    parser.add_argument('--config', default='auto_collection_config.json')
    parser.add_argument('--host', help='CARLA服务器地址')
    parser.add_argument('--port', type=int, help='CARLA服务器端口')
    parser.add_argument('--save-path', help='保存路径')
    parser.add_argument('--strategy', choices=['smart', 'exhaustive'])
    parser.add_argument('--target-routes', type=int)
    parser.add_argument('--frames-per-route', type=int)
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    # 命令行覆盖
    if args.host:
        config['carla_settings']['host'] = args.host
    if args.port:
        config['carla_settings']['port'] = args.port
    if args.save_path:
        config['collection_settings']['save_path'] = args.save_path
    if args.strategy:
        config['route_generation']['strategy'] = args.strategy
    if args.target_routes:
        config['route_generation']['target_routes'] = args.target_routes
    if args.frames_per_route:
        config['collection_settings']['frames_per_route'] = args.frames_per_route
    
    collector = AutoFullTownCollector(
        host=config['carla_settings']['host'],
        port=config['carla_settings']['port'],
        town=config['carla_settings']['town'],
        ignore_traffic_lights=config['traffic_rules']['ignore_traffic_lights'],
        ignore_signs=config['traffic_rules']['ignore_signs'],
        ignore_vehicles_percentage=config['traffic_rules']['ignore_vehicles_percentage'],
        target_speed=config['collection_settings']['target_speed_kmh'],
        simulation_fps=config['collection_settings']['simulation_fps'],
        spawn_npc_vehicles=config['world_settings']['spawn_npc_vehicles'],
        num_npc_vehicles=config['world_settings']['num_npc_vehicles'],
        spawn_npc_walkers=config['world_settings']['spawn_npc_walkers'],
        num_npc_walkers=config['world_settings']['num_npc_walkers'],
        weather_config=config.get('weather_settings', {})
    )
    
    collector.min_distance = config['route_generation']['min_distance']
    collector.max_distance = config['route_generation']['max_distance']
    collector.frames_per_route = config['collection_settings']['frames_per_route']
    collector.target_routes = config['route_generation']['target_routes']
    collector.overlap_threshold = config['route_generation']['overlap_threshold']
    
    # 噪声配置
    noise_config = config.get('noise_settings', {})
    collector.noise_enabled = noise_config.get('enabled', False)
    collector.lateral_noise_enabled = noise_config.get('lateral_noise', True)
    collector.longitudinal_noise_enabled = noise_config.get('longitudinal_noise', False)
    
    # 噪声参数
    collector.lateral_frequency = noise_config.get('lateral_frequency', 25)
    collector.lateral_intensity = noise_config.get('lateral_intensity', 4)
    collector.lateral_min_time = noise_config.get('lateral_min_time', 0.5)
    collector.longitudinal_frequency = noise_config.get('longitudinal_frequency', 15)
    collector.longitudinal_intensity = noise_config.get('longitudinal_intensity', 10)
    collector.longitudinal_min_time = noise_config.get('longitudinal_min_time', 2.0)
    
    if collector.noise_enabled:
        print(f"\n🎲 噪声注入已启用:")
        print(f"  • 横向噪声: {'✅' if collector.lateral_noise_enabled else '❌'} "
              f"(freq={collector.lateral_frequency}, intensity={collector.lateral_intensity})")
        print(f"  • 纵向噪声: {'✅' if collector.longitudinal_noise_enabled else '❌'} "
              f"(freq={collector.longitudinal_frequency}, intensity={collector.longitudinal_intensity})")
    
    collector.run(
        save_path=config['collection_settings']['save_path'],
        strategy=config['route_generation']['strategy']
    )


if __name__ == '__main__':
    main()
