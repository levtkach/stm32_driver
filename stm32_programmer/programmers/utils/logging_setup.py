import sys
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging(log_dir=None):
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = log_dir / f"{timestamp}.log"

    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[file_handler, console_handler],
    )

    logger = logging.getLogger(__name__)
    logger.warning(f"Логи записываются в файл: {log_filename}")
    return logger, str(log_filename)

