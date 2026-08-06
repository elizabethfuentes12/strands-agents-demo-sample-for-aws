# 02 · Structured Output

Free text becomes a validated, typed record, field by field.

## What it shows

This fundamentals demo turns a visitor's free-form introduction into a validated, typed object. Instead of returning prose, the agent returns a Pydantic model whose fields are extracted from the text, and the Insights panel renders the schema filling in. The teaching point: the model output is constrained to a schema, so downstream code gets clean, typed data (or explicit nulls) rather than free text to parse.

## How it works

A single Strands `Agent` (see `agent.py`) runs on AgentCore Runtime with a `BedrockModel` (default `us.amazon.nova-pro-v1:0`, overridable via `MODEL_ID`). It uses the Strands structured-output feature: the entrypoint calls

```python
result = await agent.invoke_async(prompt, structured_output_model=EventLead)
lead = result.structured_output
```

`EventLead` is a Pydantic `BaseModel` defined in `agent.py` with these fields:

- `name` (optional)
- `company` (optional)
- `role` (optional)
- `interests` (list of strings, defaults to empty)
- `use_case` (optional)
- `cloud_experience` (optional: beginner, intermediate, or expert)
- `follow_up` (required: a one-sentence suggested follow-up for booth staff)

The system prompt instructs the model to stay faithful to the text and leave unmentioned fields null rather than inventing them. The agent is cached per AgentCore `session_id` for multi-turn memory (`_get_agent`); a new session resets the conversation.

Note that this demo does not define custom tools or hooks. It calls the model once per turn and validates the result against the schema.

## Files

- `agent.py`: the `EventLead` Pydantic model, the agent, and the AgentCore entrypoint that requests structured output.
- `requirements.txt`: `bedrock-agentcore`, `strands-agents[otel]`, `aws-opentelemetry-distro`, `pydantic>=2.0`.

## Events emitted

The entrypoint emits events directly (it does not use the shared streaming translator):

- `structured`: `{type, fields}` where `fields` is the validated `EventLead` as a dict (`lead.model_dump()`). This is what drives the field-by-field render in the panel.
- `token`: a short chat summary (personalized with the extracted name when present).
- `metrics`: token and cycle tally from the Strands `AgentResult` (via `metrics_from_result`).
- `error` / `done`: failure message and end-of-stream marker.

## Run it

Deployed as its own AgentCore Runtime (stack `StrandsDemo02Stack`). From the repo root:

```bash
python scripts/smoke_test.py structured-output "Hi, I'm Dana from Acme, a data engineer interested in RAG and agents."
```

Watch the `name`, `company`, `role`, `interests`, `use_case`, `cloud_experience`, and `follow_up` fields populate in the panel, with unmentioned fields left null.
