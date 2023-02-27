from core import storage
from core.utils import ActivityTimer
from core.compat import time


class LoraDbg:
    def __init__(self):
        self.lora = None
        self.timer = ActivityTimer("", time, 30, 0)
        self.timer.start()
        self.iam = storage.get("IAM")

    def connect(self, devices):
        self.lora = devices['lora']

    def __call__(self, val):
        print(val)
        if self.lora:
            self.lora.messages.append("{}: {}".format(self.iam, val))

    def run(self):
        if not self.lora:
            print("Lora debugger is not connected!")
            return
        if self.timer.expired:
            self.lora.messages.append("{}: *hc*".format(self.iam))
            self.timer.reset()
        if self.lora:
            self.lora.run()


lora_dbg = LoraDbg()
