# Midaz on AWS

[Midaz](https://github.com/LerianStudio/midaz) is an open-source ledger platform. This guide covers deploying Midaz on AWS using CloudFormation.

**Infrastructure components:** RDS PostgreSQL, DocumentDB, ElastiCache (Valkey/Redis), AmazonMQ (RabbitMQ)

## Deployment Options

```
Option 1: Full Stack (single deploy, standalone)
┌─────────────────────────────────────────────────────────────┐
│ full-stack.yaml                                             │
│ VPC + EKS + RDS + DocumentDB + ElastiCache + AmazonMQ + App │
└─────────────────────────────────────────────────────────────┘

Option 2: Modular (Foundation → Infrastructure → Application)
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│ foundation   │────▶│ infrastructure   │────▶│ application  │
│ VPC + EKS    │     │ RDS, DocumentDB  │     │ Helm deploy  │
│              │     │ ElastiCache      │     │              │
│              │     │ AmazonMQ         │     │              │
└──────────────┘     └──────────────────┘     └──────────────┘

Option 3: Existing Cluster (attach to existing VPC/EKS)
  Use Existing* parameters to skip Foundation and point to your own infra
```

1. **Full Stack** — Single deploy, standalone. Best for quick starts and single-product environments.
2. **Modular** — Foundation + Infrastructure + Application as separate stacks. Best when running multiple products on shared infrastructure.
3. **Existing Cluster** — Skip Foundation entirely and attach to your own VPC/EKS using `Existing*` parameters.

## Quick Start — One-Click Deploy

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Full Stack** | VPC, EKS, databases, and application (standalone) | [![Launch][img]][midaz-full-sa-east-1] |
| **Infrastructure** | RDS, DocumentDB, ElastiCache, AmazonMQ (auto-imports from Foundation) | [![Launch][img]][midaz-infra-sa-east-1] |
| **Application** | Helm charts (requires Infrastructure) | [![Launch][img]][midaz-app-sa-east-1] |

[midaz-full-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=sa-east-1a&param_AvailabilityZone2=sa-east-1b&param_AvailabilityZone3=sa-east-1c
[midaz-infra-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-app-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

> **Required:** You must provide `RDSMasterUsername`, `DocumentDBMasterUsername`, and `AmazonMQAdminUsername` in the console.

<details>
<summary>Other Regions</summary>

**Full Stack**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][midaz-full-us-east-1] |
| US West (Oregon) | [![Launch][img]][midaz-full-us-west-2] |
| Europe (Ireland) | [![Launch][img]][midaz-full-eu-west-1] |

[midaz-full-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-east-1a&param_AvailabilityZone2=us-east-1b&param_AvailabilityZone3=us-east-1c
[midaz-full-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-west-2a&param_AvailabilityZone2=us-west-2b&param_AvailabilityZone3=us-west-2c
[midaz-full-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/full-stack.yaml&stackName=midaz&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=eu-west-1a&param_AvailabilityZone2=eu-west-1b&param_AvailabilityZone3=eu-west-1c

**Infrastructure**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][midaz-infra-us-east-1] |
| US West (Oregon) | [![Launch][img]][midaz-infra-us-west-2] |
| Europe (Ireland) | [![Launch][img]][midaz-infra-eu-west-1] |

[midaz-infra-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-infra-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-infra-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

**Application**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][midaz-app-us-east-1] |
| US West (Oregon) | [![Launch][img]][midaz-app-us-west-2] |
| Europe (Ireland) | [![Launch][img]][midaz-app-eu-west-1] |

[midaz-app-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-app-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-app-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/application.yaml&stackName=midaz-app&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

</details>

## CLI Deploy

### Option 1: Full Stack (standalone, single deploy)

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

### Option 2: Modular (Foundation + Infrastructure + Application)

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

| Template | Description |
|----------|-------------|
| `full-stack.yaml` | Full stack — standalone VPC, EKS, databases, and application |
| `infrastructure.yaml` | Databases only — RDS, DocumentDB, ElastiCache, AmazonMQ (auto-imports from Foundation) |
| `application.yaml` | Application only — Helm charts (requires Infrastructure) |
| `helm.yaml` | Helm deployment (internal) |

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ProjectName` | `midaz` | Resource naming prefix |
| `EnvironmentName` | `production` | Environment tag |
| `FoundationStackName` | `lerian-foundation` | Foundation stack to import VPC/EKS from (infrastructure stack) |
| `KubernetesVersion` | `1.35` | EKS version (foundation/full-stack) |
| `NodeInstanceType` | `c7g.large` | EC2 instance type (foundation/full-stack) |
| `RDSInstanceClass` | `db.t3.medium` | Database instance |
| `EnableIngress` | `false` | Enable ALB ingress |
| `DomainName` | — | Domain for Route53 + ALB |
| `IngressHostname` | — | Hostname for the ingress endpoint |

See [examples/aws/README.md](../../examples/aws/README.md) for all parameters.

## Architecture

See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) for full architecture details.

---

[Back to main README](../../README.md)
