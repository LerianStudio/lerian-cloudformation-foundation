# Marketplace Delivery Options — Content Draft

Reference for the `AddDeliveryOptions` changeset. Each delivery option needs:
DeliveryOptionTitle, ShortDescription, LongDescription, UsageInstructions.

---

## Delivery Option 1: Full Stack

**DeliveryOptionTitle:** `Midaz Full Stack`

**ShortDescription:**
Deploy the complete Midaz ledger infrastructure and application in a single CloudFormation stack. Includes VPC, Amazon EKS, RDS PostgreSQL, DocumentDB, ElastiCache, AmazonMQ, and the Midaz application — fully configured across 3 Availability Zones with enterprise-grade security.

**LongDescription:**
The Full Stack deployment creates everything you need to run Midaz in a single CloudFormation stack. This is the fastest way to get started — one deploy, one stack, fully standalone.

What gets deployed:
- VPC with 3-tier subnet architecture (public, private, database) across 3 AZs
- Amazon EKS cluster with managed node groups
- RDS PostgreSQL with Multi-AZ support for transactional data
- Amazon DocumentDB (MongoDB-compatible) for document storage
- Amazon ElastiCache (Valkey/Redis) for high-performance caching
- Amazon MQ (RabbitMQ) for message queuing
- Midaz ledger application deployed via Helm

Security included:
- Customer-managed KMS keys for encryption at rest
- TLS/SSL encryption for all data in transit
- AWS Secrets Manager for credential management
- IAM Roles for Service Accounts (IRSA)
- Security groups following least-privilege principles

Best for: Quick starts, single-product environments, evaluations, and standalone deployments where you don't plan to share infrastructure with other products.

**UsageInstructions:**
After stack creation completes (~45 minutes):

1. Configure kubectl:
   aws eks update-kubeconfig --name <cluster-name> --region <region>

2. Verify pods are running:
   kubectl get pods -n midaz

3. Check stack outputs for connection endpoints (RDS, DocumentDB, ElastiCache).

Required parameters: RDSMasterUsername, DocumentDBMasterUsername, AmazonMQAdminUsername.

Optional: Set EnableIngress=true with DomainName and IngressHostname for external access via ALB.

---

## Delivery Option 2: Infrastructure Only

**DeliveryOptionTitle:** `Midaz Infrastructure`

**ShortDescription:**
Deploy Midaz databases and services (RDS PostgreSQL, DocumentDB, ElastiCache, AmazonMQ) on an existing Foundation stack. Part of the modular deployment — use this when sharing VPC and EKS across multiple products or when you need independent lifecycle management for infrastructure and application layers.

**LongDescription:**
The Infrastructure deployment creates only the data layer for Midaz, importing the shared VPC and EKS cluster from an existing Foundation stack. This is the modular approach — deploy Foundation once, then add product infrastructure stacks independently.

What gets deployed:
- RDS PostgreSQL with Multi-AZ support for transactional data
- Amazon DocumentDB (MongoDB-compatible) for document storage
- Amazon ElastiCache (Valkey/Redis) for high-performance caching
- Amazon MQ (RabbitMQ) for message queuing
- AWS Secrets Manager entries for all credentials
- Security groups and KMS keys

Prerequisites:
- A Foundation stack must be deployed first (provides VPC + EKS)
- The FoundationStackName parameter must reference the existing Foundation stack

Best for: Multi-product environments (e.g., Midaz + Tracer on shared infrastructure), teams that want independent lifecycle management for infrastructure and application layers, and organizations with existing VPC/EKS infrastructure.

After this stack completes, deploy the Application stack to install the Midaz ledger.

**UsageInstructions:**
Prerequisites: Deploy the Foundation stack first (provides VPC + EKS).

1. Set FoundationStackName to your Foundation stack name (default: lerian-foundation).
2. Provide RDSMasterUsername, DocumentDBMasterUsername, and AmazonMQAdminUsername.
3. After stack creation completes (~30 minutes), deploy the Midaz Application stack.
4. Use the ExistingVpcId, ExistingClusterName parameters to override Foundation values if needed.

---

## Delivery Option 3: Application Only

**DeliveryOptionTitle:** `Midaz Application`

**ShortDescription:**
Deploy the Midaz ledger application via Helm to an existing EKS cluster with pre-provisioned databases. Part of the modular deployment — use this after deploying the Infrastructure stack. Supports custom domains, ALB ingress, and CRM integration.

**LongDescription:**
The Application deployment installs the Midaz ledger on an existing EKS cluster using Helm. It imports all database endpoints and credentials from the Infrastructure stack automatically.

What gets deployed:
- Midaz ledger application (Helm chart)
- Kubernetes namespace, service accounts, and RBAC
- Optional: ALB Ingress for external access
- Optional: CRM service and ingress

Prerequisites:
- A Midaz Infrastructure stack must be deployed first
- The InfrastructureStackName parameter must reference the existing Infrastructure stack

Ingress options:
- Set EnableIngress=true for ALB-based external access
- Provide DomainName and IngressHostname for DNS routing
- Optionally provide IngressCertificateArn for HTTPS

Best for: Teams using the modular deployment approach, environments where infrastructure is managed separately from applications, and scenarios requiring independent application updates without touching the data layer.

**UsageInstructions:**
Prerequisites: Deploy the Midaz Infrastructure stack first.

1. Set InfrastructureStackName to your Infrastructure stack name (default: midaz-infra).
2. After stack creation completes (~15 minutes), configure kubectl:
   aws eks update-kubeconfig --name <cluster-name> --region <region>
3. Verify pods: kubectl get pods -n midaz
4. Optional: Enable ingress by setting EnableIngress=true, DomainName, and IngressHostname.
