# pylint: disable=C0111  # docstrings are always outdated and wrong

import os
import sys  # benchmark that
from pathlib import Path
from functools import update_wrapper
from math import inf
import attr
#from icecream import ic

BUFF_SIZE = 4096 * 16  # 64k

from ._getdents import (  # noqa: ignore=F401
    DT_BLK,
    DT_CHR,
    DT_DIR,
    DT_FIFO,
    DT_LNK,
    DT_REG,
    DT_SOCK,
    DT_UNKNOWN,
    MIN_GETDENTS_BUFF_SIZE,
    O_GETDENTS,
    getdents_raw,
)


# https://raw.githubusercontent.com/Pylons/pyramid/master/src/pyramid/decorator.py
class Reify():
    def __init__(self, wrapped):
        self.wrapped = wrapped
        update_wrapper(self, wrapped)

    def __get__(self, inst, objtype=None):
        if inst is None:
            return self
        val = self.wrapped(inst)
        setattr(inst, self.wrapped.__name__, val)
        return val


def getdents(path, buff_size=BUFF_SIZE, random=False):
    """Get directory entries.

    Wrapper around getdents_raw(), simulates ls behaviour: ignores deleted
    files, skips .. entries.

    Note:
       Default buffer size is 32k, it's a default allocation size of glibc's
       readdir() implementation.

    Note:
       Larger buffer will result in a fewer syscalls, so for really large
       dirs you should pick larger value.

    Note:
       For better performance, set buffer size to be multiple of your block
       size for filesystem IO.

    Args:
        path (str): Location of the directory.
        buff_size (int): Buffer size in bytes for getdents64 syscall.
    """

    path_fd = os.open(path, O_GETDENTS)

    if random is False:
        random = 0
    else:
        random = 1

    try:
        for inode, dtype, name in getdents_raw(path_fd, buff_size, random):
            if name != b'..':
                yield (inode, dtype, name)
    finally:
        os.close(path_fd)


@attr.s(auto_attribs=True)
class Dent():
    parent: bytes
    name: bytes
    inode: int
    dtype: int

    def __attrs_post_init__(self):
        if self.name == b'.':
            split_p = self.parent.split(b'/')
            self.name = split_p[-1]
            self.parent = b'/'.join(split_p[:-1])
            del split_p
        self.path = b'/'.join((self.parent, self.name))
        #self.pathlib = Path(os.fsdecode(self.path))

    @Reify
    def pathlib(self):
        return Path(os.fsdecode(self.path))

    def __str__(self):
        return os.fsdecode(self.path)

    def __iter__(self):
        return iter(self.path)

    #def __repr__(self):
    #    return repr(os.fsdecode(self.path))  # todo

    def __hash__(self):
        return self.path

    def __fspath__(self):
        return os.fsdecode(self.path)

    def relative_to(self, path):  # temp dont keep
        return self.path.split(path)[-1]

    def is_unknown(self):
        if self.dtype == 0:
            return True
        return False

    def is_fifo(self):
        if self.dtype == 1:
            return True
        return False

    def is_char_device(self):
        if self.dtype == 2:
            return True
        return False

    def is_dir(self):
        if self.dtype == 4:
            return True
        return False

    def is_block_device(self):
        if self.dtype == 6:
            return True
        return False

    def is_file(self):
        if self.dtype in [8, 0]:  # temp
            return True
        return False

    def is_symlink(self):
        if self.dtype == 10:
            return True
        return False

    def is_socket(self):
        if self.dtype == 12:
            return True
        return False

    def depth(self):
        return len(self.pathlib.parts)

    def size(self):
        return self.pathlib.stat().st_size


@attr.s(auto_attribs=True)
class DentGen():
    path: bytes = attr.ib(converter=os.fsencode)
    min_depth: int = 0
    max_depth: float = inf
    buff_size: int = BUFF_SIZE
    random: bool = False  # bool is new in C99 and cpython tries to remain C90 compatible
    verbose: bool = False
    #iters: int = 0

    def __attrs_post_init__(self):
        if self.path[0] != b'/':
            self.path = os.path.realpath(os.path.expanduser(self.path))
        if self.max_depth < 0:
            self.max_depth = inf
        if self.min_depth < 0:
            self.min_depth = 0
        else:
            self.min_depth = self.min_depth + len(self.path.split(b'/'))
        if self.verbose:
            print("path:", self.path, file=sys.stderr)

    def __iter__(self, cur_depth=0):
        #print("cur_depth:", cur_depth)
        #self.iters += 1
        for inode, dtype, name in getdents(path=self.path, buff_size=self.buff_size, random=self.random):
            dent = Dent(parent=self.path, name=name, inode=inode, dtype=dtype)
            if dent.path == self.path:
                if self.min_depth:
                    if dent.depth() < self.min_depth:
                        continue
                #print("yielding dent", dent.depth())
                yield dent
            elif dent.is_dir():
                self.path = dent.parent + b'/' + dent.name
                if cur_depth < self.max_depth:
                    #print(cur_depth, "<", self.max_depth)
                    yield from self.__iter__(cur_depth + 1)
                elif cur_depth == self.max_depth:
                    #print(cur_depth, "==", self.max_depth)
                    if self.min_depth:
                        if dent.depth() < self.min_depth:
                            continue
                    yield dent
                self.path = dent.parent
            else:
                yield dent


# TODO: it may be faster to filter in a function that this feeds
def paths(path,
          *,
          return_dirs=True,
          return_files=True,
          return_symlinks=True,
          names_only=False,
          max_depth=inf,
          min_depth=0,
          random=False,
          verbose=False) -> Dent:
    path = os.fsencode(path)
    fiterator = DentGen(path=path,
                        max_depth=max_depth,
                        min_depth=min_depth,
                        random=random,
                        verbose=verbose)
    for thing in fiterator:
        if not return_dirs:
            if thing.is_dir():
                continue
        if not return_files:
            if thing.is_file():
                continue
        if not return_symlinks:
            if thing.is_symlink():
                continue
        if names_only:
            yield thing.name    # this should still be a Dent,
                                # but it CANT BE, Dents reprsent real fs objects, and have parents
                                # so, unless one wants bytes, just return the Dents and use Dent.pathlib.name
        else:
            yield thing
    #print(fiterator.iters)


def files(path,
          *,
          names_only=False,
          max_depth=inf,
          min_depth=0,
          max_size=inf,
          min_size=0,
          random=False,
          verbose=False) -> Dent:
    if max_size < 0:
        max_size = inf
    for p in paths(path=path,
                   return_dirs=False,
                   return_symlinks=False,
                   return_files=True,
                   names_only=False,
                   max_depth=max_depth,
                   min_depth=min_depth,
                   random=random,
                   verbose=verbose):
        if min_size > 0 or max_size < inf:
            size = p.size()
            if size < min_size:
                continue
            if size > max_size:
                continue
        if names_only:
            yield p.name
        else:
            yield p


def links(path,
          *,
          names_only=False,
          max_depth=inf,
          min_depth=0,
          random=False,
          verbose=False) -> Dent:
    return paths(path=path,
                 return_dirs=False,
                 return_symlinks=True,
                 return_files=False,
                 names_only=names_only,
                 max_depth=max_depth,
                 min_depth=min_depth,
                 random=random,
                 verbose=verbose)


def dirs(path,
         *,
         names_only=False,
         max_depth=inf,
         min_depth=0,
         random=False,
         verbose=False) -> Dent:
    return paths(path=path,
                 return_dirs=True,
                 return_symlinks=False,
                 return_files=False,
                 names_only=names_only,
                 max_depth=max_depth,
                 min_depth=min_depth,
                 random=random,
                 verbose=verbose)
