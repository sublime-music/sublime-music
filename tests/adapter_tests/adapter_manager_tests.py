from time import sleep

from sublime.adapters import Result


def test_result_immediate():
    result = Result(42)
    assert result.data_is_available
    assert result.result() == 42


def test_result_immediate_callback():
    callback_called = True

    def check_done_callback(f: Result):
        nonlocal callback_called
        assert f.result() == 42
        callback_called = True

    result = Result(42)
    result.add_done_callback(check_done_callback)
    assert callback_called


def test_result_future():
    def resolve_later() -> int:
        sleep(1)
        return 42

    result = Result(resolve_later)
    assert not result.data_is_available
    assert result.result() == 42
    assert result.data_is_available


def test_result_future_callback():
    def resolve_later() -> int:
        sleep(1)
        return 42

    check_done = False

    def check_done_callback(f: Result):
        nonlocal check_done
        assert result.data_is_available
        assert f.result() == 42
        check_done = True

    result = Result(resolve_later)
    result.add_done_callback(check_done_callback)

    # Should take much less than 2 seconds to complete. If the assertion fails, then the
    # check_done_callback failed.
    t = 0
    while not check_done:
        assert t < 2
        t += 0.1
        sleep(0.1)


def test_default_value():
    def resolve_fail() -> int:
        sleep(1)
        raise Exception()

    result = Result(resolve_fail, default_value=42)
    assert not result.data_is_available
    assert result.result() == 42
    assert result.data_is_available
