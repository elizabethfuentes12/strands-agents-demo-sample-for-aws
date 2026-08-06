import aws_cdk as core
import aws_cdk.assertions as assertions

from 02_frontend.02_frontend_stack import 02FrontendStack

# example tests. To run these tests, uncomment this file along with the example
# resource in 02_frontend/02_frontend_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = 02FrontendStack(app, "02-frontend")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
