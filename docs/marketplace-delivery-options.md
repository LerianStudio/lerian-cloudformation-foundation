# Marketplace Delivery Options — Content Draft

Reference for the `AddDeliveryOptions` changeset. Each delivery option needs:
DeliveryOptionTitle, ShortDescription, LongDescription, UsageInstructions.

The listing offers **one** delivery option. It creates the cluster and enrolls
the Lerian agent in it; every product — Midaz included — is installed afterwards
by the Lerian control plane through that agent, not by a CloudFormation stack.
The three options this file used to describe (Full Stack, Infrastructure,
Application) launched templates that no longer exist. See
[marketplace-changesets.md](marketplace-changesets.md) for the changeset that
adds this one and restricts those three, in that order.

---

## Delivery Option: Lerian Foundation

**DeliveryOptionTitle:** `Lerian Foundation`

**ShortDescription:**
Deploy the Lerian foundation — VPC, Amazon EKS, and the Lerian agent — in a single CloudFormation stack across 3 Availability Zones. The agent enrolls with the Lerian control plane, and you install and upgrade Midaz and every other Lerian product from the Lerian console, without further CloudFormation changes.

**LongDescription:**
The Foundation stack creates the cluster Lerian products run on and connects it to the Lerian control plane. It is the only stack you launch from AWS Marketplace; everything after it happens in the Lerian console.

What gets deployed:
- VPC with 3-tier subnet architecture (public, private, database) across 3 AZs
- Amazon EKS cluster with ARM64 (Graviton) managed node groups
- The Lerian agent, installed into the cluster and enrolled with the control plane
- Optional: Route53 hosted zone, AWS Load Balancer Controller, and ExternalDNS when you supply a domain name

Security included:
- Customer-managed KMS keys for encryption at rest
- TLS/SSL encryption for all data in transit
- IAM Roles for Service Accounts (IRSA)
- Security groups following least-privilege principles
- The agent holds an outbound-only connection to the control plane: nothing needs to reach into your VPC, and no Lerian credential is stored in your account
- Optional PermissionsBoundaryArn constrains every IAM role the stack creates

What is deliberately not here: no product application is installed by this stack. The deployer Lambdas it creates — for the agent, and for the AWS Load Balancer Controller and ExternalDNS when you enable them — keep cluster access for the lifetime of the stack, because CloudFormation needs them to update and delete what they installed; none of them installs, upgrades or configures a Lerian product. Product installs, upgrades, rollbacks and values changes are performed by the agent from inside the cluster, driven by the control plane.

Best for: every customer. This is the entry point for Midaz and for any other Lerian product on the same cluster.

**UsageInstructions:**
Before you launch: sign in to the Lerian console, create the environment for this cluster, and copy the enrollment token it issues. The token is single-use and short-lived, so generate it right before launching.

Required parameters:
- ControlPlaneURL — the control plane URL shown in the console
- EnrollmentToken — the single-use token from the console
- AgentChartVersion — the agent chart version the console tells you to run

Leave all three empty to create the cluster with no control-plane connection. Supplying only some of them is rejected at CreateStack rather than 20 minutes into the deploy.

After stack creation completes (~25 minutes):

1. Confirm the cluster appears as connected in the Lerian console. That is the only check that matters — it proves the agent enrolled and is reachable.

2. Optional, if you want cluster access yourself:
   aws eks update-kubeconfig --name <cluster-name> --region <region>
   kubectl get pods -n lerian-system

3. Deploy the data services for the product you are installing (RDS PostgreSQL, DocumentDB, ElastiCache, AmazonMQ) with the product infrastructure stack, then create the release in the console.

If the cluster does not appear in the console, the agent's installation log is in the CloudWatch log group named by the AgentLogGroup output of the stack.

Optional: Set DomainName to create a Route53 hosted zone and the AWS Load Balancer Controller; add EnableExternalDNS=true for automatic DNS records.
Optional: Set PermissionsBoundaryArn to an IAM permissions boundary ARN (e.g., arn:aws:iam::ACCOUNT:policy/boundary) to constrain all IAM roles created by this stack.

Full documentation: https://github.com/LerianStudio/lerian-cloudformation-foundation/blob/main/README.md
