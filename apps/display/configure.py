from .elements import (
    Element,
    Selectable,
    Text,
    GPSCoord,
    Heading,
    Speed,
    Distance,
    DistanceUnits,
    Display,
    Arrow,
    LastMileIndicator,
)
from .font import (
    main_10r,
    main_15r,
    main_20r,
)
from .controllers import (
    ui_data,
    flasher,
)


def configure_messages():
    button1 = Element((0, 0), 44, 25)
    button1.children = [Text((5, 5), "Back")]
    button2 = Element((44, 0), 44, 25)
    button2.children = [Text((15, 5), "Up")]
    button3 = Element((88, 0), 44, 25)
    button3.children = [Text((9, 5), "Down")]
    button4 = Element((132, 0), 44, 25)
    button4.children = [Text((6, 5), "Send")]

    menu = Element((0, 264-25), 176, 25, border=False)
    menu.children = [button1, button2, button3, button4]

    beacon_on = Selectable((0, 25), 176, 26)
    beacon_on.children = [Text((5, 10), "Turn Last Mile On")]

    def beacon_on_cb():
        ui_data.send(b"PK005;1")
        flasher("Sending", 3)

    beacon_on.set_callback(beacon_on_cb)

    ird_update_5 = Selectable((0, 50), 176, 26)
    ird_update_5.children = [Text((5, 10), "Set Buoy Update 5 min")]

    def ird5_cb():
        ui_data.send(b"PK006;5")
        flasher("Sending", 3)

    ird_update_5.set_callback(ird5_cb)

    ird_update_10 = Selectable((0, 75), 176, 26)
    ird_update_10.children = [Text((5, 10), "Set Buoy Update 10 min")]

    def ird10_cb():
        ui_data.send(b"PK006;10")
        flasher("Sending", 3)

    ird_update_10.set_callback(ird10_cb)

    ird_update_15 = Selectable((0, 100), 176, 26)
    ird_update_15.children = [Text((5, 10), "Set Buoy Update 15 min")]

    def ird15_cb():
        ui_data.send(b"PK006;15")
        flasher("Sending", 3)

    ird_update_15.set_callback(ird15_cb)

    beacon_off = Selectable((0, 125), 176, 26)
    beacon_off.children = [Text((5, 10), "Turn Last Mile Off")]

    def beacon_off_cb():
        ui_data.send(b"PK005;0")
        flasher("Sending", 3)

    beacon_off.set_callback(beacon_off_cb)

    messages = Display((0, 0), 176, 264)
    messages.children = [
        menu,
        beacon_on,
        ird_update_5,
        ird_update_10,
        ird_update_15,
        beacon_off
    ]
    messages.selectables = [
        beacon_on,
        ird_update_5,
        ird_update_10,
        ird_update_15,
        beacon_off
    ]
    messages.init_selected()
    return messages


def configure_main():
    msg_button = Element((0, 0), 44, 45)
    msg_button.children = [Text((10, 5), "CMD")]
    data_button = Element((45, 0), 44, 45)
    data_button.children = [Text((5, 5), "Data")]
    pwr_button = Element((132, 0), 44, 45)
    pwr_button.children = [Text((2, 5), "Power")]

    menu = Element((0, 264-25), 176, 25, border=False)
    menu.children = [msg_button, data_button, pwr_button]

    dist = Distance((60, 20), "N/A", font=main_20r)
    head = Text((60, 0), "N/A", font=main_20r)
    # dist_u = DistanceUnits((85, 0), "km", font=main_20r)
    dist_pane = Element((0, 156), 176, 20, border=False)

    dist_pane.children = [
        # Text((5, 5), "Distance"),
        Text((0, 0), "Head:", font=main_20r),
        head,
        Text((0, 20), "Dist:", font=main_20r),
        dist,
        # dist_u,
    ]
    arrow = Arrow((0, 10), 136, 176, border=True)

    indicator_pane = Element((0, 195), 176, 40, border=False)

    my_utc = Text((60, 0), "00:00:00", font=main_20r)
    tg_utc = Text((60, 20), "00:00:00", font=main_20r)
    tg_src = Text((160, 20), "N", font=main_20r)
    indicator_pane.children = [
        Text((0, 0), "Time:", font=main_20r),
        Text((0, 20), "Last:", font=main_20r),
        # Text((120, 20), "Source"),
        my_utc,
        tg_utc,
        tg_src,
    ]

    main_display = Display((0, 0), 176, 264, border=False)
    main_display.children = [
        menu,
        arrow,
        dist_pane,
        indicator_pane,
    ]
    ui_data.register('dist', dist, 'value')
    ui_data.register('my_utc', my_utc, 'value')
    ui_data.register('tg_utc', tg_utc, 'value')
    ui_data.register('tg_src', tg_src, 'value')
    ui_data.register('angle', arrow, 'angle')
    ui_data.register('locked', arrow, 'locked')
    ui_data.register('turn', head, 'value')
    main_display.init_selected()
    return main_display


def configure_flash():
    flash_display = Element((0, 0), 175, 20)
    flash_text = Text((5, 2), "")
    flash_display.children = [flash_text]
    ui_data.register('flash', flash_text, 'value')
    return flash_display


def configure_power():
    button1 = Element((0, 0), 44, 25)
    button1.children = [Text((5, 5), "Back")]
    button2 = Element((44, 0), 44, 25)
    button2.children = [Text((15, 5), "Up")]
    button3 = Element((88, 0), 44, 25)
    button3.children = [Text((9, 5), "Down")]
    button4 = Element((132, 0), 44, 25)
    button4.children = [Text((5, 5), "Select", font=main_10r)]

    menu = Element((0, 264-25), 176, 25, border=False)
    menu.children = [
        button1,
        button2,
        button3,
        button4]

    power_off = Selectable((0, 50), 176, 26)
    power_off.children = [Text((5, 10), "Power Off")]

    batt_label = Text((0, 25), "Battery: ")
    batt_display = Text((100, 25), "100")

    def power_off_cb():
        print("power off!")
        ui_data.send(b"CMD;001\r\n")
        ui_data.shutdown()

    power_off.set_callback(power_off_cb)

    ota = Selectable((0, 75), 176, 26)
    ota.children = [Text((5, 5), "Switch to OTA")]

    def switch_to_ota_cb():
        print("switching to OTA")
        ui_data.send(b"CMD;002\r\n")
        ui_data.switch_to_ota()

    ota.set_callback(switch_to_ota_cb)

    power = Display((0, 0), 176, 264)
    power.children = [
        menu,
        batt_label,
        batt_display,
        power_off,
        ota,
    ]
    power.selectables = [
        power_off,
        ota
    ]
    power.init_selected()

    ui_data.register('st_batt', batt_display, 'value')

    return power


def configure_data():
    button1 = Element((0, 0), 44, 25)
    button1.children = [Text((5, 5), "Back")]

    menu = Element((0, 264-25), 176, 25, border=False)
    menu.children = [button1, ]

    my_loc = Element((0, 30), 176, 80, border=False)

    my_utc = Text((60, 1), "00:00:00", font=main_15r)
    my_lat = GPSCoord((50, 15), "00 0\" 0", font=main_15r)
    my_lon = GPSCoord((50, 30), "00 0\" 0", font=main_15r)
    my_head = Heading((80, 45), "0", font=main_15r)
    my_speed = Speed((70, 60), "0", font=main_15r)

    my_loc.children = [
        Text((2, 1), "Boat", font=main_15r),
        my_utc,
        Text((10, 15), "Lat:", font=main_15r),
        my_lat,
        Text((10, 30), "Lon:", font=main_15r),
        my_lon,
        Text((10, 45), "Course:", font=main_15r),
        my_head,
        Text((10, 60), "Speed:", font=main_15r),
        my_speed,
    ]

    tg_loc = Element((0, 120), 176, 115, border=False)

    tg_utc = Text((60, 1), "00:00:00", font=main_15r)
    tg_lat = GPSCoord((50, 16), "00 0\" 0", font=main_15r)
    tg_lon = GPSCoord((50, 32), "00 0\" 0", font=main_15r)
    tg_head = Heading((80, 48), "0", font=main_15r)
    tg_speed = Speed((70, 64), "0", font=main_15r)
    tg_src = Text((120, 80), "N", font=main_15r)
    tg_lastmile = LastMileIndicator((100, 96), "N/A", font=main_15r)

    tg_loc.children = [
        Text((2, 1), "Buoy", font=main_15r),
        tg_utc,
        Text((10, 16), "Lat:", font=main_15r),
        tg_lat,
        Text((10, 32), "Lon:", font=main_15r),
        tg_lon,
        Text((10, 48), "Course:", font=main_15r),
        tg_head,
        Text((10, 64), "Speed:", font=main_15r),
        tg_speed,
        Text((10, 80), "Msg Source:", font=main_15r),
        tg_src,
        Text((10, 96), "Last Mile:", font=main_15r),
        tg_lastmile,
    ]

    data_display = Display((0, 0), 176, 264, border=False)
    data_display.children = [
        menu,
        my_loc,
        tg_loc,
    ]

    ui_data.register('my_lat', my_lat, 'value')
    ui_data.register('my_lon', my_lon, 'value')
    ui_data.register('my_cog', my_head, 'value')
    ui_data.register('my_sog', my_speed, 'value')
    ui_data.register('tg_lat', tg_lat, 'value')
    ui_data.register('tg_lon', tg_lon, 'value')
    ui_data.register('tg_cog', tg_head, 'value')
    ui_data.register('tg_sog', tg_speed, 'value')
    ui_data.register('tg_src', tg_src, 'value')
    ui_data.register('my_utc', my_utc, 'value')
    ui_data.register('tg_utc', tg_utc, 'value')
    ui_data.register('st_target', tg_lastmile, 'value')
    return data_display
