#!/bin/bash
# =============================================================================
# Deploy Midaz Helm Stack (requires infrastructure stack)
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Parameters
S3_BUCKET="${1:?Usage: $0 <s3-bucket> [infra-stack] [region] [helm-stack] [product]}"
INFRA_STACK="${2:-midaz-infra}"
AWS_REGION="${3:-us-east-1}"
HELM_STACK="${4:-${INFRA_STACK}-helm}"
PRODUCT="${5:-midaz}"

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Midaz Helm Stack Deployment${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""
echo "Infra Stack:  $INFRA_STACK"
echo "Helm Stack:   $HELM_STACK"
echo "Region:       $AWS_REGION"
echo "S3 Bucket:    $S3_BUCKET"
echo ""

# Check if infra stack exists
echo "Checking infrastructure stack..."
INFRA_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$INFRA_STACK" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$INFRA_STATUS" == "NOT_FOUND" ]; then
    echo -e "${RED}❌ Infrastructure stack '$INFRA_STACK' not found${NC}"
    echo "Run deploy-infra.sh first"
    exit 1
fi

if [ "$INFRA_STATUS" != "CREATE_COMPLETE" ] && [ "$INFRA_STATUS" != "UPDATE_COMPLETE" ]; then
    echo -e "${YELLOW}⚠ Infrastructure stack status: $INFRA_STATUS${NC}"
    echo "Wait for stack to complete before deploying Helm"
    exit 1
fi

echo -e "${GREEN}✓${NC} Infrastructure stack ready"
echo ""

# Get outputs from infra stack
echo "Fetching infrastructure outputs..."
get_output() {
    aws cloudformation describe-stacks \
        --stack-name "$INFRA_STACK" \
        --region "$AWS_REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
        --output text
}

PROJECT_NAME=$(get_output "ProjectName")
VPC_ID=$(get_output "VpcId")
PRIVATE_SUBNETS=$(get_output "PrivateSubnetIds")
CLUSTER_NAME=$(get_output "EKSClusterName")
CLUSTER_SG=$(get_output "ClusterSecurityGroupId")
RDS_ENDPOINT=$(get_output "RDSEndpoint")
RDS_SECRET=$(get_output "RDSSecretArn")
DOCDB_ENDPOINT=$(get_output "DocumentDBEndpoint")
DOCDB_SECRET=$(get_output "DocumentDBSecretArn")
CACHE_ENDPOINT=$(get_output "ElastiCacheEndpoint")
MQ_ENDPOINT=$(get_output "AmazonMQEndpoint")
MQ_SECRET=$(get_output "AmazonMQSecretArn")

# Handle missing ClusterSecurityGroupId (get from EKS directly)
if [ -z "$CLUSTER_SG" ] || [ "$CLUSTER_SG" == "None" ]; then
    echo "  Fetching ClusterSecurityGroupId from EKS..."
    CLUSTER_SG=$(aws eks describe-cluster \
        --name "$CLUSTER_NAME" \
        --region "$AWS_REGION" \
        --query 'cluster.resourcesVpcConfig.clusterSecurityGroupId' \
        --output text)
fi

echo "  Project:        $PROJECT_NAME"
echo "  Cluster:        $CLUSTER_NAME"
echo "  VPC:            $VPC_ID"
echo "  RDS:            $RDS_ENDPOINT"
echo "  DocumentDB:     $DOCDB_ENDPOINT"
echo "  ElastiCache:    $CACHE_ENDPOINT"
echo "  AmazonMQ:       $MQ_ENDPOINT"
echo ""

# Deploy Helm stack
echo -e "${BLUE}Deploying Helm stack...${NC}"
aws cloudformation deploy \
    --stack-name "$HELM_STACK" \
    --template-url "https://${S3_BUCKET}.s3.${AWS_REGION}.amazonaws.com/products/${PRODUCT}/helm.yaml" \
    --parameter-overrides \
        ProjectName="$PROJECT_NAME" \
        EnvironmentName="production" \
        VpcId="$VPC_ID" \
        PrivateSubnetIds="$PRIVATE_SUBNETS" \
        ClusterName="$CLUSTER_NAME" \
        ClusterSecurityGroupId="$CLUSTER_SG" \
        RDSEndpoint="$RDS_ENDPOINT" \
        RDSSecretArn="$RDS_SECRET" \
        DocumentDBEndpoint="$DOCDB_ENDPOINT" \
        DocumentDBSecretArn="$DOCDB_SECRET" \
        ElastiCacheEndpoint="$CACHE_ENDPOINT" \
        AmazonMQEndpoint="$MQ_ENDPOINT" \
        AmazonMQSecretArn="$MQ_SECRET" \
        EnableIngress="false" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --disable-rollback

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  Helm Stack Deployed!${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""

# Show outputs
aws cloudformation describe-stacks \
    --stack-name "$HELM_STACK" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo "Configure kubectl:"
echo "  aws eks update-kubeconfig --name $CLUSTER_NAME --region $AWS_REGION"
echo ""
echo "Check pods:"
echo "  kubectl get pods -n midaz"
