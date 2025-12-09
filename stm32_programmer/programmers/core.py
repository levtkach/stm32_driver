import sys
import io
import logging
from datetime import datetime
from pathlib import Path
import time
import serial
from serial.tools import list_ports
from .base import BaseProgrammer

logger = logging.getLogger(__name__)


def setup_logging(log_dir=None):
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = log_dir / f"{timestamp}.log"

    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[file_handler, console_handler],
    )

    logger = logging.getLogger(__name__)
    logger.warning(f"Логи записываются в файл: {log_filename}")
    return logger, str(log_filename)


def connect_to_uart_port(port_name, baudrate=None, line_ending=None):
    if baudrate is None or line_ending is None:
        from stm32_programmer.utils.uart_settings import UARTSettings

        uart_settings = UARTSettings()
        if baudrate is None:
            baudrate = uart_settings.get_baud_rate()
        if line_ending is None:
            line_ending = uart_settings.get_line_ending()

    time.sleep(0.1)

    try:

        port_timeout = 3.0 if sys.platform == "win32" else 3.0

        serial_port = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=port_timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

        serial_port.dtr = False
        serial_port.rts = False

        if serial_port.is_open:
            logger = logging.getLogger(__name__)
            logger.info(
                f"[UART] подключено к {port_name} (baud={baudrate}, line_ending={line_ending}, timeout={port_timeout})"
            )

            time.sleep(0.2)

            try:
                serial_port.reset_input_buffer()
                serial_port.reset_output_buffer()
            except:
                pass
            return serial_port
        else:
            raise serial.SerialException(f"Не удалось открыть {port_name}")

    except serial.SerialException as e:
        error_msg = str(e).lower()
        if (
            "access is denied" in error_msg
            or "permission denied" in error_msg
            or "busy" in error_msg
        ):
            logger.warning(f"Порт {port_name} занят, ожидание освобождения...")

            time.sleep(0.5)
            try:
                serial_port = serial.Serial(
                    port=port_name,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=port_timeout,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False,
                )
                serial_port.dtr = False
                serial_port.rts = False
                if serial_port.is_open:
                    logger.info(
                        f"[UART] подключено к {port_name} после повторной попытки"
                    )
                    time.sleep(0.2)
                    try:
                        serial_port.reset_input_buffer()
                        serial_port.reset_output_buffer()
                    except:
                        pass
                    return serial_port
            except Exception as e2:
                raise serial.SerialException(
                    f"Ошибка подключения к {port_name} после повторной попытки: {e2}"
                )
        raise serial.SerialException(f"Ошибка подключения к {port_name}: {e}")
    except Exception as e:
        raise Exception(f"Ошибка при открытии порта {port_name}: {e}")


def detect_serial_port(selected_device):
    if not selected_device:
        return None

    try:
        ports = list(list_ports.comports())
    except Exception:
        return None

    if not ports:
        return None

    TARGET_UART_VID = 0x1A86
    TARGET_UART_PID = 0x7523

    def is_target_uart(port):
        if port.vid is not None and port.pid is not None:
            return port.vid == TARGET_UART_VID and port.pid == TARGET_UART_PID
        hwid = (port.hwid or "").upper()
        signature = f"VID:PID={TARGET_UART_VID:04X}:{TARGET_UART_PID:04X}"
        return signature in hwid

    matching_ports = [p for p in ports if is_target_uart(p)]

    if not matching_ports:
        logger.warning(
            "UART устройство с VID=0x1A86 и PID=0x7523 не найдено. Подключите устройство и попробуйте снова."
        )
        return None

    stlink_bus = selected_device.get("usb_bus") if selected_device else None
    stlink_address = selected_device.get("usb_address") if selected_device else None
    stlink_serial = selected_device.get("serial") if selected_device else None

    found_port = None

    if stlink_bus is not None or stlink_address is not None or stlink_serial:
        for port in matching_ports:
            hwid = (port.hwid or "").upper()

            if stlink_serial and hasattr(port, "serial_number") and port.serial_number:
                if (
                    stlink_serial.lower() in port.serial_number.lower()
                    or port.serial_number.lower() in stlink_serial.lower()
                ):
                    logger.info(
                        f"Найден связанный UART порт {port.device} по серийному номеру"
                    )
                    found_port = port.device
                    break

            if found_port is None and stlink_bus is not None:
                bus_patterns = [
                    f":{stlink_bus:03d}.",
                    f":{stlink_bus:03d}:",
                    f"BUS{stlink_bus:03d}",
                    f"BUS{stlink_bus}",
                    f"BUS {stlink_bus}",
                ]
                if any(pattern in hwid for pattern in bus_patterns):
                    logger.info(
                        f"Найден связанный UART порт {port.device} по USB bus {stlink_bus}"
                    )
                    found_port = port.device
                    break

            if found_port is None and stlink_address is not None:
                address_patterns = [
                    f":{stlink_address:03d}.",
                    f":{stlink_address:03d}:",
                    f"ADDR{stlink_address:03d}",
                ]
                if any(pattern in hwid for pattern in address_patterns):
                    logger.info(
                        f"Найден связанный UART порт {port.device} по USB address {stlink_address}"
                    )
                    found_port = port.device
                    break

            if (
                found_port is None
                and sys.platform == "darwin"
                and stlink_address is not None
            ):
                if hasattr(port, "location") and port.location:
                    location = port.location
                    logger.debug(
                        f"Порт {port.device} имеет location: {location}, ST-Link address: {stlink_address}"
                    )

            if found_port is None and sys.platform == "win32":
                if hasattr(port, "location") and port.location:
                    logger.debug(f"Порт {port.device} имеет location: {port.location}")

            if found_port is None and hasattr(port, "description") and port.description:
                desc_upper = port.description.upper()
                if "ST-LINK" in desc_upper or "STLINK" in desc_upper:
                    logger.info(
                        f"Найден связанный UART порт {port.device} по описанию: {port.description}"
                    )
                    found_port = port.device
                    break

    if found_port:
        return found_port

    if len(matching_ports) == 1:
        logger.info(f"Найден единственный UART порт: {matching_ports[0].device}")
        return matching_ports[0].device

    if len(matching_ports) > 1:
        logger.warning(
            f"Обнаружено несколько UART устройств с VID=0x1A86 и PID=0x7523 ({len(matching_ports)} шт.). "
            f"Не удалось автоматически определить связанный порт для выбранного ST-Link устройства. "
            f"Пожалуйста, выберите порт вручную из списка."
        )
        return None

    return None


def load_firmware_image(file_path):
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Файл прошивки не найден: {file_path}")

    start_address, data = _parse_intel_hex(file_path)
    return start_address, data, file_path


def _parse_intel_hex(file_path):
    data_bytes = {}
    upper_linear_address = 0
    segment_base = 0
    use_linear_addressing = False

    with open(file_path, "r", encoding="utf-8") as hex_file:
        for line_number, raw_line in enumerate(hex_file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise ValueError(
                    f"Некорректная строка Intel HEX (без префикса ':') в строке {line_number}"
                )

            try:
                record = bytes.fromhex(line[1:])
            except ValueError as hex_error:
                raise ValueError(
                    f"Некорректные данные Intel HEX в строке {line_number}: {hex_error}"
                ) from hex_error

            if len(record) < 5:
                raise ValueError(
                    f"Слишком короткая запись Intel HEX в строке {line_number}"
                )

            byte_count = record[0]
            address = (record[1] << 8) | record[2]
            record_type = record[3]
            payload = record[4 : 4 + byte_count]
            checksum = record[4 + byte_count]

            if ((sum(record[:-1]) + checksum) & 0xFF) != 0:
                raise ValueError(f"Ошибка контрольной суммы в строке {line_number}")

            if record_type == 0x00:
                if use_linear_addressing:
                    absolute_address = (upper_linear_address << 16) | address
                else:
                    absolute_address = segment_base + address

                for offset, value in enumerate(payload):
                    data_bytes[absolute_address + offset] = value

            elif record_type == 0x01:
                break

            elif record_type == 0x02:
                if byte_count != 2:
                    raise ValueError(
                        f"Некорректная длина extended segment address в строке {line_number}"
                    )
                segment_base = ((payload[0] << 8) | payload[1]) << 4
                use_linear_addressing = False

            elif record_type == 0x04:
                if byte_count != 2:
                    raise ValueError(
                        f"Некорректная длина extended linear address в строке {line_number}"
                    )
                upper_linear_address = (payload[0] << 8) | payload[1]
                use_linear_addressing = True

            else:
                continue

    if not data_bytes:
        raise ValueError("Файл прошивки не содержит данных")

    min_address = min(data_bytes.keys())
    max_address = max(data_bytes.keys())
    image = bytearray([0xFF] * (max_address - min_address + 1))

    for address, value in data_bytes.items():
        image[address - min_address] = value

    return min_address, bytes(image)


def check_current_mode(programmer, expected_mode, max_retries=3, retry_delay=0.5):
    logger = logging.getLogger(__name__)

    if not programmer.selected_uart or not programmer.selected_uart.is_open:
        logger.warning("UART порт не открыт для проверки режима")
        return False

    query_commands = [
        f"GET SWICH_SWD1__2\n",
        f"SWICH_SWD1__2?\n",
        f"STATUS SWICH_SWD1__2\n",
    ]

    for attempt in range(max_retries):
        for query_cmd in query_commands:
            try:
                programmer.selected_uart.reset_input_buffer()
                programmer.selected_uart.write(query_cmd.encode("utf-8"))
                programmer.selected_uart.flush()
                time.sleep(0.15)

                buffer = b""
                start_time = time.time()
                while (time.time() - start_time) < 2.0:
                    if programmer.selected_uart.in_waiting > 0:
                        data = programmer.selected_uart.read(
                            programmer.selected_uart.in_waiting
                        )
                        if data:
                            buffer += data
                            if b"\n" in buffer or b"\r" in buffer:
                                break
                            if (
                                f"SWICH_SWD1__2={expected_mode}".encode("utf-8")
                                in buffer
                            ):
                                logger.info(
                                    f"Режим {expected_mode} подтвержден через команду запроса"
                                )
                                return True
                    time.sleep(0.01)

                if buffer:
                    response = buffer.strip().rstrip(b"\r\n").rstrip(b"\n\r")
                    response_str = response.decode("utf-8", errors="replace")
                    logger.debug(
                        f"Получен ответ на запрос режима '{query_cmd.strip()}': {response_str}"
                    )

                    if f"SWICH_SWD1__2={expected_mode}" in response_str:
                        logger.info(f"Режим {expected_mode} подтвержден")
                        return True
                    elif "SWICH_SWD1__2=" in response_str:
                        actual_mode = (
                            response_str.split("SWICH_SWD1__2=")[-1].split()[0].strip()
                        )
                        logger.warning(
                            f"Режим не соответствует ожидаемому. Ожидали {expected_mode}, получили {actual_mode}"
                        )
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            break
                        return False

            except Exception as e:
                logger.debug(
                    f"Ошибка при запросе режима (команда '{query_cmd.strip()}'): {e}"
                )
                continue

        if attempt < max_retries - 1:
            logger.debug(
                f"Проверка режима через повторную команду SET (попытка {attempt + 1}/{max_retries})..."
            )
            time.sleep(retry_delay)
            command = f"SETSWICH_SWD1__2={expected_mode}".strip().encode("utf-8")
            expected_response = f"SWICH_SWD1__2={expected_mode}".strip().encode("utf-8")
            if programmer.send_command_uart(command, expected_response):
                logger.info(
                    f"Режим {expected_mode} подтвержден через повторную команду SET"
                )
                return True

    logger.warning(
        f"Не удалось подтвердить режим {expected_mode} после {max_retries} попыток"
    )
    return False


def parse_status_response(response_text):
    logger = logging.getLogger(__name__)
    status_dict = {}

    if not response_text:
        logger.warning("ответ пустой, статус не распарсен")
        return status_dict

    logger.debug(f"начало парсинга ответа, длина: {len(response_text)} символов")
    lines = response_text.strip().split("\n")
    logger.debug(f"разделено на {len(lines)} строк")

    parsed_count = 0
    skipped_count = 0

    for line_num, line in enumerate(lines, 1):
        original_line = line
        line = line.strip()
        if not line:
            skipped_count += 1
            continue

        key = None
        value = None

        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                logger.debug(
                    f"строка {line_num}: найдено ':' -> key='{key}', value='{value}'"
                )
        elif "=" in line:
            parts = line.split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                logger.debug(
                    f"строка {line_num}: найдено '=' -> key='{key}', value='{value}'"
                )
        else:
            logger.debug(
                f"строка {line_num}: не найдено разделителя ':' или '=', пропущено: '{line[:50]}'"
            )
            skipped_count += 1
            continue

        if key and value is not None:
            if key in status_dict:
                logger.warning(
                    f"дублирующийся ключ '{key}': старое значение '{status_dict[key]}', новое значение '{value}'"
                )
            status_dict[key] = value
            parsed_count += 1
        else:
            logger.debug(
                f"строка {line_num}: не удалось извлечь key/value, пропущено: '{line[:50]}'"
            )
            skipped_count += 1

    logger.info(
        f"парсинг завершен: распарсено {parsed_count} параметров, пропущено {skipped_count} строк"
    )
    logger.debug(f"распарсенные параметры: {list(status_dict.keys())}")
    if parsed_count > 0:
        logger.debug(
            f"примеры распарсенных параметров: {list(status_dict.items())[:10]}"
        )
    return status_dict


def get_status_from_uart(programmer, timeout=5.0):
    logger = logging.getLogger(__name__)
    import sys

    if not programmer.selected_uart or not programmer.selected_uart.is_open:
        logger.error("UART порт не открыт")
        return None

    logger.info("=" * 80)
    logger.info("КРИТИЧЕСКАЯ КОМАНДА: GET STATUS")
    logger.info(f"платформа: {sys.platform}")
    logger.info(f"timeout: {timeout} сек")

    max_retries = 3
    retry_delays = [0.2, 0.3, 0.5]

    for attempt in range(max_retries):
        logger.info(f"попытка {attempt + 1}/{max_retries} получения статуса")

        if attempt > 0:
            delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
            logger.info(f"задержка перед повторной попыткой: {delay} сек")
            time.sleep(delay)

        try:

            try:
                bytes_before = programmer.selected_uart.in_waiting
                programmer.selected_uart.reset_input_buffer()
                logger.info(f"очищен буфер uart, было байт: {bytes_before}")
            except Exception as e:
                logger.warning(f"ошибка при очистке буфера: {e}")

            from stm32_programmer.utils.uart_settings import UARTSettings

            uart_settings = UARTSettings()
            line_ending_bytes = uart_settings.get_line_ending_bytes()
            command = "GET STATUS".strip().encode("utf-8") + line_ending_bytes

            logger.info(f"отправка команды GET STATUS (hex): {command.hex()}")
            start_send_time = time.time()
            programmer.selected_uart.write(command)
            programmer.selected_uart.flush()
            send_duration = time.time() - start_send_time
            logger.info(f"команда отправлена за {send_duration:.4f} сек")

            post_send_delay = retry_delays[min(attempt, len(retry_delays) - 1)]
            logger.info(f"задержка после отправки: {post_send_delay} сек")
            time.sleep(post_send_delay)

            buffer = b""
            start_time = time.time()
            last_data_time = start_time
            max_idle_time = 0.5
            read_attempts = 0

            logger.info(f"начало чтения ответа, timeout: {timeout} сек")

            while (time.time() - start_time) < timeout:
                read_attempts += 1
                elapsed = time.time() - start_time

                if programmer.selected_uart.in_waiting > 0:
                    bytes_to_read = programmer.selected_uart.in_waiting
                    if read_attempts % 20 == 0:
                        logger.info(
                            f"попытка {read_attempts}: доступно {bytes_to_read} байт, прошло {elapsed:.3f} сек"
                        )

                    data = programmer.selected_uart.read(bytes_to_read)
                    if data:
                        buffer += data
                        last_data_time = time.time()
                        logger.info(
                            f"прочитано {len(data)} байт, всего: {len(buffer)} байт"
                        )
                        if len(buffer) > 0 and read_attempts % 10 == 0:
                            logger.debug(
                                f"данные (text, первые 200): {data.decode('utf-8', errors='replace')[:200]}"
                            )
                else:
                    if buffer and (time.time() - last_data_time) > max_idle_time:
                        logger.info(
                            f"пауза в данных {max_idle_time} сек, прерываем чтение"
                        )
                        break
                time.sleep(0.05)

            total_read_time = time.time() - start_time
            logger.info(
                f"чтение завершено за {total_read_time:.3f} сек, попыток: {read_attempts}"
            )

            if buffer:
                response = buffer.decode("utf-8", errors="replace").strip()
                logger.info(f"получен ответ GET STATUS ({len(response)} символов)")
                logger.info(f"первые 300 символов: {response[:300]}")
                logger.info("=" * 80)
                return response
            else:
                logger.warning(f"не получен ответ на попытке {attempt + 1}, буфер пуст")
                if programmer.selected_uart:
                    logger.warning(
                        f"uart in_waiting после неудачи: {programmer.selected_uart.in_waiting}"
                    )

        except Exception as e:
            logger.error(f"ошибка при получении статуса (попытка {attempt + 1}): {e}")
            import traceback

            logger.error(f"трассировка: {traceback.format_exc()}")
            if attempt < max_retries - 1:
                continue
            else:
                logger.info("=" * 80)
                return None

    logger.warning("не получен ответ на GET STATUS после всех попыток")
    logger.info("=" * 80)
    return None


def validate_status(status_dict, expected_values, ignore_fields=None):
    logger = logging.getLogger(__name__)
    errors = []
    warnings = []

    if ignore_fields is None:
        ignore_fields = []

    logger.debug(f"начало валидации статуса")
    logger.debug(f"проверяется {len(expected_values)} параметров")
    logger.debug(f"игнорируется {len(ignore_fields)} полей")
    logger.debug(f"в статусе найдено {len(status_dict)} параметров")

    for key, expected_value in expected_values.items():
        if key in ignore_fields:
            logger.debug(f"параметр '{key}' игнорируется")
            continue

        actual_value = status_dict.get(key)

        if actual_value is None:
            error_msg = f"Параметр '{key}' не найден в ответе"
            logger.error(f"  {error_msg}")
            errors.append(error_msg)
        else:
            expected_str = str(expected_value).strip()
            actual_str = str(actual_value).strip()
            if actual_str != expected_str:
                error_msg = f"Параметр '{key}': ожидалось '{expected_str}', получено '{actual_str}'"
                logger.error(f"  {error_msg}")
                errors.append(error_msg)
            else:
                logger.debug(
                    f"  ✓ параметр '{key}': '{actual_str}' совпадает с ожидаемым"
                )

    is_valid = len(errors) == 0
    logger.debug(
        f"валидация завершена: {'успех' if is_valid else 'ошибки'}, ошибок: {len(errors)}, предупреждений: {len(warnings)}"
    )
    return is_valid, errors, warnings


def load_test_plan():
    logger = logging.getLogger(__name__)
    import json

    test_plan_path = Path(__file__).resolve().parent.parent / "test_plan.json"

    try:
        with open(test_plan_path, "r", encoding="utf-8") as f:
            test_plan = json.load(f)
        logger.info(f"План тестирования загружен из {test_plan_path}")
        return test_plan
    except FileNotFoundError:
        logger.error(f"Файл плана тестирования не найден: {test_plan_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON файла плана тестирования: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при загрузке плана тестирования: {e}")
        return None


def run_test_plan(
    programmer,
    progress_callback=None,
    status_callback=None,
    progress_percent_callback=None,
):
    logger = logging.getLogger(__name__)

    if not programmer.selected_uart or not programmer.selected_uart.is_open:
        error_msg = "UART порт не открыт для тестирования"
        logger.error(error_msg)
        if status_callback:
            status_callback(error_msg)
        return False, error_msg

    test_plan_data = load_test_plan()
    if not test_plan_data:
        error_msg = "Не удалось загрузить план тестирования"
        logger.error(error_msg)
        if status_callback:
            status_callback(error_msg)
        return False, error_msg

    test_plan = test_plan_data.get("test_plan", {}).get("steps", [])
    if not test_plan:
        error_msg = "План тестирования пуст"
        logger.error(error_msg)
        if status_callback:
            status_callback(error_msg)
        return False, error_msg

    if status_callback:
        status_callback("Начало тестирования после прошивки...")

    all_tests_passed = True
    test_errors = []
    total_steps = len(test_plan)

    for step_idx, step in enumerate(test_plan, 1):
        if progress_percent_callback:
            test_progress = 80 + int((step_idx / total_steps) * 20)
            progress_percent_callback(test_progress)
        step_name = step.get("name", f"Шаг {step_idx}")
        command = step.get("command", "").strip()
        expected_response = step.get("expected_response")
        if expected_response and isinstance(expected_response, str):
            expected_response = expected_response.strip()
        wait_time = step.get("wait_time", 0)
        description = step.get("description", "")
        validation = step.get("validation")

        if not command:
            logger.warning(f"Шаг '{step_name}': команда пустая после удаления пробелов")
            continue

        if status_callback:
            status_callback(f"Тест {step_idx}/{len(test_plan)}: {step_name}")
        if progress_callback:
            progress_callback(f"->> {command}")

        logger.info(f"Выполнение шага тестирования: {step_name} - {command}")

        if command:
            from stm32_programmer.utils.uart_settings import UARTSettings

            uart_settings = UARTSettings()
            line_ending_bytes = uart_settings.get_line_ending_bytes()
            command_bytes = command.encode("utf-8") + line_ending_bytes

            if command.startswith(" "):
                logger.error(f"ОШИБКА: команда начинается с пробела! '{command}'")
            logger.debug(
                f"команда после strip: '{command}' (hex: {command_bytes.hex()})"
            )
            if expected_response:
                expected_response_bytes = expected_response.encode("utf-8")

                if expected_response.startswith(" "):
                    logger.error(
                        f"ОШИБКА: ожидаемый ответ начинается с пробела! '{expected_response}'"
                    )
                logger.debug(
                    f"ожидаемый ответ после strip: '{expected_response}' (hex: {expected_response_bytes.hex()})"
                )

                logger.info("=" * 80)
                logger.info(f"КРИТИЧЕСКАЯ КОМАНДА ТЕСТИРОВАНИЯ: {command}")
                logger.info(f"платформа: {sys.platform}")
                logger.info(
                    f"uart порт открыт: {programmer.selected_uart.is_open if programmer.selected_uart else False}"
                )
                if programmer.selected_uart:
                    logger.info(f"uart порт имя: {programmer.selected_uart.port}")
                    logger.info(f"uart timeout: {programmer.selected_uart.timeout}")
                    logger.info(
                        f"uart in_waiting до отправки: {programmer.selected_uart.in_waiting}"
                    )

                max_retries = 5
                retry_delays = [0.1, 0.2, 0.3, 0.5, 1.0]
                success = False
                actual_response = None

                for attempt in range(max_retries):
                    logger.info(
                        f"попытка {attempt + 1}/{max_retries} отправки команды {command}"
                    )

                    if attempt > 0:
                        delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                        logger.info(f"задержка перед повторной попыткой: {delay} сек")
                        time.sleep(delay)

                    try:
                        logger.info(
                            f"отправка команды через send_command_uart (попытка {attempt + 1})..."
                        )

                        if command.startswith("SET"):
                            original_timeout = programmer.selected_uart.timeout

                            programmer.selected_uart.timeout = (
                                5.0 if sys.platform == "win32" else 4.0
                            )
                            success = programmer.send_command_uart(
                                command_bytes, expected_response_bytes
                            )
                            programmer.selected_uart.timeout = original_timeout

                            if success and (
                                "SWICH_MODE" in command or "SWICH_PROFILE" in command
                            ):
                                logger.info(
                                    "дополнительное ожидание после установки режима/профиля (0.5 сек)..."
                                )
                                time.sleep(0.5)
                        else:
                            success = programmer.send_command_uart(
                                command_bytes, expected_response_bytes
                            )

                        if success:
                            logger.info(f"успех на попытке {attempt + 1}!")
                            break
                        else:
                            logger.warning(f"не получен ответ на попытке {attempt + 1}")
                            if programmer.selected_uart:
                                logger.warning(
                                    f"uart in_waiting после неудачи: {programmer.selected_uart.in_waiting}"
                                )

                            time.sleep(0.5)
                            buffer = b""
                            start_time = time.time()

                            while (time.time() - start_time) < 2.0:
                                if (
                                    programmer.selected_uart
                                    and programmer.selected_uart.is_open
                                ):
                                    if programmer.selected_uart.in_waiting > 0:
                                        data = programmer.selected_uart.read(
                                            programmer.selected_uart.in_waiting
                                        )
                                        if data:
                                            buffer += data
                                            logger.info(
                                                f"дополнительно прочитано {len(data)} байт"
                                            )
                                            if b"\n" in buffer or b"\r" in buffer:
                                                break
                                time.sleep(0.05)

                            if buffer:
                                try:
                                    actual_response = buffer.decode(
                                        "utf-8", errors="replace"
                                    ).strip()
                                    logger.info(
                                        f"дополнительный ответ (text): {actual_response}"
                                    )
                                    logger.info(
                                        f"дополнительный ответ (hex): {buffer.hex()}"
                                    )

                                    if actual_response == expected_response:
                                        success = True
                                        logger.info(
                                            "дополнительный ответ совпадает с ожидаемым!"
                                        )
                                        break
                                except:
                                    actual_response = str(buffer)

                    except Exception as e:
                        logger.error(
                            f"ошибка при получении ответа (попытка {attempt + 1}): {e}"
                        )
                        import traceback

                        logger.error(f"трассировка: {traceback.format_exc()}")
                        continue

                logger.info(
                    f"результат всех попыток: {'успех' if success else 'неудача'}"
                )
                logger.info("=" * 80)

                if not success:
                    if actual_response:
                        error_msg = f"Ошибка на шаге '{step_name}': ожидали '{expected_response}', получили '{actual_response}'"
                    else:
                        error_msg = f"Ошибка на шаге '{step_name}': не получен ожидаемый ответ '{expected_response}' (ответ не получен)"

                    logger.error(error_msg)
                    test_errors.append(error_msg)
                    all_tests_passed = False
                    if status_callback:
                        status_callback(f"{error_msg}")
                    if progress_callback and actual_response:
                        progress_callback(f"<<- {actual_response}")
                    continue

                if progress_callback:
                    progress_callback(f"<<- {expected_response}")
            else:
                programmer.selected_uart.reset_input_buffer()
                programmer.selected_uart.write(command_bytes)
                programmer.selected_uart.flush()

        if wait_time > 0:
            logger.info(f"Ожидание {wait_time} секунд...")
            time.sleep(wait_time)

        if command == "GET STATUS" and validation and step_idx > 1:

            prev_step_idx = step_idx - 2
            if prev_step_idx >= 0 and prev_step_idx < len(test_plan):
                prev_step = test_plan[prev_step_idx]
                if prev_step and prev_step.get("command", "").startswith("SET SWICH"):
                    logger.info(
                        "дополнительное ожидание перед проверкой статуса после SET команды (1.0 сек)..."
                    )
                    time.sleep(1.0)

        if command == "GET STATUS" and validation:
            expected_values = validation.get("expected_values", {})
            ignore_fields = validation.get("ignore_fields", [])

            logger.info("=" * 80)
            logger.info(f"НАЧАЛО ВАЛИДАЦИИ СТАТУСА: {step_name}")
            logger.info(f"ожидаемые значения: {expected_values}")
            logger.info(f"игнорируемые поля: {ignore_fields}")
            logger.info("=" * 80)

            max_validation_retries = 5
            validation_retry_delays = [1.0, 2.0, 3.0, 5.0, 10.0]
            validation_success = False
            final_errors = []
            final_status_dict = None

            for validation_attempt in range(max_validation_retries):
                logger.info("-" * 80)
                logger.info(
                    f"ПОПЫТКА ВАЛИДАЦИИ {validation_attempt + 1}/{max_validation_retries}"
                )
                logger.info("-" * 80)

                if validation_attempt > 0:
                    delay = validation_retry_delays[
                        min(validation_attempt - 1, len(validation_retry_delays) - 1)
                    ]
                    logger.info(
                        f"ожидание перед повторной попыткой валидации: {delay} сек"
                    )
                    time.sleep(delay)

                    if step_idx > 1:
                        prev_step_idx = step_idx - 2
                        if prev_step_idx >= 0 and prev_step_idx < len(test_plan):
                            prev_step = test_plan[prev_step_idx]
                            if prev_step and prev_step.get("command", "").startswith(
                                "SET SWICH"
                            ):
                                logger.info(
                                    f"повторная отправка команды SET перед проверкой статуса: {prev_step.get('command')}"
                                )
                                try:
                                    from stm32_programmer.utils.uart_settings import (
                                        UARTSettings,
                                    )

                                    uart_settings = UARTSettings()
                                    line_ending_bytes = (
                                        uart_settings.get_line_ending_bytes()
                                    )
                                    prev_command = prev_step.get("command", "").strip()
                                    prev_command_bytes = (
                                        prev_command.encode("utf-8") + line_ending_bytes
                                    )
                                    prev_expected = prev_step.get(
                                        "expected_response", ""
                                    ).strip()
                                    if prev_expected:
                                        prev_expected_bytes = prev_expected.encode(
                                            "utf-8"
                                        )
                                        logger.info(f"отправка команды: {prev_command}")
                                        retry_success = programmer.send_command_uart(
                                            prev_command_bytes, prev_expected_bytes
                                        )
                                        if retry_success:
                                            logger.info(
                                                "команда SET успешно переотправлена"
                                            )
                                            time.sleep(1.0)
                                        else:
                                            logger.warning(
                                                "не получен ответ на переотправленную команду SET"
                                            )
                                except Exception as e:
                                    logger.warning(
                                        f"ошибка при переотправке команды SET: {e}"
                                    )

                status_response = get_status_from_uart(programmer, timeout=5.0)

                if not status_response:
                    logger.error(
                        f"попытка {validation_attempt + 1}: не получен ответ на GET STATUS"
                    )
                    if validation_attempt < max_validation_retries - 1:
                        logger.info("будет повторная попытка...")
                        continue
                    else:
                        error_msg = f"Шаг '{step_name}': не получен ответ на GET STATUS после {max_validation_retries} попыток"
                        logger.error(error_msg)
                        test_errors.append(error_msg)
                        all_tests_passed = False
                        if status_callback:
                            status_callback(error_msg)
                        break

                logger.info(f"получен ответ на попытке {validation_attempt + 1}:")
                logger.info(f"длина ответа: {len(status_response)} символов")
                logger.info(f"первые 500 символов ответа:\n{status_response[:500]}")

                if progress_callback:
                    for line in status_response.split("\n"):
                        if line.strip():
                            progress_callback(f"<<- {line.strip()}")

                status_dict = parse_status_response(status_response)
                logger.info(f"распарсено параметров: {len(status_dict)}")
                logger.info(f"все параметры статуса: {list(status_dict.keys())}")

                logger.info("значения всех параметров статуса:")
                for key, value in sorted(status_dict.items()):
                    logger.info(f"  {key}: {value}")

                logger.info("начало валидации параметров...")
                is_valid, errors, warnings = validate_status(
                    status_dict, expected_values, ignore_fields
                )

                logger.info(f"результат валидации на попытке {validation_attempt + 1}:")
                logger.info(f"  валидность: {is_valid}")
                logger.info(f"  количество ошибок: {len(errors)}")
                logger.info(f"  количество предупреждений: {len(warnings)}")

                if errors:
                    logger.error("ошибки валидации:")
                    for error in errors:
                        logger.error(f"  - {error}")

                if warnings:
                    logger.warning("предупреждения валидации:")
                    for warning in warnings:
                        logger.warning(f"  - {warning}")

                logger.info("детальное сравнение параметров:")
                for key, expected_value in expected_values.items():
                    if key in ignore_fields:
                        logger.debug(f"  {key}: игнорируется")
                        continue
                    actual_value = status_dict.get(key)
                    match = (
                        str(actual_value).strip() == str(expected_value).strip()
                        if actual_value is not None
                        else False
                    )
                    status_icon = "✓" if match else "✗"
                    logger.info(
                        f"  {status_icon} {key}: ожидалось '{expected_value}', получено '{actual_value}'"
                    )

                if is_valid:
                    logger.info(
                        f"✓ ВАЛИДАЦИЯ УСПЕШНА на попытке {validation_attempt + 1}"
                    )
                    validation_success = True
                    final_status_dict = status_dict
                    break
                else:
                    logger.warning(
                        f"✗ ВАЛИДАЦИЯ НЕУСПЕШНА на попытке {validation_attempt + 1}"
                    )
                    final_errors = errors
                    final_status_dict = status_dict
                    if validation_attempt < max_validation_retries - 1:
                        logger.info("будет повторная попытка валидации...")

            logger.info("=" * 80)
            if validation_success:
                logger.info(f"✓ Шаг '{step_name}': все проверки пройдены")
                if status_callback:
                    status_callback(f"✓ {step_name}: проверки пройдены")
            else:
                error_msg = f"Шаг '{step_name}': ошибки валидации после {max_validation_retries} попыток"
                logger.error(error_msg)
                logger.error("финальные ошибки валидации:")
                for error in final_errors:
                    logger.error(f"  - {error}")
                    test_errors.append(f"{step_name}: {error}")

                if final_status_dict:
                    logger.error("финальный статус устройства:")
                    for key, value in sorted(final_status_dict.items()):
                        logger.error(f"  {key}: {value}")

                all_tests_passed = False
                if status_callback:
                    status_callback(f"{step_name}: ошибки валидации")
                    for error in final_errors:
                        status_callback(f"  - {error}")
            logger.info("=" * 80)

    if all_tests_passed:
        success_msg = "Все тесты пройдены успешно!"
        logger.info(success_msg)
        if status_callback:
            status_callback(success_msg)
        if progress_percent_callback:
            progress_percent_callback(100)
        return True, success_msg
    else:
        error_msg = f"Тестирование завершено с ошибками:\n" + "\n".join(test_errors)
        logger.error(error_msg)
        if status_callback:
            status_callback(error_msg)
        if progress_percent_callback:
            progress_percent_callback(100)
        return False, error_msg


def program_device(
    lv_firmware_path=None,
    hv_firmware_path=None,
    progress_callback=None,
    status_callback=None,
    progress_percent_callback=None,
    stop_check_callback=None,
    uart_port=None,
    device_index=None,
):
    logger = logging.getLogger(__name__)

    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

    programmer = BaseProgrammer()

    devices = programmer.find_devices()
    if not devices:
        error_msg = "Устройства не найдены"
        logger.warning(error_msg)
        if status_callback:
            status_callback(error_msg)

        programmer.close_uart()
        return False, error_msg

    try:
        if device_index is None:
            device_index = 1
            logger.info("Индекс устройства не указан, используется первое устройство")
        else:
            logger.info(f"Используется устройство с индексом {device_index}")

        if device_index < 1 or device_index > len(devices):
            error_msg = f"Неверный индекс устройства: {device_index}. Доступно устройств: {len(devices)}"
            logger.error(error_msg)
            if status_callback:
                status_callback(error_msg)
            return False, error_msg

        selected_device_info = devices[device_index - 1]
        logger.info(f"Выбрано устройство {selected_device_info}")
        if not programmer.select_device(device_index):
            raise RuntimeError(
                f"Не удалось выбрать устройство с индексом {device_index}"
            )

        selected_device = programmer.selected
        selected_address = 0x08000000

        if uart_port is None:
            uart_port = detect_serial_port(selected_device)

        if status_callback:
            status_callback("Инициализация...")
        if progress_callback:
            progress_callback("Инициализация")
        if progress_percent_callback:
            progress_percent_callback(0)

        if uart_port:
            programmer.selected_uart = connect_to_uart_port(uart_port)
        logger.info(f"Открыто UART подключение на порту {uart_port}")

        if status_callback:
            status_callback("Включение питания (начальное)...")

        if programmer.selected_uart:
            logger.info("ожидание стабилизации UART перед первой командой...")
            time.sleep(1.0)
            try:
                programmer.selected_uart.reset_input_buffer()
                programmer.selected_uart.reset_output_buffer()
                logger.info("буферы UART очищены перед первой командой")
                logger.info(
                    f"UART порт состояние: открыт={programmer.selected_uart.is_open}, timeout={programmer.selected_uart.timeout}, baudrate={programmer.selected_uart.baudrate}"
                )
            except Exception as e:
                logger.warning(f"ошибка при очистке буферов: {e}")

        if progress_callback:
            progress_callback("->> SET EN_12V=ON")
        from stm32_programmer.utils.uart_settings import UARTSettings

        uart_settings = UARTSettings()
        line_ending_bytes = uart_settings.get_line_ending_bytes()
        command = "SET EN_12V=ON".strip().encode("utf-8") + line_ending_bytes
        en_12v_success = programmer.send_command_uart(
            command, "EN_12V=ON".strip().encode("utf-8")
        )
        if not en_12v_success:
            error_msg = (
                "Не удалось включить питание (EN_12V=ON): устройство не ответило"
            )
            logger.error(error_msg)
            if status_callback:
                status_callback(error_msg)
            return False, error_msg
        if progress_callback:
            progress_callback("<<- EN_12V=ON")
        if progress_percent_callback:
            progress_percent_callback(2)
        if stop_check_callback and stop_check_callback():
            return False, "Остановлено пользователем"
        time.sleep(1)

        results = {}

        firmware_configs = []
        if lv_firmware_path:
            firmware_configs.append(("LV", lv_firmware_path))
        if hv_firmware_path:
            firmware_configs.append(("HV", hv_firmware_path))

        if not firmware_configs:
            error_msg = "Не выбраны файлы прошивки"
            logger.error(error_msg)
            if status_callback:
                status_callback(error_msg)
            return False, error_msg

        num_modes = len(firmware_configs)
        mode_progress_range = 80 if num_modes == 1 else 40

        for mode_idx, (target_mode, firmware_path) in enumerate(firmware_configs):
            if stop_check_callback and stop_check_callback():
                return False, "Остановлено пользователем"

            base_progress = mode_idx * mode_progress_range
            if status_callback:
                status_callback(f"Переключение в режим {target_mode}...")
            if progress_callback:
                progress_callback(f"Переключение режима: {target_mode}")
            if progress_percent_callback:
                progress_percent_callback(base_progress + 2)

            if uart_port:
                logger.info(f"Выбран UART порт: {uart_port}")
                if programmer.selected_uart is None:
                    try:
                        programmer.selected_uart = connect_to_uart_port(uart_port)
                        logger.info(f"Открыто UART подключение на порту {uart_port}")
                    except serial.SerialException as e:
                        raise ValueError(
                            f"Не удалось открыть UART порт {uart_port}: {e}"
                        )
                        programmer.selected_uart = None

                if programmer.selected_uart:
                    if progress_callback:
                        progress_callback(f"->> SET SWICH_SWD1__2={target_mode}")
                    command_str = f"SET SWICH_SWD1__2={target_mode}".strip()
                    command = command_str.encode("utf-8")
                    expected_response = f"SWICH_SWD1__2={target_mode}".strip().encode(
                        "utf-8"
                    )

                    if command_str.startswith(" "):
                        logger.error(
                            f"ОШИБКА: команда начинается с пробела! '{command_str}'"
                        )
                    logger.debug(
                        f"команда после strip: '{command_str}' (hex: {command.hex()})"
                    )

                    if not command.endswith(b"\n"):
                        from stm32_programmer.utils.uart_settings import UARTSettings

                        uart_settings = UARTSettings()
                        line_ending_bytes = uart_settings.get_line_ending_bytes()
                        command = command + line_ending_bytes
                        logger.info(
                            f"добавлен line ending к команде: {line_ending_bytes.hex()}"
                        )

                    logger.info("=" * 80)
                    logger.info(f"КРИТИЧЕСКАЯ КОМАНДА: SET SWICH_SWD1__2={target_mode}")
                    logger.info(f"платформа: {sys.platform}")
                    logger.info(
                        f"uart порт открыт: {programmer.selected_uart.is_open if programmer.selected_uart else False}"
                    )
                    if programmer.selected_uart:
                        logger.info(f"uart порт имя: {programmer.selected_uart.port}")
                        logger.info(f"uart timeout: {programmer.selected_uart.timeout}")
                        logger.info(
                            f"uart in_waiting до отправки: {programmer.selected_uart.in_waiting}"
                        )

                    max_retries = 5
                    retry_delays = [0.1, 0.2, 0.3, 0.5, 1.0]
                    switch_success = False

                    logger.info("=" * 80)
                    logger.info("ДИАГНОСТИКА ПЕРЕД ОТПРАВКОЙ КОМАНДЫ:")
                    if programmer.selected_uart:
                        logger.info(f"  UART порт: {programmer.selected_uart.port}")
                        logger.info(
                            f"  UART открыт: {programmer.selected_uart.is_open}"
                        )
                        logger.info(
                            f"  UART таймаут: {programmer.selected_uart.timeout}"
                        )
                        logger.info(
                            f"  UART in_waiting: {programmer.selected_uart.in_waiting}"
                        )
                        logger.info(
                            f"  UART baudrate: {programmer.selected_uart.baudrate}"
                        )
                        logger.info(
                            f"  UART bytesize: {programmer.selected_uart.bytesize}"
                        )
                        logger.info(f"  UART parity: {programmer.selected_uart.parity}")
                        logger.info(
                            f"  UART stopbits: {programmer.selected_uart.stopbits}"
                        )
                    else:
                        logger.error("  UART порт не установлен!")
                    logger.info(f"  Команда: {command_str}")
                    logger.info(f"  Команда (hex): {command.hex()}")
                    logger.info(
                        f"  Ожидаемый ответ: {expected_response.decode('utf-8')}"
                    )
                    logger.info(f"  Ожидаемый ответ (hex): {expected_response.hex()}")

                    logger.info("Проверка текущего режима перед переключением...")
                    try:
                        current_mode_check = check_current_mode(
                            programmer, "LV", max_retries=1, retry_delay=0.3
                        )
                        logger.info(f"  Текущий режим LV: {current_mode_check}")
                        current_mode_check = check_current_mode(
                            programmer, "HV", max_retries=1, retry_delay=0.3
                        )
                        logger.info(f"  Текущий режим HV: {current_mode_check}")
                    except Exception as e:
                        logger.warning(f"  Не удалось проверить текущий режим: {e}")
                    logger.info("=" * 80)

                    for attempt in range(max_retries):
                        logger.info(
                            f"попытка {attempt + 1}/{max_retries} отправки команды SET SWICH_SWD1__2={target_mode}"
                        )

                        if attempt > 0:
                            delay = retry_delays[
                                min(attempt - 1, len(retry_delays) - 1)
                            ]
                            logger.info(
                                f"задержка перед повторной попыткой: {delay} сек"
                            )
                            time.sleep(delay)

                        try:
                            if programmer.selected_uart:
                                bytes_before = programmer.selected_uart.in_waiting
                                programmer.selected_uart.reset_input_buffer()
                                logger.info(
                                    f"очищен буфер uart, было байт: {bytes_before}"
                                )
                        except Exception as e:
                            logger.warning(f"ошибка при очистке буфера: {e}")

                        try:
                            logger.info(f"отправка команды (hex): {command.hex()}")
                            logger.info(
                                f"отправка команды (text): {command.decode('utf-8', errors='replace')}"
                            )

                            start_send_time = time.time()
                            programmer.selected_uart.write(command)
                            programmer.selected_uart.flush()
                            send_duration = time.time() - start_send_time
                            logger.info(
                                f"команда отправлена за {send_duration:.4f} сек"
                            )

                            post_send_delay = retry_delays[
                                min(attempt, len(retry_delays) - 1)
                            ]
                            logger.info(
                                f"задержка после отправки: {post_send_delay} сек"
                            )
                            time.sleep(post_send_delay)

                        except Exception as e:
                            logger.error(
                                f"ошибка при отправке команды (попытка {attempt + 1}): {e}"
                            )
                            import traceback

                            logger.error(f"трассировка: {traceback.format_exc()}")
                            continue

                        try:
                            logger.info(f"ожидание ответа (попытка {attempt + 1})...")

                            response = None
                            buffer = b""
                            max_wait_time = 3.0 if sys.platform == "win32" else 2.0
                            start_read_time = time.time()

                            while (time.time() - start_read_time) < max_wait_time:
                                if not programmer.selected_uart.is_open:
                                    logger.warning(
                                        "UART порт закрыт во время чтения ответа"
                                    )
                                    break

                                if programmer.selected_uart.in_waiting > 0:
                                    data = programmer.selected_uart.read(
                                        programmer.selected_uart.in_waiting
                                    )
                                    if data:
                                        buffer += data
                                        logger.info(
                                            f"прочитано {len(data)} байт, всего: {len(buffer)} байт"
                                        )

                                        if b"\n" in buffer or b"\r" in buffer:
                                            break
                                        if expected_response in buffer:
                                            break
                                time.sleep(0.01)

                            if buffer:
                                response = buffer.strip()
                                response = response.rstrip(b"\r\n").rstrip(b"\n\r")
                                logger.info(
                                    f"получен ответ (text): {response.decode('utf-8', errors='replace')}"
                                )
                                logger.info(f"получен ответ (hex): {response.hex()}")

                                if response == expected_response:
                                    switch_success = True
                                    logger.info(f"успех на попытке {attempt + 1}!")
                                    break
                                else:
                                    logger.warning(
                                        f"ответ не совпадает на попытке {attempt + 1}"
                                    )
                                    logger.warning(
                                        f"ожидали: {expected_response.decode('utf-8')}"
                                    )
                                    logger.warning(
                                        f"получили: {response.decode('utf-8', errors='replace')}"
                                    )
                            else:
                                logger.warning(
                                    f"не получен ответ на попытке {attempt + 1}, буфер пуст"
                                )
                                if programmer.selected_uart:
                                    logger.warning(
                                        f"uart in_waiting после неудачи: {programmer.selected_uart.in_waiting}"
                                    )

                                logger.info("ожидание задержанного ответа (0.5 сек)...")
                                time.sleep(0.5)
                                delayed_buffer = b""
                                delayed_start_time = time.time()
                                delayed_wait_time = 2.0  # Дополнительное ожидание для задержанных ответов
                                logger.info(
                                    f"дополнительное чтение ответа в течение {delayed_wait_time} сек..."
                                )
                                while (
                                    time.time() - delayed_start_time
                                ) < delayed_wait_time:
                                    if (
                                        programmer.selected_uart
                                        and programmer.selected_uart.is_open
                                    ):
                                        if programmer.selected_uart.in_waiting > 0:
                                            delayed_data = (
                                                programmer.selected_uart.read(
                                                    programmer.selected_uart.in_waiting
                                                )
                                            )
                                            if delayed_data:
                                                delayed_buffer += delayed_data
                                                logger.info(
                                                    f"дополнительно прочитано {len(delayed_data)} байт, всего: {len(delayed_buffer)} байт"
                                                )
                                                if (
                                                    b"\n" in delayed_buffer
                                                    or b"\r" in delayed_buffer
                                                ):
                                                    logger.info(
                                                        "найден символ конца строки в дополнительном ответе"
                                                    )
                                                    break
                                    time.sleep(0.05)

                                if delayed_buffer:
                                    try:
                                        delayed_response = delayed_buffer.strip()
                                        delayed_response = delayed_response.rstrip(
                                            b"\r\n"
                                        ).rstrip(b"\n\r")
                                        logger.info(
                                            f"дополнительный ответ (text): {delayed_response.decode('utf-8', errors='replace')}"
                                        )
                                        logger.info(
                                            f"дополнительный ответ (hex): {delayed_buffer.hex()}"
                                        )

                                        if delayed_response == expected_response:
                                            switch_success = True
                                            logger.info(
                                                "дополнительный ответ совпадает с ожидаемым!"
                                            )
                                            break
                                    except:
                                        pass
                                else:
                                    logger.warning(
                                        f"дополнительный ответ не получен после ожидания {delayed_wait_time} сек"
                                    )

                        except Exception as e:
                            logger.error(
                                f"ошибка при получении ответа (попытка {attempt + 1}): {e}"
                            )
                            import traceback

                            logger.error(f"трассировка: {traceback.format_exc()}")
                            continue

                    if not switch_success:
                        logger.warning("=" * 80)
                        logger.warning(
                            "ВСЕ СТАНДАРТНЫЕ ПОПЫТКИ НЕУДАЧНЫ, ПРОБУЕМ АЛЬТЕРНАТИВНЫЕ ВАРИАНТЫ"
                        )
                        logger.warning("=" * 80)

                        logger.info("АЛЬТЕРНАТИВА 1: Проверка текущего режима...")
                        try:
                            if check_current_mode(
                                programmer, target_mode, max_retries=2, retry_delay=0.5
                            ):
                                logger.info(f"✓ Режим {target_mode} уже установлен!")
                                switch_success = True
                        except Exception as e:
                            logger.warning(f"ошибка при проверке текущего режима: {e}")

                        if not switch_success:
                            logger.info(
                                "АЛЬТЕРНАТИВА 2: Отправка команды без пробела после SET..."
                            )
                            try:
                                alt_command_str = (
                                    f"SETSWICH_SWD1__2={target_mode}".strip()
                                )
                                alt_command = alt_command_str.encode("utf-8")
                                from stm32_programmer.utils.uart_settings import (
                                    UARTSettings,
                                )

                                uart_settings = UARTSettings()
                                line_ending_bytes = (
                                    uart_settings.get_line_ending_bytes()
                                )
                                alt_command = alt_command + line_ending_bytes

                                logger.info(
                                    f"отправка альтернативной команды: {alt_command_str}"
                                )
                                alt_success = programmer.send_command_uart(
                                    alt_command, expected_response
                                )

                                if alt_success:
                                    logger.info("✓ Альтернативная команда успешна!")
                                    switch_success = True
                                else:
                                    logger.warning(
                                        "альтернативная команда не получила ответа"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"ошибка при отправке альтернативной команды: {e}"
                                )

                        if not switch_success:
                            logger.info(
                                "АЛЬТЕРНАТИВА 3: Отправка команды с нижним регистром..."
                            )
                            try:
                                alt_command_str = (
                                    f"set swich_swd1__2={target_mode.lower()}".strip()
                                )
                                alt_command = alt_command_str.encode("utf-8")
                                from stm32_programmer.utils.uart_settings import (
                                    UARTSettings,
                                )

                                uart_settings = UARTSettings()
                                line_ending_bytes = (
                                    uart_settings.get_line_ending_bytes()
                                )
                                alt_command = alt_command + line_ending_bytes
                                alt_expected = f"swich_swd1__2={target_mode.lower()}".strip().encode(
                                    "utf-8"
                                )

                                logger.info(
                                    f"отправка альтернативной команды (lowercase): {alt_command_str}"
                                )
                                alt_success = programmer.send_command_uart(
                                    alt_command, alt_expected
                                )

                                if alt_success:
                                    logger.info(
                                        "✓ Альтернативная команда (lowercase) успешна!"
                                    )
                                    switch_success = True
                                else:
                                    logger.warning(
                                        "альтернативная команда (lowercase) не получила ответа"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"ошибка при отправке альтернативной команды (lowercase): {e}"
                                )

                        if not switch_success:
                            logger.info(
                                "АЛЬТЕРНАТИВА 4: Прямая отправка команды без ожидания ответа..."
                            )
                            try:
                                if (
                                    programmer.selected_uart
                                    and programmer.selected_uart.is_open
                                ):
                                    programmer.selected_uart.reset_input_buffer()
                                    programmer.selected_uart.write(command)
                                    programmer.selected_uart.flush()
                                    logger.info(
                                        "команда отправлена напрямую, ожидание 2 секунды..."
                                    )
                                    time.sleep(2.0)

                                    if check_current_mode(
                                        programmer,
                                        target_mode,
                                        max_retries=3,
                                        retry_delay=0.5,
                                    ):
                                        logger.info(
                                            f"✓ Режим {target_mode} установлен после прямой отправки!"
                                        )
                                        switch_success = True
                                    else:
                                        logger.warning(
                                            "режим не установлен после прямой отправки"
                                        )
                            except Exception as e:
                                logger.warning(
                                    f"ошибка при прямой отправке команды: {e}"
                                )

                        if not switch_success:
                            logger.info(
                                "АЛЬТЕРНАТИВА 5: Отправка команды с CRLF вместо LF..."
                            )
                            try:
                                alt_command = command_str.encode("utf-8") + b"\r\n"

                                logger.info(f"отправка команды с CRLF: {command_str}")
                                alt_success = programmer.send_command_uart(
                                    alt_command, expected_response
                                )

                                if alt_success:
                                    logger.info("✓ Команда с CRLF успешна!")
                                    switch_success = True
                                else:
                                    logger.warning("команда с CRLF не получила ответа")
                            except Exception as e:
                                logger.warning(
                                    f"ошибка при отправке команды с CRLF: {e}"
                                )

                        logger.warning("=" * 80)
                        logger.warning(
                            f"РЕЗУЛЬТАТ АЛЬТЕРНАТИВНЫХ ВАРИАНТОВ: {'успех' if switch_success else 'неудача'}"
                        )
                        logger.warning("=" * 80)

                    logger.info(
                        f"результат всех попыток: {'успех' if switch_success else 'неудача'}"
                    )
                    logger.info("=" * 80)

                    if switch_success and progress_callback:
                        progress_callback(f"<<- {expected_response.decode('utf-8')}")

                    if not switch_success:
                        error_msg = f"Не удалось переключить режим на {target_mode} после {max_retries} попыток и всех альтернативных вариантов"
                        logger.error(error_msg)
                        if status_callback:
                            status_callback(error_msg)
                        results[target_mode] = False
                        continue

                    if status_callback:
                        status_callback(
                            f"Проверка переключения режима {target_mode}..."
                        )
                    if progress_callback:
                        progress_callback("Проверка переключения")
                    if progress_percent_callback:
                        progress_percent_callback(base_progress + 5)

                    logger.info(
                        f"Команда переключения на {target_mode} отправлена, проверяем текущий режим..."
                    )

                    mode_check_retries = 3
                    mode_check_delay = 1.0
                    mode_confirmed = False

                    for check_attempt in range(mode_check_retries):
                        if check_attempt > 0:
                            logger.warning(
                                f"Повторная проверка режима (попытка {check_attempt + 1}/{mode_check_retries})..."
                            )
                            time.sleep(mode_check_delay)

                        if check_current_mode(
                            programmer, target_mode, max_retries=2, retry_delay=0.3
                        ):
                            mode_confirmed = True
                            logger.info(f"Режим {target_mode} подтвержден")
                            break
                        else:
                            logger.warning(
                                f"Режим {target_mode} не подтвержден (попытка {check_attempt + 1}/{mode_check_retries})"
                            )

                    if not mode_confirmed:
                        error_msg = (
                            f"Не удалось подтвердить переключение в режим {target_mode}"
                        )
                        logger.error(error_msg)
                        if status_callback:
                            status_callback(error_msg)
                        results[target_mode] = False
                        continue

                    if status_callback:
                        status_callback(
                            f"Стабилизация после переключения в режим {target_mode}..."
                        )
                    if progress_callback:
                        progress_callback("Стабилизация")
                    if progress_percent_callback:
                        progress_percent_callback(base_progress + 8)

                    logger.warning(
                        f"Переключение в режим {target_mode} подтверждено, ожидание стабилизации..."
                    )
                    stabilization_time = 5 if target_mode == "LV" else 4
                    for _ in range(int(stabilization_time * 10)):
                        if stop_check_callback and stop_check_callback():
                            return False, "Остановлено пользователем"
                        time.sleep(0.1)
                    if progress_percent_callback:
                        progress_percent_callback(base_progress + 10)

                    logger.warning(
                        "Повторный поиск устройства после переключения режима..."
                    )
                    max_retries = 5
                    retry_delay = 2.0
                    device_found = False

                    for retry in range(max_retries):
                        devices = programmer.find_devices()
                        if devices:
                            if device_index <= len(
                                devices
                            ) and programmer.select_device(device_index):
                                logger.warning(
                                    f"устройство перевыбрано после переключения режима (попытка {retry + 1}/{max_retries}, индекс {device_index})"
                                )
                                device_found = True
                                post_select_delay = 4 if target_mode == "HV" else 5
                                logger.warning(
                                    f"ожидание {post_select_delay} секунд для стабилизации SWD интерфейса..."
                                )
                                for _ in range(int(post_select_delay * 10)):
                                    if stop_check_callback and stop_check_callback():
                                        return False, "Остановлено пользователем"
                                    time.sleep(0.1)
                                break
                            else:
                                logger.warning(
                                    f"не удалось перевыбрать устройство с индексом {device_index} (попытка {retry + 1}/{max_retries})"
                                )
                        else:
                            logger.warning(
                                f"устройство не найдено после переключения режима (попытка {retry + 1}/{max_retries})"
                            )

                        if retry < max_retries - 1:
                            time.sleep(retry_delay)

                    if not device_found:
                        logger.error(
                            "устройство не найдено после всех попыток переподключения"
                        )
                        results[target_mode] = False
                        continue
                else:
                    logger.warning("Не удалось определить UART порт")

            if status_callback:
                status_callback(f"Загрузка прошивки для режима {target_mode}...")
            if progress_callback:
                progress_callback(f"Загрузка прошивки: {target_mode}")
            if progress_percent_callback:
                progress_percent_callback(base_progress + 15)

            try:
                firmware_start, firmware_data, firmware_file = load_firmware_image(
                    firmware_path
                )
            except (FileNotFoundError, ValueError) as firmware_error:
                error_msg = f"Не удалось загрузить прошивку для режима {target_mode}: {firmware_error}"
                logger.error(error_msg)
                results[target_mode] = False
                if status_callback:
                    status_callback(error_msg)
                continue

            if selected_address != firmware_start:
                error_msg = f"Предупреждение: адрес прошивки и выбранный адрес не совпадают. Прошивка рассчитана на {hex(firmware_start)}, выбрано {hex(selected_address)}."
                logger.warning(error_msg)

            if status_callback:
                status_callback(f"Запись {target_mode} прошивки...")
            if progress_callback:
                progress_callback(f"Запись прошивки: {target_mode}")
            if progress_percent_callback:
                progress_percent_callback(base_progress + 20)

            logger.info(
                f"Запись прошивки {firmware_file.name} размером {len(firmware_data)} байт "
                f"в Flash начало (адрес {hex(selected_address)})..."
            )

            if stop_check_callback and stop_check_callback():
                return False, "Остановлено пользователем"

            write_result = programmer.write_bytes(firmware_data, selected_address)

            if isinstance(write_result, tuple):
                success, error_details = write_result
            else:
                success = write_result
                error_details = None

            if progress_percent_callback:
                progress_percent_callback(base_progress + 60)

            if not success:
                if error_details:
                    error_msg = (
                        f"Ошибка записи для режима {target_mode}: {error_details}"
                    )
                else:
                    error_msg = f"Ошибка записи для режима {target_mode}"
                logger.error(error_msg)
                results[target_mode] = False
                if status_callback:
                    status_callback(error_msg)
                return False, error_msg

            if status_callback:
                status_callback(f"Перезагрузка питания после записи {target_mode}...")
            if progress_callback:
                progress_callback("Перезагрузка питания")
                progress_callback("->> SET EN_12V=OFF")
            if progress_percent_callback:
                progress_percent_callback(base_progress + 65)

            from stm32_programmer.utils.uart_settings import UARTSettings

            uart_settings = UARTSettings()
            line_ending_bytes = uart_settings.get_line_ending_bytes()

            command_off = "SET EN_12V=OFF".strip().encode("utf-8") + line_ending_bytes
            programmer.send_command_uart(
                command_off, "EN_12V=OFF".strip().encode("utf-8")
            )
            if progress_callback:
                progress_callback("<<- EN_12V=OFF")
            time.sleep(1)

            if progress_callback:
                progress_callback("->> SET EN_12V=ON")
            command_on = "SET EN_12V=ON".strip().encode("utf-8") + line_ending_bytes
            programmer.send_command_uart(
                command_on, "EN_12V=ON".strip().encode("utf-8")
            )
            if progress_callback:
                progress_callback("<<- EN_12V=ON")
            if progress_percent_callback:
                progress_percent_callback(base_progress + 70)

            logger.warning(f"Результат записи для {target_mode}: успех")
            results[target_mode] = True

            if status_callback:
                status_callback(f"{target_mode}: ЗАПИСАН")

            if progress_percent_callback:
                if target_mode == "LV" and num_modes == 2:
                    progress_percent_callback(40)
                elif target_mode == "LV" and num_modes == 1:
                    progress_percent_callback(80)
                elif target_mode == "HV":
                    progress_percent_callback(80)

            if target_mode == "LV":
                if status_callback:
                    status_callback("Переподключение устройства после записи LV...")
                if progress_callback:
                    progress_callback("Переподключение устройства")
                if progress_percent_callback:
                    progress_percent_callback(base_progress + 75)

                logger.warning("ожидание стабилизации устройства после записи LV...")
                for _ in range(50):
                    if stop_check_callback and stop_check_callback():
                        return False, "Остановлено пользователем"
                    time.sleep(0.1)

                logger.warning("переподключение к устройству...")
                max_reconnect_retries = 5
                reconnect_delay = 2.0
                device_reconnected = False

                for retry in range(max_reconnect_retries):
                    if stop_check_callback and stop_check_callback():
                        return False, "Остановлено пользователем"

                    devices = programmer.find_devices()
                    if devices:
                        if device_index <= len(devices) and programmer.select_device(
                            device_index
                        ):
                            logger.warning(
                                f"устройство переподключено (попытка {retry + 1}/{max_reconnect_retries}, индекс {device_index})"
                            )
                            device_reconnected = True
                            for _ in range(30):
                                if stop_check_callback and stop_check_callback():
                                    return False, "Остановлено пользователем"
                                time.sleep(0.1)
                            break
                        else:
                            logger.warning(
                                f"не удалось перевыбрать устройство с индексом {device_index} (попытка {retry + 1}/{max_reconnect_retries})"
                            )
                    else:
                        logger.warning(
                            f"устройство не найдено для переподключения (попытка {retry + 1}/{max_reconnect_retries})"
                        )

                    if retry < max_reconnect_retries - 1:
                        for _ in range(int(reconnect_delay * 10)):
                            if stop_check_callback and stop_check_callback():
                                return False, "Остановлено пользователем"
                            time.sleep(0.1)

                if not device_reconnected:
                    logger.error(
                        "не удалось переподключиться к устройству после записи LV"
                    )
                    logger.warning("продолжаем, но запись HV может не удаться")
                    for _ in range(50):
                        if stop_check_callback and stop_check_callback():
                            return False, "Остановлено пользователем"
                        time.sleep(0.1)

                if progress_percent_callback and num_modes == 2:
                    progress_percent_callback(40)

        success = all(results.values()) if results else False
        test_success = None
        test_message = None

        if success:
            if status_callback:
                status_callback("Результат: УСПЕХ")
            logger.warning("Программа успешно завершена")

            if programmer.selected_uart and programmer.selected_uart.is_open:
                test_success, test_message = run_test_plan(
                    programmer,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                    progress_percent_callback=progress_percent_callback,
                )

                if test_success:
                    if status_callback:
                        status_callback("Все тесты пройдены успешно!")
                    logger.info("Тестирование завершено успешно")
                else:
                    error_msg = f"ОШИБКА: Тестирование не пройдено!\n\n{test_message}"
                    if status_callback:
                        status_callback(error_msg)
                    logger.error(f"Тестирование не пройдено: {test_message}")
            else:
                logger.warning("UART порт не открыт, пропускаем тестирование")
                test_success = True  # Нет тестирования - считаем успехом
        else:
            failed_modes = [mode for mode, result in results.items() if not result]
            error_msg = f"Ошибка записи для режимов: {', '.join(failed_modes)}"
            if status_callback:
                status_callback(error_msg)

        if success:
            if test_success is None or test_success:
                return True, "Успех. Все тесты пройдены." if test_success else "Успех"
            else:
                error_msg = f"ОШИБКА: Тестирование не пройдено!\n\n{test_message}"
                return False, error_msg
        else:
            return False, error_msg

    except Exception as e:
        import traceback

        error_msg = f"Критическая ошибка: {e}"
        logger.error("=" * 80)
        logger.error(f"Критическая ошибка: {type(e).__name__}")
        logger.error(f"Сообщение: {str(e)}")
        logger.error("Трассировка стека:")
        for line in traceback.format_exc().strip().split("\n"):
            logger.error(f"  {line}")
        logger.error("=" * 80)
        if status_callback:
            status_callback(error_msg)
        return False, error_msg
    finally:

        if programmer and programmer.selected_uart:
            try:
                if programmer.selected_uart.is_open:
                    logger.info("=" * 80)
                    logger.info("ВЫКЛЮЧЕНИЕ ПИТАНИЯ В БЛОКЕ FINALLY (гарантированно)")
                    logger.info("=" * 80)
                    if status_callback:
                        status_callback(
                            "Выключение питания (финальное, гарантированно)..."
                        )
                    if progress_callback:
                        progress_callback("->> SET EN_12V=OFF")
                    from stm32_programmer.utils.uart_settings import UARTSettings

                    uart_settings = UARTSettings()
                    line_ending_bytes = uart_settings.get_line_ending_bytes()
                    command_off = (
                        "SET EN_12V=OFF".strip().encode("utf-8") + line_ending_bytes
                    )
                    try:
                        programmer.send_command_uart(
                            command_off, "EN_12V=OFF".strip().encode("utf-8")
                        )
                        if progress_callback:
                            progress_callback("<<- EN_12V=OFF")
                        logger.info("Питание выключено в блоке finally")
                        time.sleep(0.5)
                    except Exception as send_error:
                        logger.warning(
                            f"Ошибка при отправке команды EN_12V=OFF: {send_error}"
                        )

                        try:
                            if programmer.selected_uart.is_open:
                                programmer.selected_uart.write(command_off)
                                programmer.selected_uart.flush()
                                logger.info(
                                    "Команда EN_12V=OFF отправлена напрямую (без ожидания ответа)"
                                )
                        except Exception as direct_error:
                            logger.warning(
                                f"Ошибка при прямой отправке EN_12V=OFF: {direct_error}"
                            )
                else:
                    logger.warning(
                        "UART порт уже закрыт в блоке finally, пропускаем выключение питания"
                    )
            except (ValueError, OSError, IOError) as e:
                error_msg_lower = str(e).lower()
                if (
                    "closed" in error_msg_lower
                    or "operation on closed" in error_msg_lower
                ):
                    logger.warning(
                        f"Попытка выключить питание на закрытом порту в блоке finally: {e}"
                    )
                else:
                    logger.warning(
                        f"Ошибка при выключении питания в блоке finally (порт закрыт): {e}"
                    )
            except Exception as e:
                logger.warning(
                    f"Неожиданная ошибка при выключении питания в блоке finally: {e}"
                )
        else:
            logger.warning(
                "UART объект не инициализирован в блоке finally, пропускаем выключение питания"
            )

        if programmer:
            programmer.close_uart()
