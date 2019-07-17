import os
#from sys import getfilesystemencoding
#from sys import getfilesystemencodeerrors
#from posix import open as _open
#from posix import close as _close
#from posix import fspath
#from posix import lstat
#from posix import stat
#from posix import readlink
#from posix import getcwdb
#from posix import getcwd
#import genericpath
#import posixpath

BUFF_SIZE = 4096 * 16  # 64k

#ENCODING = getfilesystemencoding()
#ERRORS = getfilesystemencodeerrors()
#
#
#def fsdecode(filename):
#    """Decode filename (an os.PathLike, bytes, or str) from the filesystem
#    encoding with 'surrogateescape' error handler, return str unchanged. On
#    Windows, use 'strict' error handler if the file system encoding is
#    'mbcs' (which is the default encoding).
#    """
#    filename = fspath(filename)  # Does type-checking of `filename`.
#    if isinstance(filename, bytes):
#        return filename.decode(ENCODING, ERRORS)
#    else:
#        return filename
#
#
#def _get_sep(path):
#    if isinstance(path, bytes):
#        return b'/'
#    else:
#        return '/'
#
#
## Return whether a path is absolute.
## Trivial in Posix, harder on the Mac or MS-DOS.
#def isabs(s):
#    """Test whether a path is absolute"""
#    s = fspath(s)
#    sep = _get_sep(s)
#    return s.startswith(sep)
#
#
## Split a path in head (everything up to the last '/') and tail (the
## rest).  If the path ends in '/', tail will be empty.  If there is no
## '/' in the path, head  will be empty.
## Trailing '/'es are stripped from head unless it is the root.
#def split(p):
#    """Split a pathname.  Returns tuple "(head, tail)" where "tail" is
#    everything after the final slash.  Either part may be empty."""
#    p = fspath(p)
#    sep = _get_sep(p)
#    i = p.rfind(sep) + 1
#    head, tail = p[:i], p[i:]
#    if head and head != sep*len(head):
#        head = head.rstrip(sep)
#    return head, tail
#
#
## Join pathnames.
## Ignore the previous parts if a part is absolute.
## Insert a '/' unless the first part is empty or already ends in '/'.
#
#def join(a, *p):
#    """Join two or more pathname components, inserting '/' as needed.
#    If any component is an absolute path, all previous path components
#    will be discarded.  An empty last part will result in a path that
#    ends with a separator."""
#    a = fspath(a)
#    sep = _get_sep(a)
#    path = a
#    try:
#        if not p:
#            path[:0] + sep  #23780: Ensure compatible data type even if p is null.
#        for b in map(fspath, p):
#            if b.startswith(sep):
#                path = b
#            elif not path or path.endswith(sep):
#                path += b
#            else:
#                path += sep + b
#    except (TypeError, AttributeError, BytesWarning):
#        genericpath._check_arg_types('join', a, *p)
#        raise
#    return path
#
#
## Is a path a symbolic link?
## This will always return false on systems where os.lstat doesn't exist.
#def islink(path):
#    """Test whether a path is a symbolic link"""
#    try:
#        st = lstat(path)
#    except (OSError, AttributeError):
#        return False
#    return stat.S_ISLNK(st.st_mode)
#
#
## Join two paths, normalizing and eliminating any symbolic links
## encountered in the second path.
#def _joinrealpath(path, rest, seen):
#    if isinstance(path, bytes):
#        sep = b'/'
#        curdir = b'.'
#        pardir = b'..'
#    else:
#        sep = '/'
#        curdir = '.'
#        pardir = '..'
#
#    if isabs(rest):
#        rest = rest[1:]
#        path = sep
#
#    while rest:
#        name, _, rest = rest.partition(sep)
#        if not name or name == curdir:
#            # current dir
#            continue
#        if name == pardir:
#            # parent dir
#            if path:
#                path, name = split(path)
#                if name == pardir:
#                    path = join(path, pardir, pardir)
#            else:
#                path = pardir
#            continue
#        newpath = join(path, name)
#        if not islink(newpath):
#            path = newpath
#            continue
#        # Resolve the symbolic link
#        if newpath in seen:
#            # Already seen this path
#            path = seen[newpath]
#            if path is not None:
#                # use cached value
#                continue
#            # The symlink is not resolved, so we must have a symlink loop.
#            # Return already resolved part + rest of the path unchanged.
#            return join(newpath, rest), False
#        seen[newpath] = None # not resolved symlink
#        path, ok = _joinrealpath(path, readlink(newpath), seen)
#        if not ok:
#            return join(path, rest), False
#        seen[newpath] = path # resolved symlink
#
#    return path, True
#
#
## Normalize a path, e.g. A//B, A/./B and A/foo/../B all become A/B.
## It should be understood that this may change the meaning of the path
## if it contains symbolic links!
#def normpath(path):
#    """Normalize path, eliminating double slashes, etc."""
#    path = fspath(path)
#    if isinstance(path, bytes):
#        sep = b'/'
#        empty = b''
#        dot = b'.'
#        dotdot = b'..'
#    else:
#        sep = '/'
#        empty = ''
#        dot = '.'
#        dotdot = '..'
#    if path == empty:
#        return dot
#    initial_slashes = path.startswith(sep)
#    # POSIX allows one or two initial slashes, but treats three or more
#    # as single slash.
#    if (initial_slashes and
#        path.startswith(sep*2) and not path.startswith(sep*3)):
#        initial_slashes = 2
#    comps = path.split(sep)
#    new_comps = []
#    for comp in comps:
#        if comp in (empty, dot):
#            continue
#        if (comp != dotdot or (not initial_slashes and not new_comps) or
#             (new_comps and new_comps[-1] == dotdot)):
#            new_comps.append(comp)
#        elif new_comps:
#            new_comps.pop()
#    comps = new_comps
#    path = sep.join(comps)
#    if initial_slashes:
#        path = sep*initial_slashes + path
#    return path or dot
#
#
#def abspath(path):
#    """Return an absolute path."""
#    path = fspath(path)
#    if not isabs(path):
#        if isinstance(path, bytes):
#            cwd = getcwdb()
#        else:
#            cwd = getcwd()
#        path = join(cwd, path)
#    return normpath(path)
#
#
#def realpath(filename):
#    """Return the canonical path of the specified filename, eliminating any
#symbolic links encountered in the path."""
#    filename = fspath(filename)
#    path, ok = _joinrealpath(filename[:0], filename, {})
#    return abspath(path)


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


def getdents(path, buff_size=BUFF_SIZE, verbose=False):
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
    #fd = _open(path, O_GETDENTS)

    try:
        for inode, dtype, name in getdents_raw(fd, buff_size):
            if name != b'..':
                yield (inode, dtype, name)
    finally:
        os.close(fd)
        #_close(fd)


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
        #return fsdecode(self.path)

    def __repr__(self):
        return repr(os.fsdecode(self.path))  # todo
        #return repr(fsdecode(self.path))  # todo

    def __fspath__(self):
        return os.fsdecode(self.path)
        #return fsdecode(self.path)

    def relative_to(self, path):  # temp dont keep
        return self.path.split(path)[-1]

    #def absolute(self):  # this will hand back a pathlib.Path TODO
    #    if self.parent.is_absolute():
    #        return self.parent / self.name
    #    return self.parent.resolve() / self.name

    # values from /usr/include/dirent.h
    # FUSE mounts may return DT_UNKNOWN (bup-fuse with overlayfs for example)

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


class DentGen():
    def __init__(self, path: bytes, buff_size: int = BUFF_SIZE, verbose: bool = False):
        self.path = path
        self.buff_size = buff_size
        self.verbose = verbose
        if self.path[0] != b'/':
            self.path = os.path.realpath(os.path.expanduser(self.path))
            #self.path = posixpath.realpath(posixpath.expanduser(self.path))

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
