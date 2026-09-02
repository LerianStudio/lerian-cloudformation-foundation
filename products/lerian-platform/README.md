# Lerian Platform on AWS

[Lerian Platform](https://docs.lerian.studio) deploys the `platform-orchestrator`
Kubernetes controller onto an existing EKS cluster, then hands module lifecycle
(Ledger, Access Manager, Tracer, Console, Reporter, Fetcher, Bank Transfer, Fees)
to it declaratively via two CRDs (`EnvironmentContract` + `Platform`) — the
operator reconciles continuously as a long-running Deployment instead of the
Lambda looping a `helm install` per app.

**Status: v0, dev-scoped, one-click.** Not yet an AWS Marketplace submission
(no ECR migration, no admission webhook, no CI/CD pipeline for the operator
image/chart — see [`CHECKPOINT.md`](./CHECKPOINT.md) for the full backlog).
7 of 9 catalog modules have been validated live end-to-end against a real AWS
sandbox account via real `create-stack`/`update-stack` calls.

The current, correct template is **`orchestrator.yaml`**. `full-stack.yaml`,
`app-stack.yaml`, `application.yaml`, and `helm.yaml` are earlier iterations
kept in this directory for reference — they are **not** the deployment path
described here; do not launch them expecting this behavior.

## Prerequisites

`orchestrator.yaml` installs the operator and hands it module lifecycle — it
does **not** provision the data layer. Before launching it you need an
existing EKS cluster plus (depending on which modules you enable) RDS
PostgreSQL, DocumentDB, ElastiCache (Valkey/Redis), AmazonMQ (RabbitMQ), and
MSK, with their endpoints/Secrets Manager ARNs/KMS key ARNs on hand to pass
in as stack parameters. Midaz's own `foundation.yaml` + `infrastructure.yaml`
templates in this repo provision that same infra shape and are a reasonable
way to stand it up first if you don't already have it.

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

- **`fees`** (`EnableFees`) — catalog entry exists but has never been
  enabled/validated live. Every module tested so far surfaced at least one
  real bug before it worked; `fees` has not been through that pass. Default
  is `false` — leave it that way.
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
| **Orchestrator** | Installs `platform-orchestrator` onto an existing EKS cluster and reconciles the enabled module set | [![Launch][img]][lerian-platform-orchestrator-sa-east-1] |

[lerian-platform-orchestrator-sa-east-1]: https://console.aws.amazon.com/cloudformation/home?region=sa-east-1#/stacks/quickcreate?templateURL=https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/products/lerian-platform/orchestrator.yaml&stackName=lerian-platform

[img]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

You will be prompted in the console for the required inputs the template
does not default (`ProjectName`, `EnvironmentName`, `ClusterName`, and the
existing data-layer endpoints/secret ARNs listed under Prerequisites).
`OrchestratorChartVersion` and the manager image are already pinned to a
live-validated build — see the parameter's inline description in
`orchestrator.yaml` for exactly which commit and what was validated on it.

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
    ParameterKey=DocumentDBSecretArn,ParameterValue=<...>
    # ... remaining data-layer params per your enabled module set
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
