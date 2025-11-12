import usb.core
import time


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

        for vid, pid in STLINK_IDS:
            if usb.core.find(idVendor=vid, idProduct=pid):
                self.devices.append(
                    {
                        "type": "ST-Link",
                        "name": f"ST-Link {vid:04X}:{pid:04X}",
                        "vid": vid,
                        "pid": pid,
                    }
                )

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
            return False

        device_type = self.selected["type"]
        success = False

        if device_type == "ST-Link":
            lib_programmer = None
            try:
                from programmer_stlink_lib import STLinkProgrammerLib

                lib_programmer = STLinkProgrammerLib(self.selected)
                success = lib_programmer.write_bytes(data, address)
            except Exception:
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
                from programmer_stlink_cube import STLinkProgrammerCube

                programmer = STLinkProgrammerCube(self.selected)
                if programmer.cube_path:
                    success = programmer.write_bytes(data, address)
                else:
                    success = False
            except Exception:
                success = False

        if device_type == "ST-Link" and not success:
            try:
                from programmer_stlink_openocd import STLinkProgrammerOpenOCD

                programmer = STLinkProgrammerOpenOCD(self.selected)
                if programmer.openocd_path:
                    success = programmer.write_bytes(data, address)
                else:
                    success = False
            except Exception:
                success = False

        if device_type == "ST-Link" and not success:
            try:
                from programmer_stlink import STLinkProgrammer

                programmer = STLinkProgrammer(self.selected)
                success = programmer.write_bytes(data, address)
            except Exception:
                success = False

        if device_type != "ST-Link":
            return False

        if success:
            return self._verify_write(data, address)
        return False

    def _verify_write(self, expected_data, address):
        try:
            device_type = self.selected["type"]

            if device_type == "ST-Link":
                try:
                    from programmer_stlink_cube import STLinkProgrammerCube

                    programmer = STLinkProgrammerCube(self.selected)
                    if programmer.cube_path:
                        read_data = programmer.read_bytes(len(expected_data), address)
                    else:
                        read_data = b""
                except:
                    read_data = b""

                if not read_data:
                    try:
                        from programmer_stlink_openocd import STLinkProgrammerOpenOCD

                        programmer = STLinkProgrammerOpenOCD(self.selected)
                        if programmer.openocd_path:
                            read_data = programmer.read_bytes(
                                len(expected_data), address
                            )
                    except:
                        read_data = b""

                if not read_data:
                    try:
                        from programmer_stlink import STLinkProgrammer

                        programmer = STLinkProgrammer(self.selected)
                        read_data = programmer.read_bytes(len(expected_data), address)
                    except:
                        read_data = b""

                if not read_data:
                    return False

            if not read_data:
                return False

            if read_data == expected_data:
                return True
            else:
                return False

        except Exception as e:
            return False

    def clear_memory(self, address, size):
        if not self.selected:
            return False

        device_type = self.selected["type"]

        if device_type == "ST-Link":
            try:
                from programmer_stlink_cube import STLinkProgrammerCube

                programmer = STLinkProgrammerCube(self.selected)
                if programmer.cube_path:
                    return programmer.clear_memory(address, size)
            except Exception as e:
                pass

            try:
                from programmer_stlink_openocd import STLinkProgrammerOpenOCD

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
                from programmer_stlink_cube import STLinkProgrammerCube

                programmer = STLinkProgrammerCube(self.selected)
                if programmer.cube_path:
                    data = programmer.read_bytes(size, address)
                else:
                    data = b""
            except:
                data = b""

            if not data:
                try:
                    from programmer_stlink_openocd import STLinkProgrammerOpenOCD

                    programmer = STLinkProgrammerOpenOCD(self.selected)
                    if programmer.openocd_path:
                        data = programmer.read_bytes(size, address)
                except:
                    data = b""

            if not data:
                try:
                    from programmer_stlink import STLinkProgrammer

                    programmer = STLinkProgrammer(self.selected)
                    data = programmer.read_bytes(size, address)
                except:
                    data = b""

            if not data:
                return b""

        return data

    def send_command_uart(self, command, expected_response):
        self.selected_uart.reset_input_buffer()
        self.selected_uart.write(command)
        self.selected_uart.flush()

        response = None
        try:
            response = self.selected_uart.readline().strip()
        except serial.SerialException as read_error:
            raise ValueError(f"Ошибка чтения ответа от UART: {read_error}")

        if response == expected_response:
            print(f"Получен ответ от UART: {response.decode('utf-8')}")
        else:
            display_response = (
                response.decode("utf-8", errors="replace") if response else "нет ответа"
            )
            print(
                "Не получено ожидаемого ответа от UART. "
                f"Ожидали '{expected_response.decode('utf-8')}', получили '{display_response}'."
            )

        return response == expected_response
