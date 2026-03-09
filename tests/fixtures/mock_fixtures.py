"""
Mock fixtures for external dependencies.

Provides mocks for:
- IPFS client (in-memory storage)
- AsyncSubtensor (commitment storage)
- IWAP client (all endpoints)
- SandboxManager (without Docker)
"""

import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def mock_ipfs_client() -> Mock:
    """
    Mock IPFS client with in-memory storage.

    Simulates IPFS operations without requiring an actual IPFS node.
    Stores data in memory and returns deterministic CIDs.
    """
    storage: dict[str, bytes] = {}
    cid_counter = [0]  # Use list for mutability in closure

    def add_json(data: dict[str, Any]) -> str:
        """Add JSON data and return a mock CID."""
        cid_counter[0] += 1
        cid = f"Qm{'0' * 44}{cid_counter[0]:04d}"
        storage[cid] = json.dumps(data).encode()
        return cid

    def cat(cid: str) -> bytes | None:
        """Retrieve data by CID."""
        return storage.get(cid)

    def get_json(cid: str) -> dict[str, Any] | None:
        """Retrieve and parse JSON data by CID."""
        data = storage.get(cid)
        if data:
            return json.loads(data.decode())
        return None

    client = Mock()
    client.add_json = Mock(side_effect=add_json)
    client.cat = Mock(side_effect=cat)
    client.get_json = Mock(side_effect=get_json)
    client.storage = storage  # Expose for test inspection

    return client


@pytest.fixture
def mock_async_subtensor() -> Mock:
    """
    Mock AsyncSubtensor with commitment storage.

    Simulates blockchain operations without requiring actual network connection.
    Stores commitments in memory.
    """
    commitments: dict[int, list[dict[str, Any]]] = {}  # uid -> list of commits

    async def commit(uid: int, data: dict[str, Any]) -> bool:
        """Store a commitment for a validator."""
        if uid not in commitments:
            commitments[uid] = []
        commitments[uid].append(data)
        return True

    async def get_commitments(netuid: int, block: int | None = None) -> dict[int, Any]:
        """Retrieve all commitments for a subnet."""
        # Return the latest commitment for each validator
        result = {}
        for uid, commits in commitments.items():
            if commits:
                result[uid] = commits[-1]
        return result

    async def get_commitment(uid: int, netuid: int, block: int | None = None) -> dict[str, Any] | None:
        """Retrieve commitment for a specific validator."""
        if commitments.get(uid):
            return commitments[uid][-1]
        return None

    subtensor = Mock()
    subtensor.commit = AsyncMock(side_effect=commit)
    subtensor.get_commitments = AsyncMock(side_effect=get_commitments)
    subtensor.get_commitment = AsyncMock(side_effect=get_commitment)
    subtensor.commitments = commitments  # Expose for test inspection

    return subtensor


@pytest.fixture
def mock_iwap_client() -> Mock:
    """
    Mock IWAP (IWA Platform) client with all endpoints.

    Simulates the platform API without requiring actual service.
    """

    async def evaluate_agent(agent_url: str, task: dict[str, Any]) -> dict[str, Any]:
        """Mock agent evaluation."""
        return {
            "score": 0.8,
            "success": True,
            "actions": [
                {"type": "click", "selector": "#test"},
            ],
        }

    async def health_check() -> bool:
        """Mock health check."""
        return True

    client = Mock()
    client.evaluate_agent = AsyncMock(side_effect=evaluate_agent)
    client.health_check = AsyncMock(side_effect=health_check)

    return client


@pytest.fixture
def mock_sandbox_manager() -> Mock:
    """
    Mock SandboxManager without Docker.

    Simulates agent deployment and cleanup without requiring Docker.
    Useful for testing evaluation logic without container overhead.
    """
    deployed_agents: dict[int, dict[str, Any]] = {}

    async def deploy_agent(uid: int, github_url: str, agent_name: str) -> bool:
        """Mock agent deployment."""
        deployed_agents[uid] = {
            "github_url": github_url,
            "agent_name": agent_name,
            "base_url": f"http://localhost:{8000 + uid}",
        }
        return True

    async def cleanup_agent(uid: int) -> bool:
        """Mock agent cleanup."""
        if uid in deployed_agents:
            del deployed_agents[uid]
            return True
        return False

    async def cleanup_all_agents() -> None:
        """Mock cleanup all agents."""
        deployed_agents.clear()

    def get_base_url(uid: int) -> str | None:
        """Get base URL for deployed agent."""
        if uid in deployed_agents:
            return deployed_agents[uid]["base_url"]
        return None

    async def health_check(uid: int) -> bool:
        """Mock health check for deployed agent."""
        return uid in deployed_agents

    manager = Mock()
    manager.deploy_agent = AsyncMock(side_effect=deploy_agent)
    manager.cleanup_agent = Mock(side_effect=cleanup_agent)
    manager.cleanup_all_agents = Mock(side_effect=cleanup_all_agents)
    manager.get_base_url = Mock(side_effect=get_base_url)
    manager.health_check = AsyncMock(side_effect=health_check)
    manager.deployed_agents = deployed_agents  # Expose for test inspection

    return manager
