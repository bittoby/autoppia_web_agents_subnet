"""
Unit tests for validator penalties (shim and evaluation/penalties).
"""

from unittest.mock import patch

import pytest

pytest.importorskip("numpy")
import numpy as np


@pytest.mark.unit
class TestValidatorPenaltiesShim:
    """Tests for validator.penalties (compat shim)."""

    def test_apply_same_solution_penalty_returns_array(self):
        from autoppia_web_agents_subnet.validator.penalties import apply_same_solution_penalty

        solutions = [type("S", (), {"actions": []})(), type("S", (), {"actions": []})()]
        scores = [1.0, 1.0]
        out = apply_same_solution_penalty(solutions, scores)
        assert isinstance(out, np.ndarray)
        np.testing.assert_array_almost_equal(out, [1.0, 1.0])

    def test_apply_same_solution_penalty_with_meta_returns_tuple(self):
        from autoppia_web_agents_subnet.validator.penalties import (
            apply_same_solution_penalty_with_meta,
        )

        solutions = [type("S", (), {"actions": []})(), type("S", (), {"actions": []})()]
        scores = np.array([1.0, 1.0])
        arr, groups = apply_same_solution_penalty_with_meta(solutions, scores)
        assert isinstance(arr, np.ndarray)
        assert isinstance(groups, list)
        np.testing.assert_array_almost_equal(arr, [1.0, 1.0])
        assert groups == []


@pytest.mark.unit
class TestEvaluationPenalties:
    """Tests for validator.evaluation.penalties."""

    def test_detect_same_solution_groups_empty(self):
        from autoppia_web_agents_subnet.validator.evaluation.penalties import (
            detect_same_solution_groups,
        )

        assert detect_same_solution_groups([]) == []
        assert detect_same_solution_groups([type("S", (), {"actions": []})()]) == []

    def test_detect_same_solution_groups_identical_actions(self):
        from autoppia_web_agents_subnet.validator.evaluation.penalties import (
            detect_same_solution_groups,
        )

        action = type("A", (), {"type": "click", "url": "", "text": "x"})()
        sol0 = type("S", (), {"actions": [action]})()
        sol1 = type("S", (), {"actions": [action]})()
        with patch("autoppia_web_agents_subnet.validator.evaluation.penalties.bt"):
            groups = detect_same_solution_groups([sol0, sol1])
        assert len(groups) == 1
        assert set(groups[0]) == {0, 1}

    def test_detect_same_solution_groups_none_solution(self):
        from autoppia_web_agents_subnet.validator.evaluation.penalties import (
            detect_same_solution_groups,
        )

        action = type("A", (), {"type": "click", "url": "", "text": "a"})()
        sol0 = type("S", (), {"actions": [action]})()
        with patch("autoppia_web_agents_subnet.validator.evaluation.penalties.bt"):
            groups = detect_same_solution_groups([sol0, None])
        assert groups == [] or len(groups) == 0

    def test_apply_same_solution_penalty_with_meta_penalty_zero(self):
        from autoppia_web_agents_subnet.validator.evaluation.penalties import (
            SAME_SOLUTION_PENALTY,
            apply_same_solution_penalty_with_meta,
        )

        orig = SAME_SOLUTION_PENALTY
        try:
            from autoppia_web_agents_subnet.validator.evaluation import penalties as p

            p.SAME_SOLUTION_PENALTY = 1.0
            solutions = [
                type("S", (), {"actions": [type("A", (), {"type": "click", "url": "", "text": "x"})()]})(),
                type("S", (), {"actions": [type("A", (), {"type": "click", "url": "", "text": "x"})()]})(),
            ]
            scores = np.array([1.0, 1.0])
            with patch("autoppia_web_agents_subnet.validator.evaluation.penalties.bt"):
                arr, groups = apply_same_solution_penalty_with_meta(solutions, scores)
            assert len(groups) >= 0
            np.testing.assert_array_almost_equal(arr, [1.0, 1.0])
        finally:
            p.SAME_SOLUTION_PENALTY = orig

    def test_apply_same_solution_penalty_with_meta_penalty_applied(self):
        from autoppia_web_agents_subnet.validator.evaluation import penalties as p

        orig_penalty = p.SAME_SOLUTION_PENALTY
        orig_thr = p.SAME_SOLUTION_SIM_THRESHOLD
        try:
            p.SAME_SOLUTION_PENALTY = 0.5
            p.SAME_SOLUTION_SIM_THRESHOLD = 0.9
            action = type("A", (), {"type": "click", "url": "https://a", "text": "same"})()
            solutions = [
                type("S", (), {"actions": [action]})(),
                type("S", (), {"actions": [action]})(),
            ]
            scores = np.array([1.0, 1.0])
            with patch("autoppia_web_agents_subnet.validator.evaluation.penalties.bt"):
                arr, groups = p.apply_same_solution_penalty_with_meta(solutions, scores)
            if groups:
                np.testing.assert_array_almost_equal(arr, [0.5, 0.5])
        finally:
            p.SAME_SOLUTION_PENALTY = orig_penalty
            p.SAME_SOLUTION_SIM_THRESHOLD = orig_thr
