import gc
import time
import os
from apps.updatepy import utils
from core import storage
from core.support import net
from core.compat import machine


def app_init():
    # on reset, rever to ota app
    storage.put("APP", "ota")

    # requires support network up, server, and api registration
    net.connect()

    start_time = time.time()

    while time.time() - start_time < 30:
        if net.healthcheck():
            print("Got network")
            return True
        time.sleep(1)

    # network healthcheck failed, revert to ota app
    os.umount("/")
    time.sleep(1)
    machine.reset()


# upgrade loop
# 1. check for pending upgrade job
# 2. if no job, request a new job
# 3. check job status
# 4. if job status is no upgrade, clean-up, done, reboot into app
# 5. if job status is pending, loop
# 6. if job status is ready, get the job metadata
# 7. double check free space allows for upgrade
# 8. loop through files
# 9.


def update():
    job_id = None
    status = None
    size = None
    dirs = None
    files = None
    old_dirs = utils.dirs("/")
    rec_base = "/new"
    utils.create_path(rec_base)
    succeeded = False

    while True:
        if job_id is None:
            result = utils.check_upgrade_job()
            status = result['status']
            job_id = result['job_id']
            del result
            if status in [9, 10]:
                break
        else:
            if status == 0:
                result = utils.job_status(job_id=job_id)
                status = result['status']
                del result

            if status == 2:
                result = utils.get_metadata(job_id=job_id)
                dirs = result['dirs']
                size = result['size']
                files = result['files']
                del result

            if size:
                if size > .9 * utils.free_space():
                    raise ValueError("Probably don't have space")
            if dirs:
                for d in dirs:
                    utils.create_path(d, rec_base)
            if files:
                for fname, data in files.items():
                    print(fname, end=": ")
                    utils.get_file(job_id=job_id,
                                   get_file_path=fname,
                                   put_file_path=rec_base + "/" + fname)
                    rec_digest = utils.hash_file(rec_base + "/" + fname)
                    if rec_digest != data[1]:
                        raise ValueError("File didn't hash")
                    else:
                        print("hash OK")
                succeeded = True
                break

        gc.collect()
        time.sleep(5)

    if succeeded:
        deploy_update(old_dirs)
    else:
        utils.remove_path(rec_base)

    utils.complete(job_id, succeeded)


def deploy_update(old_dirs):
    if 'backup' in os.listdir("/"):
        utils.remove_path("/backup")
    os.mkdir("/backup")

    for dir in old_dirs:
        if dir in ['/new', '/backup']:
            continue
        print('old: {}'.format(dir))
        os.rename(dir, "/backup/" + dir)

    utils.deploy("/new", "/")
    os.rmdir("/new")  # fails if not empty


def app_main():
    app_init()
    try:
        update()
    except Exception:
        pass
    os.umount("/")
    time.sleep(1)
    machine.reset()
