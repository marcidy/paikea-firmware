"""
AT Modem Controller
-------------------
Controller for a modem responsive to AT commands.

Modem Controllers implement the `connect` interface and switch between
connection types.  Connection types are current 'u' for UART and 's' for
Serial.  This allows modems to be tested though a serial port or a uart.

The controller buffers received partial lines as the `unterminated` instance
variable.

"""
from core.compat import time
import gc


class ModemController:

    def __init__(self):
        self.modem_wait = .05
        self.conn = None
        self.conn_type = None
        self.unterminated = b''

    def connect(self, conn, conn_type):
        ''' Connect the controller to a serial or uart peripheral

            :param conn: Serial or UART
            :param str conn_type: 's' for serial, 'u' for Uart

        '''
        if conn_type not in ['u', 's']:
            raise ValueError("Connection must be 'u' for UART"
                             "or 's' for Serial")

        self.conn = conn
        self.conn_type = conn_type
        retries = 5
        while not self.get_mode() and retries > 0:
            time.sleep(1)
            retries -= 1

    def raw_read(self):
        ''' Read all pending bytes from underlying peripheral

            :rtype: bytes
            :return: byte string

        '''
        if self.conn_type == 's':
            return self.conn.read_all()
        elif self.conn_type == 'u':
            return self.conn.read()

    def any(self):
        ''' Check if any pending bytes to read

            :return: number of pending bytes
            :rtype: int
        '''
        if self.conn_type == 's':
            return self.conn.in_waiting
        elif self.conn_type == 'u':
            return self.conn.any()

    def raw_write(self, msg):
        '''  Write msg to underlying peripheral

            :param bytes msg: message to send
        '''
        if self.conn:
            self.conn.write(msg)

    def readline(self):
        ''' Read a full line from underlying peripheral and return as ascii
            string

            :rtype: string
            :return: ascii decoded string
        '''
        if self.conn:
            return self.conn.readline().strip().decode("ascii")

    def ascii_write(self, msg):
        ''' Write an ascii message to underlying peripheral

            :param str mgs: Ascii sctring
        '''
        return self.raw_write(msg.encode('ascii'))

    def clear_comm(self):
        ''' Flush underlying peripheral read buffer via repeated reads.  Note
            micropython's flush method doesn't exist so this manages it
        '''
        while self.raw_read() is not None:
            pass

    def get_mode(self):
        ''' gets the mode line from AT&V and parses it.  Checks for sanity
            around Echo and Verbosity
        '''
        gc.collect()
        self.raw_read()  # quick sorta flush the interface
        self.ascii_write("AT\r")
        time.sleep(1)
        raw_data = self.raw_read()
        if raw_data:
            try:
                output = raw_data.decode("ascii")
            except UnicodeError:
                print("Unicode Error")
                return False
        else:
            return False

        lfs = output.count("\n")
        crs = output.count("\r")

        self.verbose = (lfs > 0)
        self.quiet = (lfs == 0 and crs == 0)
        self.echo = (output[0:2] == "AT")
        self.idx = int(self.echo)
        return True

    def read(self):
        ''' Read data from device and return non blank reads, decode as ascii
            per the device spec.

            :rtype: list
            :rtype: list of AT return items, decoded

        '''
        gc.collect()
        val = self.raw_read()

        if val is None:
            return ""
        else:
            # TODO: drop bad character only and let parsers decide?
            for i, b in enumerate(val):
                if b > 127:
                    break
            else:
                i = len(val)
            val = val[0:i]

            try:
                val.decode('ascii')
                self.unterminated += val
            except UnicodeError:
                pass

            items = self.unterminated.decode("ascii").replace("\n", "\r").split("\r")  # NOQA

            if len(items) > 1:
                self.unterminated = items[-1].encode("ascii")
                return [item for item in items[:-1] if item != '']
            else:
                return ""

    def more(self):
        ''' Return length of controller's unprocessed buffer '''
        return len(self.unterminated) > 0

    def atcmd(self, msg, reply=True):
        ''' Append AT prefix to msg and \\r suffix, and optionally wait
            for reply.

            :param str msg: Ascii encoded suffix for AT commands
            :param bool reply: Attempt to read response sequentially
            :rtype: None or bytes
            :return: response from modem if reply=True

        '''

        _msg = "AT" + msg + "\r"
        self.raw_write(_msg.encode("ascii"))

        if reply:
            time.sleep(self.modem_wait)
            response = self.read()
            return response

    def ping(self):
        """ Sends a bare AT command and returns the response """
        return self.atcmd("")

    def wait_for_reply(self, reply, wait_seconds):
        ''' Wait on modem for a specific string.  Appends all modem response
            to unterminated buffer and returns True if reply is in reposnse.

            Removes `reply` from unterminated buffer.

            :param bytes reply: byte buffer indicating reply on which this
                method waits
            :param int seconds: Time out in seconds after which function stops
                waiting
            :rtype: bool
            :return: True if reply received before timeout, else False

        '''
        gc.collect()
        read_start_time = time.time()

        while reply not in self.unterminated:
            val = self.raw_read()

            if val is not None:
                self.unterminated += val

            if time.time() - read_start_time > max(self.modem_wait,
                                                   wait_seconds):
                break

        if reply not in self.unterminated:
            return False
        else:
            self.unterminated = self.unterminated.replace(b"READY", b"")
            return True
