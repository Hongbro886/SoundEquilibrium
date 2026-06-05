import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    FluentWindow,
    NavigationItemPosition,
    FluentIcon,
    TitleLabel,
    SubtitleLabel,
    BodyLabel,
    CardWidget,
    SwitchButton,
    PushButton,
    setTheme,
    Theme,
)

from AudioControl import AudioWorker


class HomePage(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("homepage")
        self.worker = None

        layout = QVBoxLayout(self)

        title = TitleLabel("统一音量控制器")
        layout.addWidget(title)

        status_card = CardWidget()
        status_layout = QVBoxLayout(status_card)
        self.status_label = SubtitleLabel("状态: 未启动")
        self.volume_label = BodyLabel("当前音量: --")
        self.raw_loudness_label = BodyLabel("原始响度: -- dBFS")
        self.loudness_label = BodyLabel("平滑响度: -- dBFS")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.volume_label)
        status_layout.addWidget(self.raw_loudness_label)
        status_layout.addWidget(self.loudness_label)
        layout.addWidget(status_card)

        btn_layout = QHBoxLayout()
        self.start_btn = PushButton("启动")
        self.stop_btn = PushButton("停止")
        self.set_start_up_btn = PushButton("设置开机自启动")
        self.stop_btn.setEnabled(False)

        self.start_btn.clicked.connect(self.start_control)
        self.stop_btn.clicked.connect(self.stop_control)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def start_control(self):
        self.worker = AudioWorker()
        self.worker.volume_changed.connect(self.on_volume_changed)
        self.worker.raw_loudness_changed.connect(self.on_raw_loudness_changed)
        self.worker.loudness_changed.connect(self.on_loudness_changed)
        self.worker.status_changed.connect(self.on_status_changed)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_control(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def on_volume_changed(self, vol):
        self.volume_label.setText(f"当前音量: {vol:.2f}")

    def on_raw_loudness_changed(self, loudness):
        self.raw_loudness_label.setText(f"原始响度: {loudness:.1f} dBFS")

    def on_loudness_changed(self, loudness):
        self.loudness_label.setText(f"当前响度: {loudness:.1f} dBFS")

    def on_status_changed(self, status):
        self.status_label.setText(f"状态: {status}")

    def on_error(self, msg):
        self.status_label.setText(f"错误: {msg}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        self.stop_control()
        event.accept()

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("统一音量控制器")
        self.resize(500, 350)

        self.homepage = HomePage()
        self.addSubInterface(
            self.homepage,
            FluentIcon.HOME,
            "主页"
        )


def main():
    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
