import json
import os
import base64
import logging
import secrets
import subprocess
import tarfile
import stat
import urllib.request
import urllib.parse

# boto3 is optional: the in-cluster operator (operator.py) overrides every AWS
# touchpoint (get_secret / get_msk_brokers / get_aws_ca_cert_base64 /
# setup_kubeconfig) to read from the EnvironmentContract + K8s Secrets, so the
# boto3-using functions below are never called in-cluster. Guard the import so
# the module loads on a cloud-agnostic image with no boto3 present. (In the CF
# Lambda path boto3 is provided by the Lambda runtime.)
try:
    import boto3
except ModuleNotFoundError:
    boto3 = None

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------
# App registry (single-tenant). Coordinates from gitops staging (plan 4.2).
# 'ns' = per-app namespace (kept to match chart service DNS references).
# 'needs' = which shared services this app touches.
# NOTE: exact chart value keys must be validated against each chart in the
# sandbox deploy (plan Phase 1.5). This encodes the connection contract.
# ---------------------------------------------------------------------
REGISTRY = {
    "access_manager": {
        "enable": "ENABLE_ACCESS_MANAGER",
        "release": "plugin-access-manager", "ns": "plugin-access-manager",
        "repo": "oci://ghcr.io/lerianstudio/plugin-access-manager",
        "version_env": "ACCESS_MANAGER_VERSION",
        "needs": ["pg", "redis"], "order": 0,
    },
    "ledger": {
        "enable": "ENABLE_LEDGER",
        "release": "midaz", "ns": "midaz-mt",
        "repo": "oci://ghcr.io/lerianstudio/midaz-helm",
        "version_env": "LEDGER_VERSION",
        "needs": ["pg", "mongo", "redis", "mq"], "order": 1,
    },
    "tracer": {
        "enable": "ENABLE_TRACER",
        "release": "tracer", "ns": "tracer",
        "repo": "oci://ghcr.io/lerianstudio/tracer-helm",
        "version_env": "TRACER_VERSION",
        "needs": ["pg"], "order": 2,
    },
    "fetcher": {
        "enable": "ENABLE_FETCHER",
        "release": "fetcher", "ns": "fetcher-mt",
        # There IS a real fetcher-helm chart (LerianStudio/helm charts/fetcher, its
        # own manager/worker/common structure) — the render targets it. gitops staging
        # pins helm-internal/flowker-helm:1.0.0 for fetcher; CONFIRM which chart with
        # the team before release (repo/version below assume the public fetcher-helm).
        "repo": "oci://ghcr.io/lerianstudio/fetcher-helm",
        "version_env": "FETCHER_VERSION",
        "needs": ["mongo", "redis", "mq", "s3"], "order": 2,
    },
    "reporter": {
        "enable": "ENABLE_REPORTER",
        "release": "reporter", "ns": "reporter",
        "repo": "oci://ghcr.io/lerianstudio/reporter-helm",
        "version_env": "REPORTER_VERSION",
        "needs": ["mongo", "redis", "mq", "s3"], "order": 3,
    },
    "fees": {
        "enable": "ENABLE_FEES",
        "release": "plugin-fees", "ns": "plugin-fees",
        "repo": "oci://ghcr.io/lerianstudio/plugin-fees-helm",
        "version_env": "FEES_VERSION",
        "needs": ["mongo"], "order": 3,
    },
    "bank_transfer": {
        "enable": "ENABLE_BANK_TRANSFER",
        "release": "plugin-br-bank-transfer", "ns": "plugin-br-bank-transfer-mt",
        # TODO(plan 4.2): version pinned 1.1.0-beta.4 vs comments citing 2.0.0-beta.x — confirm.
        "repo": "oci://ghcr.io/lerianstudio/plugin-br-bank-transfer-helm",
        "version_env": "BANK_TRANSFER_VERSION",
        "needs": ["pg", "redis"], "order": 3,
    },
    "console": {
        "enable": "ENABLE_CONSOLE",
        "release": "product-console", "ns": "product-console",
        "repo": "oci://ghcr.io/lerianstudio/product-console-helm",
        "version_env": "CONSOLE_VERSION",
        "needs": ["mongo"], "order": 4,
    },
}

# In-cluster service base URLs (single-tenant, per-app namespaces above).
AUTH_URL = "http://plugin-access-manager-auth.plugin-access-manager.svc.cluster.local:4000"
IDENTITY_URL = "http://plugin-access-manager-identity.plugin-access-manager.svc.cluster.local:4001"
LEDGER_URL = "http://midaz-ledger.midaz-mt.svc.cluster.local:3002"
CRM_URL = "http://midaz-crm.midaz-mt.svc.cluster.local:4003"
REPORTER_URL = "http://reporter-manager.reporter.svc.cluster.local:4005"
FETCHER_URL = "http://fetcher-manager.fetcher-mt.svc.cluster.local:4006"
FEES_URL = "http://plugin-fees.plugin-fees.svc.cluster.local:4002"

DOCDB_PARAMS = ("tls=true&tlsInsecure=true&replicaSet=rs0&readPreference=secondaryPreferred"
                "&retryWrites=false&connectTimeoutMS=10000&serverSelectionTimeoutMS=10000")

# =====================================================================
# CloudFormation response
# =====================================================================
def send_response(event, context, status, data=None, reason=None):
    body = {
        'Status': status,
        'Reason': reason or f'See CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': event.get('PhysicalResourceId', context.log_stream_name),
        'StackId': event['StackId'], 'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'], 'Data': data or {},
    }
    raw = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(event['ResponseURL'], data=raw, method='PUT')
    req.add_header('Content-Type', '')
    req.add_header('Content-Length', str(len(raw)))
    try:
        urllib.request.urlopen(req)
        logger.info(f"Response sent: {status}")
    except Exception as e:
        logger.error(f"Failed to send response: {e}")

# =====================================================================
# Tooling / cluster access
# =====================================================================
def run(cmd, check=True, env=None, input_text=None):
    logger.info("Running: " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, env=env or os.environ,
                       input=input_text)
    if r.stdout:
        logger.info(r.stdout[-4000:])
    if r.returncode != 0:
        logger.error(r.stderr[-4000:])
        if check:
            raise Exception(f"Command failed: {' '.join(cmd)}: {r.stderr[-500:]}")
    return r.stdout

# Self-contained git for the Lambda runtime (python3.11 base ships no git).
# lambci/git-lambda-layer bundles git + ssh + their shared libs, built for
# the Amazon Linux Lambda environment. Pinned + overridable; the exact asset
# is confirmed on the first sandbox deploy (plan Phase 1.5).
GIT_LAYER_URL_DEFAULT = ("https://github.com/lambci/git-lambda-layer/releases/"
                         "download/build.11/git-lambda-layer.zip")

def install_git(tmp):
    layer = f'{tmp}/git-layer'
    gitbin = f'{layer}/bin/git'
    if not os.path.exists(gitbin):
        url = os.environ.get('GIT_LAYER_URL', GIT_LAYER_URL_DEFAULT)
        archive = f'{tmp}/git-layer.zip'
        urllib.request.urlretrieve(url, archive)
        os.makedirs(layer, exist_ok=True)
        # The layer is a zip; extract with the stdlib (no unzip binary either).
        import zipfile
        with zipfile.ZipFile(archive) as z:
            z.extractall(layer)
        for root, _, files in os.walk(f'{layer}/bin'):
            for fn in files:
                p = os.path.join(root, fn)
                os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    # Wire git's runtime layout: exec-path (git-core), templates, shared libs, ssh.
    os.environ['PATH'] = f"{layer}/bin:{os.environ.get('PATH', '')}"
    os.environ['GIT_EXEC_PATH'] = f'{layer}/libexec/git-core'
    os.environ['GIT_TEMPLATE_DIR'] = f'{layer}/share/git-core/templates'
    os.environ['LD_LIBRARY_PATH'] = f"{layer}/lib:{os.environ.get('LD_LIBRARY_PATH', '')}"
    # Fail fast with a clear message instead of a confusing subprocess error.
    if not os.path.exists(gitbin):
        raise Exception("GitOps mode requires git; layer download/extract failed. "
                        "Set GIT_LAYER_URL to a valid git-lambda-layer asset.")

def install_tools(need_git=False):
    tmp = '/tmp'
    os.environ['HOME'] = tmp
    for d in ('cache', 'config', 'data'):
        os.makedirs(f'{tmp}/.helm/{d}', exist_ok=True)
    os.environ['HELM_CACHE_HOME'] = f'{tmp}/.helm/cache'
    os.environ['HELM_CONFIG_HOME'] = f'{tmp}/.helm/config'
    os.environ['HELM_DATA_HOME'] = f'{tmp}/.helm/data'
    kubectl = f'{tmp}/kubectl'
    if not os.path.exists(kubectl):
        urllib.request.urlretrieve(
            'https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl', kubectl)
        os.chmod(kubectl, os.stat(kubectl).st_mode | stat.S_IEXEC)
    helm = f'{tmp}/helm'
    if not os.path.exists(helm):
        tgz = f'{tmp}/helm.tar.gz'
        urllib.request.urlretrieve('https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz', tgz)
        with tarfile.open(tgz, 'r:gz') as t:
            t.extractall(tmp)
        os.rename(f'{tmp}/linux-amd64/helm', helm)
        os.chmod(helm, os.stat(helm).st_mode | stat.S_IEXEC)
    os.environ['PATH'] = f"{tmp}:{os.environ.get('PATH', '')}"
    if need_git:
        install_git(tmp)

def eks_token(cluster_name):
    from botocore.signers import RequestSigner
    from botocore.model import ServiceId
    sess = boto3.Session()
    region = sess.region_name
    signer = RequestSigner(ServiceId('sts'), region, 'sts', 'v4',
                           sess.get_credentials(), sess.events)
    url = signer.generate_presigned_url(
        {'method': 'GET',
         'url': f'https://sts.{region}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15',
         'body': {}, 'headers': {'x-k8s-aws-id': cluster_name}, 'context': {}},
        region_name=region, expires_in=60, operation_name='')
    return 'k8s-aws-v1.' + base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')

def setup_kubeconfig():
    name = os.environ['CLUSTER_NAME']
    c = boto3.client('eks').describe_cluster(name=name)['cluster']
    kubeconfig = f'''apiVersion: v1
kind: Config
clusters:
- name: {name}
  cluster:
    server: {c['endpoint']}
    certificate-authority-data: {c['certificateAuthority']['data']}
contexts:
- name: {name}
  context:
    cluster: {name}
    user: aws
current-context: {name}
users:
- name: aws
  user:
    token: {eks_token(name)}
'''
    path = '/tmp/kubeconfig'
    with open(path, 'w') as f:
        f.write(kubeconfig)
    os.environ['KUBECONFIG'] = path

def get_secret(arn):
    # Tolerant of empty ARN (dedicated topology: an app may not use every
    # data service, so its unused secret ARNs arrive empty).
    if not arn:
        return {}
    return json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=arn)['SecretString'])

def get_redis_password():
    arn = os.environ.get('ELASTICACHE_SECRET_ARN', '')
    if not arn:
        return ''
    try:
        return boto3.client('secretsmanager').get_secret_value(SecretId=arn)['SecretString']
    except Exception as e:
        logger.warning(f"ElastiCache secret fetch failed: {e}")
        return ''

_CA_CACHE = {}
def get_aws_ca_cert_base64():
    # Amazon Root CA 1, base64'd — the public root that ElastiCache (Valkey/Redis)
    # in-transit-encryption certs chain to. Used for REDIS_CA_CERT (the apps REQUIRE
    # an explicit CA when REDIS_TLS=true and reject the RDS bundle / empty). ~1.2KB,
    # well under Linux MAX_ARG_STRLEN so it's safe as an env var (see the exec-arg
    # incident with the 160KB global RDS bundle). RDS/DocDB use sslmode=require /
    # tlsInsecure so they don't need a verified CA here.
    if 'v' in _CA_CACHE:
        return _CA_CACHE['v']
    url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            _CA_CACHE['v'] = base64.b64encode(r.read()).decode()
    except Exception as e:
        logger.warning(f"CA cert fetch failed: {e}")
        _CA_CACHE['v'] = ""
    return _CA_CACHE['v']

_MSK_CACHE = {}
def get_msk_brokers():
    # MSK (streaming backbone). AWS::MSK::Cluster exposes no bootstrap-broker
    # attribute, so resolve them from the cluster ARN at deploy time. Returns the
    # SASL/SCRAM broker string, or "" when MSK is not provisioned (streaming off).
    arn = os.environ.get('MSK_CLUSTER_ARN', '')
    if not arn:
        return ""
    if 'v' in _MSK_CACHE:
        return _MSK_CACHE['v']
    try:
        _MSK_CACHE['v'] = boto3.client('kafka').get_bootstrap_brokers(
            ClusterArn=arn).get('BootstrapBrokerStringSaslScram', '')
    except Exception as e:
        logger.warning(f"MSK bootstrap brokers fetch failed: {e}")
        _MSK_CACHE['v'] = ""
    return _MSK_CACHE['v']

# Per-app runtime Secret key sets. Contract mirrors the proven core-bank
# deployer (chart-specific keys), adapted to standalone (single-tenant) charts.
# Keys marked (validate) are best-effort for modules core-bank did not cover
# and are confirmed against each chart in the sandbox deploy (plan Phase 1.5).
def secret_data(app):
    rds = get_secret(os.environ['RDS_SECRET_ARN'])
    docdb = get_secret(os.environ['DOCUMENTDB_SECRET_ARN'])
    mq = get_secret(os.environ['AMAZONMQ_SECRET_ARN'])
    redis_pw = get_redis_password()
    pg = rds.get('password', '')
    mongo = docdb.get('password', '')
    mqp = mq.get('password', '')
    mqu = mq.get('username', '')
    if app == "access_manager":            # casdoor (validate exact keys)
        return {"DB_PASSWORD": pg, "POSTGRES_PASSWORD": pg, "REDIS_PASSWORD": redis_pw}
    if app == "ledger":                    # midaz-helm
        return {
            "DB_ONBOARDING_PASSWORD": pg, "DB_ONBOARDING_REPLICA_PASSWORD": pg,
            "DB_TRANSACTION_PASSWORD": pg, "DB_TRANSACTION_REPLICA_PASSWORD": pg,
            "MONGO_ONBOARDING_PASSWORD": mongo, "MONGO_TRANSACTION_PASSWORD": mongo,
            "RABBITMQ_DEFAULT_PASS": mqp, "RABBITMQ_CONSUMER_PASS": mqp,
            "REDIS_PASSWORD": redis_pw,
        }
    if app == "tracer":
        return {"DB_PASSWORD": pg}
    if app == "reporter":
        return {
            "MONGO_PASSWORD": mongo, "REDIS_PASSWORD": redis_pw,
            "RABBITMQ_DEFAULT_USER": mqu, "RABBITMQ_DEFAULT_PASS": mqp,
            "RABBITMQ_ADMIN_USER": mqu, "RABBITMQ_ADMIN_PASS": mqp,
            "DATASOURCE_ONBOARDING_PASSWORD": pg,
            "OBJECT_STORAGE_ACCESS_KEY_ID": "", "OBJECT_STORAGE_SECRET_KEY": "",
            "APP_ENC_KEY": "",
        }
    if app == "fetcher":
        return {
            "MONGO_PASSWORD": mongo, "REDIS_PASSWORD": redis_pw,
            "RABBITMQ_DEFAULT_USER": mqu, "RABBITMQ_DEFAULT_PASS": mqp,
            "OBJECT_STORAGE_ACCESS_KEY_ID": "", "OBJECT_STORAGE_SECRET_KEY": "",
        }
    if app == "fees":
        return {"MONGO_PASSWORD": mongo}
    if app == "bank_transfer":             # (validate)
        return {"POSTGRES_PASSWORD": pg, "MONGO_PASSWORD": mongo, "REDIS_PASSWORD": redis_pw}
    if app == "console":
        return {"NEXTAUTH_SECRET": secrets.token_hex(32), "MONGO_PASSWORD": mongo}
    return {}

def enabled(app):
    return os.environ.get(REGISTRY[app]['enable'], 'false').lower() == 'true'

def selected_apps():
    only = os.environ.get('ONLY_APP', '').strip()
    if only:
        # Dedicated topology: deploy exactly this app (its stack already
        # gated on Enable<app> at the CloudFormation level).
        return [only] if only in REGISTRY else []
    apps = [a for a in REGISTRY if enabled(a)]
    return sorted(apps, key=lambda a: REGISTRY[a]['order'])

# =====================================================================
# Values rendering (single-tenant). Common connection block + per-app.
# Returns a YAML string. MULTI_TENANT is always disabled.
# =====================================================================
def host_only(endpoint):
    e = endpoint.split('://')[-1]
    return e.split(':')[0]

def render_values(app):
    rds = host_only(os.environ['RDS_ENDPOINT'])
    rds_rep = host_only(os.environ.get('RDS_REPLICA_ENDPOINT') or os.environ['RDS_ENDPOINT'])
    docdb = host_only(os.environ['DOCUMENTDB_ENDPOINT'])
    redis = host_only(os.environ['ELASTICACHE_ENDPOINT'])
    mq_host = host_only(os.environ['AMAZONMQ_ENDPOINT'])
    region = os.environ.get('AWS_DEFAULT_REGION', 'sa-east-1')
    replicas = os.environ.get('REPLICA_COUNT', '2')
    # Tolerant: in dedicated topology an app may not use every data service.
    docdb_user = get_secret(os.environ.get('DOCUMENTDB_SECRET_ARN', '')).get('username', '')
    mq_user = get_secret(os.environ.get('AMAZONMQ_SECRET_ARN', '')).get('username', '')
    rds_user = get_secret(os.environ.get('RDS_SECRET_ARN', '')).get('username', '')
    ca = get_aws_ca_cert_base64()
    msk_brokers = get_msk_brokers()
    msk_user = get_secret(os.environ.get('MSK_SECRET_ARN', '')).get('username', '')
    rel = REGISTRY[app]['release']
    sec = f"{rel}-secrets"

    if app == "access_manager":
        # Structure matches the real plugin-access-manager chart (auth + identity
        # components, common.authorizer, subcharts auth-database/valkey OFF for
        # managed RDS/ElastiCache). Secrets via useExistingSecret (created by
        # create_runtime_secret). Uses the RDS master user so Casdoor can create
        # its "casdoor" database on first boot.
        rel = REGISTRY[app]['release']
        rds_user = get_secret(os.environ.get('RDS_SECRET_ARN', '')).get('username', '')
        authz_id = os.environ.get('AUTHORIZER_CLIENT_ID', 'ac56c81d4d6d95c0ac12')
        return f'''
global:
  multiTenant:
    enabled: false
common:
  authorizer:
    clientId: "{authz_id}"
auth-database:
  enabled: false
valkey:
  enabled: false
identity:
  useExistingSecret: true
  existingSecretName: "{rel}-identity"
  configmap:
    ENV_NAME: "production"
    ALLOW_INSECURE_TLS: "true"
    AUTH_ENABLED: "true"
    AUTH_PORT: "4000"
    AUTH_ADDRESS: "http://{rel}-auth:4000"
    AUTHORIZER_CLIENT_ID: "{authz_id}"
    REDIS_HOST: "{host_only(redis)}"
    REDIS_PORT: "6379"
    REDIS_USER: "default"
    REDIS_TLS: "true"
    REDIS_CA_CERT: "{ca}"
    MULTI_TENANT_ENABLED: "false"
auth:
  useExistingSecret: true
  existingSecretName: "{rel}-auth"
  initUser:
    enabled: true
    useExistingSecret: true
    adminPasswordSecretName: "{rel}-admin"
    adminPasswordSecretKey: "ADMIN_PASSWORD"
    adminEmail: "admin@lerian.local"
    adminDisplayName: "Administrator"
  configmap:
    ENV_NAME: "production"
    ALLOW_INSECURE_TLS: "true"
    DB_HOST: "{host_only(rds)}"
    DB_PORT: "5432"
    DB_NAME: "casdoor"
    DB_USER: "{rds_user}"
    DB_SSLMODE: "require"
    REDIS_HOST: "{host_only(redis)}"
    REDIS_PORT: "6379"
    REDIS_USER: "default"
    REDIS_TLS: "true"
    REDIS_CA_CERT: "{ca}"
    AUTHORIZER_CLIENT_ID: "{authz_id}"
    MULTI_TENANT_ENABLED: "false"
'''
    if app == "ledger":
        # Real midaz-helm structure: unified ledger.* (onboarding+transaction),
        # crm.* (enabled — console/bank-transfer call it). Subcharts OFF; RDS DBs
        # bootstrapped via global.externalPostgresDefinitions (role midaz). Mongo
        # uses the DocDB master user (auto-creates DBs); RabbitMQ uses the AmazonMQ
        # admin user for both default/consumer (single-tenant bundle simplification).
        return f'''
global:
  multiTenant:
    enabled: false
  externalPostgresDefinitions:
    enabled: true
    connection:
      host: "{rds}"
      port: "5432"
    postgresAdminLogin:
      useExistingSecret:
        name: "{sec}"
    midazCredentials:
      useExistingSecret:
        name: "{sec}"
postgresql:
  enabled: false
mongodb:
  enabled: false
valkey:
  enabled: false
rabbitmq:
  enabled: false
grafana:
  enabled: false
otel-collector-lerian:
  enabled: false
ledger:
  enabled: true
  replicaCount: {replicas}
  useExistingSecret: true
  existingSecretName: "{sec}"
  configmap:
    ENV_NAME: "production"
    DB_ONBOARDING_HOST: "{rds}"
    DB_ONBOARDING_PORT: "5432"
    DB_ONBOARDING_USER: "midaz"
    DB_ONBOARDING_NAME: "onboarding"
    DB_ONBOARDING_SSLMODE: "require"
    DB_ONBOARDING_REPLICA_HOST: "{rds_rep}"
    DB_ONBOARDING_REPLICA_PORT: "5432"
    DB_ONBOARDING_REPLICA_USER: "midaz"
    DB_ONBOARDING_REPLICA_NAME: "onboarding"
    DB_ONBOARDING_REPLICA_SSLMODE: "require"
    DB_TRANSACTION_HOST: "{rds}"
    DB_TRANSACTION_PORT: "5432"
    DB_TRANSACTION_USER: "midaz"
    DB_TRANSACTION_NAME: "transaction"
    DB_TRANSACTION_SSLMODE: "require"
    DB_TRANSACTION_REPLICA_HOST: "{rds_rep}"
    DB_TRANSACTION_REPLICA_PORT: "5432"
    DB_TRANSACTION_REPLICA_USER: "midaz"
    DB_TRANSACTION_REPLICA_NAME: "transaction"
    DB_TRANSACTION_REPLICA_SSLMODE: "require"
    MONGO_ONBOARDING_URI: "mongodb"
    MONGO_ONBOARDING_HOST: "{docdb}"
    MONGO_ONBOARDING_PORT: "27017"
    MONGO_ONBOARDING_USER: "{docdb_user}"
    MONGO_ONBOARDING_NAME: "onboarding"
    MONGO_ONBOARDING_PARAMETERS: "{DOCDB_PARAMS}"
    MONGO_TRANSACTION_URI: "mongodb"
    MONGO_TRANSACTION_HOST: "{docdb}"
    MONGO_TRANSACTION_PORT: "27017"
    MONGO_TRANSACTION_USER: "{docdb_user}"
    MONGO_TRANSACTION_NAME: "transaction"
    MONGO_TRANSACTION_PARAMETERS: "{DOCDB_PARAMS}"
    REDIS_HOST: "{redis}:6379"
    REDIS_TLS: "true"
    REDIS_CA_CERT: "{ca}"
    RABBITMQ_URI: "amqps"
    RABBITMQ_PROTOCOL: "https"
    RABBITMQ_HOST: "{mq_host}"
    RABBITMQ_PORT_HOST: "5671"
    RABBITMQ_PORT_AMQP: "15671"
    RABBITMQ_DEFAULT_USER: "{mq_user}"
    RABBITMQ_CONSUMER_USER: "{mq_user}"
    PLUGIN_AUTH_ENABLED: "true"
    PLUGIN_AUTH_HOST: "{AUTH_URL}"
    MULTI_TENANT_ENABLED: "false"
crm:
  enabled: true
  replicaCount: {replicas}
  useExistingSecret: true
  existingSecretName: "{rel}-crm-secrets"
  configmap:
    ENV_NAME: "production"
    MONGO_URI: "mongodb"
    MONGO_HOST: "{docdb}"
    MONGO_PORT: "27017"
    MONGO_USER: "{docdb_user}"
    MONGO_NAME: "crm"
    MONGO_PARAMETERS: "{DOCDB_PARAMS}"
    PLUGIN_AUTH_ENABLED: "true"
    PLUGIN_AUTH_ADDRESS: "{AUTH_URL}"
    MULTI_TENANT_ENABLED: "false"
'''
    if app == "tracer":
        # Single-service chart (no subcharts). RDS role+db `tracer` bootstrapped
        # via global.externalPostgresDefinitions. ENV_NAME is mandatory (lib-commons
        # fails fast without it). No Redis single-tenant.
        return f'''
global:
  externalPostgresDefinitions:
    enabled: true
    connection:
      host: "{rds}"
      port: "5432"
    postgresAdminLogin:
      useExistingSecret:
        name: "{sec}"
    tracerCredentials:
      useExistingSecret:
        name: "{sec}"
tracer:
  useExistingSecret: true
  existingSecretName: "{sec}"
  # Chart defaults set BOTH pdb.minAvailable and pdb.maxUnavailable, which is an
  # invalid PodDisruptionBudget. Null out maxUnavailable, keeping minAvailable: 1.
  pdb:
    maxUnavailable: null
  configmap:
    ENV_NAME: "production"
    DB_HOST: "{rds}"
    DB_PORT: "5432"
    DB_NAME: "tracer"
    DB_USER: "tracer"
    DB_SSL_MODE: "require"
    PLUGIN_AUTH_ENABLED: "true"
    PLUGIN_AUTH_ADDRESS: "{AUTH_URL}"
    API_KEY_ENABLED: "false"
    MULTI_TENANT_ENABLED: "false"
'''
    if app == "reporter":
        bucket = os.environ.get('REPORTER_S3_BUCKET', '')
        # IRSA role granting the reporter SAs access to the S3 storage bucket.
        s3_role_arn = os.environ.get('REPORTER_S3_ROLE_ARN', '')
        return f'''
# common.configmap feeds both manager & worker; per-component useExistingSecret.
# KEDA off → worker is a plain Deployment. DATASOURCE_ONBOARDING_* points at the
# ledger's onboarding Postgres (reporter reads it). Mongo uses the DocDB master
# user; MONGO_PASSWORD placeholder gates the env (real value from the Secret).
global:
  multiTenant:
    enabled: false
mongodb:
  enabled: false
rabbitmq:
  enabled: false
valkey:
  enabled: false
seaweedfs:
  enabled: false
keda:
  enabled: false
  external: false
otel-collector-lerian:
  enabled: false
# External broker (AmazonMQ): no rabbitmq subchart to preload definitions, so
# the worker's passive queue declare 404s. This Job applies the reporter
# exchange/queue/DLQ topology via the AmazonMQ management API (HTTPS:443).
externalRabbitmqDefinitions:
  enabled: true
  connection:
    protocol: "https"
    host: "{mq_host}"
    port: "443"
    portAmqp: "5671"
  rabbitmqAdminLogin:
    useExistingSecret:
      name: "{sec}"
  appCredentials:
    useExistingSecret:
      name: "{sec}"
secrets:
  MONGO_PASSWORD: "placeholder"
common:
  configmap:
    MONGO_URI: "mongodb"
    MONGO_HOST: "{docdb}"
    MONGO_PORT: "27017"
    MONGO_NAME: "reporter"
    MONGO_USER: "{docdb_user}"
    MONGO_PARAMETERS: "{DOCDB_PARAMS}"
    REDIS_HOST: "{redis}:6379"
    REDIS_TLS: "true"
    REDIS_CA_CERT: "{ca}"
    REDIS_PROTOCOL: "3"
    RABBITMQ_URI: "amqps"
    RABBITMQ_HOST: "{mq_host}"
    # AmazonMQ RabbitMQ: amqps broker = 5671, management HTTPS = 15671.
    # The app dials AMQP on PORT_AMQP, so that must be the broker port (5671).
    RABBITMQ_PORT_HOST: "15671"
    RABBITMQ_PORT_AMQP: "5671"
    # No OTEL collector in the managed bundle; telemetry export fails and
    # lib-commons v4 asserts on shutdown. Disable until observability is deployed.
    ENABLE_TELEMETRY: "false"
    RABBITMQ_EXCHANGE: "reporter.generate-report.exchange"
    RABBITMQ_GENERATE_REPORT_QUEUE: "reporter.generate-report.queue"
    # Readiness (/ready) probes the RabbitMQ management API; the chart default
    # points at the in-cluster subchart host (reporter-rabbitmq:15672) which does
    # not exist with external AmazonMQ -> /ready 503. Point at the broker console
    # (same host the bootstrap Job used, HTTPS:443).
    RABBITMQ_HEALTH_CHECK_URL: "https://{mq_host}"
    # App v1.2.0 validates these (ranges 1-10000/1-1000/1-5000); the chart
    # configmap ships only RATE_LIMIT_MAX, so provide them explicitly.
    RATE_LIMIT_GLOBAL: "1000"
    RATE_LIMIT_EXPORT: "100"
    RATE_LIMIT_DISPATCH: "500"
    # Empty endpoint -> AWS SDK uses the real regional S3 endpoint. The chart
    # default points at the in-cluster seaweedfs (disabled) and the manager's
    # readiness storage check fails. S3 auth comes from the SA's IRSA role.
    OBJECT_STORAGE_ENDPOINT: ""
    OBJECT_STORAGE_BUCKET: "{bucket}"
    OBJECT_STORAGE_REGION: "{region}"
    OBJECT_STORAGE_USE_PATH_STYLE: "false"
    OBJECT_STORAGE_DISABLE_SSL: "false"
    DATASOURCE_ONBOARDING_TYPE: "postgresql"
    DATASOURCE_ONBOARDING_HOST: "{rds}"
    DATASOURCE_ONBOARDING_PORT: "5432"
    DATASOURCE_ONBOARDING_USER: "midaz"
    DATASOURCE_ONBOARDING_DATABASE: "onboarding"
    DATASOURCE_ONBOARDING_SSLMODE: "require"
    # Reporter runs standalone reading the ledger's onboarding Postgres.
    # The reporter->fetcher integration needs a dedicated fetcher data-storage
    # bucket + encryption key not exposed by this chart version; enabling it
    # fails worker init with "fetcher data storage: bucket name is required".
    # Keep decoupled until that wiring is added.
    FETCHER_ENABLED: "false"
    MULTI_TENANT_ENABLED: "false"
manager:
  useExistingSecret: true
  existingSecretName: "{sec}"
  # IRSA: SA assumes the S3 role for report storage access.
  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: "{s3_role_arn}"
  # Health server exposes /health and /ready (NOT /readyz); default probe
  # path /readyz 404s and the pod never becomes Ready.
  readinessProbe:
    path: "/ready"
  configmap:
    PLUGIN_AUTH_ENABLED: "true"
    PLUGIN_AUTH_ADDRESS: "{AUTH_URL}"
worker:
  useExistingSecret: true
  existingSecretName: "{sec}"
  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: "{s3_role_arn}"
  # Worker health server exposes /health and /ready (NOT /readyz); the chart's
  # default readiness path /readyz 404s and the pod never becomes Ready.
  readinessProbe:
    path: "/ready"
'''
    if app == "fetcher":
        # Real fetcher-helm chart (manager/worker/common). Subcharts OFF; S3 via
        # STORAGE_PROVIDER=s3. Per-component useExistingSecret. The chart's top-level
        # `secrets:` block is inert — real creds go in the per-component Secret.
        bucket = os.environ.get('FETCHER_S3_BUCKET', '')
        s3_role_arn = os.environ.get('FETCHER_S3_ROLE_ARN', '')
        return f'''
global:
  multiTenant:
    enabled: false
mongodb:
  enabled: false
rabbitmq:
  enabled: false
valkey:
  enabled: false
seaweedfs:
  enabled: false
keda:
  enabled: false
# External AmazonMQ has no preloaded topology; the worker's passive queue declare
# 404s. This Job applies the fetcher exchange/queue definitions via the AmazonMQ
# management API (HTTPS:443), same pattern as the reporter.
externalRabbitmqDefinitions:
  enabled: true
  connection:
    protocol: "https"
    host: "{mq_host}"
    port: "443"
    portAmqp: "5671"
  rabbitmqAdminLogin:
    useExistingSecret:
      name: "{sec}"
  appCredentials:
    useExistingSecret:
      name: "{sec}"
common:
  configmap:
    MONGO_URI: "mongodb"
    MONGO_HOST: "{docdb}"
    MONGO_PORT: "27017"
    MONGO_NAME: "fetcher-db"
    MONGO_PARAMETERS: "{DOCDB_PARAMS}"
    RABBITMQ_URI: "amqps"
    RABBITMQ_HOST: "{mq_host}"
    # AmazonMQ amqps broker port = 5671 (15671 is the mgmt console -> EOF on amqp).
    RABBITMQ_PORT_HOST: "5671"
    RABBITMQ_PORT_AMQP: "5671"
    REDIS_HOST: "{redis}"
    REDIS_PORT: "6379"
    REDIS_DB: "0"
    # ElastiCache enforces in-transit TLS; app rejects plaintext ("TLS required").
    REDIS_TLS: "true"
    REDIS_CA_CERT: "{ca}"
    REDIS_PROTOCOL: "3"
    MULTI_TENANT_ENABLED: "false"
manager:
  useExistingSecret: true
  existingSecretName: "{sec}"
  configmap:
    PLUGIN_AUTH_ENABLED: "true"
    PLUGIN_AUTH_ADDRESS: "{AUTH_URL}"
worker:
  useExistingSecret: true
  existingSecretName: "{sec}"
  # IRSA: SA assumes the S3 role for extracted-data storage access.
  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: "{s3_role_arn}"
  configmap:
    STORAGE_PROVIDER: "s3"
    OBJECT_STORAGE_REGION: "{region}"
    OBJECT_STORAGE_BUCKET: "{bucket}"
    OBJECT_STORAGE_USE_PATH_STYLE: "false"
    # Worker mandates streaming for job-event notifications. Backed by MSK
    # (Kafka) over SASL/SCRAM-SHA-512 + TLS. Password is in the Secret.
    STREAMING_ENABLED: "true"
    STREAMING_BROKERS: "{msk_brokers}"
    STREAMING_CLOUDEVENTS_SOURCE: "//lerian.fetcher/worker"
    STREAMING_TLS_ENABLED: "true"
    STREAMING_TLS_CA_CERT: "{ca}"
    STREAMING_SASL_MECHANISM: "SCRAM-SHA-512"
    STREAMING_SASL_USERNAME: "{msk_user}"
'''
    if app == "fees":
        # Real chart: fees.* nesting; mongodb subchart OFF + external; otel off.
        # M2M via CLIENT_ID (configmap, = authorizer) + CLIENT_SECRET (secret,
        # REQUIRED). MONGO_HOST must be set explicitly. Mongo uses DocDB master user.
        authz_id = os.environ.get('AUTHORIZER_CLIENT_ID', 'ac56c81d4d6d95c0ac12')
        return f'''
global:
  multiTenant:
    enabled: false
mongodb:
  enabled: false
  external: true
# The fees app fatals ("collector exporter endpoint cannot be empty when
# telemetry is enabled") with no telemetry-disable env, so keep the chart's
# bundled OTEL collector (accepts OTLP locally) to satisfy the endpoint.
otel-collector-lerian:
  enabled: true
# UI frontend image (plugin-fees-frontend) is private (ghcr 401) and the
# Console provides the platform UI; disable the standalone fees UI.
frontend:
  enabled: false
fees:
  useExistingSecret: true
  existingSecretName: "{sec}"
  replicaCount: {replicas}
  # App serves /health and /ready (NOT /readyz); default probe path 404s.
  readinessProbe:
    path: "/ready"
  configmap:
    ENV_NAME: "production"
    MIDAZ_TRANSACTION_URL: "{LEDGER_URL}/v1/"
    MIDAZ_ONBOARDING_URL: "{LEDGER_URL}/v1/"
    MONGO_URI: "mongodb"
    MONGO_HOST: "{docdb}"
    MONGO_PORT: "27017"
    MONGO_NAME: "plugin-fees-db"
    MONGO_USER: "{docdb_user}"
    MONGO_PARAMETERS: "{DOCDB_PARAMS}"
    PLUGIN_AUTH_ENABLED: "true"
    PLUGIN_AUTH_ADDRESS: "{AUTH_URL}"
    CLIENT_ID: "{authz_id}"
    MULTI_TENANT_ENABLED: "false"
'''
    if app == "bank_transfer":
        # Structure matches the real plugin-br-bank-transfer chart: everything under
        # bankTransfer.*, bundled subcharts OFF (managed RDS/DocDB/ElastiCache), and
        # global.externalPostgresDefinitions bootstraps the bank_transfer DB+role on
        # the shared RDS (admin+role creds sourced from the injected Secret). With
        # useExistingSecret the chart loads that Secret via envFrom (M2M creds, URI-
        # only Mongo, AES keys all come from it — see create_runtime_secret).
        org = os.environ.get('ACCESS_MANAGER_ORGANIZATION_IDS', '')
        return f'''
global:
  multiTenant:
    enabled: false
  externalPostgresDefinitions:
    enabled: true
    connection:
      host: "{host_only(rds)}"
      port: "5432"
    postgresAdminLogin:
      useExistingSecret:
        name: "{sec}"
    bankTransferCredentials:
      useExistingSecret:
        name: "{sec}"
postgresql:
  enabled: false
mongodb:
  enabled: false
valkey:
  enabled: false
rabbitmq:
  enabled: false
bankTransfer:
  useExistingSecret: true
  existingSecretName: "{sec}"
  replicaCount: {replicas}
  migrations:
    enabled: true
  configmap:
    # Brazil-rails plugin: without real JD partner credentials it must run in
    # sandbox mode, which production disallows (JD_SANDBOX_MODE / license / org
    # are all hard-asserted in production). Ship as "development" until the JD
    # rail + a production license are wired for the customer.
    ENV_NAME: "development"
    ORGANIZATION_IDS: "{org}"
    ALLOW_INSECURE_TLS: "true"
    POSTGRES_HOST: "{host_only(rds)}"
    POSTGRES_PORT: "5432"
    POSTGRES_DB: "bank_transfer"
    POSTGRES_USER: "bank_transfer"
    POSTGRES_SSLMODE: "require"
    MONGO_ENABLED: "true"
    MONGO_DATABASE: "bank-transfer-db"
    # Chart's wait-for-dependencies splits REDIS_HOST on ":" for host:port, so it
    # must carry the port (a bare host makes `cut -d: -f2` echo the host as the port).
    REDIS_HOST: "{host_only(redis)}:6379"
    REDIS_PORT: "6379"
    REDIS_USER: "default"
    REDIS_TLS: "true"
    REDIS_CA_CERT: "{ca}"
    REDIS_DB: "0"
    RABBITMQ_ENABLED: "false"
    MIDAZ_BASE_URL: "{LEDGER_URL}"
    MIDAZ_TRANSACTION_URL: "{LEDGER_URL}"
    MIDAZ_AUTH_ENABLED: "true"
    MIDAZ_AUTH_ADDRESS: "{AUTH_URL}"
    CRM_BASE_URL: "{CRM_URL}"
    CRM_AUTH_ENABLED: "true"
    FEES_BASE_URL: "{FEES_URL}"
    FEES_AUTH_ENABLED: "true"
    PLUGIN_AUTH_ENABLED: "true"
    PLUGIN_AUTH_ADDRESS: "{AUTH_URL}"
    MULTI_TENANT_ENABLED: "false"
    # JD (TED rail) is client-configured post-deploy; sandbox mode keeps the pod
    # bootable without a real JD endpoint. Set JD_BASE_URL + JD_SANDBOX_MODE=false
    # and JD_POLLING_ENABLED=true when the JD rail is wired.
    JD_SANDBOX_MODE: "true"
    JD_POLLING_ENABLED: "false"
'''
    if app == "console":
        # Real product-console chart: flat top-level configmap. Only Midaz/CRM/
        # Reporter/Auth/Identity have base-path envs (no fetcher/flowker/fees keys).
        # NEXTAUTH_SECRET + MONGODB_PASS in the Secret; telemetry OFF (render guard).
        nextauth = os.environ.get('NEXTAUTH_URL', '')
        authz_id = os.environ.get('AUTHORIZER_CLIENT_ID', 'ac56c81d4d6d95c0ac12')
        led_h, auth_h, id_h = host_only(LEDGER_URL), host_only(AUTH_URL), host_only(IDENTITY_URL)
        return f'''
useExistingSecret: true
existingSecretName: "{sec}"
mongodb:
  enabled: false
global:
  externalMongoDefinitions:
    enabled: false
otel:
  enabled: false
  external: false
configmap:
  NODE_ENV: "production"
  NEXTAUTH_URL: "{nextauth}"
  ENABLE_TELEMETRY: "false"
  MIDAZ_API_HOST: "{led_h}"
  MIDAZ_API_PORT: "3002"
  MIDAZ_BASE_PATH: "{LEDGER_URL}/v1"
  MIDAZ_TRANSACTION_BASE_HOST: "{led_h}"
  MIDAZ_TRANSACTION_BASE_PORT: "3002"
  MIDAZ_TRANSACTION_BASE_PATH: "{LEDGER_URL}/v1"
  CRM_BASE_PATH: "{CRM_URL}/v1"
  REPORTER_BASE_PATH: "{REPORTER_URL}/v1"
  PLUGIN_AUTH_ENABLED: "true"
  NEXT_PUBLIC_PLUGIN_AUTH_ENABLED: "true"
  PLUGIN_AUTH_CLIENT_ID: "{authz_id}"
  PLUGIN_AUTH_HOST: "{auth_h}"
  PLUGIN_AUTH_PORT: "4000"
  PLUGIN_AUTH_BASE_PATH: "{AUTH_URL}/v1"
  PLUGIN_IDENTITY_HOST: "{id_h}"
  PLUGIN_IDENTITY_PORT: "4001"
  PLUGIN_IDENTITY_BASE_PATH: "{IDENTITY_URL}/v1"
  MONGODB_URI: "mongodb"
  MONGO_HOST: "{docdb}"
  MONGO_PORT: "27017"
  MONGODB_DB_NAME: "product-console"
  MONGODB_USER: "{docdb_user}"
  MONGO_PARAMETERS: "{DOCDB_PARAMS}"
{ingress_block()}
'''
    return "{}\n"

def ingress_block():
    if os.environ.get('ENABLE_INGRESS', 'false').lower() != 'true':
        return "ingress:\n    enabled: false"
    host = os.environ.get('INGRESS_HOSTNAME', '')
    scheme = os.environ.get('INGRESS_SCHEME', 'internet-facing')
    cert = os.environ.get('INGRESS_CERTIFICATE_ARN', '')
    if not host:
        return "ingress:\n    enabled: false"
    ann = [
        "kubernetes.io/ingress.class: alb",
        f"alb.ingress.kubernetes.io/scheme: {scheme}",
        "alb.ingress.kubernetes.io/target-type: ip",
    ]
    if cert:
        ann.append("alb.ingress.kubernetes.io/listen-ports: '[{\"HTTP\": 80}, {\"HTTPS\": 443}]'")
        ann.append("alb.ingress.kubernetes.io/ssl-redirect: '443'")
        ann.append(f"alb.ingress.kubernetes.io/certificate-arn: {cert}")
    else:
        ann.append("alb.ingress.kubernetes.io/listen-ports: '[{\"HTTP\": 80}]'")
    ann_yaml = "\n".join("      " + a for a in ann)
    return (f"ingress:\n    enabled: true\n    className: alb\n    annotations:\n{ann_yaml}\n"
            f"    hosts:\n      - host: {host}\n        paths:\n          - path: /\n            pathType: Prefix")

# =====================================================================
# MODE 1 — helm install (self-contained, default)
# =====================================================================
def kubectl_apply(manifest):
    path = '/tmp/manifest.yaml'
    with open(path, 'w') as f:
        f.write(manifest)
    run(['kubectl', 'apply', '-f', path])

def ensure_ns(ns):
    run(['kubectl', 'create', 'namespace', ns], check=False)

def _secret_manifest(name, ns, data):
    lines = "\n".join(f'  {k}: "{v}"' for k, v in data.items())
    return (f"apiVersion: v1\nkind: Secret\n"
            f"metadata:\n  name: {name}\n  namespace: {ns}\n"
            f"type: Opaque\nstringData:\n{lines}\n")

def _existing_secret_data(ns, name):
    # Decoded stringData of an existing Secret ({} if absent) — used to keep
    # generated keys (encryption keys, admin password) stable across re-runs.
    out = run(['kubectl', '-n', ns, 'get', 'secret', name, '-o', 'json'], check=False)
    try:
        raw = (json.loads(out).get('data', {}) or {}) if out else {}
        return {k: base64.b64decode(v).decode() for k, v in raw.items()}
    except Exception:
        return {}

def _mongo_uri():
    docdb = get_secret(os.environ.get('DOCUMENTDB_SECRET_ARN', ''))
    du, dp = docdb.get('username', ''), docdb.get('password', '')
    dhost = host_only(os.environ.get('DOCUMENTDB_ENDPOINT', ''))
    return (f"mongodb://{du}:{urllib.parse.quote(dp, safe='')}@{dhost}:27017/"
            f"?{DOCDB_PARAMS}&authSource=admin")

def create_runtime_secret(app, ns, m2m=None):
    # Create the Secret(s) an app's chart consumes, keyed EXACTLY as the chart
    # expects (contracts verified against LerianStudio/helm). render_values wires
    # them via useExistingSecret/existingSecretName. m2m (optional) injects
    # <TARGET>_CLIENT_ID/SECRET into caller Secrets. Generated keys are store-once.
    rel = REGISTRY[app]['release']
    rds = get_secret(os.environ.get('RDS_SECRET_ARN', ''))
    docdb = get_secret(os.environ.get('DOCUMENTDB_SECRET_ARN', ''))
    mq = get_secret(os.environ.get('AMAZONMQ_SECRET_ARN', ''))
    pg_u, pg_p = rds.get('username', ''), rds.get('password', '')
    mo_p = docdb.get('password', '')
    mq_u, mq_p = mq.get('username', ''), mq.get('password', '')
    msk_p = get_secret(os.environ.get('MSK_SECRET_ARN', '')).get('password', '')
    redis_pw = get_redis_password()
    authz = os.environ.get('AUTHORIZER_CLIENT_SECRET', '')
    # Per-app license key: each licensed plugin validates its OWN Lerian license
    # (access_manager, fetcher, fees, bank_transfer). The customer supplies one
    # key per app via the <APP>_LICENSE_KEY inputs; unlicensed apps ignore it.
    lic = os.environ.get(f'{app.upper()}_LICENSE_KEY', '')
    org = os.environ.get('ACCESS_MANAGER_ORGANIZATION_IDS', '')
    prev = _existing_secret_data(ns, f"{rel}-secrets")
    def keep_hex(k, n=32):   # store-once hex key
        return prev.get(k) or secrets.token_hex(n)
    def keep_b64(k):         # store-once base64 32-byte key
        return prev.get(k) or base64.b64encode(secrets.token_bytes(32)).decode()

    if app == "access_manager":
        # TWO envFrom secrets (auth + identity, distinct keys) + initUser admin Secret.
        common = {"AUTHORIZER_CLIENT_SECRET": authz, "LICENSE_KEY": lic,
                  "ORGANIZATION_IDS": org, "REDIS_PASSWORD": redis_pw, "SD_TOKEN": ""}
        kubectl_apply(_secret_manifest(f"{rel}-auth", ns,
            {**common, "DB_PASSWORD": pg_p, "MFA_SECRET": ""}))
        kubectl_apply(_secret_manifest(f"{rel}-identity", ns, common))
        existing = run(['kubectl', '-n', ns, 'get', 'secret', f'{rel}-admin',
                        '-o', 'name'], check=False)
        if not (existing and existing.strip()):
            admin_pw = os.environ.get('CONSOLE_ADMIN_PASSWORD', '') or secrets.token_urlsafe(24)
            kubectl_apply(_secret_manifest(f"{rel}-admin", ns, {"ADMIN_PASSWORD": admin_pw}))
        return

    if app == "ledger":
        # ledger Secret + a separate crm Secret (LCRYPTO keys store-once).
        kubectl_apply(_secret_manifest(f"{rel}-secrets", ns, {
            "DB_ONBOARDING_PASSWORD": pg_p, "DB_ONBOARDING_REPLICA_PASSWORD": pg_p,
            "DB_TRANSACTION_PASSWORD": pg_p, "DB_TRANSACTION_REPLICA_PASSWORD": pg_p,
            "MONGO_ONBOARDING_PASSWORD": mo_p, "MONGO_TRANSACTION_PASSWORD": mo_p,
            "REDIS_PASSWORD": redis_pw,
            "RABBITMQ_DEFAULT_PASS": mq_p, "RABBITMQ_CONSUMER_PASS": mq_p,
            "DB_USER_ADMIN": pg_u, "DB_ADMIN_PASSWORD": pg_p, "DB_PASSWORD_MIDAZ": pg_p,
        }))
        cprev = _existing_secret_data(ns, f"{rel}-crm-secrets")
        kubectl_apply(_secret_manifest(f"{rel}-crm-secrets", ns, {
            "MONGO_PASSWORD": mo_p,
            "LCRYPTO_HASH_SECRET_KEY": cprev.get('LCRYPTO_HASH_SECRET_KEY') or secrets.token_hex(32),
            "LCRYPTO_ENCRYPT_SECRET_KEY": cprev.get('LCRYPTO_ENCRYPT_SECRET_KEY') or secrets.token_hex(32),
        }))
        return

    if app == "tracer":
        data = {"DB_PASSWORD": pg_p, "DB_USER_ADMIN": pg_u,
                "DB_ADMIN_PASSWORD": pg_p, "DB_PASSWORD_TRACER": pg_p}
    elif app == "reporter":
        data = {"MONGO_PASSWORD": mo_p, "REDIS_PASSWORD": redis_pw,
                "RABBITMQ_DEFAULT_USER": mq_u, "RABBITMQ_DEFAULT_PASS": mq_p,
                # Admin creds for the externalRabbitmqDefinitions bootstrap Job
                # (declares exchange/queue/DLQ on the broker). On AmazonMQ the
                # broker user IS the admin, so reuse the same MQ credentials.
                "RABBITMQ_ADMIN_USER": mq_u, "RABBITMQ_ADMIN_PASS": mq_p,
                "DATASOURCE_ONBOARDING_PASSWORD": pg_p,
                "OBJECT_STORAGE_ACCESS_KEY_ID": "", "OBJECT_STORAGE_SECRET_KEY": "",
                "APP_ENC_KEY": keep_b64("APP_ENC_KEY")}
    elif app == "fetcher":
        data = {"APP_ENC_KEY": keep_b64("APP_ENC_KEY"), "APP_ENC_KEY_VERSION": "1",
                "MONGO_USER": docdb.get('username', ''), "MONGO_PASSWORD": mo_p,
                "REDIS_PASSWORD": redis_pw,
                "RABBITMQ_DEFAULT_USER": mq_u, "RABBITMQ_DEFAULT_PASS": mq_p,
                # Admin creds for the externalRabbitmqDefinitions bootstrap Job.
                "RABBITMQ_ADMIN_USER": mq_u, "RABBITMQ_ADMIN_PASS": mq_p,
                # MSK SASL/SCRAM password for the worker's streaming emitter.
                "STREAMING_SASL_PASSWORD": msk_p,
                "OBJECT_STORAGE_ACCESS_KEY_ID": "", "OBJECT_STORAGE_SECRET_KEY": "",
                "CRYPTO_ENCRYPT_FILE_STORAGE": keep_hex("CRYPTO_ENCRYPT_FILE_STORAGE"),
                "CRYPTO_HASH_SECRET_KEY_FILE_STORAGE": keep_hex("CRYPTO_HASH_SECRET_KEY_FILE_STORAGE"),
                "CRYPTO_ENCRYPT_SECRET_KEY_PLUGIN_CRM": keep_hex("CRYPTO_ENCRYPT_SECRET_KEY_PLUGIN_CRM"),
                "CRYPTO_HASH_SECRET_KEY_PLUGIN_CRM": keep_hex("CRYPTO_HASH_SECRET_KEY_PLUGIN_CRM"),
                "LICENSE_KEY": lic}
    elif app == "fees":
        data = {"CLIENT_SECRET": authz, "LICENSE_KEY": lic,
                "ORGANIZATION_IDS": org, "MONGO_PASSWORD": mo_p}
    elif app == "console":
        data = {"NEXTAUTH_SECRET": keep_hex("NEXTAUTH_SECRET"),
                "MONGODB_PASS": mo_p, "PLUGIN_AUTH_CLIENT_SECRET": authz}
    elif app == "bank_transfer":
        data = {
            "DB_USER_ADMIN": pg_u, "DB_ADMIN_PASSWORD": pg_p,
            "DB_PASSWORD_BANK_TRANSFER": pg_p, "POSTGRES_PASSWORD": pg_p,
            "REDIS_PASSWORD": redis_pw, "MONGO_URI": _mongo_uri(), "LICENSE_KEY": lic,
            "JD_INCOMING_RAW_XML_ENCRYPTION_KEY": keep_hex("JD_INCOMING_RAW_XML_ENCRYPTION_KEY"),
            "RECIPIENT_DETAILS_ENCRYPTION_KEY": keep_hex("RECIPIENT_DETAILS_ENCRYPTION_KEY"),
        }
    else:
        data = {}

    if m2m and app in m2m:
        data.update(m2m[app])
    kubectl_apply(_secret_manifest(f"{rel}-secrets", ns, data))

def helm_install(app, m2m=None):
    m = REGISTRY[app]
    ns = m['ns']
    version = os.environ[m['version_env']]
    ensure_ns(ns)
    create_runtime_secret(app, ns, m2m)
    values_path = f'/tmp/values-{app}.yaml'
    with open(values_path, 'w') as f:
        f.write(render_values(app))
    run(['helm', 'upgrade', '--install', m['release'], m['repo'],
         '--version', version, '--namespace', ns, '--create-namespace',
         '--values', values_path, '--wait', '--timeout', '15m'])

def helm_uninstall(app):
    m = REGISTRY[app]
    run(['helm', 'uninstall', m['release'], '-n', m['ns']], check=False)

# =====================================================================
# M2M bootstrap — after Access Manager is up, create the platform M2M
# applications (POST /v1/applications) and store one central Secret with
# <PREFIX>_CLIENT_ID/SECRET keys. Runs in-cluster (Job) so it can reach the
# ClusterIP auth/identity services. Store-once (skips if the Secret exists).
# Consumers (callers) get the relevant keys injected into their own Secret.
# =====================================================================
M2M_SECRET_NAME = "lerian-m2m"
# {consumer_app: {ENV_PREFIX: m2m_application_name}} — from the caller charts.
# Only plugin-br-bank-transfer consumes M2M client creds in the current charts
# (MIDAZ/CRM/FEES). Extend here as other charts adopt M2M client credentials.
M2M_CONSUMERS = {
    "bank_transfer": {"MIDAZ": "midaz", "CRM": "plugin-crm", "FEES": "plugin-fees"},
}

M2M_BOOTSTRAP_SCRIPT = """
import os, json, base64, ssl, time, urllib.request, urllib.error

def post_json(url, payload, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST')
    req.add_header('Content-Type', 'application/json')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def k8s(method, path, body=None):
    tok = open('/var/run/secrets/kubernetes.io/serviceaccount/token').read()
    ctx = ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request('https://kubernetes.default.svc' + path, data=data, method=method)
    req.add_header('Authorization', 'Bearer ' + tok)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        return e.code, {}

ns = os.environ['SECRET_NAMESPACE']
name = os.environ['SECRET_NAME']
code, _ = k8s('GET', '/api/v1/namespaces/%s/secrets/%s' % (ns, name))
if code == 200:
    print('M2M secret already present; store-once skip'); raise SystemExit(0)

access = None
for attempt in range(30):
    try:
        # Password grant as the admin initUser: the authorizer client
        # (client_credentials) is NOT authorized to create applications (403);
        # the admin user is. App names must be on the access_manager allowlist
        # (constant.Applications: midaz, plugin-crm, plugin-fees, ...).
        tok = post_json(os.environ['AUTH_TOKEN_URL'], {'grantType': 'password',
            'username': os.environ['ADMIN_USERNAME'],
            'password': os.environ['ADMIN_PASSWORD'],
            'clientId': os.environ['AUTHORIZER_CLIENT_ID'],
            'clientSecret': os.environ['AUTHORIZER_CLIENT_SECRET']})
        access = tok['accessToken']; break
    except Exception as e:
        print('admin token attempt %d: %s' % (attempt, e)); time.sleep(10)
if not access:
    raise SystemExit('could not obtain admin token from Access Manager')

string_data = {}
for pair in os.environ['M2M_APPLICATIONS'].split(','):
    pair = pair.strip()
    if not pair:
        continue
    prefix, appname = pair.split('=', 1)
    app = None
    for attempt in range(5):
        try:
            app = post_json(os.environ['IDENTITY_APPS_URL'],
                {'name': appname, 'description': 'Lerian Platform bundle M2M client for ' + appname},
                {'Authorization': 'Bearer ' + access})
            break
        except Exception as e:
            print('create %s attempt %d: %s' % (appname, attempt, e)); time.sleep(5)
    if not app:
        raise SystemExit('failed to create M2M application ' + appname)
    string_data[prefix + '_CLIENT_ID'] = app['clientId']
    string_data[prefix + '_CLIENT_SECRET'] = app['clientSecret']

body = {'apiVersion': 'v1', 'kind': 'Secret',
        'metadata': {'name': name, 'namespace': ns},
        'type': 'Opaque', 'stringData': string_data}
code, _ = k8s('POST', '/api/v1/namespaces/%s/secrets' % ns, body)
print('wrote M2M secret, status', code)
raise SystemExit(0 if code in (200, 201) else 1)
"""

def m2m_bootstrap_manifests(ns, apps_csv):
    project = os.environ['PROJECT_NAME']
    base = f"{project}-m2m-bootstrap"
    pam = REGISTRY['access_manager']['release']
    script = "\n".join("    " + l for l in M2M_BOOTSTRAP_SCRIPT.strip("\n").split("\n"))
    return f'''apiVersion: v1
kind: ServiceAccount
metadata:
  name: {base}
  namespace: {ns}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {base}
  namespace: {ns}
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {base}
  namespace: {ns}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {base}
subjects:
  - kind: ServiceAccount
    name: {base}
    namespace: {ns}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: {base}-script
  namespace: {ns}
data:
  bootstrap.py: |
{script}
---
apiVersion: batch/v1
kind: Job
metadata:
  name: {base}
  namespace: {ns}
spec:
  backoffLimit: 3
  ttlSecondsAfterFinished: 300
  template:
    spec:
      serviceAccountName: {base}
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: m2m-bootstrap
          image: public.ecr.aws/docker/library/python:3.13-alpine
          command: ["python3", "/scripts/bootstrap.py"]
          env:
            - name: SECRET_NAMESPACE
              value: "{ns}"
            - name: SECRET_NAME
              value: "{M2M_SECRET_NAME}"
            - name: AUTH_TOKEN_URL
              value: "{AUTH_URL}/v1/login/oauth/access_token"
            - name: IDENTITY_APPS_URL
              value: "{IDENTITY_URL}/v1/applications"
            - name: AUTHORIZER_CLIENT_ID
              value: "{os.environ.get('AUTHORIZER_CLIENT_ID', '')}"
            - name: AUTHORIZER_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: {pam}-auth
                  key: AUTHORIZER_CLIENT_SECRET
            - name: ADMIN_USERNAME
              value: "admin"
            - name: ADMIN_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {pam}-admin
                  key: ADMIN_PASSWORD
            - name: M2M_APPLICATIONS
              value: "{apps_csv}"
          volumeMounts:
            - name: script
              mountPath: /scripts
      volumes:
        - name: script
          configMap:
            name: {base}-script
'''

def m2m_plan(apps):
    targets, per_consumer = {}, {}
    for app in apps:
        if app in M2M_CONSUMERS:
            per_consumer[app] = M2M_CONSUMERS[app]
            targets.update(M2M_CONSUMERS[app])
    return targets, per_consumer

def run_m2m_bootstrap(apps):
    # Returns {consumer_app: {<PREFIX>_CLIENT_ID/SECRET: value}} for injection.
    if 'access_manager' not in apps:
        return {}
    targets, per_consumer = m2m_plan(apps)
    if not targets:
        return {}
    ns = REGISTRY['access_manager']['ns']
    project = os.environ['PROJECT_NAME']
    apps_csv = ",".join(f"{p}={n}" for p, n in sorted(targets.items()))
    # Re-run safe: a completed Job's spec is immutable, so delete before re-apply.
    run(['kubectl', '-n', ns, 'delete', 'job', f'{project}-m2m-bootstrap',
         '--ignore-not-found'], check=False)
    kubectl_apply(m2m_bootstrap_manifests(ns, apps_csv))
    run(['kubectl', 'wait', '--for=condition=complete',
         f'job/{project}-m2m-bootstrap', '-n', ns, '--timeout=300s'], check=False)
    out = run(['kubectl', '-n', ns, 'get', 'secret', M2M_SECRET_NAME, '-o', 'json'], check=False)
    creds = {}
    try:
        for k, v in (json.loads(out).get('data', {}) or {}).items():
            creds[k] = base64.b64decode(v).decode()
    except Exception as e:
        logger.warning(f"M2M secret read-back failed: {e}")
        return {}
    result = {}
    for app, prefixes in per_consumer.items():
        d = {}
        for prefix in prefixes:
            for suf in ('CLIENT_ID', 'CLIENT_SECRET'):
                key = f"{prefix}_{suf}"
                if key in creds:
                    d[key] = creds[key]
        result[app] = d
    return result

def helm_registry_login():
    user = os.environ.get('HELM_REGISTRY_USER', '').strip()
    token = os.environ.get('HELM_REGISTRY_TOKEN', '').strip()
    host = os.environ.get('HELM_REGISTRY_HOST', 'ghcr.io').strip()
    if user and token:
        run(['helm', 'registry', 'login', host, '-u', user, '--password-stdin'],
            check=False, input_text=token)
        logger.info(f"helm registry login: {host} as {user}")

def do_helm_install():
    helm_registry_login()
    apps = selected_apps()
    logger.info(f"helm-install mode; apps in order: {apps}")
    m2m = {}
    for app in apps:
        helm_install(app, m2m)
        if app == "access_manager":
            m2m = run_m2m_bootstrap(apps)
            logger.info(f"M2M bootstrap done; consumers wired: {list(m2m.keys())}")
    return {"Mode": "helm-install", "Apps": ",".join(apps)}

def do_helm_uninstall():
    for app in reversed(selected_apps()):
        helm_uninstall(app)

# =====================================================================
# MODE 2 — GitOps seeder (opt-in). Renders values + ArgoCD app-of-apps,
# pushes seed-once to the client's repo, installs ArgoCD + ESO.
# NEVER writes secret values — only ExternalSecret refs to the ARNs.
# =====================================================================
def write_deploy_key(key):
    path = '/tmp/deploy_key'
    with open(path, 'w') as f:
        f.write(key if key.endswith('\n') else key + '\n')
    os.chmod(path, 0o600)
    os.environ['GIT_SSH_COMMAND'] = f'ssh -i {path} -o StrictHostKeyChecking=no'
    return path

# Symbolic (value-free) map of each app secret key to its Secrets Manager
# source — mirrors secret_data() WITHOUT fetching values, so it is safe to
# render into Git for the GitOps/ESO path. Tokens resolve to remoteRefs below.
def secret_key_sources(app):
    PG, PGU = ("pg", "password"), ("pguser", "username")
    MG = ("mongo", "password")
    MQP, MQU = ("mqp", "password"), ("mqu", "username")
    RD = ("redis", None)
    m = {
        "access_manager": {"DB_PASSWORD": PG, "POSTGRES_PASSWORD": PG, "REDIS_PASSWORD": RD},
        "ledger": {
            "DB_ONBOARDING_PASSWORD": PG, "DB_ONBOARDING_REPLICA_PASSWORD": PG,
            "DB_TRANSACTION_PASSWORD": PG, "DB_TRANSACTION_REPLICA_PASSWORD": PG,
            "MONGO_ONBOARDING_PASSWORD": MG, "MONGO_TRANSACTION_PASSWORD": MG,
            "RABBITMQ_DEFAULT_PASS": MQP, "RABBITMQ_CONSUMER_PASS": MQP, "REDIS_PASSWORD": RD,
        },
        "tracer": {"DB_PASSWORD": PG},
        "reporter": {
            "MONGO_PASSWORD": MG, "REDIS_PASSWORD": RD, "RABBITMQ_DEFAULT_USER": MQU,
            "RABBITMQ_DEFAULT_PASS": MQP, "DATASOURCE_ONBOARDING_PASSWORD": PG,
            "OBJECT_STORAGE_ACCESS_KEY_ID": "", "OBJECT_STORAGE_SECRET_KEY": "", "APP_ENC_KEY": "",
        },
        "fetcher": {
            "MONGO_PASSWORD": MG, "REDIS_PASSWORD": RD, "RABBITMQ_DEFAULT_USER": MQU,
            "RABBITMQ_DEFAULT_PASS": MQP, "OBJECT_STORAGE_ACCESS_KEY_ID": "",
            "OBJECT_STORAGE_SECRET_KEY": "",
        },
        "fees": {"MONGO_PASSWORD": MG},
        "bank_transfer": {"POSTGRES_PASSWORD": PG, "MONGO_PASSWORD": MG, "REDIS_PASSWORD": RD},
        "console": {"NEXTAUTH_SECRET": "gen", "MONGO_PASSWORD": MG},
    }
    return m.get(app, {})

def external_secret_manifest(app, ns):
    # ESO ExternalSecret producing the SAME per-app keys as the helm-install
    # path (secret_data), mapped from the Secrets Manager ARNs. No secret
    # values are written to Git — only ARN refs + a value-free template.
    # NEXTAUTH_SECRET is generated in-cluster by ESO (sprig randAlphaNum).
    sources = secret_key_sources(app)
    src_arn = {
        "pg": os.environ['RDS_SECRET_ARN'], "pguser": os.environ['RDS_SECRET_ARN'],
        "mongo": os.environ['DOCUMENTDB_SECRET_ARN'],
        "mqp": os.environ['AMAZONMQ_SECRET_ARN'], "mqu": os.environ['AMAZONMQ_SECRET_ARN'],
        "redis": os.environ.get('ELASTICACHE_SECRET_ARN', ''),
    }
    src_prop = {"pg": "password", "pguser": "username", "mongo": "password",
                "mqp": "password", "mqu": "username", "redis": None}
    # Which intermediate refs this app actually needs (skip literal "" and gen).
    needed = set()
    for v in sources.values():
        if isinstance(v, tuple):
            needed.add(v[0])
    data_lines = []
    available = set()
    for name in sorted(needed):
        arn = src_arn.get(name, '')
        if not arn:
            continue
        available.add(name)
        prop = src_prop.get(name)
        data_lines.append(f"    - secretKey: {name}")
        data_lines.append(f"      remoteRef:")
        data_lines.append(f"        key: \"{arn}\"")
        if prop:
            data_lines.append(f"        property: {prop}")
    tmpl_lines = []
    for k, v in sources.items():
        if v == "gen":
            tmpl_lines.append(f"          {k}: '{{{{ randAlphaNum 64 }}}}'")
        elif isinstance(v, tuple) and v[0] in available:
            tmpl_lines.append(f"          {k}: '{{{{ .{v[0]} }}}}'")
        else:
            # Source unavailable (e.g. no ElastiCache secret) — emit empty.
            tmpl_lines.append(f"          {k}: \"\"")
    data_block = "\n".join(data_lines) if data_lines else "    []"
    tmpl_block = "\n".join(tmpl_lines)
    return f'''apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: {REGISTRY[app]['release']}-secrets
  namespace: {ns}
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: ClusterSecretStore
  target:
    name: {REGISTRY[app]['release']}-secrets
    template:
      engineVersion: v2
      data:
{tmpl_block}
  data:
{data_block}
'''

def argocd_application(app, repo, branch, path):
    m = REGISTRY[app]
    return f'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {m['release']}
  namespace: argocd
spec:
  project: default
  source:
    repoURL: {repo}
    targetRevision: {branch}
    path: {path}/apps/{app}
  destination:
    server: https://kubernetes.default.svc
    namespace: {m['ns']}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
'''

def install_argocd_and_eso():
    run(['helm', 'upgrade', '--install', 'argo-cd',
         'oci://ghcr.io/argoproj/argo-helm/argo-cd',
         '--namespace', 'argocd', '--create-namespace', '--wait', '--timeout', '15m'],
        check=False)
    run(['helm', 'upgrade', '--install', 'external-secrets',
         'oci://ghcr.io/external-secrets/charts/external-secrets',
         '--namespace', 'external-secrets', '--create-namespace',
         '--set', 'installCRDs=true', '--wait', '--timeout', '15m'],
        check=False)

def do_gitops_seed(deploy_key):
    helm_registry_login()
    repo = os.environ['GITOPS_REPO_URL']
    branch = os.environ.get('GITOPS_BRANCH', 'main')
    path = os.environ.get('GITOPS_PATH', 'environments/production').strip('/')
    write_deploy_key(deploy_key)
    workdir = '/tmp/gitops'
    run(['rm', '-rf', workdir], check=False)
    run(['git', 'clone', '--depth', '1', '--branch', branch, repo, workdir], check=False)
    if not os.path.isdir(workdir):
        run(['git', 'init', workdir])
    apps = selected_apps()
    # Seed-once: skip writing if the target path already has an app-of-apps.
    root_app = os.path.join(workdir, path, 'app-of-apps.yaml')
    if os.path.exists(root_app):
        logger.info("GitOps repo already seeded (app-of-apps present) — skipping write (seed-once).")
    else:
        for app in apps:
            appdir = os.path.join(workdir, path, 'apps', app)
            os.makedirs(appdir, exist_ok=True)
            with open(os.path.join(appdir, 'values.yaml'), 'w') as f:
                f.write(render_values(app))
            with open(os.path.join(appdir, 'external-secret.yaml'), 'w') as f:
                f.write(external_secret_manifest(app, REGISTRY[app]['ns']))
            with open(os.path.join(appdir, 'application.yaml'), 'w') as f:
                f.write(argocd_application(app, repo, branch, path))
        os.makedirs(os.path.dirname(root_app), exist_ok=True)
        with open(root_app, 'w') as f:
            f.write("# Seeded by Lerian Platform bootstrap (day-0). Edit here for day-2.\n")
        run(['git', '-C', workdir, 'add', '-A'])
        run(['git', '-C', workdir, 'config', 'user.email', 'bootstrap@lerian.studio'])
        run(['git', '-C', workdir, 'config', 'user.name', 'lerian-bootstrap'])
        run(['git', '-C', workdir, 'commit', '-m', 'chore: seed Lerian Platform (day-0)'], check=False)
        run(['git', '-C', workdir, 'push', 'origin', f'HEAD:{branch}'], check=False)
    install_argocd_and_eso()
    # Point ArgoCD at the repo by applying the Applications directly (they self-manage thereafter).
    for app in apps:
        kubectl_apply(argocd_application(app, repo, branch, path))
    return {"Mode": "gitops-seeder", "Apps": ",".join(apps), "Repo": repo}

# =====================================================================
# Handler
# =====================================================================
def handler(event, context):
    logger.info(f"Event: {json.dumps({k: v for k, v in event.items() if k != 'ResourceProperties'})}")
    try:
        req = event['RequestType']
        props = event.get('ResourceProperties', {})
        deploy_key = props.get('GitOpsDeployKey', '')
        gitops = bool(os.environ.get('GITOPS_REPO_URL', '').strip()) and bool(deploy_key.strip())

        install_tools(need_git=gitops)
        setup_kubeconfig()

        if req == 'Delete':
            # In GitOps mode day-2 is owned by the repo; we only clean helm-install releases.
            if not gitops:
                do_helm_uninstall()
            send_response(event, context, 'SUCCESS', {'Message': 'Delete handled'})
            return

        if gitops:
            data = do_gitops_seed(deploy_key)
        else:
            data = do_helm_install()
        send_response(event, context, 'SUCCESS', data)
    except Exception as e:
        logger.error(f"Error: {e}")
        send_response(event, context, 'FAILED', reason=str(e)[:1000])
