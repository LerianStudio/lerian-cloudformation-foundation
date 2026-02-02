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

# Try Ruby first (more reliable for CloudFormation), then Python
validate_yaml() {
    local file="$1"
    if command -v ruby &>/dev/null; then
        ruby -ryaml -e "YAML.load_file('$file')" 2>/dev/null
    elif python3 -c "import yaml" 2>/dev/null; then
        python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null
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

# Use Ruby for YAML parsing (more reliable)
ruby << 'RUBYEOF'
require 'yaml'

errors = []
warnings = []

Dir.glob('templates/*.yaml').sort.each do |filepath|
  name = File.basename(filepath)

  begin
    data = YAML.load_file(filepath)
  rescue => e
    errors << "#{name}: Invalid YAML - #{e.message}"
    next
  end

  # Check required sections
  errors << "#{name}: Missing AWSTemplateFormatVersion" unless data['AWSTemplateFormatVersion']
  warnings << "#{name}: Missing Description" unless data['Description']
  errors << "#{name}: Missing Resources section" unless data['Resources']

  puts "  ✓ #{name}"
end

if errors.any?
  puts "\n❌ Errors:"
  errors.each { |e| puts "  - #{e}" }
  exit 1
end

if warnings.any?
  puts "\n⚠️  Warnings (#{warnings.length}):"
  warnings.first(5).each { |w| puts "  - #{w}" }
  puts "  ... and #{warnings.length - 5} more" if warnings.length > 5
end

puts "\n✓ Structure validation passed"
RUBYEOF

echo ""

# =============================================================================
# Check Nested Stack References
# =============================================================================
echo "5. Checking nested stack references..."

ruby << 'RUBYEOF'
# Get all template names
templates = Dir.glob('templates/*.yaml').map { |f| File.basename(f, '.yaml') }.to_set

puts "   Found #{templates.size} templates"

# Check midaz-complete.yaml references
content = File.read('templates/midaz-complete.yaml')

# Find all template references in TemplateURL
refs = content.scan(/\$\{MPS3KeyPrefix\}([a-z-]+)\.yaml/).flatten.to_set

puts "   midaz-complete.yaml references: #{refs.size} templates"

missing = refs - templates
if missing.any?
  puts "\n   ❌ Missing templates: #{missing.to_a.join(', ')}"
  exit 1
else
  puts "   ✓ All referenced templates exist"
end
RUBYEOF

echo ""

# =============================================================================
# AWS CLI Validation (optional)
# =============================================================================
if [ "$HAS_AWSCLI" = true ]; then
    echo "6. AWS CloudFormation validate-template..."
    echo "   (Requires AWS credentials)"

    if aws sts get-caller-identity &>/dev/null; then
        for template in "$TEMPLATES_DIR"/midaz-complete.yaml "$TEMPLATES_DIR"/midaz-infrastructure.yaml "$TEMPLATES_DIR"/midaz-application.yaml; do
            if [ -f "$template" ]; then
                name=$(basename "$template")
                if aws cloudformation validate-template --template-body "file://$template" &>/dev/null; then
                    echo -e "  ${GREEN}✓${NC} $name"
                else
                    echo -e "  ${RED}✗${NC} $name"
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
echo "  # 2. Deploy complete stack"
echo "  aws cloudformation deploy \\"
echo "    --stack-name midaz-test \\"
echo "    --template-file templates/midaz-complete.yaml \\"
echo "    --parameter-overrides \\"
echo "      AvailabilityZone1=us-east-1a \\"
echo "      AvailabilityZone2=us-east-1b \\"
echo "      AvailabilityZone3=us-east-1c \\"
echo "      MPS3BucketName=your-bucket \\"
echo "      MPS3KeyPrefix=templates/ \\"
echo "    --capabilities CAPABILITY_NAMED_IAM"
echo ""
