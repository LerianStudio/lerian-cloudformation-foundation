module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature (minor version bump)
        'fix',      // Bug fix (patch version bump)
        'docs',     // Documentation only
        'style',    // Code style (formatting, etc)
        'refactor', // Code refactoring (patch version bump)
        'perf',     // Performance improvement (patch version bump)
        'test',     // Adding tests
        'chore',    // Maintenance tasks
        'ci',       // CI/CD changes
        'build',    // Build system changes
        'revert',   // Revert previous commit
      ],
    ],
    'scope-enum': [
      1,
      'always',
      [
        // Core templates
        'vpc',
        'eks',
        'rds',
        'documentdb',
        'elasticache',
        'amazonmq',
        'route53',
        'alb-controller',
        'external-dns',
        // Product: midaz
        'midaz',
        'midaz-helm',
        'midaz-complete',
        'midaz-infrastructure',
        'midaz-application',
        // General
        'ci',
        'deps',
        'release',
        'scripts',
      ],
    ],
    'subject-case': [0],
    'body-max-line-length': [0],
  },
};
