from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QPushButton
from stm32_programmer.utils.icon_loader import get_qt_icon, get_icon_emoji_fallback


class IconManager:

    def __init__(self, theme="dark"):
        self.theme = theme

    def set_theme(self, theme):
        self.theme = theme

    def update_refresh_icon(self, button):
        refresh_icon = get_qt_icon("refresh", 20, theme=self.theme)
        if not refresh_icon.isNull():
            button.setIcon(refresh_icon)
            button.setText("")
        else:
            button.setIcon(QIcon())
            button.setText(get_icon_emoji_fallback("refresh"))
        button.update()
        button.repaint()

    def update_play_icon(self, button, is_playing=False):
        button.setIcon(QIcon())
        button.setText("")

        if is_playing:
            stop_icon = get_qt_icon("stop", 20, theme=self.theme)
            if not stop_icon.isNull():
                button.setIcon(stop_icon)
            else:
                button.setText("■")
        else:
            play_icon = get_qt_icon("play", 20, theme=self.theme)
            if not play_icon.isNull():
                button.setIcon(play_icon)
            else:
                button.setText(get_icon_emoji_fallback("play"))
        button.update()
        button.repaint()

    def update_cross_icon(self, button):
        cross_icon = get_qt_icon("cross", 20, theme=self.theme)
        if not cross_icon.isNull():
            button.setIcon(cross_icon)
            button.setText("")
        else:
            button.setIcon(QIcon())
            button.setText(get_icon_emoji_fallback("cross"))
        button.update()
        button.repaint()

    def update_document_icon(self, button):
        document_icon = get_qt_icon("document", 20, theme=self.theme)
        if not document_icon.isNull():
            button.setIcon(document_icon)
            button.setText("")
        else:
            button.setIcon(QIcon())
            button.setText(get_icon_emoji_fallback("document"))
        button.update()
        button.repaint()

    def update_folder_icon(self, button):
        folder_icon = get_qt_icon("folder", 20, theme=self.theme)
        if not folder_icon.isNull():
            button.setIcon(folder_icon)
            button.setText("")
        else:
            button.setIcon(QIcon())
            button.setText(get_icon_emoji_fallback("folder"))

    def update_theme_icon(self, button, theme):
        icon_name = "sun" if theme == "dark" else "moon"
        theme_icon = get_qt_icon(icon_name, 20)
        if not theme_icon.isNull():
            button.setIcon(theme_icon)
            button.setText("")
        else:
            button.setIcon(QIcon())
            button.setText(get_icon_emoji_fallback(icon_name))
        button.update()
        button.repaint()

    def update_delete_icon(self, button):
        delete_icon = get_qt_icon("delete", 20, theme=self.theme)
        if not delete_icon.isNull():
            button.setIcon(delete_icon)
            button.setText("")
        else:
            button.setIcon(QIcon())
            button.setText("🗑")
        button.update()
        button.repaint()

    def update_all_icons(self, buttons_dict):
        if "refresh_devices" in buttons_dict and buttons_dict["refresh_devices"]:
            self.update_refresh_icon(buttons_dict["refresh_devices"])

        if "refresh_ports" in buttons_dict and buttons_dict["refresh_ports"]:
            self.update_refresh_icon(buttons_dict["refresh_ports"])

        if "program" in buttons_dict and buttons_dict["program"]:
            is_playing = buttons_dict.get("is_playing", False)
            self.update_play_icon(buttons_dict["program"], is_playing)

        if "clear" in buttons_dict and buttons_dict["clear"]:
            self.update_cross_icon(buttons_dict["clear"])

        if "open_log" in buttons_dict and buttons_dict["open_log"]:
            self.update_document_icon(buttons_dict["open_log"])

        if "theme" in buttons_dict and buttons_dict["theme"]:
            self.update_theme_icon(buttons_dict["theme"], self.theme)
