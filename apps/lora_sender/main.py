import machine
import time
import ntptime
from apps.lorabase import hal
from core import storage
from core.support import net
from core.utils import ActivityTimer


lora = None

def app_init():
    global lora
    hal.lora.start()
    lora = hal.lora
    # net.disconnect()


def app_main():
    app_init()
    iam = storage.get("IAM")
    st = time.time()
    seq = 0

    while lora:
        ts = time.localtime()
        lora.run()

        while lora.packets:
            pkt = lora.packets.pop(0)
            rssi = lora.txr.packetRssi()
            print("{} : {} : {}".format(ts, pkt, rssi))

        if time.time() - st > 5:
            msg = "this is a test message send by: {} seq: {}".format(iam, seq)
            seq += 1
            lora.messages.append(msg)
            st = time.time()
