#!/bin/bash
# deploy.sh — Deploy the LLM-as-a-Judge Lambda function via AWS CDK.
#
# The CFN stack name is LlmJudgeStack-<env> (e.g., LlmJudgeStack-dev,
# LlmJudgeStack-prd) so dev / prd can coexist in the same account.
#
# Usage:
#   ./scripts/deploy.sh [--env dev|prd] [--region REGION]
#
# Environment Variables (optional — override CDK context defaults):
#   ENVIRONMENT           dev|prd label (overrides parameters.json `environment`)
#   AWS_REGION            AWS region (overrides merged config/parameters*.json aws_region)
#   AWS_ACCOUNT_ID        AWS account ID (used for CDK bootstrap)
#   CRITERIA_BUCKET_ARN   ARN of the S3 bucket for criteria files
#
# Examples:
#   ./scripts/deploy.sh                                   # uses parameters.json
#   ./scripts/deploy.sh --env prd
#   ./scripts/deploy.sh --env dev --region ap-northeast-1
#   CRITERIA_BUCKET_ARN=arn:aws:s3:::my-bucket ./scripts/deploy.sh --env prd

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Read merged parameters.json + parameters.local.json once.
read -r FILE_ENV FILE_REGION < <(
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
print(merged.get("environment", "dev"), merged.get("aws_region", "ap-northeast-1"))
PY
)

ENV="${ENVIRONMENT:-${FILE_ENV}}"
REGION="${AWS_REGION:-${FILE_REGION}}"
CRITERIA_BUCKET_ARN="${CRITERIA_BUCKET_ARN:-}"

# ---------------------------------------------------------------------------
# Argument parsing (CLI flags take precedence over env vars / parameters file)
# ---------------------------------------------------------------------------

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
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--env dev|prd] [--region REGION]" >&2
      exit 1
      ;;
  esac
done

export AWS_REGION="$REGION"
STACK_NAME="LlmJudgeStack-${ENV}"

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

# ---------------------------------------------------------------------------
# Step 2: Install CDK dependencies
# ---------------------------------------------------------------------------

echo ""
echo "==> Installing CDK dependencies..."
pip install -q -r cdk/requirements.txt

# ---------------------------------------------------------------------------
# Step 3: CDK bootstrap (idempotent — safe to run every time)
# ---------------------------------------------------------------------------

echo ""
echo "==> Running CDK bootstrap..."
# Bootstrap failure is non-fatal if the environment is already bootstrapped.
cdk bootstrap "aws://${ACCOUNT_ID}/${REGION}" \
  --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess \
  || echo "    Bootstrap already complete (or failed with non-critical error)."

# ---------------------------------------------------------------------------
# Step 4: Build CDK context
# ---------------------------------------------------------------------------

CDK_CONTEXT_ARGS=(--context "environment=${ENV}")
if [[ -n "${CRITERIA_BUCKET_ARN}" ]]; then
  CDK_CONTEXT_ARGS+=(--context "criteria_bucket_arn=${CRITERIA_BUCKET_ARN}")
fi

# ---------------------------------------------------------------------------
# Step 5: Deploy
# ---------------------------------------------------------------------------

echo ""
echo "==> Deploying ${STACK_NAME}..."
cdk deploy "${STACK_NAME}" \
  --require-approval never \
  --app "python3 cdk/app.py" \
  "${CDK_CONTEXT_ARGS[@]}"

# ---------------------------------------------------------------------------
# Step 6: Output Lambda ARN
# ---------------------------------------------------------------------------

echo ""
echo "==> Fetching Lambda function ARN..."
LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionArn'].OutputValue" \
  --output text 2>/dev/null || echo "N/A")

echo ""
echo "============================================"
echo "  Deployment complete!"
echo "  Stack:      ${STACK_NAME}"
echo "  Lambda ARN: ${LAMBDA_ARN}"
echo "  Region:     ${REGION}"
echo "  Env:        ${ENV}"
echo "============================================"
