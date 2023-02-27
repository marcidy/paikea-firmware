from core.compat import (
    time,
    UART
)


class RPI:

    def __init__(self):
        self.uart_id = 2
        self.gps_def = {'rx': 23, 'tx': 22, 'baud': 9600}
        self.rpi_def = {'rx': 33, 'tx': 25, 'baud': 115200}
        self._loc_data = b""
        self.messages = []
        self.packets = []
        self.to_rb = []
        self.opened = False
        self.uart = None
        self.clock = None
        self.new_data = False
        self.loc_updated = False

    @property
    def loc_data(self):
        return self._loc_data

    @loc_data.setter
    def loc_data(self, val):
        if val != self._loc_data:
            self._loc_data = val
            self.loc_updated = True

    def connect(self, devices):
        for item in ['uart', 'gps_def', 'rpi_def']:
            if devices[item]:
                setattr(self, item, devices[item])

    def open(self):
        if not self.uart or self.opened:
            return False

        self.uart.deinit()
        self.uart = UART(self.uart_id,
                         self.rpi_def['baud'],
                         rx=self.rpi_def['rx'],
                         tx=self.rpi_def['tx'])
        self.uart.flush()
        self.opened = True
        return True

    def close(self):
        if not self.uart or not self.opened:
            return False

        self.uart.flush()
        self.uart.deinit()
        self.uart = UART(self.uart_id,
                         self.gps_def['baud'],
                         rx=self.gps_def['rx'],
                         tx=self.gps_def['tx'])
        self.opened = False
        return True

    def receive(self):
        abort = False
        num_pkts = 0

        if not self.opened:
            self.open()

        print("sending LISTEN")
        self.uart.write(b"LISTEN\r\n")

        data = b""
        marker = time.time()
        while not data:
            data = self.uart.readline()
            if time.time() - marker > 1:
                break
            time.sleep(.001)

        if data:
            print("rpi rec npkts: {}".format(data))

            try:
                num_pkts = int(data.decode('ascii'))
            except Exception:
                num_pkts = 0
                print("rpi: num pkts didn't decode!")

        print("num_pkts: {}".format(num_pkts))

        if num_pkts > 0:
            new_packets = []
            count = 0
            print("sending GO")
            self.uart.write(b"GO\r\n")

            for _pkt in range(num_pkts):
                marker = time.time()
                data = self.uart.readline()
                while not data:
                    data = self.uart.readline()
                    if time.time() - marker > 2:
                        print("data timeout")
                        break

                if data:
                    if data == b"CONFIRM\r\n":
                        print("rpi got early CONFIRM")
                        abort = True
                        break
                    new_packets.append(data)
                    print("rpi rec: {}".format(data))
                    count += 1

            if abort:
                print("ABORT")
                self.uart.write(b"0\r\n")

            else:
                data = self.uart.readline()
                print("rpi rec data: {}".format(data))
                if data == b"CONFIRM\r\n":
                    self.uart.write("{}\r\n".format(count).encode('ascii'))

        marker = time.time()
        data = self.uart.readline()
        while not data:
            data = self.uart.readline()
            if time.time() - marker > 2:
                print("data 2 timeout")
                break

        print("rpi rec data: {}".format(data))
        if data == b"DONE\r\n":
            self.packets.extend(new_packets)

        print("sending CLOSE")
        self.uart.write(b"CLOSE\r\n")
        time.sleep(.01)

    def run(self):
        self.open()
        self.uart.write(self.loc_data)

        while self.messages:
            msg = self.messages.pop(0)
            self.uart.write(msg + "\r\n")

        self.receive()

        if self.opened:
            self.close()

    def start(self):
        pass

    def stop(self, hard=False):
        pass
