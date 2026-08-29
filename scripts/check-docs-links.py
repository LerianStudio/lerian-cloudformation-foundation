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

The fourth check covers the way those same commands fail one step later, past
the CLI and inside AWS. A parameter typed `AWS::EC2::AvailabilityZone::Name` is
validated against the launch region, so its default is only valid in the region
it was written for: foundation.yaml defaults to us-east-2a/b/c. A command that
does not override those defaults is rejected at CreateStack in every other
region - including us-east-1 - before a single resource is created.

The fifth check is that same failure on the surface it actually shipped on: a
quick-create launch button, whose parameters ride in the URL as `param_<Name>`.
A button that leaves a region-scoped default unprefilled hands the customer a
console form CloudFormation rejects after they press Create - which is exactly
what the release notes' own button did.

Run: python3 scripts/check-docs-links.py
"""

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

BUCKET = "lerian-cloudformation-templates"
REGION = "sa-east-1"

# Stops at & so a quick-create link's following query parameters are not swallowed.
TEMPLATE_URL = re.compile(
    r"https://([a-z0-9.-]+)\.s3(?:\.([a-z0-9-]+))?\.amazonaws\.com/(releases/[^\s)\]\"'&]+\.yaml)"
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
TEMPLATE_ARGUMENT = re.compile(r"--template-(?:url|file)[=\s]+(\S+)")

# The console's quick-create form, carrying its template and its prefilled
# parameter values in the query string.
QUICKCREATE = re.compile(r"#/stacks/quickcreate\?(\S*)")
QUICKCREATE_TEMPLATE = re.compile(r"templateURL=([^&\s)]+)")
QUICKCREATE_PARAM = re.compile(r"param_(\w+)")

# A shell variable in a template argument is expanded by the reader's shell, not
# here, and a ${{ }} expression by the Actions runner. Dropping either leaves the
# literal path around it, which is what identifies the template. The ${{ }} form
# is matched first because it holds spaces: left in, it would cut a URL short at
# the first one and silently skip the button CI itself publishes.
SHELL_VARIABLE = re.compile(r"\$\{\{[^}]*\}\}|\$\{?\w+\}?")


class CFNLoader(yaml.SafeLoader):
    """Keeps intrinsics as {tag: value} instead of refusing to load the file."""


CFNLoader.add_multi_constructor(
    "!", lambda loader, suffix, node: {suffix: str(getattr(node, "value", ""))}
)


def command_sources():
    return sorted(
        p
        for p in ROOT.rglob("*")
        if p.suffix in {".md", ".sh", ".yaml", ".yml"} and ".git" not in p.parts
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
                if bucket != BUCKET or (region and region != REGION):
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
    for path in command_sources():
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


def template_behind(argument):
    """The repository template a --template-url or --template-file argument names.

    The argument can be an S3 URL, a local path, or either one assembled from
    shell variables, so it is matched by the path it ends with: `foundation.yaml`
    resolves to templates/foundation.yaml, and the ambiguous `infrastructure.yaml`
    is disambiguated by the product directory in front of it. None when nothing
    in the tree matches - a placeholder like `https://...` names no template
    whose parameters could be checked.
    """
    parts = [p for p in SHELL_VARIABLE.sub("", argument.strip("\"'")).split("/") if p]
    if not parts or not parts[-1].endswith((".yaml", ".yml")):
        return None
    # Both extensions, or a .yml argument would be accepted above and then always
    # resolve to None - skipped in silence, which is the failure this file exists
    # to stop rather than to reproduce.
    candidates = [
        p for p in ROOT.rglob("*") if p.suffix in {".yaml", ".yml"} and ".git" not in p.parts
    ]
    for depth in range(1, len(parts) + 1):
        tail = parts[-depth:]
        matches = [p for p in candidates if list(p.relative_to(ROOT).parts)[-depth:] == tail]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return None
    return None


def region_scoped_defaults(template):
    """Parameters whose default only works in the region the template was written for.

    An `AWS::`-prefixed parameter type is resolved against the launch region and
    account, so CloudFormation validates its value before it creates anything. A
    default for one is a region baked into the template: correct where the author
    stood, rejected everywhere else.
    """
    document = yaml.load(template.read_text(), Loader=CFNLoader) or {}
    parameters = document.get("Parameters") or {}
    return sorted(
        name
        for name, spec in parameters.items()
        if isinstance(spec, dict)
        and str(spec.get("Type", "")).startswith(("AWS::", "List<AWS::"))
        and "Default" in spec
    )


def check_commands_override_region_scoped_defaults():
    failures = []
    checked = 0
    for path in command_sources():
        text = path.read_text()
        for lineno, _subcommand, body in cfn_commands(text):
            # A protected --cli-input-json file keeps secrets out of argv. In the
            # documentation that file is generated immediately above the command,
            # so inspect the containing example for its TemplateURL and parameters.
            scope = text if "--cli-input-json" in body else body
            argument = TEMPLATE_ARGUMENT.search(scope)
            if argument:
                template = template_behind(argument.group(1))
            else:
                documented_url = TEMPLATE_URL.search(scope)
                template = template_behind(documented_url.group(0)) if documented_url else None
            if template is None:
                continue
            checked += 1
            missing = [name for name in region_scoped_defaults(template) if name not in scope]
            if missing:
                failures.append(
                    f"{path.relative_to(ROOT)}:{lineno}: launches "
                    f"{template.relative_to(ROOT)} without {', '.join(missing)}; "
                    f"the template's defaults name another region and CreateStack "
                    f"rejects them here"
                )
    assert not failures, "commands AWS would reject at CreateStack:\n  " + "\n  ".join(failures)
    return checked


def quickcreate_links(text):
    """Yield (lineno, query) for each console quick-create URL.

    Variables are dropped before the URL is read: the release notes assemble
    their button from `${{ env.* }}`, whose spaces would otherwise end the URL
    early and leave the one button CI publishes unchecked.
    """
    for lineno, line in enumerate(text.splitlines(), 1):
        for query in QUICKCREATE.findall(SHELL_VARIABLE.sub("", line)):
            yield lineno, query


def check_quickcreate_links_prefill_region_scoped_defaults():
    """A launch button fails the same way a create-stack command does.

    Its parameters ride in the URL as `param_<Name>`, and one the button omits is
    left at the template's default - which for a region-scoped type names the
    region the author stood in. CloudFormation rejects it at CreateStack, in the
    console, after the customer has already clicked. Resolving the templateURL
    back to the template is what makes the required set readable rather than
    listed here, so a fourth region-scoped parameter is covered on arrival.
    """
    failures = []
    checked = 0
    for path in command_sources():
        for lineno, query in quickcreate_links(path.read_text()):
            argument = QUICKCREATE_TEMPLATE.search(query)
            template = template_behind(argument.group(1)) if argument else None
            if template is None:
                continue
            checked += 1
            supplied = set(QUICKCREATE_PARAM.findall(query))
            missing = [name for name in region_scoped_defaults(template) if name not in supplied]
            if missing:
                failures.append(
                    f"{path.relative_to(ROOT)}:{lineno}: launches "
                    f"{template.relative_to(ROOT)} without "
                    f"{', '.join('param_' + name for name in missing)}; "
                    f"the template's defaults name another region and CreateStack "
                    f"rejects the button here"
                )
    assert not failures, "launch buttons AWS would reject at CreateStack:\n  " + "\n  ".join(
        failures
    )
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
    assert TEMPLATE_URL.findall(
        "https://lerian-cloudformation-templates.s3.amazonaws.com/releases/latest/foundation.yaml"
    ) == [("lerian-cloudformation-templates", "", "releases/latest/foundation.yaml")]
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

    # A template argument reaches the file whether it arrives as a URL, a local
    # path, or a string the reader's shell assembles.
    assert template_behind("templates/foundation.yaml") == ROOT / "templates" / "foundation.yaml"
    assert (
        template_behind("https://b.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml")
        == ROOT / "templates" / "foundation.yaml"
    )
    assert (
        template_behind('"https://${BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}foundation.yaml"')
        == ROOT / "templates" / "foundation.yaml"
    )
    # A basename every product shares is only resolved once the directory in
    # front of it says which product, and a placeholder resolves to nothing.
    assert template_behind("releases/latest/products/midaz/infrastructure.yaml") == (
        ROOT / "products" / "midaz" / "infrastructure.yaml"
    )
    assert template_behind("infrastructure.yaml") is None
    assert template_behind("https://...") is None
    # A .yml argument is accepted, so it has to be resolvable too. This tree has
    # no .yml template, so the workflow files stand in as the proof.
    assert template_behind(".github/workflows/release.yml") == (
        ROOT / ".github" / "workflows" / "release.yml"
    )
    # An Actions expression holds spaces; left in, it would truncate the URL.
    assert (
        template_behind(
            '"https://${{ env.B }}.s3.amazonaws.com/releases/latest/foundation.yaml"'
        )
        == ROOT / "templates" / "foundation.yaml"
    )
    # The parameters this repository actually has to override, read from the
    # template rather than named here, so a fourth one is covered on arrival.
    assert region_scoped_defaults(ROOT / "templates" / "foundation.yaml") == [
        "AvailabilityZone1",
        "AvailabilityZone2",
        "AvailabilityZone3",
    ]
    # A launch button is read whether its query ends the line or closes a
    # markdown link, and its prefilled parameters are read out of the query.
    button = (
        "[![Launch](img.png)](https://console.aws.amazon.com/cloudformation/home"
        "?region=${{ env.AWS_REGION }}#/stacks/quickcreate?templateURL=https://"
        "${{ env.S3_BUCKET }}.s3.sa-east-1.amazonaws.com/releases/latest/foundation.yaml"
        "&param_AvailabilityZone1=${{ env.AWS_REGION }}a)"
    )
    (lineno, query), = quickcreate_links(button)
    assert lineno == 1
    assert QUICKCREATE_PARAM.findall(query) == ["AvailabilityZone1"]
    assert template_behind(QUICKCREATE_TEMPLATE.search(query).group(1)) == (
        ROOT / "templates" / "foundation.yaml"
    )
    return 21


CHECKS = (
    check_documented_templates_are_published,
    check_relative_doc_links_resolve,
    check_cli_commands_use_the_right_template_option,
    check_commands_override_region_scoped_defaults,
    check_quickcreate_links_prefill_region_scoped_defaults,
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
