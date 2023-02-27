"""
Battery Monitor
---------------

The battery monitor checks the battery level by measuring the current
voltage on the Vs pin of the power supply using an ADC on the HelTec ESP32.

The voltage is not constantly fed to the ADC, but triggered by enabling the
'batt_mon' net on the IO expander.

The battery monitor depends on the io expander device and ADC devices.

Originally there were two batteries on board: the main battery and one for
an external device.  The external device is no longer used.

For accurate voltages, each device requires calibration, and the actual
reading is only reliable in the sense that is is a metric for the current
battery energy.

The uncalibrated voltages are acceptible for rough estimates of battery level.
anything above 4.2 indicates the battery is under charge.
Anything below 3.2 is considered low and the device requires charging.
"""

from core.compat import time


class BatteryMonitor:
    ''' Check the battery levels '''
    def __init__(self, clock=time):
        # configure the ADCs as needed since you'll need to switch the
        # calibration
        self.clock = clock
        self.hw_factor = 14/3  # constact factor from onboard resistor divider
        self.enabled = False
        self.atten = 1
        self.main_v = 0
        self.lynq_v = 0
        self.last_run = 0

    def connect(self, devices):
        ''' Connect this driver to it's depended devices.  The battery monitor
            expects access to a device.Expander object as 'exp' and two ADC
            devices as 'main_adc' for the main battery and 'ext_adc' as
            the secondary battery.

            :param dict devices: device driver dependencies

        '''
        self.exp = devices['exp']
        self.main_adc = devices['main_adc']
        self.ext_adc = devices['ext_adc']

    def start(self):
        ''' Enable the measuring of battery voltages.  This is done by
            configuring the batt_mon net on the io expander by setting the
            net to "output" and driving the pin low.  This triggers a MOSFET
            which makes the battery voltage available for ADC measurement.
        '''
        self.enabled = True
        net = list(self.exp._nets['batt_mon'])
        net[2] = 0
        self.exp._nets['batt_mon'] = tuple(net)
        self.exp.configure_net('batt_mon')
        # set io expander pin low
        self.exp['batt_mon'] = False

    def stop(self):
        ''' Disables the battery measurement so it's not constantly driving
            the measuring circuitry.  Set's the batt_mon net high on the
            expander and configures the expander to an input to cut off all
            driving of the mosfet.
        '''
        # set io expander pin High
        # self.exp['batt_mon'] = True

        # change to input on io expander
        net = list(self.exp._nets['batt_mon'])
        net[2] = 1
        self.exp._nets['batt_mon'] = tuple(net)
        self.exp.configure_net('batt_mon')
        self.enabled = False

    def set_calibration(self, factor):
        ''' Sets the calibration factor for the device when/if calibrated.

            :param float factor: calibration factor for battery ADC
        '''
        self.hw_factor = factor

    def check(self):
        ''' Check the battery levels.  Enables measurement circuits, measures
            the voltages, updates the timestamp for last check, and disables
            the measurement circuits.  This is the only function to call during
            operation.

            sets self.main_v and self.lynq_v with the voltages from this run.
        '''
        self.start()
        self.clock.sleep(.001)
        self.main_v = round(self.run(self.main_adc), 1)
        self.lynq_v = round(self.run(self.ext_adc), 1)
        self.stop()
        self.last_run = self.clock.time()

    def run(self, adc):
        ''' Run a voltage measurement on the passed adc pin.
            Takes 32 measurements from the 12bit ADC as high and low bytes,
            then averages the reading, and applies the calibration factor
            and attentuation values to get the calibrated value.

            Calibration here is assuming the hw_factor is correctly calibrated.

            :param machine.Pin adc: A configured ADC pin to measure
            :return: calibrated voltage reading
            :rtype: float

        '''
        total = 0
        meas = bytearray(2*32)  # 32 12bit measurements
        for m in range(0, 64, 2):
            read = adc.read()
            meas[m] = read & 0xFF  # low byte
            meas[m+1] = (read >> 8) & 0x0F  # high bite, low nibble
            self.clock.sleep(0.001)

        for x in range(0, 64, 2):
            total += (meas[x+1] << 8) + meas[x]
        raw = total / 32 / 4096  # make this dependent on bit with
        calib = raw * self.hw_factor * self.atten
        return calib
