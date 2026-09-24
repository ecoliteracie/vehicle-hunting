"""
Toyota inventory valuation.

Compares used-vehicle listings (data/used/*.csv) against new-vehicle
benchmark prices (data/new/*.csv) using the same comparable-key /
discount formulas discussed for the Excel version:

    Comparable Key       = Model|Trim  (Drivetrain/Powertrain appended once known)
    Comparable New Price = min / mean / median new price sharing that key
    Raw Discount          = Comparable New Price (median) - Used Price
    Discount %            = Raw Discount / Comparable New Price (median) * 100
    Mileage-Adjusted %    = Discount % / (Mileage / 10000)
    Adjusted Value Score  = Raw Discount - MileagePenalty - ModelYearPenalty
                             - RentalRiskPenalty - MaintenanceReserve
                             + WarrantyValueDiff

`discount_pct` and `mileage_adjusted_discount_per_10k` are stored as plain
percent numbers (18.1 means 18.1%, not 0.181) so they read directly off the
CSV without mental math.

Manual-adjustment inputs (rental risk, warranty, condition, etc.) are read
from optional columns on the used-vehicle CSV; if a column is absent it
defaults to 0, per the "semi-automated" approach: the script auto-computes
what it can and leaves the rest as explicit, visible inputs.

Running this script writes the core indicator columns (comparable price,
discount %, mileage-adjusted discount %, confidence, value label) directly
back into each `data/used/*.csv` file in place, so you can just open a
model's file and see the call for each row.

Also computes View 2, a used-market fair-value estimate (expected_used_price,
market_discount_pct, market_confidence, price_label) from OTHER used listings
of the same make+model+trim, leave-one-out (see compute_used_market_valuation).

KNOWN GAP: at low used_comp_count (1-2), _estimate_one falls back to a plain
median with no mileage adjustment and no check that the comparable's mileage/
year is even close to the target's. This can produce a confident-sounding
price_label (e.g. "Strong Value") built from a single wildly mismatched comp
(see README.md "Known reliability gap" for a worked example: a 2020 CR-V with
107k miles compared against a 2025 CR-V with 27k miles). market_confidence is
set correctly to "Low" in that case, but price_label does not itself reflect
that low confidence, so don't read price_label without checking
market_confidence next to it.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
NEW_DIR = ROOT / "data" / "new"
USED_DIR = ROOT / "data" / "used"
TRIM_MAP_PATH = ROOT / "data" / "trim_equivalence.csv"
SUMMARY_XLSX_PATH = ROOT / "valuation_summary.xlsx"

# One-stop Excel summary across every data/used/*.csv file: identity fields
# plus every calculated indicator, nothing else (no source/notes/retail/fee
# columns — those stay in the CSVs for whoever wants them).
SUMMARY_IDENTITY_COLUMNS = ["vehicle_id", "make", "model", "year", "trim", "mileage", "price"]

# Optional manual-adjustment columns a used-listing CSV may include.
# Missing columns default to 0 and are added automatically.
MANUAL_ADJUSTMENT_COLUMNS = [
    "model_year_penalty",
    "rental_risk_penalty",
    "maintenance_reserve",
    "warranty_value_diff",
]

# Discount % (as a plain percent number, e.g. 15 means 15%) thresholds used
# to label the deal.
VALUE_LABELS = [
    (15, "Strong Value"),
    (8, "Good Value"),
    (0, "Fair Value"),
    (float("-inf"), "Weak Value"),
]

# View 1 (new-equivalent discount) indicator columns written back onto each
# data/used/*.csv file, in this order.
INDICATOR_COLUMNS = [
    "comparable_price_median",
    "raw_discount",
    "discount_pct",
    "mileage_adjusted_discount_per_10k",
    "confidence",
    "value_label",
]

# View 2 (used-market fair value) columns. Estimated from OTHER used listings
# of the same make+model+trim (leave-one-out), so a car is never compared
# against itself. See PROJECT_PLAN.md "Used-market fair value".
VIEW2_COLUMNS = [
    "used_comp_count",
    "expected_used_price",
    "expected_price_low",
    "expected_price_high",
    "market_discount",
    "market_discount_pct",
    "market_confidence",
    "price_label",
]

# All indicator columns stripped-then-rewritten on each run.
ALL_INDICATOR_COLUMNS = INDICATOR_COLUMNS + VIEW2_COLUMNS

# Used-market deal thresholds (plain percent numbers). Used-car spreads are far
# tighter than the new-vs-used gap, so these are smaller than VALUE_LABELS.
# market_discount_pct >= threshold picks the label. Heuristics — calibrate as
# more data is collected.
USED_MARKET_LABELS = [
    (8, "Strong Value"),
    (4, "Good Value"),
    (-4, "Fair Value"),
    (float("-inf"), "Overpriced"),
]

# Fit a mileage curve only with at least this many comparables AND at least
# this much spread between their lowest and highest mileage; otherwise use the
# leave-one-out median with no mileage adjustment.
MIN_COMPS_FOR_CURVE = 4
MIN_MILEAGE_SPREAD = 8000

# A High-confidence estimate is downgraded to Medium if the comparables
# disagree by more than this fraction of the expected price.
WIDE_SPREAD_FRACTION = 0.06


def _load_csv_dir(directory: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(directory.glob("*.csv")):
        if path.name.startswith("_"):
            continue
        df = pd.read_csv(path)
        if df.empty:
            continue  # skip header-only template files
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_new_inventory() -> pd.DataFrame:
    return _load_csv_dir(NEW_DIR)


def load_used_inventory() -> pd.DataFrame:
    df = _load_csv_dir(USED_DIR)
    if df.empty:
        return df
    # Drop any indicator columns a previous run already wrote back, so this
    # run recomputes them cleanly instead of colliding with fresh values.
    df = df.drop(columns=[c for c in ALL_INDICATOR_COLUMNS if c in df.columns])
    for col in MANUAL_ADJUSTMENT_COLUMNS:
        if col not in df.columns:
            df[col] = 0
        else:
            df[col] = df[col].fillna(0)
    return df


def load_trim_equivalence() -> pd.DataFrame:
    """Optional mapping for used trims that have no exact new-trim match.

    Expected columns: model, used_trim, comparable_trim, trim_adjustment
    trim_adjustment is added to the comparable new price (usually negative,
    e.g. new trim carries extra equipment the used trim lacks).
    """
    if not TRIM_MAP_PATH.exists():
        return pd.DataFrame(columns=["model", "used_trim", "comparable_trim", "trim_adjustment"])
    return pd.read_csv(TRIM_MAP_PATH)


MATCH_COLUMNS = ["_match_model", "_match_trim"]


def _with_match_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with normalized model/trim fields used for matching.

    The CSV ``comparable_key`` column is intentionally ignored here. It is
    retained in the files for compatibility, but it can become stale when a
    model or trim is corrected later.
    """
    matched = df.copy()
    matched["_match_model"] = (
        matched["model"].fillna("").astype(str).str.strip().str.casefold()
    )
    matched["_match_trim"] = (
        matched["trim"].fillna("").astype(str).str.strip().str.casefold()
    )
    return matched


def _normalize_match_value(value) -> str:
    """Normalize one model or trim value the same way as a dataframe column."""
    return "" if pd.isna(value) else str(value).strip().casefold()


def compute_new_benchmarks(new_df: pd.DataFrame) -> pd.DataFrame:
    """Per normalized model + trim: min / mean / median / count of prices."""
    new_for_match = _with_match_columns(new_df)
    grouped = new_for_match.groupby(MATCH_COLUMNS)["price"].agg(
        comparable_price_min="min",
        comparable_price_mean="mean",
        comparable_price_median="median",
        comparable_count="count",
    )
    return grouped.reset_index()


def _label_value(discount_pct) -> str:
    if pd.isna(discount_pct):
        return "N/A"
    for threshold, label in VALUE_LABELS:
        if discount_pct >= threshold:
            return label
    return "Weak Value"


def _confidence(count: int) -> str:
    if count >= 3:
        return "Exact match (high confidence)"
    if count in (1, 2):
        return "Exact match (low sample)"
    return "No comparable found"


def compute_valuation(used_df: pd.DataFrame, benchmarks: pd.DataFrame, trim_map: pd.DataFrame) -> pd.DataFrame:
    used_for_match = _with_match_columns(used_df)
    merged = used_for_match.merge(benchmarks, on=MATCH_COLUMNS, how="left")
    merged["trim_adjusted"] = False

    # Fall back to the trim-equivalence table wherever there was no exact match.
    needs_fallback = merged["comparable_count"].isna()
    if needs_fallback.any() and not trim_map.empty:
        for idx in merged[needs_fallback].index:
            row = merged.loc[idx]
            match = trim_map[
                trim_map["model"].map(_normalize_match_value).eq(row["_match_model"])
                & trim_map["used_trim"].map(_normalize_match_value).eq(row["_match_trim"])
            ]
            if match.empty:
                continue
            comparable_trim = match.iloc[0]["comparable_trim"]
            trim_adjustment = match.iloc[0]["trim_adjustment"]
            bench_row = benchmarks[
                benchmarks["_match_model"].eq(row["_match_model"])
                & benchmarks["_match_trim"].eq(_normalize_match_value(comparable_trim))
            ]
            if bench_row.empty:
                continue
            bench_row = bench_row.iloc[0]
            merged.loc[idx, "comparable_price_min"] = bench_row["comparable_price_min"] + trim_adjustment
            merged.loc[idx, "comparable_price_mean"] = bench_row["comparable_price_mean"] + trim_adjustment
            merged.loc[idx, "comparable_price_median"] = bench_row["comparable_price_median"] + trim_adjustment
            merged.loc[idx, "comparable_count"] = bench_row["comparable_count"]
            merged.loc[idx, "trim_adjusted"] = True

    merged["comparable_count"] = merged["comparable_count"].fillna(0).astype(int)

    merged["confidence"] = merged["comparable_count"].apply(_confidence)
    merged.loc[merged["trim_adjusted"], "confidence"] = "Trim-adjusted"

    # Primary benchmark = median (least sensitive to one outlier listing).
    merged["comparable_price_median"] = merged["comparable_price_median"].round(0)
    merged["raw_discount"] = (merged["comparable_price_median"] - merged["price"]).round(0)
    discount_fraction = merged["raw_discount"] / merged["comparable_price_median"]
    merged["discount_pct"] = (discount_fraction * 100).round(1)

    mileage = merged["mileage"].replace(0, np.nan)
    merged["mileage_adjusted_discount_per_10k"] = (
        merged["discount_pct"] / (mileage / 10000)
    ).round(2)

    merged["adjusted_value_score"] = (
        merged["raw_discount"]
        - merged["model_year_penalty"]
        - merged["rental_risk_penalty"]
        - merged["maintenance_reserve"]
        + merged["warranty_value_diff"]
    )

    merged["value_label"] = merged["discount_pct"].apply(_label_value)
    merged.loc[merged["comparable_count"] == 0, "value_label"] = "Manual review"

    return merged


def _theil_sen(x: np.ndarray, y: np.ndarray):
    """Robust line fit: slope = median of pairwise slopes, intercept = median
    of per-point intercepts. Returns (slope, intercept) or None if no two
    points have distinct x. Resistant to a single outlier listing.
    """
    n = len(x)
    slopes = []
    for i in range(n):
        for j in range(i + 1, n):
            if x[j] != x[i]:
                slopes.append((y[j] - y[i]) / (x[j] - x[i]))
    if not slopes:
        return None
    slope = float(np.median(slopes))
    intercept = float(np.median(y - slope * x))
    return slope, intercept


def _used_market_label(pct) -> str:
    if pd.isna(pct):
        return "Manual review"
    for threshold, label in USED_MARKET_LABELS:
        if pct >= threshold:
            return label
    return "Overpriced"


def _estimate_one(target, comps: pd.DataFrame) -> dict:
    """Estimate expected used-market price for one listing from its comparables
    (already leave-one-out and same make+model+trim). ``comps`` has numeric
    ``mileage`` and ``price`` columns and excludes the target itself.
    """
    c = len(comps)
    blank = {
        "used_comp_count": c,
        "expected_used_price": np.nan,
        "expected_price_low": np.nan,
        "expected_price_high": np.nan,
        "market_discount": np.nan,
        "market_discount_pct": np.nan,
        "market_confidence": "Manual review",
        "price_label": "Manual review",
    }
    if c == 0:
        return blank

    prices = comps["price"].to_numpy(dtype=float)
    miles = comps["mileage"].to_numpy(dtype=float)
    target_miles = float(target["mileage"]) if pd.notna(target["mileage"]) else np.nan
    mileage_spread = float(miles.max() - miles.min())

    fitted_at_comps = None
    mileage_adjusted = False
    if (
        c >= MIN_COMPS_FOR_CURVE
        and mileage_spread >= MIN_MILEAGE_SPREAD
        and pd.notna(target_miles)
    ):
        fit = _theil_sen(miles, prices)
        # Only trust the curve when price falls with mileage (slope < 0).
        if fit is not None and fit[0] < 0:
            slope, intercept = fit
            raw_pred = intercept + slope * target_miles
            # Never extrapolate beyond the mileage the comps actually cover.
            expected = float(np.clip(raw_pred, prices.min(), prices.max()))
            fitted_at_comps = intercept + slope * miles
            mileage_adjusted = True

    if fitted_at_comps is None:
        # Median fallback: no usable mileage signal. At c=1-2 this does not
        # check whether the comp's own mileage/year is close to the target's
        # (KNOWN GAP, see module docstring) — market_confidence is downgraded
        # to Low below, but price_label itself can still read as confident.
        expected = float(np.median(prices))
        residuals = prices - expected
    else:
        residuals = prices - fitted_at_comps

    # Robust half-width of the comparable disagreement (MAD -> ~sigma).
    mad = float(np.median(np.abs(residuals)))
    half_width = 1.4826 * mad
    expected = round(expected, 0)
    low = round(expected - half_width, 0)
    high = round(expected + half_width, 0)

    price = float(target["price"])
    market_discount = round(expected - price, 0)
    market_discount_pct = round(market_discount / expected * 100, 1) if expected else np.nan

    rel_spread = (half_width / expected) if expected else 1.0
    if c >= 5:
        confidence = "High" if rel_spread <= WIDE_SPREAD_FRACTION else "Medium"
    elif c >= 3:
        confidence = "Medium"
    else:
        confidence = "Low"
    if not mileage_adjusted and confidence == "High":
        confidence = "Medium"  # median-only should not read as top confidence

    return {
        "used_comp_count": c,
        "expected_used_price": expected,
        "expected_price_low": low,
        "expected_price_high": high,
        "market_discount": market_discount,
        "market_discount_pct": market_discount_pct,
        "market_confidence": confidence,
        "price_label": _used_market_label(market_discount_pct),
    }


def compute_used_market_valuation(used_df: pd.DataFrame) -> pd.DataFrame:
    """View 2: expected used-market price per listing, from OTHER used listings
    of the same make+model+trim (leave-one-out). Returns vehicle_id + the
    VIEW2_COLUMNS. Rows with an ``Unspecified`` trim or no usable comparables
    get ``Manual review`` rather than an invented price.
    """
    df = used_df.copy()
    df["_g_make"] = df.get("make", "").fillna("").astype(str).str.strip().str.casefold()
    df["_g_model"] = df["model"].fillna("").astype(str).str.strip().str.casefold()
    df["_g_trim"] = df["trim"].fillna("").astype(str).str.strip().str.casefold()

    records = []
    for _, target in df.iterrows():
        # Unknown trim can't form a clean comparable group.
        if target["_g_trim"] in ("", "unspecified"):
            rec = {
                "used_comp_count": 0,
                "expected_used_price": np.nan,
                "expected_price_low": np.nan,
                "expected_price_high": np.nan,
                "market_discount": np.nan,
                "market_discount_pct": np.nan,
                "market_confidence": "Manual review",
                "price_label": "Manual review",
            }
        else:
            group = df[
                df["_g_make"].eq(target["_g_make"])
                & df["_g_model"].eq(target["_g_model"])
                & df["_g_trim"].eq(target["_g_trim"])
            ]
            comps = group[
                group["vehicle_id"].ne(target["vehicle_id"])  # leave-one-out
                & group["price"].notna()
                & group["mileage"].notna()
            ]
            rec = _estimate_one(target, comps)
        rec["vehicle_id"] = target["vehicle_id"]
        records.append(rec)

    return pd.DataFrame.from_records(records)[["vehicle_id"] + VIEW2_COLUMNS]


def write_back_to_used_files(results: pd.DataFrame) -> None:
    """Add/refresh the indicator columns on each source data/used/*.csv file.

    Matches rows by vehicle_id, so it only touches files that were actually
    loaded (skips the empty template and any "_"-prefixed file, same as the
    loader). Safe to re-run: previously written indicator columns are
    dropped and recomputed rather than duplicated.
    """
    indicators = results[["vehicle_id"] + ALL_INDICATOR_COLUMNS]

    for path in sorted(USED_DIR.glob("*.csv")):
        if path.name.startswith("_"):
            continue
        original = pd.read_csv(path)
        if original.empty:
            continue
        original = original.drop(columns=[c for c in ALL_INDICATOR_COLUMNS if c in original.columns])
        enriched = original.merge(indicators, on="vehicle_id", how="left")
        try:
            enriched.to_csv(path, index=False)
        except PermissionError:
            # File is open elsewhere (e.g. Excel). Skip it rather than abort the
            # whole run and leave other files unwritten; close it and re-run.
            print(f"SKIPPED {path.relative_to(ROOT)} - file is locked (open in "
                  f"another program?). Close it and re-run to update it.")
            continue
        print(f"Updated {len(enriched)} rows in {path.relative_to(ROOT)}")


def write_summary_workbook(results: pd.DataFrame) -> None:
    """Write a single-sheet Excel workbook with every used listing: just the
    identity fields (make/model/year/trim/mileage/price) plus every calculated
    View 1 and View 2 indicator. This is the "don't open every CSV" summary.
    """
    columns = SUMMARY_IDENTITY_COLUMNS + ALL_INDICATOR_COLUMNS
    summary = results[[c for c in columns if c in results.columns]].sort_values(
        ["model", "trim", "mileage"]
    )

    try:
        with pd.ExcelWriter(SUMMARY_XLSX_PATH, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Valuation Summary", index=False)
            sheet = writer.sheets["Valuation Summary"]
            sheet.freeze_panes = "A2"
            for col_cells in sheet.columns:
                width = max(len(str(c.value)) for c in col_cells if c.value is not None)
                sheet.column_dimensions[col_cells[0].column_letter].width = width + 2
    except PermissionError:
        print(f"SKIPPED {SUMMARY_XLSX_PATH.relative_to(ROOT)} - file is locked "
              f"(open in Excel?). Close it and re-run to update it.")
        return

    print(f"Wrote {len(summary)} rows to {SUMMARY_XLSX_PATH.relative_to(ROOT)}")


def main():
    new_df = load_new_inventory()
    used_df = load_used_inventory()
    trim_map = load_trim_equivalence()

    if new_df.empty:
        raise SystemExit(f"No new-inventory CSVs found in {NEW_DIR}")
    if used_df.empty:
        print(f"No used-vehicle rows found in {USED_DIR} yet — add listings to "
              f"{USED_DIR / 'toyota_used_template.csv'} (or a new file in that folder) and re-run.")
        return

    benchmarks = compute_new_benchmarks(new_df)
    results = compute_valuation(used_df, benchmarks, trim_map)

    # View 2: used-market fair value (leave-one-out across the used pool).
    used_market = compute_used_market_valuation(used_df)
    results = results.merge(used_market, on="vehicle_id", how="left")

    write_back_to_used_files(results)
    write_summary_workbook(results)

    view1_cols = [
        "vehicle_id", "model", "trim", "year", "mileage", "price",
        "comparable_price_median", "raw_discount", "discount_pct",
        "mileage_adjusted_discount_per_10k", "confidence", "value_label",
    ]
    view2_cols = [
        "vehicle_id", "model", "trim", "year", "mileage", "price",
        "used_comp_count", "expected_used_price", "expected_price_low",
        "expected_price_high", "market_discount", "market_discount_pct",
        "market_confidence", "price_label",
    ]
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print("\nView 1 - new-equivalent discount (how much cheaper than new):")
        print(results[view1_cols].to_string(index=False))
        print("\nView 2 - used-market fair value (vs. comparable used cars):")
        print(results[view2_cols].to_string(index=False))


if __name__ == "__main__":
    main()
