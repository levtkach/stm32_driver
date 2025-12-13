import os
from pathlib import Path
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QSize, Qt


ICONS_DIR = Path(__file__).parent.parent / "icons"


THEMED_ICONS = {"refresh", "play", "stop", "cross", "document", "folder", "delete", "copy"}


def get_icon_path(icon_name, extension="png", theme=None):
    if icon_name in THEMED_ICONS and theme:
        theme_suffix = "_white" if theme == "dark" else "_black"
        themed_name = f"{icon_name}{theme_suffix}"
        themed_path = ICONS_DIR / f"{themed_name}.{extension}"
        if themed_path.exists():
            return str(themed_path)
        if extension == "png":
            themed_svg = ICONS_DIR / f"{themed_name}.svg"
            if themed_svg.exists():
                return str(themed_svg)

    icon_path = ICONS_DIR / f"{icon_name}.{extension}"
    if icon_path.exists():
        return str(icon_path)
    if extension == "png":
        svg_path = ICONS_DIR / f"{icon_name}.svg"
        if svg_path.exists():
            return str(svg_path)
    return None


def get_qt_icon(icon_name, size=24, theme=None):
    icon_path = get_icon_path(icon_name, extension="png", theme=theme)
    if icon_path:
        icon = QIcon(icon_path)
        if not icon.isNull():
            return icon
    icon_path = get_icon_path(icon_name, extension="svg", theme=theme)
    if icon_path:
        icon = QIcon(icon_path)
        if not icon.isNull():
            return icon
    return QIcon()


def get_icon_html(icon_name, size=24, alt_text="", theme=None):
    icon_path = get_icon_path(icon_name, "svg", theme=theme)
    if not icon_path:
        icon_path = get_icon_path(icon_name, "png", theme=theme)

    if icon_path:
        relative_path = f"/static/icons/{Path(icon_path).name}"
        if icon_path.endswith(".svg"):
            return f'<img src="{relative_path}" alt="{alt_text}" width="{size}" height="{size}" style="vertical-align: middle;">'
        else:
            return f'<img src="{relative_path}" alt="{alt_text}" width="{size}" height="{size}" style="vertical-align: middle;">'

    return alt_text


def get_icon_emoji_fallback(icon_name):
    emoji_map = {
        "thinking": "🤔",
        "wrench": "🔧",
        "refresh": "🔄",
        "folder": "📁",
        "play": "▶️",
        "stop": "⏹️",
        "warning": "⚠️",
        "check": "✓",
        "cross": "✗",
        "loading": "⏳",
        "save": "💾",
        "sun": "☀",
        "moon": "☾",
        "document": "📄",
        "copy": "📋",
    }
    return emoji_map.get(icon_name, "")
