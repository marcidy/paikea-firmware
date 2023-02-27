"""
Storage
-------

The storage module is an interface for an underlying btree key/value store on
the flash filesystem.  All values are stored as binary values, but this
module uses ascii strings to specify them and handles the coding.
"""
from core.compat import btree

#: Default filename for the file holding the database on the filesystem
CORE_STORAGE = "data"


def init():
    ''' Initialize the storage file on the flash filesystem.  Only needs to
        be run once, this creates a file and initializes the btree database
        with a single key/value of 'MODE': 'INIT'.
    '''
    with open(CORE_STORAGE, 'w+b') as f:
        db = btree.open(f)
        db[b"MODE"] = b"INIT"
        db.close()


def get(item):
    ''' Retrieves a value from the btree database.

        :param ascii item: Key for value to retrieve
        :rtype: str
        :return: Vale for key or None

    '''
    value = None
    with open(CORE_STORAGE, 'r+b') as f:
        db = btree.open(f)
        b_item = item.encode('ascii')
        value = db.get(b_item)
        if value:
            value = value.decode('ascii')
        db.close()
    return value


def put(item, value):
    ''' Add value to database at location specified by key.

        :param ascii item: Key for database
        :param ascii value: Value to store

    '''
    b_item = None
    b_value = None
    try:
        b_item = item.encode('ascii')
        b_value = value.encode('ascii')
    except AttributeError:
        print("storage items and values must be ascii strings")
        return False

    if b_item and b_value:
        with open(CORE_STORAGE, 'r+b') as f:
            db = btree.open(f)
            db[b_item] = b_value
            db.flush()
            db.close()
        return True


def rm(item):
    ''' Removes a key/value pair by key

        :param ascii item: Item to delete

    '''
    b_item = None
    try:
        b_item = item.encode('ascii')
    except AttributeError:
        print("Storage items and values must be ascii strings")
        return False

    if b_item:
        with open(CORE_STORAGE, 'r+b') as f:
            db = btree.open(f)
            if b_item in db:
                del db[b_item]
                db.flush()
                db.close()
                return True
            else:
                print("Item {} not found.".format(item))
                db.close()
                return False

def items():
    items = {}
    with open(CORE_STORAGE, 'r+b') as f:
        db = btree.open(f)

        for k, v in db.items():
            items[k] = v
    return items
