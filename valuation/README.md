# Valuation utility — used-vs-new pricing indicators

Determines whether a used-vehicle listing is priced fairly, from two angles:

- **View 1 — new-equivalent discount:** how much cheaper the listing is than a
  comparable *new* vehicle. Useful context, but every used car is cheaper than
  new, so this alone does not say whether the used price is good.
- **View 2 — used-market fair value:** whether the listing is cheap or
  expensive versus *other used cars* of the same model/trim, adjusted for
  mileage. This is the deal-quality answer — "does the price make sense for the
  miles on it?" — and is estimated leave-one-out so a car is never compared
  against itself.

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full design and roadmap.

## Where this fits in `vehicle-hunting`

This folder was migrated wholesale from a formerly separate workspace
(`car-shopping-indicators`), which is being retired. It's a standalone data
utility, not part of the published `vehicle-hunting` website: the site
(`index.html`, `app.js`, `data/vehicles.json`, the root `vehicle-profile/`)
covers new-vehicle trim/feature comparisons only, while everything in this
folder is about pricing *used* listings against new-inventory benchmarks. The
two don't share code or data files — this is kept alongside the site because
it's the same overall car-shopping project, not because the site depends on
it. Nothing here is wired into the website; there's no plan to publish these
indicators on the live site, this is a personal research/spreadsheet tool.

## Structure

```
valuation/
  README.md               This file
  PROJECT_PLAN.md          Full design and roadmap
  data/
    new/                     One CSV per model — new-inventory benchmark prices
      toyota_corolla.csv
      toyota_corolla_cross.csv
      toyota_corolla_hatchback.csv
      toyota_4runner.csv
      toyota_prius.csv
      toyota_rav4.csv
      toyota_highlander.csv
      toyota_camry.csv
    used/                    Used-vehicle listings to be evaluated, one CSV per make+model
      toyota_corolla.csv
      toyota_camry.csv
      toyota_rav4.csv
      toyota_prius.csv
      toyota_crown.csv
      toyota_highlander.csv
      toyota_tacoma.csv
      toyota_tundra.csv
      toyota_4runner.csv
      honda_accord.csv
      honda_civic.csv
      honda_cr-v.csv
      honda_hr-v.csv
      honda_odyssey.csv
      honda_ridgeline.csv
    trim_equivalence.csv     Optional manual mapping for trims with no exact match
  scripts/
    valuation.py                  Computes the benchmarks and discount metrics,
                                   writes them back into data/used/*.csv
    regroup_used_by_model.py      One-time migration script (see below) — not part of the normal workflow
  valuation_summary.xlsx    Exported snapshot of the last computed results
```

## Data notes

- All "new" rows come from one dealership's "Today's Price," which already
  includes the $225 documentation fee and any displayed dealer adjustment.
- Mileage on new vehicles is not applicable (`0`).
- `status` (`available`, `sale_pending`, `in_transit`, `in_production`) is kept
  as its own column rather than dropped, so you can filter it out of the
  benchmark later if pending/in-production units turn out to price differently
  than on-lot stock.
- **Known limitation:** `drivetrain` and `powertrain` are marked `Unspecified`
  for most rows because the source listings didn't state them (e.g. RAV4
  "XLE Premium" doesn't say gas vs. hybrid, FWD vs. AWD). The `comparable_key`
  is therefore `Make|Model|Trim` only, not the full `Make|Model|Trim|
  Drivetrain|Powertrain` key from the original design. If you get
  drivetrain/powertrain for these listings later, add the columns and update
  `comparable_key` to sharpen the matches — a RAV4 XLE Premium Hybrid and a
  gas RAV4 XLE Premium are not really the same car.
- Prius is marked `Hybrid` (true for every trim of that model). Highlander
  Hybrid XLE is marked `Hybrid` because it's stated in the trim name.
- Used-vehicle CSVs carry two extra columns beyond the shared schema:
  `retail` (which retailer sold it — `Enterprise`, `Avis`, `Hertz`, etc.,
  a short code, distinct from the full-text `source` column) and `notes`
  (free text — e.g. why a trim reads `Unspecified`, or a callout that a
  trim is a near-miss against the new-inventory benchmark).
- `doc_fee_included` / `dealer_adjustment_included` are `Unknown` on used
  listings — unlike the new-inventory dealership, these retailers didn't
  state whether fees are baked into the listed price.
- Not every used listing has a match in `data/new/`. There is currently no
  new-inventory benchmark for Crown, Tacoma, Tundra, or any Honda model.
  Camry has SE and XSE benchmarks, while Highlander has only `Hybrid XLE`.
  Unmatched rows return `No comparable found` / `Manual review`.

## How the valuation works (`scripts/valuation.py`)

For each used listing, the script finds new listings with the same normalized
`model` and `trim`, then computes the indicators below. Matching is performed
directly from those two columns. The older `comparable_key` CSV column is kept
for compatibility but is not used by the matching logic.

| Column | Formula |
|---|---|
| `comparable_price_min/mean/median` | min/mean/median new price for that key |
| `raw_discount` | `comparable_price_median - price` |
| `discount_pct` | `raw_discount / comparable_price_median * 100` — a plain percent number (`18.1` means 18.1% cheaper than new), not a fraction |
| `mileage_adjusted_discount_per_10k` | `discount_pct / (mileage / 10000)` — how much discount % you're getting per 10,000 miles already on the odometer, also a plain percent number |
| `adjusted_value_score` | `raw_discount - model_year_penalty - rental_risk_penalty - maintenance_reserve + warranty_value_diff` (dollars; computed internally but not currently written back — see below) |
| `confidence` | `Exact match (high confidence)` (≥3 new comps), `Exact match (low sample)` (1–2), `Trim-adjusted`, or `No comparable found` |
| `value_label` | `Strong Value` (≥15% discount), `Good Value` (8–15%), `Fair Value` (0–8%), `Weak Value` (<0%), or `Manual review` (no comparable) — the "good buy vs. avoid" indicator |

The median is used as the primary benchmark (per the original design) since
one unusually optioned or discounted new listing can distort a mean.

### Indicator definitions

#### `raw_discount`

The dollar difference between the median new-vehicle price and the used
listing price:

```text
raw_discount = comparable_price_median - used_price
```

A positive number means the used vehicle is cheaper than the new benchmark.
A negative number means the used vehicle costs more. This is a
**new-versus-used price gap**, not proof that the vehicle is below its actual
used-market value. The gap also contains the effects of age, mileage,
condition, history, warranty, and market differences.

#### `discount_pct`

The same price gap expressed as a percentage of the median new price:

```text
discount_pct = raw_discount / comparable_price_median * 100
```

It makes vehicles at different price levels easier to compare. The CSV stores
a plain percent number: `16.8` means 16.8%, not `0.168`.

This is the only numeric indicator currently used to assign `value_label` and
the corresponding value color:

- `Strong Value`: 15% or more
- `Good Value`: at least 8% but less than 15%
- `Fair Value`: at least 0% but less than 8%
- `Weak Value`: below 0%
- `Manual review`: no matching benchmark

`raw_discount` and `mileage_adjusted_discount_per_10k` do not change the
label or color.

#### `mileage_adjusted_discount_per_10k`

The discount percentage divided by the vehicle's mileage in units of 10,000
miles:

```text
mileage_adjusted_discount_per_10k = discount_pct / (mileage / 10000)
```

Its unit is **discount percentage points per 10,000 miles**. A larger number
means the listing provides more new-price discount relative to the mileage
already accumulated.

This is a ranking heuristic, not an estimate of mileage depreciation. It
assumes the discount can be spread linearly across mileage, even though real
depreciation is not linear and age, condition, history, and warranty also
affect price. It can be unstable for very low-mileage vehicles and should not
be used alone to decide whether a vehicle is a good buy.

#### Worked example

For a used Corolla priced at `$20,298`, with `34,891` miles, against a median
new Corolla price of `$24,392`:

```text
raw_discount = 24,392 - 20,298 = 4,094 dollars
discount_pct = 4,094 / 24,392 * 100 = 16.8%
mileage_adjusted_discount_per_10k = 16.8 / (34,891 / 10,000) = 4.81
```

The current rules label it `Strong Value` because `discount_pct` is at least
15%. The `4.81` mileage-adjusted result is informational and does not cause
the `Strong Value` label.

Note that View 2 (below) reaches a very different verdict on this same car:
against other used Corollas it is only ~2.5% under the expected used price, so
its `price_label` is `Fair Value`, not `Strong Value`. The 15%-off-new figure
was mostly depreciation, not a bargain — which is exactly why View 2 exists.

### View 2 indicators (used-market fair value)

For each used listing, the script also estimates what comparable *used* cars of
the **same make + model + trim** sell for, adjusted for mileage, and compares
the listing to that. The comparable set is **leave-one-out** (the listing is
excluded from its own benchmark) so an underpriced car cannot drag its own
target down and hide the deal.

| Column | Meaning |
|---|---|
| `used_comp_count` | how many other same-make/model/trim used listings fed the estimate |
| `expected_used_price` | estimated fair used-market price at this listing's mileage |
| `expected_price_low` / `expected_price_high` | robust range around the estimate (from comparable disagreement, ~1.48×MAD) |
| `market_discount` | `expected_used_price - price` (positive = listing is below the used market) |
| `market_discount_pct` | `market_discount / expected_used_price * 100` |
| `market_confidence` | `High` / `Medium` / `Low` / `Manual review` (see below) |
| `price_label` | `Strong Value` (≥8%), `Good Value` (4–8%), `Fair Value` (−4–4%), `Overpriced` (<−4%), or `Manual review` |

The used-market thresholds are **tighter** than View 1's (8% vs. 15% for
`Strong Value`) because used-car spreads within one model are far narrower than
the new-vs-used gap.

**How the estimate is made (degrades gracefully with little data):**

- **≥4 comparables with real mileage spread (≥8,000 mi):** fit a robust
  Theil–Sen line of price vs. mileage (median of pairwise slopes, resistant to
  outliers) and predict at this listing's mileage. The prediction is clamped to
  the mileage range the comparables actually cover — it never extrapolates. The
  fitted slope is used only if it is negative (price falling with mileage);
  otherwise it falls back to the median.
- **A few comparables but no usable spread:** use the leave-one-out **median**
  price, with no mileage adjustment (never top `High` confidence).
- **1–2 comparables:** `Low` confidence.
- **0 comparables, or an `Unspecified` trim:** `Manual review` — no price is
  invented.

**Confidence** reflects the quality of the comparison, not just row count:
`High` needs ≥5 comparables, a real mileage fit, and a narrow spread (≤6% of
the expected price); a wide spread downgrades it to `Medium`. At the current
data size only Corolla and Camry reach `High`; most models sit at `Low` or
`Manual review`, which is the honest result until more used comparables are
collected.

#### Known reliability gap: `Low`-confidence labels with a mismatched comp

**`price_label` can read as a confident verdict even when it is not — always
check `market_confidence` alongside it, don't read `price_label` alone.**

Worked example from this dataset, `data/used/honda_cr-v.csv`, row `HZ-006`: a
**2020 CR-V EX-L, 107,228 miles, $20,501**, labeled `Strong Value` (35.1%
"discount"). Its only comparable is `AVIS-010`, a **2025 CR-V EX-L, 27,291
miles, $31,579** — one comp, 80,000 miles and 5 model years apart. With only 1
comparable, the mileage-curve fit never engages (it needs ≥4), so the estimate
falls back to the plain median of the one other price: the model effectively
assumed a 107k-mile 2020 car should sell for the same as a 27k-mile 2025 car.
The resulting "35.1% discount" is mostly the 2020-vs-2025 price gap, not a real
used-market bargain.

`market_confidence = Low` is correctly flagging this — that part of the system
is working as designed. The gap is that `price_label` still emits a specific,
confident-sounding word (`Strong Value`) instead of something that visually
signals "not enough comparable data to say." At 1–2 comparables the estimator
also does not check whether the comparable's mileage/year is even close to the
target's before using it, so a wildly mismatched single comp is treated the
same as a well-matched one.

**Rule of thumb:** trust `price_label` at `High` confidence, treat it as a
loose hint at `Medium`, and at `Low` confidence (especially 1–2 comparables)
verify manually — check the comparable's own year and mileage before believing
the label at all.

### Reliability and limitations

These indicators are useful as a **first-pass screening tool**, especially
when the model and trim are exact and several new benchmarks are available.
They are not a complete used-car appraisal and should not be the sole reason
to buy a vehicle.

Important limitations:

- The benchmark is a new-car asking price, not the local market value of an
  equivalent used vehicle.
- Exact matching currently uses model and trim only. It does not require the
  same model year, generation, drivetrain, powertrain, options, or location.
- The mileage indicator assumes linear depreciation and does not estimate a
  dollar-per-mile effect from actual used-car transactions.
- Used prices may exclude documentation fees or mandatory add-ons while the
  new benchmark includes them. Compare out-the-door prices when possible.
- Accident history, title status, rental use, number of owners, maintenance,
  tires, brakes, condition, warranty, and needed repairs are not automatically
  included.
- `confidence` measures only the number of new benchmark listings. It does not
  mean the used vehicle's condition or history has been verified.

Treat `Strong Value` and `Good Value` as signals to investigate a listing, not
as guarantees that the vehicle is mechanically sound or fairly priced.

### Where the results show up

Every time you run the script, it writes both the View 1 indicator columns
(`comparable_price_median`, `raw_discount`, `discount_pct`,
`mileage_adjusted_discount_per_10k`, `confidence`, `value_label`) and the
View 2 columns (`used_comp_count`, `expected_used_price`, `expected_price_low`,
`expected_price_high`, `market_discount`, `market_discount_pct`,
`market_confidence`, `price_label`) directly back into each `data/used/*.csv`
file, appended onto every row of the file it came from. Open e.g.
`toyota_corolla.csv` directly and the call is right there — no separate output
file to cross-reference. Re-running the script recomputes and overwrites these
columns cleanly; it doesn't duplicate them or accumulate stale values (the
loader strips them before recomputing).

If a `data/used/*.csv` file is open in another program (e.g. Excel) it is
locked for writing; the script prints a `SKIPPED ... file is locked` line for
that file and updates the rest rather than aborting. Close the file and re-run
to update it.

`adjusted_value_score` and the manual-adjustment inputs it depends on
(`model_year_penalty`, etc.) are computed in memory but not written back —
they only matter once you've actually added those manual-input columns to
a used-vehicle CSV yourself (see below).

### Manual-adjustment inputs

`model_year_penalty`, `rental_risk_penalty`, `maintenance_reserve`, and
`warranty_value_diff` are things a formula can't reliably determine — condition,
accident/rental history, tires/brakes, remaining warranty. Add them as columns
on your used-vehicle CSV; any that are missing default to `0`. This keeps the
system "semi-automated": the script computes what's derivable from price and
mileage, and leaves everything else as an explicit, visible input rather than
guessing.

### Trim-equivalence fallback

If a used trim has no exact match in `data/new/*.csv` (e.g. comparing a 2025
TRD Off-Road against only 2026 TRD Off-Road Premium listings), add a row to
`data/trim_equivalence.csv`:

```csv
model,used_trim,comparable_trim,trim_adjustment
4Runner,TRD Off-Road,TRD Off-Road Premium,-5500
```

`trim_adjustment` is added to the comparable new price (usually negative,
since the mapped new trim usually carries extra equipment the used trim
lacks). Rows resolved this way get `confidence = Trim-adjusted`.

## Running it

From inside this `valuation/` folder:

```bash
python scripts/valuation.py
```

(`ROOT` in the script resolves relative to its own file location, so this
works regardless of where the `valuation/` folder itself lives.)

1. Add used-vehicle rows to a CSV in `data/used/` (any `*.csv` in that folder
   is picked up, except files starting with `_`).
2. Run the script. It prints a summary table and writes the core indicator
   columns back into each `data/used/*.csv` file in place.
3. Rows with `confidence = No comparable found` need either a new-inventory
   row added for that trim, or a `trim_equivalence.csv` mapping — the script
   deliberately labels these `Manual review` instead of guessing a discount.

Requires `pandas` (tested with pandas 2.2.3 / Python 3.13).

## `scripts/regroup_used_by_model.py` (one-time, already run)

Used listings were originally collected as one CSV per retailer
(`enterprise_car_sales.csv`, `avis_car_sales.csv`, `hertz_rent2buy.csv`).
This script read those three files, tagged each row with its `retail`
source, and rewrote `data/used/` as one CSV per make+model to match the
`data/new/` convention — then the three retailer-grouped files were deleted.
It's kept in `scripts/` as a record of that migration, not something you
need to run again; new used listings should just be added directly to the
matching `data/used/<make>_<model>.csv` file (or a new one, following the
same naming pattern, if it's a make/model not seen yet).
