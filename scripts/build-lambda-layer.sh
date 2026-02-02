#!/bin/bash
#
# Build Lambda Layer with kubectl and helm
# This layer is required for the Midaz Helm deployer Lambda function
#

set -e

KUBECTL_VERSION="1.32.0"
HELM_VERSION="3.16.4"
AWS_CLI_VERSION="2.22.0"

LAYER_DIR="lambda-layer"
OUTPUT_FILE="kubectl-helm-layer.zip"

echo "Building Lambda Layer with kubectl ${KUBECTL_VERSION} and helm ${HELM_VERSION}..."

# Clean up
rm -rf ${LAYER_DIR} ${OUTPUT_FILE}

# Create directory structure
mkdir -p ${LAYER_DIR}/bin
mkdir -p ${LAYER_DIR}/python

# Download kubectl (Linux x86_64)
echo "Downloading kubectl..."
curl -sLO "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
chmod +x kubectl
mv kubectl ${LAYER_DIR}/bin/

# Download helm (Linux x86_64)
echo "Downloading helm..."
curl -sLO "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz"
tar -xzf helm-v${HELM_VERSION}-linux-amd64.tar.gz
mv linux-amd64/helm ${LAYER_DIR}/bin/
rm -rf linux-amd64 helm-v${HELM_VERSION}-linux-amd64.tar.gz

# Download AWS CLI v2 (for eks update-kubeconfig)
echo "Downloading AWS CLI..."
curl -sL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install --install-dir ${LAYER_DIR}/aws-cli --bin-dir ${LAYER_DIR}/bin
rm -rf aws awscliv2.zip

# Create wrapper script to set up PATH
cat > ${LAYER_DIR}/bin/setup-path.sh << 'EOF'
#!/bin/bash
export PATH="/opt/bin:$PATH"
export HOME="/tmp"
export KUBECONFIG="/tmp/kubeconfig"
EOF

# Create zip file
echo "Creating layer zip..."
cd ${LAYER_DIR}
zip -r9 ../${OUTPUT_FILE} .
cd ..

# Clean up
rm -rf ${LAYER_DIR}

echo ""
echo "Layer created: ${OUTPUT_FILE}"
echo ""
echo "To upload to S3:"
echo "  aws s3 cp ${OUTPUT_FILE} s3://midaz-artifacts-\${AWS_REGION}/lambda-layers/"
echo ""
echo "Or to publish as a Lambda Layer directly:"
echo "  aws lambda publish-layer-version \\"
echo "    --layer-name kubectl-helm-layer \\"
echo "    --zip-file fileb://${OUTPUT_FILE} \\"
echo "    --compatible-runtimes python3.11 python3.12 \\"
echo "    --compatible-architectures x86_64"
