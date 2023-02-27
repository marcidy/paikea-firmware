import uasyncio
import framebuf
from core import storage
from . import epaper
from .hal import uart
from .controllers import (
    Intercept,
    bm,
    ui_data,
    flasher,
)
from .configure import (
    configure_messages,
    configure_main,
    configure_flash,
    configure_power,
    configure_data,
)
from .esp_parser import (
    parse_esp_data,
    comm_port,
)


class Updater:

    def __init__(self):
        self.dirty = True
        self.active_item = 0
        self.bm = None
        self.busy = False
        self.items = []
        self.messages = []
        self.packets = []
        self.port = comm_port
        self.tasks = {}
        self.ui_data = ui_data
        self.intercept = Intercept()
        self.init_epd()
        self.init_image()
        self.init_buttons()
        self.init_items()
        self.init_comm_port()
        self.frames = 0

    def init_epd(self):
        self.epd = epaper.init()

    def init_image(self):
        if not self.epd:
            return
        self.buf = bytearray(self.epd.width * self.epd.height // 8)
        self.draw = framebuf.FrameBuffer(
            self.buf,
            self.epd.width,
            self.epd.height,
            framebuf.MONO_HLSB)

    def init_buttons(self):
        self.bm = bm
        self.bm.set(1, self.menu)
        self.bm.set(2, self.data)
        self.bm.set(4, self.power)

    def init_items(self):
        self.items.append(configure_main())
        self.items.append(configure_messages())
        self.items.append(configure_power())
        self.items.append(configure_data())
        self.flasher = configure_flash()

    def init_comm_port(self):
        self.tasks['comm'] = uasyncio.create_task(self.port.run())

    def menu(self):
        # self.init_image()
        self.active_item = 1
        item = self.items[self.active_item]
        self.bm.set(1, self.back)
        self.bm.set(2, item.up)
        self.bm.set(3, item.down)
        self.bm.set(4, item.select)
        item.selected = 0
        item.init_selected()

    def data(self):
        self.active_item = 3
        item = self.items[self.active_item]
        self.bm.set(1, self.back)
        self.bm.clear(2)
        self.bm.clear(3)
        self.bm.clear(4)

    def power(self):
        self.active_item = 2
        item = self.items[self.active_item]
        self.bm.set(1, self.back)
        self.bm.set(2, item.up)
        self.bm.set(3, item.down)
        self.bm.set(4, item.select)

    def back(self):
        # self.init_image()
        self.active_item = 0
        self.bm.set(1, self.menu)
        self.bm.set(2, self.data)
        self.bm.clear(3)
        self.bm.set(4, self.power)

    def shutdown(self):
        self.draw.fill(1)
        self.epd.display(self.buf)
        self.epd.display(self.buf)
        self.epd.display(self.buf)
        self.epd.sleep()
        # instead of sleep, fire of the new task?

    async def sync(self, sync_word):
        print("Syncing on {}".format(sync_word))

        cmd = "CMD;{}".format(sync_word).encode('utf-8')
        acksyn = "{}:ACKSYN".format(sync_word).encode('utf-8')
        endsyn = "{}:SYN".format(sync_word).encode('utf-8')

        await self.port.send_q.put(cmd)

        while True:

            data = await self.port.recv_q.get()
            data = data.strip(b'\r\n')

            if data:
                print("sync: {}".format(data))

            if data == acksyn:
                await self.port.send_q.put(endsyn)
                await uasyncio.sleep_ms(1000)
                break

            await self.port.send_q.put(cmd)
            await uasyncio.sleep_ms(1000)

    async def update(self):

        while ui_data.running:

            while self.ui_data.messages:
                await self.port.send_q.put(self.ui_data.messages.pop(0))

            while not self.port.recv_q.empty():
                # maybe the nowait version since I'm checking on empty?
                new_data = parse_esp_data(await self.port.recv_q.get())

                if new_data:
                    self.ui_data.update(new_data)
                    self.intercept.update(new_data)

                data = self.intercept.get()

                if data.get('refresh', False):
                    self.dirty = True
                    self.frames += 2

                self.ui_data.update(data)

            if self.bm.pressed:
                self.bm.update()
                self.bm.pressed = False
                self.frames = 3
                self.dirty = True


            if flasher.frames > 0:
                self.dirty = True
                flasher.update()

            if self.frames > 0:
                self.frames -= 1
                self.dirty = True

            if self.frames < 0:
                self.frames = 0

            if self.dirty:
                if self.items:
                    self.items[self.active_item].draw(self.draw)
                    self.flasher.draw(self.draw)
                self.epd.display(self.buf)
                self.dirty = False

            await uasyncio.sleep_ms(0)

        if not ui_data.running:
            self.shutdown()
            await self.sync(ui_data.sync_word)
            self.ui_data.sleep()
