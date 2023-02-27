import time
import ntptime
import machine
import uasyncio as asyncio
from core import storage
from core.support import net
from core.websockets import client
from apps.irdbase.hal import (
    rb,
    lora,
)


iam = storage.get("IAM")
records = [(iam, "initializing")]
logging = asyncio.Event()
server = storage.get("LOG_WS")


class NoNetwork(Exception):
    pass


def init_network():
    net.connect()
    retrys = 10
    while not net.connected:
        time.sleep(1)
        net.connect()
        retrys -= 1
        if retrys <= 0:
            print("No network, can't init")
            raise NoNetwork("No network!")


def disconn_network():
    if net.connected:
        net.net.disconnect()
        net.net.active(0)

    if net.ap:
        net.ap.active(0)


def init_localtime():
    ntptime.settime()


async def get_localtime():
    print("getting local time")
    uri = server + "/time"
    connected = False

    while not connected:
        ws = await client.connect(uri)
        if ws:
            connected = True
        else:
            await asyncio.sleep_ms(50)

    async for msg in ws:
        tm = time.localtime(int(msg))
        machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))

    print("local time: {}".format(time.localtime()))

    ws.close()
    await ws.wait_closed()


async def check_for_cmd():
    print("Checking /cmd")
    uri = server + "/cmd"
    connected = False

    while not connected:
        ws = await client.connect(uri)
        if ws:
            connected = True
        else:
            await asyncio.sleep_ms(50)

    async for msg in ws:
        print("cmd received: {}".format(msg))
        if msg == "ota":
            storage.put("APP", "ota")
            machine.reset()
        if msg == "shell":
            storage.put("APP", "shell")
            machine.reset()

    ws.close()
    await ws.wait_closed()


async def init_main():
    global records
    try:
        # init_network()
        pass
    except NoNetwork:
        import machine
        machine.reset()
    if net.connected:
        await get_localtime()
    # disconn_network()
    rb.start()
    records.append((time.localtime(), "init"))


def check_time_to_log(last_hr):
    ts = time.localtime()
    hr = ts[3]
    return (abs(hr - last_hr) >= 2)


async def send_logs():
    global records
    uri = server + "/{}".format(iam)
    connected = False

    while not connected:
        ws = await client.connect(uri)
        if ws:
            connected = True
        else:
            await asyncio.sleep_ms(50)

    while records:
        rec = records.pop(0)
        await ws.send("{} : {}".format(rec[0], rec[1]))

    ws.close()
    await ws.wait_closed()
    print("Done!")


async def run_log():
    global records
    print("sending")
    print("records: {}".format(len(records)))
    try:
        pass
        # init_network()
    except NoNetwork:
        if len(records) > 600:
            records = records[200:]
            return

    await send_logs()
    await check_for_cmd()
    # disconn_network()
    logging.clear()


async def run():
    global records
    prev_csq = 0
    dump_thresh = 400
    records.clear()
    last_log_hr = -2

    while True:
        ts = time.localtime()
        rb.run()

        if rb.csq != prev_csq:
            if not logging.is_set():
                records.append((ts, rb.csq))
            prev_csq = rb.csq

        if not logging.is_set() and check_time_to_log(last_log_hr):
            print("trying!")
            logging.set()
            asyncio.create_task(run_log())
            last_log_hr = ts[3]

        lora.run()
        while lora.packets:
            print(lora.packets.pop(0))

        await asyncio.sleep_ms(10)


def app_main():
    # storage.put("APP", "ota")
    print("init")
    asyncio.run(init_main())
    print("main")
    loop = asyncio.get_event_loop()
    asyncio.create_task(run())
    loop.run_forever()
