"""
Hardware Peripherals
--------------------

A number of abstractions are used to interface with the hardware peripherals
available on the ESP32 modules.

First, the core.compat modules is used to facilitate testing by switching
between the hardware periphals when running on a device and proxy objects
when simulating.

The peripherals themselves are configured in this module, and grouped into
dictionaries for use by the connect methods of dependent drivers.

This module can be considered as the first layer of hardware abstraction,
and configured the pin connections for the hardware periphals.

PIns are configured here, passed to hardware drivers which are also configured,
and the hardware drivers are logically grouped for the higher level hal device
drivers.

This specific module is generic, in the sense that it can be used on the
hardware, but the actual applications should manage their own pin definitions
and hals.

These definions should be used only in the hal.py file, but occasionally this
encapsulation is broken.
"""
from core.compat import (
    UART,
    SPI,
    Pin,
    I2C,
    ADC,
)

#: Configure the i2c bus with scl on pin 15 and sda on pin 4
i2c_bus = I2C(freq=400000,
              scl=Pin(15, pull=Pin.PULL_UP),
              sda=Pin(4, pull=Pin.PULL_UP))

#: The spi bus is used for the on module SX127x chip.
spi_bus = SPI(1, baudrate=10000000,
              polarity=0, phase=0, bits=8, firstbit=SPI.MSB,
              sck=Pin(5, Pin.OUT, pull=Pin.PULL_DOWN),
              mosi=Pin(27, Pin.OUT, pull=Pin.PULL_UP),
              miso=Pin(19, Pin.OUT, pull=Pin.PULL_UP))

#: On the handset, the shared uart is UART2, initially configured to
#: communicate with the GPS module
shared_uart = UART(2, 9600, tx=22, rx=23, txbuf=0)

#: The GPS hal consists of the enable pin, shared uart, and indicator that
#: the connection is a uart device (can be a serial device as well)
gps = {
    'en': Pin(17, Pin.OUT),
    'conn': shared_uart,
    'conn_type': 'u',
}

#: The RockBlock group consists of the enable pin, dedicated UART1 on pins
#: tx=13 and rx=38, and the connection type indicator which defaults to uart
rb = {
    'en': Pin(12, Pin.OUT),
    'conn': UART(1, 19200, tx=13, rx=38, txbuf=0),
    'conn_type': 'u'
}

#: The port expander has an enable pin and communicates over the i2c bus
exp = {
    'en': Pin(21, Pin.OUT),
    'i2c': i2c_bus,
}

#: The battery monitor has two dedicated ADC pins, 39 and 37.  The battery
#: monitor also uses the port expander, but this is not managed here.
batt_mon = {
    'main_adc': ADC(Pin(39)),
    'ext_adc': ADC(Pin(37)),
}

#: The on-module OLED screen uses the i2c bus and a reset pin
screen = {
    'i2c': i2c_bus,
    'rst': Pin(16, Pin.OUT)
}

#: The external UART port uses the shared UART with the GPS module, so
#: requires managing
display_port = {
    'uart': shared_uart,
    'gps_def': {'rx': 23, 'tx': 22, 'baud': 9600},
    'dsp_def': {'rx': 33, 'tx': 25, 'baud': 115200},
}

#: The sx127x has 3 pins and uses the SPI bus
lora = {
    'rst': Pin(14, Pin.OUT),
    'ss': Pin(18, Pin.OUT),
    'rx_done': Pin(26, Pin.IN),
    'spi': spi_bus,
}
