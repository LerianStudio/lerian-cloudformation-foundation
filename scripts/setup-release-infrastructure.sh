#!/bin/bash
# =============================================================================
# Setup Release Infrastructure
# Creates S3 bucket and configures GitHub OIDC for automated releases
# =============================================================================

set -e

# Configuration
STACK_NAME="midaz-cfn-templates-bucket"
BUCKET_NAME="${BUCKET_NAME:-midaz-cloudformation-templates}"
AWS_REGION="${AWS_REGION:-us-east-1}"
GITHUB_ORG="${GITHUB_ORG:-LerianStudio}"
GITHUB_REPO="${GITHUB_REPO:-midaz-cloudformation-foundation}"

echo "=========================================="
echo "Midaz CloudFormation Release Infrastructure Setup"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Stack Name:  $STACK_NAME"
echo "  Bucket Name: $BUCKET_NAME"
echo "  AWS Region:  $AWS_REGION"
echo "  GitHub Repo: $GITHUB_ORG/$GITHUB_REPO"
echo ""

# Check AWS credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi
echo "✓ AWS credentials configured"
echo ""

# Check if GitHub OIDC provider exists
echo "Checking GitHub OIDC provider..."
OIDC_ARN=$(aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn" --output text 2>/dev/null || true)

if [ -z "$OIDC_ARN" ]; then
    echo "Creating GitHub OIDC provider..."
    aws iam create-open-id-connect-provider \
        --url https://token.actions.githubusercontent.com \
        --client-id-list sts.amazonaws.com \
        --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 1c58a3a8518e8759bf075b76b750d4f2df264fcd
    echo "✓ GitHub OIDC provider created"
else
    echo "✓ GitHub OIDC provider already exists: $OIDC_ARN"
fi
echo ""

# Update the CloudFormation template with the correct GitHub repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")/infrastructure"

# Cross-platform sed in-place edit
sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

echo "Updating infrastructure template..."
sed_inplace "s|repo:LerianStudio/midaz-cloudformation-foundation:|repo:${GITHUB_ORG}/${GITHUB_REPO}:|g" "$INFRA_DIR/s3-templates-bucket.yaml"
echo "✓ Template updated for $GITHUB_ORG/$GITHUB_REPO"
echo ""

# Deploy the stack
echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file "$INFRA_DIR/s3-templates-bucket.yaml" \
    --parameter-overrides \
        BucketName="$BUCKET_NAME" \
        EnableVersioning="true" \
        EnableLogging="true" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --tags \
        Project=midaz \
        Purpose=CloudFormationTemplates

echo "✓ Stack deployed successfully"
echo ""

# Get outputs
echo "Getting stack outputs..."
ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='GitHubActionsRoleArn'].OutputValue" \
    --output text \
    --region "$AWS_REGION")

TEMPLATES_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='TemplatesBaseUrl'].OutputValue" \
    --output text \
    --region "$AWS_REGION")

QUICK_LAUNCH=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='QuickLaunchUrl'].OutputValue" \
    --output text \
    --region "$AWS_REGION")

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo ""
echo "1. Add the following secret to your GitHub repository:"
echo "   Settings > Secrets and variables > Actions > New repository secret"
echo ""
echo "   Name:  AWS_ROLE_ARN"
echo "   Value: $ROLE_ARN"
echo ""
echo "2. Create a new release by tagging:"
echo "   git tag v1.0.0"
echo "   git push origin v1.0.0"
echo ""
echo "3. Templates will be available at:"
echo "   $TEMPLATES_URL/latest/"
echo "   $TEMPLATES_URL/v1.0.0/"
echo ""
echo "4. Quick Launch URL:"
echo "   $QUICK_LAUNCH"
echo ""
echo "5. AWS Marketplace Parameters:"
echo "   MPS3BucketName: $BUCKET_NAME"
echo "   MPS3BucketRegion: $AWS_REGION"
echo "   MPS3KeyPrefix: templates/latest/"
echo ""
