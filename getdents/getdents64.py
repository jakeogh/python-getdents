#!/usr/bin/python3

import os
import sys
from getdents import DentGen


def _iterate(path, max_depth, min_depth, command, count, nodirs, nosymlinks, print_end):
    c = 0
    if command:
        from subprocess import check_output
    dentgen = DentGen(path=path, max_depth=max_depth, min_depth=min_depth, verbose=False)

    if count:
        for i, item in enumerate(dentgen):
            if nodirs and item.is_dir():
                continue
            if nosymlinks and item.is_symlink():
                continue
            c += 1
        print(c)
    else:
        with open('/dev/stdout', mode='wb') as fd:
            for item in dentgen:
                if nodirs and item.is_dir():
                    continue
                if nosymlinks and item.is_symlink():
                    continue
                if command:
                    output = check_output([command, os.fsdecode(item.path)])
                    if output.endswith(b'\n'):
                        output = output[:-1]

                    fd.write(output + b' ' + item.path + print_end)
                else:
                    fd.write(item.path + print_end)


def usage():
    return '''Usage: getdents PATH [OPTIONS]

Options:
    --max-depth INT   Descend at most levels (>= 0) of directories below the starting-point.
    --min-depth INT   Return directories atleast (>= 0) levels below the starting-point.
    --exec CMD        Execute command for every printed result. Must be a single argument. Should produce a single line.
    --count           Print number of entries under PATH.
    --nodirs          Do not print directories.
    --nosymlinks      Do not print symbolic links.
    --print0          Items are terminated by a null character.
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
    count = False
    nodirs = False
    nosymlinks = False
    print_end = b'\n'
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
            elif sys.argv[index] == '--count':
                count = True
                index += 1
            elif sys.argv[index] == "--nodirs":
                nodirs = True
                index += 1
            elif sys.argv[index] == "--nosymlinks":
                nosymlinks = True
                index += 1
            elif sys.argv[index] == "--print0":
                print_end = b'\x00'
                index += 1
            else:
                print(usage(), file=sys.stderr)
                print("Error: Unknown option \"{0}\".".format(sys.argv[index]), file=sys.stderr)
                sys.exit(1)

    _iterate(path, max_depth, min_depth, command, count, nodirs, nosymlinks, print_end)


if __name__ == '__main__':  # for dev
    main()
