/**
 * ============================================================================
 * C IoT Edge Telemetry Simulator
 * ============================================================================
 * Author: Md Nafis Walid
 * Target: CredoSense Software Engineer Assessment (Option A - Device Simulator)
 *
 * Description:
 * Generates authentic multi-device environmental telemetry records simulating
 * edge conditions over unreliable networks:
 * - Nominal telemetry packets
 * - Network duplicate packets (Idempotent retry)
 * - Out-of-order packets (Delayed buffer transmission)
 * - Warning conditions (Low soil moisture & consecutive heat stress)
 * - Conflicting submissions (Same timestamp, mutated payload)
 * - Corrupted / Out-of-bounds sensor readings
 *
 * Output: Formats and streams records as a valid JSON array into
 *         'telemetry_stream.json' for ingestion via Python bridge.
 * ============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdbool.h>

#define MAX_DEVICE_ID_LEN   64
#define MAX_TIMESTAMP_LEN   32
#define MAX_TAG_LEN         80
#define DEFAULT_OUTPUT_FILE "simulator/telemetry_stream.json"

/**
 * Representation of a single wire-format telemetry packet.
 */
typedef struct {
    char device_id[MAX_DEVICE_ID_LEN];
    char timestamp_iso[MAX_TIMESTAMP_LEN]; // Explicit UTC 'Z' ISO 8601
    double air_temperature;
    double leaf_temperature;
    double soil_moisture;
    char scenario_tag[MAX_TAG_LEN];
    const char *expected_outcome;
} TelemetryPacket;

/**
 * Formats epoch timestamp into explicit ISO 8601 UTC string (e.g. 2026-11-06T12:00:00Z).
 */
static void format_iso8601_utc(time_t epoch, char *out_buf, size_t buf_size) {
    struct tm gm_tm;
#if defined(_WIN32) || defined(_WIN64)
    gmtime_s(&gm_tm, &epoch);
#else
    gmtime_r(&epoch, &gm_tm);
#endif
    strftime(out_buf, buf_size, "%Y-%m-%dT%H:%M:%SZ", &gm_tm);
}

/**
 * Resolves output filepath dynamically whether executed from project root
 * or directly inside the simulator/ directory.
 */
static const char *resolve_output_path(int argc, char *argv[]) {
    if (argc > 1) {
        return argv[1];
    }
    FILE *fp = fopen("simulator/telemetry_stream.json", "a");
    if (fp) {
        fclose(fp);
        return "simulator/telemetry_stream.json";
    }
    return "telemetry_stream.json";
}

int main(int argc, char *argv[]) {
    const char *output_path = resolve_output_path(argc, argv);
    time_t now = time(NULL);

    printf("============================================================\n");
    printf(" CredoSense Agricultural IoT Edge Simulator (C99)\n");
    printf("============================================================\n");
    printf("[+] Base Reference Time (UTC): ");
    char base_time_str[MAX_TIMESTAMP_LEN];
    format_iso8601_utc(now, base_time_str, sizeof(base_time_str));
    printf("%s\n\n", base_time_str);

    // Pre-calculate dynamic timestamps for test packet sequencing
    char ts_dev1_nominal[MAX_TIMESTAMP_LEN];
    char ts_dev1_late[MAX_TIMESTAMP_LEN];
    char ts_dev2_p1[MAX_TIMESTAMP_LEN];
    char ts_dev2_p2[MAX_TIMESTAMP_LEN];
    char ts_dev3_bad_soil[MAX_TIMESTAMP_LEN];
    char ts_dev3_bad_temp[MAX_TIMESTAMP_LEN];
    char ts_dev3_conflict[MAX_TIMESTAMP_LEN];

    format_iso8601_utc(now - 120, ts_dev1_nominal, sizeof(ts_dev1_nominal));  // 2 mins ago
    format_iso8601_utc(now - 7200, ts_dev1_late, sizeof(ts_dev1_late));        // 2 hours ago (out of order)
    format_iso8601_utc(now - 60, ts_dev2_p1, sizeof(ts_dev2_p1));             // 1 min ago
    format_iso8601_utc(now - 10, ts_dev2_p2, sizeof(ts_dev2_p2));             // 10 secs ago
    format_iso8601_utc(now - 45, ts_dev3_bad_soil, sizeof(ts_dev3_bad_soil));
    format_iso8601_utc(now - 40, ts_dev3_bad_temp, sizeof(ts_dev3_bad_temp));
    format_iso8601_utc(now - 20, ts_dev3_conflict, sizeof(ts_dev3_conflict));

    /**
     * Deterministic Multi-Device Telemetry Sequence:
     * 3 independent devices covering all requirements and edge cases.
     */
    TelemetryPacket packets[] = {
        // --- Device 1: Open Field Monitoring Node ---
        {
            .device_id = "device-open-field-01",
            .air_temperature = 24.5,
            .leaf_temperature = 23.8,
            .soil_moisture = 48.0,
            .scenario_tag = "1. Nominal In-Range Telemetry",
            .expected_outcome = "201 Created"
        },
        {
            .device_id = "device-open-field-01",
            .air_temperature = 24.5,
            .leaf_temperature = 23.8,
            .soil_moisture = 48.0,
            .scenario_tag = "2. Network Retry (Identical Duplicate)",
            .expected_outcome = "200 OK (Idempotent ACK)"
        },
        {
            .device_id = "device-open-field-01",
            .air_temperature = 22.0,
            .leaf_temperature = 21.5,
            .soil_moisture = 50.0,
            .scenario_tag = "3. Delayed Buffered Telemetry (Late / Out-of-Order)",
            .expected_outcome = "201 Created (B-Tree Sorted)"
        },

        // --- Device 2: Greenhouse Node (Drought & Heat Stress Alerts) ---
        {
            .device_id = "device-greenhouse-02",
            .air_temperature = 25.0,
            .leaf_temperature = 30.0, // Delta = +5.0C >= 4.0C
            .soil_moisture = 14.5,    // < 20.0% Low Soil Moisture
            .scenario_tag = "4. Drought Condition + Heat Stress Reading 1",
            .expected_outcome = "201 Created (Low Moisture Active)"
        },
        {
            .device_id = "device-greenhouse-02",
            .air_temperature = 26.0,
            .leaf_temperature = 31.5, // Delta = +5.5C >= 4.0C (2nd consecutive)
            .soil_moisture = 13.8,    // Still < 20.0%
            .scenario_tag = "5. Consecutive Heat Stress Reading 2",
            .expected_outcome = "201 Created (Both Warnings Active!)"
        },

        // --- Device 3: Defective Sensor Node (Corrupt ADC & Conflict) ---
        {
            .device_id = "device-faulty-03",
            .air_temperature = 25.0,
            .leaf_temperature = 24.0,
            .soil_moisture = 150.0,   // Unphysical: > 100%
            .scenario_tag = "6. ADC Sensor Corruption (Soil Moisture > 100%)",
            .expected_outcome = "400 Bad Request (Rejected)"
        },
        {
            .device_id = "device-faulty-03",
            .air_temperature = 95.0,  // Unphysical: > 85C physical limit
            .leaf_temperature = 25.0,
            .soil_moisture = 40.0,
            .scenario_tag = "7. Corrupted Thermal Probe (Air Temp > 85C)",
            .expected_outcome = "400 Bad Request (Rejected)"
        },
        {
            .device_id = "device-faulty-03",
            .air_temperature = 22.0,
            .leaf_temperature = 21.0,
            .soil_moisture = 45.0,
            .scenario_tag = "8. Initial Telemetry for Conflict Baseline",
            .expected_outcome = "201 Created"
        },
        {
            .device_id = "device-faulty-03",
            .air_temperature = 32.0,  // Conflicting air temp (was 22.0)
            .leaf_temperature = 30.0,
            .soil_moisture = 45.0,
            .scenario_tag = "9. Conflicting Duplicate (Same TS, Different Values)",
            .expected_outcome = "409 Conflict (Preserved First Write)"
        }
    };

    // Assign dynamic timestamps to packet sequence
    strncpy(packets[0].timestamp_iso, ts_dev1_nominal, sizeof(packets[0].timestamp_iso));
    strncpy(packets[1].timestamp_iso, ts_dev1_nominal, sizeof(packets[1].timestamp_iso)); // Exact same TS
    strncpy(packets[2].timestamp_iso, ts_dev1_late, sizeof(packets[2].timestamp_iso));    // Older TS arriving after
    strncpy(packets[3].timestamp_iso, ts_dev2_p1, sizeof(packets[3].timestamp_iso));
    strncpy(packets[4].timestamp_iso, ts_dev2_p2, sizeof(packets[4].timestamp_iso));
    strncpy(packets[5].timestamp_iso, ts_dev3_bad_soil, sizeof(packets[5].timestamp_iso));
    strncpy(packets[6].timestamp_iso, ts_dev3_bad_temp, sizeof(packets[6].timestamp_iso));
    strncpy(packets[7].timestamp_iso, ts_dev3_conflict, sizeof(packets[7].timestamp_iso));
    strncpy(packets[8].timestamp_iso, ts_dev3_conflict, sizeof(packets[8].timestamp_iso)); // Exact same TS, different data

    size_t total_packets = sizeof(packets) / sizeof(packets[0]);

    // Open output JSON file safely
    FILE *fp = fopen(output_path, "w");
    if (!fp) {
        perror("[!] Failed to open output JSON file");
        return EXIT_FAILURE;
    }

    fprintf(fp, "[\n");
    for (size_t i = 0; i < total_packets; i++) {
        fprintf(fp, "  {\n");
        fprintf(fp, "    \"device_id\": \"%s\",\n", packets[i].device_id);
        fprintf(fp, "    \"timestamp\": \"%s\",\n", packets[i].timestamp_iso);
        fprintf(fp, "    \"air_temperature\": %.1f,\n", packets[i].air_temperature);
        fprintf(fp, "    \"leaf_temperature\": %.1f,\n", packets[i].leaf_temperature);
        fprintf(fp, "    \"soil_moisture\": %.1f,\n", packets[i].soil_moisture);
        fprintf(fp, "    \"scenario_tag\": \"%s\"\n", packets[i].scenario_tag);
        fprintf(fp, "  }%s\n", (i + 1 < total_packets) ? "," : ""); // Prevent trailing comma syntax error
    }
    fprintf(fp, "]\n");
    fclose(fp);

    printf("[+] Successfully generated %zu telemetry packets.\n", total_packets);
    printf("[+] Output written to: %s\n\n", output_path);

    printf("Generated Scenario Matrix:\n");
    printf("------------------------------------------------------------------------------------\n");
    printf("%-3s | %-22s | %-20s | %-32s\n", "#", "Device ID", "Timestamp (UTC)", "Scenario Description");
    printf("------------------------------------------------------------------------------------\n");
    for (size_t i = 0; i < total_packets; i++) {
        printf("%02zu  | %-22s | %-20s | %s\n",
               i + 1,
               packets[i].device_id,
               packets[i].timestamp_iso,
               packets[i].scenario_tag);
    }
    printf("------------------------------------------------------------------------------------\n");
    printf("\nExecute 'python simulator/bridge.py' to dispatch these packets to Django backend.\n");

    return EXIT_SUCCESS;
}
