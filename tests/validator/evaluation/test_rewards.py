"""
Unit tests for validator.evaluation.rewards (calculate_reward_for_task).
"""

import pytest


@pytest.mark.unit
class TestCalculateRewardForTask:
    def test_unsolved_returns_zero(self):
        from autoppia_web_agents_subnet.validator.evaluation.rewards import (
            calculate_reward_for_task,
        )

        r = calculate_reward_for_task(
            eval_score=0.5,
            execution_time=10.0,
            token_cost=0.01,
        )
        assert r == 0.0

    def test_solved_full_score_baseline(self):
        from autoppia_web_agents_subnet.validator.evaluation.rewards import (
            calculate_reward_for_task,
        )

        r = calculate_reward_for_task(
            eval_score=1.0,
            execution_time=0.0,
            token_cost=0.0,
        )
        assert r > 0.0
        assert r <= 2.0

    def test_solved_with_time_penalty(self):
        from autoppia_web_agents_subnet.validator.evaluation.rewards import (
            calculate_reward_for_task,
        )

        r_fast = calculate_reward_for_task(
            eval_score=1.0,
            execution_time=0.0,
            token_cost=0.0,
        )
        r_slow = calculate_reward_for_task(
            eval_score=1.0,
            execution_time=300.0,
            token_cost=0.0,
        )
        assert r_slow < r_fast
        assert r_slow >= 0.0

    def test_solved_with_cost_penalty(self):
        from autoppia_web_agents_subnet.validator.evaluation.rewards import (
            calculate_reward_for_task,
        )

        r_zero = calculate_reward_for_task(
            eval_score=1.0,
            execution_time=0.0,
            token_cost=0.0,
        )
        r_high_cost = calculate_reward_for_task(
            eval_score=1.0,
            execution_time=0.0,
            token_cost=1.0,
        )
        assert r_high_cost < r_zero
        assert r_high_cost >= 0.0

    def test_boundary_eval_one_is_solved(self):
        from autoppia_web_agents_subnet.validator.evaluation.rewards import (
            calculate_reward_for_task,
        )

        r = calculate_reward_for_task(
            eval_score=1.0,
            execution_time=0.0,
            token_cost=0.0,
        )
        assert r > 0.0
