import math
from core import storage
from .hal import b1, b2, b3, b4
from .utils import defaultdict
from .power import (
    shutdown,
    reset_into_ota,
)
from .aprimitives.pushbutton import Pushbutton
from .tracker import (
    Position,
    Heading,
    Course,
    intercept
)


class UIData:

    def __init__(self):
        self.subs = defaultdict(list)  # {'value_name': [{obj, attr)*]}}
        self.data = {}  # {'value_name': value}
        self.messages = []
        self.running = True
        self.shutdown_function = shutdown
        self.sync_word = "001"

    def update(self, data):
        for k, v in data.items():
            self.update_subs(k, v)

    def update_subs(self, item, value):
        subs = self.subs[item]
        if subs:
            for obj, attr in subs:
                setattr(obj, attr, value)

    def register(self, item, obj, attr):
        self.subs[item].append((obj, attr))

    def send(self, message):
        self.messages.append(message)

    def shutdown(self):
        self.running = False
        self.sync_word = "001"

    def sleep(self):
        ''' Sleep calls the shutdown function which has been set via a UI
            element '''
        self.shutdown_function()

    def switch_to_ota(self):
        # can merge this with switch to ota,
        # fires off a task to do the syn/acksyn/ack cmd
        self.running = False
        self.sync_word = "002"
        storage.put("APP", "ota")
        self.shutdown_function = reset_into_ota


class ButtonManager:

    def __init__(self):
        self.pressed = True
        self.mapping = {
            25: lambda: {},
            26: lambda: {},
            27: lambda: {},
            14: lambda: {},
        }
        self.refs = {
            1: 25,
            2: 26,
            3: 27,
            4: 14,
        }
        self.buttons = [
            Pushbutton(b1),
            Pushbutton(b2),
            Pushbutton(b3),
            Pushbutton(b4),
        ]

    def set(self, btn_ref, func):
        self.mapping[self.refs[btn_ref]] = func

    def clear(self, btn=None):
        if not btn:
            for pin in self.mapping:
                self.mapping[pin] = lambda: {}
        else:
            self.mapping[self.refs[btn]] = lambda: {}

    def update(self):
        print("calling update")

        def _handler(btn):
            print("calling handler")
            self.pressed = True
            self.mapping.get(btn, lambda: {})()

        for i, btn in enumerate(self.buttons):
            btn.press_func(_handler, (self.refs[i+1], ))


class Intercept:

    def __init__(self):
        self._my_lat = 99
        self._my_lon = 999
        self._my_cog = 0
        self._my_sog = 0
        self._tg_lat = 99
        self._tg_lon = 999
        self._tg_cog = 0
        self._tg_sog = 0
        self._angle = 0
        self.refresh_trigger = True
        self.thresh = .0001

    def thresh_check(self, val1, val2):
        return abs(val1 - val2) > self.thresh

    @property
    def my_lat(self):
        return self._my_lat

    @my_lat.setter
    def my_lat(self, val):
        if self.thresh_check(val, self._my_lat):
            self.refresh_trigger = True
            self._my_lat = val

    @property
    def my_lon(self):
        return self._my_lon

    @my_lon.setter
    def my_lon(self, val):
        if self.thresh_check(val, self._my_lon):
            self.refresh_trigger = True
            self._my_lon = val

    @property
    def my_cog(self):
        return self._my_cog

    @my_cog.setter
    def my_cog(self, val):
        if self.thresh_check(val, self._my_cog):
            self.refresh_trigger = True
            self._my_cog = val

    @property
    def my_sog(self):
        return self._my_sog

    @my_sog.setter
    def my_sog(self, val):
        if self.thresh_check(val, self._my_sog):
            self.refresh_trigger = True
            self._my_sog = val

    @property
    def tg_lat(self):
        return self._tg_lat

    @tg_lat.setter
    def tg_lat(self, val):
        if self.thresh_check(val, self._tg_lat):
            self.refresh_trigger = True
            self._tg_lat = val

    @property
    def tg_lon(self):
        return self._tg_lon

    @tg_lon.setter
    def tg_lon(self, val):
        if self.thresh_check(val, self._tg_lon):
            self.refresh_trigger = True
            self._tg_lon = val

    @property
    def tg_cog(self):
        return self._tg_cog

    @tg_cog.setter
    def tg_cog(self, val):
        if self.thresh_check(val, self._tg_cog):
            self.refresh_trigger = True
            self._tg_cog = val

    @property
    def tg_sog(self):
        return self._tg_sog

    @tg_sog.setter
    def tg_sog(self, val):
        if self.thresh_check(val, self._tg_sog):
            self.refresh_trigger = True
            self._tg_sog = val

    def update(self, data):
        for item, value in data.items():
            if hasattr(self, item):
                setattr(self, item, value)

    def distance(self):
        earth_radius = 6371
        dlat = math.radians(self.tg_lat - self.my_lat)
        dlon = math.radians(self.tg_lon - self.my_lon)
        a = (math.sin(dlat/2) * math.sin(dlat/2) +
             math.sin(dlon/2) * math.sin(dlon/2) *
             math.cos(math.radians(self.tg_lat)) *
             math.cos(math.radians(self.my_lat)))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return earth_radius * c

    def angle(self):
        my_pos = Position(self.my_lat, self.my_lon)
        my_course = Course(Heading(min(self.my_cog, 359.9)), self.my_sog)
        tg_pos = Position(self.tg_lat, self.tg_lon)
        tg_course = Course(Heading(min(self.tg_cog, 359.9)), self.tg_sog)
        h = intercept((my_pos, my_course), (tg_pos, tg_course))
        self._angle = h.value
        return h.value

    def locked(self):
        if all([self.my_lat != 99,
               self.my_lon != 999,
               self.tg_lat != 99,
               self.tg_lon != 999]):
            return True
        else:
            return False

    def get(self):
        rt = self.refresh_trigger
        self.refresh_trigger = False
        if not self.locked():
            return {"locked": False,
                    'refresh': rt}
        else:
            self.angle()
            turn = int(self.my_cog + self._angle) % 360
            return {'angle': self._angle,
                    'dist': self.distance(),
                    'turn': turn,
                    'locked': True,
                    'refresh': rt}


ui_data = UIData()


class FlashMessage:

    def __init__(self):
        self.frames = 0
        self.msg = ""
        self.reset = False

    def __call__(self, msg, frames=3):
        self.msg = msg
        self.frames += frames + 1
        # ui_data.update({'flash': self.msg})

    def update(self):
        if self.frames > 0:
            ui_data.update({'flash': self.msg})
            self.frames -= 1

        if self.frames == 1 and not self.reset:
            self.reset = True
            self.frames += 3
            self.msg = ""

        if self.reset and self.frames <= 0:
            self.reset = False
        print("fms: {} - rst: {}".format(self.frames, self.reset))


bm = ButtonManager()
flasher = FlashMessage()
