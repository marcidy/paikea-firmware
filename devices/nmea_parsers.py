"""
NMEA Sentence Parsers
---------------------

These functions all take in a populated NMEA protocol sentence and
parses them per the NMEA 0183 specification.

They all output a dictionary with keys and values based on the specific
sentence spec.

See any NMEA spec for the details for each sentence.
"""


def gga(nmea_data):
    data = nmea_data.datafields.split(nmea_data.spec.datafield_delimiter)
    result = {}
    result["utc"] = data[0]
    result["latitude"] = data[1]
    result["NS"] = data[2]
    result["longitude"] = data[3]
    result["EW"] = data[4]
    result["fix"] = data[5]
    result["sats_used"] = data[6]
    result["hdop"] = data[7]
    result["msl_alt"] = data[8]
    result["msl_alt_units"] = data[9]
    result["geo_sep"] = data[10]
    result["geoid_units"] = data[11]
    result["age_of_diff_corr"] = data[12]
    result["dgps_station_id"] = data[13]
    return result


def gsa(nmea_data):
    data = nmea_data.datafields.split(nmea_data.spec.datafield_delimiter)
    result = {}
    result["fix_mode1"] = data[0]
    result["fix_mode2"] = data[1]
    result["satellites_used"] = data[2:14]
    result["pdop"] = data[14]
    result["hdop"] = data[15]
    result["vdop"] = data[16]
    return result


def rmc(nmea_data):
    data = nmea_data.datafields.split(nmea_data.spec.datafield_delimiter)
    result = {}
    skip = 0
    result["utc"] = data[0 - skip]
    result["status"] = data[1 - skip]
    result["latitude"] = data[2 - skip]
    if not data[2 - skip]:
        skip += 1
    else:
        result["NS"] = data[3 - skip]
    result["longitude"] = data[4 - skip]
    if not data[4 - skip]:
        skip += 1
    else:
        result["EW"] = data[5 - skip]
    result["speed_over_ground"] = data[6 - skip]
    result["speed_over_course"] = data[7 - skip]
    result["date"] = data[8 - skip]
    result["mag_var"] = data[9 - skip]
    result["mode"] = data[10 - skip]
    return result


def vtg(nmea_data):
    data = nmea_data.datafields.split(nmea_data.spec.datafield_delimiter)
    result = {}
    result["t_course"] = data[0]
    result["t_ref"] = data[1]
    result["m_course"] = data[2]
    result["m_ref"] = data[3]
    result["nautical_speed"] = data[4]
    result["nautical_speed_units"] = data[5]
    result["ground_speed"] = data[6]
    result["ground_speed_units"] = data[7]
    # nmea_data.mode = data[8]  Track down this spec
    return result


def gsv(nmea_data):
    data = nmea_data.datafields.split(nmea_data.spec.datafield_delimiter)
    result = {}
    if len(data) < 6:
        return {}
    result['msgs'] = data[0]
    result['seq_num'] = data[1]
    result['num_sv'] = data[2]
    result['sv_prn'] = data[3]
    result['elevation'] = data[4]
    result['azimuth'] = data[5]
    result['snr'] = data[6]
    # This is not yet done
    return result


#: Parsers for sentences expected from an MTK device.  The sentences with
#: lambda are dummy parsers for sentences we don't care about.
#: The keys are used to route sentences to the specific parser.
MTK_PARSERS = {'gsa': gsa,
               'gga': gga,
               'rmc': rmc,
               'vtg': vtg,
               'gsv': gsv,
               'gll': lambda x: {},
               'tk010': lambda x: {},
               'tk011': lambda x: {},
               'ack': lambda x: {}}
