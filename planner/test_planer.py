from planner import Planner

# 初始化（需要指定城市名称）
planner = Planner('Town01')  # 或 'Town02'

# 定义真实坐标值（CARLA世界坐标系，单位：米）
# 注意：这些坐标需要根据实际的CARLA地图来设置
# Town01地图的有效坐标范围大约在 (-50, -50) 到 (300, 300) 之间

# 示例1：使用Town01地图上的有效坐标
# 这些坐标是通过节点转世界坐标计算得出的
# 起始位置 - 节点(15, 2)附近，远离交叉路口
x1, y1, z1 = 123.23, 16.43, 22.0

# 起始朝向（方向向量）
ox1, oy1, oz1 = 1.0, 0.0, 0.0  # 朝向正X方向

# 目标位置 - 节点(25, 10)附近，远离交叉路口
x2, y2, z2 = 205.53, 82.15, 22.0

# 目标朝向
ox2, oy2, oz2 = 1.0, 0.0, 0.0  # 朝向正X方向

# 获取导航指令
try:
    directions = planner.get_next_command(
        source=(x1, y1, z1),           # 当前位置
        source_ori=(ox1, oy1, oz1),    # 当前朝向
        target=(x2, y2, z2),           # 目标位置
        target_ori=(ox2, oy2, oz2)     # 目标朝向
    )
    # 解释导航指令
    command_names = {
        0.0: "REACH_GOAL (到达目标)",
        2.0: "LANE_FOLLOW (车道保持)",
        3.0: "TURN_LEFT (左转)",
        4.0: "TURN_RIGHT (右转)",
        5.0: "GO_STRAIGHT (直行)"
    }
    
    command_name = command_names.get(directions, f"未知指令 ({directions})")
    print(f"\n导航成功！")
    print(f"起点: ({x1:.2f}, {y1:.2f}, {z1:.2f})")
    print(f"终点: ({x2:.2f}, {y2:.2f}, {z2:.2f})")
    print(f"导航指令: {command_name}")
    
except RuntimeError as e:
    print(f"\n错误: {e}")
    print("\n提示：")
    print("1. 请确保起点和终点都在道路上且远离交叉路口")
    print("2. 建议从CARLA模拟器中获取真实的车辆位置坐标")
    print("3. 可以尝试调整坐标或使用simple_test.py查看有效的节点坐标")

print("\n" + "="*60)
print("directions 返回值说明：")
print("="*60)
print("0.0 - REACH_GOAL (到达目标)")
print("2.0 - LANE_FOLLOW (车道保持)")
print("3.0 - TURN_LEFT (左转)")
print("4.0 - TURN_RIGHT (右转)")
print("5.0 - GO_STRAIGHT (直行)")