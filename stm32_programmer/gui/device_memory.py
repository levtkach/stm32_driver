import threading
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QFrame,
    QDialog,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QMenu,
    QApplication,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor
import logging

from stm32_programmer.programmers.base import BaseProgrammer
from .icon_manager import IconManager

logger = logging.getLogger(__name__)


class MemoryAddressDialog(QDialog):

    MEMORY_ADDRESSES = {
        "Flash (0x08000000)": 0x08000000,
        "SRAM (0x20000000)": 0x20000000,
        "System Memory (0x1FFF0000)": 0x1FFF0000,
        "Option Bytes (0x1FFFC000)": 0x1FFFC000,
        "Backup SRAM (0x40024000)": 0x40024000,
    }

    def __init__(self, parent=None, current_address=0x08000000, current_size=256):
        super().__init__(parent)
        self.setWindowTitle("Настройки чтения памяти")
        self.setMinimumWidth(400)

        layout = QFormLayout()

        self.address_combo = QComboBox()
        for name, addr in self.MEMORY_ADDRESSES.items():
            self.address_combo.addItem(name, addr)

        index = self.address_combo.findData(current_address)
        if index >= 0:
            self.address_combo.setCurrentIndex(index)
        else:
            self.address_combo.insertItem(
                0, f"0x{current_address:08X}", current_address
            )
            self.address_combo.setCurrentIndex(0)

        layout.addRow("Адрес памяти:", self.address_combo)

        self.size_combo = QComboBox()
        sizes = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
        for size in sizes:
            self.size_combo.addItem(f"{size} байт", size)

        index = self.size_combo.findData(current_size)
        if index >= 0:
            self.size_combo.setCurrentIndex(index)
        else:
            self.size_combo.insertItem(0, f"{current_size} байт", current_size)
            self.size_combo.setCurrentIndex(0)

        layout.addRow("Размер чтения:", self.size_combo)

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
            "address": self.address_combo.currentData(),
            "size": self.size_combo.currentData(),
        }


class MemoryReadThread(QThread):
    finished = pyqtSignal(bytes, int)
    error = pyqtSignal(str)

    def __init__(self, programmer, device, address, size):
        super().__init__()
        self.programmer = programmer
        self.device = device
        self.address = address
        self.size = size

    def run(self):
        try:
            self.programmer.selected = self.device

            data = self.programmer.read_memory_hex(self.address, self.size)

            if data:
                self.finished.emit(data, self.address)
            else:
                self.error.emit("Не удалось прочитать память")
        except Exception as e:
            logger.exception(f"Ошибка чтения памяти: {e}")
            self.error.emit(f"Ошибка чтения памяти: {e}")


class DeviceMemoryWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.programmer = BaseProgrammer()
        self.devices = []
        self.selected_device = None
        self.read_thread = None
        self.memory_data = b""
        self.memory_address = 0x08000000
        self.memory_size = 256
        self.current_page = 0
        self.bytes_per_page = 256
        self.current_mode = None
        self.current_theme = "dark"

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

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
        device_container_layout.addWidget(self.combobox_devices, 1)

        theme = None
        parent = self.parent()
        if parent and hasattr(parent, "current_theme"):
            theme = parent.current_theme
        else:
            theme = "dark"

        self.current_theme = theme
        self.icon_manager = IconManager(theme)
        self.btn_refresh_devices = QPushButton()
        self.icon_manager.update_refresh_icon(self.btn_refresh_devices)
        self.btn_refresh_devices.setProperty("refreshButton", True)
        self.btn_refresh_devices.setFixedSize(28, 28)
        self.btn_refresh_devices.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_devices.setToolTip("Обновить список устройств")
        self.btn_refresh_devices.clicked.connect(self.refresh_devices)
        device_container_layout.addWidget(self.btn_refresh_devices)

        device_container.setLayout(device_container_layout)
        device_layout.addWidget(device_container, 1)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setProperty("iconButton", True)
        self.btn_settings.setFixedSize(28, 28)
        self.btn_settings.setToolTip("Настройки адреса памяти")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.show_settings_dialog)
        device_layout.addWidget(self.btn_settings)

        self.btn_lv = QPushButton("LV")
        self.btn_lv.setProperty("iconButton", True)
        self.btn_lv.setFixedSize(40, 28)
        self.btn_lv.setToolTip("Переключить в режим LV")
        self.btn_lv.setCursor(Qt.PointingHandCursor)
        self.btn_lv.setEnabled(False)
        self.btn_lv.clicked.connect(lambda: self.switch_mode("LV"))
        device_layout.addWidget(self.btn_lv)

        self.btn_hv = QPushButton("HV")
        self.btn_hv.setProperty("iconButton", True)
        self.btn_hv.setFixedSize(40, 28)
        self.btn_hv.setToolTip("Переключить в режим HV")
        self.btn_hv.setCursor(Qt.PointingHandCursor)
        self.btn_hv.setEnabled(False)
        self.btn_hv.clicked.connect(lambda: self.switch_mode("HV"))
        device_layout.addWidget(self.btn_hv)

        self.btn_start_stop = QPushButton()
        self.icon_manager.update_play_icon(self.btn_start_stop, False)
        self.btn_start_stop.setProperty("programButton", True)
        self.btn_start_stop.setFixedSize(28, 28)
        self.btn_start_stop.setToolTip("Начать чтение памяти")
        self.btn_start_stop.setCursor(Qt.PointingHandCursor)
        self.btn_start_stop.clicked.connect(self.toggle_reading)
        device_layout.addWidget(self.btn_start_stop)

        self.btn_erase = QPushButton()
        self.icon_manager.update_delete_icon(self.btn_erase)
        self.btn_erase.setProperty("iconButton", True)
        self.btn_erase.setFixedSize(28, 28)
        self.btn_erase.setToolTip("Стереть выбранный диапазон памяти")
        self.btn_erase.setCursor(Qt.PointingHandCursor)
        self.btn_erase.setEnabled(False)
        self.btn_erase.clicked.connect(self.erase_memory)
        device_layout.addWidget(self.btn_erase)

        self.mode_hint_label = QLabel("")
        self.mode_hint_label.setProperty("info", True)
        self.mode_hint_label.setWordWrap(True)
        device_layout.addWidget(self.mode_hint_label, 1)

        layout.addLayout(device_layout)

        self.memory_table = QTableWidget()
        self.memory_table.setColumnCount(6)
        headers = ["Address", "0", "4", "8", "C", "ASCII"]
        self.memory_table.setHorizontalHeaderLabels(headers)

        self.memory_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        for i in range(1, 5):
            self.memory_table.horizontalHeader().setSectionResizeMode(
                i, QHeaderView.Stretch
            )
        self.memory_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.Stretch
        )

        self.memory_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        font = self.memory_table.font()
        font.setFamily("JetBrains Mono")
        font.setPointSize(10)
        font.setStyleHint(font.Monospace)
        font.setFixedPitch(True)
        self.memory_table.setFont(font)
        self.memory_table.setAlternatingRowColors(True)
        self.memory_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.memory_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.memory_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.memory_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.memory_table.customContextMenuRequested.connect(self.show_context_menu)
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence

        copy_shortcut = QShortcut(QKeySequence.Copy, self.memory_table)
        copy_shortcut.activated.connect(self.copy_selected)

        layout.addWidget(self.memory_table, 1)

        pagination_layout = QHBoxLayout()
        pagination_layout.addStretch()

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setProperty("iconButton", True)
        self.btn_prev.setFixedSize(28, 28)
        self.btn_prev.setToolTip("Предыдущая страница")
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_prev.setEnabled(False)
        pagination_layout.addWidget(self.btn_prev)

        self.page_label = QLabel("Страница 0 из 0")
        self.page_label.setProperty("info", True)
        pagination_layout.addWidget(self.page_label)

        self.btn_next = QPushButton("▶")
        self.btn_next.setProperty("iconButton", True)
        self.btn_next.setFixedSize(28, 28)
        self.btn_next.setToolTip("Следующая страница")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(self.next_page)
        self.btn_next.setEnabled(False)
        pagination_layout.addWidget(self.btn_next)

        layout.addLayout(pagination_layout)

        self.info_label = QLabel(
            f"Адрес: 0x{self.memory_address:08X} | Размер: {self.memory_size} байт"
        )
        self.info_label.setProperty("info", True)
        layout.addWidget(self.info_label)

        self.setLayout(layout)

        self.refresh_devices()

        self.update_mode_buttons_state()

    def refresh_devices(self):
        try:
            self.devices = self.programmer.find_devices()
            self.combobox_devices.clear()

            for device in self.devices:
                device_name = device.get("name", "Unknown")
                self.combobox_devices.addItem(device_name, device)

            if self.devices:
                logger.info(f"Найдено устройств: {len(self.devices)}")
        except Exception as e:
            logger.exception(f"Ошибка при обновлении устройств: {e}")

    def _get_device_id(self, device):
        if device.get("serial"):
            return f"serial:{device['serial']}"
        else:
            vid = device.get("vid", 0)
            pid = device.get("pid", 0)
            bus = device.get("usb_bus", 0)
            address = device.get("usb_address", 0)
            return f"vidpid:{vid:04X}:{pid:04X}:bus{bus}:addr{address}"

    def _load_device_port_mapping(self, device_id):
        parent = self.parent()
        while parent and not hasattr(parent, "settings"):
            parent = parent.parent()
        if parent and hasattr(parent, "settings"):
            key = f"device_port_mapping/{device_id}"
            return parent.settings.value(key, None)
        return None

    def on_device_selected(self, index):
        if index >= 0 and index < len(self.devices):
            self.selected_device = self.devices[index]
        else:
            self.selected_device = None

        self.update_mode_buttons_state()

    def show_settings_dialog(self):
        dialog = MemoryAddressDialog(
            self, current_address=self.memory_address, current_size=self.memory_size
        )

        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.memory_address = settings["address"]
            self.memory_size = settings["size"]

            self.info_label.setText(
                f"Адрес: 0x{self.memory_address:08X} | Размер: {self.memory_size} байт"
            )

    def toggle_reading(self):
        if self.read_thread and self.read_thread.isRunning():
            self.stop_reading()
        else:
            self.start_reading()

    def start_reading(self):
        if not self.selected_device:
            QMessageBox.warning(self, "Ошибка", "Выберите STM32 устройство")
            return

        self.btn_start_stop.setEnabled(False)
        self.icon_manager.update_play_icon(self.btn_start_stop, True)
        self.btn_start_stop.setToolTip("Остановить чтение")

        self.read_thread = MemoryReadThread(
            self.programmer, self.selected_device, self.memory_address, self.memory_size
        )
        self.read_thread.finished.connect(self.on_reading_finished)
        self.read_thread.error.connect(self.on_reading_error)
        self.read_thread.start()

    def stop_reading(self):
        if self.read_thread and self.read_thread.isRunning():
            self.read_thread.terminate()
            self.read_thread.wait()

        self.btn_start_stop.setEnabled(True)
        self.icon_manager.update_play_icon(self.btn_start_stop, False)
        self.btn_start_stop.setToolTip("Начать чтение памяти")
        self.btn_erase.setEnabled(bool(self.memory_data))

    def on_reading_finished(self, data, address):
        self.memory_data = data
        self.current_page = 0
        self.update_memory_table()

        self.btn_start_stop.setEnabled(True)
        self.icon_manager.update_play_icon(self.btn_start_stop, False)
        self.btn_start_stop.setToolTip("Начать чтение памяти")
        self.btn_erase.setEnabled(True)

    def on_reading_error(self, error_msg):
        QMessageBox.critical(self, "Ошибка", error_msg)

        self.btn_start_stop.setEnabled(True)
        self.icon_manager.update_play_icon(self.btn_start_stop, False)
        self.btn_start_stop.setToolTip("Начать чтение памяти")
        self.btn_erase.setEnabled(False)

    def update_memory_table(self):
        if not self.memory_data:
            self.memory_table.setRowCount(0)
            self.page_label.setText("Страница 0 из 0")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        total_bytes = len(self.memory_data)
        total_pages = (total_bytes + self.bytes_per_page - 1) // self.bytes_per_page

        if total_pages == 0:
            total_pages = 1

        if self.current_page >= total_pages:
            self.current_page = total_pages - 1
        if self.current_page < 0:
            self.current_page = 0

        start_byte = self.current_page * self.bytes_per_page
        end_byte = min(start_byte + self.bytes_per_page, total_bytes)

        rows = (end_byte - start_byte + 15) // 16

        self.memory_table.setRowCount(rows)

        for row in range(rows):
            row_start = start_byte + row * 16
            row_end = min(row_start + 16, end_byte)
            row_address = self.memory_address + row_start

            address_item = QTableWidgetItem(f"0x{row_address:08X}")
            address_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.memory_table.setItem(row, 0, address_item)

            ascii_chars = []
            for word_col in range(4):
                word_start = row_start + word_col * 4
                word_end = min(word_start + 4, row_end)

                if word_start < end_byte:
                    word_bytes = []
                    word_value = 0
                    for i in range(4):
                        byte_index = word_start + i
                        if byte_index < end_byte:
                            byte_value = self.memory_data[byte_index]
                            word_bytes.append(byte_value)
                            word_value |= byte_value << (i * 8)
                            if 32 <= byte_value <= 126:
                                try:
                                    char = chr(byte_value)
                                    if char.isprintable() and ord(char) == byte_value:
                                        ascii_chars.append(char)
                                    else:
                                        ascii_chars.append(".")
                                except (ValueError, OverflowError):
                                    ascii_chars.append(".")
                            else:
                                ascii_chars.append(".")
                        else:
                            word_bytes.append(0)
                            ascii_chars.append(".")

                    word_item = QTableWidgetItem(f"{word_value:08X}")
                    word_item.setTextAlignment(Qt.AlignCenter)

                    if word_value == 0:
                        if self.current_theme == "light":
                            word_item.setBackground(QColor(180, 240, 180))
                        else:
                            word_item.setBackground(QColor(40, 60, 40))

                    self.memory_table.setItem(row, word_col + 1, word_item)
                else:
                    empty_item = QTableWidgetItem("--------")
                    empty_item.setTextAlignment(Qt.AlignCenter)
                    self.memory_table.setItem(row, word_col + 1, empty_item)
                    ascii_chars.extend(["."] * 4)

            safe_ascii = []
            for i, char in enumerate(ascii_chars[:16]):
                try:
                    byte_index = row_start + i
                    if byte_index < end_byte:
                        byte_value = self.memory_data[byte_index]
                        if 32 <= byte_value <= 126:
                            if (
                                48 <= byte_value <= 57
                                or 65 <= byte_value <= 90
                                or 97 <= byte_value <= 122
                                or byte_value == 32
                                or byte_value
                                in [
                                    33,
                                    34,
                                    35,
                                    36,
                                    37,
                                    38,
                                    39,
                                    40,
                                    41,
                                    42,
                                    43,
                                    44,
                                    45,
                                    46,
                                    47,
                                    58,
                                    59,
                                    60,
                                    61,
                                    62,
                                    63,
                                    64,
                                    91,
                                    92,
                                    93,
                                    94,
                                    95,
                                    96,
                                    123,
                                    124,
                                    125,
                                    126,
                                ]
                            ):
                                safe_ascii.append(chr(byte_value))
                            else:
                                safe_ascii.append(".")
                        else:
                            safe_ascii.append(".")
                    else:
                        safe_ascii.append(".")
                except (ValueError, TypeError, UnicodeError, IndexError):
                    safe_ascii.append(".")

            ascii_text = "".join(safe_ascii)
            ascii_item = QTableWidgetItem(ascii_text)
            ascii_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.memory_table.setItem(row, 5, ascii_item)

        self.page_label.setText(f"Страница {self.current_page + 1} из {total_pages}")
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total_pages - 1)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_memory_table()

    def next_page(self):
        if self.memory_data:
            total_bytes = len(self.memory_data)
            total_pages = (total_bytes + self.bytes_per_page - 1) // self.bytes_per_page
            if self.current_page < total_pages - 1:
                self.current_page += 1
                self.update_memory_table()

    def show_context_menu(self, position):
        menu = QMenu(self)
        copy_action = menu.addAction("Копировать")
        copy_action.triggered.connect(self.copy_selected)

        if self.memory_table.selectedItems():
            menu.exec_(self.memory_table.viewport().mapToGlobal(position))

    def copy_selected(self):
        selected_items = self.memory_table.selectedItems()
        if not selected_items:
            return

        rows_data = {}
        for item in selected_items:
            row = item.row()
            col = item.column()
            if row not in rows_data:
                rows_data[row] = {}
            rows_data[row][col] = item.text()

        lines = []
        for row in sorted(rows_data.keys()):
            cols = sorted(rows_data[row].keys())
            line_parts = []
            for col in cols:
                line_parts.append(rows_data[row][col])
            lines.append("\t".join(line_parts))

        text_to_copy = "\n".join(lines)
        clipboard = QApplication.clipboard()
        clipboard.setText(text_to_copy)

    def _update_mode_buttons_visual_state(self):
        if not hasattr(self, "btn_lv") or not hasattr(self, "btn_hv"):
            return

        self.btn_lv.setProperty("activeMode", "")
        self.btn_hv.setProperty("activeMode", "")

        if self.current_mode == "LV":
            self.btn_lv.setProperty("activeMode", "LV")
        elif self.current_mode == "HV":
            self.btn_hv.setProperty("activeMode", "HV")

        self.btn_lv.style().unpolish(self.btn_lv)
        self.btn_lv.style().polish(self.btn_lv)
        self.btn_lv.update()

        self.btn_hv.style().unpolish(self.btn_hv)
        self.btn_hv.style().polish(self.btn_hv)
        self.btn_hv.update()

    def _load_current_mode(self, device_id):
        parent = self.parent()
        while parent and not hasattr(parent, "settings"):
            parent = parent.parent()
        if parent and hasattr(parent, "settings"):
            key = f"device_mode/{device_id}"
            return parent.settings.value(key, None)
        return None

    def _save_current_mode(self, device_id, mode):
        parent = self.parent()
        while parent and not hasattr(parent, "settings"):
            parent = parent.parent()
        if parent and hasattr(parent, "settings"):
            key = f"device_mode/{device_id}"
            parent.settings.setValue(key, mode)
            parent.settings.sync()

    def update_mode_buttons_state(self, selected_device=None):
        if not hasattr(self, "btn_lv") or not hasattr(self, "btn_hv"):
            return

        if selected_device is None:
            selected_device = self.selected_device

        if selected_device:
            device_id = self._get_device_id(selected_device)
            saved_port = self._load_device_port_mapping(device_id)

            if saved_port:
                self.btn_lv.setEnabled(True)
                self.btn_hv.setEnabled(True)

                saved_mode = self._load_current_mode(device_id)
                if saved_mode in ["LV", "HV"]:
                    self.current_mode = saved_mode
                else:
                    self.current_mode = None

                self._update_mode_buttons_visual_state()

                if hasattr(self, "mode_hint_label"):
                    mode_text = (
                        f" | Режим: {self.current_mode}" if self.current_mode else ""
                    )
                    self.mode_hint_label.setText(f"Порт: {saved_port}{mode_text}")
                    self.mode_hint_label.setToolTip(
                        f"Сохраненная пара: {selected_device.get('name', 'Unknown')} - {saved_port}"
                    )
            else:
                self.btn_lv.setEnabled(False)
                self.btn_hv.setEnabled(False)
                self.current_mode = None
                self._update_mode_buttons_visual_state()
                if hasattr(self, "mode_hint_label"):
                    self.mode_hint_label.setText(
                        "Сохраните пару устройство-порт для переключения режимов"
                    )
                    self.mode_hint_label.setToolTip(
                        "Выберите устройство и порт, затем начните программирование для сохранения пары"
                    )
        else:
            self.btn_lv.setEnabled(False)
            self.btn_hv.setEnabled(False)
            self.current_mode = None
            self._update_mode_buttons_visual_state()
            if hasattr(self, "mode_hint_label"):
                self.mode_hint_label.setText("")
                self.mode_hint_label.setToolTip("")

    def switch_mode(self, mode):
        if mode not in ["LV", "HV"]:
            return

        if not self.selected_device:
            QMessageBox.warning(self, "Ошибка", "Выберите STM32 устройство")
            return

        device_id = self._get_device_id(self.selected_device)
        saved_port = self._load_device_port_mapping(device_id)

        if not saved_port:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не найдена сохраненная пара устройство-порт.\n"
                "Выберите устройство и порт, затем начните программирование для сохранения пары.",
            )
            return

        try:
            from stm32_programmer.utils.uart_settings import UARTSettings
            from stm32_programmer.programmers.core import connect_to_uart_port
            import serial
            import time

            uart_settings = UARTSettings()

            serial_port = connect_to_uart_port(
                saved_port,
                baudrate=uart_settings.get_baud_rate(),
                line_ending=uart_settings.get_line_ending(),
            )

            if not serial_port or not serial_port.is_open:
                QMessageBox.critical(
                    self, "Ошибка", f"Не удалось открыть порт {saved_port}"
                )
                return

            command = f"SET SWICH_SWD1__2={mode}"
            line_ending_bytes = uart_settings.get_line_ending_bytes()
            command_bytes = command.encode("utf-8") + line_ending_bytes

            serial_port.write(command_bytes)
            serial_port.flush()

            time.sleep(0.5)
            expected_response = f"SWICH_SWD1__2={mode}".encode("utf-8")

            response_received = False
            start_time = time.time()
            timeout = 2.0

            while time.time() - start_time < timeout:
                if serial_port.in_waiting > 0:
                    response = serial_port.read(serial_port.in_waiting)
                    if expected_response in response:
                        response_received = True
                        break
                time.sleep(0.1)

            try:
                serial_port.close()
            except:
                pass

            if response_received:
                self.current_mode = mode
                self._save_current_mode(device_id, mode)
                self._update_mode_buttons_visual_state()
                if hasattr(self, "mode_hint_label"):
                    mode_text = f" | Режим: {mode}"
                    current_text = self.mode_hint_label.text()
                    if "Порт:" in current_text:
                        port_text = current_text.split(" | ")[0]
                        self.mode_hint_label.setText(f"{port_text}{mode_text}")

                QMessageBox.information(
                    self, "Успех", f"Режим успешно переключен в {mode}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    f"Команда отправлена, но ответ не получен.\n"
                    f"Проверьте подключение к порту {saved_port}",
                )

        except Exception as e:
            logger.exception(f"Ошибка при переключении режима: {e}")
            QMessageBox.critical(
                self, "Ошибка", f"Ошибка при переключении режима:\n{str(e)}"
            )

    def erase_memory(self):
        if not self.selected_device:
            QMessageBox.warning(self, "Ошибка", "Выберите STM32 устройство")
            return

        if not self.memory_data:
            QMessageBox.warning(self, "Ошибка", "Нет данных в памяти для стирания")
            return

        address_hex = f"0x{self.memory_address:08X}"
        size_bytes = self.memory_size
        reply = QMessageBox.warning(
            self,
            "Предупреждение",
            f"Вы уверены, что хотите стереть память?\n\n"
            f"Адрес: {address_hex}\n"
            f"Размер: {size_bytes} байт\n\n"
            f"Все данные в этом диапазоне будут заменены нулями.\n"
            f"Это действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        try:
            self.programmer.selected = self.selected_device

            zero_data = b"\x00" * size_bytes

            write_result = self.programmer.write_bytes(zero_data, self.memory_address)

            if isinstance(write_result, tuple):
                success, error_details = write_result
            else:
                success = write_result
                error_details = None

            if success:
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Память успешно стерта.\n"
                    f"Диапазон {address_hex} - 0x{self.memory_address + size_bytes - 1:08X} заполнен нулями.",
                )
                self.memory_data = zero_data
                self.current_page = 0
                self.update_memory_table()
            else:
                error_msg = error_details if error_details else "Неизвестная ошибка"
                QMessageBox.critical(
                    self, "Ошибка", f"Не удалось стереть память:\n{error_msg}"
                )

        except Exception as e:
            logger.exception(f"Ошибка при стирании памяти: {e}")
            QMessageBox.critical(
                self, "Ошибка", f"Ошибка при стирании памяти:\n{str(e)}"
            )

    def update_theme(self, theme):
        self.current_theme = theme
        self.icon_manager.set_theme(theme)
        self.icon_manager.update_refresh_icon(self.btn_refresh_devices)
        self.icon_manager.update_play_icon(
            self.btn_start_stop, self.read_thread and self.read_thread.isRunning()
        )
        self.icon_manager.update_delete_icon(self.btn_erase)
        if self.memory_data:
            self.update_memory_table()
