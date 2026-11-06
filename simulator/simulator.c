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

#define MAX_DEVICE_ID_LEN   64
#define MAX_TIMESTAMP_LEN   32
#define MAX_TAG_LEN         80
#define MAX_SCENARIOS       16

typedef struct {
    char device_id[MAX_DEVICE_ID_LEN];
    char timestamp_iso[MAX_TIMESTAMP_LEN];
    double air_temperature;
    double leaf_temperature;
    double soil_moisture;
    char scenario_tag[MAX_TAG_LEN];
    int expected_status;
} TelemetryPacket;

typedef struct {
    const char *scenario_tag;   /* Description */
    int time_delta_sec;         /* Relative time delta in seconds */
    int tz_offset_mins;         /* Timezone offset minutes (0 = UTC, +360 = +06:00) */
    double air_temp;            /* Air temperature (°C) */
    double leaf_temp;           /* Leaf temperature (°C) */
    double soil_moisture;       /* Soil moisture (%) */
    int expected_status;        /* Target HTTP status (201, 200, 400, 409) */
} ScenarioDescriptor;

/**
 * The 5 Core Assessment Categories:
 */
static const ScenarioDescriptor g_scenarios[] = {
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
 * Resolves output file path: ENV -> default path -> fallback.
 */
static const char *get_output_path(void) {
    const char *env = getenv("TELEMETRY_STREAM_FILE");
    if (env && *env) return env;

    FILE *fp = fopen("simulator/telemetry_stream.json", "a");
    if (fp) { fclose(fp); return "simulator/telemetry_stream.json"; }
    return "telemetry_stream.json";
}

/**
 * Streams formatted JSON array to specified destination (file or stdout).
 */
static void write_json(FILE *fp, const TelemetryPacket *p, int count) {
    fprintf(fp, "[\n");
    for (int i = 0; i < count; i++) {
        fprintf(fp, "  {\n"
                    "    \"device_id\": \"%s\",\n"
                    "    \"timestamp\": \"%s\",\n"
                    "    \"air_temperature\": %.1f,\n"
                    "    \"leaf_temperature\": %.1f,\n"
                    "    \"soil_moisture\": %.1f,\n"
                    "    \"scenario_tag\": \"%s\",\n"
                    "    \"expected_status\": %d\n"
                    "  }%s\n",
                p[i].device_id, p[i].timestamp_iso,
                p[i].air_temperature, p[i].leaf_temperature, p[i].soil_moisture,
                p[i].scenario_tag, p[i].expected_status,
                (i + 1 < count) ? "," : "");
    }
    fprintf(fp, "]\n");
}

int main(int argc, char *argv[]) {
    const char *device_id = (argc > 1) ? argv[1] : "sensor-node-01";
    const char *out_path = get_output_path();
    time_t now = time(NULL);
    TelemetryPacket packets[MAX_SCENARIOS];
    int count = 0;

    for (int i = 0; g_scenarios[i].scenario_tag != NULL && count < MAX_SCENARIOS; i++) {
        const ScenarioDescriptor *s = &g_scenarios[i];
        TelemetryPacket *p = &packets[count++];

        strncpy(p->device_id, device_id, sizeof(p->device_id) - 1);
        p->device_id[sizeof(p->device_id) - 1] = '\0';

        format_iso8601(now + s->time_delta_sec, s->tz_offset_mins, p->timestamp_iso, sizeof(p->timestamp_iso));

        p->air_temperature = s->air_temp;
        p->leaf_temperature = s->leaf_temp;
        p->soil_moisture = s->soil_moisture;

        strncpy(p->scenario_tag, s->scenario_tag, sizeof(p->scenario_tag) - 1);
        p->scenario_tag[sizeof(p->scenario_tag) - 1] = '\0';

        p->expected_status = s->expected_status;
    }

    FILE *fp = fopen(out_path, "w");
    if (!fp) {
        perror("[!] Failed to open output JSON file");
        return EXIT_FAILURE;
    }
    write_json(fp, packets, count);
    fclose(fp);

    /* Stream clean JSON to stdout */
    write_json(stdout, packets, count);
    fprintf(stderr, "\n[+] Successfully generated %d packets into: %s\n", count, out_path);

    return EXIT_SUCCESS;
}
