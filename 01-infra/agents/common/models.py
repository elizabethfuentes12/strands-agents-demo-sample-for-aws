"""Model factory for demo agents.

Nova Pro uses the us. cross-region inference profile (US regions only).
Claude Sonnet 4.6 also uses the us. profile with interleaved thinking enabled
so reasoning is visible in the Insights panel. The us. prefix keeps routing
within US regions where the interleaved-thinking beta is supported.
"""
import os

from strands.models import BedrockModel

REGION = os.environ.get("AWS_REGION", "us-east-1")

# Default model: Nova Pro via us. cross-region inference profile.
DEFAULT_MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

# Claude Sonnet 4.6 — us. inference profile so interleaved thinking beta works.
CLAUDE_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# Allowlist of model identifiers the browser may request.
ALLOWED_MODEL_IDS = {DEFAULT_MODEL_ID, CLAUDE_MODEL_ID}


def resolve_model_id(requested: str | None) -> str:
    """Return a safe model ID from a browser request. Falls back to default."""
    if requested and requested in ALLOWED_MODEL_IDS:
        return requested
    return DEFAULT_MODEL_ID


def make_bedrock_model(model_id: str) -> BedrockModel:
    """Return a BedrockModel configured for the given model ID.

    For Claude, enables interleaved thinking so reasoning is emitted as
    reasoningText events visible in the Insights panel.
    """
    if model_id == CLAUDE_MODEL_ID:
        return BedrockModel(
            model_id=model_id,
            additional_request_fields={
                "anthropic_beta": ["interleaved-thinking-2025-05-14"],
                "thinking": {"type": "enabled", "budget_tokens": 8000},
            },
        )
    return BedrockModel(model_id=model_id)
