#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TS片段合并工具
用于将下载的TS片段合并为完整的视频文件
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def merge_with_ffmpeg(ts_files, output_file):
    """使用FFmpeg合并TS片段"""
    try:
        # 创建临时文件列表
        temp_file = "file_list.txt"
        with open(temp_file, "w", encoding="utf-8") as f:
            for ts_file in ts_files:
                # 使用正斜杠路径，避免Windows路径问题
                f.write(f"file '{ts_file}'\n")
        
        # 构建FFmpeg命令
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", temp_file,
            "-c", "copy",
            output_file
        ]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 清理临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        if result.returncode == 0:
            print(f"成功合并为: {output_file}")
            return True
        else:
            print(f"合并失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"合并过程中出现错误: {e}")
        # 清理临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False

def merge_with_copy(ts_files, output_file):
    """使用简单复制方式合并TS片段"""
    try:
        with open(output_file, "wb") as outfile:
            for ts_file in ts_files:
                with open(ts_file, "rb") as infile:
                    outfile.write(infile.read())
        print(f"成功合并为: {output_file}")
        return True
    except Exception as e:
        print(f"合并过程中出现错误: {e}")
        return False

def find_ts_files(directory):
    """在指定目录中查找TS片段文件"""
    ts_files = []
    for file in os.listdir(directory):
        if file.endswith(".ts") and file.startswith("segment_"):
            ts_files.append(os.path.join(directory, file))
    
    # 按数字顺序排序
    ts_files.sort(key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0]))
    return ts_files

def main():
    parser = argparse.ArgumentParser(description="TS片段合并工具")
    parser.add_argument("-d", "--directory", help="TS片段所在目录", default=".")
    parser.add_argument("-o", "--output", help="输出文件名", default="output.mp4")
    parser.add_argument("-m", "--method", choices=["ffmpeg", "copy"], 
                       help="合并方法 (ffmpeg 或 copy)", default="ffmpeg")
    parser.add_argument("-y", "--yes", action="store_true",
                       help="自动确认，跳过交互式提示")
    
    args = parser.parse_args()
    
    # 检查FFmpeg是否可用
    ffmpeg_available = False
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        ffmpeg_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # 如果指定了ffmpeg方法但FFmpeg不可用，则使用copy方法
    if args.method == "ffmpeg" and not ffmpeg_available:
        print("警告: FFmpeg不可用，使用复制方法合并")
        args.method = "copy"
    
    # 查找TS文件
    ts_files = find_ts_files(args.directory)
    
    if not ts_files:
        print("在指定目录中未找到TS片段文件")
        return
    
    print(f"找到 {len(ts_files)} 个TS片段文件")
    for i, file in enumerate(ts_files[:5]):  # 只显示前5个
        print(f"  {i+1}. {os.path.basename(file)}")
    if len(ts_files) > 5:
        print(f"  ... 还有 {len(ts_files) - 5} 个文件")
    
    # 确认合并
    if not args.yes:
        confirm = input(f"\n是否合并为 {args.output}? (y/N): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return
    
    # 执行合并
    if args.method == "ffmpeg" and ffmpeg_available:
        success = merge_with_ffmpeg(ts_files, args.output)
    else:
        success = merge_with_copy(ts_files, args.output)
    
    if success:
        print("合并完成!")
    else:
        print("合并失败!")

if __name__ == "__main__":
    main()