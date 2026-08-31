# Plano — Publicação do "Lerian Platform" no AWS Marketplace

> Status: **em execução (Fase 1)** — 1.1a ✅ (full-stack `shared`) · 1.1b ✅ (`dedicated`
> via `app-stack.yaml`) · 1.2 ✅ (helm.yaml / GitOps seeder / M2M / 8 renders chart-verificados)
> · 1.3 ✅ (application.yaml) · **harness de teste local ✅** (`helm template` real: 9/9 passam).
> Faltam: 1.4–1.6 (checkov/deploy sandbox/CodeRabbit) e Fase 0 (gaps de release, por último).
> Autor: Guilherme Moreira · Data: 2026-08-18
> Escopo: publicar a plataforma Lerian no AWS Marketplace seguindo o padrão já
> validado pelo Midaz, como **um único produto bundle ("Lerian Platform")** com
> ativação de módulos por flags `Enable*` no launch.

---

## 1. Decisão (o "porquê")

No AWS Marketplace a **unidade de entitlement e cobrança é o produto**. Um produto
pode expor N _delivery options_ CloudFormation, mas **não** consegue medir nem
cobrar por-módulo. Logo, "1 produto vs 1 por app" é, no fundo, uma decisão
comercial, não técnica.

Decisões tomadas:

| Eixo | Decisão | Consequência |
|------|---------|--------------|
| **Billing / entitlement** | Bundle + **billing externo** (contrato / private offer). Marketplace é canal de deploy/procurement, não de cobrança por módulo. | **1 produto** só — nada de metering por plugin na AWS. |
| **Ativação técnica** | **Flags `Enable*`** num full-stack template. O cliente liga/desliga módulos no launch. | Construir esse template (Fase 1). |
| **Escopo do bundle** | **"Lerian Platform"** — 9 apps do gitops staging (fonte da verdade). | Vai além do core-bank; é o bootstrap da plataforma. |
| **Charts** | **Standalone por app** (cada um seu OCI chart e versão própria). **Sem umbrella chart.** | `helm.yaml` faz N `helm install`, um por módulo habilitado. |
| **Infra por categoria** | **Produto → infra standalone (dedicada); Plugin/Platform-service → infra compartilhada.** | Múltiplos stacks de infra por produto + 1 stack compartilhado. |
| **Localização** | Novo diretório `products/lerian-platform/`. | `products/core-bank/` vira legado. |
| **Tenancy** | **Single-tenant** (bundle é single-customer BYOC). | Sem `MULTI_TENANT_ENABLED`, sem tenant-manager, sem Valkey MT; apps conectam direto na DB. Simplifica os values do seeder. |

**Não** vamos publicar ~15 listings individuais (cada um exigiria review de 3–5
dias, pricing, assets e suporte próprios). O Midaz permanece como está (produto
público próprio, já no ar); o novo produto é a plataforma completa.

### 1.1 Conjunto de apps (fonte: `lerian-aws-gitops` staging) e categoria

Fonte da verdade: `environments/staging/helmfile/applications` (sufixo `-mt` =
multi-tenant).

| App | Categoria | Infra (regra) |
|-----|-----------|----------------|
| midaz (Ledger) | Produto | **Standalone** |
| reporter | Produto | **Standalone** |
| tracer | Produto | **Standalone** |
| fetcher | Produto | **Standalone** |
| flowker | Produto | **Standalone** |
| product-console | Platform service | **Compartilhada** |
| plugin-access-manager | Plugin | **Compartilhada** |
| plugin-br-bank-transfer | Plugin | **Compartilhada** |
| plugin-fees | Plugin | **Compartilhada** |

- **Infra compartilhada** = **um stack dedicado** (não é a infra de um produto):
  os plugins e o console conectam nele. Escopo mínimo confirmado: DocDB comum
  (console usa `midaz-console`; plugins usam suas DBs lógicas). Cache/broker
  compartilhados só entram se algum plugin exigir (a confirmar via deps do gitops).
- As dependências reais de infra por app (Postgres/Mongo/Redis/RabbitMQ/S3) e as
  coordenadas dos charts standalone são extraídas do gitops — ver seção 4.1.

---

## 2. Como o Midaz foi publicado (padrão de referência)

Fonte: inspeção do catálogo (profile `lerian_root`, conta `239025757440`) +
`midaz-cloudformation-foundation`.

- Produto público real: **AMI Product** `prod-x6hkoywzi4csg` — _"Lerian Midaz -
  Source-Available Ledger System"_ (Visibility **Public**). **Não** é SaaS nem
  Container product.
- Expõe **3 delivery options CloudFormation** dentro do mesmo produto:
  `Full Stack` · `Infrastructure (só bancos)` · `Application (só Helm)`.
- Cobrança: **metered/hora**, dimensão `c6i.xlarge` (Hrs).
- Regiões: `us-east-1, us-east-2, us-west-2, eu-west-1, sa-east-1`.
- Entrega técnica: templates CFN aninhados servidos de bucket S3 público, com a
  convenção de parâmetros `MPS3BucketName` / `MPS3BucketRegion` / `MPS3KeyPrefix`.
- Release automatizado por GitHub Actions; a submissão ao catálogo usa a
  **Catalog API** (`aws marketplace-catalog start-change-set`, ação
  `AddDeliveryOptions`) — runbook em `docs/marketplace-changesets.md`.
- Detalhes da ingestão de AMI: role `arn:aws:iam::239025757440:role/AwsMarketplaceAmiIngestion`,
  AMI base Ubuntu, `RecommendedInstanceType: c6i.xlarge`. Templates precisam ser
  copiados para o bucket **gerenciado pelo Marketplace** (`awsmp-cft-...`) antes
  do `AddDeliveryOptions`.

> Observação: o `MarketplaceAMI` presente nos templates é um _placeholder_ exigido
> pelo formulário do Marketplace; o EKS usa AMIs gerenciadas. Mantemos o mesmo
> padrão.

---

## 3. Estado atual do `lerian-cloudformation-foundation`

O repo é uma evolução do `midaz-cloudformation-foundation` reestruturada em torno
de `products/` + um `templates/foundation.yaml` compartilhado. Ele já carrega
**duas filosofias ao mesmo tempo**:

| Padrão | Onde está | Observação |
|--------|-----------|------------|
| 1 produto por app | Cada `products/<x>/infrastructure.yaml` é standalone, versionado e publicável sozinho | Suporta o modelo "1 listing por plugin" (que **não** vamos usar) |
| 1 produto, ativa o que quer | `products/core-bank/application.yaml` (bundle: Ledger + Reporter + Tracer + Console + Fees num Helm) + `templates/foundation.yaml` (cluster compartilhado + add-on stacks) | Base para o nosso caminho |

Arquivos por produto:

- **midaz**: `infrastructure.yaml`, `application.yaml`, `helm.yaml`, `full-stack.yaml`, `README.md` (bundle completo — é a referência de estrutura).
- **core-bank**: `infrastructure.yaml`, `application.yaml`, `helm.yaml` (**falta `full-stack.yaml`**).
- **demais** (tracer, fetcher, flowker, ledger, matcher, reporter, underwriter, product-console, plugin-access-manager, plugin-crm, plugin-fees, plugin-br-bank-transfer-jd, plugin-br-pix-direct-jd, plugin-br-pix-indirect-btg, plugin-br-pix-switch): só `infrastructure.yaml`.

Pipeline de release (`.github/workflows/release.yml`) **já generalizado para N
produtos**: versiona cada `products/<p>/<template>.yaml` de forma independente,
sobe para `s3://lerian-cloudformation-templates/products/<p>/<template>/{vX,latest}/`
e, crucialmente, **copia os templates compartilhados (`templates/*.yaml`) para
dentro do prefixo de cada produto** — exigência do Marketplace: todos os nested
templates precisam compartilhar o mesmo `MPS3KeyPrefix` (`release.yml:391-432`).

Runbook de catálogo já existe: `docs/marketplace-changesets.md` e
`docs/marketplace-delivery-options.md` — mas hoje miram o produto Midaz
(`prod-fildx2w4ikmba`).

### 3.1 Gaps que bloqueiam a publicação

1. **Bucket/OIDC não portado.** `scripts/setup-release-infrastructure.sh:54,74`
   aponta para `infrastructure/s3-templates-bucket.yaml`, mas **o diretório
   `infrastructure/` não existe** no repo Lerian. O setup one-time está quebrado.
2. **Checklist desatualizado.** `docs/MARKETPLACE_CHECKLIST.md` ainda descreve o
   fluxo manual (produto tipo "CloudFormation product" via console), não o fluxo
   multi-produto via Catalog API.

---

## 4. Arquitetura-alvo

```
AmiProduct "Lerian Platform"   (novo — espelha o setup do Midaz:
                                 AMI ingestion, role AwsMarketplaceAmiIngestion,
                                 RecommendedInstanceType c6i.xlarge)
  Delivery options (CloudFormationTemplate):
   1. Foundation        -> só VPC + EKS (cluster compartilhado)          [templates/foundation.yaml]
   2. Full Stack        -> products/lerian-platform/full-stack.yaml       [ARTEFATO PRINCIPAL]
                            + flags Enable* (infra por categoria + charts standalone)
   3. Application only   -> Helm sobre cluster existente                  [products/lerian-platform/application.yaml]
  Billing: contrato / private offer (nada de metering por módulo)
  Regiões: us-east-1, us-east-2, us-west-2, eu-west-1, sa-east-1
```

### 4.1 Design do `products/lerian-platform/full-stack.yaml` (novo)

Base estrutural: `products/midaz/full-stack.yaml` (nested stacks +
`UseExistingCluster`/`Existing*` + bloco `MPS3*` + `MarketplaceAMI` +
`ProjectName = !Ref AWS::StackName`).

**Modelo de infra — ESCOLHA DO CLIENTE via `InfraTopology` (decisão travada):**

Parâmetro global `InfraTopology` com dois valores; default `shared` (espelha o gitops):

- **`shared`** (recomendado, = topologia provada no gitops): **1 RDS + 1 DocDB +
  1 ElastiCache + 1 AmazonMQ**, com **DBs lógicas por app**. S3 por app onde
  necessário. As flags `Enable*` só ligam/desligam os **releases Helm** (charts
  standalone); a infra é sempre o conjunto compartilhado. Menor custo, sem
  retrabalho de values.
- **`dedicated`** (infra separada por app): cada app habilitado ganha sua própria
  infra conforme suas deps (seção 4.2). `ProjectName` sufixado por app
  (`${AWS::StackName}-<app>`) p/ evitar colisão de nomes físicos (SGs, secrets,
  subnet groups). Mais isolamento; mais caro/lento; exige que os values de cada
  chart apontem para os endpoints isolados (ajuste no `helm.yaml`, Fase 1.2).

Implementação: `Condition IsShared / IsDedicated`; os stacks de infra compartilhada
e os por-app coexistem no template, gateados por essas Conditions + as `Enable*`.
A camada Helm resolve endpoint/secretArn/KMS de cada módulo via `!If [IsShared, <shared>, <perApp>]`.

**Charts — STANDALONE (sem umbrella).** O `helm.yaml` (Fase 1.2) instala **um chart
por módulo habilitado**, cada um com sua `ChartVersion` própria, apontando para a
infra da sua categoria. Ordem: Ledger antes dos que o consomem (Fees, Console).

**Parameters de flag (1 por app do bundle):**

```yaml
DeployApplication: { Default: "true" }   # deploy Helm de tudo (false = infra-only)
# Produtos (infra standalone)
EnableLedger:      { Default: "true"  }
EnableReporter:    { Default: "false" }
EnableTracer:      { Default: "false" }
EnableFetcher:     { Default: "false" }
EnableFlowker:     { Default: "false" }
# Platform service (infra compartilhada)
EnableConsole:     { Default: "true"  }
# Plugins (infra compartilhada)
EnableAccessManager: { Default: "false" }
EnableBankTransfer:  { Default: "false" }
EnableFees:          { Default: "false" }
```

**Composição (nested stacks):**
1. **Foundation** (cond. `CreateNewCluster`): `vpc`, `eks`, `route53`,
   `alb-controller`, `external-dns` — respeitando `UseExistingCluster`.
2. **Infra por produto** (cond. `Enable<Produto>`), com `ProjectName` sufixado:
   - Ledger: `rds` + `documentdb` + `elasticache` + `amazonmq`
   - Reporter: `documentdb` + `elasticache` + `amazonmq` + bucket S3
   - Tracer: `rds`
   - Fetcher / Flowker: conforme deps do gitops (seção 4.2 — a preencher)
3. **Infra compartilhada** (cond. `ShouldDeploySharedInfra`): `documentdb` comum
   (+ cache/broker só se algum plugin exigir).
4. **Aplicação**: stacks Helm (variantes ALB / no-ALB como no midaz full-stack)
   que recebem as flags + endpoints/secret ARNs/KMS de cada infra e instalam os
   charts standalone selecionados.

**Manter:** bloco `MPS3*`, `MarketplaceAMI`, `ParameterGroups`/`ParameterLabels`,
todos os `TemplateURL` no formato
`!Sub "https://${MPS3BucketName}.s3.${MPS3BucketRegion}.${AWS::URLSuffix}/${MPS3KeyPrefix}<name>.yaml"`.

### 4.2 Dependências de infra por app (fonte: `lerian-aws-gitops` staging)

Extraído dos `helmfile.yaml`/`values.yaml`. No gitops **tudo compartilha** um RDS,
um DocDB, um Valkey e um AmazonMQ (separação lógica por DB/user/fila). No modo
`dedicated` cada app instancia só o que usa.

| App | Chart OCI : versão | Namespace | Postgres (DB) | Mongo/DocDB (DB) | Valkey | RabbitMQ | S3 |
|-----|--------------------|-----------|---------------|------------------|--------|----------|-----|
| midaz | `midaz-helm` : 5.7.0 | midaz-mt | onboarding, transaction (+replicas), user `midaz` | onboarding, transaction, midaz-crm | ✅ shared | ✅ users transaction/consumer | — |
| reporter | `reporter-helm` : 2.3.0-beta.1 | reporter | — | reporter | ✅ shared | ✅ `reporter.*` (+ consome `fetcher.job.events`) | `lerian-staging-reporter` |
| tracer | `tracer-helm` : 2.0.0-beta.7 | tracer | tracer | — | MT only | — | — |
| fetcher | `helm-internal/flowker-helm` : 1.0.0 ⚠️ | fetcher-mt | — | fetcher-db | ✅ shared | ✅ `fetcher.*` | `lerian-staging-fetcher` |
| flowker | `flowker-helm` : 3.1.1 | flowker-mt | flowker_audit | flowker | ✅ shared (DB1) | — | `lerian-staging-flowker` |
| product-console | `product-console-helm` : 2.2.0 | product-console | — | product-console-mt | — | — | — |
| plugin-access-manager | `plugin-access-manager` : 6.1.1 | plugin-access-manager | casdoor (user `auth`) | — | ✅ shared | — | — |
| plugin-br-bank-transfer | `plugin-br-bank-transfer-helm` : 1.1.0-beta.4 ⚠️ | plugin-br-bank-transfer-mt | per-tenant (pool via `POSTGRES_PASSWORD`) | per-tenant | ✅ shared (DB0) | — | — |
| plugin-fees | `plugin-fees-helm` : 5.4.0-beta.2 | plugin-fees | — | plugin-fees-db | MT only | — | — |

**Grafo de dependência de runtime (importa para ordem de deploy e service discovery):**
- Todos os apps chamam **plugin-access-manager** (auth `:4000`, identity `:4001`)
  → access-manager sobe primeiro.
- **midaz/ledger** (`:3002`) e **crm** (`:4003`) são consumidos por: console, fees,
  bank-transfer, fetcher (M2M), flowker.
- **reporter** consome **fetcher** (bucket + eventos).
- **product-console** aponta para as URLs in-cluster de TODOS (`:3002/:4003/:4005/
  :4006/:4002/:4021/:4000/:4001`) — é o agregador; internet-facing.

**Endpoints compartilhados (referência do gitops):** RDS `shared-stg-postgres…:5432`;
DocDB `shared-stg-docdb…:27017`; Valkey `master.shared-stg-valkey…:6379`;
AmazonMQ `b-aa04154b…mq.sa-east-1.on.aws` (amqps 5671).

**⚠️ Flags a confirmar com o time antes de fechar o `helm.yaml` (Fase 1.2):**
1. **fetcher** usa `helm-internal/flowker-helm:1.0.0` (não um chart próprio de fetcher).
2. **plugin-br-bank-transfer**: comentários citam 2.0.0-beta.x, mas o `version:`
   pinado é `1.1.0-beta.4`.
3. **Valkey MT** (`tenant-manager-devops-valkey`, conta DevOps) é control-plane
   multi-tenant compartilhado — **não** se provisiona por app; no bundle BYOC
   single-customer provavelmente vira o próprio Valkey compartilhado ou é dispensado
   se o bundle não for multi-tenant.
4. **Multi-tenancy**: ✅ **RESOLVIDO — single-tenant.** Os values do gitops estão em
   MT (`MULTI_TENANT_ENABLED=true`, tenant-manager, Valkey MT); o seeder renderiza em
   **single-tenant**: `MULTI_TENANT_ENABLED=false`, sem tenant-manager, sem Valkey MT,
   conexão estática de DB por app (sem resolução por-tenant em runtime). Simplifica
   bastante — remove o control-plane MT e o Valkey da conta DevOps.

### 4.3 Quirks/coupling a resolver na Fase 1.2 (helm.yaml)

- **Nome do release vs service names hardcoded**: o `core-bank/helm.yaml` legado
  usa `core-bank-*` fixo nas URLs internas mas release = `ProjectName`. Com charts
  standalone, cada release tem nome próprio; padronizar service discovery entre
  módulos (ex.: Fees→Ledger, Console→Ledger/Reporter) via os base-paths reais do
  gitops.
- **Bootstrap de DBs/users**: infra standalone por produto simplifica (cada produto
  dono do seu cluster), mas o stack compartilhado precisa criar as DBs lógicas de
  console/plugins.

### 4.4 Gerenciamento pós-deploy (lifecycle) — GitOps seeder

**Problema:** o cliente faz o bootstrap pelo Marketplace (day-0) — e depois? Precisa
manter o ciclo de vida da **infra** e das **apps** (upgrades, escala, ligar/desligar
módulo, rollback, patch, backup/DR). O `helm install` imperativo via Lambda é ótimo
para day-0 e **péssimo para day-2** (one-shot, sem rollback/health/reconciliação).

**Decisão travada — dois control planes distintos:**

| Ciclo | Control plane | Day-2 |
|-------|---------------|-------|
| **Infra** (VPC/EKS/RDS/DocDB/cache/MQ) | **CloudFormation** `update-stack` (nativo do bootstrap) | escalar RDS/nós, versão do K8s, backup/DR (já nos templates), rollback via changeset |
| **Apps** (releases Helm) | **GitOps (ArgoCD)** — mesmo modelo do `lerian-aws-gitops` (`apps/app-of-apps.yaml`) | bump de versão, ligar/desligar módulo, tunar values, rollback, drift, health |

**Mecanismo — o Lambda do full-stack vira um "GitOps seeder"** (não mais `helm install`):

```
CFN full-stack (day-0):
  provisiona infra + EKS
  Lambda seeder:
    1. renderiza values/<app>.yaml a partir dos OUTPUTS do stack
       (endpoints + secret ARNs + buckets + flags Enable*)   ← o CFN já tem tudo
    2. git push -> repo GitOps do cliente (deploy key)         [seed-once]
    3. instala ArgoCD + External Secrets Operator (ESO)
    4. ArgoCD aponta para o repo e reconcilia (app-of-apps)
depois: o repo é a source of truth; day-2 = commit/PR
        as flags Enable* do CFN valem SÓ para o day-0 (seed)
```

Por que é melhor que o `helm install` direto: a lógica vira "renderizar config
versionada" (testável/auditável) e o day-2 fica com o ArgoCD (rollback/health/drift)
— exatamente o modelo que a Lerian já opera. É também onde o **Lifecycle Management**
e o **ungoliant-controller** plugam (canal de update: Lerian abre PR no repo do cliente).

**3 guardrails inegociáveis:**
1. **Commitar ARN/endpoint, NUNCA senha.** Os outputs dão *secret ARNs* (seguros p/
   Git); o values referencia o ARN e o **ESO** resolve em runtime → repo só tem config.
2. **Repo existente + deploy key (`NoEcho`), sem escopo de criação.** O CFN só faz
   `push` a um repo que o cliente já criou — não cria repo (evita token amplo/review).
3. **Seed-once, não clobber.** No `update` do stack o seeder NÃO sobrescreve `main`
   (senão apaga o day-2 do cliente): escreve só se vazio, ou via branch + PR.

**Fronteiras/observações:**
- **VCS-agnóstico** (GitHub/GitLab/CodeCommit — ArgoCD e `git push` funcionam em qualquer Git).
- **Opcional (default OFF)**: sem `GitOpsRepoUrl`/deploy key, o seeder cai no
  **fallback `helm install` self-contained** — sem ArgoCD, sem Git externo, sem push
  creds e **sem saída pra internet**. O produto sobe out-of-the-box (bom p/ review do
  Marketplace e p/ trial); day-2 = `update-stack`/helm manual. GitOps é opt-in para
  quem quer day-2 gerenciado.
- **Custo honesto**: o CFN passa a exigir credencial de `push` + saída pra internet →
  item de review no Marketplace e na segurança do cliente. Manter opcional mitiga.

---

## 5. Plano de execução (fases)

### Fase 0 — Corrigir gaps de release (bloqueante)
- [ ] **0.1** Portar `infrastructure/s3-templates-bucket.yaml` do repo Midaz →
      Lerian (bucket público + OIDC role escopado a `repo:LerianStudio/lerian-cloudformation-foundation:*`).
      Ajustar `S3_BUCKET`/região se o bucket alvo for `lerian-cloudformation-templates`.
- [ ] **0.2** Validar `scripts/setup-release-infrastructure.sh` contra o template portado.
- [ ] **0.3** Atualizar `docs/MARKETPLACE_CHECKLIST.md` para o fluxo Catalog-API
      multi-produto (referenciar `marketplace-changesets.md`).

### Fase 1 — Construir o full-stack com flags (único trabalho de eng. real)
- [x] **1.1a** Criar `products/lerian-platform/full-stack.yaml` — topologia
      **`shared`** completa: foundation + infra compartilhada (RDS/DocDB/ElastiCache/
      AmazonMQ) + buckets S3 por app (reporter/fetcher/flowker) + 9 flags `Enable*` +
      handoff para `helm.yaml` (variantes ALB/no-ALB). **cfn-lint: 0 erros** (mesmo
      perfil de warnings do `midaz/full-stack.yaml`). Registrado em
      `template-versions.json` → `products.lerian-platform.full-stack = 0.1.0`.
- [x] **1.1b** Topologia **`dedicated`** (isolamento total por app) entregue via
      **nested template reutilizável `products/lerian-platform/app-stack.yaml`**
      (registrado `app-stack = 0.1.0`; **cfn-lint: 0 erros**). Em vez de um único helm
      resolvendo `!If [IsShared, …]`, cada app habilitado ganha um `<App>AppStack`
      (gate `IsDedicated AND Enable<app>`) que provisiona **sua própria infra** conforme
      as deps da seção 4.2 (flags `Need{RDS,DocumentDB,ElastiCache,AmazonMQ,S3}`) e
      deploya **só aquele módulo** via `helm.yaml OnlyApp=<appkey>` apontando para os
      endpoints da própria infra. `ProjectName` sufixado (`${AWS::StackName}-<app>`).
      `dedicated` incluído em `AllowedValues` de `InfraTopology`.
      - **helm.yaml ajustado p/ dedicated:** `OnlyApp` (deploy de 1 app), `get_secret`
        e `render_values` tolerantes a ARN vazio (app sem certo serviço), e IAM policy
        com secret ARNs condicionais (`HasRDSSecret`/`HasDocumentDBSecret`/`HasAmazonMQSecret`).
        Os helm stacks **shared** ganharam gate `IsShared`; os buckets S3 top-level idem
        (no dedicated cada app cria o seu dentro do app-stack).
      - **Validado:** contrato de params app-stack↔leaf templates (rds/docdb/cache/mq/helm)
        cross-checado; GetAtt aos outputs dos leaf conferidos; simulação offline dos 9
        perfis dedicated (OnlyApp + render + secret_data tolerante) passou.
      - **Caveat conhecido (dedicated):** apps que leem a DB de outro app (ex.: reporter
        `DATASOURCE_ONBOARDING` → Postgres do ledger) ficam sem essa credencial no modo
        isolado — precisa injetar o endpoint/secret do produtor (follow-up sandbox 1.5).
        Ordenação EKS/ALB p/ os app-stacks via `DependencyHint` (GetAtt do parent).
- [x] **1.2** Criado `products/lerian-platform/helm.yaml` (**cfn-lint: 0 findings**;
      Python embutido compila; registrado em `template-versions.json` →
      `products.lerian-platform.helm = 0.1.0`). Lambda custom-resource (`python3.13`)
      com os dois modos:
      - **1.2a ✅** Renderiza values por-app + `ExternalSecret` (modo GitOps) a partir
        dos outputs do stack e das flags `Enable*`. **Correção-chave:** o Secret de
        runtime agora é **fiado nos charts** via `useExistingSecret`/`existingSecretName`
        com as **chaves exatas por chart** (contrato provado do `core-bank`: midaz
        `DB_ONBOARDING_PASSWORD`…, reporter `DATASOURCE_ONBOARDING_PASSWORD`/`APP_ENC_KEY`,
        console `NEXTAUTH_SECRET` gerado) + `REDIS_CA_CERT` p/ TLS ElastiCache. Antes o
        Secret era genérico e **órfão** (senhas nunca chegavam aos pods). O `ExternalSecret`
        do modo GitOps emite as **mesmas chaves** via `target.template` (sem valor de
        secret no Git — guardrail #1; `NEXTAUTH_SECRET` via `randAlphaNum` do ESO).
      - **1.2b ✅** Instala **ArgoCD** + **External Secrets Operator**.
      - **1.2c ✅** `git push` seed-once via **deploy key** (`NoEcho`); no `update` não
        sobrescreve `main` (guardrail #3). **git de fato funcional no Lambda**: como o
        runtime `python3.13` não traz git, o `install_tools` baixa um git self-contained
        (git-lambda-layer, URL pinada + overridable via `GIT_LAYER_URL`) e fail-fast com
        mensagem clara se faltar. Parâmetros novos **fiados no `full-stack.yaml`** (Parameters
        + ParameterGroups + pass-through nos 2 helm stacks): `GitOpsRepoUrl`, `GitOpsBranch`,
        `GitOpsPath`, `GitOpsDeployKey` (`NoEcho`) — todos opcionais (fallback helm-install).
      - **Quirks 4.3 resolvidos**; MT = single-tenant (`MULTI_TENANT_ENABLED=false` em
        todos). **Pendências ⚠️ (decisão: seguir com defaults+TODO):** coordenadas do
        chart do fetcher (`helm-internal/flowker-helm:1.0.0`) e versão do bank-transfer
        (`1.1.0-beta.4`) ficam como defaults overridable a confirmar com o time.
      - **A validar no sandbox (Fase 1.5):** chaves exatas de secret/values dos charts
        que o `core-bank` não cobria (fetcher, flowker, bank-transfer — marcados
        `(validate)` no código); a URL exata do `git-lambda-layer`; e o **bootstrap de
        users PG** dos apps novos (flowker `flowker_audit`, bank-transfer `bank_transfer`)
        no stack de infra compartilhada.
      - **1.2d — Access Manager render CORRIGIDO** (contra o chart real
        `LerianStudio/helm/charts/plugin-access-manager`, analisado direto do GitHub).
        O render antigo era inventado (`backend.postgres`/`identity.redis`); o novo bate:
        subcharts `auth-database`/`valkey` **OFF** (usa RDS/ElastiCache gerenciados),
        `auth.configmap.DB_*` (DB `casdoor`, **user = master do RDS** p/ o Casdoor criar a
        própria DB, `DB_SSLMODE=require`), `auth`/`identity` `configmap.REDIS_*`
        (`REDIS_USER=default`, TLS+CA), `common.authorizer.clientId`, e `initUser` (admin
        do Console). Secrets via `useExistingSecret` — `create_runtime_secret` cria **3**
        Secrets do PAM: `<rel>-auth-secrets` (AUTHORIZER_CLIENT_SECRET, DB_PASSWORD,
        REDIS_PASSWORD, LICENSE_KEY, ORGANIZATION_IDS, MFA_SECRET, SD_TOKEN),
        `<rel>-identity-secrets` (subset) e `<rel>-admin` (ADMIN_PASSWORD, criado só se
        ausente → senha estável). Params novos no helm+full-stack: `AuthorizerClientId`,
        `AuthorizerClientSecret` (NoEcho, default = seed), `AccessManagerLicenseKey`
        (NoEcho), `AccessManagerOrganizationIds`, `ConsoleAdminPassword` (NoEcho, auto-gen
        se vazio). **cfn-lint 0 findings; render validado offline.**
      - **1.2f — Renders por-app são CHUTES ESTRUTURAIS (workstream aberto).** Ao
        analisar os charts reais (via GitHub `LerianStudio/helm`) ficou claro que os
        `render_values` foram escritos por inferência e **não batem** com a estrutura dos
        charts: access-manager usava `backend.postgres`/`identity.redis` inexistentes
        (CORRIGIDO, 1.2d); bank-transfer namespaceia tudo sob **`bankTransfer.*`**
        (`bankTransfer.configmap`/`secrets`/`useExistingSecret`) mas o render usa top-level
        (PENDENTE). **Consequência:** até o render de cada app ser verificado contra seu
        chart, os values (e os secrets fiados) não são carregados corretamente. Os 8 renders
        (ledger/reporter/tracer/fetcher/flowker/fees/bank_transfer/console) precisam de
        rewrite chart-verificado — não só do marcador `(validate)`.
        **Corrigidos até agora:** access-manager (1.2d) e **bank-transfer** — este
        reescrito p/ a estrutura real `bankTransfer.*` (subcharts pg/mongo/valkey/rabbitmq
        OFF; `global.externalPostgresDefinitions` bootstrapa DB+role `bank_transfer` na RDS
        compartilhada c/ admin/role creds vindos do Secret injetado; `useExistingSecret` →
        envFrom carrega tudo). O Secret do bank-transfer agora traz **todas** as chaves que
        o chart exige: `DB_USER_ADMIN`/`DB_ADMIN_PASSWORD`/`DB_PASSWORD_BANK_TRANSFER`
        (extPG), `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `MONGO_URI` (URI-only, url-encoded),
        `LICENSE_KEY`, as 2 AES keys **obrigatórias** (`JD_INCOMING_RAW_XML_ENCRYPTION_KEY`,
        `RECIPIENT_DETAILS_ENCRYPTION_KEY`, geradas **store-once**) + os 6 M2M
        (`MIDAZ/CRM/FEES_CLIENT_ID/SECRET`). **Fatia vertical M2M FECHADA** (Job cria apps →
        `lerian-m2m` → injeção → bank-transfer consome via envFrom). Validado offline +
        cfn-lint 0.
      - **SWEEP DOS 8 RENDERS CONCLUÍDO** (via 6 agentes paralelos extraindo o contrato real
        de cada chart do `LerianStudio/helm`). `render_values` + `create_runtime_secret`
        reescritos chart-verificados; 9 renders = YAML válido, secrets com chaves exatas,
        cfn-lint 0. Correções-chave:
        - **ledger (midaz):** nesting `ledger.*` unificado (não `onboarding`/`transaction`);
          `REDIS_HOST` combinado `host:port`; RabbitMQ `_URI`/`_DEFAULT_USER`/`_CONSUMER_USER`;
          `PLUGIN_AUTH_HOST` (não ADDRESS); desliga grafana+otel; **CRM habilitado** (secret
          próprio `midaz-crm-secrets` c/ `LCRYPTO_*` store-once); `externalPostgresDefinitions`
          cria onboarding+transaction+role midaz.
        - **tracer:** faltava `ENV_NAME` (fail-fast) + `externalPostgresDefinitions` (role/db tracer).
        - **reporter:** `FETCHER_URL` (não `_ADDRESS`); `DATASOURCE_ONBOARDING_*` (lê o Postgres
          do ledger); RabbitMQ `_URI`/`_EXCHANGE`/`_QUEUE`; desliga **KEDA**; `APP_ENC_KEY` store-once.
        - **fetcher:** é um **chart PRÓPRIO `fetcher-helm`** (manager/worker/common), NÃO
          flowker-helm; `STORAGE_PROVIDER=s3`; 4× `CRYPTO_*`+`APP_ENC_KEY` store-once. REGISTRY
          repo→`fetcher-helm` v3.1.0 (⚠️ confirmar vs gitops que pina flowker-helm).
        - **flowker:** chart PRIVADO `helm-internal/flowker-helm` v1.1.0; `flowker.*`; MT via
          `flowker.multiTenant.enabled`; Mongo via secret `MONGO_URI`; `AUDIT_DB_*`; S3 via IRSA.
        - **fees:** `fees.*` (não top-level); mongodb off+external; **M2M via `CLIENT_ID`(cfgmap)+
          `CLIENT_SECRET`(secret, REQUIRED)** = authorizer.
        - **console:** keys corrigidas (`MIDAZ_API_HOST/PORT`, `PLUGIN_AUTH_CLIENT_ID/HOST/PORT`,
          `MONGODB_USER`); `FETCHER/FLOWKER/PLUGIN_FEES_BASE_PATH` **não existem**; secret
          `MONGODB_PASS`+`NEXTAUTH_SECRET`(store-once)+`PLUGIN_AUTH_CLIENT_SECRET`; `ENABLE_TELEMETRY=false`.
        **Decisões (documentadas):** creds **master do RDS/DocDB/MQ** p/ simplificar bootstrap de
        user (PG via `externalPostgresDefinitions`); chaves geradas obrigatórias **store-once**.
        **Gaps/validate restantes:** DB `flowker_audit` sem bootstrap no chart (pré-criar); reporter
        DATASOURCE cross-DB (ok em `shared`, quebra em `dedicated`); `secret_key_sources` do GitOps
        **dessincronizada** dos novos secrets (re-sync = follow-up junto do GitOps M2M); confirmar
        coordenada/versão do chart fetcher (fetcher-helm vs flowker-helm).
      - **1.2g — HARNESS DE TESTE LOCAL** (`scripts/test-local-deploy.{py,sh}`): extrai o
        Python do Lambda, mocka AWS, e roda **`helm template` contra os charts OCI reais**
        (valida values + `values.schema.json` sem cluster/CFN) + secrets + dry-render do
        seed GitOps. **Os 9 módulos passam** (`helm template` OK). O harness pegou 2 guards
        de chart que a validação offline não via: flowker exige `MONGO_HOST` no configmap
        (mesmo com `MONGO_URI` no secret) e bank-transfer exige `JD_BASE_URL` ou
        `JD_SANDBOX_MODE=true` — ambos CORRIGIDOS (flowker MONGO_HOST/PORT; bank-transfer
        `JD_SANDBOX_MODE=true`+`JD_POLLING_ENABLED=false`, cliente wira o rail JD depois).
        Uso: `scripts/test-local-deploy.sh [--apps a,b] [--no-helm] [--gitops]`. Charts
        privados (flowker helm-internal) exigem `helm registry login ghcr.io`.
      - **1.2e — M2M do PAM (Job IMPLEMENTADO + validado).** Doc + chart analisados. Achados:
        (a) credencial-mãe = client authorizer **`app-lerian`** (`AUTHORIZER_CLIENT_ID`
        `ac56c81d4d6d95c0ac12` + `AUTHORIZER_CLIENT_SECRET` seed `6add4bc…`, fixo no
        `files/init_data.json`); (b) fluxo: `POST auth:4000/v1/login/oauth/access_token`
        (client_credentials) → token admin → `POST identity:4001/v1/applications {name}`
        → `clientId/clientSecret` (só volta na criação → **store-once**); (c) **dois lados**:
        resource-servers (ledger/crm/reporter/tracer/fetcher) só validam token
        (`PLUGIN_AUTH_ENABLED`+`ADDRESS`, já feito); callers (bank-transfer/fees/flowker)
        guardam **1 par por alvo**: `MIDAZ_CLIENT_ID/SECRET`, `CRM_CLIENT_ID/SECRET`,
        `FEES_CLIENT_ID/SECRET` (confirmado no chart `plugin-br-bank-transfer`). **Decisões:**
        Job de bootstrap **in-cluster** `m2m-bootstrap` (funciona nos 3 modos; ArgoCD só
        referencia os Secrets) + credencial-mãe = **authorizer seedado pelo chart**.
        **IMPLEMENTADO no helm.yaml (helm-install):** após o PAM subir (`order=0`, `--wait`),
        `run_m2m_bootstrap` aplica ServiceAccount+Role+RoleBinding+ConfigMap+Job (Python
        `urllib`, image `python:3.13-alpine`): pega token admin em `auth:4000`, cria as
        Applications em `identity:4001`, grava o Secret central `lerian-m2m` na ns do PAM
        (**store-once** — pula se já existe; delete+reapply do Job p/ re-run idempotente),
        e o deployer lê de volta e injeta `<TARGET>_CLIENT_ID/SECRET` no Secret do consumer.
        **Só o `plugin-br-bank-transfer` consome** (MIDAZ/CRM/FEES — confirmado nos charts;
        fees/flowker/reporter/fetcher/crm **não** têm chaves M2M na versão atual). Validado:
        manifests = YAML válido, `bootstrap.py` compila, injeção confere. **Depende de 1.2f**
        (render do bank-transfer com `bankTransfer.useExistingSecret`/`existingSecretName`
        pra o Secret injetado ser carregado via envFrom).
        **Hardening:** rotacionar o `AUTHORIZER_CLIENT_SECRET` (exige `init_data.json`
        custom) — o default é público. **Follow-ups:** M2M nos modos `dedicated`/GitOps
        (hoje o Job roda no fluxo helm-install do deployer); forward dos params do PAM no
        `dedicated` (app-stack); `ExternalSecret` do PAM no GitOps (2 secrets + admin).
- [x] **1.3** `products/lerian-platform/application.yaml` — delivery option "Application
      only" (registrado `application = 0.1.0`; **cfn-lint 0 erros**). Importa cluster +
      endpoints/secretArns/KMS via `Fn::ImportValue` de `${InfrastructureStackName}-*` e
      invoca o `helm.yaml`. Para isso, o `full-stack.yaml` passou a **exportar** os
      SecretArn+KMS (+ RDS replica) além dos endpoints (todos `IsShared`). Buckets S3 e
      config de app (flags/ingress/gitops/access-manager) vêm por parâmetro. Contrato
      application→helm validado (sem param desconhecido/faltando). Só faz sentido em
      topologia `shared` (o `dedicated` não tem endpoint único).
- [x] **1.4** Validação estática: **cfn-lint 0 erros** (4 templates); **checkov 0 failed**
      (13 passed/3 skipped no helm.yaml IAM+Lambda; skips justificados = DLQ/VPC/env-enc do
      deployer one-shot); MPS3* presentes + sem `TemplateURL` relativo (marketplace-compliance).
      Caveat: o checkov pula silenciosamente os 3 templates grandes de nested-stack (limitação
      do parser); os S3 buckets deles são endurecidos (encryption+PAB+versioning+lifecycle,
      validado num bucket isolado). **Harness local** (`helm template` real) cobre o que o
      checkov não pega.
- [ ] **1.5** Teste de deploy real numa conta sandbox (Foundation + Full Stack com
      2–3 módulos, topologia `shared`) antes de submeter ao Marketplace.
- [ ] **1.6** CodeRabbit review do branch ANTES de abrir PR (regra do time).

### Fase 1.5 — Deploy real em sandbox (EM ANDAMENTO, 2026-08-18)
Conta sandbox `524121347244`, sa-east-1, deploy dos templates LOCAIS via bucket scratch
(≠ release), `--on-failure DO_NOTHING`. Config enxuta, InfraTopology=shared, 8 módulos
(flowker OFF a pedido). **Achados reais que o e2e pegou (que lint/harness não pegam):**
1. **Deployer não autenticava em registry OCI privado** → adicionado `helm registry login`
   (params `HelmRegistryHost/User/Token` + login no do_helm_install/do_gitops_seed). O flowker
   (helm-internal) era o único chart privado; como foi removido do produto, ficou como capacidade.
2. **`DeletionPolicy: Retain` nos buckets S3** → os buckets sobrevivem ao `delete-stack` e um
   redeploy homônimo **colide** no nome do bucket (`BucketAlreadyExists` reportado como
   "Validation failed with N errors", N = nº de módulos-com-bucket). **Gotcha operacional**:
   limpar os buckets entre deploys de teste (prod: OK, os nomes são estáveis por conta/stack).
3. **RDS `EngineVersion` default `16.8` obsoleto** (sa-east-1 só tem 16.9+) E o full-stack **não
   expunha** EngineVersion → não overridável. **Fix produtização:** adicionado `RDSEngineVersion`
   (default `16.9`) no full-stack, passado ao RDSStack. (DocDB `5.0.0` está OK.)
4. **AmazonMQ `mq.t3.micro` inválido pro RabbitMQ** (mínimo `mq.m5.large`) — erro de tuning do
   teste, não do template; corrigido nos params.
5. **`REDIS_CA_CERT` estourava o `exec`** — eu injetava o **bundle GLOBAL de CAs do RDS**
   (~165KB → base64 ~220KB) num env var. Um único env var >128KB (`MAX_ARG_STRLEN` do Linux)
   faz **`exec /bin/sh: argument list too long`** em TODO container que carrega o env via
   envFrom (o init `wait-for-dependencies` crashava). **Fix:** `get_aws_ca_cert_base64` passou
   a buscar o **bundle REGIONAL** (`<region>-bundle.pem`, ~4.5KB → base64 ~6KB).
6. **Imagens Lerian são amd64-only** — com nós **Graviton/ARM64** (`c7g.xlarge` default) o
   auth-backend (Casdoor) falha com **`exec format error`**. **Fix (config):** usar nós **x86**
   (`c6i.xlarge`) no bundle. (Ideal futuro: imagens multi-arch.)
7. **VPC Flow Logs log group também é `Retain`** (`/aws/vpc/<stack>-flow-logs`) → colide no
   redeploy homônimo (mesma família do #2). Pro teste: `EnableFlowLogs=false` (evita + mais barato).
   Padrão geral: **todo recurso `Retain` de nome fixo** (buckets, log groups) colide em redeploy
   com o mesmo nome de stack — limpar entre iterações de teste (em prod é 1 stack, sem colisão).
8. **`eks.yaml` hardcodava `AmiType: AL2023_ARM_64_STANDARD`** (Graviton) → `c6i.xlarge` (x86)
   era rejeitado (`not a valid instance type for requested amiType`). Raiz do #6: o template
   assumia nós ARM64, incompatível com imagens amd64. **Fix produtização:** `NodeAmiType` virou
   **param** no `eks.yaml` + full-stack (default **`AL2023_x86_64_STANDARD`**, pois as imagens são
   amd64) + default de `NodeInstanceType` mudou pra **`c6i.xlarge`** (x86). ARM64 continua possível
   (set NodeAmiType+node type ARM) se as imagens forem multi-arch — decisão do time.
9. **Órfãos `Retain`/nome-fixo bloqueiam redeploy do MESMO nome de stack** — deletar a stack
   deixa: KMS keys (janela de deleção 7-30d) + **aliases**, **DB subnet groups** (rds/docdb),
   **DB cluster parameter groups** (`<stack>-documentdb-params`), S3 buckets, VPC flow-log log
   group — todos nomeados por `${ProjectName}` (=stack name). Um redeploy homônimo colide
   (DocDB `Validation failed with 1 error` = o param group já existia → cancela os irmãos).
   **Impacto:** upgrade-in-place / recreate do MESMO stack quebra; em Marketplace (nome único,
   1 deploy) é OK. **Workaround de teste:** nome de stack novo por iteração (`sbx2`, `sbx3`…) —
   zero colisão, sem limpeza. **Fix produtização (futuro):** `DeletionPolicy` coerente +
   `ForceDeleteWithoutRecovery` nos secrets/nomes com sufixo, pra permitir recreate homônimo.
Cada camada só aparece no deploy real. **Estratégia de teste (decisão do usuário):** CF sobe
**só a infra** (`DeployApplication=false`); o helm-install é dirigido manualmente no cluster vivo
(`run-deployer-live.py`, com os valores exatos do Lambda) pra iterar bugs de app sem rebuild;
`--on-failure DO_NOTHING` garante que a infra não é destruída em erro de helm. Deploy final flipa
`DeployApplication=true` (`update-stack`) pra validar o caminho CF→Lambda→helm.

### Flowker REMOVIDO do produto (2026-08-18)
O **flowker** foi removido do bundle (é chart **privado** `helm-internal/flowker-helm` — clientes
externos/Marketplace não conseguem puxar). Removido de **helm.yaml** (REGISTRY, render_values,
create_runtime_secret, secret_key_sources, params `EnableFlowker`/`FlowkerChartVersion`/
`FlowkerStorageBucketName`, envs, `FLOWKER_URL`, ConfigHash) **+ full-stack.yaml** (param, grupo,
label, conditions `EnableFlowkerCond`/`DedicatedFlowker`/`SharedFlowkerBucket`, `FlowkerStorageBucket`,
`FlowkerAppStack`, output, 13 forwards) **+ application.yaml + app-stack.yaml**. Módulos agora = **8**
(ledger+crm, access-manager, tracer, reporter, fetcher, fees, bank-transfer, console). Validado:
4 templates 0 erros, Python compila, harness 8/8, contratos de param cross-checados. A capacidade
`helm registry login` (params `HelmRegistry*`, default vazio) foi mantida como opcional/dormante.

### Fase 2 — Release → S3
- [ ] **2.1** Merge em `main` tocando `products/lerian-platform/**` dispara `release.yml`.
- [ ] **2.2** Confirmar upload em `releases/vX/products/lerian-platform/` **com os
      templates compartilhados copiados** para o mesmo prefixo (nested-URL rule).

### Fase 3 — Catálogo Marketplace
- [ ] **3.1** Criar o AmiProduct "Lerian Platform" (console 1x ou
      `start-change-set` `CreateProduct`).
- [ ] **3.2** Copiar os templates para o bucket gerenciado do Marketplace
      (`awsmp-cft-...`).
- [ ] **3.3** `AddDeliveryOptions` com as 3 delivery options apontando para o
      full-stack — adaptar `docs/marketplace-changesets.md` para o **novo product id**
      (hoje mira `prod-fildx2w4ikmba`/Midaz).
- [ ] **3.4** `AddRegions` (mesmas 5 regiões do Midaz).
- [ ] **3.5** Preencher descrição/UsageInstructions (base:
      `docs/marketplace-delivery-options.md`) e submeter para review (3–5 dias úteis).

---

## 6. Riscos e pontos de atenção

- **Matriz de Conditions**: se muitos módulos exigirem infra dedicada, o
  full-stack pode ficar grande. Mitigação: manter a infra de dados condicional em
  nested stacks e o Helm como único ponto de "ligar módulo".
- **Limite de tamanho de template CFN** (nested URLs + número de recursos):
  monitorar; a estratégia de nested stacks já ajuda.
- **Nested-URL rule do Marketplace**: todos os nested templates precisam do mesmo
  `MPS3KeyPrefix` — o `release.yml` já resolve copiando os compartilhados por
  prefixo de produto. Não quebrar isso.
- **Billing externo**: garantir que o produto no Marketplace fique como
  free/BYOL (ou metering nominal), já que a cobrança real é por contrato.
- **Nome/positioning**: confirmar título comercial ("Lerian Core Banking" vs
  "Lerian Platform") com Produto/Marketing antes de criar o listing.

---

## 7. Próximo passo imediato

Após aprovação deste plano: iniciar pela **Fase 1.1** (rascunho do
`products/core-bank/full-stack.yaml`) — que é o único artefato de engenharia
novo; o restante é reuso do que o Midaz já provou + correção dos 2 gaps da Fase 0.
