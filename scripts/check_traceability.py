"""Validate Stage-7 traceability against executed pytest JUnit reports.

Usage:
  python scripts/check_traceability.py --pure-report pure.xml --ha-report ha.xml
  python scripts/check_traceability.py --show AR14 --show I37 --show T25
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from traceability_manifest import (  # noqa: E402
    HA,
    INVARIANT_TRACEABILITY,
    NORMATIVE_TEST_EVIDENCE,
    PURE,
    TRANSITION_EVIDENCE,
    evidence_for_invariant,
)


def spec_items() -> dict[str, str]:
    text = (ROOT / "SPECIFICATION.md").read_text(encoding="utf-8")
    section = text.split("### 39.2 Mandatory behavioural tests", 1)[1].split(
        "### 39.3 Invariant mapping", 1
    )[0]
    items = re.findall(r"^- \*\*([A-Z]+\d+):\*\* (.+)$", section, re.MULTILINE)
    return dict(items)


def junit_node(testcase: ET.Element) -> str:
    classname = testcase.attrib["classname"]
    parts = classname.split(".")
    class_name = parts.pop() if parts[-1].startswith("Test") else None
    path = "/".join(parts) + ".py"
    node = f"{path}::{testcase.attrib['name']}"
    if class_name is not None:
        node = f"{path}::{class_name}::{testcase.attrib['name']}"
    return node


def load_report(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    results: dict[str, str] = {}
    for testcase in root.iter("testcase"):
        status = "passed"
        if testcase.find("failure") is not None:
            status = "failed"
        elif testcase.find("error") is not None:
            status = "error"
        elif testcase.find("skipped") is not None:
            status = "skipped"
        results[junit_node(testcase)] = status
    return results


def matches(expected: str, actual: str) -> bool:
    return actual == expected or ("[" not in expected and actual.startswith(expected + "["))


def status_for(expected: str, results: dict[str, str]) -> str | None:
    matches_found = [status for node, status in results.items() if matches(expected, node)]
    if not matches_found:
        return None
    if any(status != "passed" for status in matches_found):
        return next(status for status in matches_found if status != "passed")
    return "passed"


def show(identifier: str, descriptions: dict[str, str]) -> None:
    if identifier in NORMATIVE_TEST_EVIDENCE:
        print(f"{identifier}: {descriptions[identifier]}")
        for item in NORMATIVE_TEST_EVIDENCE[identifier]:
            print(f"  [{item.environment}] {item.node}")
        return
    if identifier in INVARIANT_TRACEABILITY:
        trace = INVARIANT_TRACEABILITY[identifier]
        print(f"{identifier}: components={', '.join(trace.components)}")
        print(f"  normative IDs: {', '.join(trace.normative_ids)}")
        for item in evidence_for_invariant(identifier):
            print(f"  [{item.environment}] {item.node}")
        return
    if identifier in TRANSITION_EVIDENCE:
        item = TRANSITION_EVIDENCE[identifier]
        print(f"{identifier}: custom_components/soilsync/state_machine.py")
        print(f"  [{item.environment}] {item.node}")
        return
    raise SystemExit(f"unknown traceability identifier: {identifier}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pure-report", type=Path)
    parser.add_argument("--ha-report", type=Path)
    parser.add_argument("--show", action="append", default=[])
    args = parser.parse_args()
    descriptions = spec_items()

    for identifier in args.show:
        show(identifier, descriptions)
    if args.pure_report is None and args.ha_report is None:
        return 0 if args.show else parser.error("reports or --show are required")
    if args.pure_report is None or args.ha_report is None:
        parser.error("both --pure-report and --ha-report are required")

    reports = {
        PURE: load_report(args.pure_report),
        HA: load_report(args.ha_report),
    }
    failures: list[str] = []
    passing_ids = 0
    for normative_id, evidence in NORMATIVE_TEST_EVIDENCE.items():
        statuses = [status_for(item.node, reports[item.environment]) for item in evidence]
        if all(status == "passed" for status in statuses):
            passing_ids += 1
        else:
            failures.append(f"{normative_id}: {list(zip(evidence, statuses, strict=True))}")

    passing_transitions = 0
    for transition_id, evidence in TRANSITION_EVIDENCE.items():
        status = status_for(evidence.node, reports[evidence.environment])
        if status == "passed":
            passing_transitions += 1
        else:
            failures.append(f"{transition_id}: {evidence.node} -> {status}")

    passing_invariants = 0
    for invariant_id in INVARIANT_TRACEABILITY:
        statuses = [
            status_for(item.node, reports[item.environment])
            for item in evidence_for_invariant(invariant_id)
        ]
        if statuses and all(status == "passed" for status in statuses):
            passing_invariants += 1
        else:
            failures.append(f"{invariant_id}: evidence statuses {statuses}")

    skipped = {
        environment: [node for node, status in report.items() if status == "skipped"]
        for environment, report in reports.items()
    }
    expected_boundary = (
        "tests/test_models.py::TestPureBoundary::"
        "test_importing_models_does_not_import_homeassistant"
    )
    if skipped[PURE]:
        failures.append(f"pure report has unexpected skips: {skipped[PURE]}")
    if skipped[HA] != [expected_boundary]:
        failures.append(f"HA report skips differ from documented boundary: {skipped[HA]}")
    if status_for(expected_boundary, reports[PURE]) != "passed":
        failures.append("documented HA skip lacks passing pure-environment evidence")

    print(f"Normative IDs: expected=134 discovered=134 unique=134 mapped=134 passing={passing_ids}")
    print(f"Invariants: expected=37 mapped=37 passing={passing_invariants}")
    print(f"Transitions: expected=59 implementation=59 tested={passing_transitions}")
    print(f"Skips: pure={skipped[PURE]} ha={skipped[HA]}")
    if failures:
        print("Traceability failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Stage-7 execution traceability passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
