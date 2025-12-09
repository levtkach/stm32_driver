import serial
import serial.tools.list_ports
import threading
import time


class COMPortTerminal:
    def __init__(self):
        self.serial_port = None
        self.read_thread = None
        self.running = False
        self.target_port = "COM18"
        self.line_ending = "\n"

    def list_available_ports(self):
        print("\nДоступные COM-порты:")
        ports = serial.tools.list_ports.comports()

        if not ports:
            print("  COM-порты не найдены")
            return []

        for i, port in enumerate(ports, 1):
            print(f"  {i}. {port.device} - {port.description}")

        return [port.device for port in ports]

    def connect_to_port(self, port_name, baudrate=115200):
        try:
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )

            self.serial_port.dtr = False
            self.serial_port.rts = False

            if self.serial_port.is_open:
                print(f"\nУспешно подключено к {port_name}")
                print(f"  Скорость: {baudrate} бод")
                print(f"  Данные: 8 бит, Parity: None, Стоп-биты: 1")
                print(f"  Flow control: None")
                print(f"  DTR: Off, RTS: Off")
                print(f"  Line ending: LF (\\n)")
                return True
            else:
                print(f"\nОшибка: Не удалось открыть {port_name}")
                return False

        except serial.SerialException as e:
            print(f"\nОшибка подключения к {port_name}: {e}")
            return False
        except Exception as e:
            print(f"\nНеожиданная ошибка: {e}")
            return False

    def read_from_port(self):
        buffer = ""
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        print(text, end="", flush=True)
                        buffer += text
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    print(f"\nОшибка чтения: {e}")
                break

    def send_data(self, data):
        if self.serial_port and self.serial_port.is_open:
            try:
                data_with_lf = data + self.line_ending
                self.serial_port.write(data_with_lf.encode("utf-8"))
                self.serial_port.flush()
                print(f"[Отправлено: '{data}']")
                return True
            except Exception as e:
                print(f"Ошибка отправки: {e}")
                return False
        else:
            print("Порт не открыт")
            return False

    def disconnect(self):
        self.running = False
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)

        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("\nОтключено от COM-порта")

    def start_terminal(self):
        print("=" * 60)
        print("ТЕРМИНАЛ COM-ПОРТА")
        print("Настройки: 8 бит, 1 стоп бит, Parity None, DTR Off, RTS Off")
        print("=" * 60)

        available_ports = self.list_available_ports()

        print(f"\nПопытка подключения к {self.target_port}...")

        if self.target_port not in available_ports:
            print(f"ВНИМАНИЕ: {self.target_port} не найден в списке доступных портов!")
            print("Проверьте правильность номера порта и подключение устройства")
            response = input("Продолжить попытку подключения? (y/n): ")
            if response.lower() != "y":
                return

        if self.connect_to_port(self.target_port, 115200):
            self.running = True
            self.read_thread = threading.Thread(target=self.read_from_port)
            self.read_thread.daemon = True
            self.read_thread.start()

            print("\n" + "-" * 50)
            print("Терминал запущен. Введите текст для отправки.")
            print("Команды:")
            print("  /help - показать справку")
            print("  /disconnect - отключиться")
            print("  /baud [скорость] - изменить скорость")
            print("  /lineending [cr/lf/crlf] - изменить line ending")
            print("  /dtr [on/off] - управление DTR")
            print("  /rts [on/off] - управление RTS")
            print("  /exit - выход")
            print("-" * 50)

            self.command_loop()

        self.disconnect()

    def command_loop(self):
        while self.running:
            try:
                user_input = input().strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if user_input.lower() == "/exit":
                        break
                    elif user_input.lower() == "/disconnect":
                        break
                    elif user_input.lower() == "/help":
                        self.show_help()
                    elif user_input.lower().startswith("/baud"):
                        self.change_baudrate(user_input)
                    elif user_input.lower().startswith("/lineending"):
                        self.handle_line_ending_command(user_input)
                    elif user_input.lower().startswith("/dtr"):
                        self.handle_dtr_command(user_input)
                    elif user_input.lower().startswith("/rts"):
                        self.handle_rts_command(user_input)
                    else:
                        print("Неизвестная команда. Введите /help для справки")
                else:
                    if not self.send_data(user_input):
                        print("Ошибка отправки данных")

            except KeyboardInterrupt:
                print("\nПрервано пользователем")
                break
            except Exception as e:
                print(f"Ошибка: {e}")
                break

    def handle_dtr_command(self, command):
        parts = command.split()
        if len(parts) == 2:
            state = parts[1].lower()
            if state in ["on", "1", "true"]:
                self.serial_port.dtr = True
                print("DTR включен")
            elif state in ["off", "0", "false"]:
                self.serial_port.dtr = False
                print("DTR выключен")
            else:
                print("Использование: /dtr [on/off]")
        else:
            print(f"Текущее состояние DTR: {'On' if self.serial_port.dtr else 'Off'}")

    def handle_rts_command(self, command):
        parts = command.split()
        if len(parts) == 2:
            state = parts[1].lower()
            if state in ["on", "1", "true"]:
                self.serial_port.rts = True
                print("RTS включен")
            elif state in ["off", "0", "false"]:
                self.serial_port.rts = False
                print("RTS выключен")
            else:
                print("Использование: /rts [on/off]")
        else:
            print(f"Текущее состояние RTS: {'On' if self.serial_port.rts else 'Off'}")

    def handle_line_ending_command(self, command):
        parts = command.split()
        if len(parts) == 2:
            self.change_line_ending(parts[1])
        else:
            print("Использование: /lineending [cr/lf/crlf]")
            self.show_current_line_ending()

    def change_line_ending(self, ending_type):
        endings = {"cr": "\r", "lf": "\n", "crlf": "\r\n"}

        if ending_type.lower() in endings:
            self.line_ending = endings[ending_type.lower()]
            print(f"Line ending изменен на: {ending_type.upper()}")
            self.show_current_line_ending()
        else:
            print("Неверный тип line ending. Используйте: cr, lf или crlf")

    def show_current_line_ending(self):
        if self.line_ending == "\r":
            print("  (Carriage Return: \\r)")
        elif self.line_ending == "\n":
            print("  (Line Feed: \\n)")
        elif self.line_ending == "\r\n":
            print("  (Carriage Return + Line Feed: \\r\\n)")

    def show_help(self):
        print("\nДоступные команды:")
        print("  /help - показать эту справку")
        print("  /disconnect - отключиться от порта")
        print("  /baud [скорость] - изменить скорость")
        print("  /lineending [cr/lf/crlf] - изменить line ending")
        print("  /dtr [on/off] - управление DTR")
        print("  /rts [on/off] - управление RTS")
        print("  /exit - выйти из программы")
        print("\nТекущие настройки:")
        print(
            f"  Line ending: {'CR (\\\\r)' if self.line_ending == '\\r' else 'LF (\\\\n)' if self.line_ending == '\\n' else 'CRLF (\\\\r\\\\n)'}"
        )
        print(f"  DTR: {'On' if self.serial_port and self.serial_port.dtr else 'Off'}")
        print(f"  RTS: {'On' if self.serial_port and self.serial_port.rts else 'Off'}")
        print("\nЛюбой другой текст будет отправлен в COM-порт")

    def change_baudrate(self, command):
        try:
            parts = command.split()
            if len(parts) == 2:
                new_baud = int(parts[1])
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.baudrate = new_baud
                    print(f"Скорость изменена на {new_baud} бод")
                else:
                    print("Порт не открыт")
            else:
                print("Использование: /baud [скорость]")
        except ValueError:
            print("Неверный формат скорости")
        except Exception as e:
            print(f"Ошибка изменения скорости: {e}")


def main():
    terminal = COMPortTerminal()

    try:
        terminal.start_terminal()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        terminal.disconnect()
        print("\nПрограмма завершена.")


if __name__ == "__main__":
    main()
