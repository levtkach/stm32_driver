from programmer_base import BaseProgrammer


def main():
    programmer = BaseProgrammer()
    devices = programmer.find_devices()
    if not devices:
        return
    try:
        print("Устройства:")
        for i, dev in enumerate(devices, 1):
            print(f"{i}. {dev['name']}")
        choice = 1
        if programmer.select_device(choice):
            test_addresses = [
                (0x08000000, "Flash начало"),
            ]
            for address, description in test_addresses:
                data = (
                    b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa"
                )
                success = programmer.write_bytes(data, address)
                print(f"Результат: {'успех' if success else 'ошибка'}")
    except Exception as e:
        print(f"Ошибка: {e}")


if __name__ == "__main__":
    main()
