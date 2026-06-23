import os

from unittest.mock import ANY

from pytest import fixture, raises

from getdents._getdents import (
    DT_DIR,
    MIN_GETDENTS_BUFF_SIZE,
    getdents_raw,
)


@fixture
def fixt_regular_file(tmpdir):
    f = tmpdir.join('test.txt')
    f.write('content')

    fd = os.open(str(f), os.O_RDONLY)

    yield fd

    os.close(fd)


@fixture
def fixt_dir(tmpdir):
    for i in range(10):
        tmpdir.mkdir('subdir%d' % i)

    fd = os.open(str(tmpdir), os.O_DIRECTORY | os.O_RDONLY)

    yield fd

    os.close(fd)


def test_not_a_directory(fixt_regular_file):
    with raises(NotADirectoryError):
        getdents_raw(fixt_regular_file, MIN_GETDENTS_BUFF_SIZE)


def test_bad_fd():
    with raises(OSError):
        getdents_raw(-1, MIN_GETDENTS_BUFF_SIZE)


def test_small_buffer(fixt_dir):
    with raises(ValueError):
        getdents_raw(fixt_dir, MIN_GETDENTS_BUFF_SIZE - 1)


def test_bad_random(fixt_dir):
    with raises(ValueError):
        getdents_raw(fixt_dir, MIN_GETDENTS_BUFF_SIZE, 2)


def test_random_optional(fixt_dir):
    # rand defaults to 0 and may be passed explicitly as 0 or 1
    names0 = {e[2] for e in getdents_raw(fixt_dir, MIN_GETDENTS_BUFF_SIZE)}
    os.lseek(fixt_dir, 0, os.SEEK_SET)
    names1 = {e[2] for e in getdents_raw(fixt_dir, MIN_GETDENTS_BUFF_SIZE, 1)}
    assert names0 == names1


def test_malloc_fail(fixt_dir):
    with raises(MemoryError):
        getdents_raw(fixt_dir, 1 << 62)


def test_getdents_raw(fixt_dir):
    # Names are returned as bytes (PyBytes_FromString).
    iterator = iter(sorted(
        getdents_raw(
            fixt_dir,
            MIN_GETDENTS_BUFF_SIZE,
        ),
        key=lambda d: d[2],
    ))

    assert next(iterator) == (ANY, DT_DIR, b'.')
    assert next(iterator) == (ANY, DT_DIR, b'..')

    for i, entry in enumerate(iterator):
        assert entry == (ANY, DT_DIR, b'subdir%d' % i)
