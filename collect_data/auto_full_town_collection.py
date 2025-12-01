#!/usr/bin/env python
# coding=utf-8
'''
作者: AI Assistant
日期: 2025-12-01
说明: 全自动Town01场景数据收集器
      自动遍历所有生成点组合，收集完整的Town01场景数据
      无需人工干预，智能选择路线并自动保存
'''

import glob
import os
import sys
import time
import numpy as np
import json
from datetime import datetime

# 添加CARLA Python API路径
try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla

# 导入数据收集器
from command_based_data_collection import CommandBasedDataCollector

# 导入agents模块
try:
    from agents.navigation.global_route_planner import GlobalRoutePlanner
    from agents.navigation.local_planner_info import LocalPlanner, RoadOption
    AGENTS_AVAILABLE = True
except ImportError as e:
    AGENTS_AVAILABLE = False
    print(f"⚠️  警告: 无法导入agents模块: {e}")


class AutoFullTownCollector:
    """全自动Town01数据收集器"""
    
    def __init__(self, host='localhost', port=2000, town='Town01',
                 ignore_traffic_lights=True, ignore_signs=True,
                 ignore_vehicles_percentage=80):
        """
        初始化全自动收集器
        
        参数:
            host (str): CARLA服务器地址
            port (int): CARLA服务器端口
            town (str): 地图名称
            ignore_traffic_lights (bool): 是否忽略红绿灯
            ignore_signs (bool): 是否忽略停车标志
            ignore_vehicles_percentage (int): 忽略其他车辆的百分比
        """
        self.host = host
        self.port = port
        self.town = town
        
        # 交通规则配置
        self.ignore_traffic_lights = ignore_traffic_lights
        self.ignore_signs = ignore_signs
        self.ignore_vehicles_percentage = ignore_vehicles_percentage
        
        # CARLA对象
        self.client = None
        self.world = None
        self.spawn_points = []
        self.route_planner = None
        
        # 数据收集器
        self.collector = None
        
        # 收集策略
        self.min_distance = 50.0  # 最小直线距离（米）
        self.max_distance = 500.0  # 最大直线距离（米）
        self.frames_per_route = 1000  # 每条路线收集的帧数
        
        # 统计信息
        self.total_routes_attempted = 0
        self.total_routes_completed = 0
        self.total_frames_collected = 0
        self.failed_routes = []
        
        # 路线生成策略
        self.route_generation_strategy = 'smart'  # 'smart' 或 'exhaustive'
        
    def connect(self):
        """连接到CARLA服务器"""
        print("\n" + "="*70)
        print("🚗 全自动Town01数据收集器")
        print("="*70)
        print(f"正在连接到CARLA服务器 {self.host}:{self.port}...")
        
        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(10.0)
        
        # 加载地图
        self.world = self.client.get_world()
        current_map_name = self.world.get_map().name.split('/')[-1]
        
        if current_map_name != self.town:
            print(f"正在加载地图 {self.town}...")
            self.world = self.client.load_world(self.town)
        else:
            print(f"✅ 已连接到地图 {self.town}")
        
        # 获取生成点
        self.spawn_points = self.world.get_map().get_spawn_points()
        print(f"✅ 成功连接！共找到 {len(self.spawn_points)} 个生成点")
        
        # 显示交通规则配置
        print(f"\n📋 交通规则配置:")
        print(f"  • 忽略红绿灯: {'✅ 是' if self.ignore_traffic_lights else '❌ 否'}")
        print(f"  • 忽略停车标志: {'✅ 是' if self.ignore_signs else '❌ 否'}")
        print(f"  • 忽略其他车辆: {self.ignore_vehicles_percentage}%")
        
        # 初始化路径规划器
        if AGENTS_AVAILABLE:
            try:
                self.route_planner = GlobalRoutePlanner(
                    self.world.get_map(), 
                    sampling_resolution=2.0
                )
                print("✅ 路径规划器初始化成功")
            except Exception as e:
                print(f"⚠️  路径规划器初始化失败: {e}")
                self.route_planner = None
        
        print()
        
    def generate_route_pairs(self):
        """
        生成路线对（起点-终点组合）
        
        策略：
        1. 智能模式：选择距离适中、分布均匀的路线
        2. 穷举模式：遍历所有可能的组合（数量巨大）
        
        返回:
            list: [(start_idx, end_idx), ...] 路线对列表
        """
        print("\n" + "="*70)
        print("📍 生成路线对")
        print("="*70)
        
        num_spawns = len(self.spawn_points)
        route_pairs = []
        
        if self.route_generation_strategy == 'smart':
            print(f"策略: 智能选择（距离适中、分布均匀）")
            print(f"距离范围: {self.min_distance:.0f}m - {self.max_distance:.0f}m")
            
            # 为每个起点选择多个合适的终点
            for start_idx in range(num_spawns):
                start_loc = self.spawn_points[start_idx].location
                
                # 找到所有距离合适的终点
                valid_ends = []
                for end_idx in range(num_spawns):
                    if start_idx == end_idx:
                        continue
                    
                    end_loc = self.spawn_points[end_idx].location
                    distance = self._calculate_distance(start_loc, end_loc)
                    
                    if self.min_distance <= distance <= self.max_distance:
                        valid_ends.append((end_idx, distance))
                
                # 按距离排序，选择不同距离段的终点
                if valid_ends:
                    valid_ends.sort(key=lambda x: x[1])
                    
                    # 选择短、中、长距离各一个
                    num_ends = len(valid_ends)
                    selected_indices = [
                        0,  # 最短
                        num_ends // 2,  # 中等
                        num_ends - 1  # 最长
                    ]
                    
                    for idx in selected_indices:
                        if idx < num_ends:
                            end_idx, distance = valid_ends[idx]
                            route_pairs.append((start_idx, end_idx, distance))
            
            print(f"✅ 生成了 {len(route_pairs)} 条智能路线")
            
        else:  # exhaustive
            print(f"策略: 穷举所有组合（警告：数量巨大！）")
            
            for start_idx in range(num_spawns):
                for end_idx in range(num_spawns):
                    if start_idx == end_idx:
                        continue
                    
                    start_loc = self.spawn_points[start_idx].location
                    end_loc = self.spawn_points[end_idx].location
                    distance = self._calculate_distance(start_loc, end_loc)
                    
                    if self.min_distance <= distance <= self.max_distance:
                        route_pairs.append((start_idx, end_idx, distance))
            
            print(f"✅ 生成了 {len(route_pairs)} 条穷举路线")
        
        # 显示统计信息
        if route_pairs:
            distances = [d for _, _, d in route_pairs]
            print(f"\n📊 路线统计:")
            print(f"  • 总路线数: {len(route_pairs)}")
            print(f"  • 平均距离: {np.mean(distances):.1f}m")
            print(f"  • 最短距离: {np.min(distances):.1f}m")
            print(f"  • 最长距离: {np.max(distances):.1f}m")
            
            # 估算收集时间
            estimated_minutes = len(route_pairs) * 2  # 假设每条路线2分钟
            print(f"  • 预计耗时: {estimated_minutes:.0f}分钟 ({estimated_minutes/60:.1f}小时)")
        
        print()
        return route_pairs
    
    def _calculate_distance(self, loc1, loc2):
        """计算两点之间的直线距离"""
        dx = loc2.x - loc1.x
        dy = loc2.y - loc1.y
        return np.sqrt(dx**2 + dy**2)
    
    def validate_route(self, start_idx, end_idx):
        """
        验证路线是否可行
        
        参数:
            start_idx (int): 起点索引
            end_idx (int): 终点索引
            
        返回:
            tuple: (是否可行, 路径数据, 路径长度)
        """
        if not AGENTS_AVAILABLE or self.route_planner is None:
            return True, None, 0.0  # 无法验证，假设可行
        
        try:
            start_point = self.spawn_points[start_idx]
            end_point = self.spawn_points[end_idx]
            
            # 规划路径
            route = self.route_planner.trace_route(
                start_point.location, 
                end_point.location
            )
            
            if not route or len(route) == 0:
                return False, None, 0.0
            
            # 计算路径长度
            route_distance = 0.0
            for i in range(len(route) - 1):
                wp1 = route[i][0].transform.location
                wp2 = route[i+1][0].transform.location
                route_distance += wp1.distance(wp2)
            
            return True, route, route_distance
            
        except Exception as e:
            print(f"⚠️  路径验证失败: {e}")
            return False, None, 0.0
    
    def collect_route_data(self, start_idx, end_idx, route_data, save_path):
        """
        收集单条路线的数据（全自动）
        
        参数:
            start_idx (int): 起点索引
            end_idx (int): 终点索引
            route_data: 路径数据
            save_path (str): 保存路径
            
        返回:
            bool: 是否成功
        """
        print(f"\n{'='*70}")
        print(f"📊 收集路线数据: {start_idx} → {end_idx}")
        print(f"{'='*70}")
        
        try:
            # 创建数据收集器
            self.collector = CommandBasedDataCollector(
                host=self.host,
                port=self.port,
                town=self.town,
                ignore_traffic_lights=self.ignore_traffic_lights,
                ignore_signs=self.ignore_signs,
                ignore_vehicles_percentage=self.ignore_vehicles_percentage
            )
            
            # 复用已有的连接
            self.collector.client = self.client
            self.collector.world = self.world
            self.collector.blueprint_library = self.world.get_blueprint_library()
            
            # 设置同步模式
            settings = self.world.get_settings()
            if not settings.synchronous_mode:
                settings.synchronous_mode = True
                settings.fixed_delta_seconds = 0.05  # 20FPS
                self.world.apply_settings(settings)
            
            # 生成车辆
            if not self.collector.spawn_vehicle(start_idx, end_idx):
                print("❌ 无法生成车辆！")
                return False
            
            # 设置摄像头
            self.collector.setup_camera()
            
            # 等待传感器准备
            print("等待传感器准备...")
            time.sleep(1.0)
            
            # 开始自动收集数据（启用可视化）
            print(f"🎬 开始自动收集数据...")
            success = self._auto_collect_data(save_path, enable_visualization=True)
            
            return success
            
        except Exception as e:
            print(f"❌ 收集数据出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 清理资源
            if self.collector:
                print("正在清理车辆和传感器...")
                try:
                    if self.collector.camera is not None:
                        self.collector.camera.stop()
                        self.collector.camera.destroy()
                except:
                    pass
                    
                try:
                    if self.collector.vehicle is not None:
                        self.collector.vehicle.destroy()
                except:
                    pass
                
                print("✅ 清理完成")
    
    def _auto_collect_data(self, save_path, enable_visualization=True):
        """
        自动收集数据（带可视化窗口）
        
        策略：
        1. 自动收集所有命令段
        2. 每200帧自动保存
        3. 到达终点或达到帧数限制后停止
        4. 实时显示可视化窗口
        
        参数:
            save_path (str): 保存路径
            enable_visualization (bool): 是否启用可视化
            
        返回:
            bool: 是否成功
        """
        import cv2
        
        os.makedirs(save_path, exist_ok=True)
        
        # 启用可视化
        self.collector.enable_visualization = enable_visualization
        if enable_visualization:
            print("✅ 已启用实时可视化窗口")
            print("💡 提示：按ESC键可关闭可视化窗口（数据收集继续）\n")
        
        # 等待第一帧
        print("等待第一帧图像...")
        while len(self.collector.image_buffer) == 0:
            if self.collector.agent is not None:
                control = self.collector.agent.run_step()
                self.collector.vehicle.apply_control(control)
            self.world.tick()
            time.sleep(0.01)
        
        print("摄像头就绪！开始收集...\n")
        
        collected_frames = 0
        max_frames = self.frames_per_route
        current_segment_data = {'rgb': [], 'targets': []}
        segment_count = 0
        
        # 获取初始命令
        current_command = self.collector._get_navigation_command()
        
        try:
            while collected_frames < max_frames:
                # 推进模拟
                if self.collector.agent is not None:
                    control = self.collector.agent.run_step()
                    self.collector.vehicle.apply_control(control)
                self.world.tick()
                
                # 检查是否到达终点
                if self.collector._is_route_completed():
                    print(f"\n🎯 已到达目的地！")
                    break
                
                if len(self.collector.image_buffer) == 0:
                    continue
                
                # 获取数据
                current_image = self.collector.image_buffer[-1]
                vehicle_velocity = self.collector.vehicle.get_velocity()
                vehicle_control = self.collector.vehicle.get_control()
                
                speed_kmh = 3.6 * np.sqrt(
                    vehicle_velocity.x**2 + 
                    vehicle_velocity.y**2 + 
                    vehicle_velocity.z**2
                )
                
                # 获取当前命令
                current_cmd = self.collector._get_navigation_command()
                
                # 构建targets
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
                current_segment_data['rgb'].append(current_image)
                current_segment_data['targets'].append(targets)
                segment_count += 1
                collected_frames += 1
                
                # 可视化（如果启用）
                if self.collector.enable_visualization:
                    self.collector._visualize_frame(
                        current_image, 
                        speed_kmh, 
                        current_cmd, 
                        collected_frames, 
                        max_frames,
                        is_collecting=True
                    )
                
                # 每200帧自动保存
                if segment_count >= 200:
                    print(f"💾 自动保存数据段（{segment_count} 帧）...")
                    self._save_segment_auto(current_segment_data, save_path, current_cmd)
                    
                    # 重置当前段
                    current_segment_data = {'rgb': [], 'targets': []}
                    segment_count = 0
                
                # 进度显示
                if collected_frames % 100 == 0:
                    cmd_name = self.collector.command_names.get(current_cmd, 'Unknown')
                    print(f"  [收集中] 帧数: {collected_frames}/{max_frames}, "
                          f"命令: {cmd_name}, 速度: {speed_kmh:.1f} km/h")
            
            # 保存剩余数据
            if segment_count > 0:
                print(f"💾 保存剩余数据（{segment_count} 帧）...")
                self._save_segment_auto(current_segment_data, save_path, current_command)
            
            print(f"✅ 路线收集完成！总帧数: {collected_frames}")
            self.total_frames_collected += collected_frames
            return True
            
        except Exception as e:
            print(f"❌ 自动收集出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 关闭可视化窗口
            if self.collector.enable_visualization:
                try:
                    import cv2
                    cv2.destroyAllWindows()
                except:
                    pass
    
    def _save_segment_auto(self, segment_data, save_path, command):
        """
        自动保存数据段
        
        参数:
            segment_data (dict): 数据段
            save_path (str): 保存路径
            command (float): 命令类型
        """
        if len(segment_data['rgb']) == 0:
            return
        
        import h5py
        
        # 转换为numpy数组
        rgb_array = np.array(segment_data['rgb'], dtype=np.uint8)
        targets_array = np.array(segment_data['targets'], dtype=np.float32)
        
        # 生成文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        command_name = self.collector.command_names.get(command, 'Unknown')
        filename = os.path.join(
            save_path,
            f"carla_cmd{command}_{command_name}_{timestamp}.h5"
        )
        
        # 保存
        with h5py.File(filename, 'w') as hf:
            hf.create_dataset('rgb', data=rgb_array, compression='gzip', compression_opts=4)
            hf.create_dataset('targets', data=targets_array, compression='gzip', compression_opts=4)
        
        file_size_mb = os.path.getsize(filename) / 1024 / 1024
        print(f"  ✓ 已保存: {os.path.basename(filename)} ({len(rgb_array)} 样本, {file_size_mb:.2f} MB)")
    
    def run(self, save_path='./auto_collected_data', strategy='smart'):
        """
        运行全自动收集流程
        
        参数:
            save_path (str): 数据保存路径
            strategy (str): 路线生成策略 ('smart' 或 'exhaustive')
        """
        self.route_generation_strategy = strategy
        
        try:
            # 步骤1: 连接CARLA
            self.connect()
            
            # 步骤2: 生成路线对
            route_pairs = self.generate_route_pairs()
            
            if not route_pairs:
                print("❌ 没有生成任何路线！")
                return
            
            # 步骤3: 遍历所有路线并收集数据
            print("\n" + "="*70)
            print("🚀 开始全自动数据收集")
            print("="*70)
            print(f"总路线数: {len(route_pairs)}")
            print(f"保存路径: {save_path}")
            print(f"每条路线帧数: {self.frames_per_route}")
            print("="*70 + "\n")
            
            start_time = time.time()
            
            for idx, (start_idx, end_idx, distance) in enumerate(route_pairs):
                self.total_routes_attempted += 1
                
                print(f"\n{'='*70}")
                print(f"📍 路线 {idx+1}/{len(route_pairs)}")
                print(f"{'='*70}")
                print(f"起点: #{start_idx}")
                print(f"终点: #{end_idx}")
                print(f"直线距离: {distance:.1f}m")
                
                # 验证路线
                print("验证路线可行性...")
                valid, route_data, route_distance = self.validate_route(start_idx, end_idx)
                
                if not valid:
                    print(f"❌ 路线不可行，跳过")
                    self.failed_routes.append((start_idx, end_idx, "路线不可达"))
                    continue
                
                if route_data:
                    print(f"✅ 路线可行，实际长度: {route_distance:.1f}m")
                
                # 收集数据
                success = self.collect_route_data(start_idx, end_idx, route_data, save_path)
                
                if success:
                    self.total_routes_completed += 1
                    print(f"✅ 路线 {idx+1} 完成")
                else:
                    print(f"❌ 路线 {idx+1} 失败")
                    self.failed_routes.append((start_idx, end_idx, "收集失败"))
                
                # 显示进度
                elapsed = time.time() - start_time
                avg_time_per_route = elapsed / (idx + 1)
                remaining_routes = len(route_pairs) - (idx + 1)
                estimated_remaining = avg_time_per_route * remaining_routes
                
                print(f"\n📊 总体进度:")
                print(f"  • 已完成: {idx+1}/{len(route_pairs)} ({(idx+1)/len(route_pairs)*100:.1f}%)")
                print(f"  • 成功: {self.total_routes_completed}")
                print(f"  • 失败: {len(self.failed_routes)}")
                print(f"  • 已用时: {elapsed/60:.1f}分钟")
                print(f"  • 预计剩余: {estimated_remaining/60:.1f}分钟")
                print(f"  • 总帧数: {self.total_frames_collected}")
            
            # 最终统计
            total_time = time.time() - start_time
            self._print_final_statistics(total_time, save_path)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  收到中断信号，正在退出...")
            self._print_final_statistics(time.time() - start_time, save_path)
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 恢复异步模式
            if self.world is not None:
                try:
                    settings = self.world.get_settings()
                    if settings.synchronous_mode:
                        settings.synchronous_mode = False
                        self.world.apply_settings(settings)
                        print("✅ 已恢复CARLA异步模式")
                except:
                    pass
    
    def _print_final_statistics(self, total_time, save_path):
        """打印最终统计信息"""
        print("\n" + "="*70)
        print("📊 全自动收集完成 - 最终统计")
        print("="*70)
        print(f"总尝试路线: {self.total_routes_attempted}")
        print(f"成功完成: {self.total_routes_completed}")
        print(f"失败路线: {len(self.failed_routes)}")
        print(f"成功率: {self.total_routes_completed/self.total_routes_attempted*100:.1f}%")
        print(f"总收集帧数: {self.total_frames_collected}")
        print(f"总耗时: {total_time/60:.1f}分钟 ({total_time/3600:.2f}小时)")
        print(f"数据保存路径: {save_path}")
        
        if self.failed_routes:
            print(f"\n❌ 失败路线列表:")
            for start, end, reason in self.failed_routes[:10]:  # 只显示前10个
                print(f"  • {start} → {end}: {reason}")
            if len(self.failed_routes) > 10:
                print(f"  ... 还有 {len(self.failed_routes)-10} 条失败路线")
        
        print("="*70 + "\n")
        
        # 保存统计信息到JSON
        stats = {
            'total_routes_attempted': self.total_routes_attempted,
            'total_routes_completed': self.total_routes_completed,
            'total_frames_collected': self.total_frames_collected,
            'total_time_seconds': total_time,
            'failed_routes': [
                {'start': s, 'end': e, 'reason': r} 
                for s, e, r in self.failed_routes
            ],
            'timestamp': datetime.now().isoformat()
        }
        
        stats_file = os.path.join(save_path, 'collection_statistics.json')
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)
        
        print(f"✅ 统计信息已保存到: {stats_file}\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='全自动Town01数据收集器')
    parser.add_argument('--host', default='localhost', help='CARLA服务器地址')
    parser.add_argument('--port', type=int, default=2000, help='CARLA服务器端口')
    parser.add_argument('--town', default='Town01', help='地图名称')
    parser.add_argument('--save-path', default='./auto_collected_data', help='数据保存路径')
    parser.add_argument('--strategy', choices=['smart', 'exhaustive'], default='smart',
                       help='路线生成策略：smart=智能选择，exhaustive=穷举所有')
    parser.add_argument('--min-distance', type=float, default=50.0, help='最小路线距离（米）')
    parser.add_argument('--max-distance', type=float, default=500.0, help='最大路线距离（米）')
    parser.add_argument('--frames-per-route', type=int, default=1000, help='每条路线收集的帧数')
    parser.add_argument('--ignore-traffic-lights', action='store_true', default=True,
                       help='忽略红绿灯')
    parser.add_argument('--ignore-signs', action='store_true', default=True,
                       help='忽略停车标志')
    parser.add_argument('--ignore-vehicles', type=int, default=80,
                       help='忽略其他车辆的百分比（0-100）')
    parser.add_argument('--no-visualization', action='store_true',
                       help='禁用实时可视化窗口（默认启用）')
    
    args = parser.parse_args()
    
    # 验证帧数（最少200帧）
    if args.frames_per_route < 200:
        print(f"⚠️  警告：每条路线帧数 ({args.frames_per_route}) 小于最小值 200")
        print(f"✅ 自动调整为 200 帧\n")
        args.frames_per_route = 200
    
    # 创建收集器
    collector = AutoFullTownCollector(
        host=args.host,
        port=args.port,
        town=args.town,
        ignore_traffic_lights=args.ignore_traffic_lights,
        ignore_signs=args.ignore_signs,
        ignore_vehicles_percentage=args.ignore_vehicles
    )
    
    # 设置参数
    collector.min_distance = args.min_distance
    collector.max_distance = args.max_distance
    collector.frames_per_route = args.frames_per_route
    
    # 运行收集
    collector.run(save_path=args.save_path, strategy=args.strategy)


if __name__ == '__main__':
    main()
