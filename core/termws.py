"""
Websocket Terminal
------------------
Experimental websocket terminal.  Has problems and doens't work well
"""
import os
import uio as io
import uasyncio
from .websockets import client


class QueueEmpty(Exception):
    ''' Exception used with the async Queue implementation to indicate queue
        is empty on a get
    '''
    pass


class QueueFull(Exception):
    ''' Exception used with the async Queue implementation to indicate queue
    is full on a put
    '''
    pass


class Queue:
    ''' Async Queue implementation '''
    def __init__(self, maxsize=0):
        self.maxsize = maxsize
        self._queue = []
        self._evput = uasyncio.Event()
        self._evget = uasyncio.Event()

    def _get(self):
        self._evget.set()
        self._evget.clear()
        return self._queue.pop(0)

    async def get(self):
        ''' Async get, notifies coroutines waiting for a spot to put if queue
            was full before get

            :return: Oldest item from queue
            '''
        while self.empty():
            await self._evput.wait()
        return self._get()

    def get_nowait(self):
        ''' Synchronous get, raises QueueEmpty if no items in the Queue

            :return: Oldest item from the queue
            :raises: QueueEmpty
        '''
        if self.empty():
            raise QueueEmpty()
        return self._get()

    def _put(self, val):
        self._evput.set()
        self._evput.clear()
        self._queue.extend(val)

    async def put(self, val):
        ''' Async put, notifies coroutines waiting for items if queue was
            empty before put

            :param val: item to place at the back of the queue

        '''
        while self.full():
            await self._evget.wait()
        self._put(val)

    def put_nowait(self, val):
        ''' Synchronous put, raises QueueFull if Queue is full.

            :param val: Item to place in back of queue

        '''
        if self.full():
            raise QueueFull()
        self._put(val)

    def qsize(self):
        ''' Size of the queue

            :rtype: int
            :return: length of queue

        '''
        return len(self._queue)

    def empty(self):
        ''' Check if queue is empty.

            :rtype: bool
            :return: True if queue is empty, else False

        '''
        return len(self._queue) == 0

    def full(self):
        ''' Check if queue is full.

            :rtype: bool
            :return: True if queue is full, else False

        '''
        return self.maxsize > 0 and self.qsize() >= self.maxsize

    def clear(self):
        ''' Empty the queue '''
        self._queue.clear()


class ReverseShell(io.IOBase):
    ''' An IO class for use with os.dupterm which will buffer terminal output
        to a send Queue and pass input from a receive queue to the terminal
        input.
    '''

    def __init__(self, recv_q, send_q):
        self.recv_buf = recv_q
        self.send_buf = send_q

    def ioctl(self, arg, val):
        ''' ioctl interface '''
        pass

    def readinto(self, buf, n=1):
        ''' readinto is called by os.dupterm with data to write to interpretter
            from duplicated terminal.

            :param bytes buf: single byte buffer which will receive data
            :param int n: number of bytes to read, currently 1 with micropython
        '''
        # lock the buffer?
        if not self.recv_buf.empty():
            buf[0] = self.recv_buf.get_nowait()
            return 1
        else:
            return None  # or 0?

    def write(self, buf):
        ''' Add passed buffer to terminal send buffer.

            :param bytes buf: bytes to send
        '''
        # lock the buffer?
        self.send_buf.put_nowait(buf)

    def clear(self):
        ''' Clear underlying queues '''
        self.send_buf.clear()
        self.recv_buf.clear()


async def receiver(recv_q, ws, path):
    ''' Task to receive data from a websocket adn add it into the received data
        queue.  Dupterm.notify is called to notify the main interpretter that
        data is available.

        :param Queue recv_1: async queue to which data is added
        :param websocket ws: websocket connection which is sending data
        :param str path: websocket uri endpoint of connection

    '''
    print("starting receiver")
    async for msg in ws:
        print(msg)
        if isinstance(msg, str):
            await recv_q.put(msg.encode('utf-8'))
            os.dupterm_notify(None)


async def sender(send_q, ws, path):
    ''' Task which monitors a queue of data to send and outputs it over a
        websocket.

        :param Queue send_q: Asynchronous queue
        :param websocket ws: websocket over which to send data
        :param websocket path: websocket uri endpoint of connection

    '''
    print("starting sender")
    while True:
        data = await send_q.get()
        await ws.send(bytes([data]).decode('utf-8'))

#: Hold module tasks
tasks = []
#: Module events
events = {
    'connected': uasyncio.Event(),
    'cancel': uasyncio.Event(),
}


async def connect(server):
    ''' Async coroutine to establish a websocket connection with an external
        server.

        :param str server: Websocket server uri
    '''

    connected = events['connected']
    cancel = events['cancel']
    trying = False
    while not cancel.is_set():
        if not connected.is_set() and not trying:
            try:
                ws = await client.connect(server)
                if ws:
                    uasyncio.create_task(start_term(ws))
            except Exception:
                uasyncio.create_task(end_term())
                connected.clear()

        await uasyncio.sleep(5)
        trying = False
    connected.clear()
    uasyncio.create_task(end_term())


async def start_term(ws):
    ''' Asynchronous coroutine to configure the queues and ReverseShell when
        a connection is established.

        :param websocket ws: established websocket client

    '''
    print("Starting Term")
    recv_q = Queue()
    send_q = Queue()
    rshell = ReverseShell(recv_q, send_q)
    tasks.append(uasyncio.create_task(receiver(recv_q, ws, "/console")))
    tasks.append(uasyncio.create_task(sender(send_q, ws, "/console")))
    os.dupterm(rshell)
    os.dupterm_notify(None)
    print("Term started")
    events['connected'].set()


async def end_term():
    ''' Clean up the ReverseShell, tasks and queues when terminal is ended '''
    rshell = os.dupterm(None)
    while tasks:
        task = tasks.pop()
        task.cancel()

    if rshell:
        rshell.clear()
    print("Term ended")
