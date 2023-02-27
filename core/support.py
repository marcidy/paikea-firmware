"""
Support
-------

The support module manages connections.

This module was larger but now contains minimal functionality related to
maintaining a wifi connection and switching the device into service
mode.

"""
import time
import os
from core import storage
from core.compat import (
    machine,
    network,
)
from core.utils import ActivityTimer


def switch_to_support():
    ''' Set the device to run the ota app on reboot, set the mode to SUPPORT,
        and reset the device.
        :rtype: bool
        :return: False if not successful
    '''
    storage.put("APP", "ota")
    if storage.put("MODE", "SUPPORT"):
        os.umount("/")
        time.sleep(1)
        machine.reset()
    return False


class Supported:
    ''' Originally an interface for multiple object.  By implementing the
        Supported interface, all supportable objects would be able to monitor
        their own state and recover from failure conditations

        Mixing in this class requires the parent class to implement
        members self.state, self.timer, self.attempts, as well
        as self.healthcheck() which sets the state and self.reconnect which
        attempts recovery.

        self.state has three values
        0 - new
        1 - degraded
        2 - healthy

        self.timer is a core.utils.ActivityTimer which, when expired, will
        trigger a self.healthcheck.
        self.attempts will track how many consequetive reconnection attempts
        are tried before giving up.
    '''

    def check(self):
        ''' check is run periodically to test the current state of a
            Supported class and make attempts to recover from failure
            conditions.

        '''
        if not self.timer.running:
            self.timer.start()
        if self.timer.expired:
            healthy = self.healthcheck()
            if healthy:
                self.state = 2
            elif self.state == 2:
                # Not healthy, transition state
                self.state = 1
                self.attempts = 0
            else:
                # otherwise, attempted to reconnect
                self.attempts += 1
                try:
                    self.reconnect()
                except Exception:
                    print("Reconnect of {} failed!".format(self))
            self.timer.reset()


class SupportNetwork(Supported):
    ''' SupportNetwork holds state related to the ESP32 networking functions
        for both an Access Point and Station.  Releveant parameteres are
        retrieved from storage.

        The Supported interface is used to maintain the Station's connection to
        and external Access Point.
    '''

    def __init__(self, clock=time):
        self.state = 0
        self.attempts = 0
        self.configured = False
        self.ap = None
        self.net = None
        self.timer = ActivityTimer("", clock, 5, -5)
        self.timer.start()

    def configure_ap(self):
        ''' Set up the ESP32 Wifi Access Point.  The AP name is the combination
            of the device type and device iam as
            Paikea-<device-type>-<device IAM>
        '''
        if machine.freq() < 80000000:
            print("machine freq too low")
            return False

        self.ap = network.WLAN(network.AP_IF)
        iam = storage.get("IAM")
        dev = storage.get("DEV")
        self.ap.active(1)
        self.ap.config(essid="Paikea-" + dev + "-" + iam)

    @property
    def connected(self):
        ''' Check if connected to the network or the access point is
            configured.

            :rtype: bool
            :return: True if connectable, False if not

        '''
        connected = False
        if self.net:
            connected = self.net.isconnected() and self.net.active()
        if self.ap:
            connected = connected or self.ap.active()
        return connected

    @property
    def dns_ok(self):
        ''' If the device is connceted, check if we have a good ip config

            :rtype: bool
            :return: True if we have ip address, dns, gateway configured

        '''
        if self.connected:
            return all([add != '0.0.0.0' for add in self.net.ifconfig()])
        else:
            return False

    def healthcheck(self):
        ''' Check if we are connected and ip config is OK

            :rtype: bool
            :returns: True when connected and ip config is OK, else False

        '''
        return self.connected and self.dns_ok

    def ready(self):
        ''' Same as self.healthcheck() '''
        return self.healthcheck()

    def connect(self, ssid=None, wifi_pass=None):
        ''' Connect to a Wifi AP using stored or passed parameters.

            If None is passed to a parameter, the stored values are in the
            on-device storage as "SSID" or "WIFIPASS".

            :param str ssid: SSID of network to connect to
            :param str wifi_pass: WiFi AP Password
            :rtype: bool
            :return: True if connection attemped

        '''
        if machine.freq() < 80000000:
            print("machine freq too low")
            return False

        if not self.net:
            self.net = network.WLAN(network.STA_IF)

        if not self.net.active():
            self.net.active(True)

        if not ssid:
            ssid = storage.get("SSID")

        if self.net.isconnected():
            if not self.net.config("essid") == ssid:
                self.net.disconnect()
            else:
                self.configured = True
                # connected to target ssid
                return

        if not wifi_pass:
            wifi_pass = storage.get("WIFIPASS")

        # might want to scan for networks and check that ssid is in there
        if ssid and wifi_pass:
            self.net.connect(ssid, wifi_pass)
        else:
            raise ValueError("messed up w/ ssid and wifipass")
        self.configured = True

    def reconnect(self):
        ''' Attempt to reconnect if disconnected '''
        if not self.configured:
            self.connect()

    def deinit(self):
        ''' Disconnect and turn off WiFi radio '''
        if self.net:
            self.net.disconnect()
            self.net.active(False)
        if self.ap:
            self.ap.active(False)


#: The Networking management object, instanciated and availble here.
net = SupportNetwork()
