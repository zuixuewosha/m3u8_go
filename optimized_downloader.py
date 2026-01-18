"""
优化的下载模块 - 改进并发下载机制
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import time
import os
from typing import Callable, Optional


class DownloadSession:
    """优化的HTTP会话管理，支持连接池和重试机制"""
    
    def __init__(self, pool_connections=10, pool_maxsize=10, max_retries=3):
        """
        初始化下载会话
        
        Args:
            pool_connections: 连接池大小
            pool_maxsize: 最大连接数
            max_retries: 最大重试次数
        """
        self.session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # 配置适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置默认超时
        self.timeout = 30
        
    def get(self, url, **kwargs):
        """发送GET请求"""
        kwargs.setdefault('timeout', self.timeout)
        return self.session.get(url, **kwargs)
    
    def head(self, url, **kwargs):
        """发送HEAD请求"""
        kwargs.setdefault('timeout', self.timeout)
        return self.session.head(url, **kwargs)
    
    def close(self):
        """关闭会话"""
        self.session.close()


class OptimizedDownloader:
    """优化的下载器，支持速度限制和智能并发控制"""
    
    def __init__(self, max_speed: Optional[int] = None, chunk_size: int = 65536):
        """
        初始化下载器
        
        Args:
            max_speed: 最大下载速度（字节/秒），None表示无限制
            chunk_size: 下载块大小（字节）
        """
        self.max_speed = max_speed
        self.chunk_size = chunk_size
        self.session = DownloadSession()
        self._lock = threading.Lock()
        self._last_download_time = time.time()
        self._downloaded_bytes = 0
        
    def download_segment(
        self,
        url: str,
        filepath: str,
        progress_callback: Callable[[int, int], None],
        semaphore: threading.Semaphore,
        max_retries: int = 3,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        下载单个片段
        
        Args:
            url: 下载URL
            filepath: 保存路径
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)
            semaphore: 并发控制信号量（由调用者管理）
            max_retries: 最大重试次数
            stop_check: 停止检查函数
            
        Returns:
            bool: 是否下载成功
        """
        downloaded_bytes = 0
        temp_filepath = filepath + ".tmp"
        
        try:
            # 检查文件是否已存在
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                downloaded_bytes = file_size
                progress_callback(downloaded_bytes, file_size)
                return True
                
            # 检查是否存在部分下载的文件
            if os.path.exists(temp_filepath):
                downloaded_bytes = os.path.getsize(temp_filepath)
                
            # 尝试下载
            for attempt in range(max_retries + 1):
                try:
                    # 如果已有部分下载内容，使用 Range 请求继续下载
                    headers = {}
                    if downloaded_bytes > 0:
                        headers['Range'] = f'bytes={downloaded_bytes}-'
                    
                    response = self.session.get(
                        url,
                        stream=True,
                        headers=headers
                    )
                    
                    # 处理 Range 请求的响应
                    if downloaded_bytes > 0 and response.status_code == 206:
                        pass
                    elif downloaded_bytes == 0 or response.status_code == 200:
                        downloaded_bytes = 0
                        response.raise_for_status()
                    else:
                        downloaded_bytes = 0
                        response = self.session.get(url, stream=True)
                        response.raise_for_status()
                    
                    # 获取文件大小
                    content_length = response.headers.get('content-length')
                    if content_length:
                        segment_size = int(content_length) + downloaded_bytes
                    else:
                        segment_size = 0
                    
                    # 下载文件到临时文件
                    mode = 'ab' if downloaded_bytes > 0 else 'wb'
                    with open(temp_filepath, mode) as f:
                        for chunk in response.iter_content(chunk_size=self.chunk_size):
                            # 检查是否需要停止
                            if stop_check and stop_check():
                                return False
                                
                            if chunk:
                                # 速度限制
                                if self.max_speed:
                                    self._limit_speed(len(chunk))
                                
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                                progress_callback(downloaded_bytes, segment_size)
                                
                    # 下载成功
                    if segment_size == 0:
                        segment_size = os.path.getsize(temp_filepath)
                    
                    # 将临时文件重命名为正式文件
                    if os.path.exists(temp_filepath):
                        os.rename(temp_filepath, filepath)
                    
                    return True
                    
                except Exception as e:
                    if attempt < max_retries:
                        wait_time = 1 * (attempt + 1)  # 指数退避
                        time.sleep(wait_time)
                    else:
                        # 记录详细的错误信息
                        print(f"下载失败详情 - URL: {url}")
                        print(f"  文件路径: {filepath}")
                        print(f"  错误类型: {type(e).__name__}")
                        print(f"  错误信息: {str(e)}")
                        print(f"  已下载字节数: {downloaded_bytes}")
                        print(f"  临时文件是否存在: {os.path.exists(temp_filepath)}")
                        if os.path.exists(temp_filepath):
                            print(f"  临时文件大小: {os.path.getsize(temp_filepath)} 字节")
                        raise
                        
        except Exception as e:
            # 记录详细的错误信息
            print(f"下载异常详情 - URL: {url}")
            print(f"  文件路径: {filepath}")
            print(f"  错误类型: {type(e).__name__}")
            print(f"  错误信息: {str(e)}")
            print(f"  已下载字节数: {downloaded_bytes}")
            print(f"  临时文件是否存在: {os.path.exists(temp_filepath)}")
            if os.path.exists(temp_filepath):
                print(f"  临时文件大小: {os.path.getsize(temp_filepath)} 字节")
            # 保留临时文件以便断点续传
            if os.path.exists(temp_filepath):
                pass
            return False
    
    def _limit_speed(self, chunk_size: int):
        """限制下载速度"""
        if not self.max_speed:
            return
            
        with self._lock:
            current_time = time.time()
            self._downloaded_bytes += chunk_size
            
            # 计算应该等待的时间
            elapsed = current_time - self._last_download_time
            expected_time = self._downloaded_bytes / self.max_speed
            
            if elapsed < expected_time:
                sleep_time = expected_time - elapsed
                time.sleep(sleep_time)
            
            # 重置计数器（每秒重置一次）
            if current_time - self._last_download_time >= 1.0:
                self._downloaded_bytes = 0
                self._last_download_time = current_time
    
    def close(self):
        """关闭下载器"""
        self.session.close()


class DownloadPool:
    """下载池，管理多个下载器实例"""
    
    def __init__(self, pool_size: int = 5, max_speed: Optional[int] = None):
        """
        初始化下载池
        
        Args:
            pool_size: 池大小
            max_speed: 最大下载速度（字节/秒）
        """
        self.pool_size = pool_size
        self.max_speed = max_speed
        self.downloaders = []
        self._lock = threading.Lock()
        self._index = 0
        
        # 创建下载器实例
        for _ in range(pool_size):
            downloader = OptimizedDownloader(max_speed=max_speed)
            self.downloaders.append(downloader)
    
    def get_downloader(self) -> OptimizedDownloader:
        """获取一个下载器实例（轮询方式）"""
        with self._lock:
            downloader = self.downloaders[self._index]
            self._index = (self._index + 1) % self.pool_size
            return downloader
    
    def close_all(self):
        """关闭所有下载器"""
        for downloader in self.downloaders:
            downloader.close()
        self.downloaders.clear()