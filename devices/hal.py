"""
Generic Handware Abstraction Layer
----------------------------------
This module is a functional example of a device hal which configures device
drivers from lower level primities configured in the pin_defs module.

These are usable for exploration, but the application specific hals should be
used from the apps/... directory.

The dictionaries from the pin_def module are updated with shared or higher
level peripheral drivers and passed to the device driver's `connect` functions
to complete driver initialization.

Drivers should be imported from the hal modules so they are configured in a
single place and globally availalbe in the hal module namespace.
"""
import devices.clock
import devices.expander
import devices.gps
import devices.rockblock
import devices.display_port
import devices.battery_monitor
import devices.sx127x
import devices.lora

from devices import (
    pin_defs,
)


clock = devices.clock.Clock()

exp = devices.expander.Expander()
exp.connect(pin_defs.exp)

gps = devices.gps.GPS(clock=clock)
gps.connect(pin_defs.gps)
gps.stop()

rb = devices.rockblock.RockBlock(clock=clock)
rb.connect(pin_defs.rb)
rb.stop()

display_port = devices.display_port.DisplayPort()
display_port.connect(pin_defs.display_port)

batt = devices.battery_monitor.BatteryMonitor(clock=clock)
dev = {}
dev.update(**pin_defs.batt_mon)
dev['exp'] = exp
batt.connect(dev)
dev.clear()

txr = devices.sx127x.SX127x()
txr.connect(pin_defs.lora)

lora = devices.lora.Lora(clock=clock)
lora.connect({'txr': txr})
