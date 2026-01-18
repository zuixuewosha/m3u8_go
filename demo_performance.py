#!/usr/bin/env python3
"""
M3U8多线程下载器性能监控演示脚本
演示如何使用性能监控功能来跟踪下载性能和统计信息
"""

import time
import threading
from advanced_downloader import (
    get_batch_downloader, 
    print_batch_downloader_stats,
    get_batch_downloader_performance_stats,
    DownloadPriority
)
from performance_monitor import get_performance_monitor, PerformanceMonitor


def demo_basic_performance_monitoring():
    """演示基本的性能监控功能"""
    print("=== 基本性能监控演示 ===")
    
    # 获取批量下载器实例
    batch_downloader = get_batch_downloader(max_concurrent_tasks=2, max_concurrent_downloads_per_task=5)
    
    # 模拟一些下载任务
    test_urls = [
        ("https://httpbin.org/bytes/1024", "segment1.ts"),
        ("https://httpbin.org/bytes/2048", "segment2.ts"), 
        ("https://httpbin.org/bytes/512", "segment3.ts"),
        ("https://httpbin.org/bytes/1536", "segment4.ts"),
    ]
    
    # 添加任务到下载器
    for i in range(2):
        task_id = f"task_{i+1}"
        
        batch_downloader.add_m3u8_task(
            task_id=task_id,
            ts_segments=test_urls,
            priority=DownloadPriority.NORMAL,
            retry_count=1
        )
    
    # 等待任务完成（模拟）
    print("模拟下载任务执行中...")
    time.sleep(5)
    
    # 打印性能统计报告
    print("\n=== 下载器性能报告 ===")
    print_batch_downloader_stats()
    
    # 获取详细的性能统计
    stats = get_batch_downloader_performance_stats()
    print(f"\n=== 详细统计信息 ===")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")


def demo_advanced_performance_monitoring():
    """演示高级性能监控功能"""
    print("\n\n=== 高级性能监控演示 ===")
    
    # 获取性能监控器
    monitor = get_performance_monitor()
    
    # 启动实时监控
    monitor.start_monitoring(interval=1.0)
    print("开始实时监控...")
    
    # 模拟一些下载活动
    for i in range(5):
        # 模拟下载事件
        monitor.record_download_event(
            task_id=f"demo_task_{i}",
            url=f"https://example.com/video{i}/segment.ts",
            file_size=1024 * 1024,  # 1MB
            download_time=2.5,
            success=True
        )
        time.sleep(0.5)
    
    # 获取实时监控数据
    print("\n=== 实时性能数据 ===")
    current_stats = monitor.get_current_stats()
    print(f"当前下载速度: {current_stats.get('current_download_speed', 0):.2f} MB/s")
    print(f"活跃任务数: {current_stats.get('active_tasks', 0)}")
    print(f"成功率: {current_stats.get('success_rate', 0):.1%}")
    
    # 获取历史统计
    print("\n=== 历史性能统计 ===")
    historical_stats = monitor.get_historical_stats()
    print(f"总下载任务: {historical_stats.get('total_tasks', 0)}")
    print(f"成功任务: {historical_stats.get('successful_tasks', 0)}")
    print(f"失败任务: {historical_stats.get('failed_tasks', 0)}")
    print(f"平均下载速度: {historical_stats.get('average_download_speed', 0):.2f} MB/s")
    print(f"总下载量: {historical_stats.get('total_downloaded', 0) / (1024*1024):.2f} MB")
    
    # 停止监控
    monitor.stop_monitoring()
    print("\n停止实时监控")


def demo_performance_report():
    """演示性能报告生成功能"""
    print("\n\n=== 性能报告生成演示 ===")
    
    monitor = get_performance_monitor()
    
    # 生成性能报告
    print("生成性能报告...")
    report = monitor.generate_performance_report()
    
    # 显示报告摘要
    print("\n=== 性能报告摘要 ===")
    print(f"监控时间: {report['monitoring_period']['start']} - {report['monitoring_period']['end']}")
    print(f"总任务数: {report['summary']['total_tasks']}")
    print(f"成功率: {report['summary']['success_rate']:.1%}")
    print(f"平均速度: {report['summary']['average_download_speed']:.2f} MB/s")
    print(f"峰值速度: {report['summary']['peak_download_speed']:.2f} MB/s")
    
    # 显示性能趋势
    print("\n=== 性能趋势 ===")
    trends = report['trends']
    print(f"速度趋势: {'上升' if trends['download_speed'] > 0 else '下降' if trends['download_speed'] < 0 else '稳定'}")
    print(f"成功率趋势: {'上升' if trends['success_rate'] > 0 else '下降' if trends['success_rate'] < 0 else '稳定'}")
    
    # 导出报告
    print("\n=== 导出性能报告 ===")
    success = monitor.export_report("performance_report.json")
    if success:
        print("性能报告已导出到 performance_report.json")
    else:
        print("导出失败")


def demo_performance_optimization_tips():
    """演示性能优化建议"""
    print("\n\n=== 性能优化建议演示 ===")
    
    monitor = get_performance_monitor()
    
    # 获取优化建议
    recommendations = monitor.get_optimization_recommendations()
    
    print("=== 系统性能优化建议 ===")
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec['title']}")
        print(f"   描述: {rec['description']}")
        print(f"   优先级: {rec['priority']}")
        print(f"   预期效果: {rec['expected_improvement']}")
        print()


def main():
    """主函数 - 运行所有演示"""
    print("M3U8多线程下载器性能监控演示")
    print("=" * 50)
    
    try:
        # 演示基本性能监控
        demo_basic_performance_monitoring()
        
        # 演示高级性能监控
        demo_advanced_performance_monitoring()
        
        # 演示性能报告生成
        demo_performance_report()
        
        # 演示优化建议
        demo_performance_optimization_tips()
        
        print("\n" + "=" * 50)
        print("性能监控演示完成！")
        print("\n使用提示:")
        print("1. 在实际使用中，性能数据会自动收集")
        print("2. 可以随时调用 print_batch_downloader_stats() 查看当前统计")
        print("3. 使用 get_batch_downloader_performance_stats() 获取详细数据")
        print("4. 性能监控器会在后台持续记录下载性能")
        
    except KeyboardInterrupt:
        print("\n演示被用户中断")
    except Exception as e:
        print(f"演示过程中发生错误: {e}")


if __name__ == "__main__":
    main()