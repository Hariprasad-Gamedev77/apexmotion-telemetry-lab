# Accepted CSV Schema & Unit Conventions

## Overview

ApexMotion Telemetry Lab expects CSV files with columns representing
time-series telemetry data from a single lap. This document describes
the accepted schema, unit conventions, and how column mapping works.

> **All demo data in this application is synthetic.** It is generated
> for demonstration and testing purposes and does not represent real
> Formula 1 or any other real motorsport telemetry.

---

## Required Columns

| Canonical Name | Description | Unit | Example Values |
|---|---|---|---|
| `time_s` | Elapsed time since lap start | seconds | 0.0, 0.1, 0.2 … |
| `distance_m` | Cumulative distance from lap start | metres | 0.0, 10.4, 20.8 … |
| `speed_kmh` | Vehicle speed | km/h | 0.0, 150.5, 310.2 … |

## Optional Columns

| Canonical Name | Description | Unit | Example Values |
|---|---|---|---|
| `throttle_pct` | Throttle position | % (0–100) | 0.0, 50.0, 100.0 |
| `brake_pct` | Brake pressure/position | % (0–100) | 0.0, 30.0, 85.0 |

---

## Column Mapping

Your CSV doesn't need to use our exact column names. We automatically
recognise common alternatives (case-insensitive):

- **Time:** `time`, `time_s`, `time_sec`, `timestamp`, `t`, `elapsed`
- **Distance:** `distance`, `distance_m`, `dist`, `lap_distance`, `dist_m`
- **Speed:** `speed`, `speed_kmh`, `speed_kph`, `velocity`, `vcar`
- **Throttle:** `throttle`, `throttle_pct`, `throttle_pos`, `tps`
- **Brake:** `brake`, `brake_pct`, `brake_pos`, `brake_pressure`

You can also provide an explicit column mapping if your names differ.

---

## Unit Conversions

If your data uses different units, specify the source unit and we
convert automatically:

| Channel | Supported Source Units | Canonical Unit |
|---|---|---|
| Speed | `m/s`, `mph`, `km/h` | km/h |
| Distance | `km`, `ft`, `m` | metres |

**Example:** If your speed is in m/s, pass `unit_overrides={"speed": "m/s"}`.

---

## Data Requirements

1. **Time must increase monotonically** — each sample should have a
   later time than the previous one.
2. **Distance must increase monotonically** — within a single lap,
   distance should always increase.
3. **No duplicate timestamps** — each sample should have a unique time.
4. **Numeric values only** — all columns must contain valid numbers.
5. **At least 10 samples** recommended for meaningful analysis.

Values that violate these rules are flagged by the quality engine but
**never silently modified**.

---

## Plausible Ranges (defaults)

| Channel | Min | Max | Note |
|---|---|---|---|
| `speed_kmh` | 0 | 380 km/h | Values outside are flagged as warnings |
| `throttle_pct` | 0 | 100% | |
| `brake_pct` | 0 | 100% | |
| `time_s` | 0 | 600 s | Up to 10-minute laps |
| `distance_m` | 0 | 25,000 m | Up to 25 km circuits |

These ranges are configurable. Exceeding them produces a **warning**
(heuristic suspicion), not an error.
