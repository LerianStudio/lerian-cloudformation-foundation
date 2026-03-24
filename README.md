# Lerian CloudFormation Foundation

Production-ready AWS CloudFormation templates for deploying Lerian products infrastructure.

[![CI](https://github.com/LerianStudio/lerian-cloudformation-foundation/actions/workflows/ci.yml/badge.svg)](https://github.com/LerianStudio/lerian-cloudformation-foundation/actions/workflows/ci.yml)
[![Release](https://github.com/LerianStudio/lerian-cloudformation-foundation/actions/workflows/release.yml/badge.svg)](https://github.com/LerianStudio/lerian-cloudformation-foundation/actions/workflows/release.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## What's Included

- **VPC** with public, private, and database subnets (3 AZs)
- **Amazon EKS** with managed node groups
- **RDS PostgreSQL** with Multi-AZ support
- **DocumentDB** (MongoDB-compatible)
- **ElastiCache** (Valkey/Redis)
- **AmazonMQ** (RabbitMQ)
- **Route53**, **ALB Controller**, and **ExternalDNS**

## Deployment Options

There are two ways to deploy Midaz:

```
Option 1: Full Stack (single deploy, standalone)
┌─────────────────────────────────────────────────────────────┐
│ full-stack.yaml                                             │
│ VPC + EKS + RDS + DocumentDB + ElastiCache + AmazonMQ + App │
└─────────────────────────────────────────────────────────────┘

Option 2: Modular (multi-product, shared infrastructure)
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│ foundation   │────▶│ infrastructure   │────▶│ application  │
│ VPC + EKS    │     │ RDS, DocumentDB  │     │ Helm deploy  │
│ Route53      │     │ ElastiCache      │     │              │
│ ALB + DNS    │     │ AmazonMQ         │     │              │
└──────────────┘     └──────────────────┘     └──────────────┘
       │             ┌──────────────────┐     ┌──────────────┐
       └────────────▶│ tracer/infra     │────▶│ tracer/app   │
                     │ RDS              │     │ Helm deploy  │
                     └──────────────────┘     └──────────────┘
```

- **Full Stack**: Best for single-product deployments. One stack, one deploy.
- **Modular**: Best when running multiple products (Midaz + Tracer) on a shared VPC and EKS cluster. Deploy Foundation once, then add product stacks independently.

## Quick Start

### One-Click Deploy

#### Foundation (Multi-Product)

Use the Foundation stack when deploying **more than one product** (e.g., Midaz + Tracer). It always creates the shared VPC and EKS. Route53 and ALB Controller are created only when `DomainName` is set, and ExternalDNS only when `DomainName` is set and `EnableExternalDNS=true`. Product infrastructure stacks auto-import Foundation outputs via `FoundationStackName` parameter.

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Foundation** | Shared VPC and EKS, with optional Route53 / ALB Controller / ExternalDNS | [![Launch][img]][foundation-sa-east-1] |

[foundation-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=sa-east-1a&param_AvailabilityZone2=sa-east-1b&param_AvailabilityZone3=sa-east-1c

#### Midaz

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Full Stack** | VPC, EKS, databases, and application (standalone) | [![Launch][img]][midaz-full-sa-east-1] |
| **Infrastructure** | RDS, DocumentDB, ElastiCache, AmazonMQ (auto-imports from Foundation) | [![Launch][img]][midaz-infra-sa-east-1] |
| **Application** | Helm charts (requires Infrastructure) | [![Launch][img]][midaz-app-sa-east-1] |

[midaz-full-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=sa-east-1a&param_AvailabilityZone2=sa-east-1b&param_AvailabilityZone3=sa-east-1c
[midaz-infra-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-app-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

#### Tracer

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Infrastructure** | VPC, EKS, RDS | [![Launch][img]][tracer-infra-sa-east-1] |

[tracer-infra-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/tracer/infrastructure.yaml&stackName=tracer-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=sa-east-1a&param_AvailabilityZone2=sa-east-1b&param_AvailabilityZone3=sa-east-1c

<details>
<summary>Other Regions</summary>

**Foundation**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][foundation-us-east-1] |
| US West (Oregon) | [![Launch][img]][foundation-us-west-2] |
| Europe (Ireland) | [![Launch][img]][foundation-eu-west-1] |

[foundation-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-east-1a&param_AvailabilityZone2=us-east-1b&param_AvailabilityZone3=us-east-1c
[foundation-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-west-2a&param_AvailabilityZone2=us-west-2b&param_AvailabilityZone3=us-west-2c
[foundation-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=eu-west-1a&param_AvailabilityZone2=eu-west-1b&param_AvailabilityZone3=eu-west-1c

**Midaz Full Stack**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][midaz-full-us-east-1] |
| US West (Oregon) | [![Launch][img]][midaz-full-us-west-2] |
| Europe (Ireland) | [![Launch][img]][midaz-full-eu-west-1] |

[midaz-full-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-east-1a&param_AvailabilityZone2=us-east-1b&param_AvailabilityZone3=us-east-1c
[midaz-full-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-west-2a&param_AvailabilityZone2=us-west-2b&param_AvailabilityZone3=us-west-2c
[midaz-full-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=eu-west-1a&param_AvailabilityZone2=eu-west-1b&param_AvailabilityZone3=eu-west-1c

**Midaz Infrastructure**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][midaz-infra-us-east-1] |
| US West (Oregon) | [![Launch][img]][midaz-infra-us-west-2] |
| Europe (Ireland) | [![Launch][img]][midaz-infra-eu-west-1] |

[midaz-infra-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-infra-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-infra-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

**Midaz Application**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][midaz-app-us-east-1] |
| US West (Oregon) | [![Launch][img]][midaz-app-us-west-2] |
| Europe (Ireland) | [![Launch][img]][midaz-app-eu-west-1] |

[midaz-app-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-app-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-app-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

**Tracer Infrastructure**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][tracer-infra-us-east-1] |
| US West (Oregon) | [![Launch][img]][tracer-infra-us-west-2] |
| Europe (Ireland) | [![Launch][img]][tracer-infra-eu-west-1] |

[tracer-infra-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/tracer/infrastructure.yaml&stackName=tracer-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-east-1a&param_AvailabilityZone2=us-east-1b&param_AvailabilityZone3=us-east-1c
[tracer-infra-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/tracer/infrastructure.yaml&stackName=tracer-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-west-2a&param_AvailabilityZone2=us-west-2b&param_AvailabilityZone3=us-west-2c
[tracer-infra-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/tracer/infrastructure.yaml&stackName=tracer-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=eu-west-1a&param_AvailabilityZone2=eu-west-1b&param_AvailabilityZone3=eu-west-1c

</details>

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

> **Required:** You must provide `RDSMasterUsername`, `DocumentDBMasterUsername`, and `AmazonMQAdminUsername` in the console.

### CLI Deploy

#### Option 1: Full Stack (standalone, single deploy)

Deploys everything (VPC, EKS, databases, and application) in one stack:

```bash
aws cloudformation create-stack \
  --stack-name midaz \
  --template-url https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml \
  --parameters \
    ParameterKey=AvailabilityZone1,ParameterValue=sa-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=sa-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=sa-east-1c \
    ParameterKey=RDSMasterUsername,ParameterValue=postgres \
    ParameterKey=DocumentDBMasterUsername,ParameterValue=docdbadmin \
    ParameterKey=AmazonMQAdminUsername,ParameterValue=mqadmin \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --region sa-east-1
```

#### Option 2: Modular (Foundation + Infrastructure + Application)

Use this when deploying **multiple products** on shared infrastructure, or when you want independent lifecycle management for each layer.

**Step 1 — Foundation** (shared VPC + EKS):

```bash
aws cloudformation create-stack \
  --stack-name lerian-foundation \
  --template-url https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml \
  --parameters \
    ParameterKey=MPS3BucketName,ParameterValue=lerian-cloudformation-templates \
    ParameterKey=MPS3BucketRegion,ParameterValue=sa-east-1 \
    ParameterKey=MPS3KeyPrefix,ParameterValue=releases/latest/ \
    ParameterKey=AvailabilityZone1,ParameterValue=sa-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=sa-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=sa-east-1c \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --region sa-east-1
```

**Step 2 — Product Infrastructure** (databases, auto-imports from Foundation):

```bash
aws cloudformation create-stack \
  --stack-name midaz-infra \
  --template-url https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml \
  --parameters \
    ParameterKey=MPS3BucketName,ParameterValue=lerian-cloudformation-templates \
    ParameterKey=MPS3BucketRegion,ParameterValue=sa-east-1 \
    ParameterKey=MPS3KeyPrefix,ParameterValue=releases/latest/ \
    ParameterKey=FoundationStackName,ParameterValue=lerian-foundation \
    ParameterKey=RDSMasterUsername,ParameterValue=postgres \
    ParameterKey=DocumentDBMasterUsername,ParameterValue=docdbadmin \
    ParameterKey=AmazonMQAdminUsername,ParameterValue=mqadmin \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --region sa-east-1
```

> VPC, subnets, EKS cluster, and OIDC are automatically imported from the Foundation stack via `Fn::ImportValue`. To override any value, use the `Existing*` parameters (e.g., `ExistingVpcId`, `ExistingClusterName`).

**Step 3 — Application** (Helm deploy on existing infrastructure):

```bash
aws cloudformation create-stack \
  --stack-name midaz-app \
  --template-url https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml \
  --parameters \
    ParameterKey=InfrastructureStackName,ParameterValue=midaz-infra \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --region sa-east-1
```

> **Tip:** You can deploy multiple product infrastructure stacks (e.g., Midaz + Tracer) on the same Foundation.

### With Ingress

Add these parameters to enable external access:

```bash
    ParameterKey=EnableIngress,ParameterValue=true \
    ParameterKey=DomainName,ParameterValue=example.com \
    ParameterKey=IngressHostname,ParameterValue=ledger.example.com
```

## Templates

### Products

| Product | Template | Description |
|---------|----------|-------------|
| **Midaz** | `products/midaz/full-stack.yaml` | Full stack — standalone VPC, EKS, databases, and application |
| | `products/midaz/infrastructure.yaml` | Databases only — RDS, DocumentDB, ElastiCache, AmazonMQ (auto-imports from Foundation) |
| | `products/midaz/application.yaml` | Application only — Helm charts (requires Infrastructure) |
| | `products/midaz/helm.yaml` | Helm deployment (internal) |
| **Tracer** | `products/tracer/infrastructure.yaml` | Infrastructure (VPC, EKS, RDS) |

### Shared

| Template | Description |
|----------|-------------|
| `foundation.yaml` | Shared VPC and EKS, with optional Route53 / ALB Controller / ExternalDNS (for multi-product deployments) |

### Foundation Templates

| Template | Description |
|----------|-------------|
| `vpc.yaml` | VPC with 3-tier subnets |
| `eks.yaml` | EKS cluster |
| `rds.yaml` | PostgreSQL database |
| `documentdb.yaml` | DocumentDB cluster |
| `elasticache.yaml` | Redis/Valkey cache |
| `amazonmq.yaml` | RabbitMQ broker |

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ProjectName` | `midaz` | Resource naming prefix |
| `EnvironmentName` | `production` | Environment tag |
| `FoundationStackName` | `lerian-foundation` | Foundation stack to import VPC/EKS from (infrastructure stack) |
| `KubernetesVersion` | `1.32` | EKS version (foundation/full-stack) |
| `NodeInstanceType` | `c7g.large` | EC2 instance type (foundation/full-stack) |
| `RDSInstanceClass` | `db.t3.medium` | Database instance |

See [examples/aws/README.md](examples/aws/README.md) for all parameters.

## Cost Estimate

| Size | Monthly Cost |
|------|--------------|
| Development | ~$970 |
| Production | ~$1,220 |
| Enterprise | ~$2,450 |

See [docs/COST_ESTIMATION.md](docs/COST_ESTIMATION.md) for breakdown.

## Documentation

- [Security](SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache License 2.0 - see [LICENSE](LICENSE)

---

Built by [Lerian Studio](https://lerian.studio)
