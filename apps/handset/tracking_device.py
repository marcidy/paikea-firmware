import binascii
from devices.serialprotocols import (
    ProtocolSpec,
    SimpleSerialProtocol,
)
from apps.handset.tracker import (
    Position,
    Heading,
    Course,
)
from core import storage
from core.compat import reset
from core.utils import ActivityTimer
from devices.power import shutdown


def degdm(val):
    x, y = val.split('.')
    b = x[-2:]
    a = x[:-2]
    degs = int(a)
    dcms = float(b + "." + y)/60
    if degs >= 0:
        return degs + dcms
    if degs < 0:
        return degs - dcms


class TrackingDevice:

    # This is a bad approximation
    # FIXME: turn this into a property which takes position (lonfitude
    # specifically) into account
    km2deg = 111.112

    def __init__(self):
        self.my_location_msg = ""
        self.my_location = Position(0, 0)
        self.my_course = Course(Heading(0), 0)
        self.last_target_update = 0
        self.buoy_location = None
        self.buoy_course = None
        self.buoy_commands = []
        self.gps = None
        self.lora = None
        self.screen = None
        self.updated = False
        self.protocol = SimpleSerialProtocol(spec=ProtocolSpec())
        self.mode = None
        self.pkts = 0
        self.timers = {}
        self.clock = None
        self.utc = 0
        self._lora_csq = 0
        self.last_lora_sig = 0
        self.target_src = "N"
        self.target_sta = 42
        self.rb_load = False

    def connect(self, devices):
        self.gps = devices.get('gps')
        self.lora = devices.get('lora')
        # self.screen = devices.get('screen')
        self.rb = devices.get('rb')
        self.clock = devices.get('clock')
        self.display_port = devices.get('display_port')
        self.batt = devices.get('batt')

        if self.gps:
            self.gps.start()

        if self.rb:
            self.rb.start()
            self.timers['loc_send'] = ActivityTimer('loc_send',
                                                    self.clock,
                                                    600)
            self.timers['loc_send'].start()
            self.rb.atcmd("+CIER=1,1,1", False)
            self.clock.sleep(.05)
            self.rb.atcmd("+SBDAREG=1", False)
            self.clock.sleep(.05)
            self.rb.atcmd("+SBDMTA=1", False)
            self.clock.sleep(.05)
            self.rb.create_sbd_session()

        if self.display_port:
            self.timers['display_run'] = ActivityTimer('display_run',
                                                   self.clock,
                                                   2)
            self.timers['display_run'].start()
            self.timers['update_status'] = ActivityTimer('update_status',
                                                         self.clock,
                                                         30)
            self.timers['update_status'].start()

    def set_mode(self, mode):
        if mode in ['t', 'r', 'x']:
            self.mode = mode

    def update_my_location(self):
        ns = self.gps.location_data['NS']
        ew = self.gps.location_data['EW']
        lat = self.gps.location_data['latitude']
        lon = self.gps.location_data['longitude']
        cog = self.gps.course_data['t_course']
        sog = self.gps.course_data['ground_speed']
        utc = self.gps.location_data['utc']

        if utc:
            try:
                self.utc = float(utc)
            except Exception:
                print("bad UTC to float")

        if cog and sog:
            try:
                self.my_course = Course(
                    Heading(float(cog)),
                    float(sog)/self.km2deg)
                self.updated = True
            except Exception as e:
                print("update_my_location A: {}".format(e))

        if ns and ew and lat and lon:
            try:
                if ns == "N":
                    lat = degdm(lat)
                else:
                    lat = -degdm(lat)

                if ew == "E":
                    lon = degdm(lon)
                else:
                    lon = -degdm(lon)

                self.my_location = Position(lat, lon)
                self.updated = True

            except Exception as e:
                print("{}, {}, {}".format(lat, lon, self.my_location))
                print("update_my_location b: {}".format(e))

    def send_my_location(self):
        data_fields = "{},{},{},{}".format(
            self.my_location.lat.value,
            self.my_location.lon.value,
            self.my_course.heading.value,
            self.my_course.speed)

        pkt = self.protocol.create_packet("PKEA", "003", data_fields)
        self.lora.messages.append(pkt)

    def set_target_location(self, lat, ns, lon, ew, sog, cog, utc, src):
        f_utc = 0
        try:
            f_utc = float(utc)
        except Exception:
            print("Bad utc float conversion")
            return

        new_update = self.utc - f_utc
        last_update = self.utc - self.last_target_update

        if new_update < 0 and last_update < 0:
            if new_update < last_update:
                return
        elif new_update < 0 and last_update > 0:
            return
        elif new_update > 0 and last_update > 0:
            if new_update > last_update:
                return

        if ew == "E":
            lon = degdm(lon)
        else:
            lon = -degdm(lon)
        if ns == "N":
            lat = degdm(lat)
        else:
            lat = -degdm(lat)

        self.buoy_location = Position(lat, lon)
        self.buoy_course = Course(Heading(float(cog)),
                                  float(sog)/self.km2deg)
        self.last_target_update = f_utc
        self.target_src = src
        self.updated = True

    @property
    def lora_csq(self):
        if self.clock.time() - self.last_lora_sig > 180:
            self._lora_csq = 0
        return self._lora_csq

    @lora_csq.setter
    def lora_csq(self, rssi):
        self.last_lora_sig = self.clock.time()

        if rssi <= -140:
            self._lora_csq = 0
        elif rssi > -140 and rssi <= -130:
            self._lora_csq = 1
        elif rssi > -130 and rssi <= -120:
            self._lora_csq = 2
        elif rssi > -120 and rssi <= -110:
            self._lora_csq = 3
        elif rssi > -110 and rssi <= -70:
            self._lora_csq = 4
        elif rssi > -70:
            self._lora_csq = 5

    def read_lora(self):

        while self.lora.packets:
            self.pkts += 1
            self.updated = True
            data = self.lora.packets.pop(0)
            rssi = self.lora.txr.packetRssi()
            self.lora_csq = rssi
            print("lora rssi: {}".format(rssi))

            try:
                self.protocol(data)
            except Exception as e:
                print("read lora A: {}".format(e))
                return

            if self.protocol.valid and self.protocol.pkt_type == "PK004":
                data_fields = self.protocol.datafields
                try:
                    lat, ns, lon, ew, sog, cog, utc, sta = data_fields.split(",")
                    self.set_target_location(lat, ns, lon,
                                             ew, sog, cog,
                                             utc, 'L')
                    self.target_sta = binascii.unhexlify(sta)[0]
                except Exception as e:
                    print(e)
                    print("read_lora error: {}".format(data_fields))

            print("trk_log {}: ".format(self.clock.time()), end="")
            print(self.protocol.sentence)

    def read_iridium(self):
        if not self.rb:
            return
        if self.rb.new_data:
            new_data = self.rb.data.pop('pkea', None)
            self.rb.new_data = False

            for item, values in new_data.items():
                if item == "PK004":
                    try:
                        lat, ns, lon, ew, sog, cog, utc, sta = values.split(",")
                        self.set_target_location(lat, ns, lon,
                                                 ew, sog, cog,
                                                 utc, 'R')
                        self.target_sta = int(sta)
                    except Exception as e:
                        print(e)
                        print("ird_read error: {}".format(new_data))

    def utc_to_hms(self, utc):
        s_utc = "{:06}".format(int(utc))
        hh = s_utc[0:2]
        mm = s_utc[2:4]
        ss = s_utc[4:6]
        return "{}:{}:{}".format(hh, mm, ss)

    def get_updated_data(self):
        if self.my_location and self.my_course:
            my_loc = "MY:{},{},{},{},{};".format(
                self.my_location.lat,
                self.my_location.lon,
                self.my_course.heading.value,
                self.my_course.speed * self.km2deg,
                self.utc_to_hms(self.utc),
            )
        else:
            # my_loc = "MY:99,999,0,0,00:00:00;"
            my_loc = ""
        if self.buoy_location and self.buoy_course:
            tg_loc = "TG:{},{},{},{},{},{};".format(
                self.buoy_location.lat,
                self.buoy_location.lon,
                self.buoy_course.heading.value,
                self.buoy_course.speed * self.km2deg,
                self.utc_to_hms(self.last_target_update),
                self.target_src
            )
        else:
            # tg_loc = "TG:99,999,0,0,00:00:00,N;"
            tg_loc = ""
        return my_loc + tg_loc

    def location_msg(self, data):
        lat = data['latitude']
        lon = data['longitude']
        NS = data['NS']
        EW = data['EW']
        utc = data['utc']
        sog = data['ground_speed']
        if not sog:
            sog = 0
        cog = data['t_course']
        if not cog:
            cog = 0
        msg = "lat:{},NS:{},lon:{},EW:{},utc:{}".format(lat, NS, lon, EW, utc)
        msg += ",sog:{},cog:{}".format(sog, cog)
        msg = "PK001;" + msg
        return msg

    def send_location(self):
        if not self.gps or not self.rb:
            return

        if self.gps.wait_for_firstfix:
            return

        location_data = {}
        location_data.update(**self.gps.location_data)
        location_data.update(**self.gps.course_data)
        location_data.update(**self.gps.signal_data)
        msg = self.location_msg(location_data)
        self.timers['loc_send'].reset()  # init timer, yah
        self.my_location_msg = msg

    def status_msg(self):
        tg_sta = self.target_sta
        to_send = (
            len(self.rb.messages) +
            len(self.buoy_commands) +
            int(self.rb.mo_flag))
        to_rec = int(self.rb.queue)
        try:
            self.batt.check()
            voltage = batt.main_v
        except Exception:
            voltage = 0
        return "ST:{},{},{},{};".format(
            to_send,
            to_rec,
            tg_sta,
            self.batt.main_v).encode('ascii')

    def send_iridium(self):
        if not self.rb.wait_for_send and not self.rb.messages:
            if self.buoy_commands:
                self.rb.messages.append(self.buoy_commands.pop(0))
            elif self.my_location_msg:
                self.rb.messages.append(self.my_location_msg)
                self.my_location_msg = ""

    def sync(self, sync_word):
        print("Syncing on {}".format(sync_word))
        cmd = "CMD;{}".format(sync_word).encode('utf-8')
        acksyn = "{}:ACKSYN".format(sync_word).encode('utf-8')
        endsyn = "{}:SYN".format(sync_word).encode('utf-8')

        self.display_port.messages.append(acksyn)
        # run display port
        # get {}:SYN message, finish
        self.display_port.run()
        cmd_seen = False

        while True:
            while self.display_port.packets:
                pkt = self.display_port.packets.pop(0).strip(b'\r\n')
                print("   ** SYNC: {}".format(pkt))
                if pkt == endsyn:
                    return
                if pkt == cmd:
                    cmd_seen = True

            if cmd_seen:
                self.display_port.messages.append(acksyn)
                cmd_seen = False

            self.display_port.run()

    def run(self):
        self.gps.run()
        self.rb.run()

        self.read_iridium()

        if not self.gps.wait_for_firstfix:
            try:
                self.update_my_location()
            except Exception as e:
                print("run: {}".format(e))

        if self.mode in ['x', 't']:
            self.send_my_location()

        if self.mode in ['t', 'x', 'r']:
            self.lora.run()

        if self.mode in ['x', 'r']:
            self.read_lora()

        if self.updated:
            if self.display_port:
                self.display_port.loc_data = self.get_updated_data().encode('ascii')
            self.updated = False

        if self.display_port:
            if self.timers['update_status'].expired:
                self.display_port.messages.append(self.status_msg())
                self.timers['update_status'].reset()

            if self.timers['display_run'].expired:
                self.display_port.run()
                self.timers['display_run'].reset()

            while self.display_port.packets:
                pkt = self.display_port.packets.pop(0).strip(b"\r\n")

                try:
                    pkt = pkt.decode('ascii')
                except UnicodeError:
                    print("bad packet: {}".format(pkt))
                    continue

                if pkt[0:2] == "PK":
                    # put into command queue, not right into rockblock
                    # message queue
                    self.buoy_commands.append(pkt)
                elif pkt == "CMD;001":
                    self.sync("001")
                    shutdown()
                elif pkt == "CMD;002":
                    storage.put("APP", "ota")
                    self.sync("002")
                    reset()

        if self.timers['loc_send'].expired:
            self.send_location()

        self.send_iridium()
