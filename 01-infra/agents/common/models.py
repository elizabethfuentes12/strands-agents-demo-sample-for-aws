"""Model factory for demo agents.

Nova Pro uses bedrock-runtime (default endpoint).
Claude Haiku 4.5 uses the global. cross-region inference profile and enables
interleaved thinking so the reasoning is visible in the Insights panel.
"""
import os

from strands.models import BedrockModel

REGION = os.environ.get("AWS_REGION", "us-east-1")

# Default model: Nova Pro via bedrock-runtime (env-overridable at deploy time).
DEFAULT_MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

# Claude Sonnet 4.6 — global inference profile, no account activation needed.
CLAUDE_MODEL_ID = "global.anthropic.claude-sonnet-4-6"

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
                "thinking": {"type": "enabled", "budget_tokens": 2000},
            },
        )
    return BedrockModel(model_id=model_id)
