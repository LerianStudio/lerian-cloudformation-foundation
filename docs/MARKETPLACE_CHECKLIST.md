# AWS Marketplace - Checklist de Publicação

O produto já está publicado: `prod-fildx2w4ikmba`, entidade `AmiProduct@1.0`,
"Lerian Midaz - Open-Source Ledger System". Este arquivo cobre o que é feito a
cada nova versão da listagem. Os changesets prontos estão em
[marketplace-changesets.md](marketplace-changesets.md), e o texto das delivery
options em [marketplace-delivery-options.md](marketplace-delivery-options.md).

O template que a listagem lança é `templates/foundation.yaml`: VPC + EKS + agent
Lerian. Nenhum template deste repositório instala produto — isso é feito pelo
control plane, através do agent, de dentro do cluster.

---

## 1. Infraestrutura de release (uma vez, já feita)

O bucket de distribuição é `lerian-cloudformation-templates` (sa-east-1), e o
release é publicado nele pelo workflow `.github/workflows/release.yml` via OIDC.

```bash
# Recriar o bucket e a role do GitHub Actions, se necessário
./scripts/setup-release-infrastructure.sh
```

O secret `AWS_ROLE_ARN` do repositório aponta para a role criada por esse script.

---

## 2. Validação pré-Marketplace

### 2.1 Validar templates localmente

```bash
pip install cfn-lint pyyaml
./scripts/validate.sh
```

`validate.sh` roda o parse YAML de todos os templates, confere os parâmetros
obrigatórios de Marketplace em `foundation.yaml`, checa `NoEcho` nos parâmetros
sensíveis, executa `scripts/check-agent-templates.py` (comportamento do handler
do agent e o guarda de parâmetros da foundation), `scripts/check-docs-links.py`
(todo link de template citado na documentação existe no layout de release) e,
se `cfn-lint` estiver instalado, o lint completo.

O CI roda o mesmo conjunto em cada pull request, mais Checkov e cfn-lint em sete
regiões.

### 2.2 Teste de deploy

Um deploy real em conta sandbox é a única verificação de que o caminho de
enrolamento funciona ponta a ponta — nenhum check de CI prova isso. Lance a
`foundation.yaml` com `ControlPlaneURL`, `EnrollmentToken` e `AgentChartVersion`
preenchidos e confirme que o cluster aparece como conectado no console.

```bash
aws cloudformation create-stack \
  --stack-name lerian-foundation-test \
  --template-url https://lerian-cloudformation-templates.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml \
  --parameters \
    ParameterKey=AvailabilityZone1,ParameterValue=sa-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=sa-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=sa-east-1c \
    ParameterKey=ControlPlaneURL,ParameterValue=https://api.lerian.studio \
    ParameterKey=EnrollmentToken,ParameterValue=<token-do-console> \
    ParameterKey=AgentChartVersion,ParameterValue=<versao-do-chart> \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --region sa-east-1

# Limpar após o teste
aws cloudformation delete-stack --stack-name lerian-foundation-test --region sa-east-1
```

---

## 3. Requisitos do AWS Marketplace

### 3.1 Checklist técnico

- [x] Templates hospedados em S3 público
- [x] URLs S3 para nested stacks (não paths relativos)
- [x] Parâmetros MPS3BucketName, MPS3BucketRegion, MPS3KeyPrefix
- [x] Parâmetro `MarketplaceAMI` na `foundation.yaml`, para o binding
      `TemplateSources` exigido pela entidade `AmiProduct`
- [x] NoEcho em parâmetros sensíveis (`EnrollmentToken`)
- [x] AllowedPattern e ConstraintDescription em parâmetros
- [x] Descriptions claras em todos os parâmetros
- [x] Metadata com ParameterGroups e ParameterLabels
- [ ] Deploy de validação em conta sandbox (seção 2.2)

### 3.2 Documentação

- [x] `docs/ARCHITECTURE.md`
- [x] `docs/TROUBLESHOOTING.md`
- [x] `README.md` com a jornada de onboarding
- [x] `products/midaz/README.md`

### 3.3 Assets de marketing

Já publicados na listagem; só precisam de revisão se a arquitetura mudar.

- [x] Logo do produto (120x120 e 250x250)
- [x] Diagrama de arquitetura
- [ ] Screenshots do console (mostrando o cluster conectado e o release do Midaz)

---

## 4. Publicar uma nova versão

1. Merge na `main`. O workflow de release publica em
   `releases/latest/` e em `releases/v<versão>/`, e cria a tag e a GitHub Release.
2. Fazer upload da `foundation.yaml` e de **todos** os templates que ela aninha
   (`vpc`, `eks`, `agent`, `route53`, `alb-controller`, `external-dns`) para o
   bucket S3 do Marketplace, sob um único prefixo compartilhado.
3. Rodar os changesets de [marketplace-changesets.md](marketplace-changesets.md)
   na ordem descrita lá — a ordem importa, a API rejeita dois dos passos fora de
   sequência.
4. Acompanhar em **Products** → **Fulfillment** no Marketplace Portal. Review da
   AWS leva de 3 a 5 dias úteis.

---

## Comandos Úteis

```bash
# Ver versões atuais
./scripts/show-versions.sh

# Validar templates
./scripts/validate.sh

# Ver releases no GitHub
gh release list

# Ver conteúdo do S3
aws s3 ls s3://lerian-cloudformation-templates/releases/ --recursive

# Ver a listagem publicada
aws marketplace-catalog describe-entity \
  --catalog AWSMarketplace --entity-id prod-fildx2w4ikmba --profile lerian_root
```

---

## Links Úteis

- [AWS Marketplace Seller Guide](https://docs.aws.amazon.com/marketplace/latest/userguide/cloudformation-products.html)
- [Work with AMI-based products (Catalog API)](https://docs.aws.amazon.com/marketplace/latest/APIReference/work-with-single-ami-products.html)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)
- [cfn-lint Rules](https://github.com/aws-cloudformation/cfn-lint/blob/main/docs/rules.md)
