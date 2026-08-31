# Plano de Testes — Lerian Platform (CloudFormation)

> Alvo: `products/lerian-platform/{full-stack,helm,app-stack}.yaml`
> Escopo desta rodada: **3 cenários de deploy real em conta AWS + EKS**
> 1. **Cenário A** — Stack completa (todos os módulos, topologia `shared`, modo helm-install)
> 2. **Cenário B** — Apenas Midaz (Ledger), modo helm-install self-contained
> 3. **Cenário C** — Midaz + **GitOps Seed** (ArgoCD + External Secrets Operator)
>
> Modo de entrega das apps (`helm.yaml`): **helm-install** (default, sem Git externo)
> quando `GitOpsRepoUrl` vazio; **gitops-seeder** quando `GitOpsRepoUrl` + `GitOpsDeployKey`
> setados. Cenários A/B usam helm-install; C usa gitops-seeder.

---

## 0. Pré-requisitos

| Item | Detalhe |
|------|---------|
| Conta AWS sandbox | Permissões p/ CFN, EKS, RDS, DocumentDB, ElastiCache, AmazonMQ, S3, IAM, Lambda, Secrets Manager, KMS |
| CLI | `aws` (perfil configurado), `kubectl`, `helm` v3.14+, `jq` |
| Região | Ex.: `sa-east-1` (mesma dos MPS3 params) |
| Bucket S3 de templates | Um bucket p/ hospedar os templates aninhados (todos no **mesmo prefixo**) |
| 3 AZs | Da região escolhida (params `AvailabilityZone1/2/3` são **obrigatórios**) |
| Cenário C | Repo Git (GitHub/GitLab/CodeCommit) **já criado** + **deploy key SSH** com push |
| Saída p/ internet | Os node groups (e o Lambda deployer) precisam puxar charts OCI (ghcr.io), kubectl/helm e — no modo GitOps — o `git-lambda-layer` e clonar/pushar o repo |

**Parâmetros obrigatórios (sem default)**: `AvailabilityZone1`, `AvailabilityZone2`,
`AvailabilityZone3`, `RDSMasterUsername`, `DocumentDBMasterUsername`, `AmazonMQAdminUsername`.

---

## 1. Setup comum — publicar os templates no S3

Todos os templates aninhados (compartilhados **e** de produto) precisam ficar sob o
**mesmo prefixo** (`MPS3KeyPrefix`) — exigência de nested-URL do CloudFormation/Marketplace.

```bash
export AWS_PROFILE=lerian_sandbox            # ajuste
export REGION=sa-east-1
export TPL_BUCKET=lerian-cfn-test-$RANDOM    # ou um bucket existente
export PREFIX=lerian-platform/               # = MPS3KeyPrefix

# cria bucket (se necessário)
aws s3api create-bucket --bucket "$TPL_BUCKET" --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

# sobe os templates COMPARTILHADOS (vpc, eks, rds, documentdb, elasticache,
# amazonmq, route53, alb-controller, external-dns) + os de PRODUTO (full-stack,
# helm, app-stack) TODOS no mesmo prefixo:
aws s3 sync templates/ "s3://$TPL_BUCKET/$PREFIX" --region "$REGION" \
  --exclude "*" --include "*.yaml"
aws s3 cp products/lerian-platform/full-stack.yaml "s3://$TPL_BUCKET/$PREFIX" --region "$REGION"
aws s3 cp products/lerian-platform/helm.yaml       "s3://$TPL_BUCKET/$PREFIX" --region "$REGION"
aws s3 cp products/lerian-platform/app-stack.yaml  "s3://$TPL_BUCKET/$PREFIX" --region "$REGION"

# sanity: os leaf templates referenciados existem no prefixo
aws s3 ls "s3://$TPL_BUCKET/$PREFIX" --region "$REGION"
```

> **Nota:** o `scripts/upload-templates.sh` sozinho só sincroniza `templates/` — por isso
> os 3 `products/lerian-platform/*.yaml` são copiados à parte acima.

Todos os cenários usam estes 3 params de Marketplace apontando p/ o bucket acima:
`MPS3BucketName=$TPL_BUCKET`, `MPS3BucketRegion=$REGION`, `MPS3KeyPrefix=$PREFIX`.

---

## 2. Cenário A — Stack completa em EKS (shared, helm-install)

**Objetivo:** validar o caminho default de ponta a ponta — VPC + EKS + infra
compartilhada (RDS/DocDB/ElastiCache/AmazonMQ) + os 9 módulos via helm-install.

### 2.1 Parâmetros (`params-A.json`)

```json
[
  {"ParameterKey":"MPS3BucketName","ParameterValue":"REPLACE_TPL_BUCKET"},
  {"ParameterKey":"MPS3BucketRegion","ParameterValue":"sa-east-1"},
  {"ParameterKey":"MPS3KeyPrefix","ParameterValue":"lerian-platform/"},
  {"ParameterKey":"EnvironmentName","ParameterValue":"staging"},
  {"ParameterKey":"InfraTopology","ParameterValue":"shared"},
  {"ParameterKey":"DeployApplication","ParameterValue":"true"},
  {"ParameterKey":"EnableLedger","ParameterValue":"true"},
  {"ParameterKey":"EnableAccessManager","ParameterValue":"true"},
  {"ParameterKey":"EnableConsole","ParameterValue":"true"},
  {"ParameterKey":"EnableReporter","ParameterValue":"true"},
  {"ParameterKey":"EnableTracer","ParameterValue":"true"},
  {"ParameterKey":"EnableFetcher","ParameterValue":"true"},
  {"ParameterKey":"EnableFlowker","ParameterValue":"true"},
  {"ParameterKey":"EnableBankTransfer","ParameterValue":"true"},
  {"ParameterKey":"EnableFees","ParameterValue":"true"},
  {"ParameterKey":"EnableALBController","ParameterValue":"true"},
  {"ParameterKey":"EnableExternalDNS","ParameterValue":"false"},
  {"ParameterKey":"AvailabilityZone1","ParameterValue":"sa-east-1a"},
  {"ParameterKey":"AvailabilityZone2","ParameterValue":"sa-east-1b"},
  {"ParameterKey":"AvailabilityZone3","ParameterValue":"sa-east-1c"},
  {"ParameterKey":"RDSMasterUsername","ParameterValue":"lerian_admin"},
  {"ParameterKey":"DocumentDBMasterUsername","ParameterValue":"lerian_admin"},
  {"ParameterKey":"AmazonMQAdminUsername","ParameterValue":"lerian_admin"},
  {"ParameterKey":"RDSDeletionProtection","ParameterValue":"false"},
  {"ParameterKey":"DocumentDBDeletionProtection","ParameterValue":"false"}
]
```

> `*DeletionProtection=false` só p/ facilitar teardown de teste — em produção deixe `true`.

### 2.2 Deploy

```bash
export STACK=lerian-platform-full
aws cloudformation create-stack \
  --stack-name "$STACK" --region "$REGION" \
  --template-url "https://$TPL_BUCKET.s3.$REGION.amazonaws.com/${PREFIX}full-stack.yaml" \
  --parameters file://params-A.json \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation wait stack-create-complete --stack-name "$STACK" --region "$REGION"
aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs" --output table
```

### 2.3 Verificação

```bash
# 1) kubeconfig (output KubeconfigCommand)
aws eks update-kubeconfig --name "$STACK" --region "$REGION"

# 2) pods por módulo (namespaces do REGISTRY)
for ns in plugin-access-manager midaz-mt tracer fetcher-mt reporter flowker-mt \
          plugin-fees plugin-br-bank-transfer-mt product-console; do
  echo "== $ns =="; kubectl get pods -n "$ns" 2>/dev/null
done

# 3) releases helm
helm list -A

# 4) log do deployer Lambda (render de values + helm install)
aws logs tail "/aws/lambda/$STACK-platform-deployer" --region "$REGION" --since 30m
```

**Critérios de sucesso:**
- Stack `CREATE_COMPLETE`.
- `helm list -A` mostra os 9 releases (`midaz`, `plugin-access-manager`, `tracer`,
  `fetcher`, `reporter`, `flowker`, `plugin-fees`, `plugin-br-bank-transfer`, `product-console`).
- Pods `Running`/`Ready` em cada namespace (dar tempo p/ migrations).
- Log do deployer termina com `SUCCESS` e `Mode: helm-install`.
- Console acessível pelo ALB (se `EnableIngress=true` + hostname; ver §5).

---

## 3. Cenário B — Apenas Midaz (helm-install)

**Objetivo:** provar o deploy isolado do Ledger. O config do ledger tem
`PLUGIN_AUTH_ENABLED=true` apontando p/ o Access Manager (`:4000`), então o
**conjunto mínimo funcional é Ledger + Access Manager**.

> Se quiser **Ledger estritamente sozinho**, é preciso um toggle de auth
> (`PLUGIN_AUTH_ENABLED=false`) — hoje é fixo em `true` no `render_values`. Fica como
> follow-up (tornar o auth do ledger parametrizável). Neste teste habilitamos os dois.

### 3.1 Parâmetros (`params-B.json`) — diferença vs A

```json
[
  {"ParameterKey":"MPS3BucketName","ParameterValue":"REPLACE_TPL_BUCKET"},
  {"ParameterKey":"MPS3BucketRegion","ParameterValue":"sa-east-1"},
  {"ParameterKey":"MPS3KeyPrefix","ParameterValue":"lerian-platform/"},
  {"ParameterKey":"EnvironmentName","ParameterValue":"staging"},
  {"ParameterKey":"InfraTopology","ParameterValue":"shared"},
  {"ParameterKey":"DeployApplication","ParameterValue":"true"},
  {"ParameterKey":"EnableLedger","ParameterValue":"true"},
  {"ParameterKey":"EnableAccessManager","ParameterValue":"true"},
  {"ParameterKey":"EnableConsole","ParameterValue":"false"},
  {"ParameterKey":"EnableReporter","ParameterValue":"false"},
  {"ParameterKey":"EnableTracer","ParameterValue":"false"},
  {"ParameterKey":"EnableFetcher","ParameterValue":"false"},
  {"ParameterKey":"EnableFlowker","ParameterValue":"false"},
  {"ParameterKey":"EnableBankTransfer","ParameterValue":"false"},
  {"ParameterKey":"EnableFees","ParameterValue":"false"},
  {"ParameterKey":"EnableALBController","ParameterValue":"true"},
  {"ParameterKey":"EnableExternalDNS","ParameterValue":"false"},
  {"ParameterKey":"AvailabilityZone1","ParameterValue":"sa-east-1a"},
  {"ParameterKey":"AvailabilityZone2","ParameterValue":"sa-east-1b"},
  {"ParameterKey":"AvailabilityZone3","ParameterValue":"sa-east-1c"},
  {"ParameterKey":"RDSMasterUsername","ParameterValue":"lerian_admin"},
  {"ParameterKey":"DocumentDBMasterUsername","ParameterValue":"lerian_admin"},
  {"ParameterKey":"AmazonMQAdminUsername","ParameterValue":"lerian_admin"},
  {"ParameterKey":"RDSDeletionProtection","ParameterValue":"false"},
  {"ParameterKey":"DocumentDBDeletionProtection","ParameterValue":"false"}
]
```

> Observação: no modo `shared`, a infra (RDS/DocDB/ElastiCache/AmazonMQ) é criada
> inteira mesmo com poucos módulos. Para **isolar só a infra do Midaz**, use
> `InfraTopology=dedicated` (Cenário B-dedicated abaixo).

### 3.2 Deploy + verificação

```bash
export STACK=lerian-midaz-only
aws cloudformation create-stack --stack-name "$STACK" --region "$REGION" \
  --template-url "https://$TPL_BUCKET.s3.$REGION.amazonaws.com/${PREFIX}full-stack.yaml" \
  --parameters file://params-B.json --capabilities CAPABILITY_NAMED_IAM
aws cloudformation wait stack-create-complete --stack-name "$STACK" --region "$REGION"

aws eks update-kubeconfig --name "$STACK" --region "$REGION"
kubectl get pods -n midaz-mt
kubectl get pods -n plugin-access-manager
helm list -A                       # espera: midaz, plugin-access-manager
kubectl -n midaz-mt get secret midaz-secrets -o jsonpath='{.data}' | jq 'keys'   # chaves DB_*/MONGO_*/...

# smoke do ledger (port-forward)
kubectl -n midaz-mt port-forward svc/midaz-ledger 3002:3002 &
curl -s http://localhost:3002/health || curl -s http://localhost:3002/v1/health
```

**Critérios de sucesso:** stack `CREATE_COMPLETE`; releases `midaz` + `plugin-access-manager`;
pods `Running`; Secret `midaz-secrets` com as chaves esperadas
(`DB_ONBOARDING_PASSWORD`, `DB_TRANSACTION_PASSWORD`, `MONGO_ONBOARDING_PASSWORD`,
`MONGO_TRANSACTION_PASSWORD`, `RABBITMQ_DEFAULT_PASS`, `REDIS_PASSWORD`); ledger responde ao health.

### 3.2b (Opcional) Midaz-only em topologia `dedicated`

Troque `InfraTopology=dedicated`. Só o `LedgerAppStack` (+ `AuthmgrAppStack`) é criado,
cada um com sua **infra dedicada** (ledger: RDS+DocDB+ElastiCache+AmazonMQ; access-manager:
RDS+ElastiCache). Verifique:

```bash
aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs"
# deployer log por-app: ProjectName = <STACK>-ledger, <STACK>-authmgr
aws logs tail "/aws/lambda/$STACK-ledger-platform-deployer" --region "$REGION" --since 30m
```

---

## 4. Cenário C — Midaz + GitOps Seed

**Objetivo:** validar o modo **gitops-seeder** do `helm.yaml`: renderiza values +
`ExternalSecret` + `Application` do ArgoCD, faz **git push seed-once** no repo do cliente,
instala **ArgoCD + External Secrets Operator (ESO)** e aponta o ArgoCD p/ o repo.

### 4.1 Preparação do repo

```bash
# repo VAZIO já criado (GitHub/GitLab/CodeCommit); gere uma deploy key com push:
ssh-keygen -t ed25519 -f ./gitops_deploy_key -N ""
# cadastre ./gitops_deploy_key.pub como Deploy Key (write) no repo
export GITOPS_REPO="git@github.com:ORG/lerian-gitops-test.git"
export DEPLOY_KEY="$(cat ./gitops_deploy_key)"
```

### 4.2 Parâmetros (`params-C.json`) — Midaz + GitOps

Igual ao `params-B.json`, **adicionando**:

```json
  {"ParameterKey":"GitOpsRepoUrl","ParameterValue":"git@github.com:ORG/lerian-gitops-test.git"},
  {"ParameterKey":"GitOpsBranch","ParameterValue":"main"},
  {"ParameterKey":"GitOpsPath","ParameterValue":"environments/production"},
  {"ParameterKey":"GitOpsDeployKey","ParameterValue":"-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----\n"}
```

> `GitOpsDeployKey` é `NoEcho` (não aparece em console/logs). Passe o conteúdo do
> `gitops_deploy_key` com quebras `\n` escapadas, ou via `--parameters ParameterKey=...`
> lendo de arquivo com ferramenta que preserve newlines.

### 4.3 Deploy + verificação

```bash
export STACK=lerian-midaz-gitops
aws cloudformation create-stack --stack-name "$STACK" --region "$REGION" \
  --template-url "https://$TPL_BUCKET.s3.$REGION.amazonaws.com/${PREFIX}full-stack.yaml" \
  --parameters file://params-C.json --capabilities CAPABILITY_NAMED_IAM
aws cloudformation wait stack-create-complete --stack-name "$STACK" --region "$REGION"

# 1) log do deployer deve indicar Mode: gitops-seeder
aws logs tail "/aws/lambda/$STACK-platform-deployer" --region "$REGION" --since 30m | grep -i "gitops\|git\|argo\|external-secrets"

# 2) o repo foi semeado (seed-once)
git clone "$GITOPS_REPO" /tmp/seed-check && ls -R /tmp/seed-check/environments/production
#   espera: app-of-apps.yaml + apps/<app>/{values.yaml,external-secret.yaml,application.yaml}

# 3) ArgoCD + ESO instalados
aws eks update-kubeconfig --name "$STACK" --region "$REGION"
kubectl get pods -n argocd
kubectl get pods -n external-secrets

# 4) Applications do ArgoCD e sync
kubectl get applications -n argocd
kubectl -n midaz-mt get externalsecret,secret
```

**Critérios de sucesso:**
- Log do deployer: `Mode: gitops-seeder` e `SUCCESS`.
- Repo contém `environments/production/app-of-apps.yaml` + `apps/ledger/*` + `apps/access_manager/*`
  (values SEM senhas — só refs; `external-secret.yaml` referenciando os ARNs do Secrets Manager).
- Namespaces `argocd` e `external-secrets` com pods `Running`.
- ArgoCD `Application`s presentes; ArgoCD reconciliando.

### 4.4 Teste do guardrail seed-once (não clobber)

```bash
# faça um commit "day-2" manual no repo (simula o cliente)
cd /tmp/seed-check && echo "# day-2 edit" >> environments/production/apps/ledger/values.yaml
git commit -am "day-2 manual change" && git push

# dispare um update do stack (ex.: mude um EnableX) e confirme que o seeder NÃO sobrescreveu main
aws cloudformation update-stack --stack-name "$STACK" --region "$REGION" \
  --template-url "https://$TPL_BUCKET.s3.$REGION.amazonaws.com/${PREFIX}full-stack.yaml" \
  --parameters file://params-C.json --capabilities CAPABILITY_NAMED_IAM
aws cloudformation wait stack-update-complete --stack-name "$STACK" --region "$REGION"
git -C /tmp/seed-check pull && grep "day-2 edit" environments/production/apps/ledger/values.yaml && echo "SEED-ONCE OK (edição day-2 preservada)"
```

**Critério:** a edição day-2 permanece (o seeder detecta `app-of-apps.yaml` e pula a escrita).

---

## 5. Console via ALB (opcional, cenários A/C)

Para expor o Console, adicione aos params:

```json
  {"ParameterKey":"EnableIngress","ParameterValue":"true"},
  {"ParameterKey":"IngressHostname","ParameterValue":"console.seu-dominio.com"},
  {"ParameterKey":"IngressScheme","ParameterValue":"internet-facing"},
  {"ParameterKey":"NextAuthUrl","ParameterValue":"https://console.seu-dominio.com"}
```

Verifique: `kubectl -n product-console get ingress` → ALB provisionado; aponte o DNS
(`IngressHostname`) p/ o ALB (ou use `EnableExternalDNS=true` + `DomainName`).

---

## 6. Teardown

```bash
aws cloudformation delete-stack --stack-name "$STACK" --region "$REGION"
aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$REGION"
```

> **Atenção:** buckets S3 (`*StorageBucket`) e os secrets/KMS têm `Retain` — apague à mão
> depois. RDS/DocDB só deletam se `*DeletionProtection=false`. No modo GitOps, o
> `Delete` do stack **não** desfaz o repo nem os apps geridos pelo ArgoCD (day-2 é do repo);
> remova o ArgoCD/apps manualmente se quiser limpar o cluster.

---

## 7. Troubleshooting & lacunas conhecidas (validar nesta rodada)

| Sintoma / risco | Onde olhar / ação |
|---|---|
| Deployer Lambda falha | `aws logs tail /aws/lambda/<STACK[-<app>]>-platform-deployer` |
| **ESO não materializa o Secret** (Cenário C) | ⚠️ **Lacuna:** o seeder instala o ESO mas **não cria o `ClusterSecretStore` `aws-secretsmanager` nem o IRSA** que o `ExternalSecret` referencia. Sem isso os `ExternalSecret` ficam `SecretSyncError`. Criar ClusterSecretStore + IRSA (service account com policy de `secretsmanager:GetSecretValue`) é **pré-req do modo GitOps** — item de fix/sandbox. |
| **git indisponível no Lambda** (Cenário C) | O `install_tools` baixa o `git-lambda-layer` (`GIT_LAYER_URL`, pinado + overridable). Se falhar o download/extract, o deploy aborta com mensagem clara. Confirmar que a URL do layer resolve na região; senão setar `GIT_LAYER_URL`. |
| **Chaves de secret/values erradas por chart** | Marcadas `(validate)` no `helm.yaml` p/ access-manager (casdoor), fetcher, flowker, bank-transfer. Se um pod não autentica no banco, comparar as chaves esperadas pelo chart com `secret_data()`/`render_values()`. |
| **Reporter sem DATASOURCE no `dedicated`** | Caveat: reporter lê o Postgres do ledger (`DATASOURCE_ONBOARDING`). No `dedicated` (isolado) essa credencial fica vazia — injetar endpoint/secret do produtor (follow-up). |
| **Bootstrap de users PG** (apps novos) | access-manager (`auth`/casdoor), flowker (`flowker_audit`), bank-transfer (`bank_transfer`) precisam do user PG criado. Validar se o chart cria via `externalPostgresDefinitions` ou se falta bootstrap no stack de infra. |
| `spec.template immutable` em Job de migração | Padrão conhecido em re-deploys; ver `docs/TROUBLESHOOTING.md`. |
| Nome de role > 64 chars (`dedicated`) | `helm.yaml` cria `${ProjectName}-platform-deployer-role`; com `ProjectName=<stack>-<app>` cuidar p/ o nome do stack não ser longo demais. |
| Pods do módulo em `CrashLoopBackOff` | Ver `kubectl logs`; conferir endpoints (RDS/DocDB/Redis/MQ) e TLS (`REDIS_CA_CERT`). |

---

## 8. Apêndice — teste local (sem CloudFormation)

A lógica do deployer (`helm.yaml` → Python) é extraível e roda local, mockando as 3
chamadas AWS (`get_secret`, `setup_kubeconfig`, `eks_token`). Cobre o que **não** exige
a casca CFN (IAM/EKS AccessEntry):

- **Render de values / ExternalSecret**: validado offline (YAML válido p/ os 9 apps).
- **Validar values contra os charts REAIS**: `helm install --dry-run <chart-oci> -f values-<app>.yaml`
  puxa o chart e valida `existingSecretName`/chaves — pega o risco #1 sem cluster.
- **GitOps seed**: rodar `do_gitops_seed()` contra um repo bare local (`file://`) — vê o
  seed-once + os manifests `Application`/`ExternalSecret`.

**Harness pronto: `scripts/test-local-deploy.sh`** — extrai o Python do Lambda, mocka a
AWS, e roda **`helm template` contra os charts OCI reais** (valida values +
`values.schema.json` sem cluster/CFN) + monta os secrets + dry-render do seed GitOps.

```bash
scripts/test-local-deploy.sh                      # todos os módulos
scripts/test-local-deploy.sh --apps ledger,fees   # subconjunto
scripts/test-local-deploy.sh --no-helm            # offline (render+secret só)
scripts/test-local-deploy.sh --gitops             # + dry-render do seed GitOps
```

Pré-req: `helm` v3, `pyyaml`, e `helm registry login ghcr.io` para os charts privados
(flowker = helm-internal). Falha de pull vira **SKIP** (não quebra a suíte). Os 9 módulos
passam `helm template` contra os charts reais — de-risca os itens `(validate)` em minutos.
