import subprocess
import tempfile
import os
import time
from typing import Optional


class STLinkProgrammerCube:
    def __init__(self, device):
        self.device = device
        self.cube_path = self._find_cube_programmer()
        self.temp_dir = None

    def _find_cube_programmer(self):
        import platform

        possible_paths = [
            "STM32_Programmer_CLI",
            "STM32_Programmer_CLI.exe",
        ]

        if platform.system() == "Windows":
            possible_paths.extend(
                [
                    r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
                    r"C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe",
                    os.path.join(
                        os.environ.get("ProgramFiles", ""),
                        "STMicroelectronics",
                        "STM32Cube",
                        "STM32CubeProgrammer",
                        "bin",
                        "STM32_Programmer_CLI.exe",
                    ),
                    os.path.join(
                        os.environ.get("ProgramFiles(x86)", ""),
                        "STMicroelectronics",
                        "STM32Cube",
                        "STM32CubeProgrammer",
                        "bin",
                        "STM32_Programmer_CLI.exe",
                    ),
                ]
            )

        possible_paths.extend(
            [
                "/Applications/STMicroelectronics/STM32Cube/STM32CubeProgrammer/STM32_Programmer_CLI",
                "/Applications/STMicroelectronics/STM32Cube/STM32CubeProgrammer/STM32CubeProgrammer.app/Contents/MacOS/STM32_Programmer_CLI",
                "/Applications/STMicroelectronics/STM32Cube/STM32CubeProgrammer/STM32CubeProgrammer.app/Contents/MacOs/bin/STM32_Programmer_CLI",
                "/Applications/STMicroelectronics/STM32Cube/STM32CubeProgrammer/STM32CubeProgrammer.app/Contents/MacOS/bin/STM32_Programmer_CLI",
                "/usr/local/bin/STM32_Programmer_CLI",
                "/opt/STM32CubeProgrammer/bin/STM32_Programmer_CLI",
            ]
        )

        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return path
            except Exception:
                continue

        return None

    def write_bytes(self, data, address):
        if not self.cube_path:
            return False

        try:

            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp()

            data_file = os.path.join(self.temp_dir, "data.bin")
            with open(data_file, "wb") as f:
                f.write(data)

            cmd = [
                self.cube_path,
                "-c",
                "port=SWD",
                "-w",
                f"{data_file}",
                f"0x{address:08X}",
                "-v",
                "1",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return True
            else:
                if result.stderr:
                    print(f"STM32CubeProgrammer stderr: {result.stderr}")
                if result.stdout and "error" in result.stdout.lower():
                    print(f"STM32CubeProgrammer stdout (ошибка): {result.stdout}")
                return False

        except Exception as e:
            return False

    def read_bytes(self, size, address):
        if not self.cube_path:
            return b""

        try:

            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp()

            read_file = os.path.join(self.temp_dir, "read.bin")

            cmd = [
                self.cube_path,
                "-c",
                "port=SWD",
                "-r",
                f"{read_file}",
                f"0x{address:08X}",
                f"{size}",
                "-v",
                "1",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and os.path.exists(read_file):
                with open(read_file, "rb") as f:
                    data = f.read()
                return data
            else:
                return b""

        except Exception as e:
            return b""

    def erase_flash(self):
        if not self.cube_path:
            return False

        try:

            cmd = [self.cube_path, "-c", "port=SWD", "-e", "all", "-v", "1"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return True
            else:
                return False

        except Exception as e:
            return False

    def reset_target(self):
        if not self.cube_path:
            return False

        try:

            cmd = [self.cube_path, "-c", "port=SWD", "-rst", "-v", "1"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return True
            else:
                return False

        except Exception as e:
            return False

    def __del__(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil

                shutil.rmtree(self.temp_dir)
            except:
                pass
