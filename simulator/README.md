# IoT Edge Telemetry Simulator in C (Option A)

**Author:** Md Nafis Walid  
**Role:** Software Engineer (Mobile App Backend Management / IoT Integration)

---

## 1. Overview

This subsystem implements **Task 2: Option A (Device simulator in C)** for the CredoSense assessment. It simulates realistic agricultural IoT edge devices transmitting sensor telemetry across an unreliable network connection to the Django monitoring cloud backend.

The subsystem consists of two decoupled, robust components:
1. **C Simulator Engine (`simulator.c`):** High-performance, standard C99 program that generates deterministic telemetry records with realistic network anomalies and writes them to `telemetry_stream.json`.
2. **Python Ingestion Bridge (`bridge.py`):** Zero-dependency Python script (using standard `urllib.request`) that dispatches the generated records over HTTP to the Django backend (`/api/measurements/`) and verifies device status and warnings.

---

## 2. Multi-Device Test Scenarios Covered

The simulator models **three distinct physical edge devices** to verify multi-device isolation and core domain rules:

| # | Device ID | Scenario Description | Network / Hardware Condition | Expected HTTP Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **01** | `device-open-field-01` | Nominal Telemetry | Normal cellular backhaul transmission | `201 Created` |
| **02** | `device-open-field-01` | Network Retry (Duplicate) | ACK packet lost in transit; device retransmits | `200 OK (Idempotent)` |
| **03** | `device-open-field-01` | Delayed Buffer Transmission | Device was offline; buffered reading arrives 2 hours late | `201 Created (B-Tree Sorted)` |
| **04** | `device-greenhouse-02` | Drought & Heat Stress 1 | Soil moisture $14.5\%$ (< 20%); Leaf temp $30.0^\circ\text{C}$ vs Air $25.0^\circ\text{C}$ | `201 Created (Low Soil Moisture Alert)` |
| **05** | `device-greenhouse-02` | Consecutive Heat Stress 2 | 2nd consecutive reading with $\Delta \ge 4.0^\circ\text{C}$ ($31.5^\circ\text{C}$ vs $26.0^\circ\text{C}$) | `201 Created (Both Warnings Active!)` |
| **06** | `device-faulty-03` | ADC Glitch (Soil Moisture) | Damaged sensor pin reads $150.0\%$ (out of bounds) | `400 Bad Request (Rejected)` |
| **07** | `device-faulty-03` | Thermal Probe Corruption | Faulty thermocouple reads $95.0^\circ\text{C}$ (> physical envelope) | `400 Bad Request (Rejected)` |
| **08** | `device-faulty-03` | Conflict Baseline | Initial valid reading at timestamp $T$ | `201 Created` |
| **09** | `device-faulty-03` | Conflicting Duplicate | Corrupted retransmission with same timestamp $T$ but mutated air temperature | `409 Conflict (First Write Preserved)` |

---

## 3. Division of Reliability Responsibilities (Device vs. Backend vs. Both)

As specified in the assessment requirements, real-world IoT systems require a clear architectural boundary between what must be handled by the Edge Device, what must be handled by the Cloud Backend, and what requires shared collaboration:

```
┌──────────────────────────────────────┐       ┌──────────────────────────────────────┐
│        Device Responsibilities       │       │       Backend Responsibilities       │
├──────────────────────────────────────┤       ├──────────────────────────────────────┤
│ 1. Local Flash/EEPROM Storage Buffer │       │ 1. Idempotency (Duplicate ack)       │
│ 2. Exponential Backoff & Jitter      │       │ 2. Immutable First-Write Audit Guard │
│ 3. Hardware ADC Sanity Filtering     │       │ 3. Chronological B-Tree Re-indexing  │
│ 4. Network Time Synchronization      │       │ 4. Rejection of Future Clock Skew    │
│ 5. Explicit Timezone Emission (UTC)  │       │ 5. Multi-Device Isolation Assurance  │
└──────────────────┬───────────────────┘       └──────────────────┬───────────────────┘
                   │                                              │
                   └──────────────────────┬───────────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────┐
                       │        Both (Shared Contracts)      │
                       ├─────────────────────────────────────┤
                       │ - ISO 8601 UTC Timestamp Agreement  │
                       │ - Standard Schema & Physical Bounds │
                       │ - End-to-End Delivery Ack Protocol  │
                       └─────────────────────────────────────┘
```

### Detailed Breakdown:

1. **Problems that should be handled by the DEVICE:**
   - **Network Disconnections & Buffer Management:** When cellular/LoRa/Wi-Fi signal drops, the device must buffer unsent telemetry in local non-volatile flash memory (FIFO queue) rather than dropping data.
   - **Retry Storm Prevention:** Retries must use exponential backoff with random jitter to prevent overwhelming the backend when network connectivity restores.
   - **Local Sensor Sanity Checks:** Physical ADC electrical failures (open circuit, short circuit) should be detected locally before transmitting garbage packets over expensive cellular bandwidth.
   - **Clock Synchronization:** The device is responsible for periodically synchronizing its internal Real-Time Clock (RTC) via cellular NITZ, NTP (RFC 5905), or BLE provisioning app, and emitting ISO 8601 timestamps with explicit UTC timezone indicator (`Z`).

2. **Problems that should be handled by the BACKEND:**
   - **Duplicate Ingestion & Idempotency:** Because unreliable networks cause lost ACK packets, devices will inevitably retry. The backend must enforce database uniqueness constraints `(device_id, timestamp)` and acknowledge identical retransmissions with `200 OK` without creating duplicate records.
   - **Conflicting Values (First Write Wins):** If a retransmission contains mutated values for an already recorded timestamp, the backend must preserve the physical audit truth of the first recorded observation and return `409 Conflict`.
   - **Out-of-Order Sorting:** Edge devices flushes buffered readings after reconnecting, causing older timestamps to arrive after newer ones. The backend database index `(device_id, -timestamp)` automatically orders them chronologically in $O(\log N)$ B-Tree insertion.
   - **Multi-Device Isolation:** High-throughput telemetry from multiple concurrent devices must be strictly partitioned and queried independently.

3. **Problems handled by BOTH:**
   - **Wire Protocol & Schema Contract:** Both layers must adhere to strict serialization types (temperatures in °C, moisture in 0–100%).
   - **Timezone Standardization:** The device must explicitly format timestamps in UTC (`Z`), and the backend must validate and reject naive (timezone-unaware) timestamps.

---

## 4. How to Build & Run

### Prerequisites
- GCC or Clang (Standard C99)
- Python 3.8+ (Standard Library only; no `pip install` required)
- Running Django server (`python manage.py runserver`)

### Step 1: Start Django Backend
In terminal 1:
```bash
python manage.py runserver
```

### Step 2: Compile & Run Simulator
In terminal 2:
```bash
cd simulator

# Option A: Using Makefile
make run

# Option B: Manual execution
gcc -Wall -Wextra -O2 -std=c99 simulator.c -o simulator
./simulator
python3 bridge.py
```
