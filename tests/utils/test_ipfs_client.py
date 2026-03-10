"""
Unit tests for utils.ipfs_client (minidumps, sha256_hex, IPFSError).
"""

import hashlib

import pytest


@pytest.mark.unit
class TestMinidumps:
    def test_minidumps_compact(self):
        from autoppia_web_agents_subnet.utils.ipfs_client import minidumps

        out = minidumps({"a": 1, "b": 2})
        assert "a" in out and "b" in out
        assert out == '{"a":1,"b":2}' or '"a":1' in out

    def test_minidumps_sort_keys_false(self):
        from autoppia_web_agents_subnet.utils.ipfs_client import minidumps

        out = minidumps({"b": 1, "a": 2}, sort_keys=False)
        assert "a" in out and "b" in out


@pytest.mark.unit
class TestSha256Hex:
    def test_sha256_hex(self):
        from autoppia_web_agents_subnet.utils.ipfs_client import sha256_hex

        out = sha256_hex(b"hello")
        assert len(out) == 64
        assert all(c in "0123456789abcdef" for c in out)
        assert out == hashlib.sha256(b"hello").hexdigest()


@pytest.mark.unit
class TestIPFSError:
    def test_ipfs_error_is_exception(self):
        from autoppia_web_agents_subnet.utils.ipfs_client import IPFSError

        e = IPFSError("test")
        assert str(e) == "test"
        assert isinstance(e, Exception)
