"""Self-contained semantic safety tests; fixtures make no real attribution claim."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import sys
import unittest

# Support both module invocation and the repository's file-path check style.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.evidence_semantics import (
    Adjustment, AlignmentMode, Attribution, AttributionStatus, ClaimKind,
    CrossSourceSemantics, EvidenceRole, EvidenceSemantics, IHMEYLLSemantics,
    PLACESPrevalenceSemantics, ProvenanceReference, RUCCSemantics,
    SemanticsError, UncertaintyType, semantic_claim_label,
)


def ihme(**changes):
    values = dict(dataset_version="synthetic-test-import", concept="Stroke", cause_id=494,
                  population_basis="Total race; Both sexes; age 20+",
                  unit="unknown", adjustment=Adjustment.AGE_STANDARDIZED,
                  measurement_year=2019, release_year=None, uncertainty_level=None)
    return IHMEYLLSemantics(**(values | changes))


def places(**changes):
    values = dict(dataset_version="synthetic-test-release", concept="Stroke", measure_id="STROKE",
                  population_basis="County adults", unit="Percent",
                  adjustment=Adjustment.AGE_ADJUSTED, measurement_year=2019,
                  release_year=2021, uncertainty_level=0.95, carry_forward=False)
    return PLACESPrevalenceSemantics(**(values | changes))


def rucc(**changes):
    values = dict(dataset_version="synthetic-test-rucc", concept="Rurality",
                  population_basis="County geography", unit="Category",
                  adjustment=Adjustment.NOT_APPLICABLE, measurement_year=None,
                  release_year=None, uncertainty_level=None)
    return RUCCSemantics(**(values | changes))


def verified(label="High BMI", **changes):
    ref = ProvenanceReference(dataset="ihme.burden", dataset_version="synthetic-test-import",
                              reference="fixture://import-manifest", verification_note=(
                                  "SYNTHETIC TEST ATTESTATION ONLY; no real dataset verified"))
    return Attribution(status=AttributionStatus.VERIFIED, label=label,
                       provenance=(replace(ref, **changes),))


def bundle(**changes):
    values = dict(items=(ihme(), places(), rucc()), geography_basis="county FIPS",
                  alignment=AlignmentMode.SAME_YEAR, alignment_note="Explicit 2019 alignment")
    return CrossSourceSemantics(**(values | changes))


class EvidenceSemanticsChecks(unittest.TestCase):
    def test_completeness_of_source_contracts(self):
        required = {"version", "source", "dataset", "dataset_version", "measure", "metric", "concept",
                    "attribution", "population_basis", "unit", "adjustment",
                    "uncertainty_type", "uncertainty_level", "measurement_year",
                    "release_year", "provenance"}
        for evidence in (ihme(), places(), rucc()):
            self.assertTrue(required <= {f.name for f in fields(evidence)})
            for name in ("dataset", "dataset_version", "measure", "metric", "concept",
                         "population_basis", "unit"):
                self.assertTrue(getattr(evidence, name))
        for kwargs in ({"concept": ""}, {"population_basis": " "}, {"dataset_version": ""},
                       {"unit": ""}, {"unit": "Percent"}, {"adjustment": "unknown"}, {"measurement_year": True},
                       {"uncertainty_level": 95}, {"uncertainty_level": float("nan")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(SemanticsError):
                ihme(**kwargs)
        with self.assertRaises(TypeError):
            IHMEYLLSemantics(cause_id=494)
        with self.assertRaises(SemanticsError):
            EvidenceSemantics(dataset_version="test", concept="test", population_basis="test",
                              unit="unknown", adjustment=Adjustment.UNKNOWN,
                              measurement_year=None, release_year=None, uncertainty_level=None)

    def test_ihme_defaults_to_unknown_attribution_despite_ids(self):
        evidence = ihme(cause_id=976)
        self.assertIs(evidence.attribution.status, AttributionStatus.UNKNOWN)
        self.assertIsNone(evidence.attribution.label)
        self.assertEqual(evidence.attribution.provenance, ())
        self.assertNotIn("High BMI", semantic_claim_label(evidence, ClaimKind.YLL))
        self.assertIn("attribution unknown", semantic_claim_label(evidence, ClaimKind.BURDEN))

    def test_attribution_dependent_labels_fail_closed_for_every_claim_kind(self):
        for kind in ClaimKind:
            with self.subTest(kind=kind), self.assertRaises(SemanticsError):
                semantic_claim_label(ihme(), kind, required_attribution="High BMI")
        with self.assertRaises(SemanticsError):
            semantic_claim_label(ihme(), ClaimKind.ATTRIBUTED_YLL)
        with self.assertRaises(SemanticsError):
            semantic_claim_label(ihme(), "attributed_yll_rate")

    def test_attribution_cannot_be_marked_verified_without_provenance(self):
        for kwargs in (
            {"status": AttributionStatus.VERIFIED, "label": "High BMI"},
            {"status": AttributionStatus.UNKNOWN, "label": "High BMI"},
            {"status": AttributionStatus.NOT_APPLICABLE, "label": "High BMI"},
            {"status": "verified", "label": "High BMI"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(SemanticsError):
                Attribution(**kwargs)
        with self.assertRaises(SemanticsError):
            ihme(attribution=Attribution(status=AttributionStatus.NOT_APPLICABLE))

    def test_verified_attribution_requires_matching_dataset_and_version(self):
        for attribution in (verified(dataset="places.estimates"),
                            verified(dataset_version="different-import")):
            with self.assertRaises(SemanticsError):
                ihme(attribution=attribution)
        with self.assertRaises(SemanticsError):
            ihme(dataset_version="unknown", attribution=verified(dataset_version="unknown"))
        with self.assertRaises(SemanticsError):
            ihme(provenance=(verified().provenance[0].__class__(
                dataset="other", dataset_version="synthetic-test-import",
                reference="fixture://other", verification_note="Wrong dataset"),))

    def test_verified_label_does_not_authorize_stronger_or_different_attribution(self):
        evidence = ihme(attribution=verified("Synthetic risk factor"))
        label = semantic_claim_label(evidence, ClaimKind.ATTRIBUTED_YLL,
                                     required_attribution="Synthetic risk factor")
        self.assertIn("attributable to Synthetic risk factor", label)
        self.assertNotIn("High BMI", label)
        with self.assertRaises(SemanticsError):
            semantic_claim_label(evidence, ClaimKind.ATTRIBUTED_YLL, required_attribution="High BMI")

    def test_interval_types_are_source_specific_and_not_overridable(self):
        self.assertIs(ihme().uncertainty_type, UncertaintyType.IHME_UI)
        self.assertIs(places().uncertainty_type, UncertaintyType.PLACES_CI)
        self.assertIs(rucc().uncertainty_type, UncertaintyType.NONE)
        for evidence, wrong in ((ihme(), UncertaintyType.PLACES_CI),
                                (places(), UncertaintyType.IHME_UI)):
            with self.assertRaises(ValueError):
                replace(evidence, uncertainty_type=wrong)

    def test_places_cannot_be_described_as_burden_or_attributed_yll(self):
        for kind in (ClaimKind.YLL, ClaimKind.BURDEN, ClaimKind.ATTRIBUTED_YLL,
                     ClaimKind.CLASSIFICATION):
            with self.subTest(kind=kind), self.assertRaises(SemanticsError):
                semantic_claim_label(places(), kind)
        self.assertIn("modeled prevalence", semantic_claim_label(places(), ClaimKind.PREVALENCE))
        for changes in ({"unit": "YLL per 100,000"}, {"adjustment": Adjustment.AGE_SPECIFIC},
                        {"attribution": verified()}, {"measurement_year": None},
                        {"release_year": None}, {"measurement_year": 2022},
                        {"carry_forward": "false"}):
            with self.subTest(changes=changes), self.assertRaises(SemanticsError):
                places(**changes)

    def test_rucc_is_never_a_health_outcome(self):
        for kind in (ClaimKind.YLL, ClaimKind.BURDEN, ClaimKind.ATTRIBUTED_YLL,
                     ClaimKind.PREVALENCE):
            with self.subTest(kind=kind), self.assertRaises(SemanticsError):
                semantic_claim_label(rucc(), kind)
        self.assertIs(rucc().role, EvidenceRole.CLASSIFICATION)
        self.assertIn("2023 geographic classification",
                      semantic_claim_label(rucc(), ClaimKind.CLASSIFICATION))
        for changes in ({"unit": "Percent"}, {"measurement_year": 2019},
                        {"release_year": 2023}, {"uncertainty_level": 0.95},
                        {"adjustment": Adjustment.AGE_ADJUSTED}):
            with self.subTest(changes=changes), self.assertRaises(SemanticsError):
                rucc(**changes)

    def test_source_measure_metric_and_roles_cannot_be_relabelled(self):
        for evidence in (ihme(), places(), rucc()):
            for name in ("source", "dataset", "measure", "metric", "role"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    replace(evidence, **{name: "wrong"})
        with self.assertRaises(SemanticsError):
            semantic_claim_label(ihme(), ClaimKind.PREVALENCE)

    def test_contracts_and_nested_provenance_are_immutable(self):
        evidence = ihme(attribution=verified())
        with self.assertRaises(FrozenInstanceError):
            evidence.attribution.label = "different"
        with self.assertRaises(FrozenInstanceError):
            evidence.attribution.provenance[0].reference = "different"
        with self.assertRaises(FrozenInstanceError):
            evidence.unit = "Percent"
        with self.assertRaises(SemanticsError):
            ihme(provenance=[])
        with self.assertRaises(SemanticsError):
            Attribution(status=AttributionStatus.VERIFIED, label="High BMI", provenance=[])
        with self.assertRaises(SemanticsError):
            bundle(items=[ihme(), places()])

    def test_cross_source_bundle_preserves_distinct_populations_units_and_intervals(self):
        evidence = bundle()
        self.assertEqual(len(evidence.items), 3)
        self.assertEqual({x.unit for x in evidence.items}, {"unknown", "Percent", "Category"})
        self.assertEqual(len({x.population_basis for x in evidence.items}), 3)
        self.assertEqual(evidence.interpretation, "descriptive_noncausal")
        with self.assertRaises(TypeError):
            CrossSourceSemantics(items=evidence.items, geography_basis="county FIPS",
                                 alignment=AlignmentMode.SAME_YEAR, alignment_note="test",
                                 composite_metric="combined")
        # A known attribution on one item cannot authorize the unknown IHME item.
        with self.assertRaises(SemanticsError):
            semantic_claim_label(evidence.items[0], ClaimKind.ATTRIBUTED_YLL)

    def test_cross_source_pairs_exactly_allow_only_the_three_approved_mappings(self):
        for measure, cause in (("DIABETES", 976), ("STROKE", 494), ("CASTHMA", 515)):
            self.assertEqual(len(bundle(items=(ihme(cause_id=cause),
                                               places(measure_id=measure))).items), 2)
        for measure, cause in (("CANCER", 429), ("DIABETES", 494), ("STROKE", 976),
                               ("CASTHMA", 494), ("CHD", 493)):
            with self.subTest(measure=measure, cause=cause), self.assertRaises(SemanticsError):
                bundle(items=(ihme(cause_id=cause), places(measure_id=measure)))

    def test_cross_source_alignment_and_carry_forward_fail_closed(self):
        with self.assertRaises(SemanticsError):
            bundle(items=(ihme(), places(measurement_year=2018)))
        aligned = bundle(items=(ihme(), places(measurement_year=2018)),
                         alignment=AlignmentMode.CONTEXTUAL, alignment_note="2019 vs 2018")
        self.assertIs(aligned.alignment, AlignmentMode.CONTEXTUAL)
        with self.assertRaises(SemanticsError):
            bundle(alignment=AlignmentMode.CONTEXTUAL)
        with self.assertRaises(SemanticsError):
            bundle(items=(ihme(), places(carry_forward=True)))
        for items in ((ihme(), ihme()), (places(), rucc()), (ihme(),),
                      (ihme(), places(), places())):
            with self.subTest(items=items), self.assertRaises(SemanticsError):
                bundle(items=items)


if __name__ == "__main__":
    unittest.main(verbosity=2)
