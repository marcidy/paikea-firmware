from devices.nmea_parsers import MTK_PARSERS
from devices.serialprotocols import (
    SimpleSerialProtocol,
    SimpleStream,
    ProtocolSpec,
)


#: Definition of NMEA protocol parsing specificaiton.  Probably
#: shouldn't be instanciated at modules level but it's here now and working
NMEAProtocol = ProtocolSpec(
    preamble='$',
    datafield_terminator='*',
    datafield_delimiter=',',
    postfix="\r\n")


class MTKTalker():
    ''' An MTK Talker is an MTK branded GPS device which produces sentences
        parsable via the NMEA protocol.  While originally intended to be
        device specific, it's currently used as the driver for NMEA sentence
        parsing in the GPS driver.

        The create packet method is extremely useful and should be extracted
        into the NMEA protocol.

        FIXME: Needs to be make into the GPS parser rather than being
        MTK specific.

    '''
    def __init__(self):
        self.talker_id = 'PMTK'
        self.protocol = SimpleSerialProtocol(NMEAProtocol,
                                             parser_lut=MTK_PARSERS)
        self.protocol.set_router(self.router)
        self.data = {}
        self.conn = None
        self.stream = None

    def connect(self, conn):
        ''' Connect driver to peripheral and set up the data stream.

            :param driver conn: Underling peripheral driver

        '''
        self.conn = conn
        self.stream = SimpleStream(conn, self.protocol)

    def router(self):
        ''' Route lines from peripheral to packet parsers.

            :rtype: func
            :returns: function to parse packet identified by packet's type

        '''
        return lambda prot: prot.pkt_type.lower()[2:]

    def send(self, pkt_type, datafields):
        ''' Construct and send a packet to underlying driver.

            :param str pkt_type: packet type identifier
            :param str datafields: string of delimited datafields for packet
        '''
        command = self.protocol.create_packet(
            self.talker_id, pkt_type, datafields
        )
        self.conn.write(command.encode("ascii"))

    def get_power_save(self):
        return self.create_packet("420")

    def version(self):
        return self.create_packet("604")

    def fw_version(self):
        return self.create_packet("704")

    def restart(self, restart_type='hot'):
        restart_types = {
            'hot': "101",
            'warm': "102",
            'cold': "103",
            'full': "104"}
        pkt_type = restart_types[restart_type]
        return self.create_packet(pkt_type)

    def set_power_save(self, mode=0):
        return self.create_packet("320", ","+str(mode))

    def set_antenna_sentence(self, on=True):
        ''' Enable antenna status command: PGCMD,33,1*6C'''
        talker = self.talker_id
        self.talker_id = "PG"
        # print(self.send("CMD", ",33,{}".format(int(on))))
        self.talker_id = talker

    def create_packet(self, talker_id, pkt_type, pkt_data):
        ''' Create a packet based on underlying device protocol.

            :param str talker_id: NMEA talker ID
            :param str pkt_type: NMEA packet type
            :param str pkt_data: NMEA packet data
            :rtype: str
            :returns: complete NMEA packet

        '''
        return self.protocol.create_packet(talker_id, pkt_type, pkt_data)
