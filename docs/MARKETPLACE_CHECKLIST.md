# AWS Marketplace - Checklist de Publicação

## 1. Setup da Infraestrutura (Uma vez)

### 1.1 Criar bucket S3 e IAM Role

```bash
# Configurar variáveis (opcional - já tem defaults)
export BUCKET_NAME="midaz-cloudformation-templates"
export AWS_REGION="us-east-1"
export GITHUB_ORG="LerianStudio"
export GITHUB_REPO="midaz-cloudformation-foundation"

# Executar setup
./scripts/setup-release-infrastructure.sh
```

Isso cria:
- ✅ S3 Bucket com acesso público para templates
- ✅ IAM Role para GitHub Actions (OIDC)
- ✅ Bucket policy para CloudFormation

### 1.2 Configurar GitHub Secret

Após o setup, adicionar o secret no repositório:

1. Ir em **Settings** → **Secrets and variables** → **Actions**
2. Criar **New repository secret**:
   - Name: `AWS_ROLE_ARN`
   - Value: `arn:aws:iam::ACCOUNT_ID:role/midaz-cloudformation-templates-github-actions`

---

## 2. Primeira Release

### 2.1 Inicializar o repositório Git (se ainda não)

```bash
git init
git add .
git commit -m "feat: initial release of Midaz CloudFormation templates"
git remote add origin git@github.com:LerianStudio/midaz-cloudformation-foundation.git
git push -u origin main
```

### 2.2 Verificar Release Automático

Após o push, o workflow `auto-release.yml` irá:
- Criar tags para cada template (ex: `vpc-v0.1.0`)
- Criar tag do bundle (ex: `release-v0.1.0`)
- Upload para S3
- Criar GitHub Releases

---

## 3. Validação Pré-Marketplace

### 3.1 Validar Templates Localmente

```bash
# Instalar cfn-lint
pip install cfn-lint

# Validar todos os templates
cfn-lint templates/*.yaml

# Ou usar o script
./scripts/validate.sh
```

### 3.2 Testar Deploy Manual

```bash
# Testar em us-east-1
aws cloudformation deploy \
  --stack-name midaz-test \
  --template-file templates/midaz-complete.yaml \
  --parameter-overrides \
    EnvironmentName=test \
    AvailabilityZone1=us-east-1a \
    AvailabilityZone2=us-east-1b \
    AvailabilityZone3=us-east-1c \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Limpar após teste
aws cloudformation delete-stack --stack-name midaz-test --region us-east-1
```

---

## 4. Requisitos do AWS Marketplace

### 4.1 Checklist Técnico

- [x] Templates hospedados em S3 público
- [x] URLs S3 para nested stacks (não paths relativos)
- [x] Parâmetros MPS3BucketName, MPS3BucketRegion, MPS3KeyPrefix
- [x] NoEcho em parâmetros sensíveis (passwords, usernames)
- [x] AllowedPattern e ConstraintDescription em parâmetros
- [x] Descriptions claras em todos os parâmetros
- [x] Metadata com ParameterGroups e ParameterLabels
- [ ] Testar em pelo menos 3 regiões (us-east-1, eu-west-1, ap-southeast-1)
- [ ] Documentação do produto

### 4.2 Documentação Necessária

Criar na pasta `docs/`:
- [ ] `ARCHITECTURE.md` - Diagrama de arquitetura
- [ ] `PRICING.md` - Estimativa de custos
- [ ] `USER_GUIDE.md` - Guia de uso
- [ ] `TROUBLESHOOTING.md` - Problemas comuns

### 4.3 Assets de Marketing

- [ ] Logo do produto (120x120 e 250x250)
- [ ] Screenshots do console
- [ ] Descrição curta (< 200 caracteres)
- [ ] Descrição longa (features, benefícios)

---

## 5. Submissão ao Marketplace

### 5.1 Criar Conta de Seller

1. Acessar [AWS Marketplace Management Portal](https://aws.amazon.com/marketplace/management/)
2. Registrar como Seller
3. Completar verificação de identidade
4. Configurar informações de pagamento

### 5.2 Criar Produto

1. **Product** → **Create product** → **CloudFormation**
2. Preencher informações:
   - Product title: `Midaz - Open Source Ledger Platform`
   - Short description
   - Long description
   - Categories: Financial Services, Databases
3. Upload do logo
4. Configurar pricing (Free ou BYOL)

### 5.3 Configurar Template

1. **Fulfillment** → **CloudFormation templates**
2. Adicionar template:
   - Template URL: `https://midaz-cloudformation-templates.s3.us-east-1.amazonaws.com/releases/v1.0.0/midaz-complete.yaml`
   - Supported regions: selecionar regiões testadas
3. Configurar parâmetros que serão expostos ao usuário

### 5.4 Submeter para Review

1. **Submit for review**
2. AWS irá validar:
   - Template syntax
   - Security best practices
   - Compliance com guidelines
3. Tempo estimado: 3-5 dias úteis

---

## 6. Manutenção Pós-Publicação

### 6.1 Atualizar Versão no Marketplace

Quando houver nova release:

1. Verificar que `auto-release.yml` criou nova versão
2. No Marketplace Portal:
   - **Products** → **Midaz** → **Fulfillment**
   - Atualizar Template URL para nova versão
   - **Submit for review**

### 6.2 Monitoramento

- Acompanhar métricas no Marketplace Portal
- Responder reviews de usuários
- Manter templates atualizados com patches de segurança

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
aws s3 ls s3://midaz-cloudformation-templates/releases/ --recursive
```

---

## Links Úteis

- [AWS Marketplace Seller Guide](https://docs.aws.amazon.com/marketplace/latest/userguide/cloudformation-products.html)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)
- [cfn-lint Rules](https://github.com/aws-cloudformation/cfn-lint/blob/main/docs/rules.md)
