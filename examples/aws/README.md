# AWS Example Configuration

This directory contains example configurations for deploying Midaz on AWS.

## Parameters Reference

### General Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ProjectName` | midaz | Project name for resource naming |
| `EnvironmentName` | production | Environment (development/staging/production) |

### Network Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VpcCIDR` | 10.50.0.0/16 | VPC CIDR block |
| `AvailabilityZone1-3` | - | Three availability zones (required) |
| `EnableFlowLogs` | false | Enable VPC Flow Logs for network traffic auditing |
| `FlowLogsRetentionDays` | 14 | Days to retain Flow Logs (1-3653) |

### EKS Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `KubernetesVersion` | 1.32 | Kubernetes version |
| `NodeInstanceType` | c7g.large | Worker node instance type (ARM64 Graviton) |
| `NodeGroupMinSize` | 3 | Minimum nodes |
| `NodeGroupMaxSize` | 15 | Maximum nodes |
| `NodeGroupDesiredSize` | 3 | Desired nodes |

### RDS Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RDSInstanceClass` | db.t3.medium | Instance class |
| `RDSAllocatedStorage` | 20 | Initial storage (GB) |
| `RDSMaxAllocatedStorage` | 100 | Max storage for autoscaling |
| `RDSDatabaseName` | midaz | Database name |
| `RDSMasterUsername` | postgres | Master username |
| `CreateReadReplica` | false | Create read replica |
| `RDSForceSSL` | 0 | Force SSL connections (0=disabled, 1=enabled) |
| `RDSMultiAZ` | false | Enable Multi-AZ deployment for high availability |
| `RDSDeletionProtection` | false | Prevent accidental deletion |
| `RDSBackupRetentionPeriod` | 7 | Days to retain backups (1-35) |

### DocumentDB Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DocumentDBInstanceClass` | db.t3.medium | Instance class |
| `DocumentDBInstanceCount` | 2 | Number of instances |
| `DocumentDBMasterUsername` | docdbadmin | Master username |
| `DocumentDBDeletionProtection` | false | Prevent accidental deletion |
| `DocumentDBBackupRetentionPeriod` | 7 | Days to retain backups (1-35) |

### ElastiCache Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ElastiCacheNodeType` | cache.m7g.large | Node type |

### AmazonMQ Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `AmazonMQInstanceType` | mq.t3.micro | Broker instance type |
| `AmazonMQAdminUsername` | mqadmin | Admin username |

### DNS and Ingress Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DomainName` | "" | Domain name for Route53 (optional) |
| `EnableALBController` | true | Deploy AWS Load Balancer Controller |
| `EnableExternalDNS` | false | Deploy External DNS for automatic DNS records |

### Midaz Application Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DeployMidazHelm` | true | Automatically deploy Midaz Helm chart |
| `MidazHelmRepository` | oci://registry-1.docker.io/lerianstudio/midaz-helm | Helm chart repository (OCI or HTTP) |
| `MidazChartVersion` | 5.3.0 | Midaz Helm chart version to deploy |
| `MidazNamespace` | midaz | Kubernetes namespace for Midaz |
| `ArtifactsBucket` | (auto) | S3 bucket for Lambda layer (leave empty for default) |

## Deployment Examples

### Development Environment

```bash
aws cloudformation create-stack \
  --stack-name midaz-dev \
  --template-url https://your-bucket.s3.amazonaws.com/templates/midaz-complete.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz-dev \
    ParameterKey=EnvironmentName,ParameterValue=development \
    ParameterKey=AvailabilityZone1,ParameterValue=us-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=us-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=us-east-1c \
    ParameterKey=NodeGroupMinSize,ParameterValue=2 \
    ParameterKey=NodeGroupMaxSize,ParameterValue=5 \
    ParameterKey=NodeGroupDesiredSize,ParameterValue=2 \
    ParameterKey=RDSInstanceClass,ParameterValue=db.t3.small \
    ParameterKey=RDSForceSSL,ParameterValue=0 \
    ParameterKey=RDSMultiAZ,ParameterValue=false \
    ParameterKey=DocumentDBInstanceCount,ParameterValue=1 \
    ParameterKey=ElastiCacheNodeType,ParameterValue=cache.t3.small \
  --capabilities CAPABILITY_NAMED_IAM
```

### Production Environment

```bash
aws cloudformation create-stack \
  --stack-name midaz-prod \
  --template-url https://your-bucket.s3.amazonaws.com/templates/midaz-complete.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz-prod \
    ParameterKey=EnvironmentName,ParameterValue=production \
    ParameterKey=AvailabilityZone1,ParameterValue=us-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=us-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=us-east-1c \
    ParameterKey=EnableFlowLogs,ParameterValue=true \
    ParameterKey=FlowLogsRetentionDays,ParameterValue=30 \
    ParameterKey=NodeGroupMinSize,ParameterValue=3 \
    ParameterKey=NodeGroupMaxSize,ParameterValue=20 \
    ParameterKey=NodeGroupDesiredSize,ParameterValue=5 \
    ParameterKey=NodeInstanceType,ParameterValue=c7g.xlarge \
    ParameterKey=RDSInstanceClass,ParameterValue=db.m7g.large \
    ParameterKey=RDSForceSSL,ParameterValue=1 \
    ParameterKey=RDSMultiAZ,ParameterValue=true \
    ParameterKey=RDSDeletionProtection,ParameterValue=true \
    ParameterKey=RDSBackupRetentionPeriod,ParameterValue=30 \
    ParameterKey=CreateReadReplica,ParameterValue=true \
    ParameterKey=DocumentDBInstanceClass,ParameterValue=db.r6g.large \
    ParameterKey=DocumentDBInstanceCount,ParameterValue=3 \
    ParameterKey=DocumentDBDeletionProtection,ParameterValue=true \
    ParameterKey=DocumentDBBackupRetentionPeriod,ParameterValue=30 \
    ParameterKey=ElastiCacheNodeType,ParameterValue=cache.r7g.large \
    ParameterKey=AmazonMQInstanceType,ParameterValue=mq.m5.large \
  --capabilities CAPABILITY_NAMED_IAM
```

### One-Click Deployment (with Midaz Application)

```bash
aws cloudformation create-stack \
  --stack-name midaz-complete \
  --template-url https://your-bucket.s3.amazonaws.com/templates/midaz-complete.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz \
    ParameterKey=EnvironmentName,ParameterValue=production \
    ParameterKey=AvailabilityZone1,ParameterValue=us-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=us-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=us-east-1c \
    ParameterKey=DeployMidazHelm,ParameterValue=true \
    ParameterKey=MidazChartVersion,ParameterValue=5.3.0 \
    ParameterKey=ArtifactsBucket,ParameterValue=your-artifacts-bucket \
  --capabilities CAPABILITY_NAMED_IAM
```

### Custom Helm Repository

```bash
aws cloudformation create-stack \
  --stack-name midaz-custom \
  --template-url https://your-bucket.s3.amazonaws.com/templates/midaz-complete.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz \
    ParameterKey=EnvironmentName,ParameterValue=production \
    ParameterKey=AvailabilityZone1,ParameterValue=us-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=us-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=us-east-1c \
    ParameterKey=MidazHelmRepository,ParameterValue=oci://your-registry.com/midaz-helm \
    ParameterKey=MidazChartVersion,ParameterValue=5.3.0 \
  --capabilities CAPABILITY_NAMED_IAM
```

### Infrastructure Only (Manual Helm Deployment)

```bash
aws cloudformation create-stack \
  --stack-name midaz-infra \
  --template-url https://your-bucket.s3.amazonaws.com/templates/midaz-infrastructure.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=midaz \
    ParameterKey=EnvironmentName,ParameterValue=production \
    ParameterKey=AvailabilityZone1,ParameterValue=us-east-1a \
    ParameterKey=AvailabilityZone2,ParameterValue=us-east-1b \
    ParameterKey=AvailabilityZone3,ParameterValue=us-east-1c \
  --capabilities CAPABILITY_NAMED_IAM
```

## Post-Deployment Steps

1. **Configure kubectl**:
   ```bash
   aws eks update-kubeconfig --name midaz-prod-eks --region us-east-1
   ```

2. **Verify cluster**:
   ```bash
   kubectl get nodes
   ```

3. **Deploy Midaz manually** (if `DeployMidazHelm=false`):
   ```bash
   helm install midaz oci://registry-1.docker.io/lerianstudio/midaz-helm \
     --version 5.3.0 \
     --namespace midaz \
     --create-namespace
   ```

## Security Recommendations

### Development
- `RDSForceSSL`: 0 (disabled for easier debugging)
- `RDSMultiAZ`: false (cost savings)
- `EnableFlowLogs`: false (cost savings)
- `DeletionProtection`: false (easier cleanup)

### Production
- `RDSForceSSL`: 1 (enforce encrypted connections)
- `RDSMultiAZ`: true (high availability)
- `EnableFlowLogs`: true (audit trail)
- `DeletionProtection`: true (prevent accidents)
- `BackupRetentionPeriod`: 30+ days
