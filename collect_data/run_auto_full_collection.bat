@echo off
chcp 65001 >nul
title 自动收集Town01数据工具

echo ========================================
echo [自动收集Town01数据工具]
echo ========================================
echo.
echo 功能说明：
echo   * 自动在Town01地图中收集驾驶数据
echo   * 支持多种收集策略和参数配置
echo   * 自动生成路径并记录传感器数据
echo   * 数据保存为HDF5格式
echo.
echo ========================================
echo.

:menu
echo 请选择收集模式：
echo.
echo   [1] 智能收集模式 - 平衡数据质量和收集效率（推荐）
echo   [2] 快速测试 - 快速验证系统功能
echo   [3] 穷举收集模式 - 收集所有可能路径（耗时长）
echo   [4] 自定义参数
echo   [5] 多天气轮换收集 - 自动切换天气收集数据（新功能）
echo   [Q] 退出
echo.

set /p choice="请输入选项 [1-5/Q]: "

if /i "%choice%"=="1" goto smart_mode
if /i "%choice%"=="2" goto quick_test
if /i "%choice%"=="3" goto exhaustive_mode
if /i "%choice%"=="4" goto custom_mode
if /i "%choice%"=="5" goto multi_weather_mode
if /i "%choice%"=="Q" goto end
if /i "%choice%"=="q" goto end

echo.
echo [错误] 无效的选项，请重新选择
echo.
goto menu

:smart_mode
echo.
echo ========================================
echo [智能收集模式]
echo ========================================
echo   * 策略: 智能筛选路径
echo   * 路径距离: 50-500米
echo   * 每条路线: 1000帧
echo   * 预计路线数: ~150条
echo   * 预计时长: ~5小时
echo ========================================
echo.
pause
python auto_full_town_collection.py --strategy smart --min-distance 80 --max-distance 800 --frames-per-route 2000
goto end

:quick_test
echo.
echo ========================================
echo [快速测试模式]
echo ========================================
echo   * 策略: 智能筛选路径
echo   * 路径距离: 100-300米
echo   * 每条路线: 200帧
echo   * 预计路线数: ~50条
echo   * 预计时长: ~30分钟
echo ========================================
echo.
pause
python auto_full_town_collection.py --strategy smart --min-distance 100 --max-distance 300 --frames-per-route 200
goto end

:exhaustive_mode
echo.
echo ========================================
echo [穷举模式 - 完整收集]
echo ========================================
echo   * 策略: 收集所有可能路径
echo   * 路径距离: 50-500米
echo   * 每条路线: 1000帧
echo   * 预计路线数: ~5000条（取决于地图）
echo   * 预计时长: ~150小时（约6天）
echo ========================================
echo.
echo [警告] 此模式将收集大量数据，需要充足的存储空间和时间
echo.
set /p confirm="确认继续？(y/n): "
if /i not "%confirm%"=="y" goto menu
echo.
pause
python auto_full_town_collection.py --strategy exhaustive --min-distance 50 --max-distance 500 --frames-per-route 1000
goto end

:custom_mode
echo.
echo ========================================
echo [自定义参数模式]
echo ========================================
echo.
set /p min_dist="最小路径距离（米，默认50）: "
set /p max_dist="最大路径距离（米，默认500）: "
set /p frames="每条路线帧数（默认1000）: "
set /p strategy="收集策略smart/exhaustive（默认smart）: "

if "%min_dist%"=="" set min_dist=50
if "%max_dist%"=="" set max_dist=500
if "%frames%"=="" set frames=1000
if "%strategy%"=="" set strategy=smart

echo.
echo 配置确认：
echo   * 策略: %strategy%
echo   * 路径距离: %min_dist%-%max_dist%米
echo   * 每条路线: %frames%帧
echo.
pause
python auto_full_town_collection.py --strategy %strategy% --min-distance %min_dist% --max-distance %max_dist% --frames-per-route %frames%
goto end

:multi_weather_mode
echo.
echo ========================================
echo [多天气轮换收集模式]
echo ========================================
echo.
echo 可选天气组合：
echo   [1] basic    - 基础组合（4种天气）：晴朗正午、多云正午、晴朗日落、晴朗夜晚
echo   [2] all_noon - 所有正午天气（5种）
echo   [3] clear_all - 所有晴朗天气（3种）
echo   [4] full     - 完整组合（11种天气）
echo   [5] 自定义天气列表
echo.
set /p weather_choice="请选择天气组合 [1-5]: "

if "%weather_choice%"=="1" (
    set weather_preset=basic
    goto run_multi_weather
)
if "%weather_choice%"=="2" (
    set weather_preset=all_noon
    goto run_multi_weather
)
if "%weather_choice%"=="3" (
    set weather_preset=clear_all
    goto run_multi_weather
)
if "%weather_choice%"=="4" (
    set weather_preset=full
    goto run_multi_weather
)
if "%weather_choice%"=="5" (
    echo.
    echo 请输入天气列表（空格分隔），可选天气：
    echo   ClearNoon CloudyNoon WetNoon SoftRainNoon HardRainNoon
    echo   ClearSunset CloudySunset WetSunset SoftRainSunset
    echo   ClearNight CloudyNight WetNight SoftRainNight
    echo.
    set /p custom_weathers="天气列表: "
    goto run_custom_weather
)
goto multi_weather_mode

:run_multi_weather
echo.
echo ========================================
echo [开始多天气轮换收集]
echo ========================================
echo   * 天气组合: %weather_preset%
echo   * 策略: 智能筛选路径
echo   * 每条路线: 1000帧
echo   * 数据将按天气分目录保存
echo ========================================
echo.
pause
python auto_full_town_collection.py --multi-weather %weather_preset% --strategy smart --frames-per-route 1000
goto end

:run_custom_weather
echo.
echo ========================================
echo [开始自定义天气收集]
echo ========================================
echo   * 天气列表: %custom_weathers%
echo   * 策略: 智能筛选路径
echo   * 每条路线: 1000帧
echo ========================================
echo.
pause
python auto_full_town_collection.py --weather-list %custom_weathers% --strategy smart --frames-per-route 1000
goto end

:end
echo.
echo ========================================
echo [程序已结束]
echo ========================================
pause
