try:
    import machine
except ImportError:
    from core.compat import machine
machine.freq(20000000)

from apps.buoy import hal
from apps.buoy.paikea import Paikea


def app_init():
    hal.lora.start()
    # hal.gps.passthrough = True
    buoy.connect({'rb': hal.rb,
                  'gps': hal.gps,
                  'exp': hal.exp,
                  'batt_mon': hal.batt,
                  'lora': hal.lora})
    buoy.start()
    buoy.timers['loc_send'].marker = -3600
    buoy.update_marker("bat_check", -3600)


buoy = Paikea(clock=hal.clock)


def app_main():

    app_init()

    try:
        while True:
            buoy.run()
    except KeyboardInterrupt:
        return
