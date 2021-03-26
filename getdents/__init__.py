# pylint: disable=C0111  # docstrings are always outdated and wrong

import os
import stat
import sys  # benchmark that
from functools import update_wrapper
from math import inf
from pathlib import Path
from typing import Generator
from typing import Sequence

import attr

from ._getdents import O_GETDENTS  # pylint: disable=import-error
from ._getdents import getdents_raw  # pylint: disable=import-error

#from ._getdents import DT_BLK  # noqa: ignore=F401
#from ._getdents import DT_CHR  # noqa: ignore=E0401
#from ._getdents import DT_DIR
#from ._getdents import DT_FIFO
#from ._getdents import DT_LNK
#from ._getdents import DT_REG
#from ._getdents import DT_SOCK
#from ._getdents import DT_UNKNOWN
#from ._getdents import MIN_GETDENTS_BUFF_SIZE


BUFF_SIZE = 4096 * 16  # 64k


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


def getdents(path,
             buff_size=BUFF_SIZE,
             random: bool = False,):
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
        _random = 0
    else:
        _random = 1

    try:
        for inode, dtype, name in getdents_raw(path_fd, buff_size, _random):
            if name != b'..':
                yield (inode, dtype, name)
    finally:
        os.close(path_fd)


@attr.s(auto_attribs=True, hash=False, cmp=False)
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
        self.lstat = None

    @Reify
    def pathlib(self):
        return Path(os.fsdecode(self.path))

    def __str__(self):
        return os.fsdecode(self.path)

    def __iter__(self):
        return iter(self.path)

    def __repr__(self):
        return 'Dent(parent={parent}, name={name}, inode={inode}, dtype={dtype}, path={path})'.format(parent=os.fsdecode(self.parent),
                                                                                                      name=os.fsdecode(self.name),
                                                                                                      inode=self.inode,
                                                                                                      dtype=self.dtype,
                                                                                                      path=os.fsdecode(self.path),
                                                                                                      )

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        if self.path == other.path:
            return True
        return False

    def __ne__(self, other):
        if self.path != other.path:
            return True
        return False

    def __lt__(self, other):
        if self.path < other.path:
            return True
        return False

    def __le__(self, other):
        if self.path <= other.path:
            return True
        return False

    def __gt__(self, other):
        if self.path > other.path:
            return True
        return False

    def __ge__(self, other):
        if self.path >= other.path:
            return True
        return False

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
        elif self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISFIFO(self.lstat.st_mode):
                return True
        return False

    def is_char_device(self):
        if self.dtype == 2:
            return True
        elif self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISCHR(self.lstat.st_mode):
                return True
        return False

    def is_dir(self):
        if self.dtype == 4:
            return True
        elif self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISDIR(self.lstat.st_mode):
                return True
        return False

    def is_block_device(self):
        if self.dtype == 6:
            return True
        elif self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISBLK(self.lstat.st_mode):
                return True
        return False

    def is_file(self):
        if self.dtype == 8:
            return True
        elif self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISREG(self.lstat.st_mode):
                return True
        return False

    def is_symlink(self):
        if self.dtype == 10:
            return True
        elif self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISLNK(self.lstat.st_mode):
                return True
        return False

    def is_socket(self):
        if self.dtype == 12:
            return True
        elif self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISSOCK(self.lstat.st_mode):
                return True
        return False

    @Reify
    def depth(self):
        return len(self.pathlib.parts)  # pylint: disable=no-member

    @Reify
    def size(self):
        return self.pathlib.stat().st_size  # pylint: disable=no-member


@attr.s(auto_attribs=True)
class NameGen():
    verbose: bool
    debug: bool
    path: bytes = attr.ib(converter=os.fsencode)
    very_debug: bool = False
    buff_size: int = BUFF_SIZE
    random: bool = False  # bool is new in C99 and cpython tries to remain C90 compatible
    names_only: bool = False

    def __attrs_post_init__(self):
        if self.path[0] != b'/':
            self.path = os.path.realpath(os.path.expanduser(self.path))
        if self.verbose:
            print("NameGen __attrs_post_init__() self.path:", self.path, file=sys.stderr)
            print("NameGen __attrs_post_init__() self.names_only:", self.names_only, file=sys.stderr)
            print("NameGen __attrs_post_init__() self.random:", self.random, file=sys.stderr)

    def __iter__(self):
        if self.verbose:
            print("NameGen __iter__() self.path:", self.path, file=sys.stderr)

        for inode, dtype, name in getdents(path=self.path,
                                           buff_size=self.buff_size,
                                           random=self.random,):
            if name == b'.':
                continue
            if not self.names_only:
                name = Path(os.fsdecode(self.path)) / Path(os.fsdecode(name))
            if self.very_debug:
                print("NameGen __iter__() inode:", inode, file=sys.stderr)
                print("NameGen __iter__() dtype:", dtype, file=sys.stderr)
                print("NameGen __iter__() name:", name, file=sys.stderr)
            yield inode, dtype, name


@attr.s(auto_attribs=True)
class DentGen():
    path: bytes = attr.ib(converter=os.fsencode)
    verbose: bool
    debug: bool
    very_debug: bool = False
    min_depth: int = 0
    max_depth: float = inf
    buff_size: int = BUFF_SIZE
    random: bool = False  # bool is new in C99 and cpython tries to remain C90 compatible
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
        if self.very_debug:
            print("DentGen() __attrs_post_init__() self.path:", self.path, file=sys.stderr)
            print("DentGen() __attrs_post_init__() self.min_depth:", self.min_depth, file=sys.stderr)
            print("DentGen() __attrs_post_init__() self.max_depth:", self.max_depth, file=sys.stderr)

    def __iter__(self, cur_depth=0):
        #print("cur_depth:", cur_depth)
        #self.iters += 1
        if self.very_debug:
            print("DentGen() __iter__() cur_depth:", cur_depth, file=sys.stderr)
            print("DentGen() __iter__() self.path:", self.path, file=sys.stderr)
        for inode, dtype, name in getdents(path=self.path,
                                           buff_size=self.buff_size,
                                           random=self.random,):
            if self.very_debug:
                print("DentGen() __iter__() inode:", inode, file=sys.stderr)
                print("DentGen() __iter__() dtype:", dtype, file=sys.stderr)
                print("DentGen() __iter__() name:", name, file=sys.stderr)
            dent = Dent(parent=self.path, name=name, inode=inode, dtype=dtype)
            if self.very_debug or self.debug:
                print("DentGen() __iter__() dent:", repr(dent), file=sys.stderr)
            if dent.path == self.path:
                if self.min_depth:
                    if dent.depth < self.min_depth:
                        continue
                #print("yielding dent", dent.depth)
                yield dent
            elif dent.is_dir():
                self.path = dent.parent + b'/' + dent.name
                if cur_depth < self.max_depth:
                    #print(cur_depth, "<", self.max_depth)
                    yield from self.__iter__(cur_depth + 1)
                elif cur_depth == self.max_depth:
                    #print(cur_depth, "==", self.max_depth)
                    if self.min_depth:
                        if dent.depth < self.min_depth:
                            continue
                    yield dent
                self.path = dent.parent
            else:
                yield dent


# TODO: it may be faster to filter in a function that this feeds
def paths(path,
          *,
          verbose: bool,
          debug: bool,
          return_dirs: bool = True,
          return_files: bool = True,
          return_symlinks: bool = True,
          names_only: bool = False,
          names: Sequence[str] = None,
          max_depth=inf,
          min_depth=0,
          random: bool = False,) -> Generator:
    path = os.fsencode(path)
    if debug:
        print('getdents/__init__.py',
              path,
              "return_dirs:", return_dirs,
              "return_files:", return_files,
              "return_symlinks:", return_symlinks,
              "max_depth:", max_depth,
              "min_depth:", min_depth,
              "names:", names,
              file=sys.stderr)
    fiterator = DentGen(path=path,
                        max_depth=max_depth,
                        min_depth=min_depth,
                        random=random,
                        verbose=verbose,
                        debug=debug,)
    if names:
        #names = [os.fsdecode(name) for name in names]
        for name in names:
            assert isinstance(name, str)
    for thing in fiterator:
        if names:
            #print(thing.name)
            if os.fsdecode(thing.name) not in names:
                continue
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
            yield thing.name    # on first glance it might seem that this should still be a Dent,
                                # but it CANT BE, Dents reprsent real fs objects, and have parents
                                # names are just bytes
                                # so, unless one wants bytes, just return the Dents and use Dent.pathlib.name
        else:
            yield thing


def files(path,
          *,
          verbose: bool,
          debug: bool,
          names_only: bool = False,
          names=None,
          max_depth=inf,
          min_depth: int = 0,
          max_size=inf,
          min_size: int = 0,
          random: bool = False,) -> Generator:
    if max_size < 0:
        max_size = inf
    for p in paths(path=path,
                   return_dirs=False,
                   return_symlinks=False,
                   return_files=True,
                   names_only=False,
                   names=names,
                   max_depth=max_depth,
                   min_depth=min_depth,
                   random=random,
                   verbose=verbose,
                   debug=debug,):
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
          verbose: bool,
          debug: bool,
          names_only: bool = False,
          names=None,
          max_depth=inf,
          min_depth=0,
          random: bool = False,) -> Generator:
    return paths(path=path,
                 return_dirs=False,
                 return_symlinks=True,
                 return_files=False,
                 names_only=names_only,
                 names=names,
                 max_depth=max_depth,
                 min_depth=min_depth,
                 random=random,
                 verbose=verbose,
                 debug=debug,)


def dirs(path,
         *,
         verbose: bool,
         debug: bool,
         names_only: bool = False,
         names=None,
         max_depth=inf,
         min_depth=0,
         random: bool = False,) -> Generator:
    return paths(path=path,
                 return_dirs=True,
                 return_symlinks=False,
                 return_files=False,
                 names_only=names_only,
                 names=names,
                 max_depth=max_depth,
                 min_depth=min_depth,
                 random=random,
                 verbose=verbose,
                 debug=debug,)
