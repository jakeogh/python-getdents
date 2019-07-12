#!/usr/bin/python3

import os
from getdents import DentGen


def _iterate(path, count):
    c = 0
    dentgen = DentGen(path, verbose=False).go()

    if count:
        for i, item in enumerate(dentgen):
            c += 1
        print(c)
    else:
        with open('/dev/stdout', mode='wb') as fd:
            for item in dentgen:
                fd.write(item.path + b'\n')


def main():
    import sys
    args = len(sys.argv)
    if args >= 2:
        path = os.fsencode(sys.argv[1])
    else:
        print("a path is required", file=sys.stderr)
        quit(1)
    if args == 3:
        if sys.argv[2] == '--count':
            count = True
        else:
            print("unknown option {0}".format(sys.argv[2]), file=sys.stderr)
            quit(1)
    else:
        count = False

    _iterate(path, count)


if __name__ == '__main__':  # for dev
    main()
