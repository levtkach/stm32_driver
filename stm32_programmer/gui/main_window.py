import sys
import subprocess
import platform
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QHBoxLayout,
    QTextEdit,
    QComboBox,
    QProgressBar,
    QMessageBox,
    QSizePolicy,
    QFrame,
    QTabWidget,
)
from PyQt5.QtGui import QCloseEvent, QMouseEvent, QPainter
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDateTime, QSettings, QTimer
import serial.tools.list_ports
import threading
from pathlib import Path
import html
from stm32_programmer.programmers.core import setup_logging, program_device
from stm32_programmer.programmers.base import BaseProgrammer
from .styles import get_stylesheet
from .serial_monitor import SerialMonitorWidget
from .button_animation import DeleteAnimation
import logging

logger = logging.getLogger(__name__)


class ProgrammingThread(QThread):
    finished = pyqtSignal(bool, str)
    progress_updated = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    progress_percent_updated = pyqtSignal(int)
    programming_progress_updated = pyqtSignal(int)
    testing_progress_updated = pyqtSignal(int)

    def __init__(self, lv_path, hv_path, uart_port, device_index):
        super().__init__()
        self.lv_path = lv_path
        self.hv_path = hv_path
        self.uart_port = uart_port
        self.device_index = device_index
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        try:
            if self._stop_requested:
                self.finished.emit(False, "Остановлено пользователем")
                return
            stop_check = lambda: self._stop_requested

            success, message = program_device(
                lv_firmware_path=self.lv_path,
                hv_firmware_path=self.hv_path,
                progress_callback=self.progress_updated.emit,
                status_callback=self.status_updated.emit,
                progress_percent_callback=self.progress_percent_updated.emit,
                programming_progress_callback=self.programming_progress_updated.emit,
                testing_progress_callback=self.testing_progress_updated.emit,
                stop_check_callback=stop_check,
                uart_port=self.uart_port,
                device_index=self.device_index,
            )
            if self._stop_requested:
                self.finished.emit(False, "Остановлено пользователем")
            else:
                self.finished.emit(success, message)
        except Exception as e:
            if self._stop_requested:
                self.finished.emit(False, "Остановлено пользователем")
            else:
                self.finished.emit(False, f"Критическая ошибка: {e}")


class FirmwareLoadButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.clear_callback = None
        self.has_firmware_check = None
        self.long_press_timer = QTimer()
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(self._on_long_press)
        self.long_press_duration = 800
        self.animation_delay_timer = QTimer()
        self.animation_delay_timer.setSingleShot(True)
        self.animation_delay_timer.timeout.connect(self._start_animation)
        self.animation_delay = 150
        animation_duration = self.long_press_duration - self.animation_delay
        self.delete_animation = DeleteAnimation(self, animation_duration)
        self._animation_started = False
        self.setMinimumHeight(28)
        self.setMaximumHeight(28)

    def set_validation_border(self, is_valid):
        if is_valid is None:
            self.setProperty("validationBorder", "")
        elif is_valid:
            self.setProperty("validationBorder", "valid")
        else:
            self.setProperty("validationBorder", "invalid")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.delete_animation.is_animating:
            painter = QPainter()
            if painter.begin(self):
                try:
                    painter.setRenderHint(QPainter.Antialiasing)
                    self.delete_animation.draw_progress_bar(painter)
                finally:
                    painter.end()

    def set_clear_callback(self, callback):
        self.clear_callback = callback

    def set_has_firmware_check(self, check_func):
        self.has_firmware_check = check_func

    def _start_animation(self):
        if not self._animation_started:
            if self.has_firmware_check and not self.has_firmware_check():
                return
            self._animation_started = True
            self.delete_animation.start()

    def _on_long_press(self):
        if self.has_firmware_check and not self.has_firmware_check():
            self.delete_animation.stop()
            self._animation_started = False
            return
        self.delete_animation.stop()
        self._animation_started = False
        if self.clear_callback:
            self.clear_callback()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.has_firmware_check and not self.has_firmware_check():
                super().mousePressEvent(event)
                return
            self.long_press_timer.start(self.long_press_duration)
            self._animation_started = False
            self.animation_delay_timer.start(self.animation_delay)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.long_press_timer.stop()
            self.animation_delay_timer.stop()
            self.delete_animation.stop()
            self._animation_started = False
        super().mouseReleaseEvent(event)


class STM32ProgrammerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STM32 Programmer")
        self.setGeometry(200, 200, 800, 750)
        self.setMinimumSize(700, 600)

        self.lv_file_path = ""
        self.hv_file_path = ""
        self.is_programming = False
        self.is_stopping = False
        self.programming_thread = None
        self.devices = []
        self.programmer = BaseProgrammer()
        self.lv_status = None
        self.hv_status = None
        self.settings = QSettings("STM32Programmer", "FirmwarePaths")
        self.current_device_id = None
        self.current_port = None
        self.current_theme = self.settings.value("theme", "dark")
        self.init_sounds()
        logger, log_file = setup_logging()
        self.log_file = log_file
        self.init_ui()
        self.apply_theme(self.current_theme)

    def init_sounds(self):
        self.sound_enabled = True
        self.platform = platform.system()

    def play_sound(self, sound_type):
        if not self.sound_enabled:
            return

        try:
            if self.platform == "Darwin":
                self._play_sound_macos(sound_type)
            elif self.platform == "Windows":
                self._play_sound_windows(sound_type)
            else:
                self._play_sound_linux(sound_type)
        except Exception:
            pass

    def _play_sound_macos(self, sound_type):
        sound_map = {
            "success": "/System/Library/Sounds/Glass.aiff",
            "warning": "/System/Library/Sounds/Basso.aiff",
            "error": "/System/Library/Sounds/Funk.aiff",
        }

        sound_file = sound_map.get(sound_type)
        if sound_file:
            try:
                subprocess.Popen(
                    ["afplay", sound_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def _play_sound_windows(self, sound_type):
        try:
            import winsound

            sound_map = {
                "success": winsound.MB_OK,
                "warning": winsound.MB_ICONEXCLAMATION,
                "error": winsound.MB_ICONERROR,
            }

            sound_flag = sound_map.get(sound_type)
            if sound_flag:
                winsound.MessageBeep(sound_flag)
        except ImportError:
            app = QApplication.instance()
            if app:
                app.beep()
        except Exception:
            pass

    def _play_sound_linux(self, sound_type):
        sound_map = {
            "success": "bell",
            "warning": "message",
            "error": "dialog-error",
        }

        sound_name = sound_map.get(sound_type, "bell")

        try:
            subprocess.Popen(
                ["paplay", f"/usr/share/sounds/freedesktop/stereo/{sound_name}.oga"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

        try:
            app = QApplication.instance()
            if app:
                app.beep()
        except Exception:
            pass

    def show_message_box(
        self, title, message, icon_type=QMessageBox.Information, buttons=None
    ):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon_type)
        if icon_type == QMessageBox.Information:
            self.play_sound("success")
        elif icon_type == QMessageBox.Warning:
            self.play_sound("warning")
        elif icon_type == QMessageBox.Critical:
            self.play_sound("error")

        if buttons is None:
            buttons = QMessageBox.Ok

        return msg_box.exec_()

        if buttons == (QMessageBox.Yes | QMessageBox.No):
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            yes_button = msg_box.button(QMessageBox.Yes)
            no_button = msg_box.button(QMessageBox.No)
            if yes_button:
                yes_button.setText("С Богом")
            if no_button:
                no_button.setText("Нет")
            return msg_box.exec_()
        else:
            msg_box.setStandardButtons(buttons)
            if buttons == QMessageBox.Ok:
                ok_button = msg_box.button(QMessageBox.Ok)
                if ok_button:
                    ok_button.setText("ОК")
            return msg_box.exec_()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        header_layout = QHBoxLayout()
        header_layout.addStretch()

        title_label = QLabel("STM32 Programmer")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setProperty("title", True)
        header_layout.addWidget(title_label, 1)

        self.btn_theme = QPushButton("☀" if self.current_theme == "dark" else "☾")
        self.btn_theme.setProperty("themeToggle", True)
        self.btn_theme.setMinimumWidth(28)
        self.btn_theme.setToolTip("Переключить тему (светлая/темная)")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.btn_theme)

        layout.addLayout(header_layout)

        self.tabs = QTabWidget()
        self.tabs.setProperty("tabs", True)
        self.programming_widget = QWidget()
        programming_layout = QVBoxLayout()
        programming_layout.setContentsMargins(0, 0, 0, 0)
        self.programming_widget.setLayout(programming_layout)
        self.serial_monitor = SerialMonitorWidget(self)
        self.tabs.addTab(self.programming_widget, "Программатор")
        self.tabs.addTab(self.serial_monitor, "Serial Monitor")
        layout.addWidget(self.tabs)
        layout.addSpacing(20)
        programming_content = self.create_programming_content()
        programming_layout.addWidget(programming_content)
        self.combobox_ports.currentIndexChanged.connect(
            self.on_programming_port_changed
        )
        self.serial_monitor.port_changed.connect(self.on_serial_monitor_port_changed)
        self.setLayout(layout)
        self.init_ui_finalize()

    def init_ui_finalize(self):
        self.update_buttons_state()
        self._load_saved_firmware_paths()
        self.refresh_devices()
        self.refresh_ports(None)
        self._load_last_device_and_port()
        if self.combobox_ports.currentIndex() >= 0:
            port = self.combobox_ports.currentData()
            if port:
                self.serial_monitor.set_port(port)

    def create_programming_content(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)
        device_port_group = QFrame()
        device_port_group.setProperty("inputGroup", True)
        device_port_layout = QVBoxLayout()
        device_port_layout.setSpacing(4)
        device_port_layout.setContentsMargins(6, 4, 6, 4)
        device_layout = QHBoxLayout()
        device_layout.setSpacing(6)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_label = QLabel("STM32 устройство:")
        device_label.setMinimumWidth(150)
        device_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        device_layout.addWidget(device_label)

        device_container = QFrame()
        device_container.setProperty("inputContainer", True)
        device_container_layout = QHBoxLayout()
        device_container_layout.setContentsMargins(4, 2, 8, 2)
        device_container_layout.setSpacing(8)
        self.combobox_devices = QComboBox()
        self.combobox_devices.setMinimumHeight(28)
        self.combobox_devices.currentIndexChanged.connect(self.on_device_selected)
        self.combobox_devices.currentTextChanged.connect(
            lambda text: self.combobox_devices.setToolTip(text)
        )
        self.combobox_devices.currentIndexChanged.connect(self._on_device_changed)
        device_container_layout.addWidget(self.combobox_devices, 1)

        self.btn_refresh_devices = QPushButton("↻")
        self.btn_refresh_devices.setProperty("refreshButton", True)
        self.btn_refresh_devices.setFixedSize(28, 28)
        self.btn_refresh_devices.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_devices.setToolTip("Обновить список устройств")
        self.btn_refresh_devices.clicked.connect(self.refresh_devices)
        device_container_layout.addWidget(self.btn_refresh_devices)
        device_container.setLayout(device_container_layout)
        device_layout.addWidget(device_container, 1)
        device_port_layout.addLayout(device_layout)
        port_layout = QHBoxLayout()
        port_layout.setSpacing(6)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_label = QLabel("COM порт:")
        port_label.setMinimumWidth(150)
        port_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        port_layout.addWidget(port_label)

        port_container = QFrame()
        port_container.setProperty("inputContainer", True)
        port_container_layout = QHBoxLayout()
        port_container_layout.setContentsMargins(4, 2, 8, 2)
        port_container_layout.setSpacing(8)
        self.combobox_ports = QComboBox()
        self.combobox_ports.setMinimumHeight(28)
        self.combobox_ports.currentIndexChanged.connect(self._on_port_changed)
        self.combobox_ports.currentTextChanged.connect(
            lambda text: self.combobox_ports.setToolTip(text)
        )
        port_container_layout.addWidget(self.combobox_ports, 1)
        self.btn_refresh_ports = QPushButton("↻")
        self.btn_refresh_ports.setProperty("refreshButton", True)
        self.btn_refresh_ports.setFixedSize(28, 28)
        self.btn_refresh_ports.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_ports.setToolTip("Обновить список портов")
        self.btn_refresh_ports.clicked.connect(self.refresh_ports)
        port_container_layout.addWidget(self.btn_refresh_ports)
        port_container.setLayout(port_container_layout)
        port_layout.addWidget(port_container, 1)
        device_port_layout.addLayout(port_layout)
        firmware_layout = QHBoxLayout()
        firmware_layout.setSpacing(6)
        firmware_layout.setContentsMargins(0, 0, 0, 6)
        self.btn_load_lv = FirmwareLoadButton("Загрузить LV прошивку")
        self.btn_load_lv.setMinimumHeight(28)
        self.btn_load_lv.clicked.connect(lambda: self.load_firmware("LV"))
        self.btn_load_lv.set_clear_callback(lambda: self.clear_firmware("LV"))
        self.btn_load_lv.set_has_firmware_check(lambda: bool(self.lv_file_path))
        firmware_layout.addWidget(self.btn_load_lv, 1)

        self.btn_load_hv = FirmwareLoadButton("Загрузить HV прошивку")
        self.btn_load_hv.setMinimumHeight(28)
        self.btn_load_hv.clicked.connect(lambda: self.load_firmware("HV"))
        self.btn_load_hv.set_clear_callback(lambda: self.clear_firmware("HV"))
        self.btn_load_hv.set_has_firmware_check(lambda: bool(self.hv_file_path))
        firmware_layout.addWidget(self.btn_load_hv, 1)
        device_port_layout.addLayout(firmware_layout)

        device_port_group.setLayout(device_port_layout)
        layout.addWidget(device_port_group)

        log_control_layout = QHBoxLayout()
        log_control_layout.setSpacing(8)
        log_control_layout.setContentsMargins(8, 4, 8, 4)

        log_label = QLabel("Логи:")
        log_label.setProperty("info", True)
        log_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        log_control_layout.addWidget(log_label)

        log_control_layout.addStretch()

        self.btn_program = QPushButton("▶")
        self.btn_program.setProperty("programButton", True)
        self.btn_program.setEnabled(False)
        self.btn_program.setFixedSize(28, 28)
        self.btn_program.setToolTip("Прошить микроконтроллер")
        self.btn_program.setCursor(Qt.PointingHandCursor)
        self.btn_program.clicked.connect(self.toggle_programming)
        log_control_layout.addWidget(self.btn_program)

        self.btn_clear = QPushButton("✕")
        self.btn_clear.setProperty("iconButton", True)
        self.btn_clear.setFixedSize(28, 28)
        self.btn_clear.setToolTip("Очистить логи")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_files)
        log_control_layout.addWidget(self.btn_clear)

        self.btn_open_log = QPushButton("📄")
        self.btn_open_log.setProperty("iconButton", True)
        self.btn_open_log.setFixedSize(28, 28)
        self.btn_open_log.setToolTip("Открыть файл лога")
        self.btn_open_log.setCursor(Qt.PointingHandCursor)
        self.btn_open_log.clicked.connect(self.open_log_file)
        log_control_layout.addWidget(self.btn_open_log)

        layout.addLayout(log_control_layout)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        font = self.console.font()
        font.setFamily("JetBrains Mono")
        font.setPointSize(11)
        font.setStyleHint(font.Monospace)
        font.setFixedPitch(True)
        self.console.setFont(font)
        layout.addWidget(self.console)

        self.programming_progress_bar = QProgressBar()
        self.programming_progress_bar.setRange(0, 100)
        self.programming_progress_bar.setTextVisible(True)
        self.programming_progress_bar.setFormat("Программирование: %p%")
        self.programming_progress_bar.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.programming_progress_bar.hide()

        self.testing_progress_bar = QProgressBar()
        self.testing_progress_bar.setRange(0, 100)
        self.testing_progress_bar.setTextVisible(True)
        self.testing_progress_bar.setFormat("Тестирование: %p%")
        self.testing_progress_bar.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.testing_progress_bar.hide()

        self.current_process_label = QLabel()
        self.current_process_label.setAlignment(Qt.AlignCenter)
        self.current_process_label.setStyleSheet(
            "color: #50fa7b; font-weight: 500; padding: 4px;"
        )

        progress_container = QVBoxLayout()
        progress_container.addWidget(self.current_process_label)
        progress_container.addWidget(self.programming_progress_bar)
        progress_container.addWidget(self.testing_progress_bar)
        layout.addLayout(progress_container)

        info_label = QLabel(f"Логи записываются в: {self.log_file}")
        info_label.setProperty("info", True)
        layout.addWidget(info_label)

        widget.setLayout(layout)
        return widget

    def on_programming_port_changed(self, index):
        if index >= 0:
            port = self.combobox_ports.currentData()
            if port:
                self.serial_monitor.set_port(port)

    def on_serial_monitor_port_changed(self, port_name):
        for i in range(self.combobox_ports.count()):
            if self.combobox_ports.itemData(i) == port_name:
                self.combobox_ports.blockSignals(True)
                self.combobox_ports.setCurrentIndex(i)
                self.combobox_ports.blockSignals(False)
                break

    def refresh_devices(self):
        self.combobox_devices.clear()
        try:
            self.devices = self.programmer.find_devices()
            for idx, device in enumerate(self.devices):
                device_text = device.get("name", f"Устройство {idx + 1}")
                self.combobox_devices.addItem(device_text, idx + 1)

            if self.devices:
                self.log(
                    f"Найдено STM32 устройств: {len(self.devices)}", msg_type="info"
                )
            else:
                self.log("STM32 устройства не найдены", msg_type="error")
        except Exception as e:
            self.log(f"Ошибка при обновлении устройств: {e}", msg_type="error")

    def on_device_selected(self, index):
        if index == -1:
            return
        if self.combobox_devices.signalsBlocked():
            logger.debug("Сигналы заблокированы, пропускаем on_device_selected")
            return
        device_index = self.combobox_devices.currentData()
        if device_index is None or device_index < 1 or device_index > len(self.devices):
            return

        selected_device = self.devices[device_index - 1]

        self.refresh_ports(selected_device, restore_mode=False)

    def _get_device_id(self, device):
        if device.get("serial"):
            return f"serial:{device['serial']}"
        else:
            vid = device.get("vid", 0)
            pid = device.get("pid", 0)
            bus = device.get("usb_bus", 0)
            address = device.get("usb_address", 0)
            return f"vidpid:{vid:04X}:{pid:04X}:bus{bus}:addr{address}"

    def _save_device_port_mapping(self, device_id, port):
        key = f"device_port_mapping/{device_id}"
        self.settings.setValue(key, port)
        self.settings.sync()

    def _load_device_port_mapping(self, device_id):
        key = f"device_port_mapping/{device_id}"
        return self.settings.value(key, None)

    def _save_firmware_paths(self):
        if self.lv_file_path:
            self.settings.setValue("last_lv_firmware_file", self.lv_file_path)
            logger.debug(f"Сохранен путь LV прошивки: {self.lv_file_path}")
        else:
            self.settings.remove("last_lv_firmware_file")
            logger.debug("Удален сохраненный путь LV прошивки")

        if self.hv_file_path:
            self.settings.setValue("last_hv_firmware_file", self.hv_file_path)
            logger.debug(f"Сохранен путь HV прошивки: {self.hv_file_path}")
        else:
            self.settings.remove("last_hv_firmware_file")
            logger.debug("Удален сохраненный путь HV прошивки")

        self.settings.sync()

    def _load_saved_firmware_paths(self):
        lv_path = self.settings.value("last_lv_firmware_file", "")
        logger.debug(f"Попытка загрузить сохраненный путь LV: {lv_path}")
        if lv_path:
            if Path(lv_path).exists():
                self.lv_file_path = lv_path
                self.btn_load_lv.setText(f"LV прошивка: {Path(lv_path).name}")
                is_valid, _ = self.validate_firmware_name(lv_path, "LV")
                self.btn_load_lv.set_validation_border(is_valid)
                self.log(
                    f"Загружен сохраненный путь LV прошивки: {Path(lv_path).name}",
                    msg_type="info",
                )
                logger.debug(f"Успешно загружен путь LV: {lv_path}")
            else:
                logger.warning(f"Сохраненный путь LV не существует: {lv_path}")
                self.settings.remove("last_lv_firmware_file")

        hv_path = self.settings.value("last_hv_firmware_file", "")
        logger.debug(f"Попытка загрузить сохраненный путь HV: {hv_path}")
        if hv_path:
            if Path(hv_path).exists():
                self.hv_file_path = hv_path
                self.btn_load_hv.setText(f"HV прошивка: {Path(hv_path).name}")
                is_valid, _ = self.validate_firmware_name(hv_path, "HV")
                self.btn_load_hv.set_validation_border(is_valid)
                self.log(
                    f"Загружен сохраненный путь HV прошивки: {Path(hv_path).name}",
                    msg_type="info",
                )
                logger.debug(f"Успешно загружен путь HV: {hv_path}")
            else:
                logger.warning(f"Сохраненный путь HV не существует: {hv_path}")
                self.settings.remove("last_hv_firmware_file")

        self.update_buttons_state()

    def closeEvent(self, event):
        logger.info("Сохранение состояния при закрытии приложения...")
        self._save_firmware_paths()
        self._save_last_device_and_port()

        if hasattr(self, "serial_monitor") and self.serial_monitor:
            try:
                if (
                    self.serial_monitor.serial_port
                    and self.serial_monitor.serial_port.is_open
                ):
                    logger.info("Закрытие Serial Monitor порта...")
                    self.serial_monitor.disconnect_port()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии Serial Monitor порта: {e}")

        if hasattr(self, "programmer") and self.programmer:

            if self.programmer.selected_uart:
                try:
                    if self.programmer.selected_uart.is_open:
                        logger.info("Выключение питания при закрытии приложения...")
                        from stm32_programmer.utils.uart_settings import UARTSettings

                        uart_settings = UARTSettings()
                        line_ending_bytes = uart_settings.get_line_ending_bytes()
                        command_off = (
                            "SET EN_12V=OFF".strip().encode("utf-8") + line_ending_bytes
                        )
                        try:
                            self.programmer.send_command_uart(
                                command_off, "EN_12V=OFF".strip().encode("utf-8")
                            )
                        except:

                            try:
                                self.programmer.selected_uart.write(command_off)
                                self.programmer.selected_uart.flush()
                                logger.info("Команда EN_12V=OFF отправлена напрямую")
                            except:
                                pass
                        import time

                        time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Ошибка при выключении питания при закрытии: {e}")
            self.programmer.close_uart()

        try:
            logger.info("Закрытие файлов логов...")
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                try:
                    handler.close()
                    root_logger.removeHandler(handler)
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии handler: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при закрытии логов: {e}")

        logger.info(
            "Состояние сохранено, питание выключено, UART закрыт, ресурсы освобождены"
        )
        event.accept()

    def _save_last_device_and_port(self):
        device_index = self.combobox_devices.currentIndex()
        logger.debug(f"Сохранение устройства: индекс в комбобоксе = {device_index}")
        if device_index >= 0:
            device_data = self.combobox_devices.currentData()
            logger.debug(f"Данные устройства: {device_data}")
            if device_data:
                self.settings.setValue("last_device_index", device_data)
                logger.info(f"Сохранен индекс устройства: {device_data}")
                if device_data > 0 and device_data <= len(self.devices):
                    device = self.devices[device_data - 1]
                    device_id = self._get_device_id(device)
                    self.settings.setValue("last_device_id", device_id)
                    logger.info(f"Сохранен идентификатор устройства: {device_id}")
                else:
                    logger.warning(
                        f"Индекс устройства {device_data} вне диапазона [1, {len(self.devices)}]"
                    )
        else:
            logger.debug("Устройство не выбрано (index = -1), не сохраняем")

        port_index = self.combobox_ports.currentIndex()
        logger.debug(f"Сохранение порта: индекс в комбобоксе = {port_index}")
        if port_index >= 0:
            port_data = self.combobox_ports.currentData()
            logger.debug(f"Данные порта: {port_data}")
            if port_data:
                self.settings.setValue("last_port", port_data)
                logger.info(f"Сохранен порт: {port_data}")
            else:
                logger.warning("Порт выбран, но данные порта отсутствуют")
        else:
            logger.debug("Порт не выбран (index = -1), не сохраняем")

        self.settings.sync()
        logger.debug("Настройки синхронизированы")

    def _on_device_changed(self, index):
        if not self.combobox_devices.signalsBlocked() and index >= 0:
            logger.debug(f"Изменен выбор устройства на индекс {index}")
            self._save_last_device_and_port()

    def _on_port_changed(self, index):
        if not self.combobox_ports.signalsBlocked() and index >= 0:
            logger.debug(f"Изменен выбор порта на индекс {index}")
            self._save_last_device_and_port()

    def _load_last_device_and_port(self):
        saved_port = self.settings.value("last_port", "")
        saved_device_id = self.settings.value("last_device_id", "")
        saved_device_index = self.settings.value("last_device_index", None, type=int)

        logger.info(
            f"Загрузка сохраненных значений: порт={saved_port}, device_id={saved_device_id}, device_index={saved_device_index}"
        )

        self._restore_logged = {"device": False, "port": False}

        self.combobox_devices.blockSignals(True)
        self.combobox_ports.blockSignals(True)

        try:
            device_restored = False
            restored_device = None
            restored_device_index = None

            if saved_device_id and self.devices:
                logger.debug(f"Поиск устройства по ID: {saved_device_id}")
                for idx, device in enumerate(self.devices):
                    device_id = self._get_device_id(device)
                    logger.debug(
                        f"Сравнение: сохраненный={saved_device_id}, текущий={device_id}"
                    )
                    if device_id == saved_device_id:
                        device_index = idx + 1
                        restored_device_index = device_index
                        logger.info(
                            f"Найдено устройство по ID, индекс в списке: {device_index}"
                        )
                        for i in range(self.combobox_devices.count()):
                            if self.combobox_devices.itemData(i) == device_index:
                                logger.info(
                                    f"Установка индекса комбобокса: {i} (device_index={device_index})"
                                )
                                self.combobox_devices.setCurrentIndex(i)
                                verify_index = self.combobox_devices.currentIndex()
                                verify_data = self.combobox_devices.currentData()
                                logger.info(
                                    f"Проверка после установки: индекс={verify_index}, данные={verify_data}"
                                )
                                if verify_index == i and verify_data == device_index:
                                    restored_device = device
                                    if not self._restore_logged["device"]:
                                        self.log(
                                            f"Восстановлено последнее выбранное устройство: {device.get('name', 'Unknown')}",
                                            msg_type="info",
                                        )
                                        logger.info(
                                            f"Устройство восстановлено: {device.get('name', 'Unknown')}"
                                        )
                                        self._restore_logged["device"] = True
                                    device_restored = True
                                else:
                                    logger.error(
                                        f"ОШИБКА: Индекс не установлен правильно! Ожидалось: {i}/{device_index}, получено: {verify_index}/{verify_data}"
                                    )
                                break
                        if device_restored:
                            break
            if not device_restored and saved_device_index and saved_device_index > 0:
                restored_device_index = saved_device_index
                logger.debug(f"Попытка восстановления по индексу: {saved_device_index}")
                for i in range(self.combobox_devices.count()):
                    if self.combobox_devices.itemData(i) == saved_device_index:
                        logger.info(
                            f"Установка индекса комбобокса по сохраненному индексу: {i} (saved_device_index={saved_device_index})"
                        )
                        self.combobox_devices.setCurrentIndex(i)
                        verify_index = self.combobox_devices.currentIndex()
                        verify_data = self.combobox_devices.currentData()
                        logger.info(
                            f"Проверка после установки: индекс={verify_index}, данные={verify_data}"
                        )
                        if (
                            verify_index == i
                            and verify_data == saved_device_index
                            and saved_device_index <= len(self.devices)
                        ):
                            restored_device = self.devices[saved_device_index - 1]
                            if not self._restore_logged["device"]:
                                self.log(
                                    f"Восстановлено последнее выбранное устройство (по индексу): {restored_device.get('name', 'Unknown')}",
                                    msg_type="info",
                                )
                                logger.info(
                                    f"Устройство восстановлено по индексу: {restored_device.get('name', 'Unknown')}"
                                )
                                self._restore_logged["device"] = True
                            device_restored = True
                        else:
                            logger.error(
                                f"ОШИБКА: Индекс не установлен правильно! Ожидалось: {i}/{saved_device_index}, получено: {verify_index}/{verify_data}"
                            )
                        break
            current_device_check = self.combobox_devices.currentIndex()
            logger.info(
                f"Перед обновлением портов: индекс устройства в комбобоксе = {current_device_check}, device_restored = {device_restored}"
            )

            if restored_device and device_restored:
                if current_device_check >= 0:
                    logger.info(
                        f"Обновление портов для восстановленного устройства: {restored_device.get('name', 'Unknown')}"
                    )
                    self.refresh_ports(restored_device, restore_mode=True)
                    after_refresh_index = self.combobox_devices.currentIndex()
                    if after_refresh_index != current_device_check:
                        logger.warning(
                            f"ВНИМАНИЕ: Индекс устройства изменился после refresh_ports: было {current_device_check}, стало {after_refresh_index}"
                        )
                        if restored_device_index:
                            for i in range(self.combobox_devices.count()):
                                if (
                                    self.combobox_devices.itemData(i)
                                    == restored_device_index
                                ):
                                    self.combobox_devices.setCurrentIndex(i)
                                    logger.info(
                                        f"Восстановление устройства после refresh_ports на индекс {i}"
                                    )
                                    break
                else:
                    logger.warning(
                        "Устройство было восстановлено, но индекс сброшен перед обновлением портов!"
                    )
                    if restored_device_index:
                        for i in range(self.combobox_devices.count()):
                            if (
                                self.combobox_devices.itemData(i)
                                == restored_device_index
                            ):
                                self.combobox_devices.setCurrentIndex(i)
                                logger.info(
                                    f"Повторное восстановление устройства на индекс {i}"
                                )
                                self.refresh_ports(restored_device, restore_mode=True)
                                break
            elif saved_port:
                logger.info(
                    "Устройство не восстановлено, но есть сохраненный порт, обновляем порты"
                )
                self.refresh_ports(None, restore_mode=True)
            if saved_port:
                port_found = False
                for i in range(self.combobox_ports.count()):
                    port_data = self.combobox_ports.itemData(i)
                    if port_data == saved_port:
                        self.combobox_ports.setCurrentIndex(i)
                        if not self._restore_logged["port"]:
                            self.log(
                                f"Восстановлен последний выбранный порт: {saved_port}",
                                msg_type="info",
                            )
                            logger.info(f"Порт {saved_port} успешно восстановлен")
                            self._restore_logged["port"] = True
                        port_found = True
                        break
                if not port_found:
                    logger.warning(
                        f"Сохраненный порт {saved_port} не найден в списке доступных портов"
                    )
            else:
                logger.debug("Сохраненный порт отсутствует")
        finally:
            final_device_index = self.combobox_devices.currentIndex()
            final_device_data = self.combobox_devices.currentData()
            final_port_index = self.combobox_ports.currentIndex()
            final_port_data = self.combobox_ports.currentData()
            logger.info(
                f"Перед разблокировкой сигналов: устройство индекс={final_device_index} (данные={final_device_data}), порт индекс={final_port_index} (данные={final_port_data})"
            )
            self.combobox_devices.blockSignals(False)
            self.combobox_ports.blockSignals(False)
            logger.debug("Сигналы комбобоксов разблокированы")
            after_device_index = self.combobox_devices.currentIndex()
            after_device_data = self.combobox_devices.currentData()
            after_port_index = self.combobox_ports.currentIndex()
            after_port_data = self.combobox_ports.currentData()
            if (
                after_device_index != final_device_index
                or after_device_data != final_device_data
            ):
                logger.warning(
                    f"ВНИМАНИЕ: Индекс устройства изменился после разблокировки: было {final_device_index}/{final_device_data}, стало {after_device_index}/{after_device_data}"
                )
                if restored_device_index and final_device_index >= 0:
                    for i in range(self.combobox_devices.count()):
                        if self.combobox_devices.itemData(i) == restored_device_index:
                            self.combobox_devices.setCurrentIndex(i)
                            logger.info(
                                f"Восстановление устройства после разблокировки на индекс {i}"
                            )
                            break
            else:
                logger.info(
                    f"Устройство успешно восстановлено и осталось выбранным: индекс={after_device_index}, данные={after_device_data}"
                )
            if (
                after_port_index != final_port_index
                or after_port_data != final_port_data
            ):
                logger.warning(
                    f"ВНИМАНИЕ: Индекс порта изменился после разблокировки: было {final_port_index}/{final_port_data}, стало {after_port_index}/{after_port_data}"
                )
                if saved_port and final_port_index >= 0:
                    for i in range(self.combobox_ports.count()):
                        if self.combobox_ports.itemData(i) == saved_port:
                            self.combobox_ports.setCurrentIndex(i)
                            logger.info(
                                f"Восстановление порта после разблокировки на индекс {i}"
                            )
                            break
            else:
                logger.info(
                    f"Порт успешно восстановлен и остался выбранным: индекс={after_port_index}, данные={after_port_data}"
                )

    def refresh_ports(self, selected_device=None, restore_mode=False):
        self.combobox_ports.clear()
        try:
            from stm32_programmer.programmers.core import detect_serial_port

            ports = list(serial.tools.list_ports.comports())

            TARGET_UART_VID = 0x1A86
            TARGET_UART_PID = 0x7523

            def is_target_uart(port):
                if port.vid is not None and port.pid is not None:
                    return port.vid == TARGET_UART_VID and port.pid == TARGET_UART_PID
                hwid = (port.hwid or "").upper()
                signature = f"VID:PID={TARGET_UART_VID:04X}:{TARGET_UART_PID:04X}"
                return signature in hwid

            matching_ports = [p for p in ports if is_target_uart(p)]

            linked_port = None
            saved_port = None

            if selected_device:
                device_id = self._get_device_id(selected_device)
                saved_port = self._load_device_port_mapping(device_id)
                try:
                    linked_port = detect_serial_port(selected_device)
                except Exception as e:
                    self.log(
                        f"Не удалось найти связанный порт: {e}", msg_type="warning"
                    )

            linked_port_index = -1
            saved_port_index = -1

            for idx, port in enumerate(matching_ports):
                port_text = port.device
                if port.description:
                    port_text = f"{port.device} - {port.description}"
                if linked_port and port.device == linked_port:
                    port_text = f"{port_text} (связан с выбранным ST-Link)"
                    linked_port_index = idx
                elif saved_port and port.device == saved_port:
                    port_text = f"💾 {port_text} (сохраненное сопоставление)"
                    saved_port_index = idx

                self.combobox_ports.addItem(port_text, port.device)

            last_port = self.settings.value("last_port", "")
            last_port_index = -1
            if last_port:
                for idx, port in enumerate(matching_ports):
                    if port.device == last_port:
                        last_port_index = idx
                        break

            if last_port_index >= 0:
                self.combobox_ports.setCurrentIndex(last_port_index)
                if not hasattr(self, "_restore_logged") or not self._restore_logged.get(
                    "port", False
                ):
                    self.log(
                        f"Восстановлен последний выбранный UART порт: {last_port}",
                        msg_type="info",
                    )
                    if not hasattr(self, "_restore_logged"):
                        self._restore_logged = {"device": False, "port": False}
                    self._restore_logged["port"] = True
            elif not restore_mode:
                if linked_port_index >= 0:
                    self.combobox_ports.setCurrentIndex(linked_port_index)
                    self.log(
                        f"Автоматически выбран связанный UART порт: {linked_port}",
                        msg_type="info",
                    )
                elif saved_port_index >= 0:
                    self.combobox_ports.setCurrentIndex(saved_port_index)
                    self.log(
                        f"Автоматически выбран сохраненный UART порт: {saved_port}",
                        msg_type="info",
                    )
                elif (
                    linked_port is None and selected_device and len(matching_ports) > 1
                ):
                    self.log(
                        f"Обнаружено несколько UART портов. Не удалось автоматически определить связанный порт для выбранного ST-Link устройства. Выберите порт вручную.",
                        msg_type="warning",
                    )
                elif (
                    linked_port is None and selected_device and len(matching_ports) == 1
                ):
                    self.combobox_ports.setCurrentIndex(0)
                    self.log(
                        f"Выбран единственный доступный UART порт: {matching_ports[0].device}",
                        msg_type="info",
                    )

            if matching_ports:
                self.log(
                    f"Найдено целевых портов (VID=0x{TARGET_UART_VID:04X}, PID=0x{TARGET_UART_PID:04X}): {len(matching_ports)}",
                    msg_type="info",
                )
            else:
                self.log(
                    f"Целевые порты (VID=0x{TARGET_UART_VID:04X}, PID=0x{TARGET_UART_PID:04X}) не найдены",
                    msg_type="error",
                )
        except Exception as e:
            self.log(f"Ошибка при обновлении портов: {e}", msg_type="error")

    def validate_firmware_name(self, file_path, mode):
        file_name = Path(file_path).name.lower()

        if mode == "LV":
            expected_keyword = "master"
            if expected_keyword not in file_name:
                return (
                    False,
                    f"⚠️ Предупреждение: Для LV режима ожидается прошивка с 'master' в названии, но выбран файл '{Path(file_path).name}'",
                )
        elif mode == "HV":
            expected_keyword = "slave"
            if expected_keyword not in file_name:
                return (
                    False,
                    f"⚠️ Предупреждение: Для HV режима ожидается прошивка с 'slave' в названии, но выбран файл '{Path(file_path).name}'",
                )

        return True, None

    def get_last_firmware_directory(self, mode):
        last_path = self.settings.value(f"last_{mode}_path", "")
        if last_path:
            try:
                parent_dir = Path(last_path).parent
                if parent_dir.exists():
                    return str(parent_dir)
            except Exception:
                pass

        most_common_dir = self.settings.value("most_common_firmware_dir", "")
        if most_common_dir:
            try:
                if Path(most_common_dir).exists():
                    return most_common_dir
            except Exception:
                pass

        return ""

    def save_firmware_path(self, path, mode):
        if path:
            self.settings.setValue(f"last_{mode}_path", path)
            dir_path = str(Path(path).parent)
            current_count = self.settings.value(f"dir_count_{dir_path}", 0, type=int)
            self.settings.setValue(f"dir_count_{dir_path}", current_count + 1)
            all_keys = self.settings.allKeys()
            dir_counts = {}
            for key in all_keys:
                if key.startswith("dir_count_"):
                    dir_path_key = key.replace("dir_count_", "")
                    count = self.settings.value(key, 0, type=int)
                    dir_counts[dir_path_key] = count

            if dir_counts:
                most_common = max(dir_counts.items(), key=lambda x: x[1])
                self.settings.setValue("most_common_firmware_dir", most_common[0])

    def load_firmware(self, mode):
        last_dir = self.get_last_firmware_directory(mode)
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Выберите {mode} прошивку",
            last_dir,
            "HEX Files (*.hex);;All Files (*)",
        )
        if path:
            is_valid, warning_msg = self.validate_firmware_name(path, mode)
            if not is_valid and warning_msg:
                self.log(warning_msg, msg_type="warning")
                self.show_message_box(
                    "Предупреждение о названии файла", warning_msg, QMessageBox.Warning
                )
            self.save_firmware_path(path, mode)
            if mode == "LV":
                self.lv_file_path = path
                self.btn_load_lv.setText(f"LV прошивка: {Path(path).name}")
                self.btn_load_lv.set_validation_border(is_valid)
            else:
                self.hv_file_path = path
                self.btn_load_hv.setText(f"HV прошивка: {Path(path).name}")
                self.btn_load_hv.set_validation_border(is_valid)
            self._save_firmware_paths()

            self.log(f"Файл {mode} прошивки выбран: {path}")
            logger.info(f"Сохранен путь к файлу {mode} прошивки: {path}")
            self.update_buttons_state()

    def clear_firmware(self, mode):
        if mode == "LV":
            self.lv_file_path = ""
            self.btn_load_lv.setText("Загрузить LV прошивку")
            self.btn_load_lv.set_validation_border(None)
        else:
            self.hv_file_path = ""
            self.btn_load_hv.setText("Загрузить HV прошивку")
            self.btn_load_hv.set_validation_border(None)
        self._save_firmware_paths()

        self.update_buttons_state()
        self.log(f"Очищен файл {mode} прошивки", msg_type="info")

    def clear_files(self):
        self.console.clear()
        self.log("Логи очищены", msg_type="info")

    def update_buttons_state(self):
        has_files = bool(self.lv_file_path or self.hv_file_path)
        self.btn_program.setEnabled(has_files or self.is_programming)
        if self.is_programming:
            self.btn_program.setText("■")
            self.btn_program.setToolTip("Остановить программирование")
        else:
            self.btn_program.setText("▶")
            self.btn_program.setToolTip("Прошить микроконтроллер")
        is_enabled = not self.is_programming
        self.combobox_devices.setEnabled(is_enabled)
        self.combobox_ports.setEnabled(is_enabled)
        self.btn_load_lv.setEnabled(is_enabled)
        self.btn_load_hv.setEnabled(is_enabled)
        self.btn_refresh_devices.setEnabled(is_enabled)
        self.btn_refresh_ports.setEnabled(is_enabled)

    def log(self, message, msg_type="info"):
        if not hasattr(self, "console") or self.console is None:
            return

        dt = QDateTime.currentDateTime()
        h = str(dt.time().hour()).zfill(2)
        m = str(dt.time().minute()).zfill(2)
        s = str(dt.time().second()).zfill(2)
        ms = str(dt.time().msec()).zfill(3)
        timestamp = f"[{h}:{m}:{s}.{ms}]"
        if not message.startswith("["):
            message = f"{timestamp} {message}"
        message = html.escape(message)
        if msg_type == "error":
            color = "#ff5555"
        elif msg_type == "warning":
            color = "#ffaa00"
        elif msg_type == "command":
            color = "#50fa7b"
        elif msg_type == "response":
            color = "#8be9fd"
        else:
            color = "#e0e0e0"

        self.console.append(f'<span style="color:{color}">{message}</span>')
        self.console.moveCursor(self.console.textCursor().End)

    def toggle_programming(self):
        if self.is_programming:
            self.stop_programming()
        else:
            self.start_programming()

    def stop_programming(self):
        if not self.is_programming or not self.programming_thread:
            return
        self.is_stopping = True
        self.current_process_label.setText("Остановка...")
        self.current_process_label.setStyleSheet(
            "color: #ffb86c; font-weight: 500; padding: 4px;"
        )
        self.current_process_label.show()
        self.current_process_label.update()
        QApplication.processEvents()
        QApplication.processEvents()
        if self.programming_thread:
            try:
                self.programming_thread.progress_updated.disconnect()
                self.programming_thread.status_updated.disconnect()
                self.programming_thread.progress_percent_updated.disconnect()
            except:
                pass
        self.log("Остановка программирования...", msg_type="warning")
        if self.programming_thread.isRunning():
            self.programming_thread.request_stop()
            if not self.programming_thread.wait(1000):
                self.log("Принудительное завершение потока...", msg_type="warning")
                self.programming_thread.terminate()
                self.programming_thread.wait()
                self.on_programming_finished(False, "Остановлено пользователем")

    def start_programming(self):
        if self.is_programming:
            self.show_message_box(
                "Предупреждение",
                "Программирование уже выполняется",
                QMessageBox.Warning,
            )
            return

        if not self.lv_file_path and not self.hv_file_path:
            self.show_message_box(
                "Ошибка", "Выберите хотя бы один файл прошивки", QMessageBox.Critical
            )
            return

        for path, mode in [(self.lv_file_path, "LV"), (self.hv_file_path, "HV")]:
            if path and not Path(path).exists():
                self.show_message_box(
                    "Ошибка",
                    f"Файл {mode} прошивки не найден: {path}",
                    QMessageBox.Critical,
                )
                return

        if self.combobox_devices.currentIndex() == -1:
            self.show_message_box(
                "Ошибка", "Выберите STM32 устройство", QMessageBox.Critical
            )
            return
        if self.combobox_ports.currentIndex() == -1:
            self.show_message_box("Ошибка", "Выберите COM-порт", QMessageBox.Critical)
            return
        device_index = self.combobox_devices.currentData()
        if device_index is None:
            self.show_message_box(
                "Ошибка",
                "Не удалось определить выбранное устройство",
                QMessageBox.Critical,
            )
            return
        selected_port = self.combobox_ports.currentData()
        if not selected_port:
            selected_port = self.combobox_ports.currentText().split(" - ")[0]
        selected_device = (
            self.devices[device_index - 1]
            if device_index > 0 and device_index <= len(self.devices)
            else None
        )
        if selected_device:
            self.current_device_id = self._get_device_id(selected_device)
            self.current_port = selected_port
        has_lv = bool(self.lv_file_path)
        has_hv = bool(self.hv_file_path)

        if has_lv and not has_hv:
            reply = self.show_message_box(
                "Предупреждение",
                "Выбран только файл LV прошивки.\n\nБудет прошито только LV (master).\n\nПродолжить?",
                QMessageBox.Warning,
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return
        elif has_hv and not has_lv:
            reply = self.show_message_box(
                "Предупреждение",
                "Выбран только файл HV прошивки.\n\nБудет прошито только HV (slave).\n\nПродолжить?",
                QMessageBox.Warning,
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return

        self.lv_status = None
        self.hv_status = None
        self.is_programming = True
        self.is_stopping = False
        self.update_buttons_state()
        QApplication.processEvents()
        self.console.clear()
        self.log("Начало программирования...", msg_type="info")
        self.programming_progress_bar.show()
        self.programming_progress_bar.setValue(0)
        self.testing_progress_bar.hide()
        self.testing_progress_bar.setValue(0)
        self.current_process_label.setText("Программирование...")
        self.current_process_label.setStyleSheet(
            "color: #50fa7b; font-weight: 500; padding: 4px;"
        )
        self.current_process_label.show()
        self.programming_thread = ProgrammingThread(
            self.lv_file_path if self.lv_file_path else None,
            self.hv_file_path if self.hv_file_path else None,
            selected_port,
            device_index,
        )
        self.programming_thread.finished.connect(self.on_programming_finished)
        self.programming_thread.progress_updated.connect(self.on_progress_updated)
        self.programming_thread.status_updated.connect(self.on_status_updated)
        self.programming_thread.progress_percent_updated.connect(
            self.on_progress_percent_updated
        )
        self.programming_thread.programming_progress_updated.connect(
            self.on_programming_progress_updated
        )
        self.programming_thread.testing_progress_updated.connect(
            self.on_testing_progress_updated
        )
        self.programming_thread.start()

    def on_progress_updated(self, message):
        if self.is_stopping:
            self.current_process_label.setText("Остановка...")
            self.current_process_label.setStyleSheet(
                "color: #ffb86c; font-weight: 500; padding: 4px;"
            )
            return
        if message.startswith("->>"):
            self.log(message, msg_type="command")
        elif message.startswith("<<-"):
            self.log(message, msg_type="response")
        else:
            self.log(message, msg_type="info")

    def on_status_updated(self, message):
        msg_type = (
            "error"
            if "ошибка" in message.lower() or "error" in message.lower()
            else "info"
        )
        self.log(message, msg_type=msg_type)
        message_upper = message.upper()

        if "ТЕСТИРОВАНИЕ" in message_upper or message == "Тестирование...":
            self.current_process_label.setText("Тестирование...")
            self.current_process_label.setStyleSheet(
                "color: #ffb86c; font-weight: 500; padding: 4px;"
            )
            self.current_process_label.show()

        if "LV" in message_upper and "ЗАПИСАН" in message_upper:
            self.lv_status = True
        elif "HV" in message_upper and "ЗАПИСАН" in message_upper:
            self.hv_status = True
        elif "LV" in message_upper and (
            "ОШИБКА" in message_upper or "ERROR" in message_upper
        ):
            self.lv_status = False
        elif "HV" in message_upper and (
            "ОШИБКА" in message_upper or "ERROR" in message_upper
        ):
            self.hv_status = False

    def on_progress_percent_updated(self, percent):

        pass

    def on_programming_progress_updated(self, percent):
        if self.is_stopping:
            return
        if 0 <= percent <= 100:
            self.programming_progress_bar.setValue(percent)

    def on_testing_progress_updated(self, percent):
        if self.is_stopping:
            return
        if 0 <= percent <= 100:

            if not self.testing_progress_bar.isVisible():
                self.testing_progress_bar.show()
            self.testing_progress_bar.setValue(percent)

    def show_stop_status_dialog(self):
        status_lines = []
        if self.lv_file_path:
            if self.lv_status is True:
                status_lines.append("LV (master): Успешно записано и проверено")
            elif self.lv_status is False:
                status_lines.append("LV (master): Ошибка при записи")
            else:
                status_lines.append("LV (master): Не завершено (остановлено)")
        if self.hv_file_path:
            if self.hv_status is True:
                status_lines.append("HV (slave): Успешно записано и проверено")
            elif self.hv_status is False:
                status_lines.append("HV (slave): Ошибка при записи")
            else:
                status_lines.append("HV (slave): Не завершено (остановлено)")

        if status_lines:
            status_text = "\n".join(status_lines)
            self.show_message_box(
                "Программирование остановлено",
                f"Программирование было остановлено пользователем.\n\nСтатус:\n{status_text}",
                QMessageBox.Warning,
            )

    def on_programming_finished(self, success, message):
        self.is_programming = False
        self.is_stopping = False
        self.update_buttons_state()
        self.programming_progress_bar.hide()
        self.testing_progress_bar.hide()
        self.current_process_label.hide()

        if success:
            self.log("Программирование завершено успешно", msg_type="command")
            self.show_message_box(
                "Успех", "Прошивка записана успешно!", QMessageBox.Information
            )
            if self.current_device_id and self.current_port:
                self._save_device_port_mapping(
                    self.current_device_id, self.current_port
                )
                self.log(
                    f"Сохранено сопоставление: устройство {self.current_device_id} -> порт {self.current_port}",
                    msg_type="info",
                )
        else:
            self.log(f"Ошибка: {message}", msg_type="error")
            if (
                "Остановлено пользователем" in message
                or "остановлено" in message.lower()
            ):
                self.show_stop_status_dialog()
            elif (
                "ОШИБКА: Тестирование не пройдено" in message
                or "Тестирование не пройдено" in message
            ):
                result = self.show_message_box(
                    "Ошибка тестирования",
                    f"Прошивка записана, но тестирование не пройдено!\n\n{message}",
                    QMessageBox.Critical,
                )

                if result == QMessageBox.Ok:
                    self._turn_off_led()
            else:

                error_details = message
                if (
                    "I/O operation on closed file" in message
                    or "operation on closed" in message.lower()
                ):
                    error_details = (
                        "КРИТИЧЕСКАЯ ОШИБКА: I/O operation on closed file\n\n"
                        "Не удалось записать прошивку из-за закрытого файла/устройства.\n\n"
                        "Возможные причины:\n"
                        "  • USB устройство было закрыто другим процессом (STM32CubeProgrammer) 🤔\n"
                        "  • Устройство было отключено во время записи\n"
                        "  • USB интерфейс был закрыт\n\n"
                        "Решение:\n"
                        "  1. Закройте STM32CubeProgrammer, если он открыт\n"
                        "  2. Проверьте USB соединение\n"
                        "  3. Переподключите устройство\n"
                        "  4. Перезапустите программу\n\n"
                        f"Детали ошибки:\n{message}"
                    )
                elif "не удалось подключиться к целевому устройству" in message.lower():
                    error_details = (
                        "ОШИБКА: Не удалось подключиться к целевому устройству\n\n"
                        f"{message}\n\n"
                        "Проверьте:\n"
                        "  • Устройство подключено и включено\n"
                        "  • STM32CubeProgrammer закрыт 🤔\n"
                        "  • Драйверы ST-Link установлены правильно"
                    )
                else:
                    error_details = (
                        f"Ошибка записи прошивки:\n\n{message}\n\n"
                        "Проверьте логи для подробной информации."
                    )

                result = self.show_message_box(
                    "Ошибка",
                    error_details,
                    QMessageBox.Critical,
                )

                if result == QMessageBox.Ok:
                    self._turn_off_led()

        # Системная перезагрузка UART порта после завершения прошивки
        if self.current_port:
            try:
                from stm32_programmer.programmers.base import reset_uart_system_level

                self.log("Системная перезагрузка UART порта...", msg_type="info")
                reset_uart_system_level(self.current_port)
                self.log("UART порт перезагружен на системном уровне", msg_type="info")
            except Exception as e:
                logger.warning(f"Ошибка при системной перезагрузке порта: {e}")

        self.current_device_id = None
        self.current_port = None

    def _turn_off_led(self):
        """Выключает светодиод LED4 после ошибки"""
        try:
            if (
                self.programmer
                and self.programmer.selected_uart
                and self.programmer.selected_uart.is_open
            ):
                from stm32_programmer.utils.uart_settings import UARTSettings

                uart_settings = UARTSettings()
                line_ending_bytes = uart_settings.get_line_ending_bytes()

                self.log("->> SET LED4=OFF", msg_type="command")
                led_off_command = (
                    "SET LED4=OFF".strip().encode("utf-8") + line_ending_bytes
                )
                success = self.programmer.send_command_uart(
                    led_off_command, "LED4=OFF".strip().encode("utf-8")
                )
                if success:
                    self.log("<<- LED4=OFF", msg_type="response")
                else:
                    self.log("Не получен ответ на команду LED4=OFF", msg_type="warning")
        except Exception as e:
            self.log(f"Ошибка при выключении светодиода: {e}", msg_type="error")

    def open_log_file(self):
        import os
        import subprocess
        import platform

        log_path = Path(self.log_file)
        if log_path.exists():
            if platform.system() == "Windows":
                os.startfile(log_path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", log_path])
            else:
                subprocess.call(["xdg-open", log_path])
        else:
            self.show_message_box(
                "Предупреждение", "Лог файл не найден", QMessageBox.Warning
            )

    def toggle_theme(self):
        if self.current_theme == "dark":
            self.current_theme = "light"
            self.btn_theme.setText("☾")
        else:
            self.current_theme = "dark"
            self.btn_theme.setText("☀")

        self.apply_theme(self.current_theme)
        self.settings.setValue("theme", self.current_theme)
        self.settings.sync()

    def apply_theme(self, theme):
        stylesheet = get_stylesheet(theme)
        self.setStyleSheet(stylesheet)
        if hasattr(self, "serial_monitor"):
            self.serial_monitor.setStyleSheet(stylesheet)

        # Применяем стили к прогресс-барам в зависимости от темы
        if theme == "dark":
            border_color = "#44475a"
            text_color = "#f8f8f2"
        else:
            border_color = "#cbd5e0"
            text_color = "#2d2d2d"

        if hasattr(self, "programming_progress_bar"):
            self.programming_progress_bar.setStyleSheet(
                f"""
                QProgressBar {{
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    text-align: center;
                    color: {text_color};
                    font-weight: 500;
                    font-size: 12pt;
                    height: 28px;
                }}
                QProgressBar::chunk {{
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 #50fa7b, stop: 1 #5af78e);
                    border-radius: 5px;
                }}
            """
            )

        if hasattr(self, "testing_progress_bar"):
            self.testing_progress_bar.setStyleSheet(
                f"""
                QProgressBar {{
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    text-align: center;
                    color: {text_color};
                    font-weight: 500;
                    font-size: 12pt;
                    height: 28px;
                }}
                QProgressBar::chunk {{
                    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 #ffb86c, stop: 1 #ffaa00);
                    border-radius: 5px;
                }}
            """
            )
