"""
Unit tests for base.utils.weight_utils.
"""

import os
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("numpy")
pytest.importorskip("bittensor")
import numpy as np


@pytest.mark.unit
class TestNormalizeMaxWeight:
    def test_normalize_sum_one(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import normalize_max_weight

        x = np.array([1.0, 2.0, 3.0])
        out = normalize_max_weight(x, limit=0.5)
        np.testing.assert_almost_equal(out.sum(), 1.0)
        assert out.shape == x.shape

    def test_normalize_uniform_when_sum_zero(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import normalize_max_weight

        x = np.array([0.0, 0.0, 0.0])
        out = normalize_max_weight(x, limit=0.1)
        np.testing.assert_array_almost_equal(out, np.ones(3) / 3)

    def test_normalize_uniform_when_limit_times_n_leq_one(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import normalize_max_weight

        x = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
        out = normalize_max_weight(x, limit=0.2)
        np.testing.assert_array_almost_equal(out, np.ones(5) / 5)

    def test_normalize_caps_max_at_limit(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import normalize_max_weight

        x = np.array([10.0, 0.1, 0.1])
        out = normalize_max_weight(x, limit=0.5)
        np.testing.assert_almost_equal(out.sum(), 1.0)
        assert out.max() <= 0.5 + 1e-5


@pytest.mark.unit
class TestConvertWeightsAndUidsForEmit:
    def test_basic_conversion(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import (
            convert_weights_and_uids_for_emit,
        )

        uids = np.array([0, 1, 2])
        weights = np.array([0.5, 0.3, 0.2])
        weight_uids, weight_vals = convert_weights_and_uids_for_emit(uids, weights)
        assert len(weight_uids) == len(weight_vals) == 3
        assert sum(weight_vals) > 0

    def test_negative_weight_raises(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import (
            convert_weights_and_uids_for_emit,
        )

        with pytest.raises(ValueError, match="negative"):
            convert_weights_and_uids_for_emit(np.array([0, 1]), np.array([1.0, -0.1]))

    def test_negative_uid_raises(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import (
            convert_weights_and_uids_for_emit,
        )

        with pytest.raises(ValueError, match="uid"):
            convert_weights_and_uids_for_emit(np.array([0, -1]), np.array([0.5, 0.5]))

    def test_length_mismatch_raises(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import (
            convert_weights_and_uids_for_emit,
        )

        with pytest.raises(ValueError, match="same length"):
            convert_weights_and_uids_for_emit(np.array([0, 1]), np.array([1.0]))

    def test_zero_sum_returns_empty(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import (
            convert_weights_and_uids_for_emit,
        )

        uids = np.array([0, 1])
        weights = np.array([0.0, 0.0])
        weight_uids, weight_vals = convert_weights_and_uids_for_emit(uids, weights)
        assert weight_uids == []
        assert weight_vals == []


@pytest.mark.unit
class TestProcessWeightsForNetuid:
    def test_returns_uids_and_weights_when_sufficient_nonzero(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import (
            process_weights_for_netuid,
        )

        subtensor = Mock()
        subtensor.min_allowed_weights = Mock(return_value=2)
        subtensor.max_weight_limit = Mock(return_value=0.1)
        metagraph = Mock()
        metagraph.n = 5
        subtensor.metagraph = Mock(return_value=metagraph)

        uids = np.array([0, 1, 2])
        weights = np.array([0.5, 0.3, 0.2])
        out_uids, out_weights = process_weights_for_netuid(uids, weights, netuid=1, subtensor=subtensor, metagraph=metagraph)
        assert len(out_uids) == len(out_weights)
        np.testing.assert_almost_equal(out_weights.sum(), 1.0)

    def test_burn_when_all_zero_weights(self):
        from autoppia_web_agents_subnet.base.utils.weight_utils import (
            process_weights_for_netuid,
        )

        subtensor = Mock()
        subtensor.min_allowed_weights = Mock(return_value=2)
        metagraph = Mock()
        metagraph.n = 5
        subtensor.metagraph = Mock(return_value=metagraph)

        uids = np.array([0, 1, 2])
        weights = np.array([0.0, 0.0, 0.0])
        with patch.dict(os.environ, {"BURN_UID": "2"}):
            out_uids, out_weights = process_weights_for_netuid(uids, weights, netuid=1, subtensor=subtensor, metagraph=metagraph)
        assert out_weights.sum() == 1.0
        assert out_weights[2] == 1.0
