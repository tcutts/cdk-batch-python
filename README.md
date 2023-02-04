
# Introduction to CDK and AWS Batch

Science depends on the reproducibility of results.  This includes the reproducibility of analysis.

Historically, a lot of researchers struggled to run each other's code; developed on an individual
specific system, and requiring work to run elsewhere.

Containers help solve a lot of this problem by at least packaging an application and a lot of its
dependencies in a single runnable module.  But that's only part of the story.  What about everything
else you need to run a scientific analysis at scale?  Batch queues.  HPC nodes.  High performance
networks.  Firewalls.  Centralised logging.  Fault notifications.  The list goes on...

AWS of course has all of these features and more, but configuring them all individually through the AWS console is laborious and error prone.

AWS CloudFormation is a service allows you to describe all of
your infrastratucture in template files, in either YAML or JSON.  The service then turns these templates into a series of API calls and executes them to created the infrastructure.

However, CloudFormation templates can be unwieldy to
write and debug, especially as your stack gets more complex and has many cross-references between resources.

What if you could write code in Python, or other languages with which you are
already familiar, and have that generate the CloudFormation template for you?  And apply sensible,
best practice defaults so that you don't have to directly code every last detail?  That's what
the AWS Cloud Developer Kit does.

This allows you to specify your entire application; the containerised app itself, and the entire
infrastructure to run it reproducibly, in a single code repository.

This is an example of a simple research-oriented architecture, written almost entirely in Python, to illustrate the principles.

![Architecture diagram](assets/architecture.svg)

1. Dropping files in the `Input Bucket` triggers the `Bucket Arrival` lambda function
2. The function submits a job to the `Batch Queue` which automatically spins up instance(s) to process the jobs.
3. CDK uses docker on your machine to build and upload the container to the Amazon Elastic Container registry.  AWS Batch uses this container to process the file in the input bucket.
1. The results of the job are then stored in  `Output Bucket`
1. An `Event Bus` watches the AWS Batch events, and filters them for job status changes to `SUCCEEDED` or `FAILED` and sends these events to the `JobCompletion` SNS topic.


# Prerequisites

1. Install [Node.js](https://nodejs.org/en/download/) 14.15.0 or later on your system
1. Install Docker on your system
1. Install CDKv2: ```npm install -g aws-cdk```
1. Install Python 3.7 or higher on your system, including `pip` and `virtualenv`
1. Recommended:  Install the [AWS CLI](https://aws.amazon.com/cli/) on your system
1. Clone this repository
1. Navigate to the root of your checkout
1. Install a virtualenv: ```python3 -m venv .venv```
1. Activate the virtualenv: ```source .venv/bin/activate``` on MacOS/Linux, or ```.venv\Scripts\activate.bat``` on Windows
1. Install the python modules needed:  ```pip install -r requirements.txt```
1.  If you've never used CDK before, run ```cdk bootstrap```


# Deploy the stack

```cdk deploy --parameters NotificationEmail=youraddress@example.com```

Make a note of the name of the input and output buckets that were created.

Check your email - SNS will ask you to confirm your email address for the notifications to be sent to. 

# Submitting work to the stack

Use the `aws` CLI or web interface to add files to the OutputBucket :

```echo hello research world | aws s3 cp - s3://InputBucket-nnnnnnnn-mmmmmmmm/helloworld.txt```

Watch the magic happen in the AWS Console, by navigating to AWS Batch and looking at Jobs.

Download your results from the output bucket:

```aws s3 cp s3://OutputBucket-xxxxxxxx-yyyyyyyy/helloworld.txt.out -```

# Before you start

This project is set up like a standard Python project.  You need to create a virtualenv
for this to work.

To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are on a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

If you have never used CDK before on your account or in the region you're about to deploy to, you need to bootstrap CDK in your account and region:

```
$ cdk bootstrap
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!
