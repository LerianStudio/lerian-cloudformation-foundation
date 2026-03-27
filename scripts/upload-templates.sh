#!/bin/bash
# =============================================================================
# Upload CloudFormation Templates to S3
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="${PROJECT_DIR}/templates"

# Default values
S3_BUCKET="${1:?Usage: $0 <s3-bucket> [region] [prefix]}"
AWS_REGION="${2:-us-east-1}"
S3_PREFIX="${3:-templates/}"

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Upload CloudFormation Templates to S3${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""
echo "Bucket:     $S3_BUCKET"
echo "Region:     $AWS_REGION"
echo "Prefix:     $S3_PREFIX"
echo "Source:     $TEMPLATES_DIR"
echo ""

# Check if bucket exists
if ! aws s3api head-bucket --bucket "$S3_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
    echo -e "${RED}❌ Bucket does not exist: $S3_BUCKET${NC}"
    exit 1
fi

# Upload templates
echo "Uploading templates..."
aws s3 sync "$TEMPLATES_DIR/" "s3://${S3_BUCKET}/${S3_PREFIX}" \
    --region "$AWS_REGION" \
    --exclude "*.bak" \
    --exclude ".DS_Store"

echo ""
echo -e "${GREEN}✓ Templates uploaded successfully${NC}"
echo ""

# List uploaded files
echo "Uploaded files:"
aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}" --region "$AWS_REGION"

echo ""
echo -e "${BLUE}Next step - Deploy the stack:${NC}"
echo ""
echo "  ./scripts/deploy-stack.sh \\"
echo "      --region $AWS_REGION \\"
echo "      --s3-bucket $S3_BUCKET \\"
echo "      --s3-prefix $S3_PREFIX \\"
echo "      --enable-ingress \\"
echo "      --domain api.midaz.com"
echo ""
