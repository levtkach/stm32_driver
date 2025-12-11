def get_light_stylesheet():
    return """
    /* Основные цвета светлой темы */
    QWidget {
        background-color: #ffffff;
        color: #2d2d2d;
        font-family: 'Arial', 'Helvetica', sans-serif;
        font-size: 12pt;
    }
    
    /* Главное окно */
    QMainWindow, QWidget#main {
        background-color: #ffffff;
    }
    
    /* Заголовки */
    QLabel[title="true"] {
        font-size: 24pt;
        font-weight: bold;
        color: #2d3748;
        padding: 8px 12px;
        letter-spacing: 0.5px;
    }
    
    /* Обычные метки */
    QLabel {
        color: #1a202c;
        background-color: transparent;
        font-size: 11pt;
    }
    
    /* Кнопки */
    QPushButton {
        background-color: #f7fafc;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        padding: 4px 12px;
        font-weight: 500;
        font-size: 11pt;
        min-height: 28px;
    }
    
    QPushButton:hover {
        background-color: #edf2f7;
        border: 2px solid #718096;
    }
    
    QPushButton:pressed {
        background-color: #e2e8f0;
        border: 2px solid #4a5568;
    }
    
    QPushButton:disabled {
        background-color: #f7fafc;
        color: #a0aec0;
        border: 1px solid #e2e8f0;
    }
    
    /* Кнопка программирования */
    QPushButton[programButton="true"] {
        background-color: #edf2f7;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        font-size: 14pt;
        font-weight: bold;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
        max-width: 28px;
    }
    
    QPushButton[programButton="true"]:hover {
        background-color: #e2e8f0;
        border: 2px solid #718096;
    }
    
    QPushButton[programButton="true"]:pressed {
        background-color: #cbd5e0;
        border: 2px solid #4a5568;
    }
    
    QPushButton[programButton="true"]:disabled {
        background-color: #f7fafc;
        color: #a0aec0;
        border: 1px solid #e2e8f0;
    }
    
    /* Маленькие кнопки с иконками */
    QPushButton[iconButton="true"] {
        background-color: #f7fafc;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        font-size: 14pt;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
    }
    
    QPushButton[iconButton="true"]:hover {
        background-color: #edf2f7;
        border: 2px solid #718096;
    }
    
    QPushButton[iconButton="true"]:pressed {
        background-color: #e2e8f0;
        border: 2px solid #4a5568;
    }
    
    /* Активная кнопка режима LV/HV */
    QPushButton[iconButton="true"][activeMode="LV"],
    QPushButton[iconButton="true"][activeMode="HV"] {
        background-color: #48bb78;
        color: #ffffff;
        border: 2px solid #38a169;
        font-weight: bold;
    }
    
    QPushButton[iconButton="true"][activeMode="LV"]:hover,
    QPushButton[iconButton="true"][activeMode="HV"]:hover {
        background-color: #38a169;
        border: 2px solid #2f855a;
    }
    
    /* Обводка валидации для кнопок загрузки прошивки */
    QPushButton[validationBorder="valid"] {
        border: 2px solid #48bb78;
    }
    
    QPushButton[validationBorder="valid"]:hover {
        border: 2px solid #38a169;
    }
    
    QPushButton[validationBorder="invalid"] {
        border: 2px solid #ed8936;
    }
    
    QPushButton[validationBorder="invalid"]:hover {
        border: 2px solid #dd6b20;
    }
    
    /* Контейнер для ввода с кнопкой */
    QFrame[inputContainer="true"] {
        background-color: #ffffff;
        border: 1px solid #cbd5e0;
        border-radius: 6px;
        padding: 2px;
    }
    
    QFrame[inputContainer="true"]:hover {
        border: 2px solid #718096;
    }
    
    /* Группа для объединения полей ввода */
    QFrame[inputGroup="true"] {
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
    }
    
    /* ComboBox */
    QComboBox {
        background-color: transparent;
        color: #1a202c;
        border: none;
        border-radius: 0px;
        padding: 4px 12px;
        font-size: 11pt;
        min-height: 28px;
    }
    
    QComboBox:hover {
        background-color: transparent;
    }
    
    QComboBox:focus {
        background-color: transparent;
    }
    
    QComboBox:disabled {
        background-color: #f7fafc;
        color: #a0aec0;
        opacity: 0.6;
    }
    
    /* Скрываем стрелку выпадающего списка */
    QComboBox::drop-down {
        border: none;
        width: 0px;
        background-color: transparent;
    }
    
    QComboBox::drop-down:hover {
        background-color: transparent;
    }
    
    QComboBox::down-arrow {
        width: 0px;
        height: 0px;
    }
    
    /* Поле ввода текста */
    QLineEdit {
        background-color: #ffffff;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        padding: 4px 12px;
        font-size: 11pt;
        min-height: 28px;
    }
    
    QLineEdit:hover {
        border: 1px solid #a0aec0;
    }
    
    QLineEdit:focus {
        border: 2px solid #718096;
        background-color: #ffffff;
    }
    
    /* Кнопка обновления */
    QPushButton[refreshButton="true"] {
        background-color: #f7fafc;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        font-size: 14pt;
        font-weight: bold;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
    }
    
    QPushButton[refreshButton="true"]:hover {
        background-color: #edf2f7;
        border: 2px solid #718096;
    }
    
    QPushButton[refreshButton="true"]:pressed {
        background-color: #e2e8f0;
        border: 2px solid #4a5568;
    }
    
    QComboBox QAbstractItemView {
        background-color: #ffffff;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 6px;
        selection-background-color: #edf2f7;
        selection-color: #1a202c;
        padding: 4px;
    }
    
    /* Текстовое поле консоли */
    QTextEdit {
        background-color: #f8f9fa;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        padding: 12px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Menlo', 'Courier New', monospace;
        font-size: 11pt;
        selection-background-color: #4a5568;
        selection-color: #ffffff;
    }
    
    QTextEdit:focus {
        border: 1px solid #718096;
    }
    
    /* Прогресс-бар */
    QProgressBar {
        background-color: #f7fafc;
        border: 1px solid #cbd5e0;
        border-radius: 6px;
        text-align: center;
        color: #2d2d2d;
        font-weight: 500;
        font-size: 12pt;
        height: 28px;
    }
    
    QProgressBar::chunk {
        background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 #48bb78, stop: 1 #38a169);
        border-radius: 5px;
    }
    
    /* Разделители */
    QFrame[frameShape="4"] {
        background-color: #cbd5e0;
        max-height: 1px;
        min-height: 1px;
    }
    
    /* Информационные метки */
    QLabel[info="true"] {
        color: #4a5568;
        font-size: 11pt;
        background-color: transparent;
    }
    
    /* Сообщения об ошибках */
    QLabel[error="true"] {
        color: #e53e3e;
        background-color: transparent;
    }
    
    /* Сообщения об успехе */
    QLabel[success="true"] {
        color: #38a169;
        background-color: transparent;
    }
    
    /* Tooltip */
    QToolTip {
        background-color: #2d3748;
        color: #ffffff;
        border: 1px solid #4a5568;
        border-radius: 4px;
        padding: 4px 8px;
    }
    
    /* Scrollbar */
    QScrollBar:vertical {
        background-color: #f7fafc;
        width: 12px;
        border: none;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical {
        background-color: #cbd5e0;
        border-radius: 6px;
        min-height: 20px;
        margin: 2px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #a0aec0;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    QScrollBar:horizontal {
        background-color: #f7fafc;
        height: 12px;
        border: none;
        border-radius: 6px;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #cbd5e0;
        border-radius: 6px;
        min-width: 20px;
        margin: 2px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #a0aec0;
    }
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    
    /* Диалоговые окна */
    QMessageBox {
        background-color: #ffffff;
    }
    
    QMessageBox QLabel {
        color: #2d2d2d;
        background-color: transparent;
    }
    
    QMessageBox QPushButton {
        min-width: 80px;
        padding: 6px 20px;
    }
    
    /* Группы и фреймы */
    QGroupBox {
        border: 1px solid #cbd5e0;
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 12px;
        color: #4a5568;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        background-color: #ffffff;
    }
    
    /* Вкладки */
    QTabWidget[tabs="true"] {
        background-color: #ffffff;
        border: none;
    }
    
    QTabWidget[tabs="true"]::pane {
        background-color: #ffffff;
        border: 1px solid #cbd5e0;
        border-radius: 6px;
        top: -1px;
    }
    
    QTabBar::tab {
        background-color: #f7fafc;
        color: #2d2d2d;
        border: 1px solid #cbd5e0;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 20px;
        margin-right: 2px;
        font-size: 12pt;
        min-width: 120px;
    }
    
    QTabBar::tab:selected {
        background-color: #ffffff;
        color: #4a5568;
        border-color: #4a5568;
        border-bottom: 1px solid #ffffff;
    }
    
    QTabBar::tab:hover {
        background-color: #edf2f7;
        color: #2d3748;
    }
    
    /* Разделители */
    QFrame[separator="true"] {
        background-color: #e2e8f0;
        max-height: 2px;
        min-height: 2px;
        border: none;
        margin: 8px 0px;
    }
    
    /* Переключатель темы */
    QPushButton[themeToggle="true"] {
        background-color: #f7fafc;
        color: #1a202c;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        font-size: 14pt;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
    }
    
    QPushButton[themeToggle="true"]:hover {
        background-color: #edf2f7;
        border: 2px solid #718096;
    }
    
    QPushButton[themeToggle="true"]:pressed {
        background-color: #e2e8f0;
        border: 2px solid #4a5568;
    }
    """


def get_dark_stylesheet():
    return """
    /* Основные цвета темы Dracula */
    QWidget {
        background-color: #282a36;
        color: #f8f8f2;
        font-family: 'Arial', 'Helvetica', sans-serif;
        font-size: 12pt;
    }
    
    /* Главное окно */
    QMainWindow, QWidget#main {
        background-color: #282a36;
    }
    
    /* Заголовки */
    QLabel[title="true"] {
        font-size: 24pt;
        font-weight: bold;
        color: #bd93f9;
        padding: 8px 12px;
        letter-spacing: 0.5px;
    }
    
    /* Обычные метки */
    QLabel {
        color: #f8f8f2;
        background-color: transparent;
        font-size: 12pt;
    }
    
    /* Кнопки */
    QPushButton {
        background-color: #44475a;
        color: #f8f8f2;
        border: 1px solid #6272a4;
        border-radius: 4px;
        padding: 4px 12px;
        font-weight: 500;
        font-size: 11pt;
        min-height: 28px;
    }
    
    QPushButton:hover {
        background-color: #6272a4;
        border: 2px solid #8be9fd;
    }
    
    QPushButton:pressed {
        background-color: #44475a;
        border: 2px solid #bd93f9;
    }
    
    QPushButton:disabled {
        background-color: #21222c;
        color: #6272a4;
        border: 1px solid #44475a;
    }
    
    /* Кнопка программирования */
    QPushButton[programButton="true"] {
        background-color: #44475a;
        color: #f8f8f2;
        border: 1px solid #6272a4;
        border-radius: 4px;
        font-size: 14pt;
        font-weight: bold;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
        max-width: 28px;
    }
    
    QPushButton[programButton="true"]:hover {
        background-color: #6272a4;
        border: 2px solid #8be9fd;
    }
    
    QPushButton[programButton="true"]:pressed {
        background-color: #50fa7b;
        color: #282a36;
        border: 2px solid #50fa7b;
    }
    
    QPushButton[programButton="true"]:disabled {
        background-color: #21222c;
        color: #6272a4;
        border: 1px solid #44475a;
    }
    
    /* Маленькие кнопки с иконками */
    QPushButton[iconButton="true"] {
        background-color: #44475a;
        color: #f8f8f2;
        border: 1px solid #6272a4;
        border-radius: 4px;
        font-size: 14pt;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
    }
    
    QPushButton[iconButton="true"]:hover {
        background-color: #6272a4;
        border: 2px solid #8be9fd;
    }
    
    QPushButton[iconButton="true"]:pressed {
        background-color: #44475a;
        border: 2px solid #bd93f9;
    }
    
    /* Активная кнопка режима LV/HV */
    QPushButton[iconButton="true"][activeMode="LV"],
    QPushButton[iconButton="true"][activeMode="HV"] {
        background-color: #50fa7b;
        color: #282a36;
        border: 2px solid #3ddc84;
        font-weight: bold;
    }
    
    QPushButton[iconButton="true"][activeMode="LV"]:hover,
    QPushButton[iconButton="true"][activeMode="HV"]:hover {
        background-color: #3ddc84;
        border: 2px solid #2ec86a;
    }
    
    /* Обводка валидации для кнопок загрузки прошивки */
    QPushButton[validationBorder="valid"] {
        border: 2px solid #50fa7b;
    }
    
    QPushButton[validationBorder="valid"]:hover {
        border: 2px solid #3ddc84;
    }
    
    QPushButton[validationBorder="invalid"] {
        border: 2px solid #ffb86c;
    }
    
    QPushButton[validationBorder="invalid"]:hover {
        border: 2px solid #ff9800;
    }
    
    /* Контейнер для ввода с кнопкой */
    QFrame[inputContainer="true"] {
        background-color: #21222c;
        border: 1px solid #44475a;
        border-radius: 6px;
        padding: 2px;
    }
    
    QFrame[inputContainer="true"]:hover {
        border: 2px solid #6272a4;
    }
    
    /* Группа для объединения полей ввода */
    QFrame[inputGroup="true"] {
        background-color: #282a36;
        border: 1px solid #44475a;
        border-radius: 6px;
    }
    
    /* ComboBox */
    QComboBox {
        background-color: transparent;
        color: #f8f8f2;
        border: none;
        border-radius: 0px;
        padding: 4px 12px;
        font-size: 11pt;
        min-height: 28px;
    }
    
    QComboBox:hover {
        background-color: transparent;
    }
    
    QComboBox:focus {
        background-color: transparent;
    }
    
    QComboBox:disabled {
        background-color: #282a36;
        color: #6272a4;
        opacity: 0.6;
    }
    
    /* Скрываем стрелку выпадающего списка */
    QComboBox::drop-down {
        border: none;
        width: 0px;
        background-color: transparent;
    }
    
    QComboBox::drop-down:hover {
        background-color: transparent;
    }
    
    QComboBox::down-arrow {
        width: 0px;
        height: 0px;
    }
    
    /* Поле ввода текста */
    QLineEdit {
        background-color: #21222c;
        color: #f8f8f2;
        border: 1px solid #44475a;
        border-radius: 4px;
        padding: 4px 12px;
        font-size: 11pt;
        min-height: 28px;
    }
    
    QLineEdit:hover {
        border: 1px solid #6272a4;
    }
    
    QLineEdit:focus {
        border: 2px solid #8be9fd;
        background-color: #282a36;
    }
    
    /* Кнопка обновления */
    QPushButton[refreshButton="true"] {
        background-color: #44475a;
        color: #f8f8f2;
        border: 1px solid #6272a4;
        border-radius: 4px;
        font-size: 14pt;
        font-weight: bold;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
    }
    
    QPushButton[refreshButton="true"]:hover {
        background-color: #6272a4;
        border: 2px solid #8be9fd;
    }
    
    QPushButton[refreshButton="true"]:pressed {
        background-color: #50fa7b;
        color: #282a36;
        border: 2px solid #50fa7b;
    }
    
    QComboBox QAbstractItemView {
        background-color: #21222c;
        color: #f8f8f2;
        border: 1px solid #44475a;
        border-radius: 6px;
        selection-background-color: #44475a;
        selection-color: #f8f8f2;
        padding: 4px;
    }
    
    /* Текстовое поле консоли */
    QTextEdit {
        background-color: #181818;
        color: #e0e0e0;
        border: 1px solid #444444;
        border-radius: 4px;
        padding: 12px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Menlo', 'Courier New', monospace;
        font-size: 11pt;
        selection-background-color: #44475a;
        selection-color: #f8f8f2;
    }
    
    QTextEdit:focus {
        border: 1px solid #6272a4;
    }
    
    /* Прогресс-бар */
    QProgressBar {
        background-color: #21222c;
        border: 1px solid #44475a;
        border-radius: 6px;
        text-align: center;
        color: #f8f8f2;
        font-weight: 500;
        font-size: 12pt;
        height: 28px;
    }
    
    QProgressBar::chunk {
        background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 #50fa7b, stop: 1 #5af78e);
        border-radius: 5px;
    }
    
    /* Разделители */
    QFrame[frameShape="4"] {
        background-color: #44475a;
        max-height: 1px;
        min-height: 1px;
    }
    
    /* Информационные метки */
    QLabel[info="true"] {
        color: #888888;
        font-size: 11pt;
        background-color: transparent;
    }
    
    /* Сообщения об ошибках */
    QLabel[error="true"] {
        color: #ff5555;
        background-color: transparent;
    }
    
    /* Сообщения об успехе */
    QLabel[success="true"] {
        color: #50fa7b;
        background-color: transparent;
    }
    
    /* Tooltip */
    QToolTip {
        background-color: #21222c;
        color: #f8f8f2;
        border: 1px solid #44475a;
        border-radius: 4px;
        padding: 4px 8px;
    }
    
    /* Scrollbar */
    QScrollBar:vertical {
        background-color: #21222c;
        width: 12px;
        border: none;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical {
        background-color: #44475a;
        border-radius: 6px;
        min-height: 20px;
        margin: 2px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #6272a4;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    QScrollBar:horizontal {
        background-color: #21222c;
        height: 12px;
        border: none;
        border-radius: 6px;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #44475a;
        border-radius: 6px;
        min-width: 20px;
        margin: 2px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #6272a4;
    }
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    
    /* Диалоговые окна */
    QMessageBox {
        background-color: #282a36;
    }
    
    QMessageBox QLabel {
        color: #f8f8f2;
        background-color: transparent;
    }
    
    QMessageBox QPushButton {
        min-width: 80px;
        padding: 6px 20px;
    }
    
    /* Группы и фреймы */
    QGroupBox {
        border: 1px solid #44475a;
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 12px;
        color: #bd93f9;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        background-color: #282a36;
    }
    
    /* Вкладки */
    QTabWidget[tabs="true"] {
        background-color: #282a36;
        border: none;
    }
    
    QTabWidget[tabs="true"]::pane {
        background-color: #282a36;
        border: 1px solid #44475a;
        border-radius: 6px;
        top: -1px;
    }
    
    QTabBar::tab {
        background-color: #44475a;
        color: #f8f8f2;
        border: 1px solid #6272a4;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 20px;
        margin-right: 2px;
        font-size: 12pt;
        min-width: 120px;
    }
    
    QTabBar::tab:selected {
        background-color: #282a36;
        color: #bd93f9;
        border-color: #bd93f9;
        border-bottom: 1px solid #282a36;
    }
    
    QTabBar::tab:hover {
        background-color: #6272a4;
        color: #8be9fd;
    }
    
    /* Разделители */
    QFrame[separator="true"] {
        background-color: #6272a4;
        max-height: 2px;
        min-height: 2px;
        border: none;
        margin: 8px 0px;
    }
    
    /* Переключатель темы */
    QPushButton[themeToggle="true"] {
        background-color: #44475a;
        color: #f8f8f2;
        border: 1px solid #6272a4;
        border-radius: 4px;
        font-size: 14pt;
        padding: 0px;
        min-height: 28px;
        min-width: 28px;
    }
    
    QPushButton[themeToggle="true"]:hover {
        background-color: #6272a4;
        border: 2px solid #8be9fd;
    }
    
    QPushButton[themeToggle="true"]:pressed {
        background-color: #44475a;
        border: 2px solid #bd93f9;
    }
    """


def get_stylesheet(theme="dark"):
    if theme == "light":
        return get_light_stylesheet()
    else:
        return get_dark_stylesheet()
