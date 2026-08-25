#!/usr/bin/env python3


from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterator
from functools import update_wrapper
from math import inf
from pathlib import Path

from eprint import eprint

from ._getdents import \
    DT_BLK  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import \
    DT_CHR  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import \
    DT_DIR  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import \
    DT_FIFO  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import \
    DT_LNK  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import \
    DT_REG  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import \
    DT_SOCK  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import \
    DT_UNKNOWN  # noqa: ignore=F401 # pylint: disable=import-error
from ._getdents import O_GETDENTS  # pylint: disable=import-error
from ._getdents import getdents_raw  # pylint: disable=import-error



BUFF_SIZE = 4096 * 32  # 128k


# https://raw.githubusercontent.com/Pylons/pyramid/master/src/pyramid/decorator.py
class Reify:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        update_wrapper(self, wrapped)

    def __get__(
        self,
        inst,
        objtype=None,
    ):
        if inst is None:
            return self
        val = self.wrapped(inst)
        setattr(inst, self.wrapped.__name__, val)
        return val


def getdents(
    path,
    random: bool,
    skip_dotpaths: bool,
    skip_names: None | list[bytes],
    buff_size: int = BUFF_SIZE,
    suppress_permissionerror: bool = False,
    suppress_filenotfounderror: bool = False,
):
    """Get directory entries.

    Wrapper around getdents_raw(), simulates ls behaviour: ignores deleted
    files, skips .. entries.

    Note:
       Default buffer size is 64k.
       The default allocation size of glibc's readdir() implementation is 32k.

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
    try:
        path_fd = os.open(path, O_GETDENTS)
    except FileNotFoundError:
        sys.stderr.write(
            f"getdents: '{os.fsdecode(path)}': No such file or directory\n"
        )
        sys.stderr.flush()
        if not suppress_filenotfounderror:
            raise
        return
    except PermissionError:
        sys.stderr.write(f"getdents: '{os.fsdecode(path)}': Permission denied\n")
        sys.stderr.flush()
        if not suppress_permissionerror:
            raise
        return
    except NotADirectoryError:
        # entry enumerated as a dir by the parent but is no longer one (race)
        sys.stderr.write(f"getdents: '{os.fsdecode(path)}': Not a directory\n")
        sys.stderr.flush()
        return
    except OSError as e:
        sys.stderr.write(f"getdents: '{os.fsdecode(path)}': {e.strerror}\n")
        sys.stderr.flush()
        return

    # the C extension takes int, not bool (C90)
    if random is False:
        _random = 0
    else:
        _random = 1

    gdindex = 0
    try:
        for inode, dtype, name in getdents_raw(path_fd, buff_size, _random):
            gdindex += 1
            if skip_dotpaths:
                if name.startswith(b"."):
                    continue
            if skip_names:
                if name in skip_names:
                    continue

            if name != b"..":
                yield (inode, dtype, name)
    except OSError as e:
        # syscall-level failure mid-iteration (EIO, ESTALE, etc.); the fd was
        # opened fine but getdents64 itself failed. Don't let it abort the walk.
        sys.stderr.write(f"getdents: '{os.fsdecode(path)}': {e.strerror}\n")
        sys.stderr.flush()
    finally:
        os.close(path_fd)


class Dent:
    def __init__(
        self,
        parent: bytes,
        name: bytes,
        inode: int,
        dtype: int,
    ):
        self.parent = parent
        self.name = name
        self.inode = inode
        self.dtype = dtype

        split_p = None
        if self.name == b".":
            split_p = self.parent.split(b"/")
            self.name = split_p[-1]
            self.parent = b"/".join(split_p[:-1])
        self.path = os.path.join(self.parent, self.name)
        self.lstat = None

    @Reify
    def pathlib(self):
        return Path(os.fsdecode(self.path))  # resolve() is a mistake

    def __str__(self):
        return os.fsdecode(self.path)

    def __iter__(self):
        return iter(self.path)

    def __repr__(self):
        return f"Dent(parent={os.fsdecode(self.parent)}, name={os.fsdecode(self.name)}, inode={self.inode}, dtype={self.dtype}, path={os.fsdecode(self.path)})"

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        if not isinstance(other, Dent):
            return NotImplemented
        return self.path == other.path

    def __ne__(self, other):
        if not isinstance(other, Dent):
            return NotImplemented
        return self.path != other.path

    def __lt__(self, other):
        if not isinstance(other, Dent):
            return NotImplemented
        return self.path < other.path

    def __le__(self, other):
        if not isinstance(other, Dent):
            return NotImplemented
        return self.path <= other.path

    def __gt__(self, other):
        if not isinstance(other, Dent):
            return NotImplemented
        return self.path > other.path

    def __ge__(self, other):
        if not isinstance(other, Dent):
            return NotImplemented
        return self.path >= other.path

    def __fspath__(self):
        return os.fsdecode(self.path)

    def relative_to(self, path):
        return self.path.rsplit(path, maxsplit=1)[-1]

    def is_unknown(self):
        return self.dtype == 0

    def _stat_mode(self):
        # Only reached for DT_UNKNOWN entries (filesystems like XFS/overlayfs
        # may report 0). The path can vanish or dangle between enumeration and
        # the lstat, so a failure here just means "type indeterminate".
        if self.lstat is None:
            try:
                self.lstat = os.lstat(self.path)
            except OSError:
                return None
        return self.lstat.st_mode

    def is_fifo(self):
        if self.dtype == 1:
            return True
        if self.is_unknown():
            mode = self._stat_mode()
            return mode is not None and stat.S_ISFIFO(mode)
        return False

    def is_char_device(self):
        if self.dtype == 2:
            return True
        if self.is_unknown():
            mode = self._stat_mode()
            return mode is not None and stat.S_ISCHR(mode)
        return False

    def is_dir(self):
        if self.dtype == 4:
            return True
        if self.is_unknown():
            mode = self._stat_mode()
            return mode is not None and stat.S_ISDIR(mode)
        return False

    def is_block_device(self):
        if self.dtype == 6:
            return True
        if self.is_unknown():
            mode = self._stat_mode()
            return mode is not None and stat.S_ISBLK(mode)
        return False

    def is_file(self):
        if self.dtype == 8:
            return True
        if self.is_unknown():
            mode = self._stat_mode()
            return mode is not None and stat.S_ISREG(mode)
        return False

    def is_symlink(self):
        if self.dtype == 10:
            return True
        if self.is_unknown():
            mode = self._stat_mode()
            return mode is not None and stat.S_ISLNK(mode)
        return False

    def is_socket(self):
        if self.dtype == 12:
            return True
        if self.is_unknown():
            mode = self._stat_mode()
            return mode is not None and stat.S_ISSOCK(mode)
        return False

    def depth(self):
        # Number of path components; cheap byte count instead of building a
        # Path and tuple-splitting on the hot recursion path.
        p = self.path.rstrip(b"/")
        if not p:
            return 1  # root "/"
        return p.count(b"/") + 1

    @Reify
    def size(self):
        return self.pathlib.stat().st_size  # pylint: disable=no-member


class NameGen:
    def __init__(
        self,
        skip_dotpaths: bool,
        skip_names: None | list[bytes],
        path: bytes,
        buff_size: int = BUFF_SIZE,
        random: bool = False,
        names_only: bool = False,
        suppress_permissionerror: bool = False,
        suppress_filenotfounderror: bool = False,
        verbose: bool = False,
    ):
        self.verbose = verbose
        self.skip_dotpaths = skip_dotpaths
        self.skip_names = skip_names
        self.path = os.fsencode(path)
        self.buff_size = buff_size
        self.random = random
        self.names_only = names_only
        self.suppress_permissionerror = suppress_permissionerror
        self.suppress_filenotfounderror = suppress_filenotfounderror

        if self.path[0] != b"/":
            self.path = os.path.realpath(os.path.expanduser(self.path))

    def __iter__(self):

        for inode, dtype, name in getdents(
            path=self.path,
            buff_size=self.buff_size,
            random=self.random,
            skip_dotpaths=self.skip_dotpaths,
            skip_names=self.skip_names,
            suppress_permissionerror=self.suppress_permissionerror,
            suppress_filenotfounderror=self.suppress_filenotfounderror,
        ):
            if name == b".":
                continue
            if not self.names_only:
                name = Path(os.fsdecode(self.path)) / Path(os.fsdecode(name))
            yield inode, dtype, name


class DentGen:
    def __init__(
        self,
        path: bytes,
        skip_dotpaths: bool,
        skip_names: None | list[bytes],
        min_depth: int = 0,
        max_depth: float = inf,
        buff_size: int = BUFF_SIZE,
        random: bool = False,
        suppress_permissionerror: bool = False,
        suppress_filenotfounderror: bool = False,
        verbose: bool = False,
    ):
        self.path = os.fsencode(path)
        self.verbose = verbose
        self.skip_dotpaths = skip_dotpaths
        self.skip_names = skip_names
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.buff_size = buff_size
        self.random = random
        self.suppress_permissionerror = suppress_permissionerror
        self.suppress_filenotfounderror = suppress_filenotfounderror

        if self.path[0] != b"/":
            self.path = os.path.realpath(os.path.expanduser(self.path))
        if self.max_depth < 0:
            self.max_depth = inf
        if self.min_depth < 0:
            self.min_depth = 0
        else:
            self.min_depth = self.min_depth + len(self.path.split(b"/"))
        if self.verbose:
            eprint(
                f"DentGen() __init__() {self.path=!r} {self.min_depth=} {self.max_depth=} {self.skip_dotpaths=} {self.skip_names=}",
            )

    def __iter__(self, cur_path: bytes | None = None, cur_depth: int = 0):
        if cur_path is None:
            cur_path = self.path
        for inode, dtype, name in getdents(
            path=cur_path,
            buff_size=self.buff_size,
            random=self.random,
            skip_dotpaths=self.skip_dotpaths,
            skip_names=self.skip_names,
            suppress_permissionerror=self.suppress_permissionerror,
            suppress_filenotfounderror=self.suppress_filenotfounderror,
        ):
            if name == b".":  # skip self-reference; dirs are yielded explicitly below
                continue
            dent = Dent(
                parent=cur_path,
                name=name,
                inode=inode,
                dtype=dtype,
            )
            if dent.is_dir():
                if cur_depth < self.max_depth:
                    # yield the dir itself (replaces the old "." entry mechanism)
                    if not (self.min_depth and dent.depth() < self.min_depth):
                        yield dent
                    yield from self.__iter__(dent.path, cur_depth + 1)
                elif cur_depth == self.max_depth:
                    if self.min_depth and dent.depth() < self.min_depth:
                        continue
                    yield dent
            else:
                yield dent


# TODO: it may be faster to filter in a function that this feeds
def paths(
    path,
    *,
    skip_dotpaths: bool = False,
    skip_names: None | list[bytes] = None,
    return_dirs: bool = True,
    return_files: bool = True,
    return_symlinks: bool = True,
    return_sockets: bool = True,
    return_fifos: bool = True,
    return_block_devices: bool = True,
    return_char_devices: bool = True,
    names: None | list[str] = None,
    max_depth=inf,
    min_depth=0,
    random: bool = False,
    suppress_permissionerror: bool = False,
    suppress_filenotfounderror: bool = False,
    verbose: bool = False,
) -> Iterator[Dent]:
    if verbose:
        eprint(
            f"{path=}",
            f"{skip_dotpaths=}",
            f"{skip_names=}",
            f"{return_dirs=}",
            f"{return_files=}",
            f"{return_symlinks=}",
            f"{return_sockets=}",
            f"{return_fifos=}",
            f"{return_block_devices=}",
            f"{return_char_devices=}",
            f"{names=}",
            f"{max_depth=}",
            f"{min_depth=}",
            f"{random=}",
            f"{suppress_permissionerror=}",
            f"{suppress_filenotfounderror=}",
        )

    path = os.fsencode(path)

    fiterator = DentGen(
        path=path,
        max_depth=max_depth,
        min_depth=min_depth,
        skip_dotpaths=skip_dotpaths,
        skip_names=skip_names,
        suppress_permissionerror=suppress_permissionerror,
        suppress_filenotfounderror=suppress_filenotfounderror,
        random=random,
        verbose=verbose,
    )
    if names:
        for name in names:
            assert isinstance(name, str)  # fixme

    for thing in fiterator:
        if names:
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
        if not return_sockets:
            if thing.is_socket():
                continue
        if not return_fifos:
            if thing.is_fifo():
                continue
        if not return_char_devices:
            if thing.is_char_device():
                continue
        if not return_block_devices:
            if thing.is_block_device():
                continue

        yield thing


def paths_pathlib(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[Path]:
    for dent in paths(path=path, verbose=verbose, **kw):
        yield dent.pathlib


def paths_names(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[bytes]:
    for dent in paths(path=path, verbose=verbose, **kw):
        yield dent.name


def files(
    path,
    *,
    skip_dotpaths: bool = False,
    names: None | list[str] = None,
    max_depth=inf,
    min_depth: int = 0,
    max_size=inf,
    min_size: int = 0,
    random: bool = False,
    suppress_permissionerror: bool = False,
    suppress_filenotfounderror: bool = False,
    verbose: bool = False,
) -> Iterator[Dent]:
    if max_size < 0:
        max_size = inf
    for p in paths(
        path=path,
        return_dirs=False,
        return_symlinks=False,
        return_fifos=False,
        return_sockets=False,
        return_block_devices=False,
        return_char_devices=False,
        return_files=True,
        names=names,
        suppress_permissionerror=suppress_permissionerror,
        suppress_filenotfounderror=suppress_filenotfounderror,
        skip_dotpaths=skip_dotpaths,
        max_depth=max_depth,
        min_depth=min_depth,
        random=random,
        verbose=verbose,
    ):
        if min_size > 0 or max_size < inf:
            size = p.size()
            if size < min_size:
                continue
            if size > max_size:
                continue
        yield p


def files_pathlib(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[Path]:
    for dent in files(path=path, verbose=verbose, **kw):
        yield dent.pathlib


def files_names(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[bytes]:
    for dent in files(path=path, verbose=verbose, **kw):
        yield dent.name


def links(
    path,
    *,
    skip_dotpaths: bool = False,
    names: None | list[str] = None,
    max_depth=inf,
    min_depth: int = 0,
    random: bool = False,
    suppress_permissionerror: bool = False,
    suppress_filenotfounderror: bool = False,
    verbose: bool = False,
) -> Iterator[Dent]:
    return paths(
        path=path,
        return_dirs=False,
        return_symlinks=True,
        return_files=False,
        return_fifos=False,
        return_sockets=False,
        return_block_devices=False,
        return_char_devices=False,
        skip_dotpaths=skip_dotpaths,
        names=names,
        suppress_permissionerror=suppress_permissionerror,
        suppress_filenotfounderror=suppress_filenotfounderror,
        max_depth=max_depth,
        min_depth=min_depth,
        random=random,
        verbose=verbose,
    )


def links_pathlib(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[Path]:
    for dent in links(path=path, verbose=verbose, **kw):
        assert dent.dtype == 10
        yield dent.pathlib


def links_names(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[bytes]:
    for dent in links(path=path, verbose=verbose, **kw):
        assert dent.dtype == 10
        yield dent.name


def dirs(
    path,
    *,
    skip_dotpaths: bool = False,
    names: None | list[str] = None,
    max_depth=inf,
    min_depth: int = 0,
    random: bool = False,
    suppress_permissionerror: bool = False,
    suppress_filenotfounderror: bool = False,
    verbose: bool = False,
) -> Iterator[Dent]:
    return paths(
        path=path,
        return_dirs=True,
        return_symlinks=False,
        return_files=False,
        return_fifos=False,
        return_sockets=False,
        return_block_devices=False,
        return_char_devices=False,
        skip_dotpaths=skip_dotpaths,
        names=names,
        suppress_permissionerror=suppress_permissionerror,
        suppress_filenotfounderror=suppress_filenotfounderror,
        max_depth=max_depth,
        min_depth=min_depth,
        random=random,
        verbose=verbose,
    )


def dirs_pathlib(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[Path]:
    for dent in dirs(path=path, verbose=verbose, **kw):
        assert dent.dtype == 4
        yield dent.pathlib


def dirs_names(
    path,
    verbose: bool = False,
    **kw,
) -> Iterator[bytes]:
    for dent in dirs(path=path, verbose=verbose, **kw):
        assert dent.dtype == 4
        yield dent.name
