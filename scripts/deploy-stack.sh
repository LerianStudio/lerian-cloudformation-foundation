#!/bin/bash
# =============================================================================
# Deploy Midaz Complete Stack
# Deploys the complete Midaz stack (infrastructure + application) with all options
#
# This script:
#   1. Creates S3 bucket for templates (if needed)
#   2. Uploads all nested templates to S3
#   3. Deploys the complete CloudFormation stack
#
# Usage:
#   ./deploy-stack.sh [options]
#
# Examples:
#   ./deploy-stack.sh --stack-name midaz-dev --region us-east-1
#   ./deploy-stack.sh --stack-name midaz-prod --enable-ingress --domain midaz.net --ingress-host ledger.midaz.net
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
STACK_NAME="${STACK_NAME:-midaz}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PRODUCT="${PRODUCT:-midaz}"

# Get script directory for absolute paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="${PROJECT_DIR}/templates"
TEMPLATE_FILE="${PROJECT_DIR}/products/${PRODUCT}/full-stack.yaml"

# Infrastructure defaults
ENVIRONMENT="${ENVIRONMENT:-production}"
PROJECT_NAME="${PROJECT_NAME:-${PRODUCT}}"
VPC_CIDR="${VPC_CIDR:-10.50.0.0/16}"

# EKS defaults
K8S_VERSION="${K8S_VERSION:-1.31}"
NODE_INSTANCE_TYPE="${NODE_INSTANCE_TYPE:-m7g.large}"
NODE_MIN="${NODE_MIN:-2}"
NODE_MAX="${NODE_MAX:-10}"
NODE_DESIRED="${NODE_DESIRED:-3}"

# Database defaults
RDS_INSTANCE_CLASS="${RDS_INSTANCE_CLASS:-db.r6g.large}"
RDS_MULTI_AZ="${RDS_MULTI_AZ:-true}"
DOCDB_INSTANCE_CLASS="${DOCDB_INSTANCE_CLASS:-db.r6g.large}"
DOCDB_INSTANCE_COUNT="${DOCDB_INSTANCE_COUNT:-3}"
ELASTICACHE_NODE_TYPE="${ELASTICACHE_NODE_TYPE:-cache.r6g.large}"

# Application defaults
DEPLOY_APP="${DEPLOY_APP:-true}"
MIDAZ_VERSION="${MIDAZ_VERSION:-latest}"
MIDAZ_REPLICAS="${MIDAZ_REPLICAS:-2}"

# Ingress defaults
ENABLE_INGRESS="${ENABLE_INGRESS:-false}"
ENABLE_ALB_CONTROLLER="${ENABLE_ALB_CONTROLLER:-true}"
ENABLE_EXTERNAL_DNS="${ENABLE_EXTERNAL_DNS:-true}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
INGRESS_HOSTNAME="${INGRESS_HOSTNAME:-}"
CERTIFICATE_ARN="${CERTIFICATE_ARN:-}"

# =============================================================================
# Functions
# =============================================================================

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "General Options:"
    echo "  --product NAME           Product name (default: midaz, looks up products/<name>/full-stack.yaml)"
    echo "  --stack-name NAME        Stack name (default: midaz)"
    echo "  --region REGION          AWS region (default: us-east-1)"
    echo "  --environment ENV        Environment name (default: production)"
    echo "  --project-name NAME      Project name for resources (default: midaz)"
    echo ""
    echo "EKS Options:"
    echo "  --node-type TYPE         EKS node instance type (default: m7g.large)"
    echo "  --node-min N             Minimum nodes (default: 2)"
    echo "  --node-max N             Maximum nodes (default: 10)"
    echo "  --node-desired N         Desired nodes (default: 3)"
    echo "  --k8s-version VER        Kubernetes version (default: 1.31)"
    echo ""
    echo "Database Options:"
    echo "  --rds-class CLASS        RDS instance class (default: db.r6g.large)"
    echo "  --rds-single-az          Disable Multi-AZ for RDS"
    echo "  --docdb-class CLASS      DocumentDB instance class (default: db.r6g.large)"
    echo "  --docdb-count N          DocumentDB instance count (default: 3)"
    echo ""
    echo "Ingress Options:"
    echo "  --enable-ingress         Enable ALB Ingress for the API"
    echo "  --domain NAME            Base domain for Route53 (e.g., midaz.net)"
    echo "  --ingress-host HOST      Full hostname for Ingress (e.g., ledger.midaz.net)"
    echo "  --certificate-arn ARN    ACM certificate ARN for HTTPS"
    echo ""
    echo "Application Options:"
    echo "  --infra-only             Deploy infrastructure only (no application)"
    echo "  --replicas N             Midaz application replicas (default: 2)"
    echo "  --midaz-version VER      Midaz version (default: latest)"
    echo ""
    echo "Other Options:"
    echo "  --dry-run                Show what would be deployed without deploying"
    echo "  --help                   Show this help"
    echo ""
    echo "Examples:"
    echo "  # Basic deployment"
    echo "  $0 --stack-name midaz-dev --region us-east-1"
    echo ""
    echo "  # With ingress enabled"
    echo "  $0 --stack-name midaz-prod --enable-ingress --domain midaz.net --ingress-host ledger.midaz.net"
    echo ""
    echo "  # Production with HTTPS"
    echo "  $0 --stack-name midaz-prod --enable-ingress --domain midaz.net --ingress-host ledger.midaz.net --certificate-arn arn:aws:acm:..."
    echo ""
    echo "  # Minimal for development"
    echo "  $0 --stack-name midaz-dev --node-type m7g.medium --node-desired 2 --rds-single-az --docdb-count 1"
    echo ""
}

# Cross-platform sed in-place edit
sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# =============================================================================
# Parse arguments
# =============================================================================

DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --product)
            PRODUCT="$2"
            TEMPLATE_FILE="${PROJECT_DIR}/products/${PRODUCT}/full-stack.yaml"
            shift 2
            ;;
        --stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --node-type)
            NODE_INSTANCE_TYPE="$2"
            shift 2
            ;;
        --node-min)
            NODE_MIN="$2"
            shift 2
            ;;
        --node-max)
            NODE_MAX="$2"
            shift 2
            ;;
        --node-desired)
            NODE_DESIRED="$2"
            shift 2
            ;;
        --k8s-version)
            K8S_VERSION="$2"
            shift 2
            ;;
        --rds-class)
            RDS_INSTANCE_CLASS="$2"
            shift 2
            ;;
        --rds-single-az)
            RDS_MULTI_AZ="false"
            shift
            ;;
        --docdb-class)
            DOCDB_INSTANCE_CLASS="$2"
            shift 2
            ;;
        --docdb-count)
            DOCDB_INSTANCE_COUNT="$2"
            shift 2
            ;;
        --enable-ingress)
            ENABLE_INGRESS="true"
            shift
            ;;
        --domain)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        --ingress-host)
            INGRESS_HOSTNAME="$2"
            shift 2
            ;;
        --certificate-arn)
            CERTIFICATE_ARN="$2"
            shift 2
            ;;
        --infra-only)
            DEPLOY_APP="false"
            shift
            ;;
        --replicas)
            MIDAZ_REPLICAS="$2"
            shift 2
            ;;
        --midaz-version)
            MIDAZ_VERSION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# S3 bucket for nested templates
S3_BUCKET="${STACK_NAME}-cfn-templates-${AWS_REGION}"
S3_PREFIX="templates/"

# =============================================================================
# Validate
# =============================================================================

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}Error: Template not found: $TEMPLATE_FILE${NC}"
    echo "Make sure you're running from the project root directory."
    exit 1
fi

# =============================================================================
# Header
# =============================================================================

echo -e "${BLUE}=========================================="
echo "  Midaz Complete Stack Deployment"
echo -e "==========================================${NC}"
echo ""

# =============================================================================
# Check AWS credentials
# =============================================================================

echo "Checking AWS credentials..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
    echo -e "${RED}Error: AWS credentials not configured or expired${NC}"
    echo "Run: aws sso login"
    exit 1
}
echo -e "  ${GREEN}✓${NC} AWS Account: ${AWS_ACCOUNT_ID}"
echo ""

# =============================================================================
# Get Availability Zones
# =============================================================================

echo "Fetching availability zones for $AWS_REGION..."
AZS=($(aws ec2 describe-availability-zones \
    --region "$AWS_REGION" \
    --query 'AvailabilityZones[?State==`available`].ZoneName' \
    --output text | tr '\t' '\n' | sort | head -3))

if [ ${#AZS[@]} -lt 3 ]; then
    echo -e "${RED}Error: Need at least 3 availability zones, found ${#AZS[@]}${NC}"
    exit 1
fi

AZ1="${AZS[0]}"
AZ2="${AZS[1]}"
AZ3="${AZS[2]}"

echo -e "  ${GREEN}✓${NC} Using AZs: $AZ1, $AZ2, $AZ3"
echo ""

# =============================================================================
# Show configuration
# =============================================================================

echo -e "${BLUE}Configuration:${NC}"
echo "  Stack Name:      $STACK_NAME"
echo "  Project Name:    $PROJECT_NAME"
echo "  Region:          $AWS_REGION"
echo "  Environment:     $ENVIRONMENT"
echo ""
echo -e "${BLUE}Network:${NC}"
echo "  VPC CIDR:        $VPC_CIDR"
echo "  AZs:             $AZ1, $AZ2, $AZ3"
echo ""
echo -e "${BLUE}EKS:${NC}"
echo "  Kubernetes:      $K8S_VERSION"
echo "  Node Type:       $NODE_INSTANCE_TYPE"
echo "  Nodes:           $NODE_MIN (min) / $NODE_DESIRED (desired) / $NODE_MAX (max)"
echo ""
echo -e "${BLUE}Databases:${NC}"
echo "  RDS Class:       $RDS_INSTANCE_CLASS (Multi-AZ: $RDS_MULTI_AZ)"
echo "  DocumentDB:      $DOCDB_INSTANCE_CLASS x $DOCDB_INSTANCE_COUNT"
echo "  ElastiCache:     $ELASTICACHE_NODE_TYPE"
echo ""
echo -e "${BLUE}Application:${NC}"
echo "  Deploy App:      $DEPLOY_APP"
echo "  Midaz Version:   $MIDAZ_VERSION"
echo "  Replicas:        $MIDAZ_REPLICAS"
echo ""
echo -e "${BLUE}Ingress:${NC}"
echo "  ALB Controller:  $ENABLE_ALB_CONTROLLER"
echo "  External DNS:    $ENABLE_EXTERNAL_DNS"
echo "  Enable Ingress:  $ENABLE_INGRESS"
if [ -n "$DOMAIN_NAME" ]; then
    echo "  Domain:          $DOMAIN_NAME"
fi
if [ -n "$INGRESS_HOSTNAME" ]; then
    echo "  Ingress Host:    $INGRESS_HOSTNAME"
fi
if [ -n "$CERTIFICATE_ARN" ]; then
    echo "  Certificate:     $CERTIFICATE_ARN"
fi
echo ""
echo -e "${BLUE}S3:${NC}"
echo "  Bucket:          $S3_BUCKET"
echo "  Prefix:          $S3_PREFIX"
echo ""

# =============================================================================
# Dry Run
# =============================================================================

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY RUN - No changes will be made${NC}"
    echo ""
    echo "Would create/update:"
    echo "  1. S3 bucket: $S3_BUCKET"
    echo "  2. Upload templates to: s3://$S3_BUCKET/$S3_PREFIX"
    echo "  3. CloudFormation stack: $STACK_NAME"
    echo ""
    exit 0
fi

# =============================================================================
# Create S3 bucket
# =============================================================================

echo -e "${BLUE}Step 1: Creating S3 bucket for templates...${NC}"

if aws s3api head-bucket --bucket "$S3_BUCKET" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Bucket exists: $S3_BUCKET"
else
    echo "  Creating bucket: $S3_BUCKET"
    if [ "$AWS_REGION" == "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$S3_BUCKET" \
            --region "$AWS_REGION"
    else
        aws s3api create-bucket \
            --bucket "$S3_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
    fi

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "$S3_BUCKET" \
        --versioning-configuration Status=Enabled

    echo -e "  ${GREEN}✓${NC} Bucket created"
fi
echo ""

# =============================================================================
# Upload templates to S3
# =============================================================================

echo -e "${BLUE}Step 2: Uploading templates to S3...${NC}"

for template in "$TEMPLATES_DIR"/*.yaml; do
    template_name=$(basename "$template")
    echo "  Uploading: $template_name"
    aws s3 cp "$template" "s3://$S3_BUCKET/${S3_PREFIX}${template_name}" \
        --region "$AWS_REGION" \
        --quiet
done

# Upload product templates
PRODUCTS_DIR="${PROJECT_DIR}/products"
for product_dir in "$PRODUCTS_DIR"/*/; do
    product=$(basename "$product_dir")
    for template in "$product_dir"*.yaml; do
        template_name=$(basename "$template")
        echo "  Uploading: products/$product/$template_name"
        aws s3 cp "$template" "s3://$S3_BUCKET/${S3_PREFIX}products/${product}/${template_name}" \
            --region "$AWS_REGION" \
            --quiet
    done
done

echo -e "  ${GREEN}✓${NC} Templates uploaded to s3://$S3_BUCKET/$S3_PREFIX"
echo ""

# =============================================================================
# Build parameters
# =============================================================================

echo -e "${BLUE}Step 3: Building CloudFormation parameters...${NC}"

PARAMS=(
    "ParameterKey=MPS3BucketName,ParameterValue=$S3_BUCKET"
    "ParameterKey=MPS3BucketRegion,ParameterValue=$AWS_REGION"
    "ParameterKey=MPS3KeyPrefix,ParameterValue=$S3_PREFIX"
    "ParameterKey=AvailabilityZone1,ParameterValue=$AZ1"
    "ParameterKey=AvailabilityZone2,ParameterValue=$AZ2"
    "ParameterKey=AvailabilityZone3,ParameterValue=$AZ3"
    "ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT"
    "ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME"
    "ParameterKey=VpcCIDR,ParameterValue=$VPC_CIDR"
    "ParameterKey=KubernetesVersion,ParameterValue=$K8S_VERSION"
    "ParameterKey=NodeInstanceType,ParameterValue=$NODE_INSTANCE_TYPE"
    "ParameterKey=NodeGroupMinSize,ParameterValue=$NODE_MIN"
    "ParameterKey=NodeGroupMaxSize,ParameterValue=$NODE_MAX"
    "ParameterKey=NodeGroupDesiredSize,ParameterValue=$NODE_DESIRED"
    "ParameterKey=RDSInstanceClass,ParameterValue=$RDS_INSTANCE_CLASS"
    "ParameterKey=RDSMultiAZ,ParameterValue=$RDS_MULTI_AZ"
    "ParameterKey=DocumentDBInstanceClass,ParameterValue=$DOCDB_INSTANCE_CLASS"
    "ParameterKey=DocumentDBInstanceCount,ParameterValue=$DOCDB_INSTANCE_COUNT"
    "ParameterKey=ElastiCacheNodeType,ParameterValue=$ELASTICACHE_NODE_TYPE"
    "ParameterKey=DeployMidazApplication,ParameterValue=$DEPLOY_APP"
    "ParameterKey=MidazVersion,ParameterValue=$MIDAZ_VERSION"
    "ParameterKey=MidazReplicas,ParameterValue=$MIDAZ_REPLICAS"
    "ParameterKey=EnableALBController,ParameterValue=$ENABLE_ALB_CONTROLLER"
    "ParameterKey=EnableExternalDNS,ParameterValue=$ENABLE_EXTERNAL_DNS"
    "ParameterKey=EnableIngress,ParameterValue=$ENABLE_INGRESS"
)

# Add optional parameters
if [ -n "$DOMAIN_NAME" ]; then
    PARAMS+=("ParameterKey=DomainName,ParameterValue=$DOMAIN_NAME")
fi

if [ -n "$INGRESS_HOSTNAME" ]; then
    PARAMS+=("ParameterKey=IngressHostname,ParameterValue=$INGRESS_HOSTNAME")
fi

if [ -n "$CERTIFICATE_ARN" ]; then
    PARAMS+=("ParameterKey=IngressCertificateArn,ParameterValue=$CERTIFICATE_ARN")
fi

echo -e "  ${GREEN}✓${NC} Parameters ready (${#PARAMS[@]} parameters)"
echo ""

# =============================================================================
# Deploy CloudFormation stack
# =============================================================================

echo -e "${BLUE}Step 4: Deploying CloudFormation stack...${NC}"
echo ""
echo "This will take approximately 45-60 minutes."
echo ""

# Use regional S3 URL
if [ "$AWS_REGION" == "us-east-1" ]; then
    TEMPLATE_URL="https://$S3_BUCKET.s3.amazonaws.com/${S3_PREFIX}products/${PRODUCT}/full-stack.yaml"
else
    TEMPLATE_URL="https://$S3_BUCKET.s3.$AWS_REGION.amazonaws.com/${S3_PREFIX}products/${PRODUCT}/full-stack.yaml"
fi

# Check if stack exists
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [ "$STACK_STATUS" != "DOES_NOT_EXIST" ]; then
    echo -e "${YELLOW}Stack '$STACK_NAME' already exists (status: $STACK_STATUS)${NC}"
    read -p "Update existing stack? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi

    echo "Updating stack..."
    aws cloudformation update-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$TEMPLATE_URL" \
        --parameters "${PARAMS[@]}" \
        --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
        --region "$AWS_REGION" || {
            echo -e "${YELLOW}No updates to perform${NC}"
            exit 0
        }

    echo "Waiting for stack update to complete..."
    aws cloudformation wait stack-update-complete \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"
else
    echo "Creating stack..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-url "$TEMPLATE_URL" \
        --parameters "${PARAMS[@]}" \
        --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
        --region "$AWS_REGION" \
        --disable-rollback \
        --on-failure DO_NOTHING

    echo "Waiting for stack creation to complete..."
    echo "(You can check progress in AWS Console: CloudFormation > Stacks > $STACK_NAME)"
    echo ""

    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"
fi

echo ""
echo -e "${GREEN}=========================================="
echo "  Deployment Complete!"
echo -e "==========================================${NC}"
echo ""

# =============================================================================
# Get outputs
# =============================================================================

echo "Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo ""
echo "  # Configure kubectl"
echo "  aws eks update-kubeconfig --name ${PROJECT_NAME}-eks --region $AWS_REGION"
echo ""
echo "  # Check Midaz pods"
echo "  kubectl get pods -n midaz"
echo ""

if [ "$ENABLE_INGRESS" = "true" ]; then
    echo "  # Get Ingress endpoint"
    echo "  kubectl get ingress -n midaz"
    echo ""
    if [ -n "$INGRESS_HOSTNAME" ]; then
        echo "  # Access Midaz API (after DNS propagation)"
        echo "  curl https://$INGRESS_HOSTNAME/health"
        echo ""
    fi
fi

echo -e "${BLUE}Useful commands:${NC}"
echo ""
echo "  # View stack events"
echo "  aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $AWS_REGION"
echo ""
echo "  # Delete stack"
echo "  aws cloudformation delete-stack --stack-name $STACK_NAME --region $AWS_REGION"
echo ""
