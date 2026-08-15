# Autonomous Input: what the satellite can and cannot replace

Answers to three questions, each tested against the Gangamai register rather
than argued from first principles.

> 1. We need Pol and Brix.
> 2. Can we predict the exact plantation date so there is no manual data entry?
> 3. Our system needs one coordinate, then it autonomously derives the exact
>    sugarcane plot polygon.

Short version: **(2) yes, and it is built and working. (1) yes, but only once
your own laboratory data is plugged in — no satellite substitute exists.
(3) no, not from one coordinate at your field sizes — and you already hold
something better.**

---

## First, a correction that affects everything downstream

`ml/train_high_precision_95.py` reports 94–96% R². That number is not real.

The script calls `generate_multispectral_dataset()`, which *invents* the target
from a closed-form expression of the same features it then trains on:

```python
maturity = 12.5 * sin(min(pi/2, (age/420)*(pi/2)))
canopy   = 0.88 + ndre*0.25 + ndvi*0.15
recovery = maturity * canopy * solar * ripening + N(0, 0.05)
```

The model is learning to invert its own generator through 0.05 of noise. The
high R² is arithmetic, not agronomy — it has never seen a field.

It is worse than merely uninformative. The synthetic NDVI, NDRE and NDWI are
built from **independent uniform random reflectances**, so they are mutually
uncorrelated. In real Sentinel-2 data over sugarcane those indices correlate at
roughly r = 0.85–0.95. The model has learned to lean on band relationships that
do not exist in nature, which is precisely why it will not transfer to a real
plot.

`ml/train_ccs_model.py` replaces it and **refuses to run** on that dataset.

---

## (2) Planting date — yes. Built, and verified against your data.

`ml/sentinel_phenology.py` pulls the Sentinel-2 L2A archive from AWS Earth
Search — free, anonymous, no API key, no registration — masks cloud with the
scene-classification band, and reads the canopy time series.

### A false positive, and what it taught us

An early 4-scene look at Gat 13393 (Khodwa, register date 20-12-2024) showed
NDVI falling 0.722 → 0.291 across 19–24 Dec and looked like a clean
confirmation of the register. **It was wrong.** The full 48-observation series
shows NDVI back at **0.699 ten days later**:

| 14 Dec | 19 Dec | 24 Dec | 3 Jan |
|---|---|---|---|
| 0.709 | 0.722 | **0.291** | **0.699** |

A cut field does not re-close its canopy in ten days. That was haze, not a
harvest. The real collapse on that plot is **14 Mar 2025** (0.163, held for six
weeks).

The lesson generalises: **never trust a single low reading.** The detector now
requires a drop to be sustained — the canopy median must stay below 0.45 across
the following four weeks — before it will call a harvest. Short windows
manufacture false positives; only the full series can tell haze from a cut.

### Why ratoon is the easy case — and 8 of your 11 sample plots are ratoon

A harvest is a **step change** in the canopy: 0.72 to 0.29 in five days. That is
the sharpest, most unambiguous feature in the entire time series. Since a
Khodwa ratoon begins the day the previous crop is cut, detecting the harvest
*is* detecting the ratoon start.

Plant cane is harder. Germination is a gradual ramp, so what the satellite sees
is start-of-season, which trails actual planting by a variety- and
soil-dependent germination lag.

| | Detection basis | Expected accuracy |
|---|---|---|
| Khodwa / ratoon | canopy collapse (step) | ±5–8 days |
| Suru / Adsali / plant cane | start-of-season minus germination lag | ±10–15 days |

> **These are expectations from the literature, not measurements on Gangamai
> data.** Two plots is not a validation set, and the register dates are not yet
> trustworthy enough to score against (see below). Do not quote these figures
> to the mill until they have been measured on 20–30 plots with dates you
> trust. What *has* been measured is in the next section.

±5 days is the hard floor: Sentinel-2 revisits every 5 days, so no method can
beat the sampling interval. Sentinel-1 SAR (also free, cloud-penetrating) can
tighten monsoon-season gaps.

### The germination lag must be fitted per cane type

The `calibrate` subcommand fits it against a season whose dates you trust.
On a controlled test it recovered lags of 7 d (ratoon) and 26 d (plant cane) —
and showed that **pooling the two inflates the error 5.7×**:

```
Cane type      n   median   sd
Khodwa         3        7   1.9
Suru           3       26   1.4
ALL            6       16  10.8      <- pooling throws away the accuracy
```

Run `extract` once per cane type, each with its own lag.

### What was actually measured on your two plots

**Gat 13702 (Suru, register 31-Jan-2025) — register CORROBORATED.**

Widening the cloud mask to accept water and unclassified pixels recovered three
observations that had been discarded across the planting window:

| 18 Jan | 23 Jan | 2 Feb |
|---|---|---|
| 0.238 | 0.196 | 0.172 |

Bare soil, declining — precisely what a field being prepared for planting looks
like, sitting right on the recorded date. The previous crop was cut mid-December,
residue cleared, soil bare by end of January. The imagery independently backs
the register here.

Start-of-season lands 29-Mar-2025. With the default 25-day germination lag the
estimate was 32 days late; the true planting-to-SOS interval on this plot is
**57 days**, which is agronomically sensible — sett germination alone runs
30–45 days and early Suru canopy is sparse.

> Fitting a 57-day lag to this one plot reproduces 31-Jan exactly. That is a
> perfect fit **by construction**, not a validation — one parameter fitted to
> one observation. It shows the SOS detection is internally consistent and that
> the lag is the only free parameter. It proves nothing about accuracy. Fit the
> lag on one subset of plots and test it on another.

**Gat 13393 (Khodwa, register 20-Dec-2024) — register CONTRADICTED.**

The plot carries a closed canopy (NDVI 0.70–0.84) right through February 2025,
then collapses to 0.163 in mid-March and holds there six weeks. A ratoon
initiated on 20-Dec-2024 cannot be at 0.84 in February. The previous crop stood
until March.

### The register cannot yet serve as ground truth

`Plantation Date == Harvesting Date` in **11 of 11 rows**. One event date was
copied into both columns, so the file records what happened but not *which*
thing happened.

This retracts an earlier claim in this document that the previous-year register
is ready-made calibration data. It is not. Calibration needs dates you actually
trust — field officers' own records, or a season where the two columns differ.

**But note what just happened:** the satellite corroborated one date and
contradicted the other. That is the immediately useful capability, ahead of any
planting-date prediction — it tells you *which rows of your register to trust*.
Run it across all 11 plots and you get an audit of the register itself.

### A register problem the satellite settles

`Plantation Date == Harvesting Date` in **11 of 11 rows**. The register carries
one event date, not two — somebody filled both columns from a single field.

For the 8 Khodwa rows that is coherent (ratoon starts the day of the cut). For
the 3 Suru rows it cannot be right; you do not harvest on the planting day.
The register cannot disambiguate itself. The satellite can: it shows whether
the canopy *collapsed* on that date (a harvest) or began *rising* (a planting).

**Verdict: manual planting-date entry can be retired.** Not because the date
becomes "exact", but because ±5–15 days is comfortably inside what the decision
needs — it pins the season class (Adsali / Pre-seasonal / Suru) essentially
every time, and the season class is what drives the maturity curve.

---

## (1) Pol and Brix — the satellite cannot do this alone. Your lab can.

Sucrose is **inside the stalk**. No optical or radar sensor observes it. What a
satellite observes is the canopy behaviour that *precedes* sucrose
accumulation: the growth plateau, senescence, and the drying-off signal in the
short-wave infrared during ripening.

That is a real correlation and it is worth using. It is not a measurement.

There is no Pol or Brix ground truth anywhere in this repository. The
`pred_juice_pol` column in `data/output/farmer_heteroscedastic_output.csv` is a
model *output*, not a laboratory reading.

### You are already collecting the training set

Every cart crushed at Gangamai is sampled — Brix, Pol, Fibre → CCS — keyed to a
cane slip and therefore to a Gat number. That is thousands of labelled samples
per season, already collected and already paid for.

Export it as:

```
gat_no, sample_date, brix, pol, fibre, ccs
```

join it to the phenology output, and `ml/train_ccs_model.py` will train on it.

### What that model will realistically achieve

| Samples | Expected R² | Expected RMSE |
|---|---|---|
| < 200 | unstable | do not deploy |
| 500+, one full season | 0.55–0.70 | 0.5–0.8 CCS points |
| 2000+, multi-season, multi-variety | 0.65–0.75 | 0.4–0.6 CCS points |

Good enough to **order a harvest queue**. Not good enough to **price a
consignment** — that stays with the weighbridge and the lab, and the console
says so on every docket.

Predict **Brix and purity** rather than Pol and Brix separately: purity
(Pol/Brix × 100) sits in a tight 80–88% band and is far better conditioned than
Pol alone.

### How the new trainer avoids the old trap

- **Refuses synthetic input.** Detects the generator's column signature and exits.
- **GroupKFold by village, not random k-fold.** Neighbouring plots share soil,
  weather and management; random splits leak across them and are the usual
  reason a demo model looks better than it is.
- **Always prints the trivial baseline.** If the model cannot beat "predict the
  seasonal mean" by a clear margin, it says so and tells you not to deploy it.
- **Conformal intervals** with measured empirical coverage, not a nominal claim.

---

## (3) One coordinate → exact polygon — not at your field sizes

This is the one that fails on physics rather than effort. Measured across your
eleven plots:

| | |
|---|---|
| Mean plot | 69 m across, 1.29 ac, **52 Sentinel-2 pixels** |
| Smallest (Gat 13702) | 43 m across, 0.46 ac, **19 pixels** |
| Area within one 10 m pixel of the boundary | **29% on average, 41% on the smallest** |

A ±1 pixel boundary uncertainty translates to:

| Sensor | Pixel | Smallest plot | Mean plot | Largest plot |
|---|---|---|---|---|
| **Sentinel-2** (free) | 10 m | 46% | **29%** | 15% |
| Planet Dove (paid) | 3 m | 14% | 9% | 5% |
| SkySat / Pléiades (paid) | 0.5 m | 2% | 1% | 1% |

For ≤5% area error you need roughly a **1.1–1.7 m pixel**. Sentinel-2 is off by
more than an order of magnitude. Against a registered area used for cane
payment, a 29% error is not a rounding issue — it is the entire dispute.

### You already hold something better than any satellite will give you

All 11 sample plots carry a **4- to 5-vertex boundary walked by your own survey
team** in the `Plot Area Lat Long` column. That is a ground survey. Its accuracy
is metres, not tens of metres. Replacing it with a 10 m spectral guess would
make your data materially worse.

Until the last change, the console was ignoring that column and drawing a
synthetic rectangle over it. That is now fixed — the walked boundary is used
verbatim.

### The right source hierarchy

1. **Walked survey boundary** — you have it for these plots. Best available.
2. **Maharashtra cadastral** (Bhu-Naksha / AgriStack farmer registry), keyed by
   **Gat number, which you already hold**. A legal parcel boundary, free and
   official — the correct fallback for plots with no walked trace. This, not a
   coordinate, is the real answer to "no manual entry".
3. **Sub-metre tasked imagery** (SkySat, Pléiades) — only if 1 and 2 are
   unavailable and the parcel is disputed. Paid, per-scene.
4. **Sentinel-2 segmentation from a seed coordinate** — will not meet a payment
   standard at 0.5–4 ac. Use it only for coarse triage.

### What Sentinel-2 *can* do inside the boundary — and this is worth having

Boundary delineation is an **edge** measurement, which is exactly where 10 m
data is weakest. Net cane extent is an **interior** measurement, which is where
it is strong.

Given the walked polygon, Sentinel-2 reliably identifies which parts of the
parcel are actually under cane versus bund, cart track, gap or a failed patch —
so **net cane acreage** stops being `gross − a fixed deduction`. That is real
money, it works at your field sizes, and the eroded-core sampling in
`sentinel_phenology.py` is already the mechanism for it.

---

## Where this leaves the pipeline

| Value | Source today | Tier | Path to upgrade |
|---|---|---|---|
| Field boundary | walked survey | **Measured** | already correct; cadastral for gaps |
| Net cane acreage | boundary geometry | **Derived** | Sentinel-2 interior cane mask |
| Planting date | **Sentinel-2 phenology** | **Measured** | calibrate lag per cane type |
| Harvest / ratoon date | **Sentinel-2 phenology** | **Measured** | Sentinel-1 for monsoon gaps |
| Crop age | detected planting date | **Derived** | — |
| CCS / Pol / Brix | variety maturity curve | **Modelled** | **export mill lab data** |
| Cane tonnage | variety base rate | **Modelled** | weighbridge tickets by Gat |
| Soil moisture | none | **Unverified** | Sentinel-2 NDWI (in the extractor) |

Two of the three asks land. The third already has a better answer than the one
being asked for.

---

## Running it

```bash
pip install rasterio requests scipy numpy pandas scikit-learn

# Detect planting and harvest dates from the canopy time series
python ml/sentinel_phenology.py extract \
    --input data/sample/farmer_sample_input.csv \
    --output data/output/phenology.csv \
    --series-output data/output/phenology_series.csv \
    --season-start 2024-10-01 --season-end 2025-10-31

# Fit the germination lag against dates you already trust
python ml/sentinel_phenology.py calibrate --phenology data/output/phenology.csv

# Once the lab export exists
python ml/train_ccs_model.py --lab lab_results.csv \
    --phenology data/output/phenology.csv --target ccs
```

Runtime is roughly 7 s per scene per plot against S3, so a 12-month window is
about 9 minutes per plot. Plots in one village share scenes and tiles, so
batching the read per scene rather than per plot is the obvious next
optimisation.
