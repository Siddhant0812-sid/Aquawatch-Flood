"""
AquaWatch — Hydrological Telemetry Data Pipeline
==============================================
Handles:
  - Synthetic data generation (swap out for real NWDP CSVs later)
  - Loading & merging rainfall + water-level telemetry
  - Cleaning, interpolation, alignment
  - Saving processed data to CSV

SWAP-IN POINT: search for "# REAL DATA SWAP" to find every place
where you replace synthetic generation with your real CSV loading.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Config ──────────────────────────────────────────────────────────────────
STATIONS = {
    "water_level": [
        "NH15 Crossing Dhansirighat",
        "NH15 Crossing Fakirpara Tangni",
        "NH17 Crossing Boko",
    ],
    "rainfall": [
        "NH15 Crossing Dhansirighat",
        "NH15 Crossing Fakirpara Tangni",
        "NH17 Crossing Boko",
    ],
}
START_DATE = "2021-01-01"
END_DATE   = "2025-12-31"
FREQ       = "1h"          # hourly
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ── Synthetic data generation ────────────────────────────────────────────────
def _make_index(start=START_DATE, end=END_DATE, freq=FREQ):
    return pd.date_range(start, end, freq=freq)


def generate_synthetic_water_level() -> pd.DataFrame:
    df = pd.read_csv(PROJECT_ROOT / "data" / "raw_water_level_assam.csv",
                     parse_dates=["Data Acquisition Time"],
                     date_format={"Data Acquisition Time": "%d-%m-%Y %H:%M"})
    df_wide = df.pivot_table(
        index="Data Acquisition Time",
        columns="Station",
        values="River Water Level Telemetry Hourly (meter)"
    )
    df_wide.index.name = "datetime"
    df_wide = df_wide[STATIONS["water_level"]]
    df_wide = df_wide.asfreq("1h")
    return df_wide


def generate_synthetic_rainfall(seed: int = 7) -> pd.DataFrame:
    """
    Generates realistic hourly rainfall data (mm/hr) for Assam stations.

    Realism features:
      - Intermittent (mostly zero: ~85% dry hours)
      - Monsoon-clustered heavy events
      - Gamma-distributed intensities during wet hours
      - Spatial correlation across stations

    # REAL DATA SWAP ─────────────────────────────────────────────────────────
    Replace this entire function body with:

        df = pd.read_csv("data/raw/rainfall_cwc_assam.csv",
                         parse_dates=["datetime"], index_col="datetime")
        df = df[STATIONS["rainfall"]]
        df = df.asfreq("1h").fillna(0)    # missing = no rain
        return df

    # ─────────────────────────────────────────────────────────────────────────
    """
    rng = np.random.default_rng(seed)
    idx = _make_index()
    n   = len(idx)
    doy = idx.day_of_year.values

    # Monsoon probability envelope
    monsoon_prob = 0.03 + 0.25 * np.exp(-0.5 * ((doy - 200) / 55) ** 2)

    data = {}
    # Base wet/dry series (shared spatial driver)
    base_wet = rng.random(n) < monsoon_prob

    for j, station in enumerate(STATIONS["rainfall"]):
        # Each station has slight independent variation
        local_noise = rng.random(n) < 0.04
        wet = base_wet | local_noise

        rain = np.zeros(n)
        n_wet = wet.sum()
        # Gamma-distributed intensity (shape=0.8, scale=3.5 mm/hr typical Assam)
        rain[wet] = rng.gamma(shape=0.8, scale=3.5, size=n_wet)
        # Occasional heavy burst
        heavy_mask = rng.random(n_wet) < 0.05
        rain[wet] = np.where(heavy_mask,
                             rain[wet] * rng.uniform(3, 8, n_wet),
                             rain[wet])
        rain = np.clip(rain, 0, 80)        # max 80 mm/hr
        data[station] = rain

    df = pd.DataFrame(data, index=idx)
    df.index.name = "datetime"
    return df


# ── Cleaning & alignment ─────────────────────────────────────────────────────
def clean_water_level(df: pd.DataFrame,
                      max_gap_hours: int = 24) -> pd.DataFrame:
    """
    - Enforce hourly index
    - Linear interpolation for gaps ≤ max_gap_hours
    - Forward-fill short remaining gaps; flag long gaps as NaN
    - Remove physically impossible values (< 0 or > 200 m)
    """
    df = df.copy()
    df = df.asfreq("1h")                             # enforce freq
    df[df < 0]   = np.nan                            # impossible negatives
    df[df > 200] = np.nan                            # impossible highs

    df = df.interpolate(method="time", limit=max_gap_hours)
    df = df.ffill(limit=2)                           # small trailing gaps

    missing_pct = df.isna().mean() * 100
    print("[water_level] Missing % after cleaning:")
    print(missing_pct.round(2).to_string())
    return df


def clean_rainfall(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Enforce hourly index
    - Missing → 0 (standard: no reading = no rain)
    - Clip negative values to 0
    """
    df = df.copy()
    df = df.asfreq("1h")
    df[df < 0] = 0
    df = df.fillna(0)
    return df


# ── Merge into unified frame ─────────────────────────────────────────────────
def build_merged_dataset(wl_df: pd.DataFrame,
                         rf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merges water-level and rainfall into one DataFrame with prefixed columns.
    Aligns on the common datetime range, then aggressively fills any
    remaining NaNs from real-data gaps.
    """
    common_start = max(wl_df.index.min(), rf_df.index.min())
    common_end   = min(wl_df.index.max(), rf_df.index.max())

    wl = wl_df.loc[common_start:common_end].add_prefix("wl_")
    rf = rf_df.loc[common_start:common_end].add_prefix("rf_")

    merged = pd.concat([wl, rf], axis=1)

    # ── Diagnose NaNs before fixing ──────────────────────────────────────────
    nan_counts = merged.isna().sum()
    nan_cols   = nan_counts[nan_counts > 0]
    if len(nan_cols) > 0:
        print("\n[merge] NaNs found — diagnosing:")
        for col, count in nan_cols.items():
            pct = 100 * count / len(merged)
            print(f"  {col}: {count:,} NaNs ({pct:.1f}%)")

        # wl columns: interpolate long gaps, then forward/back fill edges
        wl_cols = [c for c in merged.columns if c.startswith("wl_")]
        merged[wl_cols] = (merged[wl_cols]
                           .interpolate(method="time", limit=24)   # up to 24h gap
                           .ffill(limit=48)                         # edge fill
                           .bfill(limit=48))

        # rf columns: missing = no rain (meteorological convention)
        rf_cols = [c for c in merged.columns if c.startswith("rf_")]
        merged[rf_cols] = merged[rf_cols].fillna(0)

        # Any columns still all-NaN (station with no data in range) → drop
        still_nan = merged.isna().sum()
        all_nan_cols = still_nan[still_nan == len(merged)].index.tolist()
        if all_nan_cols:
            print(f"\n[merge] Dropping columns with no data at all: {all_nan_cols}")
            merged = merged.drop(columns=all_nan_cols)

        # Final remaining NaNs → drop those rows
        before = len(merged)
        merged = merged.dropna()
        after  = len(merged)
        if before != after:
            print(f"[merge] Dropped {before - after:,} rows with "
                  f"unfillable NaNs ({100*(before-after)/before:.1f}%)")

    remaining = merged.isna().sum().sum()
    if remaining > 0:
        raise ValueError(f"Still {remaining} NaNs after all cleaning — "
                         f"check your CSV date range and station coverage.")

    print(f"\n[merged] Shape: {merged.shape} | "
          f"Range: {merged.index.min()} to {merged.index.max()}")
    return merged


# ── Save ─────────────────────────────────────────────────────────────────────
def save_processed(df: pd.DataFrame, name: str):
    path = PROCESSED_DIR / f"{name}.csv"
    df.to_csv(path)
    print(f"[saved] {path}  ({df.shape[0]:,} rows × {df.shape[1]} cols)")
    return path


# ── Main entry ───────────────────────────────────────────────────────────────
def run_pipeline() -> pd.DataFrame:
    print("=" * 60)
    print("AquaWatch | Hydrological Data Pipeline")
    print("=" * 60)

    print("\n[1/4] Generating water-level data ...")
    wl_raw = generate_synthetic_water_level()
    wl     = clean_water_level(wl_raw)
    save_processed(wl, "water_level_clean")

    print("\n[2/4] Generating rainfall data ...")
    rf_raw = generate_synthetic_rainfall()
    rf     = clean_rainfall(rf_raw)
    save_processed(rf, "rainfall_clean")

    print("\n[3/4] Merging ...")
    merged = build_merged_dataset(wl, rf)
    save_processed(merged, "merged_hourly")

    print("\n[4/4] Pipeline complete.")
    return merged


if __name__ == "__main__":
    run_pipeline()
