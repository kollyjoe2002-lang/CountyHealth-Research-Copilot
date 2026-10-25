# CountyHealth Research Copilot

CountyHealth Research Copilot is a county-level public health research
platform for exploring county health indicators, IHME YLL evidence,
long-term trends, national county rankings, and demographic disparities
across the United States.

The project combines:

- an IHME-derived county-level data warehouse;
- DuckDB analytical infrastructure;
- validated epidemiological functions;
- deterministic natural-language research question processing;
- evidence-backed interpretation;
- research figures;
- publication-oriented evidence tables;
- Markdown and DOCX research-report export.

The system is designed around an evidence-first principle:

> Numerical results are produced by validated analytical functions and
> stored data. The research assistant does not invent epidemiological
> estimates.

---

## V1.3 development candidate

V1.3 is **not production release ready** until the actual development warehouse
and live-model regression gates pass. Sex × age, sex × rurality and age × rurality
remain PLANNED and have no public execution surface. IHME attribution, rate scale
and dataset/version remain UNKNOWN pending source/import provenance verification;
measure/metric IDs and legacy wording do not establish these semantics.

See [release-readiness assessment](docs/V1.3_Release_Readiness.md) and the
[deployment plan, not executed](docs/V1.3_Deployment_Plan.md). Earlier release
notes below are historical and do not establish current production state.

## Historical release reference

Historical development label:

```text
v0.9.0
```
