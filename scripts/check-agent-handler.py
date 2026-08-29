#!/usr/bin/env python3
"""Behavioural checks for the inline Lambda handler in templates/agent.yaml.

The handler ships as a template string, so nothing imports it and nothing type
checks it. CI compiles it; this script loads it and asserts the behaviours the
template's comments claim: the enrollment token never reaches a log line, the
chart is pinned by digest when one is supplied, an opaque token cannot break out
of the values document, the physical id follows the namespace so a moved agent
is replaced rather than duplicated, and a delete never wedges the stack.

Run: python3 scripts/check-agent-handler.py
"""

import json
import os
import pathlib
import sys
import types

import yaml

TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "templates" / "agent.yaml"


def load_handler():
    loader = yaml.SafeLoader
    loader.add_multi_constructor("!", lambda l, suffix, node: None)
    doc = yaml.load(TEMPLATE.read_text(), Loader=loader)
    source = doc["Resources"]["AgentDeployerFunction"]["Properties"]["Code"]["ZipFile"]
    module = types.ModuleType("agent_handler")
    exec(compile(source, "agent.yaml:AgentDeployerFunction", "exec"), module.__dict__)
    return module


def check_token_never_logged(mod):
    event = {
        "RequestType": "Update",
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
    assert logged.count("<redacted>") == 2, logged
    # redact works on a copy: the handler still installs with the real token.
    assert event["ResourceProperties"]["EnrollmentToken"] == "super-secret"


def check_digest_pins_the_chart(mod):
    repo = "oci://ghcr.io/lerianstudio/charts/lerian-agent"
    digest = "sha256:" + "a" * 64
    assert mod.chart_reference({"ChartRepository": repo, "ChartDigest": digest}) == f"{repo}@{digest}"
    assert mod.chart_reference({"ChartRepository": repo, "ChartDigest": ""}) == repo
    assert mod.chart_reference({"ChartRepository": repo}) == repo


def check_values_survive_a_hostile_token(mod):
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


CHECKS = (
    check_token_never_logged,
    check_digest_pins_the_chart,
    check_values_survive_a_hostile_token,
    check_namespace_change_replaces,
    check_delete_never_wedges_the_stack,
)


def main():
    mod = load_handler()
    for check in CHECKS:
        check(mod)
        print(f"  [PASS] {check.__name__}")
    print(f"agent.yaml inline handler: {len(CHECKS)}/{len(CHECKS)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
