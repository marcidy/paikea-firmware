import os
from core import storage


defaults = {
    "IAM": "TEST",
    "LOG_WS": "ws://192.168.5.1:7777",
    "WS_SERVER": "server.hostname.com",
    "DEV": "buoy",
    "SSID": "defaultwifissid",
    "WIFIPASS": "defaultwifipass",
    "SERVER": "https://server.hostname.com/v1",
    "APP": "ota",
    "MODE": "SUPPORT",
    "LOC_SEND": "600",
    "SAT_VIEW": "900",
    "BAT_CHECK": "3600",
    "SLEEPMODE": "DEEP",
}


if storage.CORE_STORAGE not in os.listdir("/"):
    print("{} not found, creating".format(storage.CORE_STORAGE))
    storage.init()

for k, v in defaults.items():
    if not storage.get(k):
        print("Adding default {}: {}".format(k, v))
        storage.put(k, v)

    else:
        print("Found {}: {}".format(k, storage.get(k)))
