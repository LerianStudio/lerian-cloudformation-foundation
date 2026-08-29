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
  caught in the pull request instead of by a stack that hangs until it times out,
  and runs `scripts/check-agent-templates.py`, which asserts what the agent handler
  actually does: the enrollment token stays out of the logs, a supplied digest
  pins the chart, a token full of YAML metacharacters cannot corrupt the values
  document, moving the agent to another namespace replaces the release instead of
  duplicating it, and a delete never leaves a stack in `DELETE_FAILED`. The same
  script asserts that the Foundation's `Rules` block watches every agent
  parameter, so a future parameter cannot be added outside the guard.
- The Foundation rejects a half-filled agent parameter set at the `CreateStack`
  call, through a template `Rules` section. Supplying a control-plane URL and a
  token but no chart version used to build the VPC and the cluster first - about
  twenty minutes - and only then fail and roll all of it back. Supplying only the
  optional chart digest is rejected the same way, instead of quietly producing a
  cluster with no agent.
- `MarketplaceAMI` on `foundation.yaml`. The listing is an `AmiProduct` entity,
  so each delivery option must bind its AMI to a parameter of the launched
  template; without the parameter the `AddDeliveryOptions` changeset is rejected.
  The cluster runs EKS-managed ARM64 node AMIs and never launches this one.
- `scripts/check-docs-links.py`, run by CI and by `scripts/validate.sh`: every
  https template URL the documentation hands a customer is resolved back to the
  file the release workflow publishes at that key. A launch button pointing at a
  deleted template, or at a mistyped bucket, now fails the pull request - both
  defects this release had to fix by hand.
- A Getting Started section in the README covering the whole journey: enrollment
  token from the console, Foundation stack, product infrastructure stack, then
  the product installed from the console by the agent.

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
- `examples/` - its parameter tables documented the removed application layer
  (`DeployMidazHelm`, `MidazHelmRepository`, `MidazChartVersion`) and every one of
  its deployment examples launched `midaz-complete.yaml` or
  `midaz-infrastructure.yaml`, template paths this repository has not had for some
  time. Parameter documentation lives in each template's own `Description`, which
  CI checks is present and the CloudFormation console renders per field.

> **Post-merge, not delivered by this release:** the release workflow publishes
> with `aws s3 sync` without `--delete`, so `releases/latest/products/midaz/`
> keeps serving `application.yaml`, `helm.yaml` and `full-stack.yaml` after this
> change merges - and that is exactly where the current Marketplace listing and
> every previously shared quick-create link point. Removing those three objects
> needs to be sequenced with the Marketplace changeset, otherwise the live
> listing 404s before the new delivery options take effect.

### Fixed

- `NodeInstanceType` no longer offers `c6i.*` x86 instance types. The node group
  is created with `AmiType: AL2023_ARM_64_STANDARD`, so an x86 choice produced
  nodes that never joined the cluster.
- `MPS3BucketName` now defaults to `lerian-cloudformation-templates`, the bucket
  releases are actually published to. The previous default named a bucket that
  does not exist, so every nested stack 404'd on a default deployment.
- The quick-launch button on each GitHub release now prefills `MPS3KeyPrefix`
  with that release's prefix. It pinned only the top-level template, so an older
  release's button launched a pinned Foundation that pulled its nested templates
  from `releases/latest/`.
- The Marketplace listing's delivery options are rewritten to the one path that
  works. Two of the three published options - Full Stack and Application -
  launched templates this repository no longer publishes, so a customer following
  the listing reached a stack that could not be created. The draft changesets in
  `docs/marketplace-changesets.md` now add a single `Lerian Foundation` option
  and restrict the three superseded ones, in that order: the Catalog API refuses
  to restrict the last unrestricted delivery option, so restricting first would
  have failed. The runbook also sequences the deletion of the retired midaz
  objects from the release bucket after the listing stops referencing them,
  rather than before.
- Documentation links no longer name files that do not exist: the README's
  cost-estimation and security links, and the cost-estimation link in every
  GitHub release's notes, pointed at documents this repository has never had.
- The example control plane URL in the agent and Foundation parameter
  descriptions is `https://api.lerian.studio`, the address the CLI documents.
  The previous example named a host that does not resolve.

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
