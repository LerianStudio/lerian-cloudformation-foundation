#!/bin/bash
#
# Deploy Midaz Infrastructure CloudFormation Stack
#
# This script deploys the infrastructure only (VPC, EKS, RDS, DocumentDB, etc.)
# To deploy the Midaz application, use deploy-helm.sh after this completes.
#
# Usage:
#   ./deploy.sh [STACK_NAME] [REGION] [ENVIRONMENT] [NODE_INSTANCE_TYPE]
#
# Example:
#   ./deploy.sh midaz-prod sa-east-1 production c7g.large
#
# After infrastructure is ready, deploy Midaz:
#   ./deploy-helm.sh midaz-prod sa-east-1 5.3.0 midaz
#
# Available instance types (ARM64 Graviton only):
#   - c7g.medium, c7g.large, c7g.xlarge, c7g.2xlarge (Compute optimized)
#   - m7g.medium, m7g.large, m7g.xlarge, m7g.2xlarge (General purpose)
#   - r7g.medium, r7g.large, r7g.xlarge (Memory optimized)
#   - c6g.medium, c6g.large, c6g.xlarge (Graviton2 fallback)
#   - m6g.medium, m6g.large, m6g.xlarge (Graviton2 fallback)
#

set -e

STACK_NAME="${1:-midaz}"
REGION="${2:-us-east-1}"
ENVIRONMENT="${3:-production}"
NODE_INSTANCE_TYPE="${4:-c7g.large}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="${PROJECT_DIR}/templates"
S3_BUCKET="${STACK_NAME}-cfn-artifacts-${REGION}"

echo "=============================================="
echo "  Midaz Infrastructure Deployment"
echo "=============================================="
echo ""
echo "Stack Name:      ${STACK_NAME}"
echo "Region:          ${REGION}"
echo "Environment:     ${ENVIRONMENT}"
echo "Instance Type:   ${NODE_INSTANCE_TYPE}"
echo "Templates:       ${TEMPLATES_DIR}"
echo ""

# Check AWS credentials
echo "Checking AWS credentials..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account:   ${AWS_ACCOUNT_ID}"
echo ""

# =============================================================================
# NOTE: Infrastructure Only
# =============================================================================
# This stack deploys infrastructure only (VPC, EKS, RDS, DocumentDB, ElastiCache, AmazonMQ)
# Midaz application is deployed separately via deploy-helm.sh
# This separation allows retrying Helm deployment without affecting infrastructure
echo "Deploying infrastructure stack (Helm is deployed separately)"
echo ""

# =============================================================================
# CREATE S3 BUCKET
# =============================================================================
echo "Creating S3 bucket for artifacts..."
if ! aws s3api head-bucket --bucket "${S3_BUCKET}" 2>/dev/null; then
    if [ "${REGION}" == "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "${S3_BUCKET}" \
            --region "${REGION}"
    else
        aws s3api create-bucket \
            --bucket "${S3_BUCKET}" \
            --region "${REGION}" \
            --create-bucket-configuration LocationConstraint="${REGION}"
    fi

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "${S3_BUCKET}" \
        --versioning-configuration Status=Enabled

    echo "S3 bucket created: ${S3_BUCKET}"
else
    echo "S3 bucket exists: ${S3_BUCKET}"
fi
echo ""

# =============================================================================
# PACKAGE CLOUDFORMATION TEMPLATES
# =============================================================================
echo "Packaging CloudFormation templates..."

# Use regional S3 endpoint for non-us-east-1 regions
if [ "${REGION}" == "us-east-1" ]; then
    S3_URL="https://${S3_BUCKET}.s3.amazonaws.com"
else
    S3_URL="https://${S3_BUCKET}.s3.${REGION}.amazonaws.com"
fi

aws cloudformation package \
    --template-file "${TEMPLATES_DIR}/midaz-complete.yaml" \
    --s3-bucket "${S3_BUCKET}" \
    --s3-prefix "templates" \
    --output-template-file "${PROJECT_DIR}/packaged-template.yaml" \
    --region "${REGION}"

# Cross-platform sed in-place edit
sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# Fix S3 URLs in packaged template to use regional endpoint
if [ "${REGION}" != "us-east-1" ]; then
    echo "Fixing S3 URLs for regional endpoint..."
    sed_inplace "s|https://${S3_BUCKET}.s3.amazonaws.com|https://${S3_BUCKET}.s3.${REGION}.amazonaws.com|g" "${PROJECT_DIR}/packaged-template.yaml"
    sed_inplace "s|https://s3.amazonaws.com/${S3_BUCKET}|https://s3.${REGION}.amazonaws.com/${S3_BUCKET}|g" "${PROJECT_DIR}/packaged-template.yaml"
fi
echo ""

# =============================================================================
# GET AVAILABILITY ZONES
# =============================================================================
echo "Getting available Availability Zones..."
AZS=$(aws ec2 describe-availability-zones \
    --region "${REGION}" \
    --query 'AvailabilityZones[?State==`available`].ZoneName' \
    --output text)
AZ1=$(echo $AZS | awk '{print $1}')
AZ2=$(echo $AZS | awk '{print $2}')
AZ3=$(echo $AZS | awk '{print $3}')
echo "Using AZs: ${AZ1}, ${AZ2}, ${AZ3}"
echo ""

# =============================================================================
# DEPLOY STACK
# =============================================================================
echo "Deploying CloudFormation stack (with --disable-rollback for easier debugging)..."
aws cloudformation deploy \
    --template-file "${PROJECT_DIR}/packaged-template.yaml" \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --parameter-overrides \
        ProjectName="${STACK_NAME}" \
        EnvironmentName="${ENVIRONMENT}" \
        AvailabilityZone1="${AZ1}" \
        AvailabilityZone2="${AZ2}" \
        AvailabilityZone3="${AZ3}" \
        NodeInstanceType="${NODE_INSTANCE_TYPE}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --disable-rollback

echo ""
echo "=============================================="
echo "  Infrastructure Deployment Complete!"
echo "=============================================="
echo ""

# Get outputs
echo "Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo "To configure kubectl:"
echo "  aws eks update-kubeconfig --name ${STACK_NAME}-eks --region ${REGION}"
echo ""
echo "=============================================="
echo "  NEXT STEP: Deploy Midaz Application"
echo "=============================================="
echo ""
echo "Run the following command to deploy Midaz:"
echo "  ./scripts/deploy-helm.sh ${STACK_NAME} ${REGION} 5.3.0 midaz"
echo ""
