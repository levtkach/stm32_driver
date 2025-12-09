import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from .main_window import STM32ProgrammerGUI
from .styles import get_dark_stylesheet


def main():
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
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
