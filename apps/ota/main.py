import uasyncio
from apps.ota.web import server
from apps.ota.ws import add_client, call_home
from core.websockets.server import serve
from core.support import net


net.connect()
net.configure_ap()


def app_main():
    uasyncio.create_task(uasyncio.start_server(server, '0.0.0.0', 80))
    uasyncio.create_task(serve(add_client, '0.0.0.0', 7777))
    uasyncio.create_task(call_home())
    loop = uasyncio.get_event_loop()
    loop.run_forever()
