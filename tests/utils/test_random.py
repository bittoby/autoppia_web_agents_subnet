"""
Unit tests for autoppia_web_agents_subnet.utils.random.

Tests interleave, split_tasks_evenly, get_random_uids.
Requires numpy (source module imports it).
"""

from unittest.mock import Mock

import pytest

pytest.importorskip("numpy")
import numpy as np


@pytest.mark.unit
class TestInterleave:
    def test_interleave_two_lists(self):
        from autoppia_web_agents_subnet.utils.random import interleave

        result = list(interleave([1, 3], [2, 4]))
        assert result == [1, 2, 3, 4]

    def test_interleave_skips_none(self):
        from autoppia_web_agents_subnet.utils.random import interleave

        # zip_longest yields (1,2), (None,4), (3,None); non-None order is 1,2,4,3
        result = list(interleave([1, None, 3], [2, 4, None]))
        assert result == [1, 2, 4, 3]

    def test_interleave_single_list(self):
        from autoppia_web_agents_subnet.utils.random import interleave

        result = list(interleave([1, 2, 3]))
        assert result == [1, 2, 3]

    def test_interleave_unequal_lengths(self):
        from autoppia_web_agents_subnet.utils.random import interleave

        result = list(interleave([1, 3], [2]))
        assert result == [1, 2, 3]

    def test_interleave_empty(self):
        from autoppia_web_agents_subnet.utils.random import interleave

        assert list(interleave()) == []
        assert list(interleave([], [])) == []


@pytest.mark.unit
class TestSplitTasksEvenly:
    def test_split_tasks_evenly_divisible(self):
        from autoppia_web_agents_subnet.utils.random import split_tasks_evenly

        assert split_tasks_evenly(6, 3) == [2, 2, 2]
        assert split_tasks_evenly(4, 2) == [2, 2]

    def test_split_tasks_evenly_with_remainder(self):
        from autoppia_web_agents_subnet.utils.random import split_tasks_evenly

        # 7 tasks, 3 projects -> 2+2+3 (remainder goes to last)
        assert split_tasks_evenly(7, 3) == [2, 2, 3]
        assert split_tasks_evenly(5, 2) == [2, 3]

    def test_split_tasks_evenly_single_project(self):
        from autoppia_web_agents_subnet.utils.random import split_tasks_evenly

        assert split_tasks_evenly(10, 1) == [10]

    def test_split_tasks_evenly_zero_tasks(self):
        from autoppia_web_agents_subnet.utils.random import split_tasks_evenly

        assert split_tasks_evenly(0, 3) == [0, 0, 0]


@pytest.mark.unit
class TestGetRandomUids:
    def test_get_random_uids_returns_k_uids(self):
        from autoppia_web_agents_subnet.utils.random import get_random_uids

        validator = Mock()
        validator.metagraph = Mock()
        validator.metagraph.n = np.array(10)

        uids = get_random_uids(validator, 3)
        assert isinstance(uids, np.ndarray)
        assert uids.shape == (3,)
        assert len(np.unique(uids)) == 3
        assert all(0 <= u < 10 for u in uids)

    def test_get_random_uids_exclude(self):
        from autoppia_web_agents_subnet.utils.random import get_random_uids

        validator = Mock()
        validator.metagraph = Mock()
        validator.metagraph.n = np.array(10)

        uids = get_random_uids(validator, 3, exclude=[0, 1, 2])
        assert len(uids) == 3
        assert set(uids.tolist()) & {0, 1, 2} == set()

    def test_get_random_uids_k_larger_than_available(self):
        from autoppia_web_agents_subnet.utils.random import get_random_uids

        validator = Mock()
        validator.metagraph = Mock()
        validator.metagraph.n = np.array(5)

        uids = get_random_uids(validator, 10)
        assert len(uids) == 5

    def test_get_random_uids_exclude_all_but_one(self):
        from autoppia_web_agents_subnet.utils.random import get_random_uids

        validator = Mock()
        validator.metagraph = Mock()
        validator.metagraph.n = np.array(5)

        uids = get_random_uids(validator, 2, exclude=[0, 1, 2, 3])
        assert len(uids) == 1
        assert uids[0] == 4
