errors = {}
try:
    from devices import pin_defs
except Exception as e:
    errors['pin_defs'] = e

try:
    import devices.clock
except Exception as e:
    errors['clock'] = e

try:
    import devices.expander
except Exception as e:
    errors['exp'] = e

try:
    import devices.gps
except Exception as e:
    errors['exp'] = e

try:
    import devices.rockblock
except Exception as e:
    errors['rb'] = e

try:
    import devices.display_port
except Exception as e:
    errors['display'] = e

try:
    import devices.battery_monitor
except Exception as e:
    errors['batt'] = e

try:
    import devices.sx127x
except Exception as e:
    errors['sx127x'] = e

try:
    import devices.lora
except Exception as e:
    errors['lora'] = e

clock = None
if 'clock' not in errors:
    try:
        clock = devices.clock.Clock()
    except Exception as e:
        errors['clock': e]
        import time
        clock = time

exp = None
if 'exp' not in errors:
    try:
        exp = devices.expander.Expander()
        exp.connect(pin_defs.exp)
    except Exception as e:
        errors['exp'] = e

gps = None
if 'gps' not in errors:
    try:
        gps = devices.gps.GPS(clock=clock)
        gps.connect(pin_defs.gps)
        gps.stop()
    except Exception as e:
        errors['gps'] = e

rb = None
if 'rb' not in errors:
    try:
        rb = devices.rockblock.RockBlock(clock=clock)
        rb.connect(pin_defs.rb)
        rb.stop()
    except Exception as e:
        errors['rb'] = e

batt = None
if 'batt' not in errors:
    try:
        batt = devices.battery_monitor.BatteryMonitor(clock=clock)
        dev = {}
        dev.update(**pin_defs.batt_mon)
        dev['exp'] = exp
        batt.connect(dev)
        dev.clear()
    except Exception as e:
        errors['batt'] = e

txr = None
if 'sx127x' not in errors:
    try:
        txr = devices.sx127x.SX127x()
        txr.connect(pin_defs.lora)
    except Exception as e:
        errors['sx127x'] = e

lora = None
if 'lora' not in errors and 'sx127x' not in errors:
    try:
        lora = devices.lora.Lora(clock=clock)
        lora.connect({'txr': txr})
    except Exception as e:
        errors['lora'] = e

display_port = None
if 'display' not in errors:
    try:
        display_port = devices.display_port.DisplayPort()
        display_port.connect(pin_defs.display_port)
    except Exception as e:
        errors['display'] = e
