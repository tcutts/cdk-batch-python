import aws_cdk as core
import aws_cdk.assertions as assertions

from research_cdk_example.research_cdk_example_stack import ResearchCdkExampleStack

# example tests. To run these tests, uncomment this file along with the example
# resource in research_cdk_example/research_cdk_example_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = ResearchCdkExampleStack(app, "research-cdk-example")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
