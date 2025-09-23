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
                print(f"Найден ST-Link: {vid:04X}:{pid:04X}")

        return self.devices

    def show_devices(self):
        if not self.devices:
            print("Устройства не найдены")
            return
        for i, dev in enumerate(self.devices, 1):
            print(f"{i}. {dev['name']}")

    def select_device(self, num):
        if 1 <= num <= len(self.devices):
            self.selected = self.devices[num - 1]
            print(f"Выбрано: {self.selected['name']}")
            return True
        return False

    def write_bytes(self, data, address=DEFAULT_FLASH_ADDRESS):
        if not self.selected:
            return False

        device_type = self.selected["type"]

        if device_type == "ST-Link":
            try:
                from programmer_stlink_cube import STLinkProgrammerCube

                programmer = STLinkProgrammerCube(self.selected)
                if programmer.cube_path:
                    success = programmer.write_bytes(data, address)
                else:
                    success = False
            except Exception as e:
                success = False

            if not success:
                try:
                    from programmer_stlink_openocd import STLinkProgrammerOpenOCD

                    programmer = STLinkProgrammerOpenOCD(self.selected)
                    if programmer.openocd_path:
                        success = programmer.write_bytes(data, address)
                    else:
                        success = False
                except Exception as e:
                    success = False

            if not success:
                from programmer_stlink import STLinkProgrammer

                programmer = STLinkProgrammer(self.selected)
                success = programmer.write_bytes(data, address)

        if success:
            if self._verify_write(data, address):
                return True
            else:
                return False
        else:
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
            print("ST-Link: Используем STM32CubeProgrammer для очищения" * 10)
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
