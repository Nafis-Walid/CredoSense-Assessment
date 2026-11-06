# Design of IoT Edge Telemetry Simulator Module

**Author:** Md Nafis Walid  
**Document Version:** 1.0.0  
**Language Standard:** ISO/IEC 9899:1999 (C99)  

---

## 1. Introduction

### 1.1 Purpose
This document specifies the software design for the C IoT Edge Telemetry Simulator module. The simulator emulates autonomous agricultural IoT sensor nodes transmitting environmental measurements over intermittent cellular/LPWAN networks. Its primary purpose is to deterministically generate edge conditions—including nominal telemetry, network retries, out-of-order packets, consecutive heat stress warnings, and corrupt sensor readings—and serialize them into a structured JSON stream for cloud backend validation.

### 1.2 Module Scope
The module is self-contained and implemented entirely in portable C99. It decouples telemetry generation from network transmission by writing records to a local stream file (`telemetry_stream.json`), which is subsequently dispatched by an external transport adapter (Python ingestion bridge).

---

## 2. Architecture

The simulator module is divided into three decoupled layers:
1. **Entrypoint Layer (`main.c`):** Minimal execution hook.
2. **Telemetry Domain Layer (`src/packet.h`, `src/packet.c`):** Data contracts, timestamp generation (UTC Zulu and local timezone offsets), and deterministic edge scenario generation.
3. **Application & I/O Layer (`src/app.h`, `src/app.c`):** Configuration resolution, atomic file serialization, and terminal status presentation.

```
┌────────────────────────────────────────────────────────┐
│               Main Entrypoint (main.c)                 │
└───────────────────────────┬────────────────────────────┘
                            │ Calls run_simulator()
                            ▼
┌────────────────────────────────────────────────────────┐
│            Application Controller (src/app.h)          │
│   - Configuration & Path Resolver                      │
│   - Stream Serializer (File I/O)                       │
│   - Terminal Summary Table Renderer                    │
└───────────────────────────┬────────────────────────────┘
                            │ Invokes packet generators
                            ▼
┌────────────────────────────────────────────────────────┐
│         Telemetry & Scenario Engine (src/packet.h)     │
│   - ISO 8601 UTC Zulu ('Z') Formatter                  │
│   - ISO 8601 Local Offset ('+06:00') Formatter         │
│   - Deterministic 9-Scenario Array Builder             │
└────────────────────────────────────────────────────────┘
```

---

## 3. Data Specification

### 3.1 Macro Definitions

#### 3.1.1 Buffer Capacities & Limits
```c
#define SIM_MAX_DEVICE_ID_LEN   64      /* Maximum length of device identifier string */
#define SIM_MAX_TIMESTAMP_LEN   32      /* Capacity for RFC 3339 / ISO 8601 timestamps */
#define SIM_MAX_TAG_LEN         80      /* Capacity for scenario description text */
#define SIM_MAX_SCENARIOS       16      /* Maximum packet capacity in static buffer */
#define SIM_MAX_PATH_LEN        256     /* Maximum file system path length */
```

#### 3.1.2 Configuration & Default Paths
```c
#define SIM_DEFAULT_OUTPUT_FILE "simulator/telemetry_stream.json"
#define SIM_ENV_OUTPUT_KEY      "TELEMETRY_STREAM_FILE"
#define SIM_FALLBACK_FILE       "telemetry_stream.json"
```

#### 3.1.3 Physical Sensor Envelope Boundaries
```c
#define SIM_AIR_TEMP_MIN        -40.0   /* Valid operational air temperature minimum (°C) */
#define SIM_AIR_TEMP_MAX         85.0   /* Valid operational air temperature maximum (°C) */
#define SIM_SOIL_MOISTURE_MIN     0.0   /* Absolute minimum soil moisture percentage (%) */
#define SIM_SOIL_MOISTURE_MAX   100.0   /* Absolute maximum soil moisture percentage (%) */
```

#### 3.1.4 Return & Status Codes
```c
#define SIM_SUCCESS              0      /* Operation completed successfully */
#define SIM_ERR_INVALID_PARAM   -1      /* NULL pointer or invalid buffer size argument */
#define SIM_ERR_FILE_IO         -2      /* Failed to open, write, or flush output file */
#define SIM_ERR_BUFFER_OVERFLOW -3      /* Provided buffer too small for generated data */
```

---

### 3.2 Data Structures

#### 3.2.1 `TelemetryPacket`
Represents the wire-format state of a single sensor transmission:
```c
typedef struct {
    char device_id[SIM_MAX_DEVICE_ID_LEN];        /* Alphanumeric sensor node ID */
    char timestamp_iso[SIM_MAX_TIMESTAMP_LEN];    /* Formatted ISO 8601 event timestamp */
    double air_temperature;                       /* Ambient air temperature in Celsius */
    double leaf_temperature;                      /* Crop canopy/leaf temperature in Celsius */
    double soil_moisture;                         /* Volumetric soil water content percentage */
    char scenario_tag[SIM_MAX_TAG_LEN];           /* Descriptive scenario identifier */
    int expected_status;                          /* Target HTTP response code (201, 200, 400, 409) */
    const char *expected_outcome;                 /* Summary of expected backend action */
} TelemetryPacket;
```

---

## 4. Control Procedures & Data Flow

```
run_simulator(argc, argv)
   │
   ├──> 1. resolve_output_path(argc, argv)
   │       ├── Check argv[1] != NULL
   │       ├── Check getenv(SIM_ENV_OUTPUT_KEY) != NULL
   │       └── Fallback to SIM_DEFAULT_OUTPUT_FILE / SIM_FALLBACK_FILE
   │
   ├──> 2. generate_telemetry_scenarios(packet_buffer, SIM_MAX_SCENARIOS)
   │       ├── Sample reference time (time(NULL))
   │       ├── Format UTC Zulu timestamps via format_iso8601_utc()
   │       ├── Format local offset timestamps via format_iso8601_offset()
   │       └── Populate 9 deterministic test scenarios
   │
   ├──> 3. write_telemetry_stream(output_path, packet_buffer, count)
   │       ├── fopen(output_path, "w")
   │       ├── Serialize valid JSON array structure
   │       └── fclose()
   │
   └──> 4. print_summary_table(packet_buffer, count, output_path)
           └── Render formatted ASCII table to stdout
```

---

## 5. Interface Specifications (Header Files)

### 5.1 `src/packet.h`

#### 5.1.1 `format_iso8601_utc`
- **Prototype:** `int format_iso8601_utc(time_t epoch, char *out_buf, size_t buf_size);`
- **Description:** Converts an epoch timestamp into standard ISO 8601 / RFC 3339 UTC Zulu format (`YYYY-MM-DDTHH:MM:SSZ`) using `gmtime_r` / `gmtime`.
- **Arguments:**
  - `epoch`: POSIX epoch timestamp in seconds.
  - `out_buf`: Destination character buffer.
  - `buf_size`: Capacity of `out_buf` in bytes (must be $\ge 21$).
- **Return Value:** `SIM_SUCCESS` (0) on success, or `SIM_ERR_INVALID_PARAM` (-1).

#### 5.1.2 `format_iso8601_offset`
- **Prototype:** `int format_iso8601_offset(time_t epoch, int offset_minutes, char *out_buf, size_t buf_size);`
- **Description:** Converts an epoch timestamp into ISO 8601 format with an explicit numeric timezone offset (e.g., `+06:00` for $+360$ minutes).
- **Arguments:**
  - `epoch`: POSIX epoch timestamp in seconds.
  - `offset_minutes`: Timezone offset in minutes from UTC (e.g. $+360$ for Asia/Dhaka).
  - `out_buf`: Destination character buffer.
  - `buf_size`: Capacity of `out_buf` in bytes (must be $\ge 26$).
- **Return Value:** `SIM_SUCCESS` (0) on success, or `SIM_ERR_INVALID_PARAM` (-1).

#### 5.1.3 `generate_telemetry_scenarios`
- **Prototype:** `int generate_telemetry_scenarios(TelemetryPacket *packets, size_t max_packets);`
- **Description:** Populates the destination array with 9 deterministic edge scenarios simulating nominal conditions, network anomalies, and sensor hardware faults.
- **Arguments:**
  - `packets`: Pointer to array of `TelemetryPacket` structs.
  - `max_packets`: Maximum elements the array can receive.
- **Return Value:** Count of populated packets on success ($> 0$), or `SIM_ERR_INVALID_PARAM` (-1).

---

### 5.2 `src/app.h`

#### 5.2.1 `resolve_output_path`
- **Prototype:** `const char *resolve_output_path(int argc, char *argv[]);`
- **Description:** Resolves the output destination path according to strict 3-tier precedence: CLI parameter $\rightarrow$ Environment variable $\rightarrow$ Default file system macro.
- **Arguments:**
  - `argc`: Argument count from `main()`.
  - `argv`: Argument vector from `main()`.
- **Return Value:** Pointer to resolved null-terminated path string.

#### 5.2.2 `write_telemetry_stream`
- **Prototype:** `int write_telemetry_stream(const char *filepath, const TelemetryPacket *packets, int count);`
- **Description:** Opens the target file in write mode and formats the array of `TelemetryPacket` records into a syntactically valid JSON array.
- **Arguments:**
  - `filepath`: Path to output file.
  - `packets`: Array of packets to serialize.
  - `count`: Number of packets in array.
- **Return Value:** `SIM_SUCCESS` (0) on success, or `SIM_ERR_FILE_IO` (-2).

#### 5.2.3 `print_summary_table`
- **Prototype:** `void print_summary_table(const TelemetryPacket *packets, int count, const char *output_file);`
- **Description:** Prints a structured, bordered ASCII summary of generated scenarios and output targets to standard output.
- **Arguments:**
  - `packets`: Array of packets.
  - `count`: Number of packets.
  - `output_file`: Final resolved path string.

#### 5.2.4 `run_simulator`
- **Prototype:** `int run_simulator(int argc, char *argv[]);`
- **Description:** Main module controller. Initializes packet data, resolves configuration, invokes the stream writer, and reports execution status.
- **Arguments:**
  - `argc`: Argument count from `main()`.
  - `argv`: Argument vector from `main()`.
- **Return Value:** `SIM_SUCCESS` (0) on completion, non-zero error code on failure.
