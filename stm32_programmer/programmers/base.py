import usb.core
import usb.backend.libusb1
import usb.backend.libusb0
import usb.backend.openusb
import serial
import time
import os
import sys
import logging

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


class BaseProgrammer:
    def __init__(self):
        self.devices = []
        self.selected = None
        self.selected_uart = None

    def find_devices(self):
        self.devices = []

        try:
            backend = _init_usb_backend()
        except RuntimeError as e:
            raise RuntimeError(f"Ошибка USB backend: {e}")

        for vid, pid in STLINK_IDS:
            try:
                if backend is not None:
                    devices_list = usb.core.find(
                        find_all=True, idVendor=vid, idProduct=pid, backend=backend
                    )
                else:
                    devices_list = usb.core.find(
                        find_all=True, idVendor=vid, idProduct=pid
                    )

                for device in devices_list:
                    try:
                        serial = None
                        bus = None
                        address = None
                        try:
                            device.set_configuration()
                            serial = usb.util.get_string(device, device.iSerialNumber)
                            bus = device.bus
                            address = device.address
                        except Exception as e:
                            pass

                        device_info = {
                            "type": "ST-Link",
                            "name": f"ST-Link {vid:04X}:{pid:04X}",
                            "vid": vid,
                            "pid": pid,
                        }

                        if serial:
                            device_info["serial"] = serial
                            device_info["name"] = (
                                f"ST-Link {vid:04X}:{pid:04X} SN:{serial}"
                            )
                            logger.info(f"Найден ST-Link с серийным номером: {serial}")

                        if bus is not None:
                            device_info["usb_bus"] = bus
                        if address is not None:
                            device_info["usb_address"] = address

                        self.devices.append(device_info)
                    except Exception as e:
                        logger.debug(f"Ошибка при обработке ST-Link устройства: {e}")
                        continue
            except Exception:
                continue

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
            lib_programmer = None
            try:
                from .stlink_lib import STLinkProgrammerLib

                attempted_methods.append("STLinkProgrammerLib")
                lib_programmer = STLinkProgrammerLib(self.selected)
                success = lib_programmer.write_bytes(data, address)
                if success:
                    logger.info("запись выполнена через STLinkProgrammerLib")
                else:
                    last_error = "STLinkProgrammerLib: запись не удалась"
            except Exception as e:
                last_error = f"STLinkProgrammerLib: {e}"
                success = False
            finally:
                if lib_programmer is not None:
                    try:
                        if hasattr(lib_programmer, "stlink") and lib_programmer.stlink:
                            lib_programmer.stlink.disconnect()
                    except Exception:
                        pass

        if device_type == "ST-Link" and not success:
            try:
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
            except Exception as e:
                attempted_methods.append(f"STM32CubeProgrammer (ошибка: {e})")
                last_error = f"STM32CubeProgrammer: {e}"
                success = False

        if device_type == "ST-Link" and not success:
            try:
                from .stlink_openocd import STLinkProgrammerOpenOCD

                programmer = STLinkProgrammerOpenOCD(self.selected)
                if programmer.openocd_path:
                    attempted_methods.append("OpenOCD")
                    logger.info(
                        f"попытка записи через OpenOCD: {programmer.openocd_path}"
                    )
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
            except Exception as e:
                attempted_methods.append(f"OpenOCD (ошибка: {e})")
                last_error = f"OpenOCD: {e}"
                success = False

        if device_type == "ST-Link" and not success:
            try:
                from .stlink import STLinkProgrammer

                attempted_methods.append("STLinkProgrammer (прямой USB)")
                logger.info("попытка записи через прямой USB доступ (STLinkProgrammer)")
                logger.info(f"запись {len(data)} байт по адресу {hex(address)}")
                programmer = STLinkProgrammer(self.selected)
                success = programmer.write_bytes(data, address)

                if not success and hasattr(programmer, "reconnect"):
                    logger.warning("запись не удалась, попытка переподключения...")
                    if programmer.reconnect():
                        logger.info(
                            "переподключение успешно, повторная попытка записи..."
                        )
                        time.sleep(1)
                        success = programmer.write_bytes(data, address)

                if success:
                    logger.info("запись выполнена через прямой USB доступ")
                else:
                    last_error = "STLinkProgrammer: запись не удалась (не удалось подключиться к целевому устройству)"
                    logger.warning(f"запись через прямой USB доступ не удалась")
            except Exception as e:
                attempted_methods.append(f"STLinkProgrammer (ошибка: {e})")
                last_error = f"STLinkProgrammer: {e}"
                success = False

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
                        logger.info(f"чтение {read_size} байт с адреса {hex(address)}")
                        read_data = programmer.read_bytes(read_size, address)
                        if read_data:
                            logger.info(
                                f"прочитано {len(read_data)} байт через прямой USB доступ"
                            )
                        else:
                            logger.warning(
                                "не удалось прочитать данные через прямой USB доступ"
                            )
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
                    data = programmer.read_bytes(size, address)
                except:
                    data = b""

            if not data:
                return b""

        return data

    def send_command_uart(self, command, expected_response):
        import sys

        if isinstance(command, str):
            command = command.encode("utf-8")

        if (
            not command.endswith(b"\n")
            and not command.endswith(b"\r")
            and not command.endswith(b"\r\n")
        ):
            from stm32_programmer.utils.uart_settings import UARTSettings

            uart_settings = UARTSettings()
            line_ending_bytes = uart_settings.get_line_ending_bytes()
            command = command + line_ending_bytes

        self.selected_uart.reset_input_buffer()

        self.selected_uart.write(command)
        self.selected_uart.flush()

        time.sleep(0.01)

        response = None
        buffer = b""

        max_wait_time = 3.0 if sys.platform == "win32" else 2.0
        start_time = time.time()

        try:

            while (time.time() - start_time) < max_wait_time:
                if self.selected_uart.in_waiting > 0:

                    data = self.selected_uart.read(self.selected_uart.in_waiting)
                    if data:
                        buffer += data

                        if b"\n" in buffer or b"\r" in buffer:
                            break

                        if expected_response in buffer:
                            break

                time.sleep(0.01)

            if buffer:

                response = buffer.strip()

                response = response.rstrip(b"\r\n").rstrip(b"\n\r")

        except serial.SerialException as read_error:
            logger.warning(f"ошибка чтения ответа от UART: {read_error}")
            return False
        except Exception as e:
            logger.warning(f"ошибка при чтении: {e}")
            return False

        if response == expected_response:
            logger.info(
                f"получен ответ от UART: {response.decode('utf-8', errors='replace')}"
            )
            return True
        else:
            display_response = (
                response.decode("utf-8", errors="replace") if response else "нет ответа"
            )
            logger.warning(
                f"не получено ожидаемого ответа от UART. "
                f"ожидали '{expected_response.decode('utf-8')}', получили '{display_response}'."
            )

            if sys.platform == "win32" and response:
                logger.warning(f"сырой ответ (hex): {response.hex()}")
                logger.warning(f"ожидаемый ответ (hex): {expected_response.hex()}")
            return False
