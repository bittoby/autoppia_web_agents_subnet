from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from autoppia_web_agents_subnet.validator.round_start.synapse_handler import (
    send_start_round_synapse_to_miners,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_start_round_synapse_sets_version_and_logs_success():
    validator = SimpleNamespace(version="2.3.4", dendrite=Mock())
    start_synapse = SimpleNamespace(version=None)
    miner_axons = [Mock(), Mock(), Mock()]
    responses = [
        SimpleNamespace(agent_name="miner-a"),
        SimpleNamespace(agent_name=None),
        None,
    ]

    with (
        patch("autoppia_web_agents_subnet.validator.round_start.synapse_handler.dendrite_with_retries", new=AsyncMock(return_value=responses)) as mock_dendrite,
        patch("autoppia_web_agents_subnet.validator.round_start.synapse_handler.bt.logging.success") as mock_success,
    ):
        out = await send_start_round_synapse_to_miners(validator, miner_axons, start_synapse, timeout=12)

    assert start_synapse.version == "2.3.4"
    assert out == responses
    mock_dendrite.assert_awaited_once()
    kwargs = mock_dendrite.await_args.kwargs
    assert kwargs["timeout"] == 12
    assert kwargs["retries"] == 3
    mock_success.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_start_round_synapse_logs_warning_when_no_valid_names():
    validator = SimpleNamespace(version="1.0.0", dendrite=Mock())
    start_synapse = SimpleNamespace(version=None)
    miner_axons = [Mock(), Mock()]
    responses = [None, SimpleNamespace(agent_name="")]

    with (
        patch("autoppia_web_agents_subnet.validator.round_start.synapse_handler.dendrite_with_retries", new=AsyncMock(return_value=responses)),
        patch("autoppia_web_agents_subnet.validator.round_start.synapse_handler.bt.logging.warning") as mock_warning,
    ):
        out = await send_start_round_synapse_to_miners(validator, miner_axons, start_synapse)

    assert out == responses
    mock_warning.assert_called_once()
