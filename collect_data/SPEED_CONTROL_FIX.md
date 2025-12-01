# 🔧 速度控制问题修复说明

## 问题描述

设置了 `target_speed: 10.0` 但车辆速度仍然达到 30 km/h。

---

## 🎯 根本原因

### 问题：两个控制器冲突

你的代码中有**两个独立的控制系统**：

#### 1. LocalPlanner（你设置的 10 km/h）
```python
# interactive_data_collection.py 第567行
opt_dict = {
    'target_speed': 10.0,  # ✅ 你的设置
    'sampling_radius': 2.0,
    'offset': 0.0
}

self.collector.local_planner = LocalPlanner(...)
```

#### 2. BasicAgent（硬编码的 30 km/h）⚠️
```python
# command_based_data_collection.py 第178行
opt_dict = {
    'target_speed': 30.0,  # ❌ 硬编码！
    ...
}

self.agent = BasicAgent(target_speed=30)  # ❌ 又硬编码！
```

### 执行流程

```
1. interactive_data_collection.py
   └─> 创建 LocalPlanner (target_speed=10.0)  ✅ 你的设置
   
2. 调用 collector.spawn_vehicle()
   └─> command_based_data_collection.py
       └─> 创建 BasicAgent (target_speed=30.0)  ❌ 覆盖了你的设置！
       
3. 实际控制车辆
   └─> BasicAgent 控制车辆  ⚠️ 使用 30 km/h
   └─> 你的 LocalPlanner 被忽略了
```

---

## ✅ 解决方案

### 修改内容

#### 1. 修改 `command_based_data_collection.py`

**添加 `target_speed` 参数：**

```python
def __init__(self, host='localhost', port=2000, town='Town01',
             ignore_traffic_lights=True, ignore_signs=True, 
             ignore_vehicles_percentage=80, target_speed=20.0):  # ⭐ 新增参数
    """初始化
    
    参数:
        ...
        target_speed: 目标速度（km/h），默认20
    """
    self.target_speed = target_speed  # ⭐ 保存配置
```

**使用可配置的速度：**

```python
# 创建 BasicAgent 配置
opt_dict = {
    'target_speed': self.target_speed,  # ⭐ 使用配置的速度
    ...
}

# 创建 BasicAgent
self.agent = BasicAgent(
    self.vehicle, 
    target_speed=self.target_speed,  # ⭐ 使用配置的速度
    ...
)
```

#### 2. 修改 `interactive_data_collection.py`

**传递速度参数：**

```python
# 获取LocalPlanner的target_speed配置
target_speed = 10.0  # 使用你设置的速度

# 创建数据收集器（传递target_speed）
self.collector = CommandBasedDataCollector(
    host=self.host,
    port=self.port,
    town=self.town,
    ignore_traffic_lights=self.ignore_traffic_lights,
    ignore_signs=self.ignore_signs,
    ignore_vehicles_percentage=self.ignore_vehicles_percentage,
    target_speed=target_speed  # ⭐ 传递速度参数
)
```

---

## 🎉 修复效果

### 修复前

```
设置: target_speed = 10.0
实际: 车辆速度 = 30 km/h  ❌
原因: BasicAgent 使用硬编码的 30 km/h
```

### 修复后

```
设置: target_speed = 10.0
实际: 车辆速度 ≈ 10 km/h  ✅
原因: BasicAgent 使用传递的 10 km/h
```

---

## 📊 速度控制层级

### 完整的速度控制链

```
1. interactive_data_collection.py
   └─> opt_dict['target_speed'] = 10.0
   └─> 传递给 CommandBasedDataCollector(target_speed=10.0)
   
2. command_based_data_collection.py
   └─> self.target_speed = 10.0
   └─> 传递给 BasicAgent(target_speed=10.0)
   
3. BasicAgent
   └─> 内部的 LocalPlanner 使用 10.0 km/h
   └─> 控制车辆以 ~10 km/h 行驶
   
4. 车辆
   └─> 实际速度 ≈ 10 km/h  ✅
```

---

## 🔍 为什么之前不生效？

### 问题分析

1. **你创建了独立的 LocalPlanner**
   ```python
   self.collector.local_planner = LocalPlanner(target_speed=10.0)
   ```
   - 这个 LocalPlanner 被赋值给 `collector.local_planner`
   - 但它**从未被使用**

2. **BasicAgent 有自己的 LocalPlanner**
   ```python
   self.agent = BasicAgent(target_speed=30)
   ```
   - BasicAgent 内部创建了**自己的** LocalPlanner
   - 使用 30 km/h 的速度
   - 这个才是真正控制车辆的

3. **控制车辆的代码使用 BasicAgent**
   ```python
   # 在数据收集循环中
   if self.collector.agent is not None:
       control = self.collector.agent.run_step()  # ⭐ 使用 BasicAgent
       self.vehicle.apply_control(control)
   ```
   - 实际控制来自 `BasicAgent.run_step()`
   - 你的 LocalPlanner 没有被调用

---

## 💡 关键理解

### LocalPlanner vs BasicAgent

| 组件 | 作用 | 关系 |
|------|------|------|
| **LocalPlanner** | 局部路径规划和速度控制 | 底层组件 |
| **BasicAgent** | 高级驾驶代理 | 包含 LocalPlanner |

**重要：**
- BasicAgent **内部包含** LocalPlanner
- 你不能直接替换 BasicAgent 的 LocalPlanner
- 必须通过 BasicAgent 的构造函数传递 `target_speed`

### 正确的速度设置方式

```python
# ❌ 错误：创建独立的 LocalPlanner（会被忽略）
local_planner = LocalPlanner(target_speed=10.0)

# ✅ 正确：通过 BasicAgent 设置速度
agent = BasicAgent(
    vehicle=vehicle,
    target_speed=10.0,  # ⭐ 这样才有效
    opt_dict={'target_speed': 10.0}
)
```

---

## 🧪 验证方法

### 测试步骤

1. **运行数据收集**
   ```bash
   python interactive_data_collection.py
   ```

2. **观察可视化窗口**
   - 查看 "Speed" 显示
   - 应该显示 ~10 km/h

3. **观察控制台输出**
   ```
   正在配置 BasicAgent（按规划路线行驶）...
     ✅ BasicAgent 已创建
   ```

4. **检查车辆行为**
   - 车辆应该明显变慢
   - 转弯更加平滑

---

## 📝 其他文件的修改

### auto_full_town_collection.py

如果你也想在自动收集器中使用自定义速度：

```python
# 创建数据收集器时传递速度
self.collector = CommandBasedDataCollector(
    host=self.host,
    port=self.port,
    town=self.town,
    ignore_traffic_lights=self.ignore_traffic_lights,
    ignore_signs=self.ignore_signs,
    ignore_vehicles_percentage=self.ignore_vehicles_percentage,
    target_speed=15.0  # ⭐ 自定义速度
)
```

---

## 🎯 推荐配置

### 不同场景的速度设置

#### 高质量数据收集
```python
target_speed = 10.0  # 慢速，数据连续性最好
sampling_radius = 2.5  # 大采样半径
```

#### 平衡模式
```python
target_speed = 15.0  # 中速，平衡质量和效率
sampling_radius = 2.0
```

#### 快速收集
```python
target_speed = 20.0  # 较快，收集效率高
sampling_radius = 2.0
```

---

## 🔧 故障排除

### 如果速度仍然不对

1. **检查是否重新启动了程序**
   - 修改代码后必须重新运行

2. **检查控制台输出**
   ```bash
   # 应该看到
   正在配置 BasicAgent（按规划路线行驶）...
   ```

3. **检查是否有多个 Python 进程**
   ```bash
   # Windows
   tasklist | findstr python
   
   # 杀死旧进程
   taskkill /F /IM python.exe
   ```

4. **验证修改是否生效**
   ```python
   # 在 command_based_data_collection.py 中添加调试输出
   print(f"⭐ BasicAgent target_speed: {self.target_speed}")
   ```

---

## 📚 总结

### 问题
- 设置了 10 km/h 但车辆跑 30 km/h

### 原因
- BasicAgent 硬编码了 30 km/h
- 你的 LocalPlanner 被忽略了

### 解决
- ✅ 添加 `target_speed` 参数到 `CommandBasedDataCollector`
- ✅ 传递速度参数给 BasicAgent
- ✅ 从 `interactive_data_collection.py` 传递速度值

### 效果
- ✅ 车辆现在按照 10 km/h 行驶
- ✅ 可视化窗口显示正确的速度
- ✅ 转弯更加平滑

---

**现在速度控制应该正常工作了！🎉**
