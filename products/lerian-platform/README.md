# Lerian Platform on AWS

[Lerian Platform](https://docs.lerian.studio) deploys the `platform-orchestrator`
Kubernetes controller onto an existing EKS cluster, then hands module lifecycle
(Ledger, Access Manager, Tracer, Console, Reporter, Fetcher, Bank Transfer)
to it declaratively via two CRDs (`EnvironmentContract` + `Platform`) — the
operator reconciles continuously as a long-running Deployment instead of the
Lambda looping a `helm install` per app.

**Status: v0, dev-scoped, one-click.** Not yet an AWS Marketplace submission
(no ECR migration, no admission webhook, no CI/CD pipeline for the operator
image/chart — see [`CHECKPOINT.md`](./CHECKPOINT.md) for the full backlog).
7 of 9 catalog modules have been validated live end-to-end against a real AWS
sandbox account via real `create-stack`/`update-stack` calls.

There are two supported deployment paths:

- **`full-stack.yaml`** — **Full Stack**: a single stack that provisions VPC,
  EKS, RDS, DocumentDB, ElastiCache, and AmazonMQ (nesting
  `templates/foundation.yaml` and `products/midaz/infrastructure.yaml`),
  then nests `orchestrator.yaml` as the Application layer and wires every
  endpoint/secret-ARN/cluster-name parameter automatically via nested-stack
  outputs. If `EnableReporter`/`EnableFetcher` is `true`, it also provisions
  that module's S3 bucket and a shared IRSA role (`ObjectStorageRole`) for
  it — `orchestrator.yaml` itself does not provision object storage, so
  without this, enabling either module crashes it on "bucket name is
  required." Pick a region, name the project, click Launch — nothing to
  pre-provision.
- **`orchestrator.yaml`** — **Application only**: installs just the
  operator onto an **existing** EKS cluster and hands it module lifecycle.
  Requires you to already have RDS/DocumentDB/ElastiCache/AmazonMQ (and
  their Secrets Manager ARNs) on hand — see Prerequisites below.

`app-stack.yaml`, `application.yaml`, and `helm.yaml` are earlier iterations
kept in this directory for reference — they are **not** the deployment path
described here; do not launch them expecting this behavior. (The previous
`full-stack.yaml` occupying this name was one of those legacy iterations;
it has been replaced by the nested-stack template described above.)

## Prerequisites

**Full Stack (`full-stack.yaml`)** — none. It provisions the EKS cluster and
the entire data layer itself; you only need an AWS account and the
`sa-east-1` region (see below).

**Application only (`orchestrator.yaml`)** — installs the operator and hands
it module lifecycle, but does **not** provision the data layer. Before
launching it you need an existing EKS cluster plus (depending on which
modules you enable) RDS PostgreSQL, DocumentDB, ElastiCache (Valkey/Redis),
AmazonMQ (RabbitMQ), and MSK, with their endpoints/Secrets Manager ARNs/KMS
key ARNs on hand to pass in as stack parameters. Midaz's own
`foundation.yaml` + `infrastructure.yaml` templates in this repo provision
that same infra shape and are a reasonable way to stand it up first if you
don't already have it — or just launch `full-stack.yaml` instead, which does
this composition for you.

## ⚠️ Region: `sa-east-1` only

The bootstrap Lambda embeds a fixed CA bundle (`DEFAULT_CA_BUNDLE_B64`) for
RDS/DocumentDB TLS verification, built from the **`sa-east-1`** RDS
truststore. There is no multi-region override that fits within a CFN
Parameter's 4096-character limit yet. **Launch this stack only in the
`sa-east-1` console region.** Deploying elsewhere will fail TLS verification
against the data layer. Multi-region CA bundling is a known post-v0 gap, not
silently supported.

## ⚠️ Shared dev-only `AuthorizerClientSecret`

`AuthorizerClientSecret` defaults to a **hardcoded value shared across every
deploy** (`6add4bc64f394456a77fa85708ad8c9b67e39e4c`), matching the seeded
Casdoor `init_data.json`. Every dev stack that doesn't override **both** this
parameter **and** ship a custom `init_data.json` gets the identical M2M
authorizer secret as every other dev deploy of this template. This is
acceptable for an internal/dev "kick the tires" deploy, but:

- **Do not** expose this deployment's Console/API endpoints to the public
  internet without rotating this secret and providing a custom
  `init_data.json`.
- The real fix (generate a fresh per-deploy secret + `init_data.json` at
  bootstrap time) is tracked as a known limitation in `CHECKPOINT.md`, not
  yet implemented.

## Modules NOT yet supported — leave disabled

- **`fees`** — not exposed as a parameter in `orchestrator.yaml`/
  `full-stack.yaml` at all (there is no `EnableFees`/`FeesChartVersion`/
  `FeesLicenseKey` — removed; it was never enabled/validated live through
  this template, and every other module tested so far surfaced at least
  one real bug before it worked). If it's ever brought into scope, treat
  that as adding it back, not un-hiding something already there.
- **`pix_indirect_btg`** — not exposed as a parameter in `orchestrator.yaml`
  at all (there is no `EnablePixIndirectBtg`), so it cannot currently be
  enabled through this template. It also has a known, unfixed gap even in
  isolated testing: its own M2M self-identity (`PLUGIN_PIX_BTG`) is never
  registered by the operator's `m2m-app` bootstrap provider, so its inbound
  auth would get an empty credential if it were enabled.

Everything else in the catalog (`ledger`, `tracer`, `access_manager`,
`console`, `bank_transfer`, `reporter`, `fetcher`) has reached
`Platform.status.Ready=True` together in one live run.

## Quick Start — One-Click Deploy

| Stack | Description | Deploy |
|-------|-------------|--------|
| **Full Stack** | VPC, EKS, RDS, DocumentDB, ElastiCache, AmazonMQ, and the platform-orchestrator + module set — all from scratch, single click | [![Launch][img]][lerian-platform-full-sa-east-1] |
| **Orchestrator (Application only)** | Installs `platform-orchestrator` onto an **existing** EKS cluster and reconciles the enabled module set — requires the data layer already provisioned (see Prerequisites) | [![Launch][img]][lerian-platform-orchestrator-sa-east-1] |

[lerian-platform-full-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/full-stack.yaml&stackName=lerian-platform

[lerian-platform-orchestrator-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/orchestrator.yaml&stackName=lerian-platform

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

The console groups parameters into labeled sections; the 10 that have no
default are marked **`(Required)`** right in the parameter label so they're
obvious in the form, not just in this doc:
`ProjectName`, `EnvironmentName`, `ClusterName`, `RDSEndpoint`,
`RDSSecretArn`, `DocumentDBEndpoint`, `DocumentDBSecretArn`,
`ElastiCacheEndpoint`, `AmazonMQEndpoint`, `AmazonMQSecretArn` — all of
them existing data-layer endpoints/secret ARNs except the first three (see
Prerequisites). Everything else has a working default.
`OrchestratorChartVersion` and the manager image are already pinned to a
live-validated build — see the parameter's inline description in
`orchestrator.yaml` for exactly which commit and what was validated on it.

`full-stack.yaml` (Full Stack) drops that list to just **3** required
parameters — `RDSMasterUsername`, `DocumentDBMasterUsername`,
`AmazonMQAdminUsername` — since it provisions `ProjectName`/
`EnvironmentName`/`ClusterName` and every data-layer endpoint/secret ARN
itself and wires them internally via nested-stack outputs instead of asking
for them. Its console form groups parameters per module (Access Manager,
Ledger, Reporter, Tracer, Fetcher, Console, Bank Transfer) rather than by
parameter type, so each module's enable flag, chart version, license key,
and any module-specific fields sit together in one collapsible section.

### CLI equivalent

```bash
aws cloudformation create-stack \
  --region sa-east-1 \
  --stack-name lerian-platform \
  --template-url https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/orchestrator.yaml \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=lerian-platform \
    ParameterKey=EnvironmentName,ParameterValue=dev \
    ParameterKey=ClusterName,ParameterValue=<your-eks-cluster-name> \
    ParameterKey=RDSEndpoint,ParameterValue=<...> \
    ParameterKey=RDSSecretArn,ParameterValue=<...> \
    ParameterKey=DocumentDBEndpoint,ParameterValue=<...> \
    ParameterKey=DocumentDBSecretArn,ParameterValue=<...> \
    ParameterKey=ElastiCacheEndpoint,ParameterValue=<...> \
    ParameterKey=AmazonMQEndpoint,ParameterValue=<...> \
    ParameterKey=AmazonMQSecretArn,ParameterValue=<...>
    # ... remaining optional params per your enabled module set
```

## Known limitations

See [`CHECKPOINT.md`](./CHECKPOINT.md) for the full, current list (no
Marketplace-grade CI/CD, no admission webhook, no Kubernetes Events from the
operator, fixed 10s reconcile requeue, plaintext `authorizer.clientSecret` in
the `Platform` CR, ledger's Postgres password mirrored from the RDS master
password instead of a dedicated role, `bank_transfer` shipping
`JD_SANDBOX_MODE=true`/`ENV_NAME=development` by default, expensive default
sizing with no small/trial profile, and the `RDSReplicaEndpoint` output
missing an `IsShared` guard on the `dedicated` topology path).
