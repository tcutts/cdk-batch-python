from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    CfnParameter,
    RemovalPolicy, Tags,
    aws_s3 as _s3,
    aws_s3_notifications as _s3n,
    aws_lambda as _lambda,
    aws_batch_alpha as _batch,
    aws_ec2 as _ec2,
    aws_ecs as _ecs,
    aws_iam as _iam,
    aws_sns as _sns,
    aws_events as _events,
    aws_events_targets as _targets,
)
from constructs import Construct
from .queue_disabling_budget import QueueDisablingBudget

COST_TAG="research-stack-id"

class ResearchCdkExampleStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a VPC for everything to go in
        vpc = _ec2.Vpc(self, "ResearchVPC", 
            max_azs=1
        )

        # Create the roles we need
        instance_profile, job_role = self.create_roles()

        # Create an EC2 compute resource
        compute_environment = _batch.ComputeEnvironment(
            self,
            "ComputeEnvironment",
            compute_resources=_batch.ComputeResources(
                instance_types=[_ec2.InstanceType("c6a")],
                image=_ecs.EcsOptimizedImage.amazon_linux2(),
                vpc=vpc,
                instance_role=instance_profile.attr_arn,
                # Good practice to set a maximum on the number of CPUs, to avoid
                # costly accidents
                maxv_cpus=256,
                compute_resources_tags={
                    COST_TAG: self.node.addr
                }
            ),
        )

        # Create a job queue connected to the Compute Environment
        job_queue = _batch.JobQueue(
            self,
            "ResearchQueue",
            compute_environments=[
                _batch.JobQueueComputeEnvironment(
                    compute_environment=compute_environment,
                    order=1,
                )
            ],
        )

        # Create a job definition for the word_count container
        job_def = _batch.JobDefinition(
            self,
            "WordCountJob",
            container=_batch.JobDefinitionContainer(
                image=_ecs.ContainerImage.from_asset("job_definitions/word_count"),
                memory_limit_mib=100,
                vcpus=1,
                job_role=job_role,
            ),
            retry_attempts=3,
            timeout=Duration.days(1),
        )

        # Create input and output buckets. Auto_delete_objects
        # is set to true because this is an example, but is not
        # advisable in production.
        input_bucket = _s3.Bucket(
            self,
            "InputBucket",
            encryption=_s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        output_bucket = _s3.Bucket(
            self,
            "OutputBucket",
            encryption=_s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Create the lambda function which will respond to files arriving
        bucket_arrival_function = _lambda.Function(
            self,
            "BucketArrival",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("lambda/bucket_arrival"),
            handler="bucket_arrival.handler",
            # Environment variables tell the lambda where to submit jobs
            # and place output
            environment={
                "JOBDEF": job_def.job_definition_name,
                "JOBQUEUE": job_queue.job_queue_name,
                "OUTPUT_BUCKET": output_bucket.bucket_name,
            },
        )

        # Send object creation notifications from the input bucket
        # to the lambda function
        input_bucket.add_object_created_notification(
            _s3n.LambdaDestination(bucket_arrival_function),
        )

        # Allow the lambda function to submit jobs
        bucket_arrival_function.role.attach_inline_policy(
            _iam.Policy(
                self,
                "BatchSubmitPolicy",
                statements=[
                    _iam.PolicyStatement(
                        actions=["batch:SubmitJob"],
                        resources=[job_def.job_definition_arn, job_queue.job_queue_arn],
                    )
                ],
            )
        )

        # Give the lambda and job_role the permissions they need on
        # the S3 buckets
        input_bucket.grant_read(job_role)
        output_bucket.grant_write(job_role)

        # Specify email destination as parameter
        email = CfnParameter(
            self,
            "Notification Email",
            description="Email adress job success/failures will be sent to",
            allowed_pattern="\w+@(\w+\.)+(\w+)",
        )

        # Create an SNS topic for notifications
        topic = _sns.Topic(self, "JobCompletionTopic")

        if email.value_as_string != "":
            # Subscribe to it
            _sns.Subscription(
                self,
                "NotifyMe",
                topic=topic,
                protocol=_sns.SubscriptionProtocol.EMAIL,
                endpoint=email.value_as_string,
            )

        # EventBridge between Batch and topic, for success and failure
        _events.Rule(
            self,
            "BatchEvents",
            event_pattern=_events.EventPattern(
                source=["aws.batch"],
                detail_type=["Batch Job State Change"],
                detail={"status": _events.Match.any_of(["SUCCEEDED", "FAILED"])},
            ),
            targets=[_targets.SnsTopic(topic)],
        )

        budget = QueueDisablingBudget(
            self, "StackBudget", email=email.value_as_string, cost_tag=COST_TAG
        )
        budget.disable_jobqueue_on_alert(job_queue)

        Tags.of(self).add(key=COST_TAG, value=self.node.addr)

        # Print out the bucket names
        CfnOutput(self, "InputBucketName", value=input_bucket.bucket_name)
        CfnOutput(self, "OutputBucketName", value=output_bucket.bucket_name)
        CfnOutput(self, "QueueName", value=job_queue.job_queue_name)

    def create_roles(self) -> tuple[_iam.CfnInstanceProfile, _iam.Role]:
        # Create a role for jobs to assume as they run
        job_role = _iam.Role(
            self,
            "JobRole",
            assumed_by=_iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Instance role for the EC2 instances which get created
        instance_role = _iam.Role(
            self,
            "InstanceRole",
            assumed_by=_iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                _iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonEC2ContainerServiceforEC2Role")
            ],
        )

        instance_role.add_to_policy(
            _iam.PolicyStatement(effect=_iam.Effect.ALLOW, actions=["sts:AssumeRole"], resources=["*"])
        )

        instance_role.add_to_policy(
            _iam.PolicyStatement(
                effect=_iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                ],
                resources=["arn:aws:logs:*:*:*"],
            )
        )

        instance_profile = _iam.CfnInstanceProfile(self, "InstanceProfile", roles=[instance_role.role_name])

        return (instance_profile, job_role)
