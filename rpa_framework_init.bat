@echo off
chcp 936 >nul
setlocal

REM 步骤 1：检查并激活虚拟环境
echo [步骤 1/5] 检查并激活虚拟环境...
if exist ".venv\Scripts\activate.bat" (
    set "VENV_PATH=.venv"
    echo ? 检测到 .venv 虚拟环境
) else if exist "venv\Scripts\activate.bat" (
    set "VENV_PATH=venv"
    echo ? 检测到 venv 虚拟环境
) else (
    echo ? 未检测到虚拟环境，请先创建虚拟环境（python -m venv ".venv" 或 "venv"）
    pause
    exit /b 1
)
call "%VENV_PATH%\Scripts\activate.bat"
echo 虚拟环境已激活

REM 步骤 2：RPA Framework 初始化
echo.
echo [步骤 2/5] RPA Framework 初始化
echo ========================================
echo         RPA Framework 初始化
echo ========================================
echo.

REM 步骤 3：解压RPA Framework 工具包
echo [步骤 3/5] 解压RPA Framework 工具包...
powershell -Command "Expand-Archive -Path 'rpa_framework.zip' -DestinationPath '.' -Force"
echo ? 解压完成

REM 步骤 4：安装相关依赖
echo.
echo [步骤 4/5] 安装相关依赖...
pip install -r ".\requirements.txt"
echo ? 依赖安装完成

REM 步骤 5：初始化完成及使用说明
echo.
echo [步骤 5/5] 初始化完成，输出使用说明
echo ========================================
echo         rpa工程初始化完成！
echo ========================================
echo.
echo 使用说明：
echo   1. 请在 "src\robots" 目录开发新的 robots
echo   2. 资源文件请在 "src\resources" 目录存放
echo   3. 配置文件请见 "config" 目录
echo   4. 使用方法请参见 "docs\使用说明"
echo   5. 运行 "build.bat" 打包为 exe 文件
echo.
echo 现在可以运行 "main.py" 启动RPA工具了，祝开发顺利!
echo.
pause