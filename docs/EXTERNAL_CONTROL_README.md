# Local Planner 外部控制版本说明

## 📋 概述

本文档说明如何使用修改后的 `LocalPlanner`（外部控制版本），该版本删除了内置的 PID 控制器，改为由外部提供控制指令。

## 🔄 主要修改

### 删除的内容
- ✅ PID 控制器相关代码 (`VehiclePIDController`)
- ✅ PID 参数配置（横向和纵向控制参数）
- ✅ `controller.py` 的导入
- ✅ 自动计算油门/刹车/转向的逻辑

### 保留的功能
- ✅ 路点队列管理
- ✅ 自动生成路点
- ✅ 全局路径设置
- ✅ 路点清理逻辑
- ✅ 速度限制跟随
- ✅ 车道偏移设置

### 新增的功能
- ✅ `run_step()` 现在返回目标路点信息而不是控制指令
- ✅ 新方法 `apply_control()` 用于接收外部控制值
- ✅ 新方法 `get_target_waypoint_info()` 获取当前目标信息

## 🎯 使用方法

### 1. 基本工作流程

```python
# 创建局部规划器（无需PID参数）
opt_dict = {
    'target_speed': 30.0,
    'sampling_radius': 2.0,
}
local_planner = LocalPlanner(vehicle, opt_dict=opt_dict, map_inst=carla_map)

# 设置全局路径
local_planner.set_global_plan(route)

# 导航循环
while not local_planner.done():
    # 步骤1: 获取目标路点信息
    target_info = local_planner.run_step()
    
    # 步骤2: 使用外部控制器计算控制值
    throttle, brake, steer = external_controller.compute(
        target_waypoint=target_info['target_waypoint'],
        target_speed=target_info['target_speed'],
        vehicle=vehicle
    )
    
    # 步骤3: 应用控制
    local_planner.apply_control(throttle, brake, steer)
    
    world.tick()
```

### 2. run_step() 返回值

```python
target_info = local_planner.run_step()

# target_info 字典包含：
{
    'target_waypoint': carla.Waypoint,  # 目标路点对象
    'target_road_option': RoadOption,   # 道路动作（左转/右转/直行等）
    'target_speed': float,              # 建议目标速度 (km/h)
    'queue_length': int,                # 剩余路点数量
    'is_empty': bool                    # 队列是否为空
}
```

### 3. 应用控制的两种方式

#### 方式1: 使用 apply_control() 方法（推荐）
```python
throttle, brake, steer = external_controller.compute(...)
local_planner.apply_control(throttle, brake, steer)
```

#### 方式2: 手动创建 VehicleControl
```python
throttle, brake, steer = external_controller.compute(...)

control = carla.VehicleControl()
control.throttle = throttle
control.brake = brake
control.steer = steer
vehicle.apply_control(control)
```

## 🎨 外部控制器示例

### 示例1: 简单控制器

```python
class SimpleExternalController:
    def __init__(self, vehicle):
        self.vehicle = vehicle
    
    def compute(self, target_waypoint, target_speed):
        """
        计算控制指令
        
        :return: (throttle, brake, steer) 元组
        """
        if target_waypoint is None:
            return (0.0, 1.0, 0.0)  # 紧急停车
        
        # 获取车辆当前状态
        current_speed = get_vehicle_speed(self.vehicle)
        
        # 纵向控制（简单规则）
        if current_speed < target_speed - 5:
            throttle, brake = 0.7, 0.0
        elif current_speed < target_speed:
            throttle, brake = 0.3, 0.0
        elif current_speed < target_speed + 5:
            throttle, brake = 0.0, 0.2
        else:
            throttle, brake = 0.0, 0.5
        
        # 横向控制（简单规则）
        steer = compute_steering(self.vehicle, target_waypoint)
        
        return (throttle, brake, steer)
```

### 示例2: PID 控制器

```python
class PIDExternalController:
    def __init__(self, vehicle):
        self.vehicle = vehicle
        
        # PID 参数
        self.speed_kp = 1.0
        self.speed_ki = 0.05
        self.speed_kd = 0.1
        
        self.steer_kp = 2.0
        self.steer_ki = 0.0
        self.steer_kd = 0.3
        
        # 误差积分
        self.speed_error_integral = 0.0
        self.steer_error_integral = 0.0
        
        # 上一次误差
        self.speed_last_error = 0.0
        self.steer_last_error = 0.0
        
        self.dt = 0.05
    
    def compute(self, target_waypoint, target_speed):
        """使用PID计算控制指令"""
        if target_waypoint is None:
            return (0.0, 1.0, 0.0)
        
        # 纵向PID
        current_speed = get_vehicle_speed(self.vehicle)
        speed_error = target_speed - current_speed
        
        self.speed_error_integral += speed_error * self.dt
        speed_derivative = (speed_error - self.speed_last_error) / self.dt
        
        acceleration = (self.speed_kp * speed_error + 
                       self.speed_ki * self.speed_error_integral + 
                       self.speed_kd * speed_derivative)
        
        self.speed_last_error = speed_error
        
        # 转换为油门/刹车
        if acceleration >= 0:
            throttle = min(acceleration, 0.75)
            brake = 0.0
        else:
            throttle = 0.0
            brake = min(abs(acceleration), 0.5)
        
        # 横向PID
        angle_error = compute_angle_error(self.vehicle, target_waypoint)
        
        self.steer_error_integral += angle_error * self.dt
        steer_derivative = (angle_error - self.steer_last_error) / self.dt
        
        steer = (self.steer_kp * angle_error + 
                self.steer_ki * self.steer_error_integral + 
                self.steer_kd * steer_derivative)
        
        self.steer_last_error = angle_error
        steer = np.clip(steer, -0.8, 0.8)
        
        return (throttle, brake, steer)
```

### 示例3: 基于机器学习的控制器

```python
class MLExternalController:
    def __init__(self, vehicle, model_path):
        self.vehicle = vehicle
        self.model = load_trained_model(model_path)
    
    def compute(self, target_waypoint, target_speed):
        """使用机器学习模型计算控制指令"""
        if target_waypoint is None:
            return (0.0, 1.0, 0.0)
        
        # 提取特征
        features = self.extract_features(target_waypoint, target_speed)
        
        # 模型预测
        throttle, brake, steer = self.model.predict(features)
        
        return (throttle, brake, steer)
    
    def extract_features(self, target_waypoint, target_speed):
        """提取特征向量"""
        vehicle_location = self.vehicle.get_location()
        vehicle_velocity = self.vehicle.get_velocity()
        
        # 构建特征向量
        features = [
            target_waypoint.transform.location.x - vehicle_location.x,
            target_waypoint.transform.location.y - vehicle_location.y,
            vehicle_velocity.x,
            vehicle_velocity.y,
            target_speed,
            # ... 更多特征
        ]
        
        return np.array(features)
```

## 📊 对比：修改前 vs 修改后

| 特性 | 修改前（内置PID） | 修改后（外部控制） |
|------|-------------------|-------------------|
| **PID控制器** | 内置 | 无（由外部提供） |
| **run_step() 返回** | VehicleControl 对象 | 目标路点信息字典 |
| **控制计算** | 自动 | 外部提供 |
| **灵活性** | 低（固定PID） | 高（任意控制算法） |
| **适用场景** | 标准导航 | 研究、定制、ML |
| **参数数量** | 多（PID参数） | 少（仅路点管理） |
| **依赖** | controller.py | 无 |

## 🚀 运行示例

### 1. 运行完整示例

```bash
# 1. 启动CARLA服务器
./CarlaUE4.sh

# 2. 运行示例脚本
python external_control_example.py
```

### 2. 示例输出

```
=== 外部控制器示例 ===

正在连接CARLA服务器...
当前地图: Town01

正在生成车辆...
车辆已生成在: Location(x=150.0, y=199.0, z=0.5)

初始化规划器...
  ✓ 规划器已就绪

创建外部控制器...
  ✓ 使用 PIDExternalController

规划路径...
起点: (x=150.0, y=199.0)
终点: (x=50.0, y=50.0)
距离: 180.28 米
路径已设置，共 92 个路点

开始自动驾驶...

步数:     0 | 速度:   0.0 km/h | 油门: 0.75 | 刹车: 0.00 | 转向: +0.02 | 动作: LANEFOLLOW     | 剩余路点:   92 | 距目标:  180.3m
步数:    20 | 速度:  12.3 km/h | 油门: 0.50 | 刹车: 0.00 | 转向: -0.05 | 动作: LANEFOLLOW     | 剩余路点:   87 | 距目标:  165.2m
...
✓ 已到达目的地！
```

## 🎓 使用场景

### 1. 研究场景
- ✅ 测试新的控制算法
- ✅ 对比不同控制策略
- ✅ 收集控制数据

### 2. 机器学习场景
- ✅ 训练强化学习智能体
- ✅ 端到端学习
- ✅ 模仿学习

### 3. 定制场景
- ✅ 特殊车辆控制
- ✅ 复杂环境适应
- ✅ 多目标优化

### 4. 集成场景
- ✅ 与其他系统集成
- ✅ 硬件在环测试
- ✅ 分布式控制

## 🔧 参数配置

### LocalPlanner 参数（简化版）

```python
opt_dict = {
    # 速度参数
    'target_speed': 30.0,           # 目标速度 (km/h)
    
    # 路点采样参数
    'sampling_radius': 2.0,         # 路点间距 (米)
    
    # 车道偏移
    'offset': 0.0,                  # 车道偏移 (米)
    
    # 路点清理参数
    'base_min_distance': 3.0,       # 基础最小距离 (米)
    'distance_ratio': 0.5,          # 距离比率
    
    # 速度限制
    'follow_speed_limits': False    # 是否跟随速度限制
}
```

## 💡 最佳实践

### 1. 控制器设计
```python
# 始终检查目标路点是否为None
if target_info['is_empty'] or target_info['target_waypoint'] is None:
    return (0.0, 1.0, 0.0)  # 紧急停车

# 限制控制值范围
throttle = np.clip(throttle, 0.0, 1.0)
brake = np.clip(brake, 0.0, 1.0)
steer = np.clip(steer, -1.0, 1.0)
```

### 2. 性能优化
```python
# 缓存频繁计算的值
class OptimizedController:
    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.cached_transform = None
        self.cache_valid_frames = 0
    
    def compute(self, target_waypoint, target_speed):
        # 每5帧更新一次缓存
        if self.cache_valid_frames <= 0:
            self.cached_transform = self.vehicle.get_transform()
            self.cache_valid_frames = 5
        
        self.cache_valid_frames -= 1
        
        # 使用缓存的transform进行计算
        # ...
```

### 3. 安全检查
```python
# 添加安全限制
MAX_SPEED = 60.0  # km/h
MIN_DISTANCE_TO_STOP = 5.0  # meters

def safe_compute(self, target_waypoint, target_speed):
    # 限制最大速度
    target_speed = min(target_speed, MAX_SPEED)
    
    # 距离太近时强制刹车
    if target_waypoint is not None:
        distance = self.vehicle.get_location().distance(
            target_waypoint.transform.location
        )
        if distance < MIN_DISTANCE_TO_STOP:
            return (0.0, 1.0, 0.0)
    
    # 正常计算
    return self.compute_control(target_waypoint, target_speed)
```

## 📚 API 参考

### LocalPlanner 主要方法

#### `__init__(vehicle, opt_dict={}, map_inst=None)`
初始化局部规划器

#### `run_step(debug=False)`
更新路点队列并返回目标信息
- 返回: `dict` - 目标路点信息字典

#### `apply_control(throttle, brake, steer)`
应用外部控制值到车辆
- `throttle`: float [0.0, 1.0]
- `brake`: float [0.0, 1.0]
- `steer`: float [-1.0, 1.0]

#### `get_target_waypoint_info()`
获取当前目标路点信息（不更新队列）
- 返回: `dict` - 目标路点信息字典

#### `set_global_plan(current_plan, ...)`
设置全局路径

#### `done()`
检查是否到达目的地
- 返回: `bool`

## 🔗 相关文件

- **修改后的规划器**: `agents/navigation/local_planner - 副本.py`
- **使用示例**: `external_control_example.py`
- **本说明文档**: `EXTERNAL_CONTROL_README.md`

---

**现在你可以自由地实现任何控制算法，不再受限于内置的PID控制器！** 🎉

