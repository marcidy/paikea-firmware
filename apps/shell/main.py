import sys
import network
import webrepl


def core_network():
    from core.support import net
    net.connect()


def app_main():
    ap = network.WLAN(network.AP_IF)
    ap.active(1)
    webrepl.start(password="test")
    try:
        core_network()
    except Exception:
        pass
    sys.exit()
