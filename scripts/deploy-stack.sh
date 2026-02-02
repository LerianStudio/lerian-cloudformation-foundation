#!/bin/bash
# =============================================================================
# Deploy Midaz Stack
# Deploys the complete Midaz stack with customizable options
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

# Get script directory for absolute paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE_FILE="${PROJECT_DIR}/templates/midaz-complete.yaml"

# Infrastructure defaults
ENVIRONMENT="${ENVIRONMENT:-production}"
PROJECT_NAME="${PROJECT_NAME:-midaz}"
VPC_CIDR="${VPC_CIDR:-10.50.0.0/16}"

# EKS defaults
K8S_VERSION="${K8S_VERSION:-1.32}"
NODE_INSTANCE_TYPE="${NODE_INSTANCE_TYPE:-c7g.large}"
NODE_COUNT="${NODE_COUNT:-3}"

# Application defaults
DEPLOY_APP="${DEPLOY_APP:-true}"
MIDAZ_VERSION="${MIDAZ_VERSION:-latest}"
MIDAZ_REPLICAS="${MIDAZ_REPLICAS:-2}"

# Ingress defaults
ENABLE_INGRESS="${ENABLE_INGRESS:-false}"
ENABLE_ALB_CONTROLLER="${ENABLE_ALB_CONTROLLER:-true}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
CERTIFICATE_ARN="${CERTIFICATE_ARN:-}"

# S3 Template location (for nested stacks)
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-templates/}"

# =============================================================================
# Functions
# =============================================================================

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --stack-name NAME        Stack name (default: midaz)"
    echo "  --region REGION          AWS region (default: us-east-1)"
    echo "  --environment ENV        Environment name (default: production)"
    echo ""
    echo "  --enable-ingress         Enable ALB Ingress for the API"
    echo "  --domain NAME            Domain name for ingress (e.g., api.midaz.example.com)"
    echo "  --certificate-arn ARN    ACM certificate ARN for HTTPS"
    echo ""
    echo "  --node-type TYPE         EKS node instance type (default: c7g.large)"
    echo "  --node-count N           Number of EKS nodes (default: 3)"
    echo "  --replicas N             Midaz application replicas (default: 2)"
    echo ""
    echo "  --s3-bucket BUCKET       S3 bucket with templates (required for nested stacks)"
    echo "  --s3-prefix PREFIX       S3 key prefix (default: templates/)"
    echo ""
    echo "  --infra-only             Deploy infrastructure only (no application)"
    echo "  --dry-run                Show what would be deployed without deploying"
    echo "  --help                   Show this help"
    echo ""
    echo "Examples:"
    echo "  # Basic deployment"
    echo "  $0 --stack-name midaz-dev --region us-east-1"
    echo ""
    echo "  # With ingress enabled"
    echo "  $0 --stack-name midaz-prod --enable-ingress --domain api.midaz.example.com"
    echo ""
    echo "  # Production with HTTPS"
    echo "  $0 --enable-ingress --domain api.midaz.com --certificate-arn arn:aws:acm:..."
    echo ""
}

# =============================================================================
# Parse arguments
# =============================================================================

DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
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
        --enable-ingress)
            ENABLE_INGRESS="true"
            shift
            ;;
        --domain)
            DOMAIN_NAME="$2"
            shift 2
            ;;
        --certificate-arn)
            CERTIFICATE_ARN="$2"
            shift 2
            ;;
        --node-type)
            NODE_INSTANCE_TYPE="$2"
            shift 2
            ;;
        --node-count)
            NODE_COUNT="$2"
            shift 2
            ;;
        --replicas)
            MIDAZ_REPLICAS="$2"
            shift 2
            ;;
        --s3-bucket)
            S3_BUCKET="$2"
            shift 2
            ;;
        --s3-prefix)
            S3_PREFIX="$2"
            shift 2
            ;;
        --infra-only)
            DEPLOY_APP="false"
            shift
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
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# =============================================================================
# Validate template exists
# =============================================================================

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}❌ Invalid template path: $TEMPLATE_FILE${NC}"
    echo "   Make sure you're running from the project root directory."
    exit 1
fi

# =============================================================================
# Get Availability Zones
# =============================================================================

echo -e "${BLUE}=========================================="
echo "Midaz Stack Deployment"
echo -e "==========================================${NC}"
echo ""

echo "Fetching availability zones for $AWS_REGION..."
AZS=($(aws ec2 describe-availability-zones \
    --region "$AWS_REGION" \
    --query 'AvailabilityZones[?State==`available`].ZoneName' \
    --output text | tr '\t' '\n' | head -3))

if [ ${#AZS[@]} -lt 3 ]; then
    echo -e "${RED}❌ Need at least 3 availability zones, found ${#AZS[@]}${NC}"
    exit 1
fi

AZ1="${AZS[0]}"
AZ2="${AZS[1]}"
AZ3="${AZS[2]}"

echo -e "  ${GREEN}✓${NC} Using AZs: $AZ1, $AZ2, $AZ3"
echo ""

# =============================================================================
# Build parameters
# =============================================================================

PARAMS=(
    "AvailabilityZone1=$AZ1"
    "AvailabilityZone2=$AZ2"
    "AvailabilityZone3=$AZ3"
    "EnvironmentName=$ENVIRONMENT"
    "ProjectName=$PROJECT_NAME"
    "VpcCIDR=$VPC_CIDR"
    "KubernetesVersion=$K8S_VERSION"
    "NodeInstanceType=$NODE_INSTANCE_TYPE"
    "NodeGroupDesiredSize=$NODE_COUNT"
    "DeployMidazApplication=$DEPLOY_APP"
    "MidazVersion=$MIDAZ_VERSION"
    "MidazReplicas=$MIDAZ_REPLICAS"
    "EnableALBController=$ENABLE_ALB_CONTROLLER"
    "EnableIngress=$ENABLE_INGRESS"
)

# Add S3 bucket if provided
if [ -n "$S3_BUCKET" ]; then
    PARAMS+=("MPS3BucketName=$S3_BUCKET")
    PARAMS+=("MPS3BucketRegion=$AWS_REGION")
    PARAMS+=("MPS3KeyPrefix=$S3_PREFIX")
fi

# Add domain if provided
if [ -n "$DOMAIN_NAME" ]; then
    PARAMS+=("DomainName=$DOMAIN_NAME")
fi

# Add certificate if provided
if [ -n "$CERTIFICATE_ARN" ]; then
    PARAMS+=("IngressCertificateArn=$CERTIFICATE_ARN")
fi

# =============================================================================
# Show configuration
# =============================================================================

echo -e "${BLUE}Configuration:${NC}"
echo "  Stack Name:      $STACK_NAME"
echo "  Region:          $AWS_REGION"
echo "  Environment:     $ENVIRONMENT"
echo ""
echo -e "${BLUE}Infrastructure:${NC}"
echo "  VPC CIDR:        $VPC_CIDR"
echo "  Node Type:       $NODE_INSTANCE_TYPE"
echo "  Node Count:      $NODE_COUNT"
echo ""
echo -e "${BLUE}Application:${NC}"
echo "  Deploy App:      $DEPLOY_APP"
echo "  Midaz Version:   $MIDAZ_VERSION"
echo "  Replicas:        $MIDAZ_REPLICAS"
echo ""
echo -e "${BLUE}Ingress:${NC}"
echo "  ALB Controller:  $ENABLE_ALB_CONTROLLER"
echo "  Enable Ingress:  $ENABLE_INGRESS"
if [ -n "$DOMAIN_NAME" ]; then
    echo "  Domain:          $DOMAIN_NAME"
fi
if [ -n "$CERTIFICATE_ARN" ]; then
    echo "  Certificate:     $CERTIFICATE_ARN"
fi
echo ""

# =============================================================================
# Deploy
# =============================================================================

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY RUN - Command that would be executed:${NC}"
    echo ""
    echo "aws cloudformation deploy \\"
    echo "  --stack-name $STACK_NAME \\"
    echo "  --template-file $TEMPLATE_FILE \\"
    echo "  --parameter-overrides \\"
    for param in "${PARAMS[@]}"; do
        echo "    $param \\"
    done
    echo "  --capabilities CAPABILITY_NAMED_IAM \\"
    echo "  --region $AWS_REGION"
    echo ""
    exit 0
fi

echo -e "${BLUE}Starting deployment...${NC}"
echo "This will take approximately 30-45 minutes."
echo ""

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
fi

# Deploy
aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file "$TEMPLATE_FILE" \
    --parameter-overrides "${PARAMS[@]}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --no-fail-on-empty-changeset

echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo -e "==========================================${NC}"
echo ""

# Get outputs
echo "Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo "Next steps:"
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
fi
