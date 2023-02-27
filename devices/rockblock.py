"""
RockBlock
---------
"""
from core.compat import (
    time,
)
from devices.modem import ModemController
from devices.iridium import (
    SBDCommandMixin,
    ISUResponseMixin,
    SBDSession,
)


class RockBlock(ModemController, SBDCommandMixin, ISUResponseMixin):
    """ Driver for a RockBlock device """

    def __init__(self, clock=time):
        super().__init__()
        self.clock = clock
        self.session = None
        self.last_session = None
        self.data = {}
        self._csq = 0
        self._mo_flag = 0
        self._mt_flag = 0
        self._momsn = 0
        self._mtmsn = 0
        self._ra_flag = False
        self._queue = 0
        self.csq_thresh = 2
        self.status_check_period = 30
        self.last_status_check = 0
        self.last_sat_time = 0
        self.errors = []
        self.wait_for_send = False
        self.wait_for_recv = False
        self.wait_for_read = False
        self.wait_for_data = False
        self.wait_for_status = False
        self.new_data = False
        self.reg_status = None
        self.reg_err = None
        self.last_reg_attempt = 0
        self.messages = []
        self.bad_session = False
        self.quiet = False

    def connect(self, devices):
        ''' Connect driver with underlying drivers.

            expects an enable Pin as 'en' and passes
            'conn' and 'conn_type' to Modem Controller parent.

            :param dict devices: underlying drivers
        '''
        self.en = devices['en']
        self.start()
        super().connect(devices['conn'], devices['conn_type'])

    def start(self):
        ''' Start up RockBlock w/ 5s charging time

            resets self.last_sat_time to 0
        '''
        if self.en.value() == 1:
            return
        self.en.on()  # assert the enable pin
        self.clock.sleep(5)
        self.last_sat_time = 0

    def stop(self, save=False):
        ''' Disables RockBlock via enable pin '''
        if save:
            self.atcmd("&Y0")
            self.atcmd("*F")
        self.en.off()

    def read_from_device(self):
        ''' Reads data from ISU, routing responses to parsers through the
            `route_response` member function.  If data is returned from
            parsed response, data is added to the self.data dict.
        '''
        while self.any():
            for item in self.read():
                new_data = self.route_response(item)
                if new_data:
                    self.data.update(new_data)

    def create_sbd_session(self):
        ''' Creates an SBD session with current state and callback to
            trigger an SBDIX session.

            If a session exists and has not yet completed, does nothing.

            If a session exists and is completed, checks the session, and
            schedules a new one.
        '''
        if not self.session:
            self.session = SBDSession(self.state, self.sbd_initx)
        else:
            if self.session.status in [0, 1, 2]:
                return
            else:
                self.check_session()  # handle result from session
                self.session = SBDSession(self.state, self.sbd_initx)

    @property
    def csq(self):
        ''' Returns last signal strength indicator

            :rtype: int
            :return: csq
        '''
        return self._csq

    @csq.setter
    def csq(self, val):
        ''' Sets a new csq value and triggers on_csq

            :param int val: new csq value
        '''
        self._csq = val
        self.on_csq(val)

    def state(self):
        ''' Return current messages state

            :rtype: dict
            :returns: messaging state

        '''
        return {'momsn': self.momsn, 'mtmsn': self.mtmsn, 'queue': self.queue}

    def on_csq(self, val):
        ''' Triggers activity linked to changes in csq.

            Checks the current csq_threshold, and if crosssed,
            will attemped a session if a session is scheduled.

            If the ISU is not registered, a registration will be attempted.

            If any signal has been seen, updates self.last_sat_time.
        '''
        if int(val) > self.csq_thresh:
            if self.session is not None:
                if self.session.status == 0:
                    self.session.attempt()

            # if self.reg_status != 2 and (
            #         self.clock.time() - self.last_reg_attempt > 5):
            #     self.last_reg_attempt = self.clock.time()
            #     self.atcmd("+SBDREG")

        if int(val) > 0:
            self.last_sat_time = self.clock.time()

    @property
    def mo_flag(self):
        ''' Indicates a message is waiting on the ISU to be sent.

            :rtype: bool
            :returns: True if a message is waiting to be sent, false otherwise

        '''
        return self._mo_flag

    @mo_flag.setter
    def mo_flag(self, val):
        ''' Sets the driver's mo_flag to reflect the ISU MO flag state.  If
            a message is waiting to be sent, a session is created for the
            message and the `wait_for_send` flag is set.

            :param str val: Truth value for flag

        '''
        self._mo_flag = int(val)
        if val:
            self.wait_for_send = True
            self.create_sbd_session()

    @property
    def mt_flag(self):
        ''' Indicates a message has been received to the ISU.

            :rtype: bool
            :returns: True if there is a message in the MT buffer on the ISU

        '''
        return self._mt_flag

    @mt_flag.setter
    def mt_flag(self, val):
        ''' Set the driver's mt flag based on truth of val.

            If True, the `wait_for_receive` flag is set and a read command
            is emitting to the ISU to add the message to the ISU's data
            stream

            :param val: Truthy value for flag

        '''
        if val != self._mt_flag:
            self._mt_flag = val
        if val:
            # doesn't reset status of MT flag.
            self.wait_for_read = True
            self.sbd_read_text()

    @property
    def momsn(self):
        ''' Number of messages ISU has sent.

            :rtype: int
            :return: Number of sent messages

        '''
        return self._momsn

    @momsn.setter
    def momsn(self, val):
        ''' Set the driver's momsn.

            :param int val: number of messages ISU has sent

        '''
        self._momsn = val

    @property
    def mtmsn(self):
        ''' Number of messages ISU has received.

            :rtype: int
            :return: number of messages ISU has received

        '''
        return self._mtmsn

    @mtmsn.setter
    def mtmsn(self, val):
        ''' Set the driver's number of messages the ISU has received.

            :param int val: Number of messages the ISU has received

        '''
        self._mtmsn = val

    @property
    def ra_flag(self):
        ''' Check the Ring Alert status of the driver.

            :rtype: bool
            :returns: True if ISU received a ring alert
        '''
        return self._ra_flag

    @ra_flag.setter
    def ra_flag(self, val):
        ''' Set the driver's ring alert flag to reflect the ISU ring alert
            status.

            If val is Truth, set the `wait_for_recv` flag and create a new
            SBD session to retrieve message from constellation.

            :param bool val: Set flag

        '''
        self._ra_flag = val
        if val:
            self.wait_for_recv = True
            self.create_sbd_session()

    @property
    def queue(self):
        ''' Check length of message queue on driver.

            :rtype: int
            :returns: number of messages driver knows about on constellation

        '''
        return self._queue

    @queue.setter
    def queue(self, val):
        ''' Set the size of the message queue on the driver.

            If val is greater than zero, asserts ring alert flag

            :param int val: Number of messages on consteallation queue

        '''
        self._queue = int(val)
        if int(val) > 0:
            self.ra_flag = True

    def run(self):
        ''' Run driver's event loop.  Events are collected from the ISU by
            reading the data stream from the ISU.

            If there is an SBD session, check the session.
            If there are errors, print them and clear them.

            If the driver is not waiting to send a message, and there are
            messages to send, pop off the oldest message and send it.

            Check the ISU status ever 30s.

            If the current csq is greater than 0, update last_sat time.
        '''
        self.read_from_device()
        if self.session:
            self.check_session()

        if self.errors:
            for err in self.errors:
                print("rb.run: {}".format(err))
            self.errors = []

        if not self.wait_for_send and not self.mo_flag and self.messages:
            msg = self.messages.pop(0)
            self.send_message(msg)

        if self.csq > 0:
            self.last_sat_time = self.clock.time()

        if self.queue > 0 and not self.session:
            self.ra_flag = True

        if self.quiet:
            return

        if self.clock.time() - self.last_status_check > self.status_check_period:  # NOQA
            self.atcmd("+CIER?", False)
            self.clock.sleep(.01)
            self.sbd_status(True)
            self.last_status_check = self.clock.time()


    def retry_session(self, retry):
        ''' Retry a session, implementing a back-off delay based on the number
            of attempts.

            If retry is less than 5, a new SBD session is created with a delay
            related to the number of retries.

            :param int retry: attempt number

        '''
        SBD_BACKOFF = [0, 5, 10, 30, 60]
        period = SBD_BACKOFF[min(4, retry)]
        print("session failed, retry: {} period: {}".format(retry, period))
        self.session = SBDSession(self.state, self.sbd_initx,
                                  retry=retry, delay=period)

    def check_session(self):
        ''' Check the current sbd session.

            If the session is busy (ie, we are pending a response from the ISU)
            do nothing.

            If the status is done, and failed, retry teh session.

            If the status is done and successful, Check if we received a
            message and need to read the data from the ISU.

            If we are beyond the max retries, clean up flags.
        '''

        if self.session.wait():
            return

        done = False
        self.last_session = self.session
        retry = self.last_session.retry + 1

        if self.last_session.status == 3:
            # session timeout, rebuild the session
            self.retry_session(retry)
            self.bad_session = True
            print("session timeout")
            return

        # Session complete
        if self.last_session.status == 4:
            setqueue = False
            # Send successful
            if self.last_session.mosta in [0, 1, 2, 3, 4]:
                self.wait_for_send = False
                self.sbd_clear_mo()
                setqueue = True
                done = True

            # Received message
            if self.last_session.mtsta == 1:
                self.wait_for_recv = False
                self.wait_for_read = True
                setqueue = True
                self.sbd_read_text()

            if retry <= 4 and not done:
                self.retry_session(retry)

            # manage retries, reset with no session, nothing to do
            if retry > 4 and not done:
                # Fail after 5 retries
                done = True
                self.wait_for_send = False
                self.wait_for_read = False
                self.wait_for_recv = False
                print("Out of retries, failed message")

            if done:
                self.session = None
                print("Done and mo flag: {}".format(self.mo_flag))
                if self.mo_flag == 1:
                    print("clear mo")
                    self.sbd_clear_mo()
                if setqueue:
                    self.queue = self.last_session.queue

    def send_message(self, msg):
        ''' Write a message to the ISU and trigger a SBD Status reponse to
            check if ISU now has a pending message.

            :param str message: String to send

        '''
        self.wait_for_send = True
        self.sbd_write(msg)
        self.clock.wait(.01)
        # self.sbd_write(msg)
        self.clock.wait(.01)
        self.sbd_status(True)

    def sat_ping(self):
        ''' Send a PONG response over ISU '''
        self.send_message("PONG")

    @property
    def wait(self):
        ''' Inspect driver state to see if ISU or driver is busy.

            :rtype: bool
            :returns: True if pending activity, else False.

        '''
        return any([
            self.queue > 0,
            self.wait_for_send,
            self.wait_for_recv,
            self.wait_for_read,
            self.wait_for_data,
            self.wait_for_status,
            self.new_data, ])

    def _load_data(self, pkt_type, payload):
        ''' Load a packet as if it were received from the device '''
        self.data.update({'pkea': {pkt_type: payload}})
        self.new_data = True
