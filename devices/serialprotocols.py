"""
Serial Protocols
----------------

Basic string parsing used for NMEA devices
"""


class ProtocolSpec:
    ''' Specifiy the protocol for parsing a string '''

    def __init__(self,
                 preamble='$',
                 datafield_terminator='*',
                 datafield_delimiter=',',
                 postfix="\r\n"):
        self.preamble = preamble
        self.datafield_terminator = datafield_terminator
        self.datafield_delimiter = datafield_delimiter
        self.postfix = postfix


class SimpleSerialProtocol:
    ''' State management for simple serial protocol parsing '''

    def __init__(self, spec, sentence="", parser_lut=None):
        self.sentence = sentence
        self.spec = spec
        self.parser_lut = parser_lut
        self.scan()
        self.data = {}

    def __call__(self, sentence, parser=None):
        self.sentence = sentence
        self.scan()
        if parser:
            self.set_parser(parser)

    def __repr__(self):
        return self.sentence

    def set_parser(self, parser):
        ''' Set the parser for use with this sentence

            :param parser: parser to use for this sentence

        '''
        self.parser = parser

    @staticmethod
    def compute_crc(chksum_data):
        ''' NMEA CRC calculation.

            :param str chksum_data: String data on which to compute CRC
            :rtype: str
            :returns: string of CRC bytes

        '''

        crc = 0
        for _char in chksum_data:
            try:
                crc = crc ^ ord(_char.encode("ascii"))
            except Exception:
                return "00"
        return "{:02X}".format(crc)

    def clear(self):
        ''' Clear protocol state '''
        self.sentence = ""
        self.data.clear()

    def validate(self):
        '''Check for basic properties of the sentence.

            Terminators have been stripped at this step.

            Only basic syntax checks before parsing.

            Sentence is not semantically valid and not CRC checked.  If this
            check fails, a CRC cannot be computed.

            :rtype: bool
            :returns: True if basic syntax of sentence indicates parsing is
                possible

        '''
        return all([
            self.sentence.find(self.spec.preamble) == 0,
            self.sentence.find(self.spec.datafield_terminator) != -1,
            self.sentence.count(self.spec.preamble) == 1,
            self.sentence.count(self.spec.datafield_terminator) == 1,
        ])

    def scan(self):
        '''scan the sentence and separate each meaningful unit'''
        if self.validate():
            _, self.preamble, tail = \
                self.sentence.partition(self.spec.preamble)
            cksum_data, _, tail = \
                tail.partition(self.spec.datafield_terminator)
            self.pkt_type, _,  self.datafields = \
                cksum_data.partition(self.spec.datafield_delimiter)
            self.crc = tail.strip(self.spec.postfix)
            self.valid = self.compute_crc(cksum_data).upper() == self.crc
        else:
            self.valid = False

    def set_router(self, callable):
        ''' Set the sentence router for this protocol.

            :param callable: callable is called to set the route_path.

        '''
        self.route_path = callable()

    def route(self):
        ''' Set the parser via routing the route_path calculated from the
            sentence data.
        '''
        if self.route_path(self) in self.parser_lut:
            self.set_parser(self.parser_lut[self.route_path(self)])
        # else:
            # print("Bad look up: {}".format(self.route_path(self)))

    def parse(self):
        ''' Attempt to apply the sentence parser to the sentence data
        '''
        try:
            self.data = self.parser(self)
        except Exception:
            # print("Parsing Failed!")
            # print(self.sentence)
            pass

    def create_packet(self, talker_id, pkt_type, data_field=None):
        ''' construct a valid packet from given input data via this protocol

            :param str talker_id:  ID of device creating packet
            :param str pkt_type: packet type indicator
            :param str data_field: packet data fields
            :rtype: str
            :return: valid packet

        '''
        if data_field is None:
            value = pkt_type
        else:
            value = pkt_type + self.spec.datafield_delimiter + data_field

        _cmd = self.spec.preamble + talker_id
        _cmd += value
        _cmd += self.spec.datafield_terminator
        _cmd += self.compute_crc(talker_id + value)
        _cmd += self.spec.postfix
        return _cmd


class SimpleStream():
    ''' Simple stream handler for packetize data from an underlying connection.

        :ivar connection conn: connection with a read method
        :ivar Protocol prot: Protocol for packets
        :ivar str unterminated: Data read from device that is unterminated
        :ivar str terminated: Data read from device which has protoocl
            terminator
        :ivar bool more: indicator for unterminated ata
        :ivar dict data: data parsed into dicts via protocol
    '''

    def __init__(self, connection, protocol):
        self.conn = connection
        self.prot = protocol
        self.unterminated = ''
        self.terminated = ''
        self.more = False
        self.data = {}

    def read(self):
        ''' Read data from connection and set `more` attempt to decode data
            as ascii.   Ignore data which cannot be decoded.
        '''
        data = self.conn.read()
        if not data:
            self.more = False
            return
        self.more = len(data) > 0
        try:
            self.unterminated += data.decode('ascii')
        except UnicodeError:
            pass

    def consume(self):
        ''' Process data received from device and parse if via protocol '''
        postfix = self.prot.spec.postfix

        if self.unterminated.find(postfix) > -1:
            self.terminated, self.unterminated = \
                self.unterminated.split(postfix, 1)

        self.more = self.unterminated.count(postfix) > 0

        self.prot(self.terminated + postfix)
        if self.prot.valid:
            self.prot.route()
            self.prot.parse()
            self.data.update(self.prot.data)

    def clear(self):
        ''' Reset stream state '''
        self.unterminated = ''
        self.terminated = ''
        self.more = False
        if self.prot:
            self.prot.clear()
