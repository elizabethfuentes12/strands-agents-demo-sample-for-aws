"""AgentCore Runtime construct: code-based (ZIP on S3) deployment.

Builds the deployment package at synth time if missing (uv, ARM64 wheels),
uploads it as an S3 asset, and creates the CfnRuntime + CfnRuntimeEndpoint.
Pattern from whatsapp-ai-agent-sample-for-aws-agentcore.
"""
import subprocess
from pathlib import Path

from aws_cdk import (
    aws_bedrockagentcore as bedrockagentcore,
    aws_iam as iam,
    aws_s3_assets as s3_assets,
)
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]


class AgentCoreRuntime(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        demo_id: str,
        agent_dir: str,
        role: iam.IRole,
        environment_variables: dict | None = None,
        entry_point: str = "agent.py",
    ) -> None:
        super().__init__(scope, construct_id)

        agent_path = REPO_ROOT / "agents" / agent_dir
        package_zip = agent_path / "deployment_package.zip"
        if not package_zip.exists():
            subprocess.run(
                [str(REPO_ROOT / "scripts" / "create_deployment_package.sh"), str(agent_path)],
                check=True,
            )

        code_asset = s3_assets.Asset(self, "CodeAsset", path=str(package_zip))
        code_asset.grant_read(role)

        self.runtime = bedrockagentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name=f"strands_demo_{demo_id}",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                code_configuration=bedrockagentcore.CfnRuntime.CodeConfigurationProperty(
                    code=bedrockagentcore.CfnRuntime.CodeProperty(
                        s3=bedrockagentcore.CfnRuntime.S3LocationProperty(
                            bucket=code_asset.s3_bucket_name,
                            prefix=code_asset.s3_object_key,
                        )
                    ),
                    entry_point=[entry_point],
                    runtime="PYTHON_3_11",
                )
            ),
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            lifecycle_configuration=bedrockagentcore.CfnRuntime.LifecycleConfigurationProperty(
                idle_runtime_session_timeout=900,
                max_lifetime=28800,
            ),
            environment_variables=environment_variables or {},
            role_arn=role.role_arn,
        )
        self.runtime.node.add_dependency(code_asset)

        self.endpoint = bedrockagentcore.CfnRuntimeEndpoint(
            self,
            "Endpoint",
            agent_runtime_id=self.runtime.attr_agent_runtime_id,
            name=f"demo{demo_id}",
        )

        self.runtime_arn = self.runtime.attr_agent_runtime_arn
