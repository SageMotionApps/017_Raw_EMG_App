class sock:
    fs = {
        250: b"\x04",
        500: b"\x05",
    }

    def __init__(self, port) -> None:
        from serial import Serial
        import time

        self.delay = 0.1
        self.dev = Serial(port=port, baudrate=921600, timeout=3)
        self.time = time

    def set_frequency(self, fs):
        self.dev.flush()
        self.time.sleep(self.delay)
        self.dev.write(sock.fs[fs])
        self.time.sleep(self.delay)
        res = self.dev.read_all()
        if (fs == 500) and (len(res) == 0):
            raise NotImplementedError(
                "Invalid sample frequency, please update the device firmware or fall back to 250Hz."
            )

    @staticmethod
    def _find_devs() -> list:
        from serial.tools.list_ports import comports
        from serial import Serial, serialutil
        ret = []
        devices = comports()
        for device in devices:
            # Check if manufacturer is not None before using 'in' operator
            if device.manufacturer and "FTDI" in device.manufacturer:
                try:
                    print(f"Found potential EMG device: {device.device}")
                    dev = Serial(port=device.device, baudrate=921600, timeout=1)
                    dev.close()
                    ret.append(device.device)
                    print(f"Successfully connected to: {device.device}")
                except serialutil.SerialException as e:
                    print(f"Failed to connect to {device.device}: {e}")
                    continue
        print(f"Found {len(ret)} EMG devices.")
        
        if len(ret) == 0:
            print("No compatible devices found")
            raise Exception("EMG device not found")
        return ret

    def connect_socket(self):
        self.start_data()
        start = self.time.time()
        while self.time.time() - start < 2:
            if self.dev.in_waiting:
                self.stop_recv()
                return
            self.time.sleep(0.1)
        raise Exception("connection failed, no data available.")

    def recv_socket(self, buffer_size: int = 30):
        return self.dev.read(buffer_size)

    def start_data(self):
        self.dev.read_all()
        self.time.sleep(self.delay)
        self.dev.write(b"\x01")
        self.time.sleep(self.delay)

    def stop_recv(self):
        self.dev.write(b"\x02")
        self.time.sleep(self.delay)

    def close_socket(self):
        try:
            self.dev.write(b"\x02")
        except Exception:
            pass
        self.time.sleep(self.delay)
        self.dev.close()
        self.dev = None
        self.time.sleep(self.delay)
