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

from getdents import DentGen


def _filter(*,
            item,
            no_files,
            no_dirs,
            no_symlinks,
            no_sockets,
            no_block_devices,
            no_char_devices,
            no_fifos):

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
    return False


def _iterate(*,
             path,
             max_depth,
             min_depth,
             command,
             namesonly,
             count,
             random,
             no_files,
             no_dirs,
             no_symlinks,
             no_sockets,
             no_block_devices,
             no_char_devices,
             no_fifos,
             print_end,
             verbose: bool,
             debug: bool,):
    c = 0
    if command:
        from subprocess import check_output
    dentgen = DentGen(path=path,
                      max_depth=max_depth,
                      min_depth=min_depth,
                      random=random,
                      verbose=verbose,
                      debug=debug,)

    if count:
        for i, item in enumerate(dentgen):
            if _filter(item=item,
                       no_files=no_files,
                       no_dirs=no_dirs,
                       no_symlinks=no_symlinks,
                       no_block_devices=no_block_devices,
                       no_char_devices=no_char_devices,
                       no_fifos=no_fifos,
                       no_sockets=no_sockets):
                continue
            c += 1
        print(c)
    else:
        with open('/dev/stdout', mode='wb') as fd:
            for item in dentgen:
                if _filter(item=item,
                           no_files=no_files,
                           no_dirs=no_dirs,
                           no_symlinks=no_symlinks,
                           no_block_devices=no_block_devices,
                           no_char_devices=no_char_devices,
                           no_fifos=no_fifos,
                           no_sockets=no_sockets):
                    continue
                if command:
                    output = check_output([command, os.fsdecode(item.path)])
                    if output.endswith(b'\n'):
                        output = output[:-1]

                    fd.write(output + b' ' + item.path + print_end)
                else:
                    if namesonly:
                        fd.write(item.name + print_end)
                    else:
                        fd.write(item.path + print_end)


def usage():
    return '''Usage: getdents PATH [OPTIONS]

Options:
    --max-depth INT   Descend at most levels (>= 0) of directories below the starting-point.
    --min-depth INT   Return directories atleast (>= 0) levels below the starting-point.
    --exec CMD        Execute command for every printed result. Must be a single argument. Should produce a single line.
    --namesonly       Print PATH names only.
    --count           Print number of entries under PATH.
    --random          Randomize output order.
    --nofiles         Do not print regular files.
    --nodirs          Do not print directories.
    --nosymlinks      Do not print symbolic links.
    --nochar          Do not print char devices.
    --noblock         Do not print block devices.
    --nofifo          Do not print fifos.
    --nosockets       Do not print sockets.
    --printn          Items are terminated by a newline instead of null character.
    --verbose         Debugging output.
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
    random = 0
    nofiles = False
    nodirs = False
    nosymlinks = False
    nochar = False
    noblock = False
    nofifo = False
    nosockets = False
    verbose = False
    print_end = b'\x00'
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
            elif sys.argv[index] == '--exec':
                index += 1
                command = sys.argv[index]
                index += 1
            elif sys.argv[index] == '--namesonly':
                namesonly = True
                index += 1
            elif sys.argv[index] == '--count':
                count = True
                index += 1
            elif sys.argv[index] == '--random':
                random = 1
                index += 1
            elif sys.argv[index] == "--nofiles":
                nofiles = True
                index += 1
            elif sys.argv[index] == "--nodirs":
                nodirs = True
                index += 1
            elif sys.argv[index] == "--nosymlinks":
                nosymlinks = True
                index += 1
            elif sys.argv[index] == "--nochar":
                nochar = True
                index += 1
            elif sys.argv[index] == "--noblock":
                noblock = True
                index += 1
            elif sys.argv[index] == "--nofifo":
                nofifo = True
                index += 1
            elif sys.argv[index] == "--nosockets":
                nosockets = True
                index += 1
            elif sys.argv[index] == "--printn":
                print_end = b'\n'
                index += 1
            elif sys.argv[index] == "--verbose":
                verbose = True
                index += 1
            else:
                print(usage(), file=sys.stderr)
                print("Error: Unknown option \"{0}\".".format(sys.argv[index]), file=sys.stderr)
                sys.exit(1)

    _iterate(path=path,
             max_depth=max_depth,
             min_depth=min_depth,
             command=command,
             count=count,
             namesonly=namesonly,
             random=random,
             no_files=nofiles,
             no_dirs=nodirs,
             no_symlinks=nosymlinks,
             no_char_devices=nochar,
             no_block_devices=noblock,
             no_fifos=nofifo,
             no_sockets=nosockets,
             print_end=print_end,
             verbose=verbose,
             debug=debug,)


if __name__ == '__main__':  # for dev
    main()
