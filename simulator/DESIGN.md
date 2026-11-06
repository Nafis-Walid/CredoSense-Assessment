# System Architecture & Technical Design Specification
## C IoT Telemetry Simulator with Cristian's Time Synchronization & Python Ingestion Bridge

**Author:** Md Nafis Walid  
**Role:** Systems / Embedded Firmware & Backend Engineer  
**Reference Standards & Supporting Documents:** 
- [RFC 5905: Network Time Protocol (NTP) Official IETF Specification](file:///Users/shajninhaqueaishy/AI-Work/CredoSense-Assessment/docs/supporting_documents/rfc5905.pdf)
- [RFC 1350: The TFTP Protocol Official IETF Specification](file:///Users/shajninhaqueaishy/AI-Work/CredoSense-Assessment/docs/supporting_documents/rfc1350.pdf)
- ISO 8601 (Representation of dates and times)

---

## 1. Architectural Overview & Design Philosophy

The objective of this subsystem is to simulate authentic agricultural IoT edge nodes transmitting telemetry across an unreliable network to the Django monitoring cloud backend.

Rather than hardcoding static JSON payloads, the simulator is designed as a **modular C firmware harness** that incorporates:
1. **Dynamic Device Registration:** Multiple independent sensor nodes with discrete operating states.
2. **Cristian's Time Synchronization Algorithm:** Clock synchronization with round-trip latency ($\text{RTT}/2$) compensation.
3. **Deterministic Fault & Scenario Engine:** Systematic generation of nominal packets, hardware alert states, network retries (idempotency), clock desynchronization, and corrupted sensor data.
4. **Decoupled Ingestion Pipeline:** C engine formats and streams structured telemetry to an intermediate file (`telemetry_stream.json`), which a Python bridge forwards to the backend API via HTTP `POST`.

```
                  ┌──────────────────────────────────────────────┐
                  │          C Simulator (simulator.c)           │
                  │  - Device Registry Table                     │
                  │  - Cristian's Algo (Latency Compensated Sync)│
                  │  - Telemetry Scenario Generator              │
                  └──────────────────────┬───────────────────────┘
                                         │ Writes Structured JSON Stream
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │         simulator/telemetry_stream.json       │
                  └──────────────────────┬───────────────────────┘
                                         │ Reads & Dispatches HTTP POST
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │          Python Bridge (bridge.py)           │
                  │  - Multiplexes Packets to Django Endpoint    │
                  │  - Formats Latency, Status Codes (201/200/409)│
                  └──────────────────────┬───────────────────────┘
                                         │ HTTP Ingestion
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │       Django Telemetry Backend (/api/)       │
                  │  - Idempotency & Conflict Guard              │
                  │  - Agronomic Warning Engine                  │
                  └──────────────────────────────────────────────┘
```

---

## 2. Core Modules & Data Structures (`telemetry.h`)

Following the modular C design principles (similar to the TFTP daemon and packet management architecture), header definitions and implementation logic are strictly separated.

### 2.1 Device Node Representation
Each registered edge device maintains its own identity, hardware status, and synchronized local clock state:

```c
typedef enum {
    DEVICE_STATE_UNINITIALIZED = 0,
    DEVICE_STATE_TIME_SYNCED   = 1,
    DEVICE_STATE_DRIFTED_FAULT = 2
} DeviceClockState;

typedef struct {
    char device_id[64];
    DeviceClockState clock_state;
    time_t local_clock_epoch;   // Internal RTC counter
    double clock_drift_rate;    // Simulated hardware crystal drift
} DeviceNode;
```

### 2.2 Telemetry Packet Representation
Represents the wire-format physical measurement:

```c
typedef struct {
    char device_id[64];
    char timestamp_iso[32];     // Formatted ISO 8601 with explicit 'Z' (e.g. 2026-11-05T18:45:00Z)
    double air_temperature;
    double leaf_temperature;
    double soil_moisture;
    char scenario_tag[64];      // Human-readable test scenario label
} TelemetryPacket;
```

### 2.3 Scenario Dispatch Table (Table-Driven Engine)
Instead of hardcoding imperative loops, packet generation is driven by a dispatch table of test scenarios:

```c
typedef enum {
    SCENARIO_NOMINAL,
    SCENARIO_LOW_SOIL_MOISTURE,
    SCENARIO_HEAT_STRESS_P1,
    SCENARIO_HEAT_STRESS_P2,
    SCENARIO_IDEMPOTENT_DUPLICATE,
    SCENARIO_CONFLICTING_DUPLICATE,
    SCENARIO_OUT_OF_ORDER_LATE,
    SCENARIO_INVALID_OUT_OF_BOUNDS
} ScenarioType;

typedef struct {
    ScenarioType type;
    const char *target_device_id;
    double air_temp;
    double leaf_temp;
    double soil_moisture;
    int time_offset_seconds;    // Relative delta from device's synchronized RTC
    const char *description;
} ScenarioRule;
```

---

## 3. Cristian's Algorithm: Latency-Compensated Time Synchronization

### 3.1 The Network Latency Problem
When an IoT device requests time over cellular or LoRa backhaul, network transit time creates clock skew. Setting the clock directly to the server's response time causes the device to lag by the transit delay.

### 3.2 Protocol Sequence
```
   Device (Client)                                          Server / App Gateway
         │                                                           │
    (T0) │ ─── 1. Time Request ────────────────────────────────────> │
         │                                                           │ (T1) Server receives
         │                                                           │ (T2) Server replies
         │ <─── 2. Time Response (T1, T2) ────────────────────────── │
    (T3) │
         ▼
```

### 3.3 Mathematical Formulation
1. **Round Trip Time (RTT):**
   $$\delta = (T_3 - T_0) - (T_2 - T_1)$$
2. **One-Way Delay Assumption (Symmetric Transit):**
   $$\text{Transit Delay} = \frac{\delta}{2}$$
3. **Synchronized Device Clock:**
   $$\text{Device Clock} = T_2 + \frac{\delta}{2}$$

### 3.4 C Implementation Model
```c
time_t sync_device_clock_cristian(time_t t0, time_t t1, time_t t2, time_t t3) {
    time_t rtt = (t3 - t0) - (t2 - t1);
    time_t one_way_delay = rtt / 2;
    return t2 + one_way_delay;
}
```

---

## 4. Multi-Device Test Scenarios Matrix

The simulator instantiates **three distinct device nodes** to thoroughly prove multi-device isolation and domain behavior:

| Node ID | Physical Role | Executed Scenarios | Expected Backend Outcome |
| :--- | :--- | :--- | :--- |
| `sensor-open-field-01` | Normal agricultural crop field | 1. Nominal telemetry<br>2. Idempotent duplicate (same packet twice)<br>3. Out-of-order packet (2 hrs late) | - `201 Created`<br>- `200 OK` (idempotent)<br>- `201 Created` (ordered in B-Tree) |
| `sensor-greenhouse-02` | Controlled greenhouse with drought & heating | 1. Low soil moisture (< 20%)<br>2. Heat stress reading 1 (Leaf $\ge$ Air + 4°C)<br>3. Heat stress reading 2 (Consecutive) | - `201 Created` (Low Moisture Warning)<br>- `201 Created` (No warning yet)<br>- `201 Created` (Heat Stress Active) |
| `sensor-faulty-node-03` | Malfunctioning edge sensor / Corrupted ADC | 1. Out-of-bounds soil moisture (150.0%)<br>2. Conflicting duplicate (first write wins) | - `400 Bad Request` (Rejected)<br>- `409 Conflict` (First write preserved) |

---

## 5. Division of Reliability Responsibilities

As required by the specification, the design establishes a clear boundary between Device and Backend obligations:

```
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     Device Responsibilities     │       │     Backend Responsibilities    │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ 1. Local Flash Storage (Buffer) │       │ 1. Idempotency (Duplicate ack)  │
│ 2. Exponential Backoff Retries  │       │ 2. Immutable First-Write Audit  │
│ 3. Sensor Circuit Sanity Checks │       │ 3. B-Tree Out-of-Order Sorting  │
│ 4. Periodic NTP / Cristian Sync │       │ 4. Future Clock Drift Rejection │
│ 5. Explicit Timezone Emission   │       │ 5. Multi-Device Isolation Guard │
└─────────────────────────────────┘       └─────────────────────────────────┘
```

---

## 6. Build & Automation (`Makefile`)

- **Compile Target:** `gcc -Wall -Wextra -O2 -std=c99 simulator/simulator.c -o simulator/simulator`
- **Execution Target:**
  1. Compiles and executes `simulator/simulator`.
  2. Generates `simulator/telemetry_stream.json`.
  3. Executes `python simulator/bridge.py` to stream packets to Django.
  4. Queries `/api/devices/{id}/status/` to print live warning state verification.
