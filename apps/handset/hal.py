import devices.clock
import devices.expander
import devices.gps
import devices.rockblock
import devices.display_port
import devices.battery_monitor
import devices.sx127x
import devices.lora

from devices import pin_defs

clock = devices.clock.Clock()
exp = devices.expander.Expander()
exp.connect(pin_defs.exp)

gps = devices.gps.GPS(clock=clock)
gps.connect(pin_defs.gps)
gps.stop()

rb = devices.rockblock.RockBlock(clock=clock)
rb.connect(pin_defs.rb)
rb.stop()

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

display_port = devices.display_port.DisplayPort()
display_port.connect(pin_defs.display_port)
