#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3U8 下载器 - 现代化版本
使用 ttkbootstrap 实现现代化 UI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import subprocess
import requests
from urllib.parse import urljoin, urlparse
import re
import time
from datetime import datetime

try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
    HAS_TTKBOOTSTRAP = True
except ImportError:
    HAS_TTKBOOTSTRAP = False
    import tkinter.ttk as ttk

try:
    import icon
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# 导入任务管理器
from task_manager import task_manager, TaskStatus, DownloadTask
from download_queue import DownloadQueue
from optimized_downloader import DownloadPool
from advanced_downloader import (
    BatchDownloader, DownloadPriority, get_batch_downloader,
    SmartDownloadScheduler, DownloadTask as AdvancedDownloadTask,
    print_batch_downloader_stats, get_batch_downloader_performance_stats
)


class ConfigManager:
    """简单的配置管理器"""
    
    def __init__(self):
        self.config = {
            'download': {
                'speed_limit': 0,
                'default_thread_count': 8,
                'default_retry_count': 5
            },
            'proxy': {
                'enabled': False,
                'http_proxy': '',
                'https_proxy': '',
                'username': '',
                'password': ''
            }
        }
    
    def get_config(self):
        """获取配置"""
        class Config:
            def __init__(self, config_dict):
                self.download = type('DownloadConfig', (), config_dict['download'])()
                self.proxy = type('ProxyConfig', (), config_dict['proxy'])()
        
        return Config(self.config)
    
    def update_download_config(self, speed_limit=0, default_thread_count=8, default_retry_count=5):
        """更新下载配置"""
        self.config['download']['speed_limit'] = speed_limit
        self.config['download']['default_thread_count'] = default_thread_count
        self.config['download']['default_retry_count'] = default_retry_count
    
    def update_proxy_config(self, enabled=False, http_proxy='', https_proxy='', username='', password=''):
        """更新代理配置"""
        self.config['proxy']['enabled'] = enabled
        self.config['proxy']['http_proxy'] = http_proxy
        self.config['proxy']['https_proxy'] = https_proxy
        self.config['proxy']['username'] = username
        self.config['proxy']['password'] = password


class ModernM3U8DownloaderApp:
    """现代化 M3U8 下载器应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("M3U8 下载器 Pro")
        self.root.geometry("1200x900")
        
        # 初始化配置管理器
        self.config_manager = ConfigManager()
        
        # 尝试设置图标
        self.set_icon()
        
        # 设置主题
        self.setup_theme()
        
        # 初始化下载队列管理器
        self.download_queue = DownloadQueue(task_manager, max_concurrent=3)
        self.download_queue.set_download_callback(self.download_m3u8_task)
        
        # 初始化优化下载池
        self.download_pool = DownloadPool(pool_size=5, max_speed=None)
        
        # 初始化高级批量下载器 - 支持智能并发控制
        self.batch_downloader = get_batch_downloader(
            max_concurrent_tasks=3,
            max_concurrent_downloads_per_task=15,  # 增加每个任务的并发数
            log_callback=self.log_message  # 传递日志回调函数
        )
        
        # 初始化智能下载调度器
        self.smart_scheduler = SmartDownloadScheduler(
            max_concurrent_downloads=20  # 提高并发下载数
        )
        
        # 创建界面
        self.create_widgets()
        
        # 下载相关变量
        self.download_thread = None
        self.is_downloading = False
        
        # 添加任务管理器监听器
        task_manager.add_listener(self.update_task_list)
        
        # 初始化时更新一次任务列表
        self.update_task_list()
        
        # 启动定时更新任务列表
        self.auto_update_task_list()
        
    def setup_theme(self):
        """设置应用主题"""
        if HAS_TTKBOOTSTRAP:
            # 使用现代化主题
            style = ttkb.Style(theme="superhero")
            self.style = style
        else:
            # 回退到传统主题
            self.style = ttk.Style()
            self.style.theme_use('clam')
            
    def set_icon(self):
        """设置窗口图标"""
        if HAS_PIL and hasattr(icon, 'img'):
            try:
                img = Image.open(icon.img)
                self.root.iconphoto(True, ImageTk.PhotoImage(img))
            except Exception:
                pass
    
    def create_widgets(self):
        """创建界面组件"""
        # 创建主容器
        main_container = ttk.Frame(self.root, padding="15")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=1)
        
        # 创建标题区域
        self.create_header(main_container)
        
        # 创建任务输入区域
        self.create_input_section(main_container)
        
        # 创建任务列表区域
        self.create_task_list_section(main_container)
        
        # 创建日志区域
        self.create_log_section(main_container)
        
        # 创建状态栏
        self.create_status_bar(main_container)
        
    def create_header(self, parent):
        """创建标题区域"""
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        header_frame.columnconfigure(0, weight=1)
        
        # 标题 - 使用 tk.Label 以支持字体设置
        title_label = tk.Label(
            header_frame,
            text="M3U8 下载器 Pro",
            font=("Helvetica", 24, "bold"),
            fg="#2c3e50",
            bg=self.style.lookup('TFrame', 'background')
        )
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        # 副标题 - 使用 tk.Label 以支持字体设置
        subtitle_label = tk.Label(
            header_frame,
            text="高效、稳定的多线程 M3U8 视频下载工具",
            font=("Helvetica", 10),
            fg="#7f8c8d",
            bg=self.style.lookup('TFrame', 'background')
        )
        subtitle_label.grid(row=1, column=0, sticky=tk.W)
        
    def create_input_section(self, parent):
        """创建任务输入区域"""
        input_frame = ttk.LabelFrame(parent, text="添加新任务", padding="15")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        input_frame.columnconfigure(1, weight=1)
        
        # M3U8 链接输入 - 使用 tk.Label 以支持字体设置
        tk.Label(input_frame, text="M3U8 链接/文件:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 8)
        )
        
        url_frame = ttk.Frame(input_frame)
        url_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 8), padx=(10, 0))
        url_frame.columnconfigure(0, weight=1)
        
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.select_file_btn = ttk.Button(
            url_frame,
            text="选择文件",
            command=self.select_local_m3u8,
            width=10
        )
        self.select_file_btn.grid(row=0, column=1, padx=(5, 0))
        
        # 下载位置选择 - 使用 tk.Label 以支持字体设置
        tk.Label(input_frame, text="下载位置:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, pady=(0, 8)
        )
        
        folder_frame = ttk.Frame(input_frame)
        folder_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(0, 8), padx=(10, 0))
        folder_frame.columnconfigure(0, weight=1)
        
        self.folder_entry = ttk.Entry(folder_frame)
        self.folder_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.browse_btn = ttk.Button(
            folder_frame,
            text="浏览",
            command=self.browse_folder,
            width=10
        )
        self.browse_btn.grid(row=0, column=1, padx=(5, 0))
        
        # 设置区域
        settings_frame = ttk.Frame(input_frame)
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        
        # 线程数设置 - 使用 tk.Label 以支持字体设置
        tk.Label(settings_frame, text="线程数:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.thread_var = tk.StringVar(value="8")
        thread_spinbox = ttk.Spinbox(
            settings_frame,
            from_=1,
            to=32,
            textvariable=self.thread_var,
            width=8
        )
        thread_spinbox.pack(side=tk.LEFT, padx=(5, 20))
        
        # 重试次数设置 - 使用 tk.Label 以支持字体设置
        tk.Label(settings_frame, text="重试次数:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.retry_var = tk.StringVar(value="5")
        retry_spinbox = ttk.Spinbox(
            settings_frame,
            from_=0,
            to=20,
            textvariable=self.retry_var,
            width=8
        )
        retry_spinbox.pack(side=tk.LEFT, padx=(5, 20))
        
        # 自动合并选项
        self.auto_merge_var = tk.BooleanVar(value=True)
        auto_merge_check = ttk.Checkbutton(
            settings_frame,
            text="下载完成后自动合并",
            variable=self.auto_merge_var
        )
        auto_merge_check.pack(side=tk.LEFT, padx=(5, 0))
        
        # 按钮区域 - 紧凑水平布局
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        # 主要按钮 - 添加下载任务
        self.download_btn = ttk.Button(
            button_frame,
            text="🚀 添加下载任务",
            command=self.add_download_task,
            width=15,
            style="Accent.TButton"
        )
        self.download_btn.pack(side=tk.LEFT, padx=(0, 6))

        # 批量导入按钮
        self.batch_import_btn = ttk.Button(
            button_frame,
            text="📂 批量导入",
            command=self.batch_import_tasks,
            width=10,
            style="Outline.TButton"
        )
        self.batch_import_btn.pack(side=tk.LEFT, padx=(0, 6))

        # 合并TS按钮
        self.merge_btn = ttk.Button(
            button_frame,
            text="🔗 合并TS",
            command=self.merge_segments,
            width=8,
            style="Outline.TButton"
        )
        self.merge_btn.pack(side=tk.LEFT, padx=(0, 6))

        # 设置按钮
        self.settings_btn = ttk.Button(
            button_frame,
            text="⚙️ 设置",
            command=self.open_settings_dialog,
            width=6,
            style="Outline.TButton"
        )
        self.settings_btn.pack(side=tk.LEFT)
        
    def create_task_list_section(self, parent):
        """创建任务列表区域"""
        task_frame = ttk.LabelFrame(parent, text="下载任务", padding="15")
        task_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        task_frame.columnconfigure(0, weight=1)
        task_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        
        # 创建任务列表 Treeview - 支持树形结构显示线程
        self.task_tree = ttk.Treeview(
            task_frame,
            columns=("name", "status", "progress", "speed", "eta", "size", "time"),
            show="tree headings",
            height=10
        )
        
        # 设置列标题和宽度
        self.task_tree.heading("name", text="任务名称")
        self.task_tree.heading("status", text="状态")
        self.task_tree.heading("progress", text="进度")
        self.task_tree.heading("speed", text="速度")
        self.task_tree.heading("eta", text="剩余时间")
        self.task_tree.heading("size", text="大小")
        self.task_tree.heading("time", text="时间")
        
        # 设置列标题和宽度
        self.task_tree.heading("#0", text="")
        self.task_tree.column("#0", width=30, stretch=False)
        
        self.task_tree.column("name", width=280, anchor=tk.W)
        self.task_tree.column("status", width=110, anchor=tk.CENTER)
        self.task_tree.column("progress", width=200, anchor=tk.W)
        self.task_tree.column("speed", width=130, anchor=tk.CENTER)
        self.task_tree.column("eta", width=110, anchor=tk.CENTER)
        self.task_tree.column("size", width=160, anchor=tk.CENTER)
        self.task_tree.column("time", width=160, anchor=tk.CENTER)
        
        # 配置交替行颜色（如果支持）
        try:
            self.task_tree.tag_configure("evenrow", background="#f0f0f0")
            self.task_tree.tag_configure("oddrow", background="#ffffff")
        except:
            pass
        
        # 滚动条
        task_scrollbar_y = ttk.Scrollbar(task_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        task_scrollbar_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.task_tree.configure(yscrollcommand=task_scrollbar_y.set)
        
        task_scrollbar_x = ttk.Scrollbar(task_frame, orient=tk.HORIZONTAL, command=self.task_tree.xview)
        task_scrollbar_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.task_tree.configure(xscrollcommand=task_scrollbar_x.set)
        
        self.task_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 任务操作按钮
        task_button_frame = ttk.Frame(task_frame)
        task_button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)
        
        self.start_task_btn = ttk.Button(
            task_button_frame,
            text="▶ 开始任务",
            command=self.start_selected_task,
            width=12,
            style="Success.TButton"
        )
        self.start_task_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_task_btn = ttk.Button(
            task_button_frame,
            text="⏹ 停止任务",
            command=self.stop_selected_task,
            width=12,
            style="Danger.TButton"
        )
        self.stop_task_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.remove_task_btn = ttk.Button(
            task_button_frame,
            text="🗑 移除任务",
            command=self.remove_selected_task,
            width=12
        )
        self.remove_task_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_completed_btn = ttk.Button(
            task_button_frame,
            text="🧹 清除已完成",
            command=self.clear_completed_tasks,
            width=15
        )
        self.clear_completed_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.view_history_btn = ttk.Button(
            task_button_frame,
            text="📜 查看历史",
            command=self.view_download_history,
            width=15
        )
        self.view_history_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.performance_btn = ttk.Button(
            task_button_frame,
            text="📊 性能统计",
            command=self.show_performance_stats,
            width=15,
            style="Accent.TButton"
        )
        self.performance_btn.pack(side=tk.LEFT, padx=(5, 0))

        # 创建任务列表右键菜单
        self.task_context_menu = tk.Menu(self.root, tearoff=0)
        self.task_context_menu.add_command(label="📋 查看M3U8链接", command=self._show_task_m3u8_link)
        self.task_context_menu.add_command(label="📁 查看文件详情", command=self._show_task_file_details)
        self.task_context_menu.add_separator()
        self.task_context_menu.add_command(label="🗑️ 删除任务", command=self._delete_selected_task)

        # 绑定右键事件
        self.task_tree.bind("<Button-3>", self._on_task_right_click)
        
    def create_log_section(self, parent):
        """创建日志区域"""
        log_frame = ttk.LabelFrame(parent, text="下载日志", padding="15")
        log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        
        self.log_text = tk.Text(log_frame, height=8, width=70, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 滚动条
        log_scrollbar_y = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=log_scrollbar_y.set)
        
        log_scrollbar_x = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.log_text.xview)
        log_scrollbar_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.log_text.configure(xscrollcommand=log_scrollbar_x.set)
        
        # 清空日志按钮
        clear_log_btn = ttk.Button(
            log_frame,
            text="清空日志",
            command=self.clear_log
        )
        clear_log_btn.grid(row=2, column=0, pady=(5, 0), sticky=tk.E)
        
    def create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=4, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(1, weight=1)
        
        # 状态图标
        status_icon_label = ttk.Label(status_frame, text="ℹ️")
        status_icon_label.grid(row=0, column=0, padx=(0, 5))
        
        # 状态文本 - 使用 tk.Label 以支持字体设置
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = tk.Label(status_frame, textvariable=self.status_var, font=("Helvetica", 9))
        self.status_label.grid(row=0, column=1, sticky=tk.W)
        
        # 队列状态 - 使用 tk.Label 以支持字体设置
        self.queue_var = tk.StringVar(value="队列: 0/0")
        self.queue_label = tk.Label(status_frame, textvariable=self.queue_var, font=("Helvetica", 9), fg="#2196F3")
        self.queue_label.grid(row=0, column=2, padx=(10, 0))
        
        # 时间显示 - 使用 tk.Label 以支持字体设置
        self.time_var = tk.StringVar(value="")
        self.time_label = tk.Label(status_frame, textvariable=self.time_var, font=("Helvetica", 9))
        self.time_label.grid(row=0, column=3, padx=(10, 0))
        
        # 更新时间
        self.update_time()
        
        # 更新队列状态
        self.update_queue_status()
        
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_var.set(current_time)
        self.root.after(1000, self.update_time)
        
    def update_queue_status(self):
        """更新队列状态显示"""
        status = self.download_queue.get_queue_status()
        queue_text = f"队列: {status['running_count']}/{status['max_concurrent']} (等待: {status['pending_count']})"
        self.queue_var.set(queue_text)
        self.root.after(1000, self.update_queue_status)
        
    def auto_update_task_list(self):
        """自动更新任务列表"""
        self.update_task_list()
        self.root.after(1000, self.auto_update_task_list)
        
    def browse_folder(self):
        """浏览文件夹"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_selected)
            
    def select_local_m3u8(self):
        """选择本地 M3U8 文件"""
        file_selected = filedialog.askopenfilename(
            title="选择 M3U8 文件",
            filetypes=[("M3U8 Files", "*.m3u8"), ("All Files", "*.*")]
        )
        if file_selected:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, file_selected)
            
    def log_message(self, message):
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        
    def format_size(self, bytes_size):
        """格式化文件大小"""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.2f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.2f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"
        
    def add_download_task(self):
        """添加下载任务"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入 M3U8 链接")
            return
            
        folder = self.folder_entry.get().strip()
        if not folder:
            messagebox.showerror("错误", "请选择下载位置")
            return
            
        # 添加任务到任务管理器
        thread_count = int(self.thread_var.get())
        retry_count = int(self.retry_var.get())
        auto_merge = self.auto_merge_var.get()
        
        # 生成任务名
        if os.path.exists(url):
            # 本地文件
            name = os.path.basename(url)
        else:
            # 网络链接
            name = url.split('/')[-1].split('?')[0] or "未知任务"
            if not name.endswith('.m3u8'):
                name = "M3U8 下载任务"
        
        task_id = task_manager.add_task(url, folder, thread_count, retry_count, auto_merge, name)
        
        # 将任务添加到下载队列
        self.download_queue.add_to_queue(task_id)
        
        self.log_message(f"✓ 已添加下载任务到队列: {name}")
        self.status_var.set("已添加下载任务到队列")
        
        # 清空输入框
        self.url_entry.delete(0, tk.END)
        
    def batch_import_tasks(self):
        """批量导入任务"""
        # 选择文本文件
        file_path = filedialog.askopenfilename(
            title="选择批量导入文件",
            filetypes=[
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            # 使用自动编码检测读取文件
            lines = self._read_file_with_encoding(file_path).splitlines()
            
            # 解析文件内容
            imported_count = 0
            default_folder = self.folder_entry.get().strip()
            thread_count = int(self.thread_var.get())
            retry_count = int(self.retry_var.get())
            auto_merge = self.auto_merge_var.get()
            
            for line in lines:
                line = line.strip()
                
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                
                # 支持格式：URL 或 URL|文件夹
                parts = line.split('|')
                url = parts[0].strip()
                folder = parts[1].strip() if len(parts) > 1 else default_folder
                
                # 验证URL或文件路径
                if not (url.startswith('http://') or url.startswith('https://') or os.path.exists(url)):
                    self.log_message(f"⚠ 跳过无效链接: {url}")
                    continue
                
                # 生成任务名
                if os.path.exists(url):
                    name = os.path.basename(url)
                else:
                    name = url.split('/')[-1].split('?')[0] or "批量导入任务"
                    if not name.endswith('.m3u8'):
                        name = f"批量导入_{imported_count + 1}"
                
                # 添加任务
                task_id = task_manager.add_task(url, folder, thread_count, retry_count, auto_merge, name)
                self.download_queue.add_to_queue(task_id)
                imported_count += 1
            
            if imported_count > 0:
                self.log_message(f"✓ 已批量导入 {imported_count} 个任务")
                self.status_var.set(f"已批量导入 {imported_count} 个任务")
                messagebox.showinfo("批量导入", f"成功导入 {imported_count} 个下载任务！")
            else:
                self.log_message("⚠ 未找到有效的任务链接")
                messagebox.showwarning("批量导入", "未找到有效的任务链接！")
                
        except Exception as e:
            self.log_message(f"✗ 批量导入失败: {str(e)}")
            messagebox.showerror("批量导入错误", f"导入失败: {str(e)}")
            
    def start_selected_task(self):
        """开始选中的任务"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showerror("错误", "请选择要开始的任务")
            return
            
        task_id = selected[0]
        task = task_manager.get_task(task_id)
        if task:
            # 将任务添加到下载队列
            self.download_queue.add_to_queue(task_id)
            self.log_message(f"▶ 已将任务添加到队列: {task.name}")
            self.status_var.set("任务已添加到队列")
            
    def stop_selected_task(self):
        """停止选中的任务"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showerror("错误", "请选择要停止的任务")
            return
            
        task_id = selected[0]
        task = task_manager.get_task(task_id)
        if task:
            # 从队列中移除任务
            self.download_queue.remove_from_queue(task_id)
            self.log_message(f"⏹ 已停止任务: {task.name}")
            self.status_var.set("任务已停止")
            
    def remove_selected_task(self):
        """移除选中的任务"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showerror("错误", "请选择要移除的任务")
            return
            
        task_id = selected[0]
        task = task_manager.get_task(task_id)
        if task:
            task_manager.remove_task(task_id)
            self.log_message(f"🗑 已移除任务: {task.name}")
            self.status_var.set("任务已移除")
            
    def clear_completed_tasks(self):
        """清除已完成的任务"""
        tasks = task_manager.get_all_tasks()
        completed_count = 0
        for task in tasks:
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                task_manager.remove_task(task.task_id)
                completed_count += 1
                
        if completed_count > 0:
            self.log_message(f"✓ 已清除 {completed_count} 个已完成的任务")
            self.status_var.set(f"已清除 {completed_count} 个任务")
        else:
            self.log_message("没有已完成的任务")
            
    def view_download_history(self):
        """查看下载历史记录"""
        # 创建历史记录窗口
        history_window = tk.Toplevel(self.root)
        history_window.title("下载历史记录")
        history_window.geometry("900x500")
        
        # 主容器
        main_frame = ttk.Frame(history_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            main_frame,
            text="📜 下载历史记录",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # 历史记录列表
        history_frame = ttk.Frame(main_frame)
        history_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建历史记录 Treeview
        history_tree = ttk.Treeview(
            history_frame,
            columns=("name", "url", "folder", "size", "time", "duration"),
            show="headings",
            height=15
        )
        
        # 设置列标题和宽度
        history_tree.heading("name", text="任务名称")
        history_tree.heading("url", text="链接")
        history_tree.heading("folder", text="下载位置")
        history_tree.heading("size", text="大小")
        history_tree.heading("time", text="完成时间")
        history_tree.heading("duration", text="耗时")
        
        history_tree.column("name", width=150)
        history_tree.column("url", width=200)
        history_tree.column("folder", width=200)
        history_tree.column("size", width=100)
        history_tree.column("time", width=150)
        history_tree.column("duration", width=100)
        
        # 滚动条
        scrollbar_y = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=history_tree.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        history_tree.configure(yscrollcommand=scrollbar_y.set)
        
        scrollbar_x = ttk.Scrollbar(history_frame, orient=tk.HORIZONTAL, command=history_tree.xview)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        history_tree.configure(xscrollcommand=scrollbar_x.set)
        
        history_tree.pack(fill=tk.BOTH, expand=True)
        
        # 加载历史记录
        history_tasks = task_manager.get_history()
        
        if not history_tasks:
            # 空记录提示
            empty_label = ttk.Label(
                main_frame,
                text="暂无历史记录",
                font=("Helvetica", 12),
                foreground="#9E9E9E"
            )
            empty_label.pack(pady=20)
        else:
            # 添加历史记录到列表
            for task in reversed(history_tasks):  # 最新的显示在最前面
                # 格式化大小
                size_str = ""
                if task.total_bytes > 0:
                    size_str = self.format_size(task.total_bytes)
                elif task.downloaded_bytes > 0:
                    size_str = self.format_size(task.downloaded_bytes)
                
                # 格式化完成时间
                time_str = ""
                if task.end_time > 0:
                    time_str = datetime.fromtimestamp(task.end_time).strftime("%Y-%m-%d %H:%M:%S")
                
                # 格式化耗时
                duration_str = ""
                if task.start_time > 0 and task.end_time > 0:
                    duration = task.end_time - task.start_time
                    duration_str = self.format_duration(duration)
                
                # 截断URL显示
                url_display = task.url
                if len(url_display) > 50:
                    url_display = url_display[:47] + "..."
                
                # 截断文件夹显示
                folder_display = task.folder
                if len(folder_display) > 40:
                    folder_display = folder_display[:37] + "..."
                
                history_tree.insert("", tk.END, values=(
                    task.name,
                    url_display,
                    folder_display,
                    size_str,
                    time_str,
                    duration_str
                ), tags=(task.task_id,))

        # 绑定双击事件 - 双击重新添加任务
        history_tree.bind("<Double-1>", lambda e: self._on_history_double_click(e, history_tree))

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(15, 0))
        
        # 清除历史按钮
        clear_history_btn = ttk.Button(
            button_frame,
            text="清除历史记录",
            command=lambda: self.clear_download_history(history_window, history_tree)
        )
        clear_history_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 关闭按钮
        close_btn = ttk.Button(
            button_frame,
            text="关闭",
            command=history_window.destroy
        )
        close_btn.pack(side=tk.LEFT)
        
    def _on_task_right_click(self, event):
        """处理任务列表右键点击事件"""
        # 获取点击位置的项
        item = self.task_tree.identify_row(event.y)
        if item:
            # 选中该项
            self.task_tree.selection_set(item)
            # 显示右键菜单
            self.task_context_menu.post(event.x_root, event.y_root)

    def _show_task_m3u8_link(self):
        """显示选中任务的M3U8链接"""
        selected_items = self.task_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择一个任务")
            return

        task_id = selected_items[0]
        task = task_manager.get_task(task_id)
        if not task:
            messagebox.showerror("错误", "未找到任务信息")
            return

        # 创建链接显示窗口
        link_window = tk.Toplevel(self.root)
        link_window.title("M3U8链接")
        link_window.geometry("600x150")
        link_window.resizable(True, False)

        # 主框架
        main_frame = ttk.Frame(link_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(
            main_frame,
            text=f"任务: {task.name}",
            font=("Helvetica", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # 链接文本框
        link_frame = ttk.Frame(main_frame)
        link_frame.pack(fill=tk.BOTH, expand=True)

        link_text = tk.Text(
            link_frame,
            height=3,
            wrap=tk.WORD,
            font=("Consolas", 10)
        )
        link_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # 滚动条
        scrollbar = ttk.Scrollbar(link_frame, orient=tk.VERTICAL, command=link_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        link_text.configure(yscrollcommand=scrollbar.set)

        # 插入链接
        link_text.insert(tk.END, task.url)
        link_text.config(state=tk.DISABLED)

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))

        # 复制按钮
        copy_btn = ttk.Button(
            button_frame,
            text="📋 复制链接",
            command=lambda: self._copy_to_clipboard(task.url)
        )
        copy_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 打开浏览器按钮
        open_btn = ttk.Button(
            button_frame,
            text="🌐 在浏览器中打开",
            command=lambda: self._open_in_browser(task.url)
        )
        open_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 关闭按钮
        close_btn = ttk.Button(
            button_frame,
            text="关闭",
            command=link_window.destroy
        )
        close_btn.pack(side=tk.LEFT)

    def _show_task_file_details(self):
        """显示选中任务的文件详情"""
        selected_items = self.task_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择一个任务")
            return

        task_id = selected_items[0]
        task = task_manager.get_task(task_id)
        if not task:
            messagebox.showerror("错误", "未找到任务信息")
            return

        # 创建详情窗口
        details_window = tk.Toplevel(self.root)
        details_window.title("任务文件详情")
        details_window.geometry("500x400")

        # 主框架
        main_frame = ttk.Frame(details_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(
            main_frame,
            text=f"任务详情: {task.name}",
            font=("Helvetica", 14, "bold")
        )
        title_label.pack(pady=(0, 15))

        # 详情框架
        details_frame = ttk.LabelFrame(main_frame, text="基本信息", padding="10")
        details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 创建详情文本
        details_text = tk.Text(
            details_frame,
            height=12,
            wrap=tk.WORD,
            font=("Consolas", 10),
            state=tk.DISABLED
        )
        details_text.pack(fill=tk.BOTH, expand=True)

        # 插入任务详情
        details_info = f"""任务ID: {task.task_id}
任务名称: {task.name}
下载链接: {task.url}
下载位置: {task.folder}
线程数: {task.thread_count}
重试次数: {task.retry_count}
自动合并: {'是' if task.auto_merge else '否'}
任务状态: {task.status.value}
下载进度: {task.progress:.1f}%
已下载大小: {self.format_size(task.downloaded_bytes)}
总大小: {self.format_size(task.total_bytes) if task.total_bytes > 0 else '未知'}
下载速度: {task.speed}
预计剩余时间: {task.eta}"""

        if task.start_time > 0:
            from datetime import datetime
            start_time_str = datetime.fromtimestamp(task.start_time).strftime("%Y-%m-%d %H:%M:%S")
            details_info += f"\n开始时间: {start_time_str}"

        if task.end_time > 0:
            from datetime import datetime
            end_time_str = datetime.fromtimestamp(task.end_time).strftime("%Y-%m-%d %H:%M:%S")
            duration = task.end_time - task.start_time
            details_info += f"\n结束时间: {end_time_str}"
            details_info += f"\n总耗时: {self.format_duration(duration)}"

        if task.error_message:
            details_info += f"\n错误信息: {task.error_message}"

        details_text.config(state=tk.NORMAL)
        details_text.insert(tk.END, details_info)
        details_text.config(state=tk.DISABLED)

        # 文件列表框架（如果有下载的文件）
        if task.status == TaskStatus.COMPLETED and os.path.exists(task.folder):
            files_frame = ttk.LabelFrame(main_frame, text="下载文件", padding="10")
            files_frame.pack(fill=tk.BOTH, expand=True)

            files_text = tk.Text(
                files_frame,
                height=6,
                wrap=tk.WORD,
                font=("Consolas", 9),
                state=tk.DISABLED
            )
            files_text.pack(fill=tk.BOTH, expand=True)

            # 查找下载的文件
            try:
                files_info = ""
                if os.path.exists(task.folder):
                    files = os.listdir(task.folder)
                    ts_files = [f for f in files if f.endswith('.ts') and f.startswith(f"{task_id[:8]}_segment_")]
                    mp4_files = [f for f in files if f.endswith('.mp4') and task.name in f]

                    if mp4_files:
                        files_info += "合并后的MP4文件:\n"
                        for mp4_file in mp4_files:
                            file_path = os.path.join(task.folder, mp4_file)
                            if os.path.exists(file_path):
                                size = os.path.getsize(file_path)
                                files_info += f"  • {mp4_file} ({self.format_size(size)})\n"

                    if ts_files:
                        files_info += f"\nTS片段文件 ({len(ts_files)} 个):\n"
                        total_size = 0
                        for i, ts_file in enumerate(sorted(ts_files)[:5]):  # 只显示前5个
                            file_path = os.path.join(task.folder, ts_file)
                            if os.path.exists(file_path):
                                size = os.path.getsize(file_path)
                                total_size += size
                                files_info += f"  • {ts_file} ({self.format_size(size)})\n"

                        if len(ts_files) > 5:
                            files_info += f"  ... 还有 {len(ts_files) - 5} 个文件\n"
                            files_info += f"  总大小: {self.format_size(total_size)}\n"

                if not files_info:
                    files_info = "未找到相关文件"

                files_text.config(state=tk.NORMAL)
                files_text.insert(tk.END, files_info)
                files_text.config(state=tk.DISABLED)

            except Exception as e:
                files_text.config(state=tk.NORMAL)
                files_text.insert(tk.END, f"获取文件信息时出错: {str(e)}")
                files_text.config(state=tk.DISABLED)

        # 关闭按钮
        close_btn = ttk.Button(
            main_frame,
            text="关闭",
            command=details_window.destroy
        )
        close_btn.pack(pady=(10, 0))

    def _delete_selected_task(self):
        """删除选中的任务"""
        selected_items = self.task_tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选择一个任务")
            return

        task_id = selected_items[0]
        task = task_manager.get_task(task_id)
        if not task:
            messagebox.showerror("错误", "未找到任务信息")
            return

        # 确认删除
        if not messagebox.askyesno("确认删除", f"确定要删除任务：\n{task.name}\n\n此操作不可撤销。"):
            return

        try:
            # 停止任务（如果正在运行）
            if task.status == TaskStatus.DOWNLOADING:
                self.batch_downloader.stop_task(task_id)

            # 从任务管理器中移除
            task_manager.remove_task(task_id)

            # 重新更新任务列表
            self.update_task_list()

            self.log_message(f"✓ 已删除任务: {task.name}")
            messagebox.showinfo("成功", f"任务已删除：{task.name}")

        except Exception as e:
            error_msg = str(e)
            self.log_message(f"✗ 删除任务失败: {error_msg}")
            messagebox.showerror("错误", f"删除任务失败：{error_msg}")

    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("成功", "链接已复制到剪贴板")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败：{str(e)}")

    def _open_in_browser(self, url):
        """在浏览器中打开URL"""
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("错误", f"打开浏览器失败：{str(e)}")

    def _on_history_double_click(self, event, history_tree):
        """处理历史记录双击事件 - 重新添加任务"""
        # 获取选中的项
        selected_item = history_tree.selection()
        if not selected_item:
            return

        item = selected_item[0]
        tags = history_tree.item(item, 'tags')
        if not tags:
            return

        task_id = tags[0]

        # 从task_manager获取所有历史任务
        history_tasks = task_manager.get_history()
        selected_task = None
        for task in history_tasks:
            if task.task_id == task_id:
                selected_task = task
                break

        if not selected_task:
            messagebox.showerror("错误", "未找到对应的历史任务")
            return

        # 确认重新添加任务
        if not messagebox.askyesno("确认", f"确定要重新下载任务：\n{selected_task.name}\n\n链接：{selected_task.url}"):
            return

        try:
            # 设置UI控件的值
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, selected_task.url)

            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, selected_task.folder)

            self.thread_var.set(str(selected_task.thread_count))
            self.retry_var.set(str(selected_task.retry_count))
            self.auto_merge_var.set(selected_task.auto_merge)

            # 调用添加任务方法
            self.add_download_task()

            messagebox.showinfo("成功", f"已重新添加任务：{selected_task.name}")

        except Exception as e:
            error_msg = str(e)
            self.log_message(f"✗ 重新添加历史任务失败: {error_msg}")
            messagebox.showerror("错误", f"重新添加任务失败：{error_msg}")

    def clear_download_history(self, window, tree):
        """清除下载历史记录"""
        if messagebox.askyesno("确认", "确定要清除所有历史记录吗？"):
            task_manager.clear_history()
            self.log_message("✓ 已清除所有历史记录")

            # 清空列表
            for item in tree.get_children():
                tree.delete(item)

            # 显示空记录提示
            empty_label = ttk.Label(
                window.winfo_children()[0],  # main_frame
                text="暂无历史记录",
                font=("Helvetica", 12),
                foreground="#9E9E9E"
            )
            empty_label.pack(pady=20)

            messagebox.showinfo("成功", "历史记录已清除")
            
    def update_task_list(self):
        """更新任务列表显示 - 支持显示每个下载线程的进度"""
        # 保存当前选中项和展开状态
        selected = self.task_tree.selection()
        expanded_items = set()
        for item in self.task_tree.get_children():
            if self.task_tree.item(item).get('open'):
                expanded_items.add(item)
        
        # 获取所有任务
        tasks = task_manager.get_all_tasks()
        task_ids = {task.task_id for task in tasks}
        
        # 获取当前树中的所有项（包括父节点和子节点）
        all_items = set()
        for item in self.task_tree.get_children():
            all_items.add(item)
            # 获取子节点
            for child in self.task_tree.get_children(item):
                all_items.add(child)
        
        # 删除不再存在的任务
        for item in all_items - task_ids:
            self.task_tree.delete(item)
        
        # 更新或添加任务
        for task in tasks:
            # 创建进度条文本
            progress_bar = self.create_progress_bar(task.progress)
            
            # 格式化大小
            size_str = ""
            if task.total_bytes > 0:
                size_str = f"{self.format_size(task.downloaded_bytes)} / {self.format_size(task.total_bytes)}"
            elif task.downloaded_bytes > 0:
                size_str = f"{self.format_size(task.downloaded_bytes)}"
            
            # 状态图标和颜色
            status_text = task.status.value
            status_color = "black"
            if task.status == TaskStatus.DOWNLOADING:
                status_text = f"🔄 下载中"
                status_color = "#2196F3"
            elif task.status == TaskStatus.COMPLETED:
                status_text = f"✓ 已完成"
                status_color = "#4CAF50"
            elif task.status == TaskStatus.FAILED:
                status_text = f"✗ 失败"
                status_color = "#F44336"
            elif task.status == TaskStatus.STOPPED:
                status_text = f"⏹ 已停止"
                status_color = "#FF9800"
            elif task.status == TaskStatus.PENDING:
                status_text = f"⏳ 等待中"
                status_color = "#9E9E9E"
            
            # 格式化时间
            time_str = ""
            if task.start_time > 0:
                if task.end_time > 0:
                    # 已完成
                    duration = task.end_time - task.start_time
                    time_str = f"耗时: {self.format_duration(duration)}"
                else:
                    # 进行中
                    duration = time.time() - task.start_time
                    time_str = f"已运行: {self.format_duration(duration)}"
            
            # 检查任务是否已存在于树中
            task_exists = self.task_tree.exists(task.task_id)
            
            if not task_exists:
                # 插入新任务作为父节点
                item_index = len(self.task_tree.get_children())
                tags = (f"status_{task.task_id}",)
                if item_index % 2 == 0:
                    tags = tags + ("evenrow",)
                else:
                    tags = tags + ("oddrow",)
                    
                self.task_tree.insert("", tk.END, iid=task.task_id, text="📁", values=(
                    task.name,
                    status_text,
                    progress_bar,
                    task.speed,
                    task.eta,
                    size_str,
                    time_str
                ), open=False, tags=tags)
            else:
                # 更新现有任务
                self.task_tree.item(task.task_id, text="📁", values=(
                    task.name,
                    status_text,
                    progress_bar,
                    task.speed,
                    task.eta,
                    size_str,
                    time_str
                ))
            
            # 设置状态颜色
            try:
                self.task_tree.tag_configure(f"status_{task.task_id}", foreground=status_color)
                self.task_tree.item(task.task_id, tags=(f"status_{task.task_id}",))
            except Exception:
                pass
            
            # 如果是下载中状态，添加线程子节点
            if task.status == TaskStatus.DOWNLOADING:
                self._update_thread_nodes(task.task_id)
            else:
                # 删除不再需要的线程节点
                for child in self.task_tree.get_children(task.task_id):
                    if child.startswith(f"{task.task_id}_thread_"):
                        self.task_tree.delete(child)
        
        # 恢复选中项
        if selected:
            try:
                self.task_tree.selection_set(selected)
            except Exception:
                pass
    
    def _update_thread_nodes(self, task_id: str):
        """更新任务下的线程节点"""
        try:
            # 从批量下载器获取调度器
            if task_id in self.batch_downloader.schedulers:
                scheduler = self.batch_downloader.schedulers[task_id]
                # 获取活跃下载线程信息
                active_downloads = scheduler.get_active_downloads_info()
                
                # 获取当前所有线程节点
                existing_thread_nodes = set()
                for child in self.task_tree.get_children(task_id):
                    if child.startswith(f"{task_id}_thread_"):
                        existing_thread_nodes.add(child)
                
                # 更新或添加线程节点
                for thread_info in active_downloads:
                    thread_task_id = thread_info['task_id']
                    # 只显示属于当前任务的线程
                    if thread_task_id.startswith(f"{task_id}_segment_"):
                        thread_node_id = f"{task_id}_thread_{thread_task_id}"
                        
                        # 提取片段编号
                        segment_num = ""
                        try:
                            if "_segment_" in thread_task_id:
                                segment_num = thread_task_id.split("_segment_")[-1]
                                segment_num = f"片段 {segment_num}"
                        except:
                            segment_num = "片段"
                        
                        # 计算进度
                        progress = thread_info.get('progress', 0.0) * 100
                        progress_bar = self.create_progress_bar(progress)
                        
                        # 格式化大小
                        downloaded = thread_info.get('downloaded_bytes', 0)
                        total = thread_info.get('total_bytes', 0)
                        size_str = ""
                        if total > 0:
                            size_str = f"{self.format_size(downloaded)} / {self.format_size(total)}"
                        elif downloaded > 0:
                            size_str = f"{self.format_size(downloaded)}"
                        
                        # 格式化速度
                        speed_bps = thread_info.get('speed', 0.0)
                        speed_str = ""
                        if speed_bps > 0:
                            if speed_bps < 1024:
                                speed_str = f"{speed_bps:.2f} B/s"
                            elif speed_bps < 1024 * 1024:
                                speed_str = f"{speed_bps/1024:.2f} KB/s"
                            else:
                                speed_str = f"{speed_bps/(1024*1024):.2f} MB/s"
                        
                        # 格式化已运行时间
                        elapsed = thread_info.get('elapsed_time', 0)
                        time_str = f"已运行: {self.format_duration(elapsed)}" if elapsed > 0 else ""
                        
                        # 计算ETA
                        eta_str = ""
                        if speed_bps > 0 and total > 0:
                            remaining_bytes = total - downloaded
                            if remaining_bytes > 0:
                                eta_seconds = remaining_bytes / speed_bps
                                eta_str = self.format_duration(eta_seconds)
                        
                        if thread_node_id in existing_thread_nodes:
                            # 更新现有线程节点
                            self.task_tree.item(thread_node_id, text="  └─", values=(
                                f"  {segment_num}",
                                "🔄 下载中",
                                progress_bar,
                                speed_str,
                                eta_str,
                                size_str,
                                time_str
                            ))
                            existing_thread_nodes.remove(thread_node_id)
                        else:
                            # 插入新线程节点
                            self.task_tree.insert(task_id, tk.END, iid=thread_node_id, text="  └─", values=(
                                f"  {segment_num}",
                                "🔄 下载中",
                                progress_bar,
                                speed_str,
                                eta_str,
                                size_str,
                                time_str
                            ))
                
                # 删除不再存在的线程节点
                for thread_node_id in existing_thread_nodes:
                    self.task_tree.delete(thread_node_id)
        except Exception as e:
            # 静默处理错误，不影响主流程
            pass
                
    def create_progress_bar(self, progress):
        """创建进度条文本"""
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        return f"{bar} {progress:.1f}%"
        
    def format_duration(self, duration):
        """格式化持续时间"""
        try:
            # 检查duration是否为None或无效值
            if duration is None:
                return "-"
            
            # 尝试直接转换为整数（适用于int/float类型）
            total_seconds = int(duration)
            
            # 检查是否为负数
            if total_seconds < 0:
                return "-"
                
        except (TypeError, ValueError):
            # 如果转换失败，检查是否有total_seconds方法（适用于timedelta对象）
            try:
                total_seconds = int(duration.total_seconds())
                if total_seconds < 0:
                    return "-"
            except (AttributeError, TypeError):
                return "-"
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
                
    def _get_browser_headers(self, url: str) -> dict:
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
    
    def _read_file_with_encoding(self, filepath):
        """读取文件并自动检测编码"""
        # 常见的编码列表
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'shift_jis', 'euc-jp', 'euc-kr', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()
                self.log_message(f"✓ 使用 {encoding} 编码成功读取文件")
                return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.log_message(f"✗ 使用 {encoding} 编码读取文件时出错: {str(e)}")
                continue
        
        # 如果所有编码都失败,使用二进制模式读取并尝试解码
        try:
            with open(filepath, 'rb') as f:
                content_bytes = f.read()
            # 尝试使用chardet检测编码(如果可用)
            try:
                import chardet
                detected = chardet.detect(content_bytes)
                encoding = detected['encoding']
                if encoding:
                    content = content_bytes.decode(encoding, errors='ignore')
                    self.log_message(f"✓ 使用检测到的 {encoding} 编码成功读取文件")
                    return content
            except ImportError:
                pass
            # 最后尝试使用utf-8并忽略错误
            content = content_bytes.decode('utf-8', errors='ignore')
            self.log_message("⚠ 使用 UTF-8 编码(忽略错误)读取文件")
            return content
        except Exception as e:
            raise Exception(f"无法读取文件: {str(e)}")

    def download_m3u8_task(self, task_id, url, folder, thread_count, retry_count, auto_merge):
        """下载 M3U8 文件并解析（任务版本）- 使用高级多线程下载优化"""
        try:
            # 使用新的高级多线程下载方法
            self._download_m3u8_advanced(task_id, url, folder, thread_count, retry_count, auto_merge)
        except Exception as e:
            self.log_message(f"高级下载方法失败，回退到传统方法: {e}")
            # 回退到传统下载方法
            self._download_m3u8_traditional(task_id, url, folder, thread_count, retry_count, auto_merge)
    
    def _download_m3u8_advanced(self, task_id, m3u8_url, folder, thread_count=8, retry_count=5, auto_merge=True):
        """使用高级多线程下载器下载 M3U8"""
        self.log_message(f"🚀 使用高级多线程下载器开始下载任务: {task_id}")
        
        try:
            # 确保下载目录存在
            if not os.path.exists(folder):
                os.makedirs(folder)
                
            # 解析 M3U8 文件
            self.log_message("📋 正在解析 M3U8 文件...")
            
            # 获取 M3U8 内容（支持本地文件和网络链接）
            if os.path.exists(m3u8_url):
                # 本地 M3U8 文件 - 支持多种编码
                m3u8_content = self._read_file_with_encoding(m3u8_url)
                base_url = os.path.dirname(os.path.abspath(m3u8_url)).replace('\\', '/') + '/'
            else:
                # 网络 M3U8 链接 - 添加浏览器请求头以避免403错误
                headers = self._get_browser_headers(m3u8_url)
                response = requests.get(m3u8_url, headers=headers, timeout=15)
                response.raise_for_status()
                m3u8_content = response.text
                # 修复base_url生成逻辑，正确处理URL路径
                parsed_url = urlparse(m3u8_url)
                if parsed_url.path and '/' in parsed_url.path:
                    base_url = f'{parsed_url.scheme}://{parsed_url.netloc}{os.path.dirname(parsed_url.path)}/'
                else:
                    base_url = f'{parsed_url.scheme}://{parsed_url.netloc}/'
            
            # 解析 M3U8 内容，提取 TS 片段链接
            ts_segments = []
            lines = m3u8_content.split('\n')
            
            # 首先检查是否是主M3U8文件（包含子M3U8链接）
            sub_m3u8_urls = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and '.m3u8' in line:
                    # 这是一个子M3U8文件链接
                    if line.startswith('http'):
                        sub_m3u8_url = line
                    else:
                        sub_m3u8_url = urljoin(base_url, line)
                    sub_m3u8_urls.append(sub_m3u8_url)
            
            # 如果有子M3U8文件，获取第一个子M3U8文件的内容
            if sub_m3u8_urls:
                self.log_message(f"发现 {len(sub_m3u8_urls)} 个子M3U8文件，获取第一个...")
                try:
                    sub_headers = self._get_browser_headers(sub_m3u8_urls[0])
                    sub_response = requests.get(sub_m3u8_urls[0], headers=sub_headers, timeout=15)
                    sub_response.raise_for_status()
                    m3u8_content = sub_response.text
                    # 重新解析子M3U8文件，更新base_url为子M3U8文件的路径
                    parsed_sub_url = urlparse(sub_m3u8_urls[0])
                    if parsed_sub_url.path and '/' in parsed_sub_url.path:
                        base_url = f'{parsed_sub_url.scheme}://{parsed_sub_url.netloc}{os.path.dirname(parsed_sub_url.path)}/'
                    else:
                        base_url = f'{parsed_sub_url.scheme}://{parsed_sub_url.netloc}/'
                    self.log_message(f"使用子M3U8文件，新Base URL: {base_url}")
                except Exception as sub_e:
                    self.log_message(f"获取子M3U8文件失败: {sub_e}，继续使用原始内容")
            
            # 重新解析TS片段
            lines = m3u8_content.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                if line and not line.startswith('#') and line.endswith('.ts'):
                    # 这是一个 TS 片段链接
                    if line.startswith('http'):
                        ts_url = line
                    else:
                        ts_url = urljoin(base_url, line)
                    
                    # 使用任务ID前8位作为文件名前缀，避免多任务时文件名冲突
                    task_prefix = task_id[:8] if task_id else "unknown"
                    filename = f"{task_prefix}_segment_{i+1:05d}.ts"
                    filepath = os.path.join(folder, filename)
                    ts_segments.append((ts_url, filepath))
            
            if not ts_segments:
                raise Exception("未找到 TS 片段")
            
            self.log_message(f"📁 找到 {len(ts_segments)} 个 TS 片段")
            
            # 设置任务状态
            task_manager.update_task_status(task_id, TaskStatus.DOWNLOADING)
            task_manager.update_task_progress(task_id, 0.0, 0, len(ts_segments))
            
            # 使用批量下载器并行下载所有片段
            self.log_message(f"⚡ 启动智能多线程下载，最大并发数: {thread_count}")
            
            # 添加任务到批量下载器
            added_count = self.batch_downloader.add_m3u8_task(
                task_id=task_id,
                ts_segments=ts_segments,
                priority=DownloadPriority.HIGH,
                retry_count=retry_count
            )
            
            self.log_message(f"✅ 已添加 {added_count} 个下载任务到队列")
            
            # 监控下载进度
            self._monitor_advanced_download_progress(task_id, len(ts_segments), auto_merge)
            
        except Exception as e:
            error_msg = str(e)
            task_manager.set_task_error(task_id, error_msg)
            self.log_message(f"✗ 高级下载失败: {error_msg}")
            raise
    
    def _monitor_advanced_download_progress(self, task_id, total_segments, auto_merge):
        """监控高级下载进度"""
        self.log_message("📊 开始监控下载进度...")

        last_progress = 0
        consecutive_stalls = 0

        while True:
            try:
                # 获取任务进度
                progress = self.batch_downloader.get_task_progress(task_id)
                
                if not progress:
                    break
                
                completed_segments = progress.get('completed_segments', 0)
                total_bytes = progress.get('total_bytes', 0)
                downloaded_bytes = progress.get('downloaded_bytes', 0)
                active_downloads = progress.get('active_downloads', 0)
                queue_size = progress.get('queue_size', 0)

                # 计算进度百分比 - 使用传入的总片段数作为分母
                progress_percentage = (completed_segments / total_segments * 100) if total_segments > 0 else 0
                
                # 更新任务进度
                task_manager.update_task_progress(
                    task_id, 
                    progress_percentage, 
                    downloaded_bytes, 
                    total_bytes
                )
                
                # 记录详细进度信息
                if int(progress_percentage) != last_progress or consecutive_stalls % 10 == 0:
                    # 计算下载速度
                    speed_info = ""
                    if downloaded_bytes > 0:
                        task = task_manager.get_task(task_id)
                        if task and task.start_time > 0:
                            elapsed = time.time() - task.start_time
                            if elapsed > 0:
                                speed_bps = downloaded_bytes / elapsed
                                if speed_bps < 1024:
                                    speed_info = f", 速度: {speed_bps:.2f} B/s"
                                elif speed_bps < 1024 * 1024:
                                    speed_info = f", 速度: {speed_bps/1024:.2f} KB/s"
                                else:
                                    speed_info = f", 速度: {speed_bps/(1024*1024):.2f} MB/s"
                    
                    # 计算已下载大小
                    size_info = ""
                    if downloaded_bytes > 0:
                        if downloaded_bytes < 1024:
                            size_info = f", 已下载: {downloaded_bytes} B"
                        elif downloaded_bytes < 1024 * 1024:
                            size_info = f", 已下载: {downloaded_bytes/1024:.2f} KB"
                        elif downloaded_bytes < 1024 * 1024 * 1024:
                            size_info = f", 已下载: {downloaded_bytes/(1024*1024):.2f} MB"
                        else:
                            size_info = f", 已下载: {downloaded_bytes/(1024*1024*1024):.2f} GB"
                    
                    self.log_message(
                        f"📈 下载进度: {progress_percentage:.1f}% "
                        f"({completed_segments}/{total_segments} 片段){size_info}"
                        f", 活跃下载: {active_downloads}, 队列剩余: {queue_size}{speed_info}"
                    )
                    last_progress = int(progress_percentage)
                    consecutive_stalls = 0
                else:
                    consecutive_stalls += 1
                
                # 检查是否完成 - 没有活跃下载且队列为空
                if active_downloads == 0 and queue_size == 0:
                    self.log_message("✅ 所有 TS 片段下载完成")
                    task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
                    
                    if auto_merge:
                        self.log_message("🔄 开始自动合并 TS 片段...")
                        # 获取下载目录 - 从任务管理器获取
                        task = task_manager.get_task(task_id)
                        if task:
                            download_folder = task.folder
                            self.log_message(f"📁 下载目录: {download_folder}")

                            # 验证目录存在并包含TS文件
                            if os.path.exists(download_folder):
                                import re
                                ts_pattern = re.compile(r'^[a-f0-9]{8}_segment_\d{5}\.ts$')
                                ts_files = [f for f in os.listdir(download_folder) if f.endswith('.ts') and ts_pattern.match(f)]
                                if ts_files:
                                    self.log_message(f"🎬 找到 {len(ts_files)} 个TS文件，准备合并")
                                    self.root.after(0, lambda: self.merge_segments_auto_task(task_id, download_folder))
                                else:
                                    self.log_message("⚠️ 下载目录中未找到TS文件")
                            else:
                                self.log_message(f"❌ 下载目录不存在: {download_folder}")
                        else:
                            self.log_message("❌ 无法获取任务信息")
                    break
                
                # 检查任务是否被停止
                task = task_manager.get_task(task_id)
                if not task or task.status == TaskStatus.STOPPED:
                    self.log_message("⏹ 下载任务已停止")
                    self.batch_downloader.stop_task(task_id)
                    break
                
                # 检查是否卡死
                if consecutive_stalls > 60:  # 60秒无进度
                    self.log_message("⚠️ 下载进度停滞，尝试重启...")
                    consecutive_stalls = 0
                    # 可以在这里添加重启逻辑
                
                time.sleep(1.0)  # 每秒检查一次
                
            except Exception as e:
                self.log_message(f"⚠️ 监控进度时出错: {e}")
                # 打印详细的进度信息用于调试
                try:
                    if progress:
                        self.log_message(f"  📊 调试信息: 总片段={total_segments}, 已完成={completed_segments}, "
                                       f"活跃下载={active_downloads}, 队列剩余={queue_size}")
                except:
                    pass
                time.sleep(5.0)
    
    def _download_m3u8_traditional(self, task_id, url, folder, thread_count, retry_count, auto_merge):
        """传统的多线程下载方法（作为回退方案）"""
        try:
            # 确保下载目录存在
            if not os.path.exists(folder):
                os.makedirs(folder)
                
            # 获取 M3U8 内容（支持本地文件和网络链接）
            if os.path.exists(url):
                # 本地 M3U8 文件 - 支持多种编码
                m3u8_content = self._read_file_with_encoding(url)
                base_url = os.path.dirname(os.path.abspath(url)).replace('\\', '/') + '/'
            else:
                # 网络 M3U8 链接 - 添加浏览器请求头以避免403错误
                headers = self._get_browser_headers(url)
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                m3u8_content = response.text
                # 修复base_url生成逻辑，正确处理URL路径
                parsed_url = urlparse(url)
                if parsed_url.path and '/' in parsed_url.path:
                    base_url = f'{parsed_url.scheme}://{parsed_url.netloc}{os.path.dirname(parsed_url.path)}/'
                else:
                    base_url = f'{parsed_url.scheme}://{parsed_url.netloc}/'
            
            # 解析 M3U8 内容，提取 TS 片段链接
            ts_segments = []
            lines = m3u8_content.split('\n')
            
            # 首先检查是否是主M3U8文件（包含子M3U8链接）
            sub_m3u8_urls = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and '.m3u8' in line:
                    # 这是一个子M3U8文件链接
                    if line.startswith('http'):
                        sub_m3u8_url = line
                    else:
                        sub_m3u8_url = urljoin(base_url, line)
                    sub_m3u8_urls.append(sub_m3u8_url)
            
            # 如果有子M3U8文件，获取第一个子M3U8文件的内容
            if sub_m3u8_urls:
                self.log_message(f"发现 {len(sub_m3u8_urls)} 个子M3U8文件，获取第一个...")
                try:
                    sub_headers = self._get_browser_headers(sub_m3u8_urls[0])
                    sub_response = requests.get(sub_m3u8_urls[0], headers=sub_headers, timeout=15)
                    sub_response.raise_for_status()
                    m3u8_content = sub_response.text
                    # 重新解析子M3U8文件，更新base_url为子M3U8文件的路径
                    parsed_sub_url = urlparse(sub_m3u8_urls[0])
                    if parsed_sub_url.path and '/' in parsed_sub_url.path:
                        base_url = f'{parsed_sub_url.scheme}://{parsed_sub_url.netloc}{os.path.dirname(parsed_sub_url.path)}/'
                    else:
                        base_url = f'{parsed_sub_url.scheme}://{parsed_sub_url.netloc}/'
                    self.log_message(f"使用子M3U8文件，新Base URL: {base_url}")
                except Exception as sub_e:
                    self.log_message(f"获取子M3U8文件失败: {sub_e}，继续使用原始内容")
            
            # 重新解析TS片段
            lines = m3u8_content.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and line.endswith('.ts'):
                    # 这是一个 TS 片段链接
                    if line.startswith('http'):
                        ts_url = line
                    else:
                        ts_url = urljoin(base_url, line)
                    ts_segments.append(ts_url)
                    
            if not ts_segments:
                task_manager.set_task_error(task_id, "未找到 TS 片段")
                self.log_message("✗ 未找到 TS 片段")
                return
                
            self.log_message(f"✓ 找到 {len(ts_segments)} 个 TS 片段")
            
            # 更新总字节数估算
            total_bytes = 0
            if ts_segments:
                try:
                    downloader = self.download_pool.get_downloader()
                    resp = downloader.head(ts_segments[0])
                    if resp.status_code == 200:
                        content_length = resp.headers.get('content-length')
                        if content_length:
                            estimated_size = int(content_length) * len(ts_segments)
                            total_bytes = estimated_size
                except:
                    pass
                    
            # 使用信号量控制并发数
            semaphore = threading.Semaphore(thread_count)
            
            # 下载统计
            downloaded_bytes = 0
            completed_segments = 0
            total_segments = len(ts_segments)
            
            # 更新任务状态
            task_manager.update_task_progress(task_id, 0.0, 0, total_bytes)
            
            # 下载所有 TS 片段 - 使用优化下载器
            download_threads = []
            for i, ts_url in enumerate(ts_segments):
                # 检查任务是否被停止
                task = task_manager.get_task(task_id)
                if not task or task.status == TaskStatus.STOPPED:
                    break
                    
                # 生成文件名 - 添加任务ID前缀避免冲突
                task_prefix = task_id[:8] if task_id else "unknown"
                filename = f"{task_prefix}_segment_{i+1:05d}.ts"
                filepath = os.path.join(folder, filename)
                
                # 获取下载器实例
                downloader = self.download_pool.get_downloader()
                
                # 创建停止检查函数
                def make_stop_check(task_id):
                    return lambda: not task_manager.get_task(task_id) or task_manager.get_task(task_id).status == TaskStatus.STOPPED
                
                # 创建带绑定参数的进度回调函数
                def make_progress_callback(task_id, estimated_total):
                    return lambda d, t: self.update_task_progress_callback(task_id, d, t, estimated_total)
                
                # 创建下载线程（信号量在下载器内部管理）
                thread = threading.Thread(
                    target=self._download_segment_with_optimizer,
                    args=(downloader, task_id, ts_url, filepath, semaphore, retry_count, 
                          make_progress_callback(task_id, total_bytes), make_stop_check(task_id))
                )
                thread.daemon = True
                thread.start()
                download_threads.append(thread)
                
            # 等待所有下载线程完成
            for thread in download_threads:
                thread.join()
                
            # 检查任务状态
            task = task_manager.get_task(task_id)
            if task and task.status != TaskStatus.STOPPED:
                self.log_message("✓ 所有 TS 片段下载完成")
                task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
                
                # 如果启用了自动合并，则执行合并
                if auto_merge:
                    self.log_message("🔄 开始自动合并 TS 片段...")
                    self.root.after(0, lambda: self.merge_segments_auto_task(task_id, folder))
            else:
                self.log_message("⏹ 下载任务已停止")
                
        except Exception as e:
            error_msg = str(e)
            task_manager.set_task_error(task_id, error_msg)
            self.log_message(f"✗ 下载过程中出现错误: {error_msg}")
            
    def _download_segment_with_optimizer(self, downloader, task_id, url, filepath, semaphore, max_retries, progress_callback, stop_check):
        """使用优化下载器下载单个片段"""
        try:
            # 在下载前获取信号量
            semaphore.acquire()
            
            self.log_message(f"🔄 开始下载片段: {os.path.basename(filepath)} (URL: {url})")
            
            success = downloader.download_segment(
                url=url,
                filepath=filepath,
                progress_callback=progress_callback,
                semaphore=semaphore,
                max_retries=max_retries,
                stop_check=stop_check
            )
            
            if not success:
                task = task_manager.get_task(task_id)
                if task and task.status != TaskStatus.STOPPED:
                    self.log_message(f"✗ 下载 {os.path.basename(filepath)} 失败")
                    # 记录更详细的失败信息
                    self.log_message(f"  - 文件路径: {filepath}")
                    self.log_message(f"  - 下载URL: {url}")
                    self.log_message(f"  - 文件是否存在: {os.path.exists(filepath)}")
                    if os.path.exists(filepath):
                        self.log_message(f"  - 文件大小: {os.path.getsize(filepath)} 字节")
                    
        except Exception as e:
            error_detail = self._parse_download_error(str(e))
            self.log_message(f"✗ 下载 {os.path.basename(filepath)} 时出现异常: {error_detail}")
            self.log_message(f"  - 详细错误: {str(e)}")
            self.log_message(f"  - 文件路径: {filepath}")
            self.log_message(f"  - 下载URL: {url}")
            
    def update_task_progress_callback(self, task_id, downloaded_bytes, total_bytes, estimated_total):
        """更新任务进度的回调函数"""
        # 计算进度百分比
        progress = (downloaded_bytes / estimated_total * 100) if estimated_total > 0 else 0
        progress = min(progress, 100.0)
        
        # 获取任务以计算速度和剩余时间
        task = task_manager.get_task(task_id)
        if task:
            # 计算速度和剩余时间
            current_time = time.time()
            elapsed_time = current_time - task.start_time if task.start_time > 0 else 1
            
            # 计算平均速度
            speed_bps = downloaded_bytes / elapsed_time if elapsed_time > 0 else 0
            
            # 格式化速度
            if speed_bps < 1024:
                speed_str = f"{speed_bps:.2f} B/s"
            elif speed_bps < 1024 * 1024:
                speed_str = f"{speed_bps/1024:.2f} KB/s"
            else:
                speed_str = f"{speed_bps/(1024*1024):.2f} MB/s"
                
            # 计算剩余时间
            if speed_bps > 0 and estimated_total > 0:
                remaining_bytes = estimated_total - downloaded_bytes
                eta_seconds = remaining_bytes / speed_bps
                
                if eta_seconds > 365 * 24 * 3600:
                    eta_str = "> 365天"
                else:
                    eta_str = self.format_time(eta_seconds)
            else:
                eta_str = "--:--:--"
                
            task_manager.update_task_progress(task_id, progress, downloaded_bytes, estimated_total, speed_str, eta_str)
        else:
            task_manager.update_task_progress(task_id, progress, downloaded_bytes, estimated_total)
        
    def download_ts_segment_task(self, task_id, url, filepath, semaphore, max_retries, progress_callback):
        """下载单个 TS 片段（任务版本）"""
        downloaded_bytes = 0
        temp_filepath = filepath + ".tmp"
        
        try:
            self.log_message(f"🔄 开始下载TS片段: {os.path.basename(filepath)}")
            self.log_message(f"  - 下载URL: {url}")
            self.log_message(f"  - 保存路径: {filepath}")
            self.log_message(f"  - 临时文件: {temp_filepath}")
            
            # 检查文件是否已存在
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                downloaded_bytes = file_size
                self.log_message(f"  - 文件已存在，跳过下载，大小: {file_size} 字节")
                progress_callback(downloaded_bytes, file_size)
                semaphore.release()
                return
                
            # 检查是否存在部分下载的文件
            if os.path.exists(temp_filepath):
                file_size = os.path.getsize(temp_filepath)
                downloaded_bytes = file_size
                self.log_message(f"  - 发现临时文件，继续下载，已下载: {file_size} 字节")
                
            # 尝试下载
            for attempt in range(max_retries + 1):
                try:
                    self.log_message(f"  - 第 {attempt + 1} 次下载尝试")
                    
                    # 如果已有部分下载内容，使用 Range 请求继续下载
                    headers = {}
                    if downloaded_bytes > 0:
                        headers['Range'] = f'bytes={downloaded_bytes}-'
                        self.log_message(f"  - 使用断点续传，从第 {downloaded_bytes} 字节开始")
                    
                    response = requests.get(url, timeout=15, stream=True, headers=headers)
                    self.log_message(f"  - HTTP响应状态码: {response.status_code}")
                    
                    # 处理 Range 请求的响应
                    if downloaded_bytes > 0 and response.status_code == 206:
                        self.log_message("  - 断点续传成功")
                        pass
                    elif downloaded_bytes == 0 or response.status_code == 200:
                        downloaded_bytes = 0
                        response.raise_for_status()
                    else:
                        self.log_message(f"  - 意外状态码 {response.status_code}，重新开始下载")
                        downloaded_bytes = 0
                        response = requests.get(url, timeout=15, stream=True)
                        response.raise_for_status()
                    
                    # 获取文件大小
                    content_length = response.headers.get('content-length')
                    if content_length:
                        segment_size = int(content_length) + downloaded_bytes
                        self.log_message(f"  - 文件总大小: {segment_size} 字节")
                    else:
                        segment_size = 0
                        self.log_message("  - 无法获取文件大小")
                    
                    # 下载文件到临时文件
                    with open(temp_filepath, 'ab' if downloaded_bytes > 0 else 'wb') as f:
                        chunk_count = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            # 检查任务是否被停止
                            task = task_manager.get_task(task_id)
                            if not task or task.status == TaskStatus.STOPPED:
                                self.log_message(f"  - 任务被停止，中断下载")
                                semaphore.release()
                                return
                                
                            if chunk:
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                                chunk_count += 1
                                if chunk_count % 100 == 0:  # 每100个chunk记录一次
                                    self.log_message(f"  - 下载进度: {downloaded_bytes}/{segment_size} 字节")
                                progress_callback(downloaded_bytes, segment_size)
                                
                    # 下载成功
                    if segment_size == 0:
                        segment_size = os.path.getsize(temp_filepath)
                        self.log_message(f"  - 实际文件大小: {segment_size} 字节")
                    
                    # 将临时文件重命名为正式文件
                    if os.path.exists(temp_filepath):
                        os.rename(temp_filepath, filepath)
                        self.log_message(f"  - 文件重命名成功: {temp_filepath} -> {filepath}")
                    
                    self.log_message(f"✓ 下载成功: {os.path.basename(filepath)}")
                    break
                    
                except Exception as e:
                    self.log_message(f"  - 第 {attempt + 1} 次尝试失败: {str(e)}")
                    if attempt < max_retries:
                        wait_time = 2 * (attempt + 1)
                        self.log_message(f"  - 等待 {wait_time} 秒后重试")
                        time.sleep(wait_time)
                    else:
                        # 解析HTTP错误信息
                        error_detail = self._parse_download_error(str(e))
                        self.log_message(f"✗ 下载 {os.path.basename(filepath)} 失败: {error_detail}")
                        self.log_message(f"  - 最终错误详情: {str(e)}")
                        if os.path.exists(temp_filepath):
                            self.log_message(f"  - 保留临时文件: {temp_filepath}")
                        
        except Exception as e:
            # 解析HTTP错误信息
            error_detail = self._parse_download_error(str(e))
            self.log_message(f"✗ 下载 {os.path.basename(filepath)} 时出现异常: {error_detail}")
            self.log_message(f"  - 异常详情: {str(e)}")
            self.log_message(f"  - 文件路径: {filepath}")
            self.log_message(f"  - 下载URL: {url}")
            if os.path.exists(temp_filepath):
                self.log_message(f"  - 保留临时文件: {temp_filepath}")
        finally:
            semaphore.release()
            
    def merge_segments_auto_task(self, task_id, folder):
        """自动合并 TS 片段（任务版本）"""
        import time
        start_time = time.time()
        self.log_message(f"🔄 开始合并 TS 片段任务: {task_id}")

        try:
            # 查找 TS 文件 - 支持带任务前缀的文件名
            self.log_message(f"🔍 扫描目录: {folder}")
            all_files = os.listdir(folder)
            # 匹配格式: {task_prefix}_segment_xxxxx.ts
            import re
            ts_pattern = re.compile(r'^[a-f0-9]{8}_segment_\d{5}\.ts$')
            ts_files = [os.path.join(folder, f) for f in all_files if f.endswith('.ts') and ts_pattern.match(f)]

            self.log_message(f"📊 目录总文件数: {len(all_files)}")
            self.log_message(f"🎬 找到 TS 文件数: {len(ts_files)}")

            if not ts_files:
                self.log_message("✗ 未找到 TS 片段文件")
                return

            # 排序 TS 文件 - 按segment编号排序
            def get_segment_number(filename):
                # 从文件名中提取segment编号: {task_prefix}_segment_xxxxx.ts
                try:
                    parts = filename.split('_segment_')
                    if len(parts) == 2:
                        segment_part = parts[1].split('.')[0]  # 去掉 .ts 扩展名
                        return int(segment_part)
                except (ValueError, IndexError):
                    pass
                return 0  # 如果无法解析，返回0

            ts_files.sort(key=get_segment_number)
            self.log_message(f"📁 TS 文件列表 (前5个): {ts_files[:5]}")
            if len(ts_files) > 5:
                self.log_message(f"      ... 还有 {len(ts_files) - 5} 个文件")

            # 计算总大小
            total_size = 0
            for ts_file in ts_files:
                file_path = os.path.join(folder, ts_file)
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    total_size += size
                else:
                    self.log_message(f"⚠️ 文件不存在: {file_path}")

            self.log_message(f"📏 总文件大小: {total_size / (1024*1024):.2f} MB")

            # 获取任务信息用于生成文件名
            task = task_manager.get_task(task_id)
            base_name = "output"
            if task and task.name:
                # 移除文件扩展名（如果有的话）
                base_name = os.path.splitext(task.name)[0]

            # 添加合并完成时间后缀（精确到秒）
            from datetime import datetime
            merge_datetime = datetime.now()
            time_suffix = merge_datetime.strftime("_%Y%m%d_%H%M%S")

            # 生成输出文件名
            output_file = os.path.join(folder, f"{base_name}{time_suffix}.mp4")
            counter = 1
            while os.path.exists(output_file):
                output_file = os.path.join(folder, f"{base_name}{time_suffix}_{counter}.mp4")
                counter += 1

            self.log_message(f"🎯 输出文件: {output_file}")
            self.log_message(f"⏱️ 合并开始时间: {time.strftime('%H:%M:%S')}")

            # 检查 FFmpeg 是否可用
            self.log_message("🔧 检查 FFmpeg 可用性...")
            ffmpeg_available = self._check_ffmpeg_available()
            self.log_message(f"🎬 FFmpeg 状态: {'可用' if ffmpeg_available else '不可用'}")

            if ffmpeg_available:
                self.log_message("🎬 使用 FFmpeg 进行高质量合并")
                success = self._merge_with_ffmpeg_direct(ts_files, output_file, folder)
            else:
                self.log_message("📋 FFmpeg 不可用，使用备用合并方法")
                success = self._merge_with_copy_direct(ts_files, output_file, folder)

            elapsed_time = time.time() - start_time
            if success:
                self.log_message(f"✓ TS 片段合并完成! 输出文件: {output_file}")
                self.log_message(f"⏱️ 合并总耗时: {elapsed_time:.2f} 秒")
                self.log_message(f"📏 输出文件大小: {os.path.getsize(output_file) / (1024*1024):.2f} MB")

                # 清理和重命名操作
                try:
                    # 获取任务信息以确定最终文件名
                    task = task_manager.get_task(task_id)
                    final_output_file = output_file

                    if task:
                        # 从原始 URL 提取文件名
                        original_url = task.url
                        if original_url:
                            # 提取文件名，去掉路径和扩展名
                            if '/' in original_url:
                                filename = original_url.split('/')[-1]
                            else:
                                filename = original_url

                            # 去掉 .m3u8 扩展名，添加 .mp4 扩展名
                            if filename.lower().endswith('.m3u8'):
                                base_name = filename[:-5]  # 去掉 .m3u8
                            else:
                                base_name = filename

                            # 确保文件名不为空
                            if not base_name:
                                base_name = f"video_{task_id[:8]}"

                            # 生成最终文件名
                            final_name = base_name + ".mp4"
                            final_output_file = os.path.join(os.path.dirname(output_file), final_name)

                            # 如果需要重命名
                            if final_output_file != output_file:
                                if os.path.exists(output_file):
                                    os.rename(output_file, final_output_file)
                                    self.log_message(f"📝 文件重命名: {os.path.basename(output_file)} → {os.path.basename(final_output_file)}")
                                output_file = final_output_file

                    # 删除所有 TS 文件
                    self.log_message("🧹 开始清理 TS 片段文件...")
                    deleted_count = 0
                    total_deleted_size = 0

                    for ts_file in ts_files:
                        ts_path = os.path.join(folder, ts_file)
                        try:
                            if os.path.exists(ts_path):
                                file_size = os.path.getsize(ts_path)
                                os.remove(ts_path)
                                deleted_count += 1
                                total_deleted_size += file_size

                                # 每删除50个文件报告一次进度
                                if deleted_count % 50 == 0:
                                    self.log_message(f"  🗑️ 已删除 {deleted_count}/{len(ts_files)} 个文件")

                        except Exception as e:
                            self.log_message(f"  ⚠️ 删除文件失败 {ts_file}: {e}")

                    if deleted_count > 0:
                        self.log_message(f"✅ 清理完成: 删除 {deleted_count} 个 TS 文件")
                        self.log_message(f"  💾 释放磁盘空间: {total_deleted_size / (1024*1024):.2f} MB")

                    # 显示最终结果
                    final_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
                    self.log_message(f"🎉 任务完成! 最终文件: {os.path.basename(output_file)}")
                    self.log_message(f"📏 文件大小: {final_size / (1024*1024):.2f} MB")

                    messagebox.showinfo("成功", f"视频已成功合并并清理!\n\n最终文件: {os.path.basename(output_file)}\n大小: {final_size / (1024*1024):.2f} MB\n删除片段: {deleted_count} 个文件")

                except Exception as cleanup_error:
                    self.log_message(f"⚠️ 清理过程出现异常: {cleanup_error}")
                    # 即使清理失败，也显示成功信息
                    messagebox.showinfo("成功", f"视频已成功合并到:\n{output_file}\n\n⚠️ 清理过程出现异常: {cleanup_error}")
            else:
                self.log_message("✗ 合并失败")
                self.log_message(f"⏱️ 合并失败，耗时: {elapsed_time:.2f} 秒")
                messagebox.showerror("错误", "合并过程中出现错误")

        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = str(e)
            self.log_message(f"✗ 合并过程中出现异常: {error_msg}")
            self.log_message(f"⏱️ 异常发生时间: {elapsed_time:.2f} 秒")
            self.log_message(f"📍 异常位置: {folder}")
            messagebox.showerror("错误", f"合并过程中出现异常:\n{error_msg}")

    def _check_ffmpeg_available(self):
        """检查 FFmpeg 是否可用"""
        self.log_message("🔍 正在检测 FFmpeg...")
        try:
            self.log_message("  📡 执行命令: ffmpeg -version")
            start_time = time.time()
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=10)
            elapsed = time.time() - start_time
            self.log_message(f"  ✅ FFmpeg 检测成功，耗时: {elapsed:.2f}秒")
            # 记录版本信息
            version_line = result.stdout.decode('utf-8', errors='ignore').split('\n')[0]
            self.log_message(f"  ℹ️ FFmpeg 版本: {version_line}")
            return True
        except FileNotFoundError:
            self.log_message("  ❌ FFmpeg 未找到 (FileNotFoundError)")
            return False
        except subprocess.CalledProcessError as e:
            self.log_message(f"  ❌ FFmpeg 执行失败 (return code: {e.returncode})")
            return False
        except subprocess.TimeoutExpired:
            self.log_message("  ❌ FFmpeg 检测超时 (10秒)")
            return False
        except Exception as e:
            self.log_message(f"  ❌ FFmpeg 检测异常: {e}")
            return False

    def _merge_with_ffmpeg_direct(self, ts_files, output_file, folder):
        """直接使用 FFmpeg 合并 TS 片段"""
        import time
        merge_start = time.time()
        self.log_message("🔧 开始 FFmpeg 合并流程...")

        temp_file = None
        process = None

        try:
            # 创建临时文件列表
            self.log_message("📝 创建文件列表...")
            temp_file = os.path.join(folder, "file_list.txt")
            self.log_message(f"  📄 临时文件: {temp_file}")

            with open(temp_file, "w", encoding="utf-8") as f:
                for i, ts_file in enumerate(ts_files):
                    # 使用绝对路径确保正确性
                    abs_path = os.path.join(folder, ts_file)
                    f.write(f"file '{abs_path}'\n")
                    # 每50个文件记录一次进度
                    if (i + 1) % 50 == 0:
                        self.log_message(f"  📝 已添加 {i + 1}/{len(ts_files)} 个文件到列表")

            self.log_message(f"✅ 文件列表创建完成，包含 {len(ts_files)} 个文件")

            # 构建 FFmpeg 命令
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", temp_file,
                "-c", "copy",
                "-y",  # 覆盖输出文件
                output_file
            ]

            cmd_str = " ".join(cmd)
            self.log_message(f"🎬 FFmpeg 命令: {cmd_str}")
            self.log_message("🎬 启动 FFmpeg 进程...")

            # 执行命令
            process_start = time.time()
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 将 stderr 重定向到 stdout
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=folder  # 设置工作目录
            )

            self.log_message(f"✅ FFmpeg 进程已启动，PID: {process.pid}")

            # 实时读取输出
            self.log_message("📡 监听 FFmpeg 输出...")
            output_count = 0
            last_progress_time = time.time()

            while True:
                current_time = time.time()
                output = process.stdout.readline()

                if output == '':
                    if process.poll() is not None:
                        self.log_message("📡 FFmpeg 输出流结束")
                        break
                    # 如果长时间没有输出，记录状态
                    if current_time - last_progress_time > 10:
                        self.log_message(f"  ⏳ FFmpeg 运行中... (已运行 {current_time - process_start:.1f}秒)")
                        last_progress_time = current_time
                    continue

                output_clean = output.strip()
                output_count += 1

                # 显示前几行输出和进度相关的行
                if output_count <= 3:
                    self.log_message(f"  📋 FFmpeg: {output_clean}")
                elif any(keyword in output_clean.lower() for keyword in ['duration', 'time=', 'speed=', 'frame=', 'fps', 'size=', 'bitrate']):
                    self.log_message(f"  📊 FFmpeg: {output_clean}")

            # 等待进程结束
            self.log_message("⏳ 等待 FFmpeg 进程结束...")
            process.wait()
            process_time = time.time() - process_start

            self.log_message(f"✅ FFmpeg 进程结束，返回码: {process.returncode}, 耗时: {process_time:.2f}秒")

            # 检查输出文件
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                self.log_message(f"📏 输出文件存在，大小: {file_size / (1024*1024):.2f} MB")
            else:
                self.log_message("❌ 输出文件不存在")

            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
                self.log_message("🧹 已清理临时文件")

            success = process.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0
            total_time = time.time() - merge_start

            if success:
                self.log_message(f"✅ FFmpeg 合并成功，总耗时: {total_time:.2f}秒")
                return True
            else:
                self.log_message(f"❌ FFmpeg 合并失败，总耗时: {total_time:.2f}秒")
                return False

        except Exception as e:
            total_time = time.time() - merge_start
            self.log_message(f"❌ FFmpeg 合并异常: {e}")
            self.log_message(f"⏱️ 异常发生时总耗时: {total_time:.2f}秒")

            # 清理资源
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    self.log_message("🧹 异常时已清理临时文件")
                except:
                    pass

            if process and process.poll() is None:
                try:
                    process.terminate()
                    self.log_message("🛑 已终止 FFmpeg 进程")
                except:
                    pass

            return False

    def _merge_with_copy_direct(self, ts_files, output_file, folder):
        """直接使用复制方式合并 TS 片段（优化版本）"""
        import time
        merge_start = time.time()
        self.log_message("🔄 开始复制方式合并...")

        try:
            total_files = len(ts_files)
            self.log_message(f"📊 总文件数: {total_files}")

            # 计算预估总大小
            estimated_total = 0
            for ts_file in ts_files:
                file_path = os.path.join(folder, ts_file)
                try:
                    estimated_total += os.path.getsize(file_path)
                except:
                    pass

            self.log_message(f"📏 预估总大小: {estimated_total / (1024*1024):.2f} MB")

            total_size = 0
            processed_chunks = 0
            last_log_time = time.time()

            self.log_message(f"📂 打开输出文件: {output_file}")
            with open(output_file, "wb") as outfile:
                self.log_message("✅ 输出文件已打开，开始写入...")

                for i, ts_file in enumerate(ts_files):
                    file_start = time.time()
                    file_path = os.path.join(folder, ts_file)

                    try:
                        # 检查文件是否存在
                        if not os.path.exists(file_path):
                            self.log_message(f"⚠️ 文件不存在，跳过: {file_path}")
                            continue

                        file_size = os.path.getsize(file_path)
                        self.log_message(f"  📄 处理文件 {i+1}/{total_files}: {ts_file} ({file_size} bytes)")

                        bytes_written = 0
                        with open(file_path, "rb") as infile:
                            # 分块读取，避免内存溢出
                            while True:
                                chunk = infile.read(8192)  # 8KB 块
                                if not chunk:
                                    break
                                outfile.write(chunk)
                                bytes_written += len(chunk)
                                processed_chunks += 1

                                # 定期刷新输出缓冲区
                                if processed_chunks % 100 == 0:
                                    outfile.flush()

                        total_size += file_size
                        file_time = time.time() - file_start

                        # 记录文件处理完成
                        if file_time > 0:
                            speed = file_size / file_time / 1024  # KB/s
                            self.log_message(f"  ✅ 文件完成: {ts_file} ({file_time:.2f}秒, {speed:.1f} KB/s)")
                        else:
                            self.log_message(f"  ✅ 文件完成: {ts_file}")

                        # 每处理完一定数量的文件或定期报告进度
                        current_time = time.time()
                        if (i + 1) % 10 == 0 or i + 1 == total_files or current_time - last_log_time > 5:
                            progress = (i + 1) / total_files * 100
                            elapsed = current_time - merge_start
                            if elapsed > 0:
                                avg_speed = total_size / elapsed / (1024*1024)  # MB/s
                                self.log_message(f"  📈 进度: {i + 1}/{total_files} 文件 ({progress:.1f}%) - 已写入: {total_size / (1024*1024):.2f} MB - 平均速度: {avg_speed:.2f} MB/s")
                            else:
                                self.log_message(f"  📈 进度: {i + 1}/{total_files} 文件 ({progress:.1f}%) - 已写入: {total_size / (1024*1024):.2f} MB")
                            last_log_time = current_time

                    except Exception as e:
                        self.log_message(f"⚠️ 处理文件 {ts_file} 时出错: {e}")
                        continue

            # 检查结果
            if os.path.exists(output_file):
                final_size = os.path.getsize(output_file)
                total_time = time.time() - merge_start

                if final_size > 0:
                    avg_speed = final_size / total_time / (1024*1024) if total_time > 0 else 0
                    self.log_message(f"✅ 复制合并完成!")
                    self.log_message(f"  📏 文件大小: {final_size / (1024*1024):.2f} MB")
                    self.log_message(f"  ⏱️ 总耗时: {total_time:.2f} 秒")
                    self.log_message(f"  📊 平均速度: {avg_speed:.2f} MB/s")
                    return True
                else:
                    self.log_message("❌ 输出文件为空")
                    return False
            else:
                self.log_message("❌ 输出文件不存在")
                return False

        except Exception as e:
            total_time = time.time() - merge_start
            self.log_message(f"❌ 复制合并异常: {e}")
            self.log_message(f"⏱️ 异常发生时已耗时: {total_time:.2f}秒")
            return False
            
    def merge_segments(self):
        """合并 TS 片段功能"""
        folder = filedialog.askdirectory(title="选择包含 TS 片段的目录")
        if not folder:
            return
            
        # 检查目录中是否有 TS 片段
        ts_files = [f for f in os.listdir(folder) if f.endswith('.ts') and f.startswith('segment_')]
        if not ts_files:
            messagebox.showerror("错误", "在选择的目录中未找到 TS 片段文件")
            return
            
        # 询问输出文件名
        output_file = filedialog.asksaveasfilename(
            title="保存合并后的视频文件",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if not output_file:
            return
            
        # 执行合并操作
        self.status_var.set("正在合并 TS 片段...")
        self.log_message(f"🔄 开始合并 {len(ts_files)} 个 TS 片段...")
        
        # 在新线程中执行合并操作
        merge_thread = threading.Thread(
            target=self._merge_segments_thread,
            args=(folder, output_file)
        )
        merge_thread.daemon = True
        merge_thread.start()
        
    def _merge_segments_thread(self, folder, output_file):
        """合并 TS 片段的线程函数"""
        try:
            # 构建命令行参数
            cmd = [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "merge_ts.py"),
                "-d", folder,
                "-o", output_file
            ]
            
            # 执行合并脚本
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log_message(output.strip())
                    
            # 等待进程结束
            _, stderr = process.communicate()
            
            if process.returncode == 0:
                self.log_message("✓ TS 片段合并完成!")
                self.status_var.set("合并完成")
                messagebox.showinfo("成功", f"视频已成功合并到:\n{output_file}")
            else:
                error_msg = stderr.strip() if stderr else "合并失败"
                self.log_message(f"✗ 合并失败: {error_msg}")
                self.status_var.set("合并失败")
                messagebox.showerror("错误", f"合并过程中出现错误:\n{error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            self.log_message(f"✗ 合并过程中出现异常: {error_msg}")
            self.status_var.set("合并异常")
            messagebox.showerror("错误", f"合并过程中出现异常:\n{error_msg}")
            
    def format_time(self, seconds):
        """格式化时间显示"""
        if seconds <= 0:
            return "--:--:--"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
            
    def open_settings_dialog(self):
        """打开设置对话框"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("设置")
        settings_window.geometry("600x500")
        settings_window.resizable(False, False)
        
        # 使窗口居中
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 创建主容器
        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Notebook用于分页
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建下载设置页面
        download_frame = ttk.Frame(notebook, padding="15")
        notebook.add(download_frame, text="下载设置")
        
        # 速度限制设置
        speed_limit_frame = ttk.LabelFrame(download_frame, text="速度限制", padding="10")
        speed_limit_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(speed_limit_frame, text="下载速度限制 (KB/s, 0为不限制):").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        
        speed_limit_var = tk.StringVar(value="0")
        speed_limit_entry = ttk.Entry(speed_limit_frame, textvariable=speed_limit_var, width=15)
        speed_limit_entry.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(speed_limit_frame, text="设置为 0 表示不限制下载速度").grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
        )
        
        # 线程数设置
        thread_frame = ttk.LabelFrame(download_frame, text="线程设置", padding="10")
        thread_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(thread_frame, text="默认线程数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        thread_var = tk.IntVar(value=8)
        thread_spinbox = ttk.Spinbox(thread_frame, from_=1, to=32, textvariable=thread_var, width=10)
        thread_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 重试次数设置
        ttk.Label(thread_frame, text="重试次数:").grid(row=1, column=0, sticky=tk.W, pady=5)
        retry_var = tk.IntVar(value=5)
        retry_spinbox = ttk.Spinbox(thread_frame, from_=0, to=20, textvariable=retry_var, width=10)
        retry_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 创建代理设置页面
        proxy_frame = ttk.Frame(notebook, padding="15")
        notebook.add(proxy_frame, text="🌐 代理设置")
        
        # 代理启用设置
        proxy_enable_frame = ttk.LabelFrame(proxy_frame, text="⚙️ 代理配置", padding="10")
        proxy_enable_frame.pack(fill=tk.X, pady=(0, 15))
        
        proxy_enable_var = tk.BooleanVar(value=False)
        proxy_enable_check = ttk.Checkbutton(
            proxy_enable_frame,
            text="🟢 启用代理",
            variable=proxy_enable_var
        )
        proxy_enable_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # HTTP代理设置
        ttk.Label(proxy_enable_frame, text="🌐 HTTP代理:").grid(row=1, column=0, sticky=tk.W, pady=5)
        http_proxy_var = tk.StringVar(value="")
        http_proxy_entry = ttk.Entry(proxy_enable_frame, textvariable=http_proxy_var, width=30)
        http_proxy_entry.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(proxy_enable_frame, text="📝 格式: http://proxy.example.com:8080").grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
        )
        
        # HTTPS代理设置
        ttk.Label(proxy_enable_frame, text="🔒 HTTPS代理:").grid(row=3, column=0, sticky=tk.W, pady=5)
        https_proxy_var = tk.StringVar(value="")
        https_proxy_entry = ttk.Entry(proxy_enable_frame, textvariable=https_proxy_var, width=30)
        https_proxy_entry.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(proxy_enable_frame, text="📝 格式: https://proxy.example.com:8080").grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
        )
        
        # 代理认证设置
        proxy_auth_frame = ttk.LabelFrame(proxy_frame, text="🔑 代理认证 (可选)", padding="10")
        proxy_auth_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(proxy_auth_frame, text="👤 用户名:").grid(row=0, column=0, sticky=tk.W, pady=5)
        proxy_username_var = tk.StringVar(value="")
        proxy_username_entry = ttk.Entry(proxy_auth_frame, textvariable=proxy_username_var, width=20)
        proxy_username_entry.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Label(proxy_auth_frame, text="🔐 密码:").grid(row=1, column=0, sticky=tk.W, pady=5)
        proxy_password_var = tk.StringVar(value="")
        proxy_password_entry = ttk.Entry(proxy_auth_frame, textvariable=proxy_password_var, width=20, show="*")
        proxy_password_entry.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 加载当前设置
        def load_current_settings():
            """加载当前设置"""
            try:
                # 从配置管理器加载设置
                config = self.config_manager.get_config()
                
                # 下载设置
                speed_limit_var.set(str(config.download.speed_limit))
                thread_var.set(config.download.default_thread_count)
                retry_var.set(config.download.default_retry_count)
                
                # 代理设置
                proxy_enable_var.set(config.proxy.enabled)
                http_proxy_var.set(config.proxy.http_proxy)
                https_proxy_var.set(config.proxy.https_proxy)
                proxy_username_var.set(config.proxy.username)
                proxy_password_var.set(config.proxy.password)
                
            except Exception as e:
                self.log_message(f"加载设置失败: {e}")
        
        # 保存设置
        def save_settings():
            """保存设置"""
            try:
                # 验证速度限制
                try:
                    speed_limit = int(speed_limit_var.get())
                    if speed_limit < 0:
                        messagebox.showerror("错误", "速度限制不能为负数")
                        return
                except ValueError:
                    messagebox.showerror("错误", "速度限制必须是数字")
                    return
                
                # 验证代理设置
                if proxy_enable_var.get():
                    if not http_proxy_var.get() and not https_proxy_var.get():
                        messagebox.showerror("错误", "启用代理时必须至少设置HTTP或HTTPS代理")
                        return
                
                # 更新下载配置
                self.config_manager.update_download_config(
                    speed_limit=speed_limit,
                    default_thread_count=thread_var.get(),
                    default_retry_count=retry_var.get()
                )
                
                # 更新代理配置
                self.config_manager.update_proxy_config(
                    enabled=proxy_enable_var.get(),
                    http_proxy=http_proxy_var.get(),
                    https_proxy=https_proxy_var.get(),
                    username=proxy_username_var.get(),
                    password=proxy_password_var.get()
                )
                
                self.log_message(f"设置已保存: 速度限制={speed_limit}KB/s, 线程数={thread_var.get()}, 重试次数={retry_var.get()}")
                if proxy_enable_var.get():
                    self.log_message(f"代理已启用: HTTP={http_proxy_var.get()}, HTTPS={https_proxy_var.get()}")
                else:
                    self.log_message("代理未启用")
                
                messagebox.showinfo("成功", "设置已保存!")
                settings_window.destroy()
                
            except Exception as e:
                messagebox.showerror("错误", f"保存设置失败: {e}")
        
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        # 使用更具视觉吸引力的按钮样式
        ttk.Button(button_frame, text="💾 保存设置", command=save_settings, style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ 取消", command=settings_window.destroy).pack(side=tk.LEFT)
        
        # 加载当前设置
        load_current_settings()

    def _parse_download_error(self, error_msg):
        """解析下载错误信息，提供更详细的HTTP状态码和错误原因"""
        import re
        
        # 提取HTTP状态码
        status_code_match = re.search(r'HTTP.*?(\d{3})', error_msg, re.IGNORECASE)
        if status_code_match:
            status_code = status_code_match.group(1)
            status_messages = {
                '400': 'Bad Request - 请求格式错误',
                '401': 'Unauthorized - 未授权访问',
                '403': 'Forbidden - 访问被禁止',
                '404': 'Not Found - 资源未找到',
                '407': 'Proxy Authentication Required - 代理需要认证',
                '429': 'Too Many Requests - 请求过于频繁',
                '500': 'Internal Server Error - 服务器内部错误',
                '502': 'Bad Gateway - 网关错误',
                '503': 'Service Unavailable - 服务不可用',
                '504': 'Gateway Timeout - 网关超时'
            }
            if status_code in status_messages:
                return f"HTTP {status_code} - {status_messages[status_code]}"
            else:
                return f"HTTP {status_code} - 未知错误"
        
        # 提取连接超时错误
        if 'timeout' in error_msg.lower():
            return "连接超时 - 请检查网络连接或服务器响应时间"
        
        # 提取连接错误
        if 'connection' in error_msg.lower() and 'error' in error_msg.lower():
            return "连接错误 - 请检查网络连接或防火墙设置"
        
        # 提取DNS解析错误
        if 'dns' in error_msg.lower() or 'could not resolve' in error_msg.lower():
            return "DNS解析错误 - 请检查域名或DNS设置"
        
        # 提取SSL错误
        if 'ssl' in error_msg.lower() or 'certificate' in error_msg.lower():
            return "SSL证书错误 - 请检查证书配置"
        
        # 如果没有识别到特定错误，返回原始错误信息
        return error_msg

    def show_performance_stats(self):
        """显示性能统计信息"""
        try:
            # 获取当前性能统计
            stats = get_batch_downloader_performance_stats()
            
            # 创建性能统计窗口
            perf_window = tk.Toplevel(self.root)
            perf_window.title("下载性能统计")
            perf_window.geometry("600x500")
            perf_window.transient(self.root)
            
            # 创建主框架
            main_frame = ttk.Frame(perf_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            perf_window.columnconfigure(0, weight=1)
            perf_window.rowconfigure(0, weight=1)
            main_frame.columnconfigure(0, weight=1)
            
            # 标题
            title_label = tk.Label(
                main_frame,
                text="📊 下载性能统计",
                font=("Helvetica", 16, "bold"),
                fg="#2c3e50"
            )
            title_label.grid(row=0, column=0, pady=(0, 20))
            
            # 性能统计文本框
            stats_text = tk.Text(main_frame, height=20, width=70, font=("Consolas", 10))
            stats_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
            main_frame.rowconfigure(1, weight=1)
            
            # 滚动条
            scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=stats_text.yview)
            scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
            stats_text.configure(yscrollcommand=scrollbar.set)
            
            # 填充统计信息
            if stats:
                stats_text.insert(tk.END, "=== 全局性能统计 ===\n\n")
                
                # 基本统计
                stats_text.insert(tk.END, f"总运行时间: {stats.get('total_runtime', 0):.1f} 秒\n")
                stats_text.insert(tk.END, f"总下载任务: {stats.get('total_downloads', 0)}\n")
                stats_text.insert(tk.END, f"成功任务: {stats.get('successful_downloads', 0)}\n")
                stats_text.insert(tk.END, f"失败任务: {stats.get('failed_downloads', 0)}\n")
                stats_text.insert(tk.END, f"成功率: {stats.get('success_rate', 0):.1%}\n\n")
                
                # 下载统计
                stats_text.insert(tk.END, "=== 下载统计 ===\n\n")
                stats_text.insert(tk.END, f"总下载量: {self.format_size(stats.get('total_downloaded_bytes', 0))}\n")
                stats_text.insert(tk.END, f"平均下载速度: {stats.get('average_download_speed', 0):.2f} MB/s\n")
                stats_text.insert(tk.END, f"峰值下载速度: {stats.get('peak_download_speed', 0):.2f} MB/s\n\n")
                
                # 调度器统计
                if 'scheduler_stats' in stats:
                    sched_stats = stats['scheduler_stats']
                    stats_text.insert(tk.END, "=== 调度器统计 ===\n\n")
                    stats_text.insert(tk.END, f"活跃调度器: {sched_stats.get('active_schedulers', 0)}\n")
                    stats_text.insert(tk.END, f"总任务数: {sched_stats.get('total_tasks', 0)}\n")
                    stats_text.insert(tk.END, f"成功任务: {sched_stats.get('successful_tasks', 0)}\n")
                    stats_text.insert(tk.END, f"失败任务: {sched_stats.get('failed_tasks', 0)}\n")
                    stats_text.insert(tk.END, f"平均任务成功率: {sched_stats.get('average_success_rate', 0):.1%}\n")
                    stats_text.insert(tk.END, f"峰值并发下载: {sched_stats.get('peak_concurrent_downloads', 0)}\n\n")
                
                # 性能趋势
                stats_text.insert(tk.END, "=== 性能趋势 ===\n\n")
                if stats.get('average_download_speed', 0) > 5:
                    stats_text.insert(tk.END, "下载速度: 优秀 ✅\n")
                elif stats.get('average_download_speed', 0) > 2:
                    stats.text.insert(tk.END, "下载速度: 良好 ⚠️\n")
                else:
                    stats_text.insert(tk.END, "下载速度: 较慢 ❌\n")
                
                if stats.get('success_rate', 0) > 0.9:
                    stats_text.insert(tk.END, "成功率: 优秀 ✅\n")
                elif stats.get('success_rate', 0) > 0.7:
                    stats_text.insert(tk.END, "成功率: 良好 ⚠️\n")
                else:
                    stats_text.insert(tk.END, "成功率: 较低 ❌\n")
                    
            else:
                stats_text.insert(tk.END, "暂无性能统计数据\n")
                stats_text.insert(tk.END, "请执行一些下载任务后再次查看统计信息。\n")
            
            # 按钮区域
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
            
            # 刷新按钮
            refresh_btn = ttk.Button(
                button_frame,
                text="🔄 刷新",
                command=lambda: self.refresh_performance_stats(stats_text)
            )
            refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            # 导出报告按钮
            export_btn = ttk.Button(
                button_frame,
                text="📄 导出报告",
                command=lambda: self.export_performance_report(stats_text)
            )
            export_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            # 关闭按钮
            close_btn = ttk.Button(
                button_frame,
                text="关闭",
                command=perf_window.destroy
            )
            close_btn.pack(side=tk.LEFT)
            
            # 使文本框只读
            stats_text.configure(state=tk.DISABLED)
            
            self.log_message("已打开性能统计窗口")
            
        except Exception as e:
            messagebox.showerror("错误", f"显示性能统计失败: {e}")
            self.log_message(f"显示性能统计失败: {e}")

    def refresh_performance_stats(self, text_widget):
        """刷新性能统计信息"""
        try:
            # 获取最新统计
            stats = get_batch_downloader_performance_stats()
            
            # 清空并重新填充文本框
            text_widget.configure(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            
            if stats:
                text_widget.insert(tk.END, "=== 全局性能统计 ===\n\n")
                text_widget.insert(tk.END, f"总运行时间: {stats.get('total_runtime', 0):.1f} 秒\n")
                text_widget.insert(tk.END, f"总下载任务: {stats.get('total_downloads', 0)}\n")
                text_widget.insert(tk.END, f"成功任务: {stats.get('successful_downloads', 0)}\n")
                text_widget.insert(tk.END, f"失败任务: {stats.get('failed_downloads', 0)}\n")
                text_widget.insert(tk.END, f"成功率: {stats.get('success_rate', 0):.1%}\n\n")
                
                text_widget.insert(tk.END, "=== 下载统计 ===\n\n")
                text_widget.insert(tk.END, f"总下载量: {self.format_size(stats.get('total_downloaded_bytes', 0))}\n")
                text_widget.insert(tk.END, f"平均下载速度: {stats.get('average_download_speed', 0):.2f} MB/s\n")
                text_widget.insert(tk.END, f"峰值下载速度: {stats.get('peak_download_speed', 0):.2f} MB/s\n\n")
            else:
                text_widget.insert(tk.END, "暂无性能统计数据\n")
            
            text_widget.configure(state=tk.DISABLED)
            self.log_message("性能统计已刷新")
            
        except Exception as e:
            messagebox.showerror("错误", f"刷新性能统计失败: {e}")

    def export_performance_report(self, text_widget):
        """导出性能报告"""
        try:
            # 选择保存位置
            file_path = filedialog.asksaveasfilename(
                title="导出性能报告",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            
            if file_path:
                # 获取文本框内容
                content = text_widget.get(1.0, tk.END)
                
                # 添加时间戳
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                full_content = f"M3U8下载器性能报告\n生成时间: {timestamp}\n\n{content}"
                
                # 保存到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(full_content)
                
                messagebox.showinfo("成功", f"性能报告已导出到:\n{file_path}")
                self.log_message(f"性能报告已导出到: {file_path}")
                
        except Exception as e:
            messagebox.showerror("错误", f"导出性能报告失败: {e}")


def main():
    """主函数"""
    try:
        import tkinter as tk
        root = tk.Tk()
        app = ModernM3U8DownloaderApp(root)
        root.mainloop()
    except Exception as e:
        error_msg = f"启动 GUI 时出现错误: {e}"
        import traceback
        traceback.print_exc()
        
        # 尝试显示错误对话框
        try:
            import tkinter as tk_error
            from tkinter import messagebox
            error_window = tk_error.Tk()
            error_window.withdraw()
            messagebox.showerror("启动错误", f"{error_msg}\n\n详细错误信息:\n{traceback.format_exc()}")
            error_window.destroy()
        except:
            pass


if __name__ == "__main__":
    main()