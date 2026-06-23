from unittest.mock import patch, sentinel

from pytest import raises

from getdents import DT_DIR, DT_REG, DT_UNKNOWN, O_GETDENTS, getdents


def _call(**kw):
    # Helper applying the wrapper's required keyword-only-ish args with
    # sensible defaults so individual tests only set what they exercise.
    params = dict(
        path='/tmp',
        random=False,
        skip_dotpaths=False,
        skip_names=None,
        buff_size=sentinel.size,
    )
    params.update(kw)
    return getdents(**params)


@patch('getdents.os')
@patch('getdents.getdents_raw', return_value=iter([]))
def test_path(mock_getdents_raw, mock_os):
    mock_os.open.return_value = sentinel.fd

    list(_call())

    mock_os.open.assert_called_once_with('/tmp', O_GETDENTS)
    # wrapper passes (fd, buff_size, random_flag)
    mock_getdents_raw.assert_called_once_with(sentinel.fd, sentinel.size, 0)
    mock_os.close.assert_called_once_with(sentinel.fd)


@patch('getdents.os')
@patch('getdents.getdents_raw', return_value=iter([]))
def test_random_flag(mock_getdents_raw, mock_os):
    mock_os.open.return_value = sentinel.fd

    list(_call(random=True))

    mock_getdents_raw.assert_called_once_with(sentinel.fd, sentinel.size, 1)


@patch('getdents.os')
@patch('getdents.getdents_raw', side_effect=ValueError)
def test_path_err(mock_getdents_raw, mock_os):
    # Non-OSError exceptions from the C iterator must propagate, and the fd
    # must still be closed by the finally block.
    mock_os.open.return_value = sentinel.fd

    with raises(ValueError):
        list(_call())

    mock_os.open.assert_called_once_with('/tmp', O_GETDENTS)
    mock_getdents_raw.assert_called_once_with(sentinel.fd, sentinel.size, 0)
    mock_os.close.assert_called_once_with(sentinel.fd)


@patch('getdents.os')
@patch('getdents.getdents_raw', side_effect=OSError(5, 'I/O error'))
def test_oserror_swallowed(mock_getdents_raw, mock_os):
    # A syscall-level OSError mid-walk is logged and ends iteration cleanly
    # rather than propagating; the fd is still closed.
    mock_os.open.return_value = sentinel.fd

    assert list(_call()) == []
    mock_os.close.assert_called_once_with(sentinel.fd)


@patch('getdents.os')
@patch('getdents.getdents_raw', return_value=iter([
    (1, DT_DIR, b'.'),
    (2, DT_DIR, b'..'),
    (3, DT_DIR, b'dir'),
    (4, DT_REG, b'file'),
    (5, DT_UNKNOWN, b'???'),
]))
def test_filtering_parent_only(mock_getdents_raw, mock_os):
    # By default only '..' is dropped; '.' and everything else pass through.
    mock_os.open.return_value = sentinel.fd

    assert list(_call()) == [
        (1, DT_DIR, b'.'),
        (3, DT_DIR, b'dir'),
        (4, DT_REG, b'file'),
        (5, DT_UNKNOWN, b'???'),
    ]


@patch('getdents.os')
@patch('getdents.getdents_raw', return_value=iter([
    (1, DT_DIR, b'.'),
    (2, DT_DIR, b'..'),
    (3, DT_DIR, b'.hidden'),
    (4, DT_REG, b'file'),
]))
def test_skip_dotpaths(mock_getdents_raw, mock_os):
    mock_os.open.return_value = sentinel.fd

    assert list(_call(skip_dotpaths=True)) == [
        (4, DT_REG, b'file'),
    ]


@patch('getdents.os')
@patch('getdents.getdents_raw', return_value=iter([
    (3, DT_DIR, b'keep'),
    (4, DT_REG, b'drop'),
]))
def test_skip_names(mock_getdents_raw, mock_os):
    mock_os.open.return_value = sentinel.fd

    assert list(_call(skip_names=[b'drop'])) == [
        (3, DT_DIR, b'keep'),
    ]
