import sys
import logging
import time
import serial
from serial.tools import list_ports

logger = logging.getLogger(__name__)


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

    ports = list(list_ports.comports())

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

