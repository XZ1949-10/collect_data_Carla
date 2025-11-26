#!/usr/bin/env python
# coding=utf-8
'''
图像预处理模块
负责将原始图像转换为模型输入格式
'''

import numpy as np
import cv2
import torch
from carla_config import IMAGE_HEIGHT, IMAGE_WIDTH


class ImageProcessor:
    """图像预处理器"""
    
    def __init__(self, device, enable_crop=False, crop_top=115, crop_bottom=510):
        """
        初始化图像预处理器
        
        参数:
            device: torch.device 对象
            enable_crop (bool): 是否启用图像裁剪（去除天空和引擎盖）
            crop_top (int): 裁剪上边界（默认115）
            crop_bottom (int): 裁剪下边界（默认510）
        """
        self.device = device
        self.enable_crop = enable_crop
        self.crop_top = crop_top
        self.crop_bottom = crop_bottom
    
    def preprocess(self, image):
        """
        预处理图像（与训练时保持一致）
        
        参数:
            image: numpy数组 (H, W, 3)，RGB格式，值范围 [0, 255]
            
        返回:
            torch.Tensor: (1, 3, 88, 200)，值范围 [0, 1]
        """
        # 步骤0: 图像裁剪（可选）- 去除天空和引擎盖
        if self.enable_crop:
            image = image[self.crop_top:self.crop_bottom, :]
        
        # 步骤1: Resize到模型输入尺寸 (88, 200)
        if image.shape[0] != IMAGE_HEIGHT or image.shape[1] != IMAGE_WIDTH:
            image_input = cv2.resize(image, (IMAGE_WIDTH, IMAGE_HEIGHT))
        else:
            image_input = image
        
        # 步骤2: 转换数据类型
        image_input = image_input.astype(np.float32)
        
        # 步骤3: 调整维度顺序 (H, W, C) -> (C, H, W)
        image_input = np.transpose(image_input, (2, 0, 1))
        
        # 步骤4: 增加batch维度 -> (1, C, H, W)
        image_input = np.expand_dims(image_input, axis=0)
        
        # 步骤5: 归一化到 [0, 1] (与训练时保持一致：在维度转换后归一化)
        image_input = np.multiply(image_input, 1.0 / 255.0)
        
        # 步骤6: 转换为PyTorch张量并移到设备
        img_tensor = torch.from_numpy(image_input).to(self.device)
        
        return img_tensor
