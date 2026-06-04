import json
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pyaudiowpatch as pyaudio
from pycaw.pycaw import AudioUtilities

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return SimpleNamespace(**data)


config = load_config()


def debug(message):
    if config.DEBUG:
        print(message)


def get_loopback_device(audio):
    # 找到默认输出设备对应的 WASAPI loopback 录音设备。
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
    # 获取 Windows 主音量控制接口。
    debug("步骤 5：获取 Windows 默认扬声器的主音量控制接口")
    speakers = AudioUtilities.GetSpeakers()
    return speakers.EndpointVolume


def dbfs(samples):
    # 用 RMS 粗略估算当前输出音量，单位是 dBFS。
    rms = np.sqrt(np.mean(samples * samples))
    if rms <= 1e-9:
        debug("步骤 9：这一段音频几乎没有能量，按 -100.0 dBFS 处理")
        return -100.0
    return 20 * np.log10(rms)


def adjust_volume(volume, raw_dbfs, ema_dbfs):
    debug(f"步骤 10：原始响度 = {raw_dbfs:.1f} dBFS，平滑响度 = {ema_dbfs:.1f} dBFS，目标响度 = {config.TARGET_DBFS:.1f} dBFS")

    # 没有声音时不调整，避免越调越大。
    if ema_dbfs < config.SILENCE_DBFS:
        debug(f"步骤 11：低于静音阈值 {config.SILENCE_DBFS:.1f} dBFS，跳过调整")
        return

    # error > 0 表示当前太小，需要调大；error < 0 表示当前太大，需要调小。
    error = config.TARGET_DBFS - ema_dbfs
    if abs(error) < config.DEAD_ZONE_DB:
        debug(f"步骤 11：误差 {error:.1f} dB 在允许范围内，跳过调整")
        return

    # 根据误差调整音量，但限制每次调整幅度。
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


def main():
    # 初始化音频捕获和音量控制。
    debug("启动：准备监听 Windows 最终输出音量")
    audio = pyaudio.PyAudio()
    device = get_loopback_device(audio)
    volume = get_volume_control()

    # 按默认输出设备的采样率和声道数读取音频。
    rate = int(device["defaultSampleRate"])
    channels = int(device["maxInputChannels"])
    frames = int(rate * config.CHUNK_MS / 1000)
    debug(f"步骤 6：采样率={rate}，声道数={channels}，每次读取帧数={frames}")

    debug("步骤 7：打开 loopback 音频流，之后读到的就是系统最终混音")
    stream = audio.open(
        format=pyaudio.paFloat32,
        channels=channels,
        rate=rate,
        input=True,
        input_device_index=device["index"],
        frames_per_buffer=frames,
    )

    debug(f"监听中：{device['name']}")

    ema_dbfs = None

    try:
        while True:
            # 读取最终输出的混音音频，计算响度，然后调整系统主音量。
            debug("步骤 8：读取最近一小段最终输出音频")
            data = stream.read(frames, exception_on_overflow=False)
            samples = np.frombuffer(data, dtype=np.float32)

            # loopback 捕获的是系统音量控制之前的应用输出信号，
            # 需要乘以当前系统音量来估算用户实际听到的响度。
            current_vol = volume.GetMasterVolumeLevelScalar()
            actual_samples = samples * current_vol
            raw_dbfs = dbfs(actual_samples)

            # 用非对称 EMA 平滑：响度上升快跟、下降慢衰减，抑制短暂安静的干扰。
            if ema_dbfs is None:
                ema_dbfs = raw_dbfs
            else:
                alpha = config.EMA_ALPHA_UP if raw_dbfs > ema_dbfs else config.EMA_ALPHA_DOWN
                ema_dbfs = alpha * raw_dbfs + (1 - alpha) * ema_dbfs

            adjust_volume(volume, raw_dbfs, ema_dbfs)
            time.sleep(0.05)
    finally:
        debug("退出：关闭音频流并释放资源")
        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    main()
