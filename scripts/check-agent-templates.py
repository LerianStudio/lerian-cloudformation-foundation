#!/usr/bin/env python3
"""Behavioural checks for the agent templates.

templates/agent.yaml carries the Lambda handler as a template string, so nothing
imports it and nothing type checks it. CI compiles it; this script loads it and
asserts the behaviours the template's comments claim: the enrollment token never
reaches a log line, the chart is pinned by digest when one is supplied, an opaque
token cannot break out of the values document, the physical id follows the
namespace so a moved agent is replaced rather than duplicated, and a delete never
wedges the stack.

templates/foundation.yaml decides whether that stack is created at all. Its Rules
block is the only thing standing between a half-filled parameter set and a
twenty-minute deploy that ends with a cluster and no agent, so the wiring between
the agent parameters and that rule is asserted here too.

Run: python3 scripts/check-agent-templates.py
"""

import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
import types

import yaml

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"
AGENT = TEMPLATES / "agent.yaml"
FOUNDATION = TEMPLATES / "foundation.yaml"
SUB_PLACEHOLDER = re.compile(r"\$\{([A-Za-z0-9:.]+)\}")


class CFNLoader(yaml.SafeLoader):
    """Keeps intrinsics as {tag: value} instead of discarding them."""


def _intrinsic(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {suffix: loader.construct_sequence(node, deep=True)}
    return {suffix: loader.construct_mapping(node, deep=True)}


CFNLoader.add_multi_constructor("!", _intrinsic)


def load_template(path):
    return yaml.load(path.read_text(), Loader=CFNLoader)


def refs(node, known):
    """Every template parameter referenced anywhere under node."""
    if isinstance(node, dict):
        found = set()
        for key, value in node.items():
            if key == "Ref" and isinstance(value, str) and value in known:
                found.add(value)
            elif key == "Sub":
                text = value[0] if isinstance(value, list) and value else value
                overrides = (
                    set(value[1])
                    if isinstance(value, list) and len(value) > 1 and isinstance(value[1], dict)
                    else set()
                )
                if isinstance(text, str):
                    found |= {
                        name
                        for name in SUB_PLACEHOLDER.findall(text)
                        if name in known and name not in overrides
                    }
                found |= refs(value, known)
            else:
                found |= refs(value, known)
        return found
    if isinstance(node, list):
        return set().union(*(refs(item, known) for item in node))
    return set()


def load_handler():
    doc = load_template(AGENT)
    source = doc["Resources"]["AgentDeployerFunction"]["Properties"]["Code"]["ZipFile"]
    module = types.ModuleType("agent_handler")
    exec(compile(source, "agent.yaml:AgentDeployerFunction", "exec"), module.__dict__)
    return module


def check_token_never_logged(mod):
    event = {
        "RequestType": "Update",
        "ResponseURL": "https://cloudformation-custom-resource-response.example/presigned-secret",
        "ResourceProperties": {
            "EnrollmentToken": "super-secret",
            "ClusterName": "c1",
            "Namespace": "lerian-system",
        },
        "OldResourceProperties": {"EnrollmentToken": "older-secret"},
    }
    logged = json.dumps(mod.redact(event))
    assert "super-secret" not in logged, logged
    assert "older-secret" not in logged, logged
    assert "presigned-secret" not in logged, logged
    assert logged.count("<redacted>") == 3, logged
    # redact works on a copy: the handler still installs with the real token.
    assert event["ResourceProperties"]["EnrollmentToken"] == "super-secret"


def check_digest_pins_the_chart(mod):
    repo = "oci://ghcr.io/lerianstudio/charts/lerian-agent"
    digest = "sha256:" + "a" * 64
    assert mod.chart_reference({"ChartRepository": repo, "ChartDigest": digest}) == f"{repo}@{digest}"
    assert mod.chart_reference({"ChartRepository": repo, "ChartDigest": ""}) == repo
    assert mod.chart_reference({"ChartRepository": repo}) == repo


def check_values_contract_survives_a_hostile_token(mod):
    """The whole values contract with the lerian-agent chart, pinned here.

    This stack sends three keys and nothing else: controlPlane.url, agent.token
    (the SINGLE-USE ENROLLMENT token) and agent.managedNamespaces (the release's
    own namespace - what an empty list would have meant - plus lerian-infra, so
    a preflight repair can install cluster components). The chart renders write
    Roles into every managed namespace, which is why the install creates
    lerian-infra first; see check_infra_namespace_is_ensured. Nothing in this
    repository can verify the chart side, so this assertion is the contract:
    change it only together with the chart, and with the version customers are
    told to supply as AgentChartVersion. See docs/marketplace-changesets.md,
    step 8.

    The token itself is opaque and attacker-influenced, so the same check feeds
    a token full of YAML metacharacters and re-parses the document.
    """
    with tempfile.TemporaryDirectory(prefix="agent-values-check-") as workdir:
        original = mod.VALUES_FILE
        mod.VALUES_FILE = os.path.join(workdir, "values.json")
        hostile = "x\n  evil: true\n#'\""
        try:
            mod.write_values(
                {
                    "ControlPlaneURL": "https://cp.example.com",
                    "EnrollmentToken": hostile,
                    "Namespace": "lerian-system",
                }
            )
            parsed = yaml.safe_load(pathlib.Path(mod.VALUES_FILE).read_text())
            assert parsed == {
                "controlPlane": {"url": "https://cp.example.com"},
                "agent": {
                    "token": hostile,
                    "managedNamespaces": ["lerian-system", "lerian-infra"],
                },
            }, parsed
            assert oct(os.stat(mod.VALUES_FILE).st_mode)[-3:] == "600"

            # AgentNamespace is configurable and may already be lerian-infra.
            # The chart renders a Role for every list item, so do not render the
            # same namespaced resource twice in that valid configuration.
            mod.write_values(
                {
                    "ControlPlaneURL": "https://cp.example.com",
                    "EnrollmentToken": hostile,
                    "Namespace": "lerian-infra",
                }
            )
            parsed = yaml.safe_load(pathlib.Path(mod.VALUES_FILE).read_text())
            assert parsed["agent"]["managedNamespaces"] == ["lerian-infra"], parsed
        finally:
            mod.VALUES_FILE = original


def check_infra_namespace_is_ensured(mod):
    """The repair namespace is created before helm runs, and 409 is success.

    The chart's managed-namespace Roles require lerian-infra to exist at
    install time; helm --create-namespace only makes the release's own. The
    call must go to the cluster's own endpoint with the issued bearer token,
    and a namespace that already exists (409) must not fail the install while
    any other refusal must.
    """
    cluster = {
        "endpoint": "https://cluster.example",
        "certificateAuthority": {"data": mod.base64.b64encode(b"ca-pem").decode()},
    }
    calls = []

    class Refusal(mod.urllib.error.HTTPError):
        def __init__(self, code):
            Exception.__init__(self)
            self.code = code

    def urlopen(req, timeout, context):
        calls.append((req.full_url, req.get_method(), req.get_header("Authorization")))
        if len(calls) == 2:
            raise Refusal(409)
        if len(calls) == 3:
            raise Refusal(403)
        return types.SimpleNamespace()

    original_urlopen, original_ssl = mod.urllib.request.urlopen, mod.ssl.create_default_context
    mod.urllib.request.urlopen = urlopen
    mod.ssl.create_default_context = lambda cadata: None
    try:
        mod.ensure_infra_namespace(cluster, "issued-token")
        mod.ensure_infra_namespace(cluster, "issued-token")  # 409: already there
        try:
            mod.ensure_infra_namespace(cluster, "issued-token")
        except mod.urllib.error.HTTPError as exc:
            assert exc.code == 403
        else:
            raise AssertionError("a refused namespace create was swallowed")
    finally:
        mod.urllib.request.urlopen, mod.ssl.create_default_context = original_urlopen, original_ssl

    assert all(
        url == "https://cluster.example/api/v1/namespaces"
        and method == "POST"
        and auth == "Bearer issued-token"
        for url, method, auth in calls
    ), calls


def check_helm_archive_is_verified(mod):
    with tempfile.TemporaryDirectory(prefix="helm-archive-check-") as workdir:
        archive = pathlib.Path(workdir) / "helm.tar.gz"
        archive.write_bytes(b"known archive")
        original = mod.HELM_SHA256
        try:
            mod.HELM_SHA256 = hashlib.sha256(archive.read_bytes()).hexdigest()
            mod.verify_helm_archive(archive)
            mod.HELM_SHA256 = "0" * 64
            try:
                mod.verify_helm_archive(archive)
            except RuntimeError as exc:
                assert str(exc) == "Helm archive checksum mismatch"
            else:
                raise AssertionError("a mismatched Helm archive was accepted")
        finally:
            mod.HELM_SHA256 = original


def check_response_put_retries(mod):
    attempts = []
    sleeps = []

    def urlopen(_request, timeout):
        attempts.append(timeout)
        if len(attempts) < 3:
            raise RuntimeError("https://presigned-secret.example")
        return types.SimpleNamespace()

    event = {
        "RequestType": "Create",
        "ResponseURL": "https://presigned-secret.example",
        "StackId": "stack",
        "RequestId": "request",
        "LogicalResourceId": "AgentDeployment",
        "ResourceProperties": {"ClusterName": "c1", "Namespace": "lerian-system"},
    }
    original_urlopen, original_sleep = mod.urllib.request.urlopen, mod.time.sleep
    mod.urllib.request.urlopen, mod.time.sleep = urlopen, sleeps.append
    try:
        mod.send_response(event, types.SimpleNamespace(log_stream_name="stream"), "SUCCESS")
    finally:
        mod.urllib.request.urlopen, mod.time.sleep = original_urlopen, original_sleep
    assert attempts == [30, 30, 30], attempts
    assert sleeps == [1, 2], sleeps


def check_digest_is_reported_as_authoritative():
    """A pinned digest must be readable from the stack, not just the version.

    Helm rejects a version that resolves to a DIFFERENT digest, but a version
    that resolves to nothing - a typo, or a tag never pushed - installs the
    digest unchecked (helm v3.21.4, pkg/registry/client.go ValidateReference:
    "The resource does not have to be tagged when digest is specified"). So the
    AgentChartVersion output can name a chart nothing verified, and the digest
    output is the only honest record of what runs.
    """
    for path in (AGENT, FOUNDATION):
        outputs = load_template(path)["Outputs"]
        assert "AgentChartDigest" in outputs, f"{path.name} reports a chart version with no digest beside it"


def check_namespace_change_replaces(mod):
    props = {"ClusterName": "c1", "Namespace": "lerian-system"}
    create = {"RequestType": "Create", "ResourceProperties": props}
    assert mod.resource_id(create) == "c1/lerian-system/lerian-agent"

    # Same namespace: the id is unchanged, so CloudFormation updates in place.
    update_same = dict(create, RequestType="Update", PhysicalResourceId="c1/lerian-system/lerian-agent")
    assert mod.resource_id(update_same) == "c1/lerian-system/lerian-agent"

    # New namespace: a new id, which is how CloudFormation learns to delete the
    # old release instead of leaving two enrolled agents running.
    update_moved = {
        "RequestType": "Update",
        "PhysicalResourceId": "c1/lerian-system/lerian-agent",
        "ResourceProperties": {"ClusterName": "c1", "Namespace": "lerian-other"},
    }
    assert mod.resource_id(update_moved) == "c1/lerian-other/lerian-agent"

    # The follow-up delete uninstalls from the namespace recorded in the id it
    # was handed, not from whatever the current properties happen to say.
    delete_old = {
        "RequestType": "Delete",
        "PhysicalResourceId": "c1/lerian-system/lerian-agent",
        "ResourceProperties": {"ClusterName": "c1", "Namespace": "lerian-other"},
    }
    assert mod.resource_id(delete_old) == "c1/lerian-system/lerian-agent"
    assert mod.namespace_of(delete_old, delete_old["ResourceProperties"]) == "lerian-system"


def check_delete_never_wedges_the_stack(mod):
    sent = {}

    def capture(event, context, status, data=None, reason=None):
        sent.update(status=status, data=data, reason=reason)

    def explode(*_args, **_kwargs):
        raise RuntimeError("get.helm.sh unreachable")

    original = mod.install_helm, mod.send_response
    mod.install_helm, mod.send_response = explode, capture
    try:
        mod.handler(
            {
                "RequestType": "Delete",
                "PhysicalResourceId": "c1/lerian-system/lerian-agent",
                "ResourceProperties": {"ClusterName": "c1", "Namespace": "lerian-system"},
            },
            types.SimpleNamespace(log_stream_name="stream-1"),
        )
    finally:
        mod.install_helm, mod.send_response = original

    assert sent["status"] == "SUCCESS", sent
    assert "skipped" in sent["data"]["Message"], sent


def check_failure_reason_is_bounded(mod):
    sent = {}

    def capture(event, context, status, data=None, reason=None):
        sent.update(status=status, data=data, reason=reason)

    def explode(*_args, **_kwargs):
        raise RuntimeError("x" * 5000)

    original = mod.install_helm, mod.send_response, mod.logger.disabled
    mod.install_helm, mod.send_response = explode, capture
    mod.logger.disabled = True
    try:
        mod.handler(
            {
                "RequestType": "Create",
                "ResourceProperties": {"ClusterName": "c1", "Namespace": "lerian-system"},
            },
            types.SimpleNamespace(log_stream_name="stream-1"),
        )
    finally:
        mod.install_helm, mod.send_response, mod.logger.disabled = original
    assert sent["status"] == "FAILED", sent
    assert len(sent["reason"]) == 1000, sent


def check_every_agent_parameter_arms_the_rule():
    doc = load_template(FOUNDATION)
    known = set(doc["Parameters"])
    stacks = {
        name: refs(resource.get("Properties", {}).get("Parameters", {}), known)
        for name, resource in doc["Resources"].items()
        if resource.get("Type") == "AWS::CloudFormation::Stack"
    }
    shared = set().union(*(p for name, p in stacks.items() if name != "AgentStack"))
    agent_only = stacks["AgentStack"] - shared
    assert agent_only, "AgentStack forwards no parameter of its own"

    armed = refs(doc["Rules"]["AgentParametersComplete"]["RuleCondition"], known)
    # A parameter the rule does not watch is a parameter a user can fill on its
    # own: no assertion fires, ShouldDeployAgent stays false, and the deploy
    # ends in a cluster with no agent and no error.
    missing = agent_only - armed
    assert not missing, f"agent parameters missing from RuleCondition: {sorted(missing)}"

    # The condition that actually creates the stack may only rest on parameters
    # the rule has already proven arrive together.
    gate = refs(doc["Conditions"]["ShouldDeployAgent"], known)
    assert gate <= armed, f"ShouldDeployAgent rests on unguarded parameters: {sorted(gate - armed)}"

    # Arming the rule is only half the guard. The RuleCondition decides when the
    # assertions run; the assertions are what actually reject the half-filled
    # set. Drop the Assert for a parameter the gate reads - during a refactor,
    # say - and CreateStack accepts the stack, ShouldDeployAgent stays false,
    # and the deploy ends in a cluster with no agent and no error: the same
    # silent failure, reached from the other side of the rule.
    asserted = refs(
        [a["Assert"] for a in doc["Rules"]["AgentParametersComplete"]["Assertions"]],
        known,
    )
    unasserted = gate - asserted
    assert not unasserted, f"ShouldDeployAgent rests on unasserted parameters: {sorted(unasserted)}"


def check_sub_parameters_are_references():
    known = {"ControlPlaneURL", "EnrollmentToken"}
    assert refs({"Sub": "${ControlPlaneURL}/agent"}, known) == {"ControlPlaneURL"}
    assert refs(
        {"Sub": ["${ControlPlaneURL}/${Alias}", {"Alias": {"Ref": "EnrollmentToken"}}]},
        known,
    ) == {"ControlPlaneURL", "EnrollmentToken"}


HANDLER_CHECKS = (
    check_token_never_logged,
    check_digest_pins_the_chart,
    check_values_contract_survives_a_hostile_token,
    check_infra_namespace_is_ensured,
    check_helm_archive_is_verified,
    check_response_put_retries,
    check_namespace_change_replaces,
    check_delete_never_wedges_the_stack,
    check_failure_reason_is_bounded,
)

TEMPLATE_CHECKS = (
    check_every_agent_parameter_arms_the_rule,
    check_digest_is_reported_as_authoritative,
    check_sub_parameters_are_references,
)


def main():
    mod = load_handler()
    for check in HANDLER_CHECKS:
        check(mod)
        print(f"  [PASS] {check.__name__}")
    for check in TEMPLATE_CHECKS:
        check()
        print(f"  [PASS] {check.__name__}")
    total = len(HANDLER_CHECKS) + len(TEMPLATE_CHECKS)
    print(f"agent templates: {total}/{total} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
