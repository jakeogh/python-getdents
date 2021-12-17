#!/usr/bin/python3

# pylint: disable=C0111  # docstrings are always outdated and wrong
# pylint: disable=W0511  # todo is encouraged
# pylint: disable=C0301  # line too long
# pylint: disable=R0902  # too many instance attributes
# pylint: disable=C0302  # too many lines in module
# pylint: disable=C0103  # single letter var names, func name too descriptive
# pylint: disable=R0911  # too many return statements
# pylint: disable=R0912  # too many branches
# pylint: disable=R0915  # too many statements
# pylint: disable=R0913  # too many arguments
# pylint: disable=R1702  # too many nested blocks
# pylint: disable=R0914  # too many local variables
# pylint: disable=R0903  # too few public methods
# pylint: disable=E1101  # no member for base
# pylint: disable=W0201  # attribute defined outside __init__
# pylint: disable=R0916  # Too many boolean expressions in if statement


import os
import sys
from signal import SIG_DFL
from signal import SIGPIPE
from signal import signal
from typing import List
from typing import Optional

from getdents import Dent
from getdents import DentGen

signal(SIGPIPE, SIG_DFL)


def _filter(*,
            item: Dent,
            names: List[bytes],
            no_files: bool,
            no_dirs: bool,
            no_symlinks: bool,
            no_sockets: bool,
            no_block_devices: bool,
            no_char_devices: bool,
            no_fifos: bool,
            no_dotfiles: bool,
            ):

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
        if item.name.startswith(b'.'):
            return True
    return False


def _iterate(*,
             path: bytes,
             max_depth: int,
             min_depth: int,
             command: Optional[str],
             namesonly: bool,
             count: bool,
             random: bool,
             names: List[bytes],
             skip_names: List[bytes],
             no_files: bool,
             no_dirs: bool,
             no_symlinks: bool,
             no_sockets: bool,
             no_block_devices: bool,
             no_char_devices: bool,
             no_fifos: bool,
             no_dotfiles: bool,
             no_dotpaths: bool,
             end,
             verbose: bool,
             debug: bool,
             ):
    c = 0
    if command:
        from subprocess import check_output

    #assert no_dotpaths
    dentgen = DentGen(path=path,
                      max_depth=max_depth,
                      min_depth=min_depth,
                      skip_dotpaths=no_dotpaths,
                      skip_names=skip_names,
                      random=random,
                      verbose=verbose,
                      debug=debug,)

    if count:
        for item in dentgen:
            if _filter(item=item,
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
        print(c, end=end.decode('utf8'))
    else:
        with open('/dev/stdout', mode='wb') as fd:
            for item in dentgen:
                if _filter(item=item,
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
                    output = check_output([command, os.fsdecode(item.path)])
                    if output.endswith(b'\n'):
                        output = output[:-1]

                    fd.write(output + b' ' + item.path + end)
                else:
                    if namesonly:
                        fd.write(item.name + end)
                    else:
                        fd.write(item.path + end)


#    --norecurse       Dont traverse paths. TODO lower --name to C in this case
def usage():
    return '''Usage: getdents PATH [OPTIONS]

Options:
    --max-depth INT   Descend at most levels (>= 0) of directories below the starting-point.
    --min-depth INT   Return directories atleast (>= 0) levels below the starting-point.
    --exec CMD        Execute command for every printed result. Must be a single argument. Should produce a single line.
    --namesonly       Print PATH names only.
    --count           Print number of entries under PATH.
    --random          Randomize output order of each getdents64() syscall.
    --name      STR   Match name under PATH. Can be specified multiple times.
    --skipname  STR   Dont traverse PATH past name. Can be specified multiple times.
    --filesonly       Only print regular files.
    --dirsonly        Only print directories.
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
    --printn          Items are terminated by a newline instead of null character.
    --verbose         Debugging output.
    --debug           More debugging output.
'''


def help_max_depth(max_depth=None):
    print(usage(), file=sys.stderr)
    if max_depth:
        print("Error: --max-depth requires a integer >= 0, not \"{0}\".".format(max_depth), file=sys.stderr)
        return
    print("Error: --max-depth requires a integer >= 0.", file=sys.stderr)


def help_min_depth(min_depth=None):
    print(usage(), file=sys.stderr)
    if min_depth:
        print("Error: --min-depth requires a integer >= 0, not \"{0}\".".format(min_depth), file=sys.stderr)
        return
    print("Error: --min-depth requires a integer >= 0.", file=sys.stderr)


# TODO add --
def main():
    max_depth = -1
    min_depth = -1
    command = None
    args = len(sys.argv) - 1
    if args >= 1:
        path = os.fsencode(sys.argv[1])
    else:
        print(usage(), file=sys.stderr)
        print("Error: A path is required.", file=sys.stderr)
        sys.exit(1)
    namesonly = False
    count = False
    random = False
    names = []
    skipnames = []
    nofiles = False
    filesonly = False
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
    debug = False
    printn = False
    #print_end = b'\x00'
    index = 2
    if args >= 2:
        while index <= args:
            if sys.argv[index] == '--max-depth':
                index += 1
                try:
                    max_depth = int(sys.argv[index])
                except IndexError:
                    help_max_depth()
                    sys.exit(1)
                except ValueError:
                    help_max_depth(sys.argv[index])
                    sys.exit(1)
                if max_depth < 0 or sys.argv[index].startswith('-'):
                    help_max_depth()
                    sys.exit(1)
                index += 1
            elif sys.argv[index] == '--min-depth':
                index += 1
                try:
                    min_depth = int(sys.argv[index])
                except IndexError:
                    help_min_depth()
                    sys.exit(1)
                except ValueError:
                    help_min_depth(sys.argv[index])
                    sys.exit(1)
                if min_depth < 0 or sys.argv[index].startswith('-'):
                    help_min_depth()
                    sys.exit(1)
                index += 1
            elif sys.argv[index] == '--name':
                index += 1
                try:
                    names.append(os.fsencode(sys.argv[index]))
                except IndexError as e:
                    raise e
                    #help_name()
                    #sys.exit(1)
                index += 1
            elif sys.argv[index] in ['--skipname', '--skip-name']:
                index += 1
                try:
                    skipnames.append(os.fsencode(sys.argv[index]))
                except IndexError as e:
                    raise e
                    #help_name()
                    #sys.exit(1)
                index += 1
            elif sys.argv[index] == '--exec':
                index += 1
                command = sys.argv[index]
                index += 1
            elif sys.argv[index] in ["--namesonly", "--names-only"]:
                namesonly = True
                index += 1
            elif sys.argv[index] == '--count':
                count = True
                index += 1
            elif sys.argv[index] == '--random':
                random = True
                index += 1
            elif sys.argv[index] in ["--nofiles", "--no-files"]:
                nofiles = True
                index += 1
            elif sys.argv[index] in ["--filesonly", "--files-only"]:
                filesonly = True
                index += 1
            elif sys.argv[index] in ["--nodirs", "--no-dirs"]:
                nodirs = True
                index += 1
            elif sys.argv[index] in ["--dirsonly", "--dirs-only"]:
                dirsonly = True
                index += 1
            elif sys.argv[index] in ["--nosymlinks", "--no-symlinks"]:
                nosymlinks = True
                index += 1
            elif sys.argv[index] in ['--nochar', '--no-char', '--nodevices', '--no-devices',]:
                nochar = True
                index += 1
            elif sys.argv[index] in ["--noblock", "--no-block", '--nodevices', '--no-devices',]:
                noblock = True
                index += 1
            elif sys.argv[index] in ["--nofifo", "--no-fifo"]:
                nofifo = True
                index += 1
            elif sys.argv[index] in ["--nosockets", "--no-sockets"]:
                nosockets = True
                index += 1
            elif sys.argv[index] in ["--nodotfiles", "--no-dotfiles"]:
                nodotfiles = True
                index += 1
            elif sys.argv[index] in ["--nodotpaths", "--no-dotpaths", '--skipdotpaths', '--skip-dotpaths']:
                nodotpaths = True
                index += 1
            elif sys.argv[index] == "--printn":
                #printn = b'\n'
                printn = True
                index += 1
            elif sys.argv[index] == "--verbose":
                verbose = True
                index += 1
            elif sys.argv[index] == "--debug":
                debug = True
                index += 1
            else:
                print(usage(), file=sys.stderr)
                print("Error: Unknown option \"{0}\".".format(sys.argv[index]), file=sys.stderr)
                sys.exit(1)

    if nofiles:
        if filesonly:
            print("Error: --filesonly and --nofiles are mutually exclusive. Exiting.", file=sys.stderr)
            sys.exit(1)
    if nodirs:
        if dirsonly:
            print("Error: --dirsonly and --nodirs are mutually exclusive. Exiting.", file=sys.stderr)
            sys.exit(1)
    if filesonly:
        if dirsonly:
            print("Error: --dirsonly and --filesonly are mutually exclusive. Exiting.", file=sys.stderr)
            sys.exit(1)

    if filesonly:
        nodirs = True
        nosymlinks = True
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

    null = not printn
    end = b'\n'
    if null:
        end = b'\x00'
    if sys.stdout.isatty():
        end = b'\n'

    _iterate(path=path,
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
             end=end,
             verbose=verbose,
             debug=debug,)


if __name__ == '__main__':  # for dev
    main()
