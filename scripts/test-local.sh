#!/bin/bash
# =============================================================================
# Test Templates Locally
# Validates templates without deploying to AWS
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$PROJECT_DIR/templates"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Midaz CloudFormation - Local Testing"
echo "=========================================="
echo ""

# Check for required tools
check_tool() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 installed"
        return 0
    else
        echo -e "  ${YELLOW}⚠${NC} $1 not installed"
        return 1
    fi
}

echo "1. Checking required tools..."
HAS_CFNLINT=false
HAS_AWSCLI=false
HAS_PYTHON=false

check_tool "cfn-lint" && HAS_CFNLINT=true
check_tool "aws" && HAS_AWSCLI=true
check_tool "python3" && HAS_PYTHON=true
echo ""

# =============================================================================
# YAML Syntax Validation
# =============================================================================
echo "2. Validating YAML syntax..."
YAML_ERRORS=0

validate_yaml() {
    local file="$1"
    if python3 -c "import yaml" 2>/dev/null; then
        python3 -c "
import sys, yaml
yaml.SafeLoader.add_multi_constructor('!', lambda loader, suffix, node: None)
yaml.safe_load(open(sys.argv[1]))
" "$file" 2>/dev/null
    else
        # Fallback: just check basic syntax
        head -1 "$file" | grep -q "AWSTemplateFormatVersion"
    fi
}

for template in "$TEMPLATES_DIR"/*.yaml; do
    name=$(basename "$template")
    if validate_yaml "$template"; then
        echo -e "  ${GREEN}✓${NC} $name"
    else
        echo -e "  ${RED}✗${NC} $name - Invalid YAML"
        YAML_ERRORS=$((YAML_ERRORS + 1))
    fi
done

if [ $YAML_ERRORS -gt 0 ]; then
    echo -e "\n${RED}❌ $YAML_ERRORS YAML errors found${NC}"
    exit 1
fi
echo -e "  ${GREEN}All YAML files valid${NC}"
echo ""

# =============================================================================
# CloudFormation Lint
# =============================================================================
if [ "$HAS_CFNLINT" = true ]; then
    echo "3. Running cfn-lint..."

    LINT_ERRORS=0
    for template in "$TEMPLATES_DIR"/*.yaml; do
        name=$(basename "$template")
        # Run cfn-lint and capture output
        if output=$(cfn-lint "$template" 2>&1); then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${YELLOW}⚠${NC} $name"
            echo "$output" | head -10 | sed 's/^/      /'
            LINT_ERRORS=$((LINT_ERRORS + 1))
        fi
    done

    if [ $LINT_ERRORS -gt 0 ]; then
        echo -e "\n${YELLOW}⚠ $LINT_ERRORS templates have warnings${NC}"
    else
        echo -e "  ${GREEN}All templates passed cfn-lint${NC}"
    fi
    echo ""
else
    echo "3. Skipping cfn-lint (not installed)"
    echo "   Install with: pip install cfn-lint"
    echo ""
fi

# =============================================================================
# CloudFormation Structure Validation
# =============================================================================
echo "4. Validating CloudFormation structure..."

python3 << 'PYEOF'
import glob
import pathlib
import yaml


class CFNLoader(yaml.SafeLoader):
    pass


CFNLoader.add_multi_constructor("!", lambda loader, suffix, node: None)
errors = []
warnings = []

for filepath in sorted(glob.glob("templates/*.yaml")):
    name = pathlib.Path(filepath).name
    try:
        with open(filepath) as source:
            data = yaml.load(source, Loader=CFNLoader)
    except Exception as exc:
        errors.append(f"{name}: Invalid YAML - {exc}")
        continue
    if "AWSTemplateFormatVersion" not in data:
        errors.append(f"{name}: Missing AWSTemplateFormatVersion")
    if "Description" not in data:
        warnings.append(f"{name}: Missing Description")
    if "Resources" not in data:
        errors.append(f"{name}: Missing Resources section")
    print(f"  ✓ {name}")

if errors:
    print("\n❌ Errors:")
    for error in errors:
        print(f"  - {error}")
    raise SystemExit(1)
if warnings:
    print(f"\n⚠️  Warnings ({len(warnings)}):")
    for warning in warnings[:5]:
        print(f"  - {warning}")
    if len(warnings) > 5:
        print(f"  ... and {len(warnings) - 5} more")
print("\n✓ Structure validation passed")
PYEOF

echo ""

# =============================================================================
# Check Nested Stack References
# =============================================================================
echo "5. Checking nested stack references..."

python3 << 'PYEOF'
import pathlib
import re

root = pathlib.Path(".")
core_templates = {path.stem for path in (root / "templates").glob("*.yaml")}
print(f"   Found {len(core_templates)} core templates")

content = (root / "templates/foundation.yaml").read_text()
refs = set(re.findall(r"\$\{MPS3KeyPrefix\}([a-z0-9-]+)\.yaml", content))
print(f"   foundation.yaml references: {len(refs)} templates")
missing = refs - core_templates
if missing:
    raise SystemExit(f"\n   ❌ foundation.yaml: Missing templates: {', '.join(sorted(missing))}")
print("   ✓ foundation.yaml: All referenced templates exist")

for infra_file in sorted((root / "products").glob("*/infrastructure.yaml")):
    product = infra_file.parent.name
    product_templates = {path.stem for path in infra_file.parent.glob("*.yaml")}
    all_templates = core_templates | product_templates
    pattern = (
        rf"\$\{{MPS3(?:Product)?KeyPrefix\}}"
        rf"(?:products/{re.escape(product)}/)?([a-z0-9-]+)\.yaml"
    )
    refs = set(re.findall(pattern, infra_file.read_text()))
    missing = refs - all_templates
    if missing:
        raise SystemExit(f"\n   ❌ {product}: Missing templates: {', '.join(sorted(missing))}")
    print(f"   ✓ {product}/infrastructure.yaml: {len(refs)} referenced templates exist")
PYEOF

echo ""

# =============================================================================
# AWS CLI Validation (optional)
# =============================================================================
if [ "$HAS_AWSCLI" = true ]; then
    echo "6. AWS CloudFormation validate-template..."
    echo "   (Requires AWS credentials)"

    if aws sts get-caller-identity &>/dev/null; then
        for template in templates/*.yaml products/*/infrastructure.yaml; do
            if [ -f "$template" ]; then
                if aws cloudformation validate-template --template-body "file://$template" &>/dev/null; then
                    echo -e "  ${GREEN}✓${NC} $template"
                else
                    echo -e "  ${RED}✗${NC} $template"
                fi
            fi
        done
    else
        echo "   Skipped - No AWS credentials configured"
    fi
    echo ""
else
    echo "6. Skipping AWS validation (aws cli not installed)"
    echo ""
fi

# =============================================================================
# Summary
# =============================================================================
echo "=========================================="
echo "Testing Complete!"
echo "=========================================="
echo ""
echo "Next steps to deploy:"
echo ""
echo "  # 1. Upload templates to S3 (or use local file://)"
echo "  aws s3 sync templates/ s3://your-bucket/templates/"
echo ""
echo "  # 2. Deploy the foundation stack (VPC + EKS + agent)"
echo "  aws cloudformation deploy \\"
echo "    --stack-name lerian-foundation \\"
echo "    --template-file templates/foundation.yaml \\"
echo "    --parameter-overrides \\"
echo "      AvailabilityZone1=us-east-1a \\"
echo "      AvailabilityZone2=us-east-1b \\"
echo "      AvailabilityZone3=us-east-1c \\"
echo "      MPS3BucketName=your-bucket \\"
echo "      MPS3KeyPrefix=templates/ \\"
echo "    --capabilities CAPABILITY_NAMED_IAM"
echo ""
