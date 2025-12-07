import sys
import io
import logging
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Создаем директорию для логов
log_dir = Path(__file__).resolve().parent / "logs"
log_dir.mkdir(exist_ok=True)

# Создаем имя файла на основе даты и времени
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = log_dir / f"{timestamp}.log"

# Настраиваем логирование с выводом в консоль и файл
handlers = [
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(log_filename, encoding="utf-8"),
]

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)

logger = logging.getLogger(__name__)

from programmer_base import BaseProgrammer
from serial.tools import list_ports
import serial
from pathlib import Path
import time


def connect_to_uart_port(port_name, baudrate=115200):
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
            logger.info(f"[UART] подключено к {port_name}")
            return serial_port
        else:
            raise serial.SerialException(f"Не удалось открыть {port_name}")

    except serial.SerialException as e:
        raise serial.SerialException(f"Ошибка подключения к {port_name}: {e}")
    except Exception as e:
        raise Exception(f"Ошибка при открытии порта {port_name}: {e}")


def main():
    banner = """
================================================================================
================================================================================
================================================================================
                                                                                
                        ПРОГРАММА ЗАПУЩЕНА                                      
                                                                                
================================================================================
================================================================================
================================================================================
"""
    print(banner)
    logger.warning(f"Логи записываются в файл: {log_filename}")

    programmer = BaseProgrammer()

    devices = programmer.find_devices()
    if not devices:
        logger.warning("Устройства не найдены")
        return
    try:

        first_device = devices[0]
        logger.info(f"Выбрано устройство {first_device}")
        if not programmer.select_device(1):
            raise RuntimeError("Нет доступных устройств")
        selected_device = programmer.selected
        selected_address = 0x08000000
        selected_description = "Flash начало"
        uart_port = detect_serial_port(selected_device)
        programmer.selected_uart = connect_to_uart_port(uart_port, baudrate=115200)
        logger.info(f"Открыто UART подключение на порту {uart_port}")
        programmer.send_command_uart(
            "SET EN_12V=ON\n".encode("utf-8"), "EN_12V=ON".encode("utf-8")
        )
        time.sleep(1)
        for target_mode in ("LV", "HV"):

            if uart_port:
                logger.info(f"Выбран UART порт: {uart_port}")
                if programmer.selected_uart is None:
                    try:
                        programmer.selected_uart = connect_to_uart_port(
                            uart_port, baudrate=115200
                        )
                        logger.info(f"Открыто UART подключение на порту {uart_port}")
                    except serial.SerialException as e:
                        raise ValueError(
                            f"Не удалось открыть UART порт {uart_port}: {e}"
                        )
                        programmer.selected_uart = None
                if programmer.selected_uart:
                    command = f"SET SWICH_SWD1__2={target_mode}\n".encode("utf-8")
                    expected_response = f"SWICH_SWD1__2={target_mode}".encode("utf-8")

                    programmer.send_command_uart(command, expected_response)

                    time.sleep(2)
            else:
                logger.warning("Не удалось определить UART порт")

            if target_mode is None:
                target_mode = prompt_target_mode()

            try:
                firmware_start, firmware_data, firmware_path = load_firmware_image(
                    target_mode
                )
            except (FileNotFoundError, ValueError) as firmware_error:
                logger.error(
                    f"Не удалось загрузить прошивку для режима {target_mode}: {firmware_error}"
                )
                return

            if selected_address != firmware_start:
                raise ValueError(
                    "Предупреждение: адрес прошивки и выбранный адрес не совпадают. "
                    f"Прошивка рассчитана на {hex(firmware_start)}, выбрано {hex(selected_address)}."
                )

            logger.error(
                f"Запись прошивки {firmware_path.name} размером {len(firmware_data)} байт "
                f"в {selected_description} (адрес {hex(selected_address)})..."
            )

            success = programmer.write_bytes(firmware_data, selected_address)

            if not success:
                logger.error(f"Ошибка записи для режима {target_mode}")
                print(f"\n❌ ОШИБКА: Не удалось записать прошивку для режима {target_mode}")
                print("Проверьте подключение устройства и попробуйте снова.")
                return

            programmer.send_command_uart(
                "SET EN_12V=OFF\n".encode("utf-8"), "EN_12V=OFF".encode("utf-8")
            )

            time.sleep(1)
            programmer.send_command_uart(
                "SET EN_12V=ON\n".encode("utf-8"), "EN_12V=ON".encode("utf-8")
            )

            logger.warning(f"Результат записи для {target_mode}: успех")
            print(f"✅ Прошивка для режима {target_mode} успешно записана")

            if target_mode == "LV":
                logger.warning("ожидание стабилизации устройства после записи LV...")
                time.sleep(3)

                logger.warning("переподключение к устройству...")
                devices = programmer.find_devices()
                if devices:
                    if not programmer.select_device(1):
                        logger.warning("не удалось переподключиться к устройству")
                    else:
                        logger.warning("устройство переподключено")
                else:
                    logger.warning("устройство не найдено для переподключения")
    
    print("\n✅ Программа успешно завершена")
    logger.warning("Программа успешно завершена")
    except Exception as e:
        import traceback
        logger.error("=" * 80)
        logger.error(f"Критическая ошибка: {type(e).__name__}")
        logger.error(f"Сообщение: {str(e)}")
        logger.error("Трассировка стека:")
        for line in traceback.format_exc().strip().split("\n"):
            logger.error(f"  {line}")
        logger.error("=" * 80)
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("Подробности записаны в лог файл.")
        return


def detect_serial_port(selected_device):
    if not selected_device:
        return None

    try:
        ports = list(list_ports.comports())
    except Exception:
        return None

    if not ports:
        return None

    vid = selected_device.get("vid")
    pid = selected_device.get("pid")

    TARGET_UART_VID = 0x1A86
    TARGET_UART_PID = 0x7523

    def is_target_uart(port):
        if port.vid is not None and port.pid is not None:
            return port.vid == TARGET_UART_VID and port.pid == TARGET_UART_PID
        hwid = (port.hwid or "").upper()
        signature = f"VID:PID={TARGET_UART_VID:04X}:{TARGET_UART_PID:04X}"
        return signature in hwid

    matching_ports = [p for p in ports if is_target_uart(p)]

    if len(matching_ports) == 1:
        return matching_ports[0].device

    if len(matching_ports) == 0:
        raise RuntimeError(
            "UART устройство с VID=0x1A86 и PID=0x7523 не найдено. Подключите устройство и попробуйте снова."
        )

    raise RuntimeError(
        "Обнаружено несколько UART устройств с VID=0x1A86 и PID=0x7523. "
        "Отключите лишние устройства и повторите попытку."
    )


def _auto_select_serial_port(ports, selected_vid, selected_pid):
    if not ports:
        return None

    known_serial_vid_pid = {
        (0x1A86, 0x7523),
    }

    def port_score(port):
        score = 0
        device_name = (port.device or "").lower()
        desc = (port.description or "").lower()

        if port.vid == selected_vid and (
            selected_pid is None or port.pid == selected_pid
        ):
            score += 100

        if device_name.startswith("/dev/tty"):
            score -= 20
        if "usbserial" in device_name or "usb-serial" in desc or "usb serial" in desc:
            score -= 15
        if (port.vid, port.pid) in known_serial_vid_pid:
            score -= 25
        if device_name.startswith("/dev/cu"):
            score -= 5

        return score

    ranked_ports = sorted(ports, key=port_score)
    best_port = ranked_ports[0]

    if port_score(best_port) >= 100:
        candidate = next((p for p in ranked_ports if port_score(p) < 100), None)
        return candidate.device if candidate else None

    return best_port.device


def prompt_target_mode():
    while True:
        user_input = input("Выберите режим записи (HV/LV): ").strip().upper()
        if user_input in {"HV", "LV"}:
            return user_input
        logger.warning("Некорректный режим. Введите 'HV' или 'LV'.")


def load_firmware_image(mode):
    file_map = {
        "HV": "PS1200_slave.hex",
        "LV": "PS1200_master.hex",
    }

    if mode not in file_map:
        raise ValueError(f"Неизвестный режим прошивки: {mode}")

    firmware_dir = Path(__file__).resolve().parent / "firmware"
    file_path = firmware_dir / file_map[mode]

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


if __name__ == "__main__":
    main()
