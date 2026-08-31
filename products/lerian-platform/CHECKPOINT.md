# Lerian Platform (orchestrator) — checkpoint to a publishable v0 (dev, one-click)

Goal: a one-click "Launch Stack" experience for `lerian-platform` on AWS,
matching what `products/midaz/README.md` already does — publishable to a
public S3 templates bucket, reproducible from git, safe to hand to a
teammate for a dev/internal deploy. **Not** the full AWS Marketplace
submission bar (ECR migration, multi-region, CI/CD, admission webhooks —
those are a later phase, listed at the bottom as "post-v0").

Status as of this checkpoint: **6 of 9 catalog modules validated live**
end-to-end against a real AWS sandbox account (`524121347244`, `sa-east-1`),
via a real `create-stack` (not manual `kubectl` patches) —
`access_manager`, `ledger`, `tracer`, `console`, `bank_transfer`,
`reporter`, `fetcher`. `fees` and `pix_indirect_btg` are untested.

Repos involved:
- `platform-orchestrator` (Go operator + Helm chart + module catalog) —
  branch `feat/operator-e2e-hardening`, PR #2, HEAD `46175de` at checkpoint
  time. All fixes below are committed + pushed there unless noted.
- `lerian-cloudformation-foundation` — `products/lerian-platform/*.yaml`
  (the CFN templates + bootstrap Lambda) and `templates/eks.yaml`. **Neither
  is committed to git** — see blocker #1.

---

## Blockers (must fix before calling this "v0 publishable")

### 1. `products/lerian-platform/` and the `templates/eks.yaml` diff are not in git
Everything that makes the live stack work today — the S3/IRSA fix, the MSK
brokers fix, the license-secret naming fix, the `OIDCProviderHost` output —
exists only as local files on one machine + whatever was last uploaded to
the S3 templates bucket. Nothing is reproducible from `git clone`. This is
the actual first blocker: fix this before anything else, or every other fix
below is only as durable as one laptop's disk.
- Action: `git add` + commit `products/lerian-platform/` (decide the fate of
  the legacy `helm.yaml`/`app-stack.yaml`/`application.yaml` — keep as a
  documented fallback, or delete once `orchestrator.yaml` fully replaces
  them) and the `templates/eks.yaml` diff (`OIDCProviderHost` output).

### 2. Chart/image are alpha test builds, not a real release
- `charts/platform-orchestrator` has never been tagged/pushed as a real
  version — every alpha this session was `0.1.0-alpha.<timestamp>.<sha>`,
  and `OrchestratorChartVersion`'s CFN default still points at one of those.
- The manager image is `v0-e2e-21-5ffcb835-amd64` — a single-arch (amd64),
  manually-built-and-pushed tag from this session's live debugging, not a
  release artifact.
- `ledger`/`tracer` in the catalog are pinned to alpha charts
  (`oci://.../alpha/midaz-helm`, `oci://.../alpha/tracer-helm`) that depend
  on unmerged PRs (`helm#1926`/`#1927`). Fine for continued dev testing;
  flag clearly as "not yet on a stable chart" in the checkpoint, not
  something to silently ship as v0.
- Action: cut and tag a real `v0.1.0` (chart + image), update
  `OrchestratorChartVersion`'s CFN default to point at it. Merging
  `helm#1926`/`#1927` and moving ledger/tracer off alpha can follow
  separately — track as a known v0 limitation, not a hard blocker, since the
  alpha charts DO work (validated live).

### 3. `AuthorizerClientSecret` is a hardcoded, shared-across-customers default
`Default: "6add4bc64f394456a77fa85708ad8c9b67e39e4c"` (matches the seeded
Casdoor `init_data.json`) — every dev deploy that doesn't override BOTH this
value AND ship a custom `init_data.json` gets the identical M2M authorizer
secret. Confirmed real (verified directly against the current
`orchestrator.yaml`, not just the other agent's report). For a v0 aimed at
"dev, one-click, low-stakes" this is arguably acceptable *if documented*,
but it should not silently ship undocumented.
- Action (minimum for v0): document it loudly in the README ("dev-only
  shared secret; do not use for anything internet-facing without a custom
  `init_data.json`"). Real fix (generate per-deploy) is post-v0 — see below.

### 4. Region is hardcoded to `sa-east-1` via `DEFAULT_CA_BUNDLE_B64`
The Lambda's embedded CA bundle (used for RDS/DocumentDB TLS) is the
`sa-east-1` RDS truststore, and the override mechanism
(`ENVIRONMENT_CONTRACT_CA_REF`) doesn't fit a full multi-region bundle
within a CFN Parameter's 4096-char limit. For a v0 scoped to
`sa-east-1`-only (matches every test this session), this is fine — just
needs to be an explicit, documented constraint, not a silent trap.
- Action: pin `MPS3BucketRegion`'s `AllowedValues` to `[sa-east-1]`
  explicitly (already the practical reality) and say so in the README.
  Multi-region CA bundling is post-v0.

### 5. `config/rbac/role.yaml` vs the Helm chart's `templates/clusterrole.yaml`
The workload RBAC grants (deployments/statefulsets/daemonsets/pdb/jobs/etc)
live in the CHART template (fixed this session, the `daemonsets` grant is
what unblocked the whole reconciler-deadlock bug) but are NOT expressed as
`+kubebuilder:rbac` markers on the controller code, so `config/rbac/
role.yaml` (the kubebuilder-generated manifest) doesn't carry them — a
`make manifests` run regenerates `config/rbac/role.yaml` WITHOUT these
grants, silently diverging from the chart. The chart itself is unaffected
(it's hand-maintained, not generated), so this doesn't block v0 functionally
— but the next person who runs `make manifests` will get confused by the
diff and may "fix" it by deleting the wrong thing.
- Action: either add the missing `+kubebuilder:rbac` markers so generation
  stays in sync, or add a comment at the top of `config/rbac/role.yaml`
  explaining it's stale/superseded by the chart and why. Low effort, do it
  before someone else touches this file.

---

## Known limitations (fine for v0-dev, must fix before real Marketplace submission)

These don't block a "publishable in dev, one-click" v0 — they block the
*next* phase (public Marketplace listing). Listed so they don't get lost.

- **No CI/CD pipeline** for the operator (no `.github/` workflows) — every
  image/chart this session was built and pushed by hand.
  - **Images pulled from `ghcr.io`, not ECR** — Marketplace container-based
  listings require ECR; today's chart also needs `imagePullSecrets:
  [ghcr-pull]` since the packages default private.
- **No admission webhook** — an invalid `Platform` CR only fails at
  reconcile time, not at `kubectl apply` time.
- **Zero Kubernetes Events emitted** by the operator — `kubectl describe`
  on a stuck `ModuleRelease` is silent; makes support/debugging harder than
  it needs to be (this session's whole investigation style — reading
  `.status.conditions` — works, but Events would have caught some of this
  session's bugs faster).
- **Fixed 10s requeue, no exponential backoff** on retryable errors.
- **`kubectl` version pinned in the Lambda vs. cluster version skew** — worth
  a periodic check, not urgent while sa-east-1/one supported EKS version is
  the only target.
- **M2M authorizer secret is shared** (see blocker #3) — real fix is
  generating it per-deploy (e.g. render a fresh `init_data.json` at bootstrap
  time) instead of relying on the seeded default.
- **`authorizer.clientSecret` travels in plaintext** in the `Platform` CR
  and Helm values — real fix is a `secretRef` instead of an inline value,
  matching the pattern already used for `LICENSE_KEY`/`DB_PASSWORD` etc.
  elsewhere in the catalog.
- **Ledger's app Postgres password is the RDS master password**, mirrored
  into ~9 keys of the `midaz-secrets` Secret — the dedicated-role bootstrap
  mechanism (`postgres-role-bootstrap`, already used by `access_manager`/
  `bank_transfer`/`pix_indirect_btg`) exists and isn't applied to `ledger`.
- **Stack DELETE is not clean**: consistent with the operator's
  install-once/disown model, deleting the stack removes the CRs and the
  operator itself but NOT the module Helm releases — ALB/ENI/EBS resources
  those releases created can orphan and block VPC teardown (this session hit
  the ENI-orphan variant of this twice, manually unstuck both times). A
  "best-effort teardown" step in the custom resource's Delete path (only
  when the stack owns the cluster) would close this.
- **`bank_transfer` ships `JD_SANDBOX_MODE=true`/`ENV_NAME=development`
  defaults** — correct for a v0-dev checkpoint, wrong defaults to carry into
  a real Marketplace listing without a loud "this is a rails sandbox" flag.
- **Console URL chicken-and-egg**: `NextAuthUrl`/ingress hostname are asked
  for before the ALB exists; without a pre-owned domain the console has no
  working auth callback URL on first boot. Known, not solved this session.
- **Default sizing is expensive** (~US$3-4k/mo: RDS + DocumentDB×3 + MSK×2 +
  EKS 3×c6i.xlarge + 3 NATs) with no "small/trial" profile — fine for
  internal dev, a real listing needs a cost-estimate-friendly default.
- **`RDSReplicaEndpoint` output has no `IsShared` guard** (cfn-lint W1001) —
  a real bug in the "dedicated" topology path specifically (never exercised
  this session; every test used the default `shared` topology). Fix before
  anyone tries `InfraTopology=dedicated`.

## Already validated (do not re-litigate, just keep regression-testing)

- `Platform.status.Ready=True` end-to-end from a **fresh `create-stack`**
  (not `kubectl` patches) with `access_manager`, `ledger`, `tracer`,
  `console`, `bank_transfer`, `reporter`, `fetcher` all enabled via real CFN
  parameters (`Enable*=true`), including the S3/IRSA fix for reporter/
  fetcher — confirmed live at checkpoint time (`ObjectStorageRole`,
  `ReporterStorageBucket`, `FetcherStorageBucket` all `CREATE_COMPLETE`
  in the same run).
- `access_manager`'s license validates against the dev gateway via
  `LicenseUseDevGateway` (a real CFN parameter now, not a hardcoded
  literal — was the very first thing fixed this session and stayed fixed
  end-to-end through every subsequent module added).
- `bank_transfer`/`fetcher` run correctly with **no license key at all** in
  `ENV_NAME=development` (their license enforcement is gated by env, not by
  key presence — confirmed by reading each app's own source, not assumed).
- The `daemonsets` RBAC fix, the Helm-SDK REST timeout, the Pre-hook
  re-entrancy fix, and the Ready-flapping fix — the whole class of "operator
  silently deadlocks with zero error output" bugs — root-caused and fixed at
  the source, not worked around per-incident.
- `reporter`/`fetcher`'s RabbitMQ topology bootstrap moved from each chart's
  broken Job (upstream bug: `apk add jq` at runtime inside a non-root
  container, confirmed unfixed as of `reporter-helm` 4.2.0) to a direct Go
  HTTP call in the operator — no Job, no external image, nothing that can
  silently swallow a permission error.
- The 5 CRDs (`platforms`, `platformreleases`, `modulereleases`,
  `environmentcontracts`, `bootstrapoperations`) are all present in
  `charts/platform-orchestrator/crds/`, byte-identical to
  `config/crd/bases/` — the "3 of 5 CRDs missing" finding from the parallel
  agent review was checked and is **false** (stale read, not current code).

## Untested (scope decision needed for v0)

- `fees` — never enabled, unknown whether it has similar undiscovered bugs
  (every module tested so far had at least one).
- `pix_indirect_btg` — never enabled; has a **known, unfixed gap**: its own
  M2M self-identity (`PLUGIN_PIX_BTG`) is never registered by the live
  `m2m-app` BootstrapOperation provider (`effectsource/resolver.go`'s
  `m2mApplications` list doesn't include it), so its own inbound auth would
  always get an empty credential if enabled today.
- Decision needed: does v0 explicitly scope these two out (`Enable*` stays
  `false`, documented as "not yet supported") — recommended, given the
  pattern of every tested module surfacing a real bug — or do they need a
  validation pass first?

---

## Suggested sequence to close the gap

1. **Commit** (`products/lerian-platform/` + `templates/eks.yaml` diff) —
   closes blocker #1, everything else becomes reviewable/reproducible.
2. **Cut a real `v0.1.0`** chart+image tag, point `OrchestratorChartVersion`
   at it — closes blocker #2's acute half (alpha-tag-in-prod-default); the
   ledger/tracer alpha-chart dependency stays a documented limitation.
3. **Write the README** (mirror `products/midaz/README.md`'s Launch Stack
   table), publish templates to a public bucket, scope `fees`/
   `pix_indirect_btg` OUT (`Enable*=false` defaults, called out as
   unsupported) — this is the actual "one-click button exists" milestone.
4. **Document the loud caveats** (blockers #3/#4, the shared M2M secret,
   `sa-east-1`-only) directly in that README rather than fixing them —
   acceptable for a dev-scoped v0, not for a public listing.
5. Everything in "known limitations" above becomes the backlog for the
   *next* checkpoint (real Marketplace submission).
