"""
Clock
-----
    The Clock device interfaces with the time and RTC micropython modules and
    unifies access so all devices can access the same clock information through
    a single interface.
"""
from core.compat import (
    time,
    RTC
)


class Clock:

    def __init__(self):
        self.base = time.time()
        self.time = time.time
        self.date = (2020, 1, 1)

    def now(self):
        ''' access the current system time
            :return: Current timestamp in seconds
            :rtype: int
        '''
        return self.time()

    def update_date(self, new_date):
        ''' Set a new date.

            :param iterable new_data: (month year number, month number,
                day number)
        '''
        self.date = (int(new_date[0]), int(new_date[1]), int(new_date[2]))

    def update_time(self, new_time):
        ''' Set a new base timestamp.

            :param iterable[3] new_time: (hour, mintue, seconds)
        '''
        self.base = (int(new_time[0]) * 3600 +
                     int(new_time[1]) * 60 +
                     int(new_time[2]))

    def rtc_datetime(self, new_date, new_time):
        ''' Create a tuple from a date and time in a format useful for the RTC
            module.

            :param iterable[3] new_date: year, month, day
            :param iterable[3] new_time: hour, minute, second
            :returns: (year, month, day, hour, minute, second, 0, 0)
            :rtype: tuple
        '''
        return (new_date[0], new_date[1], new_date[2],
                new_time[0], new_time[1], new_time[2], 0, 0)

    def sleep(self, sleep_time):
        ''' Passes argument to time.sleep

            :param int sleep_time: number of seconds to sleep
        '''
        time.sleep(sleep_time)

    def wait(self, waitsec):
        self.wait_ms(waitsec * 1000)

    def wait_ms(self, waitms):
        start = time.ticks_ms()

        while time.ticks_ms() - start < waitms:
            pass

    def set_rtc(self, datetime_tuple):
        ''' Set up the RTC peripheral with a base datetime

            :param tuple datetime_tuple: (year, month, day, hour, minute,
                second, millisecond, microsecond)
            :rtype: Boolean
            :return: If the datetime_tuple is wrong, returns false, else true
        '''
        if len(datetime_tuple) != 8:
            return False
        rtc = RTC()
        rtc.init(datetime_tuple)
        self.rtc_set = True
        self.rtc = rtc
        return True
