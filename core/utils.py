"""
Utils
-----

Utility classes used in various places in the firmware
"""


class ActivityTimer:
    """ A software timer to keep track of expiring timers """

    def __init__(self, name, clock, delay, marker_init=0, activity=None):
        self.name = name
        self.clock = clock
        self.delay = delay
        self.marker = marker_init
        self._expired = False
        self.running = False
        self.checked = 0
        self.activity = activity

    def start(self):
        """ Start the timer.  If it's not currently running, ppdates the marker
            to the current timestamp and sets the running field to True.
        """
        if not self.running:
            self.marker = self.clock.time()
            self.running = True

    def stop(self):
        """ Sets the running field to False. """
        self.running = False

    def reset(self):
        """ Sets the marker to the current time and resets the expired flag """
        self.marker = self.clock.time()
        self._expired = False

    @property
    def expired(self):
        """ Checks to see if the timer has expired
            :rtype: bool
            :return: True if expired, False if not
        """
        self.wait
        return self._expired

    @property
    def wait(self):
        """ Waiting the timer updates it's iternal state and returns a boolean
            indicating if there is more time between the marker and the period
            end.

            :rtype: bool
            :return: True if time remains, False if not.
        """
        if not self.running:
            return False  # Not running, nothing to wait on
        else:
            self.checked = self.clock.time()
            if self.checked - self.marker > self.delay:
                self._expired = True
                return False
            return True

    @property
    def wait_time(self):
        """ Returns the time till timer expires
            :rtype: int
            :return: Time in seconds before timer expires
        """
        if self.wait:
            return max(self.delay - (self.checked - self.marker), 0)
        else:
            return 0
