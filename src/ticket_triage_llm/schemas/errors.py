from typing import Never, NoReturn


def assert_never_failure_reason(value: Never) -> NoReturn:
    raise AssertionError(f"Unhandled failure reason: {value!r}")
