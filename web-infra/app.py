#!/usr/bin/env python3
"""Standalone CDK app: static web hosting for the Strands demos showcase.

Deploys a single stack (private S3 + CloudFront with OAC) that serves the built
React SPA. Kept independent from the agents infra (../infra) so the site can be
deployed and torn down on its own:

    cd web-infra && cdk deploy

Requires web/.env.local (Cognito + AppSync outputs); the SPA is built at synth.
"""
import os

import aws_cdk as cdk

from stacks.web_stack import WebStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

WebStack(app, "StrandsDemosWebStack", env=env)

app.synth()
