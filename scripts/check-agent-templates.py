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

import json
import os
import pathlib
import sys
import types

import yaml

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"
AGENT = TEMPLATES / "agent.yaml"
FOUNDATION = TEMPLATES / "foundation.yaml"


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
    """Every template parameter Ref'd anywhere under node."""
    if isinstance(node, dict):
        found = set()
        for key, value in node.items():
            if key == "Ref" and isinstance(value, str) and value in known:
                found.add(value)
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

    This stack sends two keys and nothing else: controlPlane.url and
    agent.token, where agent.token is the SINGLE-USE ENROLLMENT token. The
    chart published today (LerianStudio/deployer, charts/lerian-agent) reads
    agent.token as a per-agent bearer token from an out-of-band registration
    call and therefore also requires agent.id, so it rejects this install;
    enrollment - the agent's first heartbeat consuming the token and fixing its
    own identity - is what removes that requirement. Nothing in this repository
    can verify the chart side, so this assertion is the contract: change it only
    together with the chart, and with the version customers are told to supply
    as AgentChartVersion. See docs/marketplace-changesets.md, step 8.

    The token itself is opaque and attacker-influenced, so the same check feeds
    a token full of YAML metacharacters and re-parses the document.
    """
    original = mod.VALUES_FILE
    mod.VALUES_FILE = "/tmp/agent-values-check.json"
    hostile = "x\n  evil: true\n#'\""
    try:
        mod.write_values({"ControlPlaneURL": "https://cp.example.com", "EnrollmentToken": hostile})
        parsed = yaml.safe_load(pathlib.Path(mod.VALUES_FILE).read_text())
        assert parsed == {
            "controlPlane": {"url": "https://cp.example.com"},
            "agent": {"token": hostile},
        }, parsed
        assert oct(os.stat(mod.VALUES_FILE).st_mode)[-3:] == "600"
    finally:
        if os.path.exists(mod.VALUES_FILE):
            os.remove(mod.VALUES_FILE)
        mod.VALUES_FILE = original


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


HANDLER_CHECKS = (
    check_token_never_logged,
    check_digest_pins_the_chart,
    check_values_contract_survives_a_hostile_token,
    check_namespace_change_replaces,
    check_delete_never_wedges_the_stack,
)

TEMPLATE_CHECKS = (
    check_every_agent_parameter_arms_the_rule,
    check_digest_is_reported_as_authoritative,
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
