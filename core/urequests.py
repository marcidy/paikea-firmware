"""
Micro Request
-------------

A rewrite of the micropython requests library.
"""


import usocket


class Response:
    """ Response object for the html request.  Handles the underlying socket"""

    def __init__(self, f):
        self.raw = f
        self.encoding = "utf-8"
        self._cached = None

    def close(self):
        """ Close and clean up the socket and cache """
        if self.raw:
            self.raw.close()
            self.raw = None
        self._cached = None

    @property
    def content(self):
        """ Reads the socket and caches the content.
            :rtype: bytes
            :return: Data read from the socket
        """
        if self._cached is None:
            try:
                self._cached = self.raw.read()
            finally:
                self.raw.close()
                self.raw = None
        return self._cached

    @property
    def text(self):
        """ Decode the response content per the expected encoding.
            :rtype: str
            :return: encoded content
        """
        return str(self.content, self.encoding)

    def json(self):
        """ Parse the response content as JSON data with the ujson library
            :rtype: dict
            :return: JSON data as a dict
        """
        import ujson
        return ujson.loads(self.content)


def request(method, url, data=None, json=None, headers={}, stream=None):
    """ Make an http request.

        :param str method: Request in ['GET', 'POST', 'HEAD', 'PUT',
            'PATCH', 'DELETE']
        :param bytes data: binary data to be send along with request
        :param dict json: dictionary of data to be convered to binary data
            using ujson
        :param dict headers: Headers to send with request
        :param None stream: Unused
        :raises: OSError when out of memory
    """
    try:
        proto, dummy, host, path = url.split("/", 3)
    except ValueError:
        proto, dummy, host = url.split("/", 2)
        path = ""
    if proto == "http:":
        port = 80
    elif proto == "https:":
        import ussl
        port = 443
    else:
        raise ValueError("Unsupported protocol: " + proto)

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
    ai = ai[0]

    s = usocket.socket(ai[0], ai[1], ai[2])
    try:
        s.connect(ai[-1])
        if proto == "https:":
            s = ussl.wrap_socket(s, server_hostname=host)
        s.write(b"%s /%s HTTP/1.0\r\n" % (method, path))

        if "Host" not in headers:
            s.write(b"Host: %s\r\n" % host)

        # Iterate over keys to avoid tuple alloc
        for k in headers:
            s.write(k)
            s.write(b": ")
            s.write(headers[k])
            s.write(b"\r\n")

        if json is not None:
            assert data is None
            import ujson
            data = ujson.dumps(json)
            s.write(b"Content-Type: application/json\r\n")

        if data:
            s.write(b"Content-Length: %d\r\n" % len(data))

        s.write(b"\r\n")

        if data:
            s.write(data)

        line = s.readline()
        line = line.split(None, 2)
        status = int(line[1])
        reason = ""

        if len(line) > 2:
            reason = line[2].rstrip()

        while True:
            line = s.readline()
            if not line or line == b"\r\n":
                break
            if line.startswith(b"Transfer-Encoding:"):
                if b"chunked" in line:
                    raise ValueError("Unsupported " + line)
            elif line.startswith(b"Location:") and not 200 <= status <= 299:
                raise NotImplementedError("Redirects not yet supported")
    except OSError:
        s.close()
        raise

    resp = Response(s)
    resp.status_code = status
    resp.reason = reason
    return resp


def head(url, **kw):
    ''' Wrapper around request to make a HEAD request '''
    return request("HEAD", url, **kw)


def get(url, **kw):
    ''' Wrapper around request to make a GET request '''
    return request("GET", url, **kw)


def post(url, **kw):
    ''' Wrapper around request to make a POST request '''
    return request("POST", url, **kw)


def put(url, **kw):
    ''' Wrapper around request to make a PUT request '''
    return request("PUT", url, **kw)


def patch(url, **kw):
    ''' Wrapper around request to make a PATCH request '''
    return request("PATCH", url, **kw)


def delete(url, **kw):
    ''' Wrapper around request to make a DELETE request '''
    return request("DELETE", url, **kw)
