"""
LoRa Driver
-----------

The LoRa driver is the interface between the rest of the firmware and the
details of sending and receiving messages with the sx127x transciever.

This driver implements the `connect` and `run` methods for configuration and
processing.

`run` will prepare packets for sending and send to the transciever, and pick
up received packets from the transciver based on the state of the `new_data`
instance variable on the transciever.

It's a convenience interface to abstract the sending and receving of data
easily.

The ability to switch the device to the 'ota' app is handled here as a short
cut.
"""
from core.compat import time
from core import storage


iam = storage.get("IAM")


class Lora:

    def __init__(self, clock=time):
        self.enabled = False
        self.clock = clock
        self.txr = None
        self.buffer = ""
        self.packets = []
        self.messages = []

    def connect(self, devices):
        ''' Connected the lora driver to the sx127x transciever driver and
            lift the chip's reset pin.

            :param dict devices: dict with the transceiver as 'txr'
        '''
        self.txr = devices.get('txr')
        self.rst = self.txr.rst

    def stop(self):
        ''' Stop the driver and put the transceiver to sleep.  Do not hold
            the transceiver in reset.
        '''
        self.txr.sleep()
        self.enabled = False

    def start(self):
        ''' Put the transceiver into standby mode'''
        self.txr.standby()
        self.clock.sleep(.05)
        self.enabled = True

    def run(self):
        ''' Run the lora driver.  If the transceiver indicates new data, lift
            the packet from the transceiver into `packets`. If the packet
            indicates a switch to the ota app, set that in storage.
            Indicate to the transceiver the packet was received.

            If there are message to send, exhaust those.

            Reset the transceiver into receive mode.
        '''
        if self.txr.new_data:
            try:
                data = self.txr.read_payload()
                if data:
                    data = data.decode('ascii')
                # a way to switch to OTA through LoRa
                if data == "{} OTA".format(iam):
                    storage.put("APP", "ota")
                self.packets.append(data)
                self.clock.sleep(.05)
            except UnicodeError:
                pass
            except Exception as e:
                print("lora.run: {}".format(e))
            self.txr.receivedPacket()
            self.clock.sleep(.05)
            self.txr.new_data = False

        if self.txr.bad_tx:
            print("lora: bad tx")
            self.txr.reset()
            self.txr.init()

        while self.messages:
            msg = self.messages.pop(0)
            self.txr.println(msg)
            self.clock.sleep(.05)
        self.txr.receive()
