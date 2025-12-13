from pathlib import Path
import logging

logger = logging.getLogger(__name__)


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

