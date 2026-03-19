"""OpenAI Agent SDK agents for the Knowledge Hub."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from antigravity_engine.config import Settings


def create_model(settings: "Settings") -> str:
    """Resolve an LLM model identifier from settings.

    Priority:
    1. GOOGLE_API_KEY              → litellm/gemini/<model_name>
    2. OPENAI_BASE_URL (any key)   → litellm/openai/<model> (custom endpoint)
    3. OPENAI_API_KEY (no base)    → <OPENAI_MODEL> (standard OpenAI)
    4. None                        → raise ValueError

    When a custom OPENAI_BASE_URL is provided (e.g. NVIDIA, Ollama), the
    model is routed through litellm so that the Agent SDK can reach the
    non-standard endpoint.  The function also exports OPENAI_API_BASE for
    litellm discovery.

    Args:
        settings: Application settings.

    Returns:
        A model string suitable for openai-agents[litellm].

    Raises:
        ValueError: When no LLM backend is configured.
    """
    import os

    if settings.GOOGLE_API_KEY:
        return f"litellm/gemini/{settings.GEMINI_MODEL_NAME}"

    # Custom endpoint (NVIDIA, Ollama, etc.) — route through litellm
    if settings.OPENAI_BASE_URL:
        os.environ.setdefault("OPENAI_API_BASE", settings.OPENAI_BASE_URL)
        if settings.OPENAI_API_KEY:
            os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)
        return f"litellm/openai/{settings.OPENAI_MODEL}"

    # Standard OpenAI (no custom base URL)
    if settings.OPENAI_API_KEY:
        return settings.OPENAI_MODEL

    raise ValueError(
        "No LLM configured. Set GOOGLE_API_KEY, OPENAI_API_KEY, "
        "or OPENAI_BASE_URL in .env"
    )


_REFRESH_INSTRUCTIONS = """\
You are a project analyst. Given a project scan report, produce a concise
conventions document in Markdown. Cover:
- Primary language(s) and framework(s)
- Project structure overview
- Code style observations
- Testing approach
- CI/CD setup
Keep it under 300 words. Output ONLY the Markdown content, no preamble.
"""

_REVIEW_INSTRUCTIONS = """\
You are a senior code reviewer. Given project context and a user question,
provide a clear, actionable answer. Reference specific files/patterns from the
context when possible. Be concise — under 200 words unless the question demands
more.
"""


def build_refresh_agent(model: str):
    """Build a refresh agent using the OpenAI Agent SDK.

    Args:
        model: Model identifier string.

    Returns:
        An Agent instance configured for project refresh.
    """
    try:
        from agents import Agent
    except ImportError:
        raise ImportError(
            "OpenAI Agent SDK not found. Install: pip install antigravity-engine"
        ) from None

    return Agent(
        name="RefreshAgent",
        instructions=_REFRESH_INSTRUCTIONS,
        model=model,
    )


def build_reviewer_agent(model: str):
    """Build a reviewer agent for answering project questions.

    Args:
        model: Model identifier string.

    Returns:
        An Agent instance configured for Q&A.
    """
    try:
        from agents import Agent
    except ImportError:
        raise ImportError(
            "OpenAI Agent SDK not found. Install: pip install antigravity-engine"
        ) from None

    return Agent(
        name="ReviewerAgent",
        instructions=_REVIEW_INSTRUCTIONS,
        model=model,
    )
