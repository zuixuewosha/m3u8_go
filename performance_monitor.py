#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控器 - 实时监控和报告下载性能
"""
import time
import threading
import json
from typing import Dict, List, Optional
from datetime import datetime
from advanced_downloader import get_batch_downloader


class PerformanceMonitor:
    """性能监控器 - 实时监控下载性能"""
    
    def __init__(self, report_interval: float = 30.0):
        """
        初始化性能监控器
        
        Args:
            report_interval: 报告间隔时间（秒）
        """
        self.report_interval = report_interval
        self._monitoring = False
        self._monitor_thread = None
        self._performance_history: List[Dict] = []
        self._max_history_size = 1000
        
    def start_monitoring(self):
        """开始性能监控"""
        if not self._monitoring:
            self._monitoring = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            print("📊 性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
            print("📊 性能监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                # 获取当前性能统计
                stats = self._collect_current_stats()
                
                if stats:
                    # 添加到历史记录
                    self._performance_history.append({
                        'timestamp': datetime.now().isoformat(),
                        'stats': stats
                    })
                    
                    # 限制历史记录大小
                    if len(self._performance_history) > self._max_history_size:
                        self._performance_history.pop(0)
                    
                    # 打印实时报告
                    self._print_realtime_report(stats)
                
                time.sleep(self.report_interval)
                
            except Exception as e:
                print(f"性能监控循环出错: {e}")
                time.sleep(5.0)
    
    def _collect_current_stats(self) -> Optional[Dict]:
        """收集当前性能统计"""
        try:
            batch_downloader = get_batch_downloader()
            if batch_downloader:
                return batch_downloader.get_global_performance_stats()
            return None
        except Exception as e:
            print(f"收集性能统计出错: {e}")
            return None
    
    def _print_realtime_report(self, stats: Dict):
        """打印实时性能报告"""
        print(f"\n📈 实时性能报告 ({datetime.now().strftime('%H:%M:%S')})")
        print("-" * 50)
        print(f"运行时间: {stats['total_runtime_seconds']:.1f} 秒")
        print(f"总下载数: {stats['total_downloads']}")
        print(f"成功下载: {stats['successful_downloads']}")
        print(f"失败下载: {stats['failed_downloads']}")
        print(f"整体成功率: {stats['overall_success_rate']:.1f}%")
        print(f"平均下载速度: {stats['average_download_speed_mbps']:.1f} MB/s")
        print(f"活跃任务数: {stats['active_tasks']}")
        print(f"峰值并发: {stats['peak_concurrent_downloads']}")
        print("-" * 50)
    
    def get_performance_history(self) -> List[Dict]:
        """获取性能历史记录"""
        return self._performance_history.copy()
    
    def export_performance_data(self, filename: str):
        """导出性能数据到文件"""
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'report_interval': self.report_interval,
                'performance_history': self._performance_history,
                'summary': self._generate_summary()
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"📊 性能数据已导出到: {filename}")
            
        except Exception as e:
            print(f"导出性能数据失败: {e}")
    
    def _generate_summary(self) -> Dict:
        """生成性能摘要"""
        if not self._performance_history:
            return {}
        
        # 计算平均性能指标
        success_rates = [entry['stats']['overall_success_rate'] for entry in self._performance_history]
        download_speeds = [entry['stats']['average_download_speed_mbps'] for entry in self._performance_history]
        concurrent_downloads = [entry['stats']['peak_concurrent_downloads'] for entry in self._performance_history]
        
        return {
            'total_records': len(self._performance_history),
            'time_span_minutes': len(self._performance_history) * self.report_interval / 60,
            'average_success_rate': sum(success_rates) / len(success_rates) if success_rates else 0,
            'max_success_rate': max(success_rates) if success_rates else 0,
            'min_success_rate': min(success_rates) if success_rates else 0,
            'average_download_speed_mbps': sum(download_speeds) / len(download_speeds) if download_speeds else 0,
            'max_download_speed_mbps': max(download_speeds) if download_speeds else 0,
            'min_download_speed_mbps': min(download_speeds) if download_speeds else 0,
            'average_peak_concurrent': sum(concurrent_downloads) / len(concurrent_downloads) if concurrent_downloads else 0,
            'max_peak_concurrent': max(concurrent_downloads) if concurrent_downloads else 0
        }
    
    def print_detailed_report(self):
        """打印详细性能报告"""
        batch_downloader = get_batch_downloader()
        if batch_downloader:
            batch_downloader.print_performance_report()
        
        summary = self._generate_summary()
        if summary:
            print("\n📊 性能历史摘要")
            print("=" * 60)
            print(f"记录总数: {summary['total_records']}")
            print(f"监控时长: {summary['time_span_minutes']:.1f} 分钟")
            print(f"平均成功率: {summary['average_success_rate']:.1f}%")
            print(f"成功率范围: {summary['min_success_rate']:.1f}% - {summary['max_success_rate']:.1f}%")
            print(f"平均下载速度: {summary['average_download_speed_mbps']:.1f} MB/s")
            print(f"下载速度范围: {summary['min_download_speed_mbps']:.1f} - {summary['max_download_speed_mbps']:.1f} MB/s")
            print(f"平均峰值并发: {summary['average_peak_concurrent']:.0f}")
            print(f"最大峰值并发: {summary['max_peak_concurrent']:.0f}")
            print("=" * 60)


# 全局性能监控器实例
_performance_monitor = None


def get_performance_monitor(report_interval: float = 30.0) -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor(report_interval=report_interval)
    return _performance_monitor


def start_performance_monitoring(report_interval: float = 30.0):
    """启动性能监控"""
    monitor = get_performance_monitor(report_interval)
    monitor.start_monitoring()
    return monitor


def stop_performance_monitoring():
    """停止性能监控"""
    global _performance_monitor
    if _performance_monitor:
        _performance_monitor.stop_monitoring()


def print_performance_report():
    """打印性能报告"""
    monitor = get_performance_monitor()
    monitor.print_detailed_report()


def export_performance_data(filename: str):
    """导出性能数据"""
    monitor = get_performance_monitor()
    monitor.export_performance_data(filename)


if __name__ == "__main__":
    # 测试性能监控器
    print("🚀 启动性能监控器测试")
    
    # 启动监控
    monitor = start_performance_monitoring(report_interval=10.0)
    
    try:
        # 模拟运行一段时间
        print("⏰ 监控运行中，按 Ctrl+C 停止...")
        time.sleep(60)  # 运行1分钟
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    
    finally:
        # 停止监控并打印报告
        stop_performance_monitoring()
        print_performance_report()
        
        # 导出数据
        export_performance_data("performance_data.json")
        print("\n✅ 测试完成")