"""Base stack: Cognito auth, AppSync Events API, and the dispatcher Lambda.

The browser authenticates with Cognito, connects to the Events API over
WebSocket, publishes prompts to ``inbox/<demo>/<sessionId>`` and subscribes to
``out/<demo>/<sessionId>``. The dispatcher Lambda (direct integration on the
inbox namespace, async invoke) calls the AgentCore Runtime and publishes the
agent's typed events back to the out channel.
"""
from aws_cdk import (
    CfnOutput,
    Duration,
    Expiration,
    RemovalPolicy,
    Stack,
    aws_appsync as appsync,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_ssm as ssm,
)
from constructs import Construct

SSM_PREFIX = "/strands-demos"


class BaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Cognito: kiosk credential for the stand ---
        user_pool = cognito.UserPool(
            self,
            "DemoUserPool",
            user_pool_name="strands-demos",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            password_policy=cognito.PasswordPolicy(min_length=12),
            removal_policy=RemovalPolicy.DESTROY,
        )
        user_pool_client = user_pool.add_client(
            "WebClient",
            auth_flows=cognito.AuthFlow(user_srp=True, user_password=True),
            access_token_validity=Duration.hours(8),
            id_token_validity=Duration.hours(8),
        )

        # --- Dispatcher Lambda: inbox events -> AgentCore -> out events ---
        dispatcher = _lambda.Function(
            self,
            "Dispatcher",
            function_name="strands-demos-dispatcher",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/dispatcher"),
            timeout=Duration.minutes(5),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                resources=["*"],
            )
        )
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter{SSM_PREFIX}/*"
                ],
            )
        )

        # --- AppSync Events API ---
        user_pool_provider = appsync.AppSyncAuthProvider(
            authorization_type=appsync.AppSyncAuthorizationType.USER_POOL,
            cognito_config=appsync.AppSyncCognitoConfig(user_pool=user_pool),
        )
        # API key for the dispatcher's publishes to `out`, stored in SSM.
        # NOTE: AppSync API keys expire (365 days max) — rotate on redeploy.
        api_key_provider = appsync.AppSyncAuthProvider(
            authorization_type=appsync.AppSyncAuthorizationType.API_KEY,
            api_key_config=appsync.AppSyncApiKeyConfig(
                description="Dispatcher publish key",
                expires=Expiration.after(Duration.days(365)),
            ),
        )
        api = appsync.EventApi(
            self,
            "EventsApi",
            api_name="strands-demos-events",
            authorization_config=appsync.EventApiAuthConfig(
                auth_providers=[user_pool_provider, api_key_provider],
                connection_auth_mode_types=[
                    appsync.AppSyncAuthorizationType.USER_POOL,
                ],
                default_publish_auth_mode_types=[
                    appsync.AppSyncAuthorizationType.USER_POOL,
                ],
                default_subscribe_auth_mode_types=[
                    appsync.AppSyncAuthorizationType.USER_POOL,
                ],
            ),
        )

        dispatcher_ds = api.add_lambda_data_source("DispatcherDS", dispatcher)

        # inbox: browser publishes prompts; dispatcher handles them async.
        api.add_channel_namespace(
            "inbox",
            channel_namespace_name="inbox",
            authorization_config=appsync.NamespaceAuthConfig(
                publish_auth_mode_types=[appsync.AppSyncAuthorizationType.USER_POOL],
                subscribe_auth_mode_types=[appsync.AppSyncAuthorizationType.USER_POOL],
            ),
            publish_handler_config=appsync.HandlerConfig(
                data_source=dispatcher_ds,
                direct=True,
                lambda_invoke_type=appsync.LambdaInvokeType.EVENT,
            ),
        )

        # out: dispatcher publishes agent events (API key from SSM);
        # browser subscribes (Cognito JWT).
        api.add_channel_namespace(
            "out",
            channel_namespace_name="out",
            authorization_config=appsync.NamespaceAuthConfig(
                publish_auth_mode_types=[appsync.AppSyncAuthorizationType.API_KEY],
                subscribe_auth_mode_types=[appsync.AppSyncAuthorizationType.USER_POOL],
            ),
        )
        api_key_param = ssm.StringParameter(
            self,
            "ParamEventsApiKey",
            parameter_name=f"{SSM_PREFIX}/events_api_key",
            string_value=api.api_keys["Default"].attr_api_key,
        )
        api_key_param.grant_read(dispatcher)

        dispatcher.add_environment("EVENTS_HTTP_DOMAIN", api.http_dns)
        dispatcher.add_environment("SSM_PREFIX", SSM_PREFIX)

        # --- Config for the web app and demo stacks ---
        params = {
            "user_pool_id": user_pool.user_pool_id,
            "user_pool_client_id": user_pool_client.user_pool_client_id,
            "events_http_domain": api.http_dns,
            "events_realtime_domain": api.realtime_dns,
        }
        for name, value in params.items():
            ssm.StringParameter(
                self,
                f"Param{name.title().replace('_', '')}",
                parameter_name=f"{SSM_PREFIX}/{name}",
                string_value=value,
            )
            CfnOutput(self, f"Out{name.title().replace('_', '')}", value=value)
