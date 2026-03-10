"""
Unit tests for autoppia_web_agents_subnet.utils.log_colors.

Tests that tag functions return strings containing expected markers and ANSI codes.
"""

import pytest


@pytest.mark.unit
class TestLogColors:
    def test_ipfs_tag(self):
        from autoppia_web_agents_subnet.utils.log_colors import ipfs_tag

        out = ipfs_tag("UPLOAD", "test message")
        assert "[IPFS]" in out
        assert "[UPLOAD]" in out
        assert "test message" in out
        assert "\033" in out

    def test_consensus_tag(self):
        from autoppia_web_agents_subnet.utils.log_colors import consensus_tag

        out = consensus_tag("msg")
        assert "[CONSENSUS]" in out
        assert "msg" in out

    def test_iwap_tag(self):
        from autoppia_web_agents_subnet.utils.log_colors import iwap_tag

        out = iwap_tag("context", "msg")
        assert "[IWAP]" in out
        assert "[context]" in out
        assert "msg" in out

    def test_checkpoint_tag(self):
        from autoppia_web_agents_subnet.utils.log_colors import checkpoint_tag

        out = checkpoint_tag("msg")
        assert "[CHECKPOINT]" in out
        assert "msg" in out

    def test_evaluation_tag(self):
        from autoppia_web_agents_subnet.utils.log_colors import evaluation_tag

        out = evaluation_tag("ctx", "msg")
        assert "[EVALUATION]" in out
        assert "[ctx]" in out
        assert "msg" in out

    def test_round_details_tag(self):
        from autoppia_web_agents_subnet.utils.log_colors import round_details_tag

        out = round_details_tag("msg")
        assert "[ROUND DETAILS]" in out
        assert "msg" in out

    def test_reset_code_present(self):
        from autoppia_web_agents_subnet.utils.log_colors import RESET, consensus_tag

        assert RESET == "\033[0m"
        out = consensus_tag("x")
        assert out.endswith(f"{RESET} x")
