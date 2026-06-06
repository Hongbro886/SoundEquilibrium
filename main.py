import sys
import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
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
    SettingCardGroup,
    SwitchSettingCard
)

from Models.AudioControl import AudioWorker
import Models.Configer
import Models.System

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.config = Models.Configer.load_config()
        self.setObjectName("settingspage")

        self.layout = QVBoxLayout(self)

        self.general_group = SettingCardGroup("常规", self)

        self.auto_start_card = SwitchSettingCard(
            FluentIcon.POWER_BUTTON,
            "开机自启动",
            "登录时启动应用",
            parent=self.general_group,
        )

        self.auto_start = SwitchSettingCard(
            FluentIcon.POWER_BUTTON,
            "启动时开启统一音量控制",
            "启动时直接开启程序主要功能",
            parent=self.general_group,
        )

        self.auto_start.setChecked(self.config.AUTO_START)
        self.auto_start_card.setChecked(self.config.START_UP)
        self.general_group.addSettingCard(self.auto_start_card)
        self.general_group.addSettingCard(self.auto_start)

        self.layout.addWidget(self.general_group)
        self.layout.addStretch(1)

        self.auto_start_card.checkedChanged.connect(self.on_auto_start_change)
        self.auto_start.checkedChanged.connect(self.on_auto_start_change_main)
    def on_auto_start_change(self,checked:bool):
        if checked:
            Models.System.create_startup_shortcut()
        else:
            Models.System.remove_startup_shortcut()
        self.config.START_UP = checked
        Models.Configer.save_config(config=self.config)
        self.config = Models.Configer.load_config()

    def on_auto_start_change_main(self,checked: bool):
        self.config.AUTO_START = checked
        Models.Configer.save_config(config=self.config)
        self.config = Models.Configer.load_config()
        

        

class HomePage(QWidget):
    def __init__(self):

        super().__init__()
        
        self.setObjectName("homepage")
        self.worker = None
        self._closing = False

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

        self.run_config()
    def run_config(self):
        config = Models.Configer.load_config()
        if config.AUTO_START:
            self.start_control()
    def start_control(self):
        self.worker = AudioWorker()
        self.worker.volume_changed.connect(self.on_volume_changed)
        self.worker.raw_loudness_changed.connect(self.on_raw_loudness_changed)
        self.worker.loudness_changed.connect(self.on_loudness_changed)
        self.worker.status_changed.connect(self.on_status_changed)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        win = self.window()
        if hasattr(win, '_update_menu_state'):
            win._update_menu_state()

    def stop_control(self):
        if self.worker:
            self.worker.stop()
            self.status_label.setText("状态: 正在停止...")
            self.stop_btn.setEnabled(False)

            win = self.window()
            if hasattr(win, '_update_menu_state'):
                win._update_menu_state()

    def on_worker_finished(self):
        self.worker = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        win = self.window()
        if hasattr(win, '_update_menu_state'):
            win._update_menu_state()

        if self._closing:
            self.window().close()


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

        win = self.window()
        if hasattr(win, '_update_menu_state'):
            win._update_menu_state()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self._closing = True
            self.stop_control()
            event.ignore()
            return

        event.accept()

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("统一音量控制器")
        self.resize(600, 450)

        self.homepage = HomePage()
        self.settingspage = SettingsPage()
        self.addSubInterface(
            self.homepage,
            FluentIcon.HOME,
            "主页"
        )
        self.addSubInterface(
            self.settingspage,
            FluentIcon.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM
        )

        self._tray_icon = None
        self._quitting = False
        self._setup_tray_icon()

    def _setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)

        app_icon = QIcon(get_icon_path())
        if app_icon.isNull():
            app_icon = QIcon.fromTheme("audio-volume-high")
        self.tray_icon.setIcon(app_icon)
        self.tray_icon.setToolTip("统一音量控制器")

        tray_menu = QMenu()

        self.enable_action = QAction("开启统一音量控制", self)
        self.enable_action.triggered.connect(self._on_enable_volume)
        self.disable_action = QAction("关闭统一音量控制", self)
        self.disable_action.triggered.connect(self._on_disable_volume)

        self._update_menu_state()

        tray_menu.addAction(self.enable_action)
        tray_menu.addAction(self.disable_action)
        tray_menu.addSeparator()

        restart_action = QAction("重启", self)
        restart_action.triggered.connect(self._on_restart)
        tray_menu.addAction(restart_action)

        quit_action = QAction("关闭", self)
        quit_action.triggered.connect(self._on_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _update_menu_state(self):
        is_running = self.homepage.worker is not None and self.homepage.worker.isRunning()
        self.enable_action.setEnabled(not is_running)
        self.disable_action.setEnabled(is_running)

    def _on_enable_volume(self):
        self.homepage.start_control()
        self._update_menu_state()

    def _on_disable_volume(self):
        self.homepage.stop_control()
        self._update_menu_state()

    def _on_restart(self):
        self._quitting = True
        if self.homepage.worker and self.homepage.worker.isRunning():
            self.homepage.worker.stop()
            self.homepage.worker.wait(3000)
        python = sys.executable
        script = os.path.abspath(__file__)
        subprocess.Popen([python, script])
        QApplication.quit()

    def _on_quit(self):
        self._quitting = True
        if self.homepage.worker and self.homepage.worker.isRunning():
            self.homepage.worker.stop()
            self.homepage.worker.wait(3000)
        QApplication.quit()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()
            self.raise_()

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        self.hide()
        self.tray_icon.showMessage(
            "统一音量控制器",
            "程序已最小化到托盘，如需退出请右键托盘图标选择关闭。",
            QSystemTrayIcon.Information,
            2000
        )
        event.ignore()


def get_icon_path():
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return str(base / "icon.ico")


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon = QIcon(get_icon_path())
    app.setWindowIcon(icon)

    setTheme(Theme.AUTO)
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
