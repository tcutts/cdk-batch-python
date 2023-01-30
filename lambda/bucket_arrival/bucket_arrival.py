import boto3
import os
import re
import pprint

batch = boto3.client('batch')

def handler(event, context):
    obj_key = event['Records'][0]['s3']['object']['key']
    bucket = event['Records'][0]['s3']['bucket']['name']

    job_environment = [
        { "name": "S3_OUTPUT_BUCKET", "value": os.environ['OUTPUT_BUCKET']},
        { "name": "S3_INPUT_BUCKET", "value": bucket},
        { "name": "S3_INPUT_OBJECT", "value": obj_key}
    ]

    try:
        print(f'submitting job for file {obj_key} in bucket {bucket}\n')
        
        job = batch.submit_job(
            jobName=re.sub(r'[^a-zA-Z0-9_-]+', '_', obj_key)[:127],
            jobQueue=os.environ['JOBQUEUE'],
            jobDefinition=os.environ['JOBDEF'],
            containerOverrides={
                "environment": job_environment
            }
        )
        response = { 'status': 'success', 'key': obj_key, 'job': job }
        pprint.pp({"Response": response})
        return response
    except Exception as e:
        print(e)
        print(f"Error submitting job for file {obj_key} in bucket {bucket}\n")
        raise e