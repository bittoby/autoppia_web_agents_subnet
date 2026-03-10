"""
Unit tests for protocol (StartRoundSynapse).
"""

import pytest

pytest.importorskip("bittensor")


@pytest.mark.unit
class TestStartRoundSynapse:
    def test_start_round_synapse_defaults(self):
        from autoppia_web_agents_subnet.protocol import StartRoundSynapse

        s = StartRoundSynapse(round_id="r1")
        assert s.round_id == "r1"
        assert s.version == ""
        assert s.validator_id is None
        assert s.note is None
        assert s.agent_name is None
        assert s.github_url is None
        assert s.agent_image is None

    def test_start_round_synapse_response_fields(self):
        from autoppia_web_agents_subnet.protocol import StartRoundSynapse

        s = StartRoundSynapse(
            round_id="r2",
            agent_name="MyAgent",
            github_url="https://github.com/foo/bar",
            agent_image="https://example.com/logo.png",
        )
        assert s.agent_name == "MyAgent"
        assert s.github_url == "https://github.com/foo/bar"
        assert s.agent_image == "https://example.com/logo.png"

    def test_deserialize_returns_self(self):
        from autoppia_web_agents_subnet.protocol import StartRoundSynapse

        s = StartRoundSynapse(round_id="r3")
        out = s.deserialize()
        assert out is s
