# 数据收集配置指南

## 配置文件说明

配置文件 `auto_collection_config.json` 包含所有数据收集的参数设置。

---

## 📋 配置项详解

### 1. CARLA服务器设置 (`carla_settings`)

```json
"carla_settings": {
    "host": "localhost",
    "port": 2000,
    "town": "Town01"
}
```

- **host**: CARLA服务器地址
  - 本地运行使用 `localhost`
  - 远程服务器使用IP地址

- **port**: CARLA服务器端口
  - 默认: `2000`
  - 如果运行多个CARLA实例，需要使用不同端口

- **town**: 地图名称
  - 可选值: `Town01`, `Town02`, ..., `Town10`
  - 推荐: `Town01` (最稳定)

---

### 2. 交通规则配置 (`traffic_rules`)

```json
"traffic_rules": {
    "ignore_traffic_lights": true,
    "ignore_signs": true,
    "ignore_vehicles_percentage": 80
}
```

- **ignore_traffic_lights**: 是否忽略红绿灯
  - `true`: 车辆不会在红灯前停车（推荐，提高收集效率）
  - `false`: 车辆遵守红绿灯

- **ignore_signs**: 是否忽略停车标志
  - `true`: 车辆不会在STOP标志前停车（推荐）
  - `false`: 车辆遵守停车标志

- **ignore_vehicles_percentage**: 忽略其他车辆的百分比
  - 范围: `0-100`
  - `0`: 完全避让其他车辆
  - `100`: 完全忽略其他车辆
  - 推荐: `80` (基本忽略但保留一些交互)

---

### 3. 世界环境配置 (`world_settings`)

```json
"world_settings": {
    "spawn_npc_vehicles": false,
    "num_npc_vehicles": 0,
    "spawn_npc_walkers": false,
    "num_npc_walkers": 0
}
```

- **spawn_npc_vehicles**: 是否生成NPC车辆
  - `false`: 场景中只有数据收集车辆（推荐，数据更纯净）
  - `true`: 生成其他自动驾驶车辆

- **num_npc_vehicles**: NPC车辆数量
  - 仅在 `spawn_npc_vehicles=true` 时有效
  - 推荐值: `0-50`

- **spawn_npc_walkers**: 是否生成NPC行人
  - `false`: 不生成行人
  - `true`: 生成随机行走的行人

- **num_npc_walkers**: NPC行人数量
  - 仅在 `spawn_npc_walkers=true` 时有效
  - 推荐值: `0-100`

---

### 4. ⭐ 天气配置 (`weather_settings`)

```json
"weather_settings": {
    "preset": "ClearNoon",
    "custom": {
        "cloudiness": 0.0,
        "precipitation": 0.0,
        "precipitation_deposits": 0.0,
        "wind_intensity": 0.0,
        "sun_azimuth_angle": 0.0,
        "sun_altitude_angle": 75.0,
        "fog_density": 0.0,
        "fog_distance": 0.0,
        "wetness": 0.0
    }
}
```

#### 天气预设 (`preset`)

可选的预设值：

| 预设名称 | 描述 |
|---------|------|
| `ClearNoon` | 晴朗正午（默认） |
| `CloudyNoon` | 多云正午 |
| `WetNoon` | 潮湿正午 |
| `WetCloudyNoon` | 潮湿多云正午 |
| `SoftRainNoon` | 小雨正午 |
| `MidRainyNoon` | 中雨正午 |
| `HardRainNoon` | 大雨正午 |
| `ClearSunset` | 晴朗日落 |
| `CloudySunset` | 多云日落 |
| `WetSunset` | 潮湿日落 |
| `WetCloudySunset` | 潮湿多云日落 |
| `SoftRainSunset` | 小雨日落 |
| `MidRainSunset` | 中雨日落 |
| `HardRainSunset` | 大雨日落 |
| `ClearNight` | 晴朗夜晚 |
| `CloudyNight` | 多云夜晚 |
| `WetNight` | 潮湿夜晚 |
| `WetCloudyNight` | 潮湿多云夜晚 |
| `SoftRainNight` | 小雨夜晚 |
| `MidRainyNight` | 中雨夜晚 |
| `HardRainNight` | 大雨夜晚 |
| `DustStorm` | 沙尘暴 |

#### 自定义天气参数 (`custom`)

当 `preset` 设为 `null` 或空字符串时，使用自定义参数：

| 参数 | 范围 | 描述 |
|-----|------|------|
| `cloudiness` | 0-100 | 云量百分比 |
| `precipitation` | 0-100 | 降水量百分比 |
| `precipitation_deposits` | 0-100 | 地面积水百分比 |
| `wind_intensity` | 0-100 | 风力强度百分比 |
| `sun_azimuth_angle` | 0-360 | 太阳方位角（度） |
| `sun_altitude_angle` | -90~90 | 太阳高度角（负值=夜晚） |
| `fog_density` | 0-100 | 雾密度百分比 |
| `fog_distance` | 0+ | 雾起始距离（米） |
| `wetness` | 0-100 | 地面湿度百分比 |

---

### 5. 路线生成配置 (`route_generation`)

```json
"route_generation": {
    "strategy": "smart",
    "min_distance": 50.0,
    "max_distance": 500.0
}
```

- **strategy**: 路线生成策略
  - `smart`: 智能选择（约150条路线，推荐）
  - `exhaustive`: 穷举所有组合（约5000条路线，耗时长）

- **min_distance**: 最小路线距离（米）
  - 过短的路线会被过滤

- **max_distance**: 最大路线距离（米）
  - 过长的路线会被过滤

---

### 6. 数据收集设置 (`collection_settings`)

```json
"collection_settings": {
    "frames_per_route": 1000,
    "save_path": "./auto_collected_data",
    "auto_save_interval": 200,
    "simulation_fps": 20,
    "target_speed_kmh": 10.0
}
```

- **frames_per_route**: 每条路线收集的最大帧数
  - 推荐: `1000-2000`
  - 实际可能因到达终点而提前结束

- **save_path**: 数据保存路径
  - 相对路径或绝对路径均可

- **auto_save_interval**: 自动保存间隔（帧数）
  - 推荐: `200`

- **simulation_fps**: 模拟帧率
  - 范围: `10-30`
  - 推荐: `20`

- **target_speed_kmh**: 车辆目标速度（km/h）
  - 范围: `5-30`
  - 推荐: `10`（低速，转弯更稳定）

---

## 🚀 命令行使用

### 基本使用

```bash
# 使用默认配置文件
python auto_full_town_collection.py

# 使用自定义配置文件
python auto_full_town_collection.py --config my_config.json
```

### 命令行覆盖配置

```bash
# 覆盖速度和帧率
python auto_full_town_collection.py --target-speed 15.0 --fps 30

# 启用NPC车辆和行人
python auto_full_town_collection.py --spawn-npc --num-npc 20 --spawn-walkers --num-walkers 50

# 设置天气
python auto_full_town_collection.py --weather HardRainNoon

# 组合使用
python auto_full_town_collection.py --target-speed 10 --weather CloudySunset --spawn-walkers --num-walkers 30
```

---

## 📝 配置示例

### 示例1：纯净数据收集（推荐）

```json
{
    "world_settings": {
        "spawn_npc_vehicles": false,
        "num_npc_vehicles": 0,
        "spawn_npc_walkers": false,
        "num_npc_walkers": 0
    },
    "weather_settings": {
        "preset": "ClearNoon"
    }
}
```

### 示例2：复杂场景数据收集

```json
{
    "world_settings": {
        "spawn_npc_vehicles": true,
        "num_npc_vehicles": 30,
        "spawn_npc_walkers": true,
        "num_npc_walkers": 50
    },
    "weather_settings": {
        "preset": "WetCloudyNoon"
    }
}
```

### 示例3：夜间雨天场景

```json
{
    "weather_settings": {
        "preset": "HardRainNight"
    }
}
```

### 示例4：自定义天气

```json
{
    "weather_settings": {
        "preset": null,
        "custom": {
            "cloudiness": 50.0,
            "precipitation": 30.0,
            "sun_altitude_angle": 45.0,
            "fog_density": 10.0
        }
    }
}
```

---

## 🌤️ 多天气轮换收集（新功能）

### 功能说明

自动在多个天气条件下收集数据，每个天气收集完成后自动切换到下一个天气继续收集。数据按天气分目录保存。

### 命令行使用

```bash
# 使用预定义天气组合
python auto_full_town_collection.py --multi-weather basic

# 使用自定义天气列表
python auto_full_town_collection.py --weather-list ClearNoon CloudyNoon WetNoon
```

### 预定义天气组合

| 组合名称 | 包含天气 | 说明 |
|---------|---------|------|
| `basic` | ClearNoon, CloudyNoon, ClearSunset, ClearNight | 基础组合（4种） |
| `all_noon` | ClearNoon, CloudyNoon, WetNoon, SoftRainNoon, HardRainNoon | 所有正午天气（5种） |
| `all_sunset` | ClearSunset, CloudySunset, WetSunset, SoftRainSunset, HardRainSunset | 所有日落天气（5种） |
| `all_night` | ClearNight, CloudyNight, WetNight, SoftRainNight, HardRainNight | 所有夜晚天气（5种） |
| `clear_all` | ClearNoon, ClearSunset, ClearNight | 所有晴朗天气（3种） |
| `rain_all` | SoftRainNoon, MidRainyNoon, HardRainNoon, SoftRainSunset, SoftRainNight | 所有雨天（5种） |
| `full` | 11种主要天气 | 完整组合 |

### 数据保存结构

```
auto_collected_data/
├── ClearNoon/
│   ├── carla_cmd2_Follow_xxx.h5
│   └── ...
├── CloudyNoon/
│   ├── carla_cmd2_Follow_xxx.h5
│   └── ...
├── WetNoon/
│   └── ...
└── multi_weather_summary.json  # 总体统计
```

### 配置文件设置

```json
"multi_weather_settings": {
    "enabled": true,
    "weather_preset": "basic",
    "custom_weather_list": []
}
```

---

**更新日期**: 2025-12-01
