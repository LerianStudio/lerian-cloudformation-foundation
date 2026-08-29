# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Agent Stack** (`agent.yaml`) - installs the `lerian-agent` Helm chart into the
  cluster and enrolls it with the Lerian control plane. Optional nested stack of
  the Foundation, created when `ControlPlaneURL` and `EnrollmentToken` are both
  supplied. The chart is pinned by version and, optionally, by OCI digest.
- CI now compiles the inline Lambda code of every template, so a syntax error is
  caught in the pull request instead of by a stack that hangs until it times out.

### Removed

- **BREAKING**: `products/midaz/application.yaml`, `products/midaz/helm.yaml`, and
  `products/midaz/full-stack.yaml`. The application layer is no longer deployed by
  CloudFormation: the Lerian control plane installs products through the cluster's
  agent. Existing stacks created from these templates keep running; they are simply
  no longer published, and Midaz upgrades move to the control plane.
- Deploy scripts that existed only to drive those templates: `deploy.sh`,
  `deploy-stack.sh`, `deploy-helm.sh`, `deploy-helm-stack.sh`.
- `MPS3ProductKeyPrefix` from `products/midaz/infrastructure.yaml` - it pointed at
  the removed `application.yaml`.

### Fixed

- `NodeInstanceType` no longer offers `c6i.*` x86 instance types. The node group
  is created with `AmiType: AL2023_ARM_64_STANDARD`, so an x86 choice produced
  nodes that never joined the cluster.
- `MPS3BucketName` now defaults to `lerian-cloudformation-templates`, the bucket
  releases are actually published to. The previous default named a bucket that
  does not exist, so every nested stack 404'd on a default deployment.

## [0.1.0] - 2026-02-02

### Added

#### Infrastructure Templates
- **VPC Stack** (`vpc.yaml`)
  - 3-tier subnet architecture (public, private, database)
  - NAT Gateway for private subnet internet access
  - VPC Endpoints for AWS services (ECR, S3, STS, SSM, CloudWatch)
  - Optional VPC Flow Logs for network auditing

- **EKS Stack** (`eks.yaml`)
  - EKS cluster with configurable Kubernetes version (1.30-1.32)
  - Managed node groups with ARM64 Graviton instances
  - OIDC provider for IAM Roles for Service Accounts (IRSA)
  - EKS add-ons: VPC CNI, CoreDNS, kube-proxy, EBS CSI driver
  - Cluster logging to CloudWatch

- **RDS Stack** (`rds.yaml`)
  - PostgreSQL 16.8 with configurable instance classes
  - Customer-managed KMS encryption
  - Configurable Multi-AZ, backup retention, deletion protection
  - Optional read replica
  - IAM database authentication
  - Performance Insights and Enhanced Monitoring

- **DocumentDB Stack** (`documentdb.yaml`)
  - MongoDB-compatible cluster
  - Customer-managed KMS encryption
  - Configurable backup retention and deletion protection
  - CloudWatch audit and profiler logs

- **ElastiCache Stack** (`elasticache.yaml`)
  - Valkey/Redis 7.2 replication group
  - Multi-AZ with automatic failover
  - Encryption in-transit and at-rest

- **AmazonMQ Stack** (`amazonmq.yaml`)
  - RabbitMQ 3.13 broker
  - Secrets Manager integration for credentials
  - CloudWatch logging

#### Kubernetes Add-ons
- **ALB Controller** (`alb-controller.yaml`)
  - AWS Load Balancer Controller via Helm
  - IRSA configuration

- **ExternalDNS** (`external-dns.yaml`)
  - Automatic Route53 DNS management
  - IRSA configuration

- **Route53** (`route53.yaml`)
  - Private hosted zone for internal DNS

#### Deployment Templates
- **midaz-complete.yaml** - One-click full deployment
- **midaz-infrastructure.yaml** - Infrastructure-only deployment
- **midaz-helm.yaml** - Helm chart deployment via Lambda
- **midaz-application.yaml** - Application wrapper

#### CI/CD
- GitHub Actions workflow for template validation
- Automated semantic versioning and S3 release
- cfn-lint and Checkov security scanning

#### Scripts
- `deploy.sh` - Main deployment orchestrator
- `deploy-infra.sh` - Infrastructure-only deployment
- `deploy-helm.sh` - Helm chart deployment
- `build-lambda-layer.sh` - Lambda layer builder
- `upload-templates.sh` - S3 upload utility
- `validate.sh` - Template validation

### Security
- All databases use customer-managed KMS keys
- Secrets stored in AWS Secrets Manager
- Security groups restrict access to VPC CIDR
- IAM roles follow least privilege principle
- Optional SSL/TLS for RDS connections

### Documentation
- Comprehensive README with architecture diagram
- AWS Marketplace checklist
- Parameter reference and examples
- Cost estimation guide

---

## Template Versioning

Each template is versioned independently. Current versions:

| Template | Version |
|----------|---------|
| vpc | 0.1.0 |
| eks | 0.1.0 |
| rds | 0.1.0 |
| documentdb | 0.1.0 |
| elasticache | 0.1.0 |
| amazonmq | 0.1.0 |
| route53 | 0.1.0 |
| alb-controller | 0.1.0 |
| external-dns | 0.1.0 |
| midaz-helm | 0.1.0 |
| midaz-infrastructure | 0.1.0 |
| midaz-application | 0.1.0 |
| midaz-complete | 0.1.0 |

---

[0.1.0]: https://github.com/LerianStudio/lerian-cloudformation-foundation/releases/tag/release-v0.1.0
