UART_COMMANDS = {
    "SET": {
        "name": "SET",
        "description": "Установка значения параметра",
        "parameters": {
            "EN_12V": {
                "name": "EN_12V",
                "description": "Включение/выключение питания 12V",
                "values": ["ON", "OFF"],
                "default": "ON",
            },
            "SWICH_SWD1__2": {
                "name": "SWICH_SWD1__2",
                "description": "Переключение режима SWD (LV/HV)",
                "values": ["LV", "HV"],
                "default": "LV",
            },
            "SWICH_PROFILE": {
                "name": "SWICH_PROFILE",
                "description": "Установка профиля переключения",
                "values": ["00", "FF"],
                "default": "00",
            },
            "SWICH_MODE": {
                "name": "SWICH_MODE",
                "description": "Установка режима переключения",
                "values": ["00", "01", "FF"],
                "default": "00",
            },
        },
    },
    "GET": {
        "name": "GET",
        "description": "Получение значения параметра или статуса",
        "parameters": {
            "STATUS": {
                "name": "STATUS",
                "description": "Получение полного статуса устройства",
                "values": None,
                "default": None,
            },
            "SWICH_SWD1__2": {
                "name": "SWICH_SWD1__2",
                "description": "Получение текущего режима SWD",
                "values": None,
                "default": None,
            },
        },
    },
}


def get_command_structure():
    return UART_COMMANDS


def build_command(command_type, parameter=None, value=None):
    if command_type not in UART_COMMANDS:
        return None
    cmd_info = UART_COMMANDS[command_type]
    if command_type == "GET":
        if parameter and parameter in cmd_info["parameters"]:
            if cmd_info["parameters"][parameter]["values"] is None:
                return f"GET {parameter}"
            return None
        return None
    elif command_type == "SET":
        if parameter and parameter in cmd_info["parameters"]:
            param_info = cmd_info["parameters"][parameter]
            if value and value in param_info["values"]:
                return f"SET {parameter}={value}"
            elif param_info["default"]:
                return f"SET {parameter}={param_info['default']}"
        return None
    return None


def get_expected_response(command):
    if command.startswith("SET "):
        parts = command.split("=", 1)
        if len(parts) == 2:
            return parts[1].strip()
    elif command.startswith("GET "):
        return None
    return None
