# Lerian Platform (orchestrator) — checkpoint to a publishable v0 (dev, one-click)

Goal: a one-click "Launch Stack" experience for `lerian-platform` on AWS,
matching what `products/midaz/README.md` already does — publishable to a
public S3 templates bucket, reproducible from git, safe to hand to a
teammate for a dev/internal deploy. **Not** the full AWS Marketplace
submission bar (ECR migration, multi-region, CI/CD, admission webhooks —
those are a later phase, listed at the bottom as "post-v0").

Status as of this update: **7 of 9 catalog modules validated live**
end-to-end against a real AWS sandbox account (`524121347244`, `sa-east-1`),
via a real `create-stack`/`update-stack` (not manual `kubectl` patches) —
`access_manager`, `ledger`, `tracer`, `console`, `bank_transfer`,
`reporter`, `fetcher` all reached `Platform.status.Ready=True` together in
one run, S3/IRSA confirmed clean for reporter/fetcher with zero manual
intervention. `fees` and `pix_indirect_btg` are still untested. The stack
was deliberately torn down afterward (data-layer teardown, no app-layer
workaround) to test the DELETE-path fix below on a real run.

Repos involved:
- `platform-orchestrator` (Go operator + Helm chart + module catalog) —
  branch `feat/operator-e2e-hardening`, HEAD `46175de` at this update.
  Separately, PR #1 (`ci/adopt-github-workflows`) adopts the shared
  LerianStudio CI/security pipelines (go-release/go-pr-validation/
  go-security) — lint now passes; still blocked on (a) `DOCKERHUB_IMAGE_
  PULL_TOKEN`/`_PUSH_TOKEN` org secrets not scoped to this repo (needs an
  org admin, not fixable from the repo) and (b) 40 real govulncheck
  findings in the helm.sh/helm/v3 OCI-registry/containerd dependency
  chain (deferred, needs its own dependency-bump investigation).
- `lerian-cloudformation-foundation` — `products/lerian-platform/*.yaml`
  (the CFN templates + bootstrap Lambda) and the `templates/eks.yaml`/
  `rds.yaml`/`documentdb.yaml`/`msk.yaml`/`ci.yml` diffs. **Now committed**
  on branch `feat/lerian-platform-cfn-fixes` (commit `05db1a3`) — blocker
  #1 below is resolved, push to origin pending.

---

## Blockers (must fix before calling this "v0 publishable")

### 1. ~~`products/lerian-platform/` and the `templates/eks.yaml` diff are not in git~~ RESOLVED
Committed on branch `feat/lerian-platform-cfn-fixes` (commit `05db1a3`):
`products/lerian-platform/` in full (including the legacy `helm.yaml`/
`app-stack.yaml`/`application.yaml` — kept as-is, fate undecided, not
blocking), the `templates/eks.yaml` (`NodeAmiType` param + `OIDCProviderHost`
output), `rds.yaml`/`documentdb.yaml` (alphanumeric-only generated
passwords — punctuation was breaking postgres/mongodb URL parsing for
downstream consumers), `msk.yaml`, `ci.yml`, and `template-versions.json`
diffs. Not yet pushed to `origin` — an automated credential-leak check
flagged two lines for manual review before push (both confirmed false
positives: a literal `...` placeholder SSH key in a docs example, and an
explicit `"RedisP@ss-1"` mock value in the local test harness, sitting
right next to `FAKE-CA`). Push once confirmed.

### 2. Chart/image are alpha test builds, not a real release
- `charts/platform-orchestrator` has never been tagged/pushed as a real
  version. `OrchestratorChartVersion`'s CFN default now points at
  `0.1.0-alpha.202608311431.46175de7` (bumped from a stale pin 5
  fix-commits behind HEAD — the stale pin was itself a live-discovered bug:
  reporter/bank_transfer failed with bugs already fixed in git but never
  shipped in a chart+image; see "Already validated" below).
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
- ~~**Stack DELETE is not clean**~~ FIXED: the Lambda's Delete handler now
  calls `purge_module_helm_releases()` before deleting the Platform CR,
  uninstalling every enabled module's Helm release (discovered live via
  `helm list` per namespace, not reconstructed hash names). This was found
  because CFN's own internal "delete the failed resource, then retry
  create" cycle on a failed attempt was leaving an orphaned release behind
  that the next attempt's Helm install then collided with on ownership
  metadata (`invalid ownership metadata; ... current value is
  lp-<module>-<old-hash>`) — confirmed live across reporter/console/ledger/
  tracer in the same run. ALB/ENI/EBS-orphan-blocking-VPC-teardown risk is
  reduced accordingly but not exhaustively re-tested past one full delete
  cycle (which used the OLD Lambda code, pre-fix — the fix itself has not
  yet been exercised by a real CFN retry or delete; validate on the next
  create-stack).
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

- **All 7 tested modules reached `Platform.status.Ready=True` together**
  in one run (`access_manager`, `ledger`, `tracer`, `console`,
  `bank_transfer`, `reporter`, `fetcher`), via real CFN
  `create-stack`/`update-stack` calls (not `kubectl` patches), with the S3/
  IRSA fix for reporter/fetcher confirmed clean (`"Storage initialized"`
  log lines with the correct bucket name, correct `eks.amazonaws.com/
  role-arn` SA annotations, zero manual intervention).
- Root-caused and fixed live in this same run, all now in
  `orchestrator.yaml`: (a) `full-stack.yaml` passing 5 stale GitOps/
  `ConsoleAdminPassword` params to a template that never declared them;
  (b) the Lambda's `install_tools()` hitting `EADDRNOTAVAIL` downloading
  kubectl/helm — non-VPC Lambda has no real IPv6 egress, dl.k8s.io/
  get.helm.sh are dual-stack — fixed by forcing IPv4-only DNS resolution,
  plus retry-with-backoff for the separate `Connection timed out` failure
  mode (a shared-egress-IP transient block, distinct from the IPv6 issue);
  (c) `OrchestratorChartVersion` pinned 5 fix-commits behind
  `platform-orchestrator` HEAD — the CFN default silently kept shipping
  bugs (RabbitMQ topology bootstrap, postgres-role-bootstrap Job race)
  that were already fixed in git but never actually built into a
  chart+image; (d) CFN's delete-then-recreate retry model orphaning Helm
  releases that then blocked the next attempt on ownership metadata (see
  "known limitations" DELETE fix above).
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

1. ~~**Commit**~~ DONE (`feat/lerian-platform-cfn-fixes`, commit `05db1a3`) —
   push to origin once the two flagged lines are confirmed (see blocker #1).
2. **Cut a real `v0.1.0`** chart+image tag, point `OrchestratorChartVersion`
   at it — closes blocker #2's acute half (alpha-tag-in-prod-default); the
   ledger/tracer alpha-chart dependency stays a documented limitation. Also
   unblocks PR #1's CI (`platform-orchestrator`, `ci/adopt-github-workflows`)
   which still needs an org admin for the DockerHub secret scoping and a
   separate pass on the 40 govulncheck findings.
3. **Write the README** (mirror `products/midaz/README.md`'s Launch Stack
   table), publish templates to a public bucket, scope `fees`/
   `pix_indirect_btg` OUT (`Enable*=false` defaults, called out as
   unsupported) — this is the actual "one-click button exists" milestone.
4. **Document the loud caveats** (blockers #3/#4, the shared M2M secret,
   `sa-east-1`-only) directly in that README rather than fixing them —
   acceptable for a dev-scoped v0, not for a public listing.
5. Everything in "known limitations" above becomes the backlog for the
   *next* checkpoint (real Marketplace submission).
