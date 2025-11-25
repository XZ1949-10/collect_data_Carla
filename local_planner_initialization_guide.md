# LocalPlanner 初始化指南

## 🎯 快速开始

### 最简单的初始化方式

```python
from agents.navigation.local_planner import LocalPlanner

# 只需要传入车辆对象（必需参数）
local_planner = LocalPlanner(vehicle)
```

## 📋 初始化参数说明

### 完整签名

```python
LocalPlanner(vehicle, opt_dict={}, map_inst=None)
```

### 参数详解

#### 1. `vehicle` （必需）⭐
- **类型**: `carla.Vehicle`
- **说明**: CARLA中的车辆对象
- **如何获取**: 通过 `world.spawn_actor()` 生成

```python
# 生成车辆
blueprint_library = world.get_blueprint_library()
vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
spawn_point = carla_map.get_spawn_points()[0]
vehicle = world.spawn_actor(vehicle_bp, spawn_point)

# 使用车辆初始化
local_planner = LocalPlanner(vehicle)
```

#### 2. `opt_dict` （可选）
- **类型**: `dict`
- **默认值**: `{}`
- **说明**: 配置参数字典

**可用参数：**

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `target_speed` | float | 20.0 | 目标速度 (km/h) |
| `sampling_radius` | float | 2.0 | 路点间距 (米) |
| `offset` | float | 0.0 | 车道偏移 (米，正值向右) |
| `base_min_distance` | float | 3.0 | 基础清理距离 (米) |
| `distance_ratio` | float | 0.5 | 速度相关距离系数 |
| `follow_speed_limits` | bool | False | 是否跟随速度限制 |

```python
# 自定义参数
opt_dict = {
    'target_speed': 30.0,        # 30 km/h
    'sampling_radius': 2.0,      # 路点间隔2米
    'offset': 0.5,               # 向右偏移0.5米
}

local_planner = LocalPlanner(vehicle, opt_dict=opt_dict)
```

#### 3. `map_inst` （可选）
- **类型**: `carla.Map`
- **默认值**: `None`
- **说明**: CARLA地图对象（如果不提供，会自动从world获取）

```python
# 提供地图对象（避免重复获取）
carla_map = world.get_map()
local_planner = LocalPlanner(vehicle, map_inst=carla_map)
```

## 💡 初始化示例

### 示例1: 最简单（使用默认参数）

```python
import carla

# 连接CARLA
client = carla.Client('localhost', 2000)
world = client.get_world()

# 生成车辆
blueprint_library = world.get_blueprint_library()
vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
spawn_point = world.get_map().get_spawn_points()[0]
vehicle = world.spawn_actor(vehicle_bp, spawn_point)

# 初始化规划器（最简单）
from agents.navigation.local_planner import LocalPlanner
local_planner = LocalPlanner(vehicle)

# 完成！可以开始使用
```

### 示例2: 自定义速度和路点间距

```python
# 自定义参数
opt_dict = {
    'target_speed': 40.0,      # 40 km/h
    'sampling_radius': 1.5,    # 路点更密集（1.5米）
}

local_planner = LocalPlanner(vehicle, opt_dict=opt_dict)
```

### 示例3: 完整配置

```python
# 完整的配置
opt_dict = {
    'target_speed': 50.0,           # 目标速度 50 km/h
    'sampling_radius': 2.0,         # 路点间距 2米
    'offset': 1.0,                  # 向右偏移1米（靠右行驶）
    'base_min_distance': 3.0,       # 基础清理距离
    'distance_ratio': 0.5,          # 速度相关系数
    'follow_speed_limits': True,    # 跟随道路速度限制
}

# 获取地图（避免重复获取）
carla_map = world.get_map()

# 初始化
local_planner = LocalPlanner(
    vehicle=vehicle,
    opt_dict=opt_dict,
    map_inst=carla_map
)
```

### 示例4: 不同场景的配置

#### 场景A: 城市低速驾驶

```python
opt_dict = {
    'target_speed': 20.0,        # 低速
    'sampling_radius': 1.0,      # 密集路点
    'offset': 0.0,               # 车道中心
}
local_planner = LocalPlanner(vehicle, opt_dict=opt_dict)
```

#### 场景B: 高速公路

```python
opt_dict = {
    'target_speed': 80.0,        # 高速
    'sampling_radius': 3.0,      # 稀疏路点
    'offset': 0.0,
}
local_planner = LocalPlanner(vehicle, opt_dict=opt_dict)
```

#### 场景C: 靠右行驶

```python
opt_dict = {
    'target_speed': 30.0,
    'offset': 1.5,               # 向右偏移1.5米
}
local_planner = LocalPlanner(vehicle, opt_dict=opt_dict)
```

#### 场景D: 跟随速度限制

```python
opt_dict = {
    'follow_speed_limits': True,  # 自动跟随道路速度限制
    'sampling_radius': 2.0,
}
local_planner = LocalPlanner(vehicle, opt_dict=opt_dict)
```

## 🔧 完整初始化流程

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import carla
import sys
import os

# 添加agents路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from agents.navigation.local_planner import LocalPlanner
from agents.navigation.global_route_planner import GlobalRoutePlanner


def main():
    # ========== 步骤1: 连接CARLA服务器 ==========
    print("连接CARLA...")
    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    carla_map = world.get_map()
    print(f"当前地图: {carla_map.name}")
    
    # ========== 步骤2: 设置同步模式（推荐）==========
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05  # 20 FPS
    world.apply_settings(settings)
    
    # ========== 步骤3: 生成车辆 ==========
    print("生成车辆...")
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
    spawn_points = carla_map.get_spawn_points()
    spawn_point = spawn_points[0]
    vehicle = world.spawn_actor(vehicle_bp, spawn_point)
    world.tick()
    print(f"车辆已生成: {vehicle.type_id}")
    
    # ========== 步骤4: 配置参数 ==========
    opt_dict = {
        'target_speed': 30.0,        # 30 km/h
        'sampling_radius': 2.0,      # 2米间距
        'offset': 0.0,               # 车道中心
        'follow_speed_limits': False,
    }
    
    # ========== 步骤5: 初始化LocalPlanner ==========
    print("初始化LocalPlanner...")
    local_planner = LocalPlanner(
        vehicle=vehicle,
        opt_dict=opt_dict,
        map_inst=carla_map
    )
    print("✓ LocalPlanner初始化完成")
    
    # ========== 步骤6: 创建GlobalPlanner（可选）==========
    print("初始化GlobalRoutePlanner...")
    global_planner = GlobalRoutePlanner(carla_map, 2.0)
    
    # ========== 步骤7: 规划路径 ==========
    print("规划路径...")
    start = vehicle.get_location()
    end = spawn_points[10].location  # 选择第10个生成点作为终点
    route = global_planner.trace_route(start, end)
    
    # ========== 步骤8: 设置路径到LocalPlanner ==========
    local_planner.set_global_plan(route)
    print(f"✓ 路径已设置，共 {len(route)} 个路点")
    
    # ========== 步骤9: 开始导航 ==========
    print("\n开始导航...\n")
    
    step = 0
    while not local_planner.done() and step < 100:
        world.tick()
        
        # 获取目标信息
        target_info = local_planner.run_step()
        
        if target_info['is_empty']:
            break
        
        # 外部控制器计算控制值（这里用简单示例）
        throttle = 0.5
        brake = 0.0
        steer = 0.0
        
        # 应用控制
        local_planner.apply_control(throttle, brake, steer)
        
        if step % 10 == 0:
            print(f"步骤 {step}: 剩余路点 {target_info['queue_length']}")
        
        step += 1
    
    print("\n✓ 导航完成")
    
    # ========== 步骤10: 清理 ==========
    print("清理资源...")
    vehicle.destroy()
    settings.synchronous_mode = False
    world.apply_settings(settings)
    print("完成！")


if __name__ == '__main__':
    main()
```

## ⚠️ 常见错误

### 错误1: 忘记传入车辆对象

```python
# ❌ 错误
local_planner = LocalPlanner()

# ✅ 正确
local_planner = LocalPlanner(vehicle)
```

### 错误2: 参数名写错

```python
# ❌ 错误
opt_dict = {
    'speed': 30.0,  # 错误的参数名
}

# ✅ 正确
opt_dict = {
    'target_speed': 30.0,  # 正确的参数名
}
```

### 错误3: 在车辆生成前初始化

```python
# ❌ 错误顺序
local_planner = LocalPlanner(vehicle)  # vehicle还不存在
vehicle = world.spawn_actor(vehicle_bp, spawn_point)

# ✅ 正确顺序
vehicle = world.spawn_actor(vehicle_bp, spawn_point)
local_planner = LocalPlanner(vehicle)  # 先生成车辆，再初始化
```

### 错误4: 传入错误类型的地图

```python
# ❌ 错误
map_string = "Town01"
local_planner = LocalPlanner(vehicle, map_inst=map_string)  # 错误类型

# ✅ 正确
carla_map = world.get_map()  # carla.Map对象
local_planner = LocalPlanner(vehicle, map_inst=carla_map)
```

## 📊 参数效果对比

### target_speed 效果

```python
# 低速（20 km/h）- 谨慎驾驶
local_planner = LocalPlanner(vehicle, opt_dict={'target_speed': 20.0})

# 中速（40 km/h）- 正常驾驶
local_planner = LocalPlanner(vehicle, opt_dict={'target_speed': 40.0})

# 高速（60 km/h）- 快速驾驶
local_planner = LocalPlanner(vehicle, opt_dict={'target_speed': 60.0})
```

### sampling_radius 效果

```python
# 密集路点（1米）- 精确跟踪，但计算量大
local_planner = LocalPlanner(vehicle, opt_dict={'sampling_radius': 1.0})

# 正常路点（2米）- 平衡
local_planner = LocalPlanner(vehicle, opt_dict={'sampling_radius': 2.0})

# 稀疏路点（4米）- 计算量小，但跟踪粗糙
local_planner = LocalPlanner(vehicle, opt_dict={'sampling_radius': 4.0})
```

### offset 效果

```python
# 靠左行驶
local_planner = LocalPlanner(vehicle, opt_dict={'offset': -1.0})

# 车道中心
local_planner = LocalPlanner(vehicle, opt_dict={'offset': 0.0})

# 靠右行驶
local_planner = LocalPlanner(vehicle, opt_dict={'offset': 1.0})
```

## 💡 最佳实践

### 1. 推荐配置（通用）

```python
opt_dict = {
    'target_speed': 30.0,
    'sampling_radius': 2.0,
    'offset': 0.0,
    'base_min_distance': 3.0,
    'distance_ratio': 0.5,
}
local_planner = LocalPlanner(vehicle, opt_dict=opt_dict, map_inst=carla_map)
```

### 2. 性能优化

```python
# 提前获取地图，避免重复调用
carla_map = world.get_map()

# 创建多个规划器时复用地图
planner1 = LocalPlanner(vehicle1, map_inst=carla_map)
planner2 = LocalPlanner(vehicle2, map_inst=carla_map)
```

### 3. 动态调整参数

```python
# 初始化
local_planner = LocalPlanner(vehicle)

# 运行时调整速度
local_planner.set_speed(40.0)  # 改为40 km/h

# 运行时调整偏移
local_planner.set_offset(1.0)  # 向右偏移

# 运行时启用速度限制
local_planner.follow_speed_limits(True)
```

## 🎓 总结

### 必需参数
- ✅ `vehicle` - CARLA车辆对象

### 可选参数
- ⭕ `opt_dict` - 配置字典（推荐提供）
- ⭕ `map_inst` - 地图对象（可选，性能优化）

### 最简单的初始化
```python
local_planner = LocalPlanner(vehicle)
```

### 推荐的初始化
```python
opt_dict = {'target_speed': 30.0, 'sampling_radius': 2.0}
local_planner = LocalPlanner(vehicle, opt_dict=opt_dict, map_inst=carla_map)
```

---

**现在你知道如何初始化 LocalPlanner 了！** 🚗💨

