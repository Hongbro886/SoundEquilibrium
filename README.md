# SoundEquilibrium - 统一音量控制器
Windows 系统音量自动均衡器 - 让每一刻声音都在最佳音量
# 简介
SoundEquilibrium 是一款 Windows 桌面工具，通过 WASAPI Loopback 实时捕获系统音频输出，自动将音量平滑调整到目标响度，解决播放不同音频音量不统一的问题。
# 功能特性
- 实时音量均衡 - 持续监测系统音频响度，自动微调音量至目标值
- EMA 平滑算法 - 使用指数移动平均过滤瞬态峰值，避免频繁抖动
- 静音检测 - 低于阈值时自动跳过调整，防止异常提升背景噪音
- 系统托盘运行 - 最小化后常驻托盘，双击恢复窗口，右键快捷控制
- 开机自启动 - 支持一键设置开机自启
- Fluent Design 界面 - 基于 PySide6 + FluentWidgets 的现代化 UI
# 快速开始
下载安装
1. 从 Releases (../../releases/latest) 下载 AudioControl.zip
2. 解压到任意目录
3. 双击运行 AudioControl.exe

# 配置说明

编辑项目根目录下的 `config.json` 可自定义参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `TARGET_DBFS` | -25.5 | 目标响度 (dBFS) |
| `SILENCE_DBFS` | -55.0 | 静音阈值，低于此值不调整 |
| `DEAD_ZONE_DB` | 1.4 | 死区范围，误差在此范围内不动作 |
| `MAX_STEP` | 0.03 | 单次最大调整步长 |
| `MIN_VOLUME` | 0.03 | 最小系统音量 |
| `MAX_VOLUME` | 0.4 | 最大系统音量 |
| `CHUNK_MS` | 500 | 音频分析块大小 (毫秒) |
| `EMA_ALPHA_UP` | 0.3 | 响度上升时的 EMA 系数 |
| `EMA_ALPHA_DOWN` | 0.05 | 响度下降时的 EMA 系数 |
| `ADJUST_INTERVAL_S` | 1.0 | 调整间隔 (秒) |
| `DEBUG` | true | 开启调试日志输出 |
| `START_UP` | false | 启动时自动开启音量控制 |
| `AUTO_START` | false | 开机自启动 |

# 从源码启动

## 安装依赖 (需要 Python 3.14)
`uv sync`

## 启动
`uv run python main.py`

# 技术栈
- Python 3.14
- PySide6 - Qt for Python
- pyside6-fluent-widgets - Fluent Design 组件库
- pyaudiowpatch - PyAudio 的 WASAPI Loopback 分支
- pycaw - Windows Core Audio API 封装
- NumPy - 音频数据处理