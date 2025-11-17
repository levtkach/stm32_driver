import usb.core
import usb.util
import time
import struct
from typing import Optional


class STLinkProgrammer:
    def __init__(self, device):
        self.device = device
        self.usb_device = None
        self.interface = None
        self.version = None
        self._connect()

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
            result = self._send_command(cmd)

            if result and len(result) > 2:
                return bytes(result[2 : 2 + size])
            return b""
        except:
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
            print("Ошибка: USB устройство или интерфейс не инициализированы")
            return False

        try:
            print("Проверка подключения к целевому устройству...")
            if not self._check_target_connection():
                print("Ошибка: не удалось подключиться к целевому устройству")
                return False
            print("Подключение к целевому устройству установлено")

            print("Вход в режим отладки...")
            if not self._enter_debug_mode():
                print("Ошибка: не удалось войти в режим отладки")
                return False
            print("Режим отладки активирован")

            time.sleep(0.1)

            block_size = 1024
            total_size = len(data)
            offset = 0
            success = True

            print(f"Начало записи {total_size} байт по адресу {hex(address)}")

            while offset < total_size:
                block = data[offset : offset + block_size]
                block_address = address + offset

                print(
                    f"Запись блока {offset // block_size + 1}/{(total_size + block_size - 1) // block_size}: "
                    f"{len(block)} байт по адресу {hex(block_address)}"
                )

                block_success = self._write_memory(block_address, block)
                if not block_success:
                    print(f"Ошибка записи блока по адресу {hex(block_address)}")
                    success = False
                    break

                offset += len(block)
                time.sleep(0.05)

            self._exit_debug_mode()

            if success:
                print("Запись завершена успешно")
            else:
                print("Запись завершена с ошибками")

            return success

        except Exception as e:
            print(f"Исключение при записи: {e}")
            try:
                self._exit_debug_mode()
            except:
                pass
            return False

    def read_bytes(self, size, address):
        if not self.usb_device:
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
        if not self.usb_device:
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

            if result:
                return True
            else:
                return False

        except Exception as e:
            return False

    def reset_target(self):
        if not self.usb_device:
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

            if result:
                return True
            else:
                return False

        except Exception as e:
            return False

    def __del__(self):
        if self.usb_device and self.interface:
            try:
                usb.util.release_interface(
                    self.usb_device, self.interface.bInterfaceNumber
                )
            except:
                pass
