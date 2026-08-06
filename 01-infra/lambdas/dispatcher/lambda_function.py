"""Dispatcher: AppSync Events inbox -> AgentCore Runtime -> AppSync Events out.

Invoked asynchronously (InvokeType=EVENT) by the AppSync Events direct Lambda
integration when the browser publishes to ``inbox/<demo>/<sessionId>``.
Streams the AgentCore response and republishes each typed JSON event to
``out/<demo>/<sessionId>`` over the Events HTTP endpoint (IAM auth).
"""
import json
import logging
import os
import time
import urllib.request

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EVENTS_HTTP_DOMAIN = os.environ["EVENTS_HTTP_DOMAIN"]
SSM_PREFIX = os.environ.get("SSM_PREFIX", "/strands-demos")
REGION = os.environ.get("AWS_REGION", "us-east-1")

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds; retries 424/429/500 from AgentCore

_session = boto3.Session()
# Long read timeout: agent streams can run for minutes. Retries are handled
# manually in _invoke_agentcore, so botocore's are disabled.
_agentcore = _session.client(
    "bedrock-agentcore",
    region_name=REGION,
    config=Config(read_timeout=900, retries={"max_attempts": 0}),
)
_ssm = _session.client("ssm", region_name=REGION)
_runtime_arn_cache: dict = {}
_api_key_cache: dict = {}


def _events_api_key() -> str:
    if "key" not in _api_key_cache:
        param = _ssm.get_parameter(Name=f"{SSM_PREFIX}/events_api_key")
        _api_key_cache["key"] = param["Parameter"]["Value"]
    return _api_key_cache["key"]


def _runtime_arn(demo: str) -> str:
    if demo not in _runtime_arn_cache:
        param = _ssm.get_parameter(Name=f"{SSM_PREFIX}/{demo}/runtime_arn")
        _runtime_arn_cache[demo] = param["Parameter"]["Value"]
    return _runtime_arn_cache[demo]


def _publish(channel: str, events: list) -> None:
    """Publish up to 5 events per call to the Events API HTTP endpoint."""
    for i in range(0, len(events), 5):
        body = json.dumps(
            {"channel": channel, "events": [json.dumps(e) for e in events[i : i + 5]]}
        )
        req = urllib.request.Request(
            f"https://{EVENTS_HTTP_DOMAIN}/event",
            data=body.encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": _events_api_key(),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()


def _invoke_agentcore(arn: str, session_id: str, payload: dict):
    """Invoke the runtime with retries for cold-start/throttle errors."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return _agentcore.invoke_agent_runtime(
                agentRuntimeArn=arn,
                # AgentCore requires session ids of at least 33 characters.
                runtimeSessionId=session_id.ljust(33, "0"),
                payload=json.dumps(payload).encode(),
            )
        except (
            _agentcore.exceptions.RuntimeClientError,
            _agentcore.exceptions.InternalServerException,
            _agentcore.exceptions.ThrottlingException,
        ) as exc:
            last_error = exc
            delay = RETRY_BASE_DELAY * (2**attempt)
            logger.warning("AgentCore error (attempt %s): %s", attempt + 1, exc)
            time.sleep(delay)
    raise last_error


def _iter_chunks(response):
    """Yield decoded text chunks from an InvokeAgentRuntime response."""
    stream = response.get("response", [])
    for chunk in stream:
        if isinstance(chunk, bytes):
            yield chunk.decode("utf-8")
        elif isinstance(chunk, dict) and "bytes" in chunk:
            yield chunk["bytes"].decode("utf-8")


def _iter_events(response):
    """Yield JSON events from the runtime's SSE-style stream.

    The agent entrypoint yields JSON objects; AgentCore delivers them as
    ``data: {...}`` SSE lines. Also tolerates plain JSON-per-chunk.
    """
    buffer = ""
    for text in _iter_chunks(response):
        buffer += text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            yield _parse_event(line)
    tail = buffer.strip()
    if tail:
        if tail.startswith("data:"):
            tail = tail[len("data:") :].strip()
        yield _parse_event(tail)


def _parse_event(line: str) -> dict:
    """Parse one SSE data line into an event dict.

    AgentCore JSON-encodes each value the entrypoint yields, so a yielded
    JSON string arrives double-encoded: ``data: "{\\"type\\": ...}"``.
    Unwrap until we get a dict; anything else becomes a token event.
    """
    value = line
    for _ in range(2):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            break
        if isinstance(value, dict):
            return value
    return {"type": "token", "text": value if isinstance(value, str) else line}


def _process_message(demo: str, session_id: str, message: dict) -> None:
    out_channel = f"out/{demo}/{session_id}"
    try:
        payload = {"prompt": message.get("prompt", ""), "demo": demo}
        # Forward optional fields from the browser payload to the agent.
        if "interrupt_response" in message:
            payload["interrupt_response"] = message["interrupt_response"]
        if "model" in message:
            payload["model"] = message["model"]
        response = _invoke_agentcore(_runtime_arn(demo), session_id, payload)
        # AppSync fan-out does not guarantee ordering across publishes, so
        # every event carries a sequence number for the client to sort on.
        seq = 0
        batch = []
        for event in _iter_events(response):
            event["seq"] = seq
            seq += 1
            batch.append(event)
            # Small batches keep the UI feeling live without one call per token.
            if len(batch) >= 5:
                _publish(out_channel, batch)
                batch = []
        if batch:
            _publish(out_channel, batch)
        _publish(out_channel, [{"type": "done", "seq": seq}])
    except Exception:
        logger.exception("Failed processing message for %s/%s", demo, session_id)
        _publish(
            out_channel,
            [
                {
                    "type": "error",
                    "message": "The agent could not process the message. Please try again.",
                    "seq": 0,
                },
                {"type": "done", "seq": 1},
            ],
        )


def lambda_handler(event, context):
    channel_path = (event.get("info") or {}).get("channel", {}).get("path", "")
    # channel path: /inbox/<demo>/<sessionId>
    parts = [p for p in channel_path.split("/") if p]
    if len(parts) != 3 or parts[0] != "inbox":
        logger.error("Unexpected channel path: %s", channel_path)
        return
    demo, session_id = parts[1], parts[2]

    for item in event.get("events", []):
        payload = item.get("payload") if isinstance(item, dict) else None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"prompt": payload}
        if isinstance(payload, dict):
            _process_message(demo, session_id, payload)
