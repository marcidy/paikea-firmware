from core import (
    support,
    storage,
)
from core.utils import ActivityTimer
from core.compat import machine
import os


class PaikeaActivitiesMixin:

    @staticmethod
    def _loc_msg(data):
        lat = data['latitude']
        long = data['longitude']
        NS = data['NS']
        EW = data['EW']
        utc = data['utc']
        cog = data['t_course']
        sog = data['ground_speed']
        msg = "lat:{},NS:{},lon:{},EW:{},utc:{}".format(lat, NS, long, EW, utc)
        if not sog:
            sog = 0
        if not cog:
            cog = 0
        msg += ",sog:{},cog:{}".format(sog, cog)
        msg = "PK001;" + msg
        return msg

    def idle(self):
        if self.timers['loc_send'].expired:
            self.activity = self.gps_init
            return

        if not self.beacon:
            sleep_time = int(self.timers['loc_send'].wait_time)

            if sleep_time > 0:
                print("sleep: {}s".format(sleep_time))
                self.sleep(sleep_time)

    def gps_init(self):
        gps = self.devices.get('gps')
        if gps and not self.beacon:
            gps.location_data.clear()
            gps.signal_data.clear()
            gps.course_data.clear()
            gps.start()
        self.timers['sat_view'].reset()
        self.activity = self.run_gps

    def run_gps(self):
        gps = self.devices.get('gps')

        if not gps:
            self.activity = self.idle
            return

        gps.run()

        if gps.signal_data and gps.location_data and gps.course_data:
            self.signal_data.update(**gps.signal_data)
            self.location_data.update(**gps.location_data)
            self.course_data.update(**gps.course_data)

            if not self.beacon:
                gps.stop()
            self.activity = self.send_update

        self.check_satellite_view()

        # if no fix after 15 mins, give up, gps issue
        if not self.beacon:
            if self.clock.time() - gps.start_time > 15*60:
                gps.stop()
                self.timers['loc_send'].reset()
                self.activity = self.idle

    def send_update(self):
        gps = self.devices.get('gps')

        msg = ""
        if gps:
            msg_data = {}
            msg_data.update(**self.location_data)
            msg_data.update(**self.course_data)
            msg += self._loc_msg(msg_data)
            self.timers['loc_send'].reset()

        # FIXME: use a function to get the actual status
        if msg:
            status = 0
            status |= int(self.beacon)  # bit 0, should formalize this a bit
            msg +=",sta:{:02X}".format(status)

        batt_mon = self.devices.get('batt_mon')
        if batt_mon:
            try:
                batt_mon.check()
                msg += ",batt:{}".format(batt_mon.main_v)
            except Exception:
                pass

        if msg:
            self.messages.append(msg)
            self.activity = self.send_message
        else:
            self.activity = self.idle

    def send_message(self):
        rb = self.devices.get('rb')
        rb.start()
        rb.run()
        self.check_iridium()
        self.clock.sleep(30)
        rb.run()
        self.check_iridium()
        rb.atcmd("+CIER?", False)
        if len(self.messages) > 0:
            msg = self.messages.pop(0)
            rb.send_message(msg)
        self.activity = self.run_rb

    def run_rb(self):
        rb = self.devices.get('rb')

        if rb.wait:
            rb.run()
            self.check_iridium()

        else:
            self.activity = self.stop_rb

        self.check_satellite_view()

    def stop_rb(self):
        rb = self.devices.get('rb')
        rb.stop()
        self.activity = self.idle

    def lost_satellite(self):
        print("lost satellite")
        self.activity = self.idle

        # maximum sleep 15 mins
        # minimum sleep 1 min
        sleep_time = max(min(int(self.timers['loc_send'].wait_time), 900), 60)

        if sleep_time > 0:
            self.sleep(sleep_time)

        self.timers['sat_view'].reset()

    def send_beacon(self):
        lora = self.devices.get('lora')
        gps = self.devices.get('gps')

        if not lora or not gps:
            return

        if not gps.en():
            gps.start()

        gps.run()

        if not gps.wait_for_firstfix:
            lat = gps.location_data.get('latitude')
            lon = gps.location_data.get('longitude')
            ns = gps.location_data.get('NS')
            ew = gps.location_data.get('EW')
            sog = gps.course_data.get('ground_speed')
            cog = gps.course_data.get('t_course')
            utc = gps.location_data.get('utc')

            if not sog:
                sog = 0
            if not cog:
                cog = 0

            data_fields = "{},{},{},{},{},{},{}".format(
                lat, ns, lon, ew, sog, cog, utc)

            # FIXME: use a function to get the actual status
            status = 0
            status |= int(self.beacon)  # bit 0, should formalize this a bit
            data_fields += ",{:02}".format(status)

            pkt = gps.protocol.create_packet("PK", "004", data_fields)
            lora.messages.append(pkt)


class Paikea(PaikeaActivitiesMixin):

    def __init__(self, clock=None):
        if clock is None:
            import time
            self.clock = time
        else:
            self.clock = clock
        self.devices = {}
        self.timers = {}
        self.data = {}
        self.init_timers()
        self._activity = self.idle
        self.messages = []
        self.beacon = False
        self.location_data = {}
        self.signal_data = {}
        self.course_data = {}
        self.sleep_mode = storage.get("SLEEPMODE")

    def connect(self, devices):
        self.devices.update(devices)

    @property
    def activity(self):
        return self._activity

    @activity.setter
    def activity(self, value):
        if self._activity != value:
            new_a, old_a = None, None

            if hasattr(self._activity, "__name__"):
                old_a = self._activity.__name__
            if hasattr(value, "__name__"):
                new_a = value.__name__

            print("{} -> {}".format(old_a, new_a))

        self._activity = value

    def init_timers(self):
        loc_send = int(storage.get('LOC_SEND'))
        sat_view = int(storage.get('SAT_VIEW'))
        timers = [
            ActivityTimer("sat_view", self.clock, sat_view,
                          activity=self.lost_satellite),
            ActivityTimer("loc_send", self.clock, loc_send,
                          activity=self.send_update),
        ]

        for timer in timers:
            self.timers[timer.name] = timer

    def start(self):
        self.timers['loc_send'].start()

    def sleep(self, sleep_time):
        rb = self.devices.get('rb')
        if rb:
            rb.stop()

        lora = self.devices.get('lora')
        if lora:
            lora.stop()

        gps = self.devices.get('gps')
        if gps:
            gps.stop()

        # sleepmode = storage.get("SLEEPMODE") # don't read before sleep.
        if self.sleep_mode == "LIGHT":
            machine.lightsleep(sleep_time*1000)
        elif self.sleep_mode == "DEEP":
            os.umount("/")  # guard against fs corruption on boot
            self.clock.sleep(1)
            machine.deepsleep(int(sleep_time*1000))

    def update_marker(self, timer_name, value):
        if timer_name in self.timers:
            self.timers[timer_name].marker = value

    def update_delay(self, timer_name, value):
        if timer_name in self.timers:
            self.timers[timer_name].delay = value
            self.timers[timer_name].reset()

    def check_satellite_view(self):
        timer = self.timers['sat_view']
        if not timer.running:
            timer.reset()
            timer.start()

        rb = self.devices.get('rb')
        gps = self.devices.get('gps')

        if not rb and not gps:
            return False

        sat_time = 0
        if gps:
            sat_time = max(sat_time, gps.last_sat_time)
        if rb:
            sat_time = max(sat_time, rb.last_sat_time)

        if sat_time == 0:
            return False
        else:
            self.update_marker('sat_view', sat_time)
            return True

        if timer.expired:
            timer.stop()
            self.activity = self.lost_satellite

    def check_iridium(self):
        rb = self.devices.get('rb')
        new_data = None
        if rb:
            if rb.new_data:
                new_data = rb.data.pop('pkea', None)
                rb.new_data = False
        if new_data:
            self.process_iridium_data(new_data)

    def process_iridium_data(self, new_data):
        for item, value in new_data.items():

            if item == "PK005":
                if value == "1":
                    self.beacon = True
                else:
                    self.beacon = False
                    if "beacon" in self.timers:
                        del self.timers['beacon']

            if item == "PK006":
                delay = max(int(value)*60, 120)
                self.timers['loc_send'].delay = delay
                storage.put('LOC_SEND', "{}".format(delay))

            elif item == "PK007":
                try:
                    sleep_time = int(value)
                except Exception:
                    return

                if sleep_time <= 0:
                    return

                self.sleep(sleep_time)

            elif item == "SUPPORT":
                print("*** SUPPORT REQUESTED ***")
                if not support.switch_to_support():
                    print("Switching failed for some reason!")

    def reset_rb(self, rb):
        rb.bad_session = False
        rb.stop()
        self.clock.sleep(.3)

    def assert_rb_state(self):
        rb = self.devices.get('rb')

        if not rb:
            return

        if rb.bad_session:
            self.reset_rb(rb)
            self.activity = self.send_update

        if not rb.wait_for_status and (not rb.mo_flag and rb.wait_for_send):
            self.reset_rb(rb)
            rb.start()
            rb.wait_for_send = False
            self.activity = self.send_update

        if rb.wait_for_recv and not rb.session:
            rb.create_sbd_session()

        if rb.wait_for_data and not rb.mt_flag:
            rb.wait_for_data = False

        if self.activity == self.idle and rb.wait:
            if not rb.en():
                rb.start()
            self.activity = self.run_rb

    def run(self):
        for _, timer in self.timers.items():
            timer.wait

        if not self.activity:
            self.activity = self.idle

        self.activity()

        self.assert_rb_state()

        lora = self.devices.get('lora')

        if self.beacon:
            if not lora.enabled:
                lora.start()
            if not self.devices['gps'].en():
                self.devices['gps'].start()
            if "beacon" not in self.timers:
                self.timers["beacon"] = ActivityTimer("beacon", self.clock, 7)
                self.timers["beacon"].start()
            if self.timers["beacon"].expired:
                self.send_beacon()
                self.timers["beacon"].reset()
        lora.run()
