# AWS Marketplace Changesets

Ready-to-run changesets for `prod-fildx2w4ikmba` (Lerian Midaz - Open-Source Ledger System).

**These are drafts. Nothing here is submitted by CI** — a human runs them against
the live catalog after this repository's changes are merged and released. Read
[Execution Order](#execution-order) before running anything: the steps are
ordered because the Catalog API rejects two of them out of sequence.

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

## 2. Add the Foundation Delivery Option

The listing used to offer three delivery options — Full Stack, Infrastructure,
Application. Two of the three launched `full-stack.yaml` and `application.yaml`,
which installed the Midaz application from a Lambda holding cluster-admin, and
which this repository no longer publishes. They are replaced by one option that
delivers the cluster with the Lerian agent enrolled in it; products are installed
afterwards by the control plane, through the agent.

Wording for the fields below is maintained in
[marketplace-delivery-options.md](marketplace-delivery-options.md) — edit there
first, then mirror it here.

Before running: pin the nested-template prefix **in the template file itself**.
A delivery option has no field for parameter defaults —
`DeploymentTemplateDeliveryOptionDetails` carries the two descriptions, the
usage instructions, a recommended instance type, the diagram URL, the template
URL and `TemplateSources`, and nothing else; `TemplateSources` binds an AMI to a
parameter and cannot set a value for any other. `MPS3BucketName`,
`MPS3BucketRegion` and `MPS3KeyPrefix` are ordinary CloudFormation parameters,
so their defaults come from `foundation.yaml` and from nowhere else.

So:

1. **Edit `MPS3KeyPrefix` to the released version's prefix** in the copy of
   `foundation.yaml` you are about to upload — `releases/v<VERSION>/`, the
   version this listing delivers. The committed default is `releases/latest/`,
   which every release overwrites; submitted as-is, the listing binds whichever
   nested templates happened to sit there at submission time rather than the
   ones released with this root template. `MPS3BucketName`
   (`lerian-cloudformation-templates`) and `MPS3BucketRegion` (`sa-east-1`)
   already name the release bucket and stay as they are.

2. **Leave the nested templates in the release bucket** at that prefix —
   `vpc.yaml`, `eks.yaml`, `agent.yaml`, `route53.yaml`, `alb-controller.yaml`
   and `external-dns.yaml`, all published there by the release workflow, all
   publicly readable. Only the edited root `foundation.yaml` is uploaded to the
   Marketplace bucket.

At publish time AWS Marketplace copies the root template and every template it
nests into its own S3 bucket, then rewrites the default **and the allowed
values** of the three `MPS3*` parameters to point at those copies. A launched
customer stack therefore never reads the Lerian bucket, and the `sa-east-1`
constraint on `MPS3BucketRegion` in the committed template is not a limit on
where the copies live. A nested template missing from the prefix fails the
changeset rather than the customer's deploy.

**Template URL** (update after upload):
`https://awsmp-cft-211125678794-1707910187780.s3.us-east-1.amazonaws.com/<path>/foundation.yaml`

**Architecture Diagram URL:**
`https://awsmp-cf-af-612309067705-1556123774245.s3.us-east-1.amazonaws.com/a72c0d74-a74a-451f-b225-71205fe3b872/a72c0d74-a74a-451f-b225-71205fe3b872/prod-fildx2w4ikmba/b1019bc9-4533-4cc7-8c59-eb970c1419fe/midaz_cf.png`

**AMI** (vestigial — the listing is an `AmiProduct` entity, so a delivery option
must bind an AMI to a template parameter. The cluster runs EKS-managed ARM64
node AMIs and never launches this one; `foundation.yaml` declares a
`MarketplaceAMI` parameter that exists for this binding and nothing else):
`ami-0f1d84b9b33468f19`

```bash
aws marketplace-catalog start-change-set \
  --catalog AWSMarketplace \
  --change-set-name "Add foundation delivery option" \
  --change-set '[{
    "ChangeType": "AddDeliveryOptions",
    "Entity": {
      "Type": "AmiProduct@1.0",
      "Identifier": "prod-fildx2w4ikmba"
    },
    "DetailsDocument": {
      "Version": {
        "VersionTitle": "v1.0.0",
        "ReleaseNotes": "The listing now delivers the Lerian foundation: VPC, Amazon EKS and the Lerian agent, enrolled with the Lerian control plane. Midaz and every other Lerian product are installed into that cluster from the Lerian console, by the agent, instead of by a CloudFormation stack. The previous Full Stack, Infrastructure and Application delivery options are restricted: they installed the application layer from a Lambda holding cluster administrator rights, and their templates are no longer published."
      },
      "DeliveryOptions": [
        {
          "DeliveryOptionTitle": "Lerian Foundation",
          "Details": {
            "DeploymentTemplateDeliveryOptionDetails": {
              "ShortDescription": "Deploy the Lerian foundation — VPC, Amazon EKS, and the Lerian agent — in a single CloudFormation stack across 3 Availability Zones. The agent enrolls with the Lerian control plane, and you install and upgrade Midaz and every other Lerian product from the Lerian console, without further CloudFormation changes.",
              "LongDescription": "The Foundation stack creates the cluster Lerian products run on and connects it to the Lerian control plane. It is the only stack you launch from AWS Marketplace; everything after it happens in the Lerian console. What gets deployed: VPC with 3-tier subnet architecture (public, private, database) across 3 AZs, an Amazon EKS cluster with ARM64 (Graviton) managed node groups, and the Lerian agent installed into the cluster and enrolled with the control plane. Optionally a Route53 hosted zone, the AWS Load Balancer Controller and ExternalDNS, when you supply a domain name. Security: customer-managed KMS keys for encryption at rest, TLS/SSL in transit, IAM Roles for Service Accounts (IRSA), least-privilege security groups, and an optional IAM permissions boundary applied to every role the stack creates. The agent holds an outbound-only connection to the control plane, so nothing needs to reach into your VPC and no Lerian credential is stored in your account. What is deliberately not here: no product application is installed by this stack, and no Lambda in your account holds cluster administrator rights after it completes. Product installs, upgrades, rollbacks and configuration changes are performed by the agent from inside the cluster, driven by the control plane. Best for every customer: this is the entry point for Midaz and for any other Lerian product on the same cluster.",
              "UsageInstructions": "Before you launch: sign in to the Lerian console, create the environment for this cluster, and copy the enrollment token it issues. The token is single-use and short-lived, so generate it right before launching.\n\nRequired parameters:\n- ControlPlaneURL - the control plane URL shown in the console\n- EnrollmentToken - the single-use token from the console\n- AgentChartVersion - the agent chart version the console tells you to run\n\nLeave all three empty to create the cluster with no control-plane connection. Supplying only some of them is rejected at CreateStack rather than 20 minutes into the deploy.\n\nAfter stack creation completes (~25 minutes):\n\n1. Confirm the cluster appears as connected in the Lerian console. That is the only check that matters - it proves the agent enrolled and is reachable.\n\n2. Optional, if you want cluster access yourself:\n   aws eks update-kubeconfig --name <cluster-name> --region <region>\n   kubectl get pods -n lerian-system\n\n3. Deploy the data services for the product you are installing (RDS PostgreSQL, DocumentDB, ElastiCache, AmazonMQ) with the product infrastructure stack, then create the release in the console.\n\nIf the cluster does not appear in the console, the agent installation log is in the CloudWatch log group named by the stack's AgentLogGroup output.\n\nOptional: set DomainName to create a Route53 hosted zone and the AWS Load Balancer Controller; add EnableExternalDNS=true for automatic DNS records.\nOptional: set PermissionsBoundaryArn to constrain all IAM roles created by this stack.\n\nFull documentation: https://github.com/LerianStudio/lerian-cloudformation-foundation/blob/main/README.md",
              "RecommendedInstanceType": "c7g.large",
              "ArchitectureDiagram": "https://awsmp-cf-af-612309067705-1556123774245.s3.us-east-1.amazonaws.com/a72c0d74-a74a-451f-b225-71205fe3b872/a72c0d74-a74a-451f-b225-71205fe3b872/prod-fildx2w4ikmba/b1019bc9-4533-4cc7-8c59-eb970c1419fe/midaz_cf.png",
              "Template": "REPLACE_WITH_FOUNDATION_TEMPLATE_URL",
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

**IMPORTANT:** replace `REPLACE_WITH_FOUNDATION_TEMPLATE_URL` with the actual S3
URL the edited root template was uploaded to. The root template has to live in
the Marketplace-managed bucket — upload it through the Marketplace console. Its
nested templates do not: they are fetched from the `MPS3*` prefix baked into
that root template and copied alongside it at publish time.

---

## 3. Restrict the Three Superseded Delivery Options

Run this **after** changeset 2 has succeeded. The Catalog API refuses to restrict
the last unrestricted delivery option of a product, so the new one has to exist
first. Existing subscribers keep access to a restricted version; only new buyers
stop seeing it.

Get the current delivery option IDs — the titles are not accepted, only the IDs:

```bash
aws marketplace-catalog describe-entity \
  --catalog AWSMarketplace \
  --entity-id prod-fildx2w4ikmba \
  --profile lerian_root \
  --query 'DetailsDocument.Versions[].DeliveryOptions[].{Id:Id,Title:Title}'
```

Then restrict the three that correspond to `Midaz Full Stack`,
`Midaz Infrastructure` and `Midaz Application`:

```bash
aws marketplace-catalog start-change-set \
  --catalog AWSMarketplace \
  --change-set-name "Restrict superseded delivery options" \
  --change-set '[{
    "ChangeType": "RestrictDeliveryOptions",
    "Entity": {
      "Type": "AmiProduct@1.0",
      "Identifier": "prod-fildx2w4ikmba"
    },
    "DetailsDocument": {
      "DeliveryOptionIds": [
        "REPLACE_WITH_FULL_STACK_DELIVERY_OPTION_ID",
        "REPLACE_WITH_INFRASTRUCTURE_DELIVERY_OPTION_ID",
        "REPLACE_WITH_APPLICATION_DELIVERY_OPTION_ID"
      ]
    }
  }]' \
  --profile lerian_root
```

AWS Marketplace guidelines require supporting existing buyers of a restricted
version for 90 days after restriction.

---

## 4. Add Regions

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

Steps 3 through 6 are the migration to the foundation-and-agent listing. The
order is load-bearing: a restricted-first sequence is rejected by the API, and a
delete-first sequence 404s the live listing for anyone mid-purchase.

1. **Fix Categories** (changeset 1) — SUCCEEDED (`cfgpdywsza9v0x8u6rxqosmaw`)
2. **Add Regions** (changeset 4) — SUBMITTED (`cfxeljkpxcvcuagkmf832ccm`)
3. **Release this repository to S3.** The GitHub release workflow publishes
   `foundation.yaml` and its nested templates to
   `s3://lerian-cloudformation-templates/releases/latest/`. Nothing in the
   Marketplace flow works before this lands.
4. **Edit and upload the root `foundation.yaml`.** Set its `MPS3KeyPrefix`
   default to the `releases/v<VERSION>/` prefix step 3 published, upload that
   copy to the Marketplace S3 bucket, and note the resulting template URL. The
   nested templates stay in the release bucket at that prefix.
5. **Add the Foundation delivery option** (changeset 2) — needs the URL from
   step 4.
6. **Restrict the three superseded delivery options** (changeset 3) — only after
   step 5 succeeds.
7. **Delete the stale objects from the release bucket.** The release workflow
   publishes with `aws s3 sync` without `--delete`, so
   `releases/latest/products/midaz/{application,helm,full-stack}.yaml` keep
   being served after this repository stops publishing them, and every
   previously shared quick-create link still points at them. Delete them only
   after step 6, so nothing the live listing references disappears while it is
   still reachable:

   ```bash
   aws s3 rm s3://lerian-cloudformation-templates/releases/latest/products/midaz/application.yaml
   aws s3 rm s3://lerian-cloudformation-templates/releases/latest/products/midaz/helm.yaml
   aws s3 rm s3://lerian-cloudformation-templates/releases/latest/products/midaz/full-stack.yaml
   ```

   Versioned prefixes (`releases/v*/`, `products/midaz/*/v*/`) are immutable
   history and stay as they are: stacks already deployed from them reference
   those URLs on update.
8. **Deploy the new delivery option once in a sandbox account** before the
   listing goes live, and confirm the cluster appears connected in the control
   plane. No CI check can prove this; it is the only end-to-end verification
   that the enrollment path works.
