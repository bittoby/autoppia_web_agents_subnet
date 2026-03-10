"""
Unit tests for autoppia_web_agents_subnet.base.utils.misc.

Tests ttl_cache, _ttl_hash_gen, ttl_get_block, _get_current_block_serialized.
"""

import threading
import time
from unittest.mock import Mock

import pytest


@pytest.mark.unit
class TestTtlCache:
    def test_ttl_cache_caches_within_ttl_window(self):
        from autoppia_web_agents_subnet.base.utils.misc import ttl_cache

        call_count = 0

        @ttl_cache(maxsize=4, ttl=2)
        def f(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert f(1) == 2
        assert f(1) == 2
        assert call_count == 1

    def test_ttl_cache_expires_after_ttl(self):
        from autoppia_web_agents_subnet.base.utils.misc import ttl_cache

        call_count = 0

        @ttl_cache(maxsize=4, ttl=1)
        def f(x):
            nonlocal call_count
            call_count += 1
            return x

        assert f(10) == 10
        assert call_count == 1
        time.sleep(1.1)
        assert f(10) == 10
        assert call_count == 2

    def test_ttl_cache_negative_ttl_uses_large_ttl(self):
        from autoppia_web_agents_subnet.base.utils.misc import ttl_cache

        @ttl_cache(ttl=-1)
        def f():
            return 1

        assert f() == 1
        assert f() == 1


@pytest.mark.unit
class TestTtlHashGen:
    def test_ttl_hash_gen_yields_increasing_hashes_over_time(self):
        from autoppia_web_agents_subnet.base.utils.misc import _ttl_hash_gen

        gen = _ttl_hash_gen(1)
        first = next(gen)
        second = next(gen)
        assert second >= first
        time.sleep(1.1)
        third = next(gen)
        assert third >= second
        assert third > first


@pytest.mark.unit
class TestGetCurrentBlockSerialized:
    def test_get_current_block_serialized_returns_subtensor_block(self):
        from autoppia_web_agents_subnet.base.utils.misc import _get_current_block_serialized

        mock_self = Mock()
        mock_self.subtensor = Mock()
        mock_self.subtensor.get_current_block = Mock(return_value=12345)
        # No pre-existing lock so code uses a real RLock (Mock doesn't support 'with')
        mock_self._subtensor_block_read_lock = None
        assert _get_current_block_serialized(mock_self) == 12345
        mock_self.subtensor.get_current_block.assert_called_once()

    def test_get_current_block_serialized_creates_lock_once(self):
        from autoppia_web_agents_subnet.base.utils.misc import _get_current_block_serialized

        mock_self = Mock()
        mock_self.subtensor = Mock()
        mock_self.subtensor.get_current_block = Mock(return_value=100)
        mock_self._subtensor_block_read_lock = None
        _get_current_block_serialized(mock_self)
        _get_current_block_serialized(mock_self)
        assert hasattr(mock_self, "_subtensor_block_read_lock")
        assert isinstance(mock_self._subtensor_block_read_lock, type(threading.RLock()))
        assert mock_self.subtensor.get_current_block.call_count == 2


@pytest.mark.unit
class TestTtlGetBlock:
    def test_ttl_get_block_delegates_to_serialized(self):
        from autoppia_web_agents_subnet.base.utils.misc import ttl_get_block

        mock_self = Mock()
        mock_self.subtensor = Mock()
        mock_self.subtensor.get_current_block = Mock(return_value=999)
        mock_self._subtensor_block_read_lock = None
        block = ttl_get_block(mock_self)
        assert block == 999
        # Second call within TTL may be cached
        block2 = ttl_get_block(mock_self)
        assert block2 == 999
