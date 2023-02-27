from math import (
    radians,
    degrees,
    sqrt,
    atan2,
    sin,
    cos,
)


def intercept(chs, tgt):
    ''' Plot interception heading correction
    :loc: (Position, Course) Starting location, current course
    :tgt: (Position, Course) Target location, target's course
    '''
    p_chs, v_chs = chs
    p_tgt, v_tgt = tgt

    chs_head = v_chs.heading
    tgt_head = v_tgt.heading

    # From chase to target is tgt - chs
    to_tgt = (p_tgt - p_chs)
    to_tgt_head = to_tgt.heading

    # If target speed is zero, turn to the target
    if v_tgt.mag == 0:
        return chs_head - to_tgt_head

    # we pointed at the target
    if chs_head == to_tgt_head and tgt_head == to_tgt_head:
        # and moving in the correct direction
        return Heading(0)

        # or going exactly the wrong direction
    if (tgt_head - chs_head == Heading(180) and
            to_tgt_head - chs_head == Heading(180)):
        return Heading(180)

    if (tgt_head - chs_head == Heading(0) and
            to_tgt_head - chs_head == Heading(180)):
        return Heading(180)

    if check_region(tgt_head, to_tgt_head, chs_head):
        # If we're in the intercept region, compute the intercept point
        icept = intercept_heading(chs, tgt)
        if icept:
            return icept
        else:
            h = (360 - v_chs.heading.value +
                 (v_tgt + to_tgt).heading.value) % 360
            return Heading(h)
    else:
        # compute turn to middle of chase region
        h = (360 - v_chs.heading.value +
             (v_tgt + to_tgt).heading.value) % 360
        return Heading(h)


def check_region(tgt_head, to_tgt_head, chs_head):
    # import pudb; pudb.set_trace()  # NOQA
    if tgt_head - to_tgt_head > Heading(180):
        # chase region is between the target's heading heading to the target
        lo_bound = tgt_head
        hi_bound = to_tgt_head
    else:
        # chase region is betwen the heading to the target and the target's
        # heading
        lo_bound = to_tgt_head
        hi_bound = tgt_head

    # rotate the boundaries for comparison
    # rot_by = Heading(0) - lo_bound
    # lo_bound = lo_bound + rot_by
    hi_bound = hi_bound - lo_bound
    check_heading = chs_head - lo_bound

    # return check_heading > lo_bound and check_heading < hi_bound
    return check_heading > Heading(0) and check_heading < hi_bound


def intercept_heading(chs, tgt):
    p_chs, v_chs = chs
    p_tgt, v_tgt = tgt

    if (v_tgt.lon != v_chs.lon) and (v_tgt.lat != v_chs.lat):
        t1 = round((p_chs.lon - p_tgt.lon).value/(v_tgt.lon - v_chs.lon)*60)
        t2 = round((p_chs.lat - p_tgt.lat).value/(v_tgt.lat - v_chs.lat)*60)
        if t1 == t2 and t1 > 0:
            intercept = Position(p_chs.lat.value + v_chs.lat * t1/60,
                                 p_chs.lon.value + v_chs.lon * t1/60)
            return (intercept - p_chs).heading
    else:
        return None


class Heading():

    def __init__(self, value, precision=1):
        if value < 0.0 or value >= 360.0:
            msg = "Heading must be between 0 and 360: {}".format(value)
            raise ValueError(msg)
        self.precision = precision
        self.value = round(float(value), precision)

    def __repr__(self):
        return "{}{}".format(self.value, chr(176))

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            raise ValueError("Not an instance of Heading: {}".format(other))

        return round(self.value - float(other.value), self.precision) == 0

    def __lt__(self, other):
        return self.value < float(other.value)

    def __gt__(self, other):
        return self.value > float(other.value)

    def __add__(self, other):
        return Heading((self.value + float(other.value)) % 360)

    def __sub__(self, other):
        val = round(abs(self.value - float(other.value)), self.precision) % 360
        if self.value <= float(other.value) or val == 0.0:
            return Heading(val, precision=self.precision)
        else:
            return Heading(360 - val, precision=self.precision)

    @property
    def rad(self):
        return radians(self.value)

    @property
    def lat(self):
        return cos(radians(self.value))

    @property
    def lon(self):
        return sin(radians(self.value))


class Coordinate():

    def __init__(self, value, *, bounds, precision=6):
        self.precision = precision
        if bounds[0] > bounds[1]:
            msg = "Coordinate boundaries reversed: {}".format(bounds)
            raise ValueError(msg)
        if value < bounds[0] or value > bounds[1]:
            msg = "Value out of bounds {}: {}".format(bounds, value)
            raise ValueError(msg)
        self.value = round(value, precision)
        self.bounds = bounds

    def __repr__(self):
        return "{}".format(self.value)

    def __eq__(self, other):
        return self.value == other.value

    def __add__(self, other):
        raw = float(self.value) + float(other.value)

        if raw > self.bounds[1]:
            val = 2 * self.bounds[1] - raw
        elif raw < self.bounds[0]:
            val = 2 * self.bounds[0] - raw
        else:
            val = raw
        return Coordinate(val, bounds=self.bounds, precision=self.precision)

    def __sub__(self, other):
        raw = float(self.value) - float(other.value)

        if raw < self.bounds[0]:
            val = 2 * self.bounds[0] - raw
        elif raw > self.bounds[1]:
            val = 2 * self.bounds[1] - raw
        else:
            val = raw
        return Coordinate(val, bounds=self.bounds, precision=self.precision)


class Position:

    def __init__(self, lat, lon):
        self.lat = Coordinate(lat, bounds=(-90, 90))
        self.lon = Coordinate(lon, bounds=(-180, 180))

    def __repr__(self):
        return "{}, {}".format(self.lat, self.lon)

    def __eq__(self, other):
        return (self.lat.value == other.lat.value and
                self.lon.value == other.lon.value)

    def __add__(self, other):
        lat = self.lat + other.lat
        lon = self.lon + other.lon
        degs = degrees(atan2(lon.value, lat.value)) % 360
        speed = sqrt(lat.value*lat.value + lon.value*lon.value)
        return Course(Heading(degs), speed)

    def __sub__(self, other):
        lat = self.lat - other.lat
        lon = self.lon - other.lon
        degs = degrees(atan2(lon.value, lat.value)) % 360
        speed = sqrt(lat.value*lat.value + lon.value*lon.value)
        return Course(Heading(degs), speed)

    def __mul__(self, other):
        return self.lat.value*other.lat.value + self.lon.value*other.lon.value

    @property
    def mag(self):
        return sqrt(self.lat.value**2 + self.lon.value**2)

    def travel(self, position):
        diff = position - self
        degs = degrees(atan2(diff.lon, diff.lat))
        if degs > 0:
            return Heading(degs)
        else:
            return Heading(360+degs)

    @property
    def course(self):
        degs = degrees(atan2(self.lon.value, self.lat.value))
        if degs >= 0:
            return Course(Heading(degs), self.mag)
        else:
            return Course(Heading(360 + degs), self.mag)


class Course:
    '''A velocity vector.
    :heading: Heading class
    :speed: non-negative float in deg/h
    '''
    def __init__(self, heading, speed, precision=6):
        if not isinstance(heading, Heading):
            msg = "heading must be an instance of Heading: {}".format(type(heading))
            raise ValueError(msg)
        if speed < 0:
            msg = "speed must be larger than zero: {}".format(speed)
            raise ValueError(msg)
        self.heading = heading
        self.speed = float(speed)
        self.precision = precision

    def __repr__(self):
        return "{}, {} degrees/h".format(self.heading, self.speed)

    def __eq__(self, other):
        return self.heading == other.heading

    def __mul__(self, other):
        return self.lat*other.lat + self.lat*other.lat

    def __sub__(self, other):
        lat = self.lat - other.lat
        lon = self.lon - other.lon
        speed = sqrt(lat*lat + lon*lon)
        return Course(Heading((360 + degrees(atan2(lon, lat))) % 360), speed)

    def __add__(self, other):
        lat = self.lat + other.lat
        lon = self.lon + other.lon
        speed = sqrt(lat*lat + lon*lon)
        return Course(Heading((360 + degrees(atan2(lon, lat))) % 360), speed)

    @property
    def lat(self):
        return round(self.speed * cos(self.heading.rad), self.precision)

    @property
    def lon(self):
        return round(self.speed * sin(self.heading.rad), self.precision)

    @property
    def mag(self):
        return self.speed
