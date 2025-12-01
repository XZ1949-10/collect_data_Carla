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
        self.command_names = {2: 'Follow', 3: 'Left', 4: 'Right', 5: 'Straight'}
        
    def verify_all(self):
        """验证所有数据文件"""
        print("\n" + "="*70)
        print("🔍 数据验证工具")
        print("="*70)
        print(f"数据路径: {self.data_path}\n")
        
        if not os.path.exists(self.data_path):
            print(f"❌ 数据路径不存在: {self.data_path}")
            return
        
        # 查找所有HDF5文件
        h5_files = [f for f in os.listdir(self.data_path) if f.endswith('.h5')]
        
        if not h5_files:
            print("❌ 未找到任何HDF5数据文件")
            return
        
        print(f"✅ 找到 {len(h5_files)} 个数据文件\n")
        
        # 统计信息
        total_frames = 0
        command_stats = defaultdict(int)
        speed_stats = []
        file_sizes = []
        corrupted_files = []
        
        print("正在验证数据文件...\n")
        
        for idx, filename in enumerate(h5_files):
            filepath = os.path.join(self.data_path, filename)
            
            try:
                with h5py.File(filepath, 'r') as f:
                    # 读取数据
                    rgb = f['rgb'][:]
                    targets = f['targets'][:]
                    
                    # 验证形状
                    assert rgb.shape[0] == targets.shape[0], "RGB和targets数量不匹配"
                    assert rgb.shape[1:] == (88, 200, 3), f"RGB形状错误: {rgb.shape}"
                    assert targets.shape[1] == 25, f"Targets形状错误: {targets.shape}"
                    
                    # 统计
                    num_frames = rgb.shape[0]
                    total_frames += num_frames
                    
                    # 命令统计
                    commands = targets[:, 24]
                    for cmd in np.unique(commands):
                        cmd_count = np.sum(commands == cmd)
                        command_stats[int(cmd)] += cmd_count
                    
                    # 速度统计
                    speeds = targets[:, 10]
                    speed_stats.extend(speeds.tolist())
                    
                    # 文件大小
                    file_size = os.path.getsize(filepath) / 1024 / 1024  # MB
                    file_sizes.append(file_size)
                    
                    # 数据质量检查
                    if rgb.mean() < 5:
                        print(f"  ⚠️  {filename}: 图像过暗（可能有问题）")
                    
                    if np.max(speeds) > 150:
                        print(f"  ⚠️  {filename}: 速度异常（{np.max(speeds):.1f} km/h）")
                    
                    # 进度显示
                    if (idx + 1) % 10 == 0 or idx == len(h5_files) - 1:
                        progress = (idx + 1) / len(h5_files) * 100
                        print(f"  进度: {progress:.1f}% ({idx + 1}/{len(h5_files)})")
                
            except Exception as e:
                print(f"  ❌ {filename}: 验证失败 - {e}")
                corrupted_files.append(filename)
        
        # 打印统计报告
        self._print_statistics(
            total_frames, 
            command_stats, 
            speed_stats, 
            file_sizes, 
            corrupted_files,
            len(h5_files)
        )
        
        # 生成可视化报告
        self._generate_visualizations(command_stats, speed_stats, file_sizes)
        
        # 保存验证报告
        self._save_verification_report(
            total_frames, 
            command_stats, 
            speed_stats, 
            file_sizes, 
            corrupted_files,
            len(h5_files)
        )
    
    def _print_statistics(self, total_frames, command_stats, speed_stats, 
                         file_sizes, corrupted_files, total_files):
        """打印统计信息"""
        print("\n" + "="*70)
        print("📊 验证报告")
        print("="*70)
        
        # 基本统计
        print(f"\n📁 文件统计:")
        print(f"  • 总文件数: {total_files}")
        print(f"  • 损坏文件: {len(corrupted_files)}")
        print(f"  • 有效文件: {total_files - len(corrupted_files)}")
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
        
        # 损坏文件列表
        if corrupted_files:
            print(f"\n❌ 损坏文件列表:")
            for filename in corrupted_files[:10]:  # 只显示前10个
                print(f"  • {filename}")
            if len(corrupted_files) > 10:
                print(f"  ... 还有 {len(corrupted_files)-10} 个损坏文件")
        
        print("\n" + "="*70 + "\n")
    
    def _generate_visualizations(self, command_stats, speed_stats, file_sizes):
        """生成可视化报告"""
        try:
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle('数据收集统计报告', fontsize=16, fontweight='bold')
            
            # 1. 命令分布饼图
            ax1 = axes[0, 0]
            if command_stats:
                labels = [self.command_names.get(cmd, f'Cmd{cmd}') for cmd in command_stats.keys()]
                sizes = list(command_stats.values())
                colors = ['#66c2a5', '#fc8d62', '#8da0cb', '#e78ac3']
                ax1.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
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
            
            # 3. 文件大小分布
            ax3 = axes[1, 0]
            if file_sizes:
                ax3.hist(file_sizes, bins=30, color='lightgreen', edgecolor='black', alpha=0.7)
                ax3.set_xlabel('文件大小 (MB)')
                ax3.set_ylabel('文件数量')
                ax3.set_title('文件大小分布')
            
            # 4. 数据质量评分
            ax4 = axes[1, 1]
            quality_metrics = {
                '完整性': min(100, len(command_stats) / 4 * 100),
                '速度合理性': min(100, (1 - sum(1 for s in speed_stats if s > 100) / max(len(speed_stats), 1)) * 100),
                '数据量': min(100, len(speed_stats) / 100000 * 100),
                '文件健康': min(100, (1 - len([f for f in file_sizes if f < 0.1]) / max(len(file_sizes), 1)) * 100)
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
                                  file_sizes, corrupted_files, total_files):
        """保存验证报告到JSON"""
        report = {
            'verification_time': __import__('datetime').datetime.now().isoformat(),
            'data_path': self.data_path,
            'file_statistics': {
                'total_files': total_files,
                'corrupted_files': len(corrupted_files),
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
            'corrupted_files': corrupted_files
        }
        
        report_path = os.path.join(self.data_path, 'verification_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        print(f"✅ 验证报告已保存: {report_path}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='验证CARLA收集的数据')
    parser.add_argument('--data-path', default='./auto_collected_data', 
                       help='数据目录路径')
    
    args = parser.parse_args()
    
    verifier = DataVerifier(args.data_path)
    verifier.verify_all()


if __name__ == '__main__':
    main()
