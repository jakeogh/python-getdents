#!/usr/bin/env python3

# pylint: disable=useless-suppression             # [I0021]
# pylint: disable=missing-docstring               # [C0111] docstrings are always outdated and wrong
# pylint: disable=fixme                           # [W0511] todo is encouraged
# pylint: disable=too-many-arguments              # [R0913]
# pylint: disable=too-many-branches               # [R0912]
# pylint: disable=too-few-public-methods          # [R0903]
# pylint: disable=missing-param-doc               # [W9015]

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterator
from functools import update_wrapper
from math import inf
from pathlib import Path

import attr
from asserttool import ic
from epprint import epprint
from eprint import eprint

# from ._getdents import \
#    MIN_GETDENTS_BUFF_SIZE  # noqa: ignore=F401 # pylint: disable=import-error
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

    def __get__(self, inst, objtype=None):
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
    supress_permissionerror: bool = False,
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
    eprint(f"getdents()          {path=!r}")
    if supress_permissionerror:
        try:
            path_fd = os.open(path, O_GETDENTS)
        except PermissionError:
            sys.stderr.write(f"getdents: ‘{os.fsdecode(path)}’: Permission denied\n")
            sys.stderr.flush()
            return
    else:
        path_fd = os.open(path, O_GETDENTS)

    if random is False:
        _random = 0
    else:
        _random = 1

    gdindex = 0
    try:
        for inode, dtype, name in getdents_raw(path_fd, buff_size, _random):
            eprint(
                f"getdents()           {gdindex=} {inode=}", f"{dtype=}", f"{name=!r}"
            )
            gdindex += 1
            if skip_dotpaths:
                if name.startswith(b"."):
                    continue
            if skip_names:
                if name in skip_names:
                    continue

            if name != b"..":
                yield (inode, dtype, name)
    finally:
        os.close(path_fd)


class Dent:
    def __init__(self, parent: bytes, name: bytes, inode: int, dtype: int):
        self.parent = parent
        self.name = name
        self.inode = inode
        self.dtype = dtype

        eprint(f"Dent      __init__() {self.inode=} {self.name=} {self.parent=!r}")
        split_p = None
        if self.name == b".":
            split_p = self.parent.split(b"/")
            # eprint(f"Dent       __init__() {self.name=} {split_p=}")
            self.name = split_p[-1]
            self.parent = b"/".join(split_p[:-1])
            # del split_p
        self.path = b"/".join((self.parent, self.name))
        eprint(
            f"Dent      __init__() {self.inode=} {self.name=} {split_p=} {self.parent=!r} {self.path=!r}"
        )
        assert Path(os.fsdecode(self.path)).exists()
        # self.pathlib = Path(os.fsdecode(self.path))
        self.lstat = None

    @Reify
    def pathlib(self):
        # return Path(os.fsdecode(self.path)).resolve()  # resolve() might be a mistake
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
        # return self.path.split(path)[-1]
        return self.path.rsplit(path, maxsplit=1)[-1]

    def is_unknown(self):
        if self.dtype == 0:
            return True
        return False

    def is_fifo(self):
        if self.dtype == 1:
            return True
        if self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISFIFO(self.lstat.st_mode):
                return True
        return False

    def is_char_device(self):
        if self.dtype == 2:
            return True
        if self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISCHR(self.lstat.st_mode):
                return True
        return False

    def is_dir(self):
        if self.dtype == 4:
            return True
        if self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISDIR(self.lstat.st_mode):
                return True
        return False

    def is_block_device(self):
        if self.dtype == 6:
            return True
        if self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISBLK(self.lstat.st_mode):
                return True
        return False

    def is_file(self):
        if self.dtype == 8:
            return True
        if self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISREG(self.lstat.st_mode):
                return True
        return False

    def is_symlink(self):
        if self.dtype == 10:
            return True
        if self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISLNK(self.lstat.st_mode):
                return True
        return False

    def is_socket(self):
        if self.dtype == 12:
            return True
        if self.is_unknown():
            if not self.lstat:
                self.lstat = os.lstat(self.path)
            if stat.S_ISSOCK(self.lstat.st_mode):
                return True
        return False

    # @Reify
    def depth(self):
        return len(self.pathlib.parts)  # pylint: disable=no-member

    @Reify
    def size(self):
        return self.pathlib.stat().st_size  # pylint: disable=no-member


class NameGen:
    # bool is new in C99 and cpython tries to remain C90 compatible
    def __init__(
        self,
        verbose: bool | int | float,
        skip_dotpaths: bool,
        skip_names: None | list[bytes],
        path: bytes,
        buff_size: int = BUFF_SIZE,
        random: bool = False,
        names_only: bool = False,
        supress_permissionerror: bool = False,
    ):

        self.verbose = verbose
        self.skip_dotpaths = skip_dotpaths
        self.skip_names = skip_names
        self.path = os.fsencode(path)
        self.buff_size = buff_size
        self.random = random
        self.names_only = names_only
        self.supress_permissionerror = supress_permissionerror

        if self.path[0] != b"/":
            self.path = os.path.realpath(os.path.expanduser(self.path))
        # if self.verbose == inf:
        #    print("NameGen() __attrs_post_init__() self.path:", self.path, file=sys.stderr)
        #    print("NameGen() __attrs_post_init__() self.names_only:", self.names_only, file=sys.stderr)
        #    print("NameGen() __attrs_post_init__() self.random:", self.random, file=sys.stderr)
        #    print("NameGen() __attrs_post_init__() self.skip_dotpaths:", self.skip_dotpaths, file=sys.stderr)
        #    print("NameGen() __attrs_post_init__() self.skip_names:", self.skip_names, file=sys.stderr)

    def __iter__(self):
        if self.verbose == inf:
            print("NameGen() __iter__() {self.path=!r}", file=sys.stderr)

        for inode, dtype, name in getdents(
            path=self.path,
            buff_size=self.buff_size,
            random=self.random,
            skip_dotpaths=self.skip_dotpaths,
            skip_names=self.skip_names,
            supress_permissionerror=self.supress_permissionerror,
        ):
            if name == b".":
                continue
            if not self.names_only:
                name = Path(os.fsdecode(self.path)) / Path(os.fsdecode(name))
            # if self.verbose == inf:
            #    print("NameGen() __iter__() inode:", inode, file=sys.stderr)
            #    print("NameGen() __iter__() dtype:", dtype, file=sys.stderr)
            #    print("NameGen() __iter__() name:", name, file=sys.stderr)
            yield inode, dtype, name


class DentGen:
    # bool is new in C99 and cpython tries to remain C90 compatible
    def __init__(
        self,
        path: bytes,
        verbose: bool | int | float,
        skip_dotpaths: bool,
        skip_names: None | list[bytes],
        min_depth: int = 0,
        max_depth: float = inf,
        buff_size: int = BUFF_SIZE,
        random: bool = False,
        supress_permissionerror: bool = False,
    ):
        self.path = os.fsencode(path)
        self.verbose = verbose
        self.skip_dotpaths = skip_dotpaths
        self.skip_names = skip_names
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.buff_size = buff_size
        self.random = random
        self.supress_permissionerror = supress_permissionerror
        # iters: int = 0

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

    # def __iter__(self, cur_depth: int = 0):
    # def __iter__(self, cur_depth: int):
    def __iter__(self, cur_depth: int = 0):
        if self.verbose:
            eprint(f"\nDentGen() __iter__() {cur_depth=} {self.path=!r}")
        index = 0
        for inode, dtype, name in getdents(
            path=self.path,
            buff_size=self.buff_size,
            random=self.random,
            skip_dotpaths=self.skip_dotpaths,
            skip_names=self.skip_names,
            supress_permissionerror=self.supress_permissionerror,
        ):
            if self.verbose:
                eprint(f"DentGen() __iter__() {index=} {inode=} {dtype=} {name=}")
            index += 1
            _test_path = Path(os.fsdecode(self.path))
            eprint(f"{_test_path=}")
            eprint(f"{self.path=}")
            assert _test_path.exists()
            assert (_test_path / Path(os.fsdecode(name))).exists()
            dent = Dent(parent=self.path, name=name, inode=inode, dtype=dtype)
            if self.verbose:
                eprint("DentGen() __iter__() dent:", repr(dent))
            if dent.path == self.path:
                if self.min_depth:
                    if dent.depth() < self.min_depth:
                        continue
                yield dent
            elif dent.is_dir():
                self.path = dent.parent + b"/" + dent.name
                eprint(f"{self.path=!r}")
                assert Path(os.fsdecode(self.path)).exists()
                if cur_depth < self.max_depth:
                    ic(self.max_depth, cur_depth + 1)
                    yield from self.__iter__(cur_depth + 1)  # hmmm
                elif cur_depth == self.max_depth:
                    ic(cur_depth, self.max_depth, self.min_depth, dent.depth(), dent)
                    if self.min_depth:
                        if dent.depth() < self.min_depth:
                            ic(dent.depth() < self.min_depth, "continueing")
                            continue
                    yield dent
                self.path = dent.parent
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
    verbose: bool | int | float,
) -> Iterator[Dent]:

    if verbose == inf:
        epprint(
            path,
            skip_dotpaths,
            skip_names,
            return_dirs,
            return_files,
            return_symlinks,
            return_sockets,
            return_fifos,
            return_block_devices,
            return_char_devices,
            names,
            max_depth,
            min_depth,
            random,
            verbose,
        )

    # eprint(f"{path=}")
    path = os.fsencode(path)

    # if verbose == inf:
    #    print('getdents/__init__.py',
    #          path,
    #          "return_dirs:", return_dirs,
    #          "return_files:", return_files,
    #          "return_symlinks:", return_symlinks,
    #          "return_sockets:", return_symlinks,
    #          "return_fifos:", return_symlinks,
    #          "return_block_devices:", return_block_devices,
    #          "return_char_devices:", return_char_devices,
    #          "max_depth:", max_depth,
    #          "min_depth:", min_depth,
    #          "names:", names,
    #          "skip_dotpaths:", skip_dotpaths,
    #          "skip_names:", skip_names,
    #          file=sys.stderr,)
    fiterator = DentGen(
        path=path,
        max_depth=max_depth,
        min_depth=min_depth,
        skip_dotpaths=skip_dotpaths,
        skip_names=skip_names,
        random=random,
        verbose=verbose,
    )
    if names:
        # names = [os.fsdecode(name) for name in names]
        for name in names:
            assert isinstance(name, str)  # fixme

    for thing in fiterator:
        if names:
            # print(thing.name)
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

        # # names_only overrules pathlib
        # if names_only:
        #    yield thing.name    # on first glance it might seem that this should still be a Dent,
        #                        # but it CANT BE, Dents reprsent real fs objects, and have parents
        #                        # names are just bytes
        #                        # so, unless one wants bytes, just return the Dents and use Dent.pathlib.name
        yield thing


def paths_pathlib(
    path,
    verbose: bool | int | float,
    **kw,
) -> Iterator[Path]:
    for dent in paths(path=path, verbose=verbose, **kw):
        yield dent.pathlib


def paths_names(
    path,
    verbose: bool | int | float,
    **kw,
) -> Iterator[bytes]:
    # for dent in paths(path=path, max_depth=0, **kw):
    for dent in paths(path=path, verbose=verbose, **kw):
        yield dent.name


def files(
    path,
    *,
    skip_dotpaths: bool = False,
    names: None | list[str] = None,  # byggy
    max_depth=inf,
    min_depth: int = 0,
    max_size=inf,
    min_size: int = 0,
    random: bool = False,
    verbose: bool | int | float,
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
        # if names_only:
        #    yield p.name
        # else:
        yield p


def files_pathlib(
    path,
    verbose: bool | int | float,
    **kw,
) -> Iterator[Path]:
    for dent in files(path=path, verbose=verbose, **kw):
        yield dent.pathlib


def files_names(
    path,
    verbose: bool | int | float,
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
    verbose: bool | int | float,
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
        max_depth=max_depth,
        min_depth=min_depth,
        random=random,
        verbose=verbose,
    )


def links_pathlib(
    path,
    verbose: bool | int | float,
    **kw,
) -> Iterator[Path]:
    for dent in links(path=path, verbose=verbose, **kw):
        assert dent.dtype == 10
        yield dent.pathlib


def links_names(
    path,
    verbose: bool | int | float,
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
    verbose: bool | int | float,
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
        max_depth=max_depth,
        min_depth=min_depth,
        random=random,
        verbose=verbose,
    )


def dirs_pathlib(
    path,
    verbose: bool | int | float,
    **kw,
) -> Iterator[Path]:
    for dent in dirs(path=path, verbose=verbose, **kw):
        assert dent.dtype == 4
        yield dent.pathlib


def dirs_names(
    path,
    verbose: bool | int | float,
    **kw,
) -> Iterator[bytes]:
    for dent in dirs(path=path, verbose=verbose, **kw):
        assert dent.dtype == 4
        yield dent.name
