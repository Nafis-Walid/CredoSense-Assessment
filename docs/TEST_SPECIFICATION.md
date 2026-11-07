# Telemetry Edge Verification & Boundary Test Specification

**Candidate:** Md Nafis Walid  
**Target Position:** Software Engineer at CredoSense  
**Assessment:** Boundary Value Analysis & Edge Test Specification  
**Methodology:** Boundary Value Analysis (BVA), Equivalence Partitioning (EP), and Golden Packet Mutation Testing  

---

## 1. Testing Philosophy & The Golden Packet Mutation Strategy

### 1.1 The Golden Packet Mutation Pattern
In embedded protocol testing and RFC conformance verification, redefining complete multi-field data structures for every edge test creates code duplication and introduces secondary confounding variables.

To guarantee rigorous test isolation, this test suite adopts the **Golden Packet Mutation Pattern**:
1. **Baseline Golden Packet:** A single canonical telemetry struct is defined where every field is certified 100% valid, nominal, and conflict-free.
2. **Atomic Field Mutation:** For each test case, the baseline packet is cloned, and **strictly one target field** is mutated into its boundary or invalid state.
3. **Causality Isolation:** If the ingestion endpoint rejects the packet with `400 Bad Request`, the failure is mathematically guaranteed to originate from the single mutated variable, not an accidental side effect in adjacent fields.

```
       ┌────────────────────────────────────────────────────────┐
       │             Canonical Golden Packet Template           │
       │  device_id:        "device-open-field-01"              │
       │  timestamp_iso:    "2026-11-06T12:00:00Z" (Valid UTC)  │
       │  air_temperature:  25.0 °C                             │
       │  leaf_temperature: 24.0 °C                             │
       │  soil_moisture:    45.0 %                              │
       └───────────────────────────┬────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       [ Mutation A ]       [ Mutation B ]       [ Mutation C ]
       soil_moisture=150%   air_temp=-45.0°C     timestamp="1970-01-01"
       (ADC Glitch)         (Sub-zero Envelope)  (Uninitialized RTC)
              │                    │                    │
              ▼                    ▼                    ▼
         Expected:            Expected:            Expected:
       400 Bad Request      400 Bad Request      400 Bad Request
```

---

## 2. Complete Test Matrix (36 Boundary & Edge Scenarios across 13 Test Suites)

### Category A: Timestamp, Timezone & RTC Clock Boundaries (7 Tests)

| Test ID | Mutated Field | Injected Value | Timezone Mode | Expected HTTP | Validation Invariant |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TS-01** | `timestamp_iso` | `2026-11-06T12:00:00Z` | Standard UTC Zulu | `201 Created` | Standard ingest & ISO 8601 parsing |
| **TS-02** | `timestamp_iso` | `2026-11-06T18:00:00+06:00` | Positive Offset (+6h) | `201 Created` | Normalized to UTC equivalent instant |
| **TS-03** | `timestamp_iso` | `2026-11-06T07:00:00-05:00` | Negative Offset (-5h) | `201 Created` | Normalized to UTC equivalent instant |
| **TS-04** | `timestamp_iso` | `1970-01-01T00:00:00Z` | Unix Epoch Zero | `400 Bad Request` | Detects hardware uninitialized RTC clock |
| **TS-05** | `timestamp_iso` | `1969-12-31T23:59:59Z` | Negative Unix Epoch | `400 Bad Request` | Pre-epoch timestamp rejection |
| **TS-06** | `timestamp_iso` | `2026-11-06T12:00:00` | Naive (No Offset) | `400 Bad Request` | Rejects ambiguous timezone-unaware ISO |
| **TS-07** | `timestamp_iso` | `"invalid-iso-string"` | Malformed String | `400 Bad Request` | RFC 3339 regex rejection |

---

### Category B: Soil Moisture Boundaries ($0.0\%$ to $100.0\%$) (8 Tests)

| Test ID | Mutated Field | Injected Value | Condition | Expected HTTP | Warning Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SM-01** | `soil_moisture` | `0.0` | Exact Lower Bound | `201 Created` | Low soil moisture warning active |
| **SM-02** | `soil_moisture` | `-0.1` | Below Lower Bound | `400 Bad Request` | Rejected (Negative ADC voltage) |
| **SM-03** | `soil_moisture` | `-15.0` | Gross Negative Error | `400 Bad Request` | Rejected (Physical impossibility) |
| **SM-04** | `soil_moisture` | `100.0` | Exact Upper Bound | `201 Created` | No moisture warning |
| **SM-05** | `soil_moisture` | `100.1` | Above Upper Bound | `400 Bad Request` | Rejected (ADC pin short/surge) |
| **SM-06** | `soil_moisture` | `150.0` | Gross Out of Bounds | `400 Bad Request` | Rejected (Hardware fault) |
| **SM-07** | `soil_moisture` | `19.9` | Just Below Threshold | `201 Created` | Low soil moisture warning active |
| **SM-08** | `soil_moisture` | `20.0` | Exact Alert Threshold | `201 Created` | No moisture warning (rule: `< 20%`) |

---

### Category C: Air Temperature Operational Envelope ($-40.0^\circ\text{C}$ to $+85.0^\circ\text{C}$) (6 Tests)

| Test ID | Mutated Field | Injected Value | Condition | Expected HTTP | Invariant |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AT-01** | `air_temperature` | `-40.0` | Exact Lower Bound | `201 Created` | Valid extreme cold agricultural reading |
| **AT-02** | `air_temperature` | `-40.1` | Below Operational Envelope | `400 Bad Request` | Rejects sub-envelope temperature |
| **AT-03** | `air_temperature` | `-55.0` | Sensor Disconnect Floor | `400 Bad Request` | Rejects pulled-down ADC float |
| **AT-04** | `air_temperature` | `85.0` | Exact Upper Bound | `201 Created` | Valid extreme greenhouse reading |
| **AT-05** | `air_temperature` | `85.1` | Above Operational Envelope | `400 Bad Request` | Rejects super-envelope temperature |
| **AT-06** | `air_temperature` | `95.0` | Thermocouple Burnout | `400 Bad Request` | Rejects shorted thermal probe |

---

### Category D: Leaf Temperature & Heat Stress Differential ($\Delta = \text{Leaf} - \text{Air}$) (4 Tests)

| Test ID | Air Temp | Leaf Temp | Differential ($\Delta$) | Sequence | Expected HTTP | Heat Stress Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **HS-01** | `25.0` | `29.0` | $+4.0^\circ\text{C}$ | 1st Reading | `201 Created` | `false` (Requires $\ge 2$ consecutive) |
| **HS-02** | `25.0` | `29.0` | $+4.0^\circ\text{C}$ | 2nd Consecutive | `201 Created` | **`true` (Heat stress warning active)** |
| **HS-03** | `25.0` | `28.9` | $+3.9^\circ\text{C}$ | 2nd Reading | `201 Created` | `false` (Sub-threshold breaks streak) |
| **HS-04** | `25.0` | `30.5` | $+5.5^\circ\text{C}$ | 2nd Reading + Soil 14% | `201 Created` | **`true` (Both warnings active simultaneously)** |

---

### Category E: Network Reliability, Idempotency & Concurrency (5 Tests)

| Test ID | Scenario | Injected Condition | Expected HTTP | Architectural Guarantee |
| :--- | :--- | :--- | :--- | :--- |
| **NW-01** | Idempotent Duplicate | Identical payload sent twice for same `(device_id, timestamp)` | `200 OK` | Safe retry handling; database row count remains 1 |
| **NW-02** | Conflicting Duplicate | Same `(device_id, timestamp)` but mutated `air_temperature` | `409 Conflict` | First-Write-Wins audit guard preserves original reading |
| **NW-03** | Out-of-Order Delivery | Reading with timestamp $T - 2\text{ hours}$ arrives after $T$ | `201 Created` | Descending B-Tree index chronologically sorts events |
| **NW-04** | Race Condition Collision | Simulated IntegrityError during concurrent conflicting write | `409 Conflict` | Re-fetch winner record strictly enforces conflict rejection |
| **NW-05** | Float Precision Drift | Micro-precision difference ($25.00000000000001$) | `200 OK` | `round(val, 2)` prevents false conflict triggers |

---

### Category F: Schema Validation & Query Guards (6 Tests)

| Test ID | Scenario | Injected Condition | Expected HTTP | Invariant |
| :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Empty Device ID | `device_id: ""` | `400 Bad Request` | Rejects empty identifier string |
| **SC-02** | Missing Required Field | Payload omitted `soil_moisture` | `400 Bad Request` | Enforces mandatory field schema constraint |
| **SC-03** | Non-Numeric Temperature | `air_temperature: "twenty-five"` | `400 Bad Request` | Enforces float data type validation |
| **SC-04** | Multi-Device Isolation | Telemetry for device A queried vs device B | `200 OK` | Strict data partition between devices |
| **SC-05** | Unknown Device 404 | Query status or history for nonexistent device | `404 Not Found` | Clean error handling for unknown nodes |
| **SC-06** | History Limit Bounds | Query `?limit=-5` or `?limit=not-a-number` | `200 OK` | Safe bounds fallback (default 100, max 1000) |
