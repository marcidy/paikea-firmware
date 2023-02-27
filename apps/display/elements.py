import math
from .utils import defaultdict
from .font.printer import put
from .paikea_protocol import convert_dd


class Element:

    def __init__(self, offset, length=0, width=0, border=True):
        self.offset = offset
        self.length = length
        self.width = width
        self.bbox = None
        self.children = []
        self.inverted = False
        self.border = border
        self.outline = 0 if self.border else 1
        self.body = 1

    def invert(self):
        self.inverted = True
        self.outline = 1 if self.border else 0
        self.body = 0
        for child in self.children:
            child.invert()

    def normal(self):
        self.inverted = False
        self.outline = 0 if self.border else 1
        self.body = 1
        for child in self.children:
            child.normal()

    def draw(self, pen, offset=(0, 0)):
        x_offset = self.offset[0] + offset[0]
        y_offset = self.offset[1] + offset[1]
        pen.fill_rect(x_offset, y_offset, self.length, self.width, self.body)
        if self.border:
            pen.rect(x_offset, y_offset, self.length, self.width, self.outline)

        for child in self.children:
            child.draw(pen, (x_offset, y_offset))


class Selectable(Element):

    def __init__(self, offset, length=0, width=0):
        self.callback = None
        super().__init__(offset, length, width)

    def set_callback(self, callback):
        self.callback = callback

    def on_select(self):
        if self.callback:
            self.callback()


class Text(Element):

    def __init__(self, offset, text, font=None, border=True):
        self.offset = offset
        self.text = text
        self._value = 0
        if not font:
            from .font import main_13r
            self.font = main_13r
        else:
            self.font = font
        super().__init__(offset, border=border)

    def _format(self, value):
        if hasattr(self, "format"):
            return self.format(value)
        else:
            return "{}".format(value)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.text = self._format(value)
        self._value = value

    def draw(self, pen, offset=(0, 0)):
        x_offset = self.offset[0] + offset[0]
        y_offset = self.offset[1] + offset[1]
        put(pen, self.text, x_offset, y_offset, self.font, self.outline)


class GPSCoord(Text):

    def format(self, value):
        if not isinstance(value, str):
            value = "{}".format(value)
        dms = convert_dd(value)
        deg = dms['deg']
        min = dms['min']
        sec = round(dms['sec'], 4)
        return ("{: 4}".format(deg) + " {:02}\" {:02}".format(min, sec))


class Heading(Text):

    def format(self, value):
        return "{} ".format(round(value, 1))


class Speed(Text):

    def format(self, value):
        return "{}".format(int(value)) + " kph"


class Distance(Text):

    def format(self, value):
        if value < 1.2:
            value = round(value * 1000, 0)
            return "{} m".format(round(value, 1))

        return "{} km".format(round(value, 1))


class DistanceUnits(Text):

    def format(self, value):
        if value < 1.2:
            return 'm'
        else:
            return 'km'


class LastMileIndicator(Text):

    def format(self, value):
        if value == 42:
            return "N/A"
        elif (value & 1) == 0:
            return 'Off'
        else:
            return 'On'


class Display(Element):

    def __init__(self, offset, length, width, border=False):
        self.selectables = None
        self.selected = 0
        super().__init__(offset, length, width, border)
        self.subscriptions = defaultdict(list)

    def set_data(self, new_data):
        for item, value in new_data.items():
            for sub in self.subscriptions[item]:
                setattr(sub, item, value)

    def init_selected(self):
        if self.selectables:
            for item in self.selectables:
                item.normal()
            self.selectables[self.selected].invert()

    def down(self):
        self.selectables[self.selected].normal()
        self.selected = max(0, min((self.selected + 1),
                                   len(self.selectables) - 1))
        self.selectables[self.selected].invert()

    def up(self):
        self.selectables[self.selected].normal()
        self.selected = max(0, min((self.selected - 1),
                                   len(self.selectables) - 1))
        self.selectables[self.selected].invert()

    def select(self):
        self.selectables[self.selected].on_select()


class Arrow(Element):

    def __init__(self, offset, length, width, border=True):
        self._last_angle = 0
        dom_dim = min(length, width)
        self.r2 = int(math.sqrt(2 * dom_dim*dom_dim)/3)
        self.r1 = int(self.r2/4)
        self._last_pts = None
        self._angle = -90
        self.locked = False
        super().__init__(offset, length, width, border=border)

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._last_angle = self._angle
        self._angle = value - 90

    def intercept(self, e1, e2, y):
        x1, y1 = e1
        x2, y2 = e2

        dx = x2 - x1
        dy = y2 - y1

        if not (y <= max(y2, y1) and y >= min(y2, y1)):
            return

        if dx == 0:
            return x1

        if dy == 0:
            return min(x1, x2)

        x = int(round((y - y1) * dx/dy + x1, 0))
        return x

    def draw_outline(self, pen, points, color=0):
        pt1, pt2, pt3 = points
        pen.line(pt1[0], pt1[1], pt2[0], pt2[1], color)
        pen.line(pt2[0], pt2[1], pt3[0], pt3[1], color)
        pen.line(pt1[0], pt1[1], pt3[0], pt3[1], color)

    def fill(self, pen, points, color=0):
        x1, y1 = points[0]
        x2, y2 = points[1]
        x3, y3 = points[2]

        y_min = min(y1, y2, y3)
        y_max = max(y1, y2, y3)

        for y in range(y_min, y_max + 1):

            icepts = []
            for i, p in enumerate(points):
                inter = self.intercept(points[i], points[(i+1) % 3], y)
                if inter is not None:
                    icepts.append(inter)

            if not icepts:
                return
            pen.line(min(icepts), y, max(icepts), y, color)

    def drawarrow(self, pen, offset=(0, 0)):

        if self._last_pts:
            self.draw_outline(pen, self._last_pts, 1)
            self.fill(pen, self._last_pts, 1)

        cx = self.offset[0] + offset[0] + self.width/2
        cy = self.offset[1] + offset[1] + self.length/2
        pt1 = (
            int(cx + self.r2 * math.cos(math.radians(self._angle))),
            int(cy + self.r2 * math.sin(math.radians(self._angle)))
        )
        pt2 = (
            int(cx + self.r1 * math.cos(math.radians(self._angle - 90))),
            int(cy + self.r1 * math.sin(math.radians(self._angle - 90)))
        )
        pt3 = (
            int(cx + self.r1 * math.cos(math.radians(self._angle + 90))),
            int(cy + self.r1 * math.sin(math.radians(self._angle + 90)))
        )
        self._last_pts = (pt1, pt2, pt3)

        self.draw_outline(pen, self._last_pts, 0)
        self.fill(pen, self._last_pts, 0)

    def draw(self, pen, offset=(0, 0)):
        if self.locked:
            self.drawarrow(pen, offset)
        else:
            x_offset = self.offset[0] + offset[0]
            y_offset = self.offset[1] + offset[1] + 30
            pen.text("Waiting for", x_offset, y_offset, 0)
            pen.text(" location  ", x_offset, y_offset+8, 0)

        for child in self.children:
            child.draw(pen, (offset[0], offset[1]))
