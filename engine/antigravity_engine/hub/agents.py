"""OpenAI Agent SDK agents for the Knowledge Hub."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from antigravity_engine.config import Settings


def create_model(settings: "Settings") -> str:
    """Resolve an LLM model identifier from settings.

    Priority:
    1. GOOGLE_API_KEY  → gemini/<model_name> via litellm
    2. OPENAI_API_KEY  → <OPENAI_MODEL>
    3. OPENAI_BASE_URL → <OPENAI_MODEL> (local Ollama etc.)
    4. None            → raise ValueError

    Args:
        settings: Application settings.

    Returns:
        A model string suitable for openai-agents[litellm].

    Raises:
        ValueError: When no LLM backend is configured.
    """
    if settings.GOOGLE_API_KEY:
        return f"litellm/gemini/{settings.GEMINI_MODEL_NAME}"

    if settings.OPENAI_API_KEY:
        return settings.OPENAI_MODEL

    if settings.OPENAI_BASE_URL:
        return f"litellm/openai/{settings.OPENAI_MODEL}"

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
    from agents import Agent

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
    from agents import Agent

    return Agent(
        name="ReviewerAgent",
        instructions=_REVIEW_INSTRUCTIONS,
        model=model,
    )
