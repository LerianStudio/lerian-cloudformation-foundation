# Midaz CloudFormation Foundation

Production-ready AWS CloudFormation templates for deploying the complete Midaz ledger infrastructure.

[![CI](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/ci.yml/badge.svg)](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/ci.yml)
[![Release](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/release.yml/badge.svg)](https://github.com/LerianStudio/midaz-cloudformation-foundation/actions/workflows/release.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## What's Included

- **VPC** with public, private, and database subnets (3 AZs)
- **Amazon EKS** with managed node groups
- **RDS PostgreSQL** with Multi-AZ support
- **DocumentDB** (MongoDB-compatible)
- **ElastiCache** (Valkey/Redis)
- **AmazonMQ** (RabbitMQ)
- **Route53**, **ALB Controller**, and **ExternalDNS**

## Quick Start

### One-Click Deploy

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)][launch-sa-east-1]

[launch-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://midaz-cloudformation-foundation.s3.sa-east-1.amazonaws.com/releases/latest/midaz-complete.yaml&stackName=midaz&param_MPS3BucketName=midaz-cloudformation-foundation&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=sa-east-1a&param_AvailabilityZone2=sa-east-1b&param_AvailabilityZone3=sa-east-1c

<details>
<summary>Other Regions</summary>

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][us-east-1] |
| US West (Oregon) | [![Launch][img]][us-west-2] |
| Europe (Ireland) | [![Launch][img]][eu-west-1] |

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
[us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://midaz-cloudformation-foundation.s3.sa-east-1.amazonaws.com/releases/latest/midaz-complete.yaml&stackName=midaz&param_MPS3BucketName=midaz-cloudformation-foundation&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-east-1a&param_AvailabilityZone2=us-east-1b&param_AvailabilityZone3=us-east-1c
[us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://midaz-cloudformation-foundation.s3.sa-east-1.amazonaws.com/releases/latest/midaz-complete.yaml&stackName=midaz&param_MPS3BucketName=midaz-cloudformation-foundation&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-west-2a&param_AvailabilityZone2=us-west-2b&param_AvailabilityZone3=us-west-2c
[eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://midaz-cloudformation-foundation.s3.sa-east-1.amazonaws.com/releases/latest/midaz-complete.yaml&stackName=midaz&param_MPS3BucketName=midaz-cloudformation-foundation&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=eu-west-1a&param_AvailabilityZone2=eu-west-1b&param_AvailabilityZone3=eu-west-1c

</details>

> **Required:** You must provide `RDSMasterUsername`, `DocumentDBMasterUsername`, and `AmazonMQAdminUsername` in the console.

### CLI Deploy

```bash
aws cloudformation create-stack \
  --stack-name midaz \
  --template-url https://midaz-cloudformation-foundation.s3.sa-east-1.amazonaws.com/releases/latest/midaz-complete.yaml \
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
| `midaz-complete.yaml` | Full stack (infrastructure + application) |
| `midaz-infrastructure.yaml` | Infrastructure only |
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
| `KubernetesVersion` | `1.31` | EKS version |
| `NodeInstanceType` | `m7g.large` | EC2 instance type |
| `RDSInstanceClass` | `db.r6g.large` | Database instance |

See [examples/aws/README.md](examples/aws/README.md) for all parameters.

## Cost Estimate

| Size | Monthly Cost |
|------|--------------|
| Development | ~$970 |
| Production | ~$1,220 |
| Enterprise | ~$2,450 |

See [docs/COST_ESTIMATION.md](docs/COST_ESTIMATION.md) for breakdown.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Security](SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache License 2.0 - see [LICENSE](LICENSE)

---

Built by [Lerian Studio](https://lerian.studio)
