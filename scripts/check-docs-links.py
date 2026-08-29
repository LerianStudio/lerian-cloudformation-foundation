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

The second check covers the other half of the same failure: links between the
documents themselves. A reader who follows the README into ARCHITECTURE.md and
finds a link to a document this repository has never had is at the same dead
end, one click further in. Every relative link in every Markdown file must
resolve to a file or directory that exists.

The third check covers the other kind of copy-pasteable surface: the
`aws cloudformation` commands in the docs, in the helper scripts, and in the
stack outputs themselves. `deploy` takes `--template-file`, a local path;
`create-stack` and `update-stack` take `--template-url`, an S3 URL. The wrong
pairing is not a subtle failure - the CLI rejects it with "Unknown options"
before it calls AWS at all - and it shipped in three places at once.

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

# Inline markdown links: [text](target), with the optional title markdown allows
# after the target. Without the title branch a titled link matches nothing at all
# and is silently skipped rather than checked.
MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")

# Reference-style definitions: [label]: target. Their targets resolve exactly like
# an inline link's, so they run through the same loop. The check above only sees
# https URLs into the release bucket, so a relative one would otherwise be unread.
# Up to three leading spaces still make a definition; four make a code block.
REFERENCE_LINK = re.compile(r"^ {0,3}\[[^\]]+\]:\s+(\S+)")

# Anything with a scheme is somebody else's to resolve, and a bare #anchor points
# inside the file that carries it.
EXTERNAL_LINK = re.compile(r"^([a-z][a-z0-9+.-]*:|//|#)")

# The template option each aws cloudformation subcommand actually accepts.
TEMPLATE_OPTION = {
    "deploy": "--template-file",
    "create-stack": "--template-url",
    "update-stack": "--template-url",
}
CFN_COMMAND = re.compile(r"aws\s+cloudformation\s+(deploy|create-stack|update-stack)\b")


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


def check_relative_doc_links_resolve():
    failures = []
    checked = 0
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            for target in MARKDOWN_LINK.findall(line) + REFERENCE_LINK.findall(line):
                if EXTERNAL_LINK.match(target):
                    continue
                checked += 1
                # A link may address a heading inside the target document.
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                if not resolved.exists():
                    failures.append(
                        f"{path.relative_to(ROOT)}:{lineno}: {target} does not exist"
                    )
    assert not failures, "documentation links with nothing behind them:\n  " + "\n  ".join(
        failures
    )
    return checked


def cfn_commands(text):
    """Yield (lineno, subcommand, body) for each aws cloudformation invocation.

    A command is its first line plus every following line while the previous one
    ends in a backslash, so the options belonging to it are read and the ones
    belonging to the next command are not.

    A match opening with a backtick is prose naming the command - a changelog
    entry, a sentence in the README - not something anyone pastes into a shell.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = CFN_COMMAND.search(lines[i])
        if match and not lines[i][: match.start()].endswith("`"):
            start, body = i + 1, [lines[i]]
            while body[-1].rstrip().rstrip('"').endswith("\\") and i + 1 < len(lines):
                i += 1
                body.append(lines[i])
            yield start, match.group(1), "\n".join(body)
        i += 1


def check_cli_commands_use_the_right_template_option():
    failures = []
    checked = 0
    sources = [p for p in ROOT.rglob("*") if p.suffix in {".md", ".sh", ".yaml", ".yml"}]
    for path in sorted(sources):
        if ".git" in path.parts:
            continue
        for lineno, subcommand, body in cfn_commands(path.read_text()):
            checked += 1
            wanted = TEMPLATE_OPTION[subcommand]
            for option in {"--template-file", "--template-url"} - {wanted}:
                if option in body:
                    failures.append(
                        f"{path.relative_to(ROOT)}:{lineno}: "
                        f"`aws cloudformation {subcommand}` is given {option}; "
                        f"it takes {wanted}"
                    )
    assert not failures, "aws cli commands the cli would reject:\n  " + "\n  ".join(failures)
    return checked


def check_link_patterns_match_what_they_claim():
    """No document in the tree carries a titled or relative reference link today,
    so the patterns covering them are asserted directly. Otherwise the coverage is
    untested until the day something depends on it."""
    assert MARKDOWN_LINK.findall('[a](./x.md) [b](./y.md "Title") [c](./z.md)') == [
        "./x.md",
        "./y.md",
        "./z.md",
    ]
    assert REFERENCE_LINK.findall("[label]: ./ref.md") == ["./ref.md"]
    assert REFERENCE_LINK.findall("   [three spaces]: ./ref.md") == ["./ref.md"]
    assert REFERENCE_LINK.findall("    [code block]: ./ref.md") == []
    assert [c[1] for c in cfn_commands("aws cloudformation deploy \\\n  --template-url x")] == [
        "deploy"
    ]
    # A backticked mention is prose about a command, not a command.
    assert list(cfn_commands("fixed: `aws cloudformation deploy` took --template-url")) == []
    # An echoed suggestion is one a reader pastes, so it is a command.
    assert [c[1] for c in cfn_commands('echo "  aws cloudformation deploy \\\\"')] == ["deploy"]
    # The continuation must stop at the end of the command, not run into the next.
    _, _, body = next(cfn_commands("aws cloudformation create-stack \\\n  --template-url x\nrm -rf /"))
    assert "rm -rf" not in body
    return 8


CHECKS = (
    check_documented_templates_are_published,
    check_relative_doc_links_resolve,
    check_cli_commands_use_the_right_template_option,
    check_link_patterns_match_what_they_claim,
)


def main():
    for check in CHECKS:
        count = check()
        print(f"  [PASS] {check.__name__} ({count} checked)")
    print(f"docs links: {len(CHECKS)}/{len(CHECKS)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
