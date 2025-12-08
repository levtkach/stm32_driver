import subprocess
import tempfile
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class STLinkProgrammerCube:
    def __init__(self, device):
        self.device = device
        self.cube_path = self._find_cube_programmer()
        self.temp_dir = None
        self.stlink_serial = device.get("serial")
    
    def _build_connection_param(self):
        if self.stlink_serial:
            param = f"port=SWD sn={self.stlink_serial}"
            logger.debug(f"Используется ST-Link с серийным номером: {self.stlink_serial}")
            return param
        logger.debug("Используется ST-Link без указания серийного номера")
        return "port=SWD"

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

            time.sleep(1.0)
            connection_param = self._build_connection_param()
            connect_test_cmd = [
                self.cube_path,
                "-c",
                connection_param,
                "-ob",
                "nRST_STOP=1",
            ]
            
            logger.info(f"проверка подключения к устройству перед записью...")
            connect_result = subprocess.run(connect_test_cmd, capture_output=True, text=True, timeout=30)
            
            if connect_result.returncode != 0:
                if connect_result.stdout and "DEV_USB_COMM_ERR" in connect_result.stdout:
                    logger.warning("обнаружена ошибка USB коммуникации, ожидание дополнительной стабилизации...")
                    time.sleep(3.0)
                else:
                    logger.warning("подключение не удалось, ожидание...")
                    time.sleep(2.0)
            
            reset_cmd = [
                self.cube_path,
                "-c",
                connection_param,
                "-rst",
            ]
            logger.info(f"выполнение команды сброса перед записью: {' '.join(reset_cmd)}")
            
            reset_success = False
            reset_result = None
            for reset_attempt in range(3):
                if reset_attempt > 0:
                    logger.warning(f"повторная попытка сброса (попытка {reset_attempt + 1}/3)...")
                    time.sleep(2.0)
                
                reset_result = subprocess.run(reset_cmd, capture_output=True, text=True, timeout=30)
                if reset_result.returncode == 0:
                    logger.info("устройство сброшено перед записью")
                    time.sleep(1.0)
                    reset_success = True
                    break
                else:
                    if reset_attempt < 2:
                        logger.warning(f"попытка сброса {reset_attempt + 1} не удалась, повтор...")
            
            if not reset_success:
                logger.warning("не удалось сбросить устройство перед записью, продолжаем без сброса...")
                if reset_result and reset_result.stdout:
                    logger.warning(f"stdout при сбросе: {reset_result.stdout}")
                if reset_result and reset_result.stderr:
                    logger.warning(f"stderr при сбросе: {reset_result.stderr}")
                time.sleep(2.0)

            cmd = [
                self.cube_path,
                "-c",
                connection_param,
                "-w",
                f"{data_file}",
                f"0x{address:08X}",
                "-v",
            ]

            max_retries = 3
            retry_delay = 3.0
            
            for attempt in range(max_retries):
                if attempt > 0:
                    logger.warning(f"повторная попытка записи (попытка {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    
                    reset_result = subprocess.run(reset_cmd, capture_output=True, text=True, timeout=30)
                    if reset_result.returncode == 0:
                        time.sleep(0.5)

                logger.info(f"выполнение команды записи: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                if result.returncode == 0:
                    logger.info("команда записи завершилась с кодом 0 (успех)")
                    if result.stdout:
                        logger.info(f"stdout при записи: {result.stdout}")
                    if result.stderr:
                        logger.info(f"stderr при записи: {result.stderr}")
                    return True
                else:
                    logger.warning(
                        f"команда записи завершилась с кодом {result.returncode} (ошибка, попытка {attempt + 1}/{max_retries})"
                    )
                    if result.stderr:
                        logger.error(f"STM32CubeProgrammer stderr: {result.stderr}")
                    if result.stdout:
                        logger.error(f"STM32CubeProgrammer stdout: {result.stdout}")
                    
                    if attempt < max_retries - 1:
                        continue
            
            return False

        except Exception as e:
            return False

    def read_bytes(self, size, address):
        if not self.cube_path:
            logger.warning("cube_path не найден, чтение невозможно")
            return b""

        try:

            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp()

            read_file = os.path.join(self.temp_dir, "read.bin")

            connection_param = self._build_connection_param()
            cmd = [
                self.cube_path,
                "-c",
                connection_param,
                "-r",
                f"0x{address:08X}",
                str(size),
                read_file,
            ]

            logger.info(f"выполнение команды чтения: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                if os.path.exists(read_file):
                    with open(read_file, "rb") as f:
                        data = f.read()
                    logger.info(f"файл прочитан, размер: {len(data)} байт")
                    return data
                else:
                    logger.warning(f"файл {read_file} не существует после чтения")
                    return b""
            else:
                logger.warning(
                    f"команда чтения завершилась с кодом {result.returncode}"
                )
                if result.stderr:
                    logger.warning(f"stderr при чтении: {result.stderr}")
                if result.stdout:
                    logger.warning(f"stdout при чтении: {result.stdout}")
                return b""

        except Exception as e:
            logger.warning(f"исключение при чтении: {e}")
            return b""

    def erase_flash(self):
        if not self.cube_path:
            return False

        try:
            connection_param = self._build_connection_param()
            cmd = [self.cube_path, "-c", connection_param, "-e", "all"]

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
            connection_param = self._build_connection_param()
            cmd = [self.cube_path, "-c", connection_param, "-rst"]

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
