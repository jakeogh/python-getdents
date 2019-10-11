#!/usr/bin/python3

import os
import sys
from getdents import DentGen


def _iterate(path, depth, command, count, nodirs, print_end):
    c = 0
    if command:
        from subprocess import check_output
    dentgen = DentGen(path, depth, verbose=False)

    if count:
        for i, item in enumerate(dentgen):
            if nodirs and item.is_dir():
                continue
            c += 1
        print(c)
    else:
        with open('/dev/stdout', mode='wb') as fd:
            for item in dentgen:
                if nodirs and item.is_dir():
                    continue
                if command:
                    output = check_output([command, os.fsdecode(item.path)])
                    if output.endswith(b'\n'):
                        output = output[:-1]

                    fd.write(output + ' ' + item.path + print_end)
                else:
                    fd.write(item.path + print_end)


def help():
    return '''Usage: getdents PATH [OPTIONS]

Options:
    --depth  INT  Descend at most levels (>= 0) levels of directories below the starting-point.
    --exec   CMD  Execute command for every printed result. Must be a single argument. Should produce a single line.
    --count       Print number of entries under PATH.
    --nodirs      Do not print directories.
    --print0      Items are terminated by a null character.
    '''


def help_depth(depth=None):
    print(help(), file=sys.stderr)
    if depth:
        print("Error: --depth requires a integer >= 0, not \"{0}\".".format(depth), file=sys.stderr)
        return
    print("Error: --depth requires a integer >= 0.", file=sys.stderr)


def main():
    depth = -1
    command = None
    args = len(sys.argv) - 1
    if args >= 1:
        path = os.fsencode(sys.argv[1])
    else:
        print(help(), file=sys.stderr)
        print("Error: A path is required.", file=sys.stderr)
        quit(1)
    count = False
    nodirs = False
    print_end = b'\n'
    index = 2
    if args >= 2:
        while index <= args:
            if sys.argv[index] == '--depth':
                index += 1
                try:
                    depth = int(sys.argv[index])
                except IndexError:
                    help_depth()
                    quit(1)
                except ValueError:
                    help_depth(sys.argv[index])
                    quit(1)
                if depth < 0 or sys.argv[index].startswith('-'):
                    help_depth()
                    quit(1)
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
            elif sys.argv[index] == "--print0":
                print_end = b'\x00'
                index += 1
            else:
                print(help(), file=sys.stderr)
                print("Error: Unknown option \"{0}\".".format(sys.argv[index]), file=sys.stderr)
                quit(1)

    _iterate(path, depth, command, count, nodirs, print_end)


if __name__ == '__main__':  # for dev
    main()
