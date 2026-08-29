#!/usr/bin/env python3
"""Every template URL the documentation hands a customer must be published.

The docs are full of launch buttons, quick-create links and copy-paste
`create-stack` commands, all carrying an https URL into the release bucket. Those
URLs are the product surface: a customer clicks one, and CloudFormation fetches
whatever is at the other end. Nothing in CI used to connect them to the files
this repository actually publishes, and both halves of that gap have already
cost a release - a default naming a bucket that does not exist, and quick-create
links left pointing at midaz templates after they were deleted.

So: every https URL into the release bucket that names a template under
`releases/latest/` is resolved back to the repository file the release workflow
would publish there. A URL with no file behind it fails the check.

`s3://` paths are deliberately not checked. They are operator commands - the
Marketplace runbook's `aws s3 rm` cleanup names the retired midaz templates on
purpose - and they are not something a customer can click.

Run: python3 scripts/check-docs-links.py
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

BUCKET = "lerian-cloudformation-templates"
REGION = "sa-east-1"

# Stops at & so a quick-create link's following query parameters are not swallowed.
TEMPLATE_URL = re.compile(
    r"https://([a-z0-9.-]+)\.s3\.([a-z0-9-]+)\.amazonaws\.com/(releases/[^\s)\]\"'&]+\.yaml)"
)


def publishes(key):
    """The repository file the release workflow would publish at this S3 key.

    Mirrors the layout in .github/workflows/release.yml: core templates at the
    root of the prefix, product templates under products/<product>/, and every
    core template also copied into each product prefix (AWS Marketplace requires
    nested templates to share one MPS3KeyPrefix).
    """
    parts = key.split("/")
    if parts[:2] != ["releases", "latest"]:
        # Versioned prefixes are immutable history: they serve the templates of
        # the release that produced them, not of this working tree.
        return None
    rest = parts[2:]
    if len(rest) == 1:
        return [ROOT / "templates" / rest[0]]
    if len(rest) == 3 and rest[0] == "products":
        product, name = rest[1], rest[2]
        return [ROOT / "products" / product / name, ROOT / "templates" / name]
    return []


def check_documented_templates_are_published():
    failures = []
    checked = 0
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            for bucket, region, key in TEMPLATE_URL.findall(line):
                where = f"{path.relative_to(ROOT)}:{lineno}"
                checked += 1
                if bucket != BUCKET or region != REGION:
                    failures.append(
                        f"{where}: URL points at {bucket} in {region}; "
                        f"releases are published to {BUCKET} in {REGION}"
                    )
                    continue
                candidates = publishes(key)
                if candidates is None:
                    continue
                if not candidates:
                    failures.append(f"{where}: {key} is not a path the release workflow publishes")
                elif not any(c.exists() for c in candidates):
                    failures.append(
                        f"{where}: {key} has no template behind it "
                        f"(looked for {', '.join(str(c.relative_to(ROOT)) for c in candidates)})"
                    )
    assert not failures, "documented template URLs that do not resolve:\n  " + "\n  ".join(failures)
    return checked


CHECKS = (check_documented_templates_are_published,)


def main():
    for check in CHECKS:
        count = check()
        print(f"  [PASS] {check.__name__} ({count} template URLs)")
    print(f"docs links: {len(CHECKS)}/{len(CHECKS)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
