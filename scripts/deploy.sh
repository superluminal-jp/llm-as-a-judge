#!/bin/bash
# deploy.sh — Deploy the LLM-as-a-Judge Lambda function via AWS CDK.
#
# Usage:
#   ./scripts/deploy.sh [--env dev|prod] [--region REGION]
#
# Environment Variables (optional — override CDK context defaults):
#   AWS_REGION            AWS region to deploy into (default: us-east-1)
#   AWS_ACCOUNT_ID        AWS account ID (used for CDK bootstrap)
#   CRITERIA_BUCKET_ARN   ARN of the S3 bucket for criteria files
#
# Examples:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --env prod --region ap-northeast-1
#   CRITERIA_BUCKET_ARN=arn:aws:s3:::my-bucket ./scripts/deploy.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

ENV="dev"
REGION="${AWS_REGION:-us-east-1}"
CRITERIA_BUCKET_ARN="${CRITERIA_BUCKET_ARN:-}"

# ---------------------------------------------------------------------------
# Argument parsing
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
      echo "Usage: $0 [--env dev|prod] [--region REGION]" >&2
      exit 1
      ;;
  esac
done

export AWS_REGION="$REGION"

echo "==> Deploying LlmJudgeStack (env=${ENV}, region=${REGION})"

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

CDK_CONTEXT_ARGS=()
if [[ -n "${CRITERIA_BUCKET_ARN}" ]]; then
  CDK_CONTEXT_ARGS+=(--context "criteria_bucket_arn=${CRITERIA_BUCKET_ARN}")
fi

# ---------------------------------------------------------------------------
# Step 5: Deploy
# ---------------------------------------------------------------------------

echo ""
echo "==> Deploying LlmJudgeStack..."
cdk deploy LlmJudgeStack \
  --require-approval never \
  --app "python3 cdk/app.py" \
  "${CDK_CONTEXT_ARGS[@]+"${CDK_CONTEXT_ARGS[@]}"}"

# ---------------------------------------------------------------------------
# Step 6: Output Lambda ARN
# ---------------------------------------------------------------------------

echo ""
echo "==> Fetching Lambda function ARN..."
LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --stack-name LlmJudgeStack \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionArn'].OutputValue" \
  --output text 2>/dev/null || echo "N/A")

echo ""
echo "============================================"
echo "  Deployment complete!"
echo "  Lambda ARN: ${LAMBDA_ARN}"
echo "  Region:     ${REGION}"
echo "  Env:        ${ENV}"
echo "============================================"
