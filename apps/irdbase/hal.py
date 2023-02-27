import devices.clock
import devices.rockblock
import devices.sx127x
import devices.lora

from devices import pin_defs

clock = devices.clock.Clock()
rb = devices.rockblock.RockBlock(clock=clock)
rb.connect(pin_defs.rb)
rb.stop()

txr = devices.sx127x.SX127x()
txr.connect(pin_defs.lora)

lora = devices.lora.Lora(clock)
lora.connect({'txr': txr})
