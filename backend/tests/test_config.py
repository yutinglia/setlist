"""Focused validation tests for environment parsing helpers."""

import pytest

from config import _env_int


def test_env_int_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("TEST_INTEGER_SETTING", "abc")

    with pytest.raises(ValueError, match="must be an integer"):
        _env_int("TEST_INTEGER_SETTING", 1, minimum=1)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_env_int_enforces_minimum(monkeypatch, value):
    monkeypatch.setenv("TEST_INTEGER_SETTING", value)

    with pytest.raises(ValueError, match="must be >= 1"):
        _env_int("TEST_INTEGER_SETTING", 1, minimum=1)
