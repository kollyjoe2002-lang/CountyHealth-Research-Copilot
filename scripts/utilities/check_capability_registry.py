"""Warehouse/API-independent capability inventory and compatibility gate."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

# Support both module invocation and the repository's file-path check style.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.capabilities import (
    APPROVED_PLACES_IHME_PAIRS, ASSISTANT_FUNCTIONS, CAPABILITIES,
    CATALOG_FUNCTIONS, DIMENSION_RULES, EXECUTOR_TRANSFORMS, RESOLUTION_OPERATIONS,
    REGISTRY_VERSION, SOURCE_RESTRICTIONS,
    CapabilityState, Source, Surface, ValidationStatus, executable_capabilities,
)

ROOT = Path(__file__).resolve().parents[2]


def literal_assignment(path: str, name: str):
    tree = ast.parse((ROOT / path).read_text())
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Missing literal legacy constant: {name}")


class CapabilityRegistryChecks(unittest.TestCase):
    def test_version_and_complete_metadata(self):
        self.assertTrue(REGISTRY_VERSION.startswith("1.3."))
        for key, cap in CAPABILITIES.items():
            self.assertEqual(key, cap.key)
            self.assertTrue(cap.operation)
            self.assertTrue(cap.restrictions or cap.sources)
            self.assertTrue(cap.validators)
            for validator in cap.validators:
                self.assertTrue((ROOT / "scripts/utilities" / f"{validator}.py").is_file(), validator)
        self.assertEqual({s.source for s in SOURCE_RESTRICTIONS}, set(Source))

    def test_all_existing_data_apis_inventoried(self):
        tree = ast.parse((ROOT / "app/data_access.py").read_text())
        public_gets = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)
                       and n.name.startswith("get_")}
        inventoried = {fn for c in executable_capabilities() for fn in c.functions}
        self.assertFalse(inventoried & set(CATALOG_FUNCTIONS))
        self.assertEqual(public_gets, inventoried | set(CATALOG_FUNCTIONS))
        self.assertEqual(sum(len(c.functions) for c in executable_capabilities()), len(inventoried))

    def test_assistant_surface_exactly_matches_executor_allowlist(self):
        tree = ast.parse((ROOT / "ai/executor.py").read_text())
        node = next(n for n in tree.body if isinstance(n, ast.AnnAssign)
                    and isinstance(n.target, ast.Name) and n.target.id == "APPROVED_FUNCTIONS")
        approved = {ast.literal_eval(k) for k in node.value.keys}
        listed = {fn for c in executable_capabilities(Surface.ASSISTANT) for fn in c.functions}
        self.assertEqual(approved, listed)
        self.assertEqual(approved, ASSISTANT_FUNCTIONS)
        self.assertNotIn("get_places_ihme_positive_deviance", listed)

    def test_legacy_executable_is_not_a_fresh_validation_claim(self):
        for cap in executable_capabilities():
            self.assertIs(cap.state, CapabilityState.LEGACY_EXECUTABLE)
            self.assertIs(cap.validation, ValidationStatus.LEGACY_RECORDED)
            self.assertTrue(cap.functions)
            self.assertIn(Surface.DATA_API, cap.surfaces)

    def test_multidimensional_capabilities_stay_disabled(self):
        planned = {c.key for c in CAPABILITIES.values() if c.state is CapabilityState.PLANNED}
        self.assertEqual(planned, {"sex_age", "sex_rurality", "age_rurality"})
        for key in planned:
            cap = CAPABILITIES[key]
            self.assertFalse(cap.executable)
            self.assertEqual(cap.functions, ())
            self.assertEqual(cap.surfaces, ())
            self.assertIs(cap.validation, ValidationStatus.PENDING)

    def test_unsupported_cannot_be_executable(self):
        expected = {"forecast", "causal_inference", "hypothesis_testing",
                    "arbitrary_demographic_intersections", "composite_cross_source_metric",
                    "places_demographic_subgroups", "unapproved_concept_pairs",
                    "aggregate_long_term_change"}
        actual = {c.key for c in CAPABILITIES.values() if c.state is CapabilityState.UNSUPPORTED}
        self.assertEqual(actual, expected)
        for key in expected:
            self.assertFalse(CAPABILITIES[key].executable)
            self.assertFalse(CAPABILITIES[key].functions)
            self.assertFalse(CAPABILITIES[key].surfaces)
            self.assertIs(CAPABILITIES[key].validation, ValidationStatus.NOT_SUPPORTED)

    def test_approved_pairs_exact_and_legacy_constant_unchanged(self):
        expected = {"DIABETES": {976}, "STROKE": {494}, "CASTHMA": {515}}
        self.assertEqual(dict(APPROVED_PLACES_IHME_PAIRS), expected)
        legacy = literal_assignment("ai/resolver.py", "PLACES_IHME_ALLOWED_PAIRS")
        self.assertEqual(legacy, expected)
        self.assertIs(type(legacy), dict)
        self.assertTrue(all(type(ids) is set for ids in legacy.values()))
        self.assertNotIn("CANCER", APPROVED_PLACES_IHME_PAIRS)
        for cap in executable_capabilities():
            self.assertEqual(cap.approved_pair_policy,
                             Source.PLACES in cap.sources and Source.IHME in cap.sources)

    def test_legacy_dimension_defaults_exact(self):
        legacy = literal_assignment("app/data_access.py", "DISPARITY_DIMENSIONS")
        current = {r.name: {"id_column": r.id_column, "name_column": r.name_column,
                            "fixed_filters": dict(r.fixed_filters)} for r in DIMENSION_RULES}
        self.assertEqual(current, legacy)
        self.assertEqual(len(current), 3)

    def test_planner_operations_and_executor_transforms_are_inventoried(self):
        tree = ast.parse((ROOT / "ai/planner.py").read_text())
        known = {fn: c.operation for c in executable_capabilities() for fn in c.functions}
        transforms = {t.function_name: t.operation for t in EXECUTOR_TRANSFORMS}
        for call in ast.walk(tree):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "AnalysisStep"):
                continue
            step = {k.arg: ast.literal_eval(k.value) for k in call.keywords
                    if k.arg in {"operation", "function_name"}}
            if step["operation"] in RESOLUTION_OPERATIONS:
                self.assertIn(step["function_name"], CATALOG_FUNCTIONS)
            elif step["function_name"] == "aggregate_long_term_change":
                self.assertFalse(CAPABILITIES["aggregate_long_term_change"].executable)
            else:
                self.assertEqual(step["operation"],
                                 (known | transforms)[step["function_name"]])
        self.assertEqual(set(RESOLUTION_OPERATIONS),
                         literal_assignment("ai/executor.py", "NON_EXECUTABLE_OPERATIONS"))
        executor = ast.parse((ROOT / "ai/executor.py").read_text())
        implementations = {n.name for n in executor.body if isinstance(n, ast.FunctionDef)}
        self.assertTrue({t.implementation for t in EXECUTOR_TRANSFORMS} <= implementations)

    def test_deeply_immutable_inventory(self):
        with self.assertRaises(TypeError):
            CAPABILITIES["forecast"] = CAPABILITIES["sex_age"]
        with self.assertRaises(FrozenInstanceError):
            CAPABILITIES["sex_age"].state = CapabilityState.LEGACY_EXECUTABLE
        with self.assertRaises(TypeError):
            APPROVED_PLACES_IHME_PAIRS["CANCER"] = frozenset({1})
        with self.assertRaises(AttributeError):
            APPROVED_PLACES_IHME_PAIRS["STROKE"].add(1)
        for cap in CAPABILITIES.values():
            for name in ("functions", "sources", "surfaces", "comparison_dimensions",
                         "geography_modes", "restrictions", "validators", "fixed_filters"):
                self.assertIsInstance(getattr(cap, name), tuple)

    def test_passive_import_has_no_runtime_dependencies(self):
        for path in ("ai/capabilities.py", "ai/evidence_semantics.py"):
            tree = ast.parse((ROOT / path).read_text())
            imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
            imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            self.assertFalse(imports & {"app.data_access", "duckdb", "streamlit", "openai",
                                        "ai.resolver", "ai.executor", "ai.planner"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
