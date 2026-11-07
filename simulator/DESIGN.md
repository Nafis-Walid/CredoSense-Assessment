# Design of IoT Edge Telemetry Simulator Module

**Candidate:** Md Nafis Walid  
**Target Position:** Software Engineer at CredoSense  
**Assessment:** Task 2: Option A — Device Simulator in C  
**Language Standard:** ISO/IEC 9899:1999 (C99)  

---

## 1. Introduction

### 1.1 Purpose
This document specifies the software design for the C IoT Edge Telemetry Simulator module (Task 2: Option A). The simulator emulates autonomous agricultural IoT sensor nodes transmitting environmental measurements over intermittent, unreliable networks. Its primary purpose is to deterministically generate edge conditions across the 5 assessment categories—including normal telemetry, delayed buffer flushes, network retries, consecutive heat stress warnings, and corrupt sensor readings—and serialize them into a structured JSON stream for cloud backend validation.

### 1.2 Module Scope
The module is self-contained and implemented entirely in portable C99 (`simulator/simulator.c`). It decouples telemetry generation from network transmission by writing records to a local stream file (`telemetry_stream.json`), which is subsequently dispatched by an external transport adapter (Python ingestion bridge `simulator/bridge.py`).

---

## 2. Architecture

The simulator module is implemented as a clean, single-file C99 program (`simulator.c`) structured into four distinct logical layers:
1. **Scenario Configuration Table:** Static declarative array of the 5 assessment categories.
2. **Timing & ISO 8601 Engine:** Reentrant timestamp calculation supporting UTC Zulu (`'Z'`) and local offsets (`'+06:00'`).
3. **JSON Stream Serializer:** Direct file and standard output stream formatting.
4. **Execution Controller (`main`):** CLI argument handling and execution flow.

```
┌────────────────────────────────────────────────────────┐
│            Execution Controller (main)                 │
│   - CLI device ID resolver (default: sensor-node-01)   │
│   - Time sampling (time(NULL))                         │
└───────────────────────────┬────────────────────────────┘
                            │ Calls serializer
                            ▼
┌────────────────────────────────────────────────────────┐
│         JSON Stream Serializer (write_telemetry_json)  │
│   - Writes to telemetry_stream.json                    │
│   - Streams valid JSON to stdout (UNIX pipeline)       │
└───────────────────────────┬────────────────────────────┘
                            │ Iterates scenario table & formats timing
                            ▼
┌────────────────────────────────────────────────────────┐
│         Timing Engine & 5-Category Scenario Table      │
│   - format_iso8601(): UTC Zulu ('Z') & Local Offset    │
│   - Declarative 5-Category Scenarios (9 Packets)       │
└────────────────────────────────────────────────────────┘
```

---

## 3. Data Specification

### 3.1 Data Structures

#### 3.1.1 `Scenario`
Represents the declarative configuration of an edge scenario:
```c
typedef struct {
    const char *tag;            /* Descriptive scenario identifier */
    int time_delta_sec;         /* Relative time offset from sample epoch (seconds) */
    int tz_offset_mins;         /* Timezone offset minutes (0 = UTC Zulu, +360 = +06:00) */
    double air_temp;            /* Ambient air temperature in Celsius (°C) */
    double leaf_temp;           /* Crop canopy/leaf temperature in Celsius (°C) */
    double soil_moisture;       /* Volumetric soil water content percentage (%) */
    int expected_status;        /* Target HTTP response code (201, 200, 400, 409) */
} Scenario;
```

---

## 4. Control Procedures & Data Flow

```
main(argc, argv)
   │
   ├──> 1. Parse device_id (argv[1] or default "sensor-node-01")
   ├──> 2. Sample baseline epoch (time(NULL))
   │
   ├──> 3. fopen("telemetry_stream.json", "w")
   │
   ├──> 4. write_telemetry_json(fp, device_id, now)
   │       └── Loops g_scenarios[]:
   │           ├── format_iso8601(now + time_delta, tz_offset, ts_buf)
   │           └── fprintf(fp, JSON format)
   │
   ├──> 5. fclose(fp)
   │
   └──> 6. write_telemetry_json(stdout, device_id, now)
           └── Streams identical JSON to stdout for UNIX pipes (./simulator | jq .)
```

---

## 5. Functional Specifications

### 5.1 `format_iso8601`
- **Prototype:** `static void format_iso8601(time_t epoch, int tz_mins, char *out, size_t size);`
- **Description:** Formats a given epoch timestamp into ISO 8601 format. If `tz_mins == 0`, produces UTC Zulu format (`YYYY-MM-DDTHH:MM:SSZ`). Otherwise, calculates local offset and produces numeric offset format (`YYYY-MM-DDTHH:MM:SS+HH:MM`).
- **Portability:** Uses thread-safe `gmtime_r` on POSIX systems (Linux/macOS) and `gmtime_s` on Windows.

### 5.2 `write_telemetry_json`
- **Prototype:** `static void write_telemetry_json(FILE *fp, const char *device_id, time_t now);`
- **Description:** Iterates through the static `g_scenarios` array, formats dynamic timestamps, and streams standard JSON objects into the target `FILE*` stream.

---

## 6. Build and Execution

```bash
# Compile with strict compiler flags
gcc -Wall -Wextra -std=c99 -pedantic -O2 simulator.c -o simulator

# Run with default device ID
./simulator

# Run with custom device ID
./simulator greenhouse-node-42
```
