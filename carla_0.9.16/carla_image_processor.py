#!/usr/bin/env python
# coding=utf-8
'''
图像预处理模块
负责将原始图像转换为模型输入格式

更新（2025-12-04）：
- 修改默认 enable_crop=True，与数据收集保持一致
- 使用动态裁剪比例（0.192, 0.85），适应不同分辨率
- 使用 INTER_LINEAR 插值，与数据收集一致
'''

import numpy as np
import cv2
import torch
from carla_config import IMAGE_HEIGHT, IMAGE_WIDTH


class ImageProcessor:
    """图像预处理器"""
    
    def __init__(self, device, enable_crop=True, crop_ratio_top=0.192, crop_ratio_bottom=0.85):
        """
        初始化图像预处理器
        
        参数:
            device: torch.device 对象
            enable_crop (bool): 是否启用图像裁剪（默认True，与数据收集一致）
            crop_ratio_top (float): 裁剪上边界比例（默认0.192，即115/600）
            crop_ratio_bottom (float): 裁剪下边界比例（默认0.85，即510/600）
        
        注意：
            裁剪参数与 collect_data/command_based_data_collection.py 保持一致
            原始参数是针对800x600的：top=115, bottom=510
            裁剪比例：top=115/600=0.192, bottom=510/600=0.85
        """
        self.device = device
        self.enable_crop = enable_crop
        self.crop_ratio_top = crop_ratio_top
        self.crop_ratio_bottom = crop_ratio_bottom
    
    def preprocess(self, image):
        """
        预处理图像（与数据收集时保持一致）
        
        处理流程（与 command_based_data_collection.py 的 _on_camera_update 一致）：
        1. 裁剪（去除天空和车头）
        2. 缩放到模型输入尺寸 (88, 200)
        3. 归一化到 [0, 1]
        4. 转换为 PyTorch 张量
        
        参数:
            image: numpy数组 (H, W, 3)，RGB格式，值范围 [0, 255]
            
        返回:
            torch.Tensor: (1, 3, 88, 200)，值范围 [0, 1]
        """
        # 步骤1: 图像裁剪 - 去除天空和车头（与数据收集一致）
        if self.enable_crop:
            # 动态计算裁剪参数（适应不同分辨率）
            crop_top = int(image.shape[0] * self.crop_ratio_top)
            crop_bottom = int(image.shape[0] * self.crop_ratio_bottom)
            image = image[crop_top:crop_bottom, :, :]
        
        # 步骤2: 缩放到模型输入尺寸 (88, 200)
        # 使用 INTER_LINEAR 插值，与数据收集一致
        if image.shape[0] != IMAGE_HEIGHT or image.shape[1] != IMAGE_WIDTH:
            image_input = cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT), 
                                     interpolation=cv2.INTER_LINEAR)
        else:
            image_input = image
        
        # 步骤3: 转换数据类型
        image_input = image_input.astype(np.float32)
        
        # 步骤4: 调整维度顺序 (H, W, C) -> (C, H, W)
        image_input = np.transpose(image_input, (2, 0, 1))
        
        # 步骤5: 增加batch维度 -> (1, C, H, W)
        image_input = np.expand_dims(image_input, axis=0)
        
        # 步骤6: 归一化到 [0, 1] (与训练时保持一致)
        image_input = np.multiply(image_input, 1.0 / 255.0)
        
        # 步骤7: 转换为PyTorch张量并移到设备
        img_tensor = torch.from_numpy(image_input).to(self.device)
        
        return img_tensor
    
    def get_processed_image(self, image):
        """
        获取处理后的图像（用于可视化，不转换为tensor）
        
        参数:
            image: numpy数组 (H, W, 3)，RGB格式，值范围 [0, 255]
            
        返回:
            numpy数组: (88, 200, 3)，RGB格式，值范围 [0, 255]
        """
        # 步骤1: 图像裁剪
        if self.enable_crop:
            crop_top = int(image.shape[0] * self.crop_ratio_top)
            crop_bottom = int(image.shape[0] * self.crop_ratio_bottom)
            image = image[crop_top:crop_bottom, :, :]
        
        # 步骤2: 缩放到模型输入尺寸 (88, 200)
        if image.shape[0] != IMAGE_HEIGHT or image.shape[1] != IMAGE_WIDTH:
            image = cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT), 
                               interpolation=cv2.INTER_LINEAR)
        
        return image
