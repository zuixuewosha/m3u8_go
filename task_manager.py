#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载任务管理器
用于管理多个下载任务及其状态
"""

import threading
import time
import uuid
import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Callable
from enum import Enum

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "等待中"
    DOWNLOADING = "下载中"
    PAUSED = "已暂停"
    COMPLETED = "已完成"
    FAILED = "已失败"
    STOPPED = "已停止"

@dataclass
class DownloadTask:
    """下载任务数据类"""
    task_id: str
    url: str
    folder: str
    thread_count: int
    retry_count: int
    auto_merge: bool
    name: str = ""  # 添加任务名字段
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: str = ""
    eta: str = ""
    start_time: float = 0
    end_time: float = 0
    error_message: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DownloadTask':
        """从字典创建任务对象"""
        # 转换状态字符串为枚举
        status_value = data.pop('status', TaskStatus.PENDING.value)
        status = TaskStatus.PENDING
        for s in TaskStatus:
            if s.value == status_value:
                status = s
                break
        
        # 创建任务对象
        task = cls(**data, status=status)
        return task

class TaskManager:
    """任务管理器"""
    
    def __init__(self, tasks_file: str = "download_tasks.json", history_file: str = "download_history.json"):
        self.tasks: Dict[str, DownloadTask] = {}
        self.lock = threading.Lock()
        self.listeners: List[Callable] = []
        self.tasks_file = tasks_file
        self.history_file = history_file
        self.load_tasks()
        self.load_history()
        
    def save_tasks(self):
        """保存任务到文件"""
        try:
            # 只保存未完成的任务
            tasks_to_save = {}
            with self.lock:
                for task_id, task in self.tasks.items():
                    # 不保存已完成、已失败或已停止的任务
                    if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                        tasks_to_save[task_id] = task.to_dict()
            
            # 写入文件
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_to_save, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 忽略保存错误
            
    def load_tasks(self):
        """从文件加载任务"""
        try:
            if not os.path.exists(self.tasks_file):
                return
                
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
                
            with self.lock:
                for task_id, task_data in tasks_data.items():
                    try:
                        task = DownloadTask.from_dict(task_data)
                        # 只加载未完成的任务，并将其状态设置为等待中
                        if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                            task.status = TaskStatus.PENDING
                            self.tasks[task_id] = task
                    except Exception:
                        pass  # 忽略加载错误的任务
                        
            self._notify_listeners()
        except Exception:
            pass  # 忽略加载错误
        
    def add_task(self, url: str, folder: str, thread_count: int = 5, 
                 retry_count: int = 3, auto_merge: bool = True, name: str = "") -> str:
        """添加新任务"""
        # 如果没有提供任务名，则从URL中提取
        if not name:
            if os.path.exists(url):
                # 本地文件
                name = os.path.basename(url)
            else:
                # 网络链接
                name = url.split('/')[-1].split('?')[0] or "未知任务"
                if not name.endswith('.m3u8'):
                    name = "M3U8下载任务"
        
        task_id = str(uuid.uuid4())
        task = DownloadTask(
            task_id=task_id,
            url=url,
            folder=folder,
            thread_count=thread_count,
            retry_count=retry_count,
            auto_merge=auto_merge,
            name=name
        )
        
        with self.lock:
            self.tasks[task_id] = task
            
        self._notify_listeners()
        self.save_tasks()
        return task_id
    
    def update_task_status(self, task_id: str, status: TaskStatus):
        """更新任务状态"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = status
                if status == TaskStatus.DOWNLOADING:
                    self.tasks[task_id].start_time = time.time()
                elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                    self.tasks[task_id].end_time = time.time()
                    # 如果任务完成，添加到历史记录
                    if status == TaskStatus.COMPLETED:
                        self._add_to_history(self.tasks[task_id])
                    
        self._notify_listeners()
        self.save_tasks()
    
    def _add_to_history(self, task: DownloadTask):
        """将任务添加到历史记录"""
        try:
            # 加载现有历史记录
            history = self._load_history_data()
            
            # 添加新任务到历史记录
            history.append(task.to_dict())
            
            # 限制历史记录数量（最多保存100条）
            if len(history) > 100:
                history = history[-100:]
            
            # 保存历史记录
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 忽略保存错误
    
    def _load_history_data(self) -> List[dict]:
        """加载历史记录数据"""
        try:
            if not os.path.exists(self.history_file):
                return []
                
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    
    def load_history(self):
        """加载历史记录（仅用于初始化）"""
        self._load_history_data()
    
    def get_history(self) -> List[DownloadTask]:
        """获取历史记录"""
        try:
            history_data = self._load_history_data()
            history = []
            for task_data in history_data:
                try:
                    task = DownloadTask.from_dict(task_data)
                    history.append(task)
                except Exception:
                    pass
            return history
        except Exception:
            return []
    
    def clear_history(self):
        """清除历史记录"""
        try:
            if os.path.exists(self.history_file):
                os.remove(self.history_file)
        except Exception:
            pass
    
    def update_task_progress(self, task_id: str, progress: float, 
                           downloaded_bytes: int = 0, total_bytes: int = 0,
                           speed: str = "", eta: str = ""):
        """更新任务进度"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                # 累加进度而不是直接替换
                if progress > 0:
                    task.progress = min(task.progress + progress, 100.0)
                # 如果progress为0，保持当前进度不变
                if downloaded_bytes > 0:
                    task.downloaded_bytes += downloaded_bytes
                if total_bytes > 0:
                    task.total_bytes = total_bytes
                if speed:
                    task.speed = speed
                if eta:
                    task.eta = eta
    
        self._notify_listeners()
        self.save_tasks()
    
    def set_task_error(self, task_id: str, error_message: str):
        """设置任务错误信息"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].error_message = error_message
                self.tasks[task_id].status = TaskStatus.FAILED
                
        self._notify_listeners()
        self.save_tasks()
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        with self.lock:
            return list(self.tasks.values())
    
    def remove_task(self, task_id: str):
        """移除任务"""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                
        self._notify_listeners()
        self.save_tasks()
    
    def add_listener(self, listener: Callable):
        """添加状态变更监听器"""
        self.listeners.append(listener)
    
    def remove_listener(self, listener: Callable):
        """移除状态变更监听器"""
        if listener in self.listeners:
            self.listeners.remove(listener)
    
    def _notify_listeners(self):
        """通知所有监听器"""
        for listener in self.listeners:
            try:
                listener()
            except Exception:
                pass  # 忽略监听器中的错误

# 全局任务管理器实例
task_manager = TaskManager()