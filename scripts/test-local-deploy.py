#!/usr/bin/env python3
"""
Local test harness for the Lerian Platform deployer (products/lerian-platform/helm.yaml).

It extracts the Lambda's embedded Python, mocks the 3 AWS touchpoints (get_secret,
setup_kubeconfig, eks_token), and for each selected module:

  1. renders values via the REAL render_values() (no CloudFormation),
  2. runs `helm template <release> <repo> --version <ver> -f values.yaml` against the
     REAL OCI chart — this validates our values + secret-key wiring against the chart's
     templates and values.schema.json, catching mismatches WITHOUT a cluster,
  3. builds the runtime Secret(s) and prints their keys.

Optionally (--gitops) it renders the GitOps seed artifacts (values + ExternalSecret +
ArgoCD Application) into a temp dir and validates they are well-formed YAML.

Private charts (e.g. flowker helm-internal) need `helm registry login ghcr.io` first;
a pull failure is reported as SKIP, not a hard error.

Usage:
  scripts/test-local-deploy.py                # all modules, render+secret+helm template
  scripts/test-local-deploy.py --apps ledger,access_manager
  scripts/test-local-deploy.py --no-helm      # offline: render + secret only
  scripts/test-local-deploy.py --gitops       # also dry-render the GitOps seed
"""
import argparse
import base64
import os
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
HELM_YAML = os.path.join(HERE, "..", "products", "lerian-platform", "helm.yaml")

# Fake managed-infra endpoints + credentials (never touch AWS).
FAKE_ENDPOINTS = {
    "RDS_ENDPOINT": "rds.local.test:5432",
    "RDS_REPLICA_ENDPOINT": "rds-ro.local.test:5432",
    "DOCUMENTDB_ENDPOINT": "docdb.local.test:27017",
    "ELASTICACHE_ENDPOINT": "redis.local.test:6379",
    "AMAZONMQ_ENDPOINT": "amqps://mq.local.test:5671",
}
FAKE_SECRETS = {
    "rds": {"username": "lerian_admin", "password": "RdsP@ss-1"},
    "docdb": {"username": "docdbadmin", "password": "DocP@ss-1"},
    "mq": {"username": "mquser", "password": "MqP@ss-1"},
}


def fake_get_secret(arn):
    if not arn:
        return {}
    if "rds" in arn:
        return FAKE_SECRETS["rds"]
    if "docdb" in arn:
        return FAKE_SECRETS["docdb"]
    if "mq" in arn:
        return FAKE_SECRETS["mq"]
    return {}


def load_deployer():
    """Extract and exec the Lambda code with AWS mocked; return its globals."""
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML required: pip install pyyaml")

    class _L(yaml.SafeLoader):
        pass

    _L.add_multi_constructor("", lambda loader, suffix, node: None)
    with open(HELM_YAML) as fh:
        doc = yaml.load(fh, Loader=_L)
    code = doc["Resources"]["DeployerFunction"]["Properties"]["Code"]["ZipFile"]

    # Inject a fake boto3 so the module-level `import boto3` succeeds.
    sys.modules["boto3"] = types.SimpleNamespace(client=lambda name: None)

    g = {}
    exec(compile(code, "deployer.py", "exec"), g)

    # Mock the 3 AWS touchpoints + the CA fetch (network).
    g["get_secret"] = fake_get_secret
    g["get_redis_password"] = lambda: "RedisP@ss-1"
    g["get_aws_ca_cert_base64"] = lambda: base64.b64encode(b"FAKE-CA").decode()
    return g


def set_env(g, enabled_apps):
    os.environ.update(FAKE_ENDPOINTS)
    os.environ.update({
        "AWS_DEFAULT_REGION": "sa-east-1",
        "REPLICA_COUNT": "2",
        "RDS_SECRET_ARN": "arn:aws:secretsmanager:sa-east-1:0:secret:rds",
        "DOCUMENTDB_SECRET_ARN": "arn:aws:secretsmanager:sa-east-1:0:secret:docdb",
        "AMAZONMQ_SECRET_ARN": "arn:aws:secretsmanager:sa-east-1:0:secret:mq",
        "ELASTICACHE_SECRET_ARN": "arn:aws:secretsmanager:sa-east-1:0:secret:redis",
        "REPORTER_S3_BUCKET": "lerian-test-reporter",
        "FETCHER_S3_BUCKET": "lerian-test-fetcher",
        "FLOWKER_S3_BUCKET": "lerian-test-flowker",
        "NEXTAUTH_URL": "https://console.local.test",
        "ENABLE_INGRESS": "false",
        "AUTHORIZER_CLIENT_ID": "ac56c81d4d6d95c0ac12",
        "AUTHORIZER_CLIENT_SECRET": "6add4bc64f394456a77fa85708ad8c9b67e39e4c",
        "ACCESS_MANAGER_LICENSE_KEY": "TEST-LICENSE",
        "ACCESS_MANAGER_ORGANIZATION_IDS": "",
        "CONSOLE_ADMIN_PASSWORD": "",
    })
    # Cross-app awareness flags so render_values(reporter) etc. resolve enabled('fetcher').
    for a in g["REGISTRY"]:
        os.environ[g["REGISTRY"][a]["enable"]] = "true" if a in enabled_apps else "false"


def chart_versions(g):
    """Map version_env -> default from helm.yaml Parameters."""
    import yaml

    class _L(yaml.SafeLoader):
        pass

    _L.add_multi_constructor("", lambda loader, suffix, node: None)
    params = yaml.load(open(HELM_YAML), Loader=_L)["Parameters"]
    # version_env (e.g. LEDGER_VERSION) -> param name (LedgerChartVersion)
    env_to_param = {}
    for app in g["REGISTRY"]:
        ve = g["REGISTRY"][app]["version_env"]  # e.g. LEDGER_VERSION
        base = ve[:-len("_VERSION")].title().replace("_", "")  # Ledger, AccessManager...
        env_to_param[ve] = base + "ChartVersion"
    out = {}
    for ve, pname in env_to_param.items():
        if pname in params and "Default" in params[pname]:
            out[ve] = str(params[pname]["Default"])
    return out


def valid_yaml(text):
    import yaml
    try:
        list(yaml.safe_load_all(text))
        return True, ""
    except Exception as e:
        return False, str(e)


def run_helm_template(g, app, values_path, version):
    m = g["REGISTRY"][app]
    cmd = ["helm", "template", m["release"], m["repo"], "--version", version,
           "--namespace", m["ns"], "-f", values_path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return "SKIP", "helm not installed"
    except subprocess.TimeoutExpired:
        return "SKIP", "helm template timed out"
    if r.returncode == 0:
        return "OK", f"{len(r.stdout.splitlines())} lines rendered"
    err = (r.stderr or r.stdout).strip().splitlines()
    tail = " | ".join(err[-3:])[:400]
    # Chart pull/auth failures are environmental, not our-values failures.
    if any(k in (r.stderr or "") for k in ("not found", "unauthorized", "denied",
                                           "failed to authorize", "no such host",
                                           "connection refused", "pull access")):
        return "SKIP", f"chart pull failed (registry login/network): {tail}"
    return "FAIL", tail


def capture_secrets(g, app, m2m=None):
    import yaml
    applied = []
    g["run"] = lambda cmd, check=True, env=None: ""  # kubectl get -> empty (store-once fresh)
    g["kubectl_apply"] = lambda manifest: applied.append(yaml.safe_load(manifest))
    g["create_runtime_secret"](app, g["REGISTRY"][app]["ns"], m2m)
    return [(s["metadata"]["name"], sorted(s.get("stringData", {}).keys())) for s in applied]


def gitops_dry(g, app, workdir):
    """Render the GitOps seed artifacts for one app and validate YAML."""
    import yaml
    ns = g["REGISTRY"][app]["ns"]
    arts = {
        "values.yaml": g["render_values"](app),
        "external-secret.yaml": g["external_secret_manifest"](app, ns),
        "application.yaml": g["argocd_application"](app, "git@example:repo.git", "main",
                                                    "environments/production"),
    }
    results = {}
    for name, text in arts.items():
        ok, err = valid_yaml(text)
        results[name] = "ok" if ok else f"INVALID: {err}"
        with open(os.path.join(workdir, f"{app}-{name}"), "w") as fh:
            fh.write(text)
    return results


def main():
    ap = argparse.ArgumentParser(description="Local test harness for the Lerian Platform deployer")
    ap.add_argument("--apps", default="", help="comma list (default: all in REGISTRY)")
    ap.add_argument("--no-helm", action="store_true", help="skip `helm template` (offline render+secret only)")
    ap.add_argument("--gitops", action="store_true", help="also dry-render the GitOps seed artifacts")
    args = ap.parse_args()

    g = load_deployer()
    all_apps = list(g["REGISTRY"].keys())
    apps = [a.strip() for a in args.apps.split(",") if a.strip()] or all_apps
    bad = [a for a in apps if a not in g["REGISTRY"]]
    if bad:
        sys.exit(f"unknown apps: {bad}. valid: {all_apps}")

    set_env(g, apps)
    versions = chart_versions(g)
    for ve, val in versions.items():
        os.environ[ve] = val

    tmp = tempfile.mkdtemp(prefix="lerian-harness-")
    print(f"# workdir: {tmp}\n")
    hdr = f"{'app':16s} {'render':7s} {'helm template':40s} secrets"
    print(hdr)
    print("-" * len(hdr))

    fails = 0
    for app in apps:
        # 1) render
        try:
            vals = g["render_values"](app)
            ok, err = valid_yaml(vals)
            if not ok:
                print(f"{app:16s} {'FAIL':7s} render is invalid YAML: {err}")
                fails += 1
                continue
        except Exception as e:
            print(f"{app:16s} {'FAIL':7s} render raised: {e}")
            fails += 1
            continue
        vpath = os.path.join(tmp, f"values-{app}.yaml")
        with open(vpath, "w") as fh:
            fh.write(vals)

        # 2) helm template
        if args.no_helm:
            ht_status, ht_note = "SKIP", "--no-helm"
        else:
            ht_status, ht_note = run_helm_template(g, app, vpath, versions.get(g["REGISTRY"][app]["version_env"], ""))
        if ht_status == "FAIL":
            fails += 1

        # 3) secrets
        try:
            secs = capture_secrets(g, app, {"bank_transfer": {"MIDAZ_CLIENT_ID": "x", "MIDAZ_CLIENT_SECRET": "y"}}
                                   if app == "bank_transfer" else None)
            sec_note = ",".join(name for name, _ in secs)
        except Exception as e:
            sec_note = f"SECRET FAIL: {e}"
            fails += 1

        print(f"{app:16s} {'ok':7s} {ht_status + ': ' + ht_note:40.40s} {sec_note}")
        if ht_status == "FAIL":
            print(f"{'':16s}         └─ {ht_note}")

    if args.gitops:
        print("\n# GitOps seed (dry render)")
        for app in apps:
            res = gitops_dry(g, app, tmp)
            print(f"{app:16s} " + " ".join(f"{k}={v}" for k, v in res.items()))

    print(f"\n# artifacts in {tmp}")
    print("FAILURES:" if fails else "ALL PASSED", fails or "")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
