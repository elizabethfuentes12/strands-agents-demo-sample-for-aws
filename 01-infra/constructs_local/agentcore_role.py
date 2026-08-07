"""Minimal execution role for an AgentCore Runtime."""
from aws_cdk import Stack, aws_iam as iam
from constructs import Construct


class AgentCoreRole(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, demo_id: str) -> None:
        super().__init__(scope, construct_id)
        stack = Stack.of(self)

        self.role = iam.Role(
            self,
            "Role",
            role_name=f"strands-demo-{demo_id}-runtime-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXRayDaemonWriteAccess"
                ),
            ],
        )
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    # Cross-region inference profiles route to multiple regions —
                    # us.* routes to us-east-1, us-east-2, us-west-2.
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:{stack.account}:inference-profile/*",
                    "arn:aws:bedrock:*::inference-profile/*",
                ],
            )
        )
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "aws-marketplace:Subscribe",
                    "aws-marketplace:Unsubscribe",
                    "aws-marketplace:ViewSubscriptions",
                ],
                resources=["*"],
            )
        )
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=[
                    f"arn:aws:logs:{stack.region}:{stack.account}:log-group:/aws/bedrock-agentcore/*"
                ],
            )
        )
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                },
            )
        )
