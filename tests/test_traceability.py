"""Mechanical Stage-7 inventory, mapping, invariant, and skip audits."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from traceability_manifest import (
    HA,
    INVARIANT_TRACEABILITY,
    NORMATIVE_TEST_EVIDENCE,
    PURE,
    TRANSITION_EVIDENCE,
    evidence_for_invariant,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "SPECIFICATION.md"
MANIFEST = Path(__file__).with_name("traceability_manifest.py")

EXPECTED_GROUPS = {
    "SR": 13,
    "PI": 27,
    "MF": 5,
    "AC": 4,
    "ER": 12,
    "LC": 13,
    "ND": 17,
    "TB": 12,
    "AR": 17,
    "RC": 12,
    "HA": 2,
}


def normative_spec_items() -> list[tuple[str, str]]:
    text = SPEC.read_text(encoding="utf-8")
    section = text.split("### 39.2 Mandatory behavioural tests", 1)[1].split(
        "### 39.3 Invariant mapping", 1
    )[0]
    candidates = [line for line in section.splitlines() if line.startswith("- **")]
    parsed: list[tuple[str, str]] = []
    for line in candidates:
        match = re.fullmatch(r"- \*\*([A-Z]+\d+):\*\* (.+)", line)
        assert match is not None, f"malformed normative test row: {line}"
        parsed.append((match.group(1), match.group(2)))
    return parsed


def invariant_spec_ids() -> list[str]:
    text = SPEC.read_text(encoding="utf-8")
    section = text.split("## 27. Safety Invariants", 1)[1].split(
        "## 28. Home Assistant Entity Model", 1
    )[0]
    return re.findall(r"^- \*\*(I\d+) —", section, re.MULTILINE)


def literal_dict_keys(variable_name: str) -> list[str]:
    tree = ast.parse(MANIFEST.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if isinstance(target, ast.Name) and target.id == variable_name:
            value = node.value
            assert isinstance(value, ast.Dict)
            return [ast.literal_eval(key) for key in value.keys]
    raise AssertionError(f"{variable_name} dictionary literal not found")


def base_node(node: str) -> tuple[Path, tuple[str, ...]]:
    parts = node.split("::")
    assert len(parts) in (2, 3), node
    parts[-1] = parts[-1].split("[", 1)[0]
    return ROOT / parts[0], tuple(parts[1:])


def node_exists(node: str) -> bool:
    path, names = base_node(node)
    if not path.is_file():
        return False
    body = ast.parse(path.read_text(encoding="utf-8")).body
    if len(names) == 1:
        return any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == names[0]
            for item in body
        )
    class_name, function_name = names
    for item in body:
        if isinstance(item, ast.ClassDef) and item.name == class_name:
            return any(
                isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                and member.name == function_name
                for member in item.body
            )
    return False


class TestNormativeInventory:
    def test_spec_has_exactly_134_unique_well_formed_ids(self) -> None:
        items = normative_spec_items()
        ids = [item[0] for item in items]
        assert len(ids) == 134
        assert len(set(ids)) == 134
        expected = {
            f"{prefix}{number}"
            for prefix, end in EXPECTED_GROUPS.items()
            for number in range(1, end + 1)
        }
        assert set(ids) == expected

    def test_manifest_has_no_duplicate_unknown_missing_or_extra_normative_ids(self) -> None:
        spec_ids = {item[0] for item in normative_spec_items()}
        literal_keys = literal_dict_keys("NORMATIVE_TEST_EVIDENCE")
        assert len(literal_keys) == len(set(literal_keys))
        assert set(literal_keys) == spec_ids
        assert set(NORMATIVE_TEST_EVIDENCE) == spec_ids
        assert all(NORMATIVE_TEST_EVIDENCE[test_id] for test_id in spec_ids)

    def test_every_normative_evidence_node_exists_and_has_a_known_environment(self) -> None:
        for test_id, evidence in NORMATIVE_TEST_EVIDENCE.items():
            for item in evidence:
                assert item.environment in {PURE, HA}, (test_id, item)
                assert node_exists(item.node), (test_id, item.node)


class TestInvariantMatrix:
    def test_spec_and_matrix_have_exactly_i1_to_i37_without_duplicates(self) -> None:
        spec_ids = invariant_spec_ids()
        expected = {f"I{number}" for number in range(1, 38)}
        assert len(spec_ids) == len(set(spec_ids)) == 37
        assert set(spec_ids) == expected
        literal_keys = literal_dict_keys("INVARIANT_TRACEABILITY")
        assert len(literal_keys) == len(set(literal_keys)) == 37
        assert set(literal_keys) == expected
        assert set(INVARIANT_TRACEABILITY) == expected

    def test_every_invariant_has_components_known_ids_and_concrete_evidence(self) -> None:
        normative_ids = set(NORMATIVE_TEST_EVIDENCE)
        for invariant_id, trace in INVARIANT_TRACEABILITY.items():
            assert trace.components, invariant_id
            assert trace.normative_ids, invariant_id
            assert set(trace.normative_ids) <= normative_ids, invariant_id
            concrete = evidence_for_invariant(invariant_id)
            assert concrete, invariant_id
            assert all(node_exists(item.node) for item in concrete), invariant_id


class TestTransitionTraceability:
    def test_transition_mapping_is_exactly_t1_to_t59_and_collectable(self) -> None:
        expected = {f"T{number}" for number in range(1, 60)}
        assert set(TRANSITION_EVIDENCE) == expected
        assert all(item.environment == PURE for item in TRANSITION_EVIDENCE.values())
        assert all(node_exists(item.node) for item in TRANSITION_EVIDENCE.values())


class TestSkipAndRaceAudit:
    def test_no_xfail_and_only_the_documented_boundary_skip_exists(self) -> None:
        skip_functions: list[str] = []
        xfail_uses: list[str] = []
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                if not isinstance(function, ast.Attribute):
                    continue
                if function.attr == "xfail":
                    xfail_uses.append(f"{path.name}:{node.lineno}")
                if function.attr != "skip":
                    continue
                parent = next(
                    (
                        candidate
                        for candidate in ast.walk(tree)
                        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node in ast.walk(candidate)
                    ),
                    None,
                )
                assert parent is not None
                skip_functions.append(f"{path.name}::{parent.name}")
        assert xfail_uses == []
        assert skip_functions == [
            "test_models.py::test_importing_models_does_not_import_homeassistant"
        ]
        mapped_nodes = {
            base_node(item.node)[1][-1]
            for evidence in NORMATIVE_TEST_EVIDENCE.values()
            for item in evidence
        }
        assert "test_importing_models_does_not_import_homeassistant" not in mapped_nodes

    def test_safety_tests_use_no_behavioural_wall_clock_sleeps(self) -> None:
        violations: list[str] = []
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "sleep":
                    continue
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "asyncio"
                    and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == 0
                ):
                    continue
                violations.append(f"{path.name}:{node.lineno}")
        assert violations == []
