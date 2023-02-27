'''
Compatibility
-------------

To facilitate testing on a computer, this module is a compatibility shim to
fall back to mock objects when not running on micropython.

Modules which only exist as builtins to micropython should be imported from
here as a single place for compatibility shims
'''
try:
    import utime as time
except ImportError:
    import time

try:
    import machine
except ImportError:
    from core import mock_machine as machine

try:
    int.from_bytes(b'\xFF', 'big', False)
    int_from_bytes = int.from_bytes
except TypeError:
    def int_from_bytes(val, endian, signed):
        ''' Provide an int_from_bytes conversion function when not running on
            micropython

            :param bytes val: value to convert
            :param str endian: 'big' or 'little' for endianness
            :param bool signed: if value is signed
            :rtype: int
            :return: converted bytes to integer

        '''
        return int.from_bytes(val, endian, signed=signed)

try:
    import collections
except ImportError:
    import ucollections as collections

try:
    import btree
except ImportError:
    from unittest.mock import MagicMock
    btree = MagicMock()

try:
    import network
except ImportError:
    from unittest.mock import MagicMock
    network = MagicMock()


deepsleep = machine.deepsleep
Pin = machine.Pin
UART = machine.UART
I2C = machine.I2C
RTC = machine.RTC
ADC = machine.ADC
SPI = machine.SPI
reset = machine.reset
