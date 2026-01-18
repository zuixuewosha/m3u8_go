#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载队列管理器
用于管理并发下载任务的数量，实现任务队列调度
"""

import threading
import time
from typing import Dict, List, Callable, Optional
from task_manager import TaskManager, TaskStatus, DownloadTask

class DownloadQueue:
    """下载队列管理器"""
    
    def __init__(self, task_manager: TaskManager, max_concurrent: int = 3):
        """
        初始化下载队列
        
        Args:
            task_manager: 任务管理器实例
            max_concurrent: 最大并发下载数
        """
        self.task_manager = task_manager
        self.max_concurrent = max_concurrent
        self.lock = threading.Lock()
        self.running_tasks: Dict[str, threading.Thread] = {}  # 正在运行的任务 {task_id: thread}
        self.pending_tasks: List[str] = []  # 等待中的任务ID列表
        self.download_callback: Optional[Callable] = None  # 下载回调函数
        self.is_running = True
        
    def set_download_callback(self, callback: Callable):
        """设置下载回调函数"""
        self.download_callback = callback
        
    def add_to_queue(self, task_id: str):
        """将任务添加到队列"""
        with self.lock:
            if task_id not in self.pending_tasks and task_id not in self.running_tasks:
                self.pending_tasks.append(task_id)
                task = self.task_manager.get_task(task_id)
                if task:
                    task.status = TaskStatus.PENDING
                    self.task_manager.update_task_status(task_id, TaskStatus.PENDING)
        
        # 尝试启动任务
        self._try_start_next_task()
        
    def remove_from_queue(self, task_id: str):
        """从队列中移除任务"""
        with self.lock:
            # 从等待队列中移除
            if task_id in self.pending_tasks:
                self.pending_tasks.remove(task_id)
            
            # 如果任务正在运行，停止它
            if task_id in self.running_tasks:
                self.task_manager.update_task_status(task_id, TaskStatus.STOPPED)
                # 注意：线程会自然结束，我们只是标记状态
        
    def _try_start_next_task(self):
        """尝试启动下一个任务"""
        with self.lock:
            # 检查是否还有空位
            if len(self.running_tasks) >= self.max_concurrent:
                return
            
            # 检查是否有等待中的任务
            if not self.pending_tasks:
                return
            
            # 获取第一个等待中的任务
            task_id = self.pending_tasks.pop(0)
            task = self.task_manager.get_task(task_id)
            
            if not task or task.status == TaskStatus.STOPPED:
                # 任务不存在或已被停止，尝试下一个
                self._try_start_next_task()
                return
            
            # 创建下载线程
            if self.download_callback:
                download_thread = threading.Thread(
                    target=self._run_task_with_callback,
                    args=(task_id, task)
                )
                download_thread.daemon = True
                download_thread.start()
                self.running_tasks[task_id] = download_thread
                
                # 更新任务状态
                self.task_manager.update_task_status(task_id, TaskStatus.DOWNLOADING)
        
        # 继续尝试启动更多任务
        self._try_start_next_task()
        
    def _run_task_with_callback(self, task_id: str, task: DownloadTask):
        """运行任务并处理完成回调"""
        try:
            # 调用下载回调函数
            if self.download_callback:
                self.download_callback(
                    task_id,
                    task.url,
                    task.folder,
                    task.thread_count,
                    task.retry_count,
                    task.auto_merge
                )
        except Exception as e:
            # 下载过程中出错
            self.task_manager.set_task_error(task_id, str(e))
        finally:
            # 任务完成或停止后，从运行列表中移除
            with self.lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
            
            # 启动下一个任务
            self._try_start_next_task()
            
    def get_queue_status(self) -> dict:
        """获取队列状态"""
        with self.lock:
            return {
                "running_count": len(self.running_tasks),
                "pending_count": len(self.pending_tasks),
                "max_concurrent": self.max_concurrent,
                "running_tasks": list(self.running_tasks.keys()),
                "pending_tasks": self.pending_tasks.copy()
            }
            
    def set_max_concurrent(self, max_concurrent: int):
        """设置最大并发数"""
        with self.lock:
            self.max_concurrent = max_concurrent
        
        # 尝试启动更多任务
        self._try_start_next_task()
        
    def stop_all(self):
        """停止所有任务"""
        with self.lock:
            # 停止所有运行中的任务
            for task_id in list(self.running_tasks.keys()):
                self.task_manager.update_task_status(task_id, TaskStatus.STOPPED)
            
            # 清空等待队列
            self.pending_tasks.clear()
            self.is_running = False
            
    def clear_pending(self):
        """清空等待队列"""
        with self.lock:
            self.pending_tasks.clear()