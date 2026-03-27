#!/bin/bash
# =============================================================================
# Deploy Midaz Infrastructure Stack (without application)
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Defaults
S3_BUCKET="${1:?Usage: $0 <s3-bucket> [stack-name] [region] [project-name] [product]}"
STACK_NAME="${2:-midaz-infra}"
AWS_REGION="${3:-us-east-1}"
PROJECT_NAME="${4:-$STACK_NAME}"
PRODUCT="${5:-midaz}"

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Midaz Infrastructure Deployment${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""
echo "Stack:      $STACK_NAME"
echo "Region:     $AWS_REGION"
echo "S3 Bucket:  $S3_BUCKET"
echo "Project:    $PROJECT_NAME"
echo ""

# Get AZs
echo "Fetching availability zones..."
AZS=($(aws ec2 describe-availability-zones \
    --region "$AWS_REGION" \
    --query 'AvailabilityZones[?State==`available`].ZoneName' \
    --output text | tr '\t' '\n' | head -3))

if [ ${#AZS[@]} -lt 3 ]; then
    echo -e "${RED}❌ Need at least 3 AZs${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Using AZs: ${AZS[0]}, ${AZS[1]}, ${AZS[2]}"
echo ""

# Deploy
echo -e "${BLUE}Deploying infrastructure...${NC}"
aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-url "https://${S3_BUCKET}.s3.${AWS_REGION}.amazonaws.com/products/${PRODUCT}/infrastructure.yaml" \
    --parameter-overrides \
        ProjectName="$PROJECT_NAME" \
        EnvironmentName="production" \
        AvailabilityZone1="${AZS[0]}" \
        AvailabilityZone2="${AZS[1]}" \
        AvailabilityZone3="${AZS[2]}" \
        MPS3BucketName="$S3_BUCKET" \
        MPS3BucketRegion="$AWS_REGION" \
        MPS3KeyPrefix="templates/" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --disable-rollback

echo ""
echo -e "${GREEN}✓ Infrastructure deployed!${NC}"
echo ""

# Show outputs
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo -e "${BLUE}Next: Deploy Helm stack${NC}"
echo "./scripts/deploy-helm-stack.sh $S3_BUCKET $STACK_NAME $AWS_REGION"
