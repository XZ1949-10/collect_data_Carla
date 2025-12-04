#!/usr/bin/env python
# coding=utf-8
'''
CARLA 可视化模块
使用OpenCV显示实时推理状态
'''

import cv2
import time
from carla_config import *


class CarlaVisualizer:
    """CARLA 推理可视化器"""
    
    def __init__(self):
        """初始化可视化器"""
        self.window_name = 'CARLA Inference'
        self.start_time = None
        
    def set_start_time(self, start_time):
        """设置开始时间（用于FPS计算）"""
        self.start_time = start_time
        
    def visualize(self, image, control_result, actual_speed, route_info, frame_count):
        """
        可视化当前状态
        
        参数:
            image: 当前RGB图像 (numpy array)
            control_result: 控制预测结果字典
            actual_speed: 实际速度（归一化值 0-1）
            route_info: 路线信息字典
            frame_count: 当前帧数
        """
        # 复制图像
        vis_image = image.copy()
        
        # 放大图像
        vis_image = cv2.resize(vis_image, (VISUALIZATION_WIDTH, VISUALIZATION_HEIGHT))
        
        # 计算实际速度（km/h）
        actual_speed_kmh = actual_speed * SPEED_NORMALIZATION_MPS 
        
        # 获取英文命令名
        command_en = COMMAND_NAMES_EN.get(route_info['current_command'], 'Unknown')
        
        # 绘制文本信息
        y_pos = 20
        line_height = 20
        
        # 导航命令
        cv2.putText(vis_image, f"Command: {command_en}", 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += line_height
        
        # 路线进度
        cv2.putText(vis_image, f"Progress: {route_info['progress']:.1f}%", 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += line_height
        
        # 剩余距离
        cv2.putText(vis_image, f"Remaining: {route_info['remaining_distance']:.0f}m", 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += line_height
        
        # 速度
        cv2.putText(vis_image, f"Speed: {actual_speed_kmh:.1f} km/h", 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += line_height
        
        # 控制信号
        cv2.putText(vis_image, f"Steer: {control_result['steer']:+.3f}", 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += line_height
        
        cv2.putText(vis_image, f"Throttle: {control_result['throttle']:.3f}", 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += line_height
        
        cv2.putText(vis_image, f"Brake: {control_result['brake']:.3f}", 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_pos += line_height
        
        # FPS
        fps_text = f"FPS: {frame_count / (time.time() - self.start_time):.1f}" \
                   if self.start_time is not None else "FPS: --"
        cv2.putText(vis_image, fps_text, 
                    (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 显示方向盘位置（可视化指示器）
        self._draw_steering_indicator(vis_image, control_result['steer'])
        
        # 转换为BGR用于OpenCV显示
        vis_image = cv2.cvtColor(vis_image, cv2.COLOR_RGB2BGR)
        
        # 显示
        cv2.imshow(self.window_name, vis_image)
        cv2.waitKey(1)
        
    def _draw_steering_indicator(self, image, steer_value):
        """
        绘制方向盘指示器
        
        参数:
            image: 图像
            steer_value: 方向盘值 [-1, 1]
        """
        center_x = VISUALIZATION_WIDTH // 2
        bar_y = VISUALIZATION_HEIGHT - 30
        
        # 绘制横线
        cv2.line(image, (100, bar_y), (300, bar_y), (100, 100, 100), 2)
        
        # 绘制中心点
        cv2.circle(image, (center_x, bar_y), 3, (255, 255, 255), -1)
        
        # 绘制方向盘位置
        steer_x = int(center_x + steer_value * 100)
        steer_x = max(100, min(300, steer_x))  # 限制范围
        cv2.circle(image, (steer_x, bar_y), 5, (0, 0, 255), -1)
        
    def close(self):
        """关闭可视化窗口"""
        cv2.destroyAllWindows()

