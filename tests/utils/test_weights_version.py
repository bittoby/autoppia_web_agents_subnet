"""
Unit tests for autoppia_web_agents_subnet.utils.weights_version.
"""

import pytest


@pytest.mark.unit
class TestVersionToTuple:
    def test_version_to_tuple(self):
        from autoppia_web_agents_subnet.utils.weights_version import version_to_tuple

        assert version_to_tuple("1.2.3") == (1, 2, 3)
        assert version_to_tuple("0.0.1") == (0, 0, 1)
        assert version_to_tuple("10.20.30") == (10, 20, 30)


@pytest.mark.unit
class TestIsValidVersionFormat:
    def test_valid_formats(self):
        from autoppia_web_agents_subnet.utils.weights_version import is_valid_version_format

        assert is_valid_version_format("1.2.3") is True
        assert is_valid_version_format("0.0.0") is True
        assert is_valid_version_format("99.99.99") is True

    def test_invalid_formats(self):
        from autoppia_web_agents_subnet.utils.weights_version import is_valid_version_format

        assert is_valid_version_format("1.2") is False
        assert is_valid_version_format("1.2.3.4") is False
        assert is_valid_version_format("a.b.c") is False
        assert is_valid_version_format("1.2.3-beta") is False
        assert is_valid_version_format("") is False


@pytest.mark.unit
class TestIsVersionInRange:
    def test_inside_range(self):
        from autoppia_web_agents_subnet.utils.weights_version import is_version_in_range

        assert is_version_in_range("1.2.3", "1.0.0", "2.0.0") is True
        assert is_version_in_range("1.0.0", "1.0.0", "1.0.0") is True
        assert is_version_in_range("1.5.0", "1.0.0", "2.0.0") is True

    def test_outside_range(self):
        from autoppia_web_agents_subnet.utils.weights_version import is_version_in_range

        assert is_version_in_range("0.9.0", "1.0.0", "2.0.0") is False
        assert is_version_in_range("2.1.0", "1.0.0", "2.0.0") is False

    def test_range_order_independent(self):
        from autoppia_web_agents_subnet.utils.weights_version import is_version_in_range

        assert is_version_in_range("1.5.0", "2.0.0", "1.0.0") is True
        assert is_version_in_range("1.5.0", "1.0.0", "2.0.0") is True

    def test_invalid_version_returns_false(self):
        from autoppia_web_agents_subnet.utils.weights_version import is_version_in_range

        assert is_version_in_range("1.2", "1.0.0", "2.0.0") is False


@pytest.mark.unit
class TestTupleToVersion:
    def test_tuple_to_version(self):
        from autoppia_web_agents_subnet.utils.weights_version import tuple_to_version

        assert tuple_to_version((1, 2, 3)) == "1.2.3"
        assert tuple_to_version((0, 0, 1)) == "0.0.1"


@pytest.mark.unit
class TestGenerateRandomVersion:
    def test_generate_random_version_returns_string(self):
        from autoppia_web_agents_subnet.utils.weights_version import generate_random_version

        v = generate_random_version("1.0.0", "2.0.0")
        assert isinstance(v, str)
        assert v.count(".") == 2

    def test_generate_random_version_outside_range(self):
        from autoppia_web_agents_subnet.utils.weights_version import (
            generate_random_version,
            is_version_in_range,
        )

        # generate_random_version returns a version outside [v1, v2]
        v = generate_random_version("1.0.0", "2.0.0")
        assert not is_version_in_range(v, "1.0.0", "2.0.0")
