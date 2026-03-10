"""
Unit tests for utils.logging_filter (coerce_level, canonical_module_name, parse functions).
"""

import logging
import os
from unittest.mock import patch

import pytest

pytest.importorskip("bittensor")


@pytest.mark.unit
class TestCoerceLevel:
    def test_coerce_level_none_empty(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _coerce_level

        assert _coerce_level(None) is None
        assert _coerce_level("") is None
        assert _coerce_level("   ") is None

    def test_coerce_level_named(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _coerce_level

        assert _coerce_level("DEBUG") == logging.DEBUG
        assert _coerce_level("info") == logging.INFO
        assert _coerce_level("WARNING") == logging.WARNING
        assert _coerce_level("error") == logging.ERROR

    def test_coerce_level_digit(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _coerce_level

        assert _coerce_level("10") == 10
        assert _coerce_level("20") == 20


@pytest.mark.unit
class TestCanonicalModuleName:
    def test_canonical_module_name_prefix_stripped(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _canonical_module_name

        assert _canonical_module_name("autoppia_web_agents_subnet.foo") == "foo"
        assert _canonical_module_name("autoppia_web_agents_subnet.validator.bar") == "validator.bar"

    def test_canonical_module_name_alias(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _canonical_module_name

        assert _canonical_module_name("platform") == "platform"
        assert _canonical_module_name("iwa") == "platform"
        assert _canonical_module_name("consensus") == "validator.settlement"

    def test_canonical_module_name_empty(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _canonical_module_name

        assert _canonical_module_name("") == ""
        assert _canonical_module_name("   ") == ""


@pytest.mark.unit
class TestParseModuleLevels:
    def test_parse_module_levels_empty(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _parse_module_levels

        with patch.dict(os.environ, {"LOG_MODULE_LEVELS": ""}, clear=False):
            assert _parse_module_levels() == {}

    def test_parse_module_levels_key_eq_val(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _parse_module_levels

        with patch.dict(os.environ, {"LOG_MODULE_LEVELS": "platform=DEBUG"}, clear=False):
            levels = _parse_module_levels()
            assert "platform" in levels
            assert levels["platform"] == logging.DEBUG

    def test_parse_module_levels_key_colon_val(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _parse_module_levels

        with patch.dict(os.environ, {"LOG_MODULE_LEVELS": "validator:INFO"}, clear=False):
            levels = _parse_module_levels()
            assert "validator" in levels
            assert levels["validator"] == logging.INFO


@pytest.mark.unit
class TestParseDisabledModules:
    def test_parse_disabled_modules_empty(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _parse_disabled_modules

        with patch.dict(os.environ, {"LOG_DISABLED_MODULES": ""}, clear=False):
            assert _parse_disabled_modules() == set()

    def test_parse_disabled_modules_list(self):
        from autoppia_web_agents_subnet.utils.logging_filter import _parse_disabled_modules

        with patch.dict(os.environ, {"LOG_DISABLED_MODULES": "platform,validator"}, clear=False):
            disabled = _parse_disabled_modules()
            assert "platform" in disabled
            assert "validator" in disabled


@pytest.mark.unit
class TestApplySubnetModuleLoggingFilters:
    def test_apply_subnet_module_logging_filters_adds_filter(self):
        from autoppia_web_agents_subnet.utils.logging_filter import (
            apply_subnet_module_logging_filters,
        )

        # Clear any existing filter to avoid duplicate filter issues
        if hasattr(logging, "_autoppia_stdlib_module_filter"):
            root = logging.getLogger()
            filt = getattr(logging, "_autoppia_stdlib_module_filter", None)
            if filt and filt in root.filters:
                root.removeFilter(filt)
            delattr(logging, "_autoppia_stdlib_module_filter")
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}, clear=False):
            apply_subnet_module_logging_filters(None)
        assert hasattr(logging, "_autoppia_stdlib_module_filter")
