# UI/UX Design Document

## AquaWatch — Flood Mapping & Forecasting Dashboard

---

## 1. Design Goals

- Usable by non-GIS-expert disaster management staff (per PRD NFR2) — no specialized training required.
- Communicate uncertainty and data limitations honestly (e.g., satellite revisit gaps) rather than implying false real-time precision.
- Single-screen-first: the most important information (current flood status + near-term risk) visible without scrolling or navigating multiple pages.

## 2. Screens

The application has **three views**, accessible via a top navigation bar:

1. **Dashboard (Home)** — default view, map + summary
2. **Station Detail** — per-station forecast detail
3. **About / Data Sources** — transparency panel listing exact datasets used (ties back to PRD Section 7)

---

## 3. Screen 1 — Dashboard (Home)

```
┌─────────────────────────────────────────────────────────────┐
│  AquaWatch                              [Home] [About]      │
├─────────────────────────────────┬─────────────────────────────┤
│                                  │  RISK SUMMARY               │
│                                  │  ┌───────────────────────┐  │
│                                  │  │ Overall Basin Risk:   │  │
│         MAP VIEW                 │  │   ● MODERATE           │  │
│   (Leaflet — Assam extent)      │  └───────────────────────┘  │
│                                  │                              │
│  - Flood extent overlay          │  STATIONS (list, click →    │
│    (semi-transparent blue)      │  Station Detail view)        │
│  - Station markers               │  ● Dibrugarh   [Rising]     │
│    (color-coded by risk)         │  ● Jorhat      [Stable]     │
│  - Legend (bottom-left)          │  ● Guwahati    [Rising]     │
│                                  │  ...                         │
│  [Date selector: ◀ 2 Aug 2026 ▶]│                              │
│  "Imagery from: 30 Jul 2026      │  [View 72h Forecast Chart]   │
│   (next pass ~6-12 days)"        │                              │
└─────────────────────────────────┴─────────────────────────────┘
```

### Key UI elements
- **Date selector with imagery-age disclosure:** always shows "Imagery from: [date]" next to the map, explicitly surfacing the satellite revisit gap rather than implying live tracking (directly addresses the honesty requirement in PRD Section 4 and TRD Section 8).
- **Color-coded risk markers:** Green (Low) / Yellow (Moderate) / Red (High), consistent across map and station list.
- **Overall Basin Risk badge:** a single aggregated indicator for at-a-glance status, computed as the maximum risk across monitored stations.

## 4. Screen 2 — Station Detail

```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                                          │
│                                                                 │
│  DIBRUGARH STATION                                             │
│  River: Brahmaputra   |   Current Level: 92.6 m               │
│                                                                 │
│  72-HOUR FORECAST                                              │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  [Line chart: predicted water level vs. danger level]   │   │
│  │   ___________________----‾‾‾                            │   │
│  │  now      24h       48h       72h                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                                 │
│  Risk Score: 0.68 (Moderate-High)                              │
│  Contributing factors (explainability):                        │
│   - Rainfall (72h): High influence                              │
│   - Rate of rise: Moderate influence                            │
│                                                                 │
│  [Simulate Alert]  (demo only — no real notification sent)     │
└─────────────────────────────────────────────────────────────┘
```

### Key UI elements
- **Forecast chart with danger-level reference line:** lets users immediately see how close the forecast trend is to the official danger level, not just an abstract number.
- **Explainability panel:** plain-language summary of which factors (rainfall vs. rate-of-rise) drove the forecast — translates the LSTM/TFT attention weights into something non-technical staff can read.
- **"Simulate Alert" button:** clearly labeled as a demo action, not a real notification — avoids misleading users about the system's operational status (per PRD Non-Goals).

## 5. Screen 3 — About / Data Sources

A simple, static panel listing:
- The exact datasets used (mirrors PRD Section 7 / README Data Sources table)
- A plain-language explanation of system limitations (satellite revisit gap, training-data transfer from MMFlood/Sen1Floods11 to Assam, no persistent storage)
- Attribution to government data providers (CWC, IMD, NWIC, ISRO)

This screen exists specifically so evaluators/supervisors can quickly verify data legitimacy without digging through code — directly supporting the transparency goal from earlier project discussions.

---

## 6. Visual Design Guidelines

| Element | Guideline |
|---|---|
| Color palette | Blues/teals for water/flood theme; standard traffic-light (green/yellow/red) reserved strictly for risk indicators, not decorative use |
| Typography | System sans-serif stack (e.g., Inter, Segoe UI, Roboto) for readability; no decorative fonts |
| Map style | Light/neutral basemap so the flood overlay (blue) and risk markers (red/yellow/green) stand out clearly |
| Responsiveness | Two-column dashboard layout collapses to single-column (map on top, summary below) on narrower windows |
| Accessibility | Color-coded risk levels always paired with a text label (e.g., "MODERATE"), never color alone — supports colorblind users |

## 7. User Flow Summary

1. User opens Dashboard → sees map with current flood overlay + station risk list.
2. User optionally moves the date selector to review a recent past pass.
3. User clicks a station → Station Detail view → sees 72h forecast chart and explainability panel.
4. User optionally clicks "Simulate Alert" to see the demo alerting behavior.
5. User can visit "About" at any time to review data sources/limitations.

(Full step-by-step interaction sequence, including backend calls at each step, is detailed in `APP_FLOW.md`.)

---
*Companion to AquaWatch_PRD_Assam.md, TRD.md, BACKEND_SCHEMA.md, and APP_FLOW.md.*
