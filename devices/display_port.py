"""
Display Port
-------------

    The display port interfaces the handset with the display.  It's sharing
    the uart peripheral, and it is responsible for de-initing the uart,
    reinitiaizing it for use with the display, deiniting, with the display and
    re-initing for use with GPS.

    This runs on the handset controller.

    Due to the shared nature, the controller uses a protocol to let the display
    controler know the port is listening.

    The comm port on the display is always listening, and so sends occur without
    synchronization.
"""
from core.compat import (
    time,
    UART
)


class DisplayPort:

    def __init__(self):
        self.uart_id = 2
        self.gps_def = {'rx': 23, 'tx': 22, 'baud': 9600}
        self.dsp_def = {'rx': 33, 'tx': 25, 'baud': 115200}
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
        for item in ['uart', 'gps_def', 'dsp_def']:
            if devices[item]:
                setattr(self, item, devices[item])

    def open(self):
        if not self.uart or self.opened:
            return False

        self.uart.deinit()
        self.uart = UART(self.uart_id,
                         self.dsp_def['baud'],
                         rx=self.dsp_def['rx'],
                         tx=self.dsp_def['tx'])
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
        new_packets = []

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
            print("dsp rec npkts: {}".format(data))

            try:
                num_pkts = int(data.decode('ascii'))
            except Exception:
                num_pkts = 0
                print("dsp: num pkts didn't decode!")

        print("num_pkts: {}".format(num_pkts))

        if num_pkts > 0:
            count = 0
            print("sending GO")
            self.uart.write(b"GO\r\n")

            for _pkt in range(num_pkts):
                marker = time.time()

                data = b""
                while not data:
                    data = self.uart.readline()
                    if time.time() - marker > 2:
                        print("data timeout")
                        break

                if data == b"CONFIRM\r\n":
                    print("dsp got early CONFIRM")
                    abort = True
                    break
                new_packets.append(data)
                print("dsp rec: {}".format(data))
                count += 1

            if abort:
                print("ABORT")
                self.uart.write(b"0\r\n")

            else:
                data = b""
                marker = time.time()
                while not data:
                    data = self.uart.readline()
                    if time.time() - marker > 2:
                        print("confirm timeout")
                        break

                print("dsp rec confirm: {}".format(data))
                if data == b"CONFIRM\r\n":
                    self.uart.write("{}\r\n".format(count).encode('ascii'))

        marker = time.time()
        data = self.uart.readline()
        while not data:
            data = self.uart.readline()
            if time.time() - marker > 2:
                print("data 2 timeout")
                break

        print("dsp rec done: {}".format(data))
        if data == b"DONE\r\n":
            self.packets.extend(new_packets)

        print("sending CLOSE")
        self.uart.write(b"CLOSE\r\n")
        time.sleep(.01)

    def run(self):
        self.open()
        self.uart.write(self.loc_data + "\r\n")

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
