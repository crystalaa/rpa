@echo off
chcp 65001 >nul
echo ========================================
echo            RPA自动化工具构建脚本
echo ========================================
echo.
echo 注意：此脚本适用于使用 rpa-framework 包的项目
echo 请确保已安装 rpa-framework: pip install rpa-framework
echo.

echo [步骤 1/8] 清理旧的构建文件...
if exist ".\build\" (
    echo 正在删除 build 目录...
    rmdir /s /q ".\build\"
    echo ✓ build 目录已清理
) else (
    echo ✓ build 目录不存在，跳过清理
)

if exist ".\dist\RPA_GUI\" (
    echo 正在删除 dist\RPA_GUI 目录...
    rmdir /s /q ".\dist\RPA_GUI\"
    echo ✓ dist\RPA_GUI 目录已清理
) else (
    echo ✓ dist\RPA_GUI 目录不存在，跳过清理
)
echo.

echo [步骤 2/8] 生成GUI版本spec文件...
echo 正在调用 make_spec.bat 生成GUI版本spec文件...
call ".\make_spec.bat"
if %errorlevel% equ 0 (
    echo ✓ GUI版本spec文件生成成功
) else (
    echo ✗ GUI版本spec文件生成失败，错误代码: %errorlevel%
    pause
    exit /b %errorlevel%
)
echo.

echo [步骤 3/8] 生成CLI版本spec文件...
echo 正在调用 make_spec_cli.bat 生成CLI版本spec文件...
call ".\make_spec_cli.bat"
if %errorlevel% equ 0 (
    echo ✓ CLI版本spec文件生成成功
) else (
    echo ✗ CLI版本spec文件生成失败，错误代码: %errorlevel%
    pause
    exit /b %errorlevel%
)
echo.

echo [步骤 4/8] 构建GUI版本...
echo 正在使用 PyInstaller 构建GUI版本...
pyinstaller --clean ".\RPA_GUI.spec"
if %errorlevel% equ 0 (
    echo ✓ GUI版本构建成功
) else (
    echo ✗ GUI版本构建失败，错误代码: %errorlevel%
    pause
    exit /b %errorlevel%
)
echo.

echo [步骤 5/8] 清理GUI构建的临时文件...
if exist ".\build\" (
    echo 正在删除GUI构建的临时文件...
    rmdir /s /q ".\build\"
    echo ✓ GUI构建临时文件已清理
) else (
    echo ✓ GUI构建临时文件不存在，跳过清理
)
echo.

echo [步骤 6/8] 清理CLI版本的旧文件...
if exist ".\dist\RPA_CLI\" (
    echo 正在删除旧的CLI版本文件...
    rmdir /s /q ".\dist\RPA_CLI\"
    echo ✓ 旧CLI版本文件已清理
) else (
    echo ✓ 旧CLI版本文件不存在，跳过清理
)
echo.

echo [步骤 7/8] 构建CLI版本...
echo 正在使用 PyInstaller 构建CLI版本...
pyinstaller --clean ".\RPA_CLI.spec"
if %errorlevel% equ 0 (
    echo ✓ CLI版本构建成功
) else (
    echo ✗ CLI版本构建失败，错误代码: %errorlevel%
    pause
    exit /b %errorlevel%
)
echo.

echo [步骤 8/8] 复制配置文件...
REM 复制 CLI 版本 docs/config/data
if exist ".\dist\RPA_CLI\_internal\docs\*" (
    xcopy ".\dist\RPA_CLI\_internal\docs\*" ".\dist\RPA_CLI\docs\" /E /I /Y
    echo ✓ CLI版本docs目录复制完成
) else (
    echo ✗ CLI版本docs目录不存在
)
if exist ".\dist\RPA_CLI\_internal\config\*" (
    xcopy ".\dist\RPA_CLI\_internal\config\*" ".\dist\RPA_CLI\config\" /E /I /Y
    echo ✓ CLI版本config目录复制完成
) else (
    echo ✗ CLI版本config目录不存在
)
if exist ".\dist\RPA_CLI\_internal\data\*" (
    xcopy ".\dist\RPA_CLI\_internal\data\*" ".\dist\RPA_CLI\data\" /E /I /Y
    echo ✓ CLI版本data目录复制完成
) else (
    echo ✗ CLI版本data目录不存在
)
REM 复制 GUI 版本 docs/config/data
if exist ".\dist\RPA_GUI\_internal\docs\*" (
    xcopy ".\dist\RPA_GUI\_internal\docs\*" ".\dist\RPA_GUI\docs\" /E /I /Y
    echo ✓ GUI版本docs目录复制完成
) else (
    echo ✗ GUI版本docs目录不存在
)
if exist ".\dist\RPA_GUI\_internal\config\*" (
    xcopy ".\dist\RPA_GUI\_internal\config\*" ".\dist\RPA_GUI\config\" /E /I /Y
    echo ✓ GUI版本config目录复制完成
) else (
    echo ✗ GUI版本config目录不存在
)
if exist ".\dist\RPA_GUI\_internal\data" (
    xcopy ".\dist\RPA_GUI\_internal\data" ".\dist\RPA_GUI\data" /E /I /Y
    echo ✓ GUI版本data目录复制完成
) else (
    echo ✗ GUI版本data目录不存在
)

if exist ".\dist\RPA_CLI\RPA_CLI.exe" (
    copy ".\dist\RPA_CLI\RPA_CLI.exe" ".\dist\RPA_GUI\RPA_CLI.exe"  /Y
    echo ✓ CLI版本exe复制完成
) else (
    echo ✗ CLI版本exe不存在
)
echo [构建完成] 构建完成！
echo ========================================
echo 构建结果：
echo   GUI版本: .\dist\RPA_GUI\
echo   CLI版本: .\dist\RPA_CLI\
echo ========================================
echo.
echo 说明
echo 1、UI资源文件从包内直接加载，无需复制
echo 2、机器人文件位于 _internal/src/robots/ 目录，支持动态加载
echo.
echo 构建过程已完成，按任意键退出...
pause >nul