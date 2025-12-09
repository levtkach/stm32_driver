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

    try:
        serial_port = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

        serial_port.dtr = False
        serial_port.rts = False

        if serial_port.is_open:
            logger = logging.getLogger(__name__)
            logger.info(
                f"[UART] подключено к {port_name} (baud={baudrate}, line_ending={line_ending})"
            )
            return serial_port
        else:
            raise serial.SerialException(f"Не удалось открыть {port_name}")

    except serial.SerialException as e:
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
            command = f"SET SWICH_SWD1__2={expected_mode}".encode("utf-8")
            expected_response = f"SWICH_SWD1__2={expected_mode}".encode("utf-8")
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
        return status_dict

    lines = response_text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        key = None
        value = None

        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
        elif "=" in line:
            parts = line.split("=", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()

        if key and value is not None:
            status_dict[key] = value

    logger.debug(f"Распарсенный статус: {len(status_dict)} параметров")
    logger.debug(f"Примеры параметров: {list(status_dict.items())[:5]}")
    return status_dict


def get_status_from_uart(programmer, timeout=5.0):
    logger = logging.getLogger(__name__)

    if not programmer.selected_uart or not programmer.selected_uart.is_open:
        logger.error("UART порт не открыт")
        return None

    try:
        programmer.selected_uart.reset_input_buffer()
        command = "GET STATUS\n".encode("utf-8")
        programmer.selected_uart.write(command)
        programmer.selected_uart.flush()

        time.sleep(0.2)

        buffer = b""
        start_time = time.time()
        last_data_time = start_time
        max_idle_time = 0.5

        while (time.time() - start_time) < timeout:
            if programmer.selected_uart.in_waiting > 0:
                data = programmer.selected_uart.read(
                    programmer.selected_uart.in_waiting
                )
                if data:
                    buffer += data
                    last_data_time = time.time()
            else:
                if buffer and (time.time() - last_data_time) > max_idle_time:
                    break
            time.sleep(0.05)

        if buffer:
            response = buffer.decode("utf-8", errors="replace").strip()
            logger.debug(f"Получен ответ GET STATUS ({len(response)} символов)")
            logger.debug(f"Первые 300 символов: {response[:300]}")
            return response
        else:
            logger.warning("Не получен ответ на GET STATUS")
            return None

    except Exception as e:
        logger.error(f"Ошибка при получении статуса: {e}")
        return None


def validate_status(status_dict, expected_values, ignore_fields=None):
    logger = logging.getLogger(__name__)
    errors = []
    warnings = []

    if ignore_fields is None:
        ignore_fields = []

    for key, expected_value in expected_values.items():
        if key in ignore_fields:
            continue

        actual_value = status_dict.get(key)

        if actual_value is None:
            errors.append(f"Параметр '{key}' не найден в ответе")
        elif str(actual_value).strip() != str(expected_value).strip():
            errors.append(
                f"Параметр '{key}': ожидалось '{expected_value}', получено '{actual_value}'"
            )

    is_valid = len(errors) == 0
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
        command = step.get("command", "")
        expected_response = step.get("expected_response")
        wait_time = step.get("wait_time", 0)
        description = step.get("description", "")
        validation = step.get("validation")

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
            if expected_response:
                expected_response_bytes = expected_response.encode("utf-8")

                if command.startswith("SET"):
                    original_timeout = programmer.selected_uart.timeout
                    programmer.selected_uart.timeout = 2.0
                    success = programmer.send_command_uart(
                        command_bytes, expected_response_bytes
                    )
                    programmer.selected_uart.timeout = original_timeout
                else:
                    success = programmer.send_command_uart(
                        command_bytes, expected_response_bytes
                    )

                if not success:
                    time.sleep(0.3)
                    actual_response = None
                    buffer = b""
                    start_time = time.time()
                    while (time.time() - start_time) < 1.0:
                        if programmer.selected_uart.in_waiting > 0:
                            data = programmer.selected_uart.read(
                                programmer.selected_uart.in_waiting
                            )
                            if data:
                                buffer += data
                                if b"\n" in buffer or b"\r" in buffer:
                                    break
                        time.sleep(0.05)

                    if buffer:
                        try:
                            actual_response = buffer.decode(
                                "utf-8", errors="replace"
                            ).strip()
                        except:
                            actual_response = str(buffer)

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

        if command == "GET STATUS" and validation:
            status_response = get_status_from_uart(programmer, timeout=5.0)

            if status_response:
                if progress_callback:
                    for line in status_response.split("\n"):
                        if line.strip():
                            progress_callback(f"<<- {line.strip()}")

                status_dict = parse_status_response(status_response)

                expected_values = validation.get("expected_values", {})
                ignore_fields = validation.get("ignore_fields", [])

                is_valid, errors, warnings = validate_status(
                    status_dict, expected_values, ignore_fields
                )

                if is_valid:
                    logger.info(f"Шаг '{step_name}': все проверки пройдены")
                    if status_callback:
                        status_callback(f"✓ {step_name}: проверки пройдены")
                else:
                    error_msg = f"Шаг '{step_name}': ошибки валидации"
                    logger.error(error_msg)
                    for error in errors:
                        logger.error(f"  - {error}")
                        test_errors.append(f"{step_name}: {error}")
                    all_tests_passed = False
                    if status_callback:
                        status_callback(f"{step_name}: ошибки валидации")
                        for error in errors:
                            status_callback(f"  - {error}")
            else:
                error_msg = f"Шаг '{step_name}': не получен ответ на GET STATUS"
                logger.error(error_msg)
                test_errors.append(error_msg)
                all_tests_passed = False
                if status_callback:
                    status_callback(error_msg)

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
        if progress_callback:
            progress_callback("->> SET EN_12V=ON")
        from stm32_programmer.utils.uart_settings import UARTSettings

        uart_settings = UARTSettings()
        line_ending_bytes = uart_settings.get_line_ending_bytes()
        command = "SET EN_12V=ON".encode("utf-8") + line_ending_bytes
        programmer.send_command_uart(command, "EN_12V=ON".encode("utf-8"))
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
                    command = f"SET SWICH_SWD1__2={target_mode}".encode("utf-8")
                    expected_response = f"SWICH_SWD1__2={target_mode}".encode("utf-8")
                    switch_success = programmer.send_command_uart(
                        command, expected_response
                    )

                    if switch_success and progress_callback:
                        progress_callback(f"<<- {expected_response.decode('utf-8')}")

                    if not switch_success:
                        error_msg = f"Не удалось переключить режим на {target_mode}"
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

            command_off = "SET EN_12V=OFF".encode("utf-8") + line_ending_bytes
            programmer.send_command_uart(command_off, "EN_12V=OFF".encode("utf-8"))
            if progress_callback:
                progress_callback("<<- EN_12V=OFF")
            time.sleep(1)

            if progress_callback:
                progress_callback("->> SET EN_12V=ON")
            command_on = "SET EN_12V=ON".encode("utf-8") + line_ending_bytes
            programmer.send_command_uart(command_on, "EN_12V=ON".encode("utf-8"))
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
                    return True, "Успех. Все тесты пройдены."
                else:
                    error_msg = f"ОШИБКА: Тестирование не пройдено!\n\n{test_message}"
                    if status_callback:
                        status_callback(error_msg)
                    logger.error(f"Тестирование не пройдено: {test_message}")
                    return False, error_msg
            else:
                logger.warning("UART порт не открыт, пропускаем тестирование")
                return True, "Успех"
        else:
            failed_modes = [mode for mode, result in results.items() if not result]
            error_msg = f"Ошибка записи для режимов: {', '.join(failed_modes)}"
            if status_callback:
                status_callback(error_msg)
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
