import subprocess
import time
import os
import tempfile
from typing import Optional


class STLinkProgrammerOpenOCD:
    def __init__(self, device):
        self.device = device
        self.openocd_path = self._find_openocd()
        self.temp_dir = None

    def _find_openocd(self):
        possible_paths = [
            "openocd",
            "/usr/bin/openocd",
            "/usr/local/bin/openocd",
            "/opt/homebrew/bin/openocd",
        ]

        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return path
            except:
                continue

        return None

    def _create_config(self):
        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp()

        config_content = """
source [find interface/stlink.cfg]
source [find target/stm32g4x.cfg]
transport select hla_swd
adapter speed 100
reset_config srst_only srst_nogate connect_assert_srst
set WORKAREASIZE 0x2000
set CHIPNAME stm32g4x
set ENDIAN little
set CPUTAPID 0x2ba01477
set DAP_TAPID 0x2ba01477
set CONNECT_UNDER_RESET 1
set ENABLE_LOW_POWER 1
"""

        config_file = os.path.join(self.temp_dir, "stlink.cfg")
        with open(config_file, "w") as f:
            f.write(config_content)

        return config_file

    def _send_openocd_command(self, command, timeout=30):
        if not self.openocd_path:
            return None, "OpenOCD не найден", -1

        try:
            config_file = self._create_config()

            cmd = [
                self.openocd_path,
                "-f",
                config_file,
                "-c",
                "init",
                "-c",
                command,
                "-c",
                "shutdown",
            ]

            process = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )

            return process.stdout, process.stderr, process.returncode

        except subprocess.TimeoutExpired as e:
            return None, f"Таймаут после {timeout} секунд", -1
        except Exception as e:
            return None, str(e), -1

    def write_bytes(self, data, address):
        if not self.openocd_path:
            return False

        try:
            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp()

            data_file = os.path.join(self.temp_dir, "data.bin")
            with open(data_file, "wb") as f:
                f.write(data)

            stdout, stderr, returncode = self._send_openocd_command("targets")
            if returncode != 0:
                return False

            reset_run_command = "reset run; sleep 1000; halt"
            stdout, stderr, returncode = self._send_openocd_command(reset_run_command)
            if returncode != 0:
                return False

            erase_command = "reset run; sleep 1000; halt; flash erase_sector 0 0 last"
            stdout, stderr, returncode = self._send_openocd_command(erase_command)
            if returncode != 0:
                return False

            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp()

            data_file = os.path.join(self.temp_dir, "flash_data.bin")
            with open(data_file, "wb") as f:
                f.write(data)

            write_command = (
                f"reset run; sleep 1000; halt; flash write_image {data_file} {address}"
            )
            stdout, stderr, returncode = self._send_openocd_command(write_command)

            if returncode != 0:
                return False
            return True

        except Exception as e:
            return False

    def read_bytes(self, size, address):
        if not self.openocd_path:
            return b""

        try:
            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp()

            read_file = os.path.join(self.temp_dir, "read.bin")

            combined_command = (
                f"reset run; sleep 1000; halt; dump_image {read_file} {address} {size}"
            )
            stdout, stderr, returncode = self._send_openocd_command(combined_command)
            if returncode != 0:
                return b""

            if os.path.exists(read_file):
                with open(read_file, "rb") as f:
                    data = f.read()
                return data
            else:
                return b""

        except Exception as e:
            return b""

    def erase_flash(self):
        if not self.openocd_path:
            return False

        try:

            commands = ["init", "flash erase_sector 0 0 last", "shutdown"]

            for cmd in commands:
                stdout, stderr, returncode = self._send_openocd_command(cmd)

                if returncode != 0:
                    return False

            return True

        except Exception as e:
            return False

    def reset_target(self):
        if not self.openocd_path:
            return False

        try:

            commands = ["init", "reset run", "shutdown"]

            for cmd in commands:
                stdout, stderr, returncode = self._send_openocd_command(cmd)

                if returncode != 0:
                    return False

            return True

        except Exception as e:
            return False

    def clear_memory(self, address, size):
        if not self.openocd_path:
            return False

        try:

            halt_command = "halt"
            stdout, stderr, returncode = self._send_openocd_command(halt_command)

            if returncode != 0:
                return False

            for i in range(size):
                command = f"mwb {address + i} 0xFF"
                stdout, stderr, returncode = self._send_openocd_command(command)
                if returncode != 0:
                    return False

            return True

        except Exception as e:
            return False

    def __del__(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil

                shutil.rmtree(self.temp_dir)
            except:
                pass
