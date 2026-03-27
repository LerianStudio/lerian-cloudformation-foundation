# AWS Marketplace Changesets

Ready-to-run changesets for `prod-fildx2w4ikmba` (Lerian Midaz - Open-Source Ledger System).

---

## 1. Fix Categories (remove "Operating Systems")

```bash
aws marketplace-catalog start-change-set \
  --catalog AWSMarketplace \
  --change-set-name "Fix product categories" \
  --change-set '[{
    "ChangeType": "UpdateInformation",
    "Entity": {
      "Type": "AmiProduct@1.0",
      "Identifier": "prod-fildx2w4ikmba"
    },
    "DetailsDocument": {
      "Categories": [
        "Financial Services",
        "Application Development",
        "Business Intelligence"
      ]
    }
  }]' \
  --profile lerian_root
```

---

## 2. Add New Version with 3 Delivery Options

Before running: upload the 3 templates to the Marketplace S3 bucket and update the Template URLs below.

**Template URLs** (update after upload):
- Full Stack: `https://awsmp-cft-211125678794-1707910187780.s3.us-east-1.amazonaws.com/<path>/full-stack.yaml`
- Infrastructure: `https://awsmp-cft-211125678794-1707910187780.s3.us-east-1.amazonaws.com/<path>/infrastructure.yaml`
- Application: `https://awsmp-cft-211125678794-1707910187780.s3.us-east-1.amazonaws.com/<path>/application.yaml`

**Architecture Diagram URL** (same for all 3):
`https://awsmp-cf-af-612309067705-1556123774245.s3.us-east-1.amazonaws.com/a72c0d74-a74a-451f-b225-71205fe3b872/a72c0d74-a74a-451f-b225-71205fe3b872/prod-fildx2w4ikmba/b1019bc9-4533-4cc7-8c59-eb970c1419fe/midaz_cf.png`

**AMI** (same for all 3 — current production AMI):
`ami-0f1d84b9b33468f19`

```bash
aws marketplace-catalog start-change-set \
  --catalog AWSMarketplace \
  --change-set-name "Add version with 3 delivery options" \
  --change-set '[{
    "ChangeType": "AddDeliveryOptions",
    "Entity": {
      "Type": "AmiProduct@1.0",
      "Identifier": "prod-fildx2w4ikmba"
    },
    "DetailsDocument": {
      "Version": {
        "VersionTitle": "v0.2.0",
        "ReleaseNotes": "Added modular deployment options: Full Stack, Infrastructure Only, and Application Only. Templates now support optional PermissionsBoundary parameter."
      },
      "DeliveryOptions": [
        {
          "DeliveryOptionTitle": "Midaz Full Stack",
          "Details": {
            "DeploymentTemplateDeliveryOptionDetails": {
              "ShortDescription": "Deploy the complete Midaz ledger infrastructure and application in a single CloudFormation stack. Includes VPC, Amazon EKS, RDS PostgreSQL, DocumentDB, ElastiCache, AmazonMQ, and the Midaz application — fully configured across 3 Availability Zones with enterprise-grade security.",
              "LongDescription": "The Full Stack deployment creates everything you need to run Midaz in a single CloudFormation stack. This is the fastest way to get started — one deploy, one stack, fully standalone. What gets deployed: VPC with 3-tier subnet architecture (public, private, database) across 3 AZs, Amazon EKS cluster with managed node groups, RDS PostgreSQL with Multi-AZ support, Amazon DocumentDB (MongoDB-compatible), Amazon ElastiCache (Valkey/Redis), Amazon MQ (RabbitMQ), and the Midaz ledger application deployed via Helm. Security: Customer-managed KMS keys, TLS/SSL encryption, AWS Secrets Manager, IAM Roles for Service Accounts (IRSA), and least-privilege security groups. Best for quick starts, single-product environments, evaluations, and standalone deployments.",
              "UsageInstructions": "After stack creation completes (~45 minutes):\n\n1. Configure kubectl:\n   aws eks update-kubeconfig --name <cluster-name> --region <region>\n\n2. Verify pods are running:\n   kubectl get pods -n midaz\n\n3. Check stack outputs for connection endpoints.\n\nRequired parameters: RDSMasterUsername, DocumentDBMasterUsername, AmazonMQAdminUsername.\nOptional: Set EnableIngress=true with DomainName and IngressHostname for external access.\n\nFull documentation: https://github.com/LerianStudio/lerian-cloudformation-foundation/blob/main/products/midaz/README.md",
              "RecommendedInstanceType": "c6i.xlarge",
              "ArchitectureDiagram": "https://awsmp-cf-af-612309067705-1556123774245.s3.us-east-1.amazonaws.com/a72c0d74-a74a-451f-b225-71205fe3b872/a72c0d74-a74a-451f-b225-71205fe3b872/prod-fildx2w4ikmba/b1019bc9-4533-4cc7-8c59-eb970c1419fe/midaz_cf.png",
              "Template": "REPLACE_WITH_FULL_STACK_TEMPLATE_URL",
              "TemplateSources": [
                {
                  "ParameterName": "MarketplaceAMI",
                  "AmiSource": {
                    "AmiId": "ami-0f1d84b9b33468f19",
                    "AccessRoleArn": "arn:aws:iam::239025757440:role/AwsMarketplaceAmiIngestion",
                    "UserName": "root",
                    "OperatingSystemName": "UBUNTU",
                    "OperatingSystemVersion": "23"
                  }
                }
              ]
            }
          }
        },
        {
          "DeliveryOptionTitle": "Midaz Infrastructure",
          "Details": {
            "DeploymentTemplateDeliveryOptionDetails": {
              "ShortDescription": "Deploy Midaz databases and services (RDS PostgreSQL, DocumentDB, ElastiCache, AmazonMQ) on an existing Foundation stack. Part of the modular deployment — use this when sharing VPC and EKS across multiple products or when you need independent lifecycle management.",
              "LongDescription": "The Infrastructure deployment creates only the data layer for Midaz, importing the shared VPC and EKS cluster from an existing Foundation stack. This is the modular approach — deploy Foundation once, then add product infrastructure stacks independently. What gets deployed: RDS PostgreSQL with Multi-AZ support, Amazon DocumentDB (MongoDB-compatible), Amazon ElastiCache (Valkey/Redis), Amazon MQ (RabbitMQ), AWS Secrets Manager entries, security groups and KMS keys. Prerequisites: A Foundation stack must be deployed first (provides VPC + EKS). After this stack completes, deploy the Application stack to install the Midaz ledger. Best for multi-product environments, teams that want independent lifecycle management, and organizations with existing VPC/EKS infrastructure.",
              "UsageInstructions": "Prerequisites: Deploy the Foundation stack first (provides VPC + EKS).\n\n1. Set FoundationStackName to your Foundation stack name (default: lerian-foundation).\n2. Provide RDSMasterUsername, DocumentDBMasterUsername, and AmazonMQAdminUsername.\n3. After stack creation completes (~30 minutes), deploy the Midaz Application stack.\n4. Use ExistingVpcId, ExistingClusterName parameters to override Foundation values if needed.\n\nFull documentation: https://github.com/LerianStudio/lerian-cloudformation-foundation/blob/main/products/midaz/README.md",
              "RecommendedInstanceType": "c6i.xlarge",
              "ArchitectureDiagram": "https://awsmp-cf-af-612309067705-1556123774245.s3.us-east-1.amazonaws.com/a72c0d74-a74a-451f-b225-71205fe3b872/a72c0d74-a74a-451f-b225-71205fe3b872/prod-fildx2w4ikmba/b1019bc9-4533-4cc7-8c59-eb970c1419fe/midaz_cf.png",
              "Template": "REPLACE_WITH_INFRASTRUCTURE_TEMPLATE_URL",
              "TemplateSources": [
                {
                  "ParameterName": "MarketplaceAMI",
                  "AmiSource": {
                    "AmiId": "ami-0f1d84b9b33468f19",
                    "AccessRoleArn": "arn:aws:iam::239025757440:role/AwsMarketplaceAmiIngestion",
                    "UserName": "root",
                    "OperatingSystemName": "UBUNTU",
                    "OperatingSystemVersion": "23"
                  }
                }
              ]
            }
          }
        },
        {
          "DeliveryOptionTitle": "Midaz Application",
          "Details": {
            "DeploymentTemplateDeliveryOptionDetails": {
              "ShortDescription": "Deploy the Midaz ledger application via Helm to an existing EKS cluster with pre-provisioned databases. Part of the modular deployment — use this after deploying the Infrastructure stack. Supports custom domains, ALB ingress, and CRM integration.",
              "LongDescription": "The Application deployment installs the Midaz ledger on an existing EKS cluster using Helm. It imports all database endpoints and credentials from the Infrastructure stack automatically. What gets deployed: Midaz ledger application (Helm chart), Kubernetes namespace, service accounts, and RBAC. Optional: ALB Ingress for external access, CRM service and ingress. Prerequisites: A Midaz Infrastructure stack must be deployed first. Ingress options: Set EnableIngress=true for ALB-based external access, provide DomainName and IngressHostname for DNS routing. Best for teams using the modular deployment approach, environments where infrastructure is managed separately from applications.",
              "UsageInstructions": "Prerequisites: Deploy the Midaz Infrastructure stack first.\n\n1. Set InfrastructureStackName to your Infrastructure stack name (default: midaz-infra).\n2. After stack creation completes (~15 minutes), configure kubectl:\n   aws eks update-kubeconfig --name <cluster-name> --region <region>\n3. Verify pods: kubectl get pods -n midaz\n4. Optional: Enable ingress with EnableIngress=true, DomainName, and IngressHostname.\n\nFull documentation: https://github.com/LerianStudio/lerian-cloudformation-foundation/blob/main/products/midaz/README.md",
              "RecommendedInstanceType": "c6i.xlarge",
              "ArchitectureDiagram": "https://awsmp-cf-af-612309067705-1556123774245.s3.us-east-1.amazonaws.com/a72c0d74-a74a-451f-b225-71205fe3b872/a72c0d74-a74a-451f-b225-71205fe3b872/prod-fildx2w4ikmba/b1019bc9-4533-4cc7-8c59-eb970c1419fe/midaz_cf.png",
              "Template": "REPLACE_WITH_APPLICATION_TEMPLATE_URL",
              "TemplateSources": [
                {
                  "ParameterName": "MarketplaceAMI",
                  "AmiSource": {
                    "AmiId": "ami-0f1d84b9b33468f19",
                    "AccessRoleArn": "arn:aws:iam::239025757440:role/AwsMarketplaceAmiIngestion",
                    "UserName": "root",
                    "OperatingSystemName": "UBUNTU",
                    "OperatingSystemVersion": "23"
                  }
                }
              ]
            }
          }
        }
      ]
    }
  }]' \
  --profile lerian_root
```

**IMPORTANT:** Before running, replace the 3 `REPLACE_WITH_*_TEMPLATE_URL` placeholders with the actual S3 URLs where the templates are uploaded. The Marketplace requires templates to be in its managed S3 bucket — you upload them via the Marketplace console or the API copies them during version creation.

---

## 3. Add Regions

The correct change type is `AddRegions` (additive — only specify new regions to add). Marketplace handles AMI replication automatically.

```bash
aws marketplace-catalog start-change-set \
  --catalog AWSMarketplace \
  --change-set-name "Expand regions" \
  --change-set '[{
    "ChangeType": "AddRegions",
    "Entity": {
      "Type": "AmiProduct@1.0",
      "Identifier": "prod-fildx2w4ikmba"
    },
    "DetailsDocument": {
      "Regions": [
        "us-west-2",
        "eu-west-1"
      ]
    }
  }]' \
  --profile lerian_root
```

**Related change types:** `RestrictRegions` (remove regions), `UpdateFutureRegionSupport` (auto-onboard new AWS regions).

---

## Execution Order

1. **Fix Categories** (changeset 1) — ✅ SUCCEEDED (`cfgpdywsza9v0x8u6rxqosmaw`)
2. **Add Regions** (changeset 3) — ✅ SUBMITTED (`cfxeljkpxcvcuagkmf832ccm`)
3. **Upload templates** to Marketplace S3 — prepare template URLs
4. **Add Delivery Options** (changeset 2) — after templates are uploaded
