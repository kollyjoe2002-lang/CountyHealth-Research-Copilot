# CountyHealth Research Copilot

CountyHealth Research Copilot is a county-level public health research platform for exploring high-BMI prevalence, attributable disease burden, demographic disparities, and long-term trends across the United States.

The platform combines a large IHME-derived county data warehouse, a validated analytics engine, interactive Streamlit applications, and a planned AI research assistant capable of producing publication-ready reports.

---

## Project Architecture

```text
IHME County Data
        │
        ▼
DuckDB Warehouse
        │
        ▼
Validated Analytics Engine
        │
        ▼
County Profile
Trend Finder
Disparity Finder
        │
        ▼
AI Research Assistant
        │
        ▼
Publication-Ready Reports