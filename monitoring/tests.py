from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from .models import Measurement
from .constants import (
    SOIL_MOISTURE_LOW_THRESHOLD,
    HEAT_STRESS_TEMP_DELTA_THRESHOLD,
    HEAT_STRESS_CONSECUTIVE_READINGS,
    SOIL_MOISTURE_MIN_VALUE,
    SOIL_MOISTURE_MAX_VALUE,
    TEMPERATURE_MIN_VALUE,
    TEMPERATURE_MAX_VALUE,
    DEFAULT_HISTORY_LIMIT,
)


class TelemetryAPITestCase(APITestCase):
    """
    Comprehensive test suite for telemetry ingestion, network idempotency,
    query endpoints, and the agronomic warning engine.
    """

    def setUp(self):
        self.ingest_url = reverse("measurement-ingest")
        self.valid_payload = {
            "device_id": "sensor-alpha-01",
            "timestamp": "2026-11-04T10:00:00Z",
            "air_temperature": 25.0,
            "leaf_temperature": 24.5,
            "soil_moisture": 45.0,
        }

    def assert_measurement_matches_payload(self, record, payload):
        """Helper to exhaustively assert all DB fields match expected payload values."""
        self.assertEqual(record.device_id, payload["device_id"])
        self.assertEqual(record.air_temperature, payload["air_temperature"])
        self.assertEqual(record.leaf_temperature, payload["leaf_temperature"])
        self.assertEqual(record.soil_moisture, payload["soil_moisture"])
        formatted_ts = record.timestamp.isoformat().replace("+00:00", "Z")
        self.assertEqual(formatted_ts, payload["timestamp"])
        self.assertIsNotNone(record.received_at)

    # ==========================================
    # 1. Ingestion & Validation Tests
    # ==========================================

    def test_successful_measurement_ingestion(self):
        """Test standard telemetry ingestion creates record and returns 201 Created."""
        response = self.client.post(self.ingest_url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Measurement.objects.count(), 1)
        self.assert_measurement_matches_payload(Measurement.objects.first(), self.valid_payload)

    def test_reject_naive_timestamp(self):
        """Test rejection of naive timestamp without explicit timezone."""
        payload = self.valid_payload.copy()
        payload["timestamp"] = "2026-11-04T10:00:00"  # Missing 'Z' or offset
        response = self.client.post(self.ingest_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("timestamp", response.data)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_soil_moisture_valid_boundary_values(self):
        """Test exact boundary points (min, min+0.1, max-0.1, max) are accepted."""
        valid_bounds = [
            SOIL_MOISTURE_MIN_VALUE,
            SOIL_MOISTURE_MIN_VALUE + 0.1,
            SOIL_MOISTURE_MAX_VALUE - 0.1,
            SOIL_MOISTURE_MAX_VALUE,
        ]
        for idx, val in enumerate(valid_bounds):
            payload = self.valid_payload.copy()
            payload["soil_moisture"] = val
            payload["timestamp"] = f"2026-11-04T10:{idx:02d}:00Z"
            res = self.client.post(self.ingest_url, payload, format="json")
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_soil_moisture_invalid_boundary_values(self):
        """Test values just outside min and max boundaries are strictly rejected."""
        invalid_bounds = [
            SOIL_MOISTURE_MIN_VALUE - 0.1,
            SOIL_MOISTURE_MIN_VALUE - 1.0,
            SOIL_MOISTURE_MAX_VALUE + 0.1,
            SOIL_MOISTURE_MAX_VALUE + 1.0,
        ]
        for val in invalid_bounds:
            payload = self.valid_payload.copy()
            payload["soil_moisture"] = val
            res = self.client.post(self.ingest_url, payload, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("soil_moisture", res.data)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_reject_uninitialized_rtc_epoch_1970(self):
        """Test rejection of uninitialized hardware RTC clock (Epoch 1970)."""
        payload = self.valid_payload.copy()
        payload["timestamp"] = "1970-01-01T00:00:00Z"
        res = self.client.post(self.ingest_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("timestamp", res.data)

    # ==========================================
    # 2. Network Reliability & Idempotency Tests
    # ==========================================

    def test_idempotent_duplicate_handling(self):
        """Test identical duplicate payload returns 200 OK without creating extra DB row."""
        first_res = self.client.post(self.ingest_url, self.valid_payload, format="json")
        self.assertEqual(first_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Measurement.objects.count(), 1)

        second_res = self.client.post(self.ingest_url, self.valid_payload, format="json")
        self.assertEqual(second_res.status_code, status.HTTP_200_OK)
        self.assertEqual(Measurement.objects.count(), 1)
        # Verify returned data contains original database record ID and received_at timestamp
        self.assertEqual(second_res.data["id"], first_res.data["id"])
        self.assertEqual(second_res.data["received_at"], first_res.data["received_at"])

    def test_conflicting_duplicate_preserves_first_write(self):
        """Test conflicting telemetry for identical timestamp returns 409 and keeps first write."""
        first_res = self.client.post(self.ingest_url, self.valid_payload, format="json")
        self.assertEqual(first_res.status_code, status.HTTP_201_CREATED)

        conflicting_payload = self.valid_payload.copy()
        conflicting_payload["soil_moisture"] = 60.0  # Conflict
        second_res = self.client.post(self.ingest_url, conflicting_payload, format="json")
        self.assertEqual(second_res.status_code, status.HTTP_409_CONFLICT)

        record = Measurement.objects.get(device_id="sensor-alpha-01")
        self.assertEqual(record.soil_moisture, 45.0)  # Original preserved

    def test_out_of_order_measurements_ordered_chronologically(self):
        """Test late/out-of-order packets are naturally ordered by measurement timestamp."""
        # Post 10:00 reading first
        self.client.post(self.ingest_url, self.valid_payload, format="json")

        # Post 09:00 reading later (out-of-order)
        older_payload = self.valid_payload.copy()
        older_payload["timestamp"] = "2026-11-04T09:00:00Z"
        self.client.post(self.ingest_url, older_payload, format="json")

        history_url = reverse("device-history", kwargs={"device_id": "sensor-alpha-01"})
        res = self.client.get(history_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Newest first
        self.assertEqual(res.data[0]["timestamp"], "2026-11-04T10:00:00Z")
        self.assertEqual(res.data[1]["timestamp"], "2026-11-04T09:00:00Z")

    # ==========================================
    # 3. Query Endpoints & Multi-Device Isolation
    # ==========================================

    def test_nonexistent_device_returns_404(self):
        """Test history and status endpoints return 404 for unknown device."""
        history_url = reverse("device-history", kwargs={"device_id": "unknown-sensor"})
        status_url = reverse("device-status", kwargs={"device_id": "unknown-sensor"})

        self.assertEqual(self.client.get(history_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(status_url).status_code, status.HTTP_404_NOT_FOUND)

    def test_multi_device_isolation(self):
        """Test telemetry from one device does not leak into another device."""
        self.client.post(self.ingest_url, self.valid_payload, format="json")

        dev2_payload = self.valid_payload.copy()
        dev2_payload["device_id"] = "sensor-beta-02"
        dev2_payload["soil_moisture"] = 70.0
        self.client.post(self.ingest_url, dev2_payload, format="json")

        dev1_hist = self.client.get(reverse("device-history", kwargs={"device_id": "sensor-alpha-01"}))
        dev2_hist = self.client.get(reverse("device-history", kwargs={"device_id": "sensor-beta-02"}))

        self.assertEqual(len(dev1_hist.data), 1)
        self.assertEqual(len(dev2_hist.data), 1)
        self.assertEqual(dev1_hist.data[0]["device_id"], "sensor-alpha-01")
        self.assertEqual(dev2_hist.data[0]["device_id"], "sensor-beta-02")

    # ==========================================
    # 4. Agronomic Warning Engine Tests
    # ==========================================

    def test_normal_conditions_no_warnings(self):
        """Test status with nominal conditions returns empty warning list."""
        self.client.post(self.ingest_url, self.valid_payload, format="json")
        status_url = reverse("device-status", kwargs={"device_id": "sensor-alpha-01"})
        res = self.client.get(status_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["warnings"], [])

    def test_low_soil_moisture_warning_triggered(self):
        """Test low soil moisture warning boundary: below threshold triggers, exact threshold does not."""
        status_url = reverse("device-status", kwargs={"device_id": "sensor-alpha-01"})

        # 1. Exact threshold value (must NOT trigger warning)
        p_boundary = self.valid_payload.copy()
        p_boundary["soil_moisture"] = SOIL_MOISTURE_LOW_THRESHOLD
        p_boundary["timestamp"] = "2026-11-04T10:00:00Z"
        self.client.post(self.ingest_url, p_boundary, format="json")
        res_boundary = self.client.get(status_url)
        self.assertEqual(res_boundary.data["warnings"], [])

        # 2. Strictly below threshold (must trigger warning)
        p_alert = self.valid_payload.copy()
        p_alert["soil_moisture"] = SOIL_MOISTURE_LOW_THRESHOLD - 0.1
        p_alert["timestamp"] = "2026-11-04T10:05:00Z"
        self.client.post(self.ingest_url, p_alert, format="json")
        res_alert = self.client.get(status_url)
        self.assertEqual(len(res_alert.data["warnings"]), 1)
        self.assertIn("Low Soil Moisture", res_alert.data["warnings"][0])

    def test_heat_stress_requires_two_consecutive_readings(self):
        """
        Test heat stress boundary delta and consecutive readings requirement.
        """
        status_url = reverse("device-status", kwargs={"device_id": "sensor-alpha-01"})

        # Reading 1: Exactly hits the heat stress delta threshold
        p1 = self.valid_payload.copy()
        p1["timestamp"] = "2026-11-04T10:00:00Z"
        p1["air_temperature"] = 25.0
        p1["leaf_temperature"] = p1["air_temperature"] + HEAT_STRESS_TEMP_DELTA_THRESHOLD
        self.client.post(self.ingest_url, p1, format="json")

        # Must NOT trigger because only 1 reading exists (< HEAT_STRESS_CONSECUTIVE_READINGS)
        res1 = self.client.get(status_url)
        self.assertEqual(res1.data["warnings"], [])

        # Reading 2: Just below delta threshold (delta - 0.1) -> Must NOT trigger
        p2_sub = self.valid_payload.copy()
        p2_sub["timestamp"] = "2026-11-04T10:05:00Z"
        p2_sub["air_temperature"] = 25.0
        p2_sub["leaf_temperature"] = p2_sub["air_temperature"] + (HEAT_STRESS_TEMP_DELTA_THRESHOLD - 0.1)
        self.client.post(self.ingest_url, p2_sub, format="json")
        res2_sub = self.client.get(status_url)
        self.assertEqual(res2_sub.data["warnings"], [])

        # Reading 3: Exactly hits threshold -> Now last 2 readings (Reading 2 and 3) don't both satisfy.
        # Let Reading 4 also satisfy -> Now last 2 readings satisfy!
        p3 = self.valid_payload.copy()
        p3["timestamp"] = "2026-11-04T10:10:00Z"
        p3["air_temperature"] = 25.0
        p3["leaf_temperature"] = p3["air_temperature"] + HEAT_STRESS_TEMP_DELTA_THRESHOLD
        self.client.post(self.ingest_url, p3, format="json")

        p4 = self.valid_payload.copy()
        p4["timestamp"] = "2026-11-04T10:15:00Z"
        p4["air_temperature"] = 26.0
        p4["leaf_temperature"] = p4["air_temperature"] + HEAT_STRESS_TEMP_DELTA_THRESHOLD
        self.client.post(self.ingest_url, p4, format="json")

        res_final = self.client.get(status_url)
        self.assertEqual(len(res_final.data["warnings"]), 1)
        self.assertIn("Heat Stress", res_final.data["warnings"][0])

    def test_simultaneous_low_moisture_and_heat_stress_warnings(self):
        """Test both low moisture and heat stress warnings appearing together dynamically."""
        # 1st reading: Heat stress delta
        p1 = self.valid_payload.copy()
        p1["timestamp"] = "2026-11-04T10:00:00Z"
        p1["air_temperature"] = 25.0
        p1["leaf_temperature"] = p1["air_temperature"] + HEAT_STRESS_TEMP_DELTA_THRESHOLD
        self.client.post(self.ingest_url, p1, format="json")

        # 2nd reading: Heat stress delta AND low moisture (< threshold)
        p2 = self.valid_payload.copy()
        p2["timestamp"] = "2026-11-04T10:05:00Z"
        p2["air_temperature"] = 25.0
        p2["leaf_temperature"] = p2["air_temperature"] + HEAT_STRESS_TEMP_DELTA_THRESHOLD
        p2["soil_moisture"] = SOIL_MOISTURE_LOW_THRESHOLD - 1.0
        self.client.post(self.ingest_url, p2, format="json")

        status_url = reverse("device-status", kwargs={"device_id": "sensor-alpha-01"})
        res = self.client.get(status_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["warnings"]), 2)
        warning_text = " ".join(res.data["warnings"])
        self.assertIn("Low Soil Moisture", warning_text)
        self.assertIn("Heat Stress", warning_text)

    # ==========================================
    # 5. Sensor Sanity, Concurrency & Query Optimization Tests
    # ==========================================

    def test_temperature_boundary_validation(self):
        """Test rejection of air and leaf temperature values outside physical operating envelope."""
        # 1. Invalid Air Temperature (Below min & above max)
        for bad_temp in [TEMPERATURE_MIN_VALUE - 0.1, TEMPERATURE_MAX_VALUE + 0.1]:
            payload = self.valid_payload.copy()
            payload["air_temperature"] = bad_temp
            res = self.client.post(self.ingest_url, payload, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("air_temperature", res.data)

        # 2. Invalid Leaf Temperature (Below min & above max)
        for bad_temp in [TEMPERATURE_MIN_VALUE - 0.1, TEMPERATURE_MAX_VALUE + 0.1]:
            payload = self.valid_payload.copy()
            payload["leaf_temperature"] = bad_temp
            res = self.client.post(self.ingest_url, payload, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("leaf_temperature", res.data)

    def test_float_rounding_idempotency(self):
        """Test IEEE 754 precision drift does not cause false 409 conflict."""
        self.client.post(self.ingest_url, self.valid_payload, format="json")

        # Telemetry with negligible float drift (e.g. 25.000000001)
        duplicate_drift = self.valid_payload.copy()
        duplicate_drift["air_temperature"] = 25.000000001
        res = self.client.post(self.ingest_url, duplicate_drift, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_race_condition_conflict_handling_under_integrity_error(self):
        """Test IntegrityError with conflicting payload correctly responds with 409 Conflict."""
        from unittest.mock import patch
        from django.db import IntegrityError

        # Ingest initial record
        self.client.post(self.ingest_url, self.valid_payload, format="json")

        # Simulate concurrent thread attempting to write conflicting data that triggers IntegrityError
        conflicting_payload = self.valid_payload.copy()
        conflicting_payload["air_temperature"] = 35.0  # Different value

        with patch("monitoring.serializers.MeasurementSerializer.save", side_effect=IntegrityError):
            res = self.client.post(self.ingest_url, conflicting_payload, format="json")
            self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
            self.assertIn("Conflict", res.data["detail"])

    def test_device_history_limit_parameter(self):
        """Test query parameter limit caps the returned records and avoids unbounded results."""
        history_url = reverse("device-history", kwargs={"device_id": "sensor-alpha-01"})

        # Ingest 5 records
        for i in range(5):
            p = self.valid_payload.copy()
            p["timestamp"] = f"2026-11-04T10:{i:02d}:00Z"
            self.client.post(self.ingest_url, p, format="json")

        # Request with limit=2
        res = self.client.get(f"{history_url}?limit=2")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

        # Request default
        res_default = self.client.get(history_url)
        self.assertEqual(len(res_default.data), 5)
