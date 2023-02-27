import gc
import uasyncio
import json
import time
import os
from core.compat import reset
from core.support import net
from core import storage
from core.websockets import client


cid = 0
clients = set()
tasks = {}

iam = storage.get("IAM")
dev = storage.get("DEV")

state = {
    "iam": iam,
    "dev": dev,
    "batt/main_v": 0,
    "rb/enabled": False,
    "rb/running": False,
    "gps/enabled": False,
    "gps/running": False,
    "lora/enabled": False,
    "lora/running": False,
}

hal = None


async def send(data):
    # print(data)
    await uasyncio.gather(*[cl.send(data) for cl in clients])


async def wifi(ws):
    await ws.send('{"info": "Querying networking..."}')
    ssid = storage.get("SSID")
    await ws.send('{{"wifi/stored/ssid": "{}"}}'.format(ssid))
    if net.ap:
        await ws.send('{{"wifi/ap/active": "{}"}}'.format(net.ap.active()))
        await ws.send('{{"wifi/ap/ssid": "{}"}}'.format(net.ap.config('essid')))
    else:
        await ws.send('{{"wifi/ap/active": "{}"}}'.format(False))
    if net.net:
        await ws.send('{{"wifi/net/active": "{}"}}'.format(net.net.active()))
        mac = (("{:02X}:"*6)[:-1]).format(*net.net.config('mac'))
        await ws.send('{{"wifi/net/mac": "{}"}}'.format(mac))
        await ws.send('{{"wifi/net/ap": "{}"}}'.format(net.net.config('essid')))
        connected = net.net.isconnected()
        await ws.send('{{"wifi/net/connected": "{}"}}'.format(connected))
        if connected:
            ip, mask, gw, dns = net.net.ifconfig()
            await ws.send('{{"wifi/net/ip": "{}"}}'.format(ip))
            await ws.send('{{"wifi/net/gw": "{}"}}'.format(gw))
            await ws.send('{{"wifi/net/dns": "{}"}}'.format(dns))

    else:
        await ws.send('{{"wifi/net/active": "{}"}}'.format(False))
    await ws.send('{"info": "Done"}')


async def init_hardware():
    global hal
    if not hal:
        await send('{"info": "Initializing hardware..."}')
        gc.collect()
        import apps.ota.hal
        hal = apps.ota.hal
        await send('{"info": "Done"}')
    errors = hal.errors
    await send('{{"hardware_errors": "{}"}}'.format(len(errors)))
    for k, v in errors.items():
        await send('{{"error": "{}"}}'.format("{} - {}".format(k, v)))

    uasyncio.create_task(check_batt())


async def run_gps():
    while True:
        hal.gps.run()
        for k, v in hal.gps.location_data.items():
            await send('{{"gps/location/{}": "{}"}}'.format(k, v))
        for k, v in hal.gps.signal_data.items():
            await send('{{"gps/signal/{}": "{}"}}'.format(k, v))
        for k, v in hal.gps.course_data.items():
            await send('{{"gps/course/{}": "{}"}}'.format(k, v))
        await uasyncio.sleep(1)


async def start_gps():
    if 'gps' in tasks:
        state["gps/enabled"] = hal.gps.en()
        state["gps/running"] = True
        return
    if not hal:
        await init_hardware()
    if 'gps' not in hal.errors:
        if not hal.gps.en():
            await send('{"info": "starting GPS"}')
            hal.gps.start()
        state["gps/enabled"] = hal.gps.en()
        state["gps/running"] = True
        await send('{"info": "Done"}')
        tasks['gps'] = uasyncio.create_task(run_gps())


async def run_rb():
    pVals = {'csq': None,
             'mo_flag': None,
             'mt_flag': None,
             'momsn': None,
             'mtmsn': None,
             'ra_flag': None,
             'queue': None}

    hal.rb.atcmd("+SBDAREG=1", False)
    hal.rb.atcmd("+SBDMTA=1", False)
    hal.rb.create_sbd_session()

    while True:
        hal.rb.run()
        if 'pkea' in hal.rb.data:
            pkt = hal.rb.data.pop('pkea')
            await send(json.dumps({"rb/msg": pkt}))
        for k, v in pVals.items():
            nv = getattr(hal.rb, k)
            if nv != v:
                await send('{{"rb/{}": "{}"}}'.format(k, nv))
                pVals[k] = nv
        await uasyncio.sleep_ms(100)


async def start_rb():
    global hal
    if 'rb' in tasks:
        state["rb/enabled"] = hal.rb.en()
        state["rb/running"] = True
        return
    if not hal:
        await init_hardware()
    if 'rb' not in hal.errors:
        if not hal.rb.en():
            await send('{"info": "Starting RockBlock"}')
            hal.rb.start()
        state["rb/enabled"] = hal.rb.en()
        state["rb/running"] = True
        await send('{"info": "Done"}')
        tasks['rb'] = uasyncio.create_task(run_rb())


async def run_lora():
    lora = hal.lora
    while True:
        lora.run()
        while hal.lora.packets:
            await send(json.dumps({'lora/msg': hal.lora.packets.pop(0)}))
            await send(json.dumps({'lora/rssi': hal.lora.txr.packetRssi()}))
        await uasyncio.sleep_ms(50)


async def check_batt():
    batt = hal.batt
    while True:
        batt.check()
        if batt.main_v != state['batt/main_v']:
            state['batt/main_v'] = batt.main_v
            await send(json.dumps({'batt/main_v': batt.main_v}))

        await uasyncio.sleep_ms(1000)


async def start_lora():
    if 'lora' in tasks:
        state["lora/running"] = True
        return
    await send('{"info": "Starting LoRa"}')
    tasks['lora'] = uasyncio.create_task(run_lora())
    state["lora/running"] = True


async def stop_lora():
    if 'lora' in tasks:
        tc = tasks.pop('lora')
        tc.cancel()
    state["lora/running"] = False


async def stop_gps_task():
    if 'gps' in tasks:
        task = tasks.pop('gps')
        task.cancel()
    state["gps/running"] = False


async def stop_rb_task():
    if 'rb' in tasks:
        task = tasks.pop('rb')
        task.cancel()
    state["rb/running"] = False


async def scan_new_network(sta_ssid):
    if not net.net.active():
        net.net.active(1)

    for ap in net.net.scan():
        if ap[0] == sta_ssid.encode('ascii'):
            return True
    return False


async def test_stored_sta(args=None):
    ssid = storage.get("SSID")
    wifi_pass = storage.get("WIFIPASS")

    if net.configured and net.connected():
        if net.net.config('essid') == ssid:
            await send('{{"wifi/stored/ok", "{}"}}'.format(True))
            return
    else:
        net.connect(ssid=ssid, wifi_pass=wifi_pass)
        if net.net.config('essid') == ssid:
            await send('{{"wifi/stored/ok", "{}"}}'.format(True))
            return


async def watch_connection():
    start_time = time.time()
    while time.time() - start_time < 10:
        if net.net.isconnected():
            return True
        uasyncio.sleep_ms(500)
    return False


async def test_new_sta(args=None):
    if not args or len(args) < 1 or len(args) > 2:
        await send('{"error": "Bad args for wifi, need at least 1, no more than 2"}')
        return

    ssid = args[0]
    wifi_pass = None
    if len(args) == 2:
        wifi_pass = args[1]
    if wifi_pass == "":
        wifi_pass = None

    sta_connected = net.net.isconnected()
    sta_ssid = net.net.config("essid")

    if (sta_connected and
            ssid == sta_ssid and
            ssid == storage.get("SSID") and
            wifi_pass != storage.get("WIFIPASS")):
        await send('{"error": "Cannot test different pass of stored, connected ssid"}')
        await send('{"wifi/test/result": "Fail"}')
        return

    await send('{"info": "Starting network scan"}')
    scan_result = await scan_new_network(ssid)

    if scan_result:
        await send('{"info": "Network Found"}')
        await send('{"info": "Attempting Connection"}')
        net.net.disconnect()
        try:
            if wifi_pass:
                net.net.connect(ssid, wifi_pass)
            else:
                net.net.connect(ssid)
        except Exception:
            net.connect()
            return
    else:
        await send('{"wifi/test/result": "Fail"}')
        await send('{{"info": "Network {} Not Found"}}'.format(ssid))
        return

    con_ssid = net.net.config("essid")
    success = "Success" if con_ssid == ssid else "Fail"
    if net.net.isconnected():
        await send('{{"wifi/test/result": "{}"}}'.format(success))
        ip, mask, gw, dns = net.net.ifconfig()
        await send('{{"wifi/sta/new_test": "{}"}}'.format(True))
        await send('{{"wifi/sta/connected": "{}"}}'.format(True))
        await send('{{"wifi/sta/ip": "{}"}}'.format(ip))
        await send('{{"wifi/sta/gw": "{}"}}'.format(gw))
        await send('{{"wifi/sta/dns": "{}"}}'.format(dns))
    else:
        net.connect()


async def store_new_sta(args=None):
    if not args or len(args) < 1 or len(args) > 2:
        await send('{"error": "Bad args for wifi, need at least 1, no more than 2"}')
        return

    ssid = args[0]
    wifi_pass = None
    if len(args) == 2:
        wifi_pass = args[1]
    if wifi_pass == "":
        wifi_pass = None

    storage.put("SSID", ssid)
    storage.put("WIFIPASS", wifi_pass)
    ssid = storage.get("SSID")
    await send('{{"wifi/stored/ssid": "{}"}}'.format(ssid))


async def send_lora(args=None):
    if not args or len(args) > 1:
        await send('{"error": "Bad args for Lora Send"}')
        return

    if 'lora' not in tasks:
        await send('{"info": "LoRa not running"}')

    hal.lora.messages.append(args[0])


async def service(args=None):
    dev = storage.get("DEV")
    storage.put("APP", dev)


async def switch_app(args=None):
    if not args or len(args) < 1 or len(args) > 2:
        await send('{"error": "Bad args for app, need at least 1, no more than 2"}')
        return

    app = args[0]
    apps = [
        "buoy",
        "handset",
        "irdbase",
        "lorabase",
        "lora_receiver",
        "lora_sender",
        "ota",
        "shell",
        "updatepy",
    ]
    if app not in apps:
        await send('{{"error": "{} not a valid app"}}'.format(app))
        return

    await send('{{"info": "Switching to app {}"}}'.format(app))
    print("Switching app to {}".format(app))
    storage.put("APP", app)
    return


async def reset_device(args=None):
    os.umount("/")
    time.sleep(1)
    reset()


get_router = {
    'wifi': wifi,
}

cmd_router = {
    'hal': init_hardware,
    'reset': reset_device,
    'send_lora': send_lora,
    'service': service,
    'start_lora': start_lora,
    'start_gps': start_gps,
    'start_rb': start_rb,
    'stop_lora': stop_lora,
    'stop_gps': stop_gps_task,
    'stop_rb': stop_rb_task,
    'store_new_sta': store_new_sta,
    'switch_app': switch_app,
    'test_new_sta': test_new_sta,
}


async def process(ws, data):
    print("Handling: {}".format(data))
    gc.collect()
    try:
        cmd, item, args = json.loads(data)
    except Exception as e:
        gc.collect()
        await ws.send('{"error": "Malformed Request"}')
        await ws.send(json.dumps({'error': data}))
        await ws.send('{{"error": "{}"}}'.format(e))
        gc.collect()
        return

    if cmd == "GET":
        if item in get_router:
            await get_router[item](ws)
    if cmd == "CMD":
        if item in cmd_router:
            if args:
                await cmd_router[item](args)
            else:
                await cmd_router[item]()
    gc.collect()


async def register(ws):
    print("register")
    clients.add(ws)


async def unregister(ws):
    print("unregister")
    clients.remove(ws)


async def add_client(ws, path):
    print("Client Connection to {}".format(path))
    await register(ws)

    try:
        await send(json.dumps(state))
        async for msg in ws:
            await process(ws, msg)
            await send(json.dumps(state))
    finally:
        await unregister(ws)
        if not net.net.isconnected():
            net.connect()


async def call_home():
    connected = False
    server = storage.get("WS_SERVER")
    uri = "ws://" + server + ":7777/" + iam
    print("uri: {}".format(uri))
    while True:
        if not connected:
            try:
                ws = await client.connect(uri)
                if ws:
                    connected = True
                    uasyncio.create_task(add_client(ws, "/" + iam))
            except Exception as e:
                print(e)
                connected = False
        else:
            connected = ws.open
        await uasyncio.sleep(5)
