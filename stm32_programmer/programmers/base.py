import usb.core
import usb.backend.libusb1
import usb.backend.libusb0
import usb.backend.openusb
import serial
from serial.serialutil import SerialException
import time
import os
import sys
import platform
import logging
import importlib.util
import subprocess
from stm32_programmer.utils.icon_loader import get_icon_emoji_fallback

logger = logging.getLogger(__name__)


def _init_usb_backend():
    backend = None
    try:
        import libusb_package

        backend = libusb_package.get_libusb1_backend()
        if backend is not None:
            return backend
    except (ImportError, Exception):
        pass

    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.util

            dll_names = ["libusb-1.0.dll", "libusb0.dll"]
            dll_paths = []
            stm32cube_paths = [
                r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin",
                r"C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin",
            ]

            for dll_name in dll_names:
                dll_path = ctypes.util.find_library(dll_name.replace(".dll", ""))
                if dll_path:
                    dll_paths.append(dll_path)

                if os.path.exists(dll_name):
                    dll_paths.append(os.path.abspath(dll_name))

                system32_path = os.path.join(
                    os.environ.get("SystemRoot", "C:\\Windows"), "System32", dll_name
                )
                if os.path.exists(system32_path):
                    dll_paths.append(system32_path)

                for cube_path in stm32cube_paths:
                    if os.path.exists(cube_path):
                        cube_dll = os.path.join(cube_path, dll_name)
                        if os.path.exists(cube_dll):
                            dll_paths.append(cube_dll)

            if dll_paths:
                try:
                    backend = usb.backend.libusb1.get_backend(
                        find_library=lambda x: dll_paths[0]
                    )
                    if backend is not None:
                        return backend
                except Exception:
                    pass
        except Exception:
            pass

    try:
        backend = usb.backend.libusb1.get_backend()
        if backend is not None:
            return backend
    except Exception:
        pass

    try:
        backend = usb.backend.libusb0.get_backend()
        if backend is not None:
            return backend
    except Exception:
        pass

    try:
        backend = usb.backend.openusb.get_backend()
        if backend is not None:
            return backend
    except Exception:
        pass

    stm32cube_bin = (
        r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin"
    )
    cube_note = ""
    if os.path.exists(stm32cube_bin):
        cube_note = f"\n\nПримечание: Обнаружена установка STM32Cube в:\n   {stm32cube_bin}\n   Вы можете скопировать libusb-1.0.dll в эту директорию."

    raise RuntimeError(
        "USB backend недоступен.\n\n"
        "Для исправления на Windows выполните следующие действия:\n"
        "1. libusb-package уже установлен, но DLL отсутствует.\n"
        "2. Скачайте libusb-1.0.dll вручную:\n"
        "   - Перейдите на https://github.com/libusb/libusb/releases\n"
        "   - Скачайте последнюю версию Windows binaries (libusb-1.0.XX-binaries.7z)\n"
        "   - Распакуйте архив и скопируйте libusb-1.0.dll в одну из директорий:\n"
        "     * Текущая директория проекта\n"
        "     * C:\\Program Files\\STMicroelectronics\\STM32Cube\\STM32CubeProgrammer\\bin\n"
        "     * Или запустите: python setup_libusb.py для инструкций\n"
        "3. После установки DLL перезапустите Python окружение.\n\n"
        "Альтернатива: используйте Zadig для установки WinUSB драйверов для вашего USB устройства."
        + cube_note
    )


try:
    backend = _init_usb_backend()
    usb.core.find(backend=backend)
except RuntimeError as e:
    _backend_error = str(e)
except Exception:
    _backend_error = "Failed to initialize USB backend"


STLINK_V2 = (0x0483, 0x3748)
STLINK_V21 = (0x0483, 0x374B)
STLINK_V21_NEW = (0x0483, 0x374D)
STLINK_V3 = (0x0483, 0x374E)
STLINK_V3_ALT = (0x0483, 0x374F)

STLINK_IDS = [STLINK_V2, STLINK_V21, STLINK_V21_NEW, STLINK_V3, STLINK_V3_ALT]

DEFAULT_FLASH_ADDRESS = 0x08000000


def reset_uart_system_level(port_name):
    logger = logging.getLogger(__name__)
    logger.info(f"Системная перезагрузка UART порта {port_name}...")

    try:
        if platform.system() == "Darwin":

            try:

                tty_port = port_name.replace("/dev/cu.", "/dev/tty.")

                lsof_result = subprocess.run(
                    ["lsof", "-t", tty_port], capture_output=True, text=True, timeout=5
                )

                if lsof_result.returncode == 0 and lsof_result.stdout.strip():
                    pids = lsof_result.stdout.strip().split("\n")
                    current_pid = str(os.getpid())
                    for pid in pids:
                        if pid.strip() != current_pid:
                            try:
                                logger.info(
                                    f"Завершение процесса {pid}, использующего порт..."
                                )
                                subprocess.run(
                                    ["kill", "-9", pid.strip()], timeout=5, check=False
                                )
                            except:
                                pass

                time.sleep(1.5)

                logger.info("Сброс последовательного порта...")

                time.sleep(2.0)

                logger.info(f"Системная перезагрузка порта {port_name} завершена")

            except (
                subprocess.TimeoutExpired,
                subprocess.SubprocessError,
                FileNotFoundError,
            ) as e:
                logger.warning(f"Ошибка при системной перезагрузке порта: {e}")

                time.sleep(2.0)

        elif platform.system() == "Windows":

            try:
                logger.info("Симуляция отключения USB устройства на Windows...")

                com_port_num = port_name.replace("COM", "").strip()

                if com_port_num.isdigit():

                    ps_command = f"""
                    try {{
                        $port = Get-WmiObject Win32_SerialPort | Where-Object {{ $_.DeviceID -eq "{port_name}" }}
                        if ($port) {{
                            $pnpDevice = Get-PnpDevice | Where-Object {{ $_.InstanceId -eq $port.PNPDeviceID }}
                            if (-not $pnpDevice) {{
                                $pnpDevice = Get-PnpDevice | Where-Object {{ $_.FriendlyName -like "*{port_name}*" -or $_.InstanceId -like "*USB*" }}
                            }}
                            if ($pnpDevice) {{
                                $instanceId = $pnpDevice.InstanceId
                                Write-Output "Найдено устройство: $instanceId"
                                
                                Disable-PnpDevice -InstanceId $instanceId -Confirm:$false -ErrorAction SilentlyContinue
                                Start-Sleep -Seconds 2
                                
                                Enable-PnpDevice -InstanceId $instanceId -Confirm:$false -ErrorAction SilentlyContinue
                                Write-Output "Устройство перезагружено"
                            }} else {{
                                Write-Output "Устройство не найдено"
                            }}
                        }} else {{
                            Write-Output "COM порт не найден"
                        }}
                    }} catch {{
                        Write-Output "Ошибка: $_"
                    }}
                    """

                    try:
                        logger.info(
                            "Выполнение PowerShell команды для перезагрузки USB устройства..."
                        )

                        result = subprocess.run(
                            ["powershell", "-Command", ps_command],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )

                        if result.returncode == 0:
                            output = result.stdout.strip()
                            logger.info(f"Результат PowerShell: {output}")
                            if (
                                "перезагружено" in output
                                or "перезагружено" in output.lower()
                            ):
                                logger.info("USB устройство успешно перезагружено")
                            time.sleep(2.0)
                        else:
                            logger.warning(
                                f"PowerShell вернул код ошибки {result.returncode}: {result.stderr}"
                            )
                            time.sleep(1.5)
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
                        logger.warning(f"Ошибка при перезагрузке USB устройства: {e}")
                        time.sleep(1.5)
                else:
                    logger.warning(f"Неверный формат COM порта: {port_name}")
                    time.sleep(1.5)

            except Exception as e:
                logger.warning(f"Ошибка при симуляции отключения USB на Windows: {e}")
                time.sleep(1.5)

        else:
            try:

                result = subprocess.run(
                    ["udevadm", "info", "-q", "path", "-n", port_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    device_path = result.stdout.strip()
                    logger.info(f"Найдено устройство: {device_path}")
                    time.sleep(1.5)
                else:
                    time.sleep(1.5)

            except (
                subprocess.TimeoutExpired,
                subprocess.SubprocessError,
                FileNotFoundError,
            ) as e:
                logger.warning(f"Ошибка при системной перезагрузке порта на Linux: {e}")
                time.sleep(1.5)

    except Exception as e:
        logger.warning(f"Ошибка при системной перезагрузке порта: {e}")
        time.sleep(2.0)


class BaseProgrammer:
    def __init__(self):
        self.devices = []
        self.selected = None
        self.selected_uart = None

    def _safe_uart_write(self, data, max_retries=2, uart_port=None):

        import sys

        logger.debug(
            f"_safe_uart_write вызван: размер данных={len(data)} байт, max_retries={max_retries}, uart_port={uart_port}"
        )

        try:
            from stm32_programmer.programmers.core import (
                connect_to_uart_port,
                detect_serial_port,
            )
        except ImportError:

            logger.warning(
                "Не удалось импортировать функции из core, используем альтернативный подход"
            )
            connect_to_uart_port = None
            detect_serial_port = None

        for attempt in range(max_retries + 1):
            logger.debug(f"_safe_uart_write: попытка {attempt + 1}/{max_retries + 1}")
            try:

                if not self.selected_uart:
                    if attempt < max_retries:
                        logger.warning(
                            f"UART порт не открыт (попытка {attempt + 1}/{max_retries + 1}), пытаемся переоткрыть..."
                        )

                        if not uart_port:

                            if self.selected and detect_serial_port:
                                try:
                                    uart_port = detect_serial_port(self.selected)
                                except Exception as e:
                                    logger.warning(
                                        f"Не удалось определить порт через detect_serial_port: {e}"
                                    )
                            if not uart_port:
                                logger.error(
                                    "Не удалось определить порт для переоткрытия"
                                )
                                raise RuntimeError(
                                    "I/O operation on closed file: UART порт не открыт и не удалось определить порт для переоткрытия"
                                )

                        if connect_to_uart_port:
                            try:
                                self.close_uart()
                                time.sleep(0.5 if sys.platform == "win32" else 0.2)
                                self.selected_uart = connect_to_uart_port(uart_port)
                                if self.selected_uart and self.selected_uart.is_open:
                                    logger.info(
                                        f"UART порт {uart_port} успешно переоткрыт"
                                    )
                                    continue
                                else:
                                    raise RuntimeError(
                                        f"Не удалось открыть порт {uart_port}"
                                    )
                            except Exception as reopen_error:
                                logger.error(
                                    f"Ошибка при переоткрытии порта {uart_port}: {reopen_error}"
                                )
                                if attempt < max_retries:
                                    time.sleep(0.5)
                                    continue
                                raise RuntimeError(
                                    f"I/O operation on closed file: Не удалось переоткрыть UART порт {uart_port} после {max_retries + 1} попыток: {reopen_error}"
                                )
                        else:
                            raise RuntimeError(
                                "I/O operation on closed file: Функция connect_to_uart_port недоступна"
                            )
                    else:
                        raise RuntimeError(
                            "I/O operation on closed file: UART порт не открыт"
                        )

                is_open = False
                try:
                    is_open = self.selected_uart.is_open
                except (ValueError, OSError, IOError) as e:
                    error_msg = str(e).lower()
                    if "closed" in error_msg or "operation on closed" in error_msg:
                        logger.warning(
                            f"Порт закрыт при проверке is_open (попытка {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        if attempt < max_retries:

                            port_name = uart_port or (
                                self.selected_uart.port
                                if hasattr(self.selected_uart, "port")
                                else None
                            )
                            if not port_name and self.selected:
                                port_name = detect_serial_port(self.selected)

                            if port_name and connect_to_uart_port:
                                try:
                                    self.close_uart()
                                    time.sleep(0.5 if sys.platform == "win32" else 0.2)
                                    self.selected_uart = connect_to_uart_port(port_name)
                                    if (
                                        self.selected_uart
                                        and self.selected_uart.is_open
                                    ):
                                        logger.info(
                                            f"UART порт {port_name} успешно переоткрыт после ошибки is_open"
                                        )
                                        continue
                                except Exception as reopen_error:
                                    logger.error(
                                        f"Ошибка при переоткрытии порта {port_name}: {reopen_error}"
                                    )
                                    if attempt < max_retries:
                                        time.sleep(0.5)
                                        continue

                            raise RuntimeError(
                                f"I/O operation on closed file: UART порт был закрыт: {e}"
                            )
                        raise RuntimeError(
                            f"I/O operation on closed file: UART порт был закрыт: {e}"
                        )
                    raise

                if not is_open:
                    logger.warning(
                        f"UART порт не открыт (попытка {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:

                        port_name = uart_port or (
                            self.selected_uart.port
                            if hasattr(self.selected_uart, "port")
                            else None
                        )
                        if not port_name and self.selected and detect_serial_port:
                            try:
                                port_name = detect_serial_port(self.selected)
                            except Exception as e:
                                logger.warning(
                                    f"Не удалось определить порт через detect_serial_port: {e}"
                                )

                        if port_name and connect_to_uart_port:
                            try:
                                self.close_uart()
                                time.sleep(0.5 if sys.platform == "win32" else 0.2)
                                self.selected_uart = connect_to_uart_port(port_name)
                                if self.selected_uart and self.selected_uart.is_open:
                                    logger.info(
                                        f"UART порт {port_name} успешно переоткрыт"
                                    )
                                    continue
                            except Exception as reopen_error:
                                logger.error(
                                    f"Ошибка при переоткрытии порта {port_name}: {reopen_error}"
                                )
                                if attempt < max_retries:
                                    time.sleep(0.5)
                                    continue

                        raise RuntimeError(
                            "I/O operation on closed file: UART порт не открыт"
                        )

                try:
                    logger.debug(
                        f"Попытка записи {len(data)} байт в UART порт (попытка {attempt + 1})..."
                    )
                    bytes_written = self.selected_uart.write(data)
                    logger.debug(f"Записано {bytes_written} байт, выполнение flush...")
                    self.selected_uart.flush()
                    logger.debug(f"UART запись успешна: {bytes_written} байт")
                    return bytes_written
                except (ValueError, OSError, IOError) as e:
                    error_msg = str(e).lower()
                    logger.warning(
                        f"Ошибка при записи в UART (попытка {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    if "closed" in error_msg or "operation on closed" in error_msg:
                        logger.warning(
                            f"Порт закрыт во время записи (попытка {attempt + 1}/{max_retries + 1}): {e}"
                        )
                        import traceback

                        logger.debug(
                            f"Трассировка ошибки записи: {traceback.format_exc()}"
                        )
                        if attempt < max_retries:

                            logger.info(
                                f"Попытка переоткрытия UART порта после ошибки записи (попытка {attempt + 1})..."
                            )
                            port_name = uart_port or (
                                self.selected_uart.port
                                if hasattr(self.selected_uart, "port")
                                else None
                            )
                            if not port_name and self.selected and detect_serial_port:
                                try:
                                    logger.debug(
                                        "Определение порта через detect_serial_port..."
                                    )
                                    port_name = detect_serial_port(self.selected)
                                    logger.debug(f"Определен порт: {port_name}")
                                except Exception as e:
                                    logger.warning(
                                        f"Не удалось определить порт через detect_serial_port: {e}"
                                    )

                            if port_name and connect_to_uart_port:
                                try:
                                    logger.info(
                                        f"Закрытие старого порта перед переоткрытием {port_name}..."
                                    )
                                    self.close_uart()
                                    time.sleep(0.5 if sys.platform == "win32" else 0.2)
                                    logger.info(f"Открытие порта {port_name}...")
                                    self.selected_uart = connect_to_uart_port(port_name)
                                    if (
                                        self.selected_uart
                                        and self.selected_uart.is_open
                                    ):
                                        logger.info(
                                            f"UART порт {port_name} успешно переоткрыт после ошибки записи"
                                        )
                                        continue
                                    else:
                                        logger.warning(
                                            f"Порт {port_name} открыт, но is_open=False"
                                        )
                                except Exception as reopen_error:
                                    logger.error(
                                        f"Ошибка при переоткрытии порта {port_name}: {reopen_error}"
                                    )
                                    import traceback

                                    logger.error(
                                        f"Трассировка ошибки переоткрытия: {traceback.format_exc()}"
                                    )
                                    if attempt < max_retries:
                                        time.sleep(0.5)
                                        continue
                            else:
                                logger.warning(
                                    f"Не удалось определить порт для переоткрытия: port_name={port_name}, connect_to_uart_port={connect_to_uart_port is not None}"
                                )

                            raise RuntimeError(
                                f"I/O operation on closed file: UART порт был закрыт во время записи: {e}"
                            )
                        raise RuntimeError(
                            f"I/O operation on closed file: UART порт был закрыт во время записи: {e}"
                        )

                    raise

            except RuntimeError:

                raise
            except Exception as e:
                logger.error(
                    f"Неожиданная ошибка при безопасной записи в UART (попытка {attempt + 1}/{max_retries + 1}): {e}"
                )
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                raise RuntimeError(
                    f"I/O operation on closed file: Неожиданная ошибка при записи в UART: {e}"
                )

        raise RuntimeError(
            f"I/O operation on closed file: Не удалось записать данные в UART после {max_retries + 1} попыток"
        )

    def close_uart(self):
        if self.selected_uart:
            try:
                port_name = (
                    self.selected_uart.port
                    if hasattr(self.selected_uart, "port")
                    else "unknown"
                )

                is_open = False
                try:
                    is_open = self.selected_uart.is_open
                except (ValueError, OSError, IOError) as e:
                    error_msg = str(e).lower()
                    if "closed" in error_msg or "operation on closed" in error_msg:
                        logger.debug(f"Порт уже был закрыт при проверке is_open: {e}")

                        self.selected_uart = None
                        return
                    else:

                        raise

                if is_open:
                    logger.info(f"закрытие UART порта {port_name}")
                    try:
                        if self.selected_uart.in_waiting > 0:
                            logger.info(
                                f"очистка входного буфера: {self.selected_uart.in_waiting} байт"
                            )
                            self.selected_uart.read(self.selected_uart.in_waiting)
                    except (ValueError, OSError, IOError) as e:
                        error_msg = str(e).lower()
                        if "closed" in error_msg or "operation on closed" in error_msg:
                            logger.debug(f"Порт закрыт при чтении буфера: {e}")
                        else:
                            logger.warning(f"Ошибка при чтении буфера: {e}")

                    try:
                        self.selected_uart.reset_input_buffer()
                        self.selected_uart.reset_output_buffer()
                    except (ValueError, OSError, IOError) as e:
                        error_msg = str(e).lower()
                        if "closed" in error_msg or "operation on closed" in error_msg:
                            logger.debug(f"Порт закрыт при очистке буферов: {e}")
                        else:
                            logger.warning(f"Ошибка при очистке буферов: {e}")

                    try:
                        if self.selected_uart.in_waiting > 0:
                            remaining = self.selected_uart.read(
                                self.selected_uart.in_waiting
                            )
                            logger.info(
                                f"дополнительная очистка: {len(remaining)} байт"
                            )
                    except (ValueError, OSError, IOError) as e:
                        error_msg = str(e).lower()
                        if "closed" in error_msg or "operation on closed" in error_msg:
                            logger.debug(f"Порт закрыт при дополнительной очистке: {e}")
                        else:
                            logger.warning(f"Ошибка при дополнительной очистке: {e}")

                    try:
                        self.selected_uart.close()
                    except (ValueError, OSError, IOError) as e:
                        error_msg = str(e).lower()
                        if "closed" in error_msg or "operation on closed" in error_msg:
                            logger.debug(f"Порт уже был закрыт при вызове close(): {e}")
                        else:
                            logger.warning(f"Ошибка при закрытии порта: {e}")

                    import time
                    import sys

                    if sys.platform == "win32":
                        time.sleep(0.5)
                    else:
                        time.sleep(0.1)
                    logger.info("UART порт закрыт и буферы очищены")

                self.selected_uart = None
            except (ValueError, OSError, IOError) as e:
                error_msg = str(e).lower()
                if "closed" in error_msg or "operation on closed" in error_msg:
                    logger.debug(f"Порт уже был закрыт: {e}")
                else:
                    logger.warning(f"ошибка при закрытии UART порта: {e}")
                self.selected_uart = None
            except Exception as e:
                logger.warning(f"Неожиданная ошибка при закрытии UART порта: {e}")
                self.selected_uart = None

    def find_devices(self):
        self.devices = []

        try:
            backend = _init_usb_backend()
        except RuntimeError as e:
            raise RuntimeError(f"Ошибка USB backend: {e}")

        for vid, pid in STLINK_IDS:
            if backend is not None:
                devices_list = usb.core.find(
                    find_all=True, idVendor=vid, idProduct=pid, backend=backend
                )
            else:
                devices_list = usb.core.find(find_all=True, idVendor=vid, idProduct=pid)

            for device in devices_list:
                serial = None
                bus = None
                address = None
                device.set_configuration()
                serial = usb.util.get_string(device, device.iSerialNumber)
                bus = device.bus
                address = device.address

                device_info = {
                    "type": "ST-Link",
                    "name": f"ST-Link {vid:04X}:{pid:04X}",
                    "vid": vid,
                    "pid": pid,
                }

                if serial:
                    device_info["serial"] = serial
                    device_info["name"] = f"ST-Link {vid:04X}:{pid:04X} SN:{serial}"
                    logger.info(f"Найден ST-Link с серийным номером: {serial}")

                if bus is not None:
                    device_info["usb_bus"] = bus
                if address is not None:
                    device_info["usb_address"] = address

                self.devices.append(device_info)

        return self.devices

    def show_devices(self):
        if not self.devices:
            return []
        return [f"{i}. {dev['name']}" for i, dev in enumerate(self.devices, 1)]

    def select_device(self, num):
        if 1 <= num <= len(self.devices):
            self.selected = self.devices[num - 1]
            return True
        return False

    def write_bytes(self, data, address=DEFAULT_FLASH_ADDRESS):
        if not self.selected:
            return False, "Устройство не выбрано"

        device_type = self.selected["type"]
        success = False
        last_error = None
        attempted_methods = []

        if device_type == "ST-Link":

            stlink_lib_spec = importlib.util.find_spec(
                "stm32_programmer.programmers.stlink_lib"
            )
            if stlink_lib_spec is not None:
                from .stlink_lib import STLinkProgrammerLib

                attempted_methods.append("STLinkProgrammerLib")
                lib_programmer = STLinkProgrammerLib(self.selected)
                success = lib_programmer.write_bytes(data, address)
                if success:
                    logger.info("запись выполнена через STLinkProgrammerLib")
                else:
                    last_error = "STLinkProgrammerLib: запись не удалась"

                if hasattr(lib_programmer, "stlink") and lib_programmer.stlink:
                    lib_programmer.stlink.disconnect()
            else:
                logger.debug(
                    "STLinkProgrammerLib не доступен, используется альтернативный метод"
                )
                attempted_methods.append("STLinkProgrammerLib (не доступен)")

        if device_type == "ST-Link" and not success:
            from .stlink_cube import STLinkProgrammerCube

            programmer = STLinkProgrammerCube(self.selected)
            if programmer.cube_path:
                attempted_methods.append("STM32CubeProgrammer")
                logger.info(
                    f"попытка записи через STM32CubeProgrammer: {programmer.cube_path}"
                )
                logger.info(f"запись {len(data)} байт по адресу {hex(address)}")
                success = programmer.write_bytes(data, address)
                if success:
                    logger.info("запись выполнена через STM32CubeProgrammer")
                else:
                    last_error = "STM32CubeProgrammer: запись не удалась"
                    logger.warning(f"запись через STM32CubeProgrammer не удалась")
            else:
                attempted_methods.append("STM32CubeProgrammer (не найден)")
                last_error = "STM32CubeProgrammer: не найден"
                success = False

        if device_type == "ST-Link" and not success:
            from .stlink_openocd import STLinkProgrammerOpenOCD

            programmer = STLinkProgrammerOpenOCD(self.selected)
            if programmer.openocd_path:
                attempted_methods.append("OpenOCD")
                logger.info(f"попытка записи через OpenOCD: {programmer.openocd_path}")
                logger.info(f"запись {len(data)} байт по адресу {hex(address)}")
                success = programmer.write_bytes(data, address)
                if success:
                    logger.info("запись выполнена через OpenOCD")
                else:
                    last_error = "OpenOCD: запись не удалась"
                    logger.warning(f"запись через OpenOCD не удалась")
            else:
                attempted_methods.append("OpenOCD (не найден)")
                last_error = "OpenOCD: не найден"
                success = False

        if device_type == "ST-Link" and not success:
            from .stlink import STLinkProgrammer

            attempted_methods.append("STLinkProgrammer (прямой USB)")
            logger.info("=" * 80)
            logger.info("ПОПЫТКА ЗАПИСИ ЧЕРЕЗ ПРЯМОЙ USB ДОСТУП (STLinkProgrammer)")
            logger.info(f"Размер данных: {len(data)} байт")
            logger.info(f"Адрес записи: {hex(address)}")
            logger.info(f"Устройство: {self.selected}")
            logger.info("=" * 80)
            programmer = STLinkProgrammer(self.selected)
            try:
                try:
                    logger.info("Вызов programmer.write_bytes()...")
                    write_result = programmer.write_bytes(data, address)
                    logger.info(
                        f"programmer.write_bytes() вернул результат: {type(write_result)}, значение: {write_result}"
                    )

                    if isinstance(write_result, tuple):
                        success, error_details = write_result
                        logger.info(
                            f"Результат записи (кортеж): success={success}, error_details={error_details}"
                        )
                    else:
                        success = write_result
                        error_details = None
                        logger.info(f"Результат записи (bool): success={success}")
                except RuntimeError as e:
                    error_msg = str(e)
                    logger.error(f"Пойман RuntimeError в base.write_bytes: {error_msg}")
                    if "I/O operation on closed file" in error_msg:
                        logger.error(
                            f"КРИТИЧЕСКАЯ ОШИБКА: USB устройство закрыто при записи через STLinkProgrammer: {e}"
                        )
                        import traceback

                        logger.error(
                            f"Трассировка RuntimeError в base.write_bytes: {traceback.format_exc()}"
                        )
                        raise RuntimeError(
                            f"I/O operation on closed file: USB устройство было закрыто при записи через STLinkProgrammer: {e}"
                        )
                    else:
                        logger.error(
                            f"RuntimeError при записи через STLinkProgrammer: {e}"
                        )
                        raise
                except Exception as e:
                    error_msg = str(e)
                    if (
                        "closed" in error_msg.lower()
                        or "operation on closed" in error_msg.lower()
                    ):
                        logger.error(
                            f"КРИТИЧЕСКАЯ ОШИБКА: USB устройство закрыто при записи через STLinkProgrammer: {e}"
                        )
                        import traceback

                        logger.error(f"Трассировка: {traceback.format_exc()}")
                        raise RuntimeError(
                            f"I/O operation on closed file: USB устройство было закрыто при записи через STLinkProgrammer: {e}"
                        )
                    else:
                        logger.error(
                            f"Неожиданная ошибка при записи через STLinkProgrammer: {e}"
                        )
                        import traceback

                        logger.error(f"Трассировка: {traceback.format_exc()}")
                        raise RuntimeError(
                            f"Ошибка при записи через STLinkProgrammer: {e}"
                        )

                if not success and hasattr(programmer, "reconnect"):
                    logger.warning(
                        f"Запись не удалась (success={success}), попытка переподключения..."
                    )
                    try:
                        logger.info("Вызов programmer.reconnect()...")
                        if programmer.reconnect():
                            logger.info(
                                "Переподключение успешно, повторная попытка записи..."
                            )
                            time.sleep(1)
                            try:
                                logger.info(
                                    "Повторный вызов programmer.write_bytes() после переподключения..."
                                )
                                write_result = programmer.write_bytes(data, address)
                                logger.info(
                                    f"Повторный вызов вернул результат: {type(write_result)}, значение: {write_result}"
                                )
                                if isinstance(write_result, tuple):
                                    success, error_details = write_result
                                else:
                                    success = write_result
                                    error_details = None
                            except RuntimeError as e:
                                error_msg = str(e)
                                if "I/O operation on closed file" in error_msg:
                                    logger.error(
                                        f"КРИТИЧЕСКАЯ ОШИБКА: USB устройство закрыто при повторной записи через STLinkProgrammer: {e}"
                                    )
                                    import traceback

                                    logger.error(
                                        f"Трассировка: {traceback.format_exc()}"
                                    )
                                    raise RuntimeError(
                                        f"I/O operation on closed file: USB устройство было закрыто при повторной записи через STLinkProgrammer: {e}"
                                    )
                                raise
                            except Exception as e:
                                error_msg = str(e)
                                if (
                                    "closed" in error_msg.lower()
                                    or "operation on closed" in error_msg.lower()
                                ):
                                    logger.error(
                                        f"КРИТИЧЕСКАЯ ОШИБКА: USB устройство закрыто при повторной записи через STLinkProgrammer: {e}"
                                    )
                                    import traceback

                                    logger.error(
                                        f"Трассировка: {traceback.format_exc()}"
                                    )
                                    raise RuntimeError(
                                        f"I/O operation on closed file: USB устройство было закрыто при повторной записи через STLinkProgrammer: {e}"
                                    )
                                raise
                    except RuntimeError:
                        raise
                    except Exception as reconnect_error:
                        logger.error(
                            f"Ошибка при переподключении и повторной записи: {reconnect_error}"
                        )
                        import traceback

                        logger.error(f"Трассировка: {traceback.format_exc()}")
                        raise RuntimeError(
                            f"Ошибка при переподключении и повторной записи: {reconnect_error}"
                        )

                if success:
                    logger.info("запись выполнена через прямой USB доступ")
                else:
                    last_error = (
                        "STLinkProgrammer: запись не удалась (не удалось подключиться к целевому устройству)\n"
                        "Возможные причины:\n"
                        f"  - Возможно у вас где-то открыт STM32CubeProgrammer и он занял устройство {get_icon_emoji_fallback('thinking')}\n"
                        "  - Устройство не подключено или не включено\n"
                        "  - Проблемы с драйверами ST-Link\n"
                        "Решение: закройте STM32CubeProgrammer и попробуйте снова"
                    )
                    logger.warning(f"запись через прямой USB доступ не удалась")
            finally:
                if hasattr(programmer, "disconnect"):
                    programmer.disconnect()

        if device_type != "ST-Link":
            return False, "Неподдерживаемый тип устройства"

        if success:
            logger.info("проверка записи...")
            time.sleep(1.0)
            verify_result, verify_details = self._verify_write(data, address)
            if verify_result:
                logger.info("проверка записи успешна")
                return True, None
            else:
                error_msg = f"Запись выполнена, но проверка не прошла. {verify_details}"
                logger.warning(error_msg)
                return False, error_msg

        error_details = []
        if attempted_methods:
            error_details.append(f"Попробованы методы: {', '.join(attempted_methods)}")
        if last_error:
            error_details.append(f"Последняя ошибка: {last_error}")

        error_msg = (
            " | ".join(error_details) if error_details else "Неизвестная ошибка записи"
        )

        if last_error:
            logger.error(f"ошибка записи: {last_error}")
        return False, error_msg

    def _verify_write(self, expected_data, address):
        try:
            device_type = self.selected["type"]

            read_size = len(expected_data) + 1024

            if device_type == "ST-Link":
                logger.info(f"попытка чтения данных через STM32CubeProgrammer...")
                try:
                    from .stlink_cube import STLinkProgrammerCube

                    programmer = STLinkProgrammerCube(self.selected)
                    if programmer.cube_path:
                        logger.info(f"чтение {read_size} байт с адреса {hex(address)}")
                        read_data = programmer.read_bytes(read_size, address)
                        if read_data:
                            logger.info(
                                f"прочитано {len(read_data)} байт через STM32CubeProgrammer"
                            )
                        else:
                            logger.warning(
                                "не удалось прочитать данные через STM32CubeProgrammer"
                            )
                    else:
                        read_data = b""
                        logger.warning("STM32CubeProgrammer не найден")
                except Exception as e:
                    read_data = b""
                    logger.warning(f"ошибка при чтении через STM32CubeProgrammer: {e}")

                if not read_data:
                    logger.info("попытка чтения данных через OpenOCD...")
                    try:
                        from .stlink_openocd import STLinkProgrammerOpenOCD

                        programmer = STLinkProgrammerOpenOCD(self.selected)
                        if programmer.openocd_path:
                            logger.info(
                                f"чтение {read_size} байт с адреса {hex(address)}"
                            )
                            read_data = programmer.read_bytes(read_size, address)
                            if read_data:
                                logger.info(
                                    f"прочитано {len(read_data)} байт через OpenOCD"
                                )
                            else:
                                logger.warning(
                                    "не удалось прочитать данные через OpenOCD"
                                )
                        else:
                            logger.warning("OpenOCD не найден")
                    except Exception as e:
                        read_data = b""
                        logger.warning(f"ошибка при чтении через OpenOCD: {e}")

                if not read_data:
                    logger.info("попытка чтения данных через прямой USB доступ...")
                    try:
                        from .stlink import STLinkProgrammer

                        programmer = STLinkProgrammer(self.selected)
                        try:
                            logger.info(
                                f"чтение {read_size} байт с адреса {hex(address)}"
                            )
                            read_data = programmer.read_bytes(read_size, address)
                            if read_data:
                                logger.info(
                                    f"прочитано {len(read_data)} байт через прямой USB доступ"
                                )
                            else:
                                logger.warning(
                                    "не удалось прочитать данные через прямой USB доступ"
                                )
                        finally:

                            if hasattr(programmer, "disconnect"):
                                programmer.disconnect()
                    except Exception as e:
                        read_data = b""
                        logger.warning(
                            f"ошибка при чтении через прямой USB доступ: {e}"
                        )

                if not read_data:
                    logger.error("не удалось прочитать данные ни одним из методов")
                    logger.error("проверка записи невозможна - данные не прочитаны")
                    return False, "Не удалось прочитать данные для проверки записи"

            if not read_data:
                logger.error("данные не прочитаны, проверка невозможна")
                return False, "Данные не прочитаны, проверка невозможна"

            while len(read_data) > 0 and read_data[-1] == 0xFF:
                read_data = read_data[:-1]

            expected_preview = expected_data[:100]
            read_preview = read_data[:100] if len(read_data) >= 100 else read_data

            logger.info("=" * 80)
            logger.info("отладка проверки записи:")
            logger.info(f"адрес записи: {hex(address)}")
            logger.info(
                f"длина данных котрые хотели записать: {len(expected_data)} байт"
            )
            logger.info(f"длина данных после чтения      : {len(read_data)} байт")
            logger.info(
                f"первые 100 байт ожидаемых данных    : {expected_preview.hex()}"
            )
            logger.info(f"первые 100 байт прочитанных данных  : {read_preview.hex()}")

            read_data_trimmed = read_data[: len(expected_data)]

            if read_data_trimmed == expected_data:
                logger.info("проверка записи:  данные совпадают")
                logger.info("=" * 80)
                return True, None
            else:
                logger.info("проверка записи: данные не совпадают")
                first_mismatch_pos = None
                first_mismatch_expected = None
                first_mismatch_actual = None

                for i in range(min(len(expected_data), len(read_data_trimmed))):
                    if expected_data[i] != read_data_trimmed[i]:
                        first_mismatch_pos = i
                        first_mismatch_expected = expected_data[i]
                        first_mismatch_actual = read_data_trimmed[i]
                        logger.info(
                            f"первое несовпадение на позиции {i}: ожидали 0x{expected_data[i]:02X},  получили 0x{read_data_trimmed[i]:02X}"
                        )
                        break

                details_parts = []
                if first_mismatch_pos is not None:
                    details_parts.append(
                        f"Первое несовпадение на позиции {first_mismatch_pos}: ожидали 0x{first_mismatch_expected:02X}, получили 0x{first_mismatch_actual:02X}"
                    )

                if len(read_data_trimmed) != len(expected_data):
                    logger.info(
                        f"длины не совпадают: ожидали {len(expected_data)},  получили {len(read_data_trimmed)}"
                    )
                    details_parts.append(
                        f"Длины не совпадают: ожидали {len(expected_data)} байт, получили {len(read_data_trimmed)} байт"
                    )

                logger.info("=" * 80)
                details = (
                    " | ".join(details_parts)
                    if details_parts
                    else "Данные не совпадают с ожидаемыми"
                )
                return False, details

        except Exception as e:
            import traceback

            error_type = type(e).__name__
            error_message = str(e)
            traceback_str = traceback.format_exc()

            logger.error("=" * 80)
            logger.error("ошибка при проверке записи:")
            logger.error(f"тип ошибки: {error_type}")
            logger.error(f"сообщение об ошибке: {error_message}")
            logger.error(f"адрес записи: {hex(address)}")
            logger.error(f"размер данных для проверки: {len(expected_data)} байт")
            if "read_size" in locals():
                logger.error(f"размер данных для чтения: {read_size} байт")
            else:
                logger.error("размер данных для чтения: не определен")

            if self.selected:
                logger.error(
                    f"выбранное устройство: {self.selected.get('name', 'неизвестно')}"
                )
                logger.error(
                    f"VID: 0x{self.selected.get('vid', 0):04X}, PID: 0x{self.selected.get('pid', 0):04X}"
                )

            if expected_data:
                expected_preview = expected_data[:100]
                logger.error(
                    f"первые 100 байт ожидаемых данных (hex): {expected_preview.hex()}"
                )

            if "read_data" in locals() and read_data:
                read_preview = read_data[:100] if len(read_data) >= 100 else read_data
                logger.error(
                    f"первые 100 байт прочитанных данных (hex): {read_preview.hex()}"
                )
                logger.error(f"длина прочитанных данных: {len(read_data)} байт")

            logger.error("трассировка стека:")
            for line in traceback_str.strip().split("\n"):
                logger.error(f"  {line}")
            logger.error("=" * 80)

            return False, f"Ошибка при проверке записи: {error_type}: {error_message}"

    def clear_memory(self, address, size):
        if not self.selected:
            return False

        device_type = self.selected["type"]

        if device_type == "ST-Link":
            try:
                from .stlink_cube import STLinkProgrammerCube

                programmer = STLinkProgrammerCube(self.selected)
                if programmer.cube_path:
                    return programmer.clear_memory(address, size)
            except Exception as e:
                pass

            try:
                from .stlink_openocd import STLinkProgrammerOpenOCD

                programmer = STLinkProgrammerOpenOCD(self.selected)
                if programmer.openocd_path:
                    return programmer.clear_memory(address, size)
            except Exception as e:
                pass

            from programmer_stlink import STLinkProgrammer

            programmer = STLinkProgrammer(self.selected)
            return programmer.clear_memory(address, size)

    def read_memory_hex(self, address, size):
        if not self.selected:
            return b""

        device_type = self.selected["type"]

        if device_type == "ST-Link":
            try:
                from .stlink_cube import STLinkProgrammerCube

                programmer = STLinkProgrammerCube(self.selected)
                if programmer.cube_path:
                    data = programmer.read_bytes(size, address)
                else:
                    data = b""
            except:
                data = b""

            if not data:
                try:
                    from .stlink_openocd import STLinkProgrammerOpenOCD

                    programmer = STLinkProgrammerOpenOCD(self.selected)
                    if programmer.openocd_path:
                        data = programmer.read_bytes(size, address)
                except:
                    data = b""

            if not data:
                try:
                    from .stlink import STLinkProgrammer

                    programmer = STLinkProgrammer(self.selected)
                    try:
                        data = programmer.read_bytes(size, address)
                    finally:

                        if hasattr(programmer, "disconnect"):
                            programmer.disconnect()
                except:
                    data = b""

            if not data:
                return b""

        return data

    def send_command_uart(self, command, expected_response):
        import sys

        logger.debug("=" * 60)
        logger.debug("send_command_uart вызван")
        logger.debug(f"платформа: {sys.platform}")

        if isinstance(command, str):
            original_command = command
            command = command.strip().encode("utf-8")
            if original_command != original_command.strip():
                logger.warning(
                    f"обнаружены пробелы в команде! было: '{original_command}', стало: '{original_command.strip()}'"
                )
        elif isinstance(command, bytes):

            if command.startswith(b" "):
                logger.warning(
                    f"обнаружены пробелы в начале команды (bytes)! было: {command.hex()}"
                )
                command = command.lstrip()
            if command.endswith(b" "):
                logger.warning(
                    f"обнаружены пробелы в конце команды (bytes)! было: {command.hex()}"
                )
                command = command.rstrip()

        if isinstance(expected_response, str):
            original_response = expected_response
            expected_response = expected_response.strip().encode("utf-8")
            if original_response != original_response.strip():
                logger.warning(
                    f"обнаружены пробелы в ожидаемом ответе! было: '{original_response}', стало: '{original_response.strip()}'"
                )
        elif isinstance(expected_response, bytes):

            if expected_response.startswith(b" ") or expected_response.endswith(b" "):
                logger.warning(
                    f"обнаружены пробелы в ожидаемом ответе (bytes)! было: {expected_response.hex()}"
                )
            expected_response = expected_response.strip()

        if (
            not command.endswith(b"\n")
            and not command.endswith(b"\r")
            and not command.endswith(b"\r\n")
        ):
            from stm32_programmer.utils.uart_settings import UARTSettings

            uart_settings = UARTSettings()
            line_ending_bytes = uart_settings.get_line_ending_bytes()
            command = command + line_ending_bytes
            logger.debug(f"добавлен line ending: {line_ending_bytes.hex()}")

        logger.debug(f"команда (text): {command.decode('utf-8', errors='replace')}")
        logger.debug(f"команда (hex): {command.hex()}")

        if command.startswith(b" "):
            logger.error(f"ОШИБКА: команда начинается с пробела! hex: {command.hex()}")
        logger.debug(
            f"ожидаемый ответ (text): {expected_response.decode('utf-8', errors='replace')}"
        )
        logger.debug(f"ожидаемый ответ (hex): {expected_response.hex()}")

        if not self.selected_uart:
            logger.error("selected_uart is None!")
            raise RuntimeError(
                "I/O operation on closed file: UART порт не инициализирован (selected_uart is None)"
            )

        try:
            is_open = self.selected_uart.is_open
        except (ValueError, OSError, IOError, AttributeError) as e:
            error_msg = str(e).lower()
            if (
                "closed" in error_msg
                or "operation on closed" in error_msg
                or "attribute" in error_msg
            ):
                logger.error(f"Порт закрыт или недоступен при проверке is_open: {e}")

                self.selected_uart = None
                raise RuntimeError(
                    f"I/O operation on closed file: UART порт был закрыт: {e}"
                )
            raise

        if not is_open:
            logger.error(
                f"uart порт не открыт! порт: {self.selected_uart.port if self.selected_uart else 'None'}"
            )
            raise RuntimeError("I/O operation on closed file: UART порт не открыт")

        logger.debug(f"uart порт: {self.selected_uart.port}")
        try:
            logger.debug(f"uart timeout: {self.selected_uart.timeout}")
        except (ValueError, OSError, IOError, PermissionError, SerialException) as e:
            error_msg = str(e).lower()
            if (
                "permission" in error_msg
                or "доступ" in error_msg
                or "access" in error_msg
            ):
                logger.error(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Нет доступа к UART порту (возможно, порт занят другим процессом): {e}"
                )
                raise RuntimeError(
                    f"I/O operation on closed file: Нет доступа к UART порту (возможно, порт занят STM32CubeProgrammer или другим процессом): {e}"
                )
            raise
        except Exception as e:
            logger.warning(f"Ошибка при получении timeout: {e}")

        try:
            logger.debug(f"uart in_waiting до очистки: {self.selected_uart.in_waiting}")
        except (ValueError, OSError, IOError, PermissionError, SerialException) as e:
            error_msg = str(e).lower()
            if (
                "permission" in error_msg
                or "доступ" in error_msg
                or "access" in error_msg
            ):
                logger.error(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Нет доступа к UART порту при проверке in_waiting (возможно, порт занят другим процессом): {e}"
                )
                raise RuntimeError(
                    f"I/O operation on closed file: Нет доступа к UART порту (возможно, порт занят STM32CubeProgrammer или другим процессом): {e}"
                )
            logger.warning(f"Ошибка при проверке in_waiting: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при проверке in_waiting: {e}")

        try:

            if not self.selected_uart.is_open:
                logger.error("UART порт закрыт во время выполнения команды")
                return False
            try:
                bytes_before_reset = self.selected_uart.in_waiting
            except (
                ValueError,
                OSError,
                IOError,
                PermissionError,
                SerialException,
            ) as e:
                error_msg = str(e).lower()
                if (
                    "permission" in error_msg
                    or "доступ" in error_msg
                    or "access" in error_msg
                ):
                    logger.error(
                        f"КРИТИЧЕСКАЯ ОШИБКА: Нет доступа к UART порту при проверке in_waiting (возможно, порт занят другим процессом): {e}"
                    )
                    raise RuntimeError(
                        f"I/O operation on closed file: Нет доступа к UART порту (возможно, порт занят STM32CubeProgrammer или другим процессом): {e}"
                    )
                raise
            self.selected_uart.reset_input_buffer()
            logger.debug(f"буфер очищен, было байт: {bytes_before_reset}")
        except (ValueError, OSError, IOError, PermissionError, SerialException) as e:
            error_msg = str(e).lower()
            if (
                "permission" in error_msg
                or "доступ" in error_msg
                or "access" in error_msg
                or "clearcommerror" in error_msg
            ):
                logger.error(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Нет доступа к UART порту при очистке буфера (возможно, порт занят другим процессом): {e}"
                )
                raise RuntimeError(
                    f"I/O operation on closed file: Нет доступа к UART порту (возможно, порт занят STM32CubeProgrammer или другим процессом): {e}"
                )
            elif "closed" in error_msg or "operation on closed" in error_msg:
                logger.error(f"Порт закрыт во время очистки буфера: {e}")
                raise RuntimeError(
                    f"I/O operation on closed file: UART порт был закрыт во время выполнения операции"
                )
            else:
                logger.warning(f"ошибка при очистке буфера: {e}")
            return False
        except Exception as e:
            error_msg = str(e).lower()
            if (
                "permission" in error_msg
                or "доступ" in error_msg
                or "access" in error_msg
                or "clearcommerror" in error_msg
            ):
                logger.error(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Нет доступа к UART порту при очистке буфера (возможно, порт занят другим процессом): {e}"
                )
                raise RuntimeError(
                    f"I/O operation on closed file: Нет доступа к UART порту (возможно, порт занят STM32CubeProgrammer или другим процессом): {e}"
                )
            logger.warning(f"ошибка при очистке буфера: {e}")
            return False

        try:

            is_open = False
            try:
                is_open = self.selected_uart.is_open
            except (ValueError, OSError, IOError) as e:
                error_msg = str(e).lower()
                if "closed" in error_msg or "operation on closed" in error_msg:
                    logger.error(
                        f"Порт закрыт при проверке is_open перед записью команды: {e}"
                    )
                    raise RuntimeError(
                        f"I/O operation on closed file: UART порт был закрыт: {e}"
                    )
                raise

            if not is_open:
                logger.error("UART порт закрыт перед записью команды")
                raise RuntimeError("I/O operation on closed file: UART порт не открыт")

            write_start = time.time()
            try:

                uart_port = None
                if hasattr(self.selected_uart, "port"):
                    uart_port = self.selected_uart.port
                elif self.selected:
                    from stm32_programmer.programmers.core import detect_serial_port

                    uart_port = detect_serial_port(self.selected)

                bytes_written = self._safe_uart_write(
                    command, max_retries=2, uart_port=uart_port
                )
                write_duration = time.time() - write_start
                logger.debug(
                    f"команда записана: {bytes_written} байт за {write_duration:.4f} сек"
                )
            except RuntimeError as e:

                raise
            except (ValueError, OSError, IOError) as e:
                error_msg = str(e).lower()
                if "closed" in error_msg or "operation on closed" in error_msg:
                    logger.error(f"Порт закрыт во время записи команды: {e}")
                    import traceback

                    logger.error(f"трассировка: {traceback.format_exc()}")
                    raise RuntimeError(
                        f"I/O operation on closed file: UART порт был закрыт во время записи команды"
                    )
                else:
                    logger.error(f"ошибка при записи команды: {e}")
                import traceback

                logger.error(f"трассировка: {traceback.format_exc()}")
                return False
            except Exception as e:
                logger.error(f"ошибка при записи команды: {e}")
                import traceback

                logger.error(f"трассировка: {traceback.format_exc()}")
                return False
        except RuntimeError:

            raise
        except (ValueError, OSError, IOError) as e:
            error_msg = str(e).lower()
            if "closed" in error_msg or "operation on closed" in error_msg:
                logger.error(f"Порт закрыт во время записи команды: {e}")
                import traceback

                logger.error(f"трассировка: {traceback.format_exc()}")
                raise RuntimeError(
                    f"I/O operation on closed file: UART порт был закрыт во время записи команды"
                )
            else:
                logger.error(f"ошибка при записи команды: {e}")
            import traceback

            logger.error(f"трассировка: {traceback.format_exc()}")
            return False
        except Exception as e:
            logger.error(f"ошибка при записи команды: {e}")
            import traceback

            logger.error(f"трассировка: {traceback.format_exc()}")
            return False

        time.sleep(0.01)

        response = None
        buffer = b""

        port_timeout = (
            self.selected_uart.timeout
            if self.selected_uart
            else (3.0 if sys.platform == "win32" else 2.0)
        )
        max_wait_time = (
            port_timeout
            if port_timeout > 0
            else (3.0 if sys.platform == "win32" else 4.0)
        )
        start_time = time.time()
        logger.debug(
            f"максимальное время ожидания: {max_wait_time} сек (таймаут порта: {port_timeout})"
        )

        try:
            read_attempts = 0
            while (time.time() - start_time) < max_wait_time:
                try:
                    is_open = self.selected_uart.is_open
                except (ValueError, OSError, IOError) as e:
                    error_msg = str(e).lower()
                    if "closed" in error_msg or "operation on closed" in error_msg:
                        logger.warning(
                            f"Порт закрыт при проверке is_open во время чтения: {e}"
                        )
                        raise RuntimeError(
                            f"I/O operation on closed file: UART порт был закрыт во время чтения ответа: {e}"
                        )
                    raise

                if not is_open:
                    logger.warning("UART порт закрыт во время чтения ответа")
                    break

                elapsed = time.time() - start_time
                read_attempts += 1

                try:
                    if self.selected_uart.in_waiting > 0:
                        bytes_to_read = self.selected_uart.in_waiting
                        logger.debug(
                            f"попытка {read_attempts}: доступно {bytes_to_read} байт, прошло {elapsed:.3f} сек"
                        )

                        data = self.selected_uart.read(bytes_to_read)
                        if data:
                            buffer += data
                            logger.debug(
                                f"прочитано {len(data)} байт, всего в буфере: {len(buffer)} байт"
                            )
                            logger.debug(f"данные (hex): {data.hex()[:100]}...")
                            logger.debug(
                                f"данные (text): {data.decode('utf-8', errors='replace')[:100]}"
                            )

                            if b"\n" in buffer or b"\r" in buffer:
                                logger.debug(
                                    "найден символ конца строки, прерываем чтение"
                                )
                                break

                            if expected_response in buffer:
                                logger.debug(
                                    "найден ожидаемый ответ в буфере, прерываем чтение"
                                )
                                break
                    else:
                        if read_attempts % 50 == 0:
                            logger.debug(
                                f"попытка {read_attempts}: нет данных, прошло {elapsed:.3f} сек"
                            )
                except (ValueError, OSError, IOError) as e:
                    error_msg = str(e).lower()
                    if "closed" in error_msg or "operation on closed" in error_msg:
                        logger.warning(f"Порт закрыт во время чтения: {e}")
                        raise RuntimeError(
                            f"I/O operation on closed file: UART порт был закрыт во время чтения ответа"
                        )
                    else:
                        logger.warning(f"Ошибка при чтении: {e}")
                        break

                time.sleep(0.01)

            total_time = time.time() - start_time
            logger.debug(
                f"чтение завершено за {total_time:.3f} сек, попыток: {read_attempts}"
            )

            if buffer:
                response = buffer.strip()
                response = response.rstrip(b"\r\n").rstrip(b"\n\r")
                logger.debug(
                    f"обработанный ответ (text): {response.decode('utf-8', errors='replace')}"
                )
                logger.debug(f"обработанный ответ (hex): {response.hex()}")
            else:
                logger.warning("буфер пуст после чтения")

        except serial.SerialException as read_error:
            logger.error(f"ошибка чтения ответа от UART: {read_error}")
            import traceback

            logger.error(f"трассировка: {traceback.format_exc()}")
            return False
        except Exception as e:
            logger.error(f"ошибка при чтении: {e}")
            import traceback

            logger.error(f"трассировка: {traceback.format_exc()}")
            return False

        if response == expected_response:
            logger.info(
                f"получен ответ от UART: {response.decode('utf-8', errors='replace')}"
            )
            logger.debug("=" * 60)
            return True
        else:
            display_response = (
                response.decode("utf-8", errors="replace") if response else "нет ответа"
            )
            logger.warning(
                f"не получено ожидаемого ответа от UART. "
                f"ожидали '{expected_response.decode('utf-8')}', получили '{display_response}'."
            )

            if sys.platform == "win32":
                logger.warning("детальная диагностика для Windows:")
                if response:
                    logger.warning(f"сырой ответ (hex): {response.hex()}")
                    logger.warning(f"ожидаемый ответ (hex): {expected_response.hex()}")
                    logger.warning(
                        f"длина ответа: {len(response)}, ожидалось: {len(expected_response)}"
                    )
                    if len(response) == len(expected_response):
                        for i, (r, e) in enumerate(zip(response, expected_response)):
                            if r != e:
                                logger.warning(
                                    f"первое несовпадение на позиции {i}: получили 0x{r:02X}, ожидали 0x{e:02X}"
                                )
                                break
                else:
                    logger.warning("ответ пустой")
                    if self.selected_uart:
                        try:
                            logger.warning(
                                f"uart in_waiting после чтения: {self.selected_uart.in_waiting}"
                            )
                        except (
                            ValueError,
                            OSError,
                            IOError,
                            PermissionError,
                            SerialException,
                        ) as e:
                            error_msg = str(e).lower()
                            if (
                                "permission" in error_msg
                                or "доступ" in error_msg
                                or "access" in error_msg
                            ):
                                logger.error(
                                    f"КРИТИЧЕСКАЯ ОШИБКА: Нет доступа к UART порту при проверке in_waiting после чтения (возможно, порт занят другим процессом): {e}"
                                )
                                raise RuntimeError(
                                    f"I/O operation on closed file: Нет доступа к UART порту (возможно, порт занят STM32CubeProgrammer или другим процессом): {e}"
                                )
                            logger.warning(
                                f"Ошибка при проверке in_waiting после чтения: {e}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Ошибка при проверке in_waiting после чтения: {e}"
                            )
            logger.debug("=" * 60)
            return False
