"""
AquaWatch — Member 2: Feature Engineering
==========================================
Transforms the merged hourly DataFrame into model-ready features.

Features created:
  - Rolling rainfall windows  (3h, 6h, 12h, 24h, 48h, 72h)
  - Rate-of-rise              (water level delta over 1h, 3h, 6h)
  - Lag features              (water level: 1h, 3h, 6h, 12h, 24h lags)
  - Antecedent soil moisture proxy (30-day cumulative rainfall)
  - Calendar features         (hour-of-day, day-of-year, month)
  - Flood label               (binary: water level > station threshold)
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── Station flood thresholds (metres) ────────────────────────────────────────
# Based on CWC danger level for each gauge station.
# REAL DATA SWAP: replace with actual CWC danger-level values per station.
FLOOD_THRESHOLDS: Dict[str, float] = {
    "NH15 Crossing Dhansirighat":     5.0,   # placeholder — replace with real danger level
    "NH15 Crossing Fakirpara Tangni": 4.5,   # placeholder
    "NH17 Crossing Boko":             4.0,   # placeholder
}

# Rolling window sizes (hours)
RF_WINDOWS  = [3, 6, 12, 24, 48, 72]
WL_LAG_HRS  = [1, 3, 6, 12, 24]
ROR_WINDOWS = [1, 3, 6]          # rate-of-rise deltas


def _rolling_rainfall_features(merged: pd.DataFrame) -> pd.DataFrame:
    """Cumulative rainfall over multiple look-back windows for every station."""
    rf_cols = [c for c in merged.columns if c.startswith("rf_")]
    frames = []
    for w in RF_WINDOWS:
        roll = merged[rf_cols].rolling(window=w, min_periods=1).sum()
        roll.columns = [f"{c}_sum{w}h" for c in rf_cols]
        frames.append(roll)
    return pd.concat(frames, axis=1)


def _rate_of_rise_features(merged: pd.DataFrame) -> pd.DataFrame:
    """Water level delta (m/hr) over short windows — key flood onset signal."""
    wl_cols = [c for c in merged.columns if c.startswith("wl_")]
    frames = []
    for w in ROR_WINDOWS:
        delta = merged[wl_cols].diff(periods=w) / w    # m per hour
        delta.columns = [f"{c}_ror{w}h" for c in wl_cols]
        frames.append(delta)
    return pd.concat(frames, axis=1)


def _lag_features(merged: pd.DataFrame) -> pd.DataFrame:
    """Past water-level readings as autoregressive features."""
    wl_cols = [c for c in merged.columns if c.startswith("wl_")]
    frames = []
    for lag in WL_LAG_HRS:
        lagged = merged[wl_cols].shift(lag)
        lagged.columns = [f"{c}_lag{lag}h" for c in wl_cols]
        frames.append(lagged)
    return pd.concat(frames, axis=1)


def _antecedent_moisture(merged: pd.DataFrame) -> pd.DataFrame:
    """30-day cumulative rainfall proxy for soil saturation."""
    rf_cols = [c for c in merged.columns if c.startswith("rf_")]
    roll30 = merged[rf_cols].rolling(window=30 * 24, min_periods=1).sum()
    roll30.columns = [f"{c}_asm30d" for c in rf_cols]
    return roll30


def _calendar_features(merged: pd.DataFrame) -> pd.DataFrame:
    """Encode time as cyclic features (hour, doy, month)."""
    idx = merged.index
    hour_sin = np.sin(2 * np.pi * idx.hour / 24)
    hour_cos = np.cos(2 * np.pi * idx.hour / 24)
    doy_sin  = np.sin(2 * np.pi * idx.day_of_year / 365)
    doy_cos  = np.cos(2 * np.pi * idx.day_of_year / 365)
    month_sin = np.sin(2 * np.pi * idx.month / 12)
    month_cos = np.cos(2 * np.pi * idx.month / 12)
    return pd.DataFrame({
        "cal_hour_sin":  hour_sin,
        "cal_hour_cos":  hour_cos,
        "cal_doy_sin":   doy_sin,
        "cal_doy_cos":   doy_cos,
        "cal_month_sin": month_sin,
        "cal_month_cos": month_cos,
    }, index=merged.index)


def _flood_labels(merged: pd.DataFrame) -> pd.DataFrame:
    """Binary flood labels per station (1 = above danger level)."""
    labels = {}
    for station, threshold in FLOOD_THRESHOLDS.items():
        col = f"wl_{station}"
        if col in merged.columns:
            labels[f"flood_{station}"] = (merged[col] > threshold).astype(int)
    return pd.DataFrame(labels, index=merged.index)


def build_features(merged: pd.DataFrame,
                   drop_warmup: int = 72 * 30) -> pd.DataFrame:
    """
    Full feature engineering pipeline.

    Args:
        merged:       Output of data_pipeline.build_merged_dataset()
        drop_warmup:  Drop first N rows so rolling windows are fully populated
                      (default: 30 days @ hourly = 720 rows)

    Returns:
        feature_df:   All features + raw columns + flood labels, no NaNs
    """
    print("[features] Computing rolling rainfall ...")
    rf_feat  = _rolling_rainfall_features(merged)

    print("[features] Computing rate-of-rise ...")
    ror_feat = _rate_of_rise_features(merged)

    print("[features] Computing lag features ...")
    lag_feat = _lag_features(merged)

    print("[features] Computing antecedent soil moisture ...")
    asm_feat = _antecedent_moisture(merged)

    print("[features] Computing calendar features ...")
    cal_feat = _calendar_features(merged)

    print("[features] Computing flood labels ...")
    labels   = _flood_labels(merged)

    full = pd.concat([merged, rf_feat, ror_feat, lag_feat,
                      asm_feat, cal_feat, labels], axis=1)

    # Drop warm-up rows where rolling/lag features are incomplete
    full = full.iloc[drop_warmup:].copy()
    full = full.dropna()

    print(f"[features] Final shape: {full.shape}")
    print(f"[features] Feature columns: {full.shape[1]}")
    return full


def get_feature_target_split(
    feature_df: pd.DataFrame,
    target_station: str = "Guwahati",
    horizons: list = [24, 48, 72],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits feature_df into:
      X  — all feature columns (excludes targets)
      y  — multi-horizon water-level targets for one station

    Args:
        target_station: which station to forecast
        horizons:       forecast horizons in hours [24, 48, 72]

    Returns:
        X, y (aligned DataFrames)
    """
    target_col = f"wl_{target_station}"
    assert target_col in feature_df.columns, \
        f"{target_col} not found in feature_df"

    # Build multi-step targets by shifting backwards
    y = pd.DataFrame(index=feature_df.index)
    for h in horizons:
        y[f"target_{h}h"] = feature_df[target_col].shift(-h)

    # Drop rows where any target is NaN (end of series)
    valid = y.dropna().index
    X = feature_df.loc[valid].copy()
    y = y.loc[valid].copy()

    # Remove target column from X (avoid leakage)
    target_cols = [c for c in X.columns if c.startswith("target_")]
    X = X.drop(columns=target_cols, errors="ignore")

    print(f"[split] X: {X.shape}  |  y: {y.shape}")
    return X, y


def train_val_test_split(
    X: pd.DataFrame,
    y: pd.DataFrame,
    val_ratio: float = 0.10,
    test_ratio: float = 0.15,
) -> Tuple:
    """
    Chronological (non-shuffled) train/val/test split.
    Default: 75% train / 10% val / 15% test
    """
    n = len(X)
    n_test = int(n * test_ratio)
    n_val  = int(n * val_ratio)
    n_train = n - n_val - n_test

    splits = {
        "train": (X.iloc[:n_train],           y.iloc[:n_train]),
        "val":   (X.iloc[n_train:n_train+n_val], y.iloc[n_train:n_train+n_val]),
        "test":  (X.iloc[n_train+n_val:],     y.iloc[n_train+n_val:]),
    }
    for k, (Xs, ys) in splits.items():
        print(f"[split] {k:5s}: {len(Xs):,} rows "
              f"({Xs.index.min().date()} to {Xs.index.max().date()})")
    return splits


if __name__ == "__main__":
    from data_pipeline import run_pipeline
    merged = run_pipeline()

    feature_df = build_features(merged)
    feature_df.to_csv(PROCESSED_DIR / "features.csv")
    print(f"\nSaved features.csv")

    X, y = get_feature_target_split(feature_df, target_station="Guwahati")
    splits = train_val_test_split(X, y)