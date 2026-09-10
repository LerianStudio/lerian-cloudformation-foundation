# Lerian Platform on AWS

[Lerian Platform](https://docs.lerian.studio) is a complete, modular core
banking platform: Midaz (the double-entry ledger engine) plus a composable
set of modules — Access Manager (auth/identity), Console, Reporter, Fetcher,
Bank Transfer — that a bank or fintech runs as their own core, in their own
AWS account (BYOC). This directory deploys it on AWS with a single
CloudFormation stack: click **Launch Stack**, fill in a handful of
parameters, and end up with a running platform — VPC, EKS, the managed data
layer (RDS/DocumentDB/ElastiCache/AmazonMQ, plus MSK when Fetcher is
enabled), and every module you enabled, all reconciled and healthy.

Under the hood, the stack installs the `platform-orchestrator` Kubernetes
controller onto the EKS cluster and hands it module lifecycle declaratively
via two CRDs (`EnvironmentContract` + `Platform`) — the operator reconciles
continuously as a long-running Deployment, the same delivery model used in
Lerian's own production BYOC deployments. **Tracer ships bundled into the
Ledger module** (midaz-helm v9.1.0/helm#1926 folded it directly into the
same chart Ledger installs) rather than as its own catalog entry — there is
no separate `EnableTracer` parameter; enabling Ledger enables Tracer too.

Validated live, end-to-end, against real AWS infrastructure: `ledger`
(+`tracer`), `access_manager`, `console`, `bank_transfer`, `reporter`, and
`fetcher` reach `Platform.status.Ready=True` together in a single run, with
zero manual intervention after clicking Launch. See
[`CHECKPOINT.md`](./CHECKPOINT.md) for the detailed validation log and the
current backlog toward a full AWS Marketplace listing.

There are two deployment paths:

- **`full-stack.yaml`** — **Full Stack**: a single stack that provisions
  VPC, EKS, RDS, DocumentDB, ElastiCache, AmazonMQ, and (when Fetcher is
  enabled) MSK, then installs `orchestrator.yaml` as the Application layer
  and wires every endpoint/secret-ARN/cluster-name parameter automatically
  via nested-stack outputs. Pick a region, name the project, click Launch —
  nothing to pre-provision.
- **`orchestrator.yaml`** — **Application only**: installs just the
  operator onto an **existing** EKS cluster and hands it module lifecycle.
  Requires you to already have the data layer (see Prerequisites).

`app-stack.yaml`, `application.yaml`, and `helm.yaml` are earlier iterations
kept in this directory for reference — they are **not** the deployment path
described here; do not launch them expecting this behavior.

## Prerequisites

| | Full Stack (`full-stack.yaml`) | Application only (`orchestrator.yaml`) |
|---|---|---|
| AWS account + region | `sa-east-1` only (see below) | `sa-east-1` only (see below) |
| VPC / EKS | Provisioned for you | Existing EKS cluster required |
| RDS / DocumentDB / ElastiCache / AmazonMQ | Provisioned for you | Existing, with endpoints + Secrets Manager ARNs on hand |
| MSK (Fetcher only) | Auto-provisioned when `EnableFetcher=true` | Bring your own (`MSKClusterArn`) or auto-provision (`MSKVpcId`/`MSKVpcCIDR`/`MSKPrivateSubnetIds`) |

**Region**: `sa-east-1` only for now — the bootstrap Lambda embeds a
region-specific CA bundle for RDS/DocumentDB TLS verification. Deploying
elsewhere fails TLS verification against the data layer; see
[`CHECKPOINT.md`](./CHECKPOINT.md) for the multi-region tracking item.

If you don't already have the data layer for **Application only**,
`foundation.yaml` + `products/midaz/infrastructure.yaml` in this repo
provision that same shape — or just launch `full-stack.yaml` instead, which
does this composition for you.

## Quick Start — One-Click Deploy

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Full Stack** | VPC, EKS, RDS, DocumentDB, ElastiCache, AmazonMQ, and the platform-orchestrator + module set — all from scratch, single click | [![Launch][img]][lerian-platform-full-sa-east-1] |
| **Orchestrator (Application only)** | Installs `platform-orchestrator` onto an **existing** EKS cluster and reconciles the enabled module set — requires the data layer already provisioned (see Prerequisites) | [![Launch][img]][lerian-platform-orchestrator-sa-east-1] |

<!--
TEMPORARY — internal testing only, on branch feat/lerian-platform-cfn-fixes.
The two links below point at a scratch S3 bucket (lerian-cfn-test-524121347244-sae1)
holding this branch's templates, NOT the real Marketplace bucket — the real bucket
(lerian-cloudformation-templates) only gets published by release.yml on a merge to
main, so it does not yet have this branch's fixes. Revert to the real-bucket URLs
(kept commented out just below) before/when merging to main.

Real (production) links, for restoring after merge:
[lerian-platform-full-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/full-stack.yaml&stackName=lerian-platform
[lerian-platform-orchestrator-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/orchestrator.yaml&stackName=lerian-platform
-->

[lerian-platform-full-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cfn-test-524121347244-sae1.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/full-stack.yaml&stackName=lerian-platform

[lerian-platform-orchestrator-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cfn-test-524121347244-sae1.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/orchestrator.yaml&stackName=lerian-platform

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

## Required parameters

**`full-stack.yaml` (Full Stack)** — only **3** parameters have no default:
`RDSMasterUsername`, `DocumentDBMasterUsername`, `AmazonMQAdminUsername`.
Everything else (VPC, EKS, module toggles, chart versions) has a working
default — pick a `ProjectName`, set those 3 usernames, and Launch.

**`orchestrator.yaml` (Application only)** — **10** parameters have no
default, since it doesn't provision its own infrastructure:
`ProjectName`, `EnvironmentName`, `ClusterName`, `RDSEndpoint`,
`RDSSecretArn`, `DocumentDBEndpoint`, `DocumentDBSecretArn`,
`ElastiCacheEndpoint`, `AmazonMQEndpoint`, `AmazonMQSecretArn` — the
Console groups them into labeled sections and marks each **`(Required)`**
directly in its label.

Access Manager needs a real Lerian license key (`AccessManagerLicenseKey`)
to operate — see `docs.lerian.studio` for how to obtain one.
`AuthorizerClientId`/`AuthorizerClientSecret` default to Lerian's own
seeded dev values; override both before exposing this deployment's
endpoints beyond your own testing (see `CHECKPOINT.md` for the per-deploy
secret rotation tracking item).

### CLI equivalent

```bash
aws cloudformation create-stack \
  --region sa-east-1 \
  --stack-name lerian-platform \
  --template-url https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/full-stack.yaml \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=lerian-platform \
    ParameterKey=EnvironmentName,ParameterValue=dev \
    ParameterKey=RDSMasterUsername,ParameterValue=midaz_admin \
    ParameterKey=DocumentDBMasterUsername,ParameterValue=midaz_admin \
    ParameterKey=AmazonMQAdminUsername,ParameterValue=midaz_admin \
    ParameterKey=AccessManagerLicenseKey,ParameterValue=<your-license-key>
    # ... remaining optional params per your enabled module set
```

## Enabling Ingress (Custom Domains)

Each of these modules can get its own AWS ALB Ingress with a custom
hostname: **Console**, **Ledger**, **Reporter**, **Fetcher**, **Bank
Transfer**, and **Access Manager** (its `auth` and `identity` endpoints
specifically — `caradhras`/`caradhras.ui` aren't wired yet, see
`CHECKPOINT.md`).

For each one, two parameters control it:

| Module | Enable | Hostname |
|--------|--------|----------|
| Console | `EnableConsoleIngress` | `ConsoleIngressHostname` |
| Ledger | `EnableLedgerIngress` | `LedgerIngressHostname` |
| Reporter | `EnableReporterIngress` | `ReporterIngressHostname` |
| Fetcher | `EnableFetcherIngress` | `FetcherIngressHostname` |
| Bank Transfer | `EnableBankTransferIngress` | `BankTransferIngressHostname` |
| Access Manager (auth) | `EnableAccessManagerAuthIngress` | `AccessManagerAuthIngressHostname` |
| Access Manager (identity) | `EnableAccessManagerIdentityIngress` | `AccessManagerIdentityIngressHostname` |

Every Ingress is **always internal** (`alb.ingress.kubernetes.io/scheme:
internal`) — no module here is meant to be reachable from the public
internet; access is via VPN/port-forward/an internal ALB. This is not a
customer-facing choice.

Two settings are shared across every enabled module's Ingress (one ALB,
via a common `alb.ingress.kubernetes.io/group.name` annotation) instead of
being repeated per module:

- `IngressClassName` — default `alb` (the AWS Load Balancer Controller's
  own default). Requires `EnableALBController: true` (the default).
- `IngressCertificateArn` — an ACM certificate ARN for HTTPS. Leave empty
  for HTTP-only.

**Hostnames auto-derive from `DomainName` when left empty.** Set
`DomainName` (e.g. `client.net`) once, and any Ingress you enable without
typing its own hostname gets `<module>.<DomainName>` automatically —
`console.client.net`, `ledger.client.net`, `auth.client.net`,
`identity.client.net`, etc. Setting a hostname explicitly always overrides
the derivation. Leaving `DomainName` empty means every enabled module's
hostname must be typed out by hand. `DomainName` also drives a private
Route53 hosted zone (VPC-internal only — it does not touch any public DNS
you may already own for that domain).

## Known limitations

See [`CHECKPOINT.md`](./CHECKPOINT.md) for the full, current list and the
path toward a full AWS Marketplace listing (ECR migration, admission
webhook, CI/CD for the operator image/chart, per-deploy secret rotation,
and a handful of smaller tracked items).
