#!/bin/bash
# =============================================================================
# Show Current Template Versions
# Displays the current versions of all templates and bundle releases
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VERSIONS_FILE="$PROJECT_DIR/template-versions.json"

echo "=========================================="
echo "Midaz CloudFormation Versions"
echo "=========================================="
echo ""

# Show individual template versions
echo "📦 Individual Template Versions"
echo "--------------------------------"

if [ -f "$VERSIONS_FILE" ]; then
    python3 << 'EOF'
import json

with open('template-versions.json', 'r') as f:
    data = json.load(f)

# Core templates
templates = data.get('templates', {})
if templates:
    print("  Core templates:")
    max_len = max(len(t) for t in templates.keys())
    for template, version in sorted(templates.items()):
        tag = "(not released)" if version == "0.0.0" else f"{template}-v{version}"
        print(f"    {template:<{max_len+2}} {version:<10} {tag}")

# Product templates
products = data.get('products', {})
for product, ptemplates in sorted(products.items()):
    print(f"\n  Product: {product}")
    if ptemplates:
        max_len = max(len(t) for t in ptemplates.keys())
        for template, version in sorted(ptemplates.items()):
            tag = "(not released)" if version == "0.0.0" else f"{product}-{template}-v{version}"
            print(f"    {template:<{max_len+2}} {version:<10} {tag}")
EOF
else
    echo "  (no template-versions.json found)"
fi

echo ""

# Show bundle releases from git tags
echo "🎁 Bundle Releases (Marketplace)"
echo "---------------------------------"

BUNDLE_TAGS=$(git tag -l "release-v*" --sort=-v:refname 2>/dev/null | head -5)

if [ -n "$BUNDLE_TAGS" ]; then
    for TAG in $BUNDLE_TAGS; do
        VERSION=$(echo "$TAG" | sed 's/release-v//')
        DATE=$(git log -1 --format=%ai "$TAG" 2>/dev/null | cut -d' ' -f1)
        echo "  v$VERSION  ($DATE)  MPS3KeyPrefix=releases/v$VERSION/"
    done
else
    echo "  (no bundle releases yet)"
fi

echo ""
echo "=========================================="
echo "Usage"
echo "=========================================="
echo ""
echo "🔹 For AWS Marketplace (recommended):"
echo "   Use bundle releases for stable, tested versions"
echo "   MPS3KeyPrefix=releases/v1.0.0/"
echo ""
echo "🔹 For Development/Testing:"
echo "   Override individual template versions"
echo "   VPCTemplateVersion=v1.2.0"
echo "   EKSTemplateVersion=v2.0.0"
echo ""
echo "🔹 To release new versions:"
echo "   1. Commit with conventional commits:"
echo "      feat(vpc): add feature  → minor bump"
echo "      fix(eks): fix bug       → patch bump"
echo "      feat!: breaking change  → major bump"
echo ""
echo "   2. Push to main → auto-release individual templates"
echo ""
echo "   3. Run 'Release Bundle' workflow → create Marketplace bundle"
echo ""
