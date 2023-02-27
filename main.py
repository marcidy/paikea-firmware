import gc
from core import storage
from core import support
import os
import time


try:
    import machine
except ImportError:
    from core.compat import machine


gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
app = storage.get("APP")


def app_main():
    support.switch_to_support()


modline = "from apps." + app + ".main import app_main"
try:
    exec(modline)
except ImportError as e:
    print(e)
    print("Unrecoverable error: defaulting to recovery")

try:
    app_main()
except Exception:
    os.umount("/")
    time.sleep(1)
    machine.reset()
