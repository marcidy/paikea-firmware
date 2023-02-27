"""
SEMTECH SX127x Driver
---------------------

The HelTec module contains a SEMTECH sx127x chip for LoRa functionality.  This
driver manages state and communication with the sx127x over SPI and associated
pins.

This driver sends and receives packets and makes that interface available to
the lora module driver.  All interfacing with the sx127x is encapsulated here.

The SX127X tranceiver uses a number of parameters for initialization which
are passed as a dictionary.

The parameters are defaulted as they must match between sending and receiving
units.

Communiction with the driver is managed over the SPI bus through the
readRegister and writeRegister functions.

Explanation of the control flow is given in the SEMTECH SX127X datasheet and
details are not provided here.
"""
from core.compat import time
import gc

PA_OUTPUT_RFO_PIN = 0
PA_OUTPUT_PA_BOOST_PIN = 1

# registers
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_LR_OCP = 0x0b
REG_LNA = 0x0c
REG_FIFO_ADDR_PTR = 0x0d

REG_FIFO_TX_BASE_ADDR = 0x0e
FifoTxBaseAddr = 0x00
# FifoTxBaseAddr = 0x80

REG_FIFO_RX_BASE_ADDR = 0x0f
FifoRxBaseAddr = 0x00
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS_MASK = 0x11
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_RSSI_VALUE = 0x1a
REG_PKT_SNR_VALUE = 0x1b
REG_MODEM_CONFIG_1 = 0x1d
REG_MODEM_CONFIG_2 = 0x1e
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_PAYLOAD_LENGTH = 0x22
REG_FIFO_RX_BYTE_ADDR = 0x25
REG_MODEM_CONFIG_3 = 0x26
REG_RSSI_WIDEBAND = 0x2c
REG_DETECTION_OPTIMIZE = 0x31
REG_DETECTION_THRESHOLD = 0x37
REG_SYNC_WORD = 0x39
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42
REG_PADAC = 0x4d

# modes
MODE_LONG_RANGE_MODE = 0x80  # bit 7: 1 => LoRa mode
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RX_CONTINUOUS = 0x05
MODE_RX_SINGLE = 0x06

# PA config
PA_BOOST = 0x80

# IRQ masks
IRQ_TX_DONE_MASK = 0x08
IRQ_PAYLOAD_CRC_ERROR_MASK = 0x20
IRQ_RX_DONE_MASK = 0x40
IRQ_RX_TIME_OUT_MASK = 0x80

# Buffer size
MAX_PKT_LENGTH = 255


class SX127x:
    """ Driver for SX127x LoRa hardware. """
    def __init__(self,
                 parameters={'frequency': 915E6,
                             'tx_power_level': 14,
                             'signal_bandwidth': 125E3,
                             'spreading_factor': 12,
                             'coding_rate': 5,
                             'preamble_length': 8,
                             'implicitHeader': False,
                             'sync_word': 0x12,
                             'enable_CRC': False},
                 onReceive=None):

        self.params = parameters
        self.new_data = False
        self.spi = None
        self.ss = None
        self.rst = None
        self.rx_done = None
        self.bad_tx = False
        self._implicitHeaderMode = None
        self._frequency = 915E6

    def connect(self, devices):
        """ Connect the driver with peripherals required to communicate with
            the sx127x.

            The driver uses an spi bus for most communication.  The `rx_done`
            pin is used as an interrupt to indicate a retrieved message.  As
            the `rx_done` pin is only high for 20us, the interrupt it generates
            sets the `new_data` flag.

            The `ss` pin is used to indicate communication with the sx127x chip
            `rst` is used to perform a hardware reset of the chip.

            After the devices are setup, `init` is called.

            :param dict devices: device hal
        """
        self.spi = devices.get('spi')
        self.ss = devices.get('ss')
        self.rst = devices.get('rst')
        if self.rst:
            self.rst.on()
        self.rx_done = devices.get('rx_done')

        if self.rx_done:
            self.rx_done.irq(
                handler=self.handleOnReceive,
                trigger=self.rx_done.IRQ_RISING)
        self.init()

    def reset(self):
        """ Perform a hardware reset of the sx127x chip by pulsing the reset
            pin for 50ms.  Reset is low and chip active is high.
        """
        self.rst.off()
        time.sleep(.05)
        self.rst.on()
        time.sleep(.05)

    def init(self, parameters=None):
        """ Initialize the SX127X into LoRa mode per the datasheet.  Please
            see the datasheet for details on the initialization requirements
        """
        if parameters:
            self.params = parameters

        self.bad_tx = False
        init_try = True
        re_try = 0
        # check version
        while(init_try and re_try < 5):
            version = self.readRegister(REG_VERSION)
            re_try = re_try + 1
            if(version != 0):
                init_try = False
        if version & 0xF0 != 0x10:
            print('Warning: unsupported sx127x version: {}'.format(version))

        # put in LoRa and sleep mode
        self.sleep()

        # config
        self.setFrequency(self.params['frequency'])
        self.setSignalBandwidth(self.params['signal_bandwidth'])

        # set LNA boost
        self.writeRegister(REG_LNA, self.readRegister(REG_LNA) | 0x03)

        # set auto AGC
        modemCfg3 = self.readRegister(REG_MODEM_CONFIG_3)
        self.writeRegister(REG_MODEM_CONFIG_3, modemCfg3 | 0x04)

        # self.setTxPower(self.params['tx_power_level'])
        self.setTxPowerMax(20)
        self.implicitHeaderMode(self.params['implicitHeader'])
        self.setSpreadingFactor(self.params['spreading_factor'])
        self.setCodingRate(self.params['coding_rate'])
        self.setPreambleLength(self.params['preamble_length'])
        self.setSyncWord(self.params['sync_word'])
        self.enableCRC(self.params['enable_CRC'])

        # set LowDataRateOptimize flag if symbol time > 16ms
        # (default disable on reset)
        # self.writeRegister(REG_MODEM_CONFIG_3,
        # self.readRegister(REG_MODEM_CONFIG_3) & 0xF7)  # default disable on
        # reset
        if 1000 / (self.params['signal_bandwidth'] / 2 **
                   self.params['spreading_factor']) > 16:
            self.writeRegister(REG_MODEM_CONFIG_3,
                               self.readRegister(REG_MODEM_CONFIG_3) | 0x08)

        # set base addresses
        self.writeRegister(REG_FIFO_TX_BASE_ADDR, FifoTxBaseAddr)
        self.writeRegister(REG_FIFO_RX_BASE_ADDR, FifoRxBaseAddr)

        # set rx_done == DIO1
        self.writeRegister(REG_DIO_MAPPING_1, 0x00)
        self.standby()

        if self.rx_done:
            self.rx_done.irq(
                handler=self.handleOnReceive,
                trigger=self.rx_done.IRQ_RISING)

    def beginPacket(self, implicitHeaderMode=False):
        ''' Prepare chip to receive pack data '''
        self.standby()
        self.implicitHeaderMode(implicitHeaderMode)

        # reset FIFO address and paload length
        self.writeRegister(REG_FIFO_ADDR_PTR, FifoTxBaseAddr)
        self.writeRegister(REG_PAYLOAD_LENGTH, 0)

    def endPacket(self):
        ''' Indicate to chip we are done sending packet data'''
        # put in TX mode
        self.writeRegister(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_TX)

        # wait for TX done, standby automatically on TX_DONE
        start_time = time.time()

        while (self.readRegister(REG_IRQ_FLAGS) & IRQ_TX_DONE_MASK) == 0:
            time.sleep(.00001)
            if time.time() - start_time > 15:
                self.bad_tx = True
                break

        # clear IRQ's
        self.writeRegister(REG_IRQ_FLAGS, IRQ_TX_DONE_MASK)

        gc.collect()

    def write(self, buffer):
        ''' Write bytes buffer to packet payload registers for sending
            :param bytes buffer: binary data to send
            :rtype: int
            :return: number of bytes in packet
        '''
        currentLength = self.readRegister(REG_PAYLOAD_LENGTH)
        size = len(buffer)

        # check size
        size = min(size, (MAX_PKT_LENGTH - FifoTxBaseAddr - currentLength))

        # write data
        for i in range(size):
            self.writeRegister(REG_FIFO, buffer[i])

        # update length
        self.writeRegister(REG_PAYLOAD_LENGTH, currentLength + size)
        return size

    def println(self, string, implicitHeader=False):
        ''' Write data into the to send packet register on the chip
            :param str string: ascii string to send over LoRa
            :param implicitHeader: False always
        '''
        self.beginPacket(implicitHeader)
        self.write(string.encode())
        self.endPacket()

    def getIrqFlags(self):
        irqFlags = self.readRegister(REG_IRQ_FLAGS)
        self.writeRegister(REG_IRQ_FLAGS, irqFlags)
        return irqFlags

    def packetRssi(self):
        ''' retrieve the RSSI value for the last received packed
            :return: packet RSSI
            :rtype: int
        '''
        return (self.readRegister(REG_PKT_RSSI_VALUE)
                - (164 if self._frequency < 868E6 else 157))

    def packetSnr(self):
        return (self.readRegister(REG_PKT_SNR_VALUE)) * 0.25

    def standby(self):
        self.writeRegister(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_STDBY)

    def sleep(self):
        self.writeRegister(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_SLEEP)

    def setTxPower(self, level, outputPin=PA_OUTPUT_PA_BOOST_PIN):
        if (outputPin == PA_OUTPUT_RFO_PIN):
            # RFO
            level = min(max(level, 0), 14)
            self.writeRegister(REG_PA_CONFIG, 0x70 | level)

        else:
            # PA BOOST
            level = min(max(level, 2), 17) - 2
            self.writeRegister(REG_PA_CONFIG, PA_BOOST | level)

    def setTxPowerMax(self, level):
        level = max(5, min(20, level)) - 5
        self.writeRegister(REG_LR_OCP, 0x3f)
        paDac = self.readRegister(REG_PADAC)
        self.writeRegister(REG_PADAC, paDac | 0x07)
        print("PADAC: {:08b}".format(self.readRegister(REG_PADAC)))
        self.writeRegister(REG_PA_CONFIG, PA_BOOST | level)

    def setFrequency(self, frequency):
        self._frequency = frequency

        frfs = {169E6: (42, 64, 0),
                433E6: (108, 64, 0),
                434E6: (108, 128, 0),
                866E6: (216, 128, 0),
                868E6: (217, 0, 0),
                915E6: (228, 192, 0)}

        self.writeRegister(REG_FRF_MSB, frfs[frequency][0])
        self.writeRegister(REG_FRF_MID, frfs[frequency][1])
        self.writeRegister(REG_FRF_LSB, frfs[frequency][2])

    def setSpreadingFactor(self, sf):
        sf = min(max(sf, 6), 12)
        self.writeRegister(REG_DETECTION_OPTIMIZE, 0xc5 if sf == 6 else 0xc3)
        self.writeRegister(REG_DETECTION_THRESHOLD, 0x0c if sf == 6 else 0x0a)
        self.writeRegister(
            REG_MODEM_CONFIG_2,
            (self.readRegister(REG_MODEM_CONFIG_2) & 0x0f) | (
                (sf << 4) & 0xf0))

    def setSignalBandwidth(self, sbw):
        bins = (
            7.8E3,
            10.4E3,
            15.6E3,
            20.8E3,
            31.25E3,
            41.7E3,
            62.5E3,
            125E3,
            250E3)

        bw = 9
        for i in range(len(bins)):
            if sbw <= bins[i]:
                bw = i
                break

        self.writeRegister(
            REG_MODEM_CONFIG_1,
            (self.readRegister(REG_MODEM_CONFIG_1) & 0x0f) | (
                bw << 4))

    def setCodingRate(self, denominator):
        denominator = min(max(denominator, 5), 8)
        cr = denominator - 4
        self.writeRegister(
            REG_MODEM_CONFIG_1,
            (self.readRegister(REG_MODEM_CONFIG_1) & 0xf1) | (
                cr << 1))

    def setPreambleLength(self, length):
        self.writeRegister(REG_PREAMBLE_MSB,  (length >> 8) & 0xff)
        self.writeRegister(REG_PREAMBLE_LSB,  (length >> 0) & 0xff)

    def enableCRC(self, enable_CRC=False):
        modem_config_2 = self.readRegister(REG_MODEM_CONFIG_2)
        config = modem_config_2 | 0x04 if enable_CRC else modem_config_2 & 0xfb
        self.writeRegister(REG_MODEM_CONFIG_2, config)

    def setSyncWord(self, sw):
        self.writeRegister(REG_SYNC_WORD, sw)

    def implicitHeaderMode(self, implicitHeaderMode=False):
        # set value only if different.
        if self._implicitHeaderMode != implicitHeaderMode:
            self._implicitHeaderMode = implicitHeaderMode
            modem_config_1 = self.readRegister(REG_MODEM_CONFIG_1)
            if implicitHeaderMode:
                config = modem_config_1 | 0x01
            else:
                config = modem_config_1 & 0xfe
            self.writeRegister(REG_MODEM_CONFIG_1, config)

    def receive(self, size=0):
        ''' when a packet has been retrieved, this function is called to
            place the chip back into receive mode
        '''
        self.implicitHeaderMode(size > 0)
        if size > 0:
            self.writeRegister(REG_PAYLOAD_LENGTH, size & 0xff)

        # The last packet always starts at FIFO_RX_CURRENT_ADDR
        # no need to reset FIFO_ADDR_PTR
        self.writeRegister(
            REG_OP_MODE,
            MODE_LONG_RANGE_MODE | MODE_RX_CONTINUOUS)

    def handleOnReceive(self, event_source):
        ''' IRQ handler for use with `rx_done` pin.  Sets the `new_data` flag
            which indicates that there is new data in the packet registers and
            that the device needs to be reset into receive mode.
            Will set the device into standby mode so packet is not overwritten

            :param int event_source: IRQ trigger, ignored
        '''
        self.new_data = True
        irqFlags = self.getIrqFlags()
        # RX_DONE only, irqFlags should be 0x40
        if (irqFlags == IRQ_RX_DONE_MASK):
            # automatically standby when RX_DONE
            self.new_data = True

        elif self.readRegister(REG_OP_MODE) != (MODE_LONG_RANGE_MODE |
                                                MODE_RX_SINGLE):
            # no packet received.
            # reset FIFO address / # enter single RX mode
            self.writeRegister(REG_FIFO_ADDR_PTR, FifoRxBaseAddr)
            self.writeRegister(REG_OP_MODE,
                               MODE_LONG_RANGE_MODE | MODE_RX_SINGLE)

    def receivedPacket(self, size=0):
        ''' When a packet is received, the reception must be acknowledged
            to set the chip back into the mode to receive additional packets.

            :param int size: passed to implicitHeaderMode
        '''
        irqFlags = self.getIrqFlags()

        self.implicitHeaderMode(size > 0)
        if size > 0:
            self.writeRegister(REG_PAYLOAD_LENGTH, size & 0xff)

        # RX_DONE only, irqFlags should be 0x40
        if (irqFlags == IRQ_RX_DONE_MASK):
            # automatically standby when RX_DONE
            return True

        elif self.readRegister(REG_OP_MODE) != (MODE_LONG_RANGE_MODE |
                                                MODE_RX_SINGLE):
            # no packet received.
            # reset FIFO address / # enter single RX mode
            self.writeRegister(REG_FIFO_ADDR_PTR, FifoRxBaseAddr)
            self.writeRegister(REG_OP_MODE,
                               MODE_LONG_RANGE_MODE | MODE_RX_SINGLE)

    def read_payload(self):
        ''' Reads the packet payload from a received LoRa packet
            :rtype: bytes
            :return: packet payload as bytes
        '''
        # set FIFO address to current RX address
        # fifo_rx_current_addr = self.readRegister(REG_FIFO_RX_CURRENT_ADDR)
        self.writeRegister(REG_FIFO_ADDR_PTR,
                           self.readRegister(REG_FIFO_RX_CURRENT_ADDR))

        # read packet length
        if self._implicitHeaderMode:
            packetLength = self.readRegister(REG_PAYLOAD_LENGTH)
        else:
            packetLength = self.readRegister(REG_RX_NB_BYTES)

        payload = bytearray()
        for i in range(packetLength):
            payload.append(self.readRegister(REG_FIFO))

        gc.collect()
        return bytes(payload)

    def readRegister(self, address, byteorder='big', signed=False):
        ''' Allocate a since byte bytearray to hold the response of reading a
            register.

            :param byte address: register address to read
            :param str byteorder: indicate significant bit ordering
            :param bool signed: indicate if byte is a signed value
            :rtype: int
            :return: integer representation of byte read from register
        '''
        response = bytearray(1)
        self.ss.off()
        self.spi.write(bytes([address & 0x7F]))
        self.spi.write_readinto(bytes([0x00]), response)
        self.ss.on()
        return int.from_bytes(response, byteorder)

    def writeRegister(self, address, value):
        ''' Write value to register address

            :param byte address: address to write with value
            :param byte value: byte value, will be OR'd with 0x80
            :rtype: int
            :return: Integer represetation of response
        '''
        response = bytearray(1)
        self.ss.off()
        self.spi.write(bytes([address | 0x80]))
        self.spi.write_readinto(bytes([value]), response)
        self.ss.on()
        return int.from_bytes(response, 'big')
