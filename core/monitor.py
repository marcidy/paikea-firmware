"""
Monitor
-------

This async based module is used to monitor an external connection to a server
which responds to a healtch check rquest with 200 OK.
"""
import uasyncio
from .support import net
from . import urequests


events = {
    'server': uasyncio.Event(),
    'wifi': uasyncio.Event(),
    'connection': uasyncio.Event(),
}


async def wifi_check():
    ''' Check the network health and set the wifi event if OK, clear if it not
    '''
    wifi = events['wifi']
    if net.healthcheck():
        wifi.set()
    else:
        wifi.clear()


async def server_check(uri):
    ''' Connect to external server at provided uri and expect a 200 OK response
        Set the server event if OK, clear it if not

        :param str uri: URI for a healthcheck endpoint

    '''
    server = events['server']

    try:
        resp = urequests.get(uri)
        if resp.status_code == 200 and resp.content == b"OK":
            server.set()
        else:
            server.clear()
    except Exception as e:
        print(e)
        server.clear()


async def wifi_disconnect():
    ''' Async coroutine to disconect from the Wifi '''
    net.net.disconnect()


async def wifi_connect():
    ''' Async coroutine to connect to the WiFi '''
    net.connect()


async def connection_check():
    ''' Async coroutine to check up on the extenal connection.  Runs on a
        50ms oeriod.
    '''
    # the connection event is used to communicate externally
    wifi = events['wifi']
    server = events['server']
    connection = events['connection']
    while True:
        if not wifi.is_set() or not server.is_set():
            connection.clear()
        await wifi.wait()
        await server.wait()
        if wifi.is_set() and server.is_set():
            connection.set()
        await uasyncio.sleep_ms(50)


async def maintain():
    ''' Async coroutine to check connection to external server.  Runs every
        10s
    '''
    wifi = events['wifi']
    server = events['server']
    hc_uri = "https://server.hostname.com/connection/hc"

    while True:
        if not wifi.is_set():
            server.clear()
            await wifi_disconnect()
            await uasyncio.sleep_ms(250)
            await wifi_connect()

        while not wifi.is_set():
            await wifi_check()
            await uasyncio.sleep_ms(250)

        await server_check(hc_uri)
        if not server.is_set():
            wifi.clear()

        await uasyncio.sleep(10)


async def app_main():
    ''' Async entrypoint for the module '''
    uasyncio.create_task(connection_check())
    uasyncio.create_task(maintain())
