#!/usr/bin/python3

import os
from getdents import DentGen


def _iterate(path, count, nodirs):
    c = 0
    dentgen = DentGen(path, verbose=False).go()

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
                fd.write(item.path + b'\n')


def main():
    import sys
    args = len(sys.argv)
    if args >= 2:
        path = os.fsencode(sys.argv[1])
    else:
        print("a path is required", file=sys.stderr)
        quit(1)
    count = False
    nodirs = False
    if args >= 3:
        for arg in sys.argv[2:]:
            if arg == '--count':
                count = True
            elif arg == "--nodirs":
                nodirs = True
            else:
                print("unknown option {0}".format(sys.argv[2]), file=sys.stderr)
                quit(1)

    _iterate(path, count, nodirs)


if __name__ == '__main__':  # for dev
    main()
