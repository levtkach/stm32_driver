import sys
import os
import argparse
import logging
import socket
from stm32_programmer.server.app import create_app

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            return True
        except OSError:
            return False


def find_available_port(start_port=8080, max_attempts=10):
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    return None


def main():
    parser = argparse.ArgumentParser(description="STM32 Programmer Web Server")
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Порт для запуска сервера (по умолчанию: 8080 или из переменной окружения PORT)",
    )
    args = parser.parse_args()

    port = args.port or int(os.environ.get("PORT", 8080))

    if not is_port_available(port):
        logger.warning(f"Порт {port} занят, ищу свободный порт...")
        available_port = find_available_port(port)
        if available_port:
            logger.info(f"Найден свободный порт: {available_port}")
            port = available_port
        else:
            logger.error("Не удалось найти свободный порт")
            sys.exit(1)

    app = create_app()
    host = "0.0.0.0"
    local_ip = get_local_ip()

    logger.info("=" * 60)
    logger.info("STM32 Programmer Web Server")
    logger.info("=" * 60)
    logger.info(f"Сервер запущен на порту {port}")
    logger.info(f"Локальный доступ: http://127.0.0.1:{port}")
    logger.info(f"Доступ в сети: http://{local_ip}:{port}")
    logger.info("=" * 60)
    logger.info("Нажмите Ctrl+C для остановки сервера")
    logger.info("=" * 60)

    try:
        app.run(host=host, port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("\nСервер остановлен")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Ошибка при запуске сервера: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
