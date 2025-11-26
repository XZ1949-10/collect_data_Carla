# target_road_option 详解

## 🎯 核心概念

`target_road_option` 表示的是：**从当前位置到达当前目标路点需要执行的道路动作**

- ✅ 是**当前目标**的信息（队列第一个路点）
- ❌ 不是未来所有目标的信息

## 📊 工作原理

### 路点队列结构

```python
_waypoints_queue = [
    (waypoint_0, RoadOption.LANEFOLLOW),     # 当前目标 ← target_road_option 是这个
    (waypoint_1, RoadOption.LANEFOLLOW),     # 下一个目标
    (waypoint_2, RoadOption.LEFT),           # 未来目标（左转）
    (waypoint_3, RoadOption.LANEFOLLOW),     # 更远的目标
    # ... 更多路点
]
```

### 代码实现

```python
# 在 local_planner 中：
self.target_waypoint, self.target_road_option = self._waypoints_queue[0]
#                                                                      ↑
#                                          取队列的第一个元素（索引0）= 当前目标
```

## 🔍 具体示例

### 示例1: 直行路段

```python
target_info = local_planner.run_step()

# 输出：
{
    'target_waypoint': Waypoint(x=100, y=200),
    'target_road_option': RoadOption.LANEFOLLOW,  # 当前：直行跟随车道
    'target_speed': 30.0,
    'queue_length': 100,
    'is_empty': False
}

# 解释：
# - 当前目标路点在 (x=100, y=200)
# - 到达这个路点需要"车道跟随"（直行）
# - 不包含下一个路点的信息
```

### 示例2: 即将左转

```python
# 第1步：当前还在直行
target_info = local_planner.run_step()
print(target_info['target_road_option'])  # 输出: LANEFOLLOW

# 第2步：继续前进
target_info = local_planner.run_step()
print(target_info['target_road_option'])  # 输出: LANEFOLLOW

# 第3步：到达路口，需要左转
target_info = local_planner.run_step()
print(target_info['target_road_option'])  # 输出: LEFT  ← 现在才显示左转

# 解释：
# - target_road_option 只显示"当前"需要执行的动作
# - 当队列中的左转路点成为第一个时，才会显示 LEFT
# - 每次只能看到一个动作，不是未来所有动作
```

### 示例3: 完整的转弯过程

```python
# 假设路点队列如下：
# [wp0:LANEFOLLOW, wp1:LANEFOLLOW, wp2:LANEFOLLOW, wp3:LEFT, wp4:LANEFOLLOW, ...]

# 步骤1: 车辆在直行
target_info = local_planner.run_step()
print(f"当前动作: {target_info['target_road_option'].name}")  
# 输出: LANEFOLLOW (wp0)

# 步骤2: 继续直行（wp0已通过，移除）
target_info = local_planner.run_step()
print(f"当前动作: {target_info['target_road_option'].name}")  
# 输出: LANEFOLLOW (wp1)

# 步骤3: 继续直行（wp1已通过，移除）
target_info = local_planner.run_step()
print(f"当前动作: {target_info['target_road_option'].name}")  
# 输出: LANEFOLLOW (wp2)

# 步骤4: 到达路口，需要左转（wp2已通过，移除）
target_info = local_planner.run_step()
print(f"当前动作: {target_info['target_road_option'].name}")  
# 输出: LEFT (wp3) ← 现在需要左转了

# 步骤5: 左转完成，继续直行（wp3已通过，移除）
target_info = local_planner.run_step()
print(f"当前动作: {target_info['target_road_option'].name}")  
# 输出: LANEFOLLOW (wp4)
```

## 🤔 如何获取未来目标的信息？

如果你需要**预判未来**的道路动作，可以使用以下方法：

### 方法1: 使用 `get_incoming_waypoint_and_direction()`

```python
# 获取当前目标（第0个）
target_info = local_planner.run_step()
current_action = target_info['target_road_option']
print(f"当前动作: {current_action.name}")

# 获取未来目标（第3个）
future_wp, future_action = local_planner.get_incoming_waypoint_and_direction(steps=3)
print(f"未来动作（3步后）: {future_action.name}")

# 示例输出：
# 当前动作: LANEFOLLOW
# 未来动作（3步后）: LEFT  ← 预判到3步后需要左转
```

### 方法2: 直接访问路点队列

```python
# 获取当前目标
target_info = local_planner.run_step()

# 获取路点队列
queue = local_planner.get_plan()

# 查看前5个路点的动作
print("未来5个动作:")
for i, (waypoint, road_option) in enumerate(list(queue)[:5]):
    print(f"  步骤{i}: {road_option.name}")

# 输出示例：
# 未来5个动作:
#   步骤0: LANEFOLLOW  ← 当前
#   步骤1: LANEFOLLOW
#   步骤2: LANEFOLLOW
#   步骤3: LEFT        ← 3步后需要左转
#   步骤4: LANEFOLLOW
```

### 方法3: 检查未来是否有转向

```python
def check_upcoming_turns(local_planner, look_ahead=10):
    """检查前方是否有转向动作"""
    queue = local_planner.get_plan()
    
    upcoming_actions = []
    for i, (waypoint, road_option) in enumerate(list(queue)[:look_ahead]):
        if road_option in [RoadOption.LEFT, RoadOption.RIGHT]:
            upcoming_actions.append((i, road_option.name))
    
    return upcoming_actions

# 使用
turns = check_upcoming_turns(local_planner, look_ahead=10)
if turns:
    for step, action in turns:
        print(f"⚠️  提前{step}步需要{action}")
else:
    print("✓ 前方10步都是直行")

# 输出示例：
# ⚠️  提前3步需要LEFT
# ⚠️  提前8步需要RIGHT
```

## 📋 对比总结

| 特性 | target_road_option | 未来路点信息 |
|------|-------------------|-------------|
| **范围** | 仅当前目标 | 可查看多个未来目标 |
| **获取方式** | `run_step()` 返回 | `get_incoming_waypoint_and_direction()` |
| **更新频率** | 每帧自动更新 | 按需查询 |
| **用途** | 立即控制决策 | 提前规划策略 |

## 💡 实际应用场景

### 场景1: 立即控制（使用 target_road_option）

```python
target_info = local_planner.run_step()

# 根据当前动作调整控制
if target_info['target_road_option'] == RoadOption.LEFT:
    # 现在需要左转
    max_speed = 20.0  # 降低速度
    print("正在左转")
elif target_info['target_road_option'] == RoadOption.LANEFOLLOW:
    # 正常直行
    max_speed = 30.0
    print("直行中")

throttle, brake, steer = controller.compute(
    target_info['target_waypoint'],
    max_speed
)
```

### 场景2: 提前规划（查看未来动作）

```python
# 获取当前动作
target_info = local_planner.run_step()
current_action = target_info['target_road_option']

# 查看未来动作（提前3步）
future_wp, future_action = local_planner.get_incoming_waypoint_and_direction(steps=3)

# 提前规划
if current_action == RoadOption.LANEFOLLOW and future_action == RoadOption.LEFT:
    print("提前准备左转：开始减速")
    max_speed = 25.0  # 提前减速
else:
    max_speed = 30.0  # 保持正常速度

throttle, brake, steer = controller.compute(
    target_info['target_waypoint'],
    max_speed
)
```

### 场景3: 复杂决策（分析整个队列）

```python
def analyze_route(local_planner, look_ahead=20):
    """分析前方路线"""
    queue = local_planner.get_plan()
    
    stats = {
        'total_waypoints': len(queue),
        'turns': 0,
        'lane_changes': 0,
        'next_turn_distance': None
    }
    
    for i, (waypoint, road_option) in enumerate(list(queue)[:look_ahead]):
        if road_option in [RoadOption.LEFT, RoadOption.RIGHT]:
            stats['turns'] += 1
            if stats['next_turn_distance'] is None:
                stats['next_turn_distance'] = i
        
        if road_option in [RoadOption.CHANGELANELEFT, RoadOption.CHANGELANERIGHT]:
            stats['lane_changes'] += 1
    
    return stats

# 使用
route_info = analyze_route(local_planner)
print(f"前方20步内:")
print(f"  转弯次数: {route_info['turns']}")
print(f"  变道次数: {route_info['lane_changes']}")
print(f"  下一个转弯距离: {route_info['next_turn_distance']} 步")

# 输出：
# 前方20步内:
#   转弯次数: 2
#   变道次数: 1
#   下一个转弯距离: 5 步
```

## ⚡ 快速参考

```python
# ✅ 获取当前目标动作
target_info = local_planner.run_step()
current_action = target_info['target_road_option']  # 当前需要执行的动作

# ✅ 预判未来动作（第N步）
future_wp, future_action = local_planner.get_incoming_waypoint_and_direction(steps=N)

# ✅ 查看所有未来动作
queue = local_planner.get_plan()
for i, (wp, action) in enumerate(queue):
    print(f"步骤{i}: {action.name}")
```

## 🎓 总结

1. **`target_road_option`** = **当前目标**的道路动作
   - 只包含队列第一个路点的信息
   - 表示"现在"需要执行什么动作
   - 每帧自动更新

2. **未来目标**的信息需要额外获取
   - 使用 `get_incoming_waypoint_and_direction(steps=N)`
   - 或直接访问路点队列 `get_plan()`

3. **实际应用**
   - 立即控制：使用 `target_road_option`
   - 提前规划：查看未来几步的动作
   - 复杂决策：分析整个路点队列

---

**记住：`target_road_option` 是"当前"的，不是"未来"的！** 🎯

