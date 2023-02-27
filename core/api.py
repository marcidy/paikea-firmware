"""
Core API
--------
The Core API communicates with the server over the network using http
requests.  Parameters like device identification and server URIs are
retrieved via the core.storage module.
"""


import gc
from core import urequests
from core import storage


def _req(ep=None, params=None):
    ''' Internal request helper function to format api requests and forward
        them to the server.

        :param str ep: server endpoint without leading slash
        :param dict params: data to be json encoded

    '''
    url = storage.get("SERVER")

    if ep:
        url += "/" + ep

    try:
        resp = urequests.post(url=url, json=params)
    except OSError as e:
        print("Post request failed: OSError")
        raise e

    if resp.status_code != 200:
        raise ValueError("API request failed: {}".format(resp.status_code))

    try:
        data = resp.json()
        return data
    except Exception as e:
        print(e)
        raise ValueError("No JSON data")


def register(params=None):
    ''' Register the device with the server.  Targets the /register end point.

        A device type stored as "DEV" is required in order to properly register
        the device.

        If the device has an ID stored, will be sent to the server for
        registration, though it's preferred to let the server identify the
        device.

        If successful, the server will respond with an identity to use, which
        will be stored on the device as IAM.
    '''
    params = {} if not params else params

    dev_type = storage.get("DEV")
    if not dev_type:
        raise ValueError("Device Type required!")

    iam = storage.get("IAM")
    if iam:
        params['iam'] = iam

    ep = '{}/register'.format(dev_type)
    result = _req(ep, params)

    if 'iam' in result:
        if result['iam'] == iam:
            return
        else:
            storage.put("IAM", result['iam'])
            return

    else:
        raise ValueError("Registration Failed: {}".format(result))


def req(ep=None, params=None):
    ''' Retrieves the device type and id to construct the device specific
        endpoint prefix for use with registered devices.  If the device isn't
        registerd, this will fail.

        This function should be used on all requests with registered devices.

        :param str ep: Target endpoint
        :param dic params: end point parameters to be json encoded
        :rtype: core.urequests.Response
        :return: Response from server

    '''
    device_type = storage.get("DEV")
    iam = storage.get("IAM")

    _ep = "{}/{}".format(device_type, iam)
    if ep:
        _ep += "/" + ep
    return _req(ep=_ep, params=params)


def chunked_req(url, method="POST", target_path=None, json=None):
    """ Handled a request which expects to received chunked data.  This
        works-around the lack of support for chunked encoding in
        core.urequests.request.

        This is specifically required for handling large files sent by the
        server during a firmware update.

        :param str url: full url for request
        :param str method: request method
        :param str target_path: Where to store the response data
        :param dict json: data to send to server

    """
    import socket
    try:
        proto, _, host, path = url.split("/", 3)
    except ValueError:
        proto, _, host = url.split("/", 2)
        path = ""
    if proto == "http:":
        port = 80
    elif proto == "https:":
        import ussl
        port = 443
    else:
        raise ValueError("Unsupported Protocol: " + proto)

    if ":" in host:
        host, port = host.split(":")
        port = int(port)

    ai = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    ai = ai[0]

    sock = socket.socket(ai[0], ai[1], ai[2])
    try:
        data = None
        sock.connect(ai[-1])
        if proto == "https:":
            sock = ussl.wrap_socket(sock, server_hostname=host)
        sock.write(b"%s /%s HTTP/1.0\r\n" % (method, path))
        sock.write(b"Host: %s\r\n" % host)
        if json is not None:
            import ujson
            data = ujson.dumps(json)
            sock.write(b"Content-Type: application/json\r\n")
            sock.write(b"Content-Length: %d\r\n" % len(data))
            # sock.write(b"Transfer-Encoding: chunked\r\n")
        sock.write(b"\r\n")
        if data:
            sock.write(data)

        head = sock.readline()
        head = head.split(None, 2)
        status = int(head[1])
        reason = ""
        fsize = 0
        if len(head) > 2:
            reason = head[2].rstrip()
        while True:
            head = sock.readline()
            if not head or head == b"\r\n":
                break
            if head.startswith(b"Location:") and not 200 <= status <= 299:
                raise NotImplementedError("Redirects not yet supported")
            if head.startswith(b"Content-Length:"):
                fsize = int(head.rstrip().split(b":")[1].strip())

        chunk_size = 1024
        with open(target_path, 'wb') as dest:
            while fsize > 0:
                to_read = min(fsize, chunk_size)
                dest.write(sock.read(to_read))
                fsize -= to_read

    except OSError as e:
        sock.close()
        gc.collect()
        raise e
    gc.collect()


def req_file(target_path, ep=None, params=None):
    """ Helper to simplifiy the request of large files from the server.
        Constructs the request from retrieved device data and executes a
        chunked_req.

        Retrieves device specific information and prepends to endpoint.

        :param str target_path: filesystem location for response contente
        :param str ep: server endpoint
        :param dict params: params passed to request, eventually json encoded

    """
    url = storage.get("SERVER")
    device_type = storage.get("DEV")
    iam = storage.get("IAM")

    _ep = "/{}/{}".format(device_type, iam)
    if ep:
        _ep += "/" + ep

    try:
        chunked_req(url=url + _ep, json=params, target_path=target_path)
    except OSError:
        raise ValueError("Post request failed")

    gc.collect()
