import os

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
       size for filesystem IO.

    Args:
        path (str): Location of the directory.
        buff_size (int): Buffer size in bytes for getdents64 syscall.
    """

    fd = os.open(path, O_GETDENTS)

    try:
        #for inode, dtype, name in getdents_raw(fd, buff_size):
        #    if dtype != DT_UNKNOWN:
        #        if name != b'..':
        #            yield (inode, dtype, name)
        yield from (
            (inode, type, name)
            for inode, type, name in getdents_raw(fd, buff_size)
            if not(type == DT_UNKNOWN or inode == 0 or name in (b'.', b'..'))
        )
    finally:
        os.close(fd)


class Dent():
    def __init__(self, parent: bytes, name: bytes, inode: int, dtype: int):
        self.parent = parent
        self.name = name
        self.inode = inode
        self.dtype = dtype

        if self.name == b'.':
            split_p = self.parent.split(b'/')
            self.name = split_p[-1]
            self.parent = b'/'.join(split_p[:-1])
            del split_p
        self.path = b'/'.join((self.parent, self.name))

    def str(self):
        return os.fsdecode(self.path)

    def __repr__(self):
        return repr(os.fsdecode(self.path))  # todo

    def __fspath__(self):
        return os.fsdecode(self.path)

    def relative_to(self, path):  # temp dont keep
        return self.path.split(path)[-1]

    #def absolute(self):  # this will hand back a pathlib.Path TODO
    #    if self.parent.is_absolute():
    #        return self.parent / self.name
    #    return self.parent.resolve() / self.name

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


class DentGen():
    def __init__(self, path: bytes, buff_size: int = 32768, verbose: bool = False):
        self.path = path
        self.buff_size = buff_size
        self.verbose = verbose
        if self.path[0] != b'/':
            self.path = os.path.realpath(os.path.expanduser(self.path))

    def go(self):
        for inode, dtype, name in getdents(path=self.path, buff_size=self.buff_size, verbose=self.verbose):
            dent = Dent(parent=self.path, name=name, inode=inode, dtype=dtype)
            if dent.path == self.path:
                yield dent
            elif dent.is_dir():
                self.path = dent.parent + b'/' + dent.name
                yield from self.go()
                self.path = dent.parent
            else:
                yield dent
