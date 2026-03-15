from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import HTTPStatusError, Request, Response

os.environ.setdefault("TESTING", "True")
os.environ.setdefault("VALIDATOR_NAME", "Test Validator")
os.environ.setdefault("VALIDATOR_IMAGE", "https://example.com/validator.png")

if "bittensor" not in sys.modules:
    bt_stub = types.ModuleType("bittensor")
    bt_stub.logging = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        debug=lambda *args, **kwargs: None,
        critical=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
    )
    bt_stub.utils = SimpleNamespace(RAO_PER_TAO=1_000_000_000)
    sys.modules["bittensor"] = bt_stub

from autoppia_web_agents_subnet.platform.utils.round_flow import finish_round_flow


def _http_error(status_code: int, detail):
    payload = detail if isinstance(detail, dict) and "detail" in detail else {"detail": detail}
    response = Response(status_code=status_code, json=payload, request=Request("POST", "https://iwap.test/finish"))
    return HTTPStatusError(f"HTTP {status_code}", request=response.request, response=response)


def _make_agent_run(agent_run_id: str):
    return SimpleNamespace(agent_run_id=agent_run_id, started_at=1000.0, ended_at=None, elapsed_sec=None)


def _make_finish_ctx(tmp_path: Path):
    ctx = SimpleNamespace()
    ctx.current_round_id = "validator_round_1_5_finish"
    ctx.uid = 83
    ctx.version = "20.0.0"
    ctx.round_start_time = 1000.0
    ctx.active_miner_uids = {48}
    ctx.current_agent_runs = {48: _make_agent_run("run-48")}
    ctx.current_miner_snapshots = {}
    ctx.current_round_tasks = {}
    ctx.agent_run_accumulators = {}
    ctx._agg_scores_cache = {}
    ctx._agg_meta_cache = {}
    ctx._best_runs = {}
    ctx._current_runs = {
        48: {
            "reward": 0.4,
            "score": 0.4,
            "time": 10.0,
            "cost": 0.02,
            "tasks_received": 100,
            "tasks_success": 40,
            "failed_tasks": 60,
        }
    }
    ctx._best_run_payload_for_miner = lambda uid: ctx._best_runs.get(uid)
    ctx._current_round_run_payload = lambda uid: ctx._current_runs.get(uid)
    ctx._ipfs_uploaded_payload = None
    ctx._ipfs_upload_cid = None
    ctx._consensus_commit_cid = None
    ctx._consensus_publish_timestamp = None
    ctx._consensus_reveal_round = 0
    ctx._iwap_offline_mode = False
    ctx._state_summary_root = Mock(return_value=tmp_path / "state")
    ctx._reset_iwap_round_state = Mock()
    ctx._upload_round_log_snapshot = AsyncMock(return_value="https://logs.example/round.log")
    ctx._persist_round_checkpoint = Mock()
    ctx.iwap_client = SimpleNamespace(finish_round=AsyncMock(return_value=None))
    ctx.wallet = SimpleNamespace(
        hotkey=SimpleNamespace(ss58_address="5FValidator"),
        coldkeypub=SimpleNamespace(ss58_address="5FColdkey"),
    )
    ctx.metagraph = SimpleNamespace(
        hotkeys=["hotkey0"] * 300,
        coldkeys=["coldkey0"] * 300,
    )
    ctx.config = SimpleNamespace(neuron=SimpleNamespace(full_path=str(tmp_path / "validator")))
    Path(ctx.config.neuron.full_path).mkdir(parents=True, exist_ok=True)
    ctx.season_manager = SimpleNamespace(season_number=1)
    ctx.round_manager = SimpleNamespace(
        round_number=5,
        round_rewards={},
        round_eval_scores={},
        round_times={},
        round_size_epochs=5.0,
        season_size_epochs=100.0,
        minimum_start_block=7736300,
        BLOCKS_PER_EPOCH=360,
        block_to_epoch=Mock(side_effect=lambda block: float(block) / 360.0),
        get_current_boundaries=Mock(
            return_value={
                "round_start_block": 7747761,
                "target_block": 7749561,
                "round_start_epoch": 21521.56,
                "target_epoch": 21526.56,
            }
        ),
    )
    ctx.agents_dict = {48: SimpleNamespace(agent_name="Miner 48")}
    ctx.handshake_results = {"48": "ok"}
    ctx.eligibility_status_by_uid = {48: "evaluated"}
    return ctx


@pytest.mark.integration
@pytest.mark.asyncio
async def test_finish_round_offline_mode_cleans_up_locally_and_returns_true(tmp_path):
    ctx = _make_finish_ctx(tmp_path)
    ctx._iwap_offline_mode = True

    success = await finish_round_flow(ctx, avg_rewards={48: 0.4}, final_weights={48: 1.0}, tasks_completed=40)

    assert success is True
    ctx.iwap_client.finish_round.assert_not_called()
    ctx._reset_iwap_round_state.assert_called_once()
    ctx._persist_round_checkpoint.assert_called_once_with(reason="finish_round_offline", status="completed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_finish_round_main_success_persists_completed_checkpoint(tmp_path):
    ctx = _make_finish_ctx(tmp_path)

    success = await finish_round_flow(ctx, avg_rewards={48: 0.4}, final_weights={48: 1.0}, tasks_completed=40)

    assert success is True
    ctx.iwap_client.finish_round.assert_awaited_once()
    ctx._persist_round_checkpoint.assert_called_once_with(reason="finish_round_completed", status="completed")
    ctx._reset_iwap_round_state.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_finish_round_authority_grace_retries_then_succeeds(tmp_path):
    ctx = _make_finish_ctx(tmp_path)
    grace_error = _http_error(409, "main validator still within finish grace")
    ctx.iwap_client.finish_round = AsyncMock(side_effect=[grace_error, grace_error, None])

    with (
        patch("autoppia_web_agents_subnet.platform.utils.round_flow.validator_config.FINISH_ROUND_MAX_RETRIES", 2),
        patch("autoppia_web_agents_subnet.platform.utils.round_flow.validator_config.FINISH_ROUND_RETRY_SECONDS", 10),
        patch("autoppia_web_agents_subnet.platform.utils.round_flow.asyncio.sleep", new=AsyncMock()),
    ):
        success = await finish_round_flow(ctx, avg_rewards={48: 0.4}, final_weights={48: 1.0}, tasks_completed=40)

    assert success is True
    assert ctx.iwap_client.finish_round.await_count == 3
    ctx._persist_round_checkpoint.assert_called_once_with(reason="finish_round_completed", status="completed")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_finish_round_generic_failure_uses_fallback_payload_and_completes(tmp_path):
    ctx = _make_finish_ctx(tmp_path)
    primary_error = _http_error(500, "backend exploded")
    ctx.iwap_client.finish_round = AsyncMock(side_effect=[primary_error, None])

    success = await finish_round_flow(ctx, avg_rewards={48: 0.4}, final_weights={48: 1.0}, tasks_completed=40)

    assert success is True
    assert ctx.iwap_client.finish_round.await_count == 2
    fallback_request = ctx.iwap_client.finish_round.await_args_list[1].kwargs["finish_request"]
    assert fallback_request.summary["round_closure_error"]["status"] == "failed_on_finish_round"
    ctx._persist_round_checkpoint.assert_called_once_with(reason="finish_round_fallback_completed", status="completed")
