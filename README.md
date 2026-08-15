# IkshuVruddhi — Gangamai Sugar Mill Harvest Console

Harvest sequencing and cane-quality planning for Gangamai Sahakari Sakhar
Karkhana (Shevgaon / Ahilyanagar, Maharashtra).

The console reads the mill's existing harvest register, works out which plots
are losing the most sucrose to standing, and sequences them against daily
crushing capacity. **Every value it shows carries a tag saying where it came
from** — see [CAPABILITIES.md](CAPABILITIES.md) for what is and is not claimed.

---

## Source tags

| Tag | Meaning |
|---|---|
| `M` Measured | Read directly from the uploaded register |
| `D` Derived | Arithmetic or geometry on measured inputs — no model error |
| `X` Modelled | Variety maturity-curve estimate, carries a stated margin |
| `?` Unverified | No input existed; planning placeholder, not valid for payment |

A plot's **record confidence** is the weighted mix of these across the fields
that drive money — boundary, area, planting date and CCS. Below 65% the
harvest docket prints *PLANNING ONLY — NOT VALID FOR PAYMENT*.

---

## Running it

```bash
python -m http.server 8123 --directory web
```

Then open <http://localhost:8123> and upload the season register CSV.

Column names are matched loosely (exact, then normalised, then prefix), so the
factory's own headers work unchanged — including the unbalanced
`Area (Hectare` header in the sample file. Hectares are detected from the
header and converted at 2.4711 ac/ha.

Recognised columns: `Plot No` / `Gut`, `Farmer`, `Village`, `Variety Name`,
`Cane Type`, `Plantation Date`, `Area (Hectare)`, `Lat 1` / `Long 1`,
`Plot Area Lat Long`, plus optional `Contact`, lab `CCS` / `Pol` / `Brix`,
`NDWI` / `LSWI` / `CWSI`, and `Yield`.

---

## What it does

- **Harvest queue** — plots ranked by sucrose lost to standing, sortable on any
  column, filterable by readiness, record state and circle.
- **Harvest program** — plots packed against daily crush capacity (MT/day) over
  a chosen horizon, with per-day tonnage, tonnage-weighted CCS and an explicit
  flag when one field pushes a day over capacity. Exports as a dispatch CSV.
- **Planning date** — set any date; crop ages, harvest windows and queue order
  all recompute against it.
- **Area reconciliation** — geodesic area from the walked boundary, compared
  against the registered hectarage, flagged past 12% divergence.
- **Data quality panel** — the source mix across every field, plus a
  field-verification worklist export sized for staffing.
- **Plot detail** — sucrose trajectory anchored to the real planting date, and
  a line-by-line account of which column each number came from.
- **Harvest docket** — printable, with source tags and a payment-validity stamp.

---

## Project layout

```
web/          Console — index.html, app.js, styles.css (no build step)
ml/           Python training and prediction scripts
models/       Pre-trained .pkl binaries
data/         Sample registers and prediction outputs
backend_main.py   FastAPI service
```

---

## Not connected in this build

No satellite, SAR, weather or laboratory feed is wired in. Soil moisture and
the within-field zone overlay are placeholders and are labelled as such
throughout the UI and on the printed docket. Cane weight and CCS for payment
come from the factory weighbridge and laboratory only.
