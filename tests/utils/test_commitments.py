"""
Unit tests for autoppia_web_agents_subnet.utils.commitments.

Tests _json_dump_compact and _maybe_json_load (pure helpers).
Requires bittensor to be installed (module imports it).
"""

import json

import pytest

pytest.importorskip("bittensor")


@pytest.mark.unit
class TestJsonDumpCompact:
    def test_json_dump_compact_returns_compact_json(self):
        from autoppia_web_agents_subnet.utils.commitments import _json_dump_compact

        data = {"a": 1, "b": "x"}
        out = _json_dump_compact(data)
        assert out == json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        assert json.loads(out) == data

    def test_json_dump_compact_raises_when_too_large(self):
        from autoppia_web_agents_subnet.utils.commitments import MAX_COMMIT_BYTES, _json_dump_compact

        # JSON is '{"key":"' + big + '"}' (8 + len(big) + 2 bytes); need total > MAX_COMMIT_BYTES
        big = "x" * (MAX_COMMIT_BYTES - 5)
        data = {"key": big}
        with pytest.raises(ValueError) as exc_info:
            _json_dump_compact(data)
        assert "too large" in str(exc_info.value).lower()
        assert str(MAX_COMMIT_BYTES) in str(exc_info.value)


@pytest.mark.unit
class TestMaybeJsonLoad:
    def test_maybe_json_load_none(self):
        from autoppia_web_agents_subnet.utils.commitments import _maybe_json_load

        assert _maybe_json_load(None) is None

    def test_maybe_json_load_bytes_decodes(self):
        from autoppia_web_agents_subnet.utils.commitments import _maybe_json_load

        payload = b'{"a":1}'
        assert _maybe_json_load(payload) == {"a": 1}

    def test_maybe_json_load_str_json(self):
        from autoppia_web_agents_subnet.utils.commitments import _maybe_json_load

        assert _maybe_json_load('{"x": 2}') == {"x": 2}
        assert _maybe_json_load("3") == 3

    def test_maybe_json_load_non_string_returns_unchanged(self):
        from autoppia_web_agents_subnet.utils.commitments import _maybe_json_load

        obj = {"already": "dict"}
        assert _maybe_json_load(obj) is obj

    def test_maybe_json_load_empty_string_returns_empty_string(self):
        from autoppia_web_agents_subnet.utils.commitments import _maybe_json_load

        assert _maybe_json_load("") == ""
        assert _maybe_json_load("   ") == ""

    def test_maybe_json_load_strip_whitespace(self):
        from autoppia_web_agents_subnet.utils.commitments import _maybe_json_load

        assert _maybe_json_load('  {"a":1}  ') == {"a": 1}
