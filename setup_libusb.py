import os
import sys
import urllib.request
import zipfile
import tempfile
import shutil
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def download_libusb_dll():
    dll_name = "libusb-1.0.dll"

    locations = []
    locations.append(os.getcwd())
    stm32cube_paths = [
        r"C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin",
        r"C:\Program Files (x86)\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin",
    ]
    for cube_path in stm32cube_paths:
        if os.path.exists(cube_path):
            locations.insert(1, cube_path)

    if hasattr(sys, "executable"):
        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        if os.path.exists(scripts_dir):
            locations.append(scripts_dir)

    system32 = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32")
    if os.path.exists(system32):
        locations.append(system32)

    for loc in locations:
        dll_path = os.path.join(loc, dll_name)
        if os.path.exists(dll_path):
            print(f"[OK] Найдена {dll_name} в: {dll_path}")
            return True

    print("libusb-package установлен, но DLL отсутствует.")
    print("\nПопытка автоматической загрузки...")

    target_dir = os.getcwd()
    dll_path = os.path.join(target_dir, dll_name)

    dll_urls = [
        "https://raw.githubusercontent.com/libusb/libusb/master/msvc/x64/Release/dll/libusb-1.0.dll",
    ]

    downloaded = False
    for url in dll_urls:
        try:
            print(f"Попытка скачать из: {url}")
            urllib.request.urlretrieve(url, dll_path)
            if os.path.exists(dll_path) and os.path.getsize(dll_path) > 1000:
                print(f"[OK] DLL успешно скачана в: {dll_path}")
                downloaded = True
                break
        except Exception as e:
            print(f"Не удалось скачать из этого источника: {e}")
            continue

    if not downloaded:
        print("\nАвтоматическая загрузка не удалась. Выполните установку вручную:\n")
        print("1. Перейдите на: https://github.com/libusb/libusb/releases")
        print(
            "2. Скачайте последнюю версию Windows binaries (например, libusb-1.0.27-binaries.7z)"
        )
        print("3. Распакуйте архив (используйте 7-Zip или WinRAR)")
        print("4. Найдите libusb-1.0.dll в папке MS64\\dll\\")
        print("5. Скопируйте DLL в одну из следующих директорий:\n")

        for i, loc in enumerate(locations, 1):
            marker = " (рекомендуется)" if "STM32Cube" in loc else ""
            print(f"   {i}. {loc}{marker}")

        print(f"\nИли просто скопируйте {dll_name} в текущую директорию:")
        print(f"   {target_dir}")
        print("\nПосле копирования DLL перезапустите Python и попробуйте снова.")
        return False

    return True


if __name__ == "__main__":
    try:
        download_libusb_dll()
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ОШИБКА] {e}")
        sys.exit(1)
