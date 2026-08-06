"""Parameterized stack: one AgentCore Runtime per demo."""
import os

from aws_cdk import CfnOutput, Stack, aws_ssm as ssm
from constructs import Construct

from constructs_local.agentcore_role import AgentCoreRole
from constructs_local.agentcore_runtime import AgentCoreRuntime

SSM_PREFIX = "/strands-demos"
# Anthropic models are gated in this account (use case form not submitted);
# Nova Pro is verified accessible.
DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"


class DemoStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        demo_id: str,
        slug: str,
        agent_dir: str,
        extra_env: dict | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        role = AgentCoreRole(self, "RuntimeRole", demo_id=demo_id)

        env_vars = {
            "MODEL_ID": os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
            "DEMO_ID": demo_id,
            "DEMO_SLUG": slug,
        }
        if extra_env:
            env_vars.update(extra_env)

        runtime = AgentCoreRuntime(
            self,
            "Runtime",
            demo_id=demo_id,
            agent_dir=agent_dir,
            role=role.role,
            environment_variables=env_vars,
        )

        ssm.StringParameter(
            self,
            "RuntimeArnParam",
            parameter_name=f"{SSM_PREFIX}/{slug}/runtime_arn",
            string_value=runtime.runtime_arn,
        )
        CfnOutput(self, "RuntimeArn", value=runtime.runtime_arn)
