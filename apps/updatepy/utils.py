import os
import gc
import hashlib
import binascii
from core import api


def free_space():
    fs_stat = os.statvfs("/")
    return fs_stat[0]*fs_stat[3]


def deploy(from_dir, to_dir):
    for file in os.listdir(from_dir):
        os.rename(from_dir + "/" + file,
                  to_dir + "/" + file)


def dirs(path):
    out = []
    for file in os.listdir(path):
        if os.stat(path + "/" + file)[0] & 2**14:
            if path[-1] == "/":
                out.append(path + file)
            else:
                out.append(path + "/" + file)

    return out


def dir_size(full_path):
    size = 0
    stat = os.stat(full_path)
    is_dir = stat[0] & 2**14
    is_file = stat[0] & 2**15

    if is_file:
        return stat[6]

    if is_dir:
        for file in os.listdir(full_path):
            size += dir_size(full_path + "/" + file)

    return size


def remove_path(path):
    if ".." in path:
        raise ValueError("Don't traverse backwards")

    print(path)
    stat = os.stat(path)
    is_dir = stat[0] & 2**14
    is_file = stat[0] & 2**15

    if is_file:
        print("removing file: {}".format(path))
        os.remove(path)

    if is_dir:
        for file in os.listdir(path):
            remove_path(path + "/" + file)
        print("removing dir: {}".format(path))
        os.rmdir(path)


def create_path(path, base="/"):
    if path[0] == "/":
        branches = path[1:].split("/")
    else:
        branches = path.split("/")

    to_create = base
    for branch in branches:
        make = False
        to_create += "/" + branch

        try:
            stat = os.stat(to_create) # path exists
            if stat[0] & 2**14:  # it's a directory so don't make it
                make = False
            else:
                raise ValueError("File where path expected: {}".format(to_create))
        except OSError:
            make = True

        if make:
            os.mkdir(to_create)


def check_upgrade_job():
    params = {'cmd': 'check', 'space': free_space()}
    return api.req(ep="upgrade", params=params)


def init_upgrade_job():
    params = {'cmd': 'init'}
    return api.req(ep='upgrade', params=params)


def job_status(job_id):
    params = {'cmd': 'status', 'job_id': job_id}
    return api.req(ep="upgrade",  params=params)


def get_metadata(job_id):
    params = {'cmd': 'metadata', 'job_id': job_id}
    return api.req(ep='upgrade', params=params)


def hash_file(full_path):
    gc.collect()
    hash = hashlib.sha1()
    fsize = os.stat(full_path)[6]
    chunk_size = 2048
    with open(full_path, 'rb') as f:
        while fsize > 0:
            to_read = min(fsize, chunk_size)
            hash.update(f.read(to_read))
            fsize -= to_read
    gc.collect()
    return binascii.hexlify(hash.digest()).decode("ascii")


def get_file(job_id, get_file_path, put_file_path):
    params = {'cmd': 'get_file',
              'job_id': job_id,
              'file_path': get_file_path}
    gc.collect()
    api.req_file(put_file_path, ep='upgrade', params=params)
    gc.collect()


def complete(job_id, success):
    params = {'job_id': job_id,
              'cmd': 'complete',
              'status': bool(success)}
    api.req(ep='upgrade', params=params)
