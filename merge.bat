@echo off
REM TS片段合并工具启动脚本
REM 用于Windows系统快速启动合并工具
cd /d "%~dp0"

echo ================================
echo M3U8下载器 - TS片段合并工具
echo ================================

REM 检查python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python环境，请先安装Python
    pause
    exit /b 1
)

REM 检查合并工具脚本
if not exist merge_ts.py (
    echo 错误: 未找到合并工具脚本(merge_ts.py)
    pause
    exit /b 1
)

echo.
echo 请按照提示输入参数
echo.

REM 获取用户输入
set /p "download_dir=请输入TS片段所在目录(直接回车使用当前目录): "
if "%download_dir%"=="" set download_dir=.

set /p "output_file=请输入输出文件名(默认: output.mp4): "
if "%output_file%"=="" set output_file=output.mp4

echo.
echo 正在合并TS片段...
echo.

REM 执行合并命令
python merge_ts.py -d "%download_dir%" -o "%output_file%"

if %errorlevel% equ 0 (
    echo.
    echo 合并完成!
    echo 输出文件: %output_file%
) else (
    echo.
    echo 合并失败，请检查错误信息
)

echo.
pause