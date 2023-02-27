import devices.clock
import devices.sx127x
import devices.lora

from devices import pin_defs

clock = devices.clock.Clock()
txr = devices.sx127x.SX127x()
txr.connect(pin_defs.lora)

lora = devices.lora.Lora(clock=clock)
lora.connect({'txr': txr})
