#!/usr/bin/env python3
"""CDK app: Strands Agents demo showcase — frontend.

Deploys the static web hosting stack (private S3 + CloudFront with OAC).
Requires web/.env.local (Cognito + AppSync outputs from 01-infra); the SPA
is built at synth time.

Run after 01-infra is deployed:
    cd 02-frontend && cdk deploy
"""
import os

import aws_cdk as cdk

from frontend.web_stack import WebStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

WebStack(app, "StrandsDemosWebStack", env=env)

app.synth()
