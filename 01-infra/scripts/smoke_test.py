"""End-to-end smoke test: browser-equivalent flow through AppSync Events.

Subscribes (WebSocket, Cognito JWT) to out/<demo>/<session>, publishes a
prompt (HTTP, Cognito JWT) to inbox/<demo>/<session>, and prints the typed
events streamed back by the demo agent until `done`.

Usage:
  AWS_PROFILE=asistant-vm python smoke_test.py [demo-slug] [prompt]
Requires: websockets, boto3 (uv pip install websockets boto3).
Credentials: KIOSK_USERNAME/KIOSK_PASSWORD env vars (defaults: kiosk / demo pass).
"""
import asyncio
import base64
import json
import os
import sys
import uuid
import urllib.request

import boto3
import websockets

REGION = os.environ.get("AWS_REGION", "us-east-1")
SSM_PREFIX = "/strands-demos"

session = boto3.Session(region_name=REGION)
ssm = session.client("ssm")


def get_param(name: str) -> str:
    return ssm.get_parameter(Name=f"{SSM_PREFIX}/{name}")["Parameter"]["Value"]


def cognito_token(client_id: str) -> str:
    idp = session.client("cognito-idp")
    resp = idp.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        ClientId=client_id,
        AuthParameters={
            "USERNAME": os.environ.get("KIOSK_USERNAME", "kiosk"),
            "PASSWORD": os.environ["KIOSK_PASSWORD"],  # required env var, never hardcoded
        },
    )
    return resp["AuthenticationResult"]["AccessToken"]


def b64url(data: dict) -> str:
    raw = base64.b64encode(json.dumps(data).encode()).decode()
    return raw.replace("+", "-").replace("/", "_").rstrip("=")


async def main():
    demo = sys.argv[1] if len(sys.argv) > 1 else "agent-loop"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "What is 23*47? And what is Amazon Bedrock?"

    http_domain = get_param("events_http_domain")
    realtime_domain = get_param("events_realtime_domain")
    client_id = get_param("user_pool_client_id")
    token = cognito_token(client_id)

    session_id = f"smoke-{uuid.uuid4().hex}"
    out_channel = f"out/{demo}/{session_id}"
    inbox_channel = f"inbox/{demo}/{session_id}"

    auth = {"host": http_domain, "authorization": token}
    ws_url = f"wss://{realtime_domain}/event/realtime"

    async with websockets.connect(
        ws_url,
        subprotocols=["aws-appsync-event-ws", f"header-{b64url(auth)}"],
    ) as ws:
        await ws.send(json.dumps({"type": "connection_init"}))
        while json.loads(await ws.recv()).get("type") != "connection_ack":
            pass
        sub_id = str(uuid.uuid4())
        await ws.send(
            json.dumps(
                {
                    "type": "subscribe",
                    "id": sub_id,
                    "channel": out_channel,
                    "authorization": auth,
                }
            )
        )
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "subscribe_success":
                break
            if msg.get("type") == "subscribe_error":
                raise SystemExit(f"subscribe_error: {msg}")
        print(f"subscribed to {out_channel}")

        # Publish the prompt over HTTP with the Cognito JWT.
        body = json.dumps(
            {"channel": inbox_channel, "events": [json.dumps({"prompt": prompt})]}
        )
        req = urllib.request.Request(
            f"https://{http_domain}/event",
            data=body.encode(),
            headers={"content-type": "application/json", "authorization": token},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            print("publish:", resp.status)

        # Collect agent events until `done` AND every earlier seq arrived
        # (AppSync fan-out does not guarantee ordering across publishes).
        events_by_seq: dict = {}
        done_seq = None
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
                msg = json.loads(raw)
                if msg.get("type") != "data":
                    continue
                event = json.loads(msg["event"])
                seq = event.get("seq", len(events_by_seq))
                events_by_seq[seq] = event
                if event["type"] == "done":
                    done_seq = seq
                if done_seq is not None and all(
                    s in events_by_seq for s in range(done_seq + 1)
                ):
                    break
        except asyncio.TimeoutError:
            got = sorted(events_by_seq)
            raise SystemExit(f"TIMEOUT. done_seq={done_seq}, seqs received={got}")

        ordered = [events_by_seq[s] for s in sorted(events_by_seq)]
        types = [e["type"] for e in ordered]
        for e in ordered:
            if e["type"] != "token":
                print(f"[{e['type']}]", {k: v for k, v in e.items() if k not in ("type", "seq")})
        print("\n--- agent text ---")
        print("".join(e["text"] for e in ordered if e["type"] == "token")[:500])
        has_metrics = "metrics" in types or "swarm_metrics" in types or "comparison" in types
        assert has_metrics and types[-1] == "done", types
        print(f"\nSMOKE TEST OK — {len(types)} events in order: {sorted(set(types))}")


if __name__ == "__main__":
    asyncio.run(main())
