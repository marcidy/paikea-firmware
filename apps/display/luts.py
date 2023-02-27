'''
are black positive and white negative?
based on stock LUTs,

VCOM always -1.0
BB tables end on 11V
WB tables end on -11V
BW tables end on 10.6V (why not 11)
tables end on -11V

weird.
'''

PWR = [0x03, 0x00, 0x2b, 0x2b, 0x29]
VCM_DC_SETTING = [0x12]
lut_labels = ["GND", "VDH", "VDL", "VDHR"]
vcom_labels = ["VCOM_DC", "VCOM_H", "VCOM_L", "FLOAT"]


def power():
    VCOM_DC = max(-3.0, -0.05*(VCM_DC_SETTING[0] & 0x3F) + -.10)
    VDG_EN = PWR[0] & 0x01
    VDS_EN = (PWR[0] & 0x02) >> 1
    VCOM_HV = (PWR[1] & 0x40) >> 2
    VGHL_LV = (PWR[1] & 0x03)
    VDH = (PWR[2] & 0x3F)
    VDL = (PWR[3] & 0x3F)
    VDHR = (PWR[4] & 0x7F)

    VGH = float(16-VGHL_LV)
    VGL = -VGH
    VDH_V = min(2.4 + VDH*0.2, 11.0)
    VDL_V = max(-11, -2.4 - VDL*0.2)
    VDHR_V = min(2.4 + 0.2*VDHR, 11.0)
    VCOMH = [VDH_V + VCOM_DC, VGH][VCOM_HV]
    VCOML = [VDL_V + VCOM_DC, VGL][VCOM_HV]
    values = {
        "VDG_EN": VDG_EN,
        "VDS_EN": VDS_EN,
        "VCOM_DC": VCOM_DC,
        "VCOM_H": VCOMH,
        "VCOM_L": VCOML,
        "VDHR": round(VDHR_V, 1),
        "VDH": VDH_V,
        "VDL": VDL_V,
        "GND": 0,
        "FLOAT": "FLT",
    }
    return values


f0 = 3
f1 = 3
f2 = 11
f3 = 0
rep = 1
lut_vcom_dc = [
          0xF0, f0, f1, f2, f3, rep,
          0x00, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x00, 0x0E, 0x01, 0x0E, 0x01, 0x00,
          0x00, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x00, 0x04, 0x10, 0x00, 0x00, 0x00,
          0x00, 0x03, 0x0E, 0x00, 0x00, 0x00,
          0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
          0x00, 0x00,
      ]
lut_ww = [
          0xAA, f0, f1, f2, f3, rep,
          0x00, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x80, 0x0E, 0x01, 0x0E, 0x01, 0x00,
          0x80, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x80, 0x04, 0x10, 0x00, 0x00, 0x00,
          0x80, 0x03, 0x0E, 0x00, 0x00, 0x00,
          0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
      ]
lut_bw = [
          0x6A, f0, f1, f2, f3, rep,
          0x00, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x80, 0x0E, 0x01, 0x0E, 0x01, 0x00,
          0x80, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x80, 0x04, 0x10, 0x00, 0x00, 0x00,
          0x80, 0x03, 0x0E, 0x00, 0x00, 0x00,
          0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
      ]
lut_wb = [
          0x95, f0, f1, f2, f3, rep,
          0x40, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x40, 0x0E, 0x01, 0x0E, 0x01, 0x00,
          0x40, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x40, 0x04, 0x10, 0x00, 0x00, 0x00,
          0x40, 0x03, 0x0E, 0x00, 0x00, 0x00,
          0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
      ]
lut_bb = [
          0x55, f0, f1, f2, f3, rep,
          0x40, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x44, 0x0E, 0x01, 0x0E, 0x01, 0x00,
          0x40, 0x0A, 0x0A, 0x00, 0x00, 0x00,
          0x40, 0x04, 0x10, 0x00, 0x00, 0x00,
          0x40, 0x03, 0x0E, 0x00, 0x00, 0x00,
          0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
      ]

all_luts = {'VCOM': lut_vcom_dc,
            'WW': lut_ww,
            'BW': lut_bw,
            'WB': lut_wb,
            'BB': lut_bb, }


def compare():
    volts = power()
    names = list(all_luts.keys())
    luts = list(all_luts.values())
    print("| {:^12} | {:^12} | {:^12} | {:^12} | {:^12} |".format(*names))
    for phrase_num in range(0, 42, 6):
        print(76*"-")
        for level in range(4):
            phrase_str = "| "
            for i, lut in enumerate(luts):
                phrase = lut[phrase_num:phrase_num+6]
                bits = 6 - 2*level
                lv_num = (phrase[0] & (0x03 << bits)) >> bits
                frames = phrase[1+level]
                if i == 0:
                    phrase_str += "{:^8}{:>4} | ".format(volts[vcom_labels[lv_num]], frames)
                else:
                    phrase_str += "{:^8}{:>4} | ".format(volts[lut_labels[lv_num]], frames)

            print(phrase_str)


def lut_wave(lut, labels):
    volts = power()
    total = 0
    for wave_num in range(0, len(lut), 6):
        wave = lut[wave_num:wave_num+6]
        levels = wave[0]
        l0 = (levels & 0xC0) >> 6
        l1 = (levels & 0x30) >> 4
        l2 = (levels & 0x0C) >> 2
        l3 = (levels & 0x03)
        frames0 = wave[1]
        frames1 = wave[2]
        frames2 = wave[3]
        frames3 = wave[4]
        repeat = wave[5]

        ftotal = wave[1] + wave[2] + wave[3] + wave[4]
        # print(f"level: {volts[labels[l0]]}, frames: {frames0}")
        # print(f"level: {volts[labels[l1]]}, frames: {frames1}")
        # print(f"level: {volts[labels[l2]]}, frames: {frames2}")
        # print(f"level: {volts[labels[l3]]}, frames: {frames3}")
        # print(f"repeat: {repeat}")
        # print(f"total frames: {ftotal}")
        total += ftotal * (repeat + 1)
    # print(f"Wave Frames: {total}")


def bb():
    print("LUT_BB")
    lut_wave(lut_bb, lut_labels)
    print("")


def vcom():
    print("VCOM")
    lut_wave(lut_vcom_dc[:-2], vcom_labels)
    print("")


def bw():
    print("LUT_BW")
    lut_wave(lut_bw, lut_labels)
    print("")


def ww():
    print("LUT_WW")
    lut_wave(lut_ww, lut_labels)
    print("")


def wb():
    print("LUT_WB")
    lut_wave(lut_wb, lut_labels)
    print("")
