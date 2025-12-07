#!/usr/bin/env python
# coding=utf-8
'''
作者: AI Assistant
日期: 2025-12-01
说明: 验证收集到的数据质量和完整性
'''

import os
import h5py
import numpy as np
import json
from collections import defaultdict
import matplotlib.pyplot as plt


class DataVerifier:
    """数据验证器"""
    
    def __init__(self, data_path):
        """
        初始化验证器
        
        参数:
            data_path (str): 数据目录路径
        """
        self.data_path = data_path
        # 命令映射（与收集代码一致）
        # 只有4个有效命令：2=Follow, 3=Left, 4=Right, 5=Straight
        self.command_names = {
            2: 'Follow',    # RoadOption.LANEFOLLOW
            3: 'Left',      # RoadOption.LEFT
            4: 'Right',     # RoadOption.RIGHT
            5: 'Straight'   # RoadOption.STRAIGHT
        }
        
    def _find_h5_files(self, path):
        """
        递归查找所有HDF5文件
        
        参数:
            path (str): 搜索路径
            
        返回:
            list: HDF5文件路径列表
        """
        h5_files = []
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.endswith('.h5'):
                    h5_files.append(os.path.join(root, f))
        return h5_files
        
    def verify_all(self, delete_invalid=False, min_frames=200):
        """
        验证所有数据文件
        
        参数:
            delete_invalid (bool): 是否删除不满足条件的文件
            min_frames (int): 最小帧数要求
        """
        print("\n" + "="*70)
        print("🔍 数据验证工具")
        print("="*70)
        print(f"数据路径: {self.data_path}")
        print(f"最小帧数要求: {min_frames}")
        print(f"模式: {'🗑️ 自动删除无效文件' if delete_invalid else '👁️ 仅预览（不删除）'}\n")
        
        if not os.path.exists(self.data_path):
            print(f"❌ 数据路径不存在: {self.data_path}")
            return
        
        # 递归查找所有HDF5文件（支持子目录）
        h5_files = self._find_h5_files(self.data_path)
        
        if not h5_files:
            print("❌ 未找到任何HDF5数据文件")
            return
        
        print(f"✅ 找到 {len(h5_files)} 个数据文件\n")
        
        # 统计信息
        total_frames = 0
        command_stats = defaultdict(int)
        speed_stats = []
        steer_stats = []
        throttle_stats = []
        brake_stats = []
        file_sizes = []
        corrupted_files = []  # [(filepath, reason)]
        warning_files = []
        incomplete_files = []  # [(filepath, frame_count)]
        deleted_files = []  # [(filepath, reason)]
        
        print("正在验证数据文件...\n")
        
        for idx, filepath in enumerate(h5_files):
            filename = os.path.basename(filepath)
            should_delete = False
            delete_reason = []
            
            try:
                with h5py.File(filepath, 'r') as f:
                    # 检查数据集是否存在
                    if 'rgb' not in f or 'targets' not in f:
                        raise ValueError("缺少必要的数据集 'rgb' 或 'targets'")
                    
                    # 读取数据
                    rgb = f['rgb'][:]
                    targets = f['targets'][:]
                    
                    # 验证形状
                    assert rgb.shape[0] == targets.shape[0], "RGB和targets数量不匹配"
                    assert rgb.shape[1:] == (88, 200, 3), f"RGB形状错误: {rgb.shape}"
                    assert targets.shape[1] == 25, f"Targets形状错误: {targets.shape}"
                    
                    # 统计
                    num_frames = rgb.shape[0]
                    
                    # 命令统计（索引24）
                    commands = targets[:, 24]
                    
                    # 速度统计（索引10）
                    speeds = targets[:, 10]
                    
                    # 控制信号统计（索引0, 1, 2）
                    steers = targets[:, 0]
                    throttles = targets[:, 1]
                    brakes = targets[:, 2]
                    
                    # 文件大小
                    file_size = os.path.getsize(filepath) / 1024 / 1024  # MB
                    
                    # 数据质量检查
                    warnings = []
                    
                    # 图像亮度检查
                    if rgb.mean() < 5:
                        warnings.append("图像过暗")
                        delete_reason.append("图像过暗(mean<5)")
                        should_delete = True
                    
                    # 速度异常检查
                    if np.max(speeds) > 150:
                        warnings.append(f"速度异常（最大{np.max(speeds):.1f} km/h）")
                    
                    # 方向盘值范围检查（应在-1到1之间）
                    if np.min(steers) < -1.1 or np.max(steers) > 1.1:
                        warnings.append(f"方向盘值异常（{np.min(steers):.2f} ~ {np.max(steers):.2f}）")
                    
                    # 油门/刹车值范围检查（应在0到1之间）
                    if np.min(throttles) < -0.1 or np.max(throttles) > 1.1:
                        warnings.append(f"油门值异常（{np.min(throttles):.2f} ~ {np.max(throttles):.2f}）")
                    
                    if np.min(brakes) < -0.1 or np.max(brakes) > 1.1:
                        warnings.append(f"刹车值异常（{np.min(brakes):.2f} ~ {np.max(brakes):.2f}）")
                    
                    # 命令值检查（应为0, 2, 3, 4, 5之一）
                    valid_commands = {0, 2, 3, 4, 5}
                    invalid_cmds = set(commands.astype(int)) - valid_commands
                    if invalid_cmds:
                        warnings.append(f"无效命令值: {invalid_cmds}")
                        delete_reason.append(f"无效命令值: {invalid_cmds}")
                        should_delete = True
                    
                    # 帧数检查
                    if num_frames < min_frames:
                        incomplete_files.append((filepath, num_frames))
                        delete_reason.append(f"帧数不足({num_frames}<{min_frames})")
                        should_delete = True
                    
                    if warnings:
                        warning_files.append((filename, warnings))
                        for w in warnings:
                            print(f"  ⚠️  {filename}: {w}")
                    
                    # 如果文件有效，统计数据
                    if not should_delete:
                        total_frames += num_frames
                        for cmd in np.unique(commands):
                            cmd_count = np.sum(commands == cmd)
                            command_stats[int(cmd)] += cmd_count
                        speed_stats.extend(speeds.tolist())
                        steer_stats.extend(steers.tolist())
                        throttle_stats.extend(throttles.tolist())
                        brake_stats.extend(brakes.tolist())
                        file_sizes.append(file_size)
                
            except Exception as e:
                print(f"  ❌ {filename}: 验证失败 - {e}")
                corrupted_files.append((filepath, str(e)))
                should_delete = True
                delete_reason.append(f"文件损坏: {e}")
            
            # 删除不满足条件的文件
            if should_delete and delete_invalid:
                try:
                    os.remove(filepath)
                    reason_str = "; ".join(delete_reason)
                    deleted_files.append((filepath, reason_str))
                    print(f"  🗑️  已删除: {filename} - 原因: {reason_str}")
                except Exception as e:
                    print(f"  ❌ 删除失败 {filename}: {e}")
            elif should_delete and not delete_invalid:
                reason_str = "; ".join(delete_reason)
                deleted_files.append((filepath, reason_str))  # 记录但不删除
            
            # 进度显示
            if (idx + 1) % 10 == 0 or idx == len(h5_files) - 1:
                progress = (idx + 1) / len(h5_files) * 100
                print(f"  进度: {progress:.1f}% ({idx + 1}/{len(h5_files)})")
        
        # 打印统计报告
        self._print_statistics(
            total_frames, 
            command_stats, 
            speed_stats,
            steer_stats,
            throttle_stats,
            brake_stats,
            file_sizes, 
            corrupted_files,
            warning_files,
            incomplete_files,
            len(h5_files)
        )
        
        # 生成可视化报告
        self._generate_visualizations(command_stats, speed_stats, steer_stats, file_sizes)
        
        # 保存验证报告
        self._save_verification_report(
            total_frames, 
            command_stats, 
            speed_stats,
            steer_stats,
            throttle_stats,
            brake_stats,
            file_sizes, 
            corrupted_files,
            warning_files,
            incomplete_files,
            len(h5_files),
            deleted_files,
            delete_invalid
        )
    
    def _print_statistics(self, total_frames, command_stats, speed_stats, 
                         steer_stats, throttle_stats, brake_stats,
                         file_sizes, corrupted_files, warning_files, incomplete_files, total_files):
        """打印统计信息"""
        print("\n" + "="*70)
        print("📊 验证报告")
        print("="*70)
        
        # 基本统计
        print(f"\n📁 文件统计:")
        print(f"  • 总文件数: {total_files}")
        print(f"  • 损坏文件: {len(corrupted_files)}")
        print(f"  • 警告文件: {len(warning_files)}")
        print(f"  • 不足200帧: {len(incomplete_files)}")
        print(f"  • 有效文件: {total_files - len(corrupted_files)}")
        if file_sizes:
            print(f"  • 平均文件大小: {np.mean(file_sizes):.2f} MB")
            print(f"  • 总数据大小: {np.sum(file_sizes):.2f} MB ({np.sum(file_sizes)/1024:.2f} GB)")
        
        # 帧统计
        print(f"\n🎬 帧统计:")
        print(f"  • 总帧数: {total_frames:,}")
        print(f"  • 平均每文件: {total_frames / max(total_files, 1):.0f} 帧")
        
        # 命令统计
        print(f"\n🎯 命令分布:")
        for cmd, count in sorted(command_stats.items()):
            cmd_name = self.command_names.get(cmd, f'Unknown({cmd})')
            percentage = count / total_frames * 100 if total_frames > 0 else 0
            print(f"  • {cmd_name}: {count:,} 帧 ({percentage:.1f}%)")
        
        # 速度统计
        if speed_stats:
            print(f"\n🚗 速度统计:")
            print(f"  • 平均速度: {np.mean(speed_stats):.1f} km/h")
            print(f"  • 最低速度: {np.min(speed_stats):.1f} km/h")
            print(f"  • 最高速度: {np.max(speed_stats):.1f} km/h")
            print(f"  • 中位速度: {np.median(speed_stats):.1f} km/h")
        
        # 控制信号统计
        if steer_stats:
            print(f"\n🎮 控制信号统计:")
            print(f"  • 方向盘: {np.min(steer_stats):.3f} ~ {np.max(steer_stats):.3f} (平均: {np.mean(steer_stats):.3f})")
            print(f"  • 油门: {np.min(throttle_stats):.3f} ~ {np.max(throttle_stats):.3f} (平均: {np.mean(throttle_stats):.3f})")
            print(f"  • 刹车: {np.min(brake_stats):.3f} ~ {np.max(brake_stats):.3f} (平均: {np.mean(brake_stats):.3f})")
        
        # 损坏文件列表
        if corrupted_files:
            print(f"\n❌ 损坏文件列表:")
            for filename in corrupted_files[:10]:  # 只显示前10个
                print(f"  • {filename}")
            if len(corrupted_files) > 10:
                print(f"  ... 还有 {len(corrupted_files)-10} 个损坏文件")
        
        # 不足200帧的文件列表
        if incomplete_files:
            print(f"\n⚠️  不足200帧的文件列表:")
            # 按帧数排序
            incomplete_files_sorted = sorted(incomplete_files, key=lambda x: x[1])
            for filename, frame_count in incomplete_files_sorted[:20]:  # 显示前20个
                print(f"  • {filename}: {frame_count} 帧")
            if len(incomplete_files) > 20:
                print(f"  ... 还有 {len(incomplete_files)-20} 个不完整文件")
        
        print("\n" + "="*70 + "\n")
    
    def _generate_visualizations(self, command_stats, speed_stats, steer_stats, file_sizes):
        """生成可视化报告"""
        try:
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle('数据收集统计报告', fontsize=16, fontweight='bold')
            
            # 1. 命令分布饼图
            ax1 = axes[0, 0]
            if command_stats:
                labels = [self.command_names.get(cmd, f'Cmd{cmd}') for cmd in command_stats.keys()]
                sizes = list(command_stats.values())
                colors = ['#66c2a5', '#fc8d62', '#8da0cb', '#e78ac3', '#a6d854']
                ax1.pie(sizes, labels=labels, autopct='%1.1f%%', 
                       colors=colors[:len(sizes)], startangle=90)
                ax1.set_title('命令分布')
            
            # 2. 速度分布直方图
            ax2 = axes[0, 1]
            if speed_stats:
                ax2.hist(speed_stats, bins=50, color='skyblue', edgecolor='black', alpha=0.7)
                ax2.set_xlabel('速度 (km/h)')
                ax2.set_ylabel('频数')
                ax2.set_title('速度分布')
                ax2.axvline(np.mean(speed_stats), color='red', linestyle='--', 
                           label=f'平均: {np.mean(speed_stats):.1f} km/h')
                ax2.legend()
            
            # 3. 方向盘分布直方图
            ax3 = axes[1, 0]
            if steer_stats:
                ax3.hist(steer_stats, bins=50, color='lightcoral', edgecolor='black', alpha=0.7)
                ax3.set_xlabel('方向盘值')
                ax3.set_ylabel('频数')
                ax3.set_title('方向盘分布')
                ax3.axvline(0, color='green', linestyle='--', label='中心')
                ax3.legend()
            
            # 4. 数据质量评分
            ax4 = axes[1, 1]
            
            # 计算各项质量指标
            # 命令完整性：有多少种有效命令（2,3,4,5）
            valid_cmd_count = len([c for c in command_stats.keys() if c in {2, 3, 4, 5}])
            cmd_completeness = min(100, valid_cmd_count / 4 * 100)
            
            # 速度合理性：速度在合理范围内的比例
            speed_reasonable = min(100, (1 - sum(1 for s in speed_stats if s > 100 or s < 0) / max(len(speed_stats), 1)) * 100) if speed_stats else 0
            
            # 数据量评分
            data_volume = min(100, len(speed_stats) / 100000 * 100) if speed_stats else 0
            
            # 文件健康度
            file_health = min(100, (1 - len([f for f in file_sizes if f < 0.1]) / max(len(file_sizes), 1)) * 100) if file_sizes else 0
            
            # 方向盘平衡性：左右转向是否平衡
            if steer_stats:
                left_ratio = sum(1 for s in steer_stats if s < -0.1) / max(len(steer_stats), 1)
                right_ratio = sum(1 for s in steer_stats if s > 0.1) / max(len(steer_stats), 1)
                steer_balance = min(100, (1 - abs(left_ratio - right_ratio)) * 100)
            else:
                steer_balance = 0
            
            quality_metrics = {
                '命令完整性': cmd_completeness,
                '速度合理性': speed_reasonable,
                '数据量': data_volume,
                '文件健康': file_health,
                '转向平衡': steer_balance
            }
            
            metrics = list(quality_metrics.keys())
            scores = list(quality_metrics.values())
            colors_bar = ['green' if s >= 80 else 'orange' if s >= 60 else 'red' for s in scores]
            
            ax4.barh(metrics, scores, color=colors_bar, alpha=0.7)
            ax4.set_xlabel('评分')
            ax4.set_title('数据质量评分')
            ax4.set_xlim(0, 100)
            
            for i, score in enumerate(scores):
                ax4.text(score + 2, i, f'{score:.1f}', va='center')
            
            plt.tight_layout()
            
            # 保存图表
            report_path = os.path.join(self.data_path, 'verification_report.png')
            plt.savefig(report_path, dpi=150, bbox_inches='tight')
            print(f"✅ 可视化报告已保存: {report_path}")
            
            # 显示图表
            plt.show()
            
        except Exception as e:
            print(f"⚠️  生成可视化报告失败: {e}")
    
    def _save_verification_report(self, total_frames, command_stats, speed_stats, 
                                  steer_stats, throttle_stats, brake_stats,
                                  file_sizes, corrupted_files, warning_files, incomplete_files, total_files,
                                  deleted_files=None, delete_enabled=False):
        """保存验证报告到JSON"""
        report = {
            'verification_time': __import__('datetime').datetime.now().isoformat(),
            'data_path': self.data_path,
            'file_statistics': {
                'total_files': total_files,
                'corrupted_files': len(corrupted_files),
                'warning_files': len(warning_files),
                'incomplete_files': len(incomplete_files),
                'valid_files': total_files - len(corrupted_files),
                'average_file_size_mb': float(np.mean(file_sizes)) if file_sizes else 0,
                'total_data_size_mb': float(np.sum(file_sizes)) if file_sizes else 0
            },
            'frame_statistics': {
                'total_frames': int(total_frames),
                'average_frames_per_file': int(total_frames / max(total_files, 1))
            },
            'command_distribution': {
                self.command_names.get(cmd, f'Unknown({cmd})'): int(count) 
                for cmd, count in command_stats.items()
            },
            'speed_statistics': {
                'mean': float(np.mean(speed_stats)) if speed_stats else 0,
                'min': float(np.min(speed_stats)) if speed_stats else 0,
                'max': float(np.max(speed_stats)) if speed_stats else 0,
                'median': float(np.median(speed_stats)) if speed_stats else 0
            },
            'control_statistics': {
                'steer': {
                    'min': float(np.min(steer_stats)) if steer_stats else 0,
                    'max': float(np.max(steer_stats)) if steer_stats else 0,
                    'mean': float(np.mean(steer_stats)) if steer_stats else 0
                },
                'throttle': {
                    'min': float(np.min(throttle_stats)) if throttle_stats else 0,
                    'max': float(np.max(throttle_stats)) if throttle_stats else 0,
                    'mean': float(np.mean(throttle_stats)) if throttle_stats else 0
                },
                'brake': {
                    'min': float(np.min(brake_stats)) if brake_stats else 0,
                    'max': float(np.max(brake_stats)) if brake_stats else 0,
                    'mean': float(np.mean(brake_stats)) if brake_stats else 0
                }
            },
            'corrupted_files': corrupted_files,
            'warning_files': [(f, w) for f, w in warning_files],
            'incomplete_files': [{'filename': f, 'frame_count': c} for f, c in incomplete_files]
        }
        
        report_path = os.path.join(self.data_path, 'verification_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        print(f"✅ 验证报告已保存: {report_path}")
        
        # 保存删除报告
        if deleted_files:
            self._save_deletion_report(deleted_files, delete_enabled)
    
    def _save_deletion_report(self, deleted_files, delete_enabled=False):
        """保存删除报告到JSON和TXT"""
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 按删除原因分类
        reason_categories = defaultdict(list)
        for filepath, reason in deleted_files:
            # 解析原因
            if '帧数不足' in reason:
                reason_categories['帧数不足'].append({'file': filepath, 'detail': reason})
            elif '图像过暗' in reason:
                reason_categories['图像过暗'].append({'file': filepath, 'detail': reason})
            elif '无效命令值' in reason:
                reason_categories['无效命令值'].append({'file': filepath, 'detail': reason})
            elif '文件损坏' in reason:
                reason_categories['文件损坏'].append({'file': filepath, 'detail': reason})
            else:
                reason_categories['其他'].append({'file': filepath, 'detail': reason})
        
        # JSON报告
        deletion_report = {
            'report_time': __import__('datetime').datetime.now().isoformat(),
            'delete_enabled': delete_enabled,
            'status': '已删除' if delete_enabled else '待删除（预览模式）',
            'total_invalid_files': len(deleted_files),
            'summary': {category: len(files) for category, files in reason_categories.items()},
            'details': dict(reason_categories)
        }
        
        json_path = os.path.join(self.data_path, f'deletion_report_{timestamp}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(deletion_report, f, indent=4, ensure_ascii=False)
        
        # TXT报告（更易读）
        txt_path = os.path.join(self.data_path, f'deletion_report_{timestamp}.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("📋 数据文件删除报告\n")
            f.write("="*70 + "\n\n")
            f.write(f"报告时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"数据路径: {self.data_path}\n")
            f.write(f"操作状态: {'✅ 已删除' if delete_enabled else '⚠️ 预览模式（未实际删除）'}\n")
            f.write(f"不满足条件的文件总数: {len(deleted_files)}\n\n")
            
            f.write("-"*70 + "\n")
            f.write("📊 按原因分类统计\n")
            f.write("-"*70 + "\n")
            for category, files in reason_categories.items():
                f.write(f"  • {category}: {len(files)} 个文件\n")
            f.write("\n")
            
            f.write("-"*70 + "\n")
            f.write("📝 详细列表\n")
            f.write("-"*70 + "\n\n")
            
            for category, files in reason_categories.items():
                f.write(f"\n【{category}】({len(files)} 个文件)\n")
                f.write("-"*40 + "\n")
                for item in files:
                    f.write(f"  文件: {item['file']}\n")
                    f.write(f"  原因: {item['detail']}\n")
                    f.write("\n")
            
            f.write("="*70 + "\n")
            f.write("报告结束\n")
            f.write("="*70 + "\n")
        
        print(f"✅ 删除报告已保存:")
        print(f"   JSON: {json_path}")
        print(f"   TXT:  {txt_path}")
        
        # 打印删除摘要
        print(f"\n" + "="*70)
        print(f"🗑️  删除报告摘要")
        print("="*70)
        print(f"状态: {'✅ 已删除' if delete_enabled else '⚠️ 预览模式（使用 --delete-invalid 参数实际删除）'}")
        print(f"不满足条件的文件总数: {len(deleted_files)}")
        print(f"\n按原因分类:")
        for category, files in reason_categories.items():
            print(f"  • {category}: {len(files)} 个文件")
        print("="*70 + "\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='验证CARLA收集的数据')
    parser.add_argument('--data-path', default='E://carla_data2', 
                       help='数据目录路径')
    parser.add_argument('--preview-only', action='store_true',
                       help='仅预览不满足条件的文件，不实际删除')
    parser.add_argument('--min-frames', type=int, default=200,
                       help='最小帧数要求，默认200')
    
    args = parser.parse_args()
    
    verifier = DataVerifier(args.data_path)
    # 默认删除不满足条件的文件，除非指定 --preview-only
    verifier.verify_all(delete_invalid=not args.preview_only, min_frames=args.min_frames)


if __name__ == '__main__':
    main()
