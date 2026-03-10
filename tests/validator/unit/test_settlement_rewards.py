from __future__ import annotations

import numpy as np
import pytest

from autoppia_web_agents_subnet.validator.settlement.rewards import wta_rewards


@pytest.mark.unit
def test_wta_rewards_empty_input_returns_empty():
    arr = np.asarray([], dtype=np.float32)
    out = wta_rewards(arr)
    assert out.size == 0


@pytest.mark.unit
def test_wta_rewards_all_non_positive_returns_all_zero():
    arr = np.asarray([0.0, -1.0, -3.2], dtype=np.float32)
    out = wta_rewards(arr)
    assert np.allclose(out, np.zeros_like(arr))


@pytest.mark.unit
def test_wta_rewards_selects_argmax_for_finite_values():
    arr = np.asarray([0.1, 0.8, 0.4], dtype=np.float32)
    out = wta_rewards(arr)
    assert np.allclose(out, np.asarray([0.0, 1.0, 0.0], dtype=np.float32))


@pytest.mark.unit
def test_wta_rewards_ignores_nan_when_selecting_winner():
    arr = np.asarray([np.nan, 0.4, 0.9], dtype=np.float32)
    out = wta_rewards(arr)
    assert np.allclose(out, np.asarray([0.0, 0.0, 1.0], dtype=np.float32))
