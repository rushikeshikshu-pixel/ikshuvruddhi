# What IkshuVruddhi Actually Delivers

A capability statement for Gangamai Sugar Mill. Written so that every line
survives a question from the Chief Chemist, the CAO, or an auditor.

---

## Why the original pitch does not survive contact

The earlier version of this pitch read:

> The mill only needs the farmer's name and a rough village. From that single
> reference the AI autonomously computes the exact boundary polygon, exact
> planting date, net acreage, SAR radar yield, Brix/Pol/CCS, peak harvest
> window and a quad-zone stress map.

Three problems, in rising order of seriousness:

1. **The word "exact" cannot be earned from that input.** A name and a village
   do not identify a parcel. Ghotan alone has multiple growers with the same
   surname and several plots each — the sample dataset has one farmer holding
   four separate Gats. Nothing downstream can be exact if the parcel itself is
   a guess.
2. **The claims are unfalsifiable as written.** "Exact planting date" invites a
   single counter-example to discredit the whole platform. One farmer saying
   "no, I planted in the second week" ends the conversation.
3. **It promises feeds that are not connected.** There is no SAR ingestion, no
   optical tasking and no lab link in this build. Brix and Pol are not measured
   anywhere in the system; they are inferred from an assumed CCS.

A mill buys this to decide *what to cut this week*. Over-claiming on inputs is
the fastest way to lose that decision the first time a number is wrong.

---

## The honest input requirement

The mill does not need to collect anything new. It needs to hand over the
harvest register it already keeps. From the sample file, that is:

| Column | Used for | If missing |
|---|---|---|
| `Plot No` / `Gut` | Parcel identity | Row is unusable as a payment record |
| `Farmer` | Slip addressing | Slip cannot be dispatched |
| `Plot Area Lat Long` | Net acreage, field map | Falls back to a placeholder square, flagged |
| `Lat 1` / `Long 1` | Map position | Falls back to the boundary centroid |
| `Plantation Date` | Crop age, harvest window | Whole ripening model becomes unreliable, flagged |
| `Area (Hectare)` | Cross-check against the walked boundary | No discrepancy check possible |
| `Variety Name` | Maturity curve, CCS band, yield base | Falls back to a generic mid-late profile |
| `Cane Type` | Ratoon yield and sucrose penalty | Inferred from crop age |
| **Contact number** | **Slip dispatch — currently absent from the register** | **Slip cannot reach the farmer** |

That last row is the one operational gap worth fixing at the gate. The sample
register has no phone column at all, so 11 of 11 plots cannot receive a slip.

---

## What the platform computes, by confidence tier

Every value in the console and in every export carries one of four tags. This
is the core of the product, not a disclaimer bolted on.

### `M` Measured — read from the register
- **Field boundary.** The multi-vertex trace the survey team already walked.
  In the sample data these are 4- and 5-vertex parcels; the console uses them
  verbatim rather than drawing a rectangle over them.
- **Planting date and crop age.**
- **GPS position.**
- **Lab CCS, Pol, Brix** — whenever a lab column is present. It always
  overrides the model.

### `D` Derived — arithmetic on measured inputs, no model error
- **Net cane acreage**, by geodesic shoelace area on the boundary trace.
- **Area discrepancy** against the registered hectarage. In the sample data
  five of eleven plots disagree by more than 12%, one by +112%. Each is a real
  payment exposure that was previously invisible.
- **CCS from Pol and Brix**, where both are recorded.
- **Optimal cut date and harvest window**, from planting date and the variety's
  maturity curve.

### `X` Modelled — an estimate with a stated margin
- **CCS %**, from a sucrose-accumulation curve anchored to the variety's
  published maturity window and the plot's real planting date. Rises through
  grand growth, plateaus at maturity, declines as the cane over-stands.
  Carries ±0.62 points. It is a sequencing aid, **not** a payment figure.
- **Cane tonnage**, from the variety's base rate scaled by crop age, with a
  ratoon penalty. Not a weighbridge number and never presented as one.
- **Sucrose lost to standing** — the 30-day CCS delta that drives the queue
  order. This is the number that actually earns the mill money, and it comes
  from the ratio of two model points, so it is far more robust than either
  point alone.

### `?` Unverified — no input existed
- **Soil moisture and within-field zones.** No satellite, SAR or weather feed
  is connected. These render so the map is legible and are labelled, in the
  UI and on the docket, as unusable for irrigation or input planning.

---

## What the mill gets that it did not have

1. **A ranked harvest queue.** Plots ordered by sucrose being lost to standing,
   not by CCS alone. In the sample register every plot is 120–200 days past its
   optimal cut date — visible in one screen, previously not visible at all.
2. **A dispatch program.** Plots packed against real daily crushing capacity
   over a chosen horizon, with per-day tonnage, weighted CCS, and an explicit
   flag when a single field pushes a day over capacity.
3. **An area-discrepancy list.** Every plot where the walked boundary disagrees
   with the registered hectarage, exported as a reconciliation worklist.
4. **A field-verification worklist.** Exactly which plots need a GPS capture, a
   boundary walk, a planting-date confirmation or a phone number — sized, so
   the CAO can staff it.
5. **A docket that refuses to lie.** Below 65% record confidence it prints
   *PLANNING ONLY — NOT VALID FOR PAYMENT* with the specific gaps listed.
6. **A forward planning date.** Move the planning date to any future date and
   every crop age, window and queue position recomputes — "what is ready on
   15 December" is one control, not a spreadsheet exercise.

---

## What would move values up a tier

Stated plainly, because this is the upgrade path and the mill should be able
to price it:

| To upgrade | Requires | Moves |
|---|---|---|
| CCS from `X` to `M` | Lab juice analysis linked by Gat number | The single highest-value change; makes the queue authoritative |
| Tonnage from `X` to `M` | Weighbridge tickets fed back by Gat | Closes the loop and calibrates the yield model season over season |
| Moisture / zones from `?` to `D` | Sentinel-2 NDWI ingestion (free, ~5-day revisit) | Makes irrigation advice real |
| Tonnage from `X` to `D` | Sentinel-1 SAR backscatter ingestion (free) | The actual basis for the "SAR radar yield" claim |
| Boundary from `?` to `M` on gap plots | One field visit per flagged plot | Removes the payment exposure on those parcels |

None of these are speculative — all four feeds are ordinary integrations. The
difference is that the console will report honestly before they are connected,
and the tier labels will change on their own once they are.

---

## The claim to make instead

> Give us the harvest register you already keep. We will tell you which plots
> are losing sucrose fastest, sequence them against your daily crush, and mark
> every figure with where it came from — so the numbers you pay on are measured
> and the numbers you plan on are labelled as estimates.
