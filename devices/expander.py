'''
IO Expander
-----------

    An I2C IO expander is attached to the HelTec ESP32 to provide more digital
    Input/output pins.  The connections are abstracted into nets accessible by
    label.

    The nets may be input, output, or both.

    Control of the expander is based on register access, and the registers
    are mirrored in this class, but reread on access.

    The driver implements the "connect" interface for accepting lower level
    interface objects.

    NOTE: Current the address is set twice, and probably should be set in only
    one place.
'''
from core.compat import int_from_bytes


class Expander:
    ''' Driver for TCA95XX io port expander

        .. table:: Port mapping
            :widths: auto

            ==== === === === === === === === ===
            Byte  7   6   5   4   3   2   1   0
            ==== === === === === === === === ===
            PXn  PX7 PX6 PX5 PX4 PX3 PX2 PX1 PX0
            ==== === === === === === === === ===

        .. table:: Pin Mapping
            :widths: auto

            ===  ========  === ======
            Pin  label     Pin label
            ===  ========  === ======
            00   led_en    17  NC
            01   NC        16  net_av
            02   fix       15  ri
            03   rpi_en    14  NC
            04   lynq_en   13  NC
            05   lbo       12  NC
            06   lynq_btn  11  NC
            07   batt_mon  10  NC
            ===  ========  === ======

    '''
    #: The I2C address for the expander is set in hardware, so it's hardcoded
    addr = 36
    #: These ports correspond to addresses used configuration registers
    ports = {
        0: {'config': 6, 'polarity': 4, 'output': 2, 'input': 0},
        1: {'config': 7, 'polarity': 5, 'output': 3, 'input': 1}}

    #: Net definitions as {'label': (port, bit, config)}
    _nets = {
        'led_en': (0, 0, 0),
        'fix': (0, 2, 1),
        'rpi_en': (0, 3, 0),
        'lynq_en': (0, 4, 0),
        'lbo': (0, 5, 1),
        'lynq_btn': (0, 6, 0),
        'batt_mon': (0, 7, 0),
        'ri': (1, 5, 1),
        'netav': (1, 6, 1)}

    #: Default configuration for registers, index by list index
    registers = [
        0b00000000,
        0b00000000,
        0b11111111,
        0b11111111,
        0b00000000,
        0b00000000,
        0b00100110,
        0b11111111]

    def __init__(self, addr=36):
        self.configured = False
        self.addr = addr

    def connect(self, devices):
        ''' Connect used devices to driver.  Expect an enable pin 'en' and
            an i2c bus 'i2c'.

            :param dict devices: dictionary with used devices
        '''
        self.en = devices['en']
        self.i2c = devices['i2c']
        if self.addr in self.i2c.scan():
            self.update()
            self.configure_nets()

    def configure_nets(self):
        ''' Configures the nets of the port expander as defined in `_nets`.
        '''
        self.update()
        nets = self._nets
        for net, values in nets.items():
            port, bit, config = values
            self.registers[self.ports[port]['config']] &= (0xff - ((1-config) << bit))  # NOQA line too long

        self.write_config()
        self.configured = True

    def configure_net(self, net_name):
        ''' Configures a single net based on passed net_name from configuration
            in '_nets'.

            :param str net_name: name of net to configure
        '''
        self.update()
        if net_name in self._nets:
            port, bit, config = self._nets[net_name]
            self.registers[self.ports[port]['config']] &= (0xff - ((1-config) << bit))  # NOQA
            self.write_config()

    def write_config(self):
        ''' Write configuration registers over i2c to port expander '''
        self.i2c.writeto_mem(self.addr, 6, bytes([self.registers[6]]))
        self.i2c.writeto_mem(self.addr, 7, bytes([self.registers[7]]))

    def update(self):
        ''' Read all register values and update driver's register values '''
        # registers[k] = reg_data
        self.registers = [
            int_from_bytes(
                self.i2c.readfrom_mem(self.addr, reg, 1),
                'big', False)
            for reg in range(len(self.registers))]

    def start(self):
        ''' Enable IO expander '''
        # on/off is inverted through the Vext pins
        self.en.off()

    def stop(self):
        ''' Disable IO expander '''
        self.en.on()

    def __getitem__(self, net):
        ''' Access value of pin via a net name.

            :param str net: name of net to access
            :rtype: bool
            :return: logic 1 or 0 of pin value for net

        '''
        if net not in self._nets:
            raise KeyError
        else:
            self.update()
            port, bit, config = self._nets[net]
            select = 'output' if config == 0 else 'input'
            val = self.registers[self.ports[port][select]] & (1 << bit)
            return val != 0

    def __setitem__(self, net, val):
        ''' Set an output value on io expander by net name.

            :param str net: name of net to access
            :param bool val: True or False for setting high or low
        '''
        port, bit, config = self._nets[net]
        if config == 1:
            # inputs don't get set
            return
        self.update()

        val = 1 if val else 0
        reg = self.ports[port]['output']
        if val == 0:
            new_val = self.registers[reg] & (0xFF - ((1-val) << bit))
        if val == 1:
            new_val = self.registers[reg] | (1 << bit)

        self.i2c.writeto_mem(self.addr, reg, bytes([new_val]))
        self.update()

    def display(self):
        ''' Display driver's representation of io expander registers '''
        for reg in self.registers:
            print("{:08b}".format(reg))
