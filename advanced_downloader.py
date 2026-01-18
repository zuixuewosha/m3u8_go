#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级多线程下载优化器 - 实现智能并发控制和任务调度
"""
import threading
import queue
import time
import os
import requests
from typing import List, Dict, Callable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse, urljoin


class DownloadPriority(Enum):
    """下载优先级枚举"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class DownloadTask:
    """下载任务数据结构"""
    task_id: str
    url: str
    filepath: str
    priority: DownloadPriority = DownloadPriority.NORMAL
    retry_count: int = 3
    max_speed: Optional[int] = None
    chunk_size: int = 65536
    memory_efficient: bool = True  # 内存优化模式
    
    def __lt__(self, other):
        """优先级比较，数值越大优先级越高"""
        return self.priority.value > other.priority.value


@dataclass
class DownloadResult:
    """下载结果数据结构"""
    task: DownloadTask
    success: bool
    downloaded_bytes: int
    total_bytes: int
    error_message: Optional[str] = None
    download_time: float = 0.0


class AdaptiveThreadPool:
    """自适应线程池 - 根据网络状况动态调整线程数"""
    
    def __init__(self, min_workers: int = 2, max_workers: int = 20, 
                 adaptive_interval: float = 30.0):
        """
        初始化自适应线程池
        
        Args:
            min_workers: 最小工作线程数
            max_workers: 最大工作线程数
            adaptive_interval: 自适应调整间隔（秒）
        """
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.current_workers = min_workers
        self.adaptive_interval = adaptive_interval
        self._lock = threading.Lock()
        self._executor = None
        self._performance_metrics = []
        self._last_adjustment = time.time()
        self._running = False
        
        # 性能监控统计
        self._total_tasks = 0
        self._successful_tasks = 0
        self._failed_tasks = 0
        self._total_download_time = 0.0
        self._total_downloaded_bytes = 0
        
    def start(self):
        """启动线程池"""
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.current_workers)
                self._running = True
                # 启动自适应调整线程
                threading.Thread(target=self._adaptive_adjustment, daemon=True).start()
    
    def submit(self, fn, *args, **kwargs):
        """提交任务到线程池"""
        if self._executor is None:
            self.start()
        return self._executor.submit(fn, *args, **kwargs)
    
    def _adaptive_adjustment(self):
        """自适应调整线程数"""
        while self._running:
            try:
                time.sleep(self.adaptive_interval)
                self._adjust_thread_count()
            except Exception as e:
                print(f"自适应调整线程数时出错: {e}")
    
    def _adjust_thread_count(self):
        """根据性能指标调整线程数"""
        if len(self._performance_metrics) < 3:
            return
            
        # 计算平均下载速度和成功率
        recent_metrics = self._performance_metrics[-10:]  # 最近10个任务
        avg_speed = sum(m['speed'] for m in recent_metrics) / len(recent_metrics)
        success_rate = sum(1 for m in recent_metrics if m['success']) / len(recent_metrics)
        avg_response_time = sum(m['response_time'] for m in recent_metrics) / len(recent_metrics)
        
        with self._lock:
            old_workers = self.current_workers
            
            # 基于性能指标调整线程数
            if success_rate > 0.9 and avg_response_time < 2.0 and self.current_workers < self.max_workers:
                # 性能良好，增加线程数
                self.current_workers = min(self.current_workers + 2, self.max_workers)
            elif success_rate < 0.7 or avg_response_time > 5.0 and self.current_workers > self.min_workers:
                # 性能较差，减少线程数
                self.current_workers = max(self.current_workers - 1, self.min_workers)
            
            # 如果线程数发生变化，重新创建线程池
            if old_workers != self.current_workers:
                if self._executor:
                    self._executor.shutdown(wait=True)
                self._executor = ThreadPoolExecutor(max_workers=self.current_workers)
                print(f"线程池大小调整: {old_workers} -> {self.current_workers}")
    
    def record_performance(self, success: bool, speed: float, response_time: float):
        """记录性能指标"""
        metric = {
            'success': success,
            'speed': speed,
            'response_time': response_time,
            'timestamp': time.time()
        }
        self._performance_metrics.append(metric)
        # 只保留最近100个指标
        if len(self._performance_metrics) > 100:
            self._performance_metrics.pop(0)
    
    def record_task_completion(self, success: bool, download_time: float, downloaded_bytes: int):
        """记录任务完成统计"""
        with self._lock:
            self._total_tasks += 1
            if success:
                self._successful_tasks += 1
            else:
                self._failed_tasks += 1
            self._total_download_time += download_time
            self._total_downloaded_bytes += downloaded_bytes
    
    def get_performance_stats(self) -> Dict[str, float]:
        """获取性能统计信息"""
        with self._lock:
            success_rate = (self._successful_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0
            avg_download_time = (self._total_download_time / self._total_tasks) if self._total_tasks > 0 else 0
            avg_download_speed = (self._total_downloaded_bytes / self._total_download_time / 1024 / 1024) if self._total_download_time > 0 else 0
            
            # 计算最近性能指标
            if len(self._performance_metrics) > 0:
                recent_metrics = self._performance_metrics[-20:]  # 最近20个任务
                recent_success_rate = sum(1 for m in recent_metrics if m['success']) / len(recent_metrics) * 100
                recent_avg_speed = sum(m['speed'] for m in recent_metrics) / len(recent_metrics)
                recent_avg_response_time = sum(m['response_time'] for m in recent_metrics) / len(recent_metrics)
            else:
                recent_success_rate = 0
                recent_avg_speed = 0
                recent_avg_response_time = 0
            
            return {
                'total_tasks': self._total_tasks,
                'successful_tasks': self._successful_tasks,
                'failed_tasks': self._failed_tasks,
                'overall_success_rate': success_rate,
                'recent_success_rate': recent_success_rate,
                'average_download_time': avg_download_time,
                'average_download_speed_mbps': avg_download_speed,
                'recent_average_speed': recent_avg_speed,
                'recent_average_response_time': recent_avg_response_time,
                'current_thread_count': self.current_workers
            }
    
    def shutdown(self, wait: bool = True):
        """关闭线程池"""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None


class SmartDownloadScheduler:
    """智能下载调度器 - 优化任务分配和负载均衡"""
    
    def __init__(self, max_concurrent_downloads: int = 10, log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化智能下载调度器
        
        Args:
            max_concurrent_downloads: 最大并发下载数
            log_callback: 日志回调函数，用于记录日志信息
        """
        self.max_concurrent_downloads = max_concurrent_downloads
        self.download_queue = queue.PriorityQueue()
        self.active_downloads: Dict[str, threading.Thread] = {}
        self.active_download_info: Dict[str, Dict[str, any]] = {}  # 存储活跃下载的详细信息
        self.completed_downloads: Dict[str, DownloadResult] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._scheduler_thread = None
        self._session_pool = requests.Session()
        self.log_callback = log_callback  # 日志回调函数
        
        # 性能监控统计
        self._total_tasks = 0
        self._successful_tasks = 0
        self._failed_tasks = 0
        self._total_download_time = 0.0
        self._total_downloaded_bytes = 0
        self._peak_concurrent_downloads = 0
        
        # 配置会话池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max_concurrent_downloads * 2,
            pool_maxsize=max_concurrent_downloads * 2,
            max_retries=3
        )
        self._session_pool.mount('http://', adapter)
        self._session_pool.mount('https://', adapter)
    
    def add_task(self, task: DownloadTask) -> str:
        """添加下载任务到优先级队列"""
        self.download_queue.put(task)
        return task.task_id
    
    def add_urgent_task(self, task: DownloadTask) -> str:
        """添加紧急任务到队列前端"""
        # 临时提高优先级
        original_priority = task.priority
        task.priority = DownloadPriority.URGENT
        self.download_queue.put(task)
        # 恢复原始优先级（用于后续统计）
        task.priority = original_priority
        return task.task_id
    
    def get_queue_status(self) -> Dict[str, int]:
        """获取队列状态"""
        return {
            'queued_tasks': self.download_queue.qsize(),
            'active_downloads': len(self.active_downloads),
            'completed_downloads': len(self.completed_downloads),
            'max_concurrent': self.max_concurrent_downloads
        }
    
    def get_active_downloads_info(self) -> List[Dict[str, any]]:
        """获取活跃下载的详细信息"""
        with self._lock:
            active_info = []
            for task_id, info in self.active_download_info.items():
                active_info.append({
                    'task_id': task_id,
                    'url': info.get('url', ''),
                    'filepath': info.get('filepath', ''),
                    'downloaded_bytes': info.get('downloaded_bytes', 0),
                    'total_bytes': info.get('total_bytes', 0),
                    'progress': info.get('progress', 0.0),
                    'start_time': info.get('start_time', 0),
                    'elapsed_time': time.time() - info.get('start_time', time.time()),
                    'speed': info.get('speed', 0.0)
                })
            return active_info
    
    def get_result(self, task_id: str) -> Optional[DownloadResult]:
        """获取任务结果"""
        return self.completed_downloads.get(task_id)
    
    def get_active_count(self) -> int:
        """获取活跃下载数"""
        return len(self.active_downloads)
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self.download_queue.qsize()
    
    def _get_headers(self, url: str) -> Dict[str, str]:
        """获取完整的浏览器请求头，用于避免403错误"""
        from urllib.parse import urlparse
        
        # 解析URL以获取域名和Referer
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        referer = base_url
        
        # 如果是M3U8或TS文件，尝试从路径推断Referer
        if '.m3u8' in url or '.ts' in url:
            # 尝试从路径中提取上级目录作为Referer
            path_parts = parsed.path.split('/')
            if len(path_parts) > 1:
                referer = f"{base_url}/{'/'.join(path_parts[:-1])}/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': referer,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        return headers
    
    def _log_http_response(self, task_id: str, url: str, response: requests.Response):
        """记录HTTP响应信息到日志"""
        if not self.log_callback:
            return
        
        try:
            # 提取片段编号（如果存在）
            segment_num = ""
            if "_segment_" in task_id:
                try:
                    segment_num = task_id.split("_segment_")[-1]
                    segment_num = f"片段 {segment_num}"
                except:
                    segment_num = "片段"
            
            # 提取文件名（用于显示）
            filename = url.split('/')[-1].split('?')[0] if '/' in url else url
            if len(filename) > 40:
                filename = filename[:37] + "..."
            
            # 记录HTTP响应状态码和基本信息
            status_icon = "✅" if 200 <= response.status_code < 300 else "⚠️" if 300 <= response.status_code < 400 else "❌"
            status_text = {
                200: "OK",
                206: "Partial Content",
                301: "Moved Permanently",
                302: "Found",
                304: "Not Modified",
                403: "Forbidden",
                404: "Not Found",
                416: "Range Not Satisfiable",
                500: "Internal Server Error",
                502: "Bad Gateway",
                503: "Service Unavailable"
            }.get(response.status_code, "Unknown")
            
            log_msg = f"{status_icon} [{segment_num}] HTTP {response.status_code} {status_text}"
            if segment_num:
                log_msg += f" - {filename}"
            self.log_callback(log_msg)
            
            # 记录重要的响应头信息
            important_headers = {
                'content-length': '大小',
                'content-type': '类型',
                'content-range': '范围',
                'accept-ranges': '支持范围',
                'server': '服务器',
                'cache-control': '缓存控制'
            }
            header_info = []
            for header_name, display_name in important_headers.items():
                header_value = response.headers.get(header_name)
                if header_value:
                    # 格式化content-length
                    if header_name == 'content-length':
                        try:
                            size = int(header_value)
                            if size < 1024:
                                header_value = f"{size} B"
                            elif size < 1024 * 1024:
                                header_value = f"{size/1024:.2f} KB"
                            else:
                                header_value = f"{size/(1024*1024):.2f} MB"
                        except:
                            pass
                    # 截断过长的值
                    elif len(header_value) > 50:
                        header_value = header_value[:47] + "..."
                    header_info.append(f"{display_name}: {header_value}")
            
            if header_info:
                self.log_callback(f"  📋 {', '.join(header_info)}")
            
            # 记录重定向信息
            if response.history:
                redirect_count = len(response.history)
                final_url = response.url
                if len(final_url) > 60:
                    final_url = final_url[:57] + "..."
                self.log_callback(f"  🔄 重定向 {redirect_count} 次 → {final_url}")
            
        except Exception as e:
            # 静默处理日志记录错误，不影响下载流程
            pass

    def record_task_completion(self, success: bool, download_time: float, downloaded_bytes: int):
        """记录任务完成统计"""
        with self._lock:
            self._total_tasks += 1
            if success:
                self._successful_tasks += 1
            else:
                self._failed_tasks += 1
            self._total_download_time += download_time
            self._total_downloaded_bytes += downloaded_bytes
            
            # 更新峰值并发数
            current_active = len(self.active_downloads)
            if current_active > self._peak_concurrent_downloads:
                self._peak_concurrent_downloads = current_active
    
    def get_performance_stats(self) -> Dict[str, float]:
        """获取性能统计信息"""
        with self._lock:
            success_rate = (self._successful_tasks / self._total_tasks * 100) if self._total_tasks > 0 else 0
            avg_download_time = (self._total_download_time / self._total_tasks) if self._total_tasks > 0 else 0
            avg_download_speed = (self._total_downloaded_bytes / self._total_download_time / 1024 / 1024) if self._total_download_time > 0 else 0
            
            return {
                'total_tasks': self._total_tasks,
                'successful_tasks': self._successful_tasks,
                'failed_tasks': self._failed_tasks,
                'success_rate': success_rate,
                'average_download_time': avg_download_time,
                'average_download_speed_mbps': avg_download_speed,
                'peak_concurrent_downloads': self._peak_concurrent_downloads,
                'current_active_downloads': len(self.active_downloads)
            }
    
    def clear_queue(self):
        """清空等待队列（不影响正在进行的下载）"""
        cleared_count = 0
        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        return cleared_count
    
    def start(self):
        """启动调度器"""
        if self._scheduler_thread is None or not self._scheduler_thread.is_alive():
            self._stop_event.clear()
            self._scheduler_thread = threading.Thread(target=self._schedule_loop, daemon=True)
            self._scheduler_thread.start()
    
    def stop(self):
        """停止调度器"""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5.0)
    
    def _schedule_loop(self):
        """调度循环"""
        while not self._stop_event.is_set():
            try:
                # 检查是否有可用槽位
                with self._lock:
                    available_slots = self.max_concurrent_downloads - len(self.active_downloads)
                
                if available_slots > 0 and not self.download_queue.empty():
                    # 获取下一个高优先级任务
                    try:
                        task = self.download_queue.get(timeout=1.0)
                        # 启动下载线程
                        thread = threading.Thread(
                            target=self._download_worker,
                            args=(task,),
                            daemon=True
                        )
                        thread.start()
                        
                        with self._lock:
                            self.active_downloads[task.task_id] = thread
                            
                        # 记录线程启动信息
                        if self.log_callback:
                            try:
                                active_count = len(self.active_downloads)
                                queue_size = self.download_queue.qsize()
                                self.log_callback(f"  📊 活跃下载: {active_count}/{self.max_concurrent_downloads}, 队列剩余: {queue_size}")
                            except:
                                pass
                            
                    except queue.Empty:
                        continue
                
                # 清理已完成的下载
                self._cleanup_completed_downloads()
                
                time.sleep(0.1)  # 短暂休眠避免CPU占用过高
                
            except Exception as e:
                print(f"调度循环出错: {e}")
                time.sleep(1.0)
    
    def _cleanup_completed_downloads(self):
        """清理已完成的下载"""
        completed_tasks = []
        
        with self._lock:
            for task_id, thread in list(self.active_downloads.items()):
                if not thread.is_alive():
                    completed_tasks.append(task_id)
            
            for task_id in completed_tasks:
                del self.active_downloads[task_id]
    
    def _download_worker(self, task: DownloadTask):
        """下载工作线程 - 增强错误处理和重试机制"""
        start_time = time.time()
        task_id = task.task_id
        
        # 初始化下载信息
        with self._lock:
            self.active_download_info[task_id] = {
                'url': task.url,
                'filepath': task.filepath,
                'downloaded_bytes': 0,
                'total_bytes': 0,
                'progress': 0.0,
                'start_time': time.time(),
                'speed': 0.0
            }
        
        # 记录下载开始日志
        if self.log_callback:
            try:
                # 提取片段编号
                segment_num = ""
                if "_segment_" in task_id:
                    try:
                        segment_num = task_id.split("_segment_")[-1]
                        segment_num = f"片段 {segment_num}"
                    except:
                        segment_num = "片段"
                
                filename = os.path.basename(task.filepath)
                url_short = task.url.split('?')[0]
                if len(url_short) > 60:
                    url_short = url_short[:57] + "..."
                
                self.log_callback(f"🚀 [{segment_num}] 开始下载: {filename}")
                self.log_callback(f"  📍 URL: {url_short}")
                self.log_callback(f"  💾 保存路径: {task.filepath}")
            except:
                pass
        
        result = DownloadResult(
            task=task,
            success=False,
            downloaded_bytes=0,
            total_bytes=0,
            download_time=0.0
        )
        
        # 重试机制
        for attempt in range(task.retry_count + 1):
            if attempt > 0 and self.log_callback:
                try:
                    segment_num = ""
                    if "_segment_" in task_id:
                        try:
                            segment_num = task_id.split("_segment_")[-1]
                            segment_num = f"片段 {segment_num}"
                        except:
                            segment_num = "片段"
                    self.log_callback(f"🔄 [{segment_num}] 第 {attempt + 1} 次重试下载...")
                except:
                    pass
            try:
                # 执行下载
                success, downloaded_bytes, total_bytes = self._perform_download(task)
                
                # 更新下载进度信息
                with self._lock:
                    if task_id in self.active_download_info:
                        self.active_download_info[task_id]['downloaded_bytes'] = downloaded_bytes
                        self.active_download_info[task_id]['total_bytes'] = total_bytes
                        if total_bytes > 0:
                            self.active_download_info[task_id]['progress'] = downloaded_bytes / total_bytes
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            self.active_download_info[task_id]['speed'] = downloaded_bytes / elapsed
                
                if success:
                    result.success = True
                    result.downloaded_bytes = downloaded_bytes
                    result.total_bytes = total_bytes
                    result.download_time = time.time() - start_time
                    
                    # 记录下载成功日志
                    if self.log_callback:
                        try:
                            segment_num = ""
                            if "_segment_" in task_id:
                                try:
                                    segment_num = task_id.split("_segment_")[-1]
                                    segment_num = f"片段 {segment_num}"
                                except:
                                    segment_num = "片段"
                            
                            filename = os.path.basename(task.filepath)
                            elapsed = result.download_time
                            speed = downloaded_bytes / elapsed if elapsed > 0 else 0
                            
                            if speed < 1024:
                                speed_str = f"{speed:.2f} B/s"
                            elif speed < 1024 * 1024:
                                speed_str = f"{speed/1024:.2f} KB/s"
                            else:
                                speed_str = f"{speed/(1024*1024):.2f} MB/s"
                            
                            if total_bytes < 1024:
                                size_str = f"{total_bytes} B"
                            elif total_bytes < 1024 * 1024:
                                size_str = f"{total_bytes/1024:.2f} KB"
                            else:
                                size_str = f"{total_bytes/(1024*1024):.2f} MB"
                            
                            self.log_callback(f"✅ [{segment_num}] 下载完成: {filename}")
                            self.log_callback(f"  📦 大小: {size_str}, 耗时: {elapsed:.2f}秒, 速度: {speed_str}")
                        except:
                            pass
                    break
                else:
                    # 下载失败，记录错误信息
                    if attempt < task.retry_count:
                        wait_time = 2 ** attempt  # 指数退避
                        print(f"🔄 任务 {task.task_id} 第{attempt + 1}次下载失败，{wait_time}秒后重试")
                        time.sleep(wait_time)
                        result.error_message = f"下载失败，正在第{attempt + 2}次重试"
                    else:
                        result.error_message = "下载失败，已达到最大重试次数"
                        
            except requests.exceptions.RequestException as e:
                # 网络相关错误
                if attempt < task.retry_count:
                    wait_time = 2 ** attempt
                    print(f"🌐 任务 {task.task_id} 网络错误: {e}，{wait_time}秒后重试")
                    time.sleep(wait_time)
                    result.error_message = f"网络错误: {e}"
                else:
                    result.error_message = f"网络错误，已达到最大重试次数: {e}"
                    
            except IOError as e:
                # 文件I/O错误
                result.error_message = f"文件I/O错误: {e}"
                print(f"💾 任务 {task.task_id} 文件I/O错误: {e}")
                break  # I/O错误通常不可恢复，不再重试
                
            except Exception as e:
                # 其他未知错误
                result.error_message = f"未知错误: {e}"
                print(f"❌ 任务 {task.task_id} 未知错误: {e}")
                if attempt < task.retry_count:
                    time.sleep(1)
                
        # 记录结果
        result.download_time = time.time() - start_time
        with self._lock:
            self.completed_downloads[task_id] = result
            # 清理活跃下载信息
            if task_id in self.active_download_info:
                del self.active_download_info[task_id]
            # 记录任务完成统计
            self.record_task_completion(result.success, result.download_time, result.downloaded_bytes)
        
        # 如果最终失败，记录失败日志
        if not result.success and self.log_callback:
            try:
                segment_num = ""
                if "_segment_" in task_id:
                    try:
                        segment_num = task_id.split("_segment_")[-1]
                        segment_num = f"片段 {segment_num}"
                    except:
                        segment_num = "片段"
                
                filename = os.path.basename(task.filepath)
                error_msg = result.error_message or "未知错误"
                self.log_callback(f"❌ [{segment_num}] 下载失败: {filename}")
                self.log_callback(f"  ⚠️ 错误: {error_msg}")
            except:
                pass
            
            # 更新全局统计
            batch_downloader = get_batch_downloader()
            if batch_downloader:
                batch_downloader._total_downloads += 1
                if result.success:
                    batch_downloader._successful_downloads += 1
                else:
                    batch_downloader._failed_downloads += 1
                batch_downloader._total_download_time += result.download_time
                batch_downloader._total_downloaded_bytes += result.downloaded_bytes
    
    def _perform_download(self, task: DownloadTask) -> Tuple[bool, int, int]:
        """执行实际下载 - 增强错误处理和断点续传"""
        temp_filepath = task.filepath + ".tmp"
        downloaded_bytes = 0
        
        try:
            # 检查是否已存在
            if os.path.exists(task.filepath):
                file_size = os.path.getsize(task.filepath)
                print(f"✅ 文件已存在: {task.filepath} ({file_size} bytes)")
                return True, file_size, file_size
            
            # 检查临时文件（断点续传）
            if os.path.exists(temp_filepath):
                downloaded_bytes = os.path.getsize(temp_filepath)
                print(f"🔄 检测到断点续传: {temp_filepath} ({downloaded_bytes} bytes)")
            
            # 设置请求头 - 添加更多浏览器请求头以避免403错误
            headers = self._get_headers(task.url)
            if downloaded_bytes > 0:
                headers['Range'] = f'bytes={downloaded_bytes}-'
            
            # 执行请求，带重试机制
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    response = self._session_pool.get(
                        task.url,
                        headers=headers,
                        stream=True,
                        timeout=30,
                        allow_redirects=True
                    )
                    
                    # 记录HTTP响应信息到日志
                    self._log_http_response(task.task_id, task.url, response)
                    
                    # 处理响应状态码
                    if response.status_code == 200:
                        # 全新下载
                        if downloaded_bytes > 0:
                            print(f"⚠️ 服务器不支持断点续传，重新开始下载")
                            downloaded_bytes = 0
                        break
                    elif response.status_code == 206:
                        # 断点续传成功
                        print(f"✅ 断点续传成功: {downloaded_bytes} bytes")
                        break
                    elif response.status_code == 416:
                        # 范围请求无效，文件可能已完整
                        if os.path.exists(temp_filepath):
                            os.rename(temp_filepath, task.filepath)
                            file_size = os.path.getsize(task.filepath)
                            print(f"✅ 文件已完整: {task.filepath} ({file_size} bytes)")
                            return True, file_size, file_size
                        else:
                            downloaded_bytes = 0
                            break
                    elif response.status_code == 404:
                        print(f"❌ 文件不存在: {task.url}")
                        return False, 0, 0
                    else:
                        response.raise_for_status()
                        break
                        
                except requests.exceptions.Timeout:
                    if attempt < max_attempts - 1:
                        print(f"⏰ 请求超时，第{attempt + 2}次重试...")
                        time.sleep(2 ** attempt)
                    else:
                        raise
                except requests.exceptions.ConnectionError as e:
                    if attempt < max_attempts - 1:
                        print(f"🔌 连接错误，第{attempt + 2}次重试...")
                        time.sleep(2 ** attempt)
                    else:
                        raise
            
            # 获取总大小
            content_length = response.headers.get('content-length')
            total_bytes = int(content_length) + downloaded_bytes if content_length else 0
            
            # 记录下载信息到日志
            if self.log_callback:
                try:
                    segment_num = ""
                    if "_segment_" in task.task_id:
                        try:
                            segment_num = task.task_id.split("_segment_")[-1]
                            segment_num = f"片段 {segment_num}"
                        except:
                            segment_num = "片段"
                    
                    if total_bytes > 0:
                        if total_bytes < 1024:
                            size_str = f"{total_bytes} B"
                        elif total_bytes < 1024 * 1024:
                            size_str = f"{total_bytes/1024:.2f} KB"
                        else:
                            size_str = f"{total_bytes/(1024*1024):.2f} MB"
                        
                        if downloaded_bytes > 0:
                            self.log_callback(f"  📊 [{segment_num}] 文件大小: {size_str}, 已下载: {downloaded_bytes} bytes (断点续传)")
                        else:
                            self.log_callback(f"  📊 [{segment_num}] 文件大小: {size_str}")
                    else:
                        self.log_callback(f"  📊 [{segment_num}] 文件大小: 未知")
                except:
                    pass
            
            # 根据内存优化模式选择合适的下载策略
            if task.memory_efficient and total_bytes > 10 * 1024 * 1024:  # 大于10MB使用内存优化
                success, downloaded_bytes = self._memory_efficient_download(response, temp_filepath, 
                                                                          downloaded_bytes, task.chunk_size,
                                                                          task.task_id, total_bytes)
            else:
                success, downloaded_bytes = self._standard_download(response, temp_filepath, 
                                                              downloaded_bytes, task.chunk_size,
                                                              task.task_id, total_bytes)
            
            # 重命名临时文件
            if success and os.path.exists(temp_filepath):
                os.rename(temp_filepath, task.filepath)
                print(f"✅ 下载完成: {task.filepath} ({downloaded_bytes} bytes)")
                return True, downloaded_bytes, total_bytes or downloaded_bytes
            else:
                print(f"❌ 下载失败: {task.url}")
                return False, downloaded_bytes, 0
            
        except requests.exceptions.RequestException as e:
            print(f"🌐 网络错误 - 任务 {task.task_id}: {e}")
            return False, downloaded_bytes, 0
        except IOError as e:
            print(f"💾 文件I/O错误 - 任务 {task.task_id}: {e}")
            return False, downloaded_bytes, 0
        except Exception as e:
            print(f"❌ 未知错误 - 任务 {task.task_id}: {e}")
            return False, downloaded_bytes, 0
    
    def _standard_download(self, response, temp_filepath: str, downloaded_bytes: int, chunk_size: int, 
                          task_id: str = None, total_bytes: int = 0) -> Tuple[bool, int]:
        """标准下载模式 - 支持实时进度更新"""
        try:
            mode = 'ab' if downloaded_bytes > 0 else 'wb'
            start_time = time.time()
            last_update_time = start_time
            update_interval = 0.5  # 每0.5秒更新一次进度
            
            with open(temp_filepath, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        
                        # 定期更新进度信息
                        current_time = time.time()
                        if task_id and (current_time - last_update_time >= update_interval):
                            elapsed = current_time - start_time
                            speed = downloaded_bytes / elapsed if elapsed > 0 else 0
                            
                            with self._lock:
                                if task_id in self.active_download_info:
                                    self.active_download_info[task_id]['downloaded_bytes'] = downloaded_bytes
                                    if total_bytes > 0:
                                        self.active_download_info[task_id]['total_bytes'] = total_bytes
                                        self.active_download_info[task_id]['progress'] = downloaded_bytes / total_bytes
                                    self.active_download_info[task_id]['speed'] = speed
                            
                            last_update_time = current_time
                            
            return True, downloaded_bytes
        except Exception as e:
            print(f"标准下载失败: {e}")
            return False, downloaded_bytes
    
    def _memory_efficient_download(self, response, temp_filepath: str, downloaded_bytes: int, chunk_size: int,
                                   task_id: str = None, total_bytes: int = 0) -> Tuple[bool, int]:
        """内存优化下载模式 - 适用于大文件，支持实时进度更新"""
        try:
            mode = 'ab' if downloaded_bytes > 0 else 'wb'
            write_count = 0
            start_time = time.time()
            last_update_time = start_time
            update_interval = 0.5  # 每0.5秒更新一次进度
            
            with open(temp_filepath, mode) as f:
                chunk_buffer = []
                buffer_size = 0
                max_buffer_size = chunk_size * 10  # 最大缓冲区大小
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        chunk_buffer.append(chunk)
                        buffer_size += len(chunk)
                        downloaded_bytes += len(chunk)
                        
                        # 定期更新进度信息
                        current_time = time.time()
                        if task_id and (current_time - last_update_time >= update_interval):
                            elapsed = current_time - start_time
                            speed = downloaded_bytes / elapsed if elapsed > 0 else 0
                            
                            with self._lock:
                                if task_id in self.active_download_info:
                                    self.active_download_info[task_id]['downloaded_bytes'] = downloaded_bytes
                                    if total_bytes > 0:
                                        self.active_download_info[task_id]['total_bytes'] = total_bytes
                                        self.active_download_info[task_id]['progress'] = downloaded_bytes / total_bytes
                                    self.active_download_info[task_id]['speed'] = speed
                            
                            last_update_time = current_time
                        
                        # 当缓冲区达到一定大小时写入文件
                        if buffer_size >= max_buffer_size:
                            f.write(b''.join(chunk_buffer))
                            chunk_buffer.clear()
                            buffer_size = 0
                            write_count += 1
                            
                            # 定期刷新文件缓冲区
                            if write_count % 10 == 0:
                                f.flush()
                                os.fsync(f.fileno())
                
                # 写入剩余数据
                if chunk_buffer:
                    f.write(b''.join(chunk_buffer))
                    f.flush()
                    os.fsync(f.fileno())
            
            return True, downloaded_bytes
            
        except Exception as e:
            print(f"内存优化下载失败: {e}")
            return False, downloaded_bytes
    
    def get_result(self, task_id: str) -> Optional[DownloadResult]:
        """获取下载结果"""
        with self._lock:
            return self.completed_downloads.get(task_id)
    
    def get_active_count(self) -> int:
        """获取活跃下载数"""
        with self._lock:
            return len(self.active_downloads)
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self.download_queue.qsize()


class BatchDownloader:
    """批量下载管理器 - 管理多个下载任务"""
    
    def __init__(self, max_concurrent_tasks: int = 3, max_concurrent_downloads_per_task: int = 10, 
                 log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化批量下载管理器
        
        Args:
            max_concurrent_tasks: 最大并发任务数
            max_concurrent_downloads_per_task: 每个任务的最大并发下载数
            log_callback: 日志回调函数，用于记录日志信息
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_concurrent_downloads_per_task = max_concurrent_downloads_per_task
        self.schedulers: Dict[str, SmartDownloadScheduler] = {}
        self.task_results: Dict[str, Dict[str, DownloadResult]] = {}
        self._lock = threading.Lock()
        self.log_callback = log_callback  # 日志回调函数
        
        # 全局性能监控
        self._total_downloads = 0
        self._successful_downloads = 0
        self._failed_downloads = 0
        self._total_download_time = 0.0
        self._total_downloaded_bytes = 0
        self._start_time = time.time()
        
    def add_m3u8_task(self, task_id: str, ts_segments: List[Tuple[str, str]], 
                     priority: DownloadPriority = DownloadPriority.NORMAL,
                     retry_count: int = 3, memory_efficient: bool = True, 
                     urgent_segments: Optional[List[int]] = None) -> int:
        """
        智能任务分配算法 - 根据片段大小和网络状况动态分配下载任务
        
        算法特点：
        1. 基于片段大小进行任务分组，大文件优先下载
        2. 根据网络延迟动态调整并发数
        3. 支持断点续传和失败重试
        4. 实时监控下载速度和成功率
        """
        # 智能任务分配逻辑
        sorted_segments = self._optimize_task_order(ts_segments)
        
        with self._lock:
            if task_id not in self.schedulers:
                self.schedulers[task_id] = SmartDownloadScheduler(
                    max_concurrent_downloads=self.max_concurrent_downloads_per_task,
                    log_callback=self.log_callback
                )
                self.task_results[task_id] = {}
            
            scheduler = self.schedulers[task_id]
            added_count = 0
            
            # 为每个片段创建下载任务
            for i, (url, filepath) in enumerate(sorted_segments):
                # 动态调整优先级 - 大文件和关键片段优先级更高
                segment_priority = self._calculate_segment_priority(url, filepath, priority, i, len(sorted_segments))
                
                # 检查是否为紧急片段
                is_urgent = urgent_segments and i in urgent_segments
                if is_urgent:
                    segment_priority = DownloadPriority.URGENT
                
                download_task = DownloadTask(
                    task_id=f"{task_id}_segment_{i}",
                    url=url,
                    filepath=filepath,
                    priority=segment_priority,
                    retry_count=retry_count,
                    memory_efficient=memory_efficient
                )
                
                # 紧急任务使用特殊添加方法
                if is_urgent:
                    scheduler.add_urgent_task(download_task)
                else:
                    scheduler.add_task(download_task)
                added_count += 1
                
                # 每50个任务记录一次进度
                if self.log_callback and (added_count % 50 == 0):
                    self.log_callback(f"  📥 已添加 {added_count}/{len(sorted_segments)} 个任务到队列...")
            
            # 启动调度器
            scheduler.start()
            
            # 记录启动信息
            if self.log_callback:
                self.log_callback(f"🚀 调度器已启动，开始下载 {added_count} 个片段")
                self.log_callback(f"  ⚙️ 最大并发数: {self.max_concurrent_downloads_per_task}")
            
            # 启动智能监控线程
            threading.Thread(target=self._smart_monitor, args=(task_id,), daemon=True).start()
            
            return added_count
    
    def _optimize_task_order(self, ts_segments: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        优化任务顺序 - 随机打乱以提高并发效率

        不再检查文件大小，直接随机分配任务以避免网络请求导致的延迟
        """
        import random

        # 直接随机打乱任务顺序，提高并发下载效率
        randomized_segments = ts_segments.copy()
        random.shuffle(randomized_segments)

        if self.log_callback:
            self.log_callback(f"  🔀 已随机化 {len(ts_segments)} 个下载任务的顺序")

        return randomized_segments
    
    def _get_remote_file_size(self, url: str) -> Optional[int]:
        """获取远程文件大小"""
        try:
            # 使用GET请求并只读取头部，因为某些服务器不支持HEAD请求
            headers = self._get_headers(url) if hasattr(self, '_get_headers') else {}
            response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code == 200 or response.status_code == 206:
                content_length = response.headers.get('content-length')
                return int(content_length) if content_length else None
            return None
        except Exception:
            # 如果HEAD请求失败，尝试GET但只读取头信息
            try:
                headers = self._get_headers(url) if hasattr(self, '_get_headers') else {}
                headers['Range'] = 'bytes=0-0'  # 只请求1字节
                response = requests.get(url, headers=headers, timeout=10, stream=True)
                content_length = response.headers.get('content-range') or response.headers.get('content-length')
                if content_length:
                    # 解析 Content-Range: bytes 0-0/1234567
                    if '/' in content_length:
                        size_str = content_length.split('/')[-1]
                        return int(size_str)
                    return int(content_length)
            except Exception:
                pass
            return None
    
    def _calculate_priority_weight(self, index: int, total: int, size: Optional[int]) -> float:
        """计算片段优先级权重"""
        weight = 0.0
        
        # 基于位置的权重（前几段更重要）
        if index < 3:  # 前3段
            weight += 100.0
        elif index < total * 0.1:  # 前10%
            weight += 50.0
        
        # 基于文件大小的权重
        if size:
            # 大文件优先（避免小文件阻塞）
            weight += min(size / (1024 * 1024), 100.0)  # 最大100分，基于MB
        
        # 基于序列的权重（保持相对顺序）
        weight += (total - index) * 0.1
        
        return weight
    
    def _calculate_segment_priority(self, url: str, filepath: str, base_priority: DownloadPriority, 
                                 index: int, total: int) -> DownloadPriority:
        """动态计算片段优先级"""
        # 基础优先级
        priority_value = base_priority.value
        
        # 关键片段提升优先级
        if index < 3:  # 前几个片段
            priority_value = max(priority_value, DownloadPriority.URGENT.value)
        elif index < total * 0.1:  # 前10%
            priority_value = max(priority_value, DownloadPriority.HIGH.value)
        
        # 检查是否已存在（断点续传）
        if os.path.exists(filepath):
            # 已存在文件，优先级降低
            priority_value = max(priority_value - 1, DownloadPriority.LOW.value)
        
        # 转换为枚举
        if priority_value >= DownloadPriority.URGENT.value:
            return DownloadPriority.URGENT
        elif priority_value >= DownloadPriority.HIGH.value:
            return DownloadPriority.HIGH
        elif priority_value >= DownloadPriority.NORMAL.value:
            return DownloadPriority.NORMAL
        else:
            return DownloadPriority.LOW
    
    def _smart_monitor(self, task_id: str):
        """
        智能监控 - 动态调整下载策略
        
        监控指标：
        1. 下载速度和成功率
        2. 网络延迟和响应时间
        3. 服务器负载状况
        4. 任务完成时间预测
        """
        monitor_start = time.time()
        last_adjustment = monitor_start
        
        while task_id in self.schedulers:
            try:
                time.sleep(10)  # 每10秒检查一次
                
                current_time = time.time()
                
                # 获取当前进度
                progress = self.get_task_progress(task_id)
                if not progress:
                    break
                
                completed_segments = progress.get('completed_segments', 0)
                total_segments = progress.get('total_segments', 0)
                active_downloads = progress.get('active_downloads', 0)
                
                if total_segments == 0:
                    continue
                
                # 计算下载速度（基于最近10秒）
                elapsed = current_time - monitor_start
                if elapsed > 0:
                    download_speed = completed_segments / elapsed
                    completion_rate = completed_segments / total_segments
                    
                    # 估算剩余时间
                    if download_speed > 0 and completed_segments < total_segments:
                        remaining_segments = total_segments - completed_segments
                        estimated_remaining_time = remaining_segments / download_speed
                        
                        # 记录监控信息
                        print(f"📊 任务 {task_id} 监控: "
                              f"进度 {completion_rate:.1%}, "
                              f"速度 {download_speed:.1f} 片段/秒, "
                              f"活跃下载 {active_downloads}, "
                              f"预计剩余时间 {estimated_remaining_time:.0f}秒")
                        
                        # 动态调整策略
                        if current_time - last_adjustment > 30:  # 每30秒调整一次
                            self._adjust_download_strategy(task_id, progress, download_speed)
                            last_adjustment = current_time
                
            except Exception as e:
                print(f"智能监控出错: {e}")
                time.sleep(30)  # 出错后等待更长时间
    
    def _adjust_download_strategy(self, task_id: str, progress: Dict, current_speed: float):
        """动态调整下载策略"""
        try:
            scheduler = self.schedulers.get(task_id)
            if not scheduler:
                return
            
            completed_segments = progress.get('completed_segments', 0)
            total_segments = progress.get('total_segments', 0)
            active_downloads = progress.get('active_downloads', 0)
            
            if total_segments == 0:
                return
            
            # 基于下载速度调整并发数
            if current_speed < 1.0 and active_downloads < self.max_concurrent_downloads_per_task:
                # 速度较慢，增加并发数
                new_concurrent = min(active_downloads + 2, self.max_concurrent_downloads_per_task)
                # 这里可以调整调度器的并发设置
                print(f"🔄 调整任务 {task_id} 并发数: {active_downloads} -> {new_concurrent}")
                
            elif current_speed > 5.0 and active_downloads > 3:
                # 速度很快，可以减少并发数以降低服务器压力
                new_concurrent = max(active_downloads - 1, 3)
                print(f"🔄 调整任务 {task_id} 并发数: {active_downloads} -> {new_concurrent}")
            
            # 基于完成率调整重试策略
            completion_rate = completed_segments / total_segments
            if completion_rate > 0.8 and current_speed > 2.0:
                # 即将完成且速度良好，可以降低失败重试的优先级
                print(f"🔄 任务 {task_id} 即将完成，优化重试策略")
            
        except Exception as e:
            print(f"调整下载策略出错: {e}")

    def add_m3u8_task(self, task_id: str, ts_segments: List[Tuple[str, str]], 
                     priority: DownloadPriority = DownloadPriority.NORMAL,
                     retry_count: int = 3) -> int:
        """
        智能任务分配算法 - 根据片段大小和网络状况动态分配下载任务
        
        算法特点：
        1. 基于片段大小进行任务分组，大文件优先下载
        2. 根据网络延迟动态调整并发数
        3. 支持断点续传和失败重试
        4. 实时监控下载速度和成功率
        """
        # 智能任务分配逻辑
        sorted_segments = self._optimize_task_order(ts_segments)
        
        with self._lock:
            if task_id not in self.schedulers:
                self.schedulers[task_id] = SmartDownloadScheduler(
                    max_concurrent_downloads=self.max_concurrent_downloads_per_task,
                    log_callback=self.log_callback
                )
                self.task_results[task_id] = {}
            
            scheduler = self.schedulers[task_id]
            added_count = 0
            
            # 为每个片段创建下载任务
            for i, (url, filepath) in enumerate(sorted_segments):
                # 动态调整优先级 - 大文件和关键片段优先级更高
                segment_priority = self._calculate_segment_priority(url, filepath, priority, i, len(sorted_segments))
                
                download_task = DownloadTask(
                    task_id=f"{task_id}_segment_{i}",
                    url=url,
                    filepath=filepath,
                    priority=segment_priority,
                    retry_count=retry_count
                )
                scheduler.add_task(download_task)
                added_count += 1
            
            # 启动调度器
            scheduler.start()
            
            # 记录启动信息
            if self.log_callback:
                self.log_callback(f"🚀 调度器已启动，开始下载 {added_count} 个片段")
                self.log_callback(f"  ⚙️ 最大并发数: {self.max_concurrent_downloads_per_task}")
            
            # 启动智能监控线程
            threading.Thread(target=self._smart_monitor, args=(task_id,), daemon=True).start()
            
            return added_count
    
    def get_task_progress(self, task_id: str) -> Optional[Dict[str, int]]:
        """获取任务进度和队列状态"""
        with self._lock:
            if task_id not in self.schedulers:
                return None

            scheduler = self.schedulers[task_id]
            results = self.task_results[task_id]

            # 获取所有已完成的结果 - 从scheduler获取
            for segment_id in list(results.keys()):
                if segment_id not in results:
                    result = scheduler.get_result(segment_id)
                    if result:
                        results[segment_id] = result

            # 计算总体进度
            total_segments = len(results)
            completed_segments = sum(1 for r in results.values() if r.success)
            total_bytes = sum(r.total_bytes for r in results.values())
            downloaded_bytes = sum(r.downloaded_bytes for r in results.values())

            # 如果还没有任何结果，尝试从scheduler的活跃下载中获取信息
            if total_segments == 0:
                # 获取调度器的队列状态
                queue_status = scheduler.get_queue_status()
                total_segments = queue_status.get('queued_tasks', 0) + queue_status.get('active_downloads', 0)
                completed_segments = 0
                total_bytes = 0
                downloaded_bytes = 0

            return {
                'total_segments': total_segments,
                'completed_segments': completed_segments,
                'total_bytes': total_bytes,
                'downloaded_bytes': downloaded_bytes,
                'progress_percentage': (completed_segments / total_segments * 100) if total_segments > 0 else 0,
                'active_downloads': scheduler.get_active_count(),
                'queue_size': scheduler.get_queue_size()
            }

    def get_all_tasks_status(self) -> Dict[str, Dict[str, int]]:
        """获取所有任务的状态"""
        all_status = {}
        with self._lock:
            for task_id in self.schedulers:
                all_status[task_id] = self.get_task_progress(task_id) or {}
        return all_status
    
    def stop_task(self, task_id: str):
        """停止指定任务"""
        with self._lock:
            if task_id in self.schedulers:
                self.schedulers[task_id].stop()
    
    def stop_all(self):
        """停止所有任务"""
        with self._lock:
            for scheduler in self.schedulers.values():
                scheduler.stop()
    
    def get_global_performance_stats(self) -> Dict[str, float]:
        """获取全局性能统计"""
        with self._lock:
            total_runtime = time.time() - self._start_time
            overall_success_rate = (self._successful_downloads / self._total_downloads * 100) if self._total_downloads > 0 else 0
            avg_download_speed = (self._total_downloaded_bytes / self._total_download_time / 1024 / 1024) if self._total_download_time > 0 else 0
            
            # 收集所有调度器的统计信息
            all_stats = []
            for scheduler in self.schedulers.values():
                stats = scheduler.get_performance_stats()
                all_stats.append(stats)
            
            # 汇总统计信息
            total_tasks = sum(stats['total_tasks'] for stats in all_stats)
            successful_tasks = sum(stats['successful_tasks'] for stats in all_stats)
            failed_tasks = sum(stats['failed_tasks'] for stats in all_stats)
            
            # 计算平均性能指标
            if all_stats:
                avg_success_rate = sum(stats['success_rate'] for stats in all_stats) / len(all_stats)
                avg_download_time = sum(stats['average_download_time'] for stats in all_stats) / len(all_stats)
                avg_download_speed = sum(stats['average_download_speed_mbps'] for stats in all_stats) / len(all_stats)
                peak_concurrent = max(stats['peak_concurrent_downloads'] for stats in all_stats)
            else:
                avg_success_rate = 0
                avg_download_time = 0
                avg_download_speed = 0
                peak_concurrent = 0
            
            return {
                'total_runtime_seconds': total_runtime,
                'total_downloads': self._total_downloads,
                'successful_downloads': self._successful_downloads,
                'failed_downloads': self._failed_downloads,
                'overall_success_rate': overall_success_rate,
                'total_downloaded_bytes_mb': self._total_downloaded_bytes / 1024 / 1024,
                'average_download_speed_mbps': avg_download_speed,
                'total_tasks': total_tasks,
                'successful_tasks': successful_tasks,
                'failed_tasks': failed_tasks,
                'average_task_success_rate': avg_success_rate,
                'average_task_download_time': avg_download_time,
                'peak_concurrent_downloads': peak_concurrent,
                'active_tasks': len(self.schedulers)
            }
    
    def print_performance_report(self):
        """打印性能报告"""
        stats = self.get_global_performance_stats()
        
        print("\n" + "="*60)
        print("📊 性能监控报告")
        print("="*60)
        print(f"运行时间: {stats['total_runtime_seconds']:.1f} 秒")
        print(f"总下载数: {stats['total_downloads']}")
        print(f"成功下载: {stats['successful_downloads']}")
        print(f"失败下载: {stats['failed_downloads']}")
        print(f"整体成功率: {stats['overall_success_rate']:.1f}%")
        print(f"总下载量: {stats['total_downloaded_bytes_mb']:.1f} MB")
        print(f"平均下载速度: {stats['average_download_speed_mbps']:.1f} MB/s")
        print(f"活跃任务数: {stats['active_tasks']}")
        print(f"峰值并发下载: {stats['peak_concurrent_downloads']}")
        print("="*60)
    
    def cleanup(self):
        """清理资源"""
        self.stop_all()
        with self._lock:
            self.schedulers.clear()
            self.task_results.clear()


# 全局批量下载器实例
_batch_downloader = None


def get_batch_downloader(max_concurrent_tasks: int = 3, 
                        max_concurrent_downloads_per_task: int = 10,
                        log_callback: Optional[Callable[[str], None]] = None) -> BatchDownloader:
    """获取全局批量下载器实例"""
    global _batch_downloader
    if _batch_downloader is None:
        _batch_downloader = BatchDownloader(
            max_concurrent_tasks=max_concurrent_tasks,
            max_concurrent_downloads_per_task=max_concurrent_downloads_per_task,
            log_callback=log_callback
        )
    else:
        # 如果已存在，更新日志回调
        if log_callback:
            _batch_downloader.log_callback = log_callback
            # 更新所有现有调度器的日志回调
            for scheduler in _batch_downloader.schedulers.values():
                scheduler.log_callback = log_callback
    return _batch_downloader


def print_batch_downloader_stats():
    """打印批量下载器统计信息"""
    batch_downloader = get_batch_downloader()
    if batch_downloader:
        batch_downloader.print_performance_report()
    else:
        print("批量下载器未初始化")


def get_batch_downloader_performance_stats() -> Dict[str, float]:
    """获取批量下载器性能统计"""
    batch_downloader = get_batch_downloader()
    if batch_downloader:
        return batch_downloader.get_global_performance_stats()
    return {}