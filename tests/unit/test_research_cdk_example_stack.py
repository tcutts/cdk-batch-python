import aws_cdk as core
import aws_cdk.assertions as assertions

from research_cdk_example.research_cdk_example_stack import ResearchCdkExampleStack

# example tests. To run these tests, install the dev requirements
# and then run "pytest" in the project root

def test_resources_created():
    app = core.App()
    stack = ResearchCdkExampleStack(app, "research-cdk-example")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::S3::Bucket", 2)

    template.has_resource_properties("AWS::SNS::Subscription", {
        "Protocol": "email"
    })

    template.has_resource_properties("AWS::Batch::JobDefinition", {
        "Type": "container"
    })
