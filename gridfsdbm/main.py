#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

"""
import io
import mmap
import pathlib
import inspect
from collections.abc import Mapping, MutableMapping
from typing import Any, Generic, Iterator, Union, List
import pymongo
import gridfs
import concurrent.futures
import multiprocessing as mp

import utils
# from . import utils



#######################################################
### Classes


class GridFSDBM(MutableMapping):
    """

    """
    def __init__(self, host: str='localhost', port: int=27017, database: str='db', flag: str = 'r', ttl: int=None):
        """

        """
        self._db = pymongo.MongoClient(host=host, port=port)[database]

        if flag == "r":  # Open existing database for reading only (default)
            write = False
        elif flag == "w":  # Open existing database for reading and writing
            write = True
        elif flag == "c":  # Open database for reading and writing, creating it if it doesn't exist
            write = True
        elif flag == "n":  # Always create a new, empty database, open for reading and writing
            write = True
            fs = gridfs.GridFS(self._db)

            files = fs.find({})

            while True:
                try:
                    f = files.next()
                    fs.delete(f._id)
                except:
                    break
        else:
            raise ValueError("Invalid flag")

        utils.set_indexes(self._db, ttl)

        self._ttl = ttl
        self._write = write


    def keys(self):
        fs = gridfs.GridFS(self._db)

        for key in fs.list():
            yield key

    def items(self, keys: List[str]=None):
        """

        """
        if keys is None:
            keys = self.keys()

            fs = gridfs.GridFSBucket(self._db)

            for key in keys:
                yield key, fs.open_download_stream_by_name(key)
        else:
            fs = gridfs.GridFS(self._db)

            files = fs.find({'filename': {'$in': keys}})

            while True:
                try:
                    f = files.next()
                    yield f.filename, f
                except:
                    break

    def values(self, keys: List[str]=None):
        """

        """
        if keys is None:
            keys = self.keys()

            fs = gridfs.GridFSBucket(self._db)

            for key in keys:
                yield fs.open_download_stream_by_name(key)
        else:
            fs = gridfs.GridFS(self._db)

            files = fs.find({'filename': {'$in': keys}})

            while True:
                try:
                    f = files.next()
                    yield f
                except:
                    break

    def __iter__(self):
        return self.keys()

    def __len__(self):
        return self._db['fs.files'].estimated_document_count()

    def __contains__(self, key):
        fs = gridfs.GridFS(self._db)
        return fs.exists(filename=key)

    def get(self, key, default=None):
        try:
            fs = gridfs.GridFSBucket(self._db)
            value = fs.open_download_stream_by_name(key)
            return value
        except gridfs.errors.NoFile:
            return default

    def update(self, key_value_dict, threads=30):
        """

        """
        if self._write:
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                futures = []
                for key, value in key_value_dict.items():
                    f = executor.submit(utils.set_item, self._db, key, value)
                    futures.append(f)
                runs = concurrent.futures.wait(futures)

            objectids = [r.result() for r in runs[0]]
            utils.update_chunks_date(self._db, objectids, self._ttl)
        else:
            raise ValueError('File is open for read only.')

    def __getitem__(self, key):

        return self.get(key)


    def __setitem__(self, key: str, value: Union[bytes, io.IOBase]):
        if self._write:
            obid = utils.set_item(self._db, key, value)
            utils.update_chunks_date(self._db, obid, self._ttl)

        else:
            raise ValueError('File is open for read only.')

    def __delitem__(self, key):
        if self._write:
            fs = gridfs.GridFS(self._db)

            f = fs.find_one({'filename': key})

            if f is None:
                raise KeyError(key)

            fs.delete(f._id)
        else:
            raise ValueError('File is open for read only.')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def clear(self):
        if self._write:
            fs = gridfs.GridFS(self._db)

            files = fs.find({})

            while True:
                try:
                    f = files.next()
                    fs.delete(f._id)
                except:
                    break
        else:
            raise ValueError('File is open for read only.')

    def close(self):
        self._db.client.close()

    # def __del__(self):
    #     self.close()



def open(
    host: str='localhost', port: int=27017, database: str='db', flag: str = 'r', ttl: int=None):
    """
    Open a MongoDB connection for writing and/or reading in a python dictionary API style (MutableMapping). The MongoDB GridFS spec is used for storing objects. All keys must be strings and values must be either bytes or file-like objects.

    Parameters
    -----------
    host : str
        The hostname where the MongoDB server is running.

    port : int
        The port that the MongoDB server is listening to.

    database : str
        The database that should be used to store the objects in the GridFS collections. The collections are always called fs.files and fs.chunks within the database, so if the user wants to use multiple GridFS-dbm databases assign a different database name.

    flag : str
        Flag associated with how the database is opened according to the dbm style. See below for details.

    ttl : int or None
        Give the database a Time To Live (ttl) lifetime in seconds. All objects will persist in the database for this length. The default None will not assign a ttl.

    Returns
    -------
    GridFSDBM

    The optional *flag* argument can be:

    +---------+-------------------------------------------+
    | Value   | Meaning                                   |
    +=========+===========================================+
    | ``'r'`` | Open existing database for reading only   |
    |         | (default)                                 |
    +---------+-------------------------------------------+
    | ``'w'`` | Open existing database for reading and    |
    |         | writing                                   |
    +---------+-------------------------------------------+
    | ``'c'`` | Open database for reading and writing,    |
    |         | creating it if it doesn't exist           |
    +---------+-------------------------------------------+
    | ``'n'`` | Always create a new, empty database, open |
    |         | for reading and writing                   |
    +---------+-------------------------------------------+
    """

    return GridFSDBM(host, port, database, flag, ttl)
