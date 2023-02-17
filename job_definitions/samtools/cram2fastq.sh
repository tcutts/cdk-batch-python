#!/bin/sh

set -e
set -o pipefail

FILEPREFIX=/tmp/${S3_INPUT_OBJECT%%.cram}
aws s3 cp "s3://${S3_INPUT_BUCKET}/${S3_INPUT_OBJECT}" - | \
  samtools sort -n -@8 - | \
  samtools fastq - -1 ${FILEPREFIX}_1.fq -2 ${FILEPREFIX}_1.fq > /dev/null
aws s3 cp ${FILEPREFIX}_1.fq s3://$S3_OUTPUT_BUCKET
aws s3 cp ${FILEPREFIX}_2.fq s3://$S3_OUTPUT_BUCKET
rm /tmp/${FILEPREFIX}_*
