# Midaz CloudFormation Foundation

Production-ready AWS CloudFormation templates for deploying the complete Midaz infrastructure stack. Designed for AWS Marketplace distribution with enterprise-grade security, scalability, and observability.

[![CI](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/ci.yml/badge.svg)](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/ci.yml)
[![Release](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/release.yml/badge.svg)](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/release.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Deployment Options](#deployment-options)
- [Templates](#templates)
- [Parameters](#parameters)
- [Security](#security)
- [Cost Estimation](#cost-estimation)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

This repository contains modular, production-ready CloudFormation templates that deploy:

- **Network Infrastructure**: VPC with public, private, and database subnets
- **Container Orchestration**: Amazon EKS with managed node groups
- **Databases**: RDS PostgreSQL, DocumentDB, ElastiCache (Valkey/Redis)
- **Messaging**: AmazonMQ (RabbitMQ)
- **DNS & Load Balancing**: Route53, AWS Load Balancer Controller
- **Application Deployment**: Helm charts via Lambda custom resources

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         VPC (10.0.0.0/16)                             │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │  Public Subnet  │  │  Public Subnet  │  │  Public Subnet  │       │  │
│  │  │   10.0.1.0/24   │  │   10.0.2.0/24   │  │   10.0.3.0/24   │       │  │
│  │  │    (AZ-1)       │  │    (AZ-2)       │  │    (AZ-3)       │       │  │
│  │  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │       │  │
│  │  │  │    NAT    │  │  │  │    NAT    │  │  │  │    NAT    │  │       │  │
│  │  │  │  Gateway  │  │  │  │  Gateway  │  │  │  │  Gateway  │  │       │  │
│  │  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │       │  │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘       │  │
│  │           │                    │                    │                │  │
│  │  ┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐       │  │
│  │  │ Private Subnet  │  │ Private Subnet  │  │ Private Subnet  │       │  │
│  │  │  10.0.11.0/24   │  │  10.0.12.0/24   │  │  10.0.13.0/24   │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │  ┌───────────────────────────────────────────────────┐   │       │  │
│  │  │  │              Amazon EKS Cluster                   │   │       │  │
│  │  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐           │   │       │  │
│  │  │  │  │  Node   │  │  Node   │  │  Node   │           │   │       │  │
│  │  │  │  │ Group 1 │  │ Group 2 │  │ Group 3 │           │   │       │  │
│  │  │  │  └─────────┘  └─────────┘  └─────────┘           │   │       │  │
│  │  │  │                                                   │   │       │  │
│  │  │  │  ┌─────────────────────────────────────────────┐ │   │       │  │
│  │  │  │  │  Midaz Application (Helm)                   │ │   │       │  │
│  │  │  │  │  - Ledger Service                           │ │   │       │  │
│  │  │  │  │  - Transaction Service                      │ │   │       │  │
│  │  │  │  │  - Auth Service                             │ │   │       │  │
│  │  │  │  └─────────────────────────────────────────────┘ │   │       │  │
│  │  │  └───────────────────────────────────────────────────┘   │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ Database Subnet │  │ Database Subnet │  │ Database Subnet │       │  │
│  │  │  10.0.21.0/24   │  │  10.0.22.0/24   │  │  10.0.23.0/24   │       │  │
│  │  │                 │  │                 │  │                 │       │  │
│  │  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │       │  │
│  │  │  │    RDS    │  │  │  │ DocumentDB│  │  │  │ElastiCache│  │       │  │
│  │  │  │ PostgreSQL│  │  │  │  Cluster  │  │  │  │  Valkey   │  │       │  │
│  │  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │                    Supporting Services                          │ │  │
│  │  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │ │  │
│  │  │  │ AmazonMQ  │  │  Route53  │  │    ALB    │  │ External  │    │ │  │
│  │  │  │ RabbitMQ  │  │  Private  │  │Controller │  │    DNS    │    │ │  │
│  │  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

For detailed architecture documentation, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Features

### Infrastructure

- **High Availability**: Multi-AZ deployment across 3 availability zones
- **Scalability**: Auto-scaling EKS node groups with configurable min/max
- **Network Isolation**: 3-tier subnet architecture (public, private, database)
- **VPC Endpoints**: Private connectivity to AWS services (ECR, S3, STS, SSM)

### Security

- **Encryption at Rest**: Customer-managed KMS keys for all data stores
- **Encryption in Transit**: TLS/SSL for all service communications
- **Secrets Management**: AWS Secrets Manager for all credentials
- **IAM Best Practices**: Least-privilege IAM roles with IRSA for EKS
- **Network Security**: Security groups with minimal required access

### Observability

- **Logging**: CloudWatch Logs for EKS, RDS, DocumentDB
- **Monitoring**: CloudWatch metrics and Performance Insights
- **Auditing**: VPC Flow Logs, database audit logs

### Operations

- **Infrastructure as Code**: Fully automated deployments
- **Modular Design**: Deploy components independently or together
- **Version Control**: Independent versioning per template
- **AWS Marketplace Ready**: Compliant with Marketplace requirements

## Quick Start

### Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Permissions to create VPC, EKS, RDS, and related resources
- (Optional) Helm CLI for local chart management

### One-Click Deployment

Deploy the complete stack with a single click:

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?stackName=midaz&templateURL=https://midaz-cloudformation-templates.s3.us-east-1.amazonaws.com/releases/latest/midaz-complete.yaml)

### CLI Deployment

```bash
# Clone the repository
git clone https://github.com/LerianStudio/midaz-cloudformation-foundation.git
cd midaz-cloudformation-foundation

# Deploy complete stack
./scripts/deploy.sh \
  --stack-name midaz-production \
  --environment production \
  --region us-east-1

# Or deploy infrastructure only
./scripts/deploy-infra.sh \
  --stack-name midaz-infra \
  --environment production
```

### Minimal Parameters

```yaml
Parameters:
  ProjectName: midaz
  EnvironmentName: production
  VpcCIDR: 10.0.0.0/16
```

## Deployment Options

### Option 1: Complete Stack (Recommended)

Deploys all infrastructure and applications in one stack:

```bash
aws cloudformation create-stack \
  --stack-name midaz-complete \
  --template-url https://midaz-cloudformation-templates.s3.us-east-1.amazonaws.com/releases/latest/midaz-complete.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz \
    ParameterKey=EnvironmentName,ParameterValue=production \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND
```

### Option 2: Infrastructure Only

Deploy infrastructure without application:

```bash
aws cloudformation create-stack \
  --stack-name midaz-infrastructure \
  --template-url https://midaz-cloudformation-templates.s3.us-east-1.amazonaws.com/releases/latest/midaz-infrastructure.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND
```

### Option 3: Individual Templates

Deploy specific components:

```bash
# VPC only
aws cloudformation create-stack \
  --stack-name midaz-vpc \
  --template-url https://midaz-cloudformation-templates.s3.us-east-1.amazonaws.com/templates/vpc/latest/vpc.yaml \
  --parameters ParameterKey=ProjectName,ParameterValue=midaz

# EKS only (requires VPC)
aws cloudformation create-stack \
  --stack-name midaz-eks \
  --template-url https://midaz-cloudformation-templates.s3.us-east-1.amazonaws.com/templates/eks/latest/eks.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz \
    ParameterKey=VpcId,ParameterValue=vpc-xxx \
    ParameterKey=PrivateSubnet1Id,ParameterValue=subnet-xxx \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
```

## Templates

| Template | Description | Dependencies |
|----------|-------------|--------------|
| `vpc.yaml` | VPC with 3-tier subnets, NAT, VPC Endpoints | None |
| `eks.yaml` | EKS cluster with managed node groups | VPC |
| `rds.yaml` | PostgreSQL with Multi-AZ, encryption | VPC |
| `documentdb.yaml` | MongoDB-compatible cluster | VPC |
| `elasticache.yaml` | Valkey/Redis replication group | VPC |
| `amazonmq.yaml` | RabbitMQ broker | VPC |
| `route53.yaml` | Private hosted zone | VPC |
| `alb-controller.yaml` | AWS Load Balancer Controller | EKS |
| `external-dns.yaml` | External DNS for Route53 | EKS, Route53 |
| `midaz-helm.yaml` | Midaz application via Helm | EKS, Databases |
| `midaz-infrastructure.yaml` | All infrastructure components | None |
| `midaz-application.yaml` | Application wrapper | Infrastructure |
| `midaz-complete.yaml` | Complete deployment | None |

## Parameters

### Common Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ProjectName` | String | `midaz` | Project name for resource naming |
| `EnvironmentName` | String | `production` | Environment (dev/staging/production) |
| `VpcCIDR` | String | `10.0.0.0/16` | VPC CIDR block |

### EKS Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `KubernetesVersion` | String | `1.31` | Kubernetes version (1.30-1.32) |
| `NodeInstanceType` | String | `m7g.large` | EC2 instance type for nodes |
| `NodeGroupMinSize` | Number | `2` | Minimum nodes per AZ |
| `NodeGroupMaxSize` | Number | `10` | Maximum nodes per AZ |
| `NodeGroupDesiredSize` | Number | `3` | Desired nodes per AZ |

### Database Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `RDSInstanceClass` | String | `db.r6g.large` | RDS instance class |
| `RDSMultiAZ` | String | `true` | Enable Multi-AZ |
| `DocumentDBInstanceClass` | String | `db.r6g.large` | DocumentDB instance class |
| `ElastiCacheNodeType` | String | `cache.r6g.large` | ElastiCache node type |

For complete parameter reference, see [examples/aws/README.md](examples/aws/README.md).

## Security

### Encryption

All data is encrypted using customer-managed KMS keys:

- **RDS**: Storage and snapshots encrypted
- **DocumentDB**: Storage encrypted
- **ElastiCache**: At-rest and in-transit encryption
- **EKS**: Secrets encrypted in etcd
- **S3**: Template bucket uses AES256

### Network Security

- Databases only accessible from VPC CIDR
- No public IP addresses on database instances
- Security groups follow least-privilege principle
- VPC endpoints for private AWS API access

### Secrets Management

- Database credentials stored in AWS Secrets Manager
- Passwords auto-generated with secure patterns
- No hardcoded credentials in templates

### IAM

- IRSA (IAM Roles for Service Accounts) for EKS workloads
- Least-privilege IAM policies
- No wildcard permissions on sensitive actions

For detailed security documentation, see [SECURITY.md](SECURITY.md).

## Cost Estimation

Estimated monthly costs for different deployment sizes:

| Component | Development | Production | Enterprise |
|-----------|-------------|------------|------------|
| **EKS Cluster** | $73 | $73 | $73 |
| **EKS Nodes** (3x m7g.large) | ~$180 | ~$180 | ~$540 |
| **RDS** (db.r6g.large) | ~$175 | ~$350 (Multi-AZ) | ~$700 |
| **DocumentDB** (3 nodes) | ~$270 | ~$270 | ~$540 |
| **ElastiCache** (2 nodes) | ~$90 | ~$90 | ~$180 |
| **AmazonMQ** | ~$30 | ~$60 | ~$120 |
| **NAT Gateway** (3x) | ~$100 | ~$100 | ~$100 |
| **Data Transfer** | ~$50 | ~$100 | ~$200 |
| **Total Estimate** | **~$970/mo** | **~$1,220/mo** | **~$2,450/mo** |

For detailed cost breakdown, see [docs/COST_ESTIMATION.md](docs/COST_ESTIMATION.md).

## Troubleshooting

### Common Issues

**Stack creation fails with IAM permissions error:**
```bash
# Ensure you have the required capabilities
aws cloudformation create-stack ... \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND
```

**EKS nodes not joining cluster:**
```bash
# Check node group status
aws eks describe-nodegroup \
  --cluster-name midaz-eks \
  --nodegroup-name midaz-nodegroup
```

**Database connection timeout:**
```bash
# Verify security group allows traffic from VPC CIDR
aws ec2 describe-security-groups --group-ids sg-xxx
```

For comprehensive troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Scripts

| Script | Description |
|--------|-------------|
| `deploy.sh` | Main deployment orchestrator |
| `deploy-infra.sh` | Infrastructure-only deployment |
| `deploy-helm.sh` | Helm chart deployment |
| `validate.sh` | Template validation |
| `test-local.sh` | Local testing without AWS |
| `show-versions.sh` | Display current versions |

## Versioning

Each template is versioned independently using semantic versioning. Current versions are tracked in `template-versions.json`.

**Version Format:**
- Individual templates: `{template}-v{major}.{minor}.{patch}` (e.g., `vpc-v0.1.0`)
- Bundle releases: `release-v{major}.{minor}.{patch}` (e.g., `release-v0.1.0`)

**S3 Structure:**
```
s3://midaz-cloudformation-templates/
├── templates/{name}/v{version}/{name}.yaml
├── templates/{name}/latest/{name}.yaml
├── releases/v{version}/
└── releases/latest/
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Install dependencies
pip install cfn-lint pyyaml
npm install

# Validate templates
./scripts/validate.sh

# Run linting
cfn-lint templates/*.yaml
```

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(eks): add support for Kubernetes 1.32
fix(rds): correct security group rules
docs(readme): update deployment instructions
```

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/LerianStudio/midaz-cloudformation-foundation/issues)
- **Discussions**: [GitHub Discussions](https://github.com/LerianStudio/midaz-cloudformation-foundation/discussions)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

---

Built with care by [Lerian Studio](https://lerian.studio)
