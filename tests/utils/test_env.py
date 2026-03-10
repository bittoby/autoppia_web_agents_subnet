"""
Unit tests for autoppia_web_agents_subnet.utils.env.

Tests _env_str, _env_bool, _env_int, _env_float with TESTING and TEST_* overrides.
"""

import os
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestEnvStr:
    def test_env_str_default_when_not_testing(self):
        from autoppia_web_agents_subnet.utils.env import _env_str

        with patch.dict(os.environ, {"TESTING": "false", "FOO": "bar"}, clear=False):
            assert _env_str("FOO", "default") == "bar"
        with patch.dict(os.environ, {"TESTING": "0"}, clear=False):
            assert _env_str("MISSING", "fallback") == "fallback"

    def test_env_str_testing_uses_test_override(self):
        from autoppia_web_agents_subnet.utils.env import _env_str

        with patch.dict(os.environ, {"TESTING": "true", "TEST_FOO": "from_test", "FOO": "from_prod"}, clear=False):
            assert _env_str("FOO", "default") == "from_test"

    def test_env_str_testing_uses_test_default_when_no_test_var(self):
        from autoppia_web_agents_subnet.utils.env import _env_str

        with patch.dict(os.environ, {"TESTING": "1"}, clear=False):
            assert _env_str("MISSING", "default", test_default="test_default") == "test_default"

    def test_env_str_strips_whitespace(self):
        from autoppia_web_agents_subnet.utils.env import _env_str

        with patch.dict(os.environ, {"TESTING": "false", "X": "  a  "}, clear=False):
            assert _env_str("X", "") == "a"


@pytest.mark.unit
class TestEnvBool:
    def test_env_bool_truthy_values(self):
        from autoppia_web_agents_subnet.utils.env import _env_bool

        for val in ("y", "yes", "t", "true", "on", "1"):
            with patch.dict(os.environ, {"TESTING": "false", "B": val}, clear=False):
                assert _env_bool("B", False) is True
            with patch.dict(os.environ, {"TESTING": "false", "B": val.upper()}, clear=False):
                assert _env_bool("B", False) is True

    def test_env_bool_falsy_default(self):
        from autoppia_web_agents_subnet.utils.env import _env_bool

        with patch.dict(os.environ, {"TESTING": "false"}, clear=False):
            assert _env_bool("MISSING", False) is False
            assert _env_bool("MISSING", True) is True

    def test_env_bool_testing_uses_test_override(self):
        from autoppia_web_agents_subnet.utils.env import _env_bool

        with patch.dict(os.environ, {"TESTING": "true", "TEST_B": "true", "B": "false"}, clear=False):
            assert _env_bool("B", False) is True

    def test_env_bool_test_default(self):
        from autoppia_web_agents_subnet.utils.env import _env_bool

        with patch.dict(os.environ, {"TESTING": "true"}, clear=False):
            assert _env_bool("MISSING", False, test_default=True) is True
            assert _env_bool("MISSING", True, test_default=False) is False


@pytest.mark.unit
class TestEnvInt:
    def test_env_int_parses_integer(self):
        from autoppia_web_agents_subnet.utils.env import _env_int

        with patch.dict(os.environ, {"TESTING": "false", "N": "42"}, clear=False):
            assert _env_int("N", 0) == 42

    def test_env_int_default_when_missing(self):
        from autoppia_web_agents_subnet.utils.env import _env_int

        with patch.dict(os.environ, {"TESTING": "false"}, clear=False):
            assert _env_int("MISSING", 99) == 99

    def test_env_int_testing_uses_test_override(self):
        from autoppia_web_agents_subnet.utils.env import _env_int

        with patch.dict(os.environ, {"TESTING": "true", "TEST_N": "7"}, clear=False):
            assert _env_int("N", 0) == 7

    def test_env_int_test_default(self):
        from autoppia_web_agents_subnet.utils.env import _env_int

        with patch.dict(os.environ, {"TESTING": "true"}, clear=False):
            assert _env_int("MISSING", 10, test_default=20) == 20


@pytest.mark.unit
class TestEnvFloat:
    def test_env_float_parses_float(self):
        from autoppia_web_agents_subnet.utils.env import _env_float

        with patch.dict(os.environ, {"TESTING": "false", "F": "3.14"}, clear=False):
            assert _env_float("F", 0.0) == 3.14

    def test_env_float_default_when_missing(self):
        from autoppia_web_agents_subnet.utils.env import _env_float

        with patch.dict(os.environ, {"TESTING": "false"}, clear=False):
            assert _env_float("MISSING", 1.5) == 1.5

    def test_env_float_testing_uses_test_override(self):
        from autoppia_web_agents_subnet.utils.env import _env_float

        with patch.dict(os.environ, {"TESTING": "true", "TEST_F": "2.5"}, clear=False):
            assert _env_float("F", 0.0) == 2.5

    def test_env_float_testing_falls_back_to_env_then_test_default(self):
        from autoppia_web_agents_subnet.utils.env import _env_float

        with patch.dict(os.environ, {"TESTING": "true", "F": "0.9"}, clear=False):
            assert _env_float("F", 0.0, test_default=0.5) == 0.9
        with patch.dict(os.environ, {"TESTING": "true"}, clear=False):
            assert _env_float("MISSING", 0.0, test_default=0.7) == 0.7
