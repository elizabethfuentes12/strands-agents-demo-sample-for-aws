"""Web hosting: private S3 + CloudFront (OAC), built and deployed by CDK.

Local bundling runs `npm run build` at synth time (requires web/.env.local with
the base-stack outputs). SPA routes 403/404 fall back to index.html.
"""
import subprocess
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
)
from constructs import Construct

# web-infra/stacks/web_stack.py -> parents[2] is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"


class WebStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        dist = WEB_DIR / "dist"
        env_local = WEB_DIR / ".env.local"
        env_example = WEB_DIR / ".env.local.example"
        if not env_local.exists():
            if env_example.exists():
                import shutil
                shutil.copy(env_example, env_local)
            else:
                raise FileNotFoundError(
                    f"{env_local} not found. Deploy the base stack first and write "
                    "web/.env.local from its outputs (see deploy.sh / README)."
                )

        # Build the SPA at synth time so dist/ reflects the current .env.local.
        subprocess.run(["npm", "install", "--silent"], cwd=WEB_DIR, check=True)
        subprocess.run(["npm", "run", "build"], cwd=WEB_DIR, check=True)

        bucket = s3.Bucket(
            self,
            "WebBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        distribution = cloudfront.Distribution(
            self,
            "WebDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=code, response_http_status=200, response_page_path="/index.html"
                )
                for code in (403, 404)
            ],
        )

        s3_deployment.BucketDeployment(
            self,
            "DeployWeb",
            sources=[s3_deployment.Source.asset(str(dist))],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        CfnOutput(self, "WebUrl", value=f"https://{distribution.distribution_domain_name}")
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
