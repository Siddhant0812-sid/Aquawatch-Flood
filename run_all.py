"""
AquaWatch — Hydrological Forecasting Pipeline Runner
===================================================
Run this to execute the full forecasting pipeline end-to-end:

    python run_all.py

Stages:
  1. Data pipeline  (synthetic → processed CSVs)
  2. Feature engineering
  3. ARIMA baseline
  4. LSTM training + evaluation
  5. TFT-Lite training + evaluation
  6. Model comparison + explainability plots
  7. Historical backtest

Tip: to skip a stage, set its flag to False below.
"""

import os
import sys
from pathlib import Path

RUN_ARIMA = True
RUN_LSTM  = True
RUN_TFT   = True
RUN_EXPL  = True

TARGET_STATION = "NH15 Crossing Dhansirighat"   # change to any of your 3 stations
SEQ_LEN        = 72
MAX_EPOCHS     = 30     # increase to 50+ for real training

# Must match what's in feature_engineering.py FLOOD_THRESHOLDS
FLOOD_THRESHOLDS = {
    "NH15 Crossing Dhansirighat":     5.0,
    "NH15 Crossing Fakirpara Tangni": 4.5,
    "NH17 Crossing Boko":             4.0,
}

PROJECT_ROOT = Path(__file__).resolve().parent
MODELS_DIR = PROJECT_ROOT / "models"
if str(MODELS_DIR) not in sys.path:
    sys.path.insert(0, str(MODELS_DIR))


def main():
    # Model modules use project-relative data/output paths.  Normalize the
    # working directory so this script behaves the same from root or backend.
    os.chdir(PROJECT_ROOT)
    # Keep importing the launcher lightweight; these are only needed by
    # training/explainability stages and are not required to discover paths.
    import numpy as np
    import torch
    try:
        from sklearn.preprocessing import MinMaxScaler
    except (ImportError, Exception):
        class MinMaxScaler:
            """Robust pure-Python / NumPy fallback for MinMaxScaler.
            Avoids C-extension DLL crashes on Windows with App Control policies.
            """
            def __init__(self, feature_range=(0, 1), copy=True, clip=False):
                self.feature_range = feature_range
                self.copy = copy
                self.clip = clip
                self.data_min_ = None
                self.data_max_ = None
                self.min_ = None
                self.scale_ = None
    
            def fit(self, X, y=None):
                X = np.asarray(X)
                self.data_min_ = np.nanmin(X, axis=0)
                self.data_max_ = np.nanmax(X, axis=0)
                diff = self.data_max_ - self.data_min_
                diff[diff == 0.0] = 1.0
                self.scale_ = (self.feature_range[1] - self.feature_range[0]) / diff
                self.min_ = self.feature_range[0] - self.data_min_ * self.scale_
                return self
    
            def transform(self, X):
                X = np.asarray(X)
                res = X * self.scale_ + self.min_
                if self.clip:
                    res = np.clip(res, self.feature_range[0], self.feature_range[1])
                return res
    
            def fit_transform(self, X, y=None):
                return self.fit(X, y).transform(X)
    
            def inverse_transform(self, X):
                X = np.asarray(X)
                return (X - self.min_) / self.scale_
    
    print("  AquaWatch Full Pipeline")

    # ── 1. Data ──────────────────────────────────────────────────
    from data_pipeline import run_pipeline
    merged = run_pipeline()

    # ── 2. Features ──────────────────────────────────────────────
    from feature_engineering import (build_features, get_feature_target_split,
                                     train_val_test_split)
    print("\n[STAGE 2] Feature engineering ...")
    feature_df = build_features(merged)
    X, y       = get_feature_target_split(feature_df, target_station=TARGET_STATION)
    splits     = train_val_test_split(X, y)
    feature_names = list(X.columns)

    # ── 3. ARIMA ─────────────────────────────────────────────────
    if RUN_ARIMA:
        print("\n[STAGE 3] ARIMA baseline ...")
        from baseline_arima import evaluate_baseline
        arima_metrics = evaluate_baseline(splits, stations=[TARGET_STATION])

    # ── 4. LSTM ──────────────────────────────────────────────────
    lstm_model = None
    if RUN_LSTM:
        print("\n[STAGE 4] LSTM training ...")
        from model_lstm import train_lstm, fit_scalers, FloodSequenceDataset
        lstm_model, lstm_history = train_lstm(
            splits, seq_len=SEQ_LEN, max_epochs=MAX_EPOCHS)

    # ── 5. TFT ───────────────────────────────────────────────────
    tft_model = None
    if RUN_TFT:
        print("\n[STAGE 5] TFT-Lite training ...")
        from model_tft import train_tft
        tft_model, tft_history = train_tft(
            splits, seq_len=SEQ_LEN, max_epochs=MAX_EPOCHS)

    # ── 6. Explainability & comparison ───────────────────────────
    if RUN_EXPL:
        print("\n[STAGE 6] Explainability & model comparison ...")
        from explainability import (compare_models, plot_attention_weights,
                                    historical_backtest)

        # Model comparison table + plot
        compare_models()

        # Attention weights
        if lstm_model is not None:
            import torch
            from model_lstm import get_attention_weights
            # Build a sample sequence from test set
            X_te = splits["test"][0].values.astype(np.float32)
            x_sc = MinMaxScaler().fit(splits["train"][0].values.astype(np.float32))
            X_te_s = x_sc.transform(X_te)
            sample = torch.tensor(X_te_s[:SEQ_LEN], dtype=torch.float32)
            weights_lstm = get_attention_weights(lstm_model, sample)
            plot_attention_weights(weights_lstm, seq_len=SEQ_LEN, model_name="LSTM")

        if tft_model is not None:
            import torch
            device = next(tft_model.parameters()).device
            x_sc = MinMaxScaler().fit(splits["train"][0].values.astype(np.float32))
            X_te_s = x_sc.transform(splits["test"][0].values.astype(np.float32))
            sample = torch.tensor(X_te_s[:SEQ_LEN], dtype=torch.float32)
            tft_model.eval()
            with torch.no_grad():
                tft_model(sample.unsqueeze(0).to(device))
            weights_tft = tft_model.get_attention_weights()
            if weights_tft is not None:
                plot_attention_weights(weights_tft, seq_len=SEQ_LEN,
                                       model_name="TFT-Lite")

    # ── 7. Historical backtest ────────────────────────────────────
    if RUN_EXPL and lstm_model is not None:
        print("\n[STAGE 7] Historical event backtest ...")
        from explainability import historical_backtest

        x_sc_fit = MinMaxScaler().fit(splits["train"][0].values.astype(np.float32))
        y_sc_fit = MinMaxScaler().fit(splits["train"][1].values.astype(np.float32))

        historical_backtest(
            feature_df      = feature_df,
            model           = lstm_model,
            x_scaler        = x_sc_fit,
            y_scaler        = y_sc_fit,
            feature_names   = feature_names,
            station         = TARGET_STATION,
            flood_threshold = FLOOD_THRESHOLDS[TARGET_STATION],
            event_window    = ("2022-06-01", "2022-09-30"),   # 2022 monsoon
            seq_len         = SEQ_LEN,
        )

    print("  All stages complete. Check outputs/ for results.")


if __name__ == "__main__":
    main()