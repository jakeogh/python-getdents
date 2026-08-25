#!/usr/bin/python3

import os
import sys
from collections.abc import Iterator
from signal import SIG_DFL
from signal import SIGPIPE
from signal import signal

import msgpack
from eprint import eprint

from getdents import Dent
from getdents import DentGen

signal(SIGPIPE, SIG_DFL)

READ_SIZE = 128


def _packed_paths(*, verbose: bool) -> Iterator[bytes]:
    unpacker = msgpack.Unpacker(strict_map_key=False, use_list=False)
    for chunk in iter(lambda: sys.stdin.buffer.read(READ_SIZE), b""):
        unpacker.feed(chunk)
        for value in unpacker:
            if not isinstance(value, bytes):
                raise TypeError(f"{type(value)} is not bytes")
            if verbose:
                eprint(f"{value=}")
            yield value


def _filter(
    *,
    item: Dent,
    names: list[bytes],
    no_files: bool,
    no_dirs: bool,
    no_symlinks: bool,
    no_sockets: bool,
    no_block_devices: bool,
    no_char_devices: bool,
    no_fifos: bool,
    no_dotfiles: bool,
) -> bool:
    if names:
        if item.name not in names:
            return True
    if no_dirs:
        if item.is_dir():
            return True
    if no_symlinks:
        if item.is_symlink():
            return True
    if no_files:
        if item.is_file():
            return True
    if no_sockets:
        if item.is_socket():
            return True
    if no_block_devices:
        if item.is_block_device():
            return True
    if no_char_devices:
        if item.is_char_device():
            return True
    if no_fifos:
        if item.is_fifo():
            return True
    if no_dotfiles:
        if item.name.startswith(b"."):
            return True
    return False


def _iterate(
    *,
    path: bytes,
    max_depth: int,
    min_depth: int,
    command: None | str,
    namesonly: bool,
    count: bool,
    random: bool,
    names: list[bytes],
    skip_names: list[bytes],
    no_files: bool,
    no_dirs: bool,
    no_symlinks: bool,
    no_sockets: bool,
    no_block_devices: bool,
    no_char_devices: bool,
    no_fifos: bool,
    no_dotfiles: bool,
    no_dotpaths: bool,
    tty: bool,
    verbose: bool = False,
) -> None:
    c = 0
    if command:
        from subprocess import check_output

    dentgen = DentGen(
        path=path,
        max_depth=max_depth,
        min_depth=min_depth,
        skip_dotpaths=no_dotpaths,
        skip_names=skip_names,
        suppress_permissionerror=True,  # for CLI/script usage
        suppress_filenotfounderror=True,  # for CLI/script usage
        random=random,
        verbose=verbose,
    )

    if count:
        for item in dentgen:
            if _filter(
                item=item,
                names=names,
                no_files=no_files,
                no_dirs=no_dirs,
                no_symlinks=no_symlinks,
                no_block_devices=no_block_devices,
                no_char_devices=no_char_devices,
                no_fifos=no_fifos,
                no_sockets=no_sockets,
                no_dotfiles=no_dotfiles,
            ):
                continue
            c += 1
        if tty:
            print(c)
            return
        sys.stdout.buffer.write(msgpack.packb(c))
        sys.stdout.buffer.flush()
        return

    end = b"\0"
    if tty:
        end = b"\n"

    with open("/dev/stdout", mode="ab") as fd:
        for item in dentgen:
            if _filter(
                item=item,
                names=names,
                no_files=no_files,
                no_dirs=no_dirs,
                no_symlinks=no_symlinks,
                no_block_devices=no_block_devices,
                no_char_devices=no_char_devices,
                no_fifos=no_fifos,
                no_sockets=no_sockets,
                no_dotfiles=no_dotfiles,
            ):
                continue
            if command:
                command_output = check_output([command, os.fsdecode(item.path)])
                if command_output.endswith(b"\n"):
                    command_output = command_output[:-1]

                fd.write(command_output + b" " + item.path + end)
            else:
                if namesonly:
                    fd.write(item.name + end)
                else:
                    if tty:
                        fd.write(repr(item.path).encode("utf8") + end)
                        continue
                    fd.write(msgpack.packb(item.path))


def usage() -> str:
    return """Usage: mpp "path" | getdents [OPTIONS]

Options:
    --maxdepth INT    Descend at most levels (>= 0) of directories below the starting-point.
    --mindepth INT    Return directories atleast (>= 0) levels below the starting-point.
    --exec CMD        Execute command for every printed result. Must be a single argument. Should produce a single line.
    --namesonly       Print PATH names only.
    --count           Print number of entries under PATH.
    --random          Randomize output order of each getdents64() syscall.
    --name      STR   Match name under PATH. Can be specified multiple times.
    --skipname  STR   Dont traverse PATH past name. Can be specified multiple times.
    --filesonly       Only print regular files.
    --dirsonly        Only print directories.
    --symlinksonly    Only print symlinks.
    --nofiles         Do not print regular files.
    --nodirs          Do not print directories.
    --nosymlinks      Do not print symbolic links.
    --nodevices       Do not print char or block devices.
    --nochar          Do not print char devices.
    --noblock         Do not print block devices.
    --nofifo          Do not print fifos.
    --nosockets       Do not print sockets.
    --nodotfiles      Do not print names that start with a dot (dot paths are still decended into).
    --nodotpaths      Do not print any paths that have one or names that starts with a dot.
    --verbose         Debugging output.
"""


def _depth_error(option: str, value: None | str = None) -> None:
    print(usage(), file=sys.stderr)
    if value:
        print(
            f'Error: {option} requires a integer >= 0, not "{value}".',
            file=sys.stderr,
        )
        return
    print(f"Error: {option} requires a integer >= 0.", file=sys.stderr)


def main() -> None:
    max_depth = -1
    min_depth = -1
    command = None
    args = len(sys.argv) - 1
    namesonly = False
    count = False
    random = False
    names: list[bytes] = []
    skipnames: list[bytes] = []
    nofiles = False
    filesonly = False
    symlinksonly = False
    dirsonly = False
    nodirs = False
    nosymlinks = False
    nochar = False
    noblock = False
    nofifo = False
    nosockets = False
    nodotfiles = False
    nodotpaths = False
    verbose = False
    index = 1
    while index <= args:
        if sys.argv[index] in {"--max-depth", "--maxdepth"}:
            index += 1
            try:
                max_depth = int(sys.argv[index])
            except IndexError:
                _depth_error("--max-depth")
                sys.exit(1)
            except ValueError:
                _depth_error("--max-depth", sys.argv[index])
                sys.exit(1)
            if max_depth < 0 or sys.argv[index].startswith("-"):
                _depth_error("--max-depth")
                sys.exit(1)
            index += 1
        elif sys.argv[index] in {"--min-depth", "--mindepth"}:
            index += 1
            try:
                min_depth = int(sys.argv[index])
            except IndexError:
                _depth_error("--min-depth")
                sys.exit(1)
            except ValueError:
                _depth_error("--min-depth", sys.argv[index])
                sys.exit(1)
            if min_depth < 0 or sys.argv[index].startswith("-"):
                _depth_error("--min-depth")
                sys.exit(1)
            index += 1
        elif sys.argv[index] == "--name":
            index += 1
            try:
                names.append(os.fsencode(sys.argv[index]))
            except IndexError:
                print(usage(), file=sys.stderr)
                print("Error: --name requires an argument.", file=sys.stderr)
                sys.exit(1)
            index += 1
        elif sys.argv[index] in {"--skipname", "--skip-name"}:
            index += 1
            try:
                skipnames.append(os.fsencode(sys.argv[index]))
            except IndexError:
                print(usage(), file=sys.stderr)
                print(
                    "Error: --skipname requires an argument.",
                    file=sys.stderr,
                )
                sys.exit(1)
            index += 1
        elif sys.argv[index] == "--exec":
            index += 1
            try:
                command = sys.argv[index]
            except IndexError:
                print(usage(), file=sys.stderr)
                print("Error: --exec requires an argument.", file=sys.stderr)
                sys.exit(1)
            index += 1
        elif sys.argv[index] in {"--namesonly", "--names-only"}:
            namesonly = True
            index += 1
        elif sys.argv[index] == "--count":
            count = True
            index += 1
        elif sys.argv[index] == "--random":
            random = True
            index += 1
        elif sys.argv[index] in {"--nofiles", "--no-files"}:
            nofiles = True
            index += 1
        elif sys.argv[index] in {"--filesonly", "--files-only", "--files"}:
            filesonly = True
            index += 1
        elif sys.argv[index] in {"--symlinksonly", "--symlinks-only", "--symlinks"}:
            symlinksonly = True
            index += 1
        elif sys.argv[index] in {"--nodirs", "--no-dirs"}:
            nodirs = True
            index += 1
        elif sys.argv[index] in {
            "--dirsonly",
            "--dirs-only",
            "--dirs",
            "--directories",
        }:
            dirsonly = True
            index += 1
        elif sys.argv[index] in {"--nosymlinks", "--no-symlinks"}:
            nosymlinks = True
            index += 1
        elif sys.argv[index] in {"--nodevices", "--no-devices"}:
            nochar = True
            noblock = True
            index += 1
        elif sys.argv[index] in {"--nochar", "--no-char"}:
            nochar = True
            index += 1
        elif sys.argv[index] in {"--noblock", "--no-block"}:
            noblock = True
            index += 1
        elif sys.argv[index] in {"--nofifo", "--no-fifo"}:
            nofifo = True
            index += 1
        elif sys.argv[index] in {"--nosockets", "--no-sockets"}:
            nosockets = True
            index += 1
        elif sys.argv[index] in {"--nodotfiles", "--no-dotfiles"}:
            nodotfiles = True
            index += 1
        elif sys.argv[index] in {
            "--nodotpaths",
            "--no-dotpaths",
            "--skipdotpaths",
            "--skip-dotpaths",
        }:
            nodotpaths = True
            index += 1
        elif sys.argv[index] == "--verbose":
            verbose = True
            index += 1
        else:
            print(usage(), file=sys.stderr)
            print(
                f'Error: Unknown option "{sys.argv[index]}".',
                file=sys.stderr,
            )
            sys.exit(1)

    if nofiles:
        if filesonly:
            print(
                "Error: --filesonly and --nofiles are mutually exclusive. Exiting.",
                file=sys.stderr,
            )
            sys.exit(1)
    if nosymlinks:
        if symlinksonly:
            print(
                "Error: --symlinksonly and --nosymlinks are mutually exclusive. Exiting.",
                file=sys.stderr,
            )
            sys.exit(1)
    if nodirs:
        if dirsonly:
            print(
                "Error: --dirsonly and --nodirs are mutually exclusive. Exiting.",
                file=sys.stderr,
            )
            sys.exit(1)
    if filesonly:
        if dirsonly:
            print(
                "Error: --dirsonly and --filesonly are mutually exclusive. Exiting.",
                file=sys.stderr,
            )
            sys.exit(1)
        if symlinksonly:
            print(
                "Error: --symlinksonly and --filesonly are mutually exclusive. Exiting.",
                file=sys.stderr,
            )
            sys.exit(1)

    if filesonly:
        nodirs = True
        nosymlinks = True
        nochar = True
        noblock = True
        nofifo = True
        nosockets = True

    if symlinksonly:
        nofiles = True
        nodirs = True
        nosymlinks = False
        nochar = True
        noblock = True
        nofifo = True
        nosockets = True

    if dirsonly:
        nofiles = True
        nosymlinks = True
        nochar = True
        noblock = True
        nofifo = True
        nosockets = True

    tty = sys.stdout.isatty()

    for path in _packed_paths(verbose=verbose):
        _iterate(
            path=path,
            max_depth=max_depth,
            min_depth=min_depth,
            command=command,
            count=count,
            namesonly=namesonly,
            random=random,
            names=names,
            skip_names=skipnames,
            no_files=nofiles,
            no_dirs=nodirs,
            no_symlinks=nosymlinks,
            no_char_devices=nochar,
            no_block_devices=noblock,
            no_fifos=nofifo,
            no_sockets=nosockets,
            no_dotfiles=nodotfiles,
            no_dotpaths=nodotpaths,
            tty=tty,
            verbose=verbose,
        )


if __name__ == "__main__":
    main()
