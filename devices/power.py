"""
Power
-----

    The Power module is used exclusively by the handset to put the HelTec ESP32
    into a low power sleep mode.

    External peripherals are turned off.

    Shutdown is a bit complex as it relies on taking over the UART sharted
    between the GPS and DevKit, implementing a protocol to coordinate shutdown,
    setting the pins to enable wake from a low signal from the DevKit, then
    finally going to sleep.

    A full reset and executed on wake so we end up in a good, initialized
    state.

"""
import time
import os
from machine import (
    UART,
    Pin,
    lightsleep,
    reset
)
import esp32
from .hal import (
    gps,
    rb,
    lora,
)
from devices.pin_defs import (
    shared_uart,
)


def shutdown():
    ''' Turn off all the external peripherals and reconfigure the UART between
        the HelTec ESP32 and the ESP32-DevKit to coordinate shutdown using a
        simple SYN -> ACK/SYN -> ACK protocol.

        Once the final SYN is received, the HelTec is set to wake on GPIO 33
        LOW, and put into lightsleep.

        When woken, the HelTec executes a full reset.
    '''
    print("shutting down")
    gps.stop()
    rb.stop()
    lora.stop()

    shared_uart.deinit()

    time.sleep(.25)
    p = Pin(33, Pin.IN, pull=Pin.PULL_UP)
    esp32.wake_on_ext0(p, esp32.WAKEUP_ALL_LOW)
    lightsleep()
    os.umount("/")
    time.sleep(1)
    reset()
