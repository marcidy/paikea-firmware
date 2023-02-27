def convert_dd(dd):
    ''' Decimal to deg, min, sec'''
    degs, mins = dd.split(".")
    d = int(degs)
    mins = float("0.{}".format(mins))
    m = int(60 * mins)
    s = 3600 * mins - 60 * m
    return {'deg': d, 'min': m, 'sec': s}


def convert_dms(d, m, s):
    ''' deg min sec to decimal degrees'''
    return {'dd': d + m/60 + s/3600}


def convert_degdm(value):
    ''' [-][D]DDMM.mmmm to deg decimal mins'''
    x, y = value.split(".")
    b = x[-2:]
    a = x[:-2]
    degs = int(a)
    dcms = float(b + "." + y)/60
    if degs >= 0:
        return degs + dcms
    if degs < 0:
        return degs - dcms


def convert_nmea(value):
    if value > 0:
        return(value // 1) * 100 + (value % 1) * 60
    else:
        return -((abs(value) // 1) * 100 + (abs(value) % 1) * 60)
