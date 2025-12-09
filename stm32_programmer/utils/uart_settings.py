import logging
from PyQt5.QtCore import QSettings

logger = logging.getLogger(__name__)


class UARTSettings:

    BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
    DEFAULT_BAUD_RATE = 115200

    LINE_ENDINGS = {"LF": "\n", "CR": "\r", "CRLF": "\r\n"}
    DEFAULT_LINE_ENDING = "LF"

    def __init__(self, settings_group="UART"):
        self.settings = QSettings("STM32Programmer", "UARTSettings")
        self.settings_group = settings_group

    def get_baud_rate(self):
        baud_rate = self.settings.value(
            f"{self.settings_group}/baud_rate", self.DEFAULT_BAUD_RATE, type=int
        )
        if baud_rate not in self.BAUD_RATES:
            baud_rate = self.DEFAULT_BAUD_RATE
        return baud_rate

    def set_baud_rate(self, baud_rate):
        if baud_rate in self.BAUD_RATES:
            self.settings.setValue(f"{self.settings_group}/baud_rate", baud_rate)
            self.settings.sync()
            logger.info(f"Сохранен baud rate: {baud_rate}")
        else:
            logger.warning(f"Недопустимый baud rate: {baud_rate}")

    def get_line_ending(self):
        line_ending = self.settings.value(
            f"{self.settings_group}/line_ending", self.DEFAULT_LINE_ENDING
        )
        if line_ending not in self.LINE_ENDINGS:
            line_ending = self.DEFAULT_LINE_ENDING
        return line_ending

    def get_line_ending_bytes(self):
        line_ending_key = self.get_line_ending()
        return self.LINE_ENDINGS[line_ending_key].encode("utf-8")

    def set_line_ending(self, line_ending):
        if line_ending in self.LINE_ENDINGS:
            self.settings.setValue(f"{self.settings_group}/line_ending", line_ending)
            self.settings.sync()
            logger.info(f"Сохранен line ending: {line_ending}")
        else:
            logger.warning(f"Недопустимый line ending: {line_ending}")

    def get_settings_dict(self):
        return {
            "baud_rate": self.get_baud_rate(),
            "line_ending": self.get_line_ending(),
        }

    def set_settings_dict(self, settings_dict):
        if "baud_rate" in settings_dict:
            self.set_baud_rate(settings_dict["baud_rate"])
        if "line_ending" in settings_dict:
            self.set_line_ending(settings_dict["line_ending"])
