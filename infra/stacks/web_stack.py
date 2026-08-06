"""Web hosting: private S3 + CloudFront (OAC), built and deployed by CDK.

Pattern from ai-agent-website-primitive: local bundling runs `npm run build`
at synth time; SPA routes 403/404 fall back to index.html.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"


class WebStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        dist = WEB_DIR / "dist"
        # Build the SPA at synth time (requires web/.env.local, see deploy.sh).
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
