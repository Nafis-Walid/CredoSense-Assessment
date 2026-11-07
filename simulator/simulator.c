/**
 * ============================================================================
 * C IoT Edge Telemetry Simulator (Option A)
 * ============================================================================
 * Author: Md Nafis Walid
 * Target: CredoSense Software Engineer Assessment
 *
 * Description:
 * Minimal, lightweight C99 device simulator. Generates simulated telemetry
 * across the 5 core assessment requirements:
 *   1. Normal readings     (UTC Zulu and local timezone offset)
 *   2. Late readings       (2 hours delayed offline buffer packet)
 *   3. Duplicate readings  (Network retry idempotency & mutated conflict)
 *   4. Warning conditions  (Low soil moisture & consecutive heat stress)
 *   5. Invalid data        (Physical envelope & ADC sensor glitches)
 *
 * Usage:
 *   ./simulator                # Generate telemetry for default device
 *   ./simulator <device_id>    # Generate telemetry for custom device
 * ============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct {
    const char *tag;
    int time_delta_sec;         /* Relative time delta in seconds */
    int tz_offset_mins;         /* Timezone offset minutes (0 = UTC, +360 = +06:00) */
    double air_temp;            /* Air temperature (°C) */
    double leaf_temp;           /* Leaf temperature (°C) */
    double soil_moisture;       /* Soil moisture (%) */
    int expected_status;        /* Target HTTP status (201, 200, 400, 409) */
} Scenario;

/**
 * The 5 Core Assessment Categories:
 */
static const Scenario g_scenarios[] = {
    /* 1. Normal Readings */
    { "Nominal Telemetry (UTC Zulu)",              -180,    0, 24.5, 23.8, 45.0, 201 },
    { "Local Offset (+06:00 Timezone Telemetry)",  -120, +360, 24.5, 23.8, 45.0, 201 },

    /* 2. Late Readings (Arrives 2 hours after other readings) */
    { "Delayed Buffer Transmission (Late Reading)",-7200,    0, 24.5, 23.8, 45.0, 201 },

    /* 3. Duplicate Readings (Exact same timestamp: -180s) */
    { "Network Retry Duplicate (Identical)",       -180,    0, 24.5, 23.8, 45.0, 200 },
    { "Conflicting Retransmission (Mutated Temp)", -180,    0, 35.0, 23.8, 45.0, 409 },

    /* 4. Warning Conditions (Low soil moisture & consecutive heat stress) */
    { "Low Soil Moisture Warning Ingestion",        -60,    0, 25.0, 30.0, 14.5, 201 },
    { "Consecutive Heat Stress Confirmation",       -30,    0, 26.0, 31.5, 14.0, 201 },

    /* 5. Invalid Data (Out-of-bounds ADC glitch & thermal envelope boundary) */
    { "Broken Pin ADC Glitch (Soil > 100%)",        -20,    0, 24.5, 23.8, 150.0, 400 },
    { "Thermal Probe Corruption (Air > 85°C)",      -15,    0, 95.0, 23.8, 45.0, 400 },

    { NULL, 0, 0, 0, 0, 0, 0 } /* Sentinel */
};

/**
 * Formats epoch timestamp into ISO 8601 string (UTC 'Z' or '+HH:MM' offset).
 */
static void format_iso8601(time_t epoch, int tz_mins, char *out, size_t size) {
    time_t shifted = epoch + (tz_mins * 60);
    struct tm tm_buf;
#if defined(_WIN32) || defined(_WIN64)
    gmtime_s(&tm_buf, &shifted);
#else
    gmtime_r(&shifted, &tm_buf);
#endif
    if (tz_mins == 0) {
        strftime(out, size, "%Y-%m-%dT%H:%M:%SZ", &tm_buf);
    } else {
        char base[20];
        strftime(base, sizeof(base), "%Y-%m-%dT%H:%M:%S", &tm_buf);
        char sign = (tz_mins >= 0) ? '+' : '-';
        int abs_m = abs(tz_mins);
        snprintf(out, size, "%s%c%02d:%02d", base, sign, abs_m / 60, abs_m % 60);
    }
}

/**
 * Writes formatted JSON array directly to specified destination stream.
 */
static void write_telemetry_json(FILE *fp, const char *device_id, time_t now) {
    char ts[32];
    fprintf(fp, "[\n");
    for (int i = 0; g_scenarios[i].tag != NULL; i++) {
        const Scenario *s = &g_scenarios[i];
        format_iso8601(now + s->time_delta_sec, s->tz_offset_mins, ts, sizeof(ts));
        fprintf(fp, "  {\n"
                    "    \"device_id\": \"%s\",\n"
                    "    \"timestamp\": \"%s\",\n"
                    "    \"air_temperature\": %.1f,\n"
                    "    \"leaf_temperature\": %.1f,\n"
                    "    \"soil_moisture\": %.1f,\n"
                    "    \"scenario_tag\": \"%s\",\n"
                    "    \"expected_status\": %d\n"
                    "  }%s\n",
                device_id, ts, s->air_temp, s->leaf_temp, s->soil_moisture,
                s->tag, s->expected_status,
                (g_scenarios[i + 1].tag != NULL) ? "," : "");
    }
    fprintf(fp, "]\n");
}

int main(int argc, char *argv[]) {
    const char *device_id = (argc > 1) ? argv[1] : "sensor-node-01";
    const char *out_path = "telemetry_stream.json";
    time_t now = time(NULL);

    FILE *fp = fopen(out_path, "w");
    if (!fp) {
        perror("[!] Failed to open output file");
        return EXIT_FAILURE;
    }

    write_telemetry_json(fp, device_id, now);
    fclose(fp);

    /* Stream clean JSON to stdout */
    write_telemetry_json(stdout, device_id, now);
    fprintf(stderr, "\n[+] Successfully generated 9 packets into: %s\n", out_path);

    return EXIT_SUCCESS;
}
