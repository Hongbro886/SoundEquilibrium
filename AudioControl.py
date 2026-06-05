import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pyaudiowpatch as pyaudio
from pycaw.pycaw import AudioUtilities
from PySide6.QtCore import QThread, Signal


def get_app_dir() -> Path:
    """Get application directory, works both in development and when frozen by PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


CONFIG_PATH = get_app_dir() / "config.json"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return SimpleNamespace(**data)


config = load_config()


def debug(message):
    if config.DEBUG:
        print(message)


def get_loopback_device(audio):
    debug("步骤 1：读取 Windows WASAPI 音频系统信息")
    wasapi = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_output = audio.get_device_info_by_index(wasapi["defaultOutputDevice"])
    debug(f"步骤 2：默认输出设备是：{default_output['name']}")

    debug("步骤 3：遍历所有音频设备，寻找默认输出设备对应的 loopback 设备")
    for i in range(audio.get_device_count()):
        device = audio.get_device_info_by_index(i)
        if device.get("isLoopbackDevice") and default_output["name"] in device["name"]:
            debug(f"步骤 4：找到 loopback 设备：{device['name']}")
            return device

    raise RuntimeError("没有找到 WASAPI loopback 设备")


def get_volume_control():
    debug("步骤 5：获取 Windows 默认扬声器的主音量控制接口")
    speakers = AudioUtilities.GetSpeakers()
    return speakers.EndpointVolume


def dbfs(samples):
    rms = np.sqrt(np.mean(samples * samples))
    if rms <= 1e-9:
        debug("步骤 9：这一段音频几乎没有能量，按 -100.0 dBFS 处理")
        return -100.0
    return 20 * np.log10(rms)


def adjust_volume(volume, raw_dbfs, ema_dbfs):
    debug(f"步骤 10：原始响度 = {raw_dbfs:.1f} dBFS，平滑响度 = {ema_dbfs:.1f} dBFS，目标响度 = {config.TARGET_DBFS:.1f} dBFS")

    if ema_dbfs < config.SILENCE_DBFS:
        debug(f"步骤 11：低于静音阈值 {config.SILENCE_DBFS:.1f} dBFS，跳过调整")
        return

    error = config.TARGET_DBFS - ema_dbfs
    if abs(error) < config.DEAD_ZONE_DB:
        debug(f"步骤 11：误差 {error:.1f} dB 在允许范围内，跳过调整")
        return

    current_volume = volume.GetMasterVolumeLevelScalar()
    step = min(abs(error) / 30.0, config.MAX_STEP)
    new_volume = current_volume + step if error > 0 else current_volume - step
    new_volume = max(config.MIN_VOLUME, min(config.MAX_VOLUME, new_volume))

    volume.SetMasterVolumeLevelScalar(new_volume, None)
    direction = "调大" if error > 0 else "调小"
    debug(
        f"步骤 11：声音偏{'小' if error > 0 else '大'}，系统音量从 "
        f"{current_volume:.2f} {direction}到 {new_volume:.2f}"
    )


class AudioWorker(QThread):
    volume_changed = Signal(float)
    raw_loudness_changed = Signal(float)
    loudness_changed = Signal(float)
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        audio = None
        stream = None
        try:
            self.status_changed.emit("正在初始化音频设备...")
            audio = pyaudio.PyAudio()
            device = get_loopback_device(audio)
            volume = get_volume_control()

            rate = int(device["defaultSampleRate"])
            channels = int(device["maxInputChannels"])
            frames = int(rate * config.CHUNK_MS / 1000)
            read_frames = max(1, int(rate * min(config.CHUNK_MS, 50) / 1000))
            debug(f"步骤 6：采样率={rate}，声道数={channels}，每次读取帧数={frames}")

            pending_chunks = []
            pending_frames = 0
            pending_lock = threading.Lock()

            def on_audio_data(in_data, frame_count, time_info, status):
                nonlocal pending_frames
                if not self._running:
                    return (None, pyaudio.paComplete)

                with pending_lock:
                    pending_chunks.append(in_data)
                    pending_frames += frame_count

                return (None, pyaudio.paContinue)

            debug("步骤 7：打开 loopback 音频流")
            stream = audio.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device["index"],
                frames_per_buffer=read_frames,
                stream_callback=on_audio_data,
            )
            stream.start_stream()

            self.status_changed.emit(f"监听中: {device['name']}")
            ema_dbfs = None
            last_adjust_time = 0.0
            debug("步骤 8：开始读取最终输出音频")

            while self._running:
                with pending_lock:
                    if pending_frames < frames:
                        chunks = None
                    else:
                        chunks = pending_chunks[:]
                        pending_chunks.clear()
                        pending_frames = 0

                if chunks is None:
                    time.sleep(0.05)
                    continue

                samples = np.frombuffer(b"".join(chunks), dtype=np.float32)

                current_vol = volume.GetMasterVolumeLevelScalar()
                actual_samples = samples * current_vol
                raw_dbfs = dbfs(actual_samples)

                if ema_dbfs is None:
                    ema_dbfs = raw_dbfs
                else:
                    alpha = config.EMA_ALPHA_UP if raw_dbfs > ema_dbfs else config.EMA_ALPHA_DOWN
                    ema_dbfs = alpha * raw_dbfs + (1 - alpha) * ema_dbfs

                now = time.monotonic()
                if now - last_adjust_time >= config.ADJUST_INTERVAL_S:
                    adjust_volume(volume, raw_dbfs, ema_dbfs)
                    last_adjust_time = now

                self.volume_changed.emit(current_vol)
                self.raw_loudness_changed.emit(raw_dbfs)
                self.loudness_changed.emit(ema_dbfs)
                time.sleep(0.05)

        except Exception as e:
            if self._running:
                self.error_occurred.emit(str(e))
                self.status_changed.emit("发生错误")
        finally:
            debug("退出：关闭音频流并释放资源")
            if stream:
                try:
                    stream.stop_stream()
                except Exception:
                    pass

                try:
                    stream.close()
                except Exception:
                    pass

            if audio:
                try:
                    audio.terminate()
                except Exception:
                    pass

            self.status_changed.emit("已停止")

    def stop(self):
        self._running = False
