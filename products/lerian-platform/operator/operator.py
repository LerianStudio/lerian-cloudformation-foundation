#!/usr/bin/env python3
"""Lerian Platform Operator (PoC) — cloud-agnostic in-cluster reconciler.

Watches the `Platform` CRD and reconciles the enabled modules by REUSING the
deployer logic (render_values / create_runtime_secret / helm_install) that today
runs inside the AWS Lambda. The difference: infra endpoints + credentials come
from the CR's environmentContract + referenced K8s Secrets — NOT boto3/AWS — so
the SAME operator runs on EKS, GKE, AKS or on-prem. The Lambda/CloudFormation (or
Terraform/Crossplane) shrinks to: provision infra, install this operator, create
the Platform CR + contract Secrets.

Day-2: because it's a controller, editing the CR (bump a version, add a module,
rotate a license) re-reconciles — not a one-shot install.
"""
import os, base64, kopf
from kubernetes import client, config

# ---- load the existing deployer code (mounted alongside) and neutralise the ----
# ---- AWS-specific touchpoints so infra comes from the contract, not boto3.  ----
DEPLOYER = os.environ.get("DEPLOYER_PATH", "/app/deployer.py")
_G = {"__name__": "__deployer__"}
exec(compile(open(DEPLOYER).read(), DEPLOYER, "exec"), _G)

config.load_incluster_config()
core = client.CoreV1Api()

_SECRET_CACHE = {}

def _read_k8s_secret(ref):
    """ref = '<namespace>/<name>' -> {key: decoded_value}."""
    if not ref:
        return {}
    if ref in _SECRET_CACHE:
        return _SECRET_CACHE[ref]
    ns, name = ref.split("/", 1)
    s = core.read_namespaced_secret(name, ns)
    d = {k: base64.b64decode(v).decode() for k, v in (s.data or {}).items()}
    _SECRET_CACHE[ref] = d
    return d


def _apply_contract_to_env(spec, logger):
    """Translate the CR's environmentContract into the env the deployer expects,
    and override its cloud touchpoints to read from K8s Secrets instead of AWS."""
    ec = spec.get("environmentContract", {})
    az = spec.get("authorizer", {})

    pg = ec.get("postgres", {}); mo = ec.get("mongo", {})
    rd = ec.get("redis", {}); mq = ec.get("amqp", {}); kf = ec.get("kafka", {})
    obj = ec.get("objectStorage", {})

    # host/string envs the deployer reads directly
    os.environ.update({
        "RDS_ENDPOINT": pg.get("host", ""), "RDS_REPLICA_ENDPOINT": "",
        "DOCUMENTDB_ENDPOINT": mo.get("host", ""),
        "ELASTICACHE_ENDPOINT": rd.get("host", ""),
        "AMAZONMQ_ENDPOINT": mq.get("host", ""),
        "AWS_DEFAULT_REGION": obj.get("region", "sa-east-1"),
        "AUTHORIZER_CLIENT_ID": az.get("clientId", ""),
        "AUTHORIZER_CLIENT_SECRET": az.get("clientSecret", ""),
        "ACCESS_MANAGER_ORGANIZATION_IDS": az.get("organizationIds", ""),
        # secret "ARNs" become K8s secret refs; get_secret is overridden below
        "RDS_SECRET_ARN": pg.get("secretRef", ""),
        "DOCUMENTDB_SECRET_ARN": mo.get("secretRef", ""),
        "ELASTICACHE_SECRET_ARN": rd.get("secretRef", ""),
        "AMAZONMQ_SECRET_ARN": mq.get("secretRef", ""),
        "MSK_SECRET_ARN": kf.get("secretRef", ""),
        "PLATFORM_NAMESPACE": "lerian-platform",
        "REPLICA_COUNT": "1",
        "ENABLE_INGRESS": "false",
    })

    # cloud touchpoints -> cloud-agnostic
    _G["get_secret"] = lambda ref: _read_k8s_secret(ref)
    _G["get_redis_password"] = lambda: _read_k8s_secret(rd.get("secretRef", "")).get(
        "REDIS_PASSWORD") or _read_k8s_secret(rd.get("secretRef", "")).get("password", "")
    _G["get_aws_ca_cert_base64"] = lambda: rd.get("caCertB64", "")
    _G["get_msk_brokers"] = lambda: kf.get("brokers", "")
    _G["install_tools"] = lambda need_git=False: os.environ.update({
        "HELM_CACHE_HOME": "/tmp/.helm/cache", "HELM_CONFIG_HOME": "/tmp/.helm/config",
        "HELM_DATA_HOME": "/tmp/.helm/data"}) or [os.makedirs(f"/tmp/.helm/{d}", exist_ok=True)
        for d in ("cache", "config", "data")]
    _G["setup_kubeconfig"] = lambda: None  # in-cluster SA


def _module_env(name, mod):
    os.environ[f"{name.upper()}_VERSION"] = mod.get("version", "") or os.environ.get(f"{name.upper()}_VERSION", "")
    if mod.get("bucket"):
        os.environ[f"{name.upper()}_S3_BUCKET"] = mod["bucket"]
    lic_ref = mod.get("licenseSecretRef", "")
    if lic_ref:
        os.environ[f"{name.upper()}_LICENSE_KEY"] = _read_k8s_secret(lic_ref).get("LICENSE_KEY", "")
    os.environ[f"ENABLE_{name.upper()}"] = "true"


@kopf.on.create("platform.lerian.io", "v1alpha1", "platforms")
@kopf.on.update("platform.lerian.io", "v1alpha1", "platforms")
def reconcile(spec, name, namespace, patch, logger, **_):
    _SECRET_CACHE.clear()
    _apply_contract_to_env(spec, logger)

    modules = spec.get("modules", {})
    enabled = [m for m, cfg in modules.items() if cfg.get("enabled")]
    logger.info(f"reconcile Platform/{name}: enabled modules = {enabled}")
    patch.status["phase"] = "Reconciling"
    patch.status["modules"] = {}

    done = []
    for m in enabled:
        try:
            _module_env(m, modules[m])
            # REUSE the deployer's per-module logic verbatim.
            _G["helm_install"](m)
            patch.status["modules"][m] = "Deployed"
            done.append(m)
            logger.info(f"module {m}: Deployed")
        except Exception as e:
            patch.status["modules"][m] = f"Failed: {e}"[:200]
            logger.error(f"module {m} failed: {e}")

    patch.status["phase"] = "Ready" if len(done) == len(enabled) else "Degraded"
    logger.info(f"Platform/{name} phase={patch.status['phase']} ({len(done)}/{len(enabled)})")
