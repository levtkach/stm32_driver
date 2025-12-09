import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from .main_window import STM32ProgrammerGUI
from .styles import get_dark_stylesheet


def main():

    pass

    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(get_dark_stylesheet())
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.Window, Qt.transparent)
    dark_palette.setColor(dark_palette.WindowText, Qt.white)
    dark_palette.setColor(dark_palette.Base, Qt.transparent)
    dark_palette.setColor(dark_palette.AlternateBase, Qt.transparent)
    dark_palette.setColor(dark_palette.ToolTipBase, Qt.transparent)
    dark_palette.setColor(dark_palette.ToolTipText, Qt.white)
    dark_palette.setColor(dark_palette.Text, Qt.white)
    dark_palette.setColor(dark_palette.Button, Qt.transparent)
    dark_palette.setColor(dark_palette.ButtonText, Qt.white)
    dark_palette.setColor(dark_palette.BrightText, Qt.red)
    dark_palette.setColor(dark_palette.Link, Qt.cyan)
    dark_palette.setColor(dark_palette.Highlight, Qt.transparent)
    dark_palette.setColor(dark_palette.HighlightedText, Qt.white)
    app.setPalette(dark_palette)
    window = STM32ProgrammerGUI()

    def cleanup_on_exit():
        if hasattr(window, "programmer") and window.programmer:

            if window.programmer.selected_uart:
                try:
                    if window.programmer.selected_uart.is_open:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.info("Выключение питания при завершении приложения...")
                        from stm32_programmer.utils.uart_settings import UARTSettings

                        uart_settings = UARTSettings()
                        line_ending_bytes = uart_settings.get_line_ending_bytes()
                        command_off = (
                            "SET EN_12V=OFF".strip().encode("utf-8") + line_ending_bytes
                        )
                        try:
                            window.programmer.send_command_uart(
                                command_off, "EN_12V=OFF".strip().encode("utf-8")
                            )
                        except:

                            try:
                                window.programmer.selected_uart.write(command_off)
                                window.programmer.selected_uart.flush()
                                logger.info("Команда EN_12V=OFF отправлена напрямую")
                            except:
                                pass
                        import time

                        time.sleep(0.5)
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Ошибка при выключении питания при завершении: {e}")
            window.programmer.close_uart()

    app.aboutToQuit.connect(cleanup_on_exit)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
