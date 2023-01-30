from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
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

class ResearchCdkExampleStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a network for everything to go in
        vpc = _ec2.Vpc(self, "ResearchVPC")

        # Create the roles we need
        self.create_roles()

        # Create an EC2 compute resource
        compute_environment = _batch.ComputeEnvironment(
            self, "ComputeEnvironment",
            compute_resources=_batch.ComputeResources(
                allocation_strategy=_batch.AllocationStrategy.BEST_FIT_PROGRESSIVE,
                instance_types=[_ec2.InstanceType("c6g")],
                image=_ecs.EcsOptimizedImage.amazon_linux2(
                    _ecs.AmiHardwareType.ARM,
                ),
                vpc=vpc,
                instance_role=self.instance_profile.attr_arn
            ),
            service_role=self.create_batch_service_role(),
        )

        # Create a job queue connected to the Compute Environment
        job_queue = _batch.JobQueue(
            self, "ResearchQueue",
            compute_environments=[
                _batch.JobQueueComputeEnvironment(
                    compute_environment=compute_environment,
                    order=1,
                )
            ]
        )

        # Create a job definition for the word_count container
        job_def = _batch.JobDefinition(
            self, "WordCountJob",
            container=_batch.JobDefinitionContainer(
                image=_ecs.ContainerImage.from_asset(
                    "job_definitions/word_count"
                ),
                memory_limit_mib=100,
                vcpus=1,
                execution_role=self.execution_role,
                job_role=self.job_role,
            ),
            platform_capabilities=[_batch.PlatformCapabilities.EC2],
            retry_attempts=3,
            timeout=Duration.days(1) 
        )

        # Create input and output buckets
        input_bucket = _s3.Bucket(
            self, "InputBucket",
            public_read_access=False,
            encryption=_s3.BucketEncryption.S3_MANAGED
        )

        output_bucket = _s3.Bucket(
            self, "OutputBucket",
            public_read_access=False,
            encryption=_s3.BucketEncryption.S3_MANAGED
        )

        # Create the lambda function which will respond to files arriving
        bucket_arrival_function = _lambda.Function(
            self, "BucketArrival",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("lambda/bucket_arrival"),
            handler="bucket_arrival.handler",
            # Environment variables tell the lambbda where to submit jobs to
            # and place output
            environment={
                "JOBDEF": job_def.job_definition_name,
                "JOBQUEUE": job_queue.job_queue_name,
                "OUTPUT_BUCKET": output_bucket.bucket_name
            }
        )

        # Allow the lambda function to submit jobs
        bucket_arrival_function.role.attach_inline_policy(
            _iam.Policy(
                self, "BatchSubmitPolicy",
                statements=[
                    _iam.PolicyStatement(
                        actions=["batch:SubmitJob"],
                        resources=[
                            job_def.job_definition_arn,
                            job_queue.job_queue_arn
                        ]
                    )
                ]
            )
        )

        # Send object creation notifications from the input bucket
        # to the lambda function
        input_bucket.add_object_created_notification(
            _s3n.LambdaDestination(bucket_arrival_function),
        )

        # Give the lambda and job_role the permissions they need on
        # the S3 buckets
        input_bucket.grant_read(bucket_arrival_function)
        input_bucket.grant_read(self.job_role)
        output_bucket.grant_write(self.job_role)

        # Create an SNS topic for notifications
        topic = _sns.Topic(
            self, "JobChangesTopic"
        )

        # Subscribe to it
        subscription = _sns.Subscription(
            self, "NotifyMe",
            topic=topic, protocol=_sns.SubscriptionProtocol.EMAIL,
            endpoint="tjrc@amazon.co.uk",
        )

        # EventBridge between Batch and topic, looking
        rule = _events.Rule(
            self, "BatchEvents",
            event_pattern=_events.EventPattern(
                source=["aws.batch"],
                detail_type=["Batch Job State Change"],
                detail={
                    "status": _events.Match.any_of(["SUCCEEDED", "FAILED"])
                }
            ),
            targets=[ _targets.SnsTopic(topic) ]
        )

        # Print out the bucket names
        CfnOutput(self, "InputBucketName", value=input_bucket.bucket_name)
        CfnOutput(self, "OutputBucketName", value=output_bucket.bucket_name)

    def create_roles(self):
        # The compute environment needs an instance role with permission to
        # create log entries
        self.instance_role = self.create_instance_role()
        self.instance_profile = _iam.CfnInstanceProfile(
            self, "InstanceProfile",
            roles=[self.instance_role.role_name]
        )

        # Create a role allowing Batch to execute tasks in ECS
        self.execution_role = _iam.Role(
            self, "ExecutionRole",
            assumed_by=_iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                _iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy",
                )
            ]
        )

        # Create a role for jobs to assume as they run
        self.job_role = _iam.Role(
            self, "JobRole",
            assumed_by=_iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

    def create_instance_role(self) -> _iam.Role:
        instance_role = _iam.Role(self, "InstanceRole",
            assumed_by=_iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies= [
                _iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonEC2ContainerServiceforEC2Role"
                )
            ],
        )

        instance_role.add_to_policy(
            _iam.PolicyStatement(
                effect=_iam.Effect.ALLOW,
                actions=["sts:AssumeRole"],
                resources=["*"]
            )
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
                resources=["arn:aws:logs:*:*:*"]
            )
        )

        return instance_role

    def create_batch_service_role(self) -> _iam.Role:
        batch_service_role = _iam.Role(
            self, "BatchServiceRole",
            assumed_by=_iam.ServicePrincipal("batch.amazonaws.com"),
            managed_policies= [
                _iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSBatchServiceRole"
                )
            ]
        )

        sts_assume_statement = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW,
            actions=["sts:AssumeRole"],
            resources=["*"]
        )
        batch_service_role.add_to_policy(sts_assume_statement)

        return batch_service_role