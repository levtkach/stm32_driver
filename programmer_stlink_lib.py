import time
from typing import Optional


class STLinkProgrammerLib:
    def __init__(self, device):
        self.device = device
        self.stlink = None
        self._connect()

    def _connect(self):
        try:
            import stlink

            self.stlink = stlink.Stlink()

            if self.stlink.is_connected():
                return True
            else:
                return False

        except ImportError:
            return False
        except Exception as e:
            return False

    def write_bytes(self, data, address):
        if not self.stlink:
            return False

        try:

            success = self.stlink.write_memory(address, data)

            if success:
                return True
            else:
                return False

        except Exception as e:
            return False

    def read_bytes(self, size, address):
        if not self.stlink:
            return b""

        try:

            data = self.stlink.read_memory(address, size)

            if data:
                return data
            else:
                return b""

        except Exception as e:
            return b""

    def erase_flash(self):
        if not self.stlink:
            return False

        try:

            success = self.stlink.erase_flash()

            if success:
                return True
            else:
                return False

        except Exception as e:
            return False

    def reset_target(self):
        if not self.stlink:
            return False

        try:

            success = self.stlink.reset()

            if success:
                return True
            else:
                return False

        except Exception as e:
            return False

    def get_target_info(self):
        if not self.stlink:
            return None

        try:

            info = self.stlink.get_target_info()

            if info:
                return info
            else:
                return None

        except Exception as e:
            return None

    def __del__(self):
        if self.stlink:
            try:
                self.stlink.disconnect()
            except:
                pass
