# Architecture Documentation

This document provides detailed architecture information for the Midaz CloudFormation Foundation.

## Table of Contents

- [Overview](#overview)
- [Network Architecture](#network-architecture)
- [Compute Architecture](#compute-architecture)
- [Data Architecture](#data-architecture)
- [Security Architecture](#security-architecture)
- [High Availability](#high-availability)
- [Scalability](#scalability)
- [Template Dependencies](#template-dependencies)

## Overview

The Midaz CloudFormation Foundation implements a production-ready, multi-tier architecture on AWS. The design follows AWS Well-Architected Framework principles across all five pillars:

- **Operational Excellence**: Infrastructure as Code, automated deployments
- **Security**: Defense in depth, encryption, least privilege
- **Reliability**: Multi-AZ, auto-scaling, backup strategies
- **Performance Efficiency**: Right-sized instances, caching layers
- **Cost Optimization**: Reserved capacity options, efficient resource usage

## Network Architecture

### VPC Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VPC: 10.0.0.0/16                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Internet Gateway                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│  ┌───────────────┬───────────┴───────────┬───────────────┐             │
│  │               │                       │               │             │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  │  Public Subnet  │  │  Public Subnet  │  │  Public Subnet  │     │
│  │  │  10.0.1.0/24    │  │  10.0.2.0/24    │  │  10.0.3.0/24    │     │
│  │  │     (AZ-a)      │  │     (AZ-b)      │  │     (AZ-c)      │     │
│  │  │                 │  │                 │  │                 │     │
│  │  │  • NAT Gateway  │  │  • NAT Gateway  │  │  • NAT Gateway  │     │
│  │  │  • ALB          │  │  • ALB          │  │  • ALB          │     │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘     │
│  │           │                    │                    │               │
│  │  ┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐     │
│  │  │ Private Subnet  │  │ Private Subnet  │  │ Private Subnet  │     │
│  │  │  10.0.11.0/24   │  │  10.0.12.0/24   │  │  10.0.13.0/24   │     │
│  │  │                 │  │                 │  │                 │     │
│  │  │  • EKS Nodes    │  │  • EKS Nodes    │  │  • EKS Nodes    │     │
│  │  │  • Lambda       │  │  • Lambda       │  │  • Lambda       │     │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘     │
│  │           │                    │                    │               │
│  │  ┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐     │
│  │  │Database Subnet  │  │Database Subnet  │  │Database Subnet  │     │
│  │  │  10.0.21.0/24   │  │  10.0.22.0/24   │  │  10.0.23.0/24   │     │
│  │  │                 │  │                 │  │                 │     │
│  │  │  • RDS Primary  │  │  • RDS Standby  │  │  • DocumentDB   │     │
│  │  │  • ElastiCache  │  │  • ElastiCache  │  │  • ElastiCache  │     │
│  │  │  • DocumentDB   │  │  • DocumentDB   │  │                 │     │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│  │                                                                     │
│  └─────────────────────────────────────────────────────────────────────┘
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      VPC Endpoints                               │   │
│  │  • S3 Gateway Endpoint                                           │   │
│  │  • ECR API/DKR Interface Endpoints                               │   │
│  │  • STS Interface Endpoint                                        │   │
│  │  • SSM/SSM Messages Interface Endpoints                          │   │
│  │  • CloudWatch Logs Interface Endpoint                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Subnet Strategy

| Tier | CIDR Range | Purpose | Internet Access |
|------|------------|---------|-----------------|
| Public | 10.0.1-3.0/24 | Load balancers, NAT | Direct (IGW) |
| Private | 10.0.11-13.0/24 | Application workloads | Outbound (NAT) |
| Database | 10.0.21-23.0/24 | Data stores | None |

### VPC Endpoints

VPC Endpoints provide private connectivity to AWS services without traversing the internet:

| Endpoint | Type | Purpose |
|----------|------|---------|
| S3 | Gateway | Container image layers, artifacts |
| ECR API | Interface | Docker registry API |
| ECR DKR | Interface | Docker registry pulls |
| STS | Interface | IAM role assumption |
| SSM | Interface | Parameter Store, Session Manager |
| CloudWatch Logs | Interface | Log shipping |

## Compute Architecture

### Amazon EKS

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EKS Control Plane                               │
│                      (AWS Managed, Multi-AZ)                            │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │  API Server   │  │    etcd       │  │  Controllers  │               │
│  │   (HA)        │  │   (HA)        │  │    (HA)       │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │ OIDC / IRSA
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         EKS Data Plane                                  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Managed Node Group (ARM64 Graviton)                 │   │
│  │                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │   │
│  │  │   Node 1     │  │   Node 2     │  │   Node 3     │           │   │
│  │  │  (AZ-a)      │  │  (AZ-b)      │  │  (AZ-c)      │           │   │
│  │  │              │  │              │  │              │           │   │
│  │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │           │   │
│  │  │ │  Midaz   │ │  │ │  Midaz   │ │  │ │  Midaz   │ │           │   │
│  │  │ │  Pods    │ │  │ │  Pods    │ │  │  │  Pods   │ │           │   │
│  │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │           │   │
│  │  │              │  │              │  │              │           │   │
│  │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │           │   │
│  │  │ │ Add-ons  │ │  │ │ Add-ons  │ │  │ │ Add-ons  │ │           │   │
│  │  │ │ CoreDNS  │ │  │ │ VPC CNI  │ │  │ │ EBS CSI  │ │           │   │
│  │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │           │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### EKS Add-ons

| Add-on | Version | Purpose |
|--------|---------|---------|
| VPC CNI | Latest | Pod networking with VPC IPs |
| CoreDNS | Latest | Cluster DNS |
| kube-proxy | Latest | Service networking |
| EBS CSI | Latest | Persistent volume provisioning |
| ALB Controller | v2.7+ | Application Load Balancer integration |
| External DNS | v0.14+ | Route53 DNS automation |

### Node Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Instance Type | m7g.large | Cost-effective ARM64 Graviton |
| AMI | Amazon Linux 2023 EKS | Optimized for EKS |
| Disk | 100GB gp3 | Sufficient for container images |
| Min/Max/Desired | 2/10/3 per AZ | Right-sized for production |

## Data Architecture

### Database Layer

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Data Architecture                                  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    Primary Data Store                             │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │                  Amazon RDS PostgreSQL                      │ │ │
│  │  │                                                             │ │ │
│  │  │  ┌─────────────┐              ┌─────────────┐              │ │ │
│  │  │  │   Primary   │  Sync Repl.  │   Standby   │              │ │ │
│  │  │  │   (AZ-a)    │◄────────────►│   (AZ-b)    │              │ │ │
│  │  │  └─────────────┘              └─────────────┘              │ │ │
│  │  │                                                             │ │ │
│  │  │  Features:                                                  │ │ │
│  │  │  • PostgreSQL 16.8                                         │ │ │
│  │  │  • Multi-AZ with automatic failover                        │ │ │
│  │  │  • Customer-managed KMS encryption                         │ │ │
│  │  │  • Performance Insights enabled                            │ │ │
│  │  │  • Automated backups (7-35 days)                          │ │ │
│  │  │  • Optional read replica                                   │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    Document Store                                 │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │                  Amazon DocumentDB                          │ │ │
│  │  │                                                             │ │ │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │ │ │
│  │  │  │Instance │  │Instance │  │Instance │                     │ │ │
│  │  │  │   1     │  │   2     │  │   3     │                     │ │ │
│  │  │  │ (AZ-a)  │  │ (AZ-b)  │  │ (AZ-c)  │                     │ │ │
│  │  │  └─────────┘  └─────────┘  └─────────┘                     │ │ │
│  │  │                                                             │ │ │
│  │  │  Features:                                                  │ │ │
│  │  │  • MongoDB 5.0 compatible                                   │ │ │
│  │  │  • 3-node cluster (configurable)                           │ │ │
│  │  │  • Customer-managed KMS encryption                         │ │ │
│  │  │  • Audit and profiler logging                              │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    Cache Layer                                    │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │               Amazon ElastiCache (Valkey)                   │ │ │
│  │  │                                                             │ │ │
│  │  │  ┌─────────┐              ┌─────────┐                       │ │ │
│  │  │  │ Primary │  Replication │ Replica │                       │ │ │
│  │  │  │ (AZ-a)  │◄────────────►│ (AZ-b)  │                       │ │ │
│  │  │  └─────────┘              └─────────┘                       │ │ │
│  │  │                                                             │ │ │
│  │  │  Features:                                                  │ │ │
│  │  │  • Valkey 7.2 (Redis compatible)                           │ │ │
│  │  │  • Multi-AZ with automatic failover                        │ │ │
│  │  │  • Encryption in-transit and at-rest                       │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    Message Queue                                  │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │               Amazon MQ (RabbitMQ)                          │ │ │
│  │  │                                                             │ │ │
│  │  │  ┌─────────────────────────────────────────────────────┐   │ │ │
│  │  │  │  RabbitMQ 3.13 Broker                               │   │ │ │
│  │  │  │  • mq.m5.large instance                             │   │ │ │
│  │  │  │  • CloudWatch logging                               │   │ │ │
│  │  │  │  • Secrets Manager credentials                      │   │ │ │
│  │  │  └─────────────────────────────────────────────────────┘   │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────►│   ALB    │────►│  EKS     │────►│   RDS    │
│          │     │          │     │  Pods    │     │PostgreSQL│
└──────────┘     └──────────┘     └────┬─────┘     └──────────┘
                                       │
                                       │
                      ┌────────────────┼────────────────┐
                      │                │                │
                      ▼                ▼                ▼
                ┌──────────┐    ┌──────────┐    ┌──────────┐
                │DocumentDB│    │ElastiCache│   │ AmazonMQ │
                │          │    │          │    │          │
                └──────────┘    └──────────┘    └──────────┘
```

## Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Security Layers                                  │
│                                                                         │
│  Layer 1: Network Security                                              │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  • VPC isolation with private subnets                             │ │
│  │  • Security groups (stateful firewall)                            │ │
│  │  • NACLs (stateless firewall)                                     │ │
│  │  • VPC Flow Logs for traffic analysis                             │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Layer 2: Identity & Access                                             │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  • IAM roles with least privilege                                 │ │
│  │  • IRSA for pod-level permissions                                 │ │
│  │  • No long-lived credentials                                      │ │
│  │  • OIDC federation for GitHub Actions                             │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Layer 3: Data Protection                                               │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  • KMS encryption for all data at rest                            │ │
│  │  • TLS 1.2+ for all data in transit                               │ │
│  │  • Secrets Manager for credentials                                │ │
│  │  • No secrets in code or environment variables                    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Layer 4: Logging & Monitoring                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  • CloudWatch Logs for all components                             │ │
│  │  • EKS audit logs                                                 │ │
│  │  • Database audit logs                                            │ │
│  │  • VPC Flow Logs                                                  │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### KMS Key Architecture

| Resource | KMS Key | Purpose |
|----------|---------|---------|
| RDS | `${ProjectName}-rds` | Database encryption |
| DocumentDB | `${ProjectName}-documentdb` | Document store encryption |
| EKS Secrets | `${ProjectName}-eks` | etcd secrets encryption |
| S3 | Default | Template storage |

### Security Group Rules

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| VPC CIDR | RDS | 5432 | TCP | PostgreSQL |
| VPC CIDR | DocumentDB | 27017 | TCP | MongoDB |
| VPC CIDR | ElastiCache | 6379 | TCP | Redis/Valkey |
| VPC CIDR | AmazonMQ | 5671 | TCP | AMQP/TLS |
| EKS Nodes | EKS Control | 443 | TCP | API Server |

## High Availability

### Multi-AZ Deployment

All critical components are deployed across multiple Availability Zones:

| Component | AZ Distribution | Failover |
|-----------|-----------------|----------|
| EKS Nodes | 3 AZs (1 per subnet) | Automatic |
| RDS | 2 AZs (Primary + Standby) | Automatic |
| DocumentDB | 3 AZs | Automatic |
| ElastiCache | 2 AZs | Automatic |
| NAT Gateway | 3 AZs | Per-AZ |

### Recovery Objectives

| Metric | Target | Implementation |
|--------|--------|----------------|
| RTO (Recovery Time) | < 5 minutes | Multi-AZ failover |
| RPO (Recovery Point) | < 1 minute | Synchronous replication |
| Availability | 99.95% | Multi-AZ architecture |

## Scalability

### Horizontal Scaling

| Component | Scaling Method | Trigger |
|-----------|----------------|---------|
| EKS Nodes | Auto Scaling Groups | CPU/Memory utilization |
| Application Pods | HPA | Custom metrics |
| RDS | Read replicas | Manual |
| ElastiCache | Add replicas | Manual |

### Vertical Scaling

| Component | Scaling Method | Downtime |
|-----------|----------------|----------|
| EKS Nodes | Instance type change | Rolling |
| RDS | Modify instance class | Brief |
| DocumentDB | Modify instance class | Brief |
| ElastiCache | Modify node type | Brief |

## Template Dependencies

```
                    ┌───────────────┐
                    │  vpc.yaml     │
                    │  (Foundation) │
                    └───────┬───────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ▼                ▼                ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  eks.yaml   │  │  rds.yaml   │  │route53.yaml │
    │             │  │             │  │             │
    └──────┬──────┘  └─────────────┘  └──────┬──────┘
           │                                  │
           │         ┌─────────────┐         │
           │         │documentdb   │         │
           │         │.yaml        │         │
           │         └─────────────┘         │
           │                                  │
           │         ┌─────────────┐         │
           │         │elasticache  │         │
           │         │.yaml        │         │
           │         └─────────────┘         │
           │                                  │
           │         ┌─────────────┐         │
           │         │amazonmq     │         │
           │         │.yaml        │         │
           │         └─────────────┘         │
           │                                  │
    ┌──────┴──────────────────────────────────┴──────┐
    │                                                │
    ▼                                                ▼
┌─────────────┐                              ┌─────────────┐
│alb-controller│                              │external-dns │
│.yaml        │                              │.yaml        │
└──────┬──────┘                              └──────┬──────┘
       │                                            │
       └────────────────────┬───────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ midaz-helm    │
                    │ .yaml         │
                    └───────────────┘
```

### Deployment Order

1. **VPC** - Network foundation
2. **EKS** - Container orchestration (parallel with databases)
3. **RDS, DocumentDB, ElastiCache, AmazonMQ** - Data layer
4. **Route53** - DNS
5. **ALB Controller, External DNS** - Ingress and DNS automation
6. **Midaz Helm** - Application deployment

---

For more information, see:
- [README.md](../README.md) - Quick start guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [COST_ESTIMATION.md](COST_ESTIMATION.md) - Cost breakdown
