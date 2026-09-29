# App Flow Document

## AquaWatch — End-to-End User & System Flow

---

## 1. High-Level User Journey

```mermaid
flowchart TD
    A[User opens Dashboard] --> B[Frontend calls GET /stations]
    B --> C[Map + station list rendered]
    C --> D{User action}
    D -->|Moves date selector| E[Frontend calls GET /segment?date=...]
    E --> F[Flood overlay updated on map]
    F --> D
    D -->|Clicks a station| G[Navigate to Station Detail]
    G --> H[Frontend calls GET /forecast?station_id=...]
    H --> I[72h forecast chart + explainability panel rendered]
    I --> J{User action}
    J -->|Clicks Simulate Alert| K[Frontend calls POST /simulate-alert]
    K --> L[Demo alert message shown]
    J -->|Clicks Back| C
    D -->|Clicks About| M[Static Data Sources panel shown]
```

---

## 2. Detailed Flow: Viewing Current Flood Extent

**Actors:** User, Frontend (React), Backend (FastAPI), Segmentation Model, Earth Engine

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend (FastAPI)
    participant M as Segmentation Model
    participant GEE as Google Earth Engine

    U->>F: Opens Dashboard
    F->>B: GET /stations
    B-->>F: station list (in-memory)
    F->>U: Renders map + station markers

    U->>F: Selects a date on date selector
    F->>B: GET /segment?date=2026-07-30
    alt cached result exists for this date
        B-->>F: SegmentResponse (from in-memory cache)
    else no cached result
        B->>GEE: Query Sentinel-1 tile nearest to requested date
        GEE-->>B: SAR image (VV, VH bands)
        B->>M: Run inference (U-Net)
        M-->>B: predicted mask
        B->>B: Convert mask to GeoJSON, cache in memory
        B-->>F: SegmentResponse
    end
    F->>U: Updates map overlay + shows "Imagery from: [actual acquisition date]"
```

**Key behavior to note:** the "requested date" and "actual imagery acquisition date" can differ, because Sentinel-1 doesn't pass over every day. The response always includes both so the frontend can display the honest imagery age (per UI/UX Design Section 3).

---

## 3. Detailed Flow: Viewing a Station Forecast

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend (FastAPI)
    participant FE as Feature Engineering
    participant FM as Forecasting Model

    U->>F: Clicks a station (e.g. Dibrugarh)
    F->>B: GET /forecast?station_id=dibrugarh
    alt cached result is recent (< refresh interval)
        B-->>F: ForecastResponse (from in-memory cache)
    else cache stale or missing
        B->>FE: Build features from latest rainfall + water-level readings
        FE-->>B: feature vector
        B->>FM: Run inference (LSTM)
        FM-->>B: predictions for 24h / 48h / 72h + attention weights
        B->>B: Map attention weights to top_factors, cache result
        B-->>F: ForecastResponse
    end
    F->>U: Renders forecast chart + risk badge + explainability panel
```

---

## 4. Detailed Flow: Simulated Alert

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend (FastAPI)

    U->>F: Clicks "Simulate Alert" on Station Detail screen
    F->>B: POST /simulate-alert {station_id, risk_score}
    B->>B: Check risk_score against threshold
    alt risk_score >= threshold
        B-->>F: {triggered: true, message: "Simulated alert: HIGH risk..."}
    else risk_score < threshold
        B-->>F: {triggered: false, message: "No alert threshold crossed"}
    end
    F->>U: Shows demo alert banner (clearly labeled as simulation, no real notification sent)
```

---

## 5. System Startup Flow

```mermaid
flowchart TD
    A[Backend process starts] --> B[Load trained U-Net weights into memory]
    B --> C[Load trained LSTM weights into memory]
    C --> D[Load Assam water-level CSV into memory as WaterLevelReading list]
    D --> E[Load Assam/CWC rainfall CSV into memory as RainfallReading list]
    E --> F[Load StationRecord list from station metadata]
    F --> G[FastAPI ready to accept requests]
```

**Important:** because there is no database, all of Steps B–F happen fresh every time the backend process starts. This keeps the system simple but means startup takes a few seconds longer than a database-backed system would (loading CSVs and model weights each time) — an acceptable tradeoff documented in the TRD.

---

## 6. Error / Edge Case Flows

| Scenario | Flow |
|---|---|
| No SAR tile available near requested date (cloud gap / no pass) | `/segment` returns the *nearest available* acquisition date with a flag `"note": "nearest available imagery, X days from requested date"` |
| Station has missing recent water-level readings | `/forecast` uses the last available reading, flags `"data_gap": true` in the response, frontend shows a "data gap" warning instead of hiding the issue |
| Earth Engine authentication expired/fails | Backend returns a 503 with `ErrorResponse {error: "gee_auth_failed", detail: "..."}`; frontend shows a friendly "map data temporarily unavailable" message |
| Backend restarted mid-session | All in-memory caches clear; frontend's next request simply triggers a fresh computation (slightly slower, but functionally correct — no crash) |

---
*Companion to AquaWatch_PRD_Assam.md, TRD.md, UI_UX_DESIGN.md, and BACKEND_SCHEMA.md.*
