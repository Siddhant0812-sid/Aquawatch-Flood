"""
AquaWatch — Member 2: LSTM Forecasting Model
=============================================
Multi-step (24h / 48h / 72h) water-level forecasting using LSTM.

Architecture:
  - Stacked 2-layer LSTM with dropout
  - Multi-output head (one output per horizon)
  - MinMax-scaled inputs
  - Sequence-to-vector: sliding window of past `seq_len` hours → 3 targets

Training:
  - AdamW optimizer, ReduceLROnPlateau scheduler
  - Early stopping on validation loss
  - Saves best checkpoint automatically
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
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

from pathlib import Path
from typing import Tuple, Dict
import json

MODELS_DIR  = Path("models")
RESULTS_DIR = Path("outputs/lstm")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

HORIZONS  = [24, 48, 72]
DEVICE    = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── Dataset ──────────────────────────────────────────────────────────────────
class FloodSequenceDataset(Dataset):
    """
    Sliding-window dataset.
    Each sample: (X[t-seq_len : t], y[t+h] for h in horizons)
    """
    def __init__(self, X: np.ndarray, y: np.ndarray, seq_len: int = 72):
        self.X       = torch.tensor(X, dtype=torch.float32)
        self.y       = torch.tensor(y, dtype=torch.float32)
        self.seq_len = seq_len

    def __len__(self):
        return len(self.X) - self.seq_len

    def __getitem__(self, idx):
        x_seq = self.X[idx : idx + self.seq_len]          # (seq_len, n_feat)
        y_tgt = self.y[idx + self.seq_len - 1]            # (n_horizons,)
        return x_seq, y_tgt


# ── Model ────────────────────────────────────────────────────────────────────
class FloodLSTM(nn.Module):
    """
    2-layer stacked LSTM with multi-horizon output head.

    Args:
        input_size:   number of features
        hidden_size:  LSTM hidden dim (default 128)
        num_layers:   number of stacked LSTM layers (default 2)
        dropout:      dropout between layers (default 0.3)
        n_horizons:   number of forecast horizons (default 3)
    """
    def __init__(self, input_size: int, hidden_size: int = 128,
                 num_layers: int = 2, dropout: float = 0.3,
                 n_horizons: int = 3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Linear(64, n_horizons),
        )

    def forward(self, x):
        # x: (batch, seq_len, input_size)
        out, _ = self.lstm(x)          # out: (batch, seq_len, hidden)
        last    = out[:, -1, :]        # take last timestep
        return self.head(last)         # (batch, n_horizons)


# ── Scaler helpers ───────────────────────────────────────────────────────────
def fit_scalers(X_train: np.ndarray,
                y_train: np.ndarray) -> Tuple[MinMaxScaler, MinMaxScaler]:
    x_scaler = MinMaxScaler()
    y_scaler = MinMaxScaler()
    x_scaler.fit(X_train)
    y_scaler.fit(y_train)
    return x_scaler, y_scaler


# ── Training loop ────────────────────────────────────────────────────────────
def train_lstm(splits: Dict,
               seq_len: int = 72,
               hidden_size: int = 128,
               num_layers: int = 2,
               dropout: float = 0.3,
               lr: float = 1e-3,
               batch_size: int = 256,
               max_epochs: int = 50,
               patience: int = 7) -> Tuple[FloodLSTM, dict]:
    """
    Full training routine.

    Returns:
        model:    best trained FloodLSTM
        history:  dict of train/val loss per epoch
    """
    print(f"[LSTM] Device: {DEVICE}")

    X_tr, y_tr = splits["train"]
    X_va, y_va = splits["val"]
    X_te, y_te = splits["test"]

    # Convert to numpy
    X_tr_np = X_tr.values.astype(np.float32)
    y_tr_np = y_tr.values.astype(np.float32)
    X_va_np = X_va.values.astype(np.float32)
    y_va_np = y_va.values.astype(np.float32)
    X_te_np = X_te.values.astype(np.float32)
    y_te_np = y_te.values.astype(np.float32)

    # Scale
    x_scaler, y_scaler = fit_scalers(X_tr_np, y_tr_np)
    X_tr_s = x_scaler.transform(X_tr_np)
    X_va_s = x_scaler.transform(X_va_np)
    X_te_s = x_scaler.transform(X_te_np)
    y_tr_s = y_scaler.transform(y_tr_np)
    y_va_s = y_scaler.transform(y_va_np)

    # Datasets & loaders
    tr_ds = FloodSequenceDataset(X_tr_s, y_tr_s, seq_len)
    va_ds = FloodSequenceDataset(X_va_s, y_va_s, seq_len)
    te_ds = FloodSequenceDataset(X_te_s, y_te_np, seq_len)   # raw y for eval

    tr_dl = DataLoader(tr_ds, batch_size=batch_size, shuffle=True,
                       num_workers=0, pin_memory=(DEVICE.type == "cuda"))
    va_dl = DataLoader(va_ds, batch_size=batch_size, shuffle=False,
                       num_workers=0)

    # Model
    n_feat = X_tr_s.shape[1]
    model  = FloodLSTM(input_size=n_feat, hidden_size=hidden_size,
                       num_layers=num_layers, dropout=dropout,
                       n_horizons=len(HORIZONS)).to(DEVICE)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr,
                                  weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=3)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_epoch    = 0
    patience_ctr  = 0
    history       = {"train_loss": [], "val_loss": []}

    print(f"[LSTM] Model params: {sum(p.numel() for p in model.parameters()):,}")
    print(f"[LSTM] Training {max_epochs} epochs | batch={batch_size} | seq={seq_len}")

    for epoch in range(1, max_epochs + 1):
        # ── train ──
        model.train()
        tr_losses = []
        for xb, yb in tr_dl:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            tr_losses.append(loss.item())

        # ── val ──
        model.eval()
        va_losses = []
        with torch.no_grad():
            for xb, yb in va_dl:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                va_losses.append(criterion(model(xb), yb).item())

        tr_loss = np.mean(tr_losses)
        va_loss = np.mean(va_losses)
        history["train_loss"].append(tr_loss)
        history["val_loss"].append(va_loss)
        scheduler.step(va_loss)

        print(f"  Epoch {epoch:3d}/{max_epochs}  "
              f"train={tr_loss:.5f}  val={va_loss:.5f}")

        if va_loss < best_val_loss:
            best_val_loss = va_loss
            best_epoch    = epoch
            patience_ctr  = 0
            pt_target = MODELS_DIR / "lstm_best.pt"
            if pt_target.exists():
                try:
                    pt_target.unlink()
                except Exception:
                    pass
            torch.save(model.state_dict(), pt_target)
        else:
            patience_ctr += 1
            if patience_ctr >= patience:
                print(f"  [early stop] best epoch={best_epoch}")
                break

    # Load best weights
    model.load_state_dict(torch.load(MODELS_DIR / "lstm_best.pt",
                                     map_location=DEVICE))

    # ── Evaluate on test set ──
    print("\n[LSTM] Evaluating on test set ...")
    metrics = evaluate_lstm(model, te_ds, y_scaler, X_te_np, y_te_np)
    pd.DataFrame(metrics).to_csv(RESULTS_DIR / "lstm_metrics.csv", index=False)

    # Save history
    with open(RESULTS_DIR / "lstm_history.json", "w") as f:
        json.dump(history, f)

    # Save scaler params for inference
    np.save(MODELS_DIR / "x_scaler_params.npy",
            [x_scaler.data_min_, x_scaler.data_max_], allow_pickle=True)
    np.save(MODELS_DIR / "y_scaler_params.npy",
            [y_scaler.data_min_, y_scaler.data_max_], allow_pickle=True)

    return model, history


def evaluate_lstm(model: FloodLSTM,
                  te_ds: FloodSequenceDataset,
                  y_scaler: MinMaxScaler,
                  X_te_np: np.ndarray,
                  y_te_np: np.ndarray) -> list:
    """Run inference on test set; compute RMSE & MAE per horizon."""
    te_dl = DataLoader(te_ds, batch_size=512, shuffle=False)
    model.eval()
    all_preds_scaled = []

    with torch.no_grad():
        for xb, _ in te_dl:
            pred = model(xb.to(DEVICE)).cpu().numpy()
            all_preds_scaled.append(pred)

    preds_scaled = np.concatenate(all_preds_scaled, axis=0)
    preds        = y_scaler.inverse_transform(preds_scaled)
    y_true       = y_te_np[te_ds.seq_len - 1 : te_ds.seq_len - 1 + len(preds)]

    records = []
    for i, h in enumerate(HORIZONS):
        rmse = float(np.sqrt(np.mean((y_true[:, i] - preds[:, i]) ** 2)))
        mae  = float(np.mean(np.abs(y_true[:, i]  - preds[:, i])))
        print(f"  {h}h -> RMSE={rmse:.4f}  MAE={mae:.4f}")
        records.append({"horizon_h": h, "RMSE": rmse, "MAE": mae, "model": "LSTM"})

        # Save predictions for dashboard / backtest
        pd.DataFrame({
            "y_true": y_true[:, i], "y_pred_lstm": preds[:, i]
        }).to_csv(RESULTS_DIR / f"lstm_preds_{h}h.csv", index=False)

    return records


def get_attention_weights(model: FloodLSTM,
                          x_seq: torch.Tensor) -> np.ndarray:
    """
    Proxy attention: returns per-timestep hidden-state L2 norm as
    an importance signal (real attention requires attention LSTM variant).
    Used for explainability visualizations.
    """
    model.eval()
    with torch.no_grad():
        x = x_seq.unsqueeze(0).to(DEVICE)        # (1, seq, feat)
        out, _ = model.lstm(x)                    # (1, seq, hidden)
        norms = out.squeeze(0).norm(dim=-1)       # (seq,)
        weights = (norms / norms.sum()).cpu().numpy()
    return weights


if __name__ == "__main__":
    from data_pipeline import run_pipeline
    from feature_engineering import (build_features, get_feature_target_split,
                                     train_val_test_split)

    merged     = run_pipeline()
    feature_df = build_features(merged)
    X, y       = get_feature_target_split(feature_df, target_station="Guwahati")
    splits     = train_val_test_split(X, y)

    model, history = train_lstm(splits, max_epochs=30)
    print("\nDone. Model saved to models/lstm_best.pt")
