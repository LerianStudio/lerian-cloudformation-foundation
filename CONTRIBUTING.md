# Contributing to Midaz CloudFormation Foundation

Thank you for your interest in contributing to Midaz CloudFormation Foundation! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Template Guidelines](#template-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please be respectful and constructive in all interactions.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment
4. Create a feature branch
5. Make your changes
6. Submit a pull request

## Development Setup

### Prerequisites

- AWS CLI v2
- Python 3.9+ (for cfn-lint)
- Node.js 18+ (for commitlint)
- Ruby (optional, for additional validation)

### Install Dependencies

```bash
# Install cfn-lint
pip install cfn-lint

# Install commitlint
npm install

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Validate Templates

```bash
# Run cfn-lint on all templates
cfn-lint templates/*.yaml

# Run the validation script
./scripts/validate.sh

# Test locally without AWS
./scripts/test-local.sh
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feat/add-elasticache-cluster-mode` - New features
- `fix/rds-security-group-rules` - Bug fixes
- `docs/update-readme` - Documentation
- `refactor/vpc-subnet-layout` - Refactoring

### Template Changes

When modifying CloudFormation templates:

1. Follow AWS CloudFormation best practices
2. Add parameter constraints and descriptions
3. Include proper tagging on all resources
4. Test with cfn-lint before committing
5. Update documentation if parameters change

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/). All commits must follow this format:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Formatting, missing semicolons, etc.
- `refactor` - Code change that neither fixes a bug nor adds a feature
- `perf` - Performance improvement
- `test` - Adding missing tests
- `chore` - Maintenance tasks
- `ci` - CI/CD changes
- `build` - Build system changes

### Scopes

Use the template name as scope:

- `vpc`, `eks`, `rds`, `documentdb`, `elasticache`, `amazonmq`
- `route53`, `alb-controller`, `external-dns`
- `midaz-helm`, `midaz-infrastructure`, `midaz-complete`
- `scripts`, `ci`, `docs`

### Examples

```bash
# Feature
feat(rds): add support for Aurora PostgreSQL

# Bug fix
fix(vpc): correct NAT gateway route table association

# Breaking change
feat(eks)!: upgrade minimum Kubernetes version to 1.30

BREAKING CHANGE: Clusters running Kubernetes < 1.30 must upgrade before updating.

# Documentation
docs(readme): add troubleshooting section
```

## Pull Request Process

1. **Update Documentation**: Update README.md and other docs if needed
2. **Pass CI**: Ensure all CI checks pass (cfn-lint, Checkov)
3. **Request Review**: Request review from maintainers
4. **Address Feedback**: Make requested changes
5. **Squash Commits**: Keep commit history clean

### PR Title

Follow the same format as commit messages:

```
feat(rds): add PostgreSQL 17 support
```

### PR Description Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] cfn-lint passes
- [ ] Checkov passes
- [ ] Manual deployment tested

## Checklist
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No sensitive data in commits
```

## Template Guidelines

### Parameters

```yaml
Parameters:
  MyParameter:
    Type: String
    Description: Clear description of what this parameter does
    Default: sensible-default
    AllowedValues:
      - option1
      - option2
    ConstraintDescription: Must be option1 or option2
```

### Resources

```yaml
Resources:
  MyResource:
    Type: AWS::Service::Resource
    Properties:
      # Include all required properties
      Tags:
        - Key: Name
          Value: !Sub "${ProjectName}-resource-name"
        - Key: Environment
          Value: !Ref EnvironmentName
        - Key: ManagedBy
          Value: CloudFormation
```

### Outputs

```yaml
Outputs:
  ResourceId:
    Description: Clear description of the output
    Value: !Ref MyResource
    Export:
      Name: !Sub "${ProjectName}-resource-id"
```

### Security Best Practices

- Never hardcode credentials
- Use Secrets Manager for sensitive data
- Enable encryption at rest and in transit
- Follow least privilege for IAM roles
- Restrict security group rules to minimum required

## Testing

### Local Validation

```bash
# Validate all templates
./scripts/validate.sh

# Test specific template
cfn-lint templates/rds.yaml
```

### Security Scanning

```bash
# Run Checkov
checkov -d templates/
```

## Documentation

### When to Update Docs

- Adding new parameters
- Changing default values
- Adding new templates
- Modifying deployment procedures
- Adding new scripts

### Documentation Files

- `README.md` - Main documentation
- `CHANGELOG.md` - Version history
- `examples/aws/README.md` - Parameter reference
- `docs/MARKETPLACE_CHECKLIST.md` - Publication guide

## Questions?

- Open an issue for bugs or feature requests
- Join our Discord community for discussions
- Check existing issues before creating new ones

Thank you for contributing!
