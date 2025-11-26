# agents 模块替换指南

## 📋 问题分析

在 `interactive_data_collection.py` 中，第537-538行使用了不存在的 `NavigationPlanner`：

```python
# ❌ 当前代码（第537-538行）
from navigation_planner import NavigationPlanner
self.collector.navigation_planner = NavigationPlanner(self.world, sampling_resolution=2.0)
```

## ✅ 正确的替换方案

### 1. **路线规划** - 已正确使用 ✅

**位置**：第117-120行、第363行

**当前代码**（已正确）：
```python
from agents.navigation.global_route_planner import GlobalRoutePlanner

# 初始化
self.route_planner = GlobalRoutePlanner(
    self.world.get_map(), 
    sampling_resolution=2.0
)

# 使用
route = self.route_planner.trace_route(start_point.location, end_point.location)
```

**说明**：
- ✅ 已经正确使用了 `GlobalRoutePlanner.trace_route()`
- ✅ 返回格式：`list[tuple[carla.Waypoint, RoadOption]]`
- ✅ 无需修改

---

### 2. **指令获取** - 需要替换 ❌

**位置**：第537-538行

**当前代码**（错误）：
```python
# ❌ 这个文件不存在
from navigation_planner import NavigationPlanner
self.collector.navigation_planner = NavigationPlanner(self.world, sampling_resolution=2.0)
```

**替换方案**：使用 `LocalPlanner` 获取指令

---

## 🔧 具体替换步骤

### 方案A：使用 `local_planner_info.py`（推荐 - 外部控制版本）

**适用场景**：需要自定义控制算法、机器学习、研究

```python
# 1. 导入
from agents.navigation.local_planner_info import LocalPlanner, RoadOption

# 2. 初始化（在 collect_data 方法中）
def collect_data(self, start_idx, end_idx, ...):
    # ... 现有代码 ...
    
    # 替换第537-538行
    # ❌ 删除这两行：
    # from navigation_planner import NavigationPlanner
    # self.collector.navigation_planner = NavigationPlanner(self.world, sampling_resolution=2.0)
    
    # ✅ 替换为：
    from agents.navigation.local_planner_info import LocalPlanner
    
    # 创建局部规划器
    opt_dict = {
        'target_speed': 30.0,           # 目标速度 (km/h)
        'sampling_radius': 2.0,         # 采样半径 (米)
        'offset': 0.0                   # 车道偏移 (米)
    }
    
    self.collector.local_planner = LocalPlanner(
        vehicle=self.collector.vehicle,
        opt_dict=opt_dict,
        map_inst=self.world.get_map()
    )
    
    # 设置全局路径（从 visualize_and_plan_route 返回的 route）
    if hasattr(self, '_current_route') and self._current_route:
        self.collector.local_planner.set_global_plan(
            self._current_route,
            stop_waypoint_creation=True,
            clean_queue=True
        )
    
    # ... 后续代码 ...
```

**获取指令的方法**：

```python
# 在数据收集循环中
while collecting:
    # 获取目标信息（包含指令）
    target_info = self.collector.local_planner.run_step()
    
    # 提取指令
    if not target_info['is_empty']:
        # 获取当前指令（RoadOption枚举）
        current_command = target_info['target_road_option']
        
        # RoadOption 映射到数值命令
        command_map = {
            RoadOption.LANEFOLLOW: 2.0,    # LANE_FOLLOW
            RoadOption.LEFT: 3.0,          # TURN_LEFT
            RoadOption.RIGHT: 4.0,         # TURN_RIGHT
            RoadOption.STRAIGHT: 5.0,       # GO_STRAIGHT
            RoadOption.CHANGELANELEFT: 2.0,  # 变道也算车道跟随
            RoadOption.CHANGELANERIGHT: 2.0,
            RoadOption.VOID: 0.0           # REACH_GOAL
        }
        
        command_value = command_map.get(current_command, 2.0)
        
        # 使用 command_value 进行数据收集
        # ...
```

---

### 方案B：使用原始 `local_planner.py`（简单版本）

**适用场景**：快速原型、标准导航

```python
# 1. 导入
from agents.navigation.local_planner import LocalPlanner, RoadOption

# 2. 初始化（在 collect_data 方法中）
def collect_data(self, start_idx, end_idx, ...):
    # ... 现有代码 ...
    
    # 替换第537-538行
    from agents.navigation.local_planner import LocalPlanner
    
    # 创建局部规划器（需要PID参数）
    opt_dict = {
        'target_speed': 30.0,
        'sampling_radius': 2.0,
        'lateral_control_dict': {
            'K_P': 1.95, 'K_I': 0.05, 'K_D': 0.2, 'dt': 0.05
        },
        'longitudinal_control_dict': {
            'K_P': 1.0, 'K_I': 0.05, 'K_D': 0, 'dt': 0.05
        }
    }
    
    self.collector.local_planner = LocalPlanner(
        vehicle=self.collector.vehicle,
        opt_dict=opt_dict,
        map_inst=self.world.get_map()
    )
    
    # 设置全局路径
    if hasattr(self, '_current_route') and self._current_route:
        self.collector.local_planner.set_global_plan(
            self._current_route,
            stop_waypoint_creation=True,
            clean_queue=True
        )
```

**获取指令的方法**：

```python
# 在数据收集循环中
while collecting:
    # 获取控制指令（原始版本直接返回VehicleControl）
    control = self.collector.local_planner.run_step()
    
    # 获取当前指令（从内部属性）
    current_command = self.collector.local_planner.target_road_option
    
    # 映射到数值命令
    command_map = {
        RoadOption.LANEFOLLOW: 2.0,
        RoadOption.LEFT: 3.0,
        RoadOption.RIGHT: 4.0,
        RoadOption.STRAIGHT: 5.0,
        RoadOption.VOID: 0.0
    }
    
    command_value = command_map.get(current_command, 2.0)
    
    # 使用 command_value 进行数据收集
    # ...
```

---

## 📝 完整修改示例

### 修改 `interactive_data_collection.py` 的 `collect_data` 方法

```python
def collect_data(self, start_idx, end_idx, num_frames=10000, 
                save_path='./carla_data', visualize=False):
    """收集数据（基于命令分段的交互式收集）"""
    
    # ... 前面的代码保持不变 ...
    
    # ========== 替换第537-538行 ==========
    # ❌ 删除：
    # from navigation_planner import NavigationPlanner
    # self.collector.navigation_planner = NavigationPlanner(self.world, sampling_resolution=2.0)
    
    # ✅ 替换为（方案A - 推荐）：
    from agents.navigation.local_planner_info import LocalPlanner, RoadOption
    
    # 创建局部规划器
    opt_dict = {
        'target_speed': 30.0,      # 目标速度 (km/h)
        'sampling_radius': 2.0,     # 采样半径 (米)
        'offset': 0.0               # 车道偏移 (米)
    }
    
    self.collector.local_planner = LocalPlanner(
        vehicle=self.collector.vehicle,
        opt_dict=opt_dict,
        map_inst=self.world.get_map()
    )
    
    # 设置全局路径（从 visualize_and_plan_route 返回的 route）
    # 需要修改 visualize_and_plan_route 方法，保存 route 到 self._current_route
    if hasattr(self, '_current_route') and self._current_route:
        self.collector.local_planner.set_global_plan(
            self._current_route,
            stop_waypoint_creation=True,
            clean_queue=True
        )
        print("✅ 全局路径已设置到局部规划器")
    
    # ... 后续代码保持不变 ...
```

### 修改 `visualize_and_plan_route` 方法，保存 route

```python
def visualize_and_plan_route(self, start_idx, end_idx, duration=30.0):
    """可视化并规划路径"""
    
    # ... 前面的代码保持不变 ...
    
    try:
        # ... 路径规划代码 ...
        route = self.route_planner.trace_route(start_point.location, end_point.location)
        
        # ✅ 新增：保存 route 供后续使用
        self._current_route = route
        
        # ... 后续代码保持不变 ...
        
        return True, route, markers_draw_time, duration
    except Exception as e:
        # ... 错误处理 ...
        return False, None, None, None
```

---

## 🔄 在数据收集循环中使用

假设 `CommandBasedDataCollector` 中有类似这样的循环：

```python
# 在 CommandBasedDataCollector.collect_data_interactive 中
def collect_data_interactive(self, max_frames, save_path, visualize):
    """交互式数据收集"""
    
    frame_count = 0
    current_command = None
    
    # 命令映射
    command_map = {
        RoadOption.LANEFOLLOW: 2.0,    # LANE_FOLLOW
        RoadOption.LEFT: 3.0,          # TURN_LEFT
        RoadOption.RIGHT: 4.0,         # TURN_RIGHT
        RoadOption.STRAIGHT: 5.0,      # GO_STRAIGHT
        RoadOption.CHANGELANELEFT: 2.0,
        RoadOption.CHANGELANERIGHT: 2.0,
        RoadOption.VOID: 0.0           # REACH_GOAL
    }
    
    while frame_count < max_frames:
        # 获取目标信息（包含指令）
        target_info = self.local_planner.run_step()
        
        if target_info['is_empty']:
            print("✅ 到达目的地")
            break
        
        # 提取当前指令
        road_option = target_info['target_road_option']
        command_value = command_map.get(road_option, 2.0)
        
        # 检测命令变化
        if command_value != current_command:
            current_command = command_value
            # 询问用户是否收集该命令段
            # ...
        
        # 收集数据
        # ...
        
        # 世界步进
        self.world.tick()
        frame_count += 1
```

---

## 📊 对比总结

| 功能 | 当前代码 | 替换方案 | 文件位置 |
|------|---------|---------|---------|
| **路线规划** | ✅ 已正确 | `GlobalRoutePlanner.trace_route()` | `agents/navigation/global_route_planner.py` |
| **指令获取** | ❌ 不存在 | `LocalPlanner.run_step()` | `agents/navigation/local_planner_info.py` |

---

## 🎯 关键点

1. **路线规划**：使用 `GlobalRoutePlanner.trace_route(start, end)` ✅
2. **指令获取**：使用 `LocalPlanner.run_step()` 获取 `target_road_option` ✅
3. **路径设置**：使用 `LocalPlanner.set_global_plan(route)` 设置全局路径 ✅
4. **命令映射**：将 `RoadOption` 枚举映射到数值命令（2.0/3.0/4.0/5.0）✅

---

## 💡 推荐方案

**推荐使用方案A**（`local_planner_info.py`）：
- ✅ 更灵活，支持外部控制
- ✅ 返回详细信息（路点、速度、队列长度等）
- ✅ 适合数据收集场景
- ✅ 不依赖PID控制器

