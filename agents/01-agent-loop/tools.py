"""Custom tool for demo 01: a tiny offline AWS service catalog lookup."""
from strands import tool

# Small, static catalog so the demo works without network calls.
_CATALOG = {
    "bedrock": "Amazon Bedrock: fully managed foundation models via a single API.",
    "agentcore": "Amazon Bedrock AgentCore: secure serverless runtime for AI agents with per-session microVM isolation.",
    "lambda": "AWS Lambda: run code without provisioning servers, pay per millisecond.",
    "s3": "Amazon S3: object storage with 11 nines of durability.",
    "dynamodb": "Amazon DynamoDB: serverless NoSQL database with single-digit millisecond latency.",
    "appsync": "AWS AppSync Events: serverless WebSocket APIs for real-time pub/sub.",
    "amplify": "AWS Amplify: build and host full-stack web and mobile apps.",
}


@tool
def aws_service_lookup(service_name: str) -> str:
    """Look up a short description of an AWS service by name.

    Args:
        service_name: Name of the AWS service, e.g. "bedrock" or "lambda".
    """
    key = service_name.lower().strip().replace("amazon ", "").replace("aws ", "")
    for name, description in _CATALOG.items():
        if name in key:
            return description
    return f"Service '{service_name}' is not in the demo catalog. Known: {', '.join(_CATALOG)}."
