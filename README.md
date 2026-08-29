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

## Products

Each product has its own deployment guide under [`products/`](products/):

| Product | Deploy Guide |
|---------|-------------|
| Midaz | [products/midaz/](products/midaz/README.md) |
| Tracer | *Coming soon* |

## Architecture Overview

```
┌──────────────────────┐     ┌──────────────────┐
│ foundation           │────▶│ product/infra    │
│ VPC + EKS            │     │ Databases        │
│ Route53, ALB + DNS   │     │ Caches, Brokers  │
│ Lerian agent ────────┼──┐  └──────────────────┘
└──────────────────────┘  │  ┌──────────────────┐
                          │  │ product/infra    │
                          │  │ Databases        │
                          │  └──────────────────┘
                          │
                          ▼  outbound-only
                   ┌──────────────────────────┐
                   │ Lerian control plane     │
                   │ installs product charts  │
                   │ through the agent        │
                   └──────────────────────────┘
```

CloudFormation delivers a cluster with an enrolled agent, plus the data services
each product needs. Product applications are installed by the Lerian control
plane through that agent, from inside the cluster — this repository contains no
template that installs a product.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Foundation Stack

The Foundation stack creates the shared VPC and EKS cluster and enrolls the
Lerian agent in it. Route53 and ALB Controller are created only when
`DomainName` is set, and ExternalDNS only when `DomainName` is set and
`EnableExternalDNS=true`. The agent is installed only when `ControlPlaneURL` and
`EnrollmentToken` are both supplied — leave them empty for a cluster with no
control-plane connection.

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Foundation** | Shared VPC and EKS with the Lerian agent, plus optional Route53 / ALB Controller / ExternalDNS | [![Launch][img]][foundation-sa-east-1] |

[foundation-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=sa-east-1a&param_AvailabilityZone2=sa-east-1b&param_AvailabilityZone3=sa-east-1c

<details>
<summary>Other Regions</summary>

| Region | Launch |
|--------|--------|
| US East (N. Virginia) | [![Launch][img]][foundation-us-east-1] |
| US West (Oregon) | [![Launch][img]][foundation-us-west-2] |
| Europe (Ireland) | [![Launch][img]][foundation-eu-west-1] |

[foundation-us-east-1]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-east-1a&param_AvailabilityZone2=us-east-1b&param_AvailabilityZone3=us-east-1c
[foundation-us-west-2]: https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=us-west-2a&param_AvailabilityZone2=us-west-2b&param_AvailabilityZone3=us-west-2c
[foundation-eu-west-1]: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml&stackName=lerian-foundation&param_MPS3BucketName=lerian-cloudformation-templates&param_MPS3BucketRegion=sa-east-1&param_MPS3KeyPrefix=releases/latest/&param_AvailabilityZone1=eu-west-1a&param_AvailabilityZone2=eu-west-1b&param_AvailabilityZone3=eu-west-1c

</details>

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

## Cost Estimate

| Size | Monthly Cost |
|------|--------------|
| Development | ~$970 |
| Production | ~$1,220 |
| Enterprise | ~$2,450 |

See [docs/COST_ESTIMATION.md](docs/COST_ESTIMATION.md) for breakdown.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

## License

Apache License 2.0 - see [LICENSE](LICENSE)

---

Built by [Lerian Studio](https://lerian.studio)
