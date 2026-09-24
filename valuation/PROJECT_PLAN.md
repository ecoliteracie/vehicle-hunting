# Project Plan: Used-Car Fair-Value Indicator

## Project goal

Build a dependable screening tool that answers:

> Is this used vehicle priced well for its model, trim, model year, mileage,
> local market, condition, history, and total purchase cost?

The tool should help identify vehicles worth investigating while clearly
separating a promising price from a safe final purchase.

## Current system

The current calculation compares a used listing with the median Today's Price
of new vehicles sharing the same model and trim.

Current indicators:

- `raw_discount`: dollar difference from the median new price
- `discount_pct`: percentage difference from the median new price
- `mileage_adjusted_discount_per_10k`: discount percentage points per 10,000
  used miles
- `value_label`: color/category based only on `discount_pct`

This remains useful as a **new-equivalent discount screen**, but it is not a
complete estimate of the vehicle's fair used-market value. Every used car is
cheaper than new — that is depreciation, not a deal. So the current
`discount_pct` (which alone drives the `value_label`) answers the wrong
question: a fairly priced used car and an overpriced one are *both* cheaper
than new. The methodology below replaces that with a comparison against other
*used* cars.

## Data-readiness prerequisite (read first)

This is the honest gate on everything below. The design assumes clean
comparable groups (same generation, drivetrain, powertrain, region) and a
pool of used listings large enough to form a median. As of this writing
neither is fully true:

- `drivetrain` and `powertrain` are `Unspecified` for most rows, so a hybrid
  and a gas RAV4 XLE would land in the same group and corrupt the estimate.
  Phase 1 (data-quality foundation) is therefore not optional prep — it is the
  real blocker for a trustworthy Phase 2.
- The used listings are currently the cars *being evaluated*, not a separate
  benchmark pool. Only two models (Corolla ~34, Camry ~18 rows) have enough
  observations to fit a mileage curve; most have one to four rows and must
  honestly report low confidence or `Manual review` rather than a confident
  number.

Expect most models to sit at `Low` / `Manual review` until more used
comparables are collected. That is the correct behavior, not a failure.

## Recommended valuation design

Use two separate valuation views instead of forcing one score to answer every
question.

### View 1: New-equivalent discount

Keep the current calculation as a secondary reference:

```text
new_equivalent_discount = median_new_price - used_price

new_equivalent_discount_pct =
    new_equivalent_discount / median_new_price * 100
```

This answers:

> How much cheaper is this used vehicle than buying a comparable new one?

Rename the current indicators in a future migration if practical so their
meaning is unmistakable. Do not remove the existing columns until downstream
usage has been checked.

### View 2: Used-market fair value

Make this the primary deal-quality measurement:

```text
expected_used_price =
    median local comparable price adjusted for mileage and model year

market_discount =
    expected_used_price - target_out_the_door_price

market_discount_pct =
    market_discount / expected_used_price * 100
```

This answers:

> Is this vehicle cheaper or more expensive than comparable used vehicles?

### Two correctness rules that make View 2 trustworthy

1. **Leave-one-out.** When estimating the expected price for a listing, exclude
   that listing from its own comparable set. Otherwise a genuinely underpriced
   car pulls its own benchmark down and looks less like a deal, and a market of
   overpriced cars makes an overpriced car look "fair." The estimate for a car
   must come only from *other* cars.
2. **Benchmark pool ⊋ shopping list.** The pool used to compute the expected
   price should be broader than the specific cars you are screening. While the
   only used data is the shopping list itself, treat every estimate built from
   a handful of siblings as low confidence and inspect outliers rather than
   deleting them — a single unusual sibling moves a small-sample median a lot.

## Comparable-selection rules

Prefer comparable vehicles with:

- same make and model
- same vehicle generation
- same trim
- same powertrain, such as gas, hybrid, plug-in hybrid, or electric
- same drivetrain, such as FWD, AWD, or 4WD
- model year within one year when the exact year has too few observations
- similar mileage
- same seller type, preferably dealer-to-dealer
- same regional market, initially within 100-200 miles
- active, available listings

Do not mix materially different body styles, generations, engines,
drivetrains, or branded/salvage titles in one comparable group.

## Mileage adjustment

Replace the current percentage-per-10,000-mile heuristic as the primary
mileage measurement. Estimate depreciation in dollars from actual used-market
comparables.

### Initial method: mileage bands

When the dataset is still small, group comparable vehicles into mileage bands,
for example:

- 0-20,000 miles
- 20,001-40,000 miles
- 40,001-60,000 miles
- 60,001-80,000 miles
- more than 80,000 miles

Use the median price within the applicable band. Require a minimum sample size
and report low confidence when the band is sparse.

**Sparse-data fallback (required at current data size).** With only a handful
of rows per model, most bands will be empty. The estimator must degrade
gracefully rather than emit a confident number from one comparable:

- Enough comparables with real mileage spread → fit a robust mileage curve
  (see below) and predict at the target's mileage.
- A few comparables but no usable spread → use the leave-one-out group median,
  with **no** mileage adjustment, at reduced confidence.
- One or two comparables → `Low` confidence estimate, clearly flagged.
- Zero comparables → `Manual review`, no invented price.

Never extrapolate a fitted price beyond the observed mileage range; clamp the
prediction to the range the comparables actually cover.

### Later method: robust regression

Once enough observations exist, estimate expected price using a robust model:

```text
price =
    model/trim baseline
    + model-year effect
    + mileage effect
    + drivetrain effect
    + powertrain effect
    + condition/history adjustments
    + local-market effect
```

Use a method resistant to unusually high or low listings. Report a prediction
range, not just one estimated price.

At the current data size a full multi-term regression would overfit. The
practical robust starting point is a **Theil–Sen** line of price vs. mileage
within a model+trim group (the median of all pairwise slopes), which needs no
extra dependencies, tolerates outliers, and collapses cleanly to a median when
mileage has no usable spread. Graduate to the full multi-term model only once
each term has enough observations to estimate.

## Out-the-door price

Base the final comparison on the actual purchase cost whenever possible:

```text
target_out_the_door_price =
    advertised_price
    + mandatory_documentation_fee
    + mandatory_dealer_add_ons
    + delivery_or_transfer_fee
```

Taxes and registration may be displayed separately because they often apply
similarly across alternatives, but include them when comparing sellers or
locations with materially different costs.

Record whether each price component is known, included, excluded, or unknown.
Unknown mandatory fees should reduce confidence.

## Risk-adjusted value

Price alone cannot determine whether a vehicle is a good purchase. Calculate a
second-stage risk adjustment:

```text
risk_adjusted_margin =
    market_discount
    - immediate_repair_cost
    - deferred_maintenance_reserve
    - accident_or_title_penalty
    - rental_use_penalty
    + remaining_warranty_value
```

Manual inputs should remain visible and auditable. Do not silently invent
repair, accident, rental, or warranty values.

## Recommended decision gates

A listing should receive the strongest recommendation only when all three
gates pass.

### Gate 1: Price

- Sufficient local used comparables exist.
- The out-the-door price is below the mileage-adjusted used-market estimate.
- The difference is large enough to remain meaningful after uncertainty.

### Gate 2: History and identity

- VIN matches the listing and documents.
- Title is clean and acceptable.
- Accident, flood, theft, odometer, owner, and rental history are understood.
- Open recalls have been checked.

### Gate 3: Mechanical condition

- An independent pre-purchase inspection has been completed.
- Immediate repairs and deferred maintenance have written estimates.
- Tires, brakes, fluids, battery, leaks, warning lights, and major systems are
  acceptable or included in the negotiated price.

If a listing fails Gate 2 or Gate 3, a low advertised price should not produce
a `Strong Value` recommendation.

## Proposed output fields

### Comparable identity

- `generation`
- `body_style`
- `drivetrain`
- `powertrain`
- `seller_type`
- `location`
- `distance_miles`
- `vin`

### Price and fees

- `advertised_price`
- `doc_fee`
- `mandatory_add_ons`
- `transfer_fee`
- `out_the_door_price_before_tax`
- `fee_data_confidence`

### Used-market analysis

- `used_comp_count`
- `used_comp_price_median`
- `expected_used_price`
- `expected_price_low`
- `expected_price_high`
- `market_discount`
- `market_discount_pct`
- `market_confidence`

### Risk adjustments

- `immediate_repair_cost`
- `maintenance_reserve`
- `accident_title_penalty`
- `rental_use_penalty`
- `warranty_value`
- `risk_adjusted_margin`

### Recommendation

- `price_label`
- `history_gate`
- `inspection_gate`
- `final_recommendation`
- `recommendation_reason`

## Confidence framework

Confidence should describe the quality of the comparison, not merely the
number of new listings.

Consider:

- number of comparable used listings
- exactness of year, generation, trim, drivetrain, and powertrain matches
- geographic distance
- age of the listing data
- completeness of fees
- spread or disagreement among comparable prices
- availability of VIN, condition, and history data

Suggested confidence levels:

- `High`: at least five close comparables with complete, recent data and a
  narrow price range
- `Medium`: three or four usable comparables or one important inferred field
- `Low`: one or two comparables, broad geography, old data, or missing fees
- `Manual review`: no defensible comparison

These thresholds are project heuristics and should be calibrated as more data
is collected.

## Implementation roadmap

### Phase 1: Data-quality foundation

- Add VIN where available and use it for deduplication.
- Normalize model, trim, drivetrain, and powertrain names.
- Add explicit location, seller type, and fee fields.
- Track `first_seen`, `last_seen`, and listing status.
- Treat price changes as updates to the same VIN, not new vehicles.
- Add validation for duplicate IDs, duplicate VINs, malformed rows, and stale
  categorical values.

### Phase 2: Local used-market benchmark

- Collect comparable used listings from multiple sellers.
- Define generation and exact-match rules.
- Build mileage bands and used-price medians.
- Add `market_discount`, `market_discount_pct`, and confidence fields.
- Keep the current new-equivalent discount alongside the new method.

### Phase 3: Out-the-door and risk adjustments

- Capture mandatory fees and add-ons.
- Add manual inspection, repair, history, rental, and warranty inputs.
- Calculate `risk_adjusted_margin`.
- Prevent strong recommendations when history or inspection gates are unknown
  or failed.

### Phase 4: Statistical improvement

- Fit a robust mileage/year price model after collecting enough observations.
- Back-test predictions against later price changes and completed purchases.
- Compare predicted ranges with independent market-value sources.
- Tune labels and confidence thresholds using observed error.

### Phase 5: Buyer-facing report

- Show the asking and out-the-door prices.
- Show the local used-market expected range.
- Show the new-equivalent discount as secondary context.
- Explain the most important positive and negative adjustments.
- Display history and inspection gates prominently.
- Include a negotiation target and maximum recommended price only when data
  quality is sufficient.

## Validation plan

Before trusting the improved recommendation:

- test known examples manually
- verify all comparable groups are mechanically equivalent
- confirm that higher mileage normally lowers expected price within a group
- inspect outliers rather than automatically deleting them
- ensure price updates do not create duplicate listings
- compare results with at least one independent valuation source
- record the prediction error when a verified transaction price is available
- review recommendations that change sharply after a small input change

## Definition of success

The project is successful when it can:

1. Explain why a vehicle received its recommendation.
2. Distinguish a discount from new price from a discount to used-market value.
3. Adjust fairly for mileage, model year, and major configuration differences.
4. Compare out-the-door costs rather than misleading advertised prices.
5. Refuse to call a vehicle a strong value when history or mechanical risk is
   unknown or unacceptable.
6. Provide a realistic expected-price range and state its confidence.

## Buyer checklist

Before making an offer:

- Confirm the VIN on the vehicle, listing, history report, and paperwork.
- Compare at least several equivalent local used vehicles.
- Request the complete out-the-door price in writing.
- Decline unwanted dealer add-ons.
- Review the Buyers Guide and warranty terms.
- Obtain a vehicle-history report.
- Check for open recalls.
- Get an independent pre-purchase inspection.
- Convert inspection findings into repair-cost estimates.
- Recalculate the risk-adjusted margin before negotiating.
- Walk away when the seller will not provide necessary information or permit a
  reasonable independent inspection.

## Guiding principle

The tool should help answer **which vehicle deserves deeper investigation**.
The final buying decision should combine market price, total cost, vehicle
history, warranty, and independent mechanical condition.
