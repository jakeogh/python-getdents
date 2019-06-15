import os
import attr
from pathlib import Path

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


def getdents(path, buff_size=32768, verbose=False):
    """Get directory entries.

    Wrapper around getdents_raw(), simulates ls behaviour: ignores deleted
    files, skips . and .. entries.

    Note:
       Default buffer size is 32k, it's a default allocation size of glibc's
       readdir() implementation.

    Note:
       Larger buffer will result in a fewer syscalls, so for really large
       dirs you should pick larger value.

    Note:
       For better performance, set buffer size to be multiple of your block
       size for filesystem I/O.

    Args:
        path (str): Location of the directory.
        buff_size (int): Buffer size in bytes for getdents64 syscall.
    """

    fd = os.open(path, O_GETDENTS)

    try:
        yield from (
            (inode, type, name)
            for inode, type, name in getdents_raw(fd, buff_size)
            if not(type == DT_UNKNOWN or inode == 0 or name in ('.', '..'))
        )
    finally:
        os.close(fd)


@attr.s(auto_attribs=True, kw_only=True)
class Dent():
    parent: str = attr.ib(converter=Path)
    name: str = attr.ib(converter=Path)
    verbose: bool = False
    inode: int
    dtype: int

    def absolute(self):
        if self.parent.is_absolute():
            return self.parent / self.name
        return self.parent.resolve() / self.name

    # values from /usr/include/dirent.h
    # shouldnt get DT_UNKNOWN since getdents() filters it

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
        if self.dtype == 8:
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


@attr.s(auto_attribs=True)
class DentGen():
    path: str = attr.ib(converter=Path)
    buff_size: int = 32768
    verbose: bool = False

    def __attrs_post_init__(self):
        if not self.path.is_absolute():
            self.path = self.path.resolve()

    def go(self):
        for inode, dtype, name in getdents(path=self.path, buff_size=self.buff_size, verbose=self.verbose):
            dent = Dent(parent=self.path, name=name, inode=inode, dtype=dtype)
            if dent.is_dir():
                self.path = dent.parent / dent.name
                yield from self.go()
                self.path = dent.parent
            yield dent


