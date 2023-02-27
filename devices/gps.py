from core.compat import time
from devices.mtk_nmea import MTKTalker


class GPS(MTKTalker):
    ''' The GPS driver is the top level driver of a GPS device, which
        produces and parses NMEA sentences.

        The connection and parsing details are managed by the parent class.

        The last reported signal, course, and location data are persisted
        on a GPS instance so they are available while the underlying stream is
        cleared and new sentences are parsed repeatedly.

        When the device is started, these dictionaries are cleared.

        :ivar int last_sat_time: Time of last satellite signal
        :ivar dict signal_data: last known signal data reported from gps device
        :ivar dict location_data: last known location data reported from
            gps device
        :ivar dict course_data: last known course data reported from gps device
        :ivar int last_fix_time:  Time of last GPS fix
        :ivar bool passthrough: Outputs raw NMEA sentences as seen from device
        :ivar bool wait_for_firstfix: Indicates if device has received it's
            first GPS fix since start
        :ivar clock clock: object with time method to retrieve system time
    '''
    #: Keys for picking location data from parsed NMEA sentences
    location_attrs = ("NS", "EW", "latitude", "longitude", "utc")
    #: Keys for picking signal data from parsed NMEA sentences
    signal_attrs = ("fix", "fix_mode1", "fix_mode2", "num_sv")
    #: Keys for picking course data from parsed NMEA sentences
    course_atts = ('t_course', 'ground_speed')

    def __init__(self, clock=time):
        self.clock = clock
        super().__init__()
        self.last_sat_time = 0
        self.signal_data = {}
        self.location_data = {}
        self.course_data = {}
        self.last_fix_time = None
        self.waypoints = []
        self.passthrough = False
        self.wait_for_firstfix = True

    def connect(self, devices):
        """ Sets up the hardware connections as the enable pin for the device
            and passess the connection to the parent class
            :param dict devices: dict with external devices
        """
        self.en = devices['en']
        super().connect(devices['conn'])

    def any(self):
        """ Returns length of data pending in the connection's buffer.
            :rtype: int
            :return: length of data in receive buffer
        """
        return self.conn.any()

    def start(self):
        """ Start the GPS hardware.
        Initializes the following state:

            .. table::

                =================  =====
                Instance variable  value
                =================  =====
                wait_for_firstfix  True
                start_time         self.clock.time()
                signal_data        {}
                location_data      {}
                last_sat_time      self.clock.time()
                =================  =====
        """

        self.wait_for_firstfix = True
        self.start_time = self.clock.time()
        if not self.en():
            self.en.on()
        self.conn.write(b"A\r\n")
        self.signal_data.clear()
        self.location_data.clear()
        self.last_sat_time = self.clock.time()

    def stop(self):
        """ Turn off the GPS unit, and clear incomplete unhandled device
            responses.
        """
        self.en.off()
        # flush the stream
        if self.stream:
            self.stream.clear()
        # flush the connection
        if self.conn:
            while self.conn.any():
                _ = self.conn.read()

    def update(self):
        ''' Inspect the underlying stream state and sift data into location,
            signal, and course.
            Check if the data was all read.  If not, the read is bad,
            and ignore it.
            If it's all non-null, it's good, update timestamp and location
        '''
        new_location_data = {
            k: self.stream.data.get(k)
            for k in self.location_attrs}

        for k in self.course_atts:
            self.course_data[k] = self.stream.data.get(k)

        for k in self.signal_attrs:
            val = self.stream.data.get(k)
            if val:
                self.signal_data[k] = val
                if k == "fix" and val != "0":
                    self.wait_for_firstfix = False
                    self.last_sat_time = self.clock.time()
                if k == "fix_mode2" and val != "1":
                    # self.wait_for_firstfix = False
                    self.last_sat_time = self.clock.time()

        self.stream.data.clear()
        if all(new_location_data.values()):
            self.location_data.update(new_location_data)
            utc = new_location_data['utc']
            self.last_fix_time = utc

    def run(self):
        ''' Read the underlying data stream, process it, and handle the
            passthrough of NMEA sentences to std out.
            Update data from the processed stream data
        '''
        self.stream.read()

        while self.stream.more:
            self.stream.consume()

            if self.passthrough:
                print(self.stream.terminated)

            self.update()

    def import_waypoint(self, wp_data):
        """ Add, modify, or delete waypoint data.

            Waypoint data wp_data is a dict

            ======  ================  ==========================
            key     value             description
            ======  ================  ==========================
            'cmd'   'A', 'D', 'M'     Add, Delete, Modify
            'name'  'waypoint label'  label to refer to waypoint
            'lat'   'DDMM.ssss'       latitude in NMEA format
            'lon'   'DDMM.ssss'       longitude in NMEA format
            'NS'    'N', 'S'          North/South indicator
            'EW'    'E', 'W'          East/West indicator
            ======  ================  ==========================

            :param dict wp_data: waypoint data
        """
        cmd = wp_data.pop('cmd')
        if cmd == "D":
            return self.del_waypoint(wp_data['name'])

        for idx, point in enumerate(self.waypoints):
            if point['name'] == wp_data['name']:
                if cmd == 'A':
                    return False
                if cmd == 'M':
                    self.waypoints[idx] = wp_data
                    return True
        self.waypoints.append(wp_data)
        return True

    def del_waypoint(self, wp_name):
        ''' Delete waypoint by name.
            :param str wp_name: name of waypoint to delete
        '''
        for point in self.waypoints:
            if wp_name == point['name']:
                self.waypoints.remove(point)
                return True
        return False

    def route(self):
        ''' Turn waypoints into RTE and WPL messages
            :rtype: list
            :return: list of messages corresponding to route and waypoints
        '''
        if len(self.waypoints) < 1:
            return False
        wp = self.waypoints[0]
        wp_data = "{},{},{},{},{}".format(
            wp['lat'], wp['NS'], wp['lon'], wp['EW'], wp['name'])

        rte_sen = self.create_packet("GP", "RTE", "2,1,c,0," + wp['name'])
        wp_sen = self.create_packet("GP", "WPL", wp_data)
        return [rte_sen, wp_sen]
