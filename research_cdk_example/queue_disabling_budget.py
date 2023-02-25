from constructs import Construct
from aws_cdk import (
    CfnParameter,
    CfnOutput,
    aws_budgets as _budgets,
    aws_lambda as _lambda,
    aws_batch_alpha as _batch,
    aws_sns as _sns,
    aws_lambda_event_sources as _les,
    aws_iam as _iam,
)

# This construct is an L3 construct which creates a Budget which:
#     * Emails the user when the budget reaches 95%
#     * Optionally disables a queue so that no further work can be submitted


class QueueDisablingBudget(Construct):
    def __init__(self, scope: Construct, id: str, email: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        budgetlimit = CfnParameter(self, "BudgetLimit", default=5, min_value=0, type="Number")
        budgetlimit.override_logical_id("BudgetLimit")

        # Create an SNS topic for budget alerts to go to
        self.budget_topic = _sns.Topic(self, "BudgetTopic")

        accountid = scope.account

        # Allow Budgets to send to the topic
        self.budget_topic.grant_publish(
            _iam.ServicePrincipal(
                "budgets.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": accountid},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:budgets::{accountid}:*"},
                },
            )
        )

        # Create the budget itself
        _budgets.CfnBudget(
            self,
            "Budget",
            budget=_budgets.CfnBudget.BudgetDataProperty(
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=_budgets.CfnBudget.SpendProperty(amount=budgetlimit.value_as_number, unit="USD"),
                # The budget only applies to this stack:
                cost_filters={"TagKeyValue": [f"aws:cloudformation:stack-id${scope.stack_id}"]},
            ),
            notifications_with_subscribers=[
                _budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=_budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type="ACTUAL",
                        threshold=95,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[
                        _budgets.CfnBudget.SubscriberProperty(subscription_type="EMAIL", address=email),
                        _budgets.CfnBudget.SubscriberProperty(
                            subscription_type="SNS", address=self.budget_topic.topic_arn
                        ),
                    ],
                )
            ],
        )

        CfnOutput(self, "BudgetAlertTopic", value=self.budget_topic.topic_name)

    def disable_jobqueue_on_alert(self, job_queue: _batch.JobQueue):
        # This lambda function will inactivate the queue, preventing further jobs from arriving
        budget_alert_function = _lambda.Function(
            self,
            "BudgetExceeded",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("lambda/budget_exceeded"),
            handler="budget_exceeded.handler",
            environment={
                "JOBQUEUE": job_queue.job_queue_name,
            },
        )

        # Allow the lambda function to inactivate the queue
        budget_alert_function.role.attach_inline_policy(
            _iam.Policy(
                self,
                "DisableQueuePolicy",
                statements=[
                    _iam.PolicyStatement(
                        actions=["batch:UpdateJobQueue"],
                        resources=[job_queue.job_queue_arn],
                    )
                ],
            )
        )

        budget_alert_function.add_event_source(_les.SnsEventSource(self.budget_topic))
