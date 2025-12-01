@echo off
chcp 936 >nul
title 全自动Town01数据收集器

echo ========================================
echo [全自动Town01数据收集器]
echo ========================================
echo.
echo 功能说明：
echo   * 自动遍历Town01的所有生成点组合
echo   * 智能选择距离适中的路线
echo   * 无需人工干预，全自动收集数据
echo   * 自动保存统计信息
echo.
echo ========================================
echo.

:menu
echo 请选择运行模式：
echo.
echo   [1] 智能模式（推荐）- 选择距离适中、分布均匀的路线
echo   [2] 快速测试 - 只收集少量路线用于测试
echo   [3] 穷举模式（警告：数量巨大！）- 遍历所有可能的组合
echo   [4] 自定义配置
echo   [Q] 退出
echo.

set /p choice="请输入选项 [1-4/Q]: "

if /i "%choice%"=="1" goto smart_mode
if /i "%choice%"=="2" goto quick_test
if /i "%choice%"=="3" goto exhaustive_mode
if /i "%choice%"=="4" goto custom_mode
if /i "%choice%"=="Q" goto end
if /i "%choice%"=="q" goto end

echo.
echo [错误] 无效选项，请重新选择
echo.
goto menu

:smart_mode
echo.
echo ========================================
echo [智能模式]
echo ========================================
echo   * 策略: 智能选择
echo   * 距离范围: 50-500米
echo   * 每条路线: 1000帧
echo   * 预计路线数: ~150条
echo   * 预计耗时: ~5小时
echo ========================================
echo.
pause
python auto_full_town_collection.py --strategy smart --min-distance 50 --max-distance 500 --frames-per-route 1000
goto end

:quick_test
echo.
echo ========================================
echo [快速测试模式]
echo ========================================
echo   * 策略: 智能选择
echo   * 距离范围: 100-300米
echo   * 每条路线: 200帧
echo   * 预计路线数: ~50条
echo   * 预计耗时: ~30分钟
echo ========================================
echo.
pause
python auto_full_town_collection.py --strategy smart --min-distance 100 --max-distance 300 --frames-per-route 200
goto end

:exhaustive_mode
echo.
echo ========================================
echo [穷举模式 - 警告]
echo ========================================
echo   * 策略: 穷举所有组合
echo   * 距离范围: 50-500米
echo   * 每条路线: 1000帧
echo   * 预计路线数: ~5000条（巨大！）
echo   * 预计耗时: ~150小时（6天）
echo ========================================
echo.
echo [警告] 此模式将收集大量数据，需要很长时间！
echo.
set /p confirm="确定要继续吗？(y/n): "
if /i not "%confirm%"=="y" goto menu
echo.
pause
python auto_full_town_collection.py --strategy exhaustive --min-distance 50 --max-distance 500 --frames-per-route 1000
goto end

:custom_mode
echo.
echo ========================================
echo [自定义配置]
echo ========================================
echo.
echo [提示] 每条路线最少需要200帧数据
echo.
set /p min_dist="最小距离（米，默认50）: "
set /p max_dist="最大距离（米，默认500）: "
set /p frames="每条路线帧数（默认1000）: "
set /p strategy="策略（smart/exhaustive，默认smart）: "

if "%min_dist%"=="" set min_dist=50
if "%max_dist%"=="" set max_dist=500
if "%frames%"=="" set frames=1000
if "%strategy%"=="" set strategy=smart

REM 检查帧数是否小于200
if %frames% LSS 200 (
    echo.
    echo [错误] 帧数不能小于200！
    echo [自动调整] 将帧数设置为200
    set frames=200
    echo.
    pause
)

echo.
echo 配置确认：
echo   * 策略: %strategy%
echo   * 距离范围: %min_dist%-%max_dist%米
echo   * 每条路线: %frames%帧
echo.
pause
python auto_full_town_collection.py --strategy %strategy% --min-distance %min_dist% --max-distance %max_dist% --frames-per-route %frames%
goto end

:end
echo.
echo ========================================
echo [程序结束]
echo ========================================
pause
