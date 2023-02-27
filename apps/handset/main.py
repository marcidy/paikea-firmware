import gc
import uasyncio
from apps.handset import hal
from apps.handset.tracking_device import TrackingDevice


def app_init():
    hal.gps.start()
    td.set_mode('r')
    td.connect({'gps': hal.gps,
                'rb': hal.rb,
                'lora': hal.lora,
                'clock': hal.clock,
                'display_port': hal.display_port,
                'batt': hal.batt,
                })
    td.lora.txr.rx_done.irq(
        td.lora.txr.handleOnReceive,
        td.lora.txr.rx_done.IRQ_RISING)


td = TrackingDevice()


async def run():
    global td
    try:
        td.updated = True  # force first draw
        while True:
            td.run()
            gc.collect()
            await uasyncio.sleep_ms(1)
    except KeyboardInterrupt:
        return


def app_main():
    app_init()
    uasyncio.create_task(run())
    loop = uasyncio.get_event_loop()
    loop.run_forever()
