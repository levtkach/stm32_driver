# STM32 Programmer

Программа для прошивки микроконтроллеров STM32 через ST-Link программатор.

## Возможности

- Прошивка плат STM32 через ST-Link
- Поддержка методов: pystlink, OpenOCD, STM32CubeProgrammer
- GUI и CLI интерфейсы
- Автоматическое тестирование после прошивки
- Работа с UART для управления режимами

## Установка

```bash
pip install -r requirements.txt
```

## Использование

GUI:
```bash
python main_gui.py
```

CLI:
```bash
python main_cli.py
```

## Требования

- Python 3.6+
- ST-Link программатор
- STM32 микроконтроллер
