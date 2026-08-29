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

## Getting Started

Four steps; steps 2 and 3 are CloudFormation.

1. **Get an enrollment token.** Sign in to the Lerian console, create the
   environment for this cluster, and copy the token it issues. It is single-use
   and short-lived, so take it right before step 2. The console also gives you
   the control plane URL and the agent chart version to run.

2. **Launch the Foundation stack** — from the AWS Marketplace listing, or with
   the launch button below, or with `aws cloudformation create-stack`. Supply
   `ControlPlaneURL`, `EnrollmentToken` and `AgentChartVersion` together. About
   25 minutes later the cluster shows up as connected in the console. If you
   leave all three empty you get a cluster with no control-plane connection and
   no way to install anything into it.

3. **Launch the product infrastructure stack** for what you are deploying — for
   Midaz, [`products/midaz/infrastructure.yaml`](products/midaz/README.md). It
   imports the VPC and cluster from the Foundation stack and creates the
   databases, cache and broker. Repeat per product on the same Foundation.

4. **Install the product from the console**, or with the `lerian` CLI
   (`lerian auth login`, then `lerian midaz ledger create`). The agent performs
   the install from inside the cluster. Upgrades, rollbacks and configuration
   changes happen there too — not as stack updates.

## Foundation Stack

The Foundation stack creates the shared VPC and EKS cluster and enrolls the
Lerian agent in it. Route53 and ALB Controller are created only when
`DomainName` is set, and ExternalDNS only when `DomainName` is set and
`EnableExternalDNS=true`. The agent is installed only when `ControlPlaneURL`,
`EnrollmentToken` and `AgentChartVersion` are all three supplied — leave them
empty for a cluster with no control-plane connection. A partial set is rejected
at CreateStack.

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

Rough monthly cost of a Foundation stack plus one product's data services, at
sa-east-1 on-demand rates. The cluster and its node group dominate; the rest
scales with the instance classes you pick.

| Size | Monthly Cost |
|------|--------------|
| Development | ~$970 |
| Production | ~$1,220 |
| Enterprise | ~$2,450 |

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributing](CONTRIBUTING.md)
- [Marketplace listing](docs/marketplace-changesets.md)

## License

Apache License 2.0 - see [LICENSE](LICENSE)

---

Built by [Lerian Studio](https://lerian.studio)
