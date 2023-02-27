'''
Mock Machine
------------

To fascillitate both unit testing and exploratory testing, this module stands
in for the micropython machine module.  It does not provide a simulation of
the hardware, just interfaces that can be used on a non-device to work
on the firmware and unittest other modules.

unittest.mock.MagicMock objects are used when no specific behavior is required,
otherwise classes and functions provide minimal working interfaces to use
with the rest of the firmware in a test setting.
'''
from unittest.mock import MagicMock
import sys
import time


#: Mock Pin
Pin = MagicMock()
# I2C = MagicMock()
# UART = MagicMock()
#: Mock RTC
RTC = MagicMock()
#: Mock ADC
ADC = MagicMock()


def reset():
    ''' use sys.exit as a proxy for a system reset '''
    sys.exit()


def lightsleep(x):
    ''' Put the process to sleep.

        :param int x: time to sleep in milliseconds
    '''

    print("light sleep for: {}".format(x/1000))
    time.sleep(x/1000)


def deepsleep(x=None):
    if x:
        time.sleep(x/1000)


def freq(x):
    ''' Mimic a change in machine CPU frequency.  Does not effect anything but
        will print the frequency

        :param int x: Frequency in Hz to switch to.
    '''
    print("setting freq to {}".format(x))


class UART:
    ''' A UART proxt for use in testing '''
    def __init__(self, num, baudrate, tx=None, rx=None, **kwargs):
        self.inited = True
        self.num = num
        self.baudrate = baudrate
        self.tx = Pin(tx)
        self.rx = Pin(rx)
        self._writebuf = b""
        self._readbuf = b""

    def any(self):
        ''' Returns the length of data in the read buffer if the UART is
            configured '''
        if self.inited:
            return len(self._readbuf)
        else:
            # raise an exception
            pass

    def read(self):
        ''' Returns the entire read buffer and clears it
            :rtype: bytes
            :return: contents of the read buffer
        '''
        out = self._readbuf
        self._readbuf = b""
        return out

    def write(self, val):
        ''' Adds data as bytes to the write buffer.  If data is not encoded,
            will attempt ascii encoding.

            :param str|bytes val: adds val to write buffer
        '''
        if isinstance(val, bytes):
            self._writebuf += val
        elif isinstance(val, str):
            self._writebuf += val.encode("ascii")

    def readline(self):
        ''' if there is a completed line in the read buffer, will return
            the first fill line, otherwise returns empty bytes.

            :rtype: bytes
            :return: Single line ending in b'\n' or b''
        '''
        if b"\n" in self._readbuf:
            ret, self._readbuf = self._readbuf.split(b"\n", 1)
            return ret + b"\n"
        else:
            return b""

    def deinit(self):
        ''' Simulates deiniting the UART '''
        self.inited = False


class I2C:
    ''' An I2C proxy for testing '''
    #: hardcode address as 36
    addr = 36

    def __init__(self, freq=100000, scl=None, sda=None):
        self.freq = freq
        self.scl = scl
        self.sda = sda
        self.registers = [0, 0, 0xFF, 0xFF, 0, 0, 0xFF, 0xFF]

    def writeto_mem(self, addr, reg, data):
        ''' Updates register data.  Registers of device are also accessible
            via data = self.registers[address]

            :param int addr: address of i2c device
            :param bytes reg: address of register on target i2c device
            :param bytes data: data to write into register
        '''
        print("I2C {}: wrote {:08b} to reg {}".format(addr, data[0], reg))
        self.registers[reg] = data[0]

    def readfrom_mem(self, addr, reg, num):
        ''' Read data from target i2c device register
            :rtype: bytes
            :return: data from register as a byte
            :param int addr: address of target i2c device
            :param bytes reg: register address from which to retrieve data
            :param int num: number of bytes to read
        '''
        ret = self.registers[reg]
        print("I2C {}: read  {:08b} from reg {}".format(addr, ret, reg))
        return bytes([ret])

    def scan(self):
        ''' Mimics scanning the i2c bus, returns attached devices as list of
            addresses which respond to scan.   Currently just using 1.
            :rtype: list
            :return: list of addresses of attached i2c devices
        '''
        return [self.addr]


class SPI:
    ''' An SPI bus proxe for testing '''
    #: Most significant bit first
    MSB = 0
    #: Least significant bit first
    LSB = 1

    def __init__(self,
                 spi_id=0,
                 baudrate=10000000,
                 polarity=0,
                 phase=0,
                 bits=8,
                 firstbit=0,
                 sck=None,
                 mosi=None,
                 miso=None):
        self.spi_id=spi_id
        self.baudrate = baudrate
        self.polarity = polarity
        self.phase = phase
        self.bits = bits
        self.firstbit = firstbit
        self.sck = sck
        self.mosi = mosi
        self.miso = miso

    def write(self, buf):
        pass

    def write_readinto(self, buf, resp):
        pass
