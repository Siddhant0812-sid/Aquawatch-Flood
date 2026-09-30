"""
AquaWatch — Member 2: ARIMA Baseline
======================================
Fits a per-station ARIMA model and produces 24h/48h/72h forecasts.
Results are saved so LSTM/TFT can be compared against this baseline.

Uses statsmodels auto_arima-style order selection via pmdarima.
Falls back to ARIMA(2,1,2) if pmdarima is unavailable.
"""

import numpy as np
import pandas as pd
import warnings
from pathlib import Path
from typing import Dict, Tuple

warnings.filterwarnings("ignore")
RESULTS_DIR = Path("outputs/arima")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

HORIZONS = [24, 48, 72]   # hours ahead


def _rmse(y_true, y_pred):
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

def _mae(y_true, y_pred):
    return float(np.mean(np.abs(y_true - y_pred)))


def fit_arima_station(train_series: pd.Series,
                      order: Tuple = (2, 1, 2)) -> object:
    """
    Fits ARIMA on a single station's water-level training series.
    Uses pmdarima.auto_arima if available, else fixed order.
    """
    try:
        from pmdarima import auto_arima
        model = auto_arima(train_series, seasonal=False,
                           max_p=4, max_q=4, d=1,
                           information_criterion="aic",
                           suppress_warnings=True, error_action="ignore",
                           stepwise=True)
        print(f"  auto_arima order: {model.order}")
    except ImportError:
        from statsmodels.tsa.arima.model import ARIMA
        model = ARIMA(train_series, order=order).fit()
        print(f"  ARIMA{order} (fixed — install pmdarima for auto selection)")
    return model


def rolling_forecast(model,
                     train_series: pd.Series,
                     test_series: pd.Series,
                     horizon: int = 24) -> np.ndarray:
    """
    Walk-forward rolling forecast:
      - At each test step, refit on all history and predict `horizon` steps.
      - Returns only the h-step-ahead prediction at each test point.

    Note: full rolling refitting is slow for large test sets.
    For speed, we refit every `refit_every` steps.
    """
    refit_every = 24          # refit once per day
    history = list(train_series.values)
    preds = []

    for i in range(len(test_series)):
        if i % refit_every == 0:
            try:
                from pmdarima import auto_arima
                m = auto_arima(history, seasonal=False, stepwise=True,
                               suppress_warnings=True, error_action="ignore")
            except ImportError:
                from statsmodels.tsa.arima.model import ARIMA
                m = ARIMA(history, order=(2, 1, 2)).fit()

        try:
            fc = m.predict(n_periods=horizon) if hasattr(m, "predict") \
                 else m.forecast(horizon)
            preds.append(fc[-1])          # h-th step ahead
        except Exception:
            preds.append(history[-1])     # fallback: last known value

        history.append(test_series.iloc[i])

        if i % 100 == 0:
            print(f"    step {i}/{len(test_series)}", end="\r")

    return np.array(preds)


def evaluate_baseline(splits: Dict,
                      stations: list = None) -> pd.DataFrame:
    """
    Evaluates ARIMA on all stations × all horizons.

    Args:
        splits:   output of feature_engineering.train_val_test_split()
        stations: list of station names (default: all wl_ columns)

    Returns:
        metrics_df: DataFrame with columns [station, horizon_h, RMSE, MAE]
    """
    X_train, y_train = splits["train"]
    X_test,  y_test  = splits["test"]

    # Reconstruct water-level series from feature matrix
    wl_cols = [c for c in X_train.columns if c.startswith("wl_")
               and "_" not in c[3:]]          # raw wl_ columns only
    # Raw wl columns: wl_Guwahati, wl_Tezpur, etc. (no suffix)
    wl_raw_cols = [c for c in X_train.columns
                   if c.startswith("wl_") and c.count("_") == 1]

    if stations is None:
        stations = [c.replace("wl_", "") for c in wl_raw_cols]

    records = []
    for station in stations:
        col = f"wl_{station}"
        if col not in X_train.columns:
            print(f"  [skip] {col} not in features — check column names")
            continue

        print(f"\n[ARIMA] Station: {station}")
        train_s = X_train[col]
        test_s  = X_test[col]

        model = fit_arima_station(train_s)

        for h in HORIZONS:
            print(f"  Forecasting {h}h horizon ...")
            # Trim test to avoid index issues
            test_trimmed = test_s.iloc[:min(500, len(test_s))]
            y_true_col = f"target_{h}h"

            if y_true_col not in y_test.columns:
                continue
            y_true = y_test[y_true_col].iloc[:len(test_trimmed)].values

            preds = rolling_forecast(model, train_s, test_trimmed, horizon=h)
            min_len = min(len(preds), len(y_true))

            rmse = _rmse(y_true[:min_len], preds[:min_len])
            mae  = _mae(y_true[:min_len],  preds[:min_len])

            print(f"    RMSE={rmse:.4f}  MAE={mae:.4f}")
            records.append({"station": station, "horizon_h": h,
                            "RMSE": rmse, "MAE": mae, "model": "ARIMA"})

            # Save per-station per-horizon predictions
            out = pd.DataFrame({
                "datetime":  test_trimmed.index[:min_len],
                "y_true":    y_true[:min_len],
                "y_pred_arima": preds[:min_len],
            })
            out.to_csv(RESULTS_DIR / f"arima_{station}_{h}h.csv", index=False)

    metrics = pd.DataFrame(records)
    metrics.to_csv(RESULTS_DIR / "arima_metrics.csv", index=False)
    print(f"\n[ARIMA] Metrics saved → {RESULTS_DIR}/arima_metrics.csv")
    return metrics


if __name__ == "__main__":
    from data_pipeline import run_pipeline
    from feature_engineering import build_features, get_feature_target_split, train_val_test_split

    merged     = run_pipeline()
    feature_df = build_features(merged)
    X, y       = get_feature_target_split(feature_df, target_station="Guwahati")
    splits     = train_val_test_split(X, y)

    metrics = evaluate_baseline(splits, stations=["Guwahati"])
    print("\nARIMA Baseline Results:")
    print(metrics.to_string(index=False))
