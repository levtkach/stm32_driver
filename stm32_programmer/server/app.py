import os
import json
import threading
import time
import logging
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from stm32_programmer.programmers.core import (
    program_device,
    detect_serial_port,
    _parse_intel_hex,
)
from stm32_programmer.programmers.base import BaseProgrammer
import serial.tools.list_ports

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
ICONS_DIR = BASE_DIR.parent / "icons"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
CORS(app)


@app.route("/static/icons/<path:filename>")
def serve_icon(filename):
    icon_path = ICONS_DIR / filename
    if icon_path.exists():
        return send_from_directory(str(ICONS_DIR), filename)
    static_icon_path = STATIC_DIR / "icons" / filename
    if static_icon_path.exists():
        return send_from_directory(str(STATIC_DIR / "icons"), filename)
    return "Icon not found", 404


programming_state = {
    "is_programming": False,
    "current_task_id": None,
    "progress": {
        "status": "",
        "message": "",
        "percent": 0,
        "programming_percent": 0,
        "testing_percent": 0,
    },
    "result": None,
    "stop_requested": False,
    "logs": [],
}

state_lock = threading.Lock()


def get_programming_state():
    with state_lock:
        return programming_state.copy()


def update_progress(
    status="", message="", percent=0, programming_percent=0, testing_percent=0
):
    with state_lock:
        programming_state["progress"] = {
            "status": status,
            "message": message,
            "percent": percent,
            "programming_percent": programming_percent,
            "testing_percent": testing_percent,
        }
        if message:
            programming_state["logs"].append(
                {"timestamp": time.time(), "message": message, "type": "info"}
            )
        if status:
            programming_state["logs"].append(
                {"timestamp": time.time(), "message": status, "type": "status"}
            )
        if len(programming_state["logs"]) > 1000:
            programming_state["logs"] = programming_state["logs"][-1000:]


def set_programming_result(success, message):
    with state_lock:
        programming_state["is_programming"] = False
        programming_state["result"] = {
            "success": success,
            "message": message,
            "timestamp": time.time(),
        }
        log_type = "success" if success else "error"
        programming_state["logs"].append(
            {"timestamp": time.time(), "message": message, "type": log_type}
        )
        if len(programming_state["logs"]) > 1000:
            programming_state["logs"] = programming_state["logs"][-1000:]


def reset_state():
    with state_lock:
        programming_state["is_programming"] = False
        programming_state["current_task_id"] = None
        programming_state["progress"] = {
            "status": "",
            "message": "",
            "percent": 0,
            "programming_percent": 0,
            "testing_percent": 0,
        }
        programming_state["result"] = None
        programming_state["stop_requested"] = False
        programming_state["logs"] = []


def program_device_thread(lv_path, hv_path, uart_port, device_index):
    try:
        with state_lock:
            programming_state["is_programming"] = True
            programming_state["stop_requested"] = False
            programming_state["result"] = None
            programming_state["logs"] = []

        def progress_callback(message):
            update_progress(message=message)

        def status_callback(status):
            update_progress(status=status)

        def progress_percent_callback(percent):
            update_progress(percent=percent)

        def programming_progress_callback(percent):
            update_progress(programming_percent=percent)

        def testing_progress_callback(percent):
            update_progress(testing_percent=percent)

        def stop_check_callback():
            with state_lock:
                return programming_state["stop_requested"]

        success, message = program_device(
            lv_firmware_path=lv_path,
            hv_firmware_path=hv_path,
            progress_callback=progress_callback,
            status_callback=status_callback,
            progress_percent_callback=progress_percent_callback,
            programming_progress_callback=programming_progress_callback,
            testing_progress_callback=testing_progress_callback,
            stop_check_callback=stop_check_callback,
            uart_port=uart_port,
            device_index=device_index,
        )

        set_programming_result(success, message)
    except Exception as e:
        logger.exception("Ошибка при программировании")
        set_programming_result(False, f"Критическая ошибка: {str(e)}")


@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/devices", methods=["GET"])
def get_devices():
    try:
        programmer = BaseProgrammer()
        devices = programmer.find_devices()

        devices_list = []
        for idx, device in enumerate(devices, 1):
            device_info = {
                "index": idx,
                "name": device.get("name", "Unknown"),
                "type": device.get("type", "Unknown"),
                "vid": device.get("vid"),
                "pid": device.get("pid"),
            }
            if "serial" in device:
                device_info["serial"] = device["serial"]
            devices_list.append(device_info)

        return jsonify({"success": True, "devices": devices_list})
    except Exception as e:
        logger.exception("Ошибка при получении списка устройств")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ports", methods=["GET"])
def get_ports():
    try:
        ports = list(serial.tools.list_ports.comports())

        TARGET_UART_VID = 0x1A86
        TARGET_UART_PID = 0x7523

        def is_target_uart(port):
            if port.vid is not None and port.pid is not None:
                return port.vid == TARGET_UART_VID and port.pid == TARGET_UART_PID
            hwid = (port.hwid or "").upper()
            signature = f"VID:PID={TARGET_UART_VID:04X}:{TARGET_UART_PID:04X}"
            return signature in hwid

        matching_ports = [p for p in ports if is_target_uart(p)]

        ports_list = []
        for port in matching_ports:
            port_info = {
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
            }
            if port.vid is not None and port.pid is not None:
                port_info["vid"] = port.vid
                port_info["pid"] = port.pid
            ports_list.append(port_info)

        return jsonify({"success": True, "ports": ports_list})
    except Exception as e:
        logger.exception("Ошибка при получении списка портов")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/firmware/list", methods=["GET"])
def list_firmware():
    try:
        firmware_dir = Path("firmware")
        if not firmware_dir.exists():
            firmware_dir.mkdir(parents=True, exist_ok=True)
            return jsonify({"success": True, "firmware_files": []})

        firmware_files = []
        for ext in ["*.hex", "*.bin", "*.elf"]:
            firmware_files.extend(firmware_dir.glob(ext))

        firmware_list = [
            {
                "name": f.name,
                "path": str(f.relative_to(Path.cwd())),
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            }
            for f in firmware_files
        ]

        return jsonify({"success": True, "firmware_files": firmware_list})
    except Exception as e:
        logger.exception("Ошибка при получении списка прошивок")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/firmware/upload", methods=["POST"])
def upload_firmware():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "Файл не предоставлен"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Имя файла пустое"}), 400

    allowed_extensions = {".hex", ".bin", ".elf"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f'Неподдерживаемый формат файла. Разрешенные: {", ".join(allowed_extensions)}',
                }
            ),
            400,
        )

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    max_size = 10 * 1024 * 1024
    if file_size > max_size:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Файл слишком большой. Максимальный размер: {max_size // 1024 // 1024} МБ",
                }
            ),
            400,
        )

    firmware_dir = Path("firmware")
    firmware_dir.mkdir(parents=True, exist_ok=True)

    temp_path = firmware_dir / file.filename
    file.save(str(temp_path))

    if file_ext == ".hex":
        try:
            _parse_intel_hex(temp_path)
        except ValueError as e:
            temp_path.unlink()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Некорректный формат HEX файла: {str(e)}",
                    }
                ),
                400,
            )

    relative_path = f"firmware/{file.filename}"

    file_name_lower = file.filename.lower()
    warnings = []
    if "master" not in file_name_lower and "slave" not in file_name_lower:
        warnings.append('В названии файла не обнаружено "master" или "slave"')

    return jsonify(
        {
            "success": True,
            "message": "Файл успешно загружен",
            "path": relative_path,
            "filename": file.filename,
            "warnings": warnings,
        }
    )


@app.route("/api/program/start", methods=["POST"])
def start_programming():
    try:
        with state_lock:
            if programming_state["is_programming"]:
                return (
                    jsonify(
                        {"success": False, "error": "Программирование уже выполняется"}
                    ),
                    400,
                )

        data = request.json
        lv_path = data.get("lv_firmware_path")
        hv_path = data.get("hv_firmware_path")
        uart_port = data.get("uart_port")
        device_index = data.get("device_index", 1)

        if not lv_path and not hv_path:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Необходимо указать хотя бы один файл прошивки",
                    }
                ),
                400,
            )

        for path, mode in [(lv_path, "LV"), (hv_path, "HV")]:
            if path:
                if not Path(path).exists():
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": f"Файл {mode} прошивки не найден: {path}",
                            }
                        ),
                        400,
                    )

        thread = threading.Thread(
            target=program_device_thread,
            args=(lv_path, hv_path, uart_port, device_index),
            daemon=True,
        )
        thread.start()

        with state_lock:
            programming_state["current_task_id"] = time.time()

        return jsonify(
            {
                "success": True,
                "message": "Программирование запущено",
                "task_id": programming_state["current_task_id"],
            }
        )
    except Exception as e:
        logger.exception("Ошибка при запуске программирования")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/program/stop", methods=["POST"])
def stop_programming():
    try:
        with state_lock:
            if not programming_state["is_programming"]:
                return (
                    jsonify(
                        {"success": False, "error": "Программирование не выполняется"}
                    ),
                    400,
                )
            programming_state["stop_requested"] = True

        return jsonify({"success": True, "message": "Запрос на остановку отправлен"})
    except Exception as e:
        logger.exception("Ошибка при остановке программирования")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/program/status", methods=["GET"])
def get_programming_status():
    state = get_programming_state()
    return jsonify({"success": True, "state": state})


@app.route("/api/program/reset", methods=["POST"])
def reset_programming():
    reset_state()
    return jsonify({"success": True, "message": "Состояние сброшено"})


@app.route("/api/logs", methods=["GET"])
def get_logs():
    state = get_programming_state()
    return jsonify({"success": True, "logs": state.get("logs", [])})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"success": True, "status": "ok", "timestamp": time.time()})


def create_app():
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=5000, debug=True)
