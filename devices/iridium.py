import gc
from core.compat import time


class SBDSession:
    '''An SBD session tracks the status and reponse from the SBD modem related
    to a Short Burst Data session.

    ======  ========
    status  meaning
    ======  ========
        0   ready
        1   trying
        2   delayed
        3   failed
        4   complete
    ======  ========
    '''

    def __init__(self, state_callback, run_callback, timeout=30,
                 retry=0, delay=0, on_complete=None):
        self.state_callback = state_callback
        self.run_callback = run_callback
        self.timeout = timeout
        self.retry = retry
        self.delay = delay
        if delay > 0:
            self.status = 2
            self.start = time.time()
        else:
            self.status = 0
            self.start = 0
        self.end = 0
        self.mosta = None
        self.mtsta = None
        self.queue = None
        self.momsn = None
        self.mtmsn = None
        self.mtlen = None
        self.prev_state = None
        self.on_complete = on_complete

    def attempt(self):
        ''' Attempt an SBD session.  If this session has not been previously
            attempted (self.status == ), then collect the modem state, set
            the start time of the session, set the status to 1, and execute
            the run callback which triggers the attempt from the modem
            controller.
        '''
        if self.status == 0:
            self.prev_state = self.state_callback()
            self.start = time.time()
            self.status = 1
            self.run_callback()

    def complete(self, status):
        ''' Complete the session.  Collect session attributes from the passed
            in status dict, update the status to complated, set the session
            end time, and run the on complete.

            :param dict status: dictionary of values from an SBDI[X] modem
                response
        '''
        for k, v in status.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.end = time.time()
        self.status = 4
        if self.on_complete:
            self.on_complete()

    def wait(self):
        ''' Wait on the session, and check the timeout.  If timeout has
            occurred, fail the session with status = 3.

            :rtype: bool
            :return: True if session is alive, False if session is complete
        '''

        if self.status == 0:
            return True

        elif self.status == 1:
            if time.time() - self.start < self.timeout:
                return True
            else:
                self.status = 3
                return False

        elif self.status == 2:
            # delayed start, check delay and trigger attempt if delay over
            if time.time() - self.start > self.delay:
                self.status = 0
            return True

        elif self.status in [3, 4]:
            return False


class SBDCommandMixin:

    SBD_INITX_PAUSE = 1
    SBD_WRITE_WAIT = 5
    SBD_WRITE_PAUSE = 1

    def sbd_clear_buffer(self, buffer_num):
        ''' Using this command or power cycling the phone are the only means
        by which both buffers are cleared.  Relevant on the 9602-SB, this
        command does not clear the Codephase data buffer (see +SBDCW), which
        may therefore still be sent in the next mobile originated SBD
        message.

        The mobile terminated buffer will be cleared when an SBD
        session is initiated.  Sending a message from the ISU to the ESS
        does not clear the mobile originated buffer.

        Reading a message from the ISU does not clear the mobile terminated
        buffer.

        :param int buffer_num: Buffer to clear, 0 - clears the MO,
            1 - clears to MT, 2 - clears both
        '''
        return self.atcmd("+SBDD" + str(buffer_num), False)

    def sbd_clear_mo(self):
        ''' Clears the MO buffer'''
        return self.sbd_clear_buffer(0)

    def sbd_clear_mt(self):
        ''' Clears the MT buffer'''
        return self.sbd_clear_buffer(1)

    def sbd_delivery_short_code(self, value="?"):
        ''' Dynamic routinging or control information for MO or MT.  All values
            in decimal <0...255>.

            .. list-table:: Values
                :header-rows: 1

                * - value
                  - meaning
                * - 0x08
                  - Hold MT message delivery
                * - 0x40
                  - Leave MT in message queue after delivery
                * - 0x20
                  - Destination in MO payload

            :rtype: str
            :return: 0 - OK, 1 - Error

        '''
        return self.atcmd("+SBDDSC" + str(value), False)

    def sbd_gateway(self, numeric=False):
        ''' Read back the iridium gateway for SBD messages.'''
        _cmd = "+SBDGW"
        if numeric:
            _cmd += "N"
        return self.atcmd(_cmd, False)

    def sbd_ring_alerts(self, value="?"):
        """ Query, enable or disable Ring Alerts.

            :param str value: "?" queries RA status
        """
        return self.atcmd("+SBDMTA" + str(value), False)

    def sbd_status(self, extended=True):
        '''Returns status of the MO and MT buffers.  Short or extended.

            Response: MO flag, MOMSN, MT flag, MTMSN[, RA flag, msg waiting]

            :param bool extended: True for an SBDIX session, False for SBDI

        '''
        _cmd = "+SBDS"
        if extended:
            _cmd += "X"
        self.atcmd(_cmd, False)
        self.wait_for_status = True

    def sbd_session_timeout(self, value="?"):
        '''Session time out, in seconds'''
        return self.atcmd("+SBDST{}".format(value), False)

    def sbd_clear_momsn(self):
        ''' Clears MOMSN - Mobile Originated Message Sequence Number.  The
        MO sequence number is stored in non-voltile memory, and therefore must
        be intentionally cleared when desired.  Power cycle does not clear the
        MOMSN.'''
        return self.atcmd("+SBDC", False)

    def sbd_initx(self, ring_alert=False, location=None):
        ''' Performs registration and should be used when application uses
            Ring Alerts.  Emits a AT+SBDIX command which should elicit
            a response from the modem.

            :param bool ring_alert: Append "A" which indicates response to a ring alert
            :param str location: GPS location
        '''
        _cmd = "+SBDIX"
        if ring_alert:
            _cmd += "A"  # if in response to ring alert
        if location:
            _cmd += "=" + location
        self.atcmd(_cmd, reply=False)

    def sbd_write(self, message):
        """ Write an ascii message to the SBD modem's MO buffer for sending.

            :param str message: message to send

        """
        gc.collect()
        max_length = 340
        if len(message) < 1 or len(message) > max_length:
            raise Exception("length: {}".format(len(message)))

        if len(message) <= max_length and message[-1] != ['\r']:
            message += '\r'

        print("rb msg load: {}".format(message))
        # this tosses some data, can append to unterminated string...
        self.atcmd("+SBDWT", False)  # Initiate long write
        if self.wait_for_reply(b"READY\r\n", self.SBD_WRITE_WAIT):
            self.ascii_write(message)
            return True

        return False

    def sbd_write_binary(self, raw_msg):
        ''' Write a binary raw_msg to ISU.

            Please note the issue regading response codes as written in the

            Iridium ISU AT Command Reference:
            "All reponse codes except 1 are followed by 'OK'"

            :param bytes raw_msg: byte message to place in MO buffer

        '''
        gc.collect()
        msg_len = len(raw_msg)
        if msg_len < 1 or msg_len > 340:
            raise Exception("length: {}".format(msg_len))

        raw_msg = raw_msg + self.sbd_crc(raw_msg)
        # Note: no termination required, based on number of bytes processed.

        self.atcmd("+SBDWB={}".format(msg_len), False)

        # Wait for a string for n seconds
        if self.wait_for_reply(b"READY\r\n", self.SBD_WRITE_WAIT):
            self.raw_write(raw_msg)
        else:
            return False

    def sbd_read_text(self):
        """ Issue the command to read the MT buffer into the data stream """
        gc.collect()
        return self.atcmd("+SBDRT", False)

    def sbd_read_binary(self):
        """ Issue the command to read the MT buffer into the datastream as
            binary data.
        """
        gc.collect()
        self.atcmd("+SBDRB", False)
        time.sleep(self.modem_wait)

        data = [word for word
                in self.raw_read().replace(b"\n", b"\r").split(b"\r")
                if word != b""]

        # FIXME: More protocol checking for raw_read() result
        data = b"".join(data[self.idx:-1])  # Strip off echo and result code
        size = int.from_bytes(data[:2], 'big')
        value = data[2: -2]
        if data[-2:] == self.sbd_crc(value) and len(value) == size:
            return value
        else:
            raise Exception(value)

    def sbd_crc(self, raw_message):
        """ Calculate the CRC of the SBD raw message.

            :param bytes raw_message: message to calculate CRC for
            :rtype: bytes
            :return: CRC value for message

        """
        return (sum(raw_message) & 0xffff).to_bytes(2, 'big')

    def sbd_mo_to_mt(self):
        """ Copy the MO buffer to the MT buffer """
        return self.atcmd("+SBDTC", False)


class ISUResponseMixin:
    """ Mixin class to hold response parsers for the ISU modem """

    def route_response(self, resp):
        """ Message are routed based on matching the initial characers in
            the response with the keys of this dict.

            If there is a match, the handler is called on the response and a
            dict is returned based on successful parsing.

            :param str resp: ascii string of a complete ISU reposnse
            :rtype: dict
            :return: response specific dictionary

        """
        responses = [
            ("AT", self.handle_default),
            ("OK", self.handle_default),
            ("+AREG", self.handle_areg),
            ("+SBDD", self.handle_sbdclear),
            ("+SBDSX", self.handle_sbdsx),
            ("+SBDREG", self.handle_sbdreg),
            ("+SBDRING", self.handle_sbdring),
            ("+SBDIX", self.handle_sbdix),
            ("+CIER", self.handle_cier),
            ("+CIEV", self.handle_ciev),
            ("+SBDMTA", self.handle_sbdmta),
            ("+SBDTC", self.handle_sbdtc),
            ("-MSSTM", self.handle_msstm),
            ("-MSGEO", self.handle_msgeo),
            ("+SBDRT", self.handle_sbdtxt),
            ("SBDTC", self.handle_sbdtc),
            ("HARDWARE", self.handle_hw_failure),
            ("+DATA", self.handle_data_msg),
            ("+WPL", self.handle_waypoint_msg), ]

        for match, handler in responses:
            if resp.startswith(match):
                print("{} -> {}".format(resp, match))
                try:
                    out = handler(resp)
                except Exception:
                    out = {}
                return out

    def handle_default(self, resp):
        """ Default response handler which returns an empty dict.  Basically
            ignores the response.

            :param str resp: ISU response string
            :rtype: dict
            :return: empty dict

        """
        return {}

    def handle_areg(self, resp):
        """ Handle an AREG response from the ISU

            Parses the response into the type of event and the registration
            status.

            :param str resp: AREG response
            :rtype: dict
            :return: {'reg_evt': (int), 'reg_sta': (int)}

        """
        cmd, ret = resp.replace(" ", "").split(":")
        evt, reg_err = ret.split(",")
        return {"reg_evt": int(evt), "reg_sta": self._reg(int(reg_err))}

    def _reg(self, reg_err):
        # 0: 0 - good
        # 1: 2:15 - bad location
        # 2: 17:32,35:65 - retry
        # 3: 15,65 - bad
        # 4: 32 - no service
        # 5: 24 - radio disabled
        if reg_err == 0:
            return 0
        if 0 < reg_err < 15:
            return 1
        if 16 < reg_err < 32 or 35 < reg_err < 65:
            return 2
        if reg_err in [15, 16, 33, 65]:
            return 3
        if reg_err == 32:
            return 4
        if reg_err == 34:
            return 5

    def _mo_status(self, status):
        if 0 <= status <= 4:
            return 0
        else:
            return self._reg(status)

    def handle_sbdclear(self, resp):
        print("handle_clear: {}".format(resp))

    def handle_sbdreg(self, resp):
        """ Checks the registration status of the ISU with the constellation.

            :param str resp: SBDREG command response from ISU
            :rtype: dict
            :return: {"reg_sta": status, "reg_err": error code}
        """
        cmd, ret = resp.replace(" ", "").split(":")
        status, reg_err = ret.split(",")
        self.reg_status = int(status)
        self.reg_error = self._reg(int(reg_err))
        return {"reg_sta": int(status), "reg_err": self._reg(int(reg_err))}

    def handle_sbdsx(self, resp):
        """ Handle SBDSX response from ISU

            The extended status response displays the internal state of the
            ISU, indicating if there is a message to send, if a message was
            received, if there is a message waiting, and the number of
            messages waiting on the constellation.

            rather than return a dictionary, these values are set directly
            on the controller, as well as updates the time of the last
            status check, and clears the "wait_for_status" flag used to
            indicate a pending request from the ISU.

            :param str resp: SBDSX response from ISU
            :rtype: dict
            :return: empty dictionary

        """
        cmd, ret = resp.replace(" ", "").split(":")
        ret = ret.split(",")

        self.mo_flag = ret[0] == "1"
        self.momsn = max(0, int(ret[1]))
        self.mt_flag = ret[2] == "1"
        self.mtmsn = max(0, int(ret[3]))
        self.ra_flag = ret[4] == "1"
        # this queue is almost always unreliable.
        # self.queue = max(0, int(ret[5]))
        self.last_status_check = self.clock.time()
        self.wait_for_status = False
        return {}

    def handle_sbdix(self, resp):
        """ Handle a SBDIX response from the ISU.

            SBDIX responses are critical for sending and receiving data from
            the constellation.  They trigger the actual send and receive
            of messages.

            When an SBDIX response is received, the response data is
            passed to a SBDSession object via the SBDSession.complete(data)
            method.

            :param str resp: SBSDIX repsonse from ISU

        """
        cmd, ret = resp.replace(" ", "").split(":")
        ret = ret.split(",")
        data = {
            "mosta": int(ret[0]),  # FIXME: _mo_status(int(ret[0])),
            "momsn": int(ret[1]),
            "mtsta": int(ret[2]),
            "mtmsn": int(ret[3]),
            "mtlen": int(ret[4]),
            "queue": int(ret[5])}
        if self.session:
            self.session.complete(data)
        else:
            self.errors.append("Session result with no session")
        print(data)

    def handle_cier(self, resp):
        ''' Handle a CIER response from the ISU.

            CIER commands are used to make sure the CSQ data is produced from
            the ISU as signal strength chages.  the CSQ data is required to
            know if we have sufficient signal to attempt a message.  Emitting
            this command regularly ensures that the ISU will always be
            emitting CSQ data.

            When the ISU responds that CSQ data is not being emitted, this
            handler will emit the CIER command to configure CSQ data.

            :param str resp: CIER response from ISU
            :rtype: dict
            :return: empty dict

        '''
        _, ret = resp.replace(" ", "").split(":")
        print(ret)
        ret = ret.split(",")
        if len(ret) > 2:
            if ret[1] == "0":
                self.atcmd("+CIER=1,1,1", False)
        return {}

    def handle_ciev(self, resp):
        """ Handle CIEV reponse from ISU.

            CIEV responses provide signal information from the ISU, such as
            CSQ, net availability, antenna information, and satellite
            information.

            This handler parses the response into a dict.

            CSQ data is critical to inform the driver to send/receive messages.

            =======  =====================
            keys     meaning
            =======  =====================
            'csq'    Signal Strength
            'netav'  Network Availability
            'sv_id'  Satellite ID
            'bm_id'  Beam ID
            'sv_bm'
            'sv_x'   Satellite longitude
            'sv_y'   Satellite latitude
            'sv_z'   Satellite Altitude
            =======  =====================

            :param str resp: CIEV response
            :rtype: dict
            :return: Signal and satellite information

        """
        _, ret = resp.replace(" ", "").split(":")
        signal, tail = ret.split(",", 1)
        if signal == "0":
            data = {"csq": int(tail)}
            self.csq = int(tail)
        elif signal == "1":
            data = {"netav": tail == "1"}
        elif signal == "2":
            data = {"anterr": tail == "1"}
        elif signal == "3":
            sv_id, bm_id, sv_bm, sv_x, sv_y, sv_z = map(int, tail.split(","))
            data = {
                "sv_id": sv_id, "bm_id": bm_id, "sv_bm": sv_bm,
                "sv_x": sv_x, "sv_y": sv_y, "sv_z": sv_z}
        return data

    def handle_sbdring(self, resp):
        ''' Handle SBDRING response from ISU

            Sets the 'ra_flag' property of the ISU

            Note this is the same information has the ra line from the ISU.

            :param str resp: ISU response
            :rtype: dict
            :return: empty dict

        '''
        self.ra_flag = True
        return {}

    def handle_sbdmta(self, resp):
        ''' Handle SBDMTA reposnse from ISU.

            SBDMTA commands enable or disable ring alerts on the ISU.

            :param str resp: SBDMTA response from ISU
            :rtype: dict
            :return: empty dict

        '''
        self.ra_flag = resp[-1] == "1"
        return {}

    def handle_sbdtc(self, resp):
        """ Handle SBDTC command response from ISU.

            SBDTC commands copy the MO data to the MT buffer, which helps
            testing the hardware.  There is no need for this during normal
            operation.

            :param str resp: SBDTC response from ISU
            :rtype: dict
            :dict: Indicates the copy occurred on the ISU

        """
        return {"copy": "OK"}

    def handle_msstm(self, resp):
        return {}

    def handle_msgeo(self, resp):
        return {}

    def handle_hw_failure(self, resp):
        return {}

    def handle_sbdtxt(self, resp):
        """ Handle SBDTXT response from ISU.

            Messages are read from the ISU via the SBDTXT command.  When
            A a SBDTXT response is received, the response includes the message
            read from the MT buffer of the device.

            This sets the `wait_for_data` flag, indicating there is a message
            to process.

            :param str resp: SBDTXT response from ISU
            :rtype: dict
            :return: dict with the message as {'text': message}

        """
        self.wait_for_read = False
        self.wait_for_data = True
        return {'text': resp}

    def handle_data_msg(self, resp):
        """ Handle a DATA message.

            When a mesasge is read from the ISU via the SBDTXT command, the
            message enters the data flow as if it were a new response from the
            ISU.

            A properly formatted packet sent to the ISU will be prefixed with
            "+DATA".

            A dict is constsructed from the packet, then packed into a response
            which may include errors in processing.

            :param str resp: a +DATA response from the ISU
            :rtype: dict
            :return: {'pkea': {packe_type: packet_fields}[, 'error': errors]}

        """
        print("pkea: {}".format(resp))
        resp = resp.replace("+DATA:", "")
        fields = resp.split(";")  # command terminator

        data = {}
        errors = False
        # FIXME: handle multiple commands and stuff
        for field in fields:
            try:
                pkt_type, data_fields = field.split(',', 1)
                data[pkt_type] = data_fields

            except Exception as e:
                errors = True
                # errors.append(e)

        if len(data) > 0:
            self.new_data = True

        self.wait_for_recv = False
        self.wait_for_data = False
        self.sbd_clear_mt()
        return {'pkea': data, 'errors': errors}

    def handle_waypoint_msg(self, resp):
        ''' Handle a +WPL response from the ISU.

            A +WPL response is similar to a +DATA reponse, and serves to create
            a waypoint from msg protocol string.

            e.g.

            >>> msg = "+WPL:<cmd>;lat,3745.7876;EW,W;lon,12223.4358;NS,N;name,PAIKEA001;"

            cmd in ['ADD', 'DEL', 'MOD']

            :param str resp: +WPL response from ISU
            :rtype: dict
            :returns: waypoint dictionary
        '''
        resp = resp.replace("+WPL:", "")
        # "<cmd>;lat,3745.7876;lon,12223.4358;name,PAIKEA001;"
        items = resp.split(";")
        # [<cmd>, lat,3745.7876, lon,12223.4358, name,PAIKEA001]
        cmd = items.pop(0)
        # [lat,3745.7876, lon,12223.4358, name,PAIKEA001]
        data = {'cmd': cmd}
        for item in items:
            if item.find(',') > -1:
                k, v = item.split(',')
                data[k] = v
        return {'wpl': data}
