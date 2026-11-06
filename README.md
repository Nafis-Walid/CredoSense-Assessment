# Agricultural IoT Monitoring Backend & C Edge Simulator

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Django 6.1+](https://img.shields.io/badge/django-6.1+-green.svg)](https://www.djangoproject.com/)
[![C99 Standard](https://img.shields.io/badge/C-C99-orange.svg)](https://en.wikipedia.org/wiki/C99)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, high-reliability backend and edge simulation subsystem designed for agricultural IoT monitoring devices communicating over lossy, unreliable networks.

Built for the **CredoSense Software Engineer Assessment** (Candidate: **Md Nafis Walid**).

---

## 1. System Overview

Agricultural field telemetry frequently suffers from intermittent network coverage, packet loss, duplicate transmissions, and delayed buffer flushes. This project delivers an end-to-end, cross-platform solution to address these challenges:

1. **Monitoring Backend (Django & Django REST Framework):**
   - Ingests, validates, and stores time-series environmental telemetry (air temp, leaf temp, soil moisture).
   - Guarantees **idempotency** on network retries (`200 OK`) and enforces **First-Write-Wins** (`409 Conflict`) on conflicting submissions.
   - Re-indexes late / out-of-order readings chronologically using indexed database B-Trees (`idx_device_timestamp_desc`).
   - Evaluates agronomic warning rules dynamically:
     - **Low Soil Moisture:** Latest reading $< 20.0\%$.
     - **Heat Stress:** Leaf temperature $\ge$ Air temperature $+ 4.0^\circ\text{C}$ in **both** of the last two consecutive measurements.
     - **Multi-warning:** Both conditions evaluate independently and can trigger simultaneously.
   - Built with an extensible Strategy Pattern / Dispatch Table (`WARNING_EVALUATORS`) for $O(1)$ rule additions without modifying view logic.
   - Protected against IEEE 754 floating-point precision drift (`round(val, 2)`), concurrency race conditions, and unbounded memory consumption (`?limit=N`).

2. **Selected Additional Task: Option A — Device Simulator in C:**
   - Standard C99 edge simulator (`simulator/simulator.c`) that models 3 distinct devices across 9 deterministic network and hardware fault scenarios.
   - Emits dynamic ISO 8601 UTC timestamps (`time(NULL)` + `gmtime_r` / `gmtime_s`) into `telemetry_stream.json`.
   - Zero-dependency Python bridge (`simulator/bridge.py`) dispatches packets via HTTP POST and verifies live warning engine state.
   - Complete architectural analysis of **Reliability Division of Responsibilities** (Device vs. Backend vs. Shared) in [`simulator/README.md`](file:///Users/shajninhaqueaishy/AI-Work/CredoSense-Assessment/simulator/README.md).

3. **Technical Explanation & Review Report:**
   - Detailed answers to all assessment questions in [`docs/EXPLANATION.md`](file:///Users/shajninhaqueaishy/AI-Work/CredoSense-Assessment/docs/EXPLANATION.md).

---

## 2. Cross-Platform Setup & Installation

The application runs locally without any paid services or external database servers. It supports **macOS, Linux, and Windows** out-of-the-box.

### Prerequisites
- Python 3.10 or higher
- C Compiler (`gcc`, `clang`, or MinGW on Windows)

---

### macOS & Linux Setup

```bash
# 1. Clone repository and navigate to folder
git clone <repo-url>
cd CredoSense-Assessment

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env

# 5. Apply database migrations
python manage.py migrate

# 6. Run automated test suite
python manage.py test

# 7. Start Django development server
python manage.py runserver
```

---

### Windows Setup (PowerShell / Command Prompt)

```powershell
# 1. Navigate to project directory
cd CredoSense-Assessment

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env

# 5. Apply database migrations
python manage.py migrate

# 6. Run automated test suite
python manage.py test

# 7. Start Django development server
python manage.py runserver
```

---

## 3. Running Automated Tests

The automated test suite (`monitoring/tests.py`) contains **18 exhaustive test cases** covering boundary value analysis (BVA), concurrency, idempotency, and alert rules:

```bash
python manage.py test
```

### Verified Test Suite Capabilities:
- ✅ `test_successful_measurement_ingestion`: Normal payload ingestion (`201 Created`).
- ✅ `test_reject_naive_timestamp`: Rejection of timestamps without explicit timezone (`400 Bad Request`).
- ✅ `test_soil_moisture_valid_boundary_values`: Strict BVA validation for $0.0\%$, $0.1\%$, $99.9\%$, $100.0\%$.
- ✅ `test_soil_moisture_invalid_boundary_values`: Rejection of out-of-bounds soil moisture ($-0.1\%$, $101.0\%$).
- ✅ `test_temperature_boundary_validation`: Rejection of unphysical temperature noise ($< -40^\circ\text{C}$ or $> 85^\circ\text{C}$).
- ✅ `test_reject_uninitialized_rtc_epoch_1970`: Uninitialized RTC (Epoch 1970) hardware rejection.
- ✅ `test_idempotent_duplicate_handling`: Network retries acknowledge existing data (`200 OK`) without duplicating records.
- ✅ `test_conflicting_duplicate_preserves_first_write`: Same timestamp with conflicting values returns `409 Conflict`.
- ✅ `test_race_condition_conflict_handling_under_integrity_error`: Database `IntegrityError` safely verifies conflict under race conditions.
- ✅ `test_float_rounding_idempotency`: IEEE 754 precision drift does not trigger false conflicts.
- ✅ `test_out_of_order_measurements_ordered_chronologically`: Delayed readings ordered descending in B-Tree.
- ✅ `test_multi_device_isolation`: Multi-device telemetry strictly partitioned.
- ✅ `test_device_history_limit_parameter`: Bounded pagination (`?limit=N`) prevents memory exhaustion.
- ✅ `test_normal_conditions_no_warnings`: Returns empty warning list `[]` for healthy crops.
- ✅ `test_low_soil_moisture_warning_triggered`: Triggers warning at moisture $< 20.0\%$.
- ✅ `test_heat_stress_requires_two_consecutive_readings`: Exactly 1 reading is insufficient; 2 consecutive readings trigger alert.
- ✅ `test_simultaneous_low_moisture_and_heat_stress_warnings`: Multi-warning independent and simultaneous activation.
- ✅ `test_nonexistent_device_returns_404`: Clean error handling for unknown device IDs.

---

## 4. Running the C IoT Edge Simulator (Option A)

The C simulator generates a realistic multi-device telemetry stream simulating network packet loss, late arrivals, duplicates, and physical alert thresholds.

### Option 1: Using Makefile (macOS / Linux / MinGW)

In a separate terminal (while Django is running):
```bash
cd simulator
make run
```

### Option 2: Direct Execution (Any OS)

**macOS / Linux:**
```bash
# 1. Compile C program
gcc -Wall -Wextra -O2 -std=c99 simulator/simulator.c -o simulator/simulator

# 2. Run simulator to generate JSON stream
./simulator/simulator

# 3. Dispatch stream to Django backend via Python bridge
python3 simulator/bridge.py
```

**Windows:**
```powershell
# 1. Compile C program
gcc -Wall -Wextra -O2 -std=c99 simulator/simulator.c -o simulator/simulator.exe

# 2. Run simulator
.\simulator\simulator.exe

# 3. Dispatch stream via Python bridge
python simulator\bridge.py
```

### Live Simulator Output Sample:
```text
======================================================================
 CredoSense Telemetry Bridge: C Engine -> Django Backend
======================================================================
[+] Loaded 9 packets from simulator/telemetry_stream.json
[+] Target Ingest Endpoint: http://127.0.0.1:8000/api/measurements/

----------------------------------------------------------------------
#   | Status          | Device ID              | Scenario
----------------------------------------------------------------------
01  | 201 CREATED     | device-open-field-01   | 1. Nominal In-Range Telemetry
02  | 200 OK (DUP)    | device-open-field-01   | 2. Network Retry (Identical Duplicate)
03  | 201 CREATED     | device-open-field-01   | 3. Delayed Buffered Telemetry (Late / Out-of-Order)
04  | 201 CREATED     | device-greenhouse-02   | 4. Drought Condition + Heat Stress Reading 1
05  | 201 CREATED     | device-greenhouse-02   | 5. Consecutive Heat Stress Reading 2
06  | 400 REJECTED    | device-faulty-03       | 6. ADC Sensor Corruption (Soil Moisture > 100%)
07  | 400 REJECTED    | device-faulty-03       | 7. Corrupted Thermal Probe (Air Temp > 85C)
08  | 201 CREATED     | device-faulty-03       | 8. Initial Telemetry for Conflict Baseline
09  | 409 CONFLICT    | device-faulty-03       | 9. Conflicting Duplicate (Same TS, Different Values)
----------------------------------------------------------------------

======================================================================
 Live Device Status & Agronomic Warnings Verification
======================================================================
[>] Device: device-greenhouse-02 (Status endpoint: HTTP 200)
    Latest Timestamp : 2026-11-06T12:45:16Z
    Air Temp / Leaf  : 26.0°C / 31.5°C
    Soil Moisture    : 13.8%
    Active Warnings  :
      - Low Soil Moisture: Current soil moisture is 13.8% (threshold: < 20.0%).
      - Heat Stress: Leaf temperature exceeded air temperature by >= 4.0°C in both of the last 2 readings.

[>] Device: device-open-field-01 (Status endpoint: HTTP 200)
    Active Warnings  : None (Operating Normally)
    Out-of-Order Sorting: 2026-11-06T12:43:26Z -> 2026-11-06T10:45:26Z (B-Tree Sorted DESC)
```

---

## 5. API Reference & Example Requests

Base URL: `http://127.0.0.1:8000/api/`

### 1. Ingest Measurement
- **Endpoint:** `POST /api/measurements/`
- **Headers:** `Content-Type: application/json`

```bash
curl -X POST http://127.0.0.1:8000/api/measurements/ \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "sensor-alpha-01",
    "timestamp": "2026-11-06T12:00:00Z",
    "air_temperature": 25.5,
    "leaf_temperature": 30.0,
    "soil_moisture": 18.5
  }'
```

**Responses:**
- `201 Created`: Telemetry successfully validated and stored.
- `200 OK`: Telemetry already processed (Idempotent duplicate retry).
- `409 Conflict`: Telemetry timestamp already recorded with conflicting sensor values (First-Write-Wins).
- `400 Bad Request`: Validation failure (naive timestamp, unphysical temperature/moisture values).

---

### 2. Device History
- **Endpoint:** `GET /api/devices/{device_id}/history/?limit=100`

```bash
curl -X GET "http://127.0.0.1:8000/api/devices/device-greenhouse-02/history/?limit=2"
```

**Sample Response (`200 OK`):**
```json
[
  {
    "id": 5,
    "device_id": "device-greenhouse-02",
    "timestamp": "2026-11-06T12:45:16Z",
    "air_temperature": 26.0,
    "leaf_temperature": 31.5,
    "soil_moisture": 13.8,
    "received_at": "2026-11-06T12:45:33.412890Z"
  },
  {
    "id": 4,
    "device_id": "device-greenhouse-02",
    "timestamp": "2026-11-06T12:44:26Z",
    "air_temperature": 25.0,
    "leaf_temperature": 30.0,
    "soil_moisture": 14.5,
    "received_at": "2026-11-06T12:45:33.398210Z"
  }
]
```

---

### 3. Latest Device Status & Active Warnings
- **Endpoint:** `GET /api/devices/{device_id}/status/`

```bash
curl -X GET http://127.0.0.1:8000/api/devices/device-greenhouse-02/status/
```

**Sample Response (`200 OK`):**
```json
{
  "device_id": "device-greenhouse-02",
  "latest_measurement": {
    "id": 5,
    "device_id": "device-greenhouse-02",
    "timestamp": "2026-11-06T12:45:16Z",
    "air_temperature": 26.0,
    "leaf_temperature": 31.5,
    "soil_moisture": 13.8,
    "received_at": "2026-11-06T12:45:33.412890Z"
  },
  "warnings": [
    "Low Soil Moisture: Current soil moisture is 13.8% (threshold: < 20.0%).",
    "Heat Stress: Leaf temperature exceeded air temperature by >= 4.0°C in both of the last 2 readings."
  ]
}
```

---

## 6. Directory Structure

```text
CredoSense-Assessment/
├── manage.py                     # Django management CLI
├── requirements.txt              # Core Python dependencies
├── .env.example                  # Environment configuration template
├── README.md                     # Comprehensive project guide (this file)
├── config/                       # Project configuration
│   ├── settings.py               # Django configuration (decoupled via .env)
│   ├── urls.py                   # Root URL routing
│   ├── wsgi.py                   # Production WSGI entrypoint
│   └── asgi.py                   # Production ASGI entrypoint
├── monitoring/                   # Telemetry backend application
│   ├── models.py                 # Measurement model & database constraints
│   ├── serializers.py            # Strict DRF input validation & ISO 8601 parser
│   ├── views.py                  # Ingest, History, Status & Warning dispatchers
│   ├── urls.py                   # Application route endpoints
│   ├── constants.py              # Centralized agronomic & physical thresholds
│   └── tests.py                  # 18 comprehensive automated test cases
├── simulator/                    # Task 2: Option A — C Device Simulator
│   ├── simulator.c               # Standard C99 multi-device telemetry generator
│   ├── bridge.py                 # Zero-dependency Python HTTP ingestion bridge
│   ├── Makefile                  # Cross-platform build & run automation
│   ├── README.md                 # Detailed division of reliability responsibilities
│   └── DESIGN.md                 # Original architecture specification document
└── docs/                         # Technical documentation & supporting files
    ├── EXPLANATION.md            # Technical review questionnaire & decisions
    └── supporting_documents/     # Reference RFC standards (RFC 5905, RFC 1350)
```

---

## 7. Technical Review Documentation

For the in-depth technical explanation covering unfamiliar topics, end-to-end data flow, investigated bugs, architectural trade-offs, production improvements, and AI verification methodology, please refer to:

👉 **[`docs/EXPLANATION.md`](file:///Users/shajninhaqueaishy/AI-Work/CredoSense-Assessment/docs/EXPLANATION.md)**
