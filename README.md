# AquaWatch — Member 2: Rainfall & Water-Level Forecasting

## File Map

```
aquawatch_member2/
├── data_pipeline.py        ← Stage 1: load/clean/merge data
├── feature_engineering.py  ← Stage 2: rolling windows, lags, labels
├── baseline_arima.py       ← Stage 3: ARIMA baseline
├── model_lstm.py           ← Stage 4: LSTM (primary model)
├── model_tft.py            ← Stage 5: TFT-Lite (comparison model)
├── explainability.py       ← Stage 6: attention viz, feature importance, backtest
├── api.py                  ← Stage 7: FastAPI endpoints for dashboard
└── run_all.py              ← Master script: runs everything
```

## Quick Start

```bash
pip install torch pandas numpy scikit-learn statsmodels fastapi uvicorn matplotlib
# optional but recommended:
pip install pmdarima   # for auto ARIMA order selection

python run_all.py      # runs full pipeline with synthetic data
```

## Swapping in Real NWDP Data

Search all files for `# REAL DATA SWAP` — there are exactly 2 swap points:

**`data_pipeline.py` → `generate_synthetic_water_level()`:**
```python
df = pd.read_csv("data/raw/water_level_assam.csv",
                 parse_dates=["datetime"], index_col="datetime")
df = df[STATIONS["water_level"]]
df = df.asfreq("1H")
return df
```

**`data_pipeline.py` → `generate_synthetic_rainfall()`:**
```python
df = pd.read_csv("data/raw/rainfall_cwc_assam.csv",
                 parse_dates=["datetime"], index_col="datetime")
df = df[STATIONS["rainfall"]]
df = df.asfreq("1H").fillna(0)
return df
```

Your CSV must have:
- Column `datetime` as the index (hourly)  
- One column per station (name must match `STATIONS` dict)

## What Each Stage Produces

| Stage | Output |
|---|---|
| data_pipeline | `data/processed/water_level_clean.csv`, `rainfall_clean.csv`, `merged_hourly.csv` |
| feature_engineering | `data/processed/features.csv` |
| baseline_arima | `outputs/arima/arima_metrics.csv`, per-station prediction CSVs |
| model_lstm | `models/lstm_best.pt`, `outputs/lstm/lstm_metrics.csv`, prediction CSVs |
| model_tft | `models/tft_best.pt`, `outputs/tft/tft_metrics.csv`, prediction CSVs |
| explainability | `outputs/explainability/model_comparison.png`, attention plots, backtest plot |
| api | FastAPI service on port 8001 |

## API for Member 3 (Dashboard)

```
GET  /health            → health check
GET  /stations          → current risk level for all 5 stations
POST /forecast          → 24h/48h/72h prediction for one station
GET  /risk              → compact risk summary (for alert banner)
GET  /history/{station} → last 7 days timeseries (for charts)
```

Start the API:
```bash
uvicorn api:app --reload --port 8001
```

Example request:
```bash
curl -X POST http://localhost:8001/forecast \
  -H "Content-Type: application/json" \
  -d '{"station": "Guwahati", "horizon_hours": [24, 48, 72]}'
```

## Evaluation Targets (from project spec)

| Metric | Target |
|---|---|
| RMSE (24h) | < ARIMA baseline |
| RMSE (48h) | < ARIMA baseline |
| RMSE (72h) | < ARIMA baseline |
| Backtest | Flags elevated risk ahead of known 2022 Assam flood |

Results are printed by `run_all.py` and saved to `outputs/explainability/model_comparison.csv`.
