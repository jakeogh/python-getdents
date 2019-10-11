#!/usr/bin/python3

import os
from getdents import DentGen


def _iterate(path, count, nodirs, print_end):
    c = 0
    dentgen = DentGen(path, verbose=False)

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
                fd.write(item.path + print_end)


def help():
    return '''Usage: getdents PATH [OPTIONS]

Options:
    --count   Print number of entries under PATH.
    --nodirs  Do not print directories.
    --print0  Items are terminated by a null character.
    '''


def main():
    import sys
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
    index = 1
    if args >= 2:
        while index <= args:
            print("index:", index, sys.argv[index])
            if sys.argv[index] == '--depth':
                index += 1
                depth = sys.argv[index]
                if not int(depth):
                    print(help(), file=sys.stderr)
                    print("Error: --depth requires an integer, not \"{0}\".".format(sys.argv[index]), file=sys.stderr)
                    quit(1)
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
                print("Error: Unknown option \"{0}\".".format(sys.argv[2]), file=sys.stderr)
                quit(1)

    _iterate(path, count, nodirs, print_end)


if __name__ == '__main__':  # for dev
    main()
