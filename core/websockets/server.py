"""
Websocket Server
----------------

Async based websocket server
"""
import ubinascii
import uhashlib
import uasyncio
import re
from .protocol import Websocket


class WebsocketServer(Websocket):
    ''' Websocket Server Object '''
    is_client = False


REQ_RE = re.compile(
    r'^(([^:/\\?#]+):)?' +  # scheme                # NOQA
    r'(//([^/\\?#]*))?' +   # user:pass@hostport    # NOQA
    r'([^\\?#]*)' +         # route                 # NOQA
    r'(\\?([^#]*))?' +      # query                 # NOQA
    r'(#(.*))?')            # fragment              # NOQA


def make_respkey(webkey):
    ''' Create a response key from a given websocket webkey.

        :param bytes webkey: webkey provided by server
        :rtype: bytes
        :return: response webkey
    '''
    d = uhashlib.sha1(webkey)
    d.update(b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
    respkey = d.digest()
    return ubinascii.b2a_base64(respkey).strip()


async def connect(reader, writer, cb):
    ''' Perform websocket server handshake and execute the passed callback
        when successful.

        :param stream reader: async stream
        :param stream writer: async stream
        :param coroutine cb: callback coroutine to run as an async task

    '''
    webkey = None

    request = await reader.readline()

    method, uri, proto = request.split(b" ")
    m = re.match(REQ_RE, uri)
    path = m.group(5) if m else "/"

    while True:
        header = await reader.readline()
        if header == b'' or header == b'\r\n':
            break

        if header.startswith(b'Sec-WebSocket-Key:'):
            webkey = header.split(b":", 1)[1]
            webkey = webkey.strip()

    if not webkey:
        writer.close()
        await writer.wait_closed()
        return

    respkey = make_respkey(webkey)

    writer.write(b"HTTP/1.1 101 Switching Protocols\r\n")
    writer.write(b"Upgrade: websocket\r\n")
    writer.write(b"Connection: Upgrade\r\n")
    writer.write(b"Sec-WebSocket-Accept: " + respkey + b"\r\n")
    writer.write(b"Server: Micropython\r\n")
    writer.write(b"\r\n")
    await writer.drain()

    ws = WebsocketServer(writer)
    uasyncio.create_task(cb(ws, path))


async def serve(cb, host, port):
    ''' Start a websocket server which will promote the provided callback to
        a running task with a connected websocket on the provided host and
        port.

        :param coroutine cb: callback to execute on successful connection
        :param ip host: IP address on which to listen for connections
        :param int port: port on which to listen for connections

    '''
    async def _connect(reader, writer):
        await connect(reader, writer, cb)

    return await uasyncio.start_server(_connect, host, port)
