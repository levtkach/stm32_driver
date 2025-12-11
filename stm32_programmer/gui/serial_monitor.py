import serial
import serial.tools.list_ports
import time
import threading
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QComboBox,
    QLineEdit,
    QFrame,
    QDialog,
    QFormLayout,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QDateTime
from PyQt5.QtGui import QFont, QTextCursor, QKeyEvent
import html
import logging

from stm32_programmer.utils.uart_commands import get_command_structure, build_command
from stm32_programmer.utils.uart_settings import UARTSettings

logger = logging.getLogger(__name__)


class CommandInputLineEdit(QLineEdit):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.command_history = []
        self.history_index = -1
        self.current_input_before_history = ""
        self.on_send_command = None

    def set_command_history(self, history):
        self.command_history = history

    def set_send_callback(self, callback):
        self.on_send_command = callback

    def add_to_history(self, command):
        if command and (
            not self.command_history or self.command_history[-1] != command
        ):
            self.command_history.append(command)
            if len(self.command_history) > 100:
                self.command_history.pop(0)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Up:
            if self.command_history:
                if self.history_index == -1:
                    self.current_input_before_history = self.text()
                    self.history_index = len(self.command_history) - 1
                elif self.history_index > 0:
                    self.history_index -= 1

                if 0 <= self.history_index < len(self.command_history):
                    self.setText(self.command_history[self.history_index])
            event.accept()
            return
        elif event.key() == Qt.Key_Down:
            if self.history_index >= 0:
                if self.history_index < len(self.command_history) - 1:
                    self.history_index += 1
                    self.setText(self.command_history[self.history_index])
                else:
                    self.history_index = -1
                    self.setText(self.current_input_before_history)
            event.accept()
            return
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self.on_send_command:
                self.on_send_command()
            event.accept()
            return
        else:
            super().keyPressEvent(event)
            if self.history_index >= 0 and event.key() not in (
                Qt.Key_Shift,
                Qt.Key_Control,
                Qt.Key_Alt,
                Qt.Key_Meta,
            ):
                self.history_index = -1
                self.current_input_before_history = ""

    def reset_history_navigation(self):
        self.history_index = -1
        self.current_input_before_history = ""


class UARTSettingsDialog(QDialog):

    def __init__(self, parent=None, current_baud_rate=115200, current_line_ending="LF"):
        super().__init__(parent)
        self.setWindowTitle("Настройки UART")
        self.setMinimumWidth(400)

        layout = QFormLayout()

        self.baud_rate_combo = QComboBox()
        popular_baud_rates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        for rate in popular_baud_rates:
            self.baud_rate_combo.addItem(str(rate), rate)
        index = self.baud_rate_combo.findData(current_baud_rate)
        if index >= 0:
            self.baud_rate_combo.setCurrentIndex(index)
        else:
            self.baud_rate_combo.insertItem(
                0, str(current_baud_rate), current_baud_rate
            )
            self.baud_rate_combo.setCurrentIndex(0)
        layout.addRow("Baud Rate:", self.baud_rate_combo)

        self.line_ending_combo = QComboBox()
        self.line_ending_combo.addItems(["LF", "CR", "CRLF"])
        self.line_ending_combo.setCurrentText(current_line_ending)
        layout.addRow("Line Ending:", self.line_ending_combo)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("ОК")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addRow(button_layout)
        self.setLayout(layout)

    def get_settings(self):
        return {
            "baud_rate": self.baud_rate_combo.currentData(),
            "line_ending": self.line_ending_combo.currentText(),
        }


class SerialMonitorWidget(QWidget):

    port_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_port = None
        self.is_connected = False
        self.read_thread = None
        self.stop_reading = False
        self.uart_settings = UARTSettings()

        self.current_baud_rate = self.uart_settings.get_baud_rate()
        self.current_line_ending = self.uart_settings.get_line_ending()

        self.command_structure = get_command_structure()

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

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
        self.combobox_ports.currentTextChanged.connect(
            lambda text: self.combobox_ports.setToolTip(text)
        )
        port_container_layout.addWidget(self.combobox_ports, 1)

        from .icon_manager import IconManager

        theme = None
        parent = self.parent()
        if parent and hasattr(parent, "current_theme"):
            theme = parent.current_theme
        else:
            theme = "dark"

        self.icon_manager = IconManager(theme)
        self.btn_refresh = QPushButton()
        self.icon_manager.update_refresh_icon(self.btn_refresh)
        self.btn_refresh.setProperty("refreshButton", True)
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Обновить список портов")
        self.btn_refresh.clicked.connect(self.refresh_ports)
        port_container_layout.addWidget(self.btn_refresh)

        port_container.setLayout(port_container_layout)
        port_layout.addWidget(port_container, 1)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setProperty("iconButton", True)
        self.btn_settings.setFixedSize(28, 28)
        self.btn_settings.setToolTip("Настройки UART")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.show_settings_dialog)
        port_layout.addWidget(self.btn_settings)

        self.btn_start_stop = QPushButton()
        self.icon_manager.update_play_icon(self.btn_start_stop, self.is_connected)
        self.btn_start_stop.setProperty("programButton", True)
        self.btn_start_stop.setFixedSize(28, 28)
        self.btn_start_stop.setToolTip(
            "Начать мониторинг" if not self.is_connected else "Остановить мониторинг"
        )
        self.btn_start_stop.setCursor(Qt.PointingHandCursor)
        self.btn_start_stop.clicked.connect(self.toggle_connection)
        port_layout.addWidget(self.btn_start_stop)

        self.btn_clear = QPushButton()
        self.icon_manager.update_cross_icon(self.btn_clear)
        self.btn_clear.setProperty("iconButton", True)
        self.btn_clear.setFixedSize(28, 28)
        self.btn_clear.setToolTip("Очистить логи")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        port_layout.addWidget(self.btn_clear)

        layout.addLayout(port_layout)

        terminal_container = QWidget()
        terminal_layout = QVBoxLayout()
        terminal_layout.setSpacing(0)
        terminal_layout.setContentsMargins(0, 0, 0, 0)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        font = self.console.font()
        font.setFamily("JetBrains Mono")
        font.setPointSize(11)
        font.setStyleHint(font.Monospace)
        font.setFixedPitch(True)
        self.console.setFont(font)
        terminal_layout.addWidget(self.console, 1)

        self.btn_clear.clicked.connect(self.console.clear)

        input_container = QFrame()
        input_container.setProperty("inputContainer", True)
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(8, 4, 8, 4)
        input_layout.setSpacing(8)

        prompt_label = QLabel(">")
        prompt_label.setProperty("info", True)
        font = prompt_label.font()
        font.setFamily("JetBrains Mono")
        font.setPointSize(11)
        prompt_label.setFont(font)
        input_layout.addWidget(prompt_label)

        self.manual_input = CommandInputLineEdit()
        self.manual_input.setPlaceholderText("Введите команду...")
        self.manual_input.setMinimumHeight(28)
        self.manual_input.set_send_callback(self.send_manual_command)
        input_layout.addWidget(self.manual_input, 1)

        input_container.setLayout(input_layout)
        terminal_layout.addWidget(input_container)

        terminal_container.setLayout(terminal_layout)
        layout.addWidget(terminal_container, 1)

        self.settings_label = QLabel(
            f"Baud: {self.current_baud_rate} | Line: {self.current_line_ending}"
        )
        self.settings_label.setProperty("info", True)
        layout.addWidget(self.settings_label)

        self.setLayout(layout)

        self.refresh_ports()

    def refresh_ports(self):
        self.combobox_ports.clear()
        try:
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

            for port in matching_ports:
                port_text = port.device
                if port.description:
                    port_text = f"{port.device} - {port.description}"
                self.combobox_ports.addItem(port_text, port.device)

            if matching_ports:
                self.log(f"Найдено портов: {len(matching_ports)}", msg_type="info")
            else:
                self.log("Порты не найдены", msg_type="warning")
        except Exception as e:
            self.log(f"Ошибка при обновлении портов: {e}", msg_type="error")

    def set_port(self, port_name):
        for i in range(self.combobox_ports.count()):
            if self.combobox_ports.itemData(i) == port_name:
                self.combobox_ports.setCurrentIndex(i)
                break

    def get_port(self):
        if self.combobox_ports.currentIndex() >= 0:
            return self.combobox_ports.currentData()
        return None

    def show_settings_dialog(self):
        dialog = UARTSettingsDialog(
            self,
            current_baud_rate=self.current_baud_rate,
            current_line_ending=self.current_line_ending,
        )

        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.current_baud_rate = settings["baud_rate"]
            self.current_line_ending = settings["line_ending"]

            self.uart_settings.set_baud_rate(self.current_baud_rate)
            self.uart_settings.set_line_ending(self.current_line_ending)

            self.settings_label.setText(
                f"Baud: {self.current_baud_rate} | Line: {self.current_line_ending}"
            )

            if self.is_connected:
                self.disconnect_port()
                self.connect_port()

            self.log(
                f"Настройки обновлены: Baud={self.current_baud_rate}, Line={self.current_line_ending}",
                msg_type="info",
            )

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect_port()
        else:
            self.connect_port()

    def connect_port(self):
        port_name = self.get_port()
        if not port_name:
            self.log("Выберите порт", msg_type="error")
            return

        try:
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=self.current_baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )

            self.serial_port.dtr = False
            self.serial_port.rts = False

            if self.serial_port.is_open:
                self.is_connected = True
                self.icon_manager.update_play_icon(
                    self.btn_start_stop, self.is_connected
                )
                self.btn_start_stop.setToolTip("Остановить мониторинг")
                self.log(f"Подключено к {port_name}", msg_type="info")

                self.stop_reading = False
                self.read_thread = threading.Thread(
                    target=self.read_from_port, daemon=True
                )
                self.read_thread.start()

                self.port_changed.emit(port_name)
            else:
                self.log(f"Не удалось открыть {port_name}", msg_type="error")
        except Exception as e:
            self.log(f"Ошибка подключения: {e}", msg_type="error")

    def disconnect_port(self):
        self.stop_reading = True

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)

        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except:
                pass

        self.serial_port = None
        self.is_connected = False
        self.icon_manager.update_play_icon(self.btn_start_stop, self.is_connected)
        self.btn_start_stop.setToolTip("Начать мониторинг")
        self.log("Отключено", msg_type="info")

    def read_from_port(self):
        buffer = ""
        while self.is_connected and not self.stop_reading:
            try:
                if self.serial_port and self.serial_port.is_open:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        if data:
                            text = data.decode("utf-8", errors="replace")
                            buffer += text

                            while "\n" in buffer or "\r" in buffer:
                                if "\n" in buffer:
                                    line, buffer = buffer.split("\n", 1)
                                elif "\r" in buffer:
                                    line, buffer = buffer.split("\r", 1)
                                else:
                                    break

                                if line.strip():
                                    self.log(f"<<- {line.strip()}", msg_type="response")
                    else:
                        time.sleep(0.01)
                else:
                    break
            except Exception as e:
                if self.is_connected:
                    self.log(f"Ошибка чтения: {e}", msg_type="error")
                break

    def send_manual_command(self):
        if not self.is_connected or not self.serial_port:
            self.log("Порт не подключен", msg_type="error")
            return

        command = self.manual_input.text().strip()
        if not command:
            return

        self.manual_input.add_to_history(command)

        self.send_command(command)
        self.manual_input.clear()
        self.manual_input.reset_history_navigation()

    def send_command(self, command):
        try:
            line_ending_bytes = self.uart_settings.get_line_ending_bytes()
            command_bytes = command.encode("utf-8") + line_ending_bytes

            self.serial_port.write(command_bytes)
            self.serial_port.flush()

            line_ending_str = line_ending_bytes.decode("utf-8", errors="replace")
            command_with_ending = command + line_ending_str

            command_display = command_with_ending.replace("\r", "\\r").replace(
                "\n", "\\n"
            )

            self.log(f"->> {command_display}", msg_type="command")
        except Exception as e:
            self.log(f"Ошибка отправки команды: {e}", msg_type="error")

    def log(self, message, msg_type="info"):
        dt = QDateTime.currentDateTime()
        h = str(dt.time().hour()).zfill(2)
        m = str(dt.time().minute()).zfill(2)
        s = str(dt.time().second()).zfill(3)
        ms = str(dt.time().msec()).zfill(3)
        timestamp = f"[{h}:{m}:{s}.{ms}]"

        if not message.startswith("["):
            message = f"{timestamp} {message}"

        message = html.escape(message)

        is_light_theme = False
        parent = self.parent()
        if parent and hasattr(parent, "current_theme"):
            is_light_theme = parent.current_theme == "light"

        if msg_type == "error":
            color = "#e53e3e" if is_light_theme else "#ff5555"
        elif msg_type == "warning":
            color = "#dd6b20" if is_light_theme else "#ffaa00"
        elif msg_type == "command":
            color = "#38a169" if is_light_theme else "#50fa7b"
        elif msg_type == "response":
            color = "#3182ce" if is_light_theme else "#8be9fd"
        else:
            color = "#1a202c" if is_light_theme else "#e0e0e0"

        self.console.append(f'<span style="color:{color}">{message}</span>')
        self.console.moveCursor(self.console.textCursor().End)

    def update_theme(self, theme):
        self.icon_manager.set_theme(theme)

        self.icon_manager.update_refresh_icon(self.btn_refresh)
        self.icon_manager.update_play_icon(self.btn_start_stop, self.is_connected)
        self.icon_manager.update_cross_icon(self.btn_clear)

        self.update_console_colors(theme)

    def update_console_colors(self, theme=None):
        if not hasattr(self, "console"):
            return

        if theme is None:
            parent = self.parent()
            if parent and hasattr(parent, "current_theme"):
                theme = parent.current_theme
            else:
                theme = "dark"

        is_light_theme = theme == "light"

        html_content = self.console.toHtml()

        if is_light_theme:
            color_mapping = {
                "#ff5555": "#e53e3e",
                "#ffaa00": "#dd6b20",
                "#50fa7b": "#38a169",
                "#8be9fd": "#3182ce",
                "#e0e0e0": "#1a202c",
            }
        else:
            color_mapping = {
                "#e53e3e": "#ff5555",
                "#dd6b20": "#ffaa00",
                "#38a169": "#50fa7b",
                "#3182ce": "#8be9fd",
                "#1a202c": "#e0e0e0",
            }

        for old_color, new_color in color_mapping.items():
            html_content = html_content.replace(
                f"color:{old_color}", f"color:{new_color}"
            )
            html_content = html_content.replace(
                f"color: {old_color}", f"color: {new_color}"
            )

        cursor = self.console.textCursor()
        scroll_position = self.console.verticalScrollBar().value()

        self.console.setHtml(html_content)

        self.console.verticalScrollBar().setValue(scroll_position)
        cursor.movePosition(cursor.End)
        self.console.setTextCursor(cursor)
