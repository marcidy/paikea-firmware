'''
b'MY:37.8251,-122.2767,0.0,0.0,21:22:00;TG:0,0,0,0,00:00:00,L;'
'''
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

from .hal import uart
from .aprimitives.queue import Queue


def loc(data_fields):
    fields = data_fields.split(",")
    lat, lon, cog, sog, utc = fields
    lat = float(lat)
    lon = float(lon)
    cog = float(cog)
    sog = float(sog)
    return {'lat': lat, 'lon': lon, 'sog': sog, 'cog': cog, 'utc': utc}


def tg_loc(data_fields):
    fields = data_fields.split(",")
    lat, lon, cog, sog, utc, src = fields
    lat = float(lat)
    lon = float(lon)
    cog = float(cog)
    sog = float(sog)
    return {'lat': lat, 'lon': lon, 'sog': sog,
            'cog': cog, 'utc': utc, 'src': src}


def status(data_fields):
    fields = data_fields.split(",")
    to_send, to_rec, target_status, batt = fields
    # int, int, bool
    return {'send': int(to_send),
            'rec': int(to_rec),
            'target': int(target_status),
            'batt': float(batt),
            }


parser_router = {
    'MY': loc,
    'TG': tg_loc,
    'ST': status,
}


def parse_esp_data(data):
    try:
        pkts = data.decode('ascii').strip().split(";")
    except UnicodeError:
        return

    out = {}

    for pkt in pkts:
        if not pkt:
            continue
        print(pkt)
        try:
            pkt_type, data_fields = pkt.split(":", 1)
        except Exception as e:
            print("esp pkt err: {}".format(e))
            return
        parsed = parser_router.get(pkt_type, lambda x: {})(data_fields)
        tag = pkt_type.lower() + "_"
        for k, v in parsed.items():
            out[tag + k] = v

    return out


class CommPort():

    def __init__(self):
        self.recv_buf = []
        self.send_buf = []
        self.uart = uart
        self.reader = asyncio.StreamReader(uart)
        self.mode = 'read'
        self.send_q = Queue(50)
        self.recv_q = Queue(50)

    async def send(self):

        to_send = len(self.send_buf)
        print("to send: {}".format(to_send))
        items = self.send_buf[0:to_send]

        self.uart.write("{}\r\n".format(to_send).encode("ascii"))

        if to_send > 0:
            data = await self.reader.readline()
            print("comm port go?: {}".format(data))

            if data == b"GO\r\n":
                while items:
                    item = items.pop(0)
                    try:
                        item = item.encode('ascii')
                    except UnicodeError:
                        item = b"IGNORE"
                    except AttributeError:
                        pass

                    print("Port send: {}".format(item))
                    self.uart.write(item + b"\r\n")

                print("comm port sending confirm")
                self.uart.write(b"CONFIRM\r\n")

                data = await self.reader.readline()

                if data:
                    print("comm port num?: {}".format(data))
                try:
                    num_items = int(data.decode('ascii').strip('\r\n'))
                except Exception:
                    print("protocol failure, returned num_items didn't decode to an int")
                    num_items = 0

                if num_items == to_send:
                    self.send_buf = self.send_buf[to_send:]
                else:
                    self.uart.write(b"CANCEL\r\n")
        self.uart.write(b"DONE\r\n")

    async def run(self):
        done = False

        while True:
            data = await self.reader.readline()

            if data:
                print("comm data: {}".format(data))
                done = False
            else:
                continue

            if data == b"LISTEN\r\n":
                self.mode = 'write'

            elif data == b"CLOSE\r\n":
                self.mode = 'read'
                done = True

            if not done and self.mode == 'write':
                await self.send()

            if not done and self.mode == 'read':
                self.recv_buf.append(data)

            if done:
                while self.recv_buf:
                    await self.recv_q.put(self.recv_buf.pop(0))

            while not self.send_q.empty():
                self.send_buf.append(await self.send_q.get())

comm_port = CommPort()


if __name__ == "__main__":
    pkt = b'MY:37.8251,-122.2767,0.0,0.0,21:22:00;TG:0,0,0,0,00:00:00,L;'
    print(parse_esp_data(pkt))
    pkt = b"ST:4,2,0;"
    print(parse_esp_data(pkt))
