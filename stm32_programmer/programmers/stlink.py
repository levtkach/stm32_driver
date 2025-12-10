import usb.core
import usb.util
import time
import struct
import logging

logger = logging.getLogger(__name__)


class STLinkProgrammer:
    def __init__(self, device):
        self.device = device
        self.usb_device = None
        self.interface = None
        self.version = None

    def disconnect(self):

        if self.usb_device and self.interface:
            try:
                usb.util.release_interface(
                    self.usb_device, self.interface.bInterfaceNumber
                )
            except:
                pass

        self.usb_device = None
        self.interface = None
        self.version = None

    def reconnect(self):

        self.disconnect()
        time.sleep(0.5)
        return self._connect()

    def _connect(self):
        try:
            vid = self.device["vid"]
            pid = self.device["pid"]
            self.usb_device = usb.core.find(idVendor=vid, idProduct=pid)

            if not self.usb_device:
                return False

            try:
                self.usb_device.set_configuration()
                cfg = self.usb_device.get_active_configuration()
                self.interface = cfg[(0, 0)]

                usb.util.claim_interface(
                    self.usb_device, self.interface.bInterfaceNumber
                )

                self.version = self._get_version()
                return True

            except usb.core.USBError as e:
                return False

        except Exception as e:
            return False

    def _get_version(self):
        try:
            cmd = [
                0xF1,
                0x80,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
            result = self.usb_device.ctrl_transfer(0x80, 0x06, 0x0300, 0, 16)
            if len(result) >= 6:
                return f"{result[5]}.{result[4]}.{result[3]}"
            return "Unknown"
        except:
            return "Unknown"

    def _check_target_connection(self):
        try:

            detection_commands = [
                ([0xF2, 0x5A] + [0x00] * 14, "READ_IDCODE"),
                ([0xF2, 0x5B] + [0x00] * 14, "READ_DBGMCU_ID"),
                ([0xF2, 0x22] + [0x00] * 14, "READ_CORE_ID"),
            ]

            for cmd, description in detection_commands:
                try:
                    result = self._send_command(cmd, timeout=2000)

                    if result and len(result) > 4:
                        if description == "READ_IDCODE":
                            idcode = struct.unpack("<I", bytes(result[2:6]))[0]
                            return True
                        elif description == "READ_DBGMCU_ID":
                            dbgmcu_id = struct.unpack("<I", bytes(result[2:6]))[0]
                            return True
                        elif description == "READ_CORE_ID":
                            core_id = struct.unpack("<I", bytes(result[2:6]))[0]
                            return True
                    else:
                        pass
                except Exception as e:
                    continue

            return False

        except Exception as e:
            return False

    def _send_command(self, cmd, data=None, timeout=1000):
        try:
            if data is None:
                data = [0] * 16

            endpoint_out = None
            endpoint_in = None

            for ep in self.interface:
                if (
                    usb.util.endpoint_direction(ep.bEndpointAddress)
                    == usb.util.ENDPOINT_OUT
                ):
                    endpoint_out = ep
                elif (
                    usb.util.endpoint_direction(ep.bEndpointAddress)
                    == usb.util.ENDPOINT_IN
                ):
                    endpoint_in = ep

            if endpoint_out and endpoint_in:
                self.usb_device.write(endpoint_out.bEndpointAddress, cmd, timeout)
                time.sleep(0.01)
                result = self.usb_device.read(endpoint_in.bEndpointAddress, 64, timeout)
                return result
            return None
        except Exception as e:
            return None

    def _enter_debug_mode(self):
        try:

            commands = [
                [0xF2, 0x20] + [0x00] * 14,
                [0xF2, 0x58] + [0x00] * 14,
                [0xF2, 0x59] + [0x00] * 14,
            ]

            for i, cmd in enumerate(commands):
                try:
                    result = self._send_command(cmd, timeout=3000)
                    if result and len(result) > 0:
                        time.sleep(0.1)
                        return True
                except Exception as e:
                    continue

            return False

        except Exception as e:
            return False

    def _exit_debug_mode(self):
        try:
            cmd = [0xF2, 0x21] + [0x00] * 14
            result = self._send_command(cmd, timeout=2000)
            return result is not None
        except:
            return False

    def _read_memory(self, address, size):
        try:
            addr_bytes = struct.pack("<I", address)
            size_bytes = struct.pack("<I", size)

            cmd = (
                [0xF2, 0x07]
                + list(addr_bytes)
                + list(size_bytes)
                + [0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            )
            logger.info(
                f"отправка команды чтения памяти: адрес {hex(address)}, размер {size}"
            )
            result = self._send_command(cmd)

            if result:
                logger.info(f"получен ответ длиной {len(result)} байт")
                if len(result) > 2:
                    data = bytes(result[2 : 2 + size])
                    logger.info(f"извлечено {len(data)} байт данных")
                    return data
                else:
                    logger.warning(
                        f"ответ слишком короткий: {len(result)} байт, ожидалось минимум 3"
                    )
            else:
                logger.warning("не получен ответ от команды чтения")
            return b""
        except Exception as e:
            logger.warning(f"исключение в _read_memory: {e}")
            return b""

    def _write_memory(self, address, data):
        try:
            addr_bytes = struct.pack("<I", address)
            size = len(data)
            size_bytes = struct.pack("<I", size)

            write_commands = [
                (
                    [0xF2, 0x08] + list(addr_bytes) + list(size_bytes) + [0x00, 0x00],
                    "WRITE_MEM_32BIT",
                ),
                (
                    [0xF2, 0x55] + list(addr_bytes) + list(size_bytes) + [0x00, 0x00],
                    "WRITE_MEM_8BIT",
                ),
                (
                    [0xF2, 0x57] + list(addr_bytes) + list(size_bytes) + [0x00, 0x00],
                    "WRITE_MEM_16BIT",
                ),
            ]

            for cmd, cmd_name in write_commands:
                try:
                    result = self._send_command(cmd, list(data), timeout=5000)
                    if result is not None and len(result) > 0:
                        if len(result) > 0 and result[0] == 0x80:
                            return True
                        elif len(result) > 0:
                            continue
                        else:
                            return True
                except Exception as e:
                    continue

            return False

        except Exception as e:
            return False

    def write_bytes(self, data, address):

        if not self.usb_device or not self.interface:
            if not self._connect():
                logger.error("Ошибка: не удалось подключиться к USB устройству")
                return False

        try:
            logger.info("Проверка подключения к целевому устройству...")
            if not self._check_target_connection():
                error_msg = (
                    "Ошибка: не удалось подключиться к целевому устройству\n"
                    "Возможные причины:\n"
                    "  - Возможно у вас где-то открыт STM32CubeProgrammer и он занял устройство 🤔\n"
                    "  - Устройство не подключено или не включено\n"
                    "  - Проблемы с драйверами ST-Link\n"
                    "Решение: закройте STM32CubeProgrammer и попробуйте снова"
                )
                logger.error(error_msg)
                return False
            logger.info("Подключение к целевому устройству установлено")

            logger.info("Вход в режим отладки...")
            if not self._enter_debug_mode():
                logger.error("Ошибка: не удалось войти в режим отладки")
                return False
            logger.info("Режим отладки активирован")

            time.sleep(0.1)

            block_size = 1024
            total_size = len(data)
            offset = 0
            success = True

            logger.info(f"Начало записи {total_size} байт по адресу {hex(address)}")

            while offset < total_size:
                block = data[offset : offset + block_size]
                block_address = address + offset

                logger.debug(
                    f"Запись блока {offset // block_size + 1}/{(total_size + block_size - 1) // block_size}: "
                    f"{len(block)} байт по адресу {hex(block_address)}"
                )

                try:
                    block_success = self._write_memory(block_address, block)
                    if not block_success:
                        logger.error(
                            f"Ошибка записи блока по адресу {hex(block_address)}"
                        )
                        success = False
                        break
                except (ValueError, OSError, IOError) as e:
                    error_msg_lower = str(e).lower()
                    if (
                        "closed" in error_msg_lower
                        or "operation on closed" in error_msg_lower
                    ):
                        error_msg = (
                            f"КРИТИЧЕСКАЯ ОШИБКА: I/O operation on closed file\n"
                            f"Ошибка: {e}\n"
                            "Возможные причины:\n"
                            "  - USB устройство было закрыто другим процессом (STM32CubeProgrammer) 🤔\n"
                            "  - Устройство было отключено во время записи\n"
                            "Решение:\n"
                            "  1. Закройте STM32CubeProgrammer, если он открыт\n"
                            "  2. Проверьте USB соединение\n"
                            "  3. Переподключите устройство"
                        )
                        logger.error(error_msg)
                        success = False
                        break
                    else:
                        logger.error(f"Ошибка при записи блока: {e}")
                        success = False
                        break
                except Exception as e:
                    logger.error(f"Неожиданная ошибка при записи блока: {e}")
                    success = False
                    break

                offset += len(block)
                time.sleep(0.05)

            self._exit_debug_mode()

            if success:
                logger.info("Запись завершена успешно")
            else:
                logger.error("Запись завершена с ошибками")

            self.disconnect()
            return success

        except (ValueError, OSError, IOError) as e:
            error_msg_lower = str(e).lower()
            if "closed" in error_msg_lower or "operation on closed" in error_msg_lower:
                error_msg = (
                    f"КРИТИЧЕСКАЯ ОШИБКА: I/O operation on closed file\n"
                    f"Ошибка: {e}\n"
                    "Возможные причины:\n"
                    "  - USB устройство было закрыто другим процессом (STM32CubeProgrammer) 🤔\n"
                    "  - Устройство было отключено во время записи\n"
                    "Решение:\n"
                    "  1. Закройте STM32CubeProgrammer, если он открыт\n"
                    "  2. Проверьте USB соединение\n"
                    "  3. Переподключите устройство"
                )
                logger.error(error_msg)
            else:
                logger.exception(f"Исключение при записи: {e}")
            try:
                self._exit_debug_mode()
            except:
                pass

            self.disconnect()
            return False
        except Exception as e:
            logger.exception(f"Исключение при записи: {e}")
            try:
                self._exit_debug_mode()
            except:
                pass

            self.disconnect()
            return False

    def read_bytes(self, size, address):

        if not self.usb_device or not self.interface:
            if not self._connect():
                logger.warning(
                    "USB устройство или интерфейс не инициализированы, чтение невозможно"
                )
                return b""

        try:
            logger.info(f"проверка подключения к целевому устройству для чтения...")
            if not self._check_target_connection():
                warning_msg = (
                    "не удалось подключиться к целевому устройству для чтения\n"
                    "Возможные причины:\n"
                    "  - Возможно у вас где-то открыт STM32CubeProgrammer и он занял устройство 🤔\n"
                    "  - Устройство не подключено или не включено\n"
                    "  - Проблемы с драйверами ST-Link\n"
                    "Решение: закройте STM32CubeProgrammer и попробуйте снова"
                )
                logger.warning(warning_msg)
                return b""

            logger.info("вход в режим отладки для чтения...")
            if not self._enter_debug_mode():
                logger.warning("не удалось войти в режим отладки для чтения")
                return b""

            time.sleep(0.1)

            logger.info(f"чтение {size} байт с адреса {hex(address)}")
            data = self._read_memory(address, size)

            if data:
                logger.info(f"прочитано {len(data)} байт через прямой USB доступ")
                self._exit_debug_mode()

                self.disconnect()
                return data
            else:
                logger.warning("не удалось прочитать данные через прямой USB доступ")
                self._exit_debug_mode()

                self.disconnect()
                return b""

        except Exception as e:
            logger.warning(f"исключение при чтении через прямой USB доступ: {e}")
            try:
                self._exit_debug_mode()
            except:
                pass

            self.disconnect()
            return b""

    def clear_memory(self, address, size):
        try:
            if not self.usb_device:
                return False
            if not self._enter_debug_mode():
                return False
            for i in range(size):
                pass
            self._exit_debug_mode()
            return False
        except Exception:
            return False

        try:

            if not self._enter_debug_mode():
                return b""

            time.sleep(0.1)

            data = self._read_memory(address, size)

            self._exit_debug_mode()

            return data

        except Exception as e:
            return b""

    def erase_flash(self):

        if not self.usb_device or not self.interface:
            if not self._connect():
                return False

        try:

            if not self._enter_debug_mode():
                return False

            time.sleep(0.1)

            cmd = [
                0xF2,
                0x44,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
            result = self._send_command(cmd)

            self._exit_debug_mode()

            self.disconnect()

            if result:
                return True
            else:
                return False

        except Exception as e:

            self.disconnect()
            return False

    def reset_target(self):

        if not self.usb_device or not self.interface:
            if not self._connect():
                return False

        try:

            if not self._enter_debug_mode():
                return False

            time.sleep(0.1)

            cmd = [
                0xF2,
                0x03,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
            result = self._send_command(cmd)

            self._exit_debug_mode()

            self.disconnect()

            if result:
                return True
            else:
                return False

        except Exception as e:

            self.disconnect()
            return False

    def __del__(self):

        self.disconnect()
