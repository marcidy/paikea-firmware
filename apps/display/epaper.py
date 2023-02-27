"""
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import gc
from time import (
    sleep_ms,
    ticks_us,
    time,
)
from micropython import const
from .hal import (
    spi,
    rst,
    dc,
    busy,
    cs,
)
from .luts import (
    lut_vcom_dc,
    lut_ww,
    lut_bw,
    lut_wb,
    lut_bb,
)

# Display resolution
EPD_WIDTH = const(176)
EPD_HEIGHT = const(264)

# Display commands
PANEL_SETTING = const(0x00)
POWER_SETTING = const(0x01)
#  POWER_OFF = const(0x02)
#  POWER_OFF_SEQUENCE_SETTING = const(0x03)
POWER_ON = const(0x04)
#  POWER_ON_MEASURE = const(0x05)
BOOSTER_SOFT_START = const(0x06)
DEEP_SLEEP = const(0x07)
DATA_START_TRANSMISSION_1 = const(0x10)
#  DATA_STOP = const(0x11)
DISPLAY_REFRESH = const(0x12)
DATA_START_TRANSMISSION_2 = const(0x13)
#  PARTIAL_DATA_START_TRANSMISSION_1 = const(0x14)
#  PARTIAL_DATA_START_TRANSMISSION_2 = const(0x15)
PARTIAL_DISPLAY_REFRESH = const(0x16)
LUT_FOR_VCOM = const(0x20)
LUT_WHITE_TO_WHITE = const(0x21)
LUT_BLACK_TO_WHITE = const(0x22)
LUT_WHITE_TO_BLACK = const(0x23)
LUT_BLACK_TO_BLACK = const(0x24)
PLL_CONTROL = const(0x30)
#  TEMPERATURE_SENSOR_COMMAND = const(0x40)
#  TEMPERATURE_SENSOR_CALIBRATION = const(0x41)
#  TEMPERATURE_SENSOR_WRITE = const(0x42)
#  TEMPERATURE_SENSOR_READ = const(0x43)
VCOM_AND_DATA_INTERVAL_SETTING = const(0x50)
#  LOW_POWER_DETECTION = const(0x51)
#  TCON_SETTING = const(0x60)
TCON_RESOLUTION = const(0x61)
#  SOURCE_AND_GATE_START_SETTING = const(0x62)
#  GET_STATUS = const(0x71)
#  AUTO_MEASURE_VCOM = const(0x80)
#  VCOM_VALUE = const(0x81)
VCM_DC_SETTING_REGISTER = const(0x82)
#  PROGRAM_MODE = const(0xA0)
#  ACTIVE_PROGRAM = const(0xA1)
#  READ_OTP_DATA = const(0xA2)
POWER_OPTIMIZATION = const(0xF8)  # Power optimization in flow diagram

# Display orientation
ROTATE_0 = const(0)
ROTATE_90 = const(1)
ROTATE_180 = const(2)
ROTATE_270 = const(3)

BUSY = const(0)  # 0=busy, 1=idle


class EPD:

    LUT_VCOM_DC = bytearray(lut_vcom_dc)
    LUT_WW = bytearray(lut_ww)
    LUT_BW = bytearray(lut_bw)
    LUT_WB = bytearray(lut_wb)
    LUT_BB = bytearray(lut_bb)

    def __init__(self, spi, cs, dc, rst, busy):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.busy = busy
        # self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=0)
        self.busy.init(self.busy.IN)
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.rotate = ROTATE_0

    def _command(self, command):
        self.dc(0)
        # self.cs(0)
        self.spi.write(bytearray([command]))
        # self.cs(1)

    def _data(self, data):
        self.dc(1)
        self.spi.write(data)
        # for d in data:
        #   self.cs(0)
        #   self.spi.write(bytearray([d]))
        #   self.cs(1)

    def init(self):
        self.reset()

        # VDS_EN VDG_EN, VCOM_HV VGHL_LV[1] VGHL_LV[0], VDH, VDL, VDHR
        self._command(POWER_SETTING)
        self._data(bytearray([0x03, 0x00, 0x2b, 0x2b, 0x09]))

        self._command(BOOSTER_SOFT_START)
        self._data(bytearray([0x07, 0x07, 0x17]))

        self._command(POWER_OPTIMIZATION)
        self._data(bytearray([0x60, 0xA5]))
        self._command(POWER_OPTIMIZATION)
        self._data(bytearray([0x89, 0xA5]))
        self._command(POWER_OPTIMIZATION)
        self._data(bytearray([0x90, 0x00]))
        self._command(POWER_OPTIMIZATION)
        self._data(bytearray([0x93, 0x2A]))
        self._command(POWER_OPTIMIZATION)
        self._data(bytearray([0xA0, 0xA5]))
        self._command(POWER_OPTIMIZATION)
        self._data(bytearray([0xA1, 0x00]))
        self._command(POWER_OPTIMIZATION)
        self._data(bytearray([0x73, 0x41]))

        self._command(0x16)
        self._data(bytearray([0x00]))
        self._command(POWER_ON)
        self.wait_until_idle()

        # (296x160, LUT from register, B/W/R run both LU1 LU2,
        # scan up, shift right, bootster on) KW-BF   KWR-AF    BWROTP 0f
        self._command(PANEL_SETTING)
        self._data(bytearray([0xAF]))
        # 3A 100HZ   29 150Hz 39 200HZ    31 171HZ
        self._command(PLL_CONTROL)
        self._data(bytearray([0x39]))

        self._command(VCM_DC_SETTING_REGISTER)
        self._data(bytearray([0x12]))
        # define by OTP
        # self._command(VCOM_AND_DATA_INTERVAL_SETTING, b'\x87')
        self.set_lut()
        # self._command(PARTIAL_DISPLAY_REFRESH, b'\x00')

    def wait_until_idle(self):
        marker = time()
        while self.busy.value() == BUSY:
            sleep_ms(50)
            if time() - marker > 2:
                print("EPD took too long to respond")
                break

    def reset(self):
        self.rst(0)
        sleep_ms(200)
        self.rst(1)
        sleep_ms(200)

    def set_lut(self):
        st = ticks_us()
        self._command(LUT_FOR_VCOM)
        self._data(self.LUT_VCOM_DC)  # vcom
        self._command(LUT_WHITE_TO_WHITE)
        self._data(self.LUT_WW)  # ww --
        self._command(LUT_BLACK_TO_WHITE)
        self._data(self.LUT_BW)  # bw r
        self._command(LUT_WHITE_TO_BLACK)
        self._data(self.LUT_WB)  # wb w
        self._command(LUT_BLACK_TO_BLACK)
        self._data(self.LUT_BB)  # bb b
        print("{}".format(ticks_us() - st))

    def display(self, new_buf):

        # self._command(DATA_START_TRANSMISSION_1)
        # self._data(self.buf)
        # self._command(0x11)

        if new_buf:
            self._command(0x13)
            self._data(new_buf)
            self._command(0x11)
        self._command(DISPLAY_REFRESH)
        self.wait_until_idle()
        gc.collect()

    # to wake call reset() or init()
    def sleep(self):
        self._command(DEEP_SLEEP)
        self._data(bytearray([0xA5]))


def init():

    epd = EPD(spi, cs, dc, rst, busy)
    epd.reset()
    epd.init()
    return epd
