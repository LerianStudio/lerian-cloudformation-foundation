#!/bin/bash
#
# Deploy Midaz Helm Stack (Independent from Infrastructure)
#
# Usage:
#   ./deploy-helm.sh [INFRA_STACK_NAME] [REGION] [CHART_VERSION] [NAMESPACE]
#
# Example:
#   ./deploy-helm.sh midaz-stack-cf sa-east-1 5.3.0 midaz
#
# Prerequisites:
#   - Infrastructure stack must be deployed first (midaz-infrastructure.yaml)
#   - AWS CLI configured with appropriate permissions
#

set -e

INFRA_STACK_NAME="${1:-midaz}"
REGION="${2:-us-east-1}"
CHART_VERSION="${3:-5.3.0}"
NAMESPACE="${4:-midaz}"
HELM_REPOSITORY="${5:-oci://registry-1.docker.io/lerianstudio/midaz-helm}"

HELM_STACK_NAME="${INFRA_STACK_NAME}-helm"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="${PROJECT_DIR}/templates"
S3_BUCKET="${INFRA_STACK_NAME}-cfn-artifacts-${REGION}"

echo "=============================================="
echo "  Midaz Helm Stack Deployment"
echo "=============================================="
echo ""
echo "Infra Stack:     ${INFRA_STACK_NAME}"
echo "Helm Stack:      ${HELM_STACK_NAME}"
echo "Region:          ${REGION}"
echo "Chart Version:   ${CHART_VERSION}"
echo "Namespace:       ${NAMESPACE}"
echo ""

# Check AWS credentials
echo "Checking AWS credentials..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account:   ${AWS_ACCOUNT_ID}"
echo ""

# =============================================================================
# VERIFY INFRASTRUCTURE STACK EXISTS
# =============================================================================
echo "Verifying infrastructure stack exists..."
INFRA_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "${INFRA_STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$INFRA_STATUS" == "NOT_FOUND" ]; then
    echo "ERROR: Infrastructure stack '${INFRA_STACK_NAME}' not found in region ${REGION}"
    echo "Please deploy the infrastructure stack first using deploy.sh"
    exit 1
fi

if [[ ! "$INFRA_STATUS" =~ ^(CREATE_COMPLETE|UPDATE_COMPLETE)$ ]]; then
    echo "WARNING: Infrastructure stack is in state: ${INFRA_STATUS}"
    echo "Continuing anyway..."
fi
echo "Infrastructure stack status: ${INFRA_STATUS}"
echo ""

# =============================================================================
# GET OUTPUTS FROM INFRASTRUCTURE STACK
# =============================================================================
echo "Getting outputs from infrastructure stack..."

get_output() {
    local key=$1
    aws cloudformation describe-stacks \
        --stack-name "${INFRA_STACK_NAME}" \
        --region "${REGION}" \
        --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue" \
        --output text
}

# Get nested stack outputs by querying the nested stacks directly
get_nested_stack_id() {
    local logical_id=$1
    aws cloudformation describe-stack-resource \
        --stack-name "${INFRA_STACK_NAME}" \
        --logical-resource-id "${logical_id}" \
        --region "${REGION}" \
        --query 'StackResourceDetail.PhysicalResourceId' \
        --output text
}

get_nested_output() {
    local stack_id=$1
    local key=$2
    aws cloudformation describe-stacks \
        --stack-name "${stack_id}" \
        --region "${REGION}" \
        --query "Stacks[0].Outputs[?OutputKey=='${key}'].OutputValue" \
        --output text
}

# Get nested stack IDs
VPC_STACK=$(get_nested_stack_id "VPCStack")
EKS_STACK=$(get_nested_stack_id "EKSStack")
RDS_STACK=$(get_nested_stack_id "RDSStack")
DOCDB_STACK=$(get_nested_stack_id "DocumentDBStack")
ELASTICACHE_STACK=$(get_nested_stack_id "ElastiCacheStack")
MQ_STACK=$(get_nested_stack_id "AmazonMQStack")

# Get values from nested stacks
VPC_ID=$(get_nested_output "$VPC_STACK" "VpcId")
PRIVATE_SUBNET_IDS=$(get_nested_output "$VPC_STACK" "PrivateSubnetIds")
CLUSTER_NAME=$(get_nested_output "$EKS_STACK" "ClusterName")
CLUSTER_SG=$(get_nested_output "$EKS_STACK" "ClusterSecurityGroupId")
RDS_ENDPOINT=$(get_nested_output "$RDS_STACK" "Endpoint")
RDS_SECRET_ARN=$(get_nested_output "$RDS_STACK" "SecretArn")
DOCDB_ENDPOINT=$(get_nested_output "$DOCDB_STACK" "ClusterEndpoint")
DOCDB_SECRET_ARN=$(get_nested_output "$DOCDB_STACK" "SecretArn")
ELASTICACHE_ENDPOINT=$(get_nested_output "$ELASTICACHE_STACK" "PrimaryEndpoint")
MQ_ENDPOINT=$(get_nested_output "$MQ_STACK" "BrokerEndpoint")
MQ_SECRET_ARN=$(get_nested_output "$MQ_STACK" "SecretArn")

# Check for RDS replica (optional)
RDS_REPLICA_ENDPOINT=$(get_nested_output "$RDS_STACK" "ReplicaEndpoint" 2>/dev/null || echo "")

echo "VPC ID:              ${VPC_ID}"
echo "Cluster Name:        ${CLUSTER_NAME}"
echo "RDS Endpoint:        ${RDS_ENDPOINT}"
echo "DocumentDB Endpoint: ${DOCDB_ENDPOINT}"
echo "ElastiCache:         ${ELASTICACHE_ENDPOINT}"
echo "AmazonMQ:            ${MQ_ENDPOINT}"
echo ""

# =============================================================================
# UPLOAD HELM TEMPLATE TO S3
# =============================================================================
echo "Uploading Helm template to S3..."
aws s3 cp "${TEMPLATES_DIR}/midaz-helm.yaml" \
    "s3://${S3_BUCKET}/templates/midaz-helm.yaml" \
    --region "${REGION}"

# Use regional S3 endpoint
if [ "${REGION}" == "us-east-1" ]; then
    TEMPLATE_URL="https://${S3_BUCKET}.s3.amazonaws.com/templates/midaz-helm.yaml"
else
    TEMPLATE_URL="https://${S3_BUCKET}.s3.${REGION}.amazonaws.com/templates/midaz-helm.yaml"
fi
echo "Template URL: ${TEMPLATE_URL}"
echo ""

# =============================================================================
# DEPLOY HELM STACK
# =============================================================================
echo "Deploying Helm stack..."

# Check if stack already exists
HELM_STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "${HELM_STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$HELM_STACK_STATUS" == "NOT_FOUND" ]; then
    echo "Creating new Helm stack..."
    aws cloudformation create-stack \
        --stack-name "${HELM_STACK_NAME}" \
        --template-url "${TEMPLATE_URL}" \
        --region "${REGION}" \
        --parameters \
            ParameterKey=ProjectName,ParameterValue="${INFRA_STACK_NAME}" \
            ParameterKey=EnvironmentName,ParameterValue="production" \
            ParameterKey=VpcId,ParameterValue="${VPC_ID}" \
            ParameterKey=PrivateSubnetIds,ParameterValue=\"${PRIVATE_SUBNET_IDS}\" \
            ParameterKey=ClusterName,ParameterValue="${CLUSTER_NAME}" \
            ParameterKey=ClusterSecurityGroupId,ParameterValue="${CLUSTER_SG}" \
            ParameterKey=RDSEndpoint,ParameterValue="${RDS_ENDPOINT}" \
            ParameterKey=RDSReplicaEndpoint,ParameterValue="${RDS_REPLICA_ENDPOINT}" \
            ParameterKey=RDSSecretArn,ParameterValue="${RDS_SECRET_ARN}" \
            ParameterKey=DocumentDBEndpoint,ParameterValue="${DOCDB_ENDPOINT}" \
            ParameterKey=DocumentDBSecretArn,ParameterValue="${DOCDB_SECRET_ARN}" \
            ParameterKey=ElastiCacheEndpoint,ParameterValue="${ELASTICACHE_ENDPOINT}" \
            ParameterKey=AmazonMQEndpoint,ParameterValue="${MQ_ENDPOINT}" \
            ParameterKey=AmazonMQSecretArn,ParameterValue="${MQ_SECRET_ARN}" \
            ParameterKey=MidazHelmRepository,ParameterValue="${HELM_REPOSITORY}" \
            ParameterKey=MidazChartVersion,ParameterValue="${CHART_VERSION}" \
            ParameterKey=MidazNamespace,ParameterValue="${NAMESPACE}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --disable-rollback

    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete \
        --stack-name "${HELM_STACK_NAME}" \
        --region "${REGION}"
else
    echo "Updating existing Helm stack (current status: ${HELM_STACK_STATUS})..."

    # If stack is in a failed state, we might need to delete and recreate
    if [[ "$HELM_STACK_STATUS" =~ ^(ROLLBACK_COMPLETE|ROLLBACK_FAILED|DELETE_FAILED)$ ]]; then
        echo "Stack is in failed state. Deleting and recreating..."
        aws cloudformation delete-stack \
            --stack-name "${HELM_STACK_NAME}" \
            --region "${REGION}"

        echo "Waiting for stack deletion..."
        aws cloudformation wait stack-delete-complete \
            --stack-name "${HELM_STACK_NAME}" \
            --region "${REGION}"

        echo "Creating new Helm stack..."
        aws cloudformation create-stack \
            --stack-name "${HELM_STACK_NAME}" \
            --template-url "${TEMPLATE_URL}" \
            --region "${REGION}" \
            --parameters \
                ParameterKey=ProjectName,ParameterValue="${INFRA_STACK_NAME}" \
                ParameterKey=EnvironmentName,ParameterValue="production" \
                ParameterKey=VpcId,ParameterValue="${VPC_ID}" \
                ParameterKey=PrivateSubnetIds,ParameterValue=\"${PRIVATE_SUBNET_IDS}\" \
                ParameterKey=ClusterName,ParameterValue="${CLUSTER_NAME}" \
                ParameterKey=ClusterSecurityGroupId,ParameterValue="${CLUSTER_SG}" \
                ParameterKey=RDSEndpoint,ParameterValue="${RDS_ENDPOINT}" \
                ParameterKey=RDSReplicaEndpoint,ParameterValue="${RDS_REPLICA_ENDPOINT}" \
                ParameterKey=RDSSecretArn,ParameterValue="${RDS_SECRET_ARN}" \
                ParameterKey=DocumentDBEndpoint,ParameterValue="${DOCDB_ENDPOINT}" \
                ParameterKey=DocumentDBSecretArn,ParameterValue="${DOCDB_SECRET_ARN}" \
                ParameterKey=ElastiCacheEndpoint,ParameterValue="${ELASTICACHE_ENDPOINT}" \
                ParameterKey=AmazonMQEndpoint,ParameterValue="${MQ_ENDPOINT}" \
                ParameterKey=AmazonMQSecretArn,ParameterValue="${MQ_SECRET_ARN}" \
                ParameterKey=MidazHelmRepository,ParameterValue="${HELM_REPOSITORY}" \
                ParameterKey=MidazChartVersion,ParameterValue="${CHART_VERSION}" \
                ParameterKey=MidazNamespace,ParameterValue="${NAMESPACE}" \
            --capabilities CAPABILITY_NAMED_IAM \
            --disable-rollback

        echo "Waiting for stack creation..."
        aws cloudformation wait stack-create-complete \
            --stack-name "${HELM_STACK_NAME}" \
            --region "${REGION}"
    else
        aws cloudformation update-stack \
            --stack-name "${HELM_STACK_NAME}" \
            --template-url "${TEMPLATE_URL}" \
            --region "${REGION}" \
            --parameters \
                ParameterKey=ProjectName,ParameterValue="${INFRA_STACK_NAME}" \
                ParameterKey=EnvironmentName,ParameterValue="production" \
                ParameterKey=VpcId,ParameterValue="${VPC_ID}" \
                ParameterKey=PrivateSubnetIds,ParameterValue=\"${PRIVATE_SUBNET_IDS}\" \
                ParameterKey=ClusterName,ParameterValue="${CLUSTER_NAME}" \
                ParameterKey=ClusterSecurityGroupId,ParameterValue="${CLUSTER_SG}" \
                ParameterKey=RDSEndpoint,ParameterValue="${RDS_ENDPOINT}" \
                ParameterKey=RDSReplicaEndpoint,ParameterValue="${RDS_REPLICA_ENDPOINT}" \
                ParameterKey=RDSSecretArn,ParameterValue="${RDS_SECRET_ARN}" \
                ParameterKey=DocumentDBEndpoint,ParameterValue="${DOCDB_ENDPOINT}" \
                ParameterKey=DocumentDBSecretArn,ParameterValue="${DOCDB_SECRET_ARN}" \
                ParameterKey=ElastiCacheEndpoint,ParameterValue="${ELASTICACHE_ENDPOINT}" \
                ParameterKey=AmazonMQEndpoint,ParameterValue="${MQ_ENDPOINT}" \
                ParameterKey=AmazonMQSecretArn,ParameterValue="${MQ_SECRET_ARN}" \
                ParameterKey=MidazHelmRepository,ParameterValue="${HELM_REPOSITORY}" \
                ParameterKey=MidazChartVersion,ParameterValue="${CHART_VERSION}" \
                ParameterKey=MidazNamespace,ParameterValue="${NAMESPACE}" \
            --capabilities CAPABILITY_NAMED_IAM \
            2>/dev/null || echo "No updates to perform"

        echo "Waiting for stack update..."
        aws cloudformation wait stack-update-complete \
            --stack-name "${HELM_STACK_NAME}" \
            --region "${REGION}" 2>/dev/null || true
    fi
fi

echo ""
echo "=============================================="
echo "  Helm Stack Deployment Complete!"
echo "=============================================="
echo ""

# Get outputs
echo "Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name "${HELM_STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo "To configure kubectl:"
echo "  aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${REGION}"
echo ""
echo "To access Midaz:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo "  kubectl get svc -n ${NAMESPACE}"
