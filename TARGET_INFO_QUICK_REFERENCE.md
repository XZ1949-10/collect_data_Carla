# target_info 返回值快速参考

## 📋 返回值结构

```python
target_info = local_planner.run_step()

# target_info 是一个字典，包含以下键值对：
{
    'target_waypoint': carla.Waypoint,  # 目标路点对象（或 None）
    'target_road_option': RoadOption,   # 道路动作枚举
    'target_speed': float,              # 建议目标速度 (km/h)
    'queue_length': int,                # 剩余路点数量
    'is_empty': bool                    # 队列是否为空
}
```

## 🎯 快速示例

### 示例1: 基本使用

```python
# 获取目标信息
target_info = local_planner.run_step()

# 访问各个字段
waypoint = target_info['target_waypoint']
action = target_info['target_road_option']
speed = target_info['target_speed']
remaining = target_info['queue_length']
is_empty = target_info['is_empty']

print(f"目标速度: {speed} km/h")
print(f"道路动作: {action.name}")
print(f"剩余路点: {remaining}")
```

**输出示例:**
```
目标速度: 30.0 km/h
道路动作: LANEFOLLOW
剩余路点: 92
```

### 示例2: 检查是否到达目的地

```python
target_info = local_planner.run_step()

if target_info['is_empty']:
    print("✓ 已到达目的地！")
    # 停车
    local_planner.apply_control(0.0, 1.0, 0.0)
else:
    # 继续导航
    throttle, brake, steer = controller.compute(...)
    local_planner.apply_control(throttle, brake, steer)
```

### 示例3: 提取路点位置

```python
target_info = local_planner.run_step()

if not target_info['is_empty']:
    waypoint = target_info['target_waypoint']
    
    # 获取位置
    location = waypoint.transform.location
    print(f"目标位置: x={location.x:.2f}, y={location.y:.2f}, z={location.z:.2f}")
    
    # 获取朝向
    rotation = waypoint.transform.rotation
    print(f"目标朝向: yaw={rotation.yaw:.2f}°")
    
    # 计算距离
    vehicle_location = vehicle.get_location()
    distance = vehicle_location.distance(location)
    print(f"距离: {distance:.2f} 米")
```

**输出示例:**
```
目标位置: x=152.35, y=195.67, z=0.50
目标朝向: yaw=180.23°
距离: 3.45 米
```

### 示例4: 根据道路动作调整策略

```python
target_info = local_planner.run_step()

if target_info['is_empty']:
    return

# 根据道路动作调整目标速度
road_option = target_info['target_road_option']
target_speed = target_info['target_speed']

if road_option == RoadOption.LEFT:
    adjusted_speed = target_speed * 0.7  # 左转减速30%
    print("左转：减速")
elif road_option == RoadOption.RIGHT:
    adjusted_speed = target_speed * 0.8  # 右转减速20%
    print("右转：减速")
elif road_option == RoadOption.LANEFOLLOW:
    adjusted_speed = target_speed  # 保持速度
    print("直行：保持速度")

# 使用调整后的速度
throttle, brake, steer = controller.compute(
    target_info['target_waypoint'], 
    adjusted_speed
)
```

### 示例5: 完整的导航循环

```python
while not local_planner.done():
    # 1. 获取目标信息
    target_info = local_planner.run_step()
    
    # 2. 检查队列状态
    if target_info['is_empty']:
        print("到达目的地")
        break
    
    # 3. 提取关键信息
    target_waypoint = target_info['target_waypoint']
    target_speed = target_info['target_speed']
    road_option = target_info['target_road_option']
    
    # 4. 计算控制指令
    throttle, brake, steer = controller.compute(
        target_waypoint,
        target_speed,
        vehicle
    )
    
    # 5. 应用控制
    local_planner.apply_control(throttle, brake, steer)
    
    # 6. 打印状态
    print(f"速度: {get_speed(vehicle):.1f} km/h | "
          f"动作: {road_option.name} | "
          f"剩余: {target_info['queue_length']}")
    
    world.tick()
```

### 示例6: 安全检查

```python
target_info = local_planner.run_step()

# 检查1: 队列是否为空
if target_info['is_empty']:
    print("⚠️  队列为空")
    local_planner.apply_control(0.0, 1.0, 0.0)
    return

# 检查2: 路点是否有效
if target_info['target_waypoint'] is None:
    print("⚠️  路点无效")
    local_planner.apply_control(0.0, 1.0, 0.0)
    return

# 检查3: 队列长度警告
if target_info['queue_length'] < 10:
    print(f"⚠️  剩余路点较少: {target_info['queue_length']}")

# 检查4: 速度是否合理
if target_info['target_speed'] <= 0:
    target_speed = 20.0  # 使用默认值
else:
    target_speed = target_info['target_speed']

# 安全地计算控制
throttle, brake, steer = controller.compute(
    target_info['target_waypoint'],
    target_speed
)
```

### 示例7: 提取所有 RoadOption 值

```python
target_info = local_planner.run_step()

road_option = target_info['target_road_option']

# RoadOption 枚举值
if road_option == RoadOption.VOID:
    print("动作: 无效/未定义")
elif road_option == RoadOption.LEFT:
    print("动作: 左转")
elif road_option == RoadOption.RIGHT:
    print("动作: 右转")
elif road_option == RoadOption.STRAIGHT:
    print("动作: 直行")
elif road_option == RoadOption.LANEFOLLOW:
    print("动作: 车道跟随")
elif road_option == RoadOption.CHANGELANELEFT:
    print("动作: 向左变道")
elif road_option == RoadOption.CHANGELANERIGHT:
    print("动作: 向右变道")

# 或者直接打印名称
print(f"动作: {road_option.name}")  # 输出: LANEFOLLOW
print(f"值: {road_option.value}")   # 输出: 4
```

### 示例8: 传递给外部控制器

```python
target_info = local_planner.run_step()

if not target_info['is_empty']:
    # 方式1: 直接传递整个字典
    control = external_controller.compute(target_info, vehicle)
    
    # 方式2: 传递单个参数
    control = external_controller.compute(
        waypoint=target_info['target_waypoint'],
        speed=target_info['target_speed'],
        action=target_info['target_road_option']
    )
    
    # 方式3: 提取为独立变量
    waypoint = target_info['target_waypoint']
    speed = target_info['target_speed']
    control = external_controller.compute(waypoint, speed, vehicle)
    
    # 应用控制
    throttle, brake, steer = control
    local_planner.apply_control(throttle, brake, steer)
```

## 📊 字段详解

### 1. `target_waypoint` (carla.Waypoint 或 None)

目标路点对象，包含位置、朝向、车道信息等

```python
waypoint = target_info['target_waypoint']

if waypoint is not None:
    # 位置
    location = waypoint.transform.location  # (x, y, z)
    rotation = waypoint.transform.rotation  # (pitch, yaw, roll)
    
    # 车道信息
    lane_id = waypoint.lane_id
    lane_width = waypoint.lane_width
    road_id = waypoint.road_id
    
    # 判断
    is_junction = waypoint.is_junction
```

### 2. `target_road_option` (RoadOption 枚举)

道路动作类型

```python
road_option = target_info['target_road_option']

# 可能的值:
# RoadOption.VOID = -1           # 无效
# RoadOption.LEFT = 1            # 左转
# RoadOption.RIGHT = 2           # 右转
# RoadOption.STRAIGHT = 3        # 直行
# RoadOption.LANEFOLLOW = 4      # 车道跟随
# RoadOption.CHANGELANELEFT = 5  # 向左变道
# RoadOption.CHANGELANERIGHT = 6 # 向右变道

# 获取名称
name = road_option.name  # "LANEFOLLOW"

# 获取数值
value = road_option.value  # 4
```

### 3. `target_speed` (float)

建议的目标速度（单位：km/h）

```python
target_speed = target_info['target_speed']  # 例如: 30.0

# 可以根据需要调整
adjusted_speed = target_speed * 0.8  # 减速20%
adjusted_speed = min(target_speed, 50.0)  # 限制最大速度
```

### 4. `queue_length` (int)

剩余路点数量

```python
remaining = target_info['queue_length']  # 例如: 92

if remaining < 10:
    print("即将到达目的地")
elif remaining < 50:
    print("已行驶过半")
else:
    print(f"还有 {remaining} 个路点")
```

### 5. `is_empty` (bool)

队列是否为空（是否到达目的地）

```python
is_empty = target_info['is_empty']

if is_empty:
    print("✓ 已到达目的地")
    # 执行停车
else:
    print("○ 继续导航")
    # 继续控制
```

## 🔍 常见用法模式

### 模式1: 防御性编程

```python
target_info = local_planner.run_step()

# 始终先检查 is_empty
if target_info.get('is_empty', True):
    # 安全停车
    return (0.0, 1.0, 0.0)

# 再检查 waypoint
waypoint = target_info.get('target_waypoint')
if waypoint is None:
    # 安全停车
    return (0.0, 1.0, 0.0)

# 现在可以安全使用
# ...
```

### 模式2: 简洁访问

```python
# 一次性提取所有需要的值
wp = target_info['target_waypoint']
opt = target_info['target_road_option']
spd = target_info['target_speed']
qlen = target_info['queue_length']

# 或使用局部变量
target_waypoint = target_info['target_waypoint']
target_speed = target_info['target_speed']
```

### 模式3: 日志记录

```python
target_info = local_planner.run_step()

# 记录详细信息
log_data = {
    'timestamp': time.time(),
    'waypoint_location': str(target_info['target_waypoint'].transform.location),
    'road_option': target_info['target_road_option'].name,
    'target_speed': target_info['target_speed'],
    'queue_length': target_info['queue_length'],
}

print(json.dumps(log_data))
```

## 💡 最佳实践

1. **始终检查 `is_empty`**
   ```python
   if target_info['is_empty']:
       # 处理到达目的地的情况
   ```

2. **检查 `target_waypoint` 是否为 None**
   ```python
   if target_info['target_waypoint'] is None:
       # 处理无效路点的情况
   ```

3. **监控 `queue_length`**
   ```python
   if target_info['queue_length'] < 10:
       # 提前准备停车
   ```

4. **根据 `target_road_option` 调整策略**
   ```python
   if target_info['target_road_option'] in [RoadOption.LEFT, RoadOption.RIGHT]:
       # 转弯时减速
   ```

## 📖 完整示例文件

查看 `target_info_usage_example.py` 获取 8 个详细示例：
1. 基本使用
2. 检查队列状态
3. 提取路点位置信息
4. 根据道路动作调整控制
5. 完整的导航循环
6. 使用字典解包
7. 错误处理
8. 与其他系统集成

---

**快速上手：** 复制示例5的代码，根据需要修改控制器即可！ 🚀

