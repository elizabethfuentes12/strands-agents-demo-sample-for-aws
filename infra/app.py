#!/usr/bin/env python3
"""CDK app: Strands Agents demo showcase.

Stacks:
- StrandsDemosBaseStack: Cognito + AppSync Events API + dispatcher Lambda.
- StrandsDemo01Stack..: one AgentCore Runtime per demo.
"""
import os

import aws_cdk as cdk

from stacks.base_stack import BaseStack
from stacks.demo_stack import DemoStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

base = BaseStack(app, "StrandsDemosBaseStack", env=env)

DEMOS = [
    {"demo_id": "01", "slug": "agent-loop", "agent_dir": "01-agent-loop"},
    {"demo_id": "02", "slug": "structured-output", "agent_dir": "02-structured-output"},
    {"demo_id": "03", "slug": "hooks-guardian", "agent_dir": "03-hooks-guardian"},
    {"demo_id": "04", "slug": "human-in-the-loop", "agent_dir": "04-human-in-the-loop"},
    {"demo_id": "05", "slug": "observability", "agent_dir": "05-observability"},
    {"demo_id": "06", "slug": "swarm", "agent_dir": "06-swarm"},
    {"demo_id": "07", "slug": "token-optimization", "agent_dir": "07-token-optimization"},
    {"demo_id": "08", "slug": "graph", "agent_dir": "08-graph"},
    {"demo_id": "09", "slug": "agents-as-tools", "agent_dir": "09-agents-as-tools"},
    {"demo_id": "10", "slug": "memory-poisoning", "agent_dir": "10-memory-poisoning"},
    {"demo_id": "11", "slug": "chaos-resilience", "agent_dir": "11-chaos-resilience"},
]

demo_stacks = []
for demo in DEMOS:
    stack = DemoStack(
        app,
        f"StrandsDemo{demo['demo_id']}Stack",
        demo_id=demo["demo_id"],
        slug=demo["slug"],
        agent_dir=demo["agent_dir"],
        env=env,
    )
    stack.add_dependency(base)
    demo_stacks.append(stack)


# Web hosting (S3 + CloudFront) lives in its own CDK app under ../web-infra so
# the site can be deployed and torn down independently of the agent runtimes.

app.synth()
