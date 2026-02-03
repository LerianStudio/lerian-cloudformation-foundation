# Troubleshooting Guide

This guide covers common issues and their solutions when deploying and operating the Midaz CloudFormation infrastructure.

## Table of Contents

- [Stack Deployment Issues](#stack-deployment-issues)
- [VPC Issues](#vpc-issues)
- [EKS Issues](#eks-issues)
- [Database Issues](#database-issues)
- [Networking Issues](#networking-issues)
- [IAM Permission Issues](#iam-permission-issues)
- [Helm Deployment Issues](#helm-deployment-issues)
- [Monitoring and Logs](#monitoring-and-logs)
- [Cleanup and Deletion](#cleanup-and-deletion)

## Stack Deployment Issues

### Stack Creation Fails Immediately

**Symptom:** Stack fails with `ROLLBACK_IN_PROGRESS` status immediately after creation.

**Common Causes:**

1. **Missing IAM Capabilities**
   ```bash
   # Error: Requires capabilities : [CAPABILITY_IAM]

   # Solution: Add required capabilities
   aws cloudformation create-stack \
     --stack-name midaz \
     --template-url https://... \
     --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND
   ```

2. **Invalid Parameter Values**
   ```bash
   # Check parameter constraints
   aws cloudformation describe-stack-events \
     --stack-name midaz \
     --query "StackEvents[?ResourceStatus=='CREATE_FAILED']"
   ```

3. **Template Validation Errors**
   ```bash
   # Validate template before deployment
   aws cloudformation validate-template \
     --template-url https://...
   ```

### Stack Stuck in CREATE_IN_PROGRESS

**Symptom:** Stack creation takes longer than expected (>30 minutes).

**Diagnosis:**
```bash
# Check which resource is taking time
aws cloudformation describe-stack-events \
  --stack-name midaz \
  --query "StackEvents[?ResourceStatus=='CREATE_IN_PROGRESS'].{Resource:LogicalResourceId,Time:Timestamp}" \
  --output table
```

**Common Slow Resources:**
- **EKS Cluster**: 10-15 minutes (normal)
- **RDS with Multi-AZ**: 10-20 minutes (normal)
- **DocumentDB Cluster**: 10-15 minutes (normal)
- **NAT Gateway**: 2-5 minutes (normal)

### Stack Creation Fails at Specific Resource

**Symptom:** Stack fails at a specific resource with detailed error.

**Diagnosis:**
```bash
# Get detailed failure reason
aws cloudformation describe-stack-events \
  --stack-name midaz \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}" \
  --output table
```

## VPC Issues

### NAT Gateway Creation Fails

**Symptom:** `CREATE_FAILED` on NAT Gateway resource.

**Common Causes:**

1. **No Elastic IP available**
   ```bash
   # Check EIP limits
   aws ec2 describe-account-attributes \
     --attribute-names vpc-max-elastic-ips

   # Request limit increase if needed
   aws service-quotas request-service-quota-increase \
     --service-code ec2 \
     --quota-code L-0263D0A3 \
     --desired-value 10
   ```

2. **Subnet has no Internet Gateway**
   ```bash
   # Verify IGW attachment
   aws ec2 describe-internet-gateways \
     --filters "Name=attachment.vpc-id,Values=vpc-xxx"
   ```

### VPC Endpoint Creation Fails

**Symptom:** Interface endpoint fails to create.

**Common Causes:**

1. **Service not available in region**
   ```bash
   # List available endpoint services
   aws ec2 describe-vpc-endpoint-services \
     --query "ServiceNames[*]" \
     --region us-east-1
   ```

2. **Security group doesn't allow HTTPS**
   ```bash
   # VPC endpoints require port 443
   aws ec2 authorize-security-group-ingress \
     --group-id sg-xxx \
     --protocol tcp \
     --port 443 \
     --cidr 10.0.0.0/16
   ```

## EKS Issues

### Nodes Not Joining Cluster

**Symptom:** Node group shows `ACTIVE` but nodes don't appear in `kubectl get nodes`.

**Diagnosis:**
```bash
# Check node group status
aws eks describe-nodegroup \
  --cluster-name midaz-eks \
  --nodegroup-name midaz-nodegroup \
  --query "nodegroup.{Status:status,Health:health}"

# Check EC2 instances
aws ec2 describe-instances \
  --filters "Name=tag:eks:nodegroup-name,Values=midaz-nodegroup" \
  --query "Reservations[].Instances[].{Id:InstanceId,State:State.Name}"
```

**Common Causes:**

1. **Security group misconfiguration**
   ```bash
   # Ensure node SG allows communication with cluster SG
   aws ec2 describe-security-groups \
     --group-ids sg-xxx \
     --query "SecurityGroups[].IpPermissions"
   ```

2. **IAM role missing required policies**
   ```bash
   # Required managed policies for node role:
   # - AmazonEKSWorkerNodePolicy
   # - AmazonEC2ContainerRegistryReadOnly
   # - AmazonEKS_CNI_Policy

   aws iam list-attached-role-policies \
     --role-name midaz-eks-node-role
   ```

3. **Subnet has no route to NAT Gateway**
   ```bash
   # Check route table
   aws ec2 describe-route-tables \
     --filters "Name=association.subnet-id,Values=subnet-xxx" \
     --query "RouteTables[].Routes"
   ```

### kubectl Connection Issues

**Symptom:** `Unable to connect to the server` or timeout.

**Solution:**
```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --name midaz-eks \
  --region us-east-1

# Verify cluster endpoint
aws eks describe-cluster \
  --name midaz-eks \
  --query "cluster.endpoint"

# Test connectivity
kubectl cluster-info
```

### Pod Scheduling Failures

**Symptom:** Pods stuck in `Pending` state.

**Diagnosis:**
```bash
kubectl describe pod <pod-name> -n <namespace>
```

**Common Causes:**

1. **Insufficient resources**
   ```bash
   # Check node capacity
   kubectl describe nodes | grep -A 5 "Allocated resources"
   ```

2. **Node taints preventing scheduling**
   ```bash
   kubectl describe nodes | grep Taints
   ```

3. **PVC not bound**
   ```bash
   kubectl get pvc -A
   ```

## Database Issues

### RDS Connection Timeout

**Symptom:** Application cannot connect to RDS.

**Diagnosis:**
```bash
# Get RDS endpoint
aws rds describe-db-instances \
  --db-instance-identifier midaz-rds \
  --query "DBInstances[0].Endpoint"

# Check security group rules
aws ec2 describe-security-groups \
  --group-ids sg-xxx \
  --query "SecurityGroups[0].IpPermissions"
```

**Common Causes:**

1. **Security group doesn't allow traffic from application**
   ```bash
   # Add rule for VPC CIDR
   aws ec2 authorize-security-group-ingress \
     --group-id sg-xxx \
     --protocol tcp \
     --port 5432 \
     --cidr 10.0.0.0/16
   ```

2. **Application using wrong credentials**
   ```bash
   # Get credentials from Secrets Manager
   aws secretsmanager get-secret-value \
     --secret-id midaz/rds-master-password \
     --query "SecretString" \
     --output text
   ```

### DocumentDB Authentication Failure

**Symptom:** `Authentication failed` when connecting.

**Solution:**
```bash
# Verify TLS requirement
aws docdb describe-db-cluster-parameters \
  --db-cluster-parameter-group-name default.docdb5.0 \
  --query "Parameters[?ParameterName=='tls'].ParameterValue"

# Connection string must include TLS
mongodb://user:pass@host:27017/?tls=true&tlsCAFile=global-bundle.pem
```

### ElastiCache Connection Issues

**Symptom:** Cannot connect to Redis/Valkey cluster.

**Diagnosis:**
```bash
# Get cluster endpoint
aws elasticache describe-replication-groups \
  --replication-group-id midaz-elasticache \
  --query "ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint"

# Check encryption settings
aws elasticache describe-replication-groups \
  --replication-group-id midaz-elasticache \
  --query "ReplicationGroups[0].{Transit:TransitEncryptionEnabled,AtRest:AtRestEncryptionEnabled}"
```

**Note:** ElastiCache with encryption in-transit requires TLS connections.

## Networking Issues

### Cross-AZ Communication Failures

**Symptom:** Pods in different AZs cannot communicate.

**Diagnosis:**
```bash
# Check VPC CNI configuration
kubectl get daemonset aws-node -n kube-system

# Verify pod CIDR allocation
kubectl get nodes -o jsonpath='{.items[*].spec.podCIDR}'
```

### DNS Resolution Failures

**Symptom:** Pods cannot resolve internal DNS names.

**Diagnosis:**
```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Test DNS from a pod
kubectl run -it --rm debug --image=busybox -- nslookup kubernetes.default
```

**Solution:**
```bash
# Restart CoreDNS if needed
kubectl rollout restart deployment coredns -n kube-system
```

## IAM Permission Issues

### AssumeRole Failures

**Symptom:** Services cannot assume IAM roles.

**Diagnosis:**
```bash
# Check trust policy
aws iam get-role \
  --role-name midaz-eks-node-role \
  --query "Role.AssumeRolePolicyDocument"
```

### IRSA Not Working

**Symptom:** Pods not getting expected AWS permissions.

**Diagnosis:**
```bash
# Verify service account annotation
kubectl get serviceaccount <sa-name> -n <namespace> -o yaml

# Check OIDC provider
aws eks describe-cluster \
  --name midaz-eks \
  --query "cluster.identity.oidc"

# Verify IAM role trust policy includes the OIDC provider
aws iam get-role \
  --role-name midaz-alb-controller-role \
  --query "Role.AssumeRolePolicyDocument"
```

## Helm Deployment Issues

### Helm Release Stuck

**Symptom:** Helm deployment times out or stays in `pending-install`.

**Diagnosis:**
```bash
# Check Helm release status
helm status midaz -n midaz

# List all releases
helm list -A

# Check for failed hooks
kubectl get jobs -n midaz
```

### Lambda Custom Resource Failures

**Symptom:** Helm stack deployed via Lambda fails.

**Diagnosis:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/midaz-helm-deployer --follow

# Check CloudFormation custom resource events
aws cloudformation describe-stack-events \
  --stack-name midaz-helm \
  --query "StackEvents[?ResourceType=='Custom::HelmChart']"
```

## Monitoring and Logs

### Viewing EKS Logs

```bash
# Control plane logs
aws logs describe-log-groups \
  --log-group-name-prefix /aws/eks/midaz-eks

# Get recent logs
aws logs tail /aws/eks/midaz-eks/cluster --since 1h
```

### Viewing RDS Logs

```bash
# List available log files
aws rds describe-db-log-files \
  --db-instance-identifier midaz-rds

# Download specific log
aws rds download-db-log-file-portion \
  --db-instance-identifier midaz-rds \
  --log-file-name error/postgresql.log.2024-01-01-00
```

### Viewing Application Logs

```bash
# All pods in namespace
kubectl logs -n midaz -l app=midaz --all-containers

# Follow logs
kubectl logs -n midaz -l app=midaz -f
```

## Cleanup and Deletion

### Stack Deletion Fails

**Symptom:** Stack stuck in `DELETE_IN_PROGRESS` or `DELETE_FAILED`.

**Common Causes:**

1. **S3 bucket not empty**
   ```bash
   # Empty bucket before deletion
   aws s3 rm s3://bucket-name --recursive
   ```

2. **ENIs still attached**
   ```bash
   # Find orphaned ENIs
   aws ec2 describe-network-interfaces \
     --filters "Name=vpc-id,Values=vpc-xxx" \
     --query "NetworkInterfaces[?Status=='available'].NetworkInterfaceId"

   # Delete orphaned ENIs
   aws ec2 delete-network-interface --network-interface-id eni-xxx
   ```

3. **Security groups with dependencies**
   ```bash
   # Find SG dependencies
   aws ec2 describe-security-groups \
     --filters "Name=vpc-id,Values=vpc-xxx" \
     --query "SecurityGroups[].{Id:GroupId,Name:GroupName}"
   ```

### Force Delete Stack

```bash
# Skip resources that fail to delete
aws cloudformation delete-stack \
  --stack-name midaz \
  --retain-resources LogicalResourceId1 LogicalResourceId2

# Or delete with role override
aws cloudformation delete-stack \
  --stack-name midaz \
  --role-arn arn:aws:iam::xxx:role/admin-role
```

### Manual Cleanup Checklist

If stack deletion fails completely:

1. [ ] Delete EKS node groups
2. [ ] Delete EKS cluster
3. [ ] Delete RDS instances and snapshots
4. [ ] Delete DocumentDB clusters
5. [ ] Delete ElastiCache clusters
6. [ ] Delete AmazonMQ brokers
7. [ ] Delete NAT Gateways
8. [ ] Release Elastic IPs
9. [ ] Delete VPC Endpoints
10. [ ] Delete Security Groups
11. [ ] Delete Subnets
12. [ ] Delete Route Tables
13. [ ] Detach and delete Internet Gateway
14. [ ] Delete VPC
15. [ ] Delete KMS keys (schedule for deletion)
16. [ ] Delete Secrets in Secrets Manager
17. [ ] Delete CloudWatch Log Groups

---

## Getting Help

If you're still experiencing issues:

1. **Check CloudFormation Events**
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name midaz \
     --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED']"
   ```

2. **Enable Detailed Logging**
   ```bash
   # For EKS
   aws eks update-cluster-config \
     --name midaz-eks \
     --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'
   ```

3. **Open an Issue**
   - [GitHub Issues](https://github.com/LerianStudio/midaz-cloudformation-foundation/issues)
   - Include: Stack events, CloudFormation template version, Region

---

For more information, see:
- [README.md](../README.md) - Quick start guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture details
- [COST_ESTIMATION.md](COST_ESTIMATION.md) - Cost breakdown
