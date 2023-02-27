import uasyncio
from core import storage
from core.compat import (
    deepsleep,
    reset,
)
from .hal import (
    p2,
    uart,
)
from .esp_parser import comm_port


def startup():
    # start up handset controller
    p2.off()


# await on comm_port recv buf for the stuff i guess?

def _waitloop(listen_for):

    cmd = "CMD;{}\r\n".format(listen_for).encode('utf-8')
    acksyn = "{}:ACKSYN\r\n".format(listen_for).encode('utf-8')
    endsyn = "{}:SYN\r\n".format(listen_for).encode('utf-8')

    while True:
        data = uart.readline()

        if data:
            print(data)
        if data == b"LISTEN\r\n":
            # uart.write(b"CMD;001\r\n")
            uart.write(cmd)

        # elif data == b"001:ACKSYN\r\n":
        elif data == acksyn:
            # uart.write(b"001:SYN\r\n")
            uart.write(endsyn)
            break



def shutdown():
    deepsleep()


def reset_into_ota():
    storage.put("APP", "ota")
    reset()
