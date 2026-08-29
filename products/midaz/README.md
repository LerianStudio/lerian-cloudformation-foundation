# Midaz on AWS

[Midaz](https://github.com/LerianStudio/midaz) is an open-source ledger platform. This guide covers the AWS data services Midaz runs on, deployed with CloudFormation.

**Infrastructure components:** RDS PostgreSQL, DocumentDB, ElastiCache (Valkey/Redis), AmazonMQ (RabbitMQ)

## How Midaz gets deployed

```
┌────────────────────────┐   ┌──────────────────────┐   ┌────────────────────┐
│ foundation.yaml        │──▶│ infrastructure.yaml  │──▶│ Lerian console     │
│ VPC + EKS + agent      │   │ RDS, DocumentDB      │   │ agent installs     │
│ (agent enrolls with    │   │ ElastiCache          │   │ Midaz in-cluster   │
│  the control plane)    │   │ AmazonMQ             │   │                    │
└────────────────────────┘   └──────────────────────┘   └────────────────────┘
```

CloudFormation stops at the data services. Midaz itself is installed by the
Lerian control plane through the agent running in the cluster, so upgrades,
rollbacks, and values changes happen in the console rather than as stack
updates. Nothing in this repository installs a product chart.

To attach to a VPC and EKS cluster you already run, skip the foundation stack
and pass the `Existing*` parameters (`ExistingVpcId`, `ExistingClusterName`) to
`infrastructure.yaml`.

## Quick Start — One-Click Deploy

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Foundation** | Shared VPC, EKS, and the Lerian agent | [![Launch][img]][foundation-sa-east-1] |
| **Infrastructure** | RDS, DocumentDB, ElastiCache, AmazonMQ (auto-imports from Foundation) | [![Launch][img]][midaz-infra-sa-east-1] |

[foundation-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=sa-east-1a&param_AvailabilityZone2=sa-east-1b&param_AvailabilityZone3=sa-east-1c
[midaz-infra-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

> **Required:** You must provide `RDSMasterUsername`, `DocumentDBMasterUsername`, and `AmazonMQAdminUsername` in the console.

<details>
<summary>Other Regions</summary>

**Infrastructure**

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][midaz-infra-us-east-1] |
| US West (Oregon) | [![Launch][img]][midaz-infra-us-west-2] |
| Europe (Ireland) | [![Launch][img]][midaz-infra-eu-west-1] |

[midaz-infra-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-infra-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/
[midaz-infra-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/midaz/infrastructure.yaml&stackName=midaz-infra&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/

The Foundation stack's launch links for other regions are in the
[main README](../../README.md).

</details>

## CLI Deploy

**Step 1 — Foundation** (shared VPC, EKS, and the agent). `EnrollmentToken` and
`ControlPlaneURL` come from the Lerian console; `AgentChartVersion` is the agent
chart version you intend to run. Omit all three to create the cluster without an
agent — nothing will be able to install products into it until you add one.

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
    ParameterKey=ControlPlaneURL,ParameterValue=https://cp.lerian.studio \
    ParameterKey=EnrollmentToken,ParameterValue=<token-from-the-console> \
    ParameterKey=AgentChartVersion,ParameterValue=<agent-chart-version> \
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

**Step 3 — Midaz.** Open the Lerian console, select this cluster's agent, and
create a Midaz release pointing at the `midaz-infra` stack. Ingress, replica
counts, and chart version are release settings in the console, not stack
parameters.

> **Tip:** You can deploy multiple product infrastructure stacks (e.g., Midaz + Tracer) on the same Foundation.

## Templates

| Template | Description |
|----------|-------------|
| `infrastructure.yaml` | Databases only — RDS, DocumentDB, ElastiCache, AmazonMQ (auto-imports from Foundation) |

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ProjectName` | `midaz` | Resource naming prefix |
| `EnvironmentName` | `production` | Environment tag |
| `FoundationStackName` | `lerian-foundation` | Foundation stack to import VPC/EKS from |
| `RDSInstanceClass` | `db.t3.medium` | Database instance |

See [examples/aws/README.md](../../examples/aws/README.md) for all parameters.

## Architecture

See [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) for full architecture details.

---

[Back to main README](../../README.md)
