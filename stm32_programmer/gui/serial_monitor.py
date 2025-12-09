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
from PyQt5.QtGui import QFont, QTextCursor
import html
import logging

from stm32_programmer.utils.uart_commands import get_command_structure, build_command
from stm32_programmer.utils.uart_settings import UARTSettings

logger = logging.getLogger(__name__)


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
        port_layout.setSpacing(8)
        port_layout.setContentsMargins(8, 4, 8, 4)
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

        btn_refresh = QPushButton("↻")
        btn_refresh.setProperty("refreshButton", True)
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setToolTip("Обновить список портов")
        btn_refresh.clicked.connect(self.refresh_ports)
        port_container_layout.addWidget(btn_refresh)

        port_container.setLayout(port_container_layout)
        port_layout.addWidget(port_container, 1)
        layout.addLayout(port_layout)

        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(8)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setProperty("iconButton", True)
        self.btn_settings.setFixedSize(28, 28)
        self.btn_settings.setToolTip("Настройки UART")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.show_settings_dialog)
        settings_layout.addWidget(self.btn_settings)

        self.settings_label = QLabel(
            f"Baud: {self.current_baud_rate} | Line: {self.current_line_ending}"
        )
        self.settings_label.setProperty("info", True)
        settings_layout.addWidget(self.settings_label)

        settings_layout.addStretch()

        self.btn_connect = QPushButton("⚡")
        self.btn_connect.setProperty("iconButton", True)
        self.btn_connect.setFixedSize(28, 28)
        self.btn_connect.setToolTip("Подключиться/Отключиться")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.clicked.connect(self.toggle_connection)
        settings_layout.addWidget(self.btn_connect)

        layout.addLayout(settings_layout)

        manual_input_layout = QHBoxLayout()
        manual_input_layout.setSpacing(8)
        manual_input_label = QLabel("Команда:")
        manual_input_label.setMinimumWidth(150)
        manual_input_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        manual_input_layout.addWidget(manual_input_label)

        btn_set = QPushButton("SET")
        btn_set.setProperty("iconButton", True)
        btn_set.setFixedSize(40, 28)
        btn_set.setToolTip("Вставить SET")
        btn_set.setCursor(Qt.PointingHandCursor)
        btn_set.clicked.connect(lambda: self.insert_command_prefix("SET "))
        manual_input_layout.addWidget(btn_set)

        btn_get = QPushButton("GET")
        btn_get.setProperty("iconButton", True)
        btn_get.setFixedSize(40, 28)
        btn_get.setToolTip("Вставить GET")
        btn_get.setCursor(Qt.PointingHandCursor)
        btn_get.clicked.connect(lambda: self.insert_command_prefix("GET "))
        manual_input_layout.addWidget(btn_get)

        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Введите команду вручную...")
        self.manual_input.setMinimumHeight(28)
        self.manual_input.returnPressed.connect(self.send_manual_command)
        manual_input_layout.addWidget(self.manual_input, 1)

        btn_send_manual = QPushButton("➤")
        btn_send_manual.setProperty("iconButton", True)
        btn_send_manual.setFixedSize(28, 28)
        btn_send_manual.setToolTip("Отправить команду")
        btn_send_manual.setCursor(Qt.PointingHandCursor)
        btn_send_manual.clicked.connect(self.send_manual_command)
        manual_input_layout.addWidget(btn_send_manual)

        layout.addLayout(manual_input_layout)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        font = self.console.font()
        font.setFamily("JetBrains Mono")
        font.setPointSize(11)
        font.setStyleHint(font.Monospace)
        font.setFixedPitch(True)
        self.console.setFont(font)
        layout.addWidget(self.console)

        clear_layout = QHBoxLayout()
        clear_layout.addStretch()
        btn_clear = QPushButton("✕")
        btn_clear.setProperty("iconButton", True)
        btn_clear.setFixedSize(28, 28)
        btn_clear.setToolTip("Очистить логи")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self.console.clear)
        clear_layout.addWidget(btn_clear)
        layout.addLayout(clear_layout)

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
                self.btn_connect.setText("⚡")
                self.btn_connect.setToolTip("Отключиться от порта")
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
        self.btn_connect.setText("⚡")
        self.btn_connect.setToolTip("Подключиться к порту")
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

    def insert_command_prefix(self, prefix):
        current_text = self.manual_input.text()
        cursor_pos = self.manual_input.cursorPosition()
        new_text = current_text[:cursor_pos] + prefix + current_text[cursor_pos:]
        self.manual_input.setText(new_text)
        self.manual_input.setCursorPosition(cursor_pos + len(prefix))
        self.manual_input.setFocus()

    def send_manual_command(self):
        if not self.is_connected or not self.serial_port:
            self.log("Порт не подключен", msg_type="error")
            return

        command = self.manual_input.text().strip()
        if not command:
            return

        self.send_command(command)
        self.manual_input.clear()

    def send_command(self, command):
        try:
            line_ending_bytes = self.uart_settings.get_line_ending_bytes()
            command_bytes = command.encode("utf-8") + line_ending_bytes

            self.serial_port.write(command_bytes)
            self.serial_port.flush()

            self.log(f"->> {command}", msg_type="command")
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
