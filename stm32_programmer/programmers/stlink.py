import usb.core
import usb.util
import time
import struct
import logging
from stm32_programmer.utils.icon_loader import get_icon_emoji_fallback

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
                try:
                    usb.util.release_interface(
                        self.usb_device, self.interface.bInterfaceNumber
                    )
                except (ValueError, OSError, IOError) as e:
                    error_msg = str(e).lower()
                    if (
                        "closed" in error_msg
                        or "operation on closed" in error_msg
                        or "no such device" in error_msg
                    ):
                        logger.debug(
                            f"USB устройство уже было закрыто при освобождении интерфейса: {e}"
                        )
                    else:
                        logger.warning(f"Ошибка при освобождении интерфейса USB: {e}")
                except Exception as e:
                    logger.warning(
                        f"Неожиданная ошибка при освобождении интерфейса USB: {e}"
                    )
            except Exception as e:
                logger.warning(f"Ошибка при отключении USB устройства: {e}")

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
            logger.info(f"Поиск USB устройства: VID={hex(vid)}, PID={hex(pid)}")
            self.usb_device = usb.core.find(idVendor=vid, idProduct=pid)

            if not self.usb_device:
                logger.warning(
                    f"USB устройство не найдено: VID={hex(vid)}, PID={hex(pid)}"
                )
                return False

            logger.info(f"USB устройство найдено, настройка конфигурации...")
            try:
                self.usb_device.set_configuration()
                cfg = self.usb_device.get_active_configuration()
                self.interface = cfg[(0, 0)]

                logger.info(f"Захват интерфейса {self.interface.bInterfaceNumber}...")
                usb.util.claim_interface(
                    self.usb_device, self.interface.bInterfaceNumber
                )

                logger.info("Получение версии устройства...")
                self.version = self._get_version()
                logger.info(
                    f"USB устройство успешно подключено, версия: {self.version}"
                )
                return True
            except (ValueError, OSError, IOError) as e:
                error_msg = str(e).lower()
                if (
                    "closed" in error_msg
                    or "operation on closed" in error_msg
                    or "no such device" in error_msg
                ):
                    logger.error(f"USB устройство закрыто при подключении: {e}")
                    self.usb_device = None
                    self.interface = None
                    return False
                else:
                    logger.error(f"Ошибка при настройке USB устройства: {e}")
                    raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при подключении к USB устройству: {e}")
            self.usb_device = None
            self.interface = None
            return False

    def _get_version(self):
        try:
            if not self.usb_device:
                return "Unknown"
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
            try:
                result = self.usb_device.ctrl_transfer(0x80, 0x06, 0x0300, 0, 16)
                if len(result) >= 6:
                    return f"{result[5]}.{result[4]}.{result[3]}"
                return "Unknown"
            except (ValueError, OSError, IOError) as e:
                error_msg = str(e).lower()
                if (
                    "closed" in error_msg
                    or "operation on closed" in error_msg
                    or "no such device" in error_msg
                ):
                    logger.warning(f"USB устройство закрыто при получении версии: {e}")
                    return "Unknown"
                else:
                    logger.warning(f"Ошибка при получении версии USB устройства: {e}")
                    return "Unknown"
        except Exception as e:
            logger.warning(
                f"Неожиданная ошибка при получении версии USB устройства: {e}"
            )
            return "Unknown"

    def _check_target_connection(self):
        detection_commands = [
            ([0xF2, 0x5A] + [0x00] * 14, "READ_IDCODE"),
            ([0xF2, 0x5B] + [0x00] * 14, "READ_DBGMCU_ID"),
            ([0xF2, 0x22] + [0x00] * 14, "READ_CORE_ID"),
        ]

        for cmd, description in detection_commands:
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

        return False

    def _send_command(self, cmd, data=None, timeout=1000):
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
                usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN
            ):
                endpoint_in = ep

        if endpoint_out and endpoint_in:
            try:

                if self.usb_device is None:
                    logger.warning(
                        "USB устройство закрыто в _send_command (usb_device is None)"
                    )
                    return None

                logger.debug(
                    f"Отправка USB команды: {len(cmd)} байт, timeout={timeout}мс"
                )
                self.usb_device.write(endpoint_out.bEndpointAddress, cmd, timeout)
                time.sleep(0.01)
                logger.debug("Чтение ответа от USB устройства...")
                result = self.usb_device.read(endpoint_in.bEndpointAddress, 64, timeout)
                logger.debug(f"Получен ответ от USB устройства: {len(result)} байт")
                return result
            except (ValueError, OSError, IOError) as e:
                error_msg = str(e).lower()
                if (
                    "closed" in error_msg
                    or "operation on closed" in error_msg
                    or "no such device" in error_msg
                ):
                    logger.error(
                        f"КРИТИЧЕСКАЯ ОШИБКА: USB устройство закрыто во время отправки команды: {e}"
                    )
                    logger.error(f"Тип ошибки: {type(e).__name__}, сообщение: {str(e)}")
                    import traceback

                    logger.error(
                        f"Трассировка при ошибке закрытого устройства: {traceback.format_exc()}"
                    )

                    try:
                        logger.info("Попытка переподключения к USB устройству...")
                        self.disconnect()
                        time.sleep(0.5)
                        if self._connect():
                            logger.info(
                                "USB устройство успешно переподключено, повторная попытка отправки команды..."
                            )

                            try:
                                logger.debug(
                                    f"Повторная отправка USB команды: {len(cmd)} байт"
                                )
                                self.usb_device.write(
                                    endpoint_out.bEndpointAddress, cmd, timeout
                                )
                                time.sleep(0.01)
                                logger.debug(
                                    "Повторное чтение ответа от USB устройства..."
                                )
                                result = self.usb_device.read(
                                    endpoint_in.bEndpointAddress, 64, timeout
                                )
                                logger.info(
                                    f"Повторная попытка успешна, получен ответ: {len(result)} байт"
                                )
                                return result
                            except (ValueError, OSError, IOError) as retry_error:
                                error_msg_retry = str(retry_error).lower()
                                if (
                                    "closed" in error_msg_retry
                                    or "operation on closed" in error_msg_retry
                                    or "no such device" in error_msg_retry
                                ):
                                    logger.error(
                                        f"USB устройство закрыто при повторной попытке отправки команды: {retry_error}"
                                    )
                                    raise RuntimeError(
                                        f"I/O operation on closed file: USB устройство было закрыто при повторной попытке отправки команды: {retry_error}"
                                    )
                                logger.error(
                                    f"Ошибка при повторной попытке отправки команды: {retry_error}"
                                )
                                raise RuntimeError(
                                    f"I/O operation on closed file: Ошибка при повторной попытке отправки команды: {retry_error}"
                                )
                            except Exception as retry_error:
                                logger.error(
                                    f"Неожиданная ошибка при повторной попытке отправки команды: {retry_error}"
                                )
                                raise RuntimeError(
                                    f"I/O operation on closed file: Неожиданная ошибка при повторной попытке отправки команды: {retry_error}"
                                )
                        else:
                            logger.error("Не удалось переподключиться к USB устройству")
                            raise RuntimeError(
                                f"I/O operation on closed file: Не удалось переподключиться к USB устройству после ошибки закрытого файла"
                            )
                    except RuntimeError:
                        raise
                    except Exception as reconnect_error:
                        logger.error(
                            f"Ошибка при переподключении USB устройства: {reconnect_error}"
                        )
                        raise RuntimeError(
                            f"I/O operation on closed file: Ошибка при переподключении USB устройства: {reconnect_error}"
                        )
                else:
                    logger.error(f"Ошибка при отправке команды USB: {e}")
                    raise RuntimeError(
                        f"I/O operation on closed file: Ошибка при отправке команды USB: {e}"
                    )
            except RuntimeError:
                raise
            except Exception as e:
                logger.error(f"Неожиданная ошибка при отправке команды USB: {e}")
                import traceback

                logger.error(f"Трассировка: {traceback.format_exc()}")
                raise RuntimeError(
                    f"I/O operation on closed file: Неожиданная ошибка при отправке команды USB: {e}"
                )
        return None

    def _enter_debug_mode(self):
        try:
            if not self.usb_device or not self.interface:
                logger.warning("USB устройство не подключено для входа в режим отладки")
                return False

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
                except RuntimeError as e:
                    error_msg = str(e)
                    if "I/O operation on closed file" in error_msg:
                        logger.error(
                            f"USB устройство закрыто при входе в режим отладки: {e}"
                        )
                        return False
                    raise
                except Exception as e:
                    logger.warning(
                        f"Ошибка при отправке команды входа в режим отладки: {e}"
                    )
                    continue

            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при входе в режим отладки: {e}")
            return False

    def _exit_debug_mode(self):
        try:
            if not self.usb_device or not self.interface:
                logger.warning(
                    "USB устройство не подключено для выхода из режима отладки"
                )
                return False

            cmd = [0xF2, 0x21] + [0x00] * 14
            try:
                result = self._send_command(cmd, timeout=2000)
                return result is not None
            except RuntimeError as e:
                error_msg = str(e)
                if "I/O operation on closed file" in error_msg:
                    logger.warning(
                        f"USB устройство закрыто при выходе из режима отладки: {e}"
                    )
                    return False
                raise
        except Exception as e:
            logger.warning(f"Неожиданная ошибка при выходе из режима отладки: {e}")
            return False

    def _read_memory(self, address, size):
        try:
            if not self.usb_device or not self.interface:
                logger.warning("USB устройство не подключено для чтения памяти")
                return b""

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
            try:
                result = self._send_command(cmd)
            except RuntimeError as e:
                error_msg = str(e)
                if "I/O operation on closed file" in error_msg:
                    logger.error(f"USB устройство закрыто при чтении памяти: {e}")
                    raise RuntimeError(
                        f"I/O operation on closed file: USB устройство было закрыто при чтении памяти: {e}"
                    )
                raise

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
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при чтении памяти: {e}")
            return b""

    def _write_memory(self, address, data):
        try:
            if not self.usb_device or not self.interface:
                logger.warning("USB устройство не подключено для записи памяти")
                return False

            logger.debug(
                f"Запись памяти: адрес={hex(address)}, размер={len(data)} байт"
            )
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
                    logger.debug(f"Попытка записи памяти командой {cmd_name}...")
                    result = self._send_command(cmd, list(data), timeout=5000)
                    if result is not None and len(result) > 0:
                        logger.debug(
                            f"Команда {cmd_name} вернула ответ: {len(result)} байт, первый байт={hex(result[0])}"
                        )
                        if len(result) > 0 and result[0] == 0x80:
                            logger.debug(f"Запись памяти успешна командой {cmd_name}")
                            return True
                        elif len(result) > 0:
                            logger.debug(
                                f"Команда {cmd_name} вернула неожиданный ответ, пробуем следующую команду"
                            )
                            continue
                        else:
                            logger.debug(
                                f"Запись памяти успешна командой {cmd_name} (пустой ответ)"
                            )
                            return True
                    else:
                        logger.warning(f"Команда {cmd_name} не вернула ответ")
                except RuntimeError as e:
                    error_msg = str(e)
                    if "I/O operation on closed file" in error_msg:
                        logger.error(
                            f"КРИТИЧЕСКАЯ ОШИБКА: USB устройство закрыто при записи памяти (команда {cmd_name}): {e}"
                        )
                        logger.error(
                            f"Адрес записи: {hex(address)}, размер данных: {len(data)} байт"
                        )
                        import traceback

                        logger.error(
                            f"Трассировка при ошибке записи памяти: {traceback.format_exc()}"
                        )
                        raise RuntimeError(
                            f"I/O operation on closed file: USB устройство было закрыто при записи памяти по адресу {hex(address)}: {e}"
                        )
                    raise
                except Exception as e:
                    logger.warning(
                        f"Ошибка при отправке команды {cmd_name} для записи памяти: {e}"
                    )
                    import traceback

                    logger.debug(
                        f"Трассировка ошибки команды {cmd_name}: {traceback.format_exc()}"
                    )
                    continue

            logger.warning(
                f"Все команды записи памяти не удались для адреса {hex(address)}"
            )
            return False
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка при записи памяти по адресу {hex(address)}: {e}"
            )
            import traceback

            logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    def write_bytes(self, data, address):
        try:
            if not self.usb_device or not self.interface:
                if not self._connect():
                    error_msg = "Ошибка: не удалось подключиться к USB устройству"
                    logger.error(error_msg)
                    return False, error_msg

            logger.info("Проверка подключения к целевому устройству...")
            if not self._check_target_connection():
                error_msg = (
                    "Ошибка: не удалось подключиться к целевому устройству\n"
                    "Возможные причины:\n"
                    f"  - Возможно у вас где-то открыт STM32CubeProgrammer и он занял устройство {get_icon_emoji_fallback('thinking')}\n"
                    "  - Устройство не подключено или не включено\n"
                    "  - Проблемы с драйверами ST-Link\n"
                    "Решение: закройте STM32CubeProgrammer и попробуйте снова"
                )
                logger.error(error_msg)
                return False, error_msg
            logger.info("Подключение к целевому устройству установлено")

            logger.info("Вход в режим отладки...")
            if not self._enter_debug_mode():
                error_msg = "Ошибка: не удалось войти в режим отладки"
                logger.error(error_msg)
                return False, error_msg
            logger.info("Режим отладки активирован")

            time.sleep(0.1)

            block_size = 1024
            total_size = len(data)
            offset = 0
            success = True

            logger.info(f"Начало записи {total_size} байт по адресу {hex(address)}")
            logger.info(
                f"Размер блока: {block_size} байт, всего блоков: {(total_size + block_size - 1) // block_size}"
            )
        except (ValueError, OSError, IOError) as e:
            error_msg = str(e).lower()
            if (
                "closed" in error_msg
                or "operation on closed" in error_msg
                or "no such device" in error_msg
            ):
                detailed_error = (
                    "I/O operation on closed file: USB устройство было закрыто во время инициализации записи\n"
                    "Возможные причины:\n"
                    "  • USB устройство было закрыто другим процессом (STM32CubeProgrammer)\n"
                    "  • Устройство было отключено во время записи\n"
                    "  • USB интерфейс был закрыт\n"
                    f"Детали: {e}"
                )
                logger.error(detailed_error)
                raise RuntimeError(f"I/O operation on closed file: {detailed_error}")
            else:
                logger.error(f"Ошибка при инициализации записи: {e}")
                raise RuntimeError(f"Ошибка при инициализации записи: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при инициализации записи: {e}")
            raise RuntimeError(f"Неожиданная ошибка при инициализации записи: {e}")

        while offset < total_size:
            block = data[offset : offset + block_size]
            block_address = address + offset

            block_num = offset // block_size + 1
            total_blocks = (total_size + block_size - 1) // block_size
            logger.info(
                f"Запись блока {block_num}/{total_blocks}: "
                f"{len(block)} байт по адресу {hex(block_address)} "
                f"(прогресс: {offset}/{total_size} байт, {100 * offset // total_size}%)"
            )

            try:
                logger.debug(f"Вызов _write_memory для блока {block_num}...")
                block_success = self._write_memory(block_address, block)
                if not block_success:
                    logger.error(
                        f"Ошибка записи блока {block_num}/{total_blocks} по адресу {hex(block_address)}"
                    )
                    success = False
                    break
                else:
                    logger.info(f"Блок {block_num}/{total_blocks} успешно записан")
            except RuntimeError as e:
                error_msg = str(e)
                if (
                    "I/O operation on closed file" in error_msg
                    or "operation on closed" in error_msg.lower()
                ):
                    logger.error(
                        f"КРИТИЧЕСКАЯ ОШИБКА: USB устройство закрыто во время записи блока {block_num}/{total_blocks}: {e}"
                    )
                    logger.error(
                        f"Адрес блока: {hex(block_address)}, размер блока: {len(block)} байт"
                    )
                    logger.error(
                        f"Прогресс записи: {offset}/{total_size} байт ({100 * offset // total_size}%)"
                    )
                    import traceback

                    logger.error(
                        f"Трассировка при ошибке записи блока: {traceback.format_exc()}"
                    )

                    try:
                        logger.info(
                            "Попытка переподключения к USB устройству после ошибки закрытого файла..."
                        )
                        self.disconnect()
                        time.sleep(1.0)
                        if not self._connect():
                            logger.error(
                                "Не удалось переподключиться к USB устройству после ошибки"
                            )
                            success = False
                            break
                        logger.info(
                            "Проверка подключения к целевому устройству после переподключения..."
                        )
                        if not self._check_target_connection():
                            logger.error(
                                "Не удалось подключиться к целевому устройству после переподключения"
                            )
                            success = False
                            break
                        logger.info("Вход в режим отладки после переподключения...")
                        if not self._enter_debug_mode():
                            logger.error(
                                "Не удалось войти в режим отладки после переподключения"
                            )
                            success = False
                            break
                        logger.info(
                            f"Повторная попытка записи блока {block_num}/{total_blocks} по адресу {hex(block_address)} после переподключения"
                        )
                        block_success = self._write_memory(block_address, block)
                        if not block_success:
                            logger.error(
                                f"Ошибка записи блока после переподключения по адресу {hex(block_address)}"
                            )
                            success = False
                            break
                        else:
                            logger.info(
                                f"Блок {block_num}/{total_blocks} успешно записан после переподключения"
                            )
                    except Exception as reconnect_error:
                        logger.error(
                            f"Ошибка при переподключении USB устройства: {reconnect_error}"
                        )
                        import traceback

                        logger.error(
                            f"Трассировка при ошибке переподключения: {traceback.format_exc()}"
                        )
                        success = False
                        break
                else:
                    raise
            except Exception as e:
                logger.error(f"Неожиданная ошибка при записи блока: {e}")
                success = False
                break

            offset += len(block)
            time.sleep(0.05)

        logger.info(
            f"Запись завершена. Успешно: {success}, записано: {offset}/{total_size} байт"
        )
        try:
            logger.info("Выход из режима отладки...")
            self._exit_debug_mode()
            logger.info("Выход из режима отладки выполнен")
        except Exception as e:
            logger.warning(f"Ошибка при выходе из режима отладки: {e}")
            import traceback

            logger.debug(
                f"Трассировка ошибки выхода из режима отладки: {traceback.format_exc()}"
            )

        if success:
            logger.info(
                f"Запись завершена успешно: {total_size} байт записано по адресу {hex(address)}"
            )
        else:
            logger.error(
                f"Запись завершена с ошибками: записано только {offset}/{total_size} байт"
            )
            logger.error(
                f"Последний успешно записанный адрес: {hex(address + offset - len(block)) if offset > 0 else hex(address)}"
            )

            error_details = "Ошибка записи прошивки через ST-Link. Возможные причины:\n"
            error_details += "  • USB устройство было закрыто другим процессом (STM32CubeProgrammer)\n"
            error_details += f"  • Устройство было отключено во время записи (записано {offset}/{total_size} байт)\n"
            error_details += "  • USB интерфейс был закрыт\n"
            return False, error_details

        try:
            logger.info("Отключение от USB устройства...")
            self.disconnect()
            logger.info("Отключение от USB устройства выполнено")
        except Exception as e:
            logger.warning(f"Ошибка при отключении: {e}")
            import traceback

            logger.debug(f"Трассировка ошибки отключения: {traceback.format_exc()}")

        return success

    def read_bytes(self, size, address):
        if not self.usb_device or not self.interface:
            if not self._connect():
                logger.warning(
                    "USB устройство или интерфейс не инициализированы, чтение невозможно"
                )
                return b""

        logger.info(f"проверка подключения к целевому устройству для чтения...")
        if not self._check_target_connection():
            warning_msg = (
                "не удалось подключиться к целевому устройству для чтения\n"
                "Возможные причины:\n"
                f"  - Возможно у вас где-то открыт STM32CubeProgrammer и он занял устройство {get_icon_emoji_fallback('thinking')}\n"
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

    def clear_memory(self, address, size):
        if not self.usb_device:
            return False
        if not self._enter_debug_mode():
            return False
        for i in range(size):
            pass
        self._exit_debug_mode()
        return False

    def erase_flash(self):
        if not self.usb_device or not self.interface:
            if not self._connect():
                return False

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

    def reset_target(self):
        if not self.usb_device or not self.interface:
            if not self._connect():
                return False

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

    def __del__(self):
        self.disconnect()
