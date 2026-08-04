#!/bin/bash
# deploy.sh — Deploy the LLM-as-a-Judge Lambda function via AWS CDK.
#
# Usage:
#   ./scripts/deploy.sh [--env dev|prod] [--region REGION]
#
# Environment Variables (optional — override CDK context defaults):
#   AWS_REGION            AWS region (overrides merged config/parameters*.json aws_region)
#   AWS_ACCOUNT_ID        AWS account ID (used for CDK bootstrap)
#   CRITERIA_BUCKET_ARN   ARN of an existing S3 bucket for criteria files.
#                         Leave unset to let the stack create and manage one.
#   CDK_BOOTSTRAP_POLICIES  Comma-separated managed policy ARNs for the
#                         CloudFormation execution role (see below).
#
# Examples:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --env prod --region ap-northeast-1
#   ./scripts/deploy.sh --bootstrap          # first deployment in an account
#   CRITERIA_BUCKET_ARN=arn:aws:s3:::my-bucket ./scripts/deploy.sh
#
# Bootstrap is NOT run automatically. It is a one-time, account-and-region-wide
# operation that provisions highly privileged roles, so it is gated behind an
# explicit --bootstrap flag rather than being re-run on every deployment.
#
# The CloudFormation execution role is granted a scoped set of managed policies
# covering only the services this stack creates, instead of AdministratorAccess.
# If bootstrap fails with a permissions error, widen the set deliberately via
# CDK_BOOTSTRAP_POLICIES rather than reverting to AdministratorAccess.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV="dev"
if [[ -n "${AWS_REGION:-}" ]]; then
  REGION="${AWS_REGION}"
elif [[ -f "${REPO_ROOT}/config/parameters.json" ]] || [[ -f "${REPO_ROOT}/config/parameters.local.json" ]]; then
  REGION="$(
    REPO_ROOT="${REPO_ROOT}" python3 <<'PY'
import json
import os

def load(name: str) -> dict:
    path = os.path.join(os.environ["REPO_ROOT"], "config", name)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}

merged = {**load("parameters.json"), **load("parameters.local.json")}
print(merged.get("aws_region", "ap-northeast-1"))
PY
  )"
else
  REGION="ap-northeast-1"
fi
CRITERIA_BUCKET_ARN="${CRITERIA_BUCKET_ARN:-}"
RUN_BOOTSTRAP="false"

# CloudFormation execution policies for `cdk bootstrap`. Scoped to the services
# this stack actually provisions rather than AdministratorAccess, so that a
# compromised or buggy deployment cannot reach unrelated resources.
DEFAULT_BOOTSTRAP_POLICIES="\
arn:aws:iam::aws:policy/AWSCloudFormationFullAccess,\
arn:aws:iam::aws:policy/AWSLambda_FullAccess,\
arn:aws:iam::aws:policy/IAMFullAccess,\
arn:aws:iam::aws:policy/AmazonS3FullAccess,\
arn:aws:iam::aws:policy/AmazonSQSFullAccess,\
arn:aws:iam::aws:policy/AmazonSNSFullAccess,\
arn:aws:iam::aws:policy/CloudWatchFullAccess,\
arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess,\
arn:aws:iam::aws:policy/SecretsManagerReadWrite,\
arn:aws:iam::aws:policy/AWSKeyManagementServicePowerUser"
BOOTSTRAP_POLICIES="${CDK_BOOTSTRAP_POLICIES:-$DEFAULT_BOOTSTRAP_POLICIES}"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

usage() {
  echo "Usage: $0 [--env dev|prod] [--region REGION] [--bootstrap]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --bootstrap)
      RUN_BOOTSTRAP="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

STACK_NAME="LlmJudgeStack-${ENV}"

export AWS_REGION="$REGION"
cd "$REPO_ROOT"

# aws-cdk-lib in cdk/requirements.txt may emit cloud assembly schema newer than a
# globally installed CDK CLI; npx keeps the CLI aligned with current v2 releases.
# Pin CLI ≥2.1118.0 (cloud assembly schema 53); plain `aws-cdk@2` can resolve too old.
CDK_CLI=(npx -y aws-cdk@2.1118.0)

echo "==> Deploying ${STACK_NAME} (env=${ENV}, region=${REGION})"

# ---------------------------------------------------------------------------
# Step 1: Verify AWS authentication
# ---------------------------------------------------------------------------

echo ""
echo "==> Verifying AWS credentials..."
IDENTITY=$(aws sts get-caller-identity --output json 2>&1) || {
  echo "ERROR: AWS authentication failed. Configure credentials and retry." >&2
  exit 1
}
ACCOUNT_ID=$(echo "$IDENTITY" | python3 -c "import sys,json; print(json.load(sys.stdin)['Account'])")
echo "    Account: ${ACCOUNT_ID}"
echo "    Region:  ${REGION}"

# cdk/app.py builds region-scoped Bedrock ARNs from an explicit environment.
export CDK_DEFAULT_ACCOUNT="${CDK_DEFAULT_ACCOUNT:-$ACCOUNT_ID}"

# ---------------------------------------------------------------------------
# Step 2: Install CDK dependencies
# ---------------------------------------------------------------------------

echo ""
echo "==> Installing CDK dependencies..."
pip install -q -r cdk/requirements.txt

# ---------------------------------------------------------------------------
# Step 3: CDK bootstrap (opt-in — provisions account-wide privileged roles)
# ---------------------------------------------------------------------------

if [[ "${RUN_BOOTSTRAP}" == "true" ]]; then
  echo ""
  echo "==> Running CDK bootstrap with scoped execution policies..."
  echo "    Policies: ${BOOTSTRAP_POLICIES}"
  "${CDK_CLI[@]}" bootstrap "aws://${ACCOUNT_ID}/${REGION}" \
    --cloudformation-execution-policies "${BOOTSTRAP_POLICIES}"
else
  echo ""
  echo "==> Skipping CDK bootstrap (pass --bootstrap for a first-time setup)."
  echo "    NOTE: an environment bootstrapped previously with AdministratorAccess"
  echo "    keeps that role until re-bootstrapped with --bootstrap."
fi

# ---------------------------------------------------------------------------
# Step 4: Build CDK context
# ---------------------------------------------------------------------------

CDK_CONTEXT_ARGS=(--context "environment=${ENV}" --context "aws_region=${REGION}")
if [[ -n "${CRITERIA_BUCKET_ARN}" ]]; then
  CDK_CONTEXT_ARGS+=(--context "criteria_bucket_arn=${CRITERIA_BUCKET_ARN}")
fi

# ---------------------------------------------------------------------------
# Step 5: Deploy
# ---------------------------------------------------------------------------

echo ""
echo "==> Deploying ${STACK_NAME}..."
"${CDK_CLI[@]}" deploy "${STACK_NAME}" \
  --require-approval never \
  --app "python3 cdk/app.py" \
  "${CDK_CONTEXT_ARGS[@]}"

# ---------------------------------------------------------------------------
# Step 6: Report stack outputs
# ---------------------------------------------------------------------------

echo ""
echo "==> Fetching stack outputs..."
stack_output() {
  aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text 2>/dev/null || echo "N/A"
}

LAMBDA_ARN="$(stack_output LambdaFunctionArn)"
LAMBDA_NAME="$(stack_output LambdaFunctionName)"
CRITERIA_BUCKET="$(stack_output CriteriaBucketName)"
SECRET_NAME="$(stack_output ApiKeysSecretName)"

echo ""
echo "============================================"
echo "  Deployment complete!"
echo "  Stack:           ${STACK_NAME}"
echo "  Lambda ARN:      ${LAMBDA_ARN}"
echo "  Lambda name:     ${LAMBDA_NAME}"
echo "  Criteria bucket: ${CRITERIA_BUCKET}"
echo "  API keys secret: ${SECRET_NAME}"
echo "  Region:          ${REGION}"
echo "  Env:             ${ENV}"
echo "============================================"
echo ""
echo "Anthropic / OpenAI API keys are read from Secrets Manager, not from"
echo "Lambda environment variables. To populate them:"
echo ""
echo "  aws secretsmanager put-secret-value --secret-id ${SECRET_NAME} \\"
echo "    --secret-string '{\"ANTHROPIC_API_KEY\":\"sk-ant-...\",\"OPENAI_API_KEY\":\"\"}'"
echo ""
echo "Bedrock requires no key — it authenticates via the execution role."
