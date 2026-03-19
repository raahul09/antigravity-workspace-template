"""Tests for hub agent ImportError handling."""
import sys
import pytest
from unittest.mock import patch


def test_build_refresh_agent_import_error():
    """build_refresh_agent raises ImportError with helpful message when agents SDK missing."""
    from antigravity_engine.hub.agents import build_refresh_agent

    with patch.dict(sys.modules, {"agents": None}):
        with pytest.raises(ImportError, match="OpenAI Agent SDK not found"):
            build_refresh_agent("test-model")


def test_build_reviewer_agent_import_error():
    """build_reviewer_agent raises ImportError with helpful message when agents SDK missing."""
    from antigravity_engine.hub.agents import build_reviewer_agent

    with patch.dict(sys.modules, {"agents": None}):
        with pytest.raises(ImportError, match="OpenAI Agent SDK not found"):
            build_reviewer_agent("test-model")
