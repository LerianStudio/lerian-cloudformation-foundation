#!/bin/bash
# =============================================================================
# Midaz CloudFormation Validation Script
# Validates templates for AWS Marketplace compatibility
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$PROJECT_DIR/templates"

echo "=========================================="
echo "Midaz CloudFormation Template Validation"
echo "=========================================="
echo ""

# Check if cfn-lint is installed
if ! command -v cfn-lint &> /dev/null; then
    echo "WARNING: cfn-lint not found. Install with: pip install cfn-lint"
    echo "Skipping cfn-lint validation..."
    CFN_LINT_AVAILABLE=false
else
    CFN_LINT_AVAILABLE=true
fi

echo ""
echo "1. Validating YAML syntax..."
echo "-------------------------------------------"
# Try Python first, then Ruby as fallback
YAML_VALIDATOR=""
if python3 -c "import yaml" 2>/dev/null; then
    YAML_VALIDATOR="python"
elif which ruby >/dev/null 2>&1; then
    YAML_VALIDATOR="ruby"
else
    echo "  [WARN] No YAML validator available (install pyyaml or ruby)"
    YAML_VALIDATOR="none"
fi

for template in "$TEMPLATES_DIR"/*.yaml; do
    filename=$(basename "$template")
    case "$YAML_VALIDATOR" in
        python)
            if python3 -c "import yaml; yaml.safe_load(open('$template'))" 2>/dev/null; then
                echo "  [OK] $filename"
            else
                echo "  [FAIL] $filename - Invalid YAML syntax"
                exit 1
            fi
            ;;
        ruby)
            if ruby -ryaml -e "YAML.load_file('$template')" 2>/dev/null; then
                echo "  [OK] $filename"
            else
                echo "  [FAIL] $filename - Invalid YAML syntax"
                exit 1
            fi
            ;;
        none)
            echo "  [SKIP] $filename"
            ;;
    esac
done

echo ""
echo "2. Checking required Marketplace parameters..."
echo "-------------------------------------------"
MASTER_TEMPLATE="$TEMPLATES_DIR/midaz-complete.yaml"
required_params=("MPS3BucketName" "MPS3BucketRegion" "MPS3KeyPrefix")
for param in "${required_params[@]}"; do
    if grep -q "$param:" "$MASTER_TEMPLATE"; then
        echo "  [OK] $param found"
    else
        echo "  [FAIL] $param not found in master template"
        exit 1
    fi
done

echo ""
echo "3. Checking TemplateURL format..."
echo "-------------------------------------------"
if grep -q "TemplateURL: \./\|TemplateURL: \"\./" "$MASTER_TEMPLATE"; then
    echo "  [FAIL] Found relative TemplateURL paths. Use S3 URLs for Marketplace."
    exit 1
else
    echo "  [OK] All TemplateURLs use S3 format"
fi

echo ""
echo "4. Checking for hardcoded credentials..."
echo "-------------------------------------------"
for template in "$TEMPLATES_DIR"/*.yaml; do
    filename=$(basename "$template")
    # Check for common credential patterns (excluding legitimate references)
    if grep -iE "(password|secret|key).*=.*['\"]" "$template" | grep -v "SecretString" | grep -v "SecretId" | grep -v "GenerateSecretString" | grep -v "secretsmanager" | grep -v "KmsKey" | grep -v "KeyArn" | grep -q .; then
        echo "  [WARN] $filename - Possible hardcoded credential found"
    else
        echo "  [OK] $filename"
    fi
done

echo ""
echo "5. Checking sensitive parameters have NoEcho..."
echo "-------------------------------------------"
sensitive_params=("MasterUsername" "AdminUsername")
for param in "${sensitive_params[@]}"; do
    count=$(grep -A5 "$param:" "$MASTER_TEMPLATE" | grep -c "NoEcho: true" || true)
    if [ "$count" -gt 0 ]; then
        echo "  [OK] $param has NoEcho"
    else
        echo "  [WARN] $param may need NoEcho property"
    fi
done

if [ "$CFN_LINT_AVAILABLE" = true ]; then
    echo ""
    echo "6. Running cfn-lint..."
    echo "-------------------------------------------"
    cd "$PROJECT_DIR"
    cfn-lint templates/*.yaml || true
fi

echo ""
echo "=========================================="
echo "Validation Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Create architecture diagram (1100x700 pixels)"
echo "  2. Upload templates to S3 bucket"
echo "  3. Submit to AWS Marketplace"
