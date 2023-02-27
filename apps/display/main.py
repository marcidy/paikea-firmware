import uasyncio
from .display import Updater
from .power import startup

startup()

u = Updater()


def app_main():
    loop = uasyncio.get_event_loop()
    # uasyncio.create_task(u.comm_esp())
    uasyncio.create_task(u.update())
    loop.run_forever()
