"""
AquaWatch — Member 2: Explainability & Evaluation
==================================================
Covers:
  1. Attention weight visualization (LSTM proxy + TFT-Lite real attention)
  2. Feature importance (permutation importance on test set)
  3. Model comparison table (ARIMA vs LSTM vs TFT)
  4. Historical event backtest (did the model flag elevated risk?)
  5. Saves all plots to outputs/explainability/
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import Dict

PLOTS_DIR = Path("outputs/explainability")
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

HORIZONS = [24, 48, 72]


# ── 1. Attention weights ─────────────────────────────────────────────────────
def plot_attention_weights(weights: np.ndarray,
                           seq_len: int = 72,
                           model_name: str = "LSTM",
                           save: bool = True):
    """
    Plots normalized per-timestep importance from the last seq_len hours.

    Args:
        weights:    1D array of length seq_len (from get_attention_weights)
        seq_len:    lookback window in hours
        model_name: "LSTM" or "TFT-Lite"
    """
    hours_back = np.arange(-seq_len + 1, 1)   # -71 ... 0

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.fill_between(hours_back, weights, alpha=0.6, color="#1f77b4")
    ax.plot(hours_back, weights, color="#1f77b4", linewidth=1.2)
    ax.axvline(0, color="red", linestyle="--", linewidth=1, label="Now")
    ax.set_xlabel("Hours relative to forecast time")
    ax.set_ylabel("Attention weight")
    ax.set_title(f"{model_name} — Temporal Attention Weights\n"
                 f"(which past hours matter most for the forecast)")
    ax.legend()
    plt.tight_layout()
    if save:
        path = PLOTS_DIR / f"attention_{model_name.lower()}.png"
        fig.savefig(path, dpi=150)
        print(f"[saved] {path}")
    plt.show()
    return fig


# ── 2. Permutation feature importance ────────────────────────────────────────
def permutation_importance(model,
                           te_ds,
                           feature_names: list,
                           n_repeats: int = 3,
                           top_k: int = 20,
                           device=None) -> pd.DataFrame:
    """
    Permutation importance: shuffle each feature, measure MSE increase.
    Higher = more important.
    """
    import torch
    from torch.utils.data import DataLoader

    if device is None:
        device = next(model.parameters()).device

    model.eval()
    dl = DataLoader(te_ds, batch_size=512, shuffle=False)

    def mse_on_loader(dl_):
        losses = []
        with torch.no_grad():
            for xb, yb in dl_:
                pred = model(xb.to(device))
                losses.append(((pred.cpu() - yb) ** 2).mean().item())
        return np.mean(losses)

    baseline = mse_on_loader(dl)
    print(f"[perm_imp] Baseline MSE: {baseline:.5f}")

    records = []
    for fi, fname in enumerate(feature_names):
        scores = []
        for _ in range(n_repeats):
            # Shuffle feature fi across all samples in the dataset
            X_shuffled = te_ds.X.clone()
            idx_perm = torch.randperm(len(X_shuffled))
            X_shuffled[:, :, fi] = X_shuffled[idx_perm, :, fi]

            # Temporary dataset with shuffled feature
            from torch.utils.data import TensorDataset
            tmp_ds = TensorDataset(X_shuffled, te_ds.y)
            tmp_dl = DataLoader(tmp_ds, batch_size=512, shuffle=False)
            scores.append(mse_on_loader(tmp_dl))

        importance = np.mean(scores) - baseline
        records.append({"feature": fname, "importance": importance})

        if fi % 10 == 0:
            print(f"  {fi}/{len(feature_names)} features done", end="\r")

    df = pd.DataFrame(records).sort_values("importance", ascending=False)
    top = df.head(top_k)

    fig, ax = plt.subplots(figsize=(9, top_k * 0.35 + 1))
    ax.barh(top["feature"][::-1], top["importance"][::-1], color="#2ca02c")
    ax.set_xlabel("MSE increase when feature shuffled\n(higher = more important)")
    ax.set_title(f"Top {top_k} Feature Importances (Permutation)")
    plt.tight_layout()
    path = PLOTS_DIR / "feature_importance.png"
    fig.savefig(path, dpi=150)
    print(f"\n[saved] {path}")
    plt.show()

    df.to_csv(PLOTS_DIR / "feature_importance.csv", index=False)
    return df


# ── 3. Model comparison table ────────────────────────────────────────────────
def compare_models(save: bool = True) -> pd.DataFrame:
    """
    Loads ARIMA, LSTM, TFT metrics and produces a unified comparison table.
    """
    frames = []
    for path in [
        Path("outputs/arima/arima_metrics.csv"),
        Path("outputs/lstm/lstm_metrics.csv"),
        Path("outputs/tft/tft_metrics.csv"),
    ]:
        if path.exists():
            frames.append(pd.read_csv(path))
        else:
            print(f"[warn] {path} not found — run that model first")

    if not frames:
        print("[compare] No results found yet.")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    pivot    = combined.pivot_table(index=["model", "horizon_h"],
                                    values=["RMSE", "MAE"],
                                    aggfunc="mean").round(4)
    print("\n" + "=" * 50)
    print("MODEL COMPARISON: RMSE & MAE per Horizon")
    print("=" * 50)
    print(pivot.to_string())

    if save:
        pivot.to_csv(PLOTS_DIR / "model_comparison.csv")
        print(f"\n[saved] {PLOTS_DIR}/model_comparison.csv")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, metric in zip(axes, ["RMSE", "MAE"]):
        for model_name, grp in combined.groupby("model"):
            ax.plot(grp["horizon_h"], grp[metric], marker="o",
                    label=model_name)
        ax.set_xlabel("Forecast Horizon (hours)")
        ax.set_ylabel(metric)
        ax.set_title(f"{metric} by Horizon")
        ax.legend()
        ax.set_xticks(HORIZONS)
    plt.suptitle("AquaWatch Forecasting Model Comparison", fontweight="bold")
    plt.tight_layout()
    path = PLOTS_DIR / "model_comparison.png"
    fig.savefig(path, dpi=150)
    print(f"[saved] {path}")
    plt.show()
    return combined


# ── 4. Historical event backtest ─────────────────────────────────────────────
def historical_backtest(feature_df: pd.DataFrame,
                        model,
                        x_scaler,
                        y_scaler,
                        feature_names: list,
                        station: str = "Guwahati",
                        flood_threshold: float = 51.0,
                        event_window: tuple = ("2022-06-01", "2022-09-30"),
                        seq_len: int = 72,
                        device=None):
    """
    Backtest: run LSTM/TFT on a historical monsoon window and check
    whether 24h/72h predictions flag the water level rising above threshold
    BEFORE the actual peak.

    This is the 'correctly flag elevated risk ahead of a known past Assam flood'
    evaluation criterion in the project spec.
    """
    import torch

    if device is None:
        device = next(model.parameters()).device

    start, end = event_window
    window_df  = feature_df.loc[start:end].copy()

    wl_col = f"wl_{station}"

    # Use EXACTLY the same features and order used during LSTM training
    feat_cols = feature_names

    # Check that all training features exist in the historical window
    missing_cols = [c for c in feat_cols if c not in window_df.columns]

    if missing_cols:
        raise ValueError(
            f"Historical backtest is missing {len(missing_cols)} "
            f"training features: {missing_cols}"
        )

    X_np = x_scaler.transform(
        window_df[feat_cols].values.astype(np.float32)
    )
    X_t  = torch.tensor(X_np, dtype=torch.float32)

    model.eval()
    preds_scaled = []
    with torch.no_grad():
        for i in range(seq_len, len(X_t)):
            seq = X_t[i - seq_len: i].unsqueeze(0).to(device)
            preds_scaled.append(model(seq).cpu().numpy())

    if not preds_scaled:
        print("[backtest] Window too short for seq_len")
        return

    preds_s  = np.concatenate(preds_scaled, axis=0)
    preds    = y_scaler.inverse_transform(preds_s)
    time_idx = window_df.index[seq_len:]
    actual   = window_df[wl_col].values[seq_len:]

    fig, axes = plt.subplots(len(HORIZONS), 1, figsize=(14, 4 * len(HORIZONS)),
                             sharex=True)
    for ax, (i, h) in zip(axes, enumerate(HORIZONS)):
        ax.plot(time_idx, actual, color="steelblue",
                linewidth=1.2, label="Actual water level")
        ax.plot(time_idx, preds[:, i], color="darkorange",
                linewidth=1, linestyle="--", label=f"Predicted (+{h}h)")
        ax.axhline(flood_threshold, color="red", linestyle=":",
                   linewidth=1.5, label=f"Flood threshold ({flood_threshold}m)")

        # Shade flood periods
        flood_mask = actual > flood_threshold
        ax.fill_between(time_idx, actual.min(), actual.max(),
                        where=flood_mask, alpha=0.15, color="red",
                        label="Actual flood period")

        ax.set_ylabel("Water level (m)")
        ax.set_title(f"{h}h ahead forecast — {station}")
        ax.legend(loc="upper left", fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))

    plt.suptitle(f"Historical Backtest: {start} → {end}\n"
                 f"Station: {station}", fontweight="bold")
    plt.xticks(rotation=30)
    plt.tight_layout()
    path = PLOTS_DIR / f"backtest_{station}_{start[:4]}.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    print(f"[saved] {path}")
    plt.show()

    # Quantify lead time
    for i, h in enumerate(HORIZONS):
        actual_flood_start = (actual > flood_threshold).argmax()
        pred_flood_start   = (preds[:, i] > flood_threshold).argmax()
        if actual_flood_start > 0 and pred_flood_start > 0:
            lead = actual_flood_start - pred_flood_start
            print(f"  {h}h horizon: model flagged flood {lead}h "
                  f"{'before' if lead > 0 else 'after'} actual onset")


if __name__ == "__main__":
    # Compare all trained models
    compare_models()
