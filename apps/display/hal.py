from core.compat import (
    Pin,
    SPI,
    UART,
)
import esp32


# main
p2 = Pin(22, Pin.OUT)

# controllers
b1 = Pin(25, Pin.IN, Pin.PULL_UP)
b2 = Pin(26, Pin.IN, Pin.PULL_UP)
b3 = Pin(27, Pin.IN, Pin.PULL_UP)
b4 = Pin(14, Pin.IN, Pin.PULL_UP)

esp32.wake_on_ext0(Pin(14), esp32.WAKEUP_ALL_LOW)

# display
uart = UART(2, 115200, rx=21, tx=22, txbuf=0)

# epaper
sck = Pin(18)
miso = Pin(19)
mosi = Pin(23)
cs = Pin(5)
rst = Pin(16)
dc = Pin(17)
busy = Pin(32)

spi = SPI(2,
          baudrate=10000000,
          polarity=0, phase=0, bits=8,
          sck=sck, mosi=mosi, miso=miso)
